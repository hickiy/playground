"""候选池的 SQLite 记录：去重、状态机、以及和 movies/ 目录的对账。

只用标准库 sqlite3，数据库落在 data/mvposter.db（见 src/config.py）。

主键取 YouTube 的 video_id：它跨平台唯一、稳定，比标题可靠（标题会改、会重名）。
discover（见 src/discover.py）只挑 store 里没见过的 id，所以「爬过的不会重复」；
下载完执行 ``backfill`` 会把 movies/ 里已有的文件登记成 downloaded，
发布成功再用 ``mark`` 写回 post_id，整条链路的状态都留在一张表里。

状态机（status）::

    found -> picked -> downloaded -> published
                      \\-> failed（附 note）
    任何阶段也可以记 skipped（不想要的内容）

字段说明见 _SCHEMA；``views`` / ``score`` 是**检索当时**的快照，不是实时值。
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config
from .logging import log

# 状态取值（顺序即正常流转顺序；failed / skipped 是旁支）
STATUSES = ("found", "picked", "downloaded", "published", "failed", "skipped")

# 文件名形如「标题 [dQw4w9WgXcQ].mp4」：id 由 yt-dlp 的 outtmpl 带出，见 src/downloader.py
_ID_IN_NAME = re.compile(r"\[([A-Za-z0-9_-]{11})\]")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id    TEXT PRIMARY KEY,   -- YouTube 视频 id（去重键）
    url         TEXT NOT NULL,
    title       TEXT,
    channel     TEXT,
    channel_id  TEXT,
    views       INTEGER,            -- 检索时的播放量快照
    duration    INTEGER,            -- 秒
    upload_date TEXT,               -- YYYY-MM-DD，拿不到就是空
    keyword     TEXT,               -- 命中的检索词
    score       REAL,               -- 本地排序分（播放速度，见 discover.score）
    status      TEXT NOT NULL DEFAULT 'found',
    local_path  TEXT,               -- 下载后的本地文件
    post_id     TEXT,               -- 视频号发布后的标识
    published_at TEXT,
    note        TEXT,               -- 失败原因等备注
    first_seen  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
"""


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


def known_ids(conn: sqlite3.Connection) -> set[str]:
    """库里所有已知 video_id —— discover 用它做去重。"""
    return {row[0] for row in conn.execute("SELECT video_id FROM videos")}


def upsert(conn: sqlite3.Connection, item: dict) -> bool:
    """写入一条候选：新的返回 True，已存在的刷新统计后返回 False。

    只刷新「会变的观测值」（标题/播放量/时长/排序分）；状态、本地路径、
    发布时间这些是流程进度，不能被一次重新检索覆盖掉。
    """
    stamp = now_text()
    cur = conn.execute(
        """
        INSERT INTO videos (video_id, url, title, channel, channel_id, views,
                            duration, upload_date, keyword, score, status,
                            first_seen, updated_at)
        VALUES (:video_id, :url, :title, :channel, :channel_id, :views,
                :duration, :upload_date, :keyword, :score, :status,
                :stamp, :stamp)
        ON CONFLICT(video_id) DO UPDATE SET
            url         = excluded.url,
            title       = excluded.title,
            channel     = excluded.channel,
            views       = excluded.views,
            duration    = excluded.duration,
            score       = excluded.score,
            keyword     = excluded.keyword,
            updated_at  = excluded.updated_at
        """,
        {
            "video_id": item["video_id"],
            "url": item["url"],
            "title": item.get("title") or "",
            "channel": item.get("channel") or "",
            "channel_id": item.get("channel_id") or "",
            "views": item.get("views"),
            "duration": item.get("duration"),
            "upload_date": item.get("upload_date") or "",
            "keyword": item.get("keyword") or "",
            "score": item.get("score"),
            "status": item.get("status") or "found",
            "stamp": stamp,
        },
    )
    conn.commit()
    return cur.rowcount == 1  # INSERT 成功才影响 1 行；UPDATE 分支不算新发现


def get(conn: sqlite3.Connection, video_id: str) -> sqlite3.Row | None:
    """按 id 取一条记录，没有返回 None。"""
    return conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()


def mark(conn: sqlite3.Connection, video_id: str, status: str,
         note: str | None = None, post_id: str | None = None,
         local_path: str | None = None) -> bool:
    """更新一条记录的状态（只写传入的字段），返回是否命中记录。"""
    if status not in STATUSES:
        raise ValueError(f"未知状态 {status!r}，可选：{'/'.join(STATUSES)}")
    sets = ["status = ?", "updated_at = ?"]
    values: list[object] = [status, now_text()]
    if note is not None:
        sets.append("note = ?")
        values.append(note)
    if post_id is not None:
        sets.append("post_id = ?")
        values.append(post_id)
        sets.append("published_at = ?")
        values.append(now_text())
    if local_path is not None:
        sets.append("local_path = ?")
        values.append(local_path)
    values.append(video_id)
    cur = conn.execute(f"UPDATE videos SET {', '.join(sets)} WHERE video_id = ?", values)
    conn.commit()
    return cur.rowcount > 0


def listing(conn: sqlite3.Connection, status: str | None = None,
            limit: int = 20) -> list[sqlite3.Row]:
    """按排序分从高到低列出记录；status 为 None 表示全部状态。"""
    sql = "SELECT * FROM videos"
    params: list[object] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY COALESCE(score, 0) DESC, COALESCE(views, 0) DESC LIMIT ?"
    params.append(limit)
    return list(conn.execute(sql, params))


def summary(conn: sqlite3.Connection) -> dict[str, int]:
    """各状态各有多少条（日志里报一句，方便判断流水线卡在哪）。"""
    counts = dict.fromkeys(STATUSES, 0)
    for status, count in conn.execute("SELECT status, COUNT(*) FROM videos GROUP BY status"):
        counts[status] = count
    counts["total"] = sum(counts[name] for name in STATUSES)
    return counts


def backfill(conn: sqlite3.Connection) -> tuple[int, int]:
    """把 movies/ 里已有的文件登记进库，返回（新登记条数，标记为已下载的条数）。

    下载目录是 movies/<日期>/<标题> [id].ext，文件名里已经带了 video_id，
    所以不用重新解析页面就能和库对上；已经标过 downloaded 的不重复写。
    """
    if not config.MOVIES_DIR.exists():
        return 0, 0
    added = 0
    marked = 0
    for path in sorted(config.MOVIES_DIR.rglob("*")):
        if not path.is_file():
            continue
        match = _ID_IN_NAME.search(path.stem)
        if not match:
            continue
        video_id = match.group(1)
        title = _ID_IN_NAME.sub("", path.stem).strip()
        row = get(conn, video_id)
        if row is None:
            upsert(conn, {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}",
                          "title": title, "status": "downloaded"})
            mark(conn, video_id, "downloaded", local_path=str(path))
            added += 1
            continue
        if row["status"] not in ("downloaded", "published") or not row["local_path"]:
            mark(conn, video_id, "downloaded" if row["status"] != "published" else "published",
                 local_path=str(path))
            marked += 1
    return added, marked


def latest_local_path(conn: sqlite3.Connection, video_id: str) -> Path | None:
    """该视频下载到本地后的文件路径（没下过返回 None）。"""
    row = get(conn, video_id)
    if row is None or not row["local_path"]:
        return None
    path = Path(row["local_path"])
    return path if path.exists() else None
