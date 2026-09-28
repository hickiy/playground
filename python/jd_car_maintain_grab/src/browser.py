"""共享的浏览器启动/连接、登录检测与日志工具。"""

import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

# Playwright 的 TargetClosedError 没有在 sync_api 顶层导出，且在私有模块里；
# 导入失败就退化为按异常消息判断（页面/连接被关闭时消息就是下面这几句）。
try:
    from playwright._impl._errors import TargetClosedError
except Exception:  # pragma: no cover - 依赖 Playwright 内部结构，保守兜底
    TargetClosedError = None

# 「页面 / 上下文 / 调试连接已经没了」时 Playwright 的错误文案
PAGE_LOST_HINTS = (
    "has been closed",
    "Target closed",
    "Connection closed",
)

CDP_WAIT_MS = 15000            # 等 Chrome 调试端口就绪的超时
PAGE_LOAD_TIMEOUT_MS = 30000   # 页面加载（goto）超时


def is_page_lost(exc: BaseException) -> bool:
    """异常是否表示「页面 / 调试连接已丢失」（可恢复），而不是业务码或脚本错误。

    这类错误必须区别于普通失败：普通失败继续重试就行，而页面没了再重试多少次
    也没用，得先把会话恢复回来。
    """
    if TargetClosedError is not None and isinstance(exc, TargetClosedError):
        return True
    msg = str(exc)
    return any(hint in msg for hint in PAGE_LOST_HINTS)


class PageLostError(RuntimeError):
    """页面或 CDP 连接已丢失，调用方应尝试 `CdpSession.recover` 后继续。"""


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
    else:  # Linux / 其他类 Unix
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
        ]
    for p in candidates:
        if Path(p).exists():
            return p
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
    """启动带远程调试端口的真实 Chrome，返回是否成功拉起进程。

    用真实用户数据目录，登录态可跨次复用；调试端口供脚本自己连接。
    """
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
            url,
        ])
    except Exception as exc:
        log(f"启动 Chrome 失败: {exc}")
        return False
    return True


def wait_for_cdp(cdp_url: str, timeout_ms: int = 15000) -> bool:
    """等调试端口就绪——Chrome 从启动到监听端口会有延迟。"""
    deadline = time.time() + timeout_ms / 1000
    while True:
        if cdp_reachable(cdp_url):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.2)


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
    """兜底：按 PID 结束 Chrome 进程（可从任意线程调用）。

    优雅关闭失败时必须真的杀掉：残留的 Chrome 会一直占着 `--user-data-dir`，
    下次启动时新进程会把命令行交给它然后自己退出，调试端口起不来，抢购必然失败。
    Windows 用 taskkill（顺带结束子进程），macOS/Linux 先 TERM 再 KILL。
    """
    global _browser_pid
    pid, _browser_pid = _browser_pid, None
    if not pid:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=5)
        else:
            os.kill(pid, signal.SIGTERM)
            deadline = time.time() + 2
            while time.time() < deadline:
                try:
                    os.kill(pid, 0)  # 探活：进程还在就不会抛异常
                except ProcessLookupError:
                    break
                time.sleep(0.2)
            else:
                os.kill(pid, signal.SIGKILL)
        log("已关闭 Chrome 窗口（强制结束进程）。")
    except ProcessLookupError:
        pass  # 已经退出了，无需处理
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


