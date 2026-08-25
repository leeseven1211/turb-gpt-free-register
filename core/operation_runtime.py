# -*- coding: utf-8 -*-
"""统一账号操作运行时上下文：协作式取消、阶段事件和资源登记。"""
from __future__ import annotations

import contextvars
import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator
from typing import Any


class OperationCancelled(RuntimeError):
    """任务在安全检查点响应了取消请求。"""


@dataclass
class CancellationToken:
    run_id: int
    token: str
    checker: Callable[[int, str], bool]
    local_event: threading.Event = field(default_factory=threading.Event)
    poll_interval: float = 0.35
    _last_poll: float = 0.0
    _last_result: bool = False

    def request_local(self) -> None:
        self.local_event.set()

    def requested(self, *, force: bool = False) -> bool:
        if self.local_event.is_set():
            return True
        now = time.monotonic()
        if force or now - self._last_poll >= self.poll_interval:
            self._last_poll = now
            self._last_result = bool(self.checker(int(self.run_id), str(self.token)))
        return self._last_result

    def checkpoint(self, message: str = "用户手动停止 Codex 补跑") -> None:
        if self.requested():
            raise OperationCancelled(message)

    def sleep(self, seconds: float, *, quantum: float = 0.25) -> None:
        deadline = time.monotonic() + max(0.0, float(seconds or 0))
        while True:
            self.checkpoint()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self.local_event.wait(min(max(0.05, quantum), remaining))


_CURRENT_TOKEN: contextvars.ContextVar[CancellationToken | None] = contextvars.ContextVar(
    "operation_cancellation_token", default=None
)
_CURRENT_REPORTER: contextvars.ContextVar[Callable[..., object] | None] = contextvars.ContextVar(
    "operation_stage_reporter", default=None
)


@contextmanager
def operation_context(
    token: CancellationToken,
    *,
    reporter: Callable[..., object] | None = None,
) -> Iterator[CancellationToken]:
    token_marker = _CURRENT_TOKEN.set(token)
    reporter_marker = _CURRENT_REPORTER.set(reporter)
    try:
        yield token
    finally:
        _CURRENT_REPORTER.reset(reporter_marker)
        _CURRENT_TOKEN.reset(token_marker)


def current_token() -> CancellationToken | None:
    return _CURRENT_TOKEN.get()


def check_cancelled(message: str = "用户手动停止 Codex 补跑") -> None:
    token = current_token()
    if token is not None:
        token.checkpoint(message)


def cancellable_sleep(seconds: float) -> None:
    token = current_token()
    if token is None:
        time.sleep(max(0.0, float(seconds or 0)))
    else:
        token.sleep(seconds)


def call_cancellable(fn: Callable[..., Any], *args, **kwargs) -> Any:
    """让第三方阻塞调用可被 operation 取消。

    Python 无法安全终止任意线程；因此阻塞调用放入 daemon 线程，当前 worker 只在
    安全检查点停止等待。后台调用会自行结束，但不会继续 OAuth 或申请新资源。
    """
    token = current_token()
    if token is None:
        return fn(*args, **kwargs)
    results: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            results.put((True, fn(*args, **kwargs)))
        except BaseException as exc:
            results.put((False, exc))

    threading.Thread(
        target=invoke,
        name=f"operation-blocking-{token.run_id}",
        daemon=True,
    ).start()
    while True:
        token.checkpoint()
        try:
            ok, value = results.get(timeout=0.25)
        except queue.Empty:
            continue
        if ok:
            return value
        raise value


def report_stage(
    stage: str,
    message: str,
    *,
    state: str = "running",
    level: str = "INFO",
    detail: dict | None = None,
) -> None:
    check_cancelled()
    reporter = _CURRENT_REPORTER.get()
    if reporter is not None:
        reporter(stage=stage, message=message, state=state, level=level, detail=detail or {})
