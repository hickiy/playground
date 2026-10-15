"""连接 browserhost 常驻的 CDP 服务：本项目不启动、不关闭浏览器，也不管 profile。

浏览器（真实 Chrome + 登录态 + 用户数据目录）由独立项目 **browserhost** 常驻提供：
在 `../browserhost` 里执行一次 `python main.py start`，之后调试端口一直可用，
窗口随手关掉都行。本项目要做的只有三件事——

  - 连上那个调试端口（连不上就给出启动提示并退出，绝不自己去拉一个浏览器）；
  - 借它的 cookies 给 yt-dlp（登录态只存在它的 profile 里，本项目读不到）；
  - 需要页面时**自己新开页签**，用完关掉自己的页签（见 `src/publish.py`）。

多任务共用同一个实例时的纪律（见 browserhost/README.md）：只连接，不启动不关闭浏览器；
只动自己开的页签；不发全局 CDP 命令（`Browser.close` / `Network.setCookie` / 改代理等）。
"""

import json
import os
import tempfile
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

from .logging import log

PROBE_TIMEOUT_S = 1.5        # 探测调试端口（L1：只看 /json/version），失败要快
CONNECT_TIMEOUT_MS = 10_000  # connect_over_cdp 的握手超时


def cdp_url(port: int) -> str:
    """调试端口对应的 CDP 地址（browserhost 的实例按约定跑在本机回环上）。"""
    return f"http://localhost:{port}"


def ensure_available(url: str) -> bool:
    """确认调试端口有人在听；连不上就打印「怎么把 browserhost 起起来」并返回 False。

    只探 `/json/version`（HTTP 层），不起 Playwright：失败得快、也没有副作用。
    「端口在、CDP 不响应」的僵死实例由 :func:`connect` 的握手超时兜住。
    """
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/json/version",
                                    timeout=PROBE_TIMEOUT_S) as resp:
            if resp.status == 200:
                return isinstance(json.loads(resp.read().decode("utf-8", "replace")), dict)
    except Exception:
        pass
    log(f"连不上 CDP 服务（{url}）。浏览器与登录态由 browserhost 常驻提供，先把它起起来：")
    log("  cd ../browserhost && python main.py start     # 幂等：已在跑且健康就直接复用")
    log("  cd ../browserhost && python main.py restart   # 端口有响应但连不上时用它")
    return False


@contextmanager
def connect(url: str):
    """连接常驻 Chrome，返回它的默认 context（登录态就在里面）。

    退出时只**断开 CDP 连接**（停掉 Playwright 驱动）：浏览器是 browserhost 的，
    从头到尾不归本程序关。因此这里不调用 `browser.close()`——它对 CDP 连接的语义
    随版本而变，最坏会把浏览器一起带走，与「只连接」的约定冲突。
    """
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(url, timeout=CONNECT_TIMEOUT_MS)
        contexts = browser.contexts
        if not contexts:
            raise RuntimeError(f"连上了 {url}，但这个实例没有可用的浏览器上下文（context）。")
        yield contexts[0]
    finally:
        playwright.stop()


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


def export_cookies(context):
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
