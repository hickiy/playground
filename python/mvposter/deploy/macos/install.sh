#!/bin/zsh
# 安装 LaunchAgent：每天 03:00 跑一轮完整任务（检索 → 挑选 → 下载 → 发布）。
# 卸载：launchctl bootout gui/$(id -u)/com.mvposter.job && rm ~/Library/LaunchAgents/com.mvposter.job.plist
set -eu

DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$DIR/../.." && pwd)"
LABEL="com.mvposter.job"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"

chmod +x "$DIR/run_job.sh"
mkdir -p "$PROJECT_DIR/logs" "$HOME/Library/LaunchAgents"   # launchd 写日志要求目录已存在

sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$DIR/$LABEL.plist" > "$TARGET"
plutil -lint "$TARGET"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true   # 已加载则先卸载
launchctl bootstrap "gui/$(id -u)" "$TARGET"
launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -E 'state|program' || true

cat <<'EOF'

安装完成。还有三步才能真正凌晨无人值守跑通：

1) 常驻 Chrome 必须先起好、并且**视频号助手仍是登录状态**（定时任务只连接它，
   不会自己启动浏览器，也不会自动登录）：
     在 browserhost 项目目录里执行：python main.py start
   登录态失效时本轮会停在登录页、记 need_login 并保留页签，下一轮同样失败——
   所以早上看到 need_login 就去那只 Chrome 里扫一次码。

2) 定时唤醒——launchd 不会唤醒睡眠中的 Mac，需要 sudo：
     sudo pmset repeat wakeorpoweron MTWRFSU 02:55:00
   查看：pmset -g sched

3) 确认这台 Mac 持续接电源、且不要合盖（caffeinate 的 -s 断言只在 AC 下有效）。

试跑（--dry-run 只检索+挑选，不会下载、也不会发）：
     ./deploy/macos/run_job.sh --dry-run
     launchctl kickstart -k gui/$(id -u)/com.mvposter.job

只想让凌晨那轮「填好表等人点发表」（更安全），编辑 run_job.sh 里的
PUBLISH_MODE 默认值，或给 plist 加一行 EnvironmentVariables：
     <key>MVPOSTER_PUBLISH_MODE</key><string>--no-publish</string>
EOF
