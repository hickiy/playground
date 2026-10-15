"""把本地视频发到微信视频号助手（web），全程只经 CDP。

浏览器由 browserhost 常驻提供（见 `src/browser.py`）：本模块只连接、只**新开自己**的
页签，绝不关闭浏览器、也不动别人的页签。

默认**填完即提交**：上传 → 填表 → 把字段读回来核对 → 点「发表」→ 等结果并如实回报。
想先人工核对一遍就加 `--no-publish`：只填表 + 截图，停在「发表」按钮前（页签留着）。
登录态失效只截图报警、不尝试自动登录（那条路不该由脚本走，页面结构与风控也一直在变）。

⚠️ 下面的选择器不是猜的，是 2026-10-15 对着真实页面实测出来的；改版后按
`logs/publish_*.png` 重新校准。三条实测结论决定了实现方式：

  1. 助手是**无界（wujie）微前端**：真实表单在 `<wujie-app>` 的 shadow DOM 里，
     所以判断页面上有什么**只能用 Playwright 定位器**（会穿透 shadow DOM）——
     `document.querySelectorAll` / `page.content()` / `body.innerText` 只看到空壳；
  2. 发布页打开后**会自己重载一次**，早期拿到的是空壳，必须等表单元素出现再动手；
  3. 上传完成的信号是「发表」按钮从 `weui-desktop-btn_disabled` 变为可点。
"""

import time
from datetime import datetime
from pathlib import Path

from . import config
from .logging import log

# ---- 选择器与标记（实测于 2026-10-15；页面改版就按截图重校这一段）----
CREATE_URL = "https://channels.weixin.qq.com/platform/post/create"
FILE_INPUT = "input[type=file][accept*='video']"   # 上传入口（隐藏，在 .ant-upload-btn 内）
DESC_EDITOR = "div.input-editor[contenteditable]"  # 视频描述（富文本，不是 textarea）
TITLE_INPUT = "input[placeholder*='短标题']"        # 短标题（可选字段）
PUBLISH_TEXT = "发表"                              # 精确匹配；子串会命中「直接发表」
CONFIRM_TEXT = "直接发表"                          # 点完发表后可能弹的确认按钮
DISABLED_CLASS = "weui-desktop-btn_disabled"       # 发表按钮的「未就绪」标记
LOGIN_URL_MARKER = "/login"                        # 未登录会跳到 login.html
LOGIN_QR_SELECTOR = "iframe[src*='qrconnect']"      # 扫码登录的二维码 iframe

# ---- 超时 ----
PAGE_TIMEOUT_MS = 30_000      # goto
FORM_TIMEOUT_MS = 60_000      # 等表单挂载（页面会自己重载一次）
UPLOAD_TIMEOUT_MS = 600_000   # 上传 + 转码（长视频慢，给足 10 分钟）
FIELD_TIMEOUT_MS = 10_000
AFTER_PUBLISH_MS = 5_000      # 点完「发表」后等页面反应
SUBMIT_TIMEOUT_MS = 60_000    # 点完「发表」后等「真的发出去了」的信号
# 提交后的成功信号（实测 2026-10-15：页面会跳到作品列表 /platform/post/list，并弹「已发表」）
SUCCESS_TEXTS = ("已发表", "发表成功", "发布成功")


def _need_login(page) -> bool:
    """当前是否停在登录/扫码页（看 URL 或页面里的扫码 iframe）。"""
    if LOGIN_URL_MARKER in (page.url or ""):
        return True
    try:
        return page.locator(LOGIN_QR_SELECTOR).count() > 0
    except Exception:
        return False


def _screenshot(page, prefix: str) -> str | None:
    """截图存进 logs/ 并返回路径（失败返回 None）——选择器对不上时全靠它排查。"""
    path = config.LOG_DIR / f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception as exc:
        log(f"截图失败：{type(exc).__name__}: {exc}")
        return None


def _wait_form(page, timeout_ms: int) -> bool:
    """等发布表单挂载（这个 SPA 打开后会自己重载一次，早期只有侧边栏空壳）。"""
    started = time.time()
    while (time.time() - started) * 1000 < timeout_ms:
        if _need_login(page):
            return False
        try:
            if page.locator(FILE_INPUT).count():
                log(f"发布表单已就绪（等了 {time.time() - started:.1f}s）。")
                return True
        except Exception:
            pass
        page.wait_for_timeout(500)
    return False


def _publish_state(page) -> str:
    """「发表」按钮的状态：``缺失`` / ``未就绪``（带 disabled 类）/ ``就绪``。"""
    button = page.get_by_role("button", name=PUBLISH_TEXT, exact=True)
    if button.count() == 0:
        return "缺失"
    try:
        classes = button.first.get_attribute("class") or ""
    except Exception:
        return "未知"
    return "未就绪" if DISABLED_CLASS in classes else "就绪"


