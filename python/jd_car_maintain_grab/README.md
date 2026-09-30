# 京东「免费小保养」抢购 (jd_car_maintain_grab)

基于 **Playwright + CDP** 的京东「免费小保养」每日 10 点自动抢购工具。

流程：10:00:00 放库存，脚本等到该时刻就在活动页内**直接调用兑换接口**
`bff_rights_points_exchange` 并重试：**头 2 秒每 100ms 打一次**（`BURST_MS` /
`BURST_INTERVAL_MS`），之后回落到每 1000ms 一次，合计 `API_ATTEMPTS`（默认 40）次。
份额基本在开抢那一瞬被抢完，所以时间分辨率比总次数更重要；长时间高频则会被风控限流。
**不提前开抢**：页面数据给出的可兑换时段是 `10:00:00-23:50:00` 与
`00:00:00-09:25:00`，09:25–10:00 属关闭时段，提前发请求只会拿到 `1714001` 而白烧机会。
接口所需的业务参数取自页面数据 `window.__react_data__`，风控参数取自页面原生的
`window.getJdEid()` / `window.getJsToken()`，因此不需要模拟点击，也不需要在每轮之间
刷新整页。

登录需在**真实 Chrome** 中手动完成（受信任会话），页面才会返回该商品完整的
兑换参数；脚本通过 CDP 连接该 Chrome 执行抢购。

## 起步（两步）

```bash
# Windows 用 py，macOS/Linux 用 python3

# 1) 只做一次：运行 launch_browser.py 打开浏览器窗口并登录，之后保持它常驻运行
python launch_browser.py

# 2) 定时执行（Windows 任务计划程序 / cron / macOS LaunchAgent 都只跑这一条）
python -m src.grab
```

- **第 1 步**：`launch_browser.py` 启动带调试端口的 Chrome、打开活动页并检测登录态——
  未登录就在窗口里引导你登录，已登录直接结束。之后这个浏览器**保持常驻**即可：窗口
  随手关掉也没关系（Chrome 进程留在后台、调试端口一直可用），只有退出 Chrome 进程或
  重启机器后才需要再跑一次。
- **第 2 步**：`grab.py` 只**连接**那个常驻浏览器完成抢购：不启动浏览器、跑完也不关它，
  因此可以放心交给定时任务。连不上调试端口（浏览器没在运行）会记日志并以退出码 `1`
  结束，并在日志里提示先跑 `python launch_browser.py`。

