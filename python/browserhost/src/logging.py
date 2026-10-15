"""按天写日志：终端 + 文件（供定时任务事后排查）。

宿主与各任务共用这一个实现，用 `configure()` 指定本项目的日志目录与文件名前缀
（例如 jd 项目是 `logs/jd_grab_2026-10-15.log`），避免每个项目再抄一份。
"""

import sys
from datetime import datetime
from pathlib import Path

from . import config

# 防止打印含 ¥ / emoji 等无法编码的字符时 UnicodeEncodeError 崩溃；
# 保持终端原生编码（如 GBK），仅对无法编码的字符做替换。
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

_log_fh = None        # 当日日志文件句柄
_log_date = None      # 句柄对应的日期，跨天时自动换文件
_log_dir: Path | None = None    # 日志目录（configure 指定）
_log_prefix = "browserhost"     # 文件名前缀：<prefix>_<YYYY-MM-DD>.log


def configure(log_dir: Path | str | None = None, prefix: str = "browserhost") -> None:
    """指定日志目录与文件名前缀；不调用则写到宿主日志目录。

    可以重复调用（例如项目在启动参数解析后才确定日志目录）。
    """
    global _log_dir, _log_prefix, _log_fh, _log_date
    if log_dir is None:
        _log_dir = config.LOG_DIR
    else:
        _log_dir = Path(log_dir)
    _log_prefix = prefix
    # 目录/前缀变了就换文件句柄，下一次写日志时按新配置打开
    if _log_fh is not None:
        try:
            _log_fh.close()
        except Exception:
            pass
        _log_fh = None
        _log_date = None


def _write_log(line: str) -> None:
    """按天追加写入日志文件；任何写入失败都不得影响主流程。"""
    global _log_fh, _log_date
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        if _log_fh is None or _log_date != today:
            if _log_fh is not None:
                _log_fh.close()
            log_dir = _log_dir if _log_dir is not None else config.LOG_DIR
            log_dir.mkdir(parents=True, exist_ok=True)
            _log_fh = (log_dir / f"{_log_prefix}_{today}.log").open("a", encoding="utf-8")
            _log_date = today
        _log_fh.write(line + "\n")
        _log_fh.flush()  # 定时任务可能随时被终止，逐行落盘
    except Exception:
        pass


def log(msg: str) -> None:
    """输出日志：终端 + 当日日志文件。

    文件行带完整日期，便于跨天与多天日志对照；终端保持短时间戳。
    """
    now = datetime.now()
    stamp = now.strftime("%H:%M:%S.%f")[:-3]
    try:
        print(f"[{stamp}] {msg}", flush=True)
    except Exception:
        pass  # 无人值守时可能没有可用的 stdout
    _write_log(f"[{now.strftime('%Y-%m-%d')} {stamp}] {msg}")
