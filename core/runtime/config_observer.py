"""Observe committed config revisions; no Flask, DB or config imports at import.

The injected applier must call before_publish immediately before its deferred
publication. This module owns only admission reason `config`, never owner_lost.
"""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable


class _ObserverFailure(RuntimeError):
    pass


class ConfigObserver:
    def __init__(self, *, admission, read_revision: Callable, read_snapshot: Callable,
                 apply_snapshot: Callable, poll_interval: float = 1.0,
                 freshness_budget: float = 5.0, clock: Callable = time.monotonic,
                 inactive_snapshot: Callable | None = None):
        if (not math.isfinite(poll_interval) or not math.isfinite(freshness_budget)
                or poll_interval <= 0 or freshness_budget <= poll_interval):
            raise ValueError('config_observer_invalid_budget')
        self._admission = admission
        self._read_revision = read_revision
        self._read_snapshot = read_snapshot
        self._apply_snapshot = apply_snapshot
        self._interval = float(poll_interval)
        self._budget = float(freshness_budget)
        self._clock = clock
        self._lock = threading.RLock()
        self._poll_lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._state = 'new'
        self._error = None
        self._observed = None
        self._applied = None
        self._local_revision = None
        self._last_success = None
        self._started_at = None
        self._inflight = False
        self._inactive_snapshot = inactive_snapshot

    def start(self) -> None:
        with self._lock:
            if self._state in {'starting', 'applied', 'pending', 'error'} and not self._stop.is_set():
                return
            if self._state != 'new':
                raise RuntimeError('config_observer_restart_requires_new_instance')
            self._admission.block('config')
            self._state = 'starting'
            self._started_at = self._clock()
            self._threads = [
                threading.Thread(target=self._watch, name='config-watchdog', daemon=True),
                threading.Thread(target=self._run, name='config-observer', daemon=True),
            ]
            try:
                for thread in self._threads:
                    thread.start()
            except BaseException:
                self._stop.set()
                self._state = 'start_failed'
                self._error = 'config_start_failed'
                raise

    @staticmethod
    def _revision(value) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise _ObserverFailure('config_invalid_revision')
        return value

    def _fail(self, code: str) -> None:
        with self._lock:
            self._admission.block('config')
            if not self._stop.is_set():
                self._state = 'error'
                self._error = code

    def _fence(self, started: float) -> None:
        with self._lock:
            if self._stop.is_set():
                raise _ObserverFailure('config_stopping')
            if self._clock() - started >= self._budget:
                raise _ObserverFailure('config_timeout')

    def _poll_once(self) -> None:
        # Also prevents accidental overlapping explicit integration ticks.
        with self._poll_lock:
            with self._lock:
                if self._stop.is_set():
                    return
                self._inflight = True
            started = self._clock()
            stage = 'read'
            try:
                revision = self._revision(self._read_revision())
                self._fence(started)
                with self._lock:
                    self._observed = revision
                    applied = self._applied
                if applied is not None and revision < applied:
                    raise _ObserverFailure('config_revision_regressed')
                if revision == applied:
                    with self._lock:
                        self._fence(started)
                        self._last_success = self._clock()
                        self._state, self._error = 'applied', None
                        self._admission.unblock('config')
                    return
                with self._lock:
                    self._admission.block('config')
                    self._state = 'pending'
                values, snapshot_revision = self._read_snapshot()
                snapshot_revision = self._revision(snapshot_revision)
                self._fence(started)
                if snapshot_revision < revision:
                    raise _ObserverFailure('config_revision_regressed')
                if values is None:
                    if snapshot_revision != 0 or applied not in (None, 0) or self._inactive_snapshot is None:
                        raise _ObserverFailure('config_inactive')
                    with self._lock:
                        self._fence(started)
                        self._applied, self._local_revision = 0, self._inactive_snapshot()
                        self._last_success = self._clock()
                        self._state, self._error = 'applied', None
                        self._admission.unblock('config')
                    return
                with self._lock:
                    self._observed = snapshot_revision
                stage = 'apply'
                actual_db, actual_local = self._apply_snapshot(
                    values, snapshot_revision, before_publish=lambda: self._fence(started),
                )
                actual_db, actual_local = self._revision(actual_db), self._revision(actual_local)
                if actual_db < snapshot_revision:
                    raise _ObserverFailure('config_apply_invalid_receipt')
                with self._lock:
                    # Publication succeeded: report its true receipt even if a
                    # stop/deadline occurred immediately afterward. Never claim
                    # old values or restore a snapshot already seen by readers.
                    self._applied, self._local_revision = actual_db, actual_local
                    self._fence(started)
                    self._last_success = self._clock()
                    self._state, self._error = 'applied', None
                    self._admission.unblock('config')
            except _ObserverFailure as exc:
                self._fail(str(exc))  # only private fixed codes constructed here
            except Exception:
                self._fail('config_read_failed' if stage == 'read' else 'config_apply_failed')
            except BaseException:
                self._fail('config_observer_interrupted')
                raise
            finally:
                with self._lock:
                    self._inflight = False

    def _check_freshness(self) -> None:
        with self._lock:
            if self._stop.is_set() or self._started_at is None:
                return
            reference = self._last_success if self._last_success is not None else self._started_at
            if self._clock() - reference >= self._budget:
                self._fail('config_timeout')

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                started = self._clock()
                self._poll_once()
                remaining = max(0.0, self._interval - (self._clock() - started))
                # Poll starts target 1 s apart. Slow failures back off a short
                # interval instead of busy looping; the watchdog stays live.
                if self._stop.wait(remaining if remaining else min(self._interval, .1)):
                    break
        finally:
            self._admission.block('config')

    def _watch(self) -> None:
        while not self._stop.wait(min(self._interval, .25)):
            self._check_freshness()
            with self._lock:
                if len(self._threads) == 2 and self._threads[1].ident is not None and not self._threads[1].is_alive():
                    self._fail('config_observer_dead')

    def status(self) -> dict:
        self._check_freshness()
        with self._lock:
            return {
                'state': self._state,
                'observed_db_revision': self._observed,
                'applied_db_revision': self._applied,
                'local_snapshot_revision': self._local_revision,
                'error_code': self._error,
                'alive': len(self._threads) == 2 and all(t.is_alive() for t in self._threads),
                'inflight': self._inflight,
            }

    def stop(self, timeout: float = 3.0) -> bool:
        deadline = self._clock() + max(0.0, float(timeout))
        with self._lock:
            self._admission.block('config')
            if self._state == 'stopped':
                return True
            self._stop.set()
            self._state = 'stopping'
        for thread in self._threads:
            if thread.ident is not None and thread is not threading.current_thread():
                thread.join(max(0.0, deadline - self._clock()))
        with self._lock:
            complete = not self._inflight and not any(t.is_alive() for t in self._threads)
            self._state = 'stopped' if complete else 'stop_incomplete'
            return complete


def create_config_observer(context) -> ConfigObserver:
    """Composition-root factory; called explicitly after bootstrap is loaded."""
    import config
    import os
    from config import schema
    from core.storage import runtime_config
    return ConfigObserver(
        admission=context.admission,
        read_revision=runtime_config.current_revision,
        read_snapshot=runtime_config.read_snapshot,
        apply_snapshot=config.apply_runtime_snapshot,
        inactive_snapshot=(lambda: schema.non_sensitive_snapshot().revision)
        if context.mode.value == 'combined' and not os.getenv('TURB_CONFIG_ENCRYPTION_KEY') else None,
    )
