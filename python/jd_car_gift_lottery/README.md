# 京东「免费小保养」抢购 (jd_car_gift_lottery)

基于 **Playwright + CDP** 的京东「免费小保养」每日 10 点自动抢购工具。

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
    └── grab.py               # 抢购流程（CLI: jd-grab）
```

## 安装

```bash
pip install -e .
playwright install chromium
```

## 使用

```bash
# 1. 启动带调试端口的真实 Chrome，并在里面手动登录京东
py launch_chrome.py --port 9222

# 2. 连接该受信任会话执行抢购（默认连接 http://localhost:9222）
jd-grab
```

> 第 1 步打开的 Chrome 会停在京东登录页；请在其中手动完成登录，确认能看到活动页「立即免费兑换」按钮后再执行第 2 步。

### 抢购参数

```bash
# 每天 09:59 开始切换商品刷新按钮，10:00 补充库存后自动点击兑换并确认
jd-grab

# 指定开始时间 / 时长 / CDP 地址
jd-grab --start 09:59:00 --duration 600 --cdp http://localhost:9222

# 立即开始（用于测试按钮定位与点击确认流程）
jd-grab --test
```

- `--start`：开始时间 `HH:MM:SS`，默认 `09:59:00`。
- `--duration`：最长持续秒数，默认 `600`。
- `--cdp`：已登录的真实 Chrome 调试地址，默认 `http://localhost:9222`。
- `--test`：立即开始点击，不等待设定时间。

## 注意事项

- 本项目仅用于**你自己的账号**与合法用途。自动化抢购涉及平台规则，请自行评估风险。
- 若活动页选择器失效（页面改版），请更新 `src/jd_car_gift/config.py` 中的选择器/关键词。
- 抢购成功与否受网络、库存与平台风控影响，脚本不保证一定成功。
