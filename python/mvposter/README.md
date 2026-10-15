# MVPoster - 检索 / 下载 / 发布

用 **yt-dlp** 检索 YouTube 候选、下载到 `movies/<日期>/`，再经 **CDP** 发到微信视频号；
需要登录态的环节（下载要 cookies、发布要扫码登录）一律借**别人常驻的真实 Chrome**。

浏览器不归本项目管理：真实 Chrome（含登录态、用户数据目录）由独立项目
[`browserhost`](../browserhost) 常驻提供——先 `cd ../browserhost && python main.py start`
起一次，之后调试端口一直可用、窗口随手关掉都行。本项目只通过 **CDP** 连它，做三件事——

1. **检索**：按语义关键词抓 YouTube 候选，按「播放速度」排序，写进 SQLite 去重（`python -m src.cli discover`）；
2. **下载**：连上常驻 Chrome、导出 cookies 交给 yt-dlp，落盘到 `movies/<当天日期>/`（`python -m src.main`）；
3. **发布**：新开**自己的**页签，把本地视频填进视频号助手，默认停在「发表」按钮前等人工确认（`python -m src.cli publish`）。

## 为什么不做客户端

旧版是 Electron 内嵌浏览器。视频站点只认**真实登录态与风控环境**，内嵌浏览器要复刻 cookie
提取、UA、指纹，维护成本全花在「把事情弄成不是浏览器」上。现在改成各司其职：

| 职责 | 由谁承担 |
|---|---|
| 浏览器内核、登录、反爬环境 | 用户自己的 Chrome（真实、受信任） |
| 选哪条视频 | 用户在 Chrome 里打开它 |
| 触发下载 | 终端里一次回车（或 `--auto`） |
| 真正下载 / 合并 | yt-dlp + ffmpeg |
| 登录态传递 | CDP 导出 cookies 给 yt-dlp（一次一个临时文件，用完即删） |
| 发布 | CDP 新开**自己的**页签，把本地视频填进视频号助手的发布页 |

代价是必须在项目根目录 `movies/` 里找产物、浏览器窗口归 browserhost 管（本项目既不启动
也不关闭它）；换来的是零安装体积、零 UI 代码，站点改版也不会连带把 UI 弄坏。

## 触发下载是怎么设计的

Chrome 侧不注入任何脚本（注入就要写扩展 = 又一个客户端），所以触发点都在程序侧：

- **回车（默认）**：程序每 0.3s 问一次 CDP「哪个标签页被激活」，把它的标题 / URL 打到
  终端；你切到目标视频页后回终端按一次回车，就下载**当前激活标签页**。只在你按键的那一刻
  取当前页，所以不会误下。
- **`--auto`**：切到视频页后**停留** `--auto-delay` 秒（默认 3s）才下载，中途切走即取消；
  同一 URL 只下一次。适合连续下多条，代价是有误下风险。
- **`--download <url>`**：不走交互，直接下载给定 URL 后退出，方便脚本化。

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
$env:HTTPS_PROXY = "http://127.0.0.1:7890"; python -m src.main

# macOS / Linux
export HTTPS_PROXY=http://127.0.0.1:7890 && python -m src.main
```

优先级：**环境变量 > `config.json` > 内置默认值**。启动日志会写明当前用的是哪个代理、
打哪来的，例如 `代理：http://127.0.0.1:1080（config.json 里的 proxy）`。

几个约定：

- 浏览器（登录、发布）走什么代理由 browserhost 启动那个 Chrome 时的设置决定；本项目不加
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
.venv/bin/python -m src.main                       # 3. 运行（Windows 用 .venv\Scripts\python.exe）
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

```bash
# 默认：进入监听，在浏览器里选好视频后回终端按回车（浏览器先由 browserhost 起好）
python -m src.main

# 自动模式：切到视频页停留 3 秒自动下载（同一 URL 只下一次）
python -m src.main --auto
python -m src.main --auto --auto-delay 8      # 更保守的停留时间

# 直接下载指定 URL 后退出
python -m src.main --download "https://www.youtube.com/watch?v=xxxx"

# 限制清晰度（默认 1080，best 表示不限）
python -m src.main --quality 720

# 指定平台：只把该站点的页面当视频页
python -m src.main --platform youtube          # 只认 YouTube 视频页
python -m src.main --platform tiktok --auto    # 只认 TikTok
```

