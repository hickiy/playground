# 指标报告（Tauri + Servo / Verso）

- 采集时间：2026-09-21T04:21:13.945Z
- 构建类型：`release`
- 采样次数：3
- 平台：Windows / x86_64-pc-windows-msvc

## 体积

| 项目 | 体积 | 说明 |
| --- | --- | --- |
| 宿主可执行文件 | 2.4 MB | src-tauri\target\release\tauri-servo-lab.exe |
| Servo 引擎进程 | 101.4 MB | versoview，以独立进程提供 |
| 合计（未打包） | 103.8 MB | 两者相加 |
| 安装包 (NSIS) | 27.0 MB | src-tauri\target\release\bundle\nsis\TauriServoLab_0.1.0_x64-setup.exe |

## 冷启动耗时

口径：宿主进程入口 → 页面脚本执行完毕并回传报告。包含窗口创建、versoview 启动、页面加载与脚本执行。

| 指标 | 值 |
| --- | --- |
| 最快 | 700.8 ms |
| 中位数 | 749.6 ms |
| 逐次结果 | 789.5 ms / 749.6 ms / 700.8 ms |

## 内存占用

口径：采集期间「宿主 + versoview」进程树工作集之和的峰值。

| 指标 | 值 |
| --- | --- |
| 最大 | 757.7 MB |
| 最小 | 756.0 MB |
| 逐次峰值 | 756.0 MB / 756.7 MB / 757.7 MB |

## 构建与重载耗时

| 项目 | 耗时 | 说明 |
| --- | --- | --- |
| 前端页面重建 | 11.3 ms | scripts/build-web.js 生成全部 .htm |
| 后端重编 | 77930 ms | 改动 src/main.rs 后 cargo build --release，含重新链接 |
| 改动生效（推导） | 761 ms | 前端重建 + 冷启动，当前没有 HMR |

## 已知缺口

- **热重载未实现**：当前 `frontendDist` 直接指向源码目录，没有接 `devUrl` 开发服务器，
  所以改完前端需要「重建 + 重启应用」。要补上真正的 HMR，需要引入本地静态服务并把
  `build.devUrl` 指过去。
- **WebGL / WebGPU 缺失**：Servo 当前构建在该环境下未提供，涉及图形密集的界面要提前评估。
- **安全限制**：tauri-runtime-verso 硬编码了自定义协议 IPC 的 `Origin`，因此不要用它加载任意外部网站。
