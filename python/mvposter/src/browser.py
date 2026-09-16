"""日志、启动/连接真实 Chrome、读取当前标签页、导出 cookies。

浏览器一定是**真实的 Chrome**（不是 Playwright 自带的 Chromium）：只有真实
Chrome 的用户数据目录里才有用户的登录态，下载需要登录的视频才拿得到。
Chrome 由本程序拉起，或复用已经开着调试端口的那个，统一通过 CDP 连接。
"""

import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import config

# 防止打印含 ¥/emoji 等无法编码的页面标题时 UnicodeEncodeError 崩溃；
# 保持终端原生编码（如 GBK），只把无法编码的字符替换掉。
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

_log_fh = None    # 当天的日志文件句柄
_log_date = None  # 句柄对应的日期，跨天自动换文件


def _write_log(line: str) -> None:
    """按天追加写日志；写日志失败绝不能影响下载主流程。"""
    global _log_fh, _log_date
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        if _log_fh is None or _log_date != today:
            if _log_fh is not None:
                _log_fh.close()
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            _log_fh = (config.LOG_DIR / f"mvposter_{today}.log").open("a", encoding="utf-8")
            _log_date = today
        _log_fh.write(line + "\n")
        _log_fh.flush()  # 随时可能被 Ctrl+C 打断，逐行落盘
    except Exception:
        pass


def log(msg: str) -> None:
    """输出日志：终端 + 当天日志文件。"""
    now = datetime.now()
    stamp = now.strftime("%H:%M:%S.%f")[:-3]
    try:
        print(f"[{stamp}] {msg}", flush=True)
    except Exception:
        pass
    _write_log(f"[{now.strftime('%Y-%m-%d')} {stamp}] {msg}")


_browser = None        # 当前 CDP 连接，退出时清理
_we_launched = False   # Chrome 是否由本程序启动（复用别人的实例就不能关）


# ---- 启动带调试端口的真实 Chrome ----

def find_chrome() -> str | None:
    """按平台常见安装位置查找 Chrome/Edge 可执行文件，找不到返回 None。"""
    if sys.platform == "darwin":  # macOS
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    elif sys.platform == "win32":  # Windows
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    else:  # Linux / 其它类 Unix
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
        ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def cdp_reachable(cdp_url: str, timeout_s: float = 1.0) -> bool:
    """探测该地址上是否已有可用的 CDP 调试端口。"""
    try:
        with urllib.request.urlopen(cdp_url.rstrip("/") + "/json/version",
                                    timeout=timeout_s) as resp:
            return resp.status == 200
    except Exception:
        return False


def launch_chrome(port: int, profile: str, url: str,
                  chrome_path: str | None = None) -> bool:
    """启动带远程调试端口的真实 Chrome，返回是否成功拉起进程。"""
    chrome = chrome_path or find_chrome()
    if not chrome:
        log("未找到 Chrome/Edge，请用 --chrome 指定可执行文件路径。")
        return False
    profile_dir = Path(profile).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    log(f"启动 Chrome: {chrome}（调试端口 {port}，用户数据目录 {profile_dir}）")
    try:
        subprocess.Popen([
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            # 关掉「关闭窗口后继续在后台运行」：否则窗口关了 chrome.exe 还留着，
            # 既占着用户数据目录的锁，也让「退出时关掉 Chrome」名不副实。
            "--disable-background-mode",
            url,
        ])
    except Exception as exc:
        log(f"启动 Chrome 失败: {exc}")
        return False
    return True


def wait_for_cdp(cdp_url: str, timeout_ms: int = config.CDP_WAIT_MS) -> bool:
    """等调试端口就绪——Chrome 从启动到监听端口有延迟。"""
    deadline = time.time() + timeout_ms / 1000
    while True:
        if cdp_reachable(cdp_url):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.2)


def ensure_cdp(args) -> bool:
    """确保存在一个可连的、带调试端口的 Chrome。

    已经开着调试端口就直接复用（退出时也不会去关别人的窗口）；否则自己拉起
    一个，退出时负责关闭。
    """
    global _we_launched
    cdp_url = f"http://localhost:{args.port}"
    if cdp_reachable(cdp_url):
        log(f"复用已开启调试端口的 Chrome（{cdp_url}），退出时不会关闭它。")
        return True
    if not launch_chrome(args.port, args.profile, args.open_url, args.chrome):
        return False
    if not wait_for_cdp(cdp_url):
        log(f"等待 {cdp_url} 就绪超时。若这个用户数据目录已被另一个正在运行的 Chrome "
            "占用，新窗口不会开调试端口——请先关掉那个 Chrome，或换 --profile。")
        return False
    _we_launched = True
    return True


