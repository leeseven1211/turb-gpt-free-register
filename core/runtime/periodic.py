"""Bounded, truthful lifecycle for the process's periodic producers."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable


def execution_allowed() -> bool:
    """Standalone callers keep their policy; managed runtimes obey admission."""
    from core.runtime.process import execution_admitted, get_runtime_context

    return get_runtime_context() is None or execution_admitted()


class StopBudget:
    """One monotonic deadline shared by every wait in a stop operation."""

    def __init__(self, timeout: float) -> None:
        self.deadline = time.monotonic() + max(0.0, float(timeout))

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())


def join_stopped(thread: threading.Thread | None, budget: StopBudget) -> bool:
    if thread is None or not thread.is_alive():
        return True
    if thread is threading.current_thread():
        return False
    try:
        thread.join(budget.remaining())
    except RuntimeError:
        return False
    return not thread.is_alive()


class PeriodicThread:
    """Own exactly one thread and keep its reference until exit is confirmed."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self._working = False
        self._error: str | None = None

    def start(self, target: Callable[[], None], *, before_start=None) -> bool:
        # Thread creation during startup is permitted; run_periodic gates work.
        from core.runtime.process import get_runtime_context

        context = get_runtime_context()
        if context is not None and not context.executes:
            return False
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._thread = None
            self.stop_event.clear()
            self._working = False
            self._error = None
            if before_start is not None:
                before_start()
            worker = threading.Thread(target=target, name=self.name, daemon=True)
            self._thread = worker
            try:
                worker.start()
            except Exception:
                # A partially started thread still belongs to this owner.
                if not worker.is_alive():
                    self._thread = None
                raise
            return True

    def stop(self, timeout: float = 2.0) -> bool:
        budget = StopBudget(timeout)
        if not self._lock.acquire(timeout=budget.remaining()):
            return False
        try:
            worker = self._thread
            self.stop_event.set()
        finally:
            self._lock.release()
        stopped = join_stopped(worker, budget)
        if not stopped:
            return False
        if not self._lock.acquire(timeout=budget.remaining()):
            return False
        try:
            if self._thread is worker:
                self._thread = None
                self._working = False
            # A concurrent restart must not turn a live process into success.
            return not bool(self._thread and self._thread.is_alive())
        finally:
            self._lock.release()

    def work_started(self) -> None:
        with self._lock:
            self._working = True
            self._error = None

    def work_finished(self) -> None:
        with self._lock:
            self._working = False

    def record_error(self, code: str | None) -> None:
        with self._lock:
            self._error = code

    def status(self, *, enabled: bool) -> dict:
        allowed = execution_allowed()
        with self._lock:
            alive = bool(self._thread and self._thread.is_alive())
            working = alive and self._working
            stopping = alive and self.stop_event.is_set()
            if not alive:
                state = "stopped"
            elif stopping:
                state = "stopping"
            elif working:
                state = "running"
            elif not enabled:
                state = "disabled"
            elif not allowed:
                state = "blocked"
            elif self._error:
                state = "error"
            else:
                state = "idle"
            return {
                "name": self.name,
                "started": self._thread is not None,
                "alive": alive,
                "running": working,
                "idle": state == "idle",
                "disabled": not enabled,
                "enabled": enabled,
                "admitted": allowed,
                "stopping": stopping,
                "state": state,
                "error_code": self._error,
            }
