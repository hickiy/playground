// Web 平台能力矩阵：概览页与兼容性矩阵页共用的唯一真实来源。
//
// 探测项分两类：
//   1. 支持度探测 —— 提供 test()，返回 true / false / { partial: true, note }；
//   2. 取值探测  —— 提供 value()，直接展示字符串（如 userAgent）。
// 每一项都必须能在任何引擎下安全运行（抛出异常会被记为「不支持」而不是让页面崩溃）。

/** 尝试取得 canvas 上下文。 */
function canvasContext(type) {
  try {
    return document.createElement('canvas').getContext(type) || null;
  } catch (err) {
    return null;
  }
}

/** 用 new Function 判断某段语法是否被引擎接受。 */
function syntaxSupported(source) {
  try {
    new Function(source);
    return true;
  } catch (err) {
    return false;
  }
}

/** 判断 CSS 属性值是否受支持。 */
function cssSupports(property, value) {
  try {
    if (typeof CSS === 'undefined' || !CSS.supports) return false;
    return CSS.supports(property, value);
  } catch (err) {
    return false;
  }
}

/** 探测存储是否真的可写（存在但被禁用的情形很常见）。 */
function storageUsable(name) {
  try {
    const store = window[name];
    if (!store) return false;
    store.setItem('__probe__', '1');
    store.removeItem('__probe__');
    return true;
  } catch (err) {
    return false;
  }
}

/** 简写：支持度探测项。 */
function p(name, test) {
  return { name, test };
}

/** 简写：取值探测项。 */
function v(name, value) {
  return { name, value };
}

