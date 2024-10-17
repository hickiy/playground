(function () {
  // 对部分被动事件添加passive属性
  const addEventListener = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (['mousewheel', 'touchmove', 'touchstart', 'wheel'].includes(type)) {
      options = { passive: true, ...options };
    }
    addEventListener.call(this, type, listener, options);
  };

  // 全局处理未捕获的promise异常
  window.addEventListener('unhandledrejection', (event) => {
    event.preventDefault();
    console.warn(event.reason);
  });
})();
