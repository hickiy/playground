"""路径与默认值。

所有运行时数据集中在「宿主目录」下，默认 `~/.browserhost`，可用环境变量
`BROWSERHOST_HOME` 覆盖（测试或多用户场景）：

    ~/.browserhost/
    ├── profile/           Chrome --user-data-dir（登录态、cookie 都在这里）
    ├── state/<name>.json   实例状态：端口、profile、pid、是否由我们启动
    ├── locks/              文件锁（状态文件读改写互斥）
    └── logs/               宿主自身日志

放在用户主目录根下而不是 Documents/Desktop/Downloads：后三者受 macOS TCC 保护，
无人值守时弹出的授权对话框会让任务直接卡住。
"""

import os
from pathlib import Path

HOME = Path(os.environ.get("BROWSERHOST_HOME") or (Path.home() / ".browserhost")).expanduser()

PROFILE_DIR = HOME / "profile"     # 唯一的 Chrome 用户数据目录（登录态、cookie 都在这里）
STATE_DIR = HOME / "state"         # 实例状态
LOCK_DIR = HOME / "locks"          # 文件锁
LOG_DIR = HOME / "logs"            # 宿主自身日志

# ---- CDP / 页面 ----
DEFAULT_PORT = 9222            # 默认调试端口（要改就在 main.py 里一起定）
CDP_WAIT_MS = 15000            # 等调试端口就绪的超时
PAGE_LOAD_TIMEOUT_MS = 30000   # 页面加载（goto）超时
HEALTH_TIMEOUT_MS = 4000       # L3 健康检查（CDP 往返）超时
CLOSE_WAIT_S = 10.0            # down 等待 Chrome 自行退出的时间
LOCK_TIMEOUT_S = 5.0           # 文件锁等待超时

# ---- Chrome 启动参数 ----
# 共享实例上跑多个无人值守任务时建议加上：让非前台标签页不被节流。
# 不加的话，隐藏标签里的定时器会被降频、rAF 直接停摆，
# `wait_for_function(polling=...)` 这类操作会莫名变慢甚至超时。
RECOMMENDED_FLAGS = (
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--no-first-run",
    "--no-default-browser-check",
)
