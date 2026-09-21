// 兼容性矩阵页：完整逐项列表 + 过滤 + 导出 JSON。
//
// 自动化模式：当 URL 带 report=1（由宿主以 --compat-report 启动时注入）时，
// 采集完成后立刻把结果回传给宿主并退出，供 scripts/bench.js 收集。

/** 当前采集到的完整报告。 */
let currentReport = null;

/** 渲染状态药丸。 */
function statePill(state, note) {
  const el = document.createElement('span');
  el.className = 'pill ' + (state === 'ok' ? 'ok' : state === 'warn' ? 'warn' : state === 'bad' ? 'bad' : '');

  if (state === 'ok') el.textContent = '通过';
  else if (state === 'bad') el.textContent = '不支持';
  else if (state === 'warn') el.textContent = note ? '部分：' + note : '部分';
  else el.textContent = note || '—';

  return el;
}

/** 渲染完整矩阵。 */
function renderMatrix(report, filterText) {
  const host = document.getElementById('compat-list');
  host.textContent = '';

  const needle = String(filterText || '').trim().toLowerCase();
  let shown = 0;

  for (const { group } of PROBE_GROUPS) {
    const rows = report.results.filter((r) => r.group === group);
    const matched = needle
      ? rows.filter((r) => (r.group + ' ' + r.name + ' ' + r.value).toLowerCase().includes(needle))
      : rows;

    if (matched.length === 0) continue;

    const header = document.createElement('div');
    header.className = 'group';
    header.textContent = group + ' · ' + matched.length + ' 项';
    host.appendChild(header);

    for (const row of matched) {
      const item = document.createElement('div');
      item.className = 'item';

      const name = document.createElement('span');
      name.className = 'name';
      name.textContent = row.name;

      const value = document.createElement('span');
      value.className = 'value';
      value.textContent = row.kind === 'value' ? String(row.value) : '';
      value.title = row.kind === 'value' ? String(row.value) : '';

      item.appendChild(name);
      item.appendChild(value);
      item.appendChild(statePill(row.state, row.note));
      host.appendChild(item);
      shown += 1;
    }
  }

  if (shown === 0) {
    const empty = document.createElement('p');
    empty.className = 'loading';
    empty.textContent = '没有匹配「' + filterText + '」的项目';
    host.appendChild(empty);
  }

  document.getElementById('foot-note').textContent =
    '显示 ' + shown + ' / ' + report.results.length + ' 项 · 采集耗时 ' + report.durationMs + ' ms';
}

/** 刷新统计药丸。 */
function refreshStats(report) {
  const counts = summarize(report);
  document.getElementById('stat-ok').textContent = '通过 ' + counts.ok;
  document.getElementById('stat-warn').textContent = '部分 ' + counts.warn;
  document.getElementById('stat-bad').textContent = '不支持 ' + counts.bad;
}

/** 重新采集并渲染。 */
function rerun() {
  currentReport = runAllProbes();
  window.__REPORT__ = currentReport;
  refreshStats(currentReport);
  renderMatrix(currentReport, document.getElementById('filter').value);
  return currentReport;
}

/** 处于自动化模式时，把报告回传宿主。 */
async function maybeReportBack(report) {
  const automated = window.location.search.indexOf('report=1') !== -1;
  if (!automated) return;

  document.getElementById('foot-note').textContent = '自动化模式：正在回传报告…';
  const result = await invokeHost('submit_report', {
    kind: 'compat',
    payload: JSON.stringify(report),
  });
  document.getElementById('foot-note').textContent = '自动化模式：回传完成 ' + JSON.stringify(result);
}

document.addEventListener('DOMContentLoaded', () => {
  initChrome('兼容性矩阵');

  const report = rerun();

  document.getElementById('filter').addEventListener('input', (event) => {
    renderMatrix(currentReport, event.target.value);
  });

  document.getElementById('btn-rerun').addEventListener('click', () => {
    rerun();
  });

  document.getElementById('btn-copy').addEventListener('click', async () => {
    const ok = await copyText(JSON.stringify(currentReport, null, 2));
    document.getElementById('foot-note').textContent = ok ? '已复制 JSON 到剪贴板' : '复制失败，请手动选取';
  });

  maybeReportBack(report);
});
