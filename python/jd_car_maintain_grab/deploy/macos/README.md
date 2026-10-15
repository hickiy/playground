# macOS 定时运行

用 LaunchAgent 每天 09:50 拉起抢购：`caffeinate` 保证「等到 10:00:00 开抢」这段期间机器不睡，
`pmset` 到点把机器唤醒（launchd 自己不会唤醒睡眠中的 Mac）。

**前提（只能由人保证）**：**不合盖**（合盖必然进入无法唤醒的睡眠）、**持续接电源**
（`caffeinate -s` 的断言只在 AC 下有效）、已在该 Mac 上登录过京东、时区与时钟正确。
`run_grab.sh` 只连接常驻实例：连不上就记日志并以退出码 `1` 结束，不会自己拉起浏览器。

## 时间线

| 时刻 | 动作 |
|---|---|
| 09:45 | `pmset` 唤醒 Mac |
| 09:50 | LaunchAgent 跑 `run_grab.sh`：`caffeinate` 持锁 → 连接常驻 Chrome 打开活动页 → 读兑换参数（之后每 20s 探活，丢了就地恢复） |
| 10:00:00 | 开抢：前 2 秒每 100ms 一次，之后每 1000ms 一次 |
| ~10:00:22 | 跑满 40 次后退出（只断开调试连接，浏览器继续常驻） |

## 安装

```bash
cd /path/to/jd_car_maintain_grab
./deploy/macos/install.sh                       # 渲染 plist、加载 LaunchAgent

# 先启动常驻 Chrome 并在窗口里登录（定时任务只连接它，不会自己启动浏览器）
cd ../browserhost && python main.py start

# 定时唤醒（需要 sudo，install.sh 不会替你执行）
sudo pmset repeat wakeorpoweron MTWRFSU 09:45:00
pmset -g sched                                  # 确认时间表
```

想改启动时刻：改 `deploy/macos/com.jd.grab.plist` 里的 `StartCalendarInterval`，再跑一次
`install.sh`。

## 验证

```bash
pmset -g sched                                   # 唤醒时间表
launchctl print gui/$(id -u)/com.jd.grab         # LaunchAgent 状态
pmset -g assertions                              # 运行时应看到 caffeinate 持有 PreventUserIdleSystemSleep
tail -f logs/launchd.out.log                     # launchd 捕获的终端输出
tail -f logs/jd_grab_$(date +%F).log             # 脚本自己的执行日志（含抢购结果）

# 常驻实例（在 browserhost 项目目录里执行）
python main.py start                             # 幂等：已在跑就复用，不健康会自动重启
tail -f ~/.browserhost/logs/browserhost_$(date +%F).log   # 宿主自己的日志（起停/健康探测）
```

日志里出现 `探活失败` / `页面/连接已丢失` / `会话已恢复` 属正常自愈，不必当成失败。

## 卸载

```bash
launchctl bootout gui/$(id -u)/com.jd.grab
rm ~/Library/LaunchAgents/com.jd.grab.plist
sudo pmset schedule cancelall
```

## 注意

- **必须装成 LaunchAgent（用户会话 `gui/<uid>`）**，不能用 LaunchDaemon：任务要连接用户
  启动的真实 Chrome，还要持有 `caffeinate`。请保持用户处于登录状态、**不要注销**
  （注销会结束用户会话，连带杀掉 LaunchAgent 与 Chrome）。
- **锁屏可以**（不影响 Chrome、CDP 连接与 Python 计时）；**合盖会睡**，见开头的前提。
- **保持浏览器常驻**：定时任务只连接它，窗口关掉没问题（Chrome 进程留在后台）。但
  **别退出 Chrome 进程**（Cmd+Q / 活动监视器里结束 `chrome.exe`），**机器重启后也要重新
  `python main.py start`**：这些情况下调试端口都会消失，脚本不会自己启动浏览器，这轮会以
  退出码 `1` 结束——在 browserhost 里 `python main.py start`（幂等）即可恢复。
- **同一时间别重复启动**（`launchctl kickstart` 与手动 `run_grab.sh --test` 并发）：两次运行
  会复用同一个 Chrome 与调试端口，变成双倍发请求，更容易撞 `F30001` 限流。
- `launchctl kickstart -k gui/$(id -u)/com.jd.grab` 或 `run_grab.sh --test` 会**真的调用
  兑换接口**，不确定时别乱试。
- 开抢那一瞬以毫秒计（前 2 秒每 100ms 一次），要求时钟准确：请开启自动设置时间（NTP）。
  `--start` 用的是本机本地时间，不在东八区要换算。
- 仓库根目录的 `.gitattributes` 已声明 `*.sh` / `*.plist` 用 `text eol=lf`；若是**直接拷贝**
  文件（不走 git）后报 `bad interpreter: /bin/zsh^M`，说明被转成了 CRLF：
  `sed -i '' $'s/\r$//' deploy/macos/*.sh`。

> 历史：2026-09-28 那次定时运行以退出码 `1` 结束、一个请求都没发出去——活动页在等待期间被
> 静默关掉，而当时既没探活也没恢复，脚本还会自己关闭浏览器。现在自愈已补齐（等待期间探活 +
> 丢失后重建会话），而且脚本**不再启动、也不再关闭浏览器**，从根上消掉了那条路径。
