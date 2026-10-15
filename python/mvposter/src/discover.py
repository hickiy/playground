"""按关键词检索 YouTube 候选视频，并按「播放速度」排序（不下载、不需要 API Key）。

为什么走 yt-dlp 而不是 YouTube Data API：
flat 模式下一次检索就能拿到 ``view_count`` / ``duration`` / ``channel``
（本机实测 5 条约 2 秒），零配额、零 Key；而 search.list 每次要花 100 quota 单位。

排序为什么要在本地再做一次：
搜索页的 ``sp`` 参数能影响召回，但 flat 返回的顺序是**分批追加**的，不是全局有序
（实测首个 4 亿播放后面会跟着 3000 播放的条目），所以必须自己按 ``score`` 重排。
时长、横竖屏这些 sp 不可靠的维度也一律本地过滤（见 ``reject_reason``）。

为什么这里不需要 cookies：
取播放量不需要登录；但**完整解析**（like/comment 等）会触发 YouTube 的
「Sign in to confirm you're not a bot」，那种场合由下载侧用 CDP 导出的 cookies 解决
（见 src/browser.py 的 export_cookies）。
"""

from __future__ import annotations

import time
import urllib.parse

import yt_dlp

from . import downloader
from .logging import log

# 默认关键词由 src/keywords.py 按语义槽位生成（见 python -m src.cli keywords）

# 搜索结果页的 sp 参数。**取值一律以实测为准，不要照抄网上的对照表**：
# 实测（2026-10-15，关键词 funny animals shorts，各取 100 条，同一代理）：
#   sp=CAM%3D（views）         时长中位数   42s，≤60s 且 ≥10 万播放的有 69/99 条
#   sp=CAMSAhAB（views_short） 时长中位数 1110s，≤60s 的 0 条  ← 名字里的 short 并不限时长
#   sp=CAI%3D（date）          时长中位数 1188s，偏长，不适合挑短视频
# 所以默认用 views；时长过滤必须自己做（见 reject_reason）。
SORTS = {
    "relevance": None,   # 相关性：改走 ytsearch:N: 语法
    "views": "CAM%3D",   # 按播放量降序（默认，实测最贴合「高播放短视频」）
    "date": "CAI%3D",    # 按上传时间降序（追新时用，内容偏长）
}
DEFAULT_SORT = "views"

DEFAULT_PER_KEYWORD = 50      # 每个关键词取多少条（playlistend 限深，实测 50 条约 2-4s）
DEFAULT_MAX_DURATION = 60     # 秒：视频号发的是竖屏短视频，长视频不搬运（实测 views 排序下约 7 成命中）
DEFAULT_MIN_VIEWS = 100_000
DEFAULT_TOP = 20

# 拿不到上传时间时的估算天数：宁可保守（分数偏低），也不把老视频当成新爆款
_UNKNOWN_AGE_DAYS = 30.0

_SEARCH_URL = "https://www.youtube.com/results?search_query={query}&sp={sp}"


class _Logger:
    """yt-dlp 的日志出口：**只留警告/错误**。

    flat 检索会为每一条结果刷一行「Downloading item N of M」，直接透传会把终端
    淹没（20 条一次就是 20 行）；每个关键词的条数与耗时由 :func:`search` 自己报一句。
    """

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        log(f"[检索] 警告: {msg}")

    def error(self, msg: str) -> None:
        log(f"[检索] 错误: {msg}")


def _options(limit: int, proxy: str | None) -> dict:
    """flat 检索用的 yt-dlp 参数：只取列表元数据，不解析视频本身。"""
    options = {
        "quiet": True,
        "extract_flat": True,
        "playlistend": limit,   # 限深：不加这条会一次拉回 600+ 条（实测 28s）
        "socket_timeout": 30,
        "logger": _Logger(),
    }
    if proxy:
        options["proxy"] = proxy
    if downloader.find_js_runtime():
        options["js_runtimes"] = {"node": {}}
    return options


def _target(keyword: str, sort: str, limit: int) -> str:
    """把关键词 + 排序参数拼成 yt-dlp 能吃的输入。"""
    sp = SORTS.get(sort)
    if sp:
        return _SEARCH_URL.format(query=urllib.parse.quote_plus(keyword), sp=sp)
    return f"ytsearch{limit}:{keyword}"


