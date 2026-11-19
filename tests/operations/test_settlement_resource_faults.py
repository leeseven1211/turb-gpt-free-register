"""Exact resource SQL faults; native PostgreSQL cases require root opt-in."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from concurrent.futures import Future
import os
import time
import uuid
from unittest.mock import patch

import pytest

ROLLBACK_SQL = """DO $$ BEGIN
    RAISE EXCEPTION 'synthetic retryable transaction rollback' USING ERRCODE='40001';
END $$"""


class TransactionFault:
    """Fault only after matching SQL ran, or after its transaction committed."""

    def __init__(self, original, matches, *, rollbacks=0, ack_losses=0):
        self.original, self.matches = original, matches
        self.rollbacks, self.ack_losses = rollbacks, ack_losses
        self.events = []
        self.sqlstates = []

    @contextmanager
    def connect(self, *args, **kwargs):
        owner = self
        matched = False

        class Cursor:
            def __init__(self, cursor):
                self.cursor = cursor

            def __getattr__(self, name):
                return getattr(self.cursor, name)

            def __enter__(self):
                self.cursor.__enter__()
                return self

            def __exit__(self, *exc):
                return self.cursor.__exit__(*exc)

            def execute(self, sql, params=None, **options):
                nonlocal matched
                self.cursor.execute(sql, params, **options)
                if owner.matches(" ".join(str(sql).split()), params):
                    matched = True
                    owner.events.append("matched_sql")
                    if owner.rollbacks:
                        owner.rollbacks -= 1
                        owner.events.append("sql_rollback")
                        # Real PostgreSQL raises SerializationFailure inside
                        # this transaction, after the target DELETE/UPDATE.
                        try:
                            self.cursor.execute(ROLLBACK_SQL)
                        except Exception as exc:
                            owner.sqlstates.append(getattr(exc, "sqlstate", None))
                            raise
                return self

        class Connection:
            def __init__(self, connection):
                self.connection = connection

            def __getattr__(self, name):
                return getattr(self.connection, name)

            def cursor(self, *args, **kwargs):
                return Cursor(self.connection.cursor(*args, **kwargs))

        with self.original(*args, **kwargs) as connection:
            yield Connection(connection)
        if matched:
            owner.events.append("transaction_committed")
            if owner.ack_losses:
                owner.ack_losses -= 1
                owner.events.append("committed_ack_lost")
                from psycopg import OperationalError
                raise OperationalError("synthetic exact transaction ACK unavailable")


def test_fault_seam_rollback_occurs_inside_transaction_and_ack_after_commit():
    """Offline seam oracle checks transaction ordering, not product success."""
    from psycopg import OperationalError
    trace = []

    class Cursor:
        rowcount = 1
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def execute(self, sql, params=None):
            trace.append(sql)
            if sql == ROLLBACK_SQL:
                raise ArithmeticError("offline SQL error")

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def original():
        trace.append("begin")
        try:
            yield Connection()
        except Exception:
            trace.append("rollback")
            raise
        else:
            trace.append("commit")

    fault = TransactionFault(original, lambda sql, params: sql == "DELETE original",
                             rollbacks=1, ack_losses=1)
    with pytest.raises(ArithmeticError):
        with fault.connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE original")
    assert trace == ["begin", "DELETE original", ROLLBACK_SQL, "rollback"]
    trace.clear()
    with pytest.raises(OperationalError):
        with fault.connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE original")
    assert trace == ["begin", "DELETE original", "commit"]
    assert fault.events == ["matched_sql", "sql_rollback", "matched_sql",
                            "transaction_committed", "committed_ack_lost"]
    trace.clear()
    with fault.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT successor")
    assert trace == ["begin", "SELECT successor", "commit"]


def test_native_lease_offline_retains_handle_for_three_failures_and_unknown_ack():
    """Native handle semantics only; fake ledger is not PostgreSQL evidence."""
    from core.operations import task_gateway as gateway
    from core.storage import postgres
    ledger = {(7, "original"): True}
    attempts = []

    class Store:
        def release_account_lease(self, run_id, token):
            attempts.append((run_id, token))
            if len(attempts) <= 3:
                raise OSError("offline exact DELETE failed")
            if len(attempts) == 4:
                ledger.pop((run_id, token))
                ledger[(8, "successor")] = True
                raise OSError("offline committed DELETE ACK unknown")
            return bool(ledger.pop((run_id, token), False))

    with patch.object(postgres, "connect", side_effect=AssertionError("offline DB forbidden")), \
            patch.object(gateway, "_operation", return_value=Store()):
        handle = gateway.OperationLease(run_id=7, account_id=9,
            resource_family="offline", token="original")
        try:
            for _ in range(4):
                with pytest.raises(OSError):
                    handle.release()
                assert not handle.released
                assert handle.state == "release_pending"
                assert handle.token == "original"
            assert handle.release()
            assert handle.released
            assert not handle._heartbeat_thread.is_alive()
            assert ledger == {(8, "successor"): True}
            assert attempts == [(7, "original")] * 5
        finally:
            handle._heartbeat_stop.set()
            handle._heartbeat_thread.join(1)


if os.getenv("SETTLEMENT_DB_TESTS") == "1":
    from cryptography.fernet import Fernet
    from psycopg.rows import dict_row
    from tests.support_pg import PostgresTestCase
    from config.concurrency import policy_values
    from core.operations import concurrency, settlement, task_gateway as gateway
    from core.storage import postgres, records, runtime_config
    from core.storage.operations import common, permits, settlements, store, legacy_task_store

    class ResourceFaultNativePostgresTests(PostgresTestCase):
        def setUp(self):
            super().setUp()
            counts = settlement.active_counts()
            self.assertTrue(counts)
            self.assertTrue(all(value == 0 for value in counts.values()), counts)
            self.assertFalse(settlement._THREAD is not None and settlement._THREAD.is_alive())
            self.assertFalse(settlement._EXPECTED)
            self.assertFalse(settlement._SCAN_BLOCKED)
            self.assertFalse(any(not item.released for item in settlement._REGISTRY.values()))
            self.assertTrue(settlement.stop_runtime(time.monotonic() + 2))
            self.stack = ExitStack()
            self.addCleanup(self.stack.close)
            self.stack.enter_context(patch.dict(os.environ, {
                "TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            }))
            for name, value in (
                ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""),
                ("_DOMAINS", {}), ("_DEADLINE", None), ("_THREAD", None),
                ("_STOP", False), ("_STARTED", False), ("_STOP_WITH_PENDING", False),
                ("_ADMISSION", None), ("_SCAN_NEXT", {}), ("_SCAN_FAILURES", {}),
                ("_SCAN_BLOCKED", {}),
            ):
                self.stack.enter_context(patch.object(settlement, name, value))
            self.stack.enter_context(patch.object(legacy_task_store, "_SCHEMA", self.schema))
            self.stack.enter_context(patch.object(legacy_task_store, "_READY_KEY", ""))
            legacy_task_store.init()
            store.reset_ready()
            store.init()
            values = policy_values({})
            values.update(GLOBAL_TASK_WORKERS=3, ACCOUNT_PLAN_CHECK_WORKERS=3,
                          MAINTENANCE_CHECK_WORKERS=3)
            runtime_config.write_values({k: str(v) for k, v in values.items()},
                                        activate=True, source="test")
            self.contexts, self.handles, self.resource_runs = [], [], []
            self.handler_contexts = {}
            self.addCleanup(self._close_originals)

        def _close_originals(self):
            for execution in self.contexts:
                item = settlement.responsibility(execution)
                if item.intent is None:
                    if not item._callback_started:
                        gateway.rollback_admission(execution, reason="resource_fixture_exit")
                    else:
                        # Resume the original context and its exact lease and
                        # renewal handles after the callback scope has exited.
                        # A new execution_scope would register a second renewal
                        # under the same immutable cleanup key.
                        context = self.handler_contexts[execution.execution_id]
                        self.assertIs(context._execution, execution)
                        try:
                            context.finish(status="cancelled")
                        except gateway.OperationSettlementPending:
                            pass  # The same intent is drained below.
                if item._callback_started:
                    settlement.callback_exited(execution)
                settlement.request_release(execution)
                self._until(execution, lambda: execution.released)
            for handle in self.handles:
                if not handle.released:
                    handle.release()
                self.assertTrue(handle.join(deadline=time.monotonic() + 2))
            for run_id, execution_id in self.resource_runs:
                if store.get_run(run_id)["status"] in {"running", "cancelling", "settling"}:
                    store.finish_run(run_id, status="cancelled", execution_id=execution_id)
            self.assertTrue(settlement.stop_runtime(time.monotonic() + 2))
            self.assertTrue(concurrency.stop_release_runtime(time.monotonic() + 2))
            self.assertTrue(all(value == 0 for value in settlement.active_counts().values()))
            self.assertFalse(settlement._SCAN_BLOCKED)
            self.assertFalse(settlement._THREAD is not None and settlement._THREAD.is_alive())

        def _until(self, execution, predicate, timeout=20):
            deadline = time.monotonic() + timeout
            while not predicate() and time.monotonic() < deadline:
                settlement._progress(settlement.responsibility(execution))
                time.sleep(.01)
            self.assertTrue(predicate(), settlement.runtime_status())

        def _progress_once(self, execution):
            item = settlement.responsibility(execution)
            delay = item.next_attempt - time.monotonic()
            if delay > 0:
                time.sleep(delay + .005)
            settlement._progress(item)

        def _create(self, *, account=True, task_type="plan_check"):
            account_id = records.insert_row(records.ACCOUNTS, {
                "email": f"resource-{uuid.uuid4().hex}@example.test",
            }) if account else None
            task = store.create_runtime_task(task_type=task_type, account_id=account_id,
                email="", resource_family="resource_fault", trigger="test")
            admitted = gateway.admit_operation_run(store.get_run(task["run"]["id"]))
            self.assertTrue(admitted.admitted, admitted.blocked_by)
            self.contexts.append(admitted.context)
            return task, admitted.context

        def _permit_row(self, execution):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {permits._permit_table(self.schema)} "
                            "WHERE permit_id=%s AND execution_id=%s",
                            (execution.permit_id, execution.execution_id))
                return dict(cur.fetchone())

        def _lease_row(self, run_id):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {common._table('account_operation_leases')} WHERE run_id=%s",
                            (run_id,))
                row = cur.fetchone()
                return dict(row) if row else None

        def _pending_negative_entries(self, execution, *, state):
            """Actual outer/future handoff, release API, retry and recovery."""
            self.assertFalse(execution.released, state)
            self.assertFalse(concurrency.release_execution(execution), state)
            # Actual noncancelled Future completion takes this same handoff.
            future = Future()
            future.add_done_callback(lambda completed: gateway._handoff_execution(
                execution, reason="future_completed"))
            future.set_exception(gateway.OperationSettlementPending("original pending"))
            permits.mark_execution_exited(execution.permit_id, execution.execution_id)
            self.assertIn((execution.permit_id, execution.execution_id), permits._LOCAL_EXITS)
            self.assertEqual(0, permits.recover_execution_permits()["released"], state)
            self.assertFalse(execution.released, state)
            self.assertIsNone(self._permit_row(execution)["released_at"], state)
            self.assertNotIn((execution.permit_id, execution.execution_id),
                             concurrency._RELEASE_PENDING, state)
            self.assertEqual(0, concurrency.release_runtime_status()["pending"], state)
            concurrency._retry_releases()  # Empty native queue cannot adopt it.
            self.assertIsNone(self._permit_row(execution)["released_at"], state)
            self.assertFalse(settlement.release_eligible(execution), state)
            self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
            with self.assertRaises(gateway.OperationSettlementConflict):
                gateway.rollback_admission(execution, reason="future_retry_must_not_replay")

        def _lease_fault(self, handle, *, rollbacks, ack_losses):
            return TransactionFault(common._connect, lambda sql, params:
                sql.startswith("DELETE") and '"account_operation_leases"' in sql
                and tuple(params or ()) == (handle.run_id, handle.token),
                rollbacks=rollbacks, ack_losses=ack_losses)

        def _permit_fault(self, execution):
            return TransactionFault(postgres.connect, lambda sql, params:
                sql.startswith("UPDATE") and '"operation_execution_permits"' in sql
                and "SET released_at=now()" in sql
                and tuple(params or ())[-2:] == (execution.permit_id, execution.execution_id),
                rollbacks=1, ack_losses=1)

        def _one_terminal(self, execution):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {common._table('operation_settlement_receipts')} "
                            "WHERE permit_id=%s AND execution_id=%s",
                            (execution.permit_id, execution.execution_id))
                self.assertEqual(1, cur.fetchone()[0])
                cur.execute(f"SELECT count(*) FROM {common._table('operation_events')} "
                            "WHERE run_id=%s AND event_type IN ('run.success','run.attention_required')",
                            (execution.claimed_run["id"],))
                self.assertEqual(1, cur.fetchone()[0])

        def _finish_permit_faults(self, execution):
            fault = self._permit_fault(execution)
            original_row = self._permit_row(execution)
            with patch.object(postgres, "connect", side_effect=fault.connect):
                self._until(execution, lambda: "sql_rollback" in fault.events)
                self.assertIn("sql_rollback", fault.events)
                self.assertEqual(original_row, self._permit_row(execution))
                self.assertFalse(execution.released)
                self._pending_negative_entries(execution, state="permit_transaction_rolled_back")
                self._until(execution, lambda: "committed_ack_lost" in fault.events)
                self.assertIn("committed_ack_lost", fault.events)
                committed = self._permit_row(execution)
                self.assertIsNotNone(committed["released_at"])
                self.assertFalse(execution.released)
                self._until(execution, lambda: execution.released)
                self.assertTrue(execution.released)
                self.assertEqual(committed, self._permit_row(execution))
            self.assertEqual(1, fault.events.count("sql_rollback"))
            self.assertEqual(["40001"], fault.sqlstates)
            self.assertEqual(1, fault.events.count("committed_ack_lost"))
            self.assertNotIn((execution.permit_id, execution.execution_id), permits._LOCAL_EXITS)
            self.assertEqual(0, concurrency.release_runtime_status()["pending"])
            self._one_terminal(execution)

        def _successor_unchanged(self, task, execution, handle):
            old_intent = settlement.responsibility(execution).intent
            next_run = store.retry_runtime_task(task["id"], trigger="test")
            admitted = gateway.admit_operation_run(store.get_run(next_run["id"]))
            self.assertTrue(admitted.admitted, admitted.blocked_by)
            successor = admitted.context
            self.contexts.append(successor)
            with concurrency.execution_scope(successor):
                self.assertTrue(settlement.callback_started(successor))
                context = gateway.OperationHandlerContext(successor.claimed_run,
                    execution_id=successor.execution_id)
                self.handler_contexts[successor.execution_id] = context
                new_handle = context.acquire_lease(scope_kind="final")
                self.handles.append(new_handle)
                before = (store.get_task(task["id"], include_events=False),
                          store.get_run(next_run["id"]), self._lease_row(next_run["id"]),
                          self._permit_row(successor))
                self.assertNotEqual(handle.token, new_handle.token)
                self.assertFalse(store.release_account_lease(handle.run_id, handle.token))
                settlements.submit_intent(old_intent, domain=execution.settlement_domain)
                after = (store.get_task(task["id"], include_events=False),
                         store.get_run(next_run["id"]), self._lease_row(next_run["id"]),
                         self._permit_row(successor))
                self.assertEqual(before, after)
                context.finish(status="cancelled")
            settlement.callback_exited(successor)
            settlement.request_release(successor)
            self._until(successor, lambda: successor.released)

        def test_s04_s05_step_three_sql_rollbacks_ack_loss_and_exact_successor(self):
            task, execution = self._create()
            calls, next_steps = [], []
            captured = {}

            def callback():
                calls.append(1)
                context = gateway.OperationHandlerContext(execution.claimed_run,
                    execution_id=execution.execution_id)
                self.handler_contexts[execution.execution_id] = context
                captured["context"] = context
                lease = context.acquire_lease(scope_kind="step")
                captured["lease"] = lease
                self.handles.append(lease)
                with patch.object(common, "_connect", side_effect=fault.connect):
                    context.release_lease()
                next_steps.append("must never resume")

            # Match identity only after native acquisition has supplied it.
            fault = TransactionFault(common._connect, lambda sql, params:
                sql.startswith("DELETE") and '"account_operation_leases"' in sql
                and captured.get("lease") is not None
                and tuple(params or ()) == (captured["lease"].run_id, captured["lease"].token),
                rollbacks=3, ack_losses=1)
            with self.assertRaises(gateway.OperationSettlementPending):
                gateway.execute_admitted(execution, callback)
            handle, context = captured["lease"], captured["context"]
            frozen = settlement.responsibility(execution).intent
            self.assertEqual("step_release_unconfirmed", frozen.origin["lease_requirement"])
            self.assertIs(context._lease, handle)
            with self.assertRaises(gateway.OperationSettlementConflict):
                context.acquire_lease()
            with self.assertRaises(ValueError):
                store.retry_runtime_task(task["id"], trigger="test_pending_must_not_replay")
            with patch.object(common, "_connect", side_effect=fault.connect):
                self._pending_negative_entries(execution, state="terminal_unconfirmed")
                for expected in (2, 3):
                    self._progress_once(execution)
                    self.assertEqual(expected, fault.events.count("sql_rollback"))
                    self.assertEqual(handle.token, self._lease_row(handle.run_id)["lease_token"])
                    self.assertFalse(handle.released)
                    self._pending_negative_entries(execution, state="step_cleanup_pending")
                self._progress_once(execution)
                self.assertIn("committed_ack_lost", fault.events)
                self.assertIsNone(self._lease_row(handle.run_id))
                self.assertFalse(handle.released)
                self.assertIsNone(settlements.read_receipt(frozen, domain=execution.settlement_domain))
                self._pending_negative_entries(execution, state="step_commit_ack_unknown")
                self._progress_once(execution)  # exact missing-token DELETE confirmation
            self._until(execution, lambda: settlement.responsibility(execution).receipt is not None)
            self.assertTrue(handle.released)
            self.assertEqual([1], calls)
            self.assertEqual([], next_steps)
            self.assertEqual(["40001"] * 3, fault.sqlstates)
            self.assertEqual(1, fault.events.count("committed_ack_lost"))
            self.assertIs(settlement.responsibility(execution).intent, frozen)
            # Next progress reaches permit only after durable local cleanup.
            self._finish_permit_faults(execution)
            self._successor_unchanged(task, execution, handle)

        def test_s04_s05_s13_terminal_residual_delete_and_permit_transaction_faults(self):
            # Resource assembly is synthetic; both native Runs and exact
            # account-lease DELETE below are real storage, with no remote call.
            account_id = records.insert_row(records.ACCOUNTS, {
                "email": f"residual-{uuid.uuid4().hex}@example.test"})
            resource_task = store.create_runtime_task(task_type="plan_check", account_id=account_id,
                email="", resource_family="residual_resource", trigger="test")
            resource_run = resource_task["run"]["id"]
            resource_execution = uuid.uuid4().hex
            self.assertTrue(store.claim_run(resource_run, execution_id=resource_execution,
                                           worker_pid=os.getpid()))
            self.resource_runs.append((resource_run, resource_execution))
            token = store.acquire_account_lease(account_id=account_id, run_id=resource_run,
                                               resource_family="residual_resource")
            task, execution = self._create(account=False, task_type="maintenance_check")
            handle = gateway.OperationLease(run_id=resource_run, account_id=account_id,
                resource_family="residual_resource", token=token,
                domain=execution.settlement_domain, execution_id=resource_execution)
            self.handles.append(handle)
            calls = []

            def callback():
                calls.append(1)
                context = gateway.OperationHandlerContext(execution.claimed_run,
                    execution_id=execution.execution_id)
                self.handler_contexts[execution.execution_id] = context
                context.register_cleanup(handle, key=f"native-residual:{resource_run}:{handle.scope_id}")
                context.finish(status="success", result_summary={"local_business_writeback_confirmed": True})

            gateway.execute_admitted(execution, callback)
            item = settlement.responsibility(execution)
            receipt = settlements.read_receipt(item.intent, domain=execution.settlement_domain)
            self.assertEqual("success", receipt["status"])
            fault = self._lease_fault(handle, rollbacks=3, ack_losses=1)
            with patch.object(common, "_connect", side_effect=fault.connect):
                for expected in (1, 2, 3):
                    self._progress_once(execution)
                    self.assertEqual(expected, fault.events.count("sql_rollback"))
                    self.assertEqual(token, self._lease_row(resource_run)["lease_token"])
                    self.assertFalse(handle.released)
                    self._pending_negative_entries(execution, state="terminal_confirmed_residual_pending")
                    self.assertEqual(receipt, settlements.read_receipt(item.intent,
                                                        domain=execution.settlement_domain))
                self._progress_once(execution)
                self.assertIsNone(self._lease_row(resource_run))
                self.assertFalse(handle.released)
                self._pending_negative_entries(execution, state="residual_commit_ack_unknown")
            # Isolate the real permit rollback/ACK transaction before the
            # confirmation tick can proceed from cleanup into permit release.
            permit_fault = self._permit_fault(execution)
            original_permit = self._permit_row(execution)
            with patch.object(postgres, "connect", side_effect=permit_fault.connect):
                self._until(execution, lambda: "sql_rollback" in permit_fault.events)
                self.assertTrue(handle.released)
                self.assertIn("sql_rollback", permit_fault.events)
                self.assertEqual(original_permit, self._permit_row(execution))
                self.assertFalse(execution.released)
                self._pending_negative_entries(execution, state="residual_done_permit_transaction_rolled_back")
                self._until(execution, lambda: "committed_ack_lost" in permit_fault.events)
                self.assertIsNotNone(self._permit_row(execution)["released_at"])
                self.assertFalse(execution.released)
                committed = self._permit_row(execution)
                self._until(execution, lambda: execution.released)
                self.assertTrue(execution.released)
                self.assertEqual(committed, self._permit_row(execution))
            self.assertEqual(1, permit_fault.events.count("sql_rollback"))
            self.assertEqual(["40001"] * 3, fault.sqlstates)
            self.assertEqual(["40001"], permit_fault.sqlstates)
            self.assertEqual(1, permit_fault.events.count("committed_ack_lost"))
            self.assertEqual([1], calls)
            self._one_terminal(execution)
            self.assertEqual(receipt, settlements.read_receipt(item.intent, domain=execution.settlement_domain))
            self.assertEqual("success", store.get_run(execution.claimed_run["id"])["status"])
            store.finish_run(resource_run, status="cancelled", execution_id=resource_execution)
            self.assertEqual("cancelled", store.get_run(resource_run)["status"])
            self.assertIsNone(self._lease_row(resource_run))
            self._successor_unchanged(resource_task, execution, handle)
