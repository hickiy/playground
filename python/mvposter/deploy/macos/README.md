# macOS 定时运行（每天 03:00 一轮完整任务）

用 LaunchAgent 每天 **03:00** 拉起 `python -m src.job`：**检索 → 挑选 → 下载 → 发布到视频号**。
`caffeinate` 保证这整段（含上传转码、等页面反应）机器不睡，`pmset` 到点把机器唤醒
（launchd 自己不会唤醒睡眠中的 Mac）。

做法与相邻项目 [`jd_car_maintain_grab`](../../../jd_car_maintain_grab/deploy/macos)
一致：`install.sh` 渲染 plist → `launchctl bootstrap` 进用户会话。

**前提（只能由人保证）**：**不合盖**（合盖必然进入无法唤醒的睡眠）、**持续接电源**
（`caffeinate -s` 的断言只在 AC 下有效）、**常驻 Chrome 里的视频号助手仍是登录状态**、
**那只 Chrome 自己打得开 youtube.com 且真的登录过 YouTube**（见下面「下载为什么会被拦」）。
`run_job.sh` 只连接常驻实例：连不上就记日志并以退出码 `1` 结束，不会自己拉起浏览器。

## 下载为什么会被拦（重要）

yt-dlp 判断「YouTube 登录了没」看的是 `LOGIN_INFO` 这个 cookie
（`yt_dlp/extractor/youtube/_base.py`：*LOGIN_INFO is cleared and should exist if logged in*）。
只有 Google 的 SSO cookie（`SID` / `HSID` / `SSID` / `SAPISID` …）而**没有** `LOGIN_INFO` 时，
YouTube 会回 `Sign in to confirm you're not a bot`，下载 100% 失败。

**实测（2026-10-15）就是这种情况**：那只常驻 Chrome 自己打不开 `youtube.com`
（没走代理），所以从来没有真正登录进 YouTube，但 `SID` 之类的 SSO cookie 是有的——
光看「有没有 SID」会误判成已登录。`src/job.py` 的只读预检 `_check_youtube_login()` 查的是
`LOGIN_INFO`，`--dry-run` 会把它打印出来：

```
预检警告：常驻 Chrome 里没有 YouTube 的 LOGIN_INFO cookie，yt-dlp 会当成未登录，
下载大概率被拦成「Sign in to confirm you're not a bot」。
```

**补救**：让那只 Chrome 能正常访问 youtube.com（浏览器代理由 browserhost 决定，
本项目不碰），然后在登录状态下访问一次 `youtube.com`，让 `LOGIN_INFO` 落地。


## 时间线

| 时刻 | 动作 |
|---|---|
| 02:55 | `pmset` 唤醒 Mac |
| 03:00 | LaunchAgent 跑 `run_job.sh`：`caffeinate` 持锁 → 探活 CDP → 语义生成关键词检索候选（跳过库里已有的） |
| 03:00+ | 按播放速度取前 `--count` 条（默认 1）→ 借 cookies 下载到 `movies/<当天日期>/` |
| 03:01+ | 新开自己的页签把视频填进视频号助手 → 读回核对字段 → 点「发表」→ 等成功信号 |
| 结束 | 断开 CDP 连接（浏览器继续常驻）；结果写进 `logs/mvposter_YYYY-MM-DD.log` |

`--count > 1` 时两条之间按 `--interval`（默认 1800s）**抖动间隔**，避免固定节奏撞风控。

## 安装

```bash
cd /path/to/mvposter
./deploy/macos/install.sh                        # 渲染 plist、加载 LaunchAgent

# 先启动常驻 Chrome 并在窗口里确认视频号助手是登录状态
cd ../browserhost && python main.py start

# 定时唤醒（需要 sudo，install.sh 不会替你执行）
sudo pmset repeat wakeorpoweron MTWRFSU 02:55:00
pmset -g sched                                   # 确认时间表
```

想改启动时刻：改 `com.mvposter.job.plist` 里的 `StartCalendarInterval`，再跑一次 `install.sh`。

## 两个开关（不改代码就能调）

