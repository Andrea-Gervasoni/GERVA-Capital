"""One local owner per long-running reader; the kernel releases locks on crashes."""
from contextlib import contextmanager
import fcntl
import os


@contextmanager
def exclusive(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('service already running; refusing duplicate reader') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
