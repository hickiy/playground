#!/usr/bin/env python
"""browserhost 入口：启动 / 关闭 / 重启 CDP 宿主。

browserhost 只做三件事：启动一个 Chrome、提供 CDP 连接服务、持久化它的 profile。
页签与任务都归连接方自己管，所以这里不需要任何参数：

    python main.py start      # 启动（幂等：已在跑且健康就复用）
    python main.py stop       # 优雅关闭（先请 Chrome 自己退出）
    python main.py restart    # 先关再启动
"""

import argparse
import sys
from pathlib import Path

# 本项目不是安装包：把项目根加进来，`python main.py` 才能 import src
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.ensure import ensure_up
from src.instance import close_instance
from src.logging import configure, log

INSTANCE = "jd"             # 只维护一个实例：状态文件名与端口（9222）跟着它走。
# profile 目录是固定的 `~/.browserhost/profile`（登录态：京东 + Google/YouTube 都在里面），
# 与实例名无关；实例名只决定状态文件名 `~/.browserhost/state/<name>.json`。


def start() -> int:
    """启动（幂等：已在跑且健康就复用）。"""
    code, _ = ensure_up(name=INSTANCE)
    return code


def stop() -> int:
    """优雅关闭（先请 Chrome 自己退出）。"""
    ok, message = close_instance(name=INSTANCE)
    log(message)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="启动/关闭/重启那个常驻 Chrome")
    parser.add_argument("action", choices=("start", "stop", "restart"),
                        help="start 启动/复用、stop 优雅关闭、restart 先关再启动")
    return parser


def main() -> int:
    configure()            # 宿主日志：~/.browserhost/logs/browserhost_<日期>.log
    action = build_parser().parse_args().action
    try:
        if action == "start":
            return start()
        if action == "stop":
            return stop()
        # restart：本来就没在跑时 stop 会失败，这不算错误——接着启动就行
        stop()
        return start()
    except KeyboardInterrupt:
        log("已中断（Ctrl+C）。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
