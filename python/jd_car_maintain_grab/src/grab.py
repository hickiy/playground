"""京东「免费小保养」抢购模块。

流程很简单：10:00:00 到点后，重复 ROUNDS（10）轮
    刷新活动页 → 立即点击「立即免费兑换」（按钮不在此状态就马上再刷新，不做等待）
    → 点击「确认兑换」
10 轮跑完自动退出。刷新页面本身就会重置按钮与弹窗状态，因此不需要处理
商品卡片切换、结果弹窗关闭等复杂逻辑。

脚本需在到点前启动：若启动时已经过了设定时间，本次不抢购，直接退出。

登录需在绑定的真实 Chrome（--cdp）中手动完成，京东才会在「受信任会话」里
渲染「立即免费兑换」按钮。
"""

import argparse
import re
import sys
import time
import traceback
from datetime import datetime

from . import config
from .browser import cdp_browser, ensure_logged_in, log

# ---- 抢购参数 ----
ROUNDS = 10                    # 刷新 → 点击兑换 → 点击确认 的重复轮数
PAGE_LOAD_TIMEOUT_MS = 30000   # 页面加载（goto / reload）超时
CONFIRM_WAIT_MS = 1500         # 点击兑换后等待「确认兑换」弹窗出现的时间
CLICK_POLL_MS = 50             # 等待弹窗时的轮询间隔


def resolve_start(start_str: str | None) -> datetime | None:
    """返回当天的到点抢购时刻，默认今天 10:00:00（放库存时刻）。

    若当前已经过了该时刻，返回 None：脚本必须在到点前启动，过期不补跑。
    """
    hh, mm, ss = 10, 0, 0
    if start_str:
        parts = start_str.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        ss = int(parts[2]) if len(parts) > 2 else 0
    now = datetime.now()
    target = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)
    if target <= now:
        return None
    return target


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


# JS 兜底：按文本精确匹配可见元素并直接触发 click()，
# 绕过「按钮被弹窗遮罩层挡住导致真实鼠标点击落到遮罩上」的问题。
_JS_CLICK_BY_TEXT = """
(keywords) => {
  const nodes = document.querySelectorAll('div, span, button, a, p');
  for (const el of nodes) {
    const t = (el.innerText || '').trim();
    if (!keywords.includes(t)) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none') continue;
    if (s.pointerEvents === 'none') continue;
    el.click();
    return t;
  }
  return null;
}
"""


def _find_visible_text_el(page, keyword: str):
    """查找文本恰为 keyword 的可见元素，返回 locator 或 None。"""
    pattern = re.compile(r"^\s*" + re.escape(keyword) + r"\s*$")
    try:
        loc = page.get_by_text(pattern)
        n = loc.count()
    except Exception:
        return None
    for i in range(n):
        try:
            el = loc.nth(i)
            if el.is_visible():
                return el
        except Exception:
            continue
    return None


def _js_click_text(page, keywords) -> str | None:
    """JS 兜底点击，返回被点击元素的文本，未点到返回 None。"""
    try:
        return page.evaluate(_JS_CLICK_BY_TEXT, list(keywords))
    except Exception:
        return None


def click_text_now(page, keywords, timeout_ms: int = 100) -> str | None:
    """立即点击第一个可见且文案精确匹配 keywords 的元素，返回该文案。

    不轮询、不等待：当前不可见就返回 None，由调用方决定下一步（例如刷新后
    按钮不是「立即免费兑换」状态，就立刻再刷新）。点击优先用真实鼠标点击
    （带命中测试），被弹窗遮罩拦住时退回 JS 直接触发元素 click。
    """
    for kw in keywords:
        el = _find_visible_text_el(page, kw)
        if el is None:
            continue
        try:
            el.click(timeout=timeout_ms)
        except Exception:
            try:
                el.evaluate("e => e.click()")
            except Exception:
                continue
        return kw
    return None


def click_text(page, keywords, wait_ms: int, poll_ms: int = CLICK_POLL_MS) -> str | None:
    """在 wait_ms 内轮询，点击首个出现的（文案精确匹配）可见元素。

    用于「点击后弹窗需要时间渲染」的场景，如点击兑换后等「确认兑换」出现。
    返回被点击的文案；超时未出现返回 None。
    """
    deadline = time.time() + wait_ms / 1000
    while True:
        kw = click_text_now(page, keywords)
        if kw:
            return kw
        kw = _js_click_text(page, keywords)
        if kw:
            return kw
        if time.time() >= deadline:
            return None
        page.wait_for_timeout(poll_ms)


