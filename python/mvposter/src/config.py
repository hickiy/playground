"""集中管理常量：目录、视频页规则、Chrome/CDP 参数与代理环境变量。"""

import re
from pathlib import Path

# ---- 目录（都相对项目根目录，与启动时的工作目录无关）----
ROOT = Path(__file__).resolve().parent.parent
MOVIES_DIR = ROOT / "movies"   # 下载产物：movies/<日期>/<标题>.<ext>
LOG_DIR = ROOT / "logs"        # 按天分的执行日志
BIN_DIR = ROOT / "resources" / "bin"  # 项目自带的二进制（ffmpeg 等），见 scripts/fetch_binaries.py

# ---- Chrome / CDP ----
DEFAULT_PORT = 9222
DEFAULT_PROFILE = "./chrome_profile"  # 用户数据目录：登录态保存在这里
DEFAULT_OPEN_URL = "https://www.youtube.com"
CDP_WAIT_MS = 15000   # 等调试端口就绪的超时
POLL_MS = 300         # 主循环间隔：轮询按键，顺带刷新「当前激活标签页」

# ---- 代理：只从环境变量读，不提供命令行开关 ----
# 有命令行开关的话，用户名密码就会进 shell 历史、进程列表和日志，不如放在环境变量里。
PROXY_ENV_VARS = (
    "HTTPS_PROXY", "https_proxy",
    "HTTP_PROXY", "http_proxy",
    "ALL_PROXY", "all_proxy",
)

# ---- 视频页规则 ----
# 自动模式只对命中的页面自动下载；手动模式仅用它提示「这条像不像视频页」。
VIDEO_URL_PATTERNS = (
    re.compile(r"^https?://(www\.|m\.)?youtube\.com/(watch\?|shorts/|live/)"),
    re.compile(r"^https?://youtu\.be/"),
    re.compile(r"^https?://(www\.|m\.)?tiktok\.com/@[^/]+/(video|photo)/"),
    re.compile(r"^https?://(vm|vt)\.tiktok\.com/"),
)


def is_video_page(url: str) -> bool:
    """该 URL 是否属于已识别的视频页（YouTube / TikTok）。"""
    return any(p.match(url or "") for p in VIDEO_URL_PATTERNS)
