"""京东「免费小保养」抢购模块（项目唯一入口，含启动 Chrome）。

10:00:00 放库存，脚本等到该时刻就在活动页内调用兑换接口
`bff_rights_points_exchange`：头 BURST_MS 毫秒（默认 2s）按 BURST_INTERVAL_MS
（默认 100ms）密集打——份额基本在这一瞬被抢完——之后回落到 API_INTERVAL_MS
（默认 1s）继续重试。按业务码判断结果，不模拟点击：既不依赖按钮渲染、遮罩遮挡与
弹窗时机，也不需要在每轮之间刷新整页。

不提前开抢：页面数据里的可兑换时段是 10:00:00-23:50:00 与 00:00:00-09:25:00，
09:25-10:00 属关闭时段，提前发请求只会拿到 1714001「请稍后再试」而白烧机会。

兑换参数（activityWareId / activityId / exchangeScore ...）来自页面打开后
异步拉取的活动数据，因此脚本启动时会先等到参数可读，再等放库存时刻。

脚本会等到放库存时刻（10:00:00）；若启动时已过该时刻，则不再等待、立即开始，
因此盘中手动补跑或试跑都是直接发请求。

浏览器：默认自动启动带调试端口的真实 Chrome（脚本自己启动、结束时关闭），并直接
打开活动页——活动数据会随页面一起开始加载。只有检测到未登录（页面被跳到登录页）时
才在该登录页手动完成登录；「受信任会话」下页面才会返回该商品完整的兑换参数。

页面会丢，但抢购不能因此报废：从打开页面到 10:00:00 之间隔着十几分钟，期间活动页
可能被关掉、调试连接可能断开、Chrome 也可能整个退出（macOS 上关掉最后一个窗口时
Chrome 进程仍在，从外部看「什么都没发生」）。所以等待期间会定期探活，丢失就地重开
会话并重新打开活动页；到点前的参数也缓存下来复用，恢复后不必再等页面重新拉数据。
2026-09-28 定时运行正是死在这一点上：页面在等待期间消失，到点第一次调用就报
`Target page, context or browser has been closed`，随后整轮以退出码 1 结束，
一个请求都没发出去。会话自愈的实现见 `src/browser.py` 的 `CdpSession`。
"""

import argparse
import sys
import time
import traceback
from datetime import datetime

from . import api, config
from .browser import (
    CdpSession,
    PageLostError,
    ensure_logged_in,
    log,
)

# ---- 抢购参数 ----
BURST_MS = 2000                # 放库存后的密集尝试时间窗（份额基本在此被抢完）
BURST_INTERVAL_MS = 100        # 密集窗口内的间隔
API_ATTEMPTS = 40              # 总调用次数（约：前 2s 内 20 次 + 之后每秒 1 次 × 20）
API_INTERVAL_MS = 1000         # 密集窗口结束后的间隔（长时间 400ms 会触发 F30001 限流）
API_COOLDOWN_MS = 3000         # 被限流（F30001）时的额外等待
PARAM_WAIT_MS = 30000          # 等待页面活动数据加载出兑换参数的超时
MAX_RECOVERIES = 2             # 到点后最多恢复几次会话（每次重建都要几秒，份额不等人）

# ---- 等待开抢期间的探活参数 ----
KEEPALIVE_MS = 20000           # 每隔多久探活一次（顺带给 CDP 连接保温）
KEEPALIVE_TIMEOUT_MS = 4000    # 单次探活超时；超时即认为页面/连接已丢失
KEEPALIVE_QUIET_S = 5          # 距开抢不足这么久就停止探活，专心精确等待

# ---- 启动 Chrome 参数 ----
DEFAULT_PORT = 9222            # 调试端口
DEFAULT_PROFILE = "./jd_cdp_profile"  # 用户数据目录（登录态保存在这里）
# 调试端口就绪 / 页面加载的超时见 src/browser.py（CDP_WAIT_MS / PAGE_LOAD_TIMEOUT_MS）


def resolve_start(start_str: str | None) -> datetime:
    """返回当天的放库存（开抢）时刻，默认今天 10:00:00。

    返回的时刻可能已经过去：此时不再等待，直接开始抢购（便于盘中补跑与
    手动试跑）。
    """
    hh, mm, ss = 10, 0, 0
    if start_str:
        parts = start_str.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        ss = int(parts[2]) if len(parts) > 2 else 0
    now = datetime.now()
    return now.replace(hour=hh, minute=mm, second=ss, microsecond=0)


def wait_until(target: datetime) -> None:
    """等到目标时刻，毫秒级精度。

    `time.sleep` 在 Windows 上有毫秒级抽动，因此先睡到剩 10ms，最后一段
    用 `perf_counter` 自旋，尽量把误差压到 1ms 以内。
    """
    deadline = time.perf_counter() + (target - datetime.now()).total_seconds()
    while True:
        remain = deadline - time.perf_counter()
        if remain <= 0:
            return
        if remain > 0.01:
            time.sleep(remain - 0.005)


