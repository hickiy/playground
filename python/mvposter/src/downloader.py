"""用 yt-dlp 下载视频：产物落在 movies/<日期>/，代理只从环境变量读。

yt-dlp 以库的形式调用（不依赖外部 yt-dlp 可执行文件）；ffmpeg 只在合并分轨
格式时用得上，优先用项目自带的 `resources/bin/<平台>/`（见 scripts/fetch_binaries.py），
没有才回退到系统 PATH。
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yt_dlp

from . import config
from .browser import log

# --quality 允许的档位；best 表示不限高度
QUALITIES = ("1080", "720", "480", "360", "best")


def resolve_proxy() -> str | None:
    """从环境变量取代理地址；都没有则返回 None（直连）。

    yt-dlp 自己不会读 HTTP(S)_PROXY，必须显式传给它，所以在这里读一次。
    """
    for name in config.PROXY_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


def mask_proxy(proxy: str) -> str:
    """日志里打码：代理 URL 可能带用户名密码。"""
    scheme, sep, rest = proxy.partition("://")
    if not sep or "@" not in rest:
        return proxy
    return f"{scheme}://***@{rest.rpartition('@')[2]}"


def day_dir(now: datetime | None = None) -> Path:
    """当天的下载目录 movies/<YYYY-MM-DD>/，不存在就创建。"""
    target = config.MOVIES_DIR / (now or datetime.now()).strftime("%Y-%m-%d")
    target.mkdir(parents=True, exist_ok=True)
    return target


def build_format(quality: str) -> str:
    """把 --quality 档位转成 yt-dlp 的格式表达式。

    清晰度优先、编解码器其次：偏好必须写在选择器里，而不是用 format_sort——
    否则低分辨率的「音视频已合体」格式会同时命中 vcodec / acodec 两个偏好，
    反而排到 1080p 的分轨格式前面（实测 1080p 会下成 360p）。
    """
    limit = "" if quality == "best" else f"[height<={int(quality)}]"
    return "/".join([
        f"bv{limit}[vcodec^=avc]+ba[acodec^=mp4a]",  # 首选 H.264 视频 + AAC 音频
        f"bv{limit}[vcodec^=avc]+ba",
        f"bv{limit}+ba",
        f"b{limit}[vcodec^=avc]",                    # 只有合体格式时的退路
        f"b{limit}",
    ])


def find_ffmpeg() -> str | None:
    """找 ffmpeg：先用项目自带的，再退到系统 PATH。

    项目自带（resources/bin/<平台>/）由 scripts/fetch_binaries.py 下载，
    这样不必全局安装 ffmpeg。
    """
    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    local = config.BIN_DIR / sys.platform / name
    if local.exists():
        return str(local)
    return shutil.which("ffmpeg")


def find_js_runtime() -> str | None:
    """找 Node：yt-dlp 解 YouTube 的 JS 挑战要用（缺了会拿不到部分格式）。"""
    return shutil.which("node")


class _Logger:
    """把 yt-dlp 的输出接到本程序的日志里（[debug] 明细丢弃）。"""

    def debug(self, msg: str) -> None:
        text = (msg or "").strip()
        if text and not text.startswith("[debug]"):
            log(f"[yt-dlp] {text}")

    def info(self, msg: str) -> None:
        self.debug(msg)

    def warning(self, msg: str) -> None:
        log(f"[yt-dlp] 警告: {msg}")

    def error(self, msg: str) -> None:
        log(f"[yt-dlp] 错误: {msg}")


def _progress_hook():
    """每前进 10% 打一行进度，避免刷屏。"""
    state = {"step": -1}

    def hook(data: dict) -> None:
        if data.get("status") != "downloading":
            return
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        if not total:
            return
        percent = data.get("downloaded_bytes", 0) * 100 / total
        step = min(int(percent // 10) * 10, 100)
        if step <= state["step"]:
            return
        state["step"] = step
        speed = data.get("speed")
        eta = data.get("eta")
        speed_text = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "-"
        eta_text = f"{int(eta)}s" if eta else "-"
        log(f"下载进度 {step}%（{speed_text}，剩余 {eta_text}）")

    return hook


def _final_path(info: dict | None) -> Path | None:
    """取最终落盘的文件路径：合并后的文件记在 requested_downloads 里。"""
    for item in (info or {}).get("requested_downloads") or []:
        path = item.get("filepath") or item.get("_filename")
        if path:
            return Path(path)
    path = (info or {}).get("filepath")
    return Path(path) if path else None


def download(url: str, quality: str = "1080", proxy: str | None = None,
             cookies_file: Path | None = None) -> Path | None:
    """下载单个视频到 movies/<当天>/，返回最终文件路径；失败返回 None。"""
    out_dir = day_dir()
    options = {
        "paths": {"home": str(out_dir)},
        # 文件名带视频 id：重名/改名都不怕，也便于去重
        "outtmpl": {"default": "%(title).100s [%(id)s].%(ext)s"},
        "format": build_format(quality),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "windowsfilenames": True,  # 去掉 Windows 不允许的字符
        "socket_timeout": 30,
        "retries": 3,
        "progress_hooks": [_progress_hook()],
        "logger": _Logger(),
        "quiet": True,
        "noprogress": True,
    }
    if cookies_file:
        options["cookiefile"] = str(cookies_file)
    if proxy:
        options["proxy"] = proxy
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        options["ffmpeg_location"] = str(Path(ffmpeg).parent)
    if find_js_runtime():
        options["js_runtimes"] = {"node": {}}

    log(f"下载到 {out_dir}")
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:
        log(f"下载失败: {exc}")
        return None
    return _final_path(info)
