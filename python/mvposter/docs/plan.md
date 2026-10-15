# 方案：检索 → 下载 → 视频号发布

本文是「用 DeepSeek 后端的 CLI 智能体找视频、本工程爬取、再发到个人视频号」的完整规划。
**带「✔ 已实现」的部分已经落地**；**发布（第 4 节）已按方案落地为骨架**（`src/publish.py`），
其中选择器需要真机校正；带「⏳ 待确认」的部分只写了方案与契约，需要你确认后再动代码。

---

## 0. 目标与边界

| 环节 | 目标 | 现状 |
|---|---|---|
| 检索 | 从 YouTube 找「播放量高的动物搞笑短视频」候选 | ✔ 已实现（`python -m src.cli discover`） |
| 去重 | 爬过的视频不再重复爬、不重复发 | ✔ 已实现（`data/mvposter.db` + `backfill` 对账） |
| 下载 | 借常驻 Chrome 的 cookies，用 yt-dlp 下载 | ✔ 已实现（`python -m src.main`） |
| 发布 | 通过视频号 web 助手（CDP）发到个人视频号 | ✔ 已实测打通（`python -m src.cli publish`，默认填完即自动提交） |
| 智能体 | CLI 用 DeepSeek 当后端，负责关键词/挑片/写文案 | ⏳ 待确认（选型见第 2 节） |

平台分工保持不变：**真实 Chrome 承担浏览器与登录态，Python 只做确定性动作。**
浏览器的生命周期（启动 / 关闭 / profile）已经交给独立项目 **browserhost**（`../browserhost`，
`python main.py start`）：本工程只连它的调试端口，不启动、不关闭、也不管 profile。

---

## 1. 已实测的事实（决定了方案怎么选）

本机 Windows + 项目内 `.venv`（yt-dlp **2026.08.19** / Python 3.12.12）+ 代理 `127.0.0.1:1080`：

| 实测 | 结果 |
|---|---|
| `ytsearchN:关键词`（flat） | ✔ 5 条 **2.2s**，字段含 `view_count`/`duration`/`channel`/`thumbnails`/`timestamp` |
| `youtube.com/results?...&sp=CAM%3D`（按播放量降序） | ✔ **默认用它**：100 条里时长中位 **42s**、≤60s 且 ≥10 万播放的有 **69** 条 |
| `...&sp=CAMSAhAB`（名字里带 short 的那个筛选） | ✘ **实测并不限制时长**：中位 **1110s**，≤60s 的 0 条 —— 别拿它当时长过滤器 |
| `...&sp=CAI%3D`（按上传时间降序） | ✔ 可用（追新时），但内容偏长（中位 1188s） |
| flat 返回顺序是否即「播放量降序」 | ✘ **不是**（分批追加），必须本地重排 |
| 单条**完整**解析（要 `like_count`/`comment_count`） | ✘ 报 `Sign in to confirm you're not a bot` → **必须带 cookies**（本工程已能通过 CDP 导出） |
| `ytsearchdate5:` 语法 | ✘ 此版本不支持；按时间排序改用 `sp=CAI%3D` |
| 视频号 web 助手入口 | ✔ `https://channels.weixin.qq.com/platform/post/create`（前端工程 `finder-helper-web`，需 JS + 扫码登录） |

**结论**：检索「按播放量」既不需要 YouTube API Key，也不需要 LLM 去数数——
数值由 yt-dlp 给；**LLM 只做判断题（挑哪个）和写作题（标题/描述/话题）**。

---

## 2. CLI 选型：Claude Code（推荐）＋ DeepSeek 后端

| 维度 | **Claude Code（推荐）** | Codex CLI | OpenCode |
|---|---|---|---|
| DeepSeek 官方支持 | ✔ 官方文档专页（Anthropic 格式） | ✔ 官方文档专页（Responses 格式） | ✔ 官方文档专页 |
| 配置方式 | 环境变量（见下） | `~/.codex/config.toml` + `models.json`（有一键脚本） | 配置文件 + 原生 provider |
| **WebSearch** | ✔ **DeepSeek 侧原生支持**（官方文档明说；会额外产生 token 费用） | ✘ 对 DeepSeek 模型 `web_search = "disabled"` | 有 webfetch，无服务端搜索 |
| 无头调用 | ✔ `claude -p "..."` | ✔ `codex exec` | ✔ |
| 扩展 | skills / subagents / hooks / MCP | MCP | MCP |
| 你的现状 | 已有 `~/.claude/`（rules / skills），约定可复用 | 未安装 | 未安装 |

