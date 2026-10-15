# 京东「免费小保养」抢购 (jd_car_maintain_grab)

基于 **Playwright + CDP** 的京东「免费小保养」每日 10 点自动抢购工具。

**怎么抢**：10:00:00 放库存，到点就在活动页内**直接调用兑换接口** `bff_rights_points_exchange`，
头 2 秒每 100ms 打一次（`BURST_MS` / `BURST_INTERVAL_MS`），之后回落到每 1000ms 一次，合计
`API_ATTEMPTS`（默认 40）次——份额在开抢那一瞬就被抢完，时间分辨率比总次数更重要；长时间高频
会被风控限流（`F30001`）。**不提前开抢**：可兑换时段是 `10:00:00-23:50:00` 与
`00:00:00-09:25:00`，09:25–10:00 提前发请求只会白烧机会。

**为什么直调接口而不是模拟点击**：实测 `locator.click()` 在这套 SSR + 弹窗结构下会超时，
`click(force=True)` 报告成功却一个请求都没发出。直调接口只要求页面已加载，绕开了元素可见性、
遮罩遮挡与弹窗时机。业务参数取自页面数据 `window.__react_data__`，风控参数取自页面原生的
`window.getJdEid()` / `window.getJsToken()`，所以也不需要每轮刷新整页。

登录必须在**真实 Chrome** 里手动完成（受信任会话），页面才会返回完整的兑换参数。

> 下文 `.venv/bin/` 在 Windows 上是 `.venv\Scripts\`。

## 起步（两步）

浏览器不由本项目启动：CDP 宿主是独立项目 [`browserhost`](../browserhost)，它负责启动一个
真实 Chrome、持久化登录态，并让多个任务共用同一个实例（见下节）。

```bash
# 1) 只做一次：启动常驻 Chrome（幂等），并在它的窗口里完成京东登录
cd ../browserhost && python main.py start

# 2) 之后定时执行（Windows 任务计划程序 / cron / macOS LaunchAgent 都只跑这一条）
python -m src.grab
```

第 2 步建议落在放库存前几分钟（如 09:55）：脚本会先读参数、等待期间每 20s 探活，到
`10:00:00` 开抢。它**不启动也不关闭浏览器**，连不上调试端口就记日志并以退出码 `1` 结束。

```bash
# Windows 任务计划程序（以管理员身份运行；路径换成你自己的项目目录）
schtasks /Create /TN "jd-grab" /SC DAILY /ST 09:55 /TR ^
  "cmd /c cd /d D:\code\jd_car_maintain_grab && .venv\Scripts\python.exe -m src.grab" /F

# Linux/macOS cron（每天 09:55）
55 9 * * * cd /path/to/jd_car_maintain_grab && .venv/bin/python -m src.grab
```

macOS 推荐用本仓库的 LaunchAgent（`caffeinate` 防睡 + `pmset` 定时唤醒）：
见 [`deploy/macos/README.md`](deploy/macos/README.md)。

## 常驻浏览器：browserhost

本项目**只连接**浏览器：启动/关闭 Chrome 与 profile（登录态）都归独立项目
[`browserhost`](../browserhost)，它只有三个命令：

```bash
cd ../browserhost
python main.py start      # 启动（幂等：已在跑且健康就复用；不健康会自动重启）
python main.py stop       # 优雅关闭
python main.py restart    # 先关再启动
```

- **调试端口 `9222`，登录态在 `~/.browserhost/profile`**（用户主目录下，不落进仓库）。
- **契约**：本项目只连 `http://localhost:9222`、只操作自己打开的标签页；不启动也不
  关闭浏览器，不碰 profile。共享/隔离的边界见
  [`browserhost/README.md`](../browserhost/README.md)。
- 窗口随手关掉没问题（macOS 上 Chrome 进程会留在后台、端口继续可用）；**Windows 上关掉
  最后一个标签页会让 Chrome 退出**，这轮抢购就会以退出码 `1` 结束，重新启动常驻实例即可
  （本项目不会自己拉起浏览器）。

## 抢购参数

```bash
python -m src.grab                 # 等到 10:00:00 开抢
python -m src.grab --start 10:00:00   # 指定放库存时间
python -m src.grab --test          # 立即开始（用于验证接口直调与登录态）
```

| 参数 | 说明 |
|---|---|
| `--start` | 放库存时间 `HH:MM:SS`，默认 `10:00:00`。到点即开抢、不提前；若启动时已过该时刻则不再等待、立即开始 |
| `--test` | 立即开始，不等待设定时间 |
| `--port` | Chrome 调试端口，默认 `9222`（与 browserhost 实例一致） |
| `--minimize-page` | 窗口关着时把新建的临时页面窗口最小化（不遮挡桌面、不抢焦点） |

开抢后共 `API_ATTEMPTS`（40）次调用：`BURST_MS`（2000ms）内每 `BURST_INTERVAL_MS`（100ms）
一次，之后每 `API_INTERVAL_MS`（1000ms）一次；命中 `1711000` 即结束，返回 `F30001` 时额外
退避 `API_COOLDOWN_MS`（3000ms）。常量都在 `src/grab.py` 顶部。

## 兑换参数与商品

