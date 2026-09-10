# 京东「免费小保养」抢购 (jd_car_gift_lottery)

基于 **Playwright + CDP** 的京东「免费小保养」每日 10 点自动抢购工具。

流程：10:00:00 到点后，重复 10 轮「刷新活动页 → 点「立即免费兑换」→ 点「确认兑换」」，
10 轮跑完自动退出。刷新后若按钮不是「立即免费兑换」状态，会立刻再次刷新（不做等待）。

登录需在**真实 Chrome** 中手动完成（受信任会话），京东才会渲染「立即免费兑换」按钮；脚本通过 CDP 连接该 Chrome 执行抢购。

## 目录结构

```text
jd_car_gift_lottery/
├── pyproject.toml            # 项目元数据、依赖与命令入口
├── requirements.txt          # 依赖列表（快速参考）
├── README.md
├── .gitignore
├── launch_chrome.py          # 启动带调试端口的真实 Chrome（登录用）
└── src/
    ├── __init__.py
    ├── config.py             # URL、选择器、关键词等常量
    ├── browser.py            # CDP 连接 / 登录检测 / 日志
    └── grab.py               # 抢购流程（运行: python -m src.grab）
```

运行时会在项目根目录生成 `logs/`（执行日志）与 `grab_result.png`（结果截图）。

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

> 本项目通过 CDP 连接**真实 Chrome**（由 `launch_chrome.py` 启动），无需额外安装
> Playwright 自带的浏览器。若你以后需要让 Playwright 自己启动浏览器（如编写
> 自动化测试），再执行 `uv run playwright install chromium`。

## 使用

```bash
# 1. 启动带调试端口的真实 Chrome，并在里面手动登录京东
#    Windows 用 py，macOS/Linux 用 python3
python launch_chrome.py --port 9222

# 2. 连接该受信任会话执行抢购（默认连接 http://localhost:9222）
python -m src.grab
```

> 第 1 步打开的 Chrome 会停在京东登录页；请在其中手动完成登录，确认能看到活动页「立即免费兑换」按钮后再执行第 2 步。

### 抢购参数

```bash
# 默认 10:00:00 到点开始：刷新页面 → 点「立即免费兑换」→ 点「确认兑换」，共 10 轮
python -m src.grab

# 指定到点时间 / CDP 地址
python -m src.grab --start 10:00:00 --cdp http://localhost:9222

# 立即开始（用于测试按钮定位与点击确认流程）
python -m src.grab --test
```

- `--start`：到点抢购时间 `HH:MM:SS`，默认 `10:00:00`。脚本需在该时刻**之前**启动；
  若启动时已过该时刻，本次不抢购、直接退出（退出码 `1`）。
- `--cdp`：已登录的真实 Chrome 调试地址，默认 `http://localhost:9222`。
- `--test`：立即开始，不等待设定时间。
- 一轮 = 刷新活动页 → 点击「立即免费兑换」→ 点击「确认兑换」，共 10 轮。
  刷新页面本身就会重置按钮与弹窗状态，因此不需要处理卡片切换与结果弹窗。
- 刷新后按钮若不是「立即免费兑换」状态（如「已抢完」），会立刻进入下一轮刷新，不做任何等待。
- 轮数由 `src/grab.py` 顶部的 `ROUNDS` 常量控制（默认 `10`）。

### 执行日志

日志同时输出到终端和 `logs/jd_grab_YYYY-MM-DD.log`（按天分文件、追加写入并逐行 flush），
适合配合 Windows 任务计划程序 / cron 无人值守运行：

- 每次运行记录启动时间、参数、目标时刻与退出码；每轮记录实际点到的按钮文案。
- 异常（如 Chrome 未启动、CDP 连接失败）也会写入日志，便于事后排查。
- 退出码：`0` 十轮流程跑完；`1` 启动时已过设定时间 / 打开页面失败 / 登录失效 / 异常终止；
  `130` 被 Ctrl+C 中断。
- 程序退出（包括关闭终端窗口）时会自动关闭所连接的 Chrome 窗口；登录态保存在
  `jd_cdp_profile/`，下次运行前重新执行 `python launch_chrome.py` 即可，无需重新登录。

> **无人值守注意**：抢购依赖预先登录好的真实 Chrome，而程序退出会自动关闭它。
> 若用任务计划程序 / cron 定时执行，请提前启动 Chrome 并让它保持运行到抢购结束
> （例如安排 09:50 执行 `python launch_chrome.py`，09:55 执行 `python -m src.grab`）。

## 注意事项

- 本项目仅用于**你自己的账号**与合法用途。自动化抢购涉及平台规则，请自行评估风险。
- 若活动页按钮文案变化（页面改版），请更新 `src/config.py` 中的关键词。
- 抢购成功与否受网络、库存与平台风控影响，脚本不保证一定成功。