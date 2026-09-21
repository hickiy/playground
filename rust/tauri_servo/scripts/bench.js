// 指标采集：冷启动、内存占用、体积、构建/重载耗时，并汇总成报告。
//
// 采集口径（重要，避免不同次运行不可比）：
//   冷启动   —— 宿主进程入口 -> 页面脚本执行完毕并回传报告 的耗时（由宿主自行计时）
//   内存     —— 进程树（宿主 + versoview）的工作集之和，在应用驻留期间采样
//   体积     —— 可执行文件 + versoview（Servo 引擎以独立进程提供，必须一并计入）
//   构建耗时 —— cargo 增量编译；重载耗时 —— 前端重建 + 冷启动
//
// 用法：
//   node scripts/bench.js                 # 用 debug 产物测，跑得快
//   node scripts/bench.js --release       # 先构建并测量 release 产物
//   node scripts/bench.js --runs 5        # 调整采样次数
//   node scripts/bench.js --bundle        # 额外调用 tauri CLI 打包，测量安装包体积

const { execFileSync, spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const SRC_TAURI = path.join(ROOT, 'src-tauri');
const DOCS = path.join(ROOT, 'docs');

const STARTUP_MARK = '___VERSO_STARTUP_MS___';
const REPORT_BEGIN = '___VERSO_REPORT_BEGIN___';
const REPORT_END = '___VERSO_REPORT_END___';

/** 解析命令行参数。 */
function parseArgs(argv) {
  const options = { release: false, runs: 3, bundle: false, hold: 4000, compatOnly: false };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--release') options.release = true;
    else if (arg === '--bundle') options.bundle = true;
    else if (arg === '--compat-only') options.compatOnly = true;
    else if (arg === '--runs') options.runs = Number(argv[i + 1]) || options.runs;
    else if (arg === '--hold') options.hold = Number(argv[i + 1]) || options.hold;
  }
  return options;
}

/** 同步执行命令并计时，返回 { ms, ok, output }。 */
function runTimed(file, args, options = {}) {
  const startedAt = Date.now();
  try {
    const output = execFileSync(file, args, {
      cwd: options.cwd || ROOT,
      encoding: 'utf8',
      stdio: options.quiet ? ['ignore', 'pipe', 'pipe'] : 'inherit',
      shell: false,
    });
    return { ms: Date.now() - startedAt, ok: true, output: output || '' };
  } catch (err) {
    return { ms: Date.now() - startedAt, ok: false, output: String(err.message || err) };
  }
}

/** 用 PowerShell 查询进程树的工作集之和（字节）。 */
function sampleMemoryBytes(processNames) {
  const command =
    `$p = Get-Process -Name ${processNames.join(',')} -ErrorAction SilentlyContinue; ` +
    'if ($p) { ($p | Measure-Object -Property WorkingSet64 -Sum).Sum } else { 0 }';

  try {
    const output = execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', command], {
      encoding: 'utf8',
    });
    return Number(String(output).trim()) || 0;
  } catch (err) {
    return 0;
  }
}

/** 启动应用、抓取报告、并在驻留期间采样内存。 */
function runOnce(exePath, holdMs) {
  return new Promise((resolve) => {
    const startedAt = Date.now();
    const child = spawn(exePath, ['--compat-report', '--hold-ms', String(holdMs)], {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    let memoryPeak = 0;
    let memorySamples = 0;
    let memoryTimer = null;

    const stopSampling = () => {
      if (memoryTimer) {
        clearInterval(memoryTimer);
        memoryTimer = null;
      }
    };

    // 报告一回来就开始采样内存，等应用退出后停止。
    const startSampling = () => {
      memoryTimer = setInterval(() => {
        const bytes = sampleMemoryBytes(['tauri-servo-lab', 'versoview-x86_64-pc-windows-msvc']);
        if (bytes > 0) {
          memoryPeak = Math.max(memoryPeak, bytes);
          memorySamples += 1;
        }
      }, 300);
    };

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString('utf8');
      if (!memoryTimer && stdout.includes(REPORT_BEGIN)) startSampling();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
    });

    child.on('close', () => {
      stopSampling();

      const startupMatch = stdout.match(new RegExp(`${STARTUP_MARK}\\s+([\\d.]+)`));
      const json = stdout.split(REPORT_BEGIN)[1]?.split(REPORT_END)[0]?.trim();

      resolve({
        totalMs: Date.now() - startedAt,
        startupMs: startupMatch ? Number(startupMatch[1]) : null,
        memoryBytes: memoryPeak,
        memorySamples,
        report: json ? safeParse(json) : null,
        stderr,
      });
    });
  });
}