def grab_by_api(session, sku: dict, url: str) -> int:
    """到点后直接在页面内调用兑换接口，返回退出码。

    节奏：放库存后的 BURST_MS 时间窗内按 BURST_INTERVAL_MS 密集打，窗口结束后
    回落到 API_INTERVAL_MS——份额基本在开抢那一瞬被抢完，但长时间高频会被风控限流。

    两条抗丢失措施（2026-09-28 定时运行「退出码 1、一个请求都没发出去」就死在这里）：
      - 轮间等待用 `time.sleep` 而不是 `page.wait_for_timeout`：页面没了最多少一次
        机会，而不是把整个循环炸掉、把剩下的机会全丢掉；
      - 页面/连接丢失（PageLostError）不当成一次普通失败，而是恢复会话后接着打；
        恢复成功会重新给一个密集窗口（新页面的风控计数也是干净的，总次数不变）。
    """
    started = time.perf_counter()
    recoveries = 0
    for attempt in range(1, API_ATTEMPTS + 1):
        resp = None
        if session.page is not None:
            try:
                resp = api.exchange(session.page, sku)
            except PageLostError as exc:
                log(f"[{attempt}/{API_ATTEMPTS}] 页面/连接已丢失: {exc}")
        if resp is None:
            # resp 为 None 只可能是页面/连接没了：能恢复就立刻用新页面继续，
            # 恢复不了就等一拍（别把剩下的次数空转在死页面上）
            if recoveries < MAX_RECOVERIES and session.recover(url):
                recoveries += 1
                started = time.perf_counter()  # 新页面：重新给一个密集窗口
            else:
                time.sleep(API_INTERVAL_MS / 1000)
            continue
        code = resp.get("code")
        msg = resp.get("msg") or resp.get("displayMsg") or ""
        if code == config.EXCHANGE_OK_CODE:
            log(f"[{attempt}/{API_ATTEMPTS}] 兑换成功: {msg or resp.get('rs')}")
            return 0
        log(f"[{attempt}/{API_ATTEMPTS}] 未成功: code={code} msg={msg}")
        if attempt >= API_ATTEMPTS:
            break
        elapsed_ms = (time.perf_counter() - started) * 1000
        wait_ms = BURST_INTERVAL_MS if elapsed_ms < BURST_MS else API_INTERVAL_MS
        # 被风控限流时多等一会儿，硬打只会继续被拒
        if code == config.EXCHANGE_RATE_LIMIT_CODE:
            wait_ms = API_COOLDOWN_MS
        time.sleep(wait_ms / 1000)
    log(f"接口调用 {API_ATTEMPTS} 次均未成功，退出。")
    return 1


def read_sku_params_with_recovery(session, url: str, tries: int = 2) -> dict | None:
    """读兑换参数；读取过程中页面/连接丢失就恢复会话后重读。

    参数（activityWareId / activityId / exchangeScore ...）与库存无关（已抢完也
    照样能读到），所以调用方读到一次就缓存住，会话恢复后直接复用。
    """
    for attempt in range(1, tries + 1):
        try:
            if session.page is None and not session.recover(url):
                return None
            return api.read_sku_params(session.page, config.SKU_ID, PARAM_WAIT_MS)
        except PageLostError as exc:
            log(f"读取兑换参数时页面/连接已丢失: {exc}")
            if attempt >= tries or not session.recover(url):
                return None
            if not ensure_logged_in(session.page, url):
                return None
    return None


def wait_until_active(session, target: datetime, url: str) -> bool:
    """等到放库存时刻（毫秒级）；期间定期探活，页面/连接丢失就地恢复。

    返回 False 表示恢复后登录态已经不对，再等下去也没有意义。

    探活是必须的：这一等就是十几分钟，而页面只在最后一刻才被用到。不探活的话，
    页面中途消失要等到 10:00:00 发第一个请求时才发现，那时只剩下一次必然失败的调用。
    """
    while True:
        remain = (target - datetime.now()).total_seconds()
        if remain <= 0:
            return True
        if remain <= KEEPALIVE_QUIET_S:
            wait_until(target)          # 临门一脚：不再探活，专心毫秒级等待
            return True
        time.sleep(min(remain - KEEPALIVE_QUIET_S, KEEPALIVE_MS / 1000))
        if session.probe(KEEPALIVE_TIMEOUT_MS):
            continue
        log(f"探活失败：活动页/调试连接已丢失（距开抢 {remain:.0f}s），尝试恢复...")
        if not session.recover(url):
            continue                    # 恢复不了就下一轮再试，时间还够
        if not ensure_logged_in(session.page, url):
            log("恢复后仍未登录，本次不再等待开抢。")
            return False


