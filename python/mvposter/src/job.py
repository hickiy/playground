"""无人值守的一轮完整任务：**检索 → 挑选 → 下载 → 发布**（定时任务用的入口）。

`src.main` 只管「我已经选好了，请下载」，`src.cli` 是分步子命令（`discover` / `mark` /
`publish`…）。凌晨三点没人敲命令，所以这里把整条链路串成一次运行：

  1. **检索**：按语义生成关键词，抓 YouTube 候选，按「播放速度」排序（逻辑全在
     `src.discover`，本模块只负责调用与记录）；
  2. **挑选**：取分数最高的前 ``--count`` 条——确定性规则，不依赖任何模型/API Key，
     也就不会在凌晨因为「模型今天不想干了」而空跑（要人工介入就用 `src.cli` 那套）；
  3. **下载**：借常驻 Chrome 的 cookies 交给 yt-dlp，落盘 `movies/<日期>/`；
  4. **发布**：把本地文件填进视频号助手，默认**填完即提交**；`--no-publish` 则只填表
     + 截图，停在「发表」按钮前等人工点（早上起来核对一眼再发）。

用法::

    python -m src.job                     # 检索 → 挑 1 条 → 下载 → 发布
    python -m src.job --count 2           # 一轮 2 条（两条之间按 --interval 抖动间隔）
    python -m src.job --no-publish        # 只填表停在「发表」前（半自动）
    python -m src.job --dry-run           # 只检索 + 挑选并打印计划，不下载、不发布
    python -m src.job --focus 猫 --count 1

定时装载见 `deploy/macos/`（LaunchAgent + caffeinate；凌晨可能睡着，还要 pmset 唤醒）。

退出码：``0`` 这一轮全部成功（含 --no-publish 的「填好表等人工」）/ ``1`` 有环节失败
（连不上 CDP、没下下来、发布出错、登录态失效）/ ``130`` 被 Ctrl+C 中断。

每一步都写进 `logs/mvposter_YYYY-MM-DD.log`，launchd 的 stdout/stderr 另存
`logs/launchd.out.log` / `logs/launchd.err.log`；库里状态机随流程推进
（``found → picked → downloaded → published``，旁支 ``failed``）。
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
import traceback

from . import (browser, config, discover as discover_mod, downloader,
               keywords as keywords_mod, publish as publish_mod, store)
from . import main as main_mod
from .logging import log

DEFAULT_COUNT = 1        # 每轮处理几条：保守起步，风控风险最低
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


def _tags_for(keyword: str, topic_display: str) -> list[str]:
    """按命中的检索词配 3~5 个中文话题（命中某动物就把它的中文名排到最前）。"""
    text = (keyword or "").lower()
    animal = next((zh for en, zh in sorted(_ANIMAL_ZH.items()) if en in text), None)
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


def _keywords(args) -> list[str]:
    """定下这一轮要搜的关键词（与 `src.cli discover` 同一套语义展开）。"""
    seed = args.seed if args.seed is not None else keywords_mod.default_seed()
    try:
        generated = keywords_mod.expand(topic=args.topic, focus=args.focus,
                                        limit=args.keyword_count, seed=seed)
    except ValueError as exc:
        log(f"错误：{exc}")
        return []
    topic = keywords_mod.resolve_topic(args.topic).display
    log(f"关键词 {len(generated)} 个（主题：{topic}，种子 {seed}"
        + (f"，聚焦 {args.focus}" if args.focus else "") + "）：" + "、".join(generated))
    return generated


def _search(args, conn, proxy) -> list[dict] | None:
    """检索并返回按分数降序的候选（跳过库里已有的 id）。

    返回 None 表示**检索本身失败了**（一条都没抓到），与「抓到一堆但都不合格」不是
    一回事：后者是正常状态，前者多半是代理/网络断了。无人值守时这两者必须分得清，
    否则整轮会以「今天没有新候选」静默退出 0。
    """
    keywords = _keywords(args)
    if not keywords:
        return None
    known = store.known_ids(conn)
    log(f"库里已有 {len(known)} 条记录，默认跳过（避免重复爬）。")
    result = discover_mod.discover(
        keywords, per_keyword=args.per_keyword,
        max_duration=args.max_duration or None, min_views=args.min_views or None,
        top=args.top, known=known, proxy=proxy)
    log(f"结果：抓取 {result['fetched']} 条 -> 过滤 {result['rejected']} 条 -> "
        f"跳过已知 {result['skipped_known']} 条 -> 去重 {result['duplicated']} 条 -> "
        f"合格 {result['candidate_total']} 条。")
    if result["fetched"] == 0:
        log(f"错误：{len(keywords)} 个关键词一条都没抓到，检索整体失败"
            f"（代理：{downloader.mask_proxy(proxy) if proxy else '直连'}）。"
            "这不同于「没有新候选」：先确认代理/网络，再重跑。")
        return None
    return result["candidates"]


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
    """处理一条候选（下载 + 发布），推进状态机并返回结果标记。"""
    video_id = item["video_id"]
    raw_title = item.get("title") or ""
    log("-" * 60)
    log(f"[{index}/{total}] {video_id} | 播放 {(item.get('views') or 0):,} | "
        f"{(item.get('duration') or 0)}s | {raw_title[:60]}")
    log(f"[{index}/{total}] {item.get('url')}")
    log(f"[{index}/{total}] 频道：{item.get('channel') or '?'} | "
        f"命中关键词：{item.get('keyword') or '?'}")

    store.upsert(conn, item)                      # 新的入 found，旧的只刷观测值
    store.mark(conn, video_id, "picked", note="src.job 自动挑选（按播放速度取前 N）")

    # 1) 下载：借常驻 Chrome 的 cookies 交给 yt-dlp
    path = main_mod.download_once(context, item["url"], raw_title, args)
    if path is None:
        store.mark(conn, video_id, "failed", note="下载失败（详见日志）")
        log(f"[{index}/{total}] 下载失败，跳过发布。")
        return "download_failed"
    store.mark(conn, video_id, "downloaded", local_path=str(path))
    log(f"[{index}/{total}] 已登记 downloaded：{path}")

    # 2) 发布：填表 → 读回核对 → （默认）点「发表」
    short_title = _clean_title(raw_title, args.title_limit)
    tags = _tags_for(item.get("keyword") or "", args.topic_display)
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
        log(f"  因登录态失效提前结束，还有 {skipped} 条没处理。")
    log(f"成功 {ok} 条 / 计划 {planned} 条。")
    return 0 if bad == 0 else 1


def run(args) -> int:
    log("=" * 20 + " MVPoster 完整任务 " + "=" * 20)
    log(f"本轮计划 {args.count} 条；发布方式："
        + ("--no-publish（只填表 + 截图，停在「发表」前）" if args.no_publish
           else "填完表核对无误即自动提交")
        + (f"；两条间隔 {args.interval:g}s（±{INTERVAL_JITTER:.0%} 抖动）"
           if args.count > 1 else ""))

    # 0) 浏览器必须先就绪：下载要 cookies、发布要页签；连不上就别白跑一趟检索
    cdp_url = browser.cdp_url(args.port)
    if not browser.ensure_available(cdp_url):
        log("运行结束 | 退出码 1（连不上 CDP 服务）")
        return 1

    conn = store.connect()
    proxy = downloader.resolve_proxy()
    log(f"代理：{downloader.mask_proxy(proxy) if proxy else '直连'}（{downloader.proxy_source()}）")

    # 1) 检索 + 挑选
    candidates = _search(args, conn, proxy)
    if candidates is None:
        log("运行结束 | 退出码 1（检索失败）")
        return 1
    picks = candidates[:args.count]
    if not picks:
        # 「抓到一堆但今天没有新的合格候选」是正常状态，不当失败：调阈值或加关键词即可
        log("没有新的合格候选：本轮不下载也不发布。"
            "可以放宽 --min-views / --max-duration，或换个 --focus。")
        return 0

    print()
    for index, item in enumerate(picks, 1):
        log(f"选出 [{index}/{len(picks)}] {item['video_id']} | "
            f"{(item.get('views') or 0):,} 播放 | {item.get('title', '')[:60]}")
        log(f"           {item.get('url')}")

    # 2) 逐条下载 + 发布。--dry-run 也连一次 CDP——只读地看一眼登录态，正是它最该干的事。
    outcomes: list[str] = []
    try:
        with browser.connect(cdp_url) as context:
            _check_youtube_login(context)
            if args.dry_run:
                log("--dry-run：只检索 + 挑选 + 登录态预检，不下载、不发布。到此结束。")
                return 0
            for index, item in enumerate(picks, 1):
                if index > 1:
                    delay = args.interval * random.uniform(1 - INTERVAL_JITTER, 1 + INTERVAL_JITTER)
                    log(f"等 {delay:.0f}s 再处理下一条（抖动过的间隔，别用固定节奏撞风控）…")
                    time.sleep(delay)
                outcome = _process(context, conn, item, args, index, len(picks))
                outcomes.append(outcome)
                if outcome == "need_login":
                    log("登录态失效：后面的候选不再尝试（去 browserhost 的 Chrome 里扫码后重跑）。")
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
        description="MVPoster 无人值守完整任务：检索候选 → 自动挑选 → 下载 → 发布到视频号")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help=f"这一轮处理几条（按播放速度取前 N），默认 {DEFAULT_COUNT}")
    # 发布方式：两个开关互斥，默认发布（run_job.sh 会把选中的那个显式传进来）
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publish", dest="no_publish", action="store_false",
                      help="填完表核对无误即自动提交（默认）")
    mode.add_argument("--no-publish", dest="no_publish", action="store_true",
                      help="只填表 + 截图，停在「发表」按钮前（人工确认后再发）")
    parser.set_defaults(no_publish=False)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help=f"两条之间的间隔秒数，默认 {DEFAULT_INTERVAL:g}"
                             "（每次还会随机浮动一下，--count 1 时用不到）")
    parser.add_argument("--title-limit", type=int, default=TITLE_LIMIT,
                        help=f"短标题最多多少字，默认 {TITLE_LIMIT}")
    parser.add_argument("--desc", default=DEFAULT_DESC,
                        help=f"视频描述正文，默认「{DEFAULT_DESC}」")
    parser.add_argument("--no-source", action="store_true",
                        help="描述里不加「来源：YouTube @频道」（默认加，注明素材出处）")
    parser.add_argument("--quality", choices=downloader.QUALITIES, default="1080",
                        help="清晰度上限，默认 1080；best 表示不限")
    parser.add_argument("--port", type=int, default=config.CDP_PORT,
                        help=f"browserhost 的调试端口，默认 {config.CDP_PORT}")
    parser.add_argument("--dry-run", action="store_true",
                        help="只检索 + 挑选并打印计划，不下载、不发布（试跑 / 排查用）")

    # 关键词与检索参数：与 `src.cli discover` 保持一致，改一边就够
    parser.add_argument("--topic", default=keywords_mod.DEFAULT_TOPIC,
                        help=f"语义主题，默认 {keywords_mod.DEFAULT_TOPIC}")
    parser.add_argument("--focus", help="聚焦某种动物，如 猫 / 狗 / 鹦鹉（中英文都认）")
    parser.add_argument("--keyword-count", type=int, default=keywords_mod.DEFAULT_LIMIT,
                        help=f"生成多少个关键词，默认 {keywords_mod.DEFAULT_LIMIT}")
    parser.add_argument("--seed", type=int,
                        help="生成种子，默认当天日期（同一天可复现，第二天换一批）")
    parser.add_argument("--per-keyword", type=int, default=discover_mod.DEFAULT_PER_KEYWORD,
                        help=f"每个关键词抓多少条，默认 {discover_mod.DEFAULT_PER_KEYWORD}")
    parser.add_argument("--max-duration", type=int, default=discover_mod.DEFAULT_MAX_DURATION,
                        help=f"时长上限（秒），0 表示不限，默认 {discover_mod.DEFAULT_MAX_DURATION}")
    parser.add_argument("--min-views", type=int, default=discover_mod.DEFAULT_MIN_VIEWS,
                        help=f"播放量下限，0 表示不限，默认 {discover_mod.DEFAULT_MIN_VIEWS}")
    parser.add_argument("--top", type=int, default=discover_mod.DEFAULT_TOP,
                        help=f"候选池最多留多少条（再取前 --count 条），默认 {discover_mod.DEFAULT_TOP}")

    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("--count 至少为 1")
    # download_once 读的是 args.platform（本入口只搜 YouTube，不额外限制）
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