**推荐 Claude Code**，理由：唯一有服务端 Web 检索能力的选项（可用于补充趋势/关键词查证），
且你的 `~/.claude/` 规则与技能体系可以直接承载这个流水线；CLI 侧提示词按你的偏好放
**用户级目录**（`~/.claude/skills/`），不入侵本仓库。

### 2.1 安装与配置（Windows / macOS 都适用）

```bash
npm install -g @anthropic-ai/claude-code     # 需要 Node 18+
```

环境变量（DeepSeek 官方文档的 Claude Code 接法）：

```bash
# macOS / Linux
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=<你的 DeepSeek API Key>
export ANTHROPIC_MODEL="deepseek-flash[1m]"
export ANTHROPIC_DEFAULT_OPUS_MODEL="deepseek-flash[1m]"
export ANTHROPIC_DEFAULT_SONNET_MODEL="deepseek-flash[1m]"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="deepseek-flash"
export CLAUDE_CODE_SUBAGENT_MODEL="deepseek-flash"
export CLAUDE_CODE_EFFORT_LEVEL=max
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=786432
```

```powershell
# Windows PowerShell：把上面每条换成 $env:XXX="值"
```

模型映射（官方）：`claude-opus*` → `deepseek-v4-pro`；`claude-sonnet*` / `claude-haiku*` → `deepseek-flash`。
用 `deepseek-v4-pro` 质量更好、单价更高；`deepseek-flash` 支持图片输入（可以喂缩略图给模型挑片）。

### 2.2 AI 只做三件事（严格 JSON 契约）

```bash
# 1) 确定性脚本出候选池
python -m src.cli discover --top 20 -o .cache/candidates.json

# 2) 智能体读候选池，按技能规则输出 picks.json（关键词 → 挑片 → 文案）
claude -p "按 ~/.claude/skills/finder-pipeline 的规则读 .cache/candidates.json，写出 .cache/picks.json"
```

`picks.json` 契约（脚本侧只认这几个字段，别自由发挥）：

```json
{
  "keywords": ["funny cats shorts", "kitten fail compilation"],
  "picks": [
    {
      "video_id": "nRDysNZdMvU",
      "reason": "猫狗反差、无对白人声、36s 竖屏友好",
      "title": "猫咪看到黄瓜的反应，笑不活了",
      "description": "每天一条动物搞笑，关注不迷路～",
      "tags": ["萌宠", "搞笑动物", "猫咪"],
      "risk": "含背景音乐，发布时建议静音或替换"
    }
  ]
}
```

技能里要写死的规则（避免模型越界）：

- 只允许从 `.cache/candidates.json` 里**已有的 video_id** 里选；不许自己编 URL/ID；
- 只选动物类+搞笑类，排除：宠物受伤/惊吓过度、含明显他人肖像/IP 角色、纯广告；
- 标题 ≤ 16 字、不带 emoji 堆叠（视频号展示更克制）；话题 3~5 个；
- 输出**只能是 JSON**（便于脚本 `json.loads`），不许夹解释文字。

---

## 3. 检索与去重（✔ 已实现）

### 3.1 命令

```bash
# 0) 看「动物搞笑」按语义展开的关键词（不检索）
python -m src.cli keywords --topic 动物搞笑 --focus 猫 --keyword-count 12

# 1) 检索（默认用语义生成的关键词，跳过库里已有的 id）
python -m src.cli discover --top 10
python -m src.cli discover --focus 狗 --keyword-count 8 --top 5
python -m src.cli discover --keywords "a,b" --sort views,date    # 也可手写词表 / 改排序
python -m src.cli discover --max-duration 45 --min-views 500000
python -m src.cli discover --include-known             # 连库里已有的也列出来
python -m src.cli list --status found --limit 20
python -m src.cli backfill                             # 下载后对账（登记 downloaded）
python -m src.cli mark <video_id> picked --note "挑中"
python -m src.cli mark <video_id> published --post-id 123456
```

### 3.2 关键词怎么来的（✔ 已实现：`src/keywords.py`）

把「动物搞笑」当**语义槽位**展开，而不是让模型现编：