def _wait_upload(page, timeout_ms: int) -> bool:
    """等上传/转码完成，返回是否就绪。

    实测的完成信号就是「发表」按钮从 ``weui-desktop-btn_disabled`` 变为可点；
    等不到时每 15s 报一次状态（便于区分「慢」和「卡」），最后返回 False。
    """
    started = time.time()
    last_log = 0.0
    while (time.time() - started) * 1000 < timeout_ms:
        state = _publish_state(page)
        if state == "就绪":
            log(f"上传/转码完成（{time.time() - started:.0f}s），「发表」按钮已可用。")
            return True
        if _need_login(page):
            log("等待期间掉回登录页，停止等待。")
            return False
        elapsed = time.time() - started
        if elapsed - last_log >= 15:
            last_log = elapsed
            log(f"等待上传/转码…（{elapsed:.0f}s，发表按钮：{state}）")
        page.wait_for_timeout(1000)
    log(f"等上传/转码超时（{timeout_ms / 1000:.0f}s）。")
    return False


def _diagnose(page) -> None:
    """把「页面上现在有什么」写进日志，失败时最容易看出是哪一步对不上。

    shadow DOM 的关系，`body.innerText` / `page.content()` 看不到真实表单，
    所以统一用 Playwright 定位器（会穿透 shadow DOM）来数。
    """
    counts = []
    for label, selector in (("上传输入", FILE_INPUT), ("描述框", DESC_EDITOR),
                            ("短标题", TITLE_INPUT)):
        try:
            counts.append(f"{label}×{page.locator(selector).count()}")
        except Exception:
            counts.append(f"{label}×?")
    try:
        buttons = [t.strip() for t in page.get_by_role("button").all_inner_texts() if t.strip()]
    except Exception:
        buttons = []
    log("页面现状：" + "、".join(counts) + "；可见按钮：" + ("/".join(buttons[:12]) or "无"))


def _fill_desc(page, text: str) -> bool:
    """填「视频描述」（富文本）。

    用 click + insert_text 而不是 fill：走真实输入事件，页面自己的话题联想才会跑
    （`fill` 在 contenteditable 上不保证触发 input 事件）。
    """
    if not text:
        return False
    editor = page.locator(DESC_EDITOR).first
    editor.wait_for(state="visible", timeout=FIELD_TIMEOUT_MS)
    editor.click()
    page.keyboard.insert_text(text)
    return True


def _fill_title(page, title: str) -> str:
    """填「短标题」，返回**实际填进去**的值（页面声明了 maxlength 就按它截断）。"""
    if not title:
        return ""
    field = page.locator(TITLE_INPUT).first
    field.wait_for(state="visible", timeout=FIELD_TIMEOUT_MS)
    limit = field.get_attribute("maxlength")
    if limit and limit.isdigit() and int(limit) < len(title):
        log(f"短标题超过页面限制 {limit} 字，截断为：{title[:int(limit)]}")
        title = title[:int(limit)]
    field.fill(title)
    return title


def _verify_filled(page, applied_title: str, desc_text: str) -> list[str]:
    """提交前把值读回来对一遍，返回对不上的项（空列表 = 没问题）。

    自动提交之后就没机会改了，所以这一步是**硬门槛**：字段没真进去就不提交。
    """
    problems = []
    if desc_text:
        try:
            actual = (page.locator(DESC_EDITOR).first.inner_text() or "").strip()
        except Exception as exc:
            actual = f"(读不到: {type(exc).__name__})"
        if desc_text.strip() not in actual:
            problems.append(f"描述没进去（页面里是 {actual[:40]!r}）")
    if applied_title:
        try:
            actual = (page.locator(TITLE_INPUT).first.input_value() or "").strip()
        except Exception as exc:
            actual = f"(读不到: {type(exc).__name__})"
        if actual != applied_title.strip():
            problems.append(f"短标题对不上（页面里是 {actual!r}）")
    return problems


def _after_submit(page) -> tuple[str, str]:
    """提交后等「真的发出去了」的信号，并把现场留在日志里。

    能识别的信号：页面离开发布页（跳去作品列表），或出现成功/审核文案；两者都没等到
    就如实返回 ``submitted``（不确定），**不谎报成功**——截图与页面现状都留在日志里。
    """
    started = time.time()
    while (time.time() - started) * 1000 < SUBMIT_TIMEOUT_MS:
        if "/post/create" not in (page.url or ""):
            shot = _screenshot(page, "publish_done")
            log(f"提交后页面已离开发布页：{page.url}（截图 {shot}）")
            return "published", f"已提交发表，页面已跳到 {page.url}（截图 {shot}）"
        for text in SUCCESS_TEXTS:
            try:
                if page.get_by_text(text).count():
                    shot = _screenshot(page, "publish_done")
                    log(f"看到成功信号「{text}」（截图 {shot}）")
                    return "published", f"已提交发表（页面提示「{text}」，截图 {shot}）"
            except Exception:
                pass
        page.wait_for_timeout(1000)
    shot = _screenshot(page, "publish_unknown")
    _diagnose(page)
    return "submitted", (f"点了「发表」，但 {SUBMIT_TIMEOUT_MS / 1000:.0f}s 内没等到成功信号"
                         f"（页面仍在 {page.url}）；截图 {shot}，请到视频号后台确认")


