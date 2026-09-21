// 所有页面共用的工具函数。
// 这个文件由编辑器手写（.js 由编辑器写入才是明文，绝不要交给脚本生成）。

/** 求值并兜住异常，任何探测失败都不应该让整页崩掉。 */
function safe(fn, fallback) {
  try {
    const value = fn();
    return value === undefined ? fallback : value;
  } catch (err) {
    return fallback === undefined ? '异常: ' + (err && err.message ? err.message : err) : fallback;
  }
}

/** 通过引擎的 UA 推断我们正跑在哪个 webview 里。 */
function detectRuntime() {
  const ua = String(navigator.userAgent || '');
  if (/Servo/i.test(ua)) return { label: 'Servo / Verso', cls: 'servo' };
  if (/WebView2|Edg\//i.test(ua)) return { label: 'WebView2', cls: 'webview2' };
  if (/Firefox\//i.test(ua)) return { label: 'Gecko', cls: 'gecko' };
  if (/Chrome\//i.test(ua)) return { label: 'Chromium', cls: 'chromium' };
  return { label: '未知引擎', cls: '' };
}

/** 是否运行在 Tauri 宿主里。 */
function hasTauri() {
  return typeof window.__TAURI__ !== 'undefined';
}

/** 调用 Tauri 命令；不在宿主里时返回 null，命令报错时返回 { error }。 */
async function invokeHost(command, args) {
  if (!hasTauri()) return null;
  const core = window.__TAURI__.core || window.__TAURI__;
  try {
    return await core.invoke(command, args);
  } catch (err) {
    return { error: String(err) };
  }
}

/** 自动化模式：宿主以 --compat-report 启动时，自动切到兼容性页并带上标记。 */
async function maybeRedirectForReport() {
  if (window.location.pathname.indexOf('compat.htm') !== -1) return;

  const info = await invokeHost('get_app_info');
  if (info && info.reportMode) {
    window.location.replace('compat.htm?report=1');
  }
}

/** 顶部徽标 + 页脚 + 导航按钮的统一初始化。 */
function initChrome(footerText) {
  const runtime = detectRuntime();
  const badge = document.getElementById('runtime-badge');
  if (badge) {
    badge.textContent = runtime.label;
    badge.className = 'badge ' + runtime.cls;
  }

  const note = document.getElementById('foot-note');
  if (note) {
    note.textContent =
      (footerText ? footerText + ' · ' : '') +
      (hasTauri() ? 'Tauri 宿主可用' : '纯浏览器环境') +
      ' · ' + new Date().toLocaleTimeString();
  }

  for (const button of document.querySelectorAll('.nav button[data-page]')) {
    button.addEventListener('click', () => {
      window.location.href = button.dataset.page;
    });
  }

  // 不 await：跳转是后台行为，不应阻塞页面渲染。
  maybeRedirectForReport();
}

/** 把文本复制到剪贴板，返回是否成功。 */
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    return false;
  }
}