class CdpSession:
    """一次抢购所需的浏览器会话：CDP 连接 + 活动页，并且可以重建。

    为什么会话必须能重建——这是本工具最要命的失败点：脚本 09:50 就打开活动页，
    之后一直等，直到 10:00:00 才发第一个请求。中途页面一旦消失（窗口被关、
    Chrome 退出、连接断开），到点就只剩一次必然失败的调用，整轮抢购直接报废。
    因此把「连接 + 页面」包成可重建的会话：`probe` 探活，`recover` 重建。

    复用 Chrome 的默认 context（含用户登录态），从而在「受信任会话」里执行抢购，
    京东才会渲染「立即免费兑换」按钮；登录态保存在 --user-data-dir 中，可跨次复用。
    """

    def __init__(self, cdp_url: str, port: int, profile: str, url: str,
                 chrome_path: str | None = None):
        self.cdp_url = cdp_url
        self.port = port
        self.profile = profile
        self.url = url              # 启动 Chrome 时打开的地址（默认活动页）
        self.chrome_path = chrome_path
        self.page = None            # 活动页；丢失后由 recover 重建
        self.context = None
        self.browser = None
        self.recoveries = 0         # 累计恢复次数，仅用于日志
        self._pw = None             # Playwright 实例（每次重建都换一个）

    # ---- 连接与页面 ----

    def connect(self) -> None:
        """连上带调试端口的 Chrome；端口不通就重新拉起一个。

        端口还在就直接复用（例如上次异常退出残留的 Chrome 也能接着用），
        避免「一次异常退出之后此后再也起不来」。
        """
        global _browser
        if not cdp_reachable(self.cdp_url):
            if not launch_chrome(self.port, self.profile, self.url, self.chrome_path):
                raise RuntimeError("启动 Chrome 失败")
            if not wait_for_cdp(self.cdp_url, CDP_WAIT_MS):
                raise RuntimeError(
                    f"等待 {self.cdp_url} 就绪超时：Chrome 没起来，或用户数据"
                    f"目录已被残留进程占用（{self.profile}）")
        self._pw = sync_playwright().start()
        browser = self._pw.chromium.connect_over_cdp(self.cdp_url)
        _browser = browser          # 供退出时统一关闭
        _remember_browser_pid(browser)
        _install_console_close_handler()
        self.browser = browser
        self.context = browser.contexts[0] if browser.contexts else browser.new_context()

    def open_page(self, url: str):
        """打开（或复用）活动页并返回；页面就是接口调用的执行环境。"""
        if self.context is None:
            raise RuntimeError("尚未连接 Chrome（请先 connect）")
        page = self._pick_page(url)
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        self.page = page
        return page

    def _pick_page(self, url: str):
        """优先复用已在活动页的标签页，其次复用任意标签页，最后新建。"""
        base = url.split("?")[0]
        pages = [p for p in (self.context.pages or []) if not p.is_closed()]
        for page in reversed(pages):
            if page.url.split("?")[0] == base:
                return page
        return pages[-1] if pages else self.context.new_page()

    def probe(self, timeout_ms: int = 4000) -> bool:
        """探活：连接在、页面还能在 timeout_ms 内响应；超时按「已丢失」处理。

        用 `wait_for_function` 而不是 `page.evaluate`：前者能带超时，连接假死时
        会按时抛错；后者没有超时，会一直等下去——等在 10:00:00 前面是致命的。
        """
        page, browser = self.page, self.browser
        if page is None or browser is None or page.is_closed() \
                or not browser.is_connected():
            return False
        try:
            page.wait_for_function("1", timeout=timeout_ms, polling=200)
            return True
        except Exception:
            return False

    def recover(self, url: str | None = None) -> bool:
        """页面/连接丢失后就地重建会话，成功返回 True。

        先断开再重连同一个调试端口：页面被关掉时浏览器通常还活着（macOS 上关掉
        最后一个窗口 Chrome 进程仍在），只有端口也不通时才重新拉起 Chrome。
        断开不会关闭 Chrome，所以恢复不会「顺手」把浏览器一起干掉。
        """
        url = url or self.url
        self.recoveries += 1
        log(f"尝试恢复会话（第 {self.recoveries} 次）：重连调试端口并重新打开活动页...")
        self._disconnect()
        try:
            self.connect()
            self.open_page(url)
        except Exception as exc:
            log(f"恢复失败: {exc}")
            self._disconnect()
            return False
        log("会话已恢复：活动页已重新打开。")
        return True

    def _disconnect(self) -> None:
        """断开当前 CDP 连接（不关闭 Chrome）并清空引用。"""
        global _browser
        self.page = None
        self.context = None
        self.browser = None
        _browser = None             # 旧连接不再参与退出时的关闭
        pw, self._pw = self._pw, None
        if pw is not None:
            try:
                pw.stop()           # CDP 连接只是断开，Chrome 继续跑
            except Exception:
                pass

    def close(self) -> None:
        """结束本次运行：关闭 Chrome 窗口（含兜底强杀）并停掉 Playwright。"""
        global _browser
        _browser = self.browser
        try:
            _close_browser()
            _kill_browser_process()  # 优雅关闭失败时的兜底
        finally:
            self.page = None
            self.context = None
            self.browser = None
            pw, self._pw = self._pw, None
            if pw is not None:
                try:
                    pw.stop()
                except Exception:
                    pass


def is_login_page(page) -> bool:
    """判断当前是否停留在京东登录页。"""
    return "plogin.m.jd.com" in page.url


def ensure_logged_in(page, url: str, max_tries: int = 5) -> bool:
    """若被重定向到登录页，引导用户在浏览器中手动完成登录。

    未登录时全程留日志（检测到登录页、等待登录、最终结果）：无人值守执行后
    靠日志即可判断「没抢到」是不是因为登录态失效，而不是库存或风控原因。
    """
    tries = 0
    while is_login_page(page):
        tries += 1
        if tries > max_tries:
            log(f"登录未完成：{max_tries} 次等待后仍停留在登录页（{page.url}），"
                "本次未执行抢购。原因很可能是登录态失效，请重新运行并在浏览器中登录。")
            return False
        log(f"检测到未登录：页面已跳到登录页（{page.url}），"
            f"未完成登录将无法抢购（第 {tries}/{max_tries} 次等待）。")
        log("请在浏览器窗口中完成登录，完成后回到终端按回车继续...")
        try:
            input(">>> 登录完成后按回车继续：")
        except Exception as exc:
            # 任务计划程序/cron 等无人值守场景没有可读输入，跳过等待直接重试
            log(f"无法读取输入（{type(exc).__name__}），跳过登录等待。")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
    log("登录态正常：未出现登录页。")
    return True
