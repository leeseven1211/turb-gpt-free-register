"""Native test-owned settlement carrier; never synthesize release or receipts."""
from __future__ import annotations

from concurrent.futures import wait
from contextlib import ExitStack
import threading
import time
from unittest.mock import patch

from core.operations import concurrency, settlement, task_gateway
from core.operations.executor import AccountOperationExecutor, executor, extract_executor
from core.storage.operations import common, permits, settlements


LIFECYCLE_DEFAULTS = (
    ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""),
    ("_CARRIER_ERROR", ""), ("_DOMAINS", {}), ("_DEADLINE", None),
    ("_THREAD", None), ("_STARTED", False), ("_STOP", False),
    ("_STOP_WITH_PENDING", False), ("_ADMISSION", None),
    ("_SCAN_NEXT", {}), ("_SCAN_FAILURES", {}), ("_SCAN_ERROR", ""),
    ("_SCAN_BLOCKED", {}), ("_SCAN_INFLIGHT", 0), ("_RESERVATIONS", 0),
)

_RETAINED_NATIVE_FIXTURES = {}


class NativeSettlementAbort(KeyboardInterrupt):
    """Abort a native test stage while retaining its original dependencies."""


class NativeSettlementFixture:
    """Own one real carrier until callbacks, durable tails and permits close."""

    def __init__(self, *, domain=None, timeout=10.0):
        self.domain = domain
        self.timeout = float(timeout)
        self.contexts = {}
        self.futures = set()
        self._future_callbacks = []
        self._active_callbacks = 0
        self._condition = threading.Condition()
        self._stack = ExitStack()
        self._started = False
        self._isolated = False
        self._closed = False
        self._blocked_cleanups = []
        self._test_case = None
        self._restoring_dependencies = False

    def start(self):
        prior = settlement._THREAD
        assert prior is None or not prior.is_alive(), settlement.runtime_status()
        assert all(value == 0 for value in settlement.active_counts().values()), settlement.runtime_status()
        assert not settlement._EXPECTED and not settlement._SCAN_BLOCKED
        assert settlement._RESERVATIONS == settlement._SCAN_INFLIGHT == 0
        assert settlement._RESERVATION.get() is None
        assert not any(concurrency.release_runtime_status().values())
        assert not task_gateway.dispatcher_status()["alive"]
        assert not task_gateway.dependency_dispatcher_status()["alive"]
        self._assert_executor_idle()
        if self.domain is None:
            self.domain = permits._settlement_domain()
        self._isolated = True
        for name, value in LIFECYCLE_DEFAULTS:
            fresh = value.copy() if isinstance(value, (dict, set)) else value
            self._stack.enter_context(patch.object(settlement, name, fresh))
        original_register = settlement.register_execution
        original_execute = task_gateway.execute_admitted

        def register(execution, ticket):
            item = original_register(execution, ticket)
            assert execution.settlement_domain == self.domain
            with self._condition:
                self.contexts[(execution.permit_id, execution.execution_id)] = execution
                self._condition.notify_all()
            return item

        def execute(execution, callback):
            with self._condition:
                self._active_callbacks += 1
            try:
                return original_execute(execution, callback)
            finally:
                with self._condition:
                    self._active_callbacks -= 1
                    self._condition.notify_all()

        self._stack.enter_context(patch.object(settlement, "register_execution", register))
        self._stack.enter_context(patch.object(task_gateway, "execute_admitted", execute))
        for name in ("submit", "try_submit"):
            original_submit = getattr(AccountOperationExecutor, name)

            def submit(pool, *args, _original=original_submit, **kwargs):
                future = _original(pool, *args, **kwargs)
                if future is not None:
                    with self._condition:
                        if future not in self.futures:
                            self.futures.add(future)
                            original_add = future.add_done_callback

                            def add_callback(callback):
                                exited = threading.Event()
                                with self._condition:
                                    self._future_callbacks.append(exited)

                                def observed(completed):
                                    try:
                                        return callback(completed)
                                    finally:
                                        exited.set()
                                        with self._condition:
                                            self._condition.notify_all()

                                return original_add(observed)

                            self._stack.enter_context(patch.object(future, "add_done_callback", add_callback))
                        self._condition.notify_all()
                return future

            self._stack.enter_context(patch.object(AccountOperationExecutor, name, submit))
        try:
            assert settlement.start_runtime(domain=self.domain), settlement.runtime_status()
        except BaseException:
            # Keep this object reachable by the caller even when startup's
            # actual stop/join cannot complete. Dependency cleanup must retry
            # this gate before restoring any schema/log patches.
            self.close()
            raise
        self._started = True
        return self

    def close(self):
        if self._closed:
            self._restore_retained_dependencies()
            return
        if not self._isolated:
            self._closed = True  # Entry refused; this fixture changed nothing.
            self._restore_retained_dependencies()
            return
        deadline = time.monotonic() + self.timeout
        if not self._started:
            assert not self.contexts and not self.futures and not self._active_callbacks
            assert settlement.stop_runtime(deadline), settlement.runtime_status()
            assert all(value == 0 for value in settlement.active_counts().values()), settlement.runtime_status()
            self._stack.close()
            self._closed = True
            self._restore_retained_dependencies()
            return
        # Stop producers, then await the actual future/callback exits. Never
        # call callback_exited or replace a pending result from fixture code.
        assert task_gateway.stop_dispatcher(timeout=max(0.0, deadline - time.monotonic()))
        assert task_gateway.stop_dependency_dispatcher(timeout=max(0.0, deadline - time.monotonic()))
        while True:
            with self._condition:
                futures = tuple(self.futures)
            _, unfinished = wait(futures, timeout=max(0.0, deadline - time.monotonic()))
            with self._condition:
                if (not unfinished and not self._active_callbacks
                        and self.futures == set(futures)
                        and all(event.is_set() for event in self._future_callbacks)):
                    break
            assert time.monotonic() < deadline, settlement.runtime_status()
            with self._condition:
                self._condition.wait(min(.01, max(0.0, deadline - time.monotonic())))
        assert settlement.drain_runtime(deadline), settlement.runtime_status()
        # Nonblocking tails (notably run_log) may still be pending after the
        # original permit releases. Keep the real scanner alive until every
        # domain tail reaches its own durable terminal state.
        # Drain publishes its budget to background attempts. Lift that bound
        # after truthful completion so an independent tail retry can progress;
        # the fixture's own original close deadline remains unchanged.
        assert settlement.end_shutdown(settlement._DEADLINE)
        while self._cleanup_counts(deadline):
            assert time.monotonic() < deadline, "native fixture durable cleanup remains pending"
            with self._condition:
                self._condition.wait(min(.01, max(0.0, deadline - time.monotonic())))
        assert settlement.drain_runtime(deadline), settlement.runtime_status()
        assert settlement.stop_runtime(deadline), settlement.runtime_status()
        assert concurrency.stop_release_runtime(deadline), concurrency.release_runtime_status()
        assert settlement._THREAD is not None and not settlement._THREAD.is_alive()
        assert all(value == 0 for value in settlement.active_counts().values()), settlement.runtime_status()
        assert not settlement._EXPECTED and not settlement._SCAN_BLOCKED
        self._assert_executor_idle()
        self._readback(deadline)
        # A failure above deliberately retains the original registry/patches.
        # Only proven physical and database closure authorizes restoration.
        self._stack.close()
        self._closed = True
        self._restore_retained_dependencies()

    def _restore_retained_dependencies(self):
        # A later explicit close may repair a failed test's original actors.
        # Restore retained dependencies only after that real close succeeds.
        if self._restoring_dependencies:
            return
        self._restoring_dependencies = True
        try:
            while self._blocked_cleanups:
                function, args, kwargs = self._blocked_cleanups[0]
                function(*args, **kwargs)
                self._blocked_cleanups.pop(0)
            owner = self._test_case
            if owner is not None and id(owner) in _RETAINED_NATIVE_FIXTURES:
                stack, _directory = owner._native_retained_export_scope
                stack.close()
                del owner._native_retained_export_scope
                _RETAINED_NATIVE_FIXTURES.pop(id(owner))
        finally:
            self._restoring_dependencies = False

    @staticmethod
    def _assert_executor_idle():
        for pool in (executor, extract_executor):
            status = pool.runtime_status()
            assert status["accepted"] == status["active"] == 0, status
        with task_gateway._RUN_DISPATCH_LOCK:
            assert not task_gateway._RUN_DISPATCHED

    def wait_for_run_released(self, run_id):
        """Read one original generation until its real carrier releases it.

        This is a subcase boundary, not shutdown: no drain, progress, release,
        deadline reset, handler retry, or policy change is performed here.
        """
        with self._condition:
            matches = [execution for execution in self.contexts.values()
                       if int(execution.claimed_run["id"]) == int(run_id)]
        assert len(matches) == 1, "release wait requires exactly one original admission"
        self.wait_for_execution_released(matches[0])

    def wait_for_execution_released(self, execution):
        """Observe one exact admission when the same Run has multiple generations."""
        with self._condition:
            identity = (execution.permit_id, execution.execution_id)
            assert self.contexts.get(identity) is execution, "release wait requires this fixture's original admission"
        deadline = time.monotonic() + self.timeout
        while True:
            released = False
            if execution.released:
                # Permit release publishes on the context before the
                # coordinator publishes its matching responsibility result.
                # Read the second gate under its own publication lock.
                with settlement._LOCK:
                    item = settlement.responsibility(execution)
                    released = bool(item is not None and item.released
                                    and item.callback_exited and not item.callback_active)
            if released and not self._cleanup_counts(deadline, execution=execution):
                self._readback(deadline, executions=(execution,), whole_domain=False)
                return
            assert time.monotonic() < deadline, "original run release wait expired"
            with self._condition:
                self._condition.wait(min(.01, max(0.0, deadline - time.monotonic())))

    def _cleanup_counts(self, deadline, *, execution=None):
        selector = "domain_id=%s"
        params = (self.domain.domain_id,)
        if execution is not None:
            selector += " AND permit_id=%s AND execution_id=%s"
            params += (execution.permit_id, execution.execution_id)
        with common.settlement_scope(self.domain, deadline=deadline), common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT state,count(*) AS n FROM {common._table('operation_settlement_cleanup')} "
                f"WHERE {selector} AND state NOT IN ('done','superseded') GROUP BY state",
                params,
            )
            counts = {row["state"]: int(row["n"]) for row in cur.fetchall()}
        assert not counts.get("reconciliation_required"), "native fixture cleanup requires reconciliation"
        return counts

    def _readback(self, deadline, *, executions=None, whole_domain=True):
        executions = tuple(self.contexts.values()) if executions is None else executions
        with common.settlement_scope(self.domain, deadline=deadline), common._connect() as conn, conn.cursor() as cur:
            for execution in executions:
                item = settlement.responsibility(execution)
                assert item is not None and item.released and execution.released
                assert not item.callback_active and item.callback_exited
                cur.execute(
                    f"SELECT permit_id,execution_id,run_id,released_at,metadata "
                    f"FROM {permits._permit_table(self.domain.permit_schema)} "
                    "WHERE permit_id=%s AND execution_id=%s",
                    (execution.permit_id, execution.execution_id),
                )
                permit = cur.fetchone()
                assert permit and permit["released_at"] is not None
                assert int(permit["run_id"]) == int(execution.claimed_run["id"])
                ticket = common._decode(permit["metadata"])["settlement_ticket"]
                assert ticket == dict(execution.settlement_ticket)
                assert item.intent is not None
                with common.settlement_scope(self.domain, deadline=deadline, conn=conn):
                    receipt = settlements.read_receipt(item.intent, domain=self.domain, deadline=deadline)
                if item.receipt is not None:
                    assert receipt is not None and receipt["transition_id"] == item.intent.transition_id
                else:
                    assert receipt is None and item.disposition is not None
                    disposition = settlements.read_disposition(
                        item.ticket, domain=self.domain, conn=conn, deadline=deadline,
                    )
                    assert disposition and disposition["disposition_kind"] == "live_superseded"
                    result = disposition["result"]
                    assert disposition["original_intent_committed"] is result["original_intent_committed"] is False
                    assert result["transition_id"] == item.intent.transition_id
                    assert result["request_digest"] == item.intent.request_digest
                    assert result["lease_disposition"] == "exact_original_token_absent"
                    for key in ("domain_id", "permit_id", "execution_id", "ticket_id", "run_id", "run_uuid"):
                        assert str(disposition[key]) == str(item.intent.origin[key])
                assert not settlements.cleanup_blocks_permit(
                    execution.permit_id, execution.execution_id,
                    domain=self.domain, conn=conn, deadline=deadline,
                )
                renewal = getattr(execution, "_permit_renewal", None)
                if renewal is not None:
                    assert renewal.release_confirmed and not renewal.thread.is_alive()
                leases = [lease for lease, _ in item._leases]
                leases.extend(cleanup.handle for cleanup in item._cleanups
                              if isinstance(cleanup.handle, task_gateway.OperationLease))
                for lease in leases:
                    assert lease.released
                    assert lease.join(deadline=deadline)
                    assert not lease._heartbeat_thread.is_alive()
                    cur.execute(
                        f"SELECT 1 FROM {common._table('account_operation_leases')} "
                        "WHERE run_id=%s AND lease_token=%s",
                        (lease.run_id, lease.token),
                    )
                    assert cur.fetchone() is None
            if whole_domain:
                cur.execute(
                    f"SELECT count(*) AS n FROM {permits._permit_table(self.domain.permit_schema)} "
                    "WHERE released_at IS NULL",
                )
                assert cur.fetchone()["n"] == 0
        if whole_domain:
            assert not self._cleanup_counts(deadline)


