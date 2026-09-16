"""MVPoster —— 真实 Chrome（CDP）+ yt-dlp 的视频下载器（唯一入口）。

不构建任何客户端界面：浏览器就是系统里的 Chrome，登录和「要下哪条视频」都在
Chrome 里完成；本程序只做三件事——

  1. 拉起（或复用）带调试端口的真实 Chrome，登录态存在 --profile 目录里；
  2. 通过 CDP 盯着「用户当前激活的那个标签页」，把标题 / URL 打到终端；
  3. 用户按下回车时，从 Chrome 导出 cookies 交给 yt-dlp，下载到 movies/<日期>/。

触发下载为什么不放在浏览器里：视频站点依赖真实登录态与风控环境，只有真实
Chrome 才稳，而给 Chrome 加一个「下载按钮」就得写扩展（等于又做一个客户端）。
把触发点放在终端——盯着当前标签页 + 一次回车——零客户端、零注入，且不会误下
用户只是随手点开的页面。

用法：
    python -m src.main                 # 进入监听：在 Chrome 里选好视频，回终端按回车
    python -m src.main --auto          # 切到视频页停留 3s 自动下载（同一 URL 只下一次）
    python -m src.main --download URL  # 直接下载该 URL 后退出
"""

import argparse
import sys
import time
import traceback

from . import browser, config, downloader
from .browser import log

_KEYBOARD_OK = True  # 终端是否支持非阻塞按键读取（管道 / 重定向时不可用）


def _keyboard_available() -> bool:
    """当前 stdin 是不是可以读按键的终端。"""
    global _KEYBOARD_OK
    try:
        if not sys.stdin or not sys.stdin.isatty():
            _KEYBOARD_OK = False
    except Exception:
        _KEYBOARD_OK = False
    return _KEYBOARD_OK


def _poll_key() -> str:
    """非阻塞读取终端上已按下的按键；没有按键时返回空串。

    Windows 用 msvcrt 直接取字符（不用等回车）；类 Unix 走 select，配合终端
    的行缓冲，仍然是按回车生效。
    """
    if not _KEYBOARD_OK:
        return ""
    try:
        if sys.platform == "win32":
            import msvcrt
            chars = []
            while msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in ("\x00", "\xe0"):  # 功能键/方向键：吞掉第二个字节
                    if msvcrt.kbhit():
                        msvcrt.getwch()
                    continue
                chars.append(char)
            return "".join(chars)
        import os
        import select
        if not select.select([sys.stdin], [], [], 0)[0]:
            return ""
        return os.read(sys.stdin.fileno(), 1024).decode(errors="replace")
    except Exception:
        return ""


def download_once(context, url: str, title: str, args) -> bool:
    """下载当前标签页指向的视频，返回是否成功。"""
    log(f"开始下载：{title or url}")
    if not config.is_video_page(url):
        log("  该 URL 不在已识别的视频页规则内，仍然交给 yt-dlp 尝试。")

    proxy = downloader.resolve_proxy()
    if proxy:
        log(f"使用代理（来自环境变量）：{downloader.mask_proxy(proxy)}")
    else:
        log("未设置代理环境变量（HTTPS_PROXY / HTTP_PROXY / ALL_PROXY），直连下载。")

    cookies_file = None
    try:
        cookies_file = browser.export_cookies(context)
    except Exception as exc:
        log(f"导出 cookies 失败（不影响公开视频）：{exc}")

    try:
        path = downloader.download(url, quality=args.quality,
                                   proxy=proxy, cookies_file=cookies_file)
    finally:
        if cookies_file is not None:
            try:
                cookies_file.unlink()
            except Exception:
                pass

    if path is None:
        return False
    log(f"已保存：{path}")
    return True


def _auto_step(context, args, page, pending: tuple | None, done: set) -> tuple | None:
    """自动模式的状态机：视频页停留够久才下载，中途切走则取消。

    返回下一轮的 pending（URL, 首次出现时间）；None 表示当前没有待下载目标。
    """
    url = page.url
    if not config.is_video_page(url) or url in done:
        if pending is not None:
            log("已切走或已下载过，取消自动下载。")
        return None
    if pending is None or pending[0] != url:
        log(f"检测到视频页，{args.auto_delay:g}s 后自动下载（期间切走则取消）。")
        return (url, time.time())
    if time.time() - pending[1] < args.auto_delay:
        return pending
    download_once(context, url, browser.page_title(page), args)
    done.add(url)  # 失败也不重试，避免在同一页循环下载
    return None


