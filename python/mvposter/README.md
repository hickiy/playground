# MVPoster - YouTube 短视频下载器

人工挑好短视频后，把 YouTube 链接或 11 位 video id 交给 `python -m src.job`：

1. **查重**：先查 `data/mvposter.db`，已有记录就提示重复并**立即终止任务**；
2. **下载**：借 browserhost 常驻 Chrome 的登录态 cookies，用 yt-dlp 下载到 `movies/<日期>/`；
3. **记录**：把标题、频道、播放量、时长、上线日期、本地路径写进 SQLite；
4. **结束**：下载完这次任务就结束。

本仓库**只负责下载**：不做程序化检索，也不做发布。视频描述与标题由你自己在发布时处理。

## 为什么不做客户端

旧版是 Electron 内嵌浏览器。视频站点只认**真实登录态与风控环境**，内嵌浏览器要复刻 cookie
提取、UA、指纹，维护成本全花在「把事情弄成不是浏览器」上。现在各司其职：

| 职责 | 由谁承担 |
|---|---|
| 浏览器内核、登录、反爬环境 | 用户自己的 Chrome（真实、受信任） |
| 选哪条视频 | 用户自己决定（复制链接，或在 Chrome 里打开） |
| 触发下载 | `python -m src.job <链接或 id>`，或终端里一次回车 |
| 查重与记录 | 本地 SQLite（`data/mvposter.db`） |
| 真正下载 / 合并 | yt-dlp + ffmpeg |
| 登录态传递 | CDP 导出 cookies 给 yt-dlp（一次一个临时文件，用完即删） |

代价是必须在项目根目录 `movies/` 里找产物、浏览器窗口归 browserhost 管（本项目既不启动
也不关闭它）；换来的是零安装体积、零 UI 代码，站点改版也不会连带把 UI 弄坏。

## 查重规则（重要）

- 去重键：YouTube 统一取 **11 位 video_id**，`watch` / `shorts` / `live` / `youtu.be`
  链接都会归一到同一个键；其他站点用 `平台:URL`。
- 每次下载前都会查库。**命中已有记录 → 打印标题、下载时间、本地路径，立即终止任务，
  退出码 `2`**，不会再下载、也不会覆盖文件。
- 只有**下载成功**才写库；下载失败不留下记录，修好后重跑同一条命令即可。
- 数据库被清空后，历史文件不会被自动识别。需要把 `movies/` 里的旧文件补登记进库时：
  `python -m src.cli backfill`（文件名里的 `[11位id]` 就是去重键）。
- 想彻底清空查重历史：删掉 `data/mvposter.db` 即可（下次运行会自动重建空库）。

## 触发下载的三种方式

Chrome 侧不注入任何脚本（注入就要写扩展 = 又一个客户端），所以触发点都在程序侧：

- **`python -m src.job <链接或 id>`（推荐）**：一次性任务，查重 → 下载 → 记录 → 结束。
- **`python -m src.main`（交互）**：程序每 0.3s 问一次 CDP「哪个标签页被激活」，你切到目标
  视频页后回终端按一次回车，就下载**当前激活标签页**。只在你按键的那一刻取当前页，不会误下。
- **`python -m src.main --auto`**：切到视频页后**停留** `--auto-delay` 秒（默认 3s）才下载，
  中途切走即取消；同一 URL 只下一次。
- **`python -m src.main --download <url>`**：不走交互，直接下载给定 URL 后退出。

以上方式共用同一套查重：一旦命中已有记录，都会提示重复并立即终止（退出码 `2`）。

「当前激活」用页面自身的 `document.hasFocus()` / `visibilityState` 判断（CDP 没有
「选中了哪个 tab」这种字段）；标题 / URL 变化时才打日志，终端不会被刷屏。

## 代理与配置（config.json）

**浏览器的代理由 browserhost 决定，本项目不碰**；这里配的是 **yt-dlp 下载**用的代理，
默认走 `http://127.0.0.1:1080`。这个默认值写在项目根目录的 `config.json` 里，直接改它即可：

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
$env:HTTPS_PROXY = "http://127.0.0.1:7890"; python -m src.job <链接或id>

# macOS / Linux
export HTTPS_PROXY=http://127.0.0.1:7890 && python -m src.job <链接或id>
```

优先级：**环境变量 > `config.json` > 内置默认值**。启动日志会写明当前用的是哪个代理、
打哪来的，例如 `代理：http://127.0.0.1:1080（config.json 里的 proxy）`。

几个约定：

