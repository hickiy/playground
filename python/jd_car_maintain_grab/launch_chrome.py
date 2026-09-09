"""启动带远程调试端口的真实 Google Chrome，供 jd-grab 通过 --cdp 连接。

在启动的 Chrome 里手动登录京东（受信任会话，兑换按钮才会渲染），
随后运行：
    jd-grab --cdp http://localhost:9222
"""

import argparse
import subprocess
import sys
from pathlib import Path


def find_chrome() -> str | None:
    if sys.platform == "darwin":  # macOS
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    elif sys.platform == "win32":  # Windows
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    else:  # Linux / 其他类 Unix
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
        ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="启动带 CDP 调试端口的真实 Chrome")
    parser.add_argument("--port", default=9222, help="调试端口，默认 9222")
    parser.add_argument("--profile", default="./jd_cdp_profile",
                        help="Chrome 用户数据目录，默认 ./jd_cdp_profile")
    parser.add_argument("--url", default="https://plogin.m.jd.com/login/login",
                        help="启动后打开的地址，默认京东登录页")
    parser.add_argument("--chrome", help="Chrome/Edge 可执行文件路径")
    args = parser.parse_args()

    chrome = args.chrome or find_chrome()
    if not chrome:
        print("未找到 Chrome/Edge，请用 --chrome 指定路径。")
        return 1

    profile = str(Path(args.profile).resolve())
    Path(profile).mkdir(parents=True, exist_ok=True)

    print(f"启动: {chrome}")
    print(f"调试端口: {args.port}  用户数据目录: {profile}")
    subprocess.Popen([
        chrome,
        f"--remote-debugging-port={args.port}",
        f"--user-data-dir={profile}",
        args.url,
    ])
    print("请在打开的 Chrome 中手动登录京东。")
    print(f"登录完成后运行：jd-grab --cdp http://localhost:{args.port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
