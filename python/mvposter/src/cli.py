"""MVPoster 的流水线入口：检索候选、维护记录、和 movies/ 对账、发到视频号。

这里是**新增**的一条入口，不替代 ``python -m src.main``（下载入口）：检索、去重、
状态记录都不需要浏览器，也没有任何会误操作的副作用；只有 ``publish`` 要连
browserhost 的 CDP，而且只**新开自己的页签**，绝不碰你或别的任务开着的页签。

用法::

    # 0) 看语义生成的关键词（不检索，只展开主题）
    python -m src.cli keywords --topic 动物搞笑 --focus 猫 --keyword-count 12

    # 1) 检索：按播放速度排出候选（默认用语义生成的关键词，并跳过库里已见过的 id）
    python -m src.cli discover --topic 动物搞笑 --top 10
    python -m src.cli discover --keywords "funny cats shorts,funny dogs shorts" --top 10
    python -m src.cli discover -o .cache/candidates.json      # 给脚本 / CLI 智能体消费

    # 看记录（默认按分数降序）
    python -m src.cli list --status found --limit 20

    # 下载完成后跑一次：把 movies/ 里已有的文件登记成 downloaded
    python -m src.cli backfill

    # 人工/智能体挑中后用 mark 推进状态（发布成功时带上 --post-id 回写）
    python -m src.cli mark dQw4w9WgXcQ picked --note "挑中"
    python -m src.cli mark dQw4w9WgXcQ published --post-id 123456

    # 发到视频号（默认填完即自动提交；想先人工核对就加 --no-publish）
    python -m src.cli publish dQw4w9WgXcQ --title "猫咪看到黄瓜的反应" --tags 萌宠,搞笑动物
    python -m src.cli publish dQw4w9WgXcQ --no-publish     # 只填表 + 截图，停在「发表」前
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (browser, config, discover as discover_mod, downloader,
               keywords as keywords_mod, publish as publish_mod, store)
from .logging import log


def _print_candidates(candidates: list[dict]) -> None:
    """把候选打到终端（不带时间戳，方便直接复制 URL）。"""
    for index, item in enumerate(candidates, 1):
        views = item.get("views") or 0
        duration = item.get("duration")
        duration_text = f"{duration}s" if duration else "?"
        velocity = (item.get("score") or 0) / 10000
        print(f"{index:>3}. {views:>12,} 播放 | {duration_text:>4} | {velocity:>8.1f}万/天 "
              f"| {item.get('title', '')[:66]}")
        print(f"     {item.get('url', '')}")
        print(f"     频道：{item.get('channel') or '?'} | 命中关键词：{item.get('keyword') or '?'}")


def _resolve_keywords(args) -> list[str]:
    """定下这一轮要搜的关键词：显式 --keywords 优先，否则按语义主题生成。"""
    if args.keywords:
        return [word.strip() for word in args.keywords.split(",") if word.strip()]
    seed = args.seed if args.seed is not None else keywords_mod.default_seed()
    try:
        generated = keywords_mod.expand(topic=args.topic, focus=args.focus,
                                        limit=args.keyword_count, seed=seed,
                                        include_chinese=args.with_chinese)
    except ValueError as exc:
        log(f"错误：{exc}")
        return []
    topic = keywords_mod.resolve_topic(args.topic).display
    log(f"语义生成 {len(generated)} 个关键词（主题：{topic}，种子 {seed}"
        + (f"，聚焦 {args.focus}" if args.focus else "")
        + ("，含中文" if args.with_chinese else "") + "）：" + "、".join(generated))
    return generated


def cmd_keywords(args) -> int:
    """只展开关键词、不检索：看看「按语义生成的词表」长什么样。"""
    seed = args.seed if args.seed is not None else keywords_mod.default_seed()
    try:
        generated = keywords_mod.expand(topic=args.topic, focus=args.focus,
                                        limit=args.keyword_count, seed=seed,
                                        include_chinese=args.with_chinese)
    except ValueError as exc:
        log(f"错误：{exc}")
        return 1
    log(f"主题：{keywords_mod.resolve_topic(args.topic).display} | 种子：{seed} | "
        f"共 {len(generated)} 个关键词"
        + (f"（聚焦 {args.focus}）" if args.focus else ""))
    print()
    for index, keyword in enumerate(generated, 1):
        print(f"{index:>3}. {keyword}")
    log(f"拿去检索：python -m src.cli discover --topic {args.topic} --top 10")
    return 0


def cmd_discover(args) -> int:
    keywords = _resolve_keywords(args)
    if not keywords:
        log("错误：关键词是空的（--keywords 或 --topic 至少给一个）。")
        return 1
    sorts = tuple(s.strip() for s in args.sort.split(",") if s.strip())
    unknown = [s for s in sorts if s not in discover_mod.SORTS]
    if unknown:
        log(f"错误：未知排序 {'、'.join(unknown)}，可选：{'/'.join(discover_mod.SORTS)}")
        return 1

    conn = store.connect()
    known = store.known_ids(conn)
    # 复用下载侧的代理解析（环境变量 > config.json > 内置默认），避免两套配置
    proxy = downloader.resolve_proxy()
    log(f"检索 {len(keywords)} 个关键词 × {len(sorts)} 种排序，每个关键词取 "
        f"{args.per_keyword} 条；过滤：时长 ≤ {args.max_duration or '不限'}s、"
        f"播放量 ≥ {args.min_views or 0:,}；代理：{proxy or '直连'}")
    log(f"库里已有 {len(known)} 条记录，默认跳过（要重看用 --include-known）")

    result = discover_mod.discover(
        keywords, sorts=sorts, per_keyword=args.per_keyword,
        max_duration=args.max_duration or None, min_views=args.min_views or None,
        top=args.top, known=known, include_known=args.include_known, proxy=proxy)

    candidates = result["candidates"]
    if not candidates:
        # 「今天没有新的合格候选」是正常状态，不当失败：调阈值或加关键词即可
        log(f"没有新的合格候选（抓取 {result['fetched']} 条，过滤 {result['rejected']} 条，"
            f"跳过已知 {result['skipped_known']} 条）。"
            "可以放宽 --min-views / --max-duration，或加 --include-known 重看旧候选。")
        return 0

    print()
    _print_candidates(candidates)

    added = 0
    if not args.no_save:
        for item in candidates:
            if store.upsert(conn, item):
                added += 1
        log(f"入库：新增 {added} 条，其余 {len(candidates) - added} 条是旧记录的观测刷新。")
    log(f"结果：抓取 {result['fetched']} 条 -> 过滤掉 {result['rejected']} 条"
        f"（播放量/时长不达标）-> 跳过已知 {result['skipped_known']} 条"
        f"-> 去重 {result['duplicated']} 条 -> 合格 {result['candidate_total']} 条，"
        f"取前 {len(candidates)} 条。")

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "keywords": result["keywords"],
            "sorts": result["sorts"],
            "generated_at": store.now_text(),
            "candidates": candidates,
            "rejected_reasons": result["rejected_reasons"],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"已写出 {len(candidates)} 条候选到 {path}")
    return 0


def cmd_list(args) -> int:
    conn = store.connect()
    status = None if args.status == "all" else args.status
    rows = store.listing(conn, status=status, limit=args.limit)
    counts = store.summary(conn)
    log("状态统计：" + "、".join(f"{name} {counts[name]}" for name in store.STATUSES)
        + f"、合计 {counts['total']}")
    if not rows:
        log("没有符合条件的记录。")
        return 0
    print()
    for row in rows:
        print(f"{row['status']:<10} {row['video_id']}  "
              f"{(row['views'] or 0):>12,}播放 {(row['duration'] or 0):>4}s  "
              f"{(row['title'] or '')[:56]}")
        detail = [f"频道：{row['channel'] or '?'}"]
        if row["local_path"]:
            detail.append(f"文件：{row['local_path']}")
        if row["post_id"]:
            detail.append(f"视频号：{row['post_id']}")
        if row["note"]:
            detail.append(f"备注：{row['note']}")
        print("           " + " | ".join(detail))
    return 0


def cmd_backfill(args) -> int:
    conn = store.connect()
    added, marked = store.backfill(conn)
    counts = store.summary(conn)
    log(f"对账完成：新登记 {added} 条、更新为已下载 {marked} 条。")
    log(f"当前库里共 {counts['total']} 条：" +
        "、".join(f"{name} {counts[name]}" for name in store.STATUSES))
    return 0


def cmd_mark(args) -> int:
    conn = store.connect()
    if store.get(conn, args.video_id) is None:
        log(f"错误：库里没有 {args.video_id}；先跑 discover 或 backfill。")
        return 1
    store.mark(conn, args.video_id, args.status, note=args.note,
               post_id=args.post_id, local_path=args.local_path)
    row = store.get(conn, args.video_id)
    log(f"{args.video_id} -> {row['status']}"
        + (f"（备注：{row['note']}）" if row["note"] else "")
        + (f"（视频号：{row['post_id']}）" if row["post_id"] else ""))
    return 0


def cmd_publish(args) -> int:
    """把某条已下载的视频填进视频号助手的发布页（默认半自动，停在「发表」前）。

    需要浏览器：只通过 CDP 连 browserhost 那个常驻实例，自己新开一个页签。
    """
    conn = store.connect()
    row = store.get(conn, args.video_id)
    path = Path(args.file) if args.file else store.latest_local_path(conn, args.video_id)
    if path is None:
        log(f"错误：{args.video_id} 还没有下载到本地（先下载，再跑 backfill 登记）。")
        return 1

    title = args.title or (row["title"] if row is not None else "")
    tags = [tag.strip() for tag in (args.tags or "").split(",") if tag.strip()]
    log(f"素材：{path}")
    log(f"短标题：{title or '（空）'}；话题：{'、'.join(tags) or '（无）'}"
        + ("；--no-publish：只填表 + 截图，不提交" if args.no_publish
           else "；填完表核对无误就自动提交"))

    cdp_url = browser.cdp_url(args.port)
    if not browser.ensure_available(cdp_url):
        return 1
    log(f"已连上常驻 Chrome（{cdp_url}）：只新开自己的页签，完事关掉它，不动别的页签。")
    with browser.connect(cdp_url) as context:
        status, message = publish_mod.publish(context, path, title=title, desc=args.desc or "",
                                              tags=tags, do_publish=not args.no_publish,
                                              keep_tab=args.keep_tab)
    log(message)

    if status == "need_login":
        # 登录态问题不是这条内容的问题，不动状态机
        log("登录完成后重跑本条命令即可；状态未改动。")
        return 1
    if status == "failed":
        if row is not None:
            store.mark(conn, args.video_id, "failed", note=message[:200])
            log(f"已把 {args.video_id} 记为 failed（备注：{message[:200]}）。")
        return 1
    if status == "published":
        store.mark(conn, args.video_id, "published", local_path=str(path))
        log(f"{args.video_id} -> published。拿到视频号里的链接/ID 后再补记一次："
            f"python -m src.cli mark {args.video_id} published --post-id <id>")
        return 0
    if status == "submitted":
        log("点了「发表」但没能确认结果：去视频号后台看一眼，确认发成功后回写状态："
            f"python -m src.cli mark {args.video_id} published --post-id <id>")
        return 0
    log("--no-publish：脚本没有点「发表」。人工确认发布后回写状态："
        f"python -m src.cli mark {args.video_id} published")
    return 0


def _add_keyword_args(parser: argparse.ArgumentParser) -> None:
    """discover / keywords 共用的「关键词从哪来」参数。"""
    parser.add_argument("--topic", default=keywords_mod.DEFAULT_TOPIC,
                        help=f"语义主题，默认 {keywords_mod.DEFAULT_TOPIC}"
                             f"（别名：{'、'.join(sorted(keywords_mod.TOPIC_ALIASES))}）")
    parser.add_argument("--focus", help="聚焦某种动物，如 猫 / 狗 / 鹦鹉（中英文都认）")
    parser.add_argument("--keyword-count", type=int, default=keywords_mod.DEFAULT_LIMIT,
                        help=f"生成多少个关键词，默认 {keywords_mod.DEFAULT_LIMIT}")
    parser.add_argument("--seed", type=int,
                        help="生成种子，默认当天日期（同一天可复现，第二天换一批）")
    parser.add_argument("--with-chinese", action="store_true",
                        help="额外带上中文关键词（默认只搜英文，英文内容多得多）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="MVPoster 流水线入口：检索候选 / 对账 / 发布到视频号")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("discover", help="按关键词检索 YouTube 候选并按播放速度排序")
    p.add_argument("--keywords",
                   help="逗号分隔的检索词；不给就按 --topic 语义生成（默认）")
    _add_keyword_args(p)
    p.add_argument("--sort", default=discover_mod.DEFAULT_SORT,
                   help="逗号分隔的排序：" + "/".join(discover_mod.SORTS)
                        + f"，默认 {discover_mod.DEFAULT_SORT}")
    p.add_argument("--per-keyword", type=int, default=discover_mod.DEFAULT_PER_KEYWORD,
                   help=f"每个关键词抓多少条，默认 {discover_mod.DEFAULT_PER_KEYWORD}")
    p.add_argument("--max-duration", type=int, default=discover_mod.DEFAULT_MAX_DURATION,
                   help=f"时长上限（秒），0 表示不限，默认 {discover_mod.DEFAULT_MAX_DURATION}")
    p.add_argument("--min-views", type=int, default=discover_mod.DEFAULT_MIN_VIEWS,
                   help=f"播放量下限，0 表示不限，默认 {discover_mod.DEFAULT_MIN_VIEWS}")
    p.add_argument("--top", type=int, default=discover_mod.DEFAULT_TOP,
                   help=f"最多输出多少条候选，默认 {discover_mod.DEFAULT_TOP}")
    p.add_argument("--include-known", action="store_true",
                   help="连库里已有的 id 一起列出（默认跳过，避免重复爬）")
    p.add_argument("--no-save", action="store_true", help="只打印，不写入库")
    p.add_argument("-o", "--out", metavar="PATH", help="把候选写成 JSON 文件（供脚本/智能体消费）")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("keywords", help="按语义展开关键词（不检索，只看词表）")
    _add_keyword_args(p)
    p.set_defaults(func=cmd_keywords)

    p = sub.add_parser("list", help="列出记录（默认按分数降序）")
    p.add_argument("--status", choices=("all", *store.STATUSES), default="all",
                   help="只看某个状态，默认 all")
    p.add_argument("--limit", type=int, default=20, help="最多列多少条，默认 20")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("backfill", help="扫描 movies/，把已下载的文件登记进库")
    p.set_defaults(func=cmd_backfill)

    p = sub.add_parser("mark", help="推进某条记录的状态（挑中 / 已发布 / 失败…）")
    p.add_argument("video_id", help="YouTube 视频 id（11 位）")
    p.add_argument("status", choices=store.STATUSES, help="新状态")
    p.add_argument("--note", help="备注（失败原因、挑选理由等）")
    p.add_argument("--post-id", help="视频号发布后的标识，给了就顺带记发布时间")
    p.add_argument("--local-path", help="本地文件路径")
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("publish", help="把已下载的视频发到视频号助手（默认停在「发表」前）")
    p.add_argument("video_id", help="YouTube 视频 id（本地文件与标题默认从库里取）")
    p.add_argument("--file", help="直接指定视频文件（默认用库里该 id 的 local_path）")
    p.add_argument("--title", help="短标题（视频号表单里的「短标题」，默认用库里的标题）")
    p.add_argument("--desc", help="视频描述（正文）")
    p.add_argument("--tags", help="话题标签，逗号分隔（以 #标签 写进描述末尾）")
    p.add_argument("--no-publish", action="store_true",
                   help="只填表 + 截图，停在「发表」按钮前不提交（想人工核对一遍时用）")
    p.add_argument("--keep-tab", action="store_true",
                   help="结束后不关自己开的页签（排查用；需要扫码与 --no-publish 时本来就会留）")
    p.add_argument("--port", type=int, default=config.CDP_PORT,
                   help=f"browserhost 的调试端口，默认 {config.CDP_PORT}")
    p.set_defaults(func=cmd_publish)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log("=" * 16 + f" MVPoster {args.command} " + "=" * 16)
    log(f"数据库：{config.DB_FILE}")
    code = args.func(args)
    log(f"运行结束 | 退出码 {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
