const express = require('express');
const path = require('path');
const app = express();
const port = 5500;

// 设置静态文件目录
app.use('/static', express.static(path.join(__dirname, 'static')));

// 设置CORS头部
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
  if (req.method === 'OPTIONS') {
    res.sendStatus(200);
  } else {
    next();
  }
});

// 根路径重定向到PDF查看器
app.get('/', (req, res) => {
  res.redirect('/static/pdf-viewer.html');
});

// 启动服务器
app.listen(port, () => {
  console.log(`服务器运行在 http://localhost:${port}`);
  console.log(`PDF查看器: http://localhost:${port}/static/pdf-viewer.html`);
  console.log(`原始HTML: http://localhost:${port}/static/draf.html`);
});
