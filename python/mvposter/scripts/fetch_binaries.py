"""把 ffmpeg 下载到项目内（resources/bin/<平台>/），免去全局安装。

用的是 yt-dlp 官方维护的 FFmpeg 构建（github.com/yt-dlp/FFmpeg-Builds）：
它带着 yt-dlp 需要的那套编解码器，且随 yt-dlp 一起更新。

用法:
    python scripts/fetch_binaries.py            # 已存在则跳过
    python scripts/fetch_binaries.py --force    # 重新下载

代理同样只从环境变量读（HTTPS_PROXY / HTTP_PROXY / ALL_PROXY）。
"""

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config                      # noqa: E402
from src.browser import log                 # noqa: E402
from src.downloader import mask_proxy, resolve_proxy  # noqa: E402

RELEASE_URL = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"
CHECKSUMS = "checksums.sha256"


def binary_names() -> tuple[str, str]:
    """本平台下两个可执行文件的名字。"""
    suffix = ".exe" if sys.platform == "win32" else ""
    return f"ffmpeg{suffix}", f"ffprobe{suffix}"


def asset_name() -> str | None:
    """按平台/架构挑官方构建名；官方没有 macOS 构建，返回 None。"""
    arch = platform.machine().lower()
    if sys.platform == "win32":
        return ("ffmpeg-master-latest-win64-gpl.zip" if arch in ("amd64", "x86_64")
                else "ffmpeg-master-latest-win32-gpl.zip")
    if sys.platform.startswith("linux"):
        return ("ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
                if arch in ("aarch64", "arm64")
                else "ffmpeg-master-latest-linux64-gpl.tar.xz")
    return None


def _opener(proxy: str | None):
    """带代理的 urllib opener（代理为空时直连）。"""
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    return urllib.request.build_opener(handler)


def fetch_to(url: str, dest: Path, proxy: str | None) -> str:
    """下载到 dest，返回内容的 sha256。

    顺带校验 Content-Length：大文件被代理/网络中断时，读取会静默结束，
    只靠 sha256 是能发现，但先比长度能立刻说出「下得不完整」。
    """
    digest = hashlib.sha256()
    written = 0
    with _opener(proxy).open(url, timeout=60) as resp, dest.open("wb") as out:
        declared = int(resp.headers.get("Content-Length") or 0)
        while chunk := resp.read(1024 * 256):
            out.write(chunk)
            digest.update(chunk)
            written += len(chunk)
    if declared and written != declared:
        raise RuntimeError(f"下载不完整：声明 {declared} 字节，实际 {written} 字节")
    log(f"下载完成：{written / 1024 / 1024:.1f} MB")
    return digest.hexdigest()


def fetch_checksums(proxy: str | None) -> dict[str, str]:
    """取官方 sha256 清单；取不到就返回空（只告警，不阻断）。"""
    try:
        with _opener(proxy).open(RELEASE_URL + CHECKSUMS, timeout=60) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        log(f"无法获取校验和清单（跳过校验）：{exc}")
        return {}
    table = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            table[parts[1].lstrip("*")] = parts[0].lower()
    return table


def extract(archive: Path, target: Path) -> list[str]:
    """从压缩包里只取出 ffmpeg / ffprobe，返回落地的文件名列表。"""
    wanted = set(binary_names())
    target.mkdir(parents=True, exist_ok=True)
    found = []
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                name = Path(member).name
                if name in wanted:
                    with zf.open(member) as src, (target / name).open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found.append(name)
    else:
        with tarfile.open(archive, "r:xz") as tf:
            for member in tf.getmembers():
                name = Path(member.name).name
                if member.isfile() and name in wanted:
                    src = tf.extractfile(member)
                    with (target / name).open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found.append(name)
    if sys.platform != "win32":
        for name in found:
            (target / name).chmod(0o755)
    return found


def verify(target: Path) -> bool:
    """跑一下 -version，确认二进制真的可用（顺便挡住被改坏的文件）。"""
    ffmpeg = target / binary_names()[0]
    try:
        out = subprocess.run([str(ffmpeg), "-version"], capture_output=True,
                             text=True, timeout=30)
    except Exception as exc:
        log(f"验证失败（无法执行 {ffmpeg}）：{exc}")
        return False
    if out.returncode != 0:
        log(f"验证失败（退出码 {out.returncode}）：{out.stderr.strip()[:200]}")
        return False
    log(f"验证通过：{out.stdout.splitlines()[0] if out.stdout else ffmpeg}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 ffmpeg 到项目内，免全局安装")
    parser.add_argument("--force", action="store_true", help="已存在也重新下载")
    parser.add_argument("--skip-checksum", action="store_true",
                        help="跳过 sha256 校验（上游滚动更新导致误报时才用）")
    args = parser.parse_args()

    target = config.BIN_DIR / sys.platform
    ffmpeg = target / binary_names()[0]
    log("=" * 20 + " 下载项目自带 ffmpeg " + "=" * 20)
    log(f"目标目录：{target}")
    if ffmpeg.exists() and not args.force:
        log("已存在，跳过下载（--force 可重新下载）。")
        return 0

    asset = asset_name()
    if asset is None:
        log("官方没有本平台（macOS）的构建。请任选一种："
            "brew install ffmpeg；或者从 https://evermeet.cx/ffmpeg/ 下载后 "
            f"放到 {target}（文件名 ffmpeg / ffprobe）。")
        return 1

    proxy = resolve_proxy()
    log(f"代理：{mask_proxy(proxy) if proxy else '未设置（直连）'}")
    url = RELEASE_URL + asset
    log(f"下载：{url}")

    work_dir = Path(tempfile.mkdtemp(prefix="mvposter_ffmpeg_"))
    archive = work_dir / asset
    try:
        # 上游是滚动发布（latest 每天重建），代理/CDN 缓存着旧包而校验和已更新时
        # 会误报，所以不匹配就重下一次；两次都不行再中止。
        for attempt in (1, 2):
            digest = fetch_to(url, archive, proxy)
            if args.skip_checksum:
                log("已跳过校验和校验（--skip-checksum）。")
                break
            expected = fetch_checksums(proxy).get(asset)
            if not expected:
                log("未取到官方校验和，跳过校验。")
                break
            if expected == digest:
                log("校验和校验通过。")
                break
            log(f"第 {attempt} 次校验不匹配：期望 {expected}，实际 {digest}。")
        else:
            log("两次下载的校验和都对不上，已中止（确认无误可用 --skip-checksum）。")
            return 1

        found = extract(archive, target)
        if set(found) != set(binary_names()):
            log(f"压缩包里没找到预期的文件（只拿到 {found or '空'}）。")
            return 1
        log(f"已放入：{', '.join(found)}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    if not verify(target):
        return 1
    log("完成：程序会自动优先使用项目内的 ffmpeg，无需再全局安装。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
