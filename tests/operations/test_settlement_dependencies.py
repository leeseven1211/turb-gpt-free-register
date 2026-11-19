"""S11 native dependency settlement acceptance; PG work is root opt-in only.

Imports and ordinary collection are offline. The gated cases use native
claim+permit, finish/receipt, durable cleanup and completion continuation APIs.
Only local repository interruption seams are injected; no remote work is run.
"""
from __future__ import annotations

import os
import time
import unittest
import uuid
from unittest.mock import patch

from core.operations.settlement_contracts import seal_intent, thaw


def existing_child_obligation(parent, child):
    """Same typed shape emitted by the native completion adapter."""
    return {
        "action_kind": "completion_dependency",
        "resource_identity": f"completion:{parent['run']['id']}:{child['source_system']}:{child['id']}",
        "blocks_permit": False,
        "payload": {
            "parent_source_system": parent["source_system"],
            "parent_source_id": str(parent["id"]),
            "parent_run_id": parent["run"]["id"],
            "child_source_system": child["source_system"],
            "child_source_id": str(child["id"]),
            "dependency_type": "account_completion",
            "payload": {"parent_run_id": parent["run"]["id"], "remaining_steps": [],
                        "settings": {}, "result_summary": {"completed_steps": ["existing_child"]}},
        },
    }


class SettlementDependencyShapeTests(unittest.TestCase):
    def test_existing_child_handoff_freezes_original_parent_generation(self):
        parent = {"id": 1, "source_system": "webui_runtime", "run": {"id": 11}}
        child = {"id": 2, "source_system": "webui_runtime", "run": {"id": 22}}
        obligation = existing_child_obligation(parent, child)
        frozen = seal_intent(kind="terminal", origin={"run_id": 11},
            payload={"status": "partial_success"}, obligations=(obligation,))
        obligation["payload"]["parent_run_id"] = 999
        obligation["payload"]["payload"]["remaining_steps"].append("never-replay")
        actual = thaw(frozen.obligations)[0]
        self.assertEqual(11, actual["payload"]["parent_run_id"])
        self.assertEqual("2", actual["payload"]["child_source_id"])
        self.assertEqual([], actual["payload"]["payload"]["remaining_steps"])


