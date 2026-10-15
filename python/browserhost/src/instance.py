"""实例状态、归属判定与优雅关闭。

替代以前那套「命令行查 9222 端口是谁占着、再手动 kill」：`python main.py start` 启动
Chrome 时把端口与 pid 记进 `~/.browserhost/state/<name>.json`，`stop` 按记录关它。

三条硬规矩：
  1. **绝不按端口号或命令行模糊匹配去 pkill**：pid 可以被复用，误杀用户日常浏览器
     的代价太大。关之前必须能证明「这个 pid 就是那个 profile 的 Chrome」。
  2. **优先请 Chrome 自己退出**（CDP `Browser.close`）：这才是干净关法，profile
     不会留下 `exit_type=Crashed`，下次启动也就不会弹「恢复上次会话」。
     强杀是最后手段。
  3. **非受管实例默认不关**：用户自己手动起的调试端口 Chrome，要 --force 才动。
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from . import config
from .chrome import (active_playwright, cdp_reachable, cdp_url_of,
                     start_playwright, stop_playwright)
from .lock import file_lock
from .logging import log


@dataclass
class Instance:
    """一个受管实例：一个 Chrome 进程 + 一个 profile + 一个调试端口。"""

    name: str
    port: int
    profile: str
    pid: int | None = None
    chrome: str | None = None
    launched_by_us: bool = False
    created_at: str = ""

    @property
    def cdp_url(self) -> str:
        return cdp_url_of(self.port)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def state_path(name: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return config.STATE_DIR / f"{safe}.json"


# ---- 状态文件 ----

def read_state(name: str) -> Instance | None:
    path = state_path(name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Instance(**{k: v for k, v in data.items() if k in Instance.__dataclass_fields__})
    except FileNotFoundError:
        return None
    except Exception:
        return None


def write_state(inst: Instance) -> None:
    path = state_path(inst.name)
    with file_lock(config.LOCK_DIR / "state.lock"):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(inst), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def remove_state(name: str) -> None:
    try:
        state_path(name).unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def list_states() -> list[Instance]:
    """列出所有受管实例（按名字排序）。"""
    if not config.STATE_DIR.exists():
        return []
    out: list[Instance] = []
    for path in sorted(config.STATE_DIR.glob("*.json")):
        inst = read_state(path.stem)
        if inst is not None:
            out.append(inst)
    return out


# ---- 进程与端口 ----

def pid_command(pid: int) -> str | None:
    """取 pid 的命令行；取不到返回 None。"""
    try:
        if sys.platform == "win32":
            cmd = ["powershell", "-NoProfile", "-Command",
                   f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"]
        else:
            cmd = ["ps", "-o", "command=", "-p", str(pid)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        text = (result.stdout or "").strip()
        return text or None
    except Exception:
        return None


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        return pid_command(pid) is not None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True     # 存在但无权发信号
    except OSError:
        return False
    return True


def verify_pid(pid: int, profile: str) -> tuple[bool, str | None]:
    """确认 pid 就是那个 profile 的 Chrome：命令行里必须带同样的 --user-data-dir。

    Chrome 打印命令行时路径可能带引号（`--user-data-dir="C:\\..."`），也可能不带，
    所以先把引号统一去掉再比对。
    """
    command = pid_command(pid)
    if not command:
        return False, None
    want = str(Path(profile).expanduser().resolve()).rstrip("\\/")
    normalized = command.replace('"', "").replace("'", "")
    return f"--user-data-dir={want}" in normalized, command


def listener_pid(port: int) -> int | None:
    """谁在监听这个 TCP 端口；取不到返回 None（工具缺失或无权限）。"""
    try:
        if sys.platform == "win32":
            result = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                                    capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[3].upper() == "LISTENING" \
                        and parts[1].endswith(f":{port}"):
                    return int(parts[4])
            return None
        result = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                                capture_output=True, text=True, timeout=10)
        for token in result.stdout.split():
            if token.strip().isdigit():
                return int(token)
        return None
    except Exception:
        return None


def owner_of(port: int) -> dict:
    """端口占用诊断：返回 {port, pid, command, managed, name}。

    `managed` 为真表示它就是我们记录在案的实例；否则是「陌生的」调试端口 Chrome
    （通常是用户手动起的），关它要 --force。
    """
    pid = listener_pid(port)
    inst = next((i for i in list_states() if i.port == port), None)
    managed = inst is not None and (pid is None or inst.pid is None or inst.pid == pid)
    return {
        "port": port,
        "pid": pid,
        "command": pid_command(pid) if pid else None,
        "managed": managed,
        "name": inst.name if inst else None,
    }


# ---- 关闭 ----

def _cdp_close(cdp_url: str, timeout_ms: int = 3000) -> bool:
    """请 Chrome 自己退出（CDP `Browser.close`）；这是最干净的关法。"""
    pw = active_playwright()
    owned = pw is None
    try:
        if owned:
            pw = start_playwright()
        browser = pw.chromium.connect_over_cdp(cdp_url, timeout=timeout_ms)
        browser.new_browser_cdp_session().send("Browser.close")
        return True
    except Exception:
        return False
    finally:
        if owned:
            stop_playwright(pw)


def _signal(pid: int, force: bool) -> None:
    """发信号：非强杀用 SIGTERM（Chrome 会正常收尾），强杀才 SIGKILL。"""
    if sys.platform == "win32":
        cmd = ["taskkill", "/PID", str(pid)]
        if force:
            cmd.append("/F")
        subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return
    os.kill(pid, 9 if force else 15)


def _wait_gone(pid: int | None, cdp_url: str, timeout_s: float) -> bool:
    """等 Chrome 退干净：进程没了、并且调试端口也不再监听。"""
    deadline = time.time() + timeout_s
    while True:
        alive = pid_alive(pid) if pid else False
        if not alive and not cdp_reachable(cdp_url, timeout_s=0.5):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.3)


def close_instance(name: str | None = None, port: int | None = None,
                   force: bool = False, wait_s: float = config.CLOSE_WAIT_S
                   ) -> tuple[bool, str]:
    """优雅关闭一个实例，返回 (是否成功, 说明)。

    顺序：CDP `Browser.close` → 等自行退出 → SIGTERM → SIGKILL。
    任何一步之前都要先证明 pid 归属；证明不了又没给 --force 就拒绝执行。
    """
    inst = read_state(name) if name else None
    if inst is not None:
        port = port or inst.port
    if port is None:
        if name:
            return True, f"没有实例「{name}」的记录（可能已经关闭，或从未启动过）"
        return False, "必须指定要关闭的实例（name 或 port）"

    cdp_url = cdp_url_of(port)
    # 记录里的 pid 只在它还活着时才可信（进程可能已退出、pid 也可能被复用）；
    # 否则以「现在谁在监听这个端口」为准。
    recorded = inst.pid if inst else None
    pid = recorded if pid_alive(recorded) else listener_pid(port)
    profile = inst.profile if inst else None

    if pid is None and not cdp_reachable(cdp_url):
        if inst is not None:
            remove_state(inst.name)     # 只剩个残留状态文件，顺手清掉
            return True, f"端口 {port} 上没有监听进程（可能已经关闭），已清理实例「{inst.name}」的记录"
        return True, f"端口 {port} 上没有监听进程，无需关闭"

    # 归属校验：pid 会被复用，必须先证明它就是我们那个 profile 的 Chrome
    if inst is None and pid is not None and not force:
        command = pid_command(pid)
        return False, (f"端口 {port} 由非受管进程占用（pid {pid}），"
                       f"拒绝关闭以免误杀。命令行：{command or '未知'}；"
                       "确认要关闭请加 --force")
    if inst is not None and pid is not None and profile:
        ok, command = verify_pid(pid, profile)
        if not ok and not force:
            return False, (f"pid {pid} 的命令行与实例「{inst.name}」的 profile 不匹配，"
                           f"拒绝关闭（pid 可能已被复用）。命令行：{command or '未知'}；"
                           "确认要关闭请加 --force")
        if not ok:
            log(f"警告：--force 关闭 pid {pid}，但它不是 profile {profile} 的 Chrome")

    # 1) 优雅：请 Chrome 自己退出
    graceful = _cdp_close(cdp_url)
    if graceful and _wait_gone(pid, cdp_url, wait_s):
        _finish_close(inst)
        return True, f"已优雅关闭实例（端口 {port}，pid {pid}）"

    # 2) SIGTERM → 3) SIGKILL
    if pid is not None and pid_alive(pid):
        log(f"CDP 关闭未生效（或浏览器已僵死），改用 SIGTERM: pid {pid}")
        try:
            _signal(pid, force=False)
        except Exception as exc:
            log(f"SIGTERM 失败: {exc}")
        if not _wait_gone(pid, cdp_url, wait_s):
            log(f"仍未退出，强杀 pid {pid}（profile 可能残留「恢复上次会话」提示）")
            try:
                _signal(pid, force=True)
            except Exception as exc:
                return False, f"强杀失败: {exc}"
            if not _wait_gone(pid, cdp_url, 3.0):
                return False, f"关闭失败：pid {pid} 仍然在运行"

    _finish_close(inst)
    return True, f"已关闭实例（端口 {port}，pid {pid}）"


def _finish_close(inst: Instance | None) -> None:
    """关闭后的清理：删掉状态文件。"""
    if inst is None:
        return
    remove_state(inst.name)
