// 生成 web/*.htm：把 web-src/pages.js 中的页面字符串写到磁盘。
//
// 用法：node scripts/build-web.js

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'web');

function main() {
  const pages = require(path.join(ROOT, 'web-src', 'pages.js'));

  fs.mkdirSync(OUT_DIR, { recursive: true });

  const startedAt = process.hrtime.bigint();
  let total = 0;

  for (const [name, html] of Object.entries(pages)) {
    const bytes = Buffer.byteLength(html, 'utf8');
    fs.writeFileSync(path.join(OUT_DIR, name), html, 'utf8');
    total += bytes;
    console.log(`  生成 ${name.padEnd(14)} ${String(bytes).padStart(6)}B`);
  }

  const elapsedMs = Number(process.hrtime.bigint() - startedAt) / 1e6;
  console.log(`\n共 ${Object.keys(pages).length} 个页面，${total} 字节，耗时 ${elapsedMs.toFixed(1)} ms。`);
}

main();
