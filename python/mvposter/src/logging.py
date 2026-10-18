"""按天写日志：终端 + ``logs/mvposter_YYYY-MM-DD.log``（追加、逐行 flush）。

浏览器与 profile 已经交给独立项目 **browserhost**，本项目不再依赖它的库接口，
这份实现就自带一份（文件名前缀仍是 ``mvposter_``，与历史日志衔接）。
任务可能被 Ctrl+C 或异常终止，因此每行写完立即 flush。
"""

import sys
from datetime import datetime

from . import config

# 防止打印 emoji 等终端编码（如 GBK）表示不了的字符时 UnicodeEncodeError 崩溃
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

_log_fh = None    # 当日日志文件句柄
_log_date = None  # 句柄对应的日期，跨天时自动换文件


def _write_log(line: str) -> None:
    """按天追加写入日志文件；任何写入失败都不得影响主流程。"""
    global _log_fh, _log_date
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        if _log_fh is None or _log_date != today:
            if _log_fh is not None:
                _log_fh.close()
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            _log_fh = (config.LOG_DIR / f"mvposter_{today}.log").open("a", encoding="utf-8")
            _log_date = today
        _log_fh.write(line + "\n")
        _log_fh.flush()
    except Exception:
        pass


def log(msg: str) -> None:
    """输出日志：终端 + 当日日志文件。

    文件行带完整日期，便于跨天对照；终端保持短时间戳。
    """
    now = datetime.now()
    stamp = now.strftime("%H:%M:%S.%f")[:-3]
    try:
        print(f"[{stamp}] {msg}", flush=True)
    except Exception:
        pass  # stdout 被重定向或关闭时不影响写日志文件
    _write_log(f"[{now.strftime('%Y-%m-%d')} {stamp}] {msg}")
