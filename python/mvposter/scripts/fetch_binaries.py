"""确保系统里装好了 ffmpeg（yt-dlp 合并分轨、探测格式要用）。

一律装在系统里，项目内不放副本：先看系统里有没有（PATH，以及 winget / Homebrew 的
目录），没有就用包管理器装——Windows 用 winget，macOS 用 Homebrew。这两个包管理器
本身也没有的话，就提示你自行安装，不会偷偷改系统，也不往项目里塞文件。

用法:
    python scripts/fetch_binaries.py      # 检测，缺了就装

代理与主程序一致（环境变量 > config.json > 内置默认），装的时候会把代理也传给包管理器。
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.browser import log                      # noqa: E402
from src.downloader import mask_proxy, proxy_source, resolve_proxy, which_binary  # noqa: E402

# winget 里最常用的完整构建（含 ffmpeg / ffprobe，yt-dlp 社区也常推这个）
WINGET_PACKAGE = "Gyan.FFmpeg"

# 没有可用的包管理器（或装不上）时，按平台给一句人话
MANUAL_HINTS = {
    "win32": "自己装一下 ffmpeg：从 https://www.gyan.dev/ffmpeg/builds/ 下 zip 后把 bin "
             "目录加进 PATH；或者先装 winget（Microsoft Store 搜「应用安装程序」）。",
    "darwin": "自己装一下 ffmpeg：先装 Homebrew（https://brew.sh 一条命令），或从 "
              "https://ffmpeg.martin-riedl.de/ 下静态构建后放进 PATH。",
}


def verify(ffmpeg: str) -> bool:
    """跑一次 -version，确认这份 ffmpeg 真的能用。"""
    try:
        done = subprocess.run([ffmpeg, "-version"], capture_output=True,
                              text=True, timeout=30)
    except Exception as exc:
        log(f"无法执行 {ffmpeg}：{exc}")
        return False
    if done.returncode != 0:
        log(f"执行失败（退出码 {done.returncode}）：{done.stderr.strip()[:200]}")
        return False
    log(f"可用：{done.stdout.splitlines()[0] if done.stdout else ffmpeg}")
    return True


def package_manager() -> list[str] | None:
    """本平台的安装命令（winget / brew）；没有可用的包管理器就返回 None。"""
    if sys.platform == "win32":
        winget = which_binary("winget")
        if winget:
            return [winget, "install", "--id", WINGET_PACKAGE, "--exact",
                    "--accept-package-agreements", "--accept-source-agreements"]
    elif sys.platform == "darwin":
        brew = which_binary("brew")
        if brew:
            return [brew, "install", "ffmpeg"]
    return None


def run_install(command: list[str], proxy: str | None) -> bool:
    """跑安装命令：输出直接接到终端（几分钟的进度看得见），代理一并传给它。"""
    log(f"开始安装：{' '.join(command)}（要几分钟，请稍等）…")
    env = None
    if proxy:
        env = {**os.environ, "HTTPS_PROXY": proxy, "HTTP_PROXY": proxy, "ALL_PROXY": proxy}
    try:
        done = subprocess.run(command, env=env, timeout=1800)
    except Exception as exc:
        log(f"安装命令失败：{exc}")
        return False
    if done.returncode != 0:
        log(f"安装命令退出码 {done.returncode}。")
        return False
    return True


def manual_hint() -> str:
    """手动安装指引（没有包管理器、或包管理器装不上时用）。"""
    return MANUAL_HINTS.get(
        sys.platform, "用系统自带的包管理器装 ffmpeg（apt / dnf / pacman 等）。")


def main() -> int:
    log("=" * 20 + " 检查系统里的 ffmpeg " + "=" * 20)

    ffmpeg = which_binary("ffmpeg")
    if ffmpeg:
        log(f"系统里已经有 ffmpeg：{ffmpeg}")
        return 0 if verify(ffmpeg) else 1

    log("系统里没有找到 ffmpeg，准备用包管理器装。")
    command = package_manager()
    if command is None:
        log("本机没有可用的包管理器（Windows 用 winget，macOS 用 Homebrew）。")
        log(f"  {manual_hint()}")
        return 1

    proxy = resolve_proxy()
    log(f"代理：{mask_proxy(proxy) if proxy else '直连'}（{proxy_source()}）")
    if not run_install(command, proxy):
        log(f"安装没成功，可以手动处理：{manual_hint()}")
        return 1

    ffmpeg = which_binary("ffmpeg")
    if not ffmpeg:
        log("装完了，但当前进程还看不到它——PATH 要新开的终端才刷新："
            "重开一个终端再跑一次本脚本，或重启 VS Code。")
        return 1
    log(f"已装好：{ffmpeg}")
    return 0 if verify(ffmpeg) else 1


if __name__ == "__main__":
    sys.exit(main())
