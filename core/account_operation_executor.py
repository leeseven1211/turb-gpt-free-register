# -*- coding: utf-8 -*-
"""Shared executor for post-registration account operations.

Registration has its own worker pools and must not consume the account
operation concurrency budget. All account-page and account-maintenance
operations submit through this executor so one batch cannot create one raw
thread per account.
"""
from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


_MIN_WORKERS = 1
_MAX_WORKERS = 16


def configured_workers() -> int:
    """Return the current common account-operation worker setting."""
    from config import codex as cfg

    try:
        value = int(getattr(cfg, "ACCOUNT_BATCH_WORKERS", 3) or 3)
    except (TypeError, ValueError):
        value = 3
    return max(_MIN_WORKERS, min(_MAX_WORKERS, value))


class AccountOperationExecutor:
    """A lazily-created, hot-reload-aware account operation thread pool."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executor: ThreadPoolExecutor | None = None
        self._workers: int | None = None
        self._generation = 0
        self._retired: list[ThreadPoolExecutor] = []

    def _current_executor(self) -> ThreadPoolExecutor:
        requested = configured_workers()
        with self._lock:
            if self._executor is None or requested != self._workers:
                old = self._executor
                if old is not None:
                    # Do not cancel queued account work. The new setting
                    # applies to newly submitted work while the old pool
                    # drains its already accepted tasks.
                    old.shutdown(wait=False, cancel_futures=False)
                    self._retired.append(old)
                self._generation += 1
                self._workers = requested
                self._executor = ThreadPoolExecutor(
                    max_workers=requested,
                    thread_name_prefix=f"account-op-{self._generation}",
                )
            return self._executor

    def submit(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future:
        return self._current_executor().submit(fn, *args, **kwargs)

    def workers(self) -> int:
        return configured_workers()

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            executors: list[ThreadPoolExecutor] = []
            if self._executor is not None:
                executors.append(self._executor)
                self._executor = None
            executors.extend(self._retired)
            self._retired.clear()
            self._workers = None
        for executor in executors:
            executor.shutdown(wait=wait, cancel_futures=False)


executor = AccountOperationExecutor()


__all__ = ["AccountOperationExecutor", "configured_workers", "executor"]