安装见下面的[安装](#安装)，详细参数见[使用](#使用)。

## 为什么不再模拟点击

实测按钮模拟在这套 SSR + 弹窗结构下很不稳定：`locator.click()` 会超时，
`click(force=True)` 虽然报告点击成功，却一个请求都没发出。直调接口只要求页面
已加载，绕开了元素可见性、遮罩遮挡与弹窗渲染时机等全部不确定因素。

接口本身也做过验证：不带 `h5st` 签名同样能通过校验，但 body 必须携带
`jsToken`，否则返回 `F30001`（操作频率过快）；参数正确时返回业务码，
如 `1711000` 成功、`1711001` 当前参与人数过多。

## 兑换参数什么时候能取到

启动日志会打印 `目标商品: ...`。取参数的时机与条件：

- **不在首屏 HTML 里**。实测服务端渲染的 HTML 中 `activityWareId` / `exchangeScore`
  出现 0 次；这些参数是页面打开后**异步拉取活动数据（floor）**才写进
  `window.__react_data__` 的，所以脚本会轮询等到能读到为止（超时 `PARAM_WAIT_MS`，
  默认 30s）。
- **与库存状态无关**。商品已抢完（`skuStatus=5`）时参数照样完整可读，因此不必
  等到 10:00 补库存——脚本在到点前就读到并缓存，到点直接发请求。库存补充后
  同样可读，两者只是 `skuStatus` 字段不同。
- **需要登录态**。打开页面后会先确认不在登录页，再读参数。
- 到点前若没读到，到点后会再试一次；仍然读不到则记日志并以退出码 `1` 结束
  （不再回退到刷新点击）。

各商品的参数与下单方式（`skuStatus`：`0` 可兑换、`5` 已抢完、`8` 即将开抢）：

| 商品 | skuId | 积分 | activityWareId | activityId | 下单方式 |
|---|---|---|---|---|---|
| **免费小保养 ¥399** | `100228358274` | 9 | 1896901 | 1421003 | **调兑换接口**（`btnRedirectUrl` 为空）|
| 京东养车1L保养机油 ¥99 | `100240903791` | 1 | 2097606 | 1582003 | 跳转 `m-sep.jd.com/Settlement` 提交订单 |
| 汽车保养5折券 ¥399 | `1409644046` | 3 | 1897301 | 1425101 | 未核实 |

> ⚠️ **只有 `btnRedirectUrl` 为空的商品才走兑换接口**。跳转型商品（如 1L 机油）的
> 下单流程是「用 `bff_rights_points` 拿 `sourceTicket` → 跳转结算页提交订单」，
> 直调兑换接口必然失败。脚本检测到这种商品会直接打印警告并以退出码 `1` 结束，
> 不会白跑 N 次。

> 抢购目标由 `config.SKU_ID` 决定，当前是 **`100228358274`（免费小保养 ¥399 / 9 积分）**；
> `ACTIVITY_URL` 里的 `skuId` 由它拼接，两者始终一致（页面按 URL 的 `skuId` 决定默认
> 选中哪张商品卡）。想换商品只改 `SKU_ID` 一处即可。

## 接口返回码（实测）

| code | 含义 | 处理 |
|---|---|---|
| `1711000` | 兑换成功 | 结束，退出码 `0` |
| `1711001` | 当前参与人数过多 | 继续重试 |
| `1714001` | 商品当前不可兑换（未开抢 / 已抢完 / 不在兑换时段）| 继续重试 |
| `F30001` | 您操作频率过快（风控限流） | 退避 `API_COOLDOWN_MS` 后重试 |
| `1711002` | 参数错误 | 参数拼装有问题，检查 `src/api.py` |

## 目录结构

```text
jd_car_maintain_grab/
├── pyproject.toml            # 项目元数据、依赖与命令入口
├── requirements.txt          # 依赖列表（快速参考）
├── README.md
├── .gitignore
├── deploy/
│   └── macos/                # macOS 定时运行（LaunchAgent + caffeinate 防睡眠）
├── launch_browser.py         # 手动启动/检查常驻 Chrome（CDP），只需开一次
└── src/
    ├── __init__.py
    ├── config.py             # URL、兑换接口等常量
    ├── browser.py            # 连接 Chrome、登录检测、日志
    ├── api.py                # 页面内直调兑换接口
    └── grab.py               # 定时任务入口：连接常驻 Chrome + 抢购
```

运行时会在项目根目录生成 `logs/`（按天分的执行日志）。

## 安装

本项目使用 [uv](https://docs.astral.sh/uv/) 进行依赖管理。若未安装 uv，请先安装：

```bash
# Windows（winget）
winget install astral-sh.uv
# 或 macOS / Linux
brew install astral-sh/uv/uv
```

在项目根目录执行：

```bash
# 创建虚拟环境 .venv 并安装项目依赖（含 playwright）
uv sync
```

> 本项目通过 CDP 连接**真实 Chrome**（由 `python launch_browser.py` 手动启动），无需
> 额外安装 Playwright 自带的浏览器。若你以后需要让 Playwright 自己启动浏览器（如编写
> 自动化测试），再执行 `uv run playwright install chromium`。

## 使用

步骤见上面的[起步（两步）](#起步两步)，这里把细节展开。

**第 1 步 · `python launch_browser.py`（只需一次）**：启动带调试端口的 Chrome、打开
活动页并**检测登录态**——已登录就直接结束；未登录则在窗口里引导你完成京东登录（最多等
`--login-timeout` 秒，默认 `300`）。登录态与页面都保存在 `jd_cdp_profile/`，之后无需
重复登录。启动后让它常驻即可（窗口可以关，进程留在后台）。

**第 2 步 · 定时执行 `python -m src.grab`**：定时任务只需要这一条命令，建议落在放库存
前几分钟（如 09:55）——脚本会先读参数、等待期间每 20s 探活，到 `10:00:00` 开抢。

```bash
# Windows 任务计划程序（以管理员身份运行；起始位置/路径换成你自己的项目目录）
schtasks /Create /TN "jd-grab" /SC DAILY /ST 09:55 /TR ^
  "cmd /c cd /d D:\code\jd_car_maintain_grab && .venv\Scripts\python.exe -m src.grab" /F

# Linux/macOS cron（每天 09:55）
55 9 * * * cd /path/to/jd_car_maintain_grab && .venv/bin/python -m src.grab
```

macOS 也可以直接用本仓库的 LaunchAgent（带 `caffeinate` 防睡眠 + `pmset` 定时唤醒）：
见 [`deploy/macos/README.md`](deploy/macos/README.md)。

> 抢购脚本**不会**启动浏览器，也**不会**在结束时把它关掉：连不上调试端口就记日志
> 并以退出码 `1` 结束（日志里会提示先跑 `python launch_browser.py`）。想单独检查
> 端口是否可用：`python launch_browser.py --check`。
>
> 窗口关掉后浏览器里一个页面也没有，而兑换请求必须跑在页面里（要读页面数据
> `window.__react_data__`、调 `window.getJsToken()`），所以这时 grab 会**临时新建
> 一个页面**（屏幕上会短暂出现一个窗口），抢完自动关掉，浏览器回到「无窗口、
> 后台进程仍在」的状态——不重启浏览器、不需要重新登录。

### 能不能自己打开浏览器、手动进活动页，再让 grab 连上去？

可以，但那个浏览器必须是**带调试端口启动**的实例：Chrome 没有「事后开启 CDP」的
开关（不是设置项、也不是 about:flags）。而且从 Chrome 136 起，
`--remote-debugging-port` 要求 `--user-data-dir` 指向**非默认**目录——Chrome 153
二进制里的原文：`DevTools remote debugging requires a non-default data directory.
Specify this using --user-data-dir`。所以你日常那个默认 profile 即使加了参数，
调试端口也不会监听。

可行的做法：

1. **就用项目自带的目录**（推荐）：`python launch_browser.py`，登录一次长期复用，
   以后随手 `python -m src.grab`。手动进活动页也支持：grab 会**优先复用已打开的活动页**
   （按 URL 前缀匹配），不会另开窗口。
2. **把自己浏览器的 profile 复制一份**（想带上书签/插件/登录态）：先完全退出 Chrome
   （含托盘后台进程，否则复制的 Cookies 可能不一致），再复制到别的目录并用 `--profile`
   启动：

   ```bash
   # Windows：复制到非默认目录（排除缓存类目录，快很多）
   robocopy "%LOCALAPPDATA%\Google\Chrome\User Data" "D:\chrome-cdp" /E ^
     /XD "Default\Cache" "Default\Code Cache" ShaderCache GrShaderCache Crashpad
   python launch_browser.py --profile "D:\chrome-cdp"
   ```
3. **自己手动启动**也行，参数照 `launch_browser.py` 的来：

   ```bash
   chrome.exe --remote-debugging-port=9222 --user-data-dir="D:\chrome-cdp" <活动页>
   python -m src.grab --port 9222
   ```

> ⚠️ 调试端口只监听本机回环（不会暴露到局域网），但**本机任何进程都能通过 CDP 读到
> 该浏览器的全部数据**（cookie、页面内容）。所以别把日常主 profile 长期跑在调试端口上
> ——这也是 Chrome 从 136 起禁止在默认 profile 上开调试端口的原因。

### 抢购参数

```bash
# 默认 10:00:00 放库存、到点开抢（前 2 秒每 100ms 一次）：页面内直调兑换接口并重试
python -m src.grab

# 指定放库存时间
python -m src.grab --start 10:00:00

# 立即开始（用于验证接口直调与登录态）
python -m src.grab --test
```

- `--start`：放库存时间 `HH:MM:SS`，默认 `10:00:00`。**到点即开抢，不再提前**（提前量只会
  撞在 09:25–10:00 的关闭时段上，白拿 `1714001`）。在开抢时刻前启动会等到该时刻；
  若启动时**已经过了**它，则不再等待、立即开始（便于盘中补跑或试跑）。
- `--test`：立即开始，不等待设定时间。
- `--port`：要连接的 Chrome 调试端口，默认 `9222`（需与 `launch_browser.py` 一致）。
- `--minimize-page`：窗口关着时把新建的临时页面所在窗口**自动最小化**（不遮挡桌面、
  不抢焦点），默认关闭。实测（Windows，最小化 11 分钟）页面一直
  `visibilityState=visible`、`wasDiscarded=false`，`evaluate` 与探活全部正常。
- 启动浏览器自己的参数在 `launch_browser.py` 上：`--port` / `--profile`（默认
  `./jd_cdp_profile`，登录态就保存在这里）/ `--url`（默认活动页）/ `--chrome`
  （可执行文件路径，默认自动查找）/ `--check`（只检查调试端口）/
  `--login-timeout`（未登录时等待登录的秒数，默认 `300`，`0` = 只检测不等待）。
- 开抢时刻起按 `API_ATTEMPTS`（默认 `40`）次调用兑换接口：开抢后 `BURST_MS`
  （默认 `2000ms`）内每 `BURST_INTERVAL_MS`（默认 `100ms`）一次，之后每
  `API_INTERVAL_MS`（默认 `1000ms`）一次；命中成功码 `1711000` 即结束，否则跑满次数后退出。
  若返回 `F30001`（操作频率过快），会额外等 `API_COOLDOWN_MS`（默认 `3000ms`）再重试。
- 抢购目标由 `config.SKU_ID` 决定（`ACTIVITY_URL` 的 `skuId` 由它拼接）。
  启动日志会打印解析出的**商品名与所需积分**，可据此核对是不是想抢的那款。
- 以上常量都在 `src/grab.py` 顶部。

### 执行日志

日志同时输出到终端和 `logs/jd_grab_YYYY-MM-DD.log`（按天分文件、追加写入并逐行 flush），
适合配合 Windows 任务计划程序 / cron 无人值守运行：

- 每次运行记录启动时间、参数、放库存/开抢时刻、退出码；每次接口调用记录返回的业务码与提示。
- **登录态有专门日志**，便于事后区分「登录态失效」与「库存 / 风控导致的没抢到」：
  - 正常：`登录态正常：未出现登录页`。
  - 被跳到登录页：`检测到未登录：页面已跳到登录页（...）（第 N/M 次等待）`。
  - 一直没登录成功：`登录未完成：M 次等待后仍停留在登录页（...），本次未执行抢购`
    → 退出码 `1`。无人值守（任务计划程序 / cron）下读不到终端输入，会记录
    `无法读取输入（...），跳过登录等待` 后按上述流程结束。
- **页面/调试连接丢失会自动恢复**，不会让整轮抢购报废：等待开抢期间每 20s 探活一次
  （`KEEPALIVE_MS`），丢失就重连调试端口并重开活动页（端口也不通就说明浏览器进程被
  整个退出了，脚本不会自己启动浏览器，这轮只能以退出码 `1` 结束），已读到的兑换参数
  缓存复用；到点后的重试循环里页面丢失同样恢复后接着打，恢复成功还会重新给一个密集
  窗口。日志表现：`探活失败：活动页/调试连接已丢失` → `会话已恢复`。
- 异常（如 CDP 连接失败）也会写入日志，便于事后排查。
- 退出码：`0` 兑换成功；`1` 连不上调试端口（浏览器没在运行）/ 打开页面失败 /
  读不到兑换参数 / 登录失效 / 接口调用全部未成功 / 异常终止；`130` 被 Ctrl+C 中断。
- 程序退出（包括关闭终端窗口）时**只断开调试连接**，浏览器继续在后台运行：它由
  `launch_browser.py` 手动启动、跨定时任务长期常驻，登录态保存在 `jd_cdp_profile/`，
  下次直接运行 `python -m src.grab` 即可，无需重新登录。窗口处于关闭状态时日志里会
  多两行：`浏览器里没有可用页面（窗口已关闭）：新建一个标签页` 与
  `已关闭本次抢购新建的页面（Chrome 进程继续在后台运行）`——这是正常的「用完还原」。

> **无人值守注意**：定时任务只需在到点前跑一次 `python -m src.grab`（例如 09:55）。
> 前提是浏览器已在运行：先执行一次 `python launch_browser.py`，之后让它常驻即可
> （窗口可以关，Chrome 进程会留在后台；只有退出 Chrome 进程或重启机器后才需要重开）。
> 脚本自己不会启动浏览器，连不上调试端口就以退出码 `1` 结束并在日志里说明原因。
>
> macOS 上的定时运行（LaunchAgent + `caffeinate` 防睡眠 + `pmset` 定时唤醒）见
> [`deploy/macos/README.md`](deploy/macos/README.md)。

## 注意事项

- 本项目仅用于**你自己的账号**与合法用途。自动化抢购涉及平台规则，请自行评估风险。
- **浏览器窗口可以放心关**（Chrome 进程会留在后台，调试端口仍可用）：grab 此时会
  临时新建一个页面（屏幕上会短暂出现一个窗口）并在跑完后自动关掉；若窗口还开着，
  被关掉的页面也会被探活发现并自动重开。但**别退出 Chrome 进程**（macOS 的 Cmd+Q、
  任务管理器里结束 `chrome.exe`）：调试端口随之消失，而脚本不会自己启动浏览器，
  本轮会以退出码 `1` 结束——重新 `python launch_browser.py` 即可恢复。
- 定时任务正处在 09:50–10:00 的等待期时，**尽量别关那个活动页**：会被自动重开，
  但重开要几秒，可能错过开抢那一瞬（窗口本来就关着的除外：那是预期状态）。
- **同一时间别重复启动**（例如 `--test` 与定时任务同时跑）：两次运行会复用同一个
  Chrome 与调试端口，变成双倍发请求，更容易被风控限流（`F30001`）。
- 若活动页改版导致读不到兑换参数，请检查 `src/api.py` 中从
  `window.__react_data__` 取字段的逻辑。
- 抢购成功与否受网络、库存与平台风控影响，脚本不保证一定成功。