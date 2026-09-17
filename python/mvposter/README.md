# MVPoster - 视频下载器

用**系统里的真实 Chrome** 挑视频，用 **yt-dlp** 下载到 `movies/<日期>/` 的多平台视频下载工具（YouTube / TikTok）。

没有客户端：不打包 Electron，也不需要装扩展。浏览器就是 Chrome，登录和「下哪条视频」都在 Chrome 里完成；本程序只通过 **CDP** 连上这个 Chrome，做三件事——

1. 拉起（或复用）带调试端口的真实 Chrome，登录态存进 `chrome_profile/`；
2. 盯着**用户当前激活的那个标签页**，把标题 / URL 打到终端；
3. 用户按下回车时，从 Chrome 导出 cookies 交给 yt-dlp，下载到 `movies/<当天日期>/`。

## 为什么不做客户端

旧版是 Electron：内嵌 webview 自己实现浏览器、再自己实现「下载按钮 → 起 yt-dlp 子进程」。
问题在于视频站点只认**真实登录态与风控环境**，内嵌浏览器要复刻 cookie 提取、UA、指纹，
维护成本全花在「把事情弄成不是浏览器」上；而且为了点一下按钮，要先装一个上百 MB 的壳。

现在的分工是：

| 职责 | 由谁承担 |
|---|---|
| 浏览器内核、登录、反爬环境 | 用户自己的 Chrome（真实、受信任） |
| 选哪条视频 | 用户在 Chrome 里打开它 |
| 触发下载 | 终端里一次回车（或 `--auto`） |
| 真正下载 / 合并 | yt-dlp + ffmpeg |
| 登录态传递 | CDP 导出 cookies 给 yt-dlp（一次一个临时文件，用完即删） |

代价是必须在项目根目录 `movies/` 里找产物、必须留着 Chrome 窗口；
换来的是零安装体积、零 UI 代码，站点改版也不会连带把 UI 弄坏。

## 触发下载是怎么设计的

难点是「用户已经在 Chrome 里选好了视频，程序怎么知道该下了」。Chrome 侧不注入任何
脚本（注入就要写扩展 = 又一个客户端），所以触发点只有三个，都在程序侧：

- **回车（默认）**：程序每 0.3s 通过 CDP 问一次「哪个标签页被激活」，把它的标题 / URL
  打到终端；你切到目标视频页后回终端按一次回车，就下载**当前激活标签页**的 URL。
  不会误下——程序只在你按键的那一刻取当前页。
- **`--auto`**：切到视频页后**停留** `--auto-delay` 秒（默认 3s）才自动下载，中途切走
  就取消；同一 URL 只下一次。适合连续下多条，代价是有误下风险。
- **`--download <url>`**：完全不走交互，直接下载给定 URL 后退出，方便脚本化。

「哪个标签页是当前激活的」用页面自身的 `document.hasFocus()` / `visibilityState`
判断（CDP 不提供「选中了哪个 tab」这种字段）；页面标题/URL 变化时才会在终端打日志，
所以终端不会被刷屏。

## 代理与配置（config.json）

浏览器（登录过程）和 yt-dlp（下载）**默认都走 `http://127.0.0.1:1080`**。这个默认值写在项目
根目录的 `config.json` 里，直接改它即可：

```json
{
  "proxy": "http://127.0.0.1:1080"
}
```

- 想直连：把 `proxy` 改成空串 `""`。
- 想换端口 / 换机器：改这个地址就行（写 `127.0.0.1:7890` 这种不带协议头的也认）。
- 不想改文件时可以用环境变量临时覆盖：按 `HTTPS_PROXY` → `HTTP_PROXY` → `ALL_PROXY`
  的顺序取第一个非空值（大小写都认）。

```bash
# Windows PowerShell
$env:HTTPS_PROXY = "http://127.0.0.1:7890"; python -m src.main

# macOS / Linux
export HTTPS_PROXY=http://127.0.0.1:7890 && python -m src.main
```

优先级：**环境变量 > `config.json` > 内置默认值**。启动日志会写明当前用的是哪个代理、
打哪来的，例如 `代理：http://127.0.0.1:1080（config.json 里的 proxy）`。

实现上的几个约定：

- Chrome 用 `--proxy-server=<proxy>` 启动，所以**登录过程**也走同一个代理；但复用已经
  开着的 Chrome 时该参数不生效（日志会提示一句），它沿用自己原来的代理设置。