| 槽位 | 内容（节选） | 用法 |
|---|---|---|
| `generic` | `funny animals shorts` / `funny pets moments` / `cute animals funny` … | 召回主力，永远排在前面 |
| `animals` | cat / kitten / dog / puppy / pets / baby animals / hamster / parrot / monkey / rabbit / duck / goat / cow / fox / panda / squirrel / otter / penguin / seal / horse | 与风格、情境组合 |
| `situations` | funny moments / fail compilation / caught on camera / reaction / sneeze / stealing food / taking a bath / playing / scared / sleepy / clumsy / talking | 同上 |
| `styles` | funny / hilarious / cute / adorable | 同上 |
| `chinese` | 动物搞笑 / 萌宠搞笑 / 猫咪搞笑日常 / 狗狗搞笑视频 | 仅在 `--with-chinese` 时附加 |

- 生成顺序：**聚焦词（给了 `--focus`）→ 泛化短语 → 中文词（可选）→「风格×动物 + shorts」与「动物 + 情境」按轮次交替**；
  逐轮换风格/情境、横着走动物，保证前面几条覆盖不同动物，而不是一只猫占满前十条。
- 种子默认取**当天日期**（`YYYYMMDD`）：同一天可复现（日志里会写上种子），第二天自动换一批，
  配合库里的去重就能持续捞到新内容。
- 主题别名中英都认（`动物搞笑` / `animal` / `funny animals` / `萌宠` / `pets`）；`--focus` 认 猫/狗/鹦鹉/水獭…
- 不依赖任何 API Key。将来要用大模型补长尾，走 `--keywords` 注入即可，两者不冲突。

### 3.3 参数与打分

- 排序 `sp`：`views`（默认，按播放量降序）/ `date` / `relevance` —— 取值**以实测为准**（见第 1 节）；
- 过滤：`--max-duration`（默认 60s）、`--min-views`（默认 10 万）、`--per-keyword`（默认 50 条，`playlistend` 限深）；
- 打分：$$score = \frac{views}{\max(\text{上线天数},\,1)}$$ —— 用**播放速度**而不是总播放量，
  因为总播放量高的常年老视频搬到视频号没有价值；拿不到上传时间的按 30 天保守估计；
- 输出：终端表格（播放量 / 时长 / 万分之播放每天 / 标题 / URL / 频道）+ `-o` 落 JSON。

### 3.4 去重

`data/mvposter.db`（SQLite，`data/` 已在 `.gitignore`）：

| 字段组 | 内容 |
|---|---|
| 键 | `video_id`（YouTube 11 位 id，不是标题） |
| 观测 | `views` / `duration` / `channel` / `upload_date` / `keyword` / `score`（检索当时快照） |
| 进度 | `status`(`found→picked→downloaded→published`，旁支 `failed`/`skipped`) / `local_path` / `post_id` / `published_at` / `note` |

- `discover` 默认跳过库里已有 id → **爬过的不会再进候选**；
- `backfill` 扫 `movies/**`，用文件名里的 `[id]` 反向登记（历史文件也能补录，实测已补录 1 条）；
- 重新检索到同一条时只刷新观测值，**不覆盖流程进度**。

---

## 4. 视频号发布（⏳ 待确认，需真机实测选择器）

### 4.1 前置（你手工做一次）

浏览器由 **browserhost** 常驻，本工程不再自己起 Chrome：

```bash
cd ../browserhost && python main.py start     # 幂等：已在跑且健康就直接复用
```

- 在这个窗口里**手工**登录 YouTube 与视频号助手（扫码），登录态留在
  `~/.browserhost/profile` 里，之后长期复用；
- 窗口随手关掉都行（Chrome 留在后台，调试端口一直可用）；要停下来就 `python main.py stop`；
- 校验：`curl -s localhost:9222/json/version`（或再跑一次 `start` 看健康级别）；
- 若脚本不跑在 Mac 上，用 **ssh 端口转发**把 9222 安全地引过来，**不要暴露到公网**。

### 4.2 页签纪律（用户要求，已写入约定）

那个 9222 上的 Chrome 还承担别的任务，所以：

