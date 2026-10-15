"""连接常驻 CDP 服务、登录检测与日志工具。

浏览器的生命周期与登录态都不在本项目里：CDP 服务由独立项目 **browserhost**（见
`../browserhost`）提供——`python main.py start` 拉起一个真实 Chrome 并长期常驻，登录态
在它自己的 profile 里持久化。所以本项目既不去找 Chrome 装在哪，也不碰 profile，只把调试
端口当成一个服务连上去，并且只操作自己打开的那个标签页。

于是这里只剩三件事：按天写日志、判断「页面 / 连接是否丢失」，以及一个**可重建**的会话
（页面丢了就地重开，抢购不因一次丢失而报废）。浏览器窗口可以随手关——Chrome 进程仍留在
后台、调试端口一直可用，本模块会自己补一个页面出来。
"""

import sys
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


def cdp_reachable(cdp_url: str, timeout_s: float = 1.0) -> bool:
    """探测该地址上是否已有可用的 CDP 调试端口。

    只为在连不上时给出人话提示（而不是让 Playwright 抛一段连接错误），不参与
    任何生命周期管理：浏览器由 browserhost 启停。
    """
    try:
        with urllib.request.urlopen(cdp_url.rstrip("/") + "/json/version",
                                    timeout=timeout_s) as resp:
            return resp.status == 200
    except Exception:
        return False


class CdpSession:
    """一次抢购所需的浏览器会话：CDP 连接 + 活动页，并且可以重建。

    为什么会话必须能重建——这是本工具最要命的失败点：脚本 09:50 就打开活动页，
    之后一直等，直到 10:00:00 才发第一个请求。中途页面一旦消失（窗口被关、
    Chrome 退出、连接断开），到点就只剩一次必然失败的调用，整轮抢购直接报废。
    因此把「连接 + 页面」包成可重建的会话：`probe` 探活，`recover` 重建。

    只连接、只重开活动页，从不启动也从不关闭浏览器：实例由 browserhost 启停并长期
    常驻（窗口关掉后 Chrome 进程仍留在后台，调试端口一直可用），所以定时任务任何
    时候执行都能连上。

    窗口关掉后浏览器里一个页面也没有，而兑换请求必须跑在页面里（要读页面数据
    `window.__react_data__`、调 `window.getJsToken()`），因此这种时候会新建一个
    页面；本次运行新建的页面会在 `close()` 时关掉，跑完即恢复「无窗口」原状。

    复用 Chrome 的默认 context（含用户登录态），从而在「受信任会话」里执行抢购，
    京东才会渲染「立即免费兑换」按钮；登录态由 browserhost 的 profile 持久化。
    """

    def __init__(self, cdp_url: str, url: str):
        self.cdp_url = cdp_url
        self.url = url              # 活动页地址；页面丢失后按它重开
        self.page = None            # 活动页；丢失后由 recover 重建
        self.context = None
        self.browser = None
        self.created_page = False   # 当前页面是否由本次运行新建（关掉它才算恢复原状）
        self.recoveries = 0         # 累计恢复次数，仅用于日志
        self._pw = None             # Playwright 实例（每次重连都换一个）

    # ---- 连接与页面 ----

    def connect(self) -> None:
        """连上 browserhost 已在运行的那台 Chrome（调试端口必须已就绪）。

        不自己启动 Chrome：本项目不知道也不需要知道浏览器在哪、profile 在哪。
        连不上就报错让人去处理——而不是悄悄拉起一个新实例：新实例会另开一份用户
        数据目录，和常驻实例不是同一个会话，登录态与页面都对不上。
        """
        if not cdp_reachable(self.cdp_url):
            raise RuntimeError(
                f"连不上 {self.cdp_url}：常驻 Chrome 没在运行，或调试端口不是这个。"
                "请在 browserhost 里执行 `python main.py start`（幂等）后再试。")
        self._pw = sync_playwright().start()
        browser = self._pw.chromium.connect_over_cdp(self.cdp_url)
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
        """优先复用已在活动页的标签页，其次复用任意标签页，最后新建一个。"""
        base = url.split("?")[0]
        pages = [p for p in (self.context.pages or []) if not p.is_closed()]
        for page in reversed(pages):
            if page.url.split("?")[0] == base:
                return page
        if pages:
            return pages[-1]
        # 窗口已经关了（浏览器进程还在、CDP 可用，但一个页面都没有）：请求必须发在
        # 页面里，所以只能新建一个。记下来，结束时把它关掉，恢复「无窗口」原状。
        log("浏览器里没有可用页面（窗口已关闭）：新建一个标签页。")
        self.created_page = True
        return self.context.new_page()

    def minimize_window(self) -> bool:
        """把当前页面所在窗口最小化（抢购期间不占用桌面），成功返回 True。

        只有 `grab --minimize-page` 时才用：窗口关着时新建的临时页面本来是可见的，
        最小化后不遮挡桌面也不抢焦点，跑完临时页面照样会被关掉。
        实测（Windows，最小化 11 分钟）：页面一直是 `visibilityState=visible`、
        `wasDiscarded=false`，`evaluate` 与探活全部正常；macOS 锁屏属同类场景
        （窗口没关、标签页仍是活动标签）但未实测。
        """
        page = self.page
        if page is None or page.is_closed() or self.browser is None:
            return False
        try:
            sess = self.browser.new_browser_cdp_session()
            base = page.url.split("?")[0]
            target_id = None
            for info in sess.send("Target.getTargets").get("targetInfos", []):
                if info.get("type") == "page" \
                        and info.get("url", "").split("?")[0] == base:
                    target_id = info["targetId"]
                    break
            if target_id is None:
                return False
            window_id = sess.send("Browser.getWindowForTarget",
                                  {"targetId": target_id})["windowId"]
            sess.send("Browser.setWindowBounds", {
                "windowId": window_id, "bounds": {"windowState": "minimized"}})
            return True
        except Exception as exc:
            log(f"最小化窗口失败（不影响抢购）: {exc}")
            return False

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

        先断开再重连同一个调试端口：页面被关掉时浏览器还活着（窗口关掉后
        Chrome 进程仍留在后台），重开活动页即可。端口也不通说明常驻实例整个退出了：
        本轮恢复不了——本项目不会自己启动浏览器，请在 browserhost 里
        `python main.py start`。断开不会关闭 Chrome。
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
        self.page = None
        self.context = None
        self.browser = None
        self.created_page = False
        pw, self._pw = self._pw, None
        if pw is not None:
            try:
                pw.stop()           # CDP 连接只是断开，Chrome 继续跑
            except Exception:
                pass

    def close(self) -> None:
        """结束本次运行：关掉本次新建的页面（若有），然后断开调试连接。

        绝不能顺手关掉浏览器：它是 browserhost 的常驻实例，被多个任务与多轮定时任务
        共用，「CDP 随时可连接」正是靠它一直活着；关窗口/退出的主动权在用户手里。

        本次运行新建的页面要一并关掉：窗口已关（无页面）时新建的页面用完就该还
        回去，让机器回到「无窗口、后台进程仍在」的状态。
        """
        page = self.page
        if self.created_page and page is not None and not page.is_closed():
            try:
                page.close()        # 关掉最后一个标签页只会关窗口，Chrome 进程仍在
                log("已关闭本次抢购新建的页面（Chrome 进程继续在后台运行）。")
            except Exception:
                pass
        self._disconnect()


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
