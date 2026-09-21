// 页面源码：所有 .htm 的唯一真实来源。
//
// 三个页面共用同一套导航条与探测脚本，放在这里只维护一份模板，
// 由 scripts/build-web.js 生成 web/*.htm。
//
// 注意：web/*.css 与 web/*.js 是手写资源，不由本文件生成。

/** 所有页面共用的导航条。 */
const NAV = `<nav class="nav">
    <button type="button" data-page="index.htm">概览</button>
    <button type="button" data-page="compat.htm">兼容性矩阵</button>
    <button type="button" data-page="metrics.htm">运行时指标</button>
  </nav>`;

const FOOTER = `<footer class="foot"><span id="foot-note">正在初始化…</span></footer>`;

/** 概览页：探测当前引擎能力并渲染成卡片。 */
const INDEX = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Servo 探索台 · 概览</title>
<link rel="stylesheet" href="style.css" />
</head>
<body>
<div id="app">
  <header class="hero">
    <div>
      <p class="eyebrow">Early exploration</p>
      <h1>Tauri &times; Servo 探索台</h1>
      <p class="sub">同一个 Tauri 外壳，把渲染引擎从 WebView2 换成 Servo（via Verso runtime）。</p>
    </div>
    <span class="badge" id="runtime-badge">检测中…</span>
  </header>
  ${NAV}
  <section class="grid" id="cards">
    <p class="loading">正在探测当前引擎能力…</p>
  </section>
  ${FOOTER}
</div>
<script src="common.js"></script>
<script src="probes.js"></script>
<script src="app.js"></script>
</body>
</html>
`;

/** 兼容性矩阵页：逐项检测 Web 平台特性，支持过滤与导出。 */
const COMPAT = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Servo 探索台 · 兼容性矩阵</title>
<link rel="stylesheet" href="style.css" />
</head>
<body>
<div id="app">
  <header class="hero">
    <div>
      <p class="eyebrow">Compatibility</p>
      <h1>Web 兼容性矩阵</h1>
      <p class="sub">同一份检测代码会在 Servo 与 WebView2 下分别运行，用于量化两者的能力差距。</p>
    </div>
    <span class="badge" id="runtime-badge">检测中…</span>
  </header>
  ${NAV}

  <section class="toolbar">
    <input id="filter" type="search" placeholder="按名称或分组过滤…" />
    <span class="pill ok" id="stat-ok">通过 0</span>
    <span class="pill warn" id="stat-warn">部分 0</span>
    <span class="pill bad" id="stat-bad">不支持 0</span>
    <span class="spacer"></span>
    <button type="button" id="btn-rerun">重新探测</button>
    <button type="button" id="btn-copy">复制 JSON</button>
  </section>

  <section class="card">
    <div id="compat-list"></div>
  </section>

  ${FOOTER}
</div>
<script src="common.js"></script>
<script src="probes.js"></script>
<script src="compat.js"></script>
</body>
</html>
`;

/** 指标页：展示宿主侧与引擎侧的运行时信息，供人工核对与排查。 */
const METRICS = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Servo 探索台 · 运行时指标</title>
<link rel="stylesheet" href="style.css" />
</head>
<body>
<div id="app">
  <header class="hero">
    <div>
      <p class="eyebrow">Metrics</p>
      <h1>运行时指标</h1>
      <p class="sub">页面侧可观测到的数据。打包体积、冷启动耗时、进程内存由 scripts/bench.js 在外部采集。</p>
    </div>
    <span class="badge" id="runtime-badge">检测中…</span>
  </header>
  ${NAV}

  <section class="toolbar">
    <button type="button" id="btn-refresh">刷新</button>
    <button type="button" id="btn-copy">复制 JSON</button>
    <span class="spacer"></span>
    <span class="pill" id="stat-done">—</span>
  </section>

  <section class="grid" id="cards">
    <p class="loading">正在采集…</p>
  </section>

  ${FOOTER}
</div>
<script src="common.js"></script>
<script src="probes.js"></script>
<script src="metrics.js"></script>
</body>
</html>
`;

module.exports = {
  'index.htm': INDEX,
  'compat.htm': COMPAT,
  'metrics.htm': METRICS,
};
