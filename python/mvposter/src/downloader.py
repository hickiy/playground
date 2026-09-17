"""用 yt-dlp 下载视频：产物落在 movies/<日期>/，代理默认走本机 127.0.0.1:1080。

yt-dlp 以库的形式调用（不依赖外部 yt-dlp 可执行文件）；ffmpeg 用它合并分轨格式，
只用系统里那份（PATH，或 Homebrew / winget 的目录），项目内不放副本——程序启动时
会检查有没有，缺了就提示安装指引并退出（见 src/main.py 的 require_ffmpeg）。
代理的取值顺序是「环境变量 > config.json > 内置默认」，细节见下面的 proxy 一节。
"""

import json
import os
import shutil
import socket
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

import yt_dlp

from . import config
from .browser import log

# --quality 允许的档位；best 表示不限高度
QUALITIES = ("1080", "720", "480", "360", "best")

_proxy_cache: tuple[str | None, str] | None = None  # 一次运行只解析一次（含探测端口）
_LOOPBACK = ("127.0.0.1", "localhost", "::1")


def load_config() -> dict:
    """读项目根目录的 config.json；文件不在就用内置默认值。

    读不了 / 内容不是 JSON 对象时只告警，不影响运行。
    """
    path = config.CONFIG_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"读 {path.name} 失败，改用内置默认值：{exc}")
        return {}
    if not isinstance(data, dict):
        log(f'{path.name} 的内容应该是一个 JSON 对象（形如 {{"proxy": "..."}}），已忽略。')
        return {}
    return data


def _with_scheme(proxy: str) -> str:
    """补上协议头：配置里写 127.0.0.1:1080 也认。"""
    return proxy if "://" in proxy else f"http://{proxy}"


def _local_proxy_alive(proxy: str) -> bool:
    """探一下本机代理的端口是不是真的有人监听。

    默认值指向本机服务，机器上没跑代理时硬用会连浏览器都打不开，所以只对
    127.0.0.1 / localhost 这种本机地址探测；远端代理不探（网络抖动不能当成没配）。
    """
    parts = urllib.parse.urlsplit(proxy)
    if parts.hostname not in _LOOPBACK or not parts.port:
        return True
    try:
        with socket.create_connection((parts.hostname, parts.port), timeout=1):
            return True
    except OSError:
        return False


def _pick_proxy() -> tuple[str | None, str]:
    """定下用哪个代理、以及它是打哪来的：(地址, 来源说明)，地址为 None 表示直连。"""
    for name in config.PROXY_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return _with_scheme(value), f"环境变量 {name}"
    if config.CONFIG_FILE.exists():
        raw = load_config().get("proxy")
        if raw is not None:
            text = str(raw).strip()
            return (_with_scheme(text) if text else None), f"{config.CONFIG_FILE.name} 里的 proxy"
    return _with_scheme(config.DEFAULT_PROXY), "内置默认值"


def _resolve_proxy() -> tuple[str | None, str]:
    """解析并缓存代理设置：一次运行只算一次，也避免重复探测端口。"""
    global _proxy_cache
    if _proxy_cache is None:
        proxy, source = _pick_proxy()
        if proxy and not _local_proxy_alive(proxy):
            log(f"代理 {mask_proxy(proxy)}（{source}）连不上，本次改为直连；"
                f"要改就编辑 {config.CONFIG_FILE.name} 的 proxy。")
            proxy, source = None, f"{source}，但连不上，已改直连"
        _proxy_cache = (proxy, source)
    return _proxy_cache


def resolve_proxy() -> str | None:
    """本次运行要用的代理地址；None 表示直连。

    yt-dlp 自己不会读 HTTP(S)_PROXY，也不会读 config.json，必须显式传给它。
    """
    return _resolve_proxy()[0]


def proxy_source() -> str:
    """代理地址的来源说明（日志里讲清楚「为什么是这个代理」）。"""
    return _resolve_proxy()[1]


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


def which_binary(name: str) -> str | None:
    """在 PATH 里找可执行文件，找不到再补几个常见目录。

    - macOS：Homebrew 的两个前缀（从访达 / VS Code 启动时 PATH 里常常没有）；
    - Windows：winget 的 shim 目录（刚用它装完 ffmpeg 的进程不用重开终端）。
    """
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "darwin":
        prefixes = ("/opt/homebrew/bin", "/usr/local/bin")
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        prefixes = (str(Path(local) / "Microsoft" / "WinGet" / "Links"),) if local else ()
    else:
        prefixes = ()
    for prefix in prefixes:
        candidate = Path(prefix) / name
        if candidate.exists():
            return str(candidate)
    return None


def find_ffmpeg() -> str | None:
    """找 ffmpeg：只用系统里那份（PATH，或 Homebrew / winget 的目录）。

    程序不代装 ffmpeg、项目内也不放副本；找不到时由 src/main.py 提示安装并退出。
    """
    return which_binary("ffmpeg")


# 没装 ffmpeg 时的安装指引（按平台给一句能直接照做的话）
FFMPEG_HINTS = {
    "win32": "winget install Gyan.FFmpeg（或从 https://www.gyan.dev/ffmpeg/builds/ 下 zip，"
             "把里面的 bin 目录加进 PATH）",
    "darwin": "brew install ffmpeg（还没装 Homebrew 就先跑 https://brew.sh 上的那行命令）",
}


def ffmpeg_hint() -> str:
    """本平台的 ffmpeg 安装指引（日志里直接用）。"""
    return FFMPEG_HINTS.get(
        sys.platform, "apt install ffmpeg（Debian/Ubuntu）/ dnf install ffmpeg / "
                      "pacman -S ffmpeg，按你的发行版选")


def find_js_runtime() -> str | None:
    """找 Node：yt-dlp 解 YouTube 的 JS 挑战要用（缺了会拿不到部分格式）。"""
    return which_binary("node")


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
    # 启动时已经确认过 ffmpeg 存在（见 src/main.py 的 require_ffmpeg）
    ffmpeg = find_ffmpeg()
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
