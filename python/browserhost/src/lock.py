"""跨平台文件锁：保护状态文件的读改写（多个入口同时 start/stop 时不会互相覆盖）。

POSIX 用 fcntl，Windows 用 msvcrt，均来自标准库，不引第三方依赖。
"""

import sys
import time
from contextlib import contextmanager
from pathlib import Path

from . import config


def _acquire(fh) -> None:
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release(fh) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


@contextmanager
def file_lock(path: Path | str, timeout_s: float = config.LOCK_TIMEOUT_S):
    """独占锁住 `path`；等不到就抛 TimeoutError。

    锁是「文件级」的：path 本身只是个锚点，进程退出（含被 kill）时由操作系统释放。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("a+")
    try:
        deadline = time.time() + timeout_s
        while True:
            try:
                _acquire(fh)
                break
            except OSError:
                if time.time() >= deadline:
                    raise TimeoutError(f"等待文件锁超时（{timeout_s:g}s）: {path}")
                time.sleep(0.05)
        yield
    finally:
        _release(fh)
        fh.close()
