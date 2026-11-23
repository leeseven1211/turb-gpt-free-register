"""Offline recovery policy tests; native PostgreSQL cases remain root-owned."""
from __future__ import annotations

import unittest
import json
import os
import uuid
from contextlib import ExitStack
from unittest.mock import patch

from core.operations.settlement_contracts import SettlementDomain
from core.storage.operations import common, permits, recovery, schema, settlements
from core.storage.operations import bulk, bulk_schema


class _RecoveryDatabase:
    """Stateful SQL boundary; the real recovery policy chooses every branch."""

    def __init__(self):
        domain_id = permits._domain_id(
            "postgresql://unit.invalid/no-connection", "test_recovery", "test_recovery",
        )
        self.domain = SettlementDomain("postgresql://unit.invalid/no-connection", "test_recovery",
                                       "test_recovery", domain_id)
        ticket = {"version": 1, "domain_id": domain_id,
                  "operation_schema": "test_recovery", "permit_schema": "test_recovery",
                  "permit_id": "permit-old", "execution_id": "execution-old",
                  "run_id": 7, "run_uuid": "run-old", "task_id": 3, "ticket_id": "ticket-old",
                  "owner": {"host_id": "host-old", "pid": 99, "process_start": "start-old"}}
        self.permit = {"permit_id": "permit-old", "execution_id": "execution-old",
                       "run_id": 7, "owner": ticket["owner"],
                       "metadata": {"settlement_ticket": ticket}, "released_at": None}
        self.run = {"id": 7, "task_id": 3, "run_uuid": "run-old",
                    "execution_id": "execution-old", "status": "running", "account_id": None,
                    "batch_id": None, "source_system": "native_operations",
                    "data": {}, "result_summary": {}, "task_type": "plan_check",
                    "heartbeat_stale": True}
        self.task = {"id": 3, "last_run_id": 7, "source_system": "native_operations",
                     "task_type": "plan_check", "parent_task_id": None, "status": "running"}
        self.receipt = None
        self.disposition = None
        self.resource_confirmation = None
        self.resources = []
        self.leases = []
        self.events = []
        self.queries = []
        self.depth = 0
        self.released_in_transaction = False
        self.fail_ack = False

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, exc_type, *_):
        self.depth -= 1
        if self.fail_ack and self.disposition and self.depth == 0 and exc_type is None:
            self.fail_ack = False
            raise ConnectionError("synthetic committed recovery ACK lost")
        return False

    def cursor(self, **_):
        return _RecoveryCursor(self)

    def release(self, *_args, **_kwargs):
        self.released_in_transaction = self.depth != 0
        if self.receipt or self.resource_confirmation or (
                self.disposition and self.disposition["result"]["resource_disposition"] == "no_blocking_resources"):
            self.permit["released_at"] = True
            return True
        return False


