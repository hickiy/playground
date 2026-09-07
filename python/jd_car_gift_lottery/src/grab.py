"""京东「免费小保养」抢购模块。

默认在每天 09:59:00 开始，先选中「免费小保养」目标卡片，10:00 放库存后
轮询点击兑换按钮，自动处理确认弹窗，成功后截图并停止。

登录需在绑定的真实 Chrome（--cdp）中手动完成，京东才会在「受信任会话」里
渲染「立即免费兑换」按钮。
"""

import argparse
import sys
import time
from datetime import datetime, timedelta

from . import config
from .browser import cdp_browser, ensure_logged_in, log


def parse_start(start_str: str | None) -> datetime:
    """计算开始抢购的时间点，默认今天 09:59:00。"""
    hh, mm, ss = 9, 59, 0
    if start_str:
        parts = start_str.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        ss = int(parts[2]) if len(parts) > 2 else 0
    now = datetime.now()
    target = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)
    if target <= now:
        # 若只是刚刚错过（如 09:59 之后才启动），立即开始，避免空等一天；
        # 若距离设定时间较远，则顺延到明天同一时间。
        if (now - target).total_seconds() <= 600:
            return now
        target += timedelta(days=1)
    return target


def _select_card(page) -> None:
    """切换到「免费保养」Tab 并选中「免费小保养」卡片。"""
    try:
        tab = page.get_by_text(config.GRAB_TAB_TEXT, exact=True).first
        if tab.is_visible(timeout=1000):
            tab.click(timeout=2000, force=True)
            page.wait_for_timeout(500)
    except Exception:
        pass
    try:
        card = page.locator(config.GRAB_CARD_SELECTOR).first
        if card.count() == 0:
            card = page.get_by_text("免费小保养", exact=False).first
        if card.count():
            card.click(timeout=3000, force=True)
            page.wait_for_timeout(300)
    except Exception:
        pass


def _find_target_card(page) -> int:
    """返回「免费小保养」卡片在商品卡片列表中的索引，找不到返回 -1。"""
    try:
        cards = page.locator(".product-info-section")
        n = cards.count()
        for i in range(n):
            try:
                if "免费小保养" in cards.nth(i).inner_text(timeout=200):
                    return i
            except Exception:
                continue
    except Exception:
        pass
    return -1


def _switch_products(page) -> bool:
    """在两个兑换商品之间切换（最后回到「免费小保养」卡片），以刷新按钮状态。

    切换选中商品会触发页面重新渲染底部按钮；连续切换可让 10:00 补充库存后
    按钮及时变为可点击状态。返回是否完成了一次切换。
    """
    try:
        cards = page.locator(".product-info-section")
        n = cards.count()
        target_idx = _find_target_card(page)
        if n < 2 or target_idx < 0:
            return False
        other_idx = (target_idx + 1) % n
        if other_idx == target_idx:
            other_idx = (target_idx + 2) % n if n > 2 else -1
        if other_idx < 0:
            return False
        # 先切到其他卡片，再切回目标卡片，触发按钮状态刷新
        cards.nth(other_idx).click(timeout=2000, force=True)
        page.wait_for_timeout(120)
        cards.nth(target_idx).click(timeout=2000, force=True)
        page.wait_for_timeout(120)
        return True
    except Exception:
        return False


def find_grab_button(page):
    """定位兑换按钮（开抢时段才出现），返回 locator 或 None。"""
    for sel in config.GRAB_BUTTON_SELECTORS:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=1500)
            return loc
        except Exception:
            continue
    for text in config.GRAB_BUTTON_TEXTS:
        try:
            loc = page.get_by_text(text, exact=False).first
            if loc.is_visible(timeout=400):
                return loc
        except Exception:
            continue
    return None


def _dump_page_diag(page) -> None:
    """输出当前页面关键信息，便于定位“找不到按钮”的原因。"""
    try:
        log(f"页面标题: {page.title()}")
        log(f"当前URL: {page.url}")
        body_text = page.inner_text("body")[:200].replace("\n", " ")
        log(f"页面文本片段: {body_text}")
    except Exception:
        pass
    try:
        page.screenshot(path="grab_debug.png")
        log("已保存诊断截图: grab_debug.png")
    except Exception:
        pass


def _is_actionable(btn) -> bool:
    """判断兑换按钮是否处于「可点击（未禁用）」状态。

    京东在非刷新时段会禁用该按钮（灰显 / 文案为倒计时、已抢完等），
    只有 10:00 补充库存后才短暂可点。本函数用于在禁用时跳过点击。
    """
    try:
        if not btn.is_enabled():
            return False
    except Exception:
        pass
    try:
        aria = btn.get_attribute("aria-disabled")
        if aria == "true":
            return False
        cls = (btn.get_attribute("class") or "").lower()
        # 该活动用 `__h1bEZ5 false` 这类 class 标记禁用态
        if "disabled" in cls or " false" in cls:
            return False
    except Exception:
        pass
    try:
        text = btn.inner_text(timeout=300) or ""
        for bad in (config.SOLD_OUT_TEXT, "抢完", "开抢", "未开始", "即将开始",
                    "敬请期待", ":"):
            if bad in text:
                return False
    except Exception:
        pass
    return True


def click_main_button(page) -> bool:
    """点击底部兑换按钮；仅在按钮处于可点击（未禁用）状态时才点击。"""
    btn = find_grab_button(page)
    if btn is None:
        return False
    if not _is_actionable(btn):
        # 禁用/未到开抢时间：跳过点击，避免对禁用按钮做无意义操作
        return False
    try:
        btn.scroll_into_view_if_needed(timeout=1000)
        btn.click(timeout=800)  # 不用 force，等待按钮真正可点
        return True
    except Exception:
        return False