/** 完整矩阵。 */
const PROBE_GROUPS = [
  {
    group: '引擎身份',
    items: [
      v('userAgent', () => navigator.userAgent),
      v('appName', () => navigator.appName),
      v('appVersion', () => navigator.appVersion),
      v('platform', () => navigator.platform),
      v('language', () => navigator.language),
      v('hardwareConcurrency', () => navigator.hardwareConcurrency),
      v('deviceMemory', () => navigator.deviceMemory),
      v('devicePixelRatio', () => window.devicePixelRatio),
      p('window.isSecureContext', () => window.isSecureContext),
      p('Tauri 宿主 (__TAURI__)', () => typeof window.__TAURI__ !== 'undefined'),
    ],
  },
  {
    group: '图形与渲染',
    items: [
      p('Canvas 2D', () => !!canvasContext('2d')),
      p('WebGL 1', () => !!canvasContext('webgl')),
      p('WebGL 2', () => !!canvasContext('webgl2')),
      p('WebGPU', () => !!navigator.gpu),
      p('OffscreenCanvas', () => typeof OffscreenCanvas !== 'undefined'),
      p('OffscreenCanvas 2D', () => {
        if (typeof OffscreenCanvas === 'undefined') return false;
        return !!new OffscreenCanvas(8, 8).getContext('2d');
      }),
      p('Path2D', () => typeof Path2D !== 'undefined'),
      p('ImageBitmap', () => typeof createImageBitmap !== 'undefined'),
      p('requestAnimationFrame', () => typeof requestAnimationFrame !== 'undefined'),
      p('CSS transform 3D', () => cssSupports('transform', 'translate3d(1px,1px,1px)')),
      p('CSS filter', () => cssSupports('filter', 'blur(2px)')),
      p('backdrop-filter', () => cssSupports('backdrop-filter', 'blur(2px)')),
      p('mix-blend-mode', () => cssSupports('mix-blend-mode', 'multiply')),
      p('clip-path', () => cssSupports('clip-path', 'circle(40%)')),
      p('CSS 渐变', () => cssSupports('background-image', 'linear-gradient(#000,#fff)')),
      p('SVG (内联)', () => typeof SVGSVGElement !== 'undefined'),
      p('IntersectionObserver', () => typeof IntersectionObserver !== 'undefined'),
      p('ResizeObserver', () => typeof ResizeObserver !== 'undefined'),
    ],
  },
  {
    group: 'CSS 布局与新特性',
    items: [
      p('Flexbox', () => cssSupports('display', 'flex')),
      p('CSS Grid', () => cssSupports('display', 'grid')),
      // 交叉验证：CSS.supports 在部分引擎里并不完整，会给出假阴性。
      // 这里真正把 display:grid 挂上去再读计算值，作为行为级判据。
      p('CSS Grid（行为验证）', () => {
        const host = document.createElement('div');
        host.style.display = 'grid';
        document.body.appendChild(host);
        const actual = getComputedStyle(host).display;
        host.remove();
        return actual === 'grid' ? true : { partial: true, note: '计算值 = ' + actual };
      }),
      p('CSS 自定义属性', () => cssSupports('--probe', '1')),
      p('gap (flex)', () => cssSupports('gap', '1px')),
      p(':has()', () => cssSupports('selector(:has(a))', 'true')),
      p('is() / where()', () => cssSupports('selector(:is(a))', 'true')),
      p('CSS 嵌套', () => cssSupports('selector(&)', 'true')),
      p('容器查询', () => cssSupports('container-type', 'inline-size')),
      p('@layer', () => cssSupports('at-rule(@layer)', '')),
      p('aspect-ratio', () => cssSupports('aspect-ratio', '1')),
      p('position: sticky', () => cssSupports('position', 'sticky')),
      p('color-scheme', () => cssSupports('color-scheme', 'dark')),
      p('scroll-behavior', () => cssSupports('scroll-behavior', 'smooth')),
      p('prefers-color-scheme', () => typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches !== undefined),
      p('矢量字体 (woff2)', () => cssSupports('font-format', 'woff2')),
      p('web font 加载 API', () => typeof document.fonts !== 'undefined'),
      p('accent-color', () => cssSupports('accent-color', 'red')),
      p('text-wrap: balance', () => cssSupports('text-wrap', 'balance')),
    ],
  },
  {
    group: 'JavaScript 语言特性',
    items: [
      p('可选链 ?.', () => syntaxSupported('({})?.a')),
      p('空值合并 ??', () => syntaxSupported('null ?? 1')),
      p('class 私有字段', () => syntaxSupported('class A { #x = 1; get y(){return this.#x} }')),
      p('class 静态块', () => syntaxSupported('class A { static { } }')),
      p('顶层 await', () => syntaxSupported('(async () => { await 0 })')),
      p('逻辑赋值 ||=', () => syntaxSupported('let a; a ||= 1')),
      p('数值分隔符', () => syntaxSupported('1_000_000')),
      p('Object.hasOwn', () => typeof Object.hasOwn === 'function'),
      p('Array.at', () => typeof [].at === 'function'),
      p('Array.flat', () => typeof [].flat === 'function'),
      p('structuredClone', () => typeof structuredClone === 'function'),
      p('Intl.Segmenter', () => typeof Intl !== 'undefined' && !!Intl.Segmenter),
      p('Intl.RelativeTimeFormat', () => typeof Intl !== 'undefined' && !!Intl.RelativeTimeFormat),
      p('BigInt', () => typeof BigInt === 'function'),
      p('WeakRef', () => typeof WeakRef === 'function'),
      p('FinalizationRegistry', () => typeof FinalizationRegistry === 'function'),
      p('Temporal', () => typeof Temporal !== 'undefined'),
    ],
  },
  {
    group: 'DOM 与事件',
    items: [
      p('Shadow DOM', () => !!Element.prototype.attachShadow),
      p('Custom Elements', () => typeof customElements !== 'undefined'),
      p('<dialog>', () => typeof HTMLDialogElement !== 'undefined'),
      p('popover 属性', () => HTMLElement.prototype.hasOwnProperty('popover')),
      p('MutationObserver', () => typeof MutationObserver !== 'undefined'),
      p('Pointer Events', () => typeof PointerEvent !== 'undefined'),
      p('拖放 Drag & Drop', () => 'draggable' in HTMLElement.prototype),
      p('剪贴板事件', () => typeof ClipboardEvent !== 'undefined'),
      p('异步剪贴板 API', () => !!(navigator.clipboard && navigator.clipboard.writeText)),
      p('全屏 API', () => !!document.documentElement.requestFullscreen),
      p('Selection API', () => typeof Selection !== 'undefined'),
      p('元素滚动 API', () => !!Element.prototype.scrollTo),
      p('DOMParser', () => typeof DOMParser !== 'undefined'),
      p('Range API', () => typeof Range !== 'undefined'),
      p('Web Animations API', () => typeof Element.prototype.animate === 'function'),
      p('View Transitions', () => !!document.startViewTransition),
      p('Compression Streams', () => typeof CompressionStream !== 'undefined'),
    ],
  },
  {
    group: '存储与持久化',
    items: [
      p('localStorage 可写', () => storageUsable('localStorage')),
      p('sessionStorage 可写', () => storageUsable('sessionStorage')),
      p('IndexedDB', () => typeof indexedDB !== 'undefined'),
      p('Cache Storage', () => typeof caches !== 'undefined'),
      p('Cookie 可写', () => {
        try {
          document.cookie = '__probe__=1';
          return document.cookie.indexOf('__probe__') !== -1;
        } catch (err) {
          return false;
        }
      }),
      p('navigator.storage.estimate', () => !!(navigator.storage && navigator.storage.estimate)),
      p('File API', () => typeof File !== 'undefined'),
      p('File System Access', () => typeof showOpenFilePicker === 'function'),
      p('网络是否在线', () => navigator.onLine),
    ],
  },
  {
    group: '网络与并发',
    items: [
      p('fetch', () => typeof fetch === 'function'),
      p('XMLHttpRequest', () => typeof XMLHttpRequest !== 'undefined'),
      p('WebSocket', () => typeof WebSocket !== 'undefined'),
      p('EventSource (SSE)', () => typeof EventSource !== 'undefined'),
      p('Web Worker', () => typeof Worker !== 'undefined'),
      p('SharedWorker', () => typeof SharedWorker !== 'undefined'),
      p('Service Worker', () => 'serviceWorker' in navigator),
      p('SharedArrayBuffer', () => typeof SharedArrayBuffer !== 'undefined'),
      p('Atomics', () => typeof Atomics !== 'undefined'),
      p('AbortController', () => typeof AbortController !== 'undefined'),
      p('ReadableStream', () => typeof ReadableStream !== 'undefined'),
      p('WebAssembly', () => typeof WebAssembly !== 'undefined'),
      p('WASM SIMD', () => {
        try {
          return WebAssembly.validate(
            new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 26, 11])
          );
        } catch (err) {
          return false;
        }
      }),
      p('WebRTC', () => typeof RTCPeerConnection !== 'undefined'),
      p('WebTransport', () => typeof WebTransport !== 'undefined'),
    ],
  },
  {
    group: '媒体与其它',
    items: [
      p('<audio>', () => typeof Audio === 'function'),
      p('MediaRecorder', () => typeof MediaRecorder !== 'undefined'),
      p('getUserMedia', () => !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)),
      p('Web Audio API', () => !!(window.AudioContext || window.webkitAudioContext)),
      p('Speech Synthesis', () => typeof speechSynthesis !== 'undefined'),
      p('Notification API', () => typeof Notification !== 'undefined'),
      p('Vibration API', () => !!navigator.vibrate),
      p('Geolocation', () => !!navigator.geolocation),
      p('Gamepad API', () => typeof GamepadEvent !== 'undefined'),
      p('WebXR', () => !!navigator.xr),
      p('屏幕方向 API', () => 'orientation' in screen),
      p('Battery Status', () => !!navigator.getBattery),
      p('Touch Events', () => typeof TouchEvent !== 'undefined'),
      p('Payment Request', () => typeof PaymentRequest !== 'undefined'),
      p('Credential Management', () => !!navigator.credentials),
    ],
  },
];

