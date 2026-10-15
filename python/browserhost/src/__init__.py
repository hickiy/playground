"""browserhost：常驻真实 Chrome 的 CDP 宿主。

任务侧与本项目交互的**唯一方式**是通过调试端口的 CDP 连接（Playwright 的
`connect_over_cdp` 即可），本项目不对外提供库接口：

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]     # 共用这份 profile 的登录态
        page = context.new_page()         # 只动自己开的标签页
        ...
        page.close()                      # 关自己的标签页；不要关浏览器

多任务共用一个实例时的约定（没有工具代劳，靠自觉）：

  - 只连接，不启动、不关闭浏览器——生命周期归 `python main.py start/stop`；
  - 只操作自己打开的标签页，别去动别人的；
  - 不发全局 CDP 命令（`Browser.close`、`Network.setCookie`、
    `Storage.clearDataForOrigin`、`Browser.setDownloadBehavior`、改代理/装扩展）；
  - 任务自己保证「运行期间机器不睡」（`caffeinate -dims`）。
"""
