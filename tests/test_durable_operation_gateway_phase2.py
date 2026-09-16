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

    def test_claimed_handler_context_includes_task_email_snapshot(self):
        account_id = self._runtime_account("claimed-context@example.test")
        task = operation.create_runtime_task(
            task_type="synthetic_context",
            account_id=account_id,
            email="claimed-context@example.test",
            source_system="synthetic_service",
            source_id="claimed-context-1",
        )

        claimed = operation.claim_run(
            int(task["run"]["id"]),
            execution_id="context-worker",
            worker_pid=123,
        )
        self.assertIsNotNone(claimed)
        context = task_gateway.OperationHandlerContext(
            claimed,
            execution_id="context-worker",
        )

        self.assertEqual("claimed-context@example.test", context.email)

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

    def test_explicit_remote_rejection_after_confirmed_request_is_terminal(self):
        account_id = self._runtime_account("unsupported-payment@example.test")
        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=account_id,
            email="unsupported-payment@example.test",
            source_system="native_operations",
            source_id="unsupported-payment-1",
        )
        run_id = int(task["run"]["id"])
        execution_id = "unsupported-payment-worker"
        operation.claim_run(run_id, execution_id=execution_id, worker_pid=707)
        lease_token = operation.acquire_account_lease(
            account_id=account_id, run_id=run_id, ttl_seconds=120,
        )
        operation.record_remote_intent(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            action="extract_job_create",
            request_id="unsupported-payment-request",
        )
        operation.record_remote_receipt(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            outcome="confirmed",
            action="extract_job_create",
            detail={
                "remote_result_confirmed": True,
                "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True,
            },
        )

        finished = operation.finish_run(
            run_id,
            status="unsupported",
            message="当前账号不支持 MoMo 支付方式",
            error="当前账号不支持 MoMo 支付方式",
            execution_id=execution_id,
            lease_token=lease_token,
            result_summary={"remote_result_state": "rejected"},
        )

        self.assertEqual("unsupported", finished["status"])
        detail = operation.get_task(int(task["id"]))
        self.assertEqual("unsupported", detail["status"])
        self.assertEqual("account_available", detail["target_status"])
        self.assertEqual([], detail["next_actions"])

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


    def test_reconciliation_account_query_deduplicates_before_limit(self):
        account_ids = [
            self._runtime_account("reconcile-many-a@example.test"),
            self._runtime_account("reconcile-many-b@example.test"),
        ]
        for account_id in account_ids:
            for ordinal in range(3):
                task = operation.create_runtime_task(
                    task_type="codex_token_refresh",
                    account_id=account_id,
                    email=f"reconcile-{account_id}-{ordinal}@example.test",
                    source_system="native_operations",
                    source_id=f"reconcile-many-{account_id}-{ordinal}",
                )
                operation.finish_run(
                    int(task["run"]["id"]),
                    status="attention_required",
                    result_summary={
                        "outcome": "request_unknown",
                        "reconcile_required": True,
                        "ordinal": ordinal,
                    },
                )

        rows = operation.list_reconciliation_accounts(
            task_type="codex_token_refresh", limit=2,
        )
        self.assertEqual(account_ids, [int(row["account_id"]) for row in rows])
        self.assertEqual(
            account_ids,
            [
                int(row["account_id"])
                for row in operation.list_reconciliation_accounts(
                    task_type="codex_token_refresh",
                    account_ids=account_ids,
                    limit=1,
                )
            ],
        )

    def test_config_allowlist_accepts_only_exact_password_policy_keys(self):
        values = MappingProxyType({
            "ACCOUNT_COMPLETION_PASSWORD_ENABLED": True,
            "ACCOUNT_PASSWORD_RESET_ENABLED": False,
            "ACCOUNT_PASSWORD_DRIVER": "roxy",
            "ACCOUNT_PASSWORD_PROXY_MODE": "registration",
            "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK": False,
            "ACCOUNT_PASSWORD_PROXY_PASSWORD": "must-never-copy",
        })
        snapshot = _ConfigSnapshot(values)
        projected = task_gateway.normalize_config_snapshot(
            snapshot,
            allowlist={
                "password_enabled": "ACCOUNT_COMPLETION_PASSWORD_ENABLED",
                "password_reset_enabled": "ACCOUNT_PASSWORD_RESET_ENABLED",
                "password_driver": "ACCOUNT_PASSWORD_DRIVER",
                "password_proxy_mode": "ACCOUNT_PASSWORD_PROXY_MODE",
                "auth_password_email_fallback": "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK",
            },
        )
        self.assertEqual("roxy", projected["password_driver"])
        self.assertNotIn("password_proxy_password", projected)
        with self.assertRaises(ValueError):
            task_gateway.normalize_config_snapshot(
                snapshot,
                allowlist={"password_proxy_password": "ACCOUNT_PASSWORD_PROXY_PASSWORD"},
            )
        with self.assertRaises(ValueError):
            task_gateway.normalize_config_snapshot(
                snapshot,
                allowlist={"PASSWORD_PROXY_PASSWORD": "ACCOUNT_PASSWORD_PROXY_MODE"},
            )

    def test_remote_write_exception_cancel_and_premature_result_require_reconciliation(self):
        cases = (
            ("started", "exception"), ("response_received", "exception"),
            ("response_received", "cancel_exception"), ("started", "failed"),
            ("started", "cancelled"), ("started", "success"),
            ("confirmed", "failed"),
        )
        for receipt, ending in cases:
            with self.subTest(receipt=receipt, ending=ending):
                kind = f"synthetic_pending_{receipt}_{ending}"
                account_id = self._runtime_account(f"{kind}@example.test")

                def handler(context, *, _receipt=receipt, _ending=ending):
                    with context.lease():
                        context.remote_request_started("synthetic_remote_write")
                        if _receipt != "started":
                            context.remote_request_receipt(
                                outcome=_receipt,
                                detail={
                                    "remote_result_confirmed": True,
                                    "local_business_writeback_confirmed": True,
                                    "local_readback_confirmed": True,
                                } if _receipt == "confirmed" else {},
                            )
                        if _ending == "exception":
                            raise RuntimeError("synthetic local writeback failure")
                        if _ending == "cancel_exception":
                            raise task_gateway.OperationCancelled("synthetic cancel")
                        return task_gateway.OperationResult(_ending)

                self._register(kind, handler)
                submitted = task_gateway.submit_durable_operation(
                    task_type=kind, account_id=account_id, email=f"{kind}@example.test", dispatch=False,
                )
                result = task_gateway._execute_operation_handler(kind, submitted["run_id"])
                persisted = operation.get_run(submitted["run_id"])
                self.assertEqual("attention_required", persisted["status"])
                self.assertEqual("request_unknown", persisted["result_summary"]["outcome"])
                self.assertEqual("request_unknown", result["status"])
                self.assertFalse(result["ok"])
                self.assertEqual("attention_required", result["database_status"])
                task = operation.get_task(submitted["task_id"])
                self.assertEqual("reconcile", task["next_actions"][0]["action"])
                with self.assertRaises(ValueError):
                    operation.retry_runtime_task(submitted["task_id"])
                self.assertEqual(1, len(operation.get_task(submitted["task_id"])["runs"]))

    def test_direct_terminal_write_cannot_bypass_remote_pending_guard(self):
        account_id = self._runtime_account("direct-pending@example.test")
        task = operation.create_runtime_task(
            task_type="synthetic_direct", account_id=account_id, email="direct-pending@example.test",
        )
        run_id = task["run"]["id"]
        operation.claim_run(run_id, execution_id="direct-worker", worker_pid=707)
        lease = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
        operation.record_remote_intent(
            run_id, execution_id="direct-worker", lease_token=lease, action="synthetic_write",
        )
        result = operation.finish_run(
            run_id, execution_id="direct-worker", lease_token=lease, status="failed",
        )
        self.assertEqual("attention_required", result["status"])
        with self.assertRaises(ValueError):
            operation.retry_runtime_task(task["id"], data={"remote_intent": {}})

    def test_rejected_write_is_retryable_but_new_run_has_no_old_checkpoint(self):
        account_id = self._runtime_account("rejected-write@example.test")
        task = operation.create_runtime_task(
            task_type="synthetic_rejected", account_id=account_id, email="rejected-write@example.test",
        )
        run_id = task["run"]["id"]
        operation.claim_run(run_id, execution_id="rejected-worker", worker_pid=808)
        lease = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
        operation.record_remote_intent(
            run_id, execution_id="rejected-worker", lease_token=lease, action="synthetic_write",
        )
        operation.record_remote_receipt(
            run_id, execution_id="rejected-worker", lease_token=lease, outcome="rejected",
        )
        operation.finish_run(
            run_id, execution_id="rejected-worker", lease_token=lease, status="failed",
        )
        retry = operation.retry_runtime_task(task["id"])
        self.assertEqual("queued", retry["status"])
        self.assertNotIn("remote_intent", retry["data"])
        self.assertNotIn("remote_receipt", retry["data"])

    def test_heartbeat_exception_latches_lease_loss_without_thread_crash(self):
        with patch.object(threading.Thread, "start"):
            lease = task_gateway.OperationLease(
                run_id=1, account_id=1, resource_family="synthetic", token="synthetic",
                ttl_seconds=120,
            )
        with patch.object(operation, "heartbeat_run", side_effect=RuntimeError("synthetic DB loss")):
            self.assertFalse(lease.heartbeat())
        self.assertTrue(lease.lost)
        with patch.object(operation, "heartbeat_run", return_value=True) as heartbeat:
            self.assertFalse(lease.heartbeat())
        heartbeat.assert_not_called()

    def test_pending_checkpoint_cannot_be_overwritten_or_receive_another_request_receipt(self):
        account_id = self._runtime_account("checkpoint-fence@example.test")
        task = operation.create_runtime_task(
            task_type="synthetic_checkpoint", account_id=account_id, email="checkpoint-fence@example.test",
        )
        run_id = task["run"]["id"]
        operation.claim_run(run_id, execution_id="checkpoint-worker", worker_pid=909)
        lease = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
        fence = {"execution_id": "checkpoint-worker", "lease_token": lease}
        operation.record_remote_intent(run_id, **fence, action="write", request_id="first")
        for kind in ("read", "remote_write"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                operation.record_remote_intent(run_id, **fence, action="next", intent_kind=kind)
        with self.assertRaises(ValueError):
            operation.record_remote_receipt(run_id, **fence, outcome="rejected", request_id="second")
        with self.assertRaises(PermissionError):
            operation.record_remote_receipt(
                run_id, execution_id="checkpoint-worker", outcome="rejected",
            )
        self.assertEqual("started", operation.get_run(run_id)["data"]["remote_intent"]["receipt_state"])
        operation.finish_run(run_id, **fence, status="attention_required")

    def test_read_only_receipt_does_not_require_an_account_lease(self):
        task = operation.create_runtime_task(
            task_type="synthetic_read", account_id=None, email="read@example.test",
        )
        run_id = task["run"]["id"]
        operation.claim_run(run_id, execution_id="read-worker", worker_pid=910)
        operation.record_remote_intent(
            run_id, execution_id="read-worker", action="read", intent_kind="read",
        )
        operation.record_remote_receipt(run_id, execution_id="read-worker", outcome="response_received")
        result = operation.finish_run(run_id, execution_id="read-worker", status="success")
        self.assertEqual("success", result["status"])

    def test_reconciliation_account_query_fences_unfinished_native_write(self):
        account_id = self._runtime_account("producer-fence@example.test")
        task = operation.create_runtime_task(
            task_type="codex_token_refresh",
            account_id=account_id,
            email="producer-fence@example.test",
            source_system="native_operations",
            source_id="producer-fence-1",
        )
        run_id = int(task["run"]["id"])
        execution_id = "producer-fence-worker"
        operation.claim_run(run_id, execution_id=execution_id, worker_pid=707)
        lease_token = operation.acquire_account_lease(
            account_id=account_id, run_id=run_id, ttl_seconds=120,
        )
        operation.record_remote_intent(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            action="codex_token_refresh",
            request_id="producer-fence-request",
        )
        operation.record_remote_receipt(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            outcome="response_received",
            action="codex_token_refresh",
        )
        fenced = operation.list_reconciliation_accounts(
            task_type="codex_token_refresh", account_ids=[account_id],
        )
        self.assertEqual([account_id], [row["account_id"] for row in fenced])
        self.assertEqual("response_received", fenced[0]["remote_intent_state"])
        self.assertTrue(fenced[0]["reconcile_required"])

        rejected_account_id = self._runtime_account("producer-rejected@example.test")
        rejected_task = operation.create_runtime_task(
            task_type="codex_token_refresh",
            account_id=rejected_account_id,
            email="producer-rejected@example.test",
            source_system="native_operations",
            source_id="producer-rejected-1",
        )
        rejected_run_id = int(rejected_task["run"]["id"])
        rejected_execution = "producer-rejected-worker"
        operation.claim_run(rejected_run_id, execution_id=rejected_execution, worker_pid=708)
        rejected_lease = operation.acquire_account_lease(
            account_id=rejected_account_id, run_id=rejected_run_id, ttl_seconds=120,
        )
        operation.record_remote_intent(
            rejected_run_id,
            execution_id=rejected_execution,
            lease_token=rejected_lease,
            action="codex_token_refresh",
            request_id="producer-rejected-request",
        )
        operation.record_remote_receipt(
            rejected_run_id,
            execution_id=rejected_execution,
            lease_token=rejected_lease,
            outcome="rejected",
            action="codex_token_refresh",
        )
        self.assertEqual(
            [],
            operation.list_reconciliation_accounts(
                task_type="codex_token_refresh", account_ids=[rejected_account_id],
            ),
        )
        operation.finish_run(
            rejected_run_id,
            status="failed",
            execution_id=rejected_execution,
            lease_token=rejected_lease,
            result_summary={"status": "failed"},
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
