from __future__ import annotations

import threading
import time
import tempfile
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from core import account_task_store, db, record_store, task_run_log
from core.operations import task_gateway
from core.storage import operation
from tests.support_pg import PostgresTestCase


class _ConfigSnapshot:
    __slots__ = ("revision", "values", "sources")

    def __init__(self, values: MappingProxyType, revision: int = 41) -> None:
        self.revision = revision
        self.values = values
        self.sources = MappingProxyType({"SYNTHETIC_DRIVER": "test.config"})

    def as_dict(self):
        return {key: value for key, value in self.values.items()}


class DurableOperationGatewayPhase2Tests(PostgresTestCase):
    def setUp(self):
        self.task_log_tempdir = tempfile.TemporaryDirectory()
        self.task_log_root_patch = patch.object(
            task_run_log, "_LOG_ROOT", Path(self.task_log_tempdir.name),
        )
        self.task_log_tasks_patch = patch.object(
            task_run_log, "_TASK_LOG_ROOT", Path(self.task_log_tempdir.name) / "tasks",
        )
        self.task_log_root_patch.start()
        self.task_log_tasks_patch.start()
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        self.schema_patch.start()
        self.ready_patch.start()
        account_task_store.init()
        operation.reset_ready()
        operation.init()
        self.handler_types: set[str] = set()

    def tearDown(self):
        for task_type in self.handler_types:
            task_gateway.unregister_operation_handler(task_type)
        task_gateway.stop_dispatcher()
        self.ready_patch.stop()
        self.schema_patch.stop()
        self.task_log_tasks_patch.stop()
        self.task_log_root_patch.stop()
        self.task_log_tempdir.cleanup()

    def _register(self, task_type, handler, **kwargs):
        task_gateway.register_operation_handler(task_type, handler, **kwargs)
        self.handler_types.add(task_type)

    def _runtime_account(self, email: str) -> int:
        return record_store.insert_row(record_store.ACCOUNTS, {
            "email": email,
            "access_token": "synthetic-access-token",
            "codex_status": "failed",
            "created_at": "2026-09-14T10:00:00",
            "updated_at": "2026-09-14T10:00:00",
        })

    def _wait_for_status(self, run_id: int, expected: set[str], timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = operation.get_run(run_id) or {}
            if str(run.get("status") or "") in expected:
                return run
            time.sleep(0.02)
        self.fail(f"run {run_id} did not reach {expected}: {operation.get_run(run_id)}")

    def test_real_submission_scanner_terminal_and_business_writeback(self):
        account_id = self._runtime_account("synthetic-maintenance@example.test")
        handler_seen = threading.Event()
        seen: dict[str, object] = {}

        def handler(context):
            seen.update({
                "run_id": context.run_id,
                "source_system": context.source_system,
                "driver": context.config_snapshot.get("driver"),
                "revision": context.config_revision,
            })
            context.task_reporter.stage(
                "preflight", "success", "synthetic preflight complete",
            )
            with context.lease(ttl_seconds=120) as lease:
                self.assertTrue(lease.heartbeat(ttl_seconds=120))
                self.assertTrue(db.update_account_note(context.account_id, "synthetic writeback"))
                context.checkpoint()
            handler_seen.set()
            return task_gateway.OperationResult.success(
                {"business_writeback": "account.note"}, message="synthetic complete",
            )

        self._register(
            "synthetic_live_check",
            handler,
            source_systems=("synthetic_service",),
            config_allowlist={"driver": "SYNTHETIC_DRIVER"},
        )
        submission = task_gateway.submit_durable_operation(
            task_type="synthetic_live_check",
            account_id=account_id,
            email="synthetic-maintenance@example.test",
            source_system="synthetic_service",
            source_id="synthetic-live-check-1",
            idempotency_key="synthetic-live-check-1",
            config_snapshot=_ConfigSnapshot(MappingProxyType({
                "SYNTHETIC_DRIVER": "no-network",
                "UNRELATED_GLOBAL_SETTING": "must-not-persist",
                "NESTED_UNRELATED": MappingProxyType({"value": "no"}),
            })),
            dispatch=False,
        )

        self.assertTrue(submission["accepted"])
        self.assertFalse(submission["busy"])
        self.assertEqual("synthetic_service", submission["source_system"])
        self.assertEqual(41, submission["config_snapshot_revision"])
        self.assertEqual(1, task_gateway.dispatch_registered_once(limit=10))
        self.assertTrue(handler_seen.wait(5))
        run = self._wait_for_status(int(submission["run_id"]), {"success"})

        account = db.get_account(account_id)
        detail = operation.get_task(int(submission["task_id"]))
        self.assertEqual("synthetic writeback", account["note"])
        self.assertEqual("synthetic_service", run["source_system"])
        self.assertEqual("success", detail["status"])
        self.assertEqual("success", detail["runs"][0]["status"])
        self.assertEqual(41, seen["revision"])
        self.assertEqual("no-network", seen["driver"])
        self.assertNotIn("UNRELATED_GLOBAL_SETTING", run["data"]["config_snapshot"])
        self.assertNotIn("NESTED_UNRELATED", run["data"]["config_snapshot"])
        self.assertEqual([], operation.active_run_for_account(account_id) or [])

    def test_new_accept_busy_false_but_idempotent_reuse_is_busy(self):
        first = task_gateway.submit_durable_operation(
            task_type="synthetic_dedupe",
            account_id=None,
            email="dedupe@example.test",
            source_system="synthetic_service",
            idempotency_key="dedupe-request-1",
            dispatch=False,
        )
        second = task_gateway.submit_durable_operation(
            task_type="synthetic_dedupe",
            account_id=None,
            email="dedupe@example.test",
            source_system="synthetic_service",
            idempotency_key="dedupe-request-1",
            dispatch=False,
        )
        self.assertTrue(first["accepted"])
        self.assertFalse(first["busy"])
        self.assertTrue(second["accepted"])
        self.assertTrue(second["reused"])
        self.assertTrue(second["busy"])
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(first["run_id"], second["run_id"])

    def test_handler_return_value_matches_persisted_terminal_result(self):
        # Polling the database alone misses failures raised after finish_run
        # commits. Verify the executor's return value as well as DB state.
        for mode in ("returned", "finished"):
            with self.subTest(mode=mode):
                task_type = f"synthetic_result_{mode}"

                def handler(context, *, _mode=mode):
                    result = task_gateway.OperationResult.success({"receipt": _mode})
                    if _mode == "finished":
                        context.finish(result)
                        return None
                    return result

                self._register(task_type, handler)
                submission = task_gateway.submit_durable_operation(
                    task_type=task_type,
                    account_id=None,
                    email="synthetic-return@example.test",
                    idempotency_key=f"return-contract-{mode}",
                    dispatch=False,
                )
                result = task_gateway._execute_operation_handler(task_type, submission["run_id"])
                self.assertEqual("success", result["status"])
                self.assertEqual("success", result["database_status"])
                self.assertEqual("success", operation.get_run(submission["run_id"])["status"])

    def test_mapping_result_normalization_has_safe_optional_defaults(self):
        result = task_gateway._coerce_operation_result(
            {"status": "success", "summary": {"receipt": "synthetic"}},
            status="failed", message="",
        )
        self.assertEqual("success", result.status)
        self.assertEqual({"receipt": "synthetic"}, result.summary)

    def test_request_unknown_is_fenced_and_only_reconcile_is_offered(self):
        completed = threading.Event()

        def handler(context):
            completed.set()
            return task_gateway.OperationResult.request_unknown(
                "synthetic remote write has no receipt",
                {"remote_write_started": True},
            )

        self._register("synthetic_unknown", handler, source_systems=("synthetic_service",))
        submission = task_gateway.submit_durable_operation(
            task_type="synthetic_unknown",
            account_id=None,
            email="unknown@example.test",
            source_system="synthetic_service",
            idempotency_key="unknown-request-1",
            dispatch=False,
        )
        self.assertFalse(submission["busy"])
        self.assertEqual(1, task_gateway.dispatch_registered_once(limit=10))
        self.assertTrue(completed.wait(5))
        run = self._wait_for_status(int(submission["run_id"]), {"attention_required"})
        self.assertEqual("request_unknown", run["result_summary"]["outcome"])
        self.assertTrue(run["result_summary"]["reconcile_required"])
        self.assertTrue(run["result_summary"]["execution_id"])
        task = operation.get_task(int(submission["task_id"]))
        self.assertEqual(
            [{"action": "reconcile", "label": "确认远端结果后继续"}],
            task["next_actions"],
        )

    def test_stale_execution_or_lease_cannot_overwrite_current_run(self):
        account_id = self._runtime_account("fenced@example.test")
        task = operation.create_runtime_task(
            task_type="synthetic_fenced",
            account_id=account_id,
            email="fenced@example.test",
            source_system="synthetic_service",
            source_id="fenced-run-1",
        )
        run_id = int(task["run"]["id"])
        claimed = operation.claim_run(run_id, execution_id="worker-current", worker_pid=101)
        lease = operation.acquire_account_lease(account_id=account_id, run_id=run_id, ttl_seconds=120)
        self.assertTrue(lease)
        with self.assertRaises(PermissionError):
            operation.finish_run(
                run_id, status="success", execution_id="worker-stale", lease_token=lease,
            )
        self.assertEqual("running", operation.get_run(run_id)["status"])
        with self.assertRaises(PermissionError):
            operation.finish_run(
                run_id, status="success", execution_id="worker-current", lease_token="wrong",
            )
        finished = operation.finish_run(
            run_id, status="success", execution_id="worker-current", lease_token=lease,
        )
        self.assertEqual("success", finished["status"])
        self.assertEqual("worker-current", finished["execution_id"])

    def test_remote_receipt_contract_requires_local_commit_and_readback_proof(self):
        account_id = self._runtime_account("receipt-contract@example.test")
        task = operation.create_runtime_task(
            task_type="synthetic_remote_receipt",
            account_id=account_id,
            email="receipt-contract@example.test",
            source_system="synthetic_service",
            source_id="receipt-contract-1",
        )
        run_id = int(task["run"]["id"])
        execution_id = "receipt-worker"
        operation.claim_run(run_id, execution_id=execution_id, worker_pid=505)
        lease_token = operation.acquire_account_lease(
            account_id=account_id, run_id=run_id, ttl_seconds=120,
        )
        self.assertTrue(lease_token)
        operation.record_remote_intent(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            action="synthetic_password_change",
            request_id="receipt-request-1",
        )
        with self.assertRaises(ValueError):
            operation.record_remote_receipt(
                run_id,
                execution_id=execution_id,
                lease_token=lease_token,
                outcome="confirmed",
                action="synthetic_password_change",
            )
        received = operation.record_remote_receipt(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            outcome="received",
            action="synthetic_password_change",
            detail={"remote_response_received": True},
        )
        self.assertEqual(
            "response_received", received["data"]["remote_intent"]["receipt_state"],
        )
        local_commit = operation.record_remote_receipt(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            receipt_state="local_commit_required",
            action="synthetic_password_change",
            detail={"remote_result_confirmed": True},
        )
        self.assertEqual(
            "local_commit_required",
            local_commit["data"]["remote_intent"]["receipt_state"],
        )
        confirmed = operation.record_remote_receipt(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            outcome="confirmed",
            action="synthetic_password_change",
            detail={
                "remote_result_confirmed": True,
                "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True,
            },
        )
        self.assertEqual(
            "confirmed", confirmed["data"]["remote_intent"]["receipt_state"],
        )
        operation.finish_run(
            run_id,
            status="success",
            execution_id=execution_id,
            lease_token=lease_token,
            result_summary={"confirmed": True},
        )

    def test_crash_after_http_receipt_never_becomes_retryable(self):
        account_id = self._runtime_account("receipt-crash@example.test")
        task = operation.create_runtime_task(
            task_type="synthetic_remote_crash",
            account_id=account_id,
            email="receipt-crash@example.test",
            source_system="synthetic_service",
            source_id="receipt-crash-1",
        )
        run_id = int(task["run"]["id"])
        execution_id = "crashed-receipt-worker"
        operation.claim_run(run_id, execution_id=execution_id, worker_pid=606)
        lease_token = operation.acquire_account_lease(
            account_id=account_id, run_id=run_id, ttl_seconds=120,
        )
        operation.record_remote_intent(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            action="synthetic_token_refresh",
            request_id="receipt-crash-request",
        )
        operation.record_remote_receipt(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            outcome="response_received",
            action="synthetic_token_refresh",
            detail={"http_status": 200},
        )
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {operation._table('operation_runs')} "
                "SET heartbeat_at=now() - interval '1 hour' WHERE id=%s",
                (run_id,),
            )
            cur.execute(
                f"UPDATE {operation._table('account_operation_leases')} "
                "SET expires_at=now() - interval '1 minute' WHERE run_id=%s",
                (run_id,),
            )
        self.assertEqual(1, operation.recover_interrupted_runtime_runs())
        recovered = operation.get_run(run_id)
        self.assertEqual("attention_required", recovered["status"])
        self.assertEqual("request_unknown", recovered["result_summary"]["outcome"])
        self.assertTrue(recovered["result_summary"]["reconcile_required"])
        self.assertEqual(
            "response_received",
            recovered["result_summary"]["remote_intent_state"],
        )
        self.assertEqual(
            [{"action": "reconcile", "label": "确认远端结果后继续"}],
            (operation.get_task(int(task["id"])) or {})["next_actions"],
        )

    def test_cancelled_queue_is_not_claimed_by_registered_handler(self):
        called = threading.Event()

        def handler(_context):
            called.set()
            return task_gateway.OperationResult.success()

        self._register("synthetic_cancel", handler, source_systems=("synthetic_service",))
        submission = task_gateway.submit_durable_operation(
            task_type="synthetic_cancel",
            account_id=None,
            email="cancel@example.test",
            source_system="synthetic_service",
            idempotency_key="cancel-request-1",
            dispatch=False,
        )
        cancelled = operation.request_run_cancel(int(submission["run_id"]), reason="test cancel")
        self.assertEqual("cancelled", cancelled["status"])
        self.assertEqual(0, task_gateway.dispatch_registered_once(limit=10))
        self.assertFalse(called.wait(0.2))
        self.assertEqual("cancelled", operation.get_run(int(submission["run_id"]))["status"])

    def test_custom_native_source_is_recovered_without_touching_compatibility_rows(self):
        task = operation.create_runtime_task(
            task_type="synthetic_recovery",
            account_id=None,
            email="recovery@example.test",
            source_system="synthetic_service",
            source_id="recovery-run-1",
        )
        run_id = int(task["run"]["id"])
        operation.claim_run(run_id, execution_id="crashed-worker", worker_pid=404)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {operation._table('operation_runs')} "
                "SET heartbeat_at=now() - interval '1 hour' WHERE id=%s",
                (run_id,),
            )
        self.assertEqual(1, operation.recover_interrupted_runtime_runs())
        self.assertEqual("interrupted", operation.get_run(run_id)["status"])


if __name__ == "__main__":
    import unittest

    unittest.main()
