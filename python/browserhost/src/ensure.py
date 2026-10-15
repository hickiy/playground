"""「确保实例可用」的完整流程：`main.py start` 的实现。

顺序：三级健康探测 → 能复用就复用 → 不健康就重启 →
端口被陌生人占着就报错退出 → 都没有才启动 → 等端口就绪 → 复核健康 → 记状态。

幂等是硬要求：定时任务、手动执行、多个任务同时启动都可能调到它，不能出现第二个实例
（同一 profile 被两个 Chrome 进程使用会互相破坏登录态）。
"""

from pathlib import Path

from . import config
from .chrome import (LEVEL_L1, LEVEL_L2, LEVEL_OK, cdp_url_of, health,
                     launch_chrome, wait_for_cdp)
from .instance import (Instance, close_instance, listener_pid, now_str,
                       owner_of, read_state, write_state)
from .logging import log


def ensure_up(name: str = "default", port: int | None = None,
              profile: str | Path | None = None, url: str | None = None,
              chrome: str | None = None, proxy: str | None = None, *,
              deep: bool = True,
              extra_flags=config.RECOMMENDED_FLAGS,
              restart_unhealthy: bool = True) -> tuple[int, Instance | None]:
    """确保实例可用；返回 (退出码, 实例)。退出码为 0 时可以直接连接它。"""
    inst = read_state(name)
    port = port or (inst.port if inst else config.DEFAULT_PORT)
    if profile is None:
        profile = Path(inst.profile) if inst and inst.profile else config.PROFILE_DIR
    profile = Path(profile).expanduser()
    cdp_url = cdp_url_of(port)

    level = health(cdp_url, deep=False)
    if level == LEVEL_OK:
        log(f"实例已就绪（端口 {port}），复用：CDP {cdp_url}")
        ready = Instance(
            name=name, port=port, profile=str(profile),
            pid=listener_pid(port) or (inst.pid if inst else None),
            chrome=chrome or (inst.chrome if inst else None),
            launched_by_us=True,
            created_at=inst.created_at if inst else now_str(),
        )
        write_state(ready)
        return 0, ready

    if level in (LEVEL_L1, LEVEL_L2) and restart_unhealthy:
        log(f"端口 {port} 有响应但健康级别只有 {level}（浏览器进程可能已僵死），先重启它...")
        ok, message = close_instance(name=name if inst else None, port=port, force=True)
        log(message)
        if not ok:
            return 1, None

    owner = owner_of(port)
    if owner["pid"] is not None and not owner["managed"]:
        log(f"端口 {port} 已被非受管进程占用（pid {owner['pid']}）：{owner['command'] or '未知'}")
        log("请先关闭占用它的进程（若是我们自己启动的实例，用 python main.py stop），"
            "或换一个端口。")
        return 1, None

    if not launch_chrome(port, str(profile), url or "about:blank", chrome,
                         proxy=proxy, extra_flags=extra_flags):
        return 1, None
    if not wait_for_cdp(cdp_url):
        log(f"等待 {cdp_url} 就绪超时：Chrome 没起来，或用户数据目录已被残留进程占用"
            f"（{profile}）；也可能是端口指向了 Chrome 的默认 profile"
            "（Chrome 136+ 会拒绝在默认目录上开启调试端口）。")
        return 1, None
    level = health(cdp_url, deep=deep)
    if level != LEVEL_OK:
        log(f"启动后健康检查未通过（{level}）：端口在监听但 CDP 不响应。")
        return 1, None

    ready = Instance(
        name=name, port=port, profile=str(profile),
        pid=listener_pid(port), chrome=chrome,
        launched_by_us=True,
        created_at=now_str(),
    )
    write_state(ready)
    log(f"Chrome 已就绪（CDP: {cdp_url}）。窗口随时可以关掉：Chrome 进程会留在后台，"
        "调试端口一直可用。")
    return 0, ready
