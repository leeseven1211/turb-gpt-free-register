"""OAuth 成功后按任务快照上传凭证并恢复 Sub2API 调度。"""
import json
import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from core import account_task_store
from core.codex import oauth, operation_service as service
from core.integrations.sub2api import client as sub2api_client
from core.operations import run_log
from core.storage import codex as codex_store, records
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase
from tests.support_settlement import install_native_settlement_fixture


class CodexOAuthSub2ApiTests(PostgresTestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        log_root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(run_log, "_LOG_ROOT", log_root))
        stack.enter_context(patch.object(run_log, "_TASK_LOG_ROOT", log_root / "tasks"))
        stack.enter_context(patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": self.schema}))
        stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        stack.enter_context(patch.object(service, "_feature_ready", return_value=(True, "")))
        account_task_store.init()
        # Each native test truncates the capability marker but retains readiness.
        operation.reset_ready()
        operation.init()
        install_native_settlement_fixture(self)
        self.email = "oauth-sub2api@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email, "account_status": "active",
        })
        self.filename = "codex-oauth-sub2api@example.test-free.json"
        self.credential = {
            "email": self.email, "type": "codex", "account_id": "oauth-account",
            "access_token": "synthetic-new-access", "refresh_token": "synthetic-new-refresh",
        }

    def _execute(self, *, enabled=True, confirmed=True, sync_error=None, credential=None, cancelled=False, saved_snapshot=True, targets=None):
        task = service.operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=self.account_id, email=self.email,
            data={"config_snapshot": {"oauth_driver": "protocol", "auto_upload_sub2api": enabled},
                  **({"sub2api_targets": targets} if targets else {})} if saved_snapshot else {},
        )
        route = Mock(proxy_url=None, provider="test", mode="direct", region="")
        route.public_dict.return_value = {"network_route": "test-direct"}
        cancellation = {"requested": False}

        def authorize(*args, **kwargs):
            if confirmed:
                codex_store.save_codex_credential_record(self.filename, credential or self.credential)
            cancellation["requested"] = cancelled
            return {
                "ok": confirmed, "status": "success" if confirmed else "failed",
                "credential_confirmed": confirmed,
                "file_path": f"/logical/credentials/{self.filename}" if confirmed else None,
                "message": "Codex 凭证已保存" if confirmed else "授权失败",
            }

        with (
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch.object(service, "_config_snapshot", return_value={"oauth_driver": "protocol", "auto_upload_sub2api": True}),
            patch.object(oauth, "run_codex_oauth", side_effect=authorize) as grant,
            patch.object(service.CancellationToken, "requested", side_effect=lambda **kwargs: cancellation["requested"]),
            patch.object(
                sub2api_client, "upload_and_enable_configured_codex_oauth_credential",
                create=True, side_effect=sync_error,
                return_value={"ok": True, "uploaded": True, "enabled": True, "sub2api_account_id": 42},
            ) as upload,
        ):
            self._oauth_grant = grant
            self._sub2api_upload = upload
            run_id = int(task["run"]["id"])
            returned = service._execute_run(run_id)
            self.settlement_fixture.wait_for_run_released(run_id)
        run = service.operation_task_store.get_run(int(task["run"]["id"]))
        row = records.get_row_by(records.CODEX_CREDENTIALS, "filename", self.filename)
        return returned, run, row, upload

    def test_monitor_success_queues_original_targets_without_generic_upload(self):
        targets = {"backend_identity": "original-backend", "remote_account_ids": [41, 42]}
        with patch("core.integrations.sub2api.jobs.queue_sync", return_value={"accepted": True, "pending": True}) as queue:
            returned, run, _, upload = self._execute(targets=targets)
        self.assertEqual("success", run["status"])
        self.assertEqual("pending", returned["sub2api_sync"]["status"])
        self.assertEqual("original-backend", queue.call_args.kwargs["expected_backend"])
        self.assertEqual([41, 42], queue.call_args.kwargs["remote_account_ids"])
        upload.assert_not_called()

    def test_monitor_cancel_after_oauth_skips_followup_sync(self):
        targets = {"backend_identity": "original-backend", "remote_account_ids": [41]}
        with patch("core.integrations.sub2api.jobs.queue_sync") as queue:
            returned, run, _, upload = self._execute(targets=targets, cancelled=True)
        self.assertEqual("success", run["status"])
        self.assertEqual("cancelled", returned["sub2api_sync"]["status"])
        queue.assert_not_called()
        upload.assert_not_called()

    def test_enabled_uploads_current_credential_and_saves_success_summary(self):
        returned, run, row, upload = self._execute()

        self.assertEqual("success", run["status"])
        self.assertEqual("success", returned["sub2api_sync"]["status"])
        self.assertEqual(42, run["result_summary"]["sub2api_sync"]["sub2api_account_id"])
        self.assertEqual(1, row["sub2_uploaded_count"])
        self.assertIsNone(row.get("sub2_sync_error"))
        self.assertEqual(self.credential, upload.call_args.args[0])
        self.assertNotIn("synthetic-new-refresh", json.dumps(run["result_summary"]))

    def test_disabled_snapshot_does_not_upload_even_if_global_is_enabled(self):
        with patch("config.codex.CODEX_OAUTH_AUTO_UPLOAD_SUB2API", True, create=True):
            returned, run, row, upload = self._execute(enabled=False)

        self.assertEqual("success", returned["status"])
        self.assertEqual("success", run["status"])
        self.assertEqual(0, int(row.get("sub2_uploaded_count") or 0))
        upload.assert_not_called()

    def test_unconfirmed_oauth_does_not_upload_old_credential(self):
        codex_store.save_codex_credential_record(self.filename, self.credential)
        _, run, _, upload = self._execute(confirmed=False)

        self.assertNotEqual("success", run["status"])
        upload.assert_not_called()

    def test_upload_failure_keeps_oauth_valid_and_records_classified_sync_error(self):
        returned, run, row, _ = self._execute(sync_error=RuntimeError("synthetic-private-response"))

        self.assertEqual("success", returned["status"])
        self.assertEqual("success", run["status"])
        self.assertEqual("valid", service.db.get_account(self.account_id)["codex_credential_state"])
        sync = run["result_summary"]["sub2api_sync"]
        self.assertEqual("failed", sync["status"])
        self.assertTrue(sync["error_code"])
        self.assertIn("sub2api", row["sub2_sync_error"])
        self.assertIn("sub2api", run["result_summary"]["message"])
        self.assertNotIn("synthetic-private-response", json.dumps(run["result_summary"]))

    def test_mismatched_credential_email_is_classified_without_upload(self):
        _, run, row, upload = self._execute(credential={**self.credential, "email": "other@example.test"})

        self.assertEqual("success", run["status"])
        self.assertEqual("sub2api_credential_identity_mismatch", run["result_summary"]["sub2api_sync"]["error_code"])
        self.assertTrue(row["sub2_sync_error"])
        upload.assert_not_called()

    def test_projection_freezes_auto_upload_choice(self):
        snapshot = service._project_config_snapshot({"CODEX_OAUTH_AUTO_UPLOAD_SUB2API": True}, 17)
        self.assertTrue(snapshot["auto_upload_sub2api"])
        self.assertFalse(service._project_config_snapshot({}, None)["auto_upload_sub2api"])

    def test_cancel_after_oauth_preserves_credential_and_skips_upload(self):
        returned, run, row, upload = self._execute(cancelled=True)

        self.assertEqual("success", returned["status"])
        self.assertEqual("cancelled", run["result_summary"]["sub2api_sync"]["status"])
        self.assertEqual("valid", service.db.get_account(self.account_id)["codex_credential_state"])
        self.assertEqual(0, int(row.get("sub2_uploaded_count") or 0))
        upload.assert_not_called()

    def test_reset_failure_records_successful_upload_separately(self):
        error = sub2api_client.Sub2ApiSyncError(
            "reset_error", "sub2api_http_error", "Sub2API 管理接口返回 HTTP 503",
            uploaded=True, sub2api_account_id=42,
        )
        _, run, row, _ = self._execute(sync_error=error)

        self.assertEqual("success", run["status"])
        self.assertEqual(1, row["sub2_uploaded_count"])
        sync = run["result_summary"]["sub2api_sync"]
        self.assertEqual("reset_error", sync["stage"])
        self.assertTrue(sync["uploaded"])
        self.assertFalse(sync["enabled"])
        self.assertIn("sub2api_http_error", row["sub2_sync_error"])

    def test_legacy_run_without_snapshot_does_not_inherit_new_enabled_switch(self):
        _, run, row, upload = self._execute(saved_snapshot=False)

        self.assertEqual("success", run["status"])
        self.assertEqual(0, int(row.get("sub2_uploaded_count") or 0))
        upload.assert_not_called()

    def test_sync_lease_loss_keeps_confirmed_oauth_result(self):
        returned, run, row, _ = self._execute(sync_error=service.task_gateway.OperationLeaseLost("租约已失效"))

        self.assertEqual("success", returned["status"])
        self.assertEqual("success", run["status"])
        self.assertTrue(run["result_summary"]["credential_confirmed"])
        sync = run["result_summary"]["sub2api_sync"]
        self.assertEqual("sub2api_sync_lease_lost", sync["error_code"])
        self.assertEqual(0, int(row.get("sub2_uploaded_count") or 0))
        self.assertNotIn("request_unknown", json.dumps(run["result_summary"]))

    def test_sync_progress_has_named_step_only_when_enabled(self):
        from core.operations.stages import flow_for

        run = {"data": {"config_snapshot": {"auto_upload_sub2api": True}}}
        enabled = {step["id"]: step for step in flow_for("codex_retry", run)}
        self.assertEqual("上传并启用 Sub2API", enabled["sub2api_sync"]["label"])
        self.assertNotIn("sub2api_sync", {step["id"] for step in flow_for("codex_retry", {})})
        self.assertIn("sub2api_sync", {step["id"] for step in flow_for("codex_retry")})

    def test_cancellation_after_upload_preserves_uploaded_fact(self):
        error = service.OperationCancelled("已取消")
        error.sub2api_uploaded = True
        error.sub2api_account_id = 42
        error.sub2api_stage = "enable_scheduling"
        _, run, row, _ = self._execute(sync_error=error)

        self.assertEqual("success", run["status"])
        self.assertEqual(1, row["sub2_uploaded_count"])
        sync = run["result_summary"]["sub2api_sync"]
        self.assertEqual("cancelled", sync["status"])
        self.assertEqual("enable_scheduling", sync["stage"])
        self.assertTrue(sync["uploaded"])

    def test_sync_finish_fence_rejection_does_not_rewrite_oauth_as_unknown(self):
        from psycopg.errors import InsufficientPrivilege
        from core.operations import settlement
        from core.operations.settlement_contracts import OperationSettlementPending
        from core.storage.operations import permits, settlements

        execution = intent = None
        try:
            with patch.object(service.operation_task_store, "finish_run", side_effect=InsufficientPrivilege("synthetic denied")):
                with self.assertRaises(OperationSettlementPending):
                    self._execute()
                executions = tuple(self.settlement_fixture.contexts.values())
                self.assertEqual(1, len(executions))
                execution = executions[0]
                owner = settlement.responsibility(execution)
                intent = owner.intent
                self.assertIsNotNone(intent)
                self.assertEqual("terminal", intent.kind)
                self.assertEqual("success", intent.payload["status"])
                self.assertTrue(intent.payload["result_summary"]["credential_confirmed"])
                self.assertNotIn("request_unknown", json.dumps(settlement.thaw(intent.payload["result_summary"])))
                self.assertEqual("valid", service.db.get_account(self.account_id)["codex_credential_state"])
                self.assertEqual("running", operation.get_run(int(execution.claimed_run["id"]))["status"])
                self.assertFalse(execution.released)
                self.assertFalse(owner.released)
                self.assertTrue(owner.callback_exited)
                self.assertFalse(owner.callback_active)
                self.assertEqual("settlement_storage_permission_denied", owner.error_code)
                self.assertIsNone(owner.receipt)
                self.assertIsNone(settlements.read_receipt(intent, domain=execution.settlement_domain))
                self.assertTrue(permits.validate(
                    execution.permit_id, execution.execution_id,
                    schema=execution.settlement_domain.permit_schema,
                    database_url=execution.settlement_domain.database_url,
                ))
                self.assertEqual(1, self._oauth_grant.call_count)
                self.assertEqual(1, self._sub2api_upload.call_count)
        finally:
            # Confirm the exact original local intent after fault removal; no business replay.
            if execution is None and self.settlement_fixture.contexts:
                executions = tuple(self.settlement_fixture.contexts.values())
                if len(executions) == 1:
                    execution = executions[0]
                    intent = settlement.responsibility(execution).intent
            if execution is not None and intent is not None:
                receipt = settlement.settle(execution, intent, lambda frozen, deadline:
                    settlements.submit_intent(frozen, domain=execution.settlement_domain, deadline=deadline))
                self.settlement_fixture.wait_for_run_released(int(execution.claimed_run["id"]))

        self.assertEqual(intent.transition_id, receipt["transition_id"])
        self.assertEqual(intent.request_digest, receipt["request_digest"])
        self.assertEqual("success", receipt["actual_result"]["status"])
        self.assertEqual("success", operation.get_run(int(execution.claimed_run["id"]))["status"])
        self.assertEqual("valid", service.db.get_account(self.account_id)["codex_credential_state"])
        self.assertNotIn("request_unknown", json.dumps(receipt["actual_result"]["result_summary"]))
        self.assertEqual(1, self._oauth_grant.call_count)
        self.assertEqual(1, self._sub2api_upload.call_count)
