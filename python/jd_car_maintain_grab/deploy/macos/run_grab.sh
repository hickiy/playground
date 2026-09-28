#!/bin/zsh
# 抢购包装脚本：锁住系统不睡 + 在项目根目录执行 python -m src.grab。
#
# 手动试跑（会真的发兑换请求）：
#   ./deploy/macos/run_grab.sh --test
#
# caffeinate 断言只在本次命令运行期间持有：覆盖「启动 Chrome → 等到 09:59:55
# 提前开抢 → 跑满重试次数」整段，跑完自动释放。持续接电源时 -s 才有效，
# 这正符合本目录的部署前提；-d 让显示屏也别睡，顺带避免 App Nap 节流 Chrome。
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "找不到 $PYTHON，请先在项目根目录执行 uv sync" >&2
    exit 1
fi

cd "$PROJECT_DIR"

# 先留一行「包装脚本被调用了」的痕迹（带日期），便于和日志里的抢购记录对齐核对；
# 注意别在同一时间重复启动：两次运行会复用同一个 Chrome 与调试端口，双倍发请求。
echo "[$(date '+%F %T')] run_grab.sh 启动（cwd=$PROJECT_DIR，参数: ${*:-（无）}）"

exec /usr/bin/caffeinate -dims "$PYTHON" -m src.grab "$@"
