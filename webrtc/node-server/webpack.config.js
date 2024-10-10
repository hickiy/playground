// webpack.config.js
const path = require('path');

module.exports = {
  // 模式
  mode: 'production',
  // 入口文件
  entry: './chatserver.js',
  // 输出配置
  output: {
    filename: 'chatserver.js',
    path: path.resolve(__dirname, 'dist')
  },
  // 目标环境为Node.js
  target: 'node',
};