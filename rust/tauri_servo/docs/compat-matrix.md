# Web 兼容性矩阵（Servo / Verso）

- 采集时间：2026-09-21T04:20:58.116Z
- 引擎：Servo / Verso
- User-Agent：`Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Servo/1.0 Firefox/111.0`
- 页内探测耗时：13.51 ms

状态说明：`通过` = 支持，`部分` = 有限支持，`不支持` = 缺失。

## 汇总

- 支持度探测项 112 项：通过 64 / 部分 1 / 不支持 47（通过率 57.1%）
- 未通过 48 项，清单如下

- 图形与渲染 / WebGL 1
- 图形与渲染 / WebGL 2
- 图形与渲染 / WebGPU
- 图形与渲染 / OffscreenCanvas
- 图形与渲染 / OffscreenCanvas 2D
- 图形与渲染 / backdrop-filter
- 图形与渲染 / IntersectionObserver
- 图形与渲染 / ResizeObserver
- CSS 布局与新特性 / CSS Grid
- CSS 布局与新特性 / CSS Grid（行为验证）（计算值 = block）
- CSS 布局与新特性 / :has()
- CSS 布局与新特性 / is() / where()
- CSS 布局与新特性 / CSS 嵌套
- CSS 布局与新特性 / 容器查询
- CSS 布局与新特性 / @layer
- CSS 布局与新特性 / color-scheme
- CSS 布局与新特性 / scroll-behavior
- CSS 布局与新特性 / 矢量字体 (woff2)
- CSS 布局与新特性 / accent-color
- CSS 布局与新特性 / text-wrap: balance
- DOM 与事件 / popover 属性
- DOM 与事件 / 拖放 Drag & Drop
- DOM 与事件 / 异步剪贴板 API
- DOM 与事件 / Web Animations API
- DOM 与事件 / View Transitions
- DOM 与事件 / Compression Streams
- 存储与持久化 / IndexedDB
- 存储与持久化 / Cache Storage
- 存储与持久化 / navigator.storage.estimate
- 存储与持久化 / File System Access
- 网络与并发 / SharedWorker
- 网络与并发 / Service Worker
- 网络与并发 / SharedArrayBuffer
- 网络与并发 / Atomics
- 网络与并发 / AbortController
- 网络与并发 / WASM SIMD
- 网络与并发 / WebRTC
- 网络与并发 / WebTransport
- 媒体与其它 / MediaRecorder
- 媒体与其它 / getUserMedia
- 媒体与其它 / Speech Synthesis
- 媒体与其它 / Vibration API
- 媒体与其它 / Geolocation
- 媒体与其它 / WebXR
- 媒体与其它 / 屏幕方向 API
- 媒体与其它 / Battery Status
- 媒体与其它 / Payment Request
- 媒体与其它 / Credential Management

## 引擎身份

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| userAgent | 取值 | Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Servo/1.0 Firefox/111.0 |
| appName | 取值 | Netscape |
| appVersion | 取值 | 4.0 |
| platform | 取值 | Win32 |
| language | 取值 | en-US |
| hardwareConcurrency | 取值 | 12 |
| deviceMemory | 取值 | — |
| devicePixelRatio | 取值 | 1 |
| window.isSecureContext | 通过 |  |
| Tauri 宿主 (__TAURI__) | 通过 |  |

## 图形与渲染

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| Canvas 2D | 通过 |  |
| WebGL 1 | 不支持 |  |
| WebGL 2 | 不支持 |  |
| WebGPU | 不支持 |  |
| OffscreenCanvas | 不支持 |  |
| OffscreenCanvas 2D | 不支持 |  |
| Path2D | 通过 |  |
| ImageBitmap | 通过 |  |
| requestAnimationFrame | 通过 |  |
| CSS transform 3D | 通过 |  |
| CSS filter | 通过 |  |
| backdrop-filter | 不支持 |  |
| mix-blend-mode | 通过 |  |
| clip-path | 通过 |  |
| CSS 渐变 | 通过 |  |
| SVG (内联) | 通过 |  |
| IntersectionObserver | 不支持 |  |
| ResizeObserver | 不支持 |  |