if os.getenv("SETTLEMENT_DB_TESTS") == "1":
    from psycopg.rows import dict_row
    from tests.support_pg import PostgresTestCase
    from core.operations import concurrency, settlement
    from core.accounts import completion_dependencies, completion_execution
    from core.storage import postgres
    from core.storage.operations import common, permits, runtime, settlements, store, legacy_task_store

    class _SettlementNativePostgresFixture(PostgresTestCase):
        def setUp(self):
            self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
            self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
            legacy_task_store.init()
            store.reset_ready()
            store.init()
            permits.ensure_tables()
            previous_thread = settlement._THREAD
            if previous_thread is not None:
                # Native stop_runtime joins its carrier without clearing the
                # reference. Accept that quiescent object, never a live carrier.
                self.assertFalse(previous_thread.is_alive(), settlement.runtime_status())
                previous_thread.join(timeout=0)
                self.assertFalse(previous_thread.is_alive(), settlement.runtime_status())
            counts = settlement.active_counts()
            self.assertTrue(all(value == 0 for value in counts.values()), settlement.runtime_status())
            self.assertFalse(settlement._EXPECTED)
            self.assertEqual(0, settlement._RESERVATIONS)
            self.patches = [patch.object(settlement,name,value) for name,value in (
                ("_REGISTRY",{}),("_EXPECTED",set()),("_REGISTRY_ERROR",""),("_DOMAINS",{}),
                ("_THREAD",None),("_STOP",False),("_STOP_WITH_PENDING",False),("_STARTED",False),
                ("_ADMISSION",None),("_DEADLINE",None),("_SCAN_ERROR",""),("_SCAN_NEXT",{}),
                ("_SCAN_FAILURES",{}))]
            for item in self.patches:
                item.start()
                self.addCleanup(item.stop)
            self.contexts = []
            self.permit_ledger = []
            self.addCleanup(self._close_original_responsibilities)

        def _close_original_responsibilities(self):
            # These PG fixtures own every local ticket they admitted. Drain the
            # actual receipt+cleanup+permit gate before temporary schema reset;
            # a failed acceptance assertion must not hide pending ownership.
            for execution in self.contexts:
                item=settlement.responsibility(execution)
                if item.released:
                    continue
                if item.intent is None:
                    self._finish(execution,status="attention_required")
                settlement.callback_exited(execution)
                settlement.request_release(execution,reason="s11_test_teardown")
            self.assertTrue(settlement.start_runtime())
            self.assertTrue(settlement.drain_runtime(time.monotonic()+5),settlement.runtime_status())
            self.assertTrue(settlement.stop_runtime(time.monotonic()+1),settlement.runtime_status())
            self.assertEqual(0,settlement.active_counts()["registered"])
            self.assertFalse(settlement._EXPECTED)
            self._assert_permit_ledger("native_teardown_released")

        def _new_task(self, kind):
            return store.create_runtime_task(task_type=kind, account_id=None,
                source_system="webui_runtime", source_id=uuid.uuid4().hex,
                email="dependency-synthetic@example.test", trigger="settlement_s11",
                resource_family="dependency_test", data={})

        def _claim(self, task, *, started=True):
            run_id = int(task["run"]["id"])
            execution_id = uuid.uuid4().hex
            key = f"operation_run:{run_id}"
            # Real admission transaction creates immutable ticket and claims the
            # Run on its own connection. Only deterministic local policy input
            # is supplied; no fixture inserts permits/tickets by hand.
            admitted = permits.try_admit(
                execution_key=key, task_type="account_setup_retry", execution_id=execution_id,
                run_id=run_id, batch_key="", owner=permits.current_owner(), metadata={},
                policy=lambda conn: ([{"kind": "global", "key": "deployment", "limit": 20}], 1, []),
                claim=lambda conn, owner: store.claim_run(run_id, execution_id=owner,
                    worker_pid=os.getpid(), conn=conn),
            )
            self.assertIn("permit_id", admitted, admitted)
            domain = admitted["settlement_domain"]
            execution = concurrency.ExecutionContext(
                admitted["permit_id"], execution_id, key, "account_setup_retry",
                admitted["claimed_run"], domain_schema=domain.permit_schema,
                _domain_url=domain.database_url, settlement_ticket=admitted["settlement_ticket"],
                settlement_domain=domain,
            )
            settlement.register_execution(execution, execution.settlement_ticket)
            if started:
                self.assertTrue(settlement.callback_started(execution))
            self.contexts.append(execution)
            self._assert_permit_ledger("admitted")
            return execution

        def _assert_permit_ledger(self, stage):
            """Account for each original permit, including compensation tails."""
            if not self.contexts:
                return
            domain = self.contexts[0].settlement_domain
            permit_table = (
                f"{postgres.quote_identifier(domain.permit_schema)}."
                f"{postgres.quote_identifier('operation_execution_permits')}"
            )
            scope_table = (
                f"{postgres.quote_identifier(domain.permit_schema)}."
                f"{postgres.quote_identifier('operation_execution_permit_scopes')}"
            )
            with common.settlement_scope(domain), common._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT permit_id,execution_id,execution_key,run_id,metadata,released_at "
                            f"FROM {permit_table} ORDER BY permit_id")
                rows = [dict(row) for row in cur.fetchall()]
                cur.execute(f"SELECT permit_id,scope_kind,scope_key,units,limit_snapshot "
                            f"FROM {scope_table} ORDER BY permit_id,scope_kind,scope_key")
                scopes = [dict(row) for row in cur.fetchall()]
            expected = {execution.permit_id: execution for execution in self.contexts}
            self.assertEqual(set(expected), {row["permit_id"] for row in rows}, stage)
            self.assertEqual(set(expected), {row["permit_id"] for row in scopes}, stage)
            self.assertEqual(len(expected), len(scopes), stage)
            active = set()
            for row in rows:
                execution = expected[row["permit_id"]]
                ticket = thaw(execution.settlement_ticket)
                actual_ticket = common._decode(row["metadata"])["settlement_ticket"]
                self.assertEqual(ticket, actual_ticket, stage)
                self.assertEqual(
                    (execution.execution_id, execution.execution_key, ticket["run_id"]),
                    (row["execution_id"], row["execution_key"], row["run_id"]), stage,
                )
                if row["released_at"] is None:
                    active.add(row["permit_id"])
            self.assertEqual(
                {execution.permit_id for execution in self.contexts if not execution.released},
                active, stage,
            )
            occupied = 0
            for scope in scopes:
                self.assertEqual(("global", "deployment", 1, 20),
                    (scope["scope_kind"], scope["scope_key"], scope["units"], scope["limit_snapshot"]), stage)
                if scope["permit_id"] in active:
                    occupied += int(scope["units"])
            self.assertEqual(len(active), occupied, stage)
            self.assertLessEqual(occupied, 20, stage)
            self.permit_ledger.append({
                "stage": stage, "limit": 20, "occupied": occupied,
                "permits": [{
                    "permit_id": row["permit_id"], "execution_id": row["execution_id"],
                    "run_id": row["run_id"], "active": row["permit_id"] in active,
                } for row in rows],
            })

        def _finish(self, execution, *, status="success", obligations=()):
            origin = {**thaw(execution.settlement_ticket), "lease_requirement": "accountless", "leases": []}
            intent = seal_intent(kind="terminal", origin=origin,
                payload={"status": status, "result_summary": {
                    "completed_steps": ["saved-parent-step"],
                    **({"awaiting_steps": ["existing_child"]} if status == "partial_success" else {}),
                }}, obligations=obligations)
            receipt = settlement.settle(execution, intent, lambda original, deadline:
                settlements.submit_intent(original, domain=execution.settlement_domain, deadline=deadline))
            settlement.callback_exited(execution)
            settlements.mark_cleanup_handoff(execution.settlement_ticket,
                domain=execution.settlement_domain)
            self._assert_permit_ledger("receipt_and_handoff_confirmed")
            return intent, receipt

        def _jobs(self, execution, *, kind=None):
            with common.settlement_scope(execution.settlement_domain), common._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {common._table('operation_settlement_cleanup')} WHERE permit_id=%s ORDER BY id",
                    (execution.permit_id,))
                rows = [dict(row) for row in cur.fetchall()]
            return [row for row in rows if kind is None or row["action_kind"] == kind]

        def _due(self, execution):
            with common.settlement_scope(execution.settlement_domain), common._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {common._table('operation_settlement_cleanup')} SET next_attempt_at=now() WHERE permit_id=%s AND state='pending'",
                    (execution.permit_id,))

        def _drain_cleanup(self, execution, *, maximum=16):
            results = []
            for _ in range(maximum):
                result = settlements.run_cleanup_once(domain=execution.settlement_domain,
                    permit_id=execution.permit_id, execution_id=execution.execution_id,
                    deadline=time.monotonic() + 5)
                if result is None:
                    break
                results.append(result)
            return results

        def _dependencies(self):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {common._table('operation_task_dependencies')} ORDER BY id")
                return [dict(row) for row in cur.fetchall()]

        def _counts(self, parent, child):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_tasks')}")
                tasks = int(cur.fetchone()["n"])
                cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_runs')} WHERE task_id=%s", (parent["id"],))
                runs = int(cur.fetchone()["n"])
                cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_events')} WHERE run_id=%s AND event_type='run.success'", (child["run"]["id"],))
                events = int(cur.fetchone()["n"])
            return tasks, runs, events

    class SettlementDependencyPostgresTests(_SettlementNativePostgresFixture):
        def test_s11_native_waiting_parent_projection_rollback_and_once_confirmation(self):
            from core.operations.settlement_contracts import OperationSettlementPending
            parent = self._new_task("account_completion")
            child = store.create_runtime_task(task_type="live_check", account_id=None,
                email="waiting-child@example.test", parent_task_id=parent["id"],
                trigger="settlement_s11", resource_family="dependency_test")
            self.assertEqual("waiting", store.get_task(parent["id"])["status"])
            execution = self._claim(child)
            origin = {**thaw(execution.settlement_ticket), "lease_requirement": "accountless", "leases": []}
            intent = seal_intent(kind="terminal", origin=origin,
                payload={"status": "success", "result_summary": {"business_writeback": "already_saved"}})
            def submit(original, deadline):
                return settlements.submit_intent(original, domain=execution.settlement_domain, deadline=deadline)
            with patch.object(runtime, "_reconcile_parent_task_cur", side_effect=OSError("parent projection interrupted")):
                with self.assertRaises(OperationSettlementPending):
                    settlement.settle(execution, intent, submit)
            self.assertEqual("waiting", store.get_task(parent["id"])["status"])
            self.assertEqual("running", store.get_run(child["run"]["id"])["status"])
            self.assertIsNone(settlements.read_receipt(intent, domain=execution.settlement_domain))
            self._assert_permit_ledger("parent_projection_rollback_pending")
            receipt = settlement.settle(execution, intent, submit)
            settlement.callback_exited(execution)
            settlements.mark_cleanup_handoff(execution.settlement_ticket, domain=execution.settlement_domain)
            self.assertEqual("success", store.get_task(parent["id"])["status"])
            before = (store.get_task(parent["id"]), self._counts(parent, child))
            # Readback must not enter the original native parent projection.
            with patch.object(runtime, "_reconcile_parent_task_cur", side_effect=AssertionError("parent projection replayed")):
                again = settlements.submit_intent(intent, domain=execution.settlement_domain)
            self.assertEqual(receipt["receipt_id"], again["receipt_id"])
            self.assertEqual(before, (store.get_task(parent["id"]), self._counts(parent, child)))
            self.assertEqual(2, before[1][0])
            self.assertEqual(1, before[1][2])
            self._assert_permit_ledger("parent_projection_exact_confirmation")

        def test_s11_fast_child_projection_interruption_and_parent_continuation_ack_loss(self):
            parent, child = self._new_task("account_completion"), self._new_task("password_setup")
            parent_execution, child_execution = self._claim(parent), self._claim(child)
            child_intent, child_receipt = self._finish(child_execution)
            obligation = existing_child_obligation(parent, child)
            self._finish(parent_execution, status="partial_success", obligations=(obligation,))
            # Real child already terminal; fail before handoff projection.
            with patch.object(completion_execution, "apply_settlement_dependency",
                              side_effect=OSError("local dependency projection unavailable")):
                self._drain_cleanup(parent_execution)
            self.assertEqual([], self._dependencies())
            self.assertEqual("partial_success", store.get_task(parent["id"])["status"])
            self.assertEqual("pending", self._jobs(parent_execution, kind="completion_dependency")[0]["state"])
            self._assert_permit_ledger("completion_dependency_projection_pending")
            self._due(parent_execution)
            self._drain_cleanup(parent_execution)
            edge = self._dependencies()[0]
            self.assertEqual("ready", edge["status"])
            self.assertEqual("success", edge["child_status"])
            self.assertEqual(2, self._counts(parent, child)[0])
            # Native continuation commits the new parent Run before its edge ACK.
            # The injected local ACK error returns this same edge to ready.
            claimed = store.claim_task_dependency(edge["id"])
            real_complete = store.complete_task_dependency
            failures = []
            def ack(dependency_id, *, success, error=None):
                if success and not failures:
                    failures.append(dependency_id)
                    raise OSError("dependency complete ACK unavailable")
                return real_complete(dependency_id, success=success, error=error)
            with patch.object(store, "complete_task_dependency", side_effect=ack):
                completion_dependencies.handle_ready_completion_dependency(claimed)
            self.assertEqual(2, self._counts(parent, child)[1])
            self._assert_permit_ledger("parent_continuation_committed_ack_pending")
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {common._table('operation_task_dependencies')} SET next_attempt_at=now() WHERE id=%s", (edge["id"],))
            retried = store.claim_task_dependency(edge["id"])
            completion_dependencies.handle_ready_completion_dependency(retried)
            self.assertEqual("completed", self._dependencies()[0]["status"])
            self.assertEqual(2, self._counts(parent, child)[0])  # no second logical child
            self.assertEqual(2, self._counts(parent, child)[1])  # one continuation only
            self.assertEqual(child_receipt["receipt_id"], settlements.read_receipt(
                child_intent, domain=child_execution.settlement_domain)["receipt_id"])
            self._assert_permit_ledger("parent_continuation_exact_confirmation")

        def test_s11_child_after_waiting_edge_retries_exact_ready_projection_after_commit(self):
            parent, child = self._new_task("account_completion"), self._new_task("password_setup")
            parent_execution, child_execution = self._claim(parent), self._claim(child)
            self._finish(parent_execution, status="partial_success", obligations=(existing_child_obligation(parent, child),))
            # Simulate commit-before-ACK on native dependency registration itself.
            original = store.register_task_dependency
            def lost(*args, **kwargs):
                original(*args, **kwargs)
                raise OSError("dependency registration ACK unavailable")
            with patch.object(store, "register_task_dependency", side_effect=lost):
                self._drain_cleanup(parent_execution)
            self.assertEqual(1, len(self._dependencies()))
            self.assertEqual("waiting", self._dependencies()[0]["status"])
            self._assert_permit_ledger("dependency_registration_commit_ack_pending")
            self._due(parent_execution)
            self._drain_cleanup(parent_execution)
            self.assertEqual(1, len(self._dependencies()))
            self.assertEqual("waiting", self._dependencies()[0]["status"])
            _, receipt = self._finish(child_execution)
            with patch.object(runtime, "mark_task_dependency_ready", side_effect=OSError("ready projection unavailable")):
                self._drain_cleanup(child_execution)
            self.assertEqual("success", store.get_run(child["run"]["id"])["status"])
            self.assertEqual("waiting", self._dependencies()[0]["status"])
            self.assertEqual("pending", self._jobs(child_execution, kind="dependency_ready")[0]["state"])
            self._assert_permit_ledger("child_ready_projection_pending")
            self._due(child_execution)
            self._drain_cleanup(child_execution)
            self.assertEqual("ready", self._dependencies()[0]["status"])
            self.assertEqual(1, len(self._dependencies()))
            self.assertEqual(2, self._counts(parent, child)[0])
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT event_uuid FROM {common._table('operation_events')} WHERE run_id=%s AND event_type='run.success'",
                    (child["run"]["id"],))
                terminal_events = [row["event_uuid"] for row in cur.fetchall()]
            self.assertEqual([receipt["transition_event_uuid"]], terminal_events)
            self._assert_permit_ledger("child_ready_projection_exact_confirmation")

        def test_s11_old_parent_obligation_cannot_attach_after_new_parent_run(self):
            parent, child = self._new_task("account_completion"), self._new_task("password_setup")
            parent_execution, child_execution = self._claim(parent), self._claim(child)
            self._finish(parent_execution, status="partial_success", obligations=(existing_child_obligation(parent, child),))
            replacement = store.retry_runtime_task(parent["id"], trigger="explicit_new_parent")
            before = store.get_task(parent["id"])
            self._finish(child_execution)
            self._drain_cleanup(parent_execution)
            self._drain_cleanup(child_execution)
            self.assertEqual([], self._dependencies())
            self.assertEqual(before, store.get_task(parent["id"]))
            self.assertEqual(replacement["id"], store.get_task(parent["id"])["last_run_id"])
            self.assertEqual(2, self._counts(parent, child)[0])
            self._assert_permit_ledger("old_parent_generation_obligation_rejected")
else:
    @unittest.skip("root-exclusive SETTLEMENT_DB_TESTS=1 required for native PG acceptance")
    class SettlementDependencyPostgresTests(unittest.TestCase):
        def test_root_exclusive_native_dependency_acceptance(self):
            pass