- yt-dlp 自己不会读环境变量、也不会读 `config.json`，所以是程序读出来显式传给它的。
- 日志里只打印打码后的地址（`http://***@host:port`）。
- 不给 `--proxy` 开关：命令行参数会进 shell 历史、进程列表和日志。要放带用户名密码的
  代理，就写在 `config.json` 里（顺带注意别把带密码的 `config.json` 提交进仓库）。
- 默认值指向的是**本机**端口。若本机没跑代理，程序启动时会说明一句并**改走直连**，
  不会让浏览器和下载一起卡死（远端代理不探测，避免网络抖动被当成没配）。

## 系统要求

- Chrome 或 Edge（Windows / macOS / Linux 常见安装位置会自动找到，也可 `--chrome` 指定）
- Python 3.10+ 与 [uv](https://docs.astral.sh/uv/)（依赖管理）
- 可选：Node.js 22+（yt-dlp 解 YouTube 的 JS 挑战要用；没装也能下，但可能缺格式）

**依赖就两处，都不用你手敲包管理器**：yt-dlp 与官方 EJS 脚本包装进项目里的 `.venv`
（不用 `pip install yt-dlp`），ffmpeg 由脚本用 `winget` / `brew` 装到**系统**里
（`python scripts/fetch_binaries.py`，已经装好就跳过）。

```bash
# Windows
winget install astral-sh.uv
# macOS
brew install uv
```

## 安装

```bash
# 1. Python 依赖装进项目内的 .venv（yt-dlp[default] = yt-dlp + 官方 EJS 脚本包）
uv sync

# 2. 确保系统里有 ffmpeg（一次性；已装好会跳过，缺了自动用 winget / Homebrew 装）
python scripts/fetch_binaries.py

# 3. 运行（用项目内 .venv 的解释器）
.venv\Scripts\python.exe -m src.main      # Windows
.venv/bin/python -m src.main              # macOS / Linux
# 或 uv run python -m src.main
```

不需要 `playwright install`：本程序只通过 CDP 连接**系统里的真实 Chrome**，
不使用 Playwright 自带的 Chromium。

### 依赖放在哪

| 依赖 | 放在哪 | 说明 |
|---|---|---|
| yt-dlp + yt-dlp-ejs | `.venv/`（`uv sync` 装的 Python 包） | 不进 PATH、不动系统环境；EJS 是官方挑战脚本包，缺了 YouTube 会少一批格式 |
| ffmpeg / ffprobe | 系统里（PATH、winget 的 `Links`、Homebrew 的 `bin`） | yt-dlp 合并分轨要用；由 `scripts/fetch_binaries.py` 用包管理器装上 |
| Chrome / Edge | 系统里已装的浏览器 | 登录态、选视频都在这里，不打包、不内嵌 |

- ffmpeg 一律装在系统里：脚本先检测（PATH，以及 Windows 的
  `%LOCALAPPDATA%\Microsoft\WinGet\Links`、macOS 的 `/opt/homebrew/bin`、`/usr/local/bin`），
  缺了就用 `winget install Gyan.FFmpeg`（Windows）或 `brew install ffmpeg`（macOS）装，
  装完立刻跑一次 `ffmpeg -version` 验证。
- 没有可用的包管理器（Windows 没有 winget、macOS 没有 Homebrew）时，脚本**只提示**手动
  安装方式，不会自己下 zip、也不往项目里塞文件。
- 万一 ffmpeg 还是缺着，下载视频时会自动降级为只挑「音视频已合体」的格式
  （不用合并，清晰度通常最多 720p），不会直接报错。
- 换机器重跑一次第 2 步即可（脚本幂等：装好了就直接跳过）。


## 使用

```bash
# 默认：启动 Chrome 并进入监听，在 Chrome 里选好视频后回终端按回车
python -m src.main

# 自动模式：切到视频页停留 3 秒自动下载（同一 URL 只下一次）
python -m src.main --auto
python -m src.main --auto --auto-delay 8      # 更保守的停留时间

# 直接下载指定 URL 后退出
python -m src.main --download "https://www.youtube.com/watch?v=xxxx"

# 限制清晰度（默认 1080，best 表示不限）
python -m src.main --quality 720

# 指定平台：只把该站点的页面当视频页，并默认打开它的首页
python -m src.main --platform youtube          # 只认 YouTube 视频页
python -m src.main --platform tiktok --auto    # 只认 TikTok，并打开 tiktok.com
```

### 参数一览

| 参数 | 说明 |
|---|---|
| `--auto` | 自动模式：切到视频页停留 `--auto-delay` 秒后自动下载 |
| `--auto-delay` | 自动模式的停留秒数，默认 `3` |
| `--download URL` | 直接下载该 URL 后退出，不进入监听 |
| `--quality` | `1080`（默认）/ `720` / `480` / `360` / `best` |
| `--platform` | `auto`（默认，识别所有已支持站点）/ `youtube` / `tiktok`：只把该站点的页面当视频页 |
| `--port` | Chrome 调试端口，默认 `9222` |
| `--profile` | Chrome 用户数据目录，默认 `./chrome_profile`（**登录态存在这里**） |
| `--chrome` | Chrome/Edge 可执行文件路径，默认自动查找 |
| `--open` | 启动 Chrome 时打开的地址，默认跟着 `--platform` 走（`auto` 时是 `https://www.youtube.com`） |

- `--platform` 有两点作用：① 只有该站点的页面才算视频页（自动模式不会对其他站点触发下载，
  终端提示里会写明「当前只下 X」）；② 没显式传 `--open` 时，启动 Chrome 打开的就是它的首页。
  想加平台只需在 `src/config.py` 的 `PLATFORMS` 里加一条（关键字 → 显示名 / 视频页正则 /
  首页），命令行会自动多出一个可选值。
- 首次使用：程序会打开一个**全新的 Chrome 窗口**（用户数据目录是 `chrome_profile/`，
  与你日常用的 Chrome 互不影响），在里面登录 YouTube / TikTok，登录态会留在该目录里，
  下次直接复用，不用再登。用 `q` 或 Ctrl+C 退出。
- 想用日常 Chrome 的登录态：先自己带调试端口启动它，再运行本程序即可复用（此时程序
  退出**不会**关掉你的 Chrome）：

  ```bash
  chrome --remote-debugging-port=9222     # 用你自己的 user-data-dir 时需先退出已开的 Chrome
  python -m src.main
  ```

- 若 `--port` 已被占用（比如日常 Chrome 开着调试端口），程序会复用它而不是再拉一个；
  若提示等待调试端口超时，通常是「同一用户数据目录已被另一个 Chrome 占用」，
  关掉那个 Chrome 或换 `--profile` 即可。

### 下载产物

```text
movies/
└── 2026-09-16/                       # 按下载当天日期分目录
    └── 视频标题 [dQw4w9WgXcQ].mp4    # 标题取自视频，方括号里是视频 id（防重名）
```

文件名走 `windowsfilenames` 规则，标题里的非法字符会被替换；标题截断到 100 字符。
同一条视频重复下载时 yt-dlp 会识别出已存在的文件并跳过。

### 执行日志

终端输出同时按天写入 `logs/mvposter_YYYY-MM-DD.log`（追加、逐行 flush）：每次运行记录
代理来源、下载目录、当前标签页变化、每次下载的结果与落盘路径，便于事后核对
「当时到底下了哪条视频」。退出码：`0` 正常退出 / 下载成功；`1` 启动 Chrome 或下载失败；
`130` 被 Ctrl+C 中断。

## 目录结构

```text
mvposter/
├── pyproject.toml      # 项目元数据与依赖（uv）
├── requirements.txt    # 依赖列表（快速参考）
├── config.json         # 运行配置（代理地址等，可直接改）
├── README.md
├── scripts/
│   └── fetch_binaries.py  # 检查 / 安装系统级 ffmpeg（winget / Homebrew）
├── src/
│   ├── config.py       # 目录、视频站点规则、Chrome/CDP 参数、代理与配置文件路径
│   ├── browser.py      # 日志、启动/连接 Chrome、当前标签页、导出 cookies
│   ├── downloader.py   # yt-dlp 封装：代理、movies/<日期>、格式与进度
│   └── main.py         # 唯一入口：监听当前标签页 + 触发下载
├── movies/             # 下载产物（运行时生成，按日期分目录）
├── logs/               # 按天分的执行日志（运行时生成）
└── chrome_profile/     # Chrome 用户数据目录（运行时生成，登录态）
```

## 注意事项

- 请遵守各平台的使用条款，仅用于个人学习与合法用途。
- 下载的视频版权归原作者所有。
- 视频站点的页面结构或风控变化可能导致下载失败，此时先升级 `yt-dlp`
  （`uv lock --upgrade-package yt-dlp && uv sync`）再试。
- 升级 ffmpeg：`winget upgrade Gyan.FFmpeg`（Windows）/ `brew upgrade ffmpeg`（macOS）；
  项目内不再放副本，旧版本遗留的 `resources/bin/` 可以直接删掉。