/** 把探测结果归一化成三种状态之一。 */
function normalizeResult(result) {
  if (result === true) return { state: 'ok', note: '' };
  if (result === false) return { state: 'bad', note: '' };
  if (result && typeof result === 'object' && result.partial) {
    return { state: 'warn', note: result.note || '部分支持' };
  }
  return { state: 'warn', note: String(result) };
}

/** 执行整张矩阵，返回扁平的结果数组。 */
function runAllProbes() {
  const startedAt = (performance && performance.now) ? performance.now() : Date.now();
  const results = [];

  for (const { group, items } of PROBE_GROUPS) {
    for (const item of items) {
      if (item.value) {
        results.push({
          group,
          name: item.name,
          kind: 'value',
          state: 'info',
          value: safe(item.value, '—'),
        });
        continue;
      }

      let normalized;
      try {
        normalized = normalizeResult(item.test());
      } catch (err) {
        normalized = { state: 'bad', note: '探测抛异常: ' + (err && err.message ? err.message : err) };
      }
      results.push({
        group,
        name: item.name,
        kind: 'support',
        state: normalized.state,
        note: normalized.note,
        value: normalized.state === 'ok' ? '支持' : normalized.state === 'bad' ? '不支持' : '部分',
      });
    }
  }

  const finishedAt = (performance && performance.now) ? performance.now() : Date.now();
  return {
    runtime: detectRuntime().label,
    userAgent: navigator.userAgent,
    collectedAt: new Date().toISOString(),
    durationMs: Math.round((finishedAt - startedAt) * 100) / 100,
    results,
  };
}

/** 统计各状态数量。 */
function summarize(report) {
  const counts = { ok: 0, warn: 0, bad: 0, info: 0 };
  for (const row of report.results) counts[row.state] += 1;
  return counts;
}