## CSS 布局与新特性

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| Flexbox | 通过 |  |
| CSS Grid | 不支持 |  |
| CSS Grid（行为验证） | 部分 | 计算值 = block |
| CSS 自定义属性 | 通过 |  |
| gap (flex) | 通过 |  |
| :has() | 不支持 |  |
| is() / where() | 不支持 |  |
| CSS 嵌套 | 不支持 |  |
| 容器查询 | 不支持 |  |
| @layer | 不支持 |  |
| aspect-ratio | 通过 |  |
| position: sticky | 通过 |  |
| color-scheme | 不支持 |  |
| scroll-behavior | 不支持 |  |
| prefers-color-scheme | 通过 |  |
| 矢量字体 (woff2) | 不支持 |  |
| web font 加载 API | 通过 |  |
| accent-color | 不支持 |  |
| text-wrap: balance | 不支持 |  |

## JavaScript 语言特性

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| 可选链 ?. | 通过 |  |
| 空值合并 ?? | 通过 |  |
| class 私有字段 | 通过 |  |
| class 静态块 | 通过 |  |
| 顶层 await | 通过 |  |
| 逻辑赋值 ||= | 通过 |  |
| 数值分隔符 | 通过 |  |
| Object.hasOwn | 通过 |  |
| Array.at | 通过 |  |
| Array.flat | 通过 |  |
| structuredClone | 通过 |  |
| Intl.Segmenter | 通过 |  |
| Intl.RelativeTimeFormat | 通过 |  |
| BigInt | 通过 |  |
| WeakRef | 通过 |  |
| FinalizationRegistry | 通过 |  |
| Temporal | 通过 |  |

## DOM 与事件

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| Shadow DOM | 通过 |  |
| Custom Elements | 通过 |  |
| <dialog> | 通过 |  |
| popover 属性 | 不支持 |  |
| MutationObserver | 通过 |  |
| Pointer Events | 通过 |  |
| 拖放 Drag & Drop | 不支持 |  |
| 剪贴板事件 | 通过 |  |
| 异步剪贴板 API | 不支持 |  |
| 全屏 API | 通过 |  |
| Selection API | 通过 |  |
| 元素滚动 API | 通过 |  |
| DOMParser | 通过 |  |
| Range API | 通过 |  |
| Web Animations API | 不支持 |  |
| View Transitions | 不支持 |  |
| Compression Streams | 不支持 |  |

## 存储与持久化

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| localStorage 可写 | 通过 |  |
| sessionStorage 可写 | 通过 |  |
| IndexedDB | 不支持 |  |
| Cache Storage | 不支持 |  |
| Cookie 可写 | 通过 |  |
| navigator.storage.estimate | 不支持 |  |
| File API | 通过 |  |
| File System Access | 不支持 |  |
| 网络是否在线 | 通过 |  |

## 网络与并发

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| fetch | 通过 |  |
| XMLHttpRequest | 通过 |  |
| WebSocket | 通过 |  |
| EventSource (SSE) | 通过 |  |
| Web Worker | 通过 |  |
| SharedWorker | 不支持 |  |
| Service Worker | 不支持 |  |
| SharedArrayBuffer | 不支持 |  |
| Atomics | 不支持 |  |
| AbortController | 不支持 |  |
| ReadableStream | 通过 |  |
| WebAssembly | 通过 |  |
| WASM SIMD | 不支持 |  |
| WebRTC | 不支持 |  |
| WebTransport | 不支持 |  |

## 媒体与其它

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| <audio> | 通过 |  |
| MediaRecorder | 不支持 |  |
| getUserMedia | 不支持 |  |
| Web Audio API | 通过 |  |
| Speech Synthesis | 不支持 |  |
| Notification API | 通过 |  |
| Vibration API | 不支持 |  |
| Geolocation | 不支持 |  |
| Gamepad API | 通过 |  |
| WebXR | 不支持 |  |
| 屏幕方向 API | 不支持 |  |
| Battery Status | 不支持 |  |
| Touch Events | 通过 |  |
| Payment Request | 不支持 |  |
| Credential Management | 不支持 |  |
