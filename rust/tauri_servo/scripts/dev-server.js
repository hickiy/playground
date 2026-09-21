// 开发期静态服务器：把 web/ 目录通过 HTTP 提供给 versoview。
//
// 与 src-tauri/tauri.conf.json 的 `build.devUrl` 配套：未启用 `custom-protocol` feature 时
// （即 `cargo run` 或 `npx tauri dev`），Tauri 让 webview 加载 devUrl 而不是嵌入资源，
// 于是改完前端只要刷新页面，不必重新编译。
//
// 用法：node scripts/dev-server.js [--port 1420]

const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const WEB_DIR = path.resolve(__dirname, '..', 'web');

const MIME_TYPES = {
  '.htm': 'text/html; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.png': 'image/png',
};

/** 解析 `--port`，默认 1420（与 tauri.conf.json 的 devUrl 保持一致）。 */
function resolvePort(argv) {
  const index = argv.indexOf('--port');
  const value = index >= 0 ? Number(argv[index + 1]) : NaN;
  return Number.isInteger(value) && value > 0 ? value : 1420;
}

/** 把请求路径映射到 web/ 下的文件；越界返回 null。 */
function resolveFile(urlPath) {
  const relative = decodeURIComponent(urlPath.split('?')[0]).replace(/^\/+/, '');
  const file = path.join(WEB_DIR, relative === '' ? 'index.htm' : relative);
  return file.startsWith(WEB_DIR + path.sep) ? file : null;
}

if (!fs.existsSync(WEB_DIR)) {
  console.error(`找不到 ${WEB_DIR}，请先运行 node scripts/build-web.js 生成页面。`);
  process.exit(1);
}

const port = resolvePort(process.argv.slice(2));

const server = http.createServer((request, response) => {
  const file = resolveFile(request.url || '/');
  console.log(`${request.method} ${request.url}`);

  if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    response.end(`404 ${request.url}`);
    return;
  }

  response.writeHead(200, {
    'content-type': MIME_TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream',
    // 开发服务器永远给最新内容，否则刷新后可能还是旧页面。
    'cache-control': 'no-store',
  });
  fs.createReadStream(file).pipe(response);
});

// 不指定 host：同时接受 IPv4/IPv6，避免 localhost 解析到另一族地址时连不上。
server.listen(port, () => {
  console.log(`dev server 已启动：http://localhost:${port}/`);
  console.log(`  根目录 ${WEB_DIR}`);
});