| 开关 | 默认 | 说明 |
|---|---|---|
| `MVPOSTER_COUNT` | `1` | 每轮处理几条。风控风险随条数上升，建议先跑 1 |
| `MVPOSTER_PUBLISH_MODE` | `--publish` | `--publish` = 填完表核对无误即自动提交；`--no-publish` = 只填表 + 截图，停在「发表」按钮前等人点 |

改默认值有两种方式：

1. 直接改 `run_job.sh` 里 `COUNT` / `PUBLISH_MODE` 的默认值（最简单）；
2. 给 plist 加环境变量，再跑一次 `install.sh`：

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>MVPOSTER_COUNT</key>
    <string>1</string>
    <key>MVPOSTER_PUBLISH_MODE</key>
    <string>--no-publish</string>
</dict>
```

> **想先稳妥一点**：把 `MVPOSTER_PUBLISH_MODE` 设成 `--no-publish`，凌晨那轮会把表单填好、
> 截图存进 `logs/publish_form_*.png`，你早上核对完在浏览器里点「发表」，再回写状态：
> `python -m src.cli mark <video_id> published`。

## 验证

```bash
pmset -g sched                                   # 唤醒时间表
launchctl print gui/$(id -u)/com.mvposter.job    # LaunchAgent 状态
pmset -g assertions                              # 运行时应看到 caffeinate 持有 PreventUserIdleSystemSleep
tail -f logs/launchd.out.log                     # launchd 捕获的终端输出（含 run_job.sh 的启动行）
tail -f logs/mvposter_$(date +%F).log            # 本程序的执行日志（检索/下载/发布全过程）
python -m src.cli list --status all              # 库里的状态机（found→picked→downloaded→published）

# 常驻实例（在 browserhost 项目目录里执行）
python main.py start                             # 幂等：已在跑就复用，不健康会自动重启
tail -f ~/.browserhost/logs/browserhost_$(date +%F).log
```

**试跑**（`--dry-run` 只检索 + 挑选 + 登录态预检，不下载、不发布，随便跑）：

```bash
./deploy/macos/run_job.sh --dry-run
launchctl kickstart -k gui/$(id -u)/com.mvposter.job     # 按定时任务的方式完整跑一轮（会真的下载+发布）
```

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 这一轮全部成功（含 `--no-publish` 的「填好表等人工」）；或「今天没有新的合格候选」——这是正常状态，不算失败 |
| `1` | 有环节失败：连不上 CDP、下载失败、发布出错、`need_login`（登录态失效） |
| `130` | 被 Ctrl+C 中断 |

## 卸载

```bash
launchctl bootout gui/$(id -u)/com.mvposter.job
rm ~/Library/LaunchAgents/com.mvposter.job.plist
sudo pmset schedule cancelall
```

## 注意

- **必须装成 LaunchAgent（用户会话 `gui/<uid>`）**，不能用 LaunchDaemon：任务要连接用户
  启动的真实 Chrome（登录态在那个 profile 里），还要持有 `caffeinate`。请保持用户处于
  登录状态、**不要注销**。
- **锁屏可以**（不影响 Chrome、CDP 连接与 Python 计时）；**合盖会睡**，见开头的前提。
- **保持浏览器常驻**：定时任务只连接它，窗口关掉没问题（Chrome 进程留在后台）。但
  **别退出 Chrome 进程**，**机器重启后也要重新 `python main.py start`**：这些情况下调试
  端口会消失，本轮会以退出码 `1` 结束。
- **登录态会过期**：日志出现 `need_login` 时本轮不发任何东西（也**不会**动状态机），
  去那只 Chrome 里重新扫码，下一轮自动恢复。
- **同一时间别重复启动**：`launchctl kickstart` 与手动 `run_job.sh` 并发会争用同一个
  Chrome 与同一个调试端口，等于双倍操作，更容易触发风控。
- **无人值守意味着一觉醒来可能已经发出去了**：默认 `--publish` 是「填完即提交」。
  想留一道人工闸门就用 `--no-publish`。
- 素材是别人拍的：默认在描述里加一行 `来源：YouTube @频道`；不想要就加 `--no-source`。
  **是否搬运、是否使用这类素材由你决定**。
