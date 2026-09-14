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
    """A lazily-created account-operation pool with one process-wide budget.

    A worker-count reload deliberately leaves already accepted work on the old
    pool.  That is useful for draining a batch, but it means the pool generation
    is not the concurrency boundary.  ``_accepted`` and ``_active`` therefore
    live on this object, outside the individual ``ThreadPoolExecutor`` objects,
    so an old and a new generation still share one budget.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._executor: ThreadPoolExecutor | None = None
        self._workers: int | None = None
        self._generation = 0
        self._retired: list[ThreadPoolExecutor] = []
        self._budget_limit: int | None = None
        self._accepted = 0
        self._active = 0

    def _refresh_budget_locked(self, requested: int | None = None) -> int:
        value = configured_workers() if requested is None else int(requested)
        value = max(_MIN_WORKERS, min(_MAX_WORKERS, value))
        if self._budget_limit != value:
            self._budget_limit = value
            self._condition.notify_all()
        return value

    def _release_cancelled_submission(self) -> None:
        with self._condition:
            if self._accepted > 0:
                self._accepted -= 1
            self._condition.notify_all()

    def _run_with_budget(self, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        """Gate execution, not queue insertion, on the shared generation budget."""
        with self._condition:
            limit = self._refresh_budget_locked()
            while self._active >= limit:
                self._condition.wait(timeout=0.25)
                limit = self._refresh_budget_locked()
            self._active += 1
        try:
            return fn(*args, **kwargs)
        finally:
            with self._condition:
                self._active -= 1
                if self._accepted > 0:
                    self._accepted -= 1
                self._condition.notify_all()

    def _current_executor(self) -> ThreadPoolExecutor:
        requested = configured_workers()
        with self._condition:
            self._refresh_budget_locked(requested)
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
        executor = self._current_executor()
        with self._condition:
            self._accepted += 1
        try:
            future = executor.submit(self._run_with_budget, fn, args, kwargs)
        except Exception:
            self._release_cancelled_submission()
            raise
        # ``cancel_futures=False`` is intentional for pool rotation, but a
        # caller may still cancel a Future explicitly.  Do not leave that
        # cancelled item consuming the global budget forever.
        try:
            future.add_done_callback(
                lambda completed: self._release_cancelled_submission()
                if completed.cancelled() else None
            )
        except AttributeError:
            # Small test doubles and compatible executors need only implement
            # submit; the real concurrent.futures Future has the callback API.
            pass
        return future

    def try_submit(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future | None:
        """Submit only when a global budget slot is available.

        Durable dispatchers use this non-blocking boundary after claiming a
        queue row.  Returning ``None`` lets the caller put that row back into
        its durable ready/queued state instead of growing an unbounded
        executor backlog or waiting while holding an account lease.
        """
        executor = self._current_executor()
        with self._condition:
            limit = self._refresh_budget_locked()
            if self._accepted >= limit:
                return None
            self._accepted += 1
        try:
            future = executor.submit(self._run_with_budget, fn, args, kwargs)
        except Exception:
            self._release_cancelled_submission()
            raise
        try:
            future.add_done_callback(
                lambda completed: self._release_cancelled_submission()
                if completed.cancelled() else None
            )
        except AttributeError:
            pass
        return future

    def workers(self) -> int:
        return configured_workers()

    def available_slots(self) -> int:
        """Return slots not already accepted by any pool generation."""
        with self._condition:
            limit = self._refresh_budget_locked()
            return max(0, limit - self._accepted)

    def status(self) -> dict[str, int | None]:
        """Expose non-sensitive runtime counters for health/readiness views."""
        with self._condition:
            limit = self._refresh_budget_locked()
            return {
                "configured_workers": configured_workers(),
                "budget": limit,
                "accepted": self._accepted,
                "active": self._active,
                "available": max(0, limit - self._accepted),
                "generation": self._generation,
                "retired_pools": len(self._retired),
                "current_pool_workers": self._workers,
            }

    def shutdown(self, wait: bool = True) -> None:
        with self._condition:
            executors: list[ThreadPoolExecutor] = []
            if self._executor is not None:
                executors.append(self._executor)
                self._executor = None
            executors.extend(self._retired)
            self._retired.clear()
            self._workers = None
            self._condition.notify_all()
        for executor in executors:
            executor.shutdown(wait=wait, cancel_futures=False)


executor = AccountOperationExecutor()


__all__ = ["AccountOperationExecutor", "configured_workers", "executor"]
