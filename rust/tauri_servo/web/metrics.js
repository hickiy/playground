// 运行时指标页：展示页面侧与宿主侧可观测到的数据。
//
// 注意：打包体积、冷启动耗时、进程内存属于「应用外部」的指标，
// 由 scripts/bench.js 从外部测量，页面里看不到，也不应该伪造。

/** 取导航计时数据。 */
function navigationTiming() {
  const entries = performance.getEntriesByType ? performance.getEntriesByType('navigation') : [];
  if (!entries || entries.length === 0) return null;
  const nav = entries[0];
  return {
    '重定向耗时': Math.round(nav.redirectEnd - nav.redirectStart),
    'DNS 耗时': Math.round(nav.domainLookupEnd - nav.domainLookupStart),
    '连接耗时': Math.round(nav.connectEnd - nav.connectStart),
    '请求到首字节': Math.round(nav.responseStart - nav.requestStart),
    '响应下载': Math.round(nav.responseEnd - nav.responseStart),
    'DOMContentLoaded': Math.round(nav.domContentLoadedEventEnd - nav.startTime),
    'load 事件': Math.round(nav.loadEventEnd - nav.startTime),
    '导航类型': nav.type || '—',
  };
}

/** 页面可见前的耗时，可近似看作「引擎启动 + 文档解析」的时间。 */
function bootCost() {
  return {
    '脚本开始执行': Math.round((performance.timeOrigin ? Date.now() - performance.timeOrigin : 0) * 100) / 100,
    'performance.now()': Math.round((performance.now ? performance.now() : 0) * 100) / 100,
    'timeOrigin': performance.timeOrigin ? new Date(performance.timeOrigin).toISOString() : '—',
  };
}

/** Windows 上的测量方式说明，避免使用者误以为页面能拿到进程内存。 */
const MEMORY_HINT = '进程内存（工作集 / 私有字节）请用 scripts/bench.js 从外部测量；页面侧只能拿到引擎自报的数据。';

/** 采集全部指标。 */
async function collect() {
  const info = await invokeHost('get_app_info');

  const host = {
    'Tauri 命令可用': info === null ? '否（非 Tauri 环境）' : info && info.error ? '调用失败：' + info.error : '是',
  };
  if (info && !info.error) {
    host['应用名'] = info.name;
    host['应用版本'] = info.version;
    host['Tauri 版本'] = info.tauriVersion;
    host['构建类型'] = info.profile;
    host['目标平台'] = info.target;
    host['可执行文件'] = info.exePath;
    host['Verso 二进制'] = info.versoPath || '（未启用 externalBin）';
    host['DevTools 端口'] = info.devtoolsPort === 0 ? '未启用' : String(info.devtoolsPort);
    host['报告模式'] = info.reportMode ? '是' : '否';
  }

  const screen_info = {
    '设备像素比': window.devicePixelRatio,
    '屏幕分辨率': screen.width + '×' + screen.height,
    '可用区域': screen.availWidth + '×' + screen.availHeight,
    '视口尺寸': window.innerWidth + '×' + window.innerHeight,
    '色深': screen.colorDepth + ' bit',
    '用户语言': navigator.language,
    '时区': safe(() => Intl.DateTimeFormat().resolvedOptions().timeZone, '—'),
    '在线状态': navigator.onLine ? '在线' : '离线',
  };

  const clientReport = runAllProbes();

  return {
    kind: 'metrics',
    collectedAt: new Date().toISOString(),
    runtime: clientReport.runtime,
    userAgent: navigator.userAgent,
    sections: [
      { title: '宿主信息', rows: host },
      { title: '启动与导航耗时 (ms)', rows: bootCost() },
      { title: '导航计时', rows: navigationTiming() || { '说明': '当前引擎未提供 navigation timing' } },
      { title: '显示与本地化', rows: screen_info },
    ],
    notes: [MEMORY_HINT],
  };
}

/** 把采集结果渲染成卡片。 */
function render(report) {
  const host = document.getElementById('cards');
  host.textContent = '';

  for (const section of report.sections) {
    const card = document.createElement('section');
    card.className = 'card';

    const heading = document.createElement('h2');
    heading.textContent = section.title;
    card.appendChild(heading);

    for (const [key, value] of Object.entries(section.rows || {})) {
      const row = document.createElement('div');
      row.className = 'row';

      const k = document.createElement('span');
      k.className = 'k';
      k.textContent = key;

      const v = document.createElement('span');
      v.className = 'v';
      v.textContent = value === null || value === undefined ? '—' : String(value);

      row.appendChild(k);
      row.appendChild(v);
      card.appendChild(row);
    }
    host.appendChild(card);
  }

  document.getElementById('stat-done').textContent = '采集完成 ' + new Date().toLocaleTimeString();
  document.getElementById('foot-note').textContent = MEMORY_HINT;
  window.__REPORT__ = report;
}

document.addEventListener('DOMContentLoaded', async () => {
  initChrome('运行时指标');

  let report = await collect();
  render(report);

  document.getElementById('btn-refresh').addEventListener('click', async () => {
    report = await collect();
    render(report);
  });

  document.getElementById('btn-copy').addEventListener('click', async () => {
    const ok = await copyText(JSON.stringify(report, null, 2));
    document.getElementById('stat-done').textContent = ok ? '已复制 JSON' : '复制失败';
  });
});
