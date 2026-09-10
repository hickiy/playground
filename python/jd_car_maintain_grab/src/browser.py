"""共享的浏览器连接、登录检测与日志工具。"""

import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

# 防止打印含 ¥ 等无法编码字符的页面文本时 UnicodeEncodeError 崩溃；
# 保持终端原生编码（如 GBK），仅对无法编码的字符做替换。
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


# 执行日志目录（项目根目录下，与启动时的工作目录无关）
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

_log_fh = None    # 当日日志文件句柄
_log_date = None  # 句柄对应的日期，跨天时自动换文件


def _write_log(line: str) -> None:
    """按天追加写入日志文件；任何写入失败都不得影响抢购主流程。"""
    global _log_fh, _log_date
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        if _log_fh is None or _log_date != today:
            if _log_fh is not None:
                _log_fh.close()
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            _log_fh = (LOG_DIR / f"jd_grab_{today}.log").open("a", encoding="utf-8")
            _log_date = today
        _log_fh.write(line + "\n")
        _log_fh.flush()  # 定时任务可能随时被终止，逐行落盘
    except Exception:
        pass


def log(msg: str) -> None:
    """输出日志：终端 + 当日日志文件（供定时任务事后排查）。

    文件行带完整日期，便于跨天与多天日志对照；终端保持短时间戳。
    """
    now = datetime.now()
    stamp = now.strftime("%H:%M:%S.%f")[:-3]
    try:
        print(f"[{stamp}] {msg}", flush=True)
    except Exception:
        pass  # 无人值守时可能没有可用的 stdout
    _write_log(f"[{now.strftime('%Y-%m-%d')} {stamp}] {msg}")


_browser = None          # 当前 CDP 浏览器连接，供退出时清理
_browser_pid = None      # Chrome 浏览器进程 PID，供终端被关闭时的兜底清理
_console_handler = None  # Win32 控制台回调，必须保持引用以免被 GC


def _remember_browser_pid(browser) -> None:
    """记录浏览器进程 PID——终端被关闭时无法使用 Playwright，只能按 PID 结束进程。"""
    global _browser_pid
    try:
        session = browser.new_browser_cdp_session()
        info = session.send("SystemInfo.getProcessInfo")
        for proc in info.get("processInfo") or []:
            if proc.get("type") == "browser":
                _browser_pid = proc.get("id")
                break
    except Exception:
        pass


def _close_browser() -> None:
    """关闭通过 CDP 连上的 Chrome（含窗口）；幂等，可重复调用。

    只能在 Playwright 所在线程调用：对 CDP 连接直接调 browser.close() 只会
    断开连接，需显式发送 CDP 的 Browser.close 才能真正关掉 Chrome。
    """
    global _browser, _browser_pid
    browser, _browser = _browser, None
    if browser is None:
        return
    try:
        browser.new_browser_cdp_session().send("Browser.close")
        _browser_pid = None  # 已优雅关闭，无需再按 PID 处理
        log("已关闭 Chrome 窗口。")
    except Exception:
        pass


def _kill_browser_process() -> None:
    """兜底：按 PID 结束 Chrome 进程树（可从任意线程调用）。"""
    global _browser_pid
    pid, _browser_pid = _browser_pid, None
    if not pid:
        return
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=5)
        log("已关闭 Chrome 窗口（强制结束进程）。")
    except Exception:
        pass


def _install_console_close_handler() -> None:
    """Windows：捕获「关闭终端窗口/注销/关机」事件，先关 Chrome 再退出。

    Ctrl+C（CTRL_C）不在此处理，交由 KeyboardInterrupt 走 finally 分支。
    """
    global _console_handler
    if _console_handler is not None or sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        # 控制台事件：0=CTRL_C 1=CTRL_BREAK 2=CTRL_CLOSE 5=LOGOFF 6=SHUTDOWN
        handler_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def _on_console_event(event: int) -> bool:
            # 此回调运行在系统新建的线程里，不能使用 Playwright
            if event in (2, 5, 6):
                _kill_browser_process()
                return True
            return False

        _console_handler = handler_type(_on_console_event)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_console_handler, True)
    except Exception:
        pass


@contextmanager
def cdp_browser(cdp_url: str):
    """连接到一个已在运行、已登录的 Chrome（需以 --remote-debugging-port 启动）。

    复用其默认 context（含用户登录态），从而在「受信任会话」里执行抢购，
    京东才会渲染「立即免费兑换」按钮。

    退出（正常结束、异常、Ctrl+C 或关闭终端窗口）时关闭该 Chrome 窗口；
    登录态保存在 --user-data-dir 中，下次启动无需重新登录。

    返回 (page, context)。
    """
    global _browser
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        _browser = browser
        _remember_browser_pid(browser)
        _install_console_close_handler()
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()
        try:
            yield page, context
        finally:
            _close_browser()
            _kill_browser_process()  # 优雅关闭失败时的兜底


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