class _RecoveryCursor:
    def __init__(self, db):
        self.db, self.rows, self.rowcount = db, [], 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=()):
        sql = " ".join(str(query).split())
        self.db.queries.append((sql, params))
        self.rows, self.rowcount = [], 0
        if sql.startswith("SELECT") and "operation_execution_permits" in sql and "NOT EXISTS" not in sql:
            self.rows = [] if self.db.permit["released_at"] else [self.db.permit]
            if "AND permit_id > %s" in sql and self.db.permit["permit_id"] <= params[0]:
                self.rows = []
        elif sql.startswith("SELECT") and "operation_settlement_receipts" in sql:
            self.rows = [self.db.receipt] if self.db.receipt else []
        elif sql.startswith("SELECT") and "operation_settlement_dispositions" in sql:
            self.rows = [self.db.disposition] if self.db.disposition else []
        elif sql.startswith("SELECT") and "operation_settlement_resource_confirmations" in sql:
            self.rows = [self.db.resource_confirmation] if self.db.resource_confirmation else []
        elif sql.startswith("SELECT") and "operation_batch_run_links" in sql:
            self.rows = [{"id": 55}]
        elif sql.startswith("SELECT") and "operation_resources" in sql:
            self.rows = self.db.resources[:]
            if "state <> 'released'" in sql:
                self.rows = [row for row in self.rows if row["state"] != "released"]
            elif "WHERE id=%s AND run_id=%s" in sql:
                self.rows = [row for row in self.rows if row["id"] == params[0]]
        elif sql.startswith("SELECT") and "account_operation_leases" in sql:
            self.rows = self.db.leases[:]
        elif sql.startswith("SELECT") and "operation_tasks" in sql and "FOR UPDATE" in sql:
            self.rows = [self.db.task]
        elif sql.startswith("SELECT") and "operation_runs" in sql and "FOR UPDATE" in sql:
            self.rows = [self.db.run]
        elif sql.startswith("SELECT account_id,task_id"):
            self.rows = [self.db.run]
        elif sql.startswith("SELECT run_uuid,data"):
            self.rows = [self.db.run]
        elif sql.startswith("INSERT INTO") and "operation_settlement_dispositions" in sql:
            result = json.loads(params[-2])
            self.db.disposition = {
                "id": 1, "domain_id": params[0], "run_id": params[1], "run_uuid": params[2],
                "execution_id": params[3], "permit_id": params[4], "ticket_id": params[5],
                "disposition_kind": params[6], "result": result, "result_digest": params[-1],
            }
            self.rows = [self.db.disposition]
        elif sql.startswith("INSERT INTO") and "operation_settlement_resource_confirmations" in sql:
            self.db.resource_confirmation = {
                "disposition_id": params[0], "domain_id": params[1], "run_uuid": params[2],
                "execution_id": params[3], "permit_id": params[4], "ticket_id": params[5],
                "confirmation_uuid": params[6], "resources": json.loads(params[7]),
                "resources_digest": params[8],
            }
        elif sql.startswith("INSERT INTO") and "operation_events" in sql:
            self.db.events.append(params)
            self.rows = [{"id": len(self.db.events)}]
        elif sql.startswith("UPDATE") and "operation_runs" in sql and "WHERE id=%s" in sql:
            self.db.run["status"] = params[0]
            self.rowcount = 1
            self.rows = [self.db.run]
        elif sql.startswith("UPDATE") and "operation_tasks" in sql and "last_run_id=%s" in sql:
            if self.db.task["last_run_id"] == 7:
                self.db.task["status"] = params[0]
                self.rowcount = 1
        elif sql.startswith("UPDATE") and "operation_resources" in sql:
            for row in self.db.resources:
                if row["state"] == "acquired":
                    row["state"] = "reconciliation_required"

    def fetchall(self):
        return self.rows[:]

    def fetchone(self):
        return self.rows[0] if self.rows else None


class SettlementRecoveryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.db = _RecoveryDatabase()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(schema, "init_operation_schema"))
        self.stack.enter_context(patch.object(recovery, "_SETTLEMENT_RECOVERY_CURSOR", {}))
        self.stack.enter_context(patch.object(common, "_connect", return_value=self.db))
        self.stack.enter_context(patch.object(permits, "_settlement_domain", return_value=self.db.domain))
        self.stack.enter_context(patch.object(permits, "_ticket_liveness", return_value="exited"))
        self.stack.enter_context(patch.object(permits, "owner_liveness", return_value="exited"))
        self.stack.enter_context(patch.object(permits, "recover_execution_permits",
                                             return_value={"released": 0, "alive": 0, "unverified": 0}))
        self.stack.enter_context(patch.object(permits, "release", side_effect=self.db.release))
        self.stack.enter_context(patch.object(permits, "admission_lock"))
        self.stack.enter_context(patch.object(recovery.bulk_execution, "lock_run", return_value=None))
        self.stack.enter_context(patch.object(recovery.bulk_execution, "changed"))
        self.stack.enter_context(patch.object(bulk, "record_managed_change"))
        self.stack.enter_context(patch.object(recovery._projection, "_refresh_batches"))
        self.stack.enter_context(patch.object(settlements, "run_cleanup_once", return_value=None))
        self.stack.enter_context(patch.object(common.postgres_store, "connect",
                                             side_effect=AssertionError("offline unexpected PostgreSQL")))

    def test_dead_process_without_receipt_recovers_while_keeping_original_permit_until_commit(self):
        recovered = recovery.recover_interrupted_runtime_runs()
        self.assertEqual("interrupted", self.db.run["status"])
        self.assertEqual(1, recovered)
        self.assertTrue(self.db.permit["released_at"])
        self.assertFalse(self.db.released_in_transaction)
        self.assertFalse(self.db.disposition["result"]["original_intent_committed"])
        self.assertEqual(1, len(self.db.events))

    def test_preflight_staleness_never_bypasses_default_fifteen_minutes(self):
        self.db.run["heartbeat_stale"] = False
        result = recovery.recover_participating_executions(stale_after_seconds=1)
        self.assertEqual(0, result["recovered"])
        self.assertEqual("running", self.db.run["status"])
        self.assertIsNone(self.db.permit["released_at"])
        stale_queries = [(sql, params) for sql, params in self.db.queries if "AS heartbeat_stale" in sql]
        self.assertEqual(900, stale_queries[0][1][0])

    def test_valid_original_lease_keeps_execution_and_capacity(self):
        self.db.leases = [{"lease_token": "old-token", "valid": True}]
        result = recovery.recover_participating_executions()
        self.assertEqual(0, result["recovered"])
        self.assertEqual("running", self.db.run["status"])
        self.assertIsNone(self.db.disposition)
        self.assertIsNone(self.db.permit["released_at"])

    def test_live_process_cannot_be_recovered_from_thread_or_exit_marker(self):
        with patch.object(permits, "owner_liveness", return_value="alive"):
            result = recovery.recover_participating_executions()
        self.assertEqual(0, result["recovered"])
        self.assertEqual("running", self.db.run["status"])
        self.assertEqual([], self.db.events)
        self.assertIsNone(self.db.permit["released_at"])

    def test_unknown_owner_is_retained_even_with_stale_heartbeat(self):
        with patch.object(permits, "owner_liveness", return_value="unverified"):
            result = recovery.recover_participating_executions()
        self.assertEqual(0, result["recovered"])
        self.assertIsNone(self.db.disposition)

    def test_orphan_physical_resource_is_classified_but_does_not_free_capacity(self):
        self.db.resources = [{"id": 12, "resource_uuid": "original-proxy", "resource_type": "proxy_lease",
                              "external_id": "lease-old", "state": "acquired", "detail": {}}]
        result = recovery.recover_participating_executions()
        self.assertEqual(1, result["recovered"])
        self.assertEqual("interrupted", self.db.run["status"])
        self.assertEqual("reconciliation_required", self.db.resources[0]["state"])
        self.assertEqual("cleanup_pending", self.db.disposition["result"]["resource_disposition"])
        self.assertIsNone(self.db.permit["released_at"])

    def test_sms_cancel_pending_retains_capacity_and_snapshots_exact_resource_identity(self):
        self.db.resources = [{"id": 18, "resource_uuid": "original-sms-resource",
                              "resource_type": "sms_activation", "external_id": "activation-old",
                              "state": "cancel_pending", "detail": {"execution_id": "execution-old"}}]
        recovery.recover_participating_executions()
        proof = self.db.disposition["result"]
        self.assertEqual("cleanup_pending", proof["resource_disposition"])
        self.assertIsNone(self.db.permit["released_at"])
        self.assertEqual([{"resource_id": 18, "resource_uuid": "original-sms-resource",
                           "resource_type": "sms_activation", "external_id": "activation-old",
                           "execution_id": "execution-old", "state": "cancel_pending"}],
                         proof.get("resources"))

    def test_later_confirmed_original_resource_release_appends_proof_without_rewriting_disposition(self):
        self.db.resources = [{"id": 18, "resource_uuid": "original-sms-resource",
                              "resource_type": "sms_activation", "external_id": "activation-old",
                              "state": "cancel_pending", "detail": {"execution_id": "execution-old"}}]
        recovery.recover_participating_executions()
        before = json.loads(json.dumps(self.db.disposition))
        self.assertIsNone(self.db.permit["released_at"])
        self.db.resources[0]["state"] = "released"
        recovery.recover_participating_executions()
        self.assertTrue(self.db.permit["released_at"])
        self.assertEqual(before, self.db.disposition)
        self.assertEqual("original-sms-resource", self.db.resource_confirmation["resources"][0]["resource_uuid"])
        self.assertEqual(1, len(self.db.events))

    def test_different_resource_identity_cannot_confirm_old_disposition_or_release(self):
        self.db.resources = [{"id": 18, "resource_uuid": "original-sms-resource",
                              "resource_type": "sms_activation", "external_id": "activation-old",
                              "state": "cancel_pending", "detail": {"execution_id": "execution-old"}}]
        recovery.recover_participating_executions()
        self.db.resources[0].update(state="released", resource_uuid="replacement-resource")
        recovery.recover_participating_executions()
        self.assertIsNone(self.db.permit["released_at"])
        self.assertIsNone(self.db.resource_confirmation)

    def test_later_new_nonreleased_resource_keeps_old_disposition_pending(self):
        self.db.resources = [{"id": 18, "resource_uuid": "original-sms-resource",
                              "resource_type": "sms_activation", "external_id": "activation-old",
                              "state": "cancel_pending", "detail": {"execution_id": "execution-old"}}]
        recovery.recover_participating_executions()
        self.db.resources[0]["state"] = "released"
        self.db.resources.append({"id": 19, "resource_uuid": "new-unreleased-resource",
                                  "resource_type": "sms_activation", "external_id": "new-activation",
                                  "state": "cancel_pending", "detail": {"execution_id": "execution-old"}})
        recovery.recover_participating_executions()
        self.assertIsNone(self.db.permit["released_at"])
        self.assertIsNone(self.db.resource_confirmation)

    def test_possible_remote_write_keeps_unknown_actual_result_separate(self):
        self.db.run["data"] = {"remote_intent": {"kind": "remote_write", "state": "started", "action": "payment"}}
        recovery.recover_participating_executions()
        self.assertEqual("attention_required", self.db.run["status"])
        self.assertEqual("request_unknown", self.db.disposition["result"]["result_summary"]["outcome"])
        self.assertFalse(self.db.disposition["result"]["original_intent_committed"])

    def test_new_task_attempt_does_not_receive_old_run_projection(self):
        self.db.task["last_run_id"] = 8
        recovery.recover_participating_executions()
        self.assertEqual("running", self.db.task["status"])
        self.assertEqual("interrupted", self.db.run["status"])
        dependency_writes = [sql for sql, _ in self.db.queries
                             if sql.startswith("UPDATE") and "operation_task_dependencies" in sql]
        self.assertEqual([], dependency_writes)

    def test_new_execution_without_original_receipt_cannot_be_classified(self):
        self.db.run["execution_id"] = "new-execution"
        result = recovery.recover_participating_executions()
        self.assertEqual(0, result["recovered"])
        self.assertEqual("running", self.db.run["status"])
        self.assertIsNone(self.db.disposition)

    def test_old_defer_receipt_preserves_new_execution_even_when_stale(self):
        self.db.run.update(execution_id="new-execution", status="running")
        self.db.receipt = {"id": 45}
        recovery.recover_participating_executions()
        self.assertEqual("new-execution", self.db.run["execution_id"])
        self.assertEqual("running", self.db.run["status"])
        self.assertIsNone(self.db.disposition)
        self.assertTrue(self.db.permit["released_at"])
        self.assertEqual([], self.db.events)

    def test_disposition_ack_loss_reads_exact_proof_then_releases_postcommit(self):
        self.db.fail_ack = True
        recovery.recover_participating_executions()
        self.assertEqual("interrupted", self.db.run["status"])
        self.assertEqual(1, len(self.db.events))
        self.assertTrue(self.db.permit["released_at"])
        self.assertFalse(self.db.released_in_transaction)

    def test_disposition_commit_before_release_survives_terminal_run_and_retries_purely(self):
        with patch.object(permits, "release", return_value=False):
            recovery.recover_participating_executions()
        self.assertEqual("interrupted", self.db.run["status"])
        self.assertIsNone(self.db.permit["released_at"])
        recovery.recover_participating_executions()
        self.assertEqual(1, len(self.db.events))
        self.assertTrue(self.db.permit["released_at"])

    def test_exact_permit_lock_precedes_run_locks_without_admission(self):
        recovery.recover_participating_executions()
        locks = [sql for sql, _ in self.db.queries if "FOR UPDATE" in sql]
        self.assertIn("operation_execution_permits", locks[0])
        self.assertIn("SKIP LOCKED", locks[0])
        self.assertFalse(any("advisory" in sql for sql, _ in self.db.queries))

    def test_captured_managed_recovery_keeps_target_lock_and_one_fact_after_ready_domain_drift(self):
        self.db.run["data"] = {"bulk_target_round_id": 55}
        with patch.object(bulk_schema, "_READY_KEY", "different-domain"), \
             patch.object(bulk, "record_managed_change") as changed:
            recovery.recover_participating_executions()
            recovery.recover_participating_executions()
        target_queries = [index for index, (sql, _) in enumerate(self.db.queries)
                          if "operation_batch_run_links" in sql and "FOR UPDATE OF target" in sql]
        self.assertEqual(1, len(target_queries), "persisted original target lock must survive ready-key drift")
        task_queries = [index for index, (sql, _) in enumerate(self.db.queries)
                        if "operation_tasks" in sql and "FOR UPDATE" in sql]
        self.assertLess(target_queries[0], task_queries[0])
        changed.assert_called_once_with(self.db, 55, event_kind="recovered")

    def test_unmanaged_recovery_locks_run_before_task_like_cancel_and_finish(self):
        recovery.recover_participating_executions()
        locks = [sql for sql, _ in self.db.queries if "FOR UPDATE" in sql]
        run_index = next(index for index, sql in enumerate(locks) if "operation_runs" in sql)
        task_index = next(index for index, sql in enumerate(locks) if "operation_tasks" in sql)
        self.assertLess(run_index, task_index, "unmanaged recovery must not invert Run -> Task writers")

    def test_receipt_with_pending_cleanup_does_not_reclassify_or_release(self):
        self.db.receipt = {"id": 45}
        with patch.object(permits, "release", return_value=False):
            result = recovery.recover_participating_executions()
        self.assertEqual(0, result["recovered"])
        self.assertEqual("running", self.db.run["status"])
        self.assertIsNone(self.db.disposition)
        self.assertIsNone(self.db.permit["released_at"])

    def test_wrong_ticket_domain_never_mutates_original_run(self):
        self.db.permit["metadata"]["settlement_ticket"]["domain_id"] = "other-domain"
        result = recovery.recover_participating_executions()
        self.assertEqual(0, result["recovered"])
        self.assertEqual("running", self.db.run["status"])
        self.assertIsNone(self.db.disposition)

    def test_keyset_scan_wraps_to_revisit_pending_permits(self):
        with patch.object(permits, "release", return_value=False):
            recovery.recover_participating_executions()
        self.assertIsNone(self.db.permit["released_at"])
        recovery.recover_participating_executions()
        self.assertTrue(self.db.permit["released_at"])
        self.assertEqual(1, len(self.db.events))
        self.assertTrue(any(
            sql.startswith("SELECT") and "operation_execution_permits" in sql
            and "ORDER BY permit_id" in sql and "AND permit_id >" not in sql
            for sql, _ in self.db.queries))

    def test_recovery_removes_only_the_original_expired_lease_token(self):
        self.db.leases = [{"lease_token": "original-expired", "valid": False}]
        recovery.recover_participating_executions()
        deleted = [(sql, params) for sql, params in self.db.queries
                   if sql.startswith("DELETE") and "account_operation_leases" in sql]
        self.assertEqual(1, len(deleted))
        self.assertEqual((7, "original-expired"), deleted[0][1])
        self.assertIn("expires_at <= now()", deleted[0][0])

    def test_missing_process_start_is_not_positive_exit_proof(self):
        owner = {"host_id": "same-host", "pid": 99}
        self.assertFalse(recovery._original_process_exited(owner))

    def test_rejected_remote_write_is_interrupted_without_fabricated_unknown(self):
        result = recovery._recovery_result({"data": {"remote_intent": {
            "kind": "remote_write", "state": "rejected"}}})
        self.assertEqual("interrupted", result["status"])
        self.assertEqual("interrupted", result["result_summary"]["outcome"])

    def test_remote_write_without_rejection_classifies_attention_unknown(self):
        result = recovery._recovery_result({"data": {"remote_intent": {
            "kind": "remote_write", "receipt_state": "started", "action": "password_submit"}}})
        self.assertEqual("attention_required", result["status"])
        self.assertEqual("request_unknown", result["result_summary"]["outcome"])
        self.assertTrue(result["result_summary"]["reconcile_required"])

    def test_recovery_keeps_permit_when_resource_is_unproved(self):
        self.assertEqual("cleanup_pending", recovery._recovery_resource_disposition(
            [{"state": "reconciliation_required"}]))

    def test_recovery_marks_no_blocking_resources_only_for_empty_rows(self):
        self.assertEqual("no_blocking_resources", recovery._recovery_resource_disposition([]))

    def test_owner_exit_requires_process_identity_and_ignores_thread(self):
        owner = {"host_id": "host-a", "pid": 99, "process_start": "start-a", "thread_id": 7}
        with patch("core.storage.operations.permits.owner_liveness", return_value="exited") as probe:
            self.assertTrue(recovery._original_process_exited(owner))
        probe.assert_called_once_with({"host_id": "host-a", "pid": 99, "process_start": "start-a"})