### 参数一览

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
- **首次使用要先登录**：在 browserhost 那个 Chrome 里手动登录 YouTube / TikTok（发视频号
  再扫码登录一次），登录态留在 `~/.browserhost/profile` 里，之后长期复用。
- 连不上就先去起 browserhost（程序也会把这行提示打在日志里）：

  ```bash
  cd ../browserhost && python main.py start      # 幂等：已在跑且健康就直接复用
  cd ../browserhost && python main.py restart    # 端口有响应但连不上时用它
  ```

- 退出本程序**不会**关掉那个 Chrome（它归 browserhost 管），也不会去关你或别的任务开的页签。

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
「当时到底下了哪条视频」。退出码：`0` 正常退出 / 下载成功；`1` 连不上 CDP 服务或下载失败；
`130` 被 Ctrl+C 中断。

## 检索候选与去重（`python -m src.cli`）

`src.main` 只管「我已经选好了，请下载」。**怎么找到值得下载的视频、怎么不重复爬、
发到视频号**由 `src.cli` 负责（检索与记录不需要浏览器；发布要连 browserhost 的 CDP）：

```bash
# 0) 看「动物搞笑」按语义展开的关键词（不检索）
python -m src.cli keywords --topic 动物搞笑 --focus 猫 --keyword-count 12

# 1) 检索：默认用语义生成的关键词抓 YouTube 候选，按「播放速度」排序（播放量 ÷ 上线天数）
python -m src.cli discover --top 10
python -m src.cli discover --focus 狗 --keyword-count 8 --top 5
python -m src.cli discover --keywords "funny cats shorts,funny dogs shorts"   # 也可手写词表
python -m src.cli discover -o .cache/candidates.json     # 给脚本 / AI CLI 消费

# 2) 挑中某条（人工或 AI 决定）
python -m src.cli mark nRDysNZdMvU picked --note "挑中"

# 3) 下载（借常驻 Chrome 的 cookies；终端里回一趟 src.main，或用 --download）
python -m src.main --download "https://www.youtube.com/watch?v=nRDysNZdMvU"

# 4) 下载完对账：把 movies/ 里的文件登记成 downloaded，下次检索就不会重复爬
python -m src.cli backfill
python -m src.cli list --status found

# 5) 发布（默认填完表、核对无误就自动提交；想先人工核对就加 --no-publish）
python -m src.cli publish nRDysNZdMvU --title "小狗撒娇求抱抱" --desc "每天一条动物搞笑" --tags 萌宠,搞笑动物
python -m src.cli publish nRDysNZdMvU --no-publish               # 只填表 + 截图，停在「发表」前
python -m src.cli mark nRDysNZdMvU published --post-id 123456    # 拿到视频号里的标识后补记
```

- **去重靠 YouTube 的 video_id**（不是标题）：记录写在 `data/mvposter.db`（SQLite，
  `data/` 已在 `.gitignore` 里）。`discover` 默认跳过库里已有的 id，`backfill` 则把
  `movies/` 里历史文件反向登记进库（文件名里的 `[id]` 就是键）。
- **状态机**：`found → picked → downloaded → published`，旁支 `failed` / `skipped`；
  `publish` 成功会自己写成 `published`，发布成功后再用 `mark --post-id` 补记视频号里的标识。
- **发布默认自动提交**：填完表会**把字段读回来核对**（对不上就绝不提交），核对通过才点「发表」，
  再以「页面跳到作品列表 / 出现『已发表』」确认结果；60s 内确认不了会如实报 `submitted` 让你去后台看。
  想先人工核对一遍用 `--no-publish`（只填表 + 截图，停在按钮前，页签留着）。
- **发布只动自己的页签**：`publish` 会**新开**一个页签打开视频号助手的发布页，绝不碰你或
  别的任务开着的页签；登录态失效时只截图报错（`logs/publish_*.png`）、不尝试自动登录。
  填的是「视频描述」（`--desc`，`--tags` 会以 `#标签` 附在末尾）与「短标题」（`--title`）；
  `声明原创` 这类作者表态**不代做**，要勾自己勾。