def install_native_settlement_fixture(test_case, *, timeout=10.0):
    """Call after native schema init; register cleanup after log/schema patches."""
    fixture = NativeSettlementFixture(timeout=timeout)
    fixture._test_case = test_case
    test_case.settlement_fixture = fixture
    test_class = type(test_case)
    if "_native_settlement_owners" not in test_class.__dict__:
        test_class._native_settlement_owners = []
    test_class._native_settlement_owners.append(test_case)

    def schema_guard():
        for owner in test_class._native_settlement_owners:
            owned_fixture = owner.settlement_fixture
            if not owned_fixture._closed or owned_fixture._blocked_cleanups or id(owner) in _RETAINED_NATIVE_FIXTURES:
                raise NativeSettlementAbort("native settlement remains owned; schema cleanup refused")

    test_class._native_settlement_before_schema_use = staticmethod(schema_guard)

    def after_run(stack, directory):
        if fixture._closed and not fixture._blocked_cleanups:
            return
        # Strong module retention outlives unittest's instance references.
        # Detach only tempfile's automatic finalizer; actual cleanup remains
        # on the retained ExitStack for an explicitly proven later closure.
        directory._finalizer.detach()
        test_case._native_retained_export_scope = (stack, directory)
        _RETAINED_NATIVE_FIXTURES[id(test_case)] = test_case
        raise NativeSettlementAbort("native settlement remains owned; test stage aborted")

    test_case._native_settlement_after_run = after_run
    original_add_cleanup = test_case.addCleanup

    def guarded_cleanup(function, *args, **kwargs):
        def after_settlement():
            try:
                fixture.close()
            except BaseException:
                fixture._blocked_cleanups.append((function, args, kwargs))
                raise
            return function(*args, **kwargs)
        return after_settlement

    # unittest continues through every cleanup after one failure. Guard both
    # already-registered dependencies and later test-body cleanups so none can
    # restore schemas/logs/mocks while an original native actor remains.
    test_case._cleanups[:] = [
        (guarded_cleanup(function, *args, **kwargs), (), {})
        for function, args, kwargs in test_case._cleanups
    ]

    def add_cleanup(function, *args, **kwargs):
        original_add_cleanup(guarded_cleanup(function, *args, **kwargs))

    test_case.addCleanup = add_cleanup
    test_case.addCleanup(fixture.close)
    fixture.start()
    return fixture
