#!/bin/zsh
# 完整任务的包装脚本：锁住系统不睡 + 在项目根目录执行 python -m src.job。
#
# 手动试跑：
#   ./deploy/macos/run_job.sh --dry-run     # 只检索 + 挑选并打印计划，不下载、不发布
#   ./deploy/macos/run_job.sh               # 真跑一轮（会下载并发布）
#   ./deploy/macos/run_job.sh --no-publish  # 真跑，但只填表停在「发表」前等人工点
#
# 两个开关用环境变量覆盖，不必改这个文件（launchd 里改则编辑 com.mvposter.job.plist 的
# EnvironmentVariables，或直接改下面的默认值）：
#   MVPOSTER_COUNT         每轮处理几条，默认 1（风控风险最低）
#   MVPOSTER_PUBLISH_MODE  --publish（默认，填完即自动提交）
#                          --no-publish（只填表 + 截图，早上人工核对后点发表）
#
# caffeinate 的断言只在本次命令运行期间持有：覆盖「检索 → 下载 → 上传 → 发布」整段，
# 跑完自动释放。用 -dims：-s 只在接电源时有效，-d 让显示屏也别睡（顺带避免 App Nap
# 节流 Chrome）。
#
# 浏览器由 browserhost 启动并常驻（见 ../browserhost 的 `python main.py start`），本脚本
# 只连接它：连不上会记日志并以退出码 1 结束，不会自动拉起浏览器。
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "找不到 $PYTHON，请先在项目根目录执行 uv sync" >&2
    exit 1
fi

cd "$PROJECT_DIR"

COUNT="${MVPOSTER_COUNT:-1}"
PUBLISH_MODE="${MVPOSTER_PUBLISH_MODE:---publish}"

# 先留一行「包装脚本被调用了」的痕迹（带日期），便于和日志里的任务记录对齐核对。
echo "[$(date '+%F %T')] run_job.sh 启动（cwd=$PROJECT_DIR，count=$COUNT，mode=$PUBLISH_MODE，参数: ${*:-（无）}）"

exec /usr/bin/caffeinate -dims "$PYTHON" -m src.job --count "$COUNT" "$PUBLISH_MODE" "$@"