- **发布页是无界（wujie）微前端**：真实表单在 `<wujie-app>` 的 shadow DOM 里（`body.innerText`
  看不到它），且打开后会自己重载一次——所以选择器只能用 Playwright 定位器，且必须等表单
  挂载。选择器（实测于 2026-10-15）集中在 `src/publish.py` 顶部，改版后按截图重校。
- **关键词是按语义生成的**：`src/keywords.py` 把主题（默认「动物搞笑」）拆成
  动物 × 情境 × 风格 三个槽位再组合，种子默认取当天日期——同一天可复现、第二天换一批。
  `--topic` 认别名（`animal` / `萌宠` / `pets` 都行），`--focus 猫` 聚焦某种动物
  （中英文都认），`--with-chinese` 额外带中文词。词表在 `python -m src.cli keywords` 里看。
- **排序参数是实测定的，不是照抄对照表**：默认 `--sort views`（按播放量降序）下，
  100 条里有 69 条是 ≤60s 的短视频；而 YouTube 那个名字带 "short" 的筛选参数实测
  **并不限制时长**（中位 1110s），所以时长/播放量过滤一律在本地做。
- **播放速度而不是总播放量**：总播放量高的常年老视频搬到视频号没意义；
  `score = 播放量 ÷ 上线天数`，取「正在涨」的。
- 检索参数（排序 `sp`、时长/播放量阈值、每关键词条数）见 `src/discover.py` 顶部常量，
  也都能用命令行覆盖。

## 目录结构

```text
mvposter/
├── pyproject.toml      # 项目元数据与依赖（uv）
├── requirements.txt    # 依赖列表（快速参考）
├── config.json         # 运行配置（代理地址等，可直接改）
├── README.md
├── src/
│   ├── config.py       # 目录、视频站点规则、CDP 端口、代理与配置文件路径
│   ├── logging.py      # 按天写日志（终端 + logs/mvposter_<日期>.log）
│   ├── browser.py      # 只连接 browserhost 的 CDP：当前标签页、导出 cookies
│   ├── downloader.py   # yt-dlp 封装：代理、movies/<日期>、格式与进度
│   ├── discover.py     # 检索候选：flat 检索 + sp 排序 + 本地重排/过滤/打分
│   ├── keywords.py     # 按语义槽位把主题展开成关键词
│   ├── store.py        # SQLite：去重、状态机、与 movies/ 对账
│   ├── publish.py      # 视频号发布（CDP 新开自己的页签，默认填完即自动提交）
│   ├── cli.py          # 流水线入口：keywords / discover / list / backfill / mark / publish
│   └── main.py         # 下载入口：监听当前标签页 / --auto / --download
├── movies/             # 下载产物（运行时生成，按日期分目录）
└── logs/               # 按天分的执行日志与发布截图（运行时生成）
```

## 注意事项

- **浏览器不归本项目管**：启动/关闭/登录态都交给 browserhost（`~/.browserhost/`），
  本仓库里遗留的 `chrome_profile/` 不再使用，可以自行删掉。
- 请遵守各平台的使用条款，仅用于个人学习与合法用途。
- 下载的视频版权归原作者所有。
- 发布**默认自动提交**（`--no-publish` 可停在「发表」前）；视频号有审核与风控，
  前几条建议用 `--no-publish` 人工过一眼，再放开自动提交。
- 发布页的选择器是 **2026-10-15 实测校准**的（上传 `input[accept*=video]`、描述
  `div.input-editor`、短标题 `input[placeholder*=短标题]`、发表按钮精确文案「发表」），
  页面改版后按 `logs/publish_*.png` 重校。
- 视频站点的页面结构或风控变化可能导致下载失败，此时先升级 `yt-dlp`
  （`uv lock --upgrade-package yt-dlp && uv sync`）再试。
- ffmpeg 的安装与升级都归系统/你自己管（`winget upgrade Gyan.FFmpeg` / `brew upgrade ffmpeg`）：
  本程序不安装、不代管、也不检查，项目内也不放副本（旧版遗留的 `resources/bin/` 已删除）。
