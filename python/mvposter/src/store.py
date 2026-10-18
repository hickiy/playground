"""下载记录（SQLite）：去重、本地文件与元数据。

本仓库只负责下载，所以库里只有「下载成功」这一种记录：

- 主键是去重键（YouTube 是 11 位 video_id，其他站点是 ``平台:URL``，见
  ``src/config.py`` 的 ``dedupe_key``）；
- 每次下载前先 :func:`get`，命中就抛 :class:`DuplicateVideo`，由入口**立即终止任务**；
- 下载成功后 :func:`record_download` 写入标题 / 频道 / 播放量 / 时长 / 上线日期 /
  本地路径；写完这次任务就结束，没有任何发布环节。

数据库落在 ``data/mvposter.db``（见 ``src/config.py``），``data/`` 不进版本库。
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config
from .logging import log

# 文件名形如「标题 [dQw4w9WgXcQ].mp4」：backfill 靠方括号里的 id 与 movies/ 对账
_ID_IN_NAME = re.compile(r"\[([A-Za-z0-9_-]{11})\]")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id      TEXT PRIMARY KEY,   -- 去重键：YouTube 11 位 id / 平台:URL
    url           TEXT NOT NULL,
    title         TEXT,
    channel       TEXT,
    views         INTEGER,            -- 下载时的播放量快照
    duration      INTEGER,            -- 秒
    upload_date   TEXT,               -- YYYY-MM-DD，拿不到就是空
    local_path    TEXT NOT NULL,      -- 落盘文件
    downloaded_at TEXT NOT NULL
);
"""


class DuplicateVideo(Exception):
    """目标已在库中：按约定入口应立即终止任务。"""

    def __init__(self, video_id: str, row: sqlite3.Row):
        self.video_id = video_id
        self.row = row
        title = row["title"] or "（无标题）"
        super().__init__(
            f"重复：{video_id} 已在数据库中（{title}，"
            f"{row['downloaded_at']}，{row['local_path']}）。按约定立即终止任务。"
        )


def now_text() -> str:
    """统一的时间文本（本地时间，秒级足够）。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    """打开数据库（必要时建表），返回按列名取值的连接。"""
    config.DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def get(conn: sqlite3.Connection, video_id: str) -> sqlite3.Row | None:
    """按去重键取一条下载记录，没有返回 None。"""
    return conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()


def record_download(conn: sqlite3.Connection, video_id: str, url: str,
                    meta: dict, path: Path) -> None:
    """记录一次成功的下载（调用前必须已经确认过 key 不在库里）。"""
    upload = str(meta.get("upload_date") or "")
    if len(upload) == 8 and upload.isdigit():      # yt-dlp 给的是 YYYYMMDD
        upload = f"{upload[:4]}-{upload[4:6]}-{upload[6:]}"
    conn.execute(
        """
        INSERT INTO videos (video_id, url, title, channel, views, duration,
                            upload_date, local_path, downloaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            video_id,
            url,
            meta.get("title") or "",
            meta.get("channel") or "",
            meta.get("views"),
            meta.get("duration"),
            upload,
            str(path),
            now_text(),
        ),
    )
    conn.commit()
    log(f"已写入数据库：{video_id} -> {path}")


def listing(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    """按下载时间倒序列出记录。"""
    return list(conn.execute(
        "SELECT * FROM videos ORDER BY downloaded_at DESC LIMIT ?", (limit,)))


def count(conn: sqlite3.Connection) -> int:
    """库里一共有多少条下载记录。"""
    return conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]


def backfill(conn: sqlite3.Connection) -> int:
    """把 movies/ 里已有的历史文件补登记进库，返回新增条数。

    文件名里带 ``[11位id]`` 才能对上；已经登记过的不重复写。补登记之后，
    同一条视频再次下载就会被查重拦住。
    """
    if not config.MOVIES_DIR.exists():
        return 0
    added = 0
    for path in sorted(config.MOVIES_DIR.rglob("*")):
        if not path.is_file():
            continue
        match = _ID_IN_NAME.search(path.stem)
        if not match:
            continue
        video_id = match.group(1)
        if get(conn, video_id) is not None:
            continue
        title = _ID_IN_NAME.sub("", path.stem).strip()
        conn.execute(
            "INSERT INTO videos (video_id, url, title, local_path, downloaded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (video_id, f"https://www.youtube.com/watch?v={video_id}",
             title, str(path), now_text()),
        )
        added += 1
    conn.commit()
    return added