def _compose_desc(desc: str, tags) -> str:
    """把描述与话题拼成一段文本：话题写成 `#标签`，随描述一起输入。

    页面上那个「#话题」按钮只是帮你插一个 `#` 并弹联想列表；这里直接把 `#标签`
    写进文本。联想列表不选也能发，但话题是否生效请在后台核对一眼。
    """
    parts = [desc.strip()] if desc else []
    tags_text = " ".join(f"#{tag.strip().lstrip('#')}" for tag in tags if tag.strip())
    if tags_text:
        parts.append(tags_text)
    return " ".join(parts)


def publish(context, path: Path, *, title: str = "", desc: str = "", tags=(),
            do_publish: bool = False, keep_tab: bool = False) -> tuple[str, str]:
    """把 ``path`` 这条视频填进视频号助手的发布页，返回（状态, 结论说明）。

    状态取值：``published``（已提交并确认）、``submitted``（点了发表但没能确认结果）、
    ``drafted``（``--no-publish``：填好停在「发表」前等人工）、``need_login``（停在登录/扫码页）、
    ``failed``（出错）。调用方据此维护状态机——`need_login` 不是内容的问题，不该记成 failed。

    ``do_publish=True``（默认路径）时：填表 → 读回核对（对不上就不提交）→ 点「发表」→ 等成功信号。
    页签纪律：**新开自己的页签**，只动它一个；只有「需要人工扫码」与「--no-publish 等人工点」
    两种情况会把它留着，其余（发表完、出错）都关掉自己的页签，现场留在 `logs/` 的截图里。
    """
    if not path.exists():
        return "failed", f"找不到本地文件：{path}"

    page = context.new_page()
    keep = keep_tab
    try:
        try:
            page.bring_to_front()   # 后台标签会被节流，这个 SPA 可能迟迟不渲染
        except Exception:
            pass
        page.goto(CREATE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)

        if not _wait_form(page, FORM_TIMEOUT_MS):
            _diagnose(page)
            if _need_login(page):
                keep = True   # 这一页留给用户扫码
                shot = _screenshot(page, "publish_login")
                log(f"未登录：停在登录页（{page.url}），截图 {shot}。")
                log("请在浏览器里扫码登录后重跑本条命令；脚本不代做登录。")
                return "need_login", "未登录（已截图），需要人工扫码"
            shot = _screenshot(page, "publish_noform")
            return "failed", f"发布页表单没出现（截图 {shot}）：可能页面改版或网络异常"

        page.set_input_files(FILE_INPUT, str(path))
        log(f"已提交文件：{path.name}（{path.stat().st_size / 1024 / 1024:.1f} MB），等上传/转码…")
        ready = _wait_upload(page, UPLOAD_TIMEOUT_MS)
        if not ready:
            _diagnose(page)

        desc_text = _compose_desc(desc, tags)
        filled = []
        if _fill_desc(page, desc_text):
            filled.append("描述")
        applied_title = _fill_title(page, title)
        if applied_title:
            filled.append("短标题")
        log(f"已填：{'、'.join(filled) if filled else '（没有可填的字段）'}")
        if tags:
            log("话题是以 `#标签` 文本写进描述的；发布后请在后台核对一下话题是否生效。")

        # 自动提交之后就没机会改了：先把值读回来核对，字段没真进去就绝不提交
        problems = _verify_filled(page, applied_title, desc_text)
        if problems:
            keep = True
            shot = _screenshot(page, "publish_unfilled")
            _diagnose(page)
            return "failed", "表单没填对，已放弃提交：" + "；".join(problems) + f"（截图 {shot}）"
        log("字段核对通过（读回来的值与要填的一致）。")

        if not do_publish:
            keep = True   # 表单留着给人看/给人点，别关掉
            shot = _screenshot(page, "publish_form")
            _diagnose(page)
            return "drafted", (
                f"半自动（--no-publish）：表单已填好（截图 {shot}），停在「发表」按钮前"
                f"（按钮状态：{_publish_state(page)}）。请在浏览器里核对后手动点「发表」；"
                f"发完回写状态：python -m src.cli mark <video_id> published --post-id <id>")

        if not ready:
            keep = True   # 留着让你看清卡在哪
            shot = _screenshot(page, "publish_notready")
            return "failed", (f"上传/转码还没完成（发表按钮{_publish_state(page)}），"
                              f"没有点发表；截图 {shot}")

        page.get_by_role("button", name=PUBLISH_TEXT, exact=True).click(timeout=PAGE_TIMEOUT_MS)
        log("已点「发表」，等结果…")
        page.wait_for_timeout(AFTER_PUBLISH_MS)
        confirm = page.get_by_role("button", name=CONFIRM_TEXT, exact=True)
        if confirm.count():
            confirm.first.click(timeout=5_000)
            log(f"弹窗要求确认，又点了「{CONFIRM_TEXT}」。")
            page.wait_for_timeout(2_000)
        return _after_submit(page)
    except Exception as exc:
        shot = _screenshot(page, "publish_fail")
        log(f"发布流程出错：{type(exc).__name__}: {exc}（截图 {shot}）")
        return "failed", f"出错：{type(exc).__name__}: {exc}（截图 {shot}）"
    finally:
        if not keep:
            try:
                page.close()
            except Exception:
                pass
