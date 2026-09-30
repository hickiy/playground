"""手动启动带调试端口的常驻 Chrome，并检测登录态（抢购的前置步骤）。

流程（只需开一次）：
    1. 启动（已在运行则复用）带调试端口的 Chrome，打开活动页；
    2. 检测登录态：未登录 → 在窗口里引导你登录并等待（默认最多等 300s，
       用 `--login-timeout` 调整）；已登录 → 直接结束；
    3. 之后随时可以关掉浏览器窗口：Chrome 进程会留在后台，调试端口一直可用
       （带 `--remote-debugging-port` 时 Chrome 默认启用后台模式；**不要**加
       `--disable-background-mode`，那会让它随窗口一起退出）；
    4. 抢购直接连这个后台进程完成：`python -m src.grab`（定时任务也只跑它），
       不会重新启动浏览器、也不需要重新登录。

窗口关掉后浏览器里一个页面也没有，而兑换请求必须跑在页面里（要读页面数据
`window.__react_data__`、调 `window.getJsToken()`），所以 grab 这时会临时新建一个
标签页（屏幕上会短暂出现一个窗口），跑完自动关掉，恢复「无窗口、进程仍在」的状态。

再启一次是安全的：检测到端口已在监听就直接复用，不会开出第二个实例。
登录态保存在 `--profile` 指定的用户数据目录里（默认 `./jd_cdp_profile`），跨次复用。

想用「平时那个浏览器」？不能直接用默认 profile：Chrome 136+ 要求
`--user-data-dir` 指向**非默认**目录（Chrome 153 二进制原文：`DevTools remote
debugging requires a non-default data directory. Specify this using --user-data-dir`）。
要带自己的登录态就先把 profile 目录复制到别的路径，再用 `--profile <副本>` 启动
（复制前要完全退出 Chrome）。

用法：
    python launch_browser.py                    # 启动/复用 + 检测登录（未登录则引导）
    python launch_browser.py --check            # 只检查调试端口是否可用
    python launch_browser.py --login-timeout 600  # 登录等待时间（0 = 只检测不等待）
    python launch_browser.py --url <页面>       # 换一个打开/检测登录用的地址
"""

import argparse
import sys

from src import config
from src.browser import (
    CDP_WAIT_MS,
    CdpSession,
    cdp_reachable,
    launch_chrome,
    log,
    wait_for_cdp,
    wait_for_login,
)

DEFAULT_PORT = 9222                     # 调试端口（与 src/grab.py 的默认值一致）
DEFAULT_PROFILE = "./jd_cdp_profile"    # 用户数据目录（登录态保存在这里）


def main() -> int:
    parser = argparse.ArgumentParser(
        description="启动带 CDP 调试端口的真实 Chrome（供 python -m src.grab 连接）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"调试端口，默认 {DEFAULT_PORT}")
    parser.add_argument("--profile", default=DEFAULT_PROFILE,
                        help=f"Chrome 用户数据目录，默认 {DEFAULT_PROFILE}"
                             "（登录态保存在这里）")
    parser.add_argument("--url", default=config.ACTIVITY_URL,
                        help="启动后打开的地址，默认活动页（未登录时会跳到登录页）")
    parser.add_argument("--chrome", help="Chrome/Edge 可执行文件路径，默认自动查找")
    parser.add_argument("--check", action="store_true",
                        help="只检查调试端口是否可用，不启动浏览器、不检测登录")
    parser.add_argument("--login-timeout", type=int, default=300,
                        help="未登录时在窗口中等待登录的秒数，默认 300；0 表示只检测不等待")
    args = parser.parse_args()

    cdp_url = f"http://localhost:{args.port}"

    if args.check:
        if cdp_reachable(cdp_url):
            log(f"浏览器已在运行，调试端口可用（CDP: {cdp_url}）。")
            return 0
        log(f"调试端口不可用（CDP: {cdp_url}）：请先运行 python launch_browser.py 启动浏览器。")
        return 1

    if cdp_reachable(cdp_url):
        log(f"浏览器已在运行（CDP: {cdp_url}），复用它，不再启动新实例。")
    else:
        log("=" * 20 + " 启动常驻 Chrome（CDP） " + "=" * 20)
        if not launch_chrome(args.port, args.profile, args.url, args.chrome):
            return 1
        if not wait_for_cdp(cdp_url, CDP_WAIT_MS):
            log(f"等待 {cdp_url} 就绪超时：Chrome 没起来，或用户数据目录已被残留进程占用"
                f"（{args.profile}，先完全退出 Chrome/关掉旧窗口再试）。")
            log("若端口指向的是 Chrome 默认 profile，Chrome 136+ 会直接拒绝开启调试端口，"
                "请换成非默认目录（如默认的 ./jd_cdp_profile）。")
            return 1
        log(f"Chrome 已就绪（CDP: {cdp_url}）。")

    # 借 src/browser.py 的会话与登录工具：打开活动页 → 检测登录态（未登录则引导等待）
    session = CdpSession(cdp_url, args.url)
    try:
        session.connect()
        page = session.open_page(args.url)
        logged_in = wait_for_login(page, args.login_timeout)
    except Exception as exc:
        log(f"连接浏览器 / 打开活动页失败: {exc}")
        return 1
    finally:
        # 只断开调试连接；页面留给用户（`keep_page=True`），浏览器保持运行
        session.close(keep_page=True)

    if not logged_in:
        return 1

    log("登录态正常，执行结束。窗口随时可以关掉：Chrome 进程会留在后台，"
        "调试端口一直可用（CDP 随时可连）。")
    log("之后运行 `python -m src.grab` 即可抢购（定时任务也只跑它）；"
        "窗口已关时它会临时新建一个页面，抢完自动关掉。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
