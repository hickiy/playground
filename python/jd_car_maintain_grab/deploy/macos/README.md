# macOS 定时运行（持续接电源）

用 LaunchAgent 每天 09:50 拉起抢购，并用 `caffeinate` 保证「等到 10:00:00 开抢」
这段期间机器不会睡过去。前提：**Mac 持续接电源**（`caffeinate -s` 的断言只在 AC 下
有效）、已在该 Mac 上登录过京东、时区正确。

## 时间线

| 时刻 | 动作 |
|---|---|
| 09:45 | `pmset` 唤醒 Mac（launchd 自己不会唤醒睡眠中的机器） |
| 09:50 | LaunchAgent 启动 `run_grab.sh`：`caffeinate` 持锁 → 启动 Chrome 打开活动页 → 读兑换参数（之后每 20s 探活一次，页面/连接丢了就地恢复） |
| 10:00:00 | 放库存即开抢：前 2 秒每 100ms 一次，之后每 1000ms 一次 |
| ~10:00:22 | 跑满 `API_ATTEMPTS=40` 次后退出，并关闭 Chrome；`caffeinate` 释放锁 |

## 运行期自愈（页面/连接丢了也不再报废）

从 09:50 打开页面到 10:00:00 发第一个请求，中间隔着十几分钟，而这段时间活动页可能
被关掉、调试连接可能断开、Chrome 也可能整个退出——macOS 上关掉最后一个窗口时
Chrome 进程还在，外部看不出任何异常。脚本对此做了两层防护：

- **等待期间探活**（每 `KEEPALIVE_MS`=20s 一次）：发现页面/连接丢失就重连调试端口、
  重新打开活动页；调试端口也没了就重新拉起 Chrome。已读到的兑换参数会缓存复用，
  所以恢复后不用再等页面重新拉活动数据。
- **到点后的重试循环**（`grab_by_api`）：轮间等待改为 `time.sleep`（不再依赖页面），
  页面丢失时恢复会话后继续打（`MAX_RECOVERIES`=2 次），恢复成功重新给一个密集窗口。

因此日志里出现下面这些行是正常自愈，不必当成失败：

```text
探活失败：活动页/调试连接已丢失（距开抢 xxx s），尝试恢复...
尝试恢复会话（第 1 次）：重连调试端口并重新打开活动页...
会话已恢复：活动页已重新打开。
```

> **故障复盘（2026-09-28）**：当天定时运行以退出码 `1` 结束，一个请求都没发出去。
> 原因不是网络或库存，而是活动页在等待期间就消失了——`pmset -g log` 显示
> `caffeinate` 的断言在 10:00:00 才释放（说明任务确实跑到了点），Chrome 主进程
> 直到 `10:00:00.044` 才走退出流程（即脚本自己发的 `Browser.close` 生效），期间没有
> 崩溃报告、没有导航、没有内存压力杀进程，profile 的 `exit_type` 也是 `Normal`：
> 页面被静默关掉，而当时的代码既没探活也没恢复，到点第一次调用就报
> `Target page, context or browser has been closed`，紧接着 `page.wait_for_timeout`
> 又把整个循环炸掉。现已按上面的方式修复。

## 安装

```bash
cd /path/to/jd_car_maintain_grab
./deploy/macos/install.sh                       # 渲染 plist、加载 LaunchAgent

# 定时唤醒（需要 sudo，install.sh 不会替你执行）：
sudo pmset repeat wakeorpoweron MTWRFSU 09:45:00
pmset -g sched                                  # 确认时间表
```

想改启动时刻：改 `deploy/macos/com.jd.grab.plist` 里的 `StartCalendarInterval`，
再跑一次 `install.sh` 即可。

## 验证

```bash
pmset -g sched                                   # 唤醒时间表
launchctl print gui/$(id -u)/com.jd.grab         # LaunchAgent 状态
pmset -g assertions                              # 运行时应看到 caffeinate 持有 PreventUserIdleSystemSleep
tail -f logs/launchd.out.log                     # launchd 捕获的终端输出
tail -f logs/jd_grab_$(date +%F).log             # 脚本自己的执行日志（含抢购结果）
```

执行日志里可用来判断「没抢到」的原因：`登录态正常` / `检测到未登录` / `登录未完成`
（登录态失效）、`等待到 10:00:00.000 放库存开抢`（时序正常）、每条接口返回的业务码
（`1714001` = 当时不可兑换：未开抢 / 已抢完 / 不在兑换时段）；出现
`探活失败` / `页面/连接已丢失` / `会话已恢复` 说明等待期间页面被关掉过、脚本已自动
恢复（见上一节）。

## 卸载

```bash
launchctl bootout gui/$(id -u)/com.jd.grab
rm ~/Library/LaunchAgents/com.jd.grab.plist
sudo pmset schedule cancelall
```

## 注意

- **必须装在用户会话**（LaunchAgent，`gui/<uid>`），不能用 LaunchDaemon：脚本要启动
  真实 Chrome 窗口。请保持用户处于登录状态、不要注销。
- **09:50 打开的那个 Chrome 窗口请别关**。它之后十几分钟什么都不做、只在等 10:00:00，
  但一旦被关掉，脚本要到下一次探活（最长 20s）才会发现并重开，白丢一段时间；实在
  关掉了也能自愈，只是别指望它一定能赶在 10:00:00 之前恢复完。
- **同一时间不要重复启动**（`launchctl kickstart` 与手动 `run_grab.sh --test` 同时跑）：
  两次运行会复用同一个 Chrome 与调试端口，变成双倍发请求，更容易撞上 `F30001` 限流。
- **合盖（clamshell）仍会睡**。接电源 + 外接显示器可避免；要彻底禁掉需
  `sudo pmset -a disablesleep 1`（会持续发热，谨慎）。
- **时区/时钟**：`--start` 用的是本机本地时间，不在东八区要换算；开抢那一瞬以毫秒计较
  （前 2 秒每 100ms 一次），要求时钟准确，请开启自动设置时间（NTP）。
- **stdin 不是终端**：若定时执行时登录态已失效，脚本不会卡在等待输入，而是记录
  `无法读取输入（EOFError）`、重试 5 次后以退出码 `1` 结束。
- `launchctl kickstart -k gui/$(id -u)/com.jd.grab` 或 `run_grab.sh --test`
  会**真的调用兑换接口**，不确定时别乱试。
- 仓库根目录的 `.gitattributes` 已声明 `*.sh` / `*.plist` 用 `text eol=lf`，从 Windows 提交
  再在 Mac 上 checkout 也会是 LF。若是**直接拷贝**文件（不走 git）后报
  `bad interpreter: /bin/zsh^M`，说明被转成了 CRLF：
  `sed -i '' $'s/\r$//' deploy/macos/*.sh`。