启动日志会打印 `目标商品: ...`。参数是页面打开后**异步拉取活动数据（floor）**才写进
`window.__react_data__` 的（首屏 HTML 里没有），所以脚本轮询等到能读到为止（`PARAM_WAIT_MS`，
默认 30s）。它与库存状态无关：已抢完（`skuStatus=5`）时参数照样完整可读，因此不必等到
补库存，到点前读到就缓存下来。

| 商品 | skuId | 积分 | activityWareId | activityId | 下单方式 |
|---|---|---|---|---|---|
| **免费小保养 ¥399** | `100228358274` | 9 | 1896901 | 1421003 | **调兑换接口**（`btnRedirectUrl` 为空）|
| 京东养车1L保养机油 ¥99 | `100240903791` | 1 | 2097606 | 1582003 | 跳转 `m-sep.jd.com/Settlement` 提交订单 |
| 汽车保养5折券 ¥399 | `1409644046` | 3 | 1897301 | 1425101 | 未核实 |

> ⚠️ **只有 `btnRedirectUrl` 为空的商品才走兑换接口**。跳转型商品（如 1L 机油）的下单流程是
> 「用 `bff_rights_points` 拿 `sourceTicket` → 跳转结算页提交订单」，直调兑换接口必然失败；
> 脚本检测到会直接告警并以退出码 `1` 结束，不会白跑 N 次。抢购目标只由 `config.SKU_ID` 决定
> （`ACTIVITY_URL` 的 `skuId` 由它拼接），换商品只改这一处。

### 接口返回码（实测）

| code | 含义 | 处理 |
|---|---|---|
| `1711000` | 兑换成功 | 结束，退出码 `0` |
| `1711001` | 当前参与人数过多 | 继续重试 |
| `1714001` | 商品当前不可兑换（未开抢 / 已抢完 / 不在兑换时段）| 继续重试 |
| `F30001` | 您操作频率过快（风控限流） | 退避 `API_COOLDOWN_MS` 后重试 |
| `1711002` | 参数错误 | 参数拼装有问题，检查 `src/api.py` |

## 日志与自愈

日志同时输出到终端和 `logs/jd_grab_YYYY-MM-DD.log`（按天、追加、逐行 flush）。

- **登录态有专门日志**，便于区分「登录失效」与「库存 / 风控导致的没抢到」：
  `登录态正常：未出现登录页` / `检测到未登录：页面已跳到登录页...` /
  `登录未完成：...本次未执行抢购`（退出码 `1`）。无人值守时读不到终端输入，会记
  `无法读取输入（...），跳过登录等待` 后按上述流程结束。
- **页面 / 调试连接丢失会自动恢复**，不会让整轮抢购报废：等待期间每 20s 探活
  （`KEEPALIVE_MS`），丢失就重连调试端口并重开活动页，已读到的兑换参数缓存复用；到点后的
  重试循环里同样恢复后接着打。日志表现：`探活失败：活动页/调试连接已丢失` → `会话已恢复`。
  端口也不通说明浏览器进程整个退出了——脚本不会自己启动它，这轮以退出码 `1` 结束
  （在 browserhost 里用 `python main.py start` 恢复）。
- 退出码：`0` 兑换成功；`1` 连不上调试端口 / 打开页面失败 / 读不到参数 / 登录失效 /
  接口调用全部未成功 / 异常终止；`130` 被 Ctrl+C 中断。程序退出时**只断开调试连接**，
  浏览器继续在后台运行。

## 安装

```bash
winget install astral-sh.uv     # Windows；macOS 用 brew install uv
uv sync                         # 建 .venv 并装依赖（playwright）

cd ../browserhost && uv sync    # 常驻 Chrome 的 CDP 宿主：单独装一次
```

本项目通过 CDP 连接**系统里的真实 Chrome**，无需 `playwright install`。

## 目录结构

```text
jd_car_maintain_grab/
├── pyproject.toml            # 项目元数据、依赖与命令入口
├── requirements.txt          # 依赖速查（正式安装用 uv sync）
├── README.md / .gitignore
├── deploy/macos/             # macOS 定时运行（LaunchAgent + caffeinate + pmset）
└── src/
    ├── config.py             # URL、兑换接口等常量
    ├── browser.py            # CDP 会话（只连接常驻实例：探活/自愈/登录页判定）+ 日志
    ├── api.py                # 页面内直调兑换接口
    └── grab.py               # 定时任务入口：连接常驻 Chrome + 抢购
```

运行时生成 `logs/`（按天执行日志）。

## 注意事项

- 仅用于**你自己的账号**与合法用途；抢购成功与否受网络、库存与平台风控影响，不保证成功。
- **浏览器窗口可以随手关**（Chrome 进程会留在后台、调试端口仍可用）：grab 此时会临时新建
  一个页面（屏幕上短暂出现一个窗口）并在跑完后自动关掉。但**别退出 Chrome 进程**
  （Cmd+Q / 结束 `chrome.exe`）：端口随之消失，本轮以退出码 `1` 结束，需在 browserhost 里
  `python main.py start` 恢复。
- 等待期内**尽量别关那个活动页**：会被自动重开，但重开要几秒，可能错过开抢那一瞬
  （窗口本来就关着的除外：那是预期状态）。
- **同一时间别重复启动**（例如 `--test` 与定时任务同时跑）：两次运行会复用同一个实例，
  变成双倍发请求，更容易撞 `F30001` 限流。
- 活动页改版导致读不到兑换参数时，检查 `src/api.py` 里从 `window.__react_data__`
  取字段的逻辑。
