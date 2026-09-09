"""共享的浏览器连接、登录检测与日志工具。"""

import sys
from contextlib import contextmanager
from datetime import datetime

from playwright.sync_api import sync_playwright

# 防止打印含 ¥ 等无法编码字符的页面文本时 UnicodeEncodeError 崩溃；
# 保持终端原生编码（如 GBK），仅对无法编码的字符做替换。
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def log(msg: str) -> None:
    """带毫秒时间戳的日志输出。"""
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}", flush=True)


@contextmanager
def cdp_browser(cdp_url: str):
    """连接到一个已在运行、已登录的 Chrome（需以 --remote-debugging-port 启动）。

    复用其默认 context（含用户登录态），从而在「受信任会话」里执行抢购，
    京东才会渲染「立即免费兑换」按钮。退出时不关闭浏览器（保留会话）。

    返回 (page, context)。
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()
        try:
            yield page, context
        finally:
            # 只断开调试连接，不关闭浏览器本身
            pass


def is_login_page(page) -> bool:
    """判断当前是否停留在京东登录页。"""
    return "plogin.m.jd.com" in page.url


def ensure_logged_in(page, url: str, max_tries: int = 5) -> bool:
    """若被重定向到登录页，引导用户在浏览器中手动完成登录。"""
    tries = 0
    while is_login_page(page):
        tries += 1
        if tries > max_tries:
            log("多次尝试后仍在登录页，请检查账号状态。")
            return False
        log("检测到需要登录：请在浏览器窗口中完成登录，完成后回到终端按回车继续...")
        try:
            input(">>> 登录完成后按回车继续：")
        except EOFError:
            log("无法读取输入，跳过登录等待。")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
    return True
