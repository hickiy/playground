"""真实 Chrome 的查找、启动、连接与健康探测。

启动时**不加** `--disable-background-mode`：带调试端口的 Chrome 默认启用后台模式，
窗口关掉后进程仍留驻、调试端口继续可用——这正是「CDP 随时可连接」的前提。

健康探测分三级，只有第三级能识别「端口在、浏览器已经僵死」（被 SIGSTOP、
或从睡眠里没恢复过来时正是这种状态，此时 `/json/version` 照样返回 200）。
"""

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from .config import CDP_WAIT_MS, HEALTH_TIMEOUT_MS
from .logging import log

# 健康级别，从差到好
LEVEL_DOWN = "down"   # 端口都不通：浏览器没在运行
LEVEL_L1 = "l1"       # /json/version 通：调试端口在监听
LEVEL_L2 = "l2"       # /json/list 通：能枚举标签页
LEVEL_OK = "ok"       # CDP 往返成功：浏览器进程真的在响应


def cdp_url_of(port: int) -> str:
    """调试端口对应的 CDP 地址。"""
    return f"http://localhost:{port}"


# ---- 进程级 Playwright 实例 ----
#
# Playwright 的**同步 API 每个线程只能有一个活动实例**：同一个进程里第二次调用
# `sync_playwright().start()` 会抛「It looks like you are using Playwright Sync API
# inside the asyncio loop」。实际用法本来就是「一个任务进程连一个浏览器实例」，
# 所以这里做两件事：把实例登记下来避免重复启动，以及给出能看懂的报错。

_active_pw = None


def active_playwright():
    """本进程当前活动的 Playwright 实例；没有则 None。"""
    return _active_pw


def start_playwright():
    """启动并登记本进程的 Playwright 实例。

    已经有活动实例时抛 RuntimeError（而不是让 Playwright 抛出难懂的内部错误）。
    """
    global _active_pw
    if _active_pw is not None:
        raise RuntimeError(
            "本进程已经有一个活动的 Playwright 会话：Playwright 同步 API 在同一线程里"
            "只能存在一个实例。一个进程连接一个浏览器实例即可；需要同时操作多个页面时，"
            "用同一个 CDP 连接开多个标签页，或把另一个任务放到子进程里跑。")
    _active_pw = sync_playwright().start()
    return _active_pw


def stop_playwright(pw) -> None:
    """停掉并注销 Playwright 实例（CDP 连接只是断开，浏览器继续跑）。"""
    global _active_pw
    if pw is None:
        return
    try:
        pw.stop()
    except Exception:
        pass
    if _active_pw is pw:
        _active_pw = None


# ---- 查找与探测 ----

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


def _http_get_json(url: str, timeout_s: float) -> object | None:
    """GET 一个返回 JSON 的调试端口端点；失败返回 None。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None


def cdp_reachable(cdp_url: str, timeout_s: float = 1.0) -> bool:
    """L1：该地址上是否已有可用的 CDP 调试端口。"""
    data = _http_get_json(cdp_url.rstrip("/") + "/json/version", timeout_s)
    return isinstance(data, dict)


def list_targets_http(cdp_url: str, timeout_s: float = 2.0) -> list | None:
    """L2：通过 HTTP 端点枚举标签页；失败返回 None。"""
    data = _http_get_json(cdp_url.rstrip("/") + "/json/list", timeout_s)
    return data if isinstance(data, list) else None


def cdp_roundtrip(cdp_url: str, timeout_ms: int = HEALTH_TIMEOUT_MS) -> bool:
    """L3：连上调试端口并做一次 CDP 往返（Browser 级，不碰任何标签页）。

    只有它能识别「端口在、浏览器进程已僵死」——`/json/version` 此时照样是 200，
    因为那只是 HTTP 处理器还活着。用 Browser 级会话是因为它无副作用：不会打开
    或关闭任何标签页，因此可以安全地在别人的实例上执行。

    说明：Playwright 的 `send()` 没有超时参数，卡住时的兜底是 `connect_over_cdp`
    的握手超时；握手成功后再僵死的窗口极小。
    本进程已有活动实例时直接复用它（再启一个会报错），用完不停止那个共享实例。
    """
    pw = _active_pw
    owned = pw is None
    try:
        if owned:
            pw = start_playwright()
        browser = pw.chromium.connect_over_cdp(cdp_url, timeout=timeout_ms)
        browser.new_browser_cdp_session().send("Target.getTargets")
        return True
    except Exception:
        return False
    finally:
        if owned:
            stop_playwright(pw)   # 只断开 CDP 连接，浏览器继续跑


def health(cdp_url: str, *, deep: bool = True) -> str:
    """返回健康级别：LEVEL_DOWN / LEVEL_L1 / LEVEL_L2 / LEVEL_OK。

    `deep=False` 时跳过 L3（省一次 Playwright 启动，约 0.3s）。
    """
    if not cdp_reachable(cdp_url):
        return LEVEL_DOWN
    if list_targets_http(cdp_url) is None:
        return LEVEL_L1
    if deep and not cdp_roundtrip(cdp_url):
        return LEVEL_L2
    return LEVEL_OK


# ---- 启动 ----

def launch_chrome(port: int, profile: str, url: str,
                  chrome_path: str | None = None,
                  proxy: str | None = None,
                  extra_flags: tuple[str, ...] | list[str] = ()) -> bool:
    """启动带远程调试端口的真实 Chrome，返回是否成功拉起进程。

    `profile` 必须是非默认目录：Chrome 136+ 直接拒绝在默认用户数据目录上开调试
    端口（`DevTools remote debugging requires a non-default data directory`）。
    """
    chrome = chrome_path or find_chrome()
    if not chrome:
        log("未找到 Chrome/Edge，请用 --chrome 指定可执行文件路径。")
        return False
    profile_dir = Path(profile).expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    command = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
    ]
    if proxy:
        command.append(f"--proxy-server={proxy}")
    command.extend(extra_flags)
    command.append(url)
    log(f"启动 Chrome: {chrome}（调试端口 {port}，用户数据目录 {profile_dir}）")
    try:
        subprocess.Popen(command)
    except Exception as exc:
        log(f"启动 Chrome 失败: {exc}")
        return False
    return True


def wait_for_cdp(cdp_url: str, timeout_ms: int = CDP_WAIT_MS) -> bool:
    """等调试端口就绪——Chrome 从启动到监听端口会有延迟。"""
    deadline = time.time() + timeout_ms / 1000
    while True:
        if cdp_reachable(cdp_url):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.2)