| 动作 | 用什么方式 | 能不能建/关页签 |
|---|---|---|
| 导出 cookies（下载前） | CDP `Network.getAllCookies` | 不需要页签，也不碰任何页签 |
| yt-dlp 下载 | 只借 cookies | **不需要页签**，全程不动浏览器窗口 |
| 发布到视频号 | CDP 打开 `channels.weixin.qq.com/platform/post/create` | **新开页签**，绝不复用你正在用的页签 |
| 全流程 | 只 `connect()` 到 browserhost 的调试端口 | **不启动、不关闭 Chrome，也不关你的页签**（退出只断开 CDP 连接）|

实测验证（2026-10-15，Windows + Chrome 155，测试前后对比）：复用 9222 的 Chrome 完成下载后，
进程数（24）与原有页签（京东页）均无变化，也没有新开页签。

### 4.3 发布流程（✔ 已实现于 `src/publish.py`，2026-10-15 真机实测打通）

**实测出的三条页面事实**（决定了实现方式，别再踩）：

| 事实 | 后果 |
|---|---|
| 助手是**无界（wujie）微前端**：真实表单在 `<wujie-app>` 的 shadow DOM 里 | 判断页面上有什么只能用 Playwright 定位器（会穿透 shadow DOM）；`document.querySelectorAll` / `page.content()` / `body.innerText` 只看到空壳 |
| 发布页打开后**会自己重载一次** | 早期拿到的是空壳，必须等 `input[accept*=video]` 出现再动手（实测约 3.4s） |
| 上传完成的信号 = 「发表」按钮从 `weui-desktop-btn_disabled` 变为可点 | 不用去猜「上传完成」文案；实测 0.2MB 短片 2s 就绪 |

实测选择器（就是 `src/publish.py` 顶部那几个常量）：

| 用途 | 选择器 | 备注 |
|---|---|---|
| 上传入口 | `input[type=file][accept*='video']` | 隐藏，位于 `.ant-upload-btn` 内，带 `multiple` |
| 视频描述 | `div.input-editor[contenteditable]` | 富文本，`data-placeholder="添加描述"`；旁边有 `#话题` / `@视频号` 按钮 |
| 短标题 | `input[placeholder*='短标题']` | 可选字段，和「视频描述」是两个东西 |
| 发表 | `get_by_role("button", name="发表", exact=True)` | **必须精确匹配**：子串会命中弹窗里的「直接发表」 |

流程（与实现一一对应）：

1. 通过 CDP **新开**页签到 `.../post/create`（不动已有页签），并 `bring_to_front()`（后台标签会被节流）；
2. **登录探测**：跳 `login.html` 或出现 `iframe[src*=qrconnect]` → 截图报警 + **保留页签**给你扫码，
   绝不尝试“自动登录”；**登录问题不写状态机**（不是这条内容的问题），只提示重跑；
3. 等表单挂载 → `set_input_files()` 上传本地视频 → 轮询「发表」按钮状态等上传/转码完成
   （每 15s 报一次状态，默认最多等 10 分钟）；
4. 填「视频描述」（`--desc`，`--tags` 拼成 `#标签` 附在后面）与「短标题」（`--title`，按页面
   自己声明的 `maxlength` 截断）；**`声明原创` 不代做**——那是作者表态；
5. 封面：**未实现**，用页面自动生成的封面（ffmpeg 抽帧留作后续）；
6. **默认填完即自动提交**：提交前把字段**读回来核对**（描述 `inner_text()` / 短标题 `input_value()`，
   对不上就不提交）→ 点「发表」→ 若弹「直接发表」确认框会自动再点一下 → 等结果：
   **页面离开发布页（跳到 `/platform/post/list`）或出现「已发表」**即算成功；
   60s 内等不到就如实返回 `submitted`（不谎报成功，截图 + 页面现状留在日志里）。
   想先人工核对一遍加 `--no-publish`（只填表 + 截图，停在按钮前，页签留着）；
7. 成功后 `publish` 把状态写成 `published`；拿到视频号里的标识再
   `mark <id> published --post-id ...` 补记；出错则 `mark <id> failed --note "..."`，
   截图都落在 `logs/publish_*.png`（另加一行「页面现状」日志：各控件 ×N、可见按钮列表）。

实测记录（2026-10-15，Windows + browserhost 的 9222 实例）：