def _close_browser() -> None:
    """关闭本程序启动的 Chrome；复用别人的实例时只断开连接。

    对 CDP 连接直接 browser.close() 只是断开连接，必须显式发 CDP 的
    Browser.close 才能真正关掉 Chrome。
    """
    global _browser
    browser, _browser = _browser, None
    if browser is None or not _we_launched:
        return
    try:
        browser.new_browser_cdp_session().send("Browser.close")
        log("已关闭 Chrome 窗口。")
    except Exception:
        pass


@contextmanager
def cdp_browser(port: int):
    """连接已就绪的 Chrome，返回它的默认 context（含登录态）。

    退出（正常结束、异常或 Ctrl+C）时会关闭本程序启动的 Chrome。
    """
    global _browser
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
        _browser = browser
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        try:
            yield context
        finally:
            _close_browser()


# ---- 读取用户在 Chrome 里选的视频 ----

def active_page(context):
    """返回用户当前正在看（激活）的标签页，拿不到就退回最后一个普通标签页。

    CDP 没有「哪个标签页被选中」这种字段，只能问页面自己：只有被切到前台的那
    一个会返回 document.hasFocus() / visibilityState 为真。
    """
    pages = [p for p in context.pages if not (p.url or "").startswith("devtools://")]
    for page in reversed(pages):
        try:
            if page.evaluate("document.hasFocus()"):
                return page
        except Exception:
            continue
    for page in reversed(pages):
        try:
            if page.evaluate("document.visibilityState") == "visible":
                return page
        except Exception:
            continue
    return pages[-1] if pages else None


def page_title(page) -> str:
    """页面标题；取不到时返回空串（关闭中的标签页会抛异常）。"""
    try:
        return page.title() or ""
    except Exception:
        return ""


# ---- 导出 cookies 给 yt-dlp ----

def _all_cookies(context) -> list[dict]:
    """取出 Chrome 当前所有 cookies。

    正常走 context.cookies()；某些版本上 CDP 连接的默认 context 会返回空，
    这时直接问 CDP 要（Network.getAllCookies 的字段名和 Playwright 一致）。
    """
    try:
        cookies = context.cookies()
    except Exception:
        cookies = []
    if cookies:
        return cookies
    for page in context.pages:
        try:
            session = context.new_cdp_session(page)
            return session.send("Network.getAllCookies").get("cookies") or []
        except Exception:
            continue
    return []


def export_cookies(context) -> Path | None:
    """把 Chrome 里的 cookies 写成 Netscape 格式的临时文件（yt-dlp 用）。

    登录态只存在 Chrome 的用户数据目录里，yt-dlp 读不到，所以通过 CDP 取一次
    导出；文件由调用方在下载结束后删除。
    """
    cookies = _all_cookies(context)
    lines = [
        "# Netscape HTTP Cookie File",
        "# 由 MVPoster 通过 CDP 从 Chrome 导出，供 yt-dlp 使用",
        "",
    ]
    for cookie in cookies:
        domain = (cookie.get("domain") or "").strip()
        name = cookie.get("name") or ""
        if not domain or not name:
            continue
        value = (cookie.get("value") or "")
        value = value.replace("\t", "").replace("\r", "").replace("\n", "")
        # HttpOnly 的 cookie 必须以 #HttpOnly_ 开头，否则 MozillaCookieJar 当注释跳过
        prefix = "#HttpOnly_" if cookie.get("httpOnly") else ""
        lines.append("\t".join([
            prefix + domain,
            "TRUE" if domain.startswith(".") else "FALSE",
            cookie.get("path") or "/",
            "TRUE" if cookie.get("secure") else "FALSE",
            str(max(0, int(cookie.get("expires") or 0))),  # 会话 cookie（-1）写成 0
            name,
            value,
        ]))

    count = len(lines) - 3
    if not count:
        log("未能从 Chrome 导出 cookies（下载需要登录的视频可能会失败）。")
        return None

    handle, path = tempfile.mkstemp(prefix="mvposter_cookies_", suffix=".txt")
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    log(f"已从 Chrome 导出 {count} 个 cookie 供 yt-dlp 使用。")
    return Path(path)