def _button_state(page) -> str:
    """返回兑换按钮当前状态：ready / disabled / sold_out / none。"""
    try:
        loc = page.locator(config.GRAB_BUTTON_SELECTOR).first
        if loc.count() == 0:
            return "none"
        text = loc.inner_text(timeout=300) or ""
        if config.SOLD_OUT_TEXT in text or "抢完" in text:
            return "sold_out"
        if not _is_actionable(loc):
            return "disabled"
        return "ready"
    except Exception:
        return "none"


def try_click_confirm(page) -> bool:
    """尝试点击确认弹窗中的按钮，返回是否点到了。

    先快速判断是否出现弹窗/遮罩（若无则立即返回，避免拖慢主循环），
    再遍历候选文案定位并点击确认按钮。
    """
    popup = page.locator(
        "[class*='popup'], [class*='modal'], [class*='dialog'], [class*='mask']"
    ).first
    try:
        if not popup.is_visible(timeout=60):
            return False
    except Exception:
        return False

    for kw in config.CONFIRM_KEYWORDS:
        try:
            loc = page.get_by_text(kw, exact=False).first
            if loc.is_visible(timeout=200):
                loc.click(timeout=400, force=True)
                log(f"点击弹窗按钮: {kw}")
                return True
        except Exception:
            continue
    return False


def detect_success(page) -> bool:
    """检测是否出现「成功」弹窗（而非常驻的公示字段），避免误判。"""
    try:
        for hint in config.MODAL_CLASS_HINTS:
            candidates = page.locator(f"[class*='{hint}']")
            count = candidates.count()
            for i in range(count):
                el = candidates.nth(i)
                try:
                    if not el.is_visible(timeout=100):
                        continue
                    txt = el.inner_text(timeout=100)
                except Exception:
                    continue
                if any(k in txt for k in config.SUCCESS_KEYWORDS):
                    log(f"检测到成功弹窗: {txt.strip()[:40]}")
                    return True
        return False
    except Exception:
        return False


def run_grab(page, start_time: datetime, test: bool, duration: int) -> int:
    """在给定页面上执行抢购流程，返回是否成功。"""
    page.goto(config.ACTIVITY_URL, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    if not ensure_logged_in(page, config.ACTIVITY_URL):
        return 1

    # 先选中「免费小保养」卡片
    _select_card(page)

    if not test:
        wait_secs = (start_time - datetime.now()).total_seconds()
        log(f"将在 {start_time.strftime('%H:%M:%S')} 开始抢购（还需 {wait_secs:.0f} 秒）。")
        while datetime.now() < start_time:
            time.sleep(0.1)

    log("开始【切换兑换商品】以刷新按钮状态（每天10点补充库存后转为可点击）...")
    deadline = time.time() + duration
    clicks = 0
    success = False
    round_no = 0
    last_state = None

    while time.time() < deadline:
        # 点击过程中若跳转登录页，重新处理登录
        if "plogin.m.jd.com" in page.url:
            log("点击过程中跳转到登录页，处理登录...")
            if not ensure_logged_in(page, config.ACTIVITY_URL):
                break
            _select_card(page)
            continue

        state = _button_state(page)
        if state != last_state:
            if state == "ready":
                log("兑换按钮已进入可点击状态，停止切换，开始点击！")
            elif state == "disabled":
                log("兑换按钮当前为禁用状态（未到开抢时间），继续切换商品刷新。")
            elif state == "sold_out":
                log("检测到【已抢完】，继续切换商品刷新（每天上午10点补充库存）。")
            last_state = state

        if state == "ready":
            # 按钮可点：执行点击 + 确认
            if click_main_button(page):
                clicks += 1
            try_click_confirm(page)
            if detect_success(page):
                success = True
                log("检测到抢购成功！")
                break
            time.sleep(0.05)
        else:
            # 未可点：切换兑换商品以刷新按钮状态
            _switch_products(page)
            time.sleep(0.05)

        # 每约 10 秒提示一次，避免长时间无输出
        round_no += 1
        if round_no % 200 == 0:
            log(f"仍在刷新按钮状态（已点击 {clicks} 次）。若长时间未可点，通常为未到开抢时段或已售罄。")

    if not success:
        log(f"未检测到成功。共点击 {clicks} 次，已停止（可加大 --duration 或检查页面）。")
        _dump_page_diag(page)

    try:
        page.screenshot(path="grab_result.png")
        log("已保存截图: grab_result.png")
    except Exception:
        pass

    return 0 if success else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="京东免费小保养自动抢购")
    parser.add_argument("--start", help="开始时间，格式 HH:MM:SS，默认 09:59:00")
    parser.add_argument("--test", action="store_true", help="立即开始点击（测试模式）")
    parser.add_argument("--duration", type=int, default=600,
                        help="最长持续秒数，默认 600 秒")
    parser.add_argument("--cdp", default="http://localhost:9222",
                        help="已登录的真实 Chrome 调试地址，默认 http://localhost:9222")
    args = parser.parse_args()

    start_time = datetime.now() if args.test else parse_start(args.start)

    with cdp_browser(args.cdp) as (page, context):
        log(f"已连接到已登录的真实浏览器（CDP: {args.cdp}）。")
        code = run_grab(page, start_time, args.test, args.duration)

    return code


if __name__ == "__main__":
    sys.exit(main())
