# browserhost

常驻**真实 Chrome**的 CDP 宿主。给多个爬虫/自动化任务提供：

- **一个持久化的登录态**：所有任务共享同一份 Chrome 用户数据目录（profile），
  登录一次长期复用，不必每个任务各登录一遍；
- **各用各的标签页**：每个任务只操作自己开的标签页（靠约定与自觉，本项目不代管）；
- **随时可连的调试端口**：`start` 拉起后浏览器常驻，任务只连接、不启动也不关闭它。

对外只有三个命令：`start` / `stop` / `restart`。


## 边界与契约（多任务共用时务必遵守）

| 共享的 | 隔离的 |
|---|---|
| Chrome 进程、profile（cookie / localStorage / IndexedDB / 扩展 / 设备指纹 / 代理） | 标签页（各任务自觉只动自己开的） |
| 登录态（这正是共享的目的） | 任务自己的页面状态、脚本、数据 |



## 安装

```bash
cd browserhost && uv sync          # 只装依赖（playwright）
```

## 用法

### 三个命令

```bash
python main.py start      # 启动（幂等：已在跑且健康就复用；不健康自动重启）
python main.py stop       # 优雅关闭（先请 Chrome 自己退出）
python main.py restart    # 先关再启动
```

browserhost 只维护**一个实例**（profile 目录、端口、实例名都写在 `main.py` 顶部）：
`start` 之后 Chrome 常驻，窗口随手关掉都行，调试端口一直可用。

`start` 内部做三级健康探测：`l1` 端口在监听、`l2` 能枚举标签页、`ok` CDP 往返成功。
只有 `ok` 才算真的能用——被 SIGSTOP 或从睡眠里没恢复过来的浏览器仍然会响应 HTTP，
但发不出 CDP 命令；遇到 `l1`/`l2` 会自动重启实例。端口被别的进程占用时会拒绝启动，
并打印占用者的 pid 与命令行。宿主日志在 `~/.browserhost/logs/`。

### 任务侧怎么访问（CDP）

推荐方式：用 CDP 直接连这台常驻浏览器（Playwright 为例）：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0]     # 共用这份 profile 的登录态
    page = context.new_page()         # 只动自己的标签页
    ...
    page.close()                      # 关自己的标签页；不要关浏览器
```

## 目录布局

所有运行时数据在 `~/.browserhost`（可用环境变量 `BROWSERHOST_HOME` 覆盖）：

```text
~/.browserhost/
├── profile/            Chrome --user-data-dir（登录态在这里）
├── state/<name>.json    实例状态：端口/profile/pid/是否由我们启动
├── locks/               文件锁（状态读改写）
└── logs/                宿主自身的日志
```

放在主目录根下而不是 Documents/Desktop/Downloads：后三者受 macOS TCC 保护，
无人值守时弹出的授权对话框会让任务直接卡住。

### 换 profile / 用自己浏览器的登录态

profile 目录固定在 `~/.browserhost/profile`（根目录可用环境变量 `BROWSERHOST_HOME` 换）。
要换一份登录态，就停掉实例、替换这个目录的内容。

Chrome 没有「事后开启 CDP」的开关，而且从 136 起 `--remote-debugging-port` 要求
`--user-data-dir` 指向**非默认**目录（Chrome 153 二进制原文：`DevTools remote debugging
requires a non-default data directory. Specify this using --user-data-dir`）——所以日常那个
默认 profile 即使加了参数也不会监听端口。想带上它的书签 / 插件 / 登录态，就把 profile
复制成 `~/.browserhost/profile`（复制前完全退出 Chrome；跨系统复制带不走登录态，
见下面「故障排查」）。

⚠️ 调试端口只监听本机回环，但**本机任何进程都能通过 CDP 读到该浏览器的全部数据**
（cookie、页面内容）——别把日常主 profile 长期挂在调试端口上，这也正是 Chrome 从 136 起
禁止在默认 profile 上开调试端口的原因。

## macOS 无人值守

browserhost 只管浏览器：**防睡与唤醒由任务侧自己负责**（本库不再提供相关命令）。

```bash
# 1) 启动实例并在浏览器窗口里完成登录（只做一次；窗口之后随手关掉都行）
python main.py start

# 2) 预约唤醒：睡眠中的 launchd 不会执行任务，必须提前排定（需 sudo，人工执行一次）
sudo pmset repeat wakeorpoweron MTWRFSU 09:45:00

# 3) 任务脚本自己保证运行期间不睡
caffeinate -dims .venv/bin/python -m src.grab
```

**前提（必须由人保证）**：机器**不合盖**且**持续接电源**。合盖必然进入无法唤醒的睡眠，
任何软件都救不回来；`caffeinate -s` 的断言也只在接电源时有效。

**没有任务时**：不持有任何防睡断言，机器自然睡眠、CDP 随之不可用——这是有意为之
（没有任务时不必占着内存和调试端口）。空闲睡眠可以被 `pmset` 唤醒；任务开始前
`python main.py start` 会重新拉起或复用实例：

- 机器只是睡过一觉：Chrome 进程还在，唤醒后端口即可用，`start` 会直接复用；
- Chrome 已经退出：`start` 重新启动它，profile 里的登录态照样复用，不必重新登录。

**锁屏可以，注销不行**（注销会结束用户会话，连带杀掉 Chrome）。

## 故障排查

```bash
python main.py start      # 连不上时先跑它：幂等，能修好不健康的实例
tail -f ~/.browserhost/logs/browserhost_$(date +%F).log
```

- **端口被别的进程占用**：`start` 会拒绝启动并打印占用者的 pid 与命令行；先关掉它，
  或改 `main.py` 里的端口／profile 目录再 `start`。
- **登录态检查**：cookie 值在 `encrypted_value` 列里、用系统密钥加密（Windows DPAPI /
  macOS Keychain），所以**跨系统复制 profile 带不走登录态**（同系统内复制可以），
  换机器只能重新登录。要在本机确认登录态，直接在浏览器窗口里打开站点看，或读
  `~/.browserhost/profile/Default/Network/Cookies`（Chrome 运行中该库被独占锁，
  要复制出来再查；cookie 名如京东的 `pt_key` / `pt_pin` 是明文，值是密文）。
- **`stop` 拒绝关闭**：那个调试端口不是我们启动的（非受管实例）→ 出于安全拒绝，
  请自己手动关闭它。
- **Windows 上关掉最后一个标签页会让 Chrome 退出**（调试端口随之消失）；macOS 上 Chrome
  会留在后台。所以「窗口关掉后 CDP 仍可用」只在 macOS 上成立。

## 目录结构

```text
browserhost/
├── main.py          唯一入口：start / stop / restart
└── src/             实现（不是安装包）
    ├── config.py    路径与运行时数据布局
    ├── logging.py   按天日志（终端 + 文件）
    ├── lock.py      跨平台文件锁
    ├── chrome.py    查找/启动/连接 Chrome + L1/L2/L3 健康探测
    ├── instance.py  实例状态、归属校验、优雅关闭、端口诊断
    └── ensure.py    start 的完整流程（探测 → 复用 → 重启 → 启动 → 记状态）
```