if os.getenv("SETTLEMENT_DB_TESTS") == "1":
    # Root's exclusive disposable-database runner is the only authorized caller.
    from tests.support_pg import PostgresTestCase
    from core.storage.operations import store
    from core.storage import postgres
    from psycopg.rows import dict_row

    class SettlementRecoveryPostgresTests(PostgresTestCase):
        def setUp(self):
            store.reset_ready()
            store.init()
            self.domain = permits._settlement_domain()
            recovery._SETTLEMENT_RECOVERY_CURSOR.pop(self.domain.domain_id, None)

        def _claim_dead(self, *, age=901, resource=False, remote=False, task=None):
            task = task or store.create_runtime_task(
                task_type="plan_check", account_id=None, email="recovery@example.test",
                trigger="test", resource_family="recovery-test")
            run = task.get("run") or store.get_run(int(task["last_run_id"]))
            execution = uuid.uuid4().hex
            store.claim_run(int(run["id"]), execution_id=execution, worker_pid=os.getpid())
            ticket = {
                "version": 1, "domain_id": self.domain.domain_id,
                "operation_schema": self.domain.operation_schema, "permit_schema": self.domain.permit_schema,
                "run_id": int(run["id"]), "run_uuid": run["run_uuid"], "task_id": int(run["task_id"]),
                "execution_id": execution, "permit_id": uuid.uuid4().hex, "ticket_id": uuid.uuid4().hex,
                "owner": {**permits.current_owner(), "pid": 1073741823, "process_start": "dead-test-process"},
            }
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"""INSERT INTO {permits._permit_table(self.domain.permit_schema)}
                    (permit_id,execution_key,execution_id,run_id,task_type,owner,metadata)
                    VALUES (%s,%s,%s,%s,'plan_check',%s::jsonb,%s::jsonb)""",
                    (ticket["permit_id"], "operation_run:" + str(run["id"]), execution, int(run["id"]),
                     json.dumps(ticket["owner"]), json.dumps({"settlement_ticket": ticket})))
                cur.execute(f"""UPDATE {common._table('operation_runs')}
                    SET heartbeat_at=now()-(%s * interval '1 second'),data=data || %s::jsonb WHERE id=%s""",
                    (age, json.dumps({"remote_intent": {"kind": "remote_write", "state": "started",
                                                        "action": "synthetic"}} if remote else {}), int(run["id"])))
            if resource:
                store.register_resource(int(run["id"]), resource_type="proxy_lease",
                                        provider="synthetic", external_id="exact-old-resource")
            return ticket

        def _facts(self, ticket):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {common._table('operation_runs')} WHERE id=%s", (ticket["run_id"],))
                run = dict(cur.fetchone())
                cur.execute(f"SELECT * FROM {permits._permit_table(self.domain.permit_schema)} WHERE permit_id=%s",
                            (ticket["permit_id"],))
                permit = dict(cur.fetchone())
                cur.execute(f"""SELECT COUNT(*) AS count FROM {common._table('operation_events')}
                    WHERE run_id=%s AND event_type IN ('run.interrupted','run.attention_required')""",
                    (ticket["run_id"],))
                events = cur.fetchone()["count"]
            return run, permit, events

        def _admit_account_task(self, task):
            """用真实准入事务模拟已退出进程持有的账号许可。"""
            run = task.get("run") or store.get_run(int(task["last_run_id"]))
            owner = {**permits.current_owner(), "pid": 1073741823,
                     "process_start": "dead-test-process"}
            return permits.try_admit(
                execution_key=f"operation_run:{run['id']}", task_type=task["task_type"],
                execution_id=uuid.uuid4().hex, run_id=int(run["id"]), batch_key="",
                owner=owner, metadata={},
                policy=lambda _conn: ([{
                    "kind": "account",
                    "key": f"{run['account_id']}:{run['resource_family']}",
                    "limit": 1,
                }], 1, []),
                claim=lambda conn, execution_id: store.claim_run(
                    int(run["id"]), execution_id=execution_id,
                    worker_pid=owner["pid"], conn=conn),
            )

        def test_deleted_stopped_task_releases_account_for_next_run_without_rewriting_result(self):
            from core.storage import records

            account_id = self.seed(records.ACCOUNTS, [{"email": "stopped-lock@example.test"}])[0]
            old_task = store.create_runtime_task(
                task_type="live_check", account_id=account_id,
                email="stopped-lock@example.test", trigger="test")
            ticket = self._admit_account_task(old_task)["settlement_ticket"]
            store.terminate_run(ticket["run_id"], reason="测试管理终止后进程退出")
            store.delete_tasks([old_task["id"]])
            before = self._facts(ticket)[0]
            waiting = store.create_runtime_task(
                task_type="token_refresh", account_id=account_id,
                email="stopped-lock@example.test", trigger="test")
            self.assertEqual(["account_busy"], self._admit_account_task(waiting)["blocked_by"])

            recovery.recover_participating_executions()
            recovery.recover_participating_executions()

            after, permit, interrupted_events = self._facts(ticket)
            self.assertIsNotNone(permit["released_at"])
            self.assertEqual(before, after, "回收许可不能改写已有终态和业务结果")
            self.assertEqual(0, interrupted_events)
            proof = settlements.read_disposition(ticket, domain=self.domain)
            self.assertEqual("stopped", proof["result"]["status"])
            self.assertFalse(proof["result"]["original_intent_committed"])
            self.assertEqual([], self._admit_account_task(waiting)["blocked_by"])

        def test_terminal_resources_keep_permit_until_exact_release_then_recover(self):
            ticket = self._claim_dead(resource=True)
            store.terminate_run(ticket["run_id"], reason="测试未释放资源的停止任务")
            before = self._facts(ticket)[0]
            recovery.recover_participating_executions()
            proof = settlements.read_disposition(ticket, domain=self.domain)
            self.assertIsNotNone(proof)
            self.assertEqual("cleanup_pending", proof["result"]["resource_disposition"])
            self.assertIsNone(self._facts(ticket)[1]["released_at"])
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {common._table('operation_resources')} WHERE run_id=%s",
                            (ticket["run_id"],))
                resource_id = cur.fetchone()["id"]
            store.release_resource(resource_id)

            recovery.recover_participating_executions()

            self.assertIsNotNone(self._facts(ticket)[1]["released_at"])
            self.assertEqual(before, self._facts(ticket)[0])
            self.assertEqual(proof, settlements.read_disposition(ticket, domain=self.domain))

        def test_terminal_recovery_preserves_success_failure_and_remote_unknown_results(self):
            for status in ("success", "failed", "attention_required"):
                with self.subTest(status=status):
                    ticket = self._claim_dead(remote=status == "attention_required")
                    store.finish_run(
                        ticket["run_id"], status=status, message="测试已落库终态",
                        result_summary={"outcome": "request_unknown"} if status == "attention_required" else {})
                    before = self._facts(ticket)[0]

                    recovery.recover_participating_executions()

                    after, permit, _ = self._facts(ticket)
                    self.assertIsNotNone(permit["released_at"])
                    self.assertEqual(before, after)
                    self.assertEqual(status, settlements.read_disposition(
                        ticket, domain=self.domain)["result"]["status"])

        def test_terminal_without_authoritative_event_does_not_release(self):
            ticket = self._claim_dead()
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {common._table('operation_runs')} SET status='stopped' WHERE id=%s",
                            (ticket["run_id"],))

            recovery.recover_participating_executions()

            self.assertIsNone(self._facts(ticket)[1]["released_at"])
            self.assertIsNone(settlements.read_disposition(ticket, domain=self.domain))

        def test_terminal_with_live_owner_or_replaced_execution_keeps_permit(self):
            for changed in ("live_owner", "execution"):
                with self.subTest(changed=changed):
                    ticket = self._claim_dead()
                    store.terminate_run(ticket["run_id"], reason="测试执行身份保护")
                    if changed == "execution":
                        with postgres.connect() as conn, conn.cursor() as cur:
                            cur.execute(f"UPDATE {common._table('operation_runs')} SET execution_id='successor' WHERE id=%s",
                                        (ticket["run_id"],))
                        recovery.recover_participating_executions()
                    else:
                        with patch.object(permits, "owner_liveness", return_value="alive"):
                            recovery.recover_participating_executions()
                    self.assertIsNone(self._facts(ticket)[1]["released_at"])
                    self.assertIsNone(settlements.read_disposition(ticket, domain=self.domain))

        def test_dead_no_receipt_recovers_once_with_default_stale(self):
            ticket = self._claim_dead()
            recovery.recover_participating_executions()
            recovery.recover_participating_executions()
            run, permit, events = self._facts(ticket)
            self.assertEqual("interrupted", run["status"])
            self.assertIsNotNone(permit["released_at"])
            self.assertEqual(1, events)
            proof = settlements.read_disposition(ticket, domain=self.domain)
            self.assertFalse(proof["result"]["original_intent_committed"])
            self.assertEqual("no_blocking_resources", proof["result"]["resource_disposition"])

        def test_unknown_resource_records_disposition_but_retains_capacity(self):
            ticket = self._claim_dead(resource=True, remote=True)
            recovery.recover_participating_executions()
            run, permit, events = self._facts(ticket)
            self.assertEqual("attention_required", run["status"])
            self.assertEqual("request_unknown", run["result_summary"]["outcome"])
            self.assertIsNone(permit["released_at"])
            self.assertEqual(1, events)
            self.assertTrue(settlements.cleanup_blocks_permit(
                ticket["permit_id"], ticket["execution_id"], domain=self.domain))

        def test_fresh_heartbeat_keeps_original_running_and_permit(self):
            ticket = self._claim_dead(age=899)
            recovery.recover_participating_executions(stale_after_seconds=1)
            run, permit, events = self._facts(ticket)
            self.assertEqual("running", run["status"])
            self.assertIsNone(permit["released_at"])
            self.assertEqual(0, events)

        def test_release_failure_then_terminal_disposition_readback(self):
            ticket = self._claim_dead()
            with patch.object(permits, "release", return_value=False):
                recovery.recover_participating_executions()
            run, permit, events = self._facts(ticket)
            self.assertEqual("interrupted", run["status"])
            self.assertIsNone(permit["released_at"])
            recovery.recover_participating_executions()
            _, permit, events = self._facts(ticket)
            self.assertIsNotNone(permit["released_at"])
            self.assertEqual(1, events)

        def test_managed_recovery_after_ready_domain_drift_locks_exact_target_and_emits_once(self):
            from core.storage import records
            from tests.bulk.test_bulk_storage import BulkStorageTests
            bulk.reset_ready()
            bulk.init()
            account_id = records.insert_row(records.ACCOUNTS, {"email": "managed-recovery@example.test"})
            with patch("core.bulk_operations.catalog.capture_settings",
                       return_value={"config_revision": "test-v1", "effective_settings": {}}):
                selection = bulk.create_selection(
                    request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": [account_id]},
                    operation_key="plan_check", parameters={}, config_revision="test-v1")
                selection = bulk.freeze_selection(selection["id"])
                batch = bulk.create_batch(
                    request_key=uuid.uuid4().hex, selection_id=selection["id"], selection_revision=1,
                    operation_key="plan_check", parameters={}, config_revision="test-v1", max_concurrency=1)
                bulk.process_batch(batch["id"], lambda conn, targets, context:
                                   BulkStorageTests.submitter(self, conn, targets, context))
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"""UPDATE {common._table('operation_runs')} run
                    SET data=run.data || jsonb_build_object('bulk_target_round_id',link.target_round_id)
                    FROM {common._table('operation_batch_run_links')} link
                    WHERE link.run_id=run.id AND run.batch_id=%s""", (batch["id"],))
                cur.execute(f"""SELECT task.*,link.target_round_id FROM {common._table('operation_tasks')} task
                    JOIN {common._table('operation_batch_run_links')} link ON link.task_id=task.id
                    WHERE task.batch_id=%s""", (batch["id"],))
                task = dict(cur.fetchone())
            ticket = self._claim_dead(task=task)
            target_id = int(task["target_round_id"])
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT source_revision FROM {common._table('operation_batch_target_rounds')} WHERE id=%s",
                            (target_id,))
                before = int(cur.fetchone()["source_revision"])
            with patch.object(bulk_schema, "_READY_KEY", "different-domain-is-now-ready"):
                recovery.recover_participating_executions()
                recovery.recover_participating_executions()
            run, permit, events = self._facts(ticket)
            self.assertEqual("interrupted", run["status"])
            self.assertIsNotNone(permit["released_at"])
            self.assertEqual(1, events)
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT source_revision FROM {common._table('operation_batch_target_rounds')} WHERE id=%s",
                            (target_id,))
                self.assertEqual(before + 1, int(cur.fetchone()["source_revision"]))
                cur.execute(f"""SELECT COUNT(*) AS count FROM {common._table('operation_projection_outbox')}
                    WHERE target_round_id=%s AND source_revision=%s AND event_kind='recovered'""",
                    (target_id, before + 1))
                self.assertEqual(1, cur.fetchone()["count"])

        def test_unmanaged_recovery_waits_for_run_without_holding_task(self):
            import threading
            ticket = self._claim_dead()
            started, done = threading.Event(), threading.Event()
            errors = []
            native_lock = settlements._lock_origin

            def lock_origin(*args, **kwargs):
                started.set()
                return native_lock(*args, **kwargs)

            def recover():
                try:
                    recovery.recover_participating_executions()
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    done.set()

            worker = threading.Thread(target=recover, name="test-unmanaged-recovery-order", daemon=True)
            with patch.object(settlements, "_lock_origin", side_effect=lock_origin):
                with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                    cur.execute(f"SELECT id FROM {common._table('operation_runs')} WHERE id=%s FOR UPDATE",
                                (ticket["run_id"],))
                    worker.start()
                    self.assertTrue(started.wait(2))
                    self.assertFalse(done.wait(0.1))
                    # A native cancellation already holding Run must still be
                    # able to take Task; reversed recovery would block this.
                    cur.execute("SET LOCAL lock_timeout='500ms'")
                    cur.execute(f"SELECT id FROM {common._table('operation_tasks')} WHERE id=%s FOR UPDATE",
                                (ticket["task_id"],))
                worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual([], errors)
            self.assertEqual("interrupted", self._facts(ticket)[0]["status"])

if __name__ == "__main__":
    unittest.main()