- 浏览器（登录）走什么代理由 browserhost 启动那个 Chrome 时的设置决定；本项目不加
  `--proxy-server`、也不改那个实例的代理——它是别的任务共用的。
- yt-dlp 不读环境变量、也不读 `config.json`，是程序读出来显式传给它的；日志里只打印
  打码后的地址（`http://***@host:port`），不带用户名密码就别写进命令行。
- 默认值指向**本机**端口；本机没跑代理时程序会说明一句并**改走直连**，不会让下载卡死
  （远端代理不探测，避免网络抖动被当成没配）。

## 安装与依赖

```bash
cd ../browserhost && python main.py start          # 0. 起常驻 Chrome（幂等；已在跑且健康就复用）
uv sync                                            # 1. Python 依赖装进项目内 .venv（yt-dlp[default] = yt-dlp + 官方 EJS 脚本包）
brew install ffmpeg                                # 2. 系统里要有 ffmpeg（Windows 用 winget install Gyan.FFmpeg）——本程序不装也不管
.venv/bin/python -m src.job <链接或id>             # 3. 运行（Windows 用 .venv\Scripts\python.exe）
```

`uv` 本身：`winget install astral-sh.uv`（Windows）/ `brew install uv`（macOS）。
不需要 `playwright install`：本程序只通过 CDP 连接**系统里的真实 Chrome**，不使用
Playwright 自带的 Chromium。

> **浏览器从哪来**：相邻项目 [`browserhost`](../browserhost) 负责启动并常驻一个真实 Chrome
> （profile 在 `~/.browserhost/profile`，登录态就存那儿）。本项目**只连它的调试端口**
> （默认 9222）：不启动、不关闭浏览器，也不管 profile；连不上时会直接提示你去
> `../browserhost` 里 `python main.py start`。所以本仓库里没有 `chrome_profile/` 这种东西，
> 也不再依赖 browserhost 的库接口（`uv sync` 只装 playwright 与 yt-dlp）。

| 依赖 | 放在哪 | 说明 |
|---|---|---|
| yt-dlp + yt-dlp-ejs | `.venv/`（`uv sync`） | 不进 PATH、不动系统环境；EJS 是官方挑战脚本包，缺了 YouTube 会少一批格式 |
| ffmpeg / ffprobe | 系统里（PATH、winget 的 `Links`、Homebrew 的 `bin`） | **只用系统里那份**：本程序不安装、不代管、也不检查，项目内不放副本；找到就把位置告诉 yt-dlp，缺了由 yt-dlp 自己报错 |
| Chrome / Edge | 系统里已装的浏览器（由 browserhost 启动并常驻） | 登录态、选视频都在那里，不打包、不内嵌 |
| Node.js 22+（可选） | 系统里 | yt-dlp 解 YouTube 的 JS 挑战要用；没装也能下，但可能缺格式 |

## 使用

### 一次性下载任务（推荐）

```bash
# 链接或 11 位 video id 都行；多条按顺序处理
python -m src.job "https://www.youtube.com/shorts/xxxxxxxxxxx"
python -m src.job dQw4w9WgXcQ
python -m src.job dQw4w9WgXcQ nRDysNZdMvU

# 只查重并打印目标，不下载、不写数据库
python -m src.job dQw4w9WgXcQ --dry-run

# 限制清晰度（默认 1080，best 表示不限）
python -m src.job dQw4w9WgXcQ --quality 720
```

### 交互式：下载当前标签页

```bash
# 默认：在 Chrome 里选好视频，回终端按回车
python -m src.main

# 自动模式：切到视频页停留 3 秒自动下载（同一 URL 只下一次）
python -m src.main --auto
python -m src.main --auto --auto-delay 8

# 直接下载指定 URL 后退出
python -m src.main --download "https://www.youtube.com/watch?v=xxxx"
```

- **首次使用要先登录**：在 browserhost 那个 Chrome 里手动登录 YouTube，登录态留在
  `~/.browserhost/profile` 里，之后长期复用。登录失效时 yt-dlp 会报
  `Sign in to confirm you're not a bot`——去那只 Chrome 里重新登录后再试。
- 连不上就先去起 browserhost（程序也会把这行提示打在日志里）：

  ```bash
  cd ../browserhost && python main.py start      # 幂等：已在跑且健康就直接复用
  cd ../browserhost && python main.py restart    # 端口有响应但连不上时用它
  ```

- 退出本程序**不会**关掉那个 Chrome（它归 browserhost 管），也不会去关你或别的任务开的页签。

### 查看记录 / 补登记历史文件