def run_grab(page, start_time: datetime, test: bool) -> int:
    """10:00 到点后重复 ROUNDS 轮「刷新 → 点兑换 → 点确认」，返回退出码。"""
    log("打开活动页...")
    try:
        page.goto(config.ACTIVITY_URL, wait_until="domcontentloaded",
                  timeout=PAGE_LOAD_TIMEOUT_MS)
    except Exception as exc:
        log(f"打开活动页失败: {exc}")
        return 1
    if not ensure_logged_in(page, config.ACTIVITY_URL):
        return 1

    if test:
        log("测试模式：立即开始抢购。")
    else:
        log(f"等待到 {start_time.strftime('%H:%M:%S.%f')[:-3]} 开始抢购...")
        wait_until(start_time)
        log(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} 到点，开始刷新页面抢购。")

    for round_no in range(1, ROUNDS + 1):
        # 1) 刷新页面：等页面 load 完毕（而非仅 DOM 就绪）后再检查按钮状态，
        #    同时重置上一轮的按钮与弹窗
        try:
            page.reload(wait_until="load", timeout=PAGE_LOAD_TIMEOUT_MS)
        except Exception as exc:
            log(f"[{round_no}/{ROUNDS}] 刷新页面失败: {exc}")
            continue

        if not ensure_logged_in(page, config.ACTIVITY_URL):
            log("登录态失效，停止抢购。")
            return 1

        # 2) 立即尝试点击「立即免费兑换」：按钮不在此状态就马上再刷新，不做等待
        main_hit = click_text_now(page, config.GRAB_BUTTON_TEXTS)
        if main_hit is None:
            log(f"[{round_no}/{ROUNDS}] 非「立即免费兑换」状态，立即刷新。")
            continue

        # 3) 点击「确认兑换」（弹窗需时间渲染，这里保留轮询等待）
        confirm_hit = click_text(page, config.CONFIRM_KEYWORDS, CONFIRM_WAIT_MS)
        log(f"[{round_no}/{ROUNDS}] {main_hit} → {confirm_hit or '确认按钮未出现'}")

    log(f"已完成 {ROUNDS} 轮，退出。")
    try:
        page.screenshot(path="grab_result.png")
        log("已保存截图: grab_result.png")
    except Exception:
        pass

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="京东免费小保养自动抢购")
    parser.add_argument("--start", help="到点抢购时间，格式 HH:MM:SS，默认 10:00:00")
    parser.add_argument("--test", action="store_true", help="立即开始点击（测试模式）")
    parser.add_argument("--cdp", default="http://localhost:9222",
                        help="已登录的真实 Chrome 调试地址，默认 http://localhost:9222")
    args = parser.parse_args()

    start_time = datetime.now() if args.test else resolve_start(args.start)

    # 运行头尾均落日志，便于定时任务执行后核对“有没有按时跑、结果如何”
    log("=" * 20 + " 京东免费小保养抢购 " + "=" * 20)

    # 已过到点时间才启动：本次不抢购，直接退出（不补跑、不空等到明天）
    if start_time is None:
        now = datetime.now()
        log(f"当前 {now.strftime('%Y-%m-%d %H:%M:%S')} 已过设定开始时间，"
            f"本次不抢购，直接退出。")
        log(f"运行结束: {now.strftime('%Y-%m-%d %H:%M:%S')} | 退出码 1")
        return 1

    log(f"启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"目标时刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"test={args.test} rounds={ROUNDS} cdp={args.cdp}")

    code = 1
    try:
        with cdp_browser(args.cdp) as (page, context):
            log(f"已连接到已登录的真实浏览器（CDP: {args.cdp}）。")
            code = run_grab(page, start_time, args.test)
    except KeyboardInterrupt:
        log("运行被中断（Ctrl+C）。")
        code = 130
    except Exception:
        # 定时任务无人值守，异常必须留痕（如 Chrome 未启动、CDP 连接失败）
        log("运行异常终止:\n" + traceback.format_exc().rstrip())
        code = 1

    log(f"运行结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 退出码 {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
