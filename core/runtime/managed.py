"""Ordered runtime drain; lifecycle ownership is independent of business leases."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping, Sequence


class ManagedRuntime:
    def __init__(self, *, controller, heartbeat, producer_names: Sequence[str],
                 claim_names: Sequence[str], active_counts: Callable[[], Mapping],
                 flush: Callable[[float], bool], close_executors: Callable[[float], bool],
                 settle: Callable[[float], bool] | None = None,
                 close_connections: Callable[[float], bool] | None = None,
                 settlement=None, settlement_component: str | None = None,
                 close_releases: Callable[[float], bool] | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.controller = controller
        self._heartbeat = heartbeat
        self._producers = tuple(producer_names)
        self._claims = tuple(claim_names)
        self._active_counts = active_counts
        self._flush = flush
        self._settle = settle or (lambda _budget: True)
        self._close_connections = close_connections or (lambda _budget: True)
        self._close_executors = close_executors
        self._settlement = settlement
        self._settlement_component = settlement_component
        self._close_releases = close_releases or (lambda _deadline: True)
        self._clock = clock
        self._lock = threading.Lock()
        self._deadline_lock = threading.RLock()
        self._shutdown_deadline = None
        self._finalize_deadline = None
        self._finalize_callers = 0
        self._state = 'new'
        self._error = None

    def start(self) -> bool:
        with self._lock:
            if self._state == 'running':
                return False
            if self._state != 'new':
                raise RuntimeError('runtime_restart_requires_new_context')
            if self.controller.context.executes:
                self.controller.context.admission.block('heartbeat')
            self._state = 'starting'
            try:
                self.controller.start()
                if self.controller.context.executes:
                    self._heartbeat.start()
                self._state = 'running'
                return True
            except BaseException:
                self._state, self._error = 'start_failed', 'runtime_start_failed'
                # Heartbeat may have allocated a thread before raising. Do not
                # let controller release its owner until that thread has joined.
                stopped = self.controller.stop(timeout=3.0, release_owner=False)
                heartbeat_stopped = self._heartbeat is None or self._heartbeat.stop(timeout=3.0) is True
                if stopped and heartbeat_stopped:
                    self.controller.close_owner(timeout=3.0)
                raise

    def _idle(self) -> bool:
        try:
            values = self._active_counts()
            if not isinstance(values, Mapping) or not values:
                return False
            return all(isinstance(value, int) and not isinstance(value, bool) and value == 0
                       for value in values.values())
        except Exception:
            return False

    def _incomplete(self, code: str) -> bool:
        self._state, self._error = 'stop_incomplete', code
        return False

    def stop_deadline(self, timeout: float) -> float:
        """The first caller owns the budget, including callers awaiting the lock."""
        with self._deadline_lock:
            if self._shutdown_deadline is None:
                self._shutdown_deadline = self._clock() + max(0., float(timeout))
            return self._shutdown_deadline

    def _drain_settlement(self, deadline: float) -> bool:
        if self._settlement is None:
            return True
        try:
            return self._settlement.drain_runtime(deadline) is True
        except Exception:
            return False

    def _begin_settlement_shutdown(self, deadline: float, *, finalizing: bool = False) -> bool:
        if self._settlement is None:
            return True
        try:
            begin = (self._settlement.begin_finalization if finalizing
                     else self._settlement.begin_shutdown)
            return begin(deadline) is not False
        except Exception:
            return False

    def _stop_remaining_components(self, budget: float) -> bool:
        if self._settlement_component is None:
            return self.controller.stop(timeout=budget, release_owner=False)
        # The carrier stays alive through every other cleanup-producing hook.
        names = tuple(name for name in reversed(
            self.controller.status()['remaining_components'])
            if name != self._settlement_component)
        return self.controller.stop_selected(names, budget)

    def _stop_settlement(self, deadline: float) -> bool:
        if self._settlement is None:
            return True
        if self._settlement_component is not None:
            return self.controller.stop_selected((self._settlement_component,),
                max(0., deadline - self._clock()))
        return self._settlement.stop_runtime(deadline) is True

    def stop(self, timeout: float = 60.0) -> bool:
        return self._stop_with_deadline(self.stop_deadline(timeout))

    def finalization_deadline(self, timeout: float) -> float | None:
        """Reserve one later physical-close budget without renewing signal stop."""
        with self._deadline_lock:
            permitted = self._state == 'stop_incomplete' or (
                self._finalize_callers > 0 and self._state == 'draining')
            if not permitted:
                return None
            if self._finalize_deadline is None:
                self._finalize_deadline = self._clock() + max(0., float(timeout))
            return self._finalize_deadline

    def finalize_incomplete(self, timeout: float = 60.0) -> bool:
        """Explicitly finish retained resources; never restart or admit business."""
        with self._deadline_lock:
            if self._state == 'stopped':
                return self._finalize_deadline is not None
            deadline = self.finalization_deadline(timeout)
            if deadline is None:
                return False
            self._finalize_callers += 1
        try:
            return self._stop_with_deadline(deadline, finalizing=True)
        finally:
            with self._deadline_lock:
                self._finalize_callers -= 1

    def _stop_with_deadline(self, deadline: float, *, finalizing: bool = False) -> bool:
        # A second stop must not consume an independent, unbounded join budget.
        if not self._lock.acquire(timeout=max(0.0, deadline - self._clock())):
            return False
        begun = False
        try:
            if self._state == 'stopped':
                return True
            self.controller.context.admission.block('draining')
            self._state = 'draining'
            remaining = lambda: max(0.0, deadline - self._clock())
            if remaining() <= 0:
                return self._incomplete('runtime_stop_deadline_exhausted')
            if not self._begin_settlement_shutdown(deadline, finalizing=finalizing):
                return self._incomplete('runtime_settlement_shutdown_start_failed')
            begun = True
            if not self.controller.stop_selected(self._producers, remaining()):
                return self._incomplete('runtime_producers_still_running')
            if not self.controller.stop_selected(self._claims, remaining()):
                return self._incomplete('runtime_claimers_still_running')
            # The projection, proxy, reports and heartbeat remain alive here.
            # Announce the original deadline before waiting for pending work.
            if not self._drain_settlement(deadline):
                return self._incomplete('runtime_settlement_drain_timeout')
            while not self._idle():
                budget = remaining()
                if budget <= 0:
                    return self._incomplete('runtime_drain_timeout')
                threading.Event().wait(min(.05, budget))
            if self._close_executors(remaining()) is not True:
                return self._incomplete('runtime_executors_still_running')
            if not self._idle():
                return self._incomplete('runtime_executor_handoff_pending')
            try:
                if self._settle(remaining()) is not True:
                    return self._incomplete('runtime_settle_timeout')
            except Exception:
                return self._incomplete('runtime_settle_failed')
            if not self._stop_remaining_components(remaining()):
                return self._incomplete('runtime_components_still_running')
            if not self._drain_settlement(deadline):
                return self._incomplete('runtime_settlement_final_drain_timeout')
            if not self._idle():
                return self._incomplete('runtime_final_cleanup_pending')
            try:
                if self._stop_settlement(deadline) is not True:
                    return self._incomplete('runtime_settlement_still_running')
            except Exception:
                return self._incomplete('runtime_settlement_stop_failed')
            try:
                if self._close_releases(deadline) is not True:
                    return self._incomplete('runtime_permit_releases_still_running')
            except Exception:
                return self._incomplete('runtime_permit_releases_stop_failed')
            # Component shutdown can still enqueue compatibility exports.
            # Finalize those only after every potential producer has joined.
            try:
                if self._flush(remaining()) is not True:
                    return self._incomplete('runtime_flush_timeout')
            except Exception:
                return self._incomplete('runtime_flush_failed')
            if self._heartbeat is not None and self._heartbeat.stop(timeout=remaining()) is not True:
                return self._incomplete('runtime_heartbeat_still_running')
            if remaining() <= 0:
                return self._incomplete('runtime_stop_deadline_exhausted')
            if self._close_connections(remaining()) is not True:
                return self._incomplete('runtime_connections_still_running')
            if remaining() <= 0:
                return self._incomplete('runtime_stop_deadline_exhausted')
            if not self.controller.close_owner(timeout=remaining()):
                return self._incomplete('runtime_owner_close_failed')
            if remaining() <= 0:
                return self._incomplete('runtime_stop_deadline_exhausted')
            self._state, self._error = 'stopped', None
            return True
        except Exception:
            return self._incomplete('runtime_stop_failed')
        finally:
            if begun and self._state == 'stop_incomplete' and self._settlement is not None:
                # Stop's caller budget has ended, while this live carrier still
                # owns the original work. Let background local compensation use
                # its normal attempt limit; no admission reason or thread restarts.
                try:
                    self._settlement.end_shutdown(deadline)
                except Exception:
                    self._error = 'runtime_settlement_background_resume_failed'
            self._lock.release()

    def status(self) -> dict:
        # Deliberately independent of the teardown lock: heartbeat cannot block
        # behind a long join and silently go stale during a legitimate drain.
        return {'state': self._state, 'error_code': self._error}