```bash
python -m src.cli list                    # 最近 20 条下载记录
python -m src.cli list --limit 100
python -m src.cli backfill                # 扫描 movies/，把历史文件补登记进库
```

## 参数一览

### `python -m src.job`

| 参数 | 说明 |
|---|---|
| `URL_OR_ID` | YouTube 链接或 11 位 video id；可给多个，按顺序处理 |
| `--quality` | `1080`（默认）/ `720` / `480` / `360` / `best` |
| `--port` | browserhost 那个常驻 Chrome 的调试端口，默认 `9222` |
| `--dry-run` | 只查重并打印目标，不下载、不写数据库 |

### `python -m src.main`

| 参数 | 说明 |
|---|---|
| `--auto` | 自动模式：切到视频页停留 `--auto-delay` 秒后自动下载 |
| `--auto-delay` | 自动模式的停留秒数，默认 `3` |
| `--download URL` | 直接下载该 URL 后退出，不进入监听 |
| `--quality` | `1080`（默认）/ `720` / `480` / `360` / `best` |
| `--platform` | `auto`（默认，识别所有已支持站点）/ `youtube` / `tiktok`：只把该站点的页面当视频页 |
| `--port` | browserhost 那个常驻 Chrome 的调试端口，默认 `9222` |

- `--platform` 的作用：只有该站点的页面才算视频页（自动模式不会对其他站点触发下载，
  终端提示里会写明「当前只下 X」）。想加平台只需在 `src/config.py` 的 `PLATFORMS` 里
  加一条（关键字 → 显示名 / 视频页正则），命令行会自动多出一个可选值。

## 下载产物

```text
movies/
└── 2026-10-18/                       # 按下载当天日期分目录
    └── 视频标题 [dQw4w9WgXcQ].mp4    # 标题取自视频，方括号里是视频 id（防重名）
```

文件名走 `windowsfilenames` 规则，标题里的非法字符会被替换；标题截断到 100 字符。
同一条视频再次下载会在**查重阶段**被拦住，不会走到 yt-dlp。

## 执行日志与退出码

终端输出同时按天写入 `logs/mvposter_YYYY-MM-DD.log`（追加、逐行 flush）：每次运行记录
代理来源、下载目录、查重结果、下载结果与落盘路径。

| 退出码 | 含义 |
|---|---|
| `0` | 下载并记录成功（`--dry-run` 查重通过也算成功） |
| `1` | 参数错误、连不上 CDP、导出 cookies / 下载失败 |
| `2` | **命中重复记录**，按约定立即终止任务 |
| `130` | 被 Ctrl+C 中断 |

## 目录结构

```text
mvposter/
├── pyproject.toml      # 项目元数据与依赖（uv）
├── requirements.txt    # 依赖列表（快速参考）
├── config.json         # 运行配置（代理地址等，可直接改）
├── README.md
├── src/
│   ├── config.py       # 目录、视频站点规则、CDP 端口、代理与去重键
│   ├── logging.py      # 按天写日志（终端 + logs/mvposter_<日期>.log）
│   ├── browser.py      # 只连接 browserhost 的 CDP：当前标签页、导出 cookies
│   ├── downloader.py   # yt-dlp 封装：代理、movies/<日期>、格式与进度
│   ├── store.py        # SQLite：查重、下载记录、与 movies/ 对账
│   ├── main.py         # 下载入口：监听当前标签页 / --auto / --download
│   ├── job.py          # 一次性下载任务：查重 → 下载 → 记录 → 结束
│   └── cli.py          # 记录查看：list / backfill
├── movies/             # 下载产物（运行时生成，按日期分目录）
└── logs/               # 按天分的执行日志（运行时生成）
```

## 注意事项

- **浏览器不归本项目管**：启动/关闭/登录态都交给 browserhost（`~/.browserhost/`），
  本仓库里遗留的 `chrome_profile/` 不再使用，可以自行删掉。
- **本仓库不发布**：描述、标题、话题都由你自己在视频号后台处理，避免自动化产出低质量文案。
- 请遵守各平台的使用条款，仅用于个人学习与合法用途；下载的视频版权归原作者所有。
- 视频站点的页面结构或风控变化可能导致下载失败，此时先升级 `yt-dlp`
  （`uv lock --upgrade-package yt-dlp && uv sync`）再试。
- ffmpeg 的安装与升级都归系统/你自己管（`winget upgrade Gyan.FFmpeg` / `brew upgrade ffmpeg`）：
  本程序不安装、不代管、也不检查，项目内也不放副本。