def watch(context, args) -> int:
    """监听用户当前在 Chrome 里看哪个标签页，按触发条件下载。"""
    if not args.auto and not _keyboard_available():
        log("当前终端读不到按键（stdin 不是终端），请改用 --auto 或 --download。")
        return 1
    if args.auto:
        log(f"自动模式：切到视频页停留 {args.auto_delay:g}s 即下载；q 或 Ctrl+C 退出。")
    else:
        log("在 Chrome 里打开想下载的视频页，回到终端按回车下载；q 或 Ctrl+C 退出。")

    current_url = None
    pending = None
    done: set = set()

    while True:
        page = browser.active_page(context)
        if page is None:
            log("已经找不到标签页（Chrome 窗口被关掉了？），退出。")
            return 1

        if page.url != current_url:
            current_url = page.url
            mark = "视频页 ✓" if config.is_video_page(current_url) else "未识别为视频页"
            log(f"当前标签页：{browser.page_title(page) or '(无标题)'} [{mark}]")
            log(f"  {current_url}")

        if args.auto:
            pending = _auto_step(context, args, page, pending, done)

        keys = _poll_key()
        if "q" in keys or "\x03" in keys:
            log("退出。")
            return 0
        if not args.auto and any(char in "\r\n" for char in keys):
            download_once(context, current_url, browser.page_title(page), args)

        time.sleep(config.POLL_MS / 1000)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MVPoster：用真实 Chrome 选视频，yt-dlp 下载到 movies/<日期>/")
    parser.add_argument("--auto", action="store_true",
                        help="自动模式：切到视频页停留 --auto-delay 秒后自动下载")
    parser.add_argument("--auto-delay", type=float, default=3.0,
                        help="自动模式的停留秒数，默认 3")
    parser.add_argument("--download", metavar="URL",
                        help="直接下载指定 URL 后退出（不进入监听）")
    parser.add_argument("--quality", choices=downloader.QUALITIES, default="1080",
                        help="清晰度上限，默认 1080；best 表示不限")
    parser.add_argument("--port", type=int, default=config.DEFAULT_PORT,
                        help=f"Chrome 调试端口，默认 {config.DEFAULT_PORT}")
    parser.add_argument("--profile", default=config.DEFAULT_PROFILE,
                        help=f"Chrome 用户数据目录（登录态存这里），默认 {config.DEFAULT_PROFILE}")
    parser.add_argument("--chrome", help="Chrome/Edge 可执行文件路径，默认自动查找")
    parser.add_argument("--open", dest="open_url", default=config.DEFAULT_OPEN_URL,
                        help=f"启动 Chrome 时打开的地址，默认 {config.DEFAULT_OPEN_URL}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log("=" * 20 + " MVPoster 视频下载器 " + "=" * 20)
    log(f"下载目录：{config.MOVIES_DIR}（每次下载按当天日期自动建子目录）")

    proxy = downloader.resolve_proxy()
    if proxy:
        log(f"代理：{downloader.mask_proxy(proxy)}（来自环境变量）")
    else:
        log("代理：未设置（HTTPS_PROXY / HTTP_PROXY / ALL_PROXY），将直连")
    ffmpeg = downloader.find_ffmpeg()
    if ffmpeg:
        log(f"ffmpeg：{ffmpeg}")
    else:
        log("警告：未找到 ffmpeg。运行 python scripts/fetch_binaries.py 可下载到项目内"
            "（推荐，免全局安装）；否则高于 720p 的分轨视频将无法合并。")
    if not downloader.find_js_runtime():
        log("提示：未找到 node，yt-dlp 解 YouTube 的 JS 挑战时会缺少部分格式。")

    if not browser.ensure_cdp(args):
        return 1

    code = 1
    try:
        with browser.cdp_browser(args.port) as context:
            if args.download:
                code = 0 if download_once(context, args.download, "", args) else 1
            else:
                code = watch(context, args)
    except KeyboardInterrupt:
        log("运行被中断（Ctrl+C）。")
        code = 130
    except Exception:
        log("运行异常终止:\n" + traceback.format_exc().rstrip())
        code = 1

    log(f"运行结束 | 退出码 {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
