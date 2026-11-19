"""Bound a non-cancellable finalization call without losing its thread owner."""
from __future__ import annotations
import threading
import time

class BoundedFinalizer:
    def __init__(self, callback):
        self._callback = callback
        self._lock = threading.Lock()
        self._thread = None
        self._succeeded = False
        self._failed = False

    def _run(self):
        try:
            self._succeeded = self._callback() is True
        except BaseException:
            self._failed = True

    def __call__(self, timeout):
        deadline = time.monotonic() + max(0., timeout)
        if not self._lock.acquire(timeout=max(0., deadline-time.monotonic())):
            return False
        try:
            if self._thread is None or (not self._thread.is_alive() and not self._succeeded):
                self._failed = False
                self._thread = threading.Thread(target=self._run,name='runtime-finalizer',daemon=True)
                self._thread.start()
            thread = self._thread
        finally:
            self._lock.release()
        if thread is threading.current_thread():
            return False
        thread.join(max(0., deadline-time.monotonic()))
        return not thread.is_alive() and self._succeeded and not self._failed