def run_grab(session, start_time: datetime, test: bool) -> int:
    """到开抢时刻直调兑换接口抢购，返回退出码。"""
    url = config.ACTIVITY_URL
    log("打开活动页...")
    try:
        session.open_page(url)
    except Exception as exc:
        log(f"打开活动页失败: {exc}")
        return 1
    if not ensure_logged_in(session.page, url):
        return 1

    # 兑换参数是页面打开后异步加载的：先等到能读到再等到点，避免到点了才发现
    # 取不到参数。已抢完的商品同样能读到完整参数，因此不用等补库存。
    sku = read_sku_params_with_recovery(session, url)
    if sku is not None:
        log(f"目标商品: {sku['name'] or '未知'}（skuId={sku['skuId']}，"
            f"{sku['exchangeScore']} 积分，skuStatus={sku['skuStatus']}）")
        if sku.get("btnRedirectUrl"):
            # 这类商品走「拿 sourceTicket → 跳转 m-sep.jd.com/Settlement 提交订单」，
            # 不调兑换接口，直调接口必然失败，提前说清楚而不是白跑 N 次
            log("警告: 该商品的下单流程是跳转结算页（btnRedirectUrl 非空），"
                "不走兑换接口，请改用「免费小保养」等走接口的商品。")
            return 1

    if test:
        log("测试模式：立即开始抢购。")
    elif start_time <= datetime.now():
        log(f"当前 {datetime.now().strftime('%H:%M:%S')} 已过放库存时刻 "
            f"{start_time.strftime('%H:%M:%S')}，不再等待，立即开始抢购。")
    else:
        log(f"等待到 {start_time.strftime('%H:%M:%S.%f')[:-3]} 放库存开抢"
            f"（前 {BURST_MS / 1000:g}s 每 {BURST_INTERVAL_MS}ms 一次，"
            f"之后每 {API_INTERVAL_MS}ms 一次；期间每 "
            f"{KEEPALIVE_MS / 1000:g}s 探活一次）...")
        # 等待期间页面若丢失就地恢复，别等到 10:00:00 才发现
        if not wait_until_active(session, start_time, url):
            return 1
        log(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} 开抢，开始调用兑换接口。")

    if sku is None:
        sku = read_sku_params_with_recovery(session, url)
    if sku is None:
        log("读不到该商品的兑换参数（页面活动数据可能没加载出来），本次不抢购。")
        return 1

    return grab_by_api(session, sku, url)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="京东免费小保养自动抢购（必要时自动启动带调试端口的 Chrome）")
    parser.add_argument("--start", help="放库存时间，格式 HH:MM:SS，默认 10:00:00"
                                       "（到点即开抢，不提前）")
    parser.add_argument("--test", action="store_true", help="立即开始（测试模式）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"启动/连接的 Chrome 调试端口，默认 {DEFAULT_PORT}")
    parser.add_argument("--profile", default=DEFAULT_PROFILE,
                        help=f"Chrome 用户数据目录，默认 {DEFAULT_PROFILE}")
    parser.add_argument("--url", default=config.ACTIVITY_URL,
                        help="启动 Chrome 时打开的地址，默认活动页"
                             "（未登录时京东会自动跳到登录页）")
    parser.add_argument("--chrome", help="Chrome/Edge 可执行文件路径，默认自动查找")
    args = parser.parse_args()

    cdp_url = f"http://localhost:{args.port}"
    start_time = datetime.now() if args.test else resolve_start(args.start)

    # 运行头尾均落日志，便于定时任务执行后核对“有没有按时跑、结果如何”
    log("=" * 20 + " 京东免费小保养抢购 " + "=" * 20)

    log(f"启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"放库存/开抢: {start_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"test={args.test} attempts={API_ATTEMPTS} "
        f"burst={BURST_MS / 1000:g}s/{BURST_INTERVAL_MS}ms cdp={cdp_url}")

    # 会话自己负责：拉起/复用带调试端口的 Chrome、打开活动页、丢失后重建
    session = CdpSession(cdp_url, args.port, args.profile, args.url, args.chrome)

    code = 1
    try:
        session.connect()
        log(f"已连接到已登录的真实浏览器（CDP: {cdp_url}）。"
            "若需登录，请在浏览器窗口中完成。")
        code = run_grab(session, start_time, args.test)
    except KeyboardInterrupt:
        log("运行被中断（Ctrl+C）。")
        code = 130
    except Exception:
        # 定时任务无人值守，异常必须留痕（如 Chrome 未启动、CDP 连接失败）
        log("运行异常终止:\n" + traceback.format_exc().rstrip())
        code = 1
    finally:
        session.close()  # 正常结束、异常、中断都要收掉 Chrome 窗口

    log(f"运行结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 退出码 {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
