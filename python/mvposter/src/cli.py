"""本地下载记录：列出已下载的视频、把 movies/ 里的历史文件补登记进库。

本仓库只负责下载，所以这里没有检索、也没有发布：

    python -m src.cli list                  # 最近 20 条下载记录
    python -m src.cli list --limit 100
    python -m src.cli backfill              # 扫描 movies/，把历史文件补登记进库

``backfill`` 补登记之后，同一条视频再次下载会被查重拦住（见 ``src/job.py``）。
"""

from __future__ import annotations

import argparse
import sys

from . import config, store
from .logging import log


def cmd_list(args) -> int:
    conn = store.connect()
    rows = store.listing(conn, limit=args.limit)
    if not rows:
        log("还没有任何下载记录。")
        return 0
    print()
    for row in rows:
        print(f"{row['downloaded_at']}  {row['video_id']}  "
              f"{(row['title'] or '')[:60]}")
        print(f"    {row['url']}")
        print(f"    文件：{row['local_path']}")
    log(f"共 {store.count(conn)} 条记录。")
    return 0


def cmd_backfill(args) -> int:
    conn = store.connect()
    added = store.backfill(conn)
    log(f"对账完成：新登记 {added} 条。当前共 {store.count(conn)} 条。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="MVPoster 下载记录：列表 / 从 movies/ 补登记")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="最近下载记录")
    p.add_argument("--limit", type=int, default=20, help="最多列多少条，默认 20")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("backfill", help="扫描 movies/，把历史文件补登记进库")
    p.set_defaults(func=cmd_backfill)

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
