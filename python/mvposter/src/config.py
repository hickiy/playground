"""集中管理常量：目录、视频站点规则、CDP 端口、代理与配置文件。"""

import re
from pathlib import Path
from typing import NamedTuple

# ---- 目录（都相对项目根目录，与启动时的工作目录无关）----
ROOT = Path(__file__).resolve().parent.parent
MOVIES_DIR = ROOT / "movies"   # 下载产物：movies/<日期>/<标题>.<ext>
LOG_DIR = ROOT / "logs"        # 按天分的执行日志
DATA_DIR = ROOT / "data"       # 本地记录：下载历史 / 去重（见 src/store.py）
DB_FILE = DATA_DIR / "mvposter.db"
# ffmpeg 是系统里的外部工具（PATH / Homebrew / winget）：本程序不安装、不代管、也不检查，
# 项目内也不放副本（原来那份 resources/bin 已删除）

# ---- CDP（浏览器由 browserhost 常驻提供，本项目只连接、不启动不关闭）----
CDP_PORT = 9222   # browserhost 实例的调试端口（它自己的默认值也是 9222）
POLL_MS = 300     # 主循环间隔：轮询按键，顺带刷新「当前激活标签页」

# ---- 代理 ----
# 只管 **yt-dlp 下载**用的代理（浏览器归 browserhost，它的代理由那个实例自己决定），
# 想改就编辑项目根目录的 config.json，或用环境变量临时覆盖：
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
# 加一个平台就加一条：关键字（--platform 用）-> 显示名 / 视频页正则。
# 正则用来判断「当前标签页是不是视频页」：自动模式只对命中的页面自动下载，
# 手动模式仅用它提示「这条像不像视频页」。
class Platform(NamedTuple):
    """一个视频站点。"""

    name: str                              # 日志里显示的名字
    patterns: tuple[re.Pattern[str], ...]  # 该站点的视频页 URL 规则


PLATFORMS: dict[str, Platform] = {
    "youtube": Platform(
        "YouTube",
        (re.compile(r"^https?://(www\.|m\.)?youtube\.com/(watch\?|shorts/|live/)"),
         re.compile(r"^https?://youtu\.be/")),
    ),
    "tiktok": Platform(
        "TikTok",
        (re.compile(r"^https?://(www\.|m\.)?tiktok\.com/@[^/]+/(video|photo)/"),
         re.compile(r"^https?://(vm|vt)\.tiktok\.com/")),
    ),
}


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


# ---- 去重键 ----
_YT_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_ID_IN_URL = re.compile(r"(?:[?&]v=|/shorts/|/live/|youtu\.be/)([A-Za-z0-9_-]{11})")


def youtube_id(text: str) -> str | None:
    """从链接或裸 id 里取出 YouTube 的 11 位 video id；不是 YouTube 返回 None。"""
    value = (text or "").strip()
    if _YT_BARE_ID.match(value):
        return value
    match = _YT_ID_IN_URL.search(value)
    return match.group(1) if match else None


def dedupe_key(text: str) -> str:
    """数据库去重键。

    YouTube 统一用 11 位 video_id（watch / shorts / live / youtu.be 都归一到同一个键）；
    其他站点用 ``平台:URL``，没识别出平台时用 ``url:`` 前缀。
    """
    value = (text or "").strip()
    found = youtube_id(value)
    if found:
        return found
    return f"{platform_of(value) or 'url'}:{value}"
