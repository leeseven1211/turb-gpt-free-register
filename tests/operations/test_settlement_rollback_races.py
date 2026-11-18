"""S15 rollback/start contention, offline first and root-exclusive native PG."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import os
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch
import uuid

from core.operations import settlement, task_gateway
from core.operations.settlement_contracts import (
    OperationSettlementConflict, OperationSettlementPending, seal_intent,
)


def contend_callback_and_rollback(execution):
    """Both native barrier entrants run only after the same three-party gate."""
    gate = threading.Barrier(3)
    outcomes, callback_calls, errors = {}, [], []

    def callback():
        try:
            gate.wait(timeout=5)
            started = settlement.callback_started(execution)
            outcomes["callback_started"] = started
            if started:
                callback_calls.append(execution.execution_id)
        except BaseException as exc:
            errors.append(exc)

    def rollback():
        try:
            gate.wait(timeout=5)
            task_gateway.rollback_admission(execution, reason="s15_same_barrier")
            outcomes["rollback"] = "confirmed"
        except OperationSettlementConflict:
            outcomes["rollback"] = "callback_won"
        except BaseException as exc:
            errors.append(exc)

    workers = [threading.Thread(target=callback), threading.Thread(target=rollback)]
    for worker in workers:
        worker.start()
    gate.wait(timeout=5)
    for worker in workers:
        worker.join(timeout=10)
        if worker.is_alive():
            raise AssertionError("native rollback/start contender did not join")
    if errors:
        raise errors[0]
    return outcomes, callback_calls


class SettlementRollbackRaceOfflineTests(unittest.TestCase):
    def setUp(self):
        from core.storage import postgres
        previous = settlement._THREAD
        self.assertTrue(previous is None or not previous.is_alive(), settlement.runtime_status())
        self.assertTrue(all(value == 0 for value in settlement.active_counts().values()),
                        settlement.runtime_status())
        self.assertFalse(settlement._EXPECTED)
        self.assertEqual(0, settlement._RESERVATIONS)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (
            ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""), ("_DOMAINS", {}),
            ("_THREAD", None), ("_STOP", False), ("_STOP_WITH_PENDING", False), ("_STARTED", False),
            ("_ADMISSION", None), ("_DEADLINE", None), ("_SCAN_NEXT", {}),
            ("_SCAN_FAILURES", {}), ("_SCAN_ERROR", ""),
        ):
            self.stack.enter_context(patch.object(settlement, name, value))
        self.stack.enter_context(patch.object(postgres, "connect", side_effect=AssertionError("offline DB forbidden")))
        self.stack.enter_context(patch.object(postgres, "database_url", side_effect=AssertionError("offline config forbidden")))
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.receipts, self.releases, self.executions = {}, [], []
        self.stack.enter_context(patch("core.storage.operations.settlements.submit_intent",
                                      side_effect=self._submit))
        self.stack.enter_context(patch.object(settlement, "_release_execution", side_effect=self._release))
        self.addCleanup(self._close_originals)

    def _submit(self, intent, **kwargs):
        return self.receipts.setdefault(intent.transition_id, {
            "transition_id": intent.transition_id, "request_digest": intent.request_digest,
            "actual_result": {"status": "queued" if intent.kind == "defer" else intent.payload["status"]},
        })

    def _release(self, execution, reason, deadline):
        item = settlement.responsibility(execution)
        self.assertIsNotNone(item.receipt)
        self.assertFalse(item.callback_active)
        self.assertTrue(item.callback_exited)
        self.releases.append((execution.permit_id, execution.execution_id))
        execution.released = True
        return True

    def _new_execution(self):
        identifier = uuid.uuid4().hex
        execution = SimpleNamespace(permit_id="p-" + identifier, execution_id="e-" + identifier,
            execution_key="operation_run:7", released=False, settlement_domain=None,
            claimed_run={"id": 7, "task_id": 8})
        execution.settlement_ticket = {"permit_id": execution.permit_id,
                                      "execution_id": execution.execution_id, "run_id": 7, "task_id": 8}
        settlement.register_execution(execution, execution.settlement_ticket)
        self.executions.append(execution)
        return execution

    def _confirm_callback(self, execution):
        intent = seal_intent(kind="terminal", origin=execution.settlement_ticket,
                             payload={"status": "success"})
        settlement.settle(execution, intent, lambda original, deadline: self._submit(original))
        settlement.callback_exited(execution)
        settlement.request_release(execution)

    def _close_originals(self):
        for execution in self.executions:
            item = settlement.responsibility(execution)
            if item.intent is None:
                self._confirm_callback(execution)
            settlement.callback_exited(execution)
            settlement.request_release(execution)
            settlement._progress(item)
            self.assertTrue(execution.released, settlement.runtime_status())
        self.assertTrue(all(value == 0 for value in settlement.active_counts().values()))
        self.assertFalse(settlement._EXPECTED)

    def test_s15_callback_and_unstarted_rollback_contend_at_same_barrier(self):
        for iteration in range(32):
            with self.subTest(iteration=iteration):
                execution = self._new_execution()
                outcomes, calls = contend_callback_and_rollback(execution)
                item = settlement.responsibility(execution)
                self.assertEqual(int(outcomes["callback_started"]), len(calls))
                self.assertTrue(item.release_requested)
                self.assertFalse(execution.released)
                self.assertNotIn((execution.permit_id, execution.execution_id), self.releases)
                if outcomes["callback_started"]:
                    self.assertEqual("callback_won", outcomes["rollback"])
                    self.assertTrue(item.callback_active)
                    self.assertFalse(item.callback_exited)
                    self.assertIsNone(item.intent)
                    self.assertIsNone(item.receipt)
                    self._confirm_callback(execution)
                else:
                    self.assertEqual("confirmed", outcomes["rollback"])
                    self.assertFalse(item.callback_active)
                    self.assertTrue(item.callback_exited)
                    self.assertFalse(item._callback_started)
                    self.assertEqual("defer", item.intent.kind)
                    self.assertEqual("unstarted_rollback", item.intent.payload["subtype"])
                    self.assertIsNotNone(item.receipt)
                settlement._progress(item)
                self.assertTrue(execution.released)
                self.assertEqual(1, self.releases.count((execution.permit_id, execution.execution_id)))
                self.assertFalse(settlement._EXPECTED)
                self.assertEqual(0, settlement.active_counts()["registered"])


if os.getenv("SETTLEMENT_DB_TESTS") == "1":
    from tests.operations.test_settlement_dependencies import _SettlementNativePostgresFixture
    from core.storage.operations import common, settlements, store

    class SettlementRollbackRacePostgresTests(_SettlementNativePostgresFixture):
        def _snapshot(self, task, execution):
            with common.settlement_scope(execution.settlement_domain), common._connect() as conn, conn.cursor() as cur:
                snapshot = {}
                for table, where, params in (
                    ("operation_tasks", "id=%s", (task["id"],)),
                    ("operation_runs", "id=%s", (task["run"]["id"],)),
                    ("operation_events", "run_id=%s", (task["run"]["id"],)),
                    ("operation_resources", "run_id=%s", (task["run"]["id"],)),
                    ("account_operation_leases", "run_id=%s", (task["run"]["id"],)),
                    ("operation_settlement_receipts", "permit_id=%s", (execution.permit_id,)),
                    ("operation_settlement_cleanup", "permit_id=%s", (execution.permit_id,)),
                    ("operation_execution_permits", "permit_id=%s", (execution.permit_id,)),
                    ("operation_execution_permit_scopes", "permit_id=%s", (execution.permit_id,)),
                ):
                    cur.execute(f"SELECT * FROM {common._table(table)} WHERE {where}", params)
                    snapshot[table] = [dict(row) for row in cur.fetchall()]
            return snapshot

        @contextmanager
        def _fail_sql_after_run_update(self):
            original = common._connect
            observed = []
            class CursorProxy:
                def __init__(self, cursor):
                    self.cursor = cursor
                def __getattr__(self, name):
                    return getattr(self.cursor, name)
                def __enter__(self):
                    self.cursor.__enter__()
                    return self
                def __exit__(self, *args):
                    return self.cursor.__exit__(*args)
                def execute(self, query, params=None, **kwargs):
                    sql = " ".join(str(query).split())
                    if not observed and sql.startswith("UPDATE") and '"operation_tasks"' in sql:
                        # The prior native Run UPDATE is already visible inside
                        # this transaction. Abort through a real PostgreSQL SQL
                        # error before the Task projection can be applied.
                        self.cursor.execute(f"SELECT status,execution_id FROM {common._table('operation_runs')}")
                        observed.extend(dict(row) for row in self.cursor.fetchall())
                        self.cursor.execute("SELECT 1 / 0")
                        raise AssertionError("PostgreSQL division by zero did not fail")
                    self.cursor.execute(query, params, **kwargs)
                    return self
            class ConnectionProxy:
                def __init__(self, connection):
                    self.connection = connection
                def __getattr__(self, name):
                    return getattr(self.connection, name)
                def cursor(self, *args, **kwargs):
                    return CursorProxy(self.connection.cursor(*args, **kwargs))
            @contextmanager
            def connect():
                with original() as connection:
                    yield ConnectionProxy(connection)
            with patch.object(common, "_connect", side_effect=connect):
                yield observed

        def test_s15_unstarted_rollback_internal_sql_failure_rolls_back_original_transaction(self):
            task = self._new_task("plan_check")
            execution = self._claim(task, started=False)
            before = self._snapshot(task, execution)
            with patch.object(task_gateway, "notify_dispatch"), self._fail_sql_after_run_update() as observed:
                with self.assertRaises(OperationSettlementPending):
                    task_gateway.rollback_admission(execution, reason="s15_native_sql_failure")
            self.assertEqual([{"status": "queued", "execution_id": None}], observed)
            self.assertEqual(before, self._snapshot(task, execution))
            item = settlement.responsibility(execution)
            original = item.intent
            self.assertEqual("unstarted_rollback", original.payload["subtype"])
            self.assertTrue(item.callback_exited)
            self.assertFalse(item.callback_active)
            self.assertFalse(item._callback_started)
            self.assertFalse(settlement.callback_started(execution))
            self.assertIsNone(item.receipt)
            self.assertFalse(execution.released)
            self._assert_permit_ledger("s15_sql_failure_compensation_pending")
            with patch.object(task_gateway, "notify_dispatch"):
                task_gateway.rollback_admission(execution, reason="later_reason_cannot_replace")
            self.assertIs(original, item.intent)
            self.assertEqual("queued", store.get_run(task["run"]["id"])["status"])
            receipt = item.receipt
            self.assertEqual("unstarted_rollback", receipt["actual_result"]["defer_subtype"])
            after = self._snapshot(task, execution)
            self.assertEqual(1, len(after["operation_settlement_receipts"]))
            self.assertEqual(1, sum(row["event_type"] == "run.requeued" for row in after["operation_events"]))
            self.assertEqual(receipt, settlements.submit_intent(original, domain=execution.settlement_domain))
            self.assertEqual(after, self._snapshot(task, execution))
            self._assert_permit_ledger("s15_sql_retry_exact_receipt")

        def test_s15_native_callback_and_unstarted_rollback_share_one_concurrent_barrier(self):
            for iteration in range(12):
                with self.subTest(iteration=iteration):
                    task = self._new_task("plan_check")
                    execution = self._claim(task, started=False)
                    with patch.object(task_gateway, "notify_dispatch"):
                        outcomes, calls = contend_callback_and_rollback(execution)
                    item = settlement.responsibility(execution)
                    self.assertEqual(int(outcomes["callback_started"]), len(calls))
                    self.assertTrue(item.release_requested)
                    self.assertFalse(execution.released)
                    if outcomes["callback_started"]:
                        self.assertEqual("callback_won", outcomes["rollback"])
                        self.assertTrue(item.callback_active)
                        self.assertFalse(item.callback_exited)
                        self.assertIsNone(item.intent)
                        self.assertIsNone(item.receipt)
                        self.assertEqual("running", store.get_run(task["run"]["id"])["status"])
                        self._assert_permit_ledger("s15_callback_won_still_active")
                        self._finish(execution)
                    else:
                        self.assertEqual("confirmed", outcomes["rollback"])
                        self.assertFalse(item.callback_active)
                        self.assertTrue(item.callback_exited)
                        self.assertFalse(item._callback_started)
                        self.assertEqual("unstarted_rollback", item.intent.payload["subtype"])
                        self.assertEqual("queued", store.get_run(task["run"]["id"])["status"])
                    self._assert_permit_ledger("s15_winner_confirmed_before_permit_release")
                    for _ in range(16):
                        if execution.released:
                            break
                        item.next_attempt = 0
                        settlement._progress(item)
                    self.assertTrue(execution.released, settlement.runtime_status())
                    self._assert_permit_ledger("s15_race_exact_permit_released")
                    snapshot = self._snapshot(task, execution)
                    self.assertEqual(1, len(snapshot["operation_settlement_receipts"]))
                    self.assertEqual(1, sum(row["event_type"] in {"run.requeued", "run.success"}
                                           for row in snapshot["operation_events"]))
                    self.assertFalse(settlement._EXPECTED)
                    self.assertEqual(0, settlement.active_counts()["registered"])
else:
    @unittest.skip("root-exclusive SETTLEMENT_DB_TESTS=1 required for native PG acceptance")
    class SettlementRollbackRacePostgresTests(unittest.TestCase):
        def test_root_exclusive_native_rollback_race_acceptance(self):
            pass
