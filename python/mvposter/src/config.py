"""集中管理常量：目录、视频站点规则、Chrome/CDP 参数、代理与配置文件。"""

import re
from pathlib import Path
from typing import NamedTuple

# ---- 目录（都相对项目根目录，与启动时的工作目录无关）----
ROOT = Path(__file__).resolve().parent.parent
MOVIES_DIR = ROOT / "movies"   # 下载产物：movies/<日期>/<标题>.<ext>
LOG_DIR = ROOT / "logs"        # 按天分的执行日志
# ffmpeg 不再放在项目内，而是装在系统里，见 scripts/fetch_binaries.py

# ---- Chrome / CDP ----
DEFAULT_PORT = 9222
DEFAULT_PROFILE = "./chrome_profile"  # 用户数据目录：登录态保存在这里
CDP_WAIT_MS = 15000   # 等调试端口就绪的超时
POLL_MS = 300         # 主循环间隔：轮询按键，顺带刷新「当前激活标签页」

# ---- 代理 ----
# 默认走本机代理（Chrome 的登录过程和 yt-dlp 的下载都走它），想改就编辑项目根目录的
# config.json，或用环境变量临时覆盖：
#     环境变量（HTTPS_PROXY / HTTP_PROXY / ALL_PROXY） > config.json > DEFAULT_PROXY
# 不提供 --proxy 开关：参数会进 shell 历史、进程列表和日志，不如放在文件和环境变量里。
CONFIG_FILE = ROOT / "config.json"     # 用户可改的运行配置，见 README「代理与配置」
DEFAULT_PROXY = "http://127.0.0.1:1080"  # config.json 里把 proxy 写成空串即直连

PROXY_ENV_VARS = (
    "HTTPS_PROXY", "https_proxy",
    "HTTP_PROXY", "http_proxy",
    "ALL_PROXY", "all_proxy",
)

# ---- 视频站点 ----
# 加一个平台就加一条：关键字（--platform 用）-> 显示名 / 视频页正则 / 首页。
# 正则用来判断「当前标签页是不是视频页」：自动模式只对命中的页面自动下载，
# 手动模式仅用它提示「这条像不像视频页」。
class Platform(NamedTuple):
    """一个视频站点。"""

    name: str                            # 日志里显示的名字
    patterns: tuple[re.Pattern[str], ...]  # 该站点的视频页 URL 规则
    home: str                            # 首页：启动 Chrome 时默认打开的地址


PLATFORMS: dict[str, Platform] = {
    "youtube": Platform(
        "YouTube",
        (re.compile(r"^https?://(www\.|m\.)?youtube\.com/(watch\?|shorts/|live/)"),
         re.compile(r"^https?://youtu\.be/")),
        "https://www.youtube.com",
    ),
    "tiktok": Platform(
        "TikTok",
        (re.compile(r"^https?://(www\.|m\.)?tiktok\.com/@[^/]+/(video|photo)/"),
         re.compile(r"^https?://(vm|vt)\.tiktok\.com/")),
        "https://www.tiktok.com",
    ),
}

# 没指定 --platform 时启动 Chrome 打开的地址
DEFAULT_OPEN_URL = PLATFORMS["youtube"].home


def platform_of(url: str) -> str | None:
    """该 URL 属于哪个平台的关键字；都不匹配返回 None。"""
    text = url or ""
    for keyword, platform in PLATFORMS.items():
        if any(p.match(text) for p in platform.patterns):
            return keyword
    return None


def is_video_page(url: str, platform: str | None = None) -> bool:
    """该 URL 是否属于已识别的视频页；给了 platform 就只看该平台。"""
    keyword = platform_of(url)
    return keyword is not None and (platform is None or keyword == platform)
