"""手动挑片 → 自动下载 → 自动发布的一条龙入口。

程序化检索（`src.discover`）挑出来的素材质量不稳定、下载也时好时坏，所以这里不再
「自动检索 + 自动挑选」：**挑哪条由人决定**，把 YouTube 链接（或 11 位 video id）
交给本模块，后面的下载、填表、发布仍然全自动。定时任务（macOS LaunchAgent）已移除，
什么时候跑、跑哪几条都由你决定。

挑片的两种方式（都只是找候选，最终仍由人拍板）：

  1. 直接在 Chrome 里逛 YouTube，复制地址栏的链接；
  2. `python -m src.cli discover --top 10` 看按播放速度排出的候选，挑中后抄下 id / URL。

用法::

    python -m src.job https://www.youtube.com/watch?v=dQw4w9WgXcQ
    python -m src.job dQw4w9WgXcQ nRDysNZdMvU      # 多条按顺序处理（中间有抖动间隔）
    python -m src.job dQw4w9WgXcQ --no-publish     # 只填表 + 截图，停在「发表」前
    python -m src.job dQw4w9WgXcQ --dry-run        # 只校验目标与登录态，不下载、不发布

退出码：``0`` 全部成功（含 --no-publish 的「填好表等人工」）/ ``1`` 有环节失败
（目标看不懂、连不上 CDP、没下下来、发布出错、登录态失效）/ ``130`` 被 Ctrl+C 中断。

每一步都写进 `logs/mvposter_YYYY-MM-DD.log`；库里状态机随流程推进
（``found → picked → downloaded → published``，旁支 ``failed``）。
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
import traceback

from . import (browser, config, downloader, keywords as keywords_mod,
               publish as publish_mod, store)
from . import main as main_mod
from .logging import log

DEFAULT_INTERVAL = 1800  # 两条之间的基准间隔（秒）：30 分钟起，风控上比连着发安全
INTERVAL_JITTER = 0.2    # 间隔抖动比例：固定的节奏更像机器人
TITLE_LIMIT = 16         # 短标题字数上限：视频号展示更克制（页面自己的 maxlength 优先）
DEFAULT_DESC = "每天一条动物搞笑，关注不迷路～"

# ---- 文案（确定性生成，不调模型）----
# 英文动物 -> 中文话题：直接复用 keywords 的动物别名表，改一处两边都生效
_ANIMAL_ZH: dict[str, str] = {}
for _zh, _en in keywords_mod.FOCUS_ALIASES.items():
    _ANIMAL_ZH.setdefault(_en, _zh)

_URL_RE = re.compile(r"https?://\S+")
_TAG_RE = re.compile(r"[#＃]\S*")          # #shorts、#viral 这类话题标签
_BRACKET_RE = re.compile(r"[\[\]【】()（）{}<>《》「」『』]")
_SPACE_RE = re.compile(r"\s+")


def _clean_title(raw: str, limit: int = TITLE_LIMIT) -> str:
    """把视频原标题压成一条可用的「短标题」。

    规则（确定性，便于复盘）：去掉 URL / `#话题` → 只留第一个 `|` 段（竖线后面
    通常是人名或频道名）→ 去掉各种括号（`【父に挑むアル】…` 这类修饰）→ 压缩空白
    → 截到 ``limit`` 字。页面自己声明的 maxlength 更严格时，由 `src.publish` 再截一次。
    """
    text = _URL_RE.sub(" ", raw or "")
    text = _TAG_RE.sub(" ", text)
    text = text.replace("｜", "|").split("|")[0]
    text = _BRACKET_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip(" -–—·:：,，.。!！?？~～")
    if len(text) > limit:
        head = text[:limit]
        cut = head.rfind(" ")
        # 拉丁标题按词边界切，别切出 "Baby dog puppy b" 这种半截单词；
        # 中文标题没有空格，cut 会很靠前，就保持按字数截断。
        if cut >= limit * 0.5:
            head = head[:cut]
        text = head
    return text.strip()


def _tags_for(text: str, topic_display: str) -> list[str]:
    """按标题配 3~5 个中文话题（命中某动物就把它的中文名排到最前）。"""
    lowered = (text or "").lower()
    animal = next((zh for en, zh in sorted(_ANIMAL_ZH.items()) if en in lowered), None)
    ordered = [animal] if animal else []
    ordered += [topic_display, "萌宠", "搞笑动物"]
    tags: list[str] = []
    for tag in ordered:
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:5]


def _source_line(channel: str) -> str:
    """描述里的素材出处（搬运的是别人拍的内容，留一行来源更稳妥）。"""
    name = (channel or "").strip()
    return f"来源：YouTube @{name}" if name else "素材来源：YouTube"


# 人工给的目标：裸 video id 或 YouTube 链接（watch / shorts / live / youtu.be 都认）
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_ID_IN_URL_RE = re.compile(r"(?:[?&]v=|/shorts/|/live/|youtu\.be/)([A-Za-z0-9_-]{11})")


def _extract_video_id(target: str) -> str | None:
    """从「链接或裸 id」里取出 YouTube 的 11 位 video id；看不懂返回 None。"""
    text = (target or "").strip()
    if _BARE_ID_RE.match(text):
        return text
    match = _ID_IN_URL_RE.search(text)
    return match.group(1) if match else None


def _resolve_target(conn, target: str) -> dict | None:
    """把人工给的目标（链接 / id）变成一条可处理的记录；看不懂返回 None。

    库里已有的记录会带上标题、频道等观测值（`discover` 写过）；没有就先用空值，
    下载时 yt-dlp 返回的元数据会把它补上。
    """
    video_id = _extract_video_id(target)
    if not video_id:
        log(f"错误：看不懂 {target!r}——需要 YouTube 链接或 11 位 video id"
            "（`python -m src.cli discover --top 10` 会打印候选的 id 与 URL）。")
        return None

    row = store.get(conn, video_id)
    url = (target or "").strip()
    if not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={video_id}"
    if row is not None and row["url"]:
        url = row["url"]
    return {
        "video_id": video_id,
        "url": url,
        "title": (row["title"] if row is not None else "") or "",
        "channel": (row["channel"] if row is not None else "") or "",
        "channel_id": (row["channel_id"] if row is not None else "") or "",
        "views": row["views"] if row is not None else None,
        "duration": row["duration"] if row is not None else None,
        "upload_date": (row["upload_date"] if row is not None else "") or "",
        "keyword": (row["keyword"] if row is not None else "") or "",
        "score": row["score"] if row is not None else None,
        "status": row["status"] if row is not None else "found",
    }


def _check_youtube_login(context) -> bool:
    """只读预检：常驻 Chrome 里有没有 YouTube 的登录态？返回是否看起来已登录。

    yt-dlp 判断「登录了没」看的是 ``LOGIN_INFO`` 这个 cookie
    （``yt_dlp/extractor/youtube/_base.py``：``LOGIN_INFO is cleared and should
    exist if logged in``）；只有 Google 的 SSO cookie（``SID`` / ``HSID`` / …）
    而没有 ``LOGIN_INFO`` 时，YouTube 会回
    ``Sign in to confirm you're not a bot``，下载必然失败。

    实测（2026-10-15）就是这个情况：那只 Chrome 自己打不开 youtube.com（没走代理），
    于是从来没有真正登录进 YouTube，``SID`` 之类的 SSO cookie 却是有的——只看
    「有没有 SID」会误判成已登录。所以这里查 ``LOGIN_INFO``，并把补救办法写进日志。
    """
    try:
        cookies = browser._all_cookies(context)
    except Exception as exc:
        log(f"预检：读不到 cookies（{type(exc).__name__}: {exc}），跳过登录态检查。")
        return True
    names = {c.get("name") for c in cookies if "youtube" in (c.get("domain") or "")}
    if "LOGIN_INFO" in names:
        return True
    log("预检警告：常驻 Chrome 里没有 YouTube 的 LOGIN_INFO cookie，"
        "yt-dlp 会当成未登录，下载大概率被拦成「Sign in to confirm you're not a bot」。")
    log("  常见原因：那只 Chrome 自己打不开 youtube.com（没走代理），所以从没真正登录进 YouTube"
        "（SID 之类的 Google SSO cookie 是有的，光看它们会误判）。")
    log("  补救：确认那只 Chrome 能正常打开 youtube.com 后，在登录状态下访问一次 youtube.com，"
        "让 LOGIN_INFO 落地。浏览器的代理由 browserhost 决定，本项目不碰。")
    return False


def _process(context, conn, item: dict, args, index: int, total: int) -> str:
    """处理一条人工选中的目标（下载 + 发布），推进状态机并返回结果标记。"""
    video_id = item["video_id"]
    log("-" * 60)
    log(f"[{index}/{total}] {video_id} | {item.get('title') or '（标题待下载时补全）'}")
    log(f"[{index}/{total}] {item.get('url')}")
    log(f"[{index}/{total}] 频道：{item.get('channel') or '（待下载时补全）'}")

    store.upsert(conn, item)                      # 新的入 found，旧的只刷观测值
    store.mark(conn, video_id, "picked", note="人工挑片（src.job）")

    # 1) 下载：借常驻 Chrome 的 cookies 交给 yt-dlp；顺带接住它返回的元数据
    meta: dict = {}
    path = main_mod.download_once(context, item["url"], item.get("title") or "",
                                  args, meta=meta)
    if path is None:
        store.mark(conn, video_id, "failed", note="下载失败（详见日志）")
        log(f"[{index}/{total}] 下载失败，跳过发布（修好后重跑同一条命令即可）。")
        return "download_failed"

    # 人工粘贴的链接可能不在库里：用 yt-dlp 返回的标题 / 频道 / 数据补齐再写回
    if meta.get("title"):
        item["title"] = meta["title"]
    if meta.get("channel"):
        item["channel"] = meta["channel"]
    for key in ("views", "duration"):
        if meta.get(key) is not None:
            item[key] = meta[key]
    upload = str(meta.get("upload_date") or "")
    if len(upload) == 8 and upload.isdigit():      # yt-dlp 给的是 YYYYMMDD
        upload = f"{upload[:4]}-{upload[4:6]}-{upload[6:]}"
    if upload:
        item["upload_date"] = upload
    store.upsert(conn, item)
    store.mark(conn, video_id, "downloaded", local_path=str(path))
    log(f"[{index}/{total}] 已登记 downloaded：{path}")

    # 2) 发布：填表 → 读回核对 → （默认）点「发表」
    raw_title = item.get("title") or path.stem
    short_title = _clean_title(raw_title, args.title_limit)
    tags = _tags_for(raw_title, args.topic_display)
    desc = args.desc.strip() if args.desc else ""
    if not args.no_source:
        desc = f"{desc} {_source_line(item.get('channel'))}".strip()
    log(f"[{index}/{total}] 短标题：{short_title or '（空）'}；话题：{'、'.join(tags) or '（无）'}")
    log(f"[{index}/{total}] 描述：{desc} #" + " #".join(tags))

    status, message = publish_mod.publish(
        context, path, title=short_title, desc=desc, tags=tags,
        do_publish=not args.no_publish)
    log(f"[{index}/{total}] 发布结果：{status} | {message}")

    if status == "published":
        store.mark(conn, video_id, "published", local_path=str(path))
        log(f"[{index}/{total}] {video_id} -> published。拿到视频号里的标识后补记："
            f"python -m src.cli mark {video_id} published --post-id <id>")
        return "published"
    if status == "drafted":
        # --no-publish：内容没问题，只是等人点「发表」，状态留在 downloaded
        log(f"[{index}/{total}] {video_id} 保持 downloaded；人工确认发布后回写："
            f"python -m src.cli mark {video_id} published")
        return "drafted"
    if status == "submitted":
        log(f"[{index}/{total}] 点了「发表」但没能确认结果，去后台看一眼再回写："
            f"python -m src.cli mark {video_id} published --post-id <id>")
        return "submitted"
    if status == "need_login":
        # 登录态是浏览器的问题，不是这条内容的问题：不动状态机
        return "need_login"
    store.mark(conn, video_id, "failed", note=message[:200])
    return "publish_failed"


def _report(outcomes: list[str], planned: int) -> int:
    """汇总这一轮并给出退出码（0 全都成；1 有环节失败）。"""
    counts: dict[str, int] = {}
    for outcome in outcomes:
        counts[outcome] = counts.get(outcome, 0) + 1
    ok = sum(counts.get(name, 0) for name in ("published", "drafted", "submitted"))
    bad = sum(counts.get(name, 0) for name in ("download_failed", "publish_failed", "need_login"))
    skipped = planned - len(outcomes)

    log("=" * 20 + " 本轮汇总 " + "=" * 20)
    for name in ("published", "drafted", "submitted", "download_failed",
                 "publish_failed", "need_login"):
        if counts.get(name):
            log(f"  {name}: {counts[name]}")
    if skipped > 0:
        log(f"  未处理 {skipped} 条（登录态失效，已提前结束）。")
    log(f"成功 {ok} 条 / 计划 {planned} 条。")
    return 0 if bad == 0 else 1


def run(args) -> int:
    log("=" * 20 + " MVPoster 手动挑片任务 " + "=" * 20)
    log(f"本轮 {len(args.targets)} 个目标；发布方式："
        + ("--no-publish（只填表 + 截图，停在「发表」前）" if args.no_publish
           else "填完表核对无误即自动提交")
        + (f"；多条之间间隔 {args.interval:g}s（±{INTERVAL_JITTER:.0%} 抖动）"
           if len(args.targets) > 1 else ""))

    conn = store.connect()

    # 1) 把人工给的链接 / id 落成记录；有一条看不懂就整体退出，避免半途而废
    picks: list[dict] = []
    seen: set[str] = set()
    for target in args.targets:
        item = _resolve_target(conn, target)
        if item is None:
            log("运行结束 | 退出码 1（目标无法识别）")
            return 1
        if item["video_id"] in seen:
            log(f"跳过重复目标：{item['video_id']}")
            continue
        seen.add(item["video_id"])
        if item["status"] == "published" and not args.force:
            log(f"跳过 {item['video_id']}：库里已是 published（确实要重发加 --force）。")
            continue
        picks.append(item)
        log(f"目标 [{len(picks)}] {item['video_id']} | "
            f"{item.get('title') or '（标题待下载时补全）'}")
        log(f"           {item['url']}")

    if not picks:
        log("没有需要处理的目标（全部重复或已发布）。")
        return 0

    # 2) 浏览器必须先就绪：下载要 cookies、发布要页签
    cdp_url = browser.cdp_url(args.port)
    if not browser.ensure_available(cdp_url):
        log("运行结束 | 退出码 1（连不上 CDP 服务）")
        return 1

    if args.dry_run:
        # 只读地看一眼登录态，正是 --dry-run 最该干的事
        try:
            with browser.connect(cdp_url) as context:
                _check_youtube_login(context)
        except KeyboardInterrupt:
            log("运行被中断（Ctrl+C）。")
            return 130
        except Exception:
            log("运行异常终止:\n" + traceback.format_exc().rstrip())
            return 1
        log("--dry-run：只校验目标与登录态，不下载、不发布。到此结束。")
        return 0

    proxy = downloader.resolve_proxy()
    log(f"代理：{downloader.mask_proxy(proxy) if proxy else '直连'}（{downloader.proxy_source()}）")

    outcomes: list[str] = []
    try:
        with browser.connect(cdp_url) as context:
            _check_youtube_login(context)
            for index, item in enumerate(picks, 1):
                if index > 1:
                    delay = args.interval * random.uniform(1 - INTERVAL_JITTER, 1 + INTERVAL_JITTER)
                    log(f"等 {delay:.0f}s 再处理下一条（抖动过的间隔，别用固定节奏撞风控）…")
                    time.sleep(delay)
                outcome = _process(context, conn, item, args, index, len(picks))
                outcomes.append(outcome)
                if outcome == "need_login":
                    log("登录态失效：后面的目标不再尝试（去 browserhost 的 Chrome 里扫码后重跑）。")
                    break
    except KeyboardInterrupt:
        log("运行被中断（Ctrl+C）。")
        return 130
    except Exception:
        log("运行异常终止:\n" + traceback.format_exc().rstrip())
        return 1

    return _report(outcomes, len(picks))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.job",
        description="MVPoster 手动挑片任务：给 YouTube 链接 / video id → 自动下载 → 发布到视频号")
    parser.add_argument("targets", nargs="+", metavar="URL_OR_ID",
                        help="YouTube 链接或 11 位 video id（可给多个，按顺序处理）")
    # 发布方式：两个开关互斥，默认发布
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publish", dest="no_publish", action="store_false",
                      help="填完表核对无误即自动提交（默认）")
    mode.add_argument("--no-publish", dest="no_publish", action="store_true",
                      help="只填表 + 截图，停在「发表」按钮前（人工确认后再发）")
    parser.set_defaults(no_publish=False)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help=f"多条之间的间隔秒数，默认 {DEFAULT_INTERVAL:g}"
                             "（每次还会随机浮动一下，只给 1 条时用不到）")
    parser.add_argument("--title-limit", type=int, default=TITLE_LIMIT,
                        help=f"短标题最多多少字，默认 {TITLE_LIMIT}")
    parser.add_argument("--desc", default=DEFAULT_DESC,
                        help=f"视频描述正文，默认「{DEFAULT_DESC}」")
    parser.add_argument("--no-source", action="store_true",
                        help="描述里不加「来源：YouTube @频道」（默认加，注明素材出处）")
    parser.add_argument("--topic", default=keywords_mod.DEFAULT_TOPIC,
                        help=f"话题里的主题名，默认 {keywords_mod.DEFAULT_TOPIC}（只影响标签）")
    parser.add_argument("--quality", choices=downloader.QUALITIES, default="1080",
                        help="清晰度上限，默认 1080；best 表示不限")
    parser.add_argument("--port", type=int, default=config.CDP_PORT,
                        help=f"browserhost 的调试端口，默认 {config.CDP_PORT}")
    parser.add_argument("--dry-run", action="store_true",
                        help="只校验目标与登录态，不下载、不发布（试跑 / 排查用）")
    parser.add_argument("--force", action="store_true",
                        help="即使库里已是 published 也重新下载并发布")

    args = parser.parse_args(argv)
    # download_once 读的是 args.platform（本入口只处理 YouTube，不额外限制）
    args.platform = None
    # 话题里的主题名固定用标准显示名（--topic 允许写别名）
    try:
        args.topic_display = keywords_mod.resolve_topic(args.topic).display
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log(f"数据库：{config.DB_FILE}")
    code = run(args)
    log(f"运行结束 | 退出码 {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