/** 解析 JSON，失败返回 null 而不是抛错。 */
function safeParse(text) {
  try {
    return JSON.parse(text);
  } catch (err) {
    return null;
  }
}

/** 求最小值 / 中位数。 */
function stats(values) {
  const valid = values.filter((v) => typeof v === 'number' && v > 0).sort((a, b) => a - b);
  if (valid.length === 0) return { min: null, median: null };
  return { min: valid[0], median: valid[Math.floor(valid.length / 2)] };
}

/** 人类可读的体积。 */
function mb(bytes) {
  return bytes === null || bytes === undefined ? '—' : (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

/** 读取文件体积，不存在返回 null。 */
function sizeOf(file) {
  try {
    return fs.statSync(file).size;
  } catch (err) {
    return null;
  }
}

/** 查找目录中体积最大的匹配文件（用于定位安装包）。 */
function findInstaller(dir, pattern) {
  try {
    return fs
      .readdirSync(dir)
      .filter((name) => pattern.test(name))
      .map((name) => path.join(dir, name))
      .map((file) => ({ file, size: sizeOf(file) }))
      .filter((entry) => entry.size !== null)
      .sort((a, b) => b.size - a.size)[0];
  } catch (err) {
    return undefined;
  }
}

/** 写文本文件（自动建父目录），返回 { file } 便于打印出处。 */
function writeDoc(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, 'utf8');
  return { file };
}

/** 由兼容性报告生成 Markdown 矩阵。 */
function compatMarkdown(report) {
  if (!report) return '# 兼容性矩阵\n\n未采集到数据。\n';

  const groups = new Map();
  for (const row of report.results) {
    if (!groups.has(row.group)) groups.set(row.group, []);
    groups.get(row.group).push(row);
  }

  const lines = [
    '# Web 兼容性矩阵（Servo / Verso）',
    '',
    `- 采集时间：${report.collectedAt}`,
    `- 引擎：${report.runtime}`,
    `- User-Agent：\`${report.userAgent}\``,
    `- 页内探测耗时：${report.durationMs} ms`,
    '',
    '状态说明：`通过` = 支持，`部分` = 有限支持，`不支持` = 缺失。',
    '',
  ];

  // 先给结论：通过率与未通过清单，避免读者在长表里自己数。
  const support = report.results.filter((row) => row.kind === 'support');
  const counts = { ok: 0, warn: 0, bad: 0 };
  for (const row of support) counts[row.state] += 1;

  const unsupported = support.filter((row) => row.state !== 'ok');
  lines.push('## 汇总', '');
  lines.push(
    `- 支持度探测项 ${support.length} 项：通过 ${counts.ok} / 部分 ${counts.warn} / 不支持 ${counts.bad}` +
      `（通过率 ${support.length ? ((counts.ok / support.length) * 100).toFixed(1) : '0'}%）`
  );
  lines.push(`- 未通过 ${unsupported.length} 项，清单如下`);
  lines.push('');
  for (const row of unsupported) {
    lines.push(`- ${row.group} / ${row.name}${row.note ? '（' + row.note + '）' : ''}`);
  }
  lines.push('');

  for (const [group, rows] of groups) {
    lines.push(`## ${group}`, '');
    lines.push('| 项目 | 状态 | 备注 |');
    lines.push('| --- | --- | --- |');
    for (const row of rows) {
      const status = row.kind === 'value' ? '取值' : row.state === 'ok' ? '通过' : row.state === 'warn' ? '部分' : '不支持';
      const note = row.kind === 'value' ? String(row.value) : row.note || '';
      lines.push(`| ${row.name} | ${status} | ${note.replace(/\|/g, '\\|')} |`);
    }
    lines.push('');
  }
  return lines.join('\n');
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const profile = options.release ? 'release' : 'debug';
  const exePath = path.join(SRC_TAURI, 'target', profile, 'tauri-servo-lab.exe');

  console.log(`== 采集目标：${profile} ==\n`);

  // 1) 前端重建耗时
  console.log('-- 前端重建 --');
  const webBuild = runTimed(process.execPath, ['scripts/build-web.js'], { cwd: ROOT, quiet: true });
  const webBuildMs = webBuild.output.match(/耗时\s*([\d.]+)\s*ms/);
  console.log(`  build-web.js: ${webBuild.ok ? (webBuildMs ? webBuildMs[1] + ' ms' : webBuild.ms + ' ms') : '失败'}\n`);

  // 只刷新兼容性矩阵时，直接复用已有构建产物，不触发重新编译。
  if (options.compatOnly) {
    console.log('-- 仅采集兼容性矩阵 --');
    const result = await runOnce(exePath, options.hold);
    const compatJsonOnly = writeDoc(
      path.join(DOCS, 'compat-report.json'),
      JSON.stringify(result.report, null, 2)
    );
    const compatMdOnly = writeDoc(path.join(DOCS, 'compat-matrix.md'), compatMarkdown(result.report));

    const support = (result.report?.results || []).filter((row) => row.kind === 'support');
    const passed = support.filter((row) => row.state === 'ok').length;
    console.log(`  支持度探测 ${support.length} 项，通过 ${passed} 项`);
    console.log(`  已写入 ${path.relative(ROOT, compatMdOnly.file)}`);
    console.log(`  已写入 ${path.relative(ROOT, compatJsonOnly.file)}`);
    return;
  }

  // 2) 后端重编耗时：先改动源码再计时，得到真实开发循环里的数字。
  //    （空构建很快，但那只测到「无需重编」，没有参考价值。）
  console.log('-- 后端重编耗时 --');
  const mainRs = path.join(SRC_TAURI, 'src', 'main.rs');
  const now = new Date();
  fs.utimesSync(mainRs, now, now); // 只更新时间戳，内容不变

  const buildArgs = ['build', '--manifest-path', path.join(SRC_TAURI, 'Cargo.toml')];
  if (options.release) buildArgs.push('--release');
  // 固定用 custom-protocol 构建：前端资源改为编译期嵌入，与 `tauri build` 的发布形态一致。
  // 否则产物处于开发模式，页面要经 devUrl 静态服务器加载，没起服务器时会白屏并一直等待报告。
  buildArgs.push('--features', 'custom-protocol');
  const build = runTimed('cargo', buildArgs, { quiet: true });
  console.log(`  cargo build (${profile}，改动 main.rs 后): ${build.ok ? build.ms + ' ms' : '失败'}\n`);

  if (!build.ok) {
    console.error(build.output);
    process.exit(1);
  }

  // 3) 冷启动 + 内存
  console.log(`-- 冷启动与内存（${options.runs} 次）--`);
  const runs = [];
  for (let i = 0; i < options.runs; i += 1) {
    const result = await runOnce(exePath, options.hold);
    runs.push(result);
    console.log(
      `  第 ${i + 1} 次：启动 ${result.startupMs ?? '—'} ms · 内存 ${mb(result.memoryBytes)}（${result.memorySamples} 次采样）`
    );
  }
  console.log('');

  const startup = stats(runs.map((r) => r.startupMs));
  const memory = stats(runs.map((r) => r.memoryBytes));

  // 4) 体积
  const appSize = sizeOf(exePath);
  const versoviewSize = sizeOf(
    path.join(SRC_TAURI, 'versoview', 'versoview-x86_64-pc-windows-msvc.exe')
  );
  const bundleDir = path.join(SRC_TAURI, 'target', 'release', 'bundle', 'nsis');
  const installer = findInstaller(bundleDir, /\.exe$/i);

  // 5) 产出报告
  const latestReport = runs.map((r) => r.report).find(Boolean) || null;
  const compatJson = writeDoc(path.join(DOCS, 'compat-report.json'), JSON.stringify(latestReport, null, 2));
  const compatMd = writeDoc(path.join(DOCS, 'compat-matrix.md'), compatMarkdown(latestReport));

  const lines = [
    '# 指标报告（Tauri + Servo / Verso）',
    '',
    `- 采集时间：${new Date().toISOString()}`,
    `- 构建类型：\`${profile}\``,
    `- 采样次数：${options.runs}`,
    `- 平台：Windows / x86_64-pc-windows-msvc`,
    '',
    '## 体积',
    '',
    '| 项目 | 体积 | 说明 |',
    '| --- | --- | --- |',
    `| 宿主可执行文件 | ${mb(appSize)} | ${appSize ? path.relative(ROOT, exePath) : '未找到'} |`,
    `| Servo 引擎进程 | ${mb(versoviewSize)} | versoview，以独立进程提供 |`,
    `| 合计（未打包） | ${mb((appSize || 0) + (versoviewSize || 0))} | 两者相加 |`,
    `| 安装包 (NSIS) | ${installer ? mb(installer.size) : '未生成'} | ${installer ? path.relative(ROOT, installer.file) : '运行 node scripts/bench.js --bundle 生成'} |`,
    '',
    '## 冷启动耗时',
    '',
    '口径：宿主进程入口 → 页面脚本执行完毕并回传报告。包含窗口创建、versoview 启动、页面加载与脚本执行。',
    '',
    '| 指标 | 值 |',
    '| --- | --- |',
    `| 最快 | ${startup.min ?? '—'} ms |`,
    `| 中位数 | ${startup.median ?? '—'} ms |`,
    `| 逐次结果 | ${runs.map((r) => (r.startupMs ?? '—') + ' ms').join(' / ')} |`,
    '',
    '## 内存占用',
    '',
    '口径：采集期间「宿主 + versoview」进程树工作集之和的峰值。',
    '',
    '| 指标 | 值 |',
    '| --- | --- |',
    `| 最大 | ${mb(runs.reduce((max, r) => Math.max(max, r.memoryBytes), 0))} |`,
    `| 最小 | ${mb(memory.min)} |`,
    `| 逐次峰值 | ${runs.map((r) => mb(r.memoryBytes)).join(' / ')} |`,
    '',
    '## 构建与重载耗时',
    '',
    '| 项目 | 耗时 | 说明 |',
    '| --- | --- | --- |',
    `| 前端页面重建 | ${webBuildMs ? webBuildMs[1] + ' ms' : webBuild.ms + ' ms'} | scripts/build-web.js 生成全部 .htm |`,
    `| 后端重编 | ${build.ms} ms | 改动 src/main.rs 后 cargo build --${profile}，含重新链接 |`,
    `| 改动生效（推导） | ${startup.median !== null && webBuildMs ? Math.round(Number(webBuildMs[1]) + startup.median) + ' ms' : '—'} | 前端重建 + 冷启动，当前没有 HMR |`,
    '',
    '## 已知缺口',
    '',
    '- **热重载未实现**：当前 `frontendDist` 直接指向源码目录，没有接 `devUrl` 开发服务器，',
    '  所以改完前端需要「重建 + 重启应用」。要补上真正的 HMR，需要引入本地静态服务并把',
    '  `build.devUrl` 指过去。',
    '- **WebGL / WebGPU 缺失**：Servo 当前构建在该环境下未提供，涉及图形密集的界面要提前评估。',
    '- **安全限制**：tauri-runtime-verso 硬编码了自定义协议 IPC 的 `Origin`，因此不要用它加载任意外部网站。',
    '',
  ];

  const metrics = writeDoc(path.join(DOCS, 'metrics.md'), lines.join('\n'));

  console.log('== 结果 ==');
  console.log(`  宿主体积      ${mb(appSize)}`);
  console.log(`  Servo 体积    ${mb(versoviewSize)}`);
  console.log(`  安装包        ${installer ? mb(installer.size) : '未生成（加 --bundle）'}`);
  console.log(`  冷启动(中位)  ${startup.median ?? '—'} ms`);
  console.log(`  内存峰值      ${mb(runs.reduce((max, r) => Math.max(max, r.memoryBytes), 0))}`);
  console.log(`  后端重编      ${build.ms} ms`);
  console.log('');
  console.log(`  已写入 ${path.relative(ROOT, metrics.file)}`);
  console.log(`  已写入 ${path.relative(ROOT, compatMd.file)}`);
  console.log(`  已写入 ${path.relative(ROOT, compatJson.file)}`);
}

main();
