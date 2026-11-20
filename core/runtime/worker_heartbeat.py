"""Worker heartbeat lifecycle, with injected I/O and no application imports.

Owns only admission reason ``heartbeat``. Generation CAS failure is permanent;
DB failures recover on a later timely write. No permit/lease cleanup exists here.
"""
from __future__ import annotations

import math
import logging
import threading
import time
from collections.abc import Callable, Mapping

logger = logging.getLogger(__name__)
_DIAGNOSTIC_CODES = frozenset({
    'heartbeat_timeout', 'heartbeat_fenced', 'heartbeat_collect_failed',
    'heartbeat_write_failed', 'heartbeat_interrupted', 'heartbeat_thread_dead',
})


class WorkerHeartbeat:
    def __init__(self, *, admission, write_heartbeat: Callable, collect_status: Callable,
                 interval: float = 5.0, freshness_budget: float = 20.0,
                 clock: Callable = time.monotonic):
        if (not math.isfinite(interval) or not math.isfinite(freshness_budget)
                or interval <= 0 or freshness_budget <= interval):
            raise ValueError('heartbeat_invalid_budget')
        self._admission = admission
        self._write = write_heartbeat
        self._collect = collect_status
        self._interval = float(interval)
        self._budget = float(freshness_budget)
        self._clock = clock
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._wake_writer = threading.Event()
        self._threads: list[threading.Thread] = []
        self._state = 'new'
        self._error = None
        self._fatal = False
        self._started_at = None
        self._last_success = None
        self._inflight = False
        self._pulse_phase = 'idle'
        self._phase_started = None
        self._collect_seconds = None
        self._write_seconds = None
        self._schedule_lag = 0.0
        self._timeout_epoch = 0
        self._timeout_pending = False
        self._started_threads = False
        self._final_write_succeeded = False

    def start(self) -> None:
        with self._lock:
            if self._started_threads and not self._stop.is_set():
                return
            if self._state != 'new':
                raise RuntimeError('heartbeat_restart_requires_new_instance')
            self._admission.block('heartbeat')
            self._state = 'starting'
            self._started_at = self._clock()
            self._threads = [
                threading.Thread(target=self._watch, name='heartbeat-watchdog', daemon=True),
                threading.Thread(target=self._run, name='worker-heartbeat', daemon=True),
            ]
            try:
                for thread in self._threads:
                    thread.start()
                self._started_threads = True
            except BaseException:
                self._stop.set()
                self._wake_writer.set()
                self._state = 'start_failed'
                self._error = 'heartbeat_start_failed'
                self._fatal = True
                raise

    def _fail(self, code, *, fatal=False, exception_type=None):
        with self._lock:
            diagnostic = self._fail_locked(code, fatal=fatal, exception_type=exception_type)
        self._log_failure(diagnostic)

    def _fail_locked(self, code, *, fatal=False, exception_type=None):
        self._admission.block('heartbeat')
        if self._fatal:
            return None
        previous = (self._state, self._error)
        # Error codes can change after timeout (e.g. a write failure).
        # Invalidate old pulses once until a fresh successful pulse recovers.
        if code == 'heartbeat_timeout' and not self._timeout_pending:
            self._timeout_epoch += 1
            self._timeout_pending = True
        self._error = code
        self._fatal = fatal
        if not self._stop.is_set():
            self._state = 'fenced' if code == 'heartbeat_fenced' else 'error'
        if previous == (self._state, self._error):
            return None
        safe_code = code if code in _DIAGNOSTIC_CODES else 'heartbeat_failed'
        safe_type = (exception_type if isinstance(exception_type, str)
                     and len(exception_type) <= 80 and exception_type.isascii()
                     and exception_type.isidentifier() else 'none')
        now = self._clock()
        phase, collect_ms, write_ms = self._pulse_timing_locked(now)
        return safe_code, safe_type, phase, collect_ms, write_ms, self._schedule_lag * 1000

    def _pulse_timing_locked(self, now):
        collect_seconds, write_seconds = self._collect_seconds, self._write_seconds
        if self._pulse_phase == 'collect':
            collect_seconds = now - self._phase_started
        elif self._pulse_phase == 'write':
            write_seconds = now - self._phase_started
        return (self._pulse_phase,
                collect_seconds * 1000 if collect_seconds is not None else -1.,
                write_seconds * 1000 if write_seconds is not None else -1.)

    @staticmethod
    def _log_failure(diagnostic):
        if diagnostic is None:
            return
        # 日志处理器可能阻塞；所有调用者必须先退出心跳状态锁。
        try:
            logger.warning(
                '后台心跳异常：code=%s exception_type=%s phase=%s collect_ms=%.1f write_ms=%.1f schedule_lag_ms=%.1f',
                *diagnostic)
        except Exception:
            # 诊断失败不能改变既有执行门禁与失败状态。
            pass

    def _pulse(self, *, final=False):
        with self._lock:
            if self._fatal or (self._stop.is_set() and not final):
                return
            self._inflight = True
            timeout_epoch = self._timeout_epoch
            started = self._phase_started = self._clock()
            self._pulse_phase = 'collect'
            self._collect_seconds = self._write_seconds = None
        stage = 'collect'
        try:
            if final:
                # Component teardown may already make collection unavailable;
                # shutdown still publishes a minimal truthful nonready status.
                payload = {'state': 'stopping', 'ready': False}
            else:
                payload = self._collect()
                if not isinstance(payload, Mapping):
                    raise ValueError('heartbeat_invalid_collector')
                payload = dict(payload)
            with self._lock:
                timed_out = self._clock() - started >= self._budget
                diagnostic = self._fail_locked('heartbeat_timeout') if timed_out else None
                aborted = timed_out or (self._stop.is_set() and not final)
            self._log_failure(diagnostic)
            if aborted:
                return
            if final:
                payload['state'], payload['ready'] = 'stopping', False
            stage = 'write'
            with self._lock:
                self._phase_started = self._clock()
                self._collect_seconds = self._phase_started - started
                self._pulse_phase = stage
            accepted = self._write(payload)
            if accepted is not True:
                self._fail('heartbeat_fenced', fatal=True)
                return
            with self._lock:
                if final:
                    self._final_write_succeeded = True
                    return
                if self._stop.is_set() or self._fatal:
                    return
                if self._clock() - started >= self._budget:
                    diagnostic = self._fail_locked('heartbeat_timeout')
                elif timeout_epoch == self._timeout_epoch:
                    self._timeout_pending = False
                    self._last_success = self._clock()
                    self._state, self._error = 'running', None
                    self._admission.unblock('heartbeat')
            self._log_failure(diagnostic)
        except Exception as exc:
            self._fail('heartbeat_collect_failed' if stage == 'collect' else 'heartbeat_write_failed',
                       exception_type=type(exc).__name__)
        except BaseException as exc:
            self._fail('heartbeat_interrupted', fatal=True, exception_type=type(exc).__name__)
        finally:
            with self._lock:
                self._inflight = False
                elapsed = self._clock() - self._phase_started
                if self._pulse_phase == 'collect':
                    self._collect_seconds = elapsed
                else:
                    self._write_seconds = elapsed
                self._pulse_phase = 'idle'
                self._phase_started = None

    def _check_health(self):
        diagnostic = None
        with self._lock:
            if self._stop.is_set() or self._started_at is None or self._fatal:
                return
            if self._started_threads and any(not thread.is_alive() for thread in self._threads):
                diagnostic = self._fail_locked('heartbeat_thread_dead', fatal=True)
            else:
                reference = self._last_success if self._last_success is not None else self._started_at
                if self._clock() - reference >= self._budget:
                    diagnostic = self._fail_locked('heartbeat_timeout')
        self._log_failure(diagnostic)

    def _run(self):
        try:
            while not self._stop.is_set():
                self._wake_writer.clear()
                self._check_health()
                with self._lock:
                    if self._fatal:
                        return
                self._pulse()
                if not self._stop.is_set():
                    due = self._clock() + self._interval
                    woke_early = self._wake_writer.wait(self._interval)
                    with self._lock:
                        self._schedule_lag = 0. if woke_early else max(0., self._clock() - due)
            # Nonready publication is best effort. It remains part of this
            # thread, so a blocked final write is visible to stop's join budget.
            self._pulse(final=True)
        except BaseException:
            self._fail('heartbeat_interrupted', fatal=True)
        finally:
            if not self._stop.is_set():
                self._fail('heartbeat_thread_dead', fatal=True)

    def request_refresh(self) -> None:
        """Wake the single writer for a new pulse after a readiness change."""
        self._wake_writer.set()

    def _watch(self):
        try:
            while not self._stop.wait(min(.25, self._interval / 2)):
                self._check_health()
        except BaseException:
            self._fail('heartbeat_interrupted', fatal=True)

    def status(self) -> dict:
        self._check_health()
        with self._lock:
            alive = any(thread.is_alive() for thread in self._threads)
            age = None if self._last_success is None else max(0., self._clock() - self._last_success)
            healthy = (self._state == 'running' and not self._stop.is_set() and not self._fatal
                       and self._error is None and age is not None and age < self._budget
                       and self._started_threads and all(thread.is_alive() for thread in self._threads))
            return {'state': self._state, 'healthy': healthy, 'error_code': self._error,
                    'alive': alive, 'inflight': self._inflight, 'last_success_age': age,
                    'final_write_succeeded': self._final_write_succeeded}

    def stop(self, timeout: float = 3.0) -> bool:
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError('heartbeat_invalid_stop_budget')
        deadline = time.monotonic() + timeout
        with self._lock:
            self._admission.block('heartbeat')
            self._stop.set()
            self._wake_writer.set()
            self._state = 'stopping'
            threads = tuple(self._threads)
        for thread in threads:
            if thread.ident is not None and thread is not threading.current_thread():
                thread.join(max(0., deadline - time.monotonic()))
        with self._lock:
            stopped = not self._inflight and all(not thread.is_alive() for thread in threads)
            self._state = 'stopped' if stopped else 'stop_incomplete'
            return stopped
