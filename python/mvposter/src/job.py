"""一次下载任务：人工给链接 / id → 查重 → 下载 → 记录 → 结束。

本仓库**只负责下载**：不检索、不发布，也不维护发布状态。

流程（任一环节不满足就立即结束）::

    1. 解析目标（YouTube 链接或 11 位 video id）；
    2. 查 data/mvposter.db：命中已有记录 → 提示重复并以退出码 2 终止；
    3. 借常驻 Chrome 的 cookies，用 yt-dlp 下载到 movies/<日期>/；
    4. 把标题 / 频道 / 播放量 / 时长 / 本地路径写进数据库；
    5. 打印结果，任务结束。

用法::

    python -m src.job https://www.youtube.com/shorts/xxxxxxxxxxx
    python -m src.job dQw4w9WgXcQ
    python -m src.job dQw4w9WgXcQ --dry-run     # 只查重，不下载
    python -m src.job dQw4w9WgXcQ --quality 720

退出码：``0`` 下载并记录成功 / ``1`` 参数、CDP 或下载失败 / ``2`` 命中重复记录
（按约定立即终止）/ ``130`` 被 Ctrl+C 中断。
"""

from __future__ import annotations

import argparse
import sys
import traceback

from . import browser, config, downloader, store
from . import main as main_mod
from .logging import log


def _target(value: str) -> tuple[str, str] | None:
    """把人工给的目标解析成 (去重键, 下载 URL)；看不懂返回 None。"""
    text = (value or "").strip()
    youtube_id = config.youtube_id(text)
    if youtube_id:
        url = text if text.startswith("http") else \
            f"https://www.youtube.com/watch?v={youtube_id}"
        return youtube_id, url
    if text.startswith("http"):
        return config.dedupe_key(text), text
    return None


def run(args) -> int:
    log("=" * 20 + " MVPoster 下载任务 " + "=" * 20)
    conn = store.connect()

    # 1) 先查重：发现重复立即终止，连 CDP 都不连
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in args.targets:
        parsed = _target(raw)
        if parsed is None:
            log(f"错误：看不懂 {raw!r}——需要 YouTube 链接或 11 位 video id。")
            log("运行结束 | 退出码 1（目标无法识别）")
            return 1
        key, url = parsed
        if key in seen:
            log(f"重复：{key} 在本次命令里出现了多次。按约定立即终止任务。")
            log("运行结束 | 退出码 2（重复目标）")
            return 2
        seen.add(key)

        row = store.get(conn, key)
        if row is not None:
            log(str(store.DuplicateVideo(key, row)))
            log("运行结束 | 退出码 2（重复目标）")
            return 2

        targets.append((key, url))
        log(f"目标 [{len(targets)}] {key} | {url}")

    if args.dry_run:
        log("--dry-run：查重通过，未下载。任务结束。")
        return 0

    # 2) 浏览器必须先就绪：下载要借它的登录态 cookies
    cdp_url = browser.cdp_url(args.port)
    if not browser.ensure_available(cdp_url):
        log("运行结束 | 退出码 1（连不上 CDP 服务）")
        return 1

    proxy = downloader.resolve_proxy()
    log(f"代理：{downloader.mask_proxy(proxy) if proxy else '直连'}"
        f"（{downloader.proxy_source()}）")

    # 3) 下载 + 记录；download_once 内部会再查一次重（防止并发/竞态）
    try:
        with browser.connect(cdp_url) as context:
            for index, (key, url) in enumerate(targets, 1):
                log("-" * 60)
                log(f"[{index}/{len(targets)}] 开始处理 {key}")
                path = main_mod.download_once(context, url, "", args, meta={})
                if path is None:
                    log(f"[{index}/{len(targets)}] 下载失败，任务结束（未写入数据库）。")
                    log("运行结束 | 退出码 1（下载失败）")
                    return 1
                log(f"[{index}/{len(targets)}] 完成：{path}")
    except store.DuplicateVideo as exc:
        log(str(exc))
        log("运行结束 | 退出码 2（重复目标）")
        return 2
    except KeyboardInterrupt:
        log("运行被中断（Ctrl+C）。")
        return 130
    except Exception:
        log("运行异常终止:\n" + traceback.format_exc().rstrip())
        return 1

    log("全部下载完成，任务结束。")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.job",
        description="MVPoster 下载任务：给链接 / id → 查重 → 下载 → 记录 → 结束")
    parser.add_argument("targets", nargs="+", metavar="URL_OR_ID",
                        help="YouTube 链接或 11 位 video id（可给多个，按顺序处理）")
    parser.add_argument("--quality", choices=downloader.QUALITIES, default="1080",
                        help="清晰度上限，默认 1080；best 表示不限")
    parser.add_argument("--port", type=int, default=config.CDP_PORT,
                        help=f"browserhost 的调试端口，默认 {config.CDP_PORT}")
    parser.add_argument("--dry-run", action="store_true",
                        help="只查重并打印目标，不下载、不写数据库")

    args = parser.parse_args(argv)
    # download_once 读的是 args.platform（本入口只做下载，不额外限制平台）
    args.platform = None
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log(f"数据库：{config.DB_FILE}")
    code = run(args)
    log(f"运行结束 | 退出码 {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