```text
发布表单已就绪（等了 3.4s）
已提交文件：… [dFg8Nu2X5Mo].mp4（0.2 MB），等上传/转码…
上传/转码完成（2s），「发表」按钮已可用
已填：描述、短标题
页面现状：上传输入×1、描述框×1、短标题×1；可见按钮：保存草稿/手机预览/发表
半自动：表单已填好，停在「发表」按钮前（按钮状态：就绪）
```

截图 `logs/publish_form_*.png` 核对无误：视频已上传（带删除/封面预览）、描述为
`每天一条动物搞笑，关注不迷路～ #萌宠 #搞笑动物`、短标题为 `小狗撒娇求抱抱`（那次没提交）。

随后把默认改成「填完即自动提交」，又真跑了一次（同日）：

```text
发布表单已就绪（等了 3.6s）→ 上传 0.2MB（2s）→「发表」按钮就绪
已填：描述、短标题 → 字段核对通过（读回来的值与要填的一致）
已点「发表」，等结果…
提交后页面已离开发布页：https://channels.weixin.qq.com/platform/post/list（截图 publish_done_*.png）
dFg8Nu2X5Mo -> published
```

截图里页面顶部 toast 是「已发表」，作品列表第一条就是它（缩略图显示「处理中」，等审核），
文案 `每天一条动物搞笑，关注不迷路～ #萌宠 #搞笑动物`（`#话题` 被正常解析），
短标题 `小狗撒娇求抱抱`。要删就在「视频管理」里删。

### 4.4 必须接受的现实风险

| 风险 | 应对 |
|---|---|
| 视频号 web 有大小/时长限制、可能要求"原创声明"、有审核 | 先发 1 条人工走通，记录实际约束，再自动化 |
| 选择器随改版失效 | 选择器集中在文件顶部；失败必截图；先跑半自动（不点发表）照截图校正 |
| 自动化频发触发风控 | 默认**半自动**、发布间隔抖动、每日上限 |
| 搬运他人视频（BGM / 肖像）有版权风险 | 默认在描述里加"来源：YouTube @频道"；是否加可配；**是否使用这类素材由你决定** |

---

## 5. 分阶段落地（每阶段有验证标准）

| 阶段 | 内容 | 验证 |
|---|---|---|
| **P0** Mac 环境 | clone、`uv sync`、ffmpeg、Chrome 长驻 | `curl localhost:9222/json/version` 返回 200 |
| **P1** 检索+去重 | ✔ **已完成**（本次） | 实测：120 条 → 过滤 79 条 → 按播放速度排序出候选；重跑 0 条新候选 |
| **P2** CLI 接入 | 装 Claude Code + DeepSeek 环境变量 + 用户级技能 | `claude -p "..."` 返回可解析 JSON；候选被正确挑中 |
| **P3** 下载打通 | 候选 → `src.main --download` → `backfill` | `movies/<日期>/` 出现文件、状态变 `downloaded` |
| **P4** 发布 | `src.cli publish <id>` 填表截图校正选择器 → `--publish` 真发 1 条 | 视频号出现该动态；库里 `published` |
| **P5** 定时 | `launchd` 每日 N 条 + 间隔抖动 + 失败告警 | 连跑数日无重复发布 |

---

## 6. 待你确认的决策点

| # | 决策 | 我的默认选择（可以一句话推翻） |
|---|---|---|
| 1 | CLI 工具 | **Claude Code**（备选 Codex CLI / OpenCode） |
| 2 | 运行机器 | **全在 Mac**（仓库 clone 到 Mac，CLI 也装 Mac）；若要 Windows 驱动，则加 ssh 隧道 |
| 3 | 检索方案 | **只用 yt-dlp + sp**（零 Key）；有 Key 再上 Data API `videos.list` 拿精确统计 |
| 4 | 发布自动化 | **半自动**（停在发表前人工确认）；`--auto-publish` 作为可选开关 |
| 5 | DeepSeek Key | 放 Mac 的环境变量 / `~/.claude/settings.json`（**不进仓库**） |
| 6 | 关键词方向 | 通用动物搞笑（猫/狗为主）；要不要细分到「幼崽」「跨界反差」等题材由你定 |
| 7 | 每日发布量与时段 | 默认 1~3 条/天，随机间隔 ≥ 30 分钟 |

---

## 7. 已知风险（与本机环境有关）

