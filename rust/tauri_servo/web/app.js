// 概览页：只呈现「结论」——通过率、引擎身份，以及各分组的差距清单。
// 完整逐项列表在 compat.htm，两页共用 probes.js，避免维护两份数据。

/** 创建一个带标题的卡片。 */
function makeCard(title) {
  const card = document.createElement('section');
  card.className = 'card';

  const heading = document.createElement('h2');
  heading.textContent = title;
  card.appendChild(heading);

  return card;
}

/** 追加一行「键 / 值」。 */
function addRow(card, key, value, state) {
  const row = document.createElement('div');
  row.className = 'row';

  const k = document.createElement('span');
  k.className = 'k';
  k.textContent = key;

  const v = document.createElement('span');
  v.className = 'v' + (state ? ' ' + state : '');
  v.textContent = value;

  row.appendChild(k);
  row.appendChild(v);
  card.appendChild(row);
}

/** 渲染整页。 */
function renderOverview(report) {
  const counts = summarize(report);
  const host = document.getElementById('cards');
  host.textContent = '';

  const summary = makeCard('探测汇总');
  addRow(summary, '运行环境', report.runtime);
  addRow(summary, '通过', String(counts.ok), 'ok');
  addRow(summary, '部分支持', String(counts.warn), counts.warn > 0 ? 'warn' : '');
  addRow(summary, '不支持', String(counts.bad), counts.bad > 0 ? 'bad' : '');
  addRow(summary, '探测耗时', report.durationMs + ' ms');
  host.appendChild(summary);

  const identity = makeCard('引擎身份');
  for (const row of report.results.filter((r) => r.group === '引擎身份' && r.kind === 'value')) {
    addRow(identity, row.name, String(row.value));
  }
  host.appendChild(identity);

  // 差距清单：只列没通过的项目 —— 这才是早期探索真正要盯的信息。
  for (const { group } of PROBE_GROUPS) {
    if (group === '引擎身份') continue;

    const rows = report.results.filter((r) => r.group === group && r.kind === 'support');
    const failed = rows.filter((r) => r.state !== 'ok');

    const card = makeCard(group + '（' + (rows.length - failed.length) + '/' + rows.length + ' 通过）');
    if (failed.length === 0) {
      const all = document.createElement('p');
      all.className = 'loading';
      all.textContent = '全部通过';
      card.appendChild(all);
    } else {
      for (const row of failed) {
        const isPartial = row.state === 'warn';
        addRow(card, row.name, isPartial ? row.note || '部分支持' : '不支持', isPartial ? 'warn' : 'bad');
      }
    }
    host.appendChild(card);
  }

  window.__REPORT__ = report;
}

document.addEventListener('DOMContentLoaded', () => {
  initChrome('概览');

  const report = runAllProbes();
  renderOverview(report);

  document.getElementById('foot-note').textContent =
    '通过 ' + summarize(report).ok + ' 项 · 完整逐项矩阵见 compat.htm';

  document.getElementById('btn-reload').addEventListener('click', () => {
    const fresh = runAllProbes();
    renderOverview(fresh);
    document.getElementById('foot-note').textContent =
      '通过 ' + summarize(fresh).ok + ' 项 · 完整逐项矩阵见 compat.htm';
  });
});