def normalize(entry: dict, keyword: str) -> dict | None:
    """把 yt-dlp 的条目转成库里那一行；不是普通视频（直播等）返回 None。"""
    video_id = entry.get("id")
    if not video_id or entry.get("live_status") == "is_live":
        return None
    views = entry.get("view_count")
    duration = entry.get("duration")
    stamp = entry.get("timestamp") or entry.get("release_timestamp")
    upload_date = entry.get("upload_date") or (
        time.strftime("%Y-%m-%d", time.gmtime(stamp)) if stamp else "")
    return {
        "video_id": video_id,
        "url": entry.get("webpage_url") or entry.get("url")
               or f"https://www.youtube.com/watch?v={video_id}",
        "title": (entry.get("title") or "").strip(),
        "channel": entry.get("channel") or entry.get("uploader") or "",
        "channel_id": entry.get("channel_id") or "",
        "views": int(views) if isinstance(views, (int, float)) else None,
        "duration": int(duration) if isinstance(duration, (int, float)) else None,
        "upload_date": upload_date,
        "timestamp": stamp,
        "keyword": keyword,
        "status": "found",
        "score": 0.0,
    }


def score(item: dict, now: float | None = None) -> float:
    """排序分 = 播放速度（播放量 / 上线天数）。

    用「速度」而不是总播放量：总播放量高的常年老视频对视频号没有参考价值，
    而当下的爆款更可能在小号上再火一次。
    """
    views = item.get("views") or 0
    stamp = item.get("timestamp")
    if stamp:
        days = max((now or time.time()) - float(stamp), 0.0) / 86400
    else:
        days = _UNKNOWN_AGE_DAYS
    return views / max(days, 1.0)


def reject_reason(item: dict, max_duration: int | None, min_views: int | None) -> str | None:
    """不合格的原因（合格的返回 None）——日志和 --why 都用它解释为什么被刷掉。"""
    if item.get("views") is None:
        return "拿不到播放量"
    if min_views and item["views"] < min_views:
        return f"播放量 < {min_views:,}"
    if item.get("duration") is None:
        return "拿不到时长"
    if max_duration and item["duration"] > max_duration:
        return f"时长 {item['duration']}s > {max_duration}s"
    return None


def search(keyword: str, sort: str = DEFAULT_SORT, limit: int = DEFAULT_PER_KEYWORD,
           proxy: str | None = None) -> list[dict]:
    """检索单个关键词，返回归一化后的条目（失败返回空列表，不抛给上层）。"""
    options = _options(limit, proxy)
    target = _target(keyword, sort, limit)
    started = time.time()
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(target, download=False)
    except Exception as exc:
        log(f"[检索] 「{keyword}」（{sort}）失败：{exc}")
        return []
    items = []
    for entry in (info or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        item = normalize(entry, keyword)
        if item:
            items.append(item)
    log(f"[检索] 「{keyword}」（{sort}）：{len(items)} 条，耗时 {time.time() - started:.1f}s")
    return items


def discover(keywords: list[str], sorts: tuple[str, ...] = (DEFAULT_SORT,),
             per_keyword: int = DEFAULT_PER_KEYWORD,
             max_duration: int | None = DEFAULT_MAX_DURATION,
             min_views: int | None = DEFAULT_MIN_VIEWS,
             top: int = DEFAULT_TOP, known: set[str] | None = None,
             include_known: bool = False, proxy: str | None = None) -> dict:
    """跑完所有关键词×排序，返回按分数降序的候选（同时给出各项计数，便于复盘）。"""
    known = known or set()
    allowed: dict[str, dict] = {}    # 通过过滤的：video_id -> 条目
    rejected: dict[str, str] = {}    # 被刷掉的：video_id -> 原因
    fetched = 0
    skipped_known = 0
    duplicated = 0

    for keyword in keywords:
        for sort in sorts:
            items = search(keyword, sort=sort, limit=per_keyword, proxy=proxy)
            fetched += len(items)
            for item in items:
                item["score"] = score(item)
                video_id = item["video_id"]
                if not include_known and video_id in known:
                    skipped_known += 1
                    continue
                reason = reject_reason(item, max_duration, min_views)
                if reason:
                    rejected.setdefault(video_id, reason)
                    continue
                previous = allowed.get(video_id)
                if previous is not None:
                    # 多个关键词命中同一条：留分数高的那份观测
                    duplicated += 1
                    if previous["score"] >= item["score"]:
                        continue
                allowed[video_id] = item

    candidates = sorted(allowed.values(), key=lambda i: i["score"], reverse=True)
    return {
        "candidates": candidates[:top],
        "candidate_total": len(candidates),
        "fetched": fetched,
        "skipped_known": skipped_known,
        "duplicated": duplicated,
        "rejected": len(rejected),
        "rejected_reasons": rejected,
        "keywords": list(keywords),
        "sorts": list(sorts),
    }