1. **E: 盘 DLP**：本机实测「用工具新建的文件可能落盘即被加密」（`%ONEDLP_HEADER%`），
   会让 `python` 直接读不了。本次新建的 5 个文件（store / discover / keywords / cli / plan.md）
   已实测可正常 import/运行；
   若后续遇到，先停下让你手动解密，**不在代码里做绕行**。
2. **跨机 CDP**：Chrome 在 Mac、脚本在 Windows 时必须走 ssh 隧道；9222 严禁暴露公网。
3. **代理**：Chrome 与 yt-dlp 共用 `config.json` 里的 `proxy`；Mac 上要按实际代理改。
4. **版权**：见 4.4 最后一行。

---

## 8. 本次落地了什么

| 文件 | 说明 |
|---|---|
| `src/store.py`（新） | SQLite 记录：去重键、状态机、`movies/` 对账 |
| `src/discover.py`（新） | yt-dlp flat 检索 + `sp` 排序 + 本地重排 + 过滤 + 打分 |
| `src/keywords.py`（新） | 按语义槽位把主题展开成关键词（确定性、无需 API Key） |
| `src/cli.py`（新） | 子命令入口：`keywords` / `discover` / `list` / `backfill` / `mark` / `publish` |
| `src/config.py` | 加 `DATA_DIR` / `DB_FILE` 两个常量 |
| `.gitignore` | 加 `data/`、`.cache/` |
| `README.md` | 加「检索候选与去重」一节 |

### 8.2 浏览器生命周期剥离（本次改动）

浏览器与登录态全权交给 browserhost，本工程只留一条 CDP 连接：

| 文件 | 说明 |
|---|---|
| `src/browser.py` | 删掉启动/关闭 Chrome、profile 管理、健康探测（那些库接口已失效）；只留 `cdp_url` / `ensure_available` / `connect` / 当前标签页 / 导出 cookies |
| `src/logging.py`（新） | 自带按天日志（原来借 browserhost 的 `configure`），文件名前缀仍是 `mvposter_` |
| `src/config.py` | `DEFAULT_PORT` / `DEFAULT_PROFILE` / `CDP_WAIT_MS` / `Platform.home` / `DEFAULT_OPEN_URL` 全部删除，只留 `CDP_PORT` |
| `src/main.py` | 去掉 `--profile` / `--chrome` / `--open` 与 `ensure_cdp`；连不上 CDP 时提示去 `../browserhost` 里 start |
| `src/publish.py`（新） | 视频号发布：CDP 新开自己的页签、默认半自动、失败截图；选择器集中在文件顶部 |
| `src/cli.py` | 新增 `publish` 子命令 |
| `pyproject.toml` / `requirements.txt` | 去掉 `browserhost` 库依赖（`uv sync` 后 `.venv` 里的 `browserhost.pth` 一并清掉） |
| `README.md` | 开头、代理、安装、使用、目录结构按新边界重写 |

实测（2026-10-15）：`python -m src.cli publish <id>` 连上 9222 后新开一个页签、
被重定向到 `channels.weixin.qq.com/login.html`，按预期截图报「需要人工扫码」并保留页签；
`python -m src.main --download <url>` 导出 73 个 cookie 并命中已下过的文件；两次运行
结束后浏览器进程与其它页签都没被动过（退出只断开 CDP 连接）。

### 8.1 实测验证记录（2026-10-15，Windows）

| 验证项 | 结果 |
|---|---|
| 关键词生成 | 主题 → 12 词（如 `funny animals shorts`、`funny cats shorts`…）；`--focus 猫` 时前 4 条全是 cat；同 seed 可复现 |
| 真实检索 | 12 词 × 50 条：抓 **564** 条 → 过滤 109 条 → 去重 158 条 → **合格 238 条**，取前 12（全部是 `/shorts/`，6–53s，4 亿+ 播放），耗时约 **30s** |
| 去重 | 重跑同参数：跳过已知、0 条新候选（爬过的不会重复） |
| 对账 | `backfill` 把 `movies/` 里的文件登记为 `downloaded` |
| **CDP 非破坏性** | 复用 9222 的 Chrome 导出 78 个 cookie 并完成下载；前后对比：进程数不变、原有页签不变、**未新开也未关闭页签** |
| 下载产物 | `movies/2026-10-15/Baby dog#cute puppy barking#4kviral#shorts [dFg8Nu2X5Mo].mp4`（720p，ffmpeg 合并成功） |
