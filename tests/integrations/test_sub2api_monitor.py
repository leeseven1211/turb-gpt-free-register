# -*- coding: utf-8 -*-
"""异常巡检只调用替身网络入口，修复阶段使用独立 PostgreSQL schema。"""
import importlib
import json
from contextlib import ExitStack
from unittest.mock import patch

from core.operations import task_gateway
from core.storage import codex, records
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class Sub2ApiMonitorTests(PostgresTestCase):
    def setUp(self):
        self.monitor = importlib.import_module("core.integrations.sub2api.monitor")
        self.store = importlib.import_module("core.storage.sub2api")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.account = {"id": 42, "email": "monitor@example.test", "extra_json": {"account_password": "saved-password"}}
        self.content = {"email": self.account["email"], "access_token": "local-access", "refresh_token": "local-refresh"}
        self.credential = {"filename": "monitor.json", "email": self.account["email"], "archived": False}
        self.remote = [{"id": 7, "status": "error", "credentials": {"email": "MONITOR@example.test"}, "error_message": "401 unauthorized"}]
        self.patch("client.configured_backend_identity", return_value="test-backend")
        self.fetch = self.patch("client.list_configured_error_accounts", side_effect=lambda **_: self.remote)
        self.drain = self.patch("jobs.enqueue_due", return_value={"queued": 0})
        self.sync = self.patch("jobs.queue_sync", return_value={"accepted": True, "pending": True, "items": [{"status": "queued"}]})
        self.refresh = self.patch("token_refresh_service.enqueue_refresh", return_value={"accepted": True, "run_id": 11, "task_id": 10})
        self.oauth = self.patch("operation_service.enqueue_oauth", return_value={"accepted": True, "run_id": 21, "task_id": 20}, create=True)
        self.patch("db.list_codex_accounts", side_effect=lambda **_: [self.credential])
        self.patch("db.get_account_by_email", side_effect=lambda email: self.account if email.lower() == self.account["email"] else None)
        self.patch("db.get_account", side_effect=lambda account_id: self.account if account_id == 42 else None)
        self.patch("db.read_codex_credential", side_effect=lambda _: (json.dumps(self.content), ""))
        self.active = self.patch("operation_runtime_store.active_run_for_account", return_value=None)
        self.run = self.patch("operation_runtime_store.get_run", return_value={"id": 11, "status": "running"})
        self.patch("_now", return_value=1000.0)
        for key, value in {"SUB2API_MONITOR_ENABLED": True, "SUB2API_MONITOR_INTERVAL_SECONDS": 300,
                           "SUB2API_MONITOR_COOLDOWN_SECONDS": 300, "SUB2API_MONITOR_MAX_PER_CYCLE": 20,
                           "SUB2API_UPLOAD_GROUP_IDS": "3"}.items():
            self.stack.enter_context(patch.object(self.monitor._cfg, key, value, create=True))

    def patch(self, name, **kwargs):
        return self.stack.enter_context(patch("core.integrations.sub2api.monitor." + name, **kwargs))

    def test_merges_email_and_repairs_multiple_remote_ids_with_one_refresh(self):
        self.remote.append({**self.remote[0], "id": 8})
        result = self.monitor._run_once()
        self.refresh.assert_called_once_with("monitor.json", trigger="sub2api_monitor")
        repair = self.store.get_repair("test-backend", 42)
        self.assertEqual(repair["stage"], "refresh_wait")
        self.assertEqual(repair["remote_account_ids"], [7, 8])
        self.assertEqual(result["refresh_queued"], 1)
        self.fetch.assert_called_once_with(group_ids=[3], expected_backend="test-backend")
        self.assertNotIn("monitor@example.test", json.dumps(result))

    def test_busy_and_persisted_cooldown_do_not_submit(self):
        self.active.return_value = {"id": 99, "status": "running"}
        self.assertEqual(self.monitor._run_once()["reasons"]["account_busy"], 1)
        self.active.return_value = None
        self.store.save_repair("test-backend", 42, stage="cooldown", next_attempt_at=1200)
        self.assertEqual(self.monitor._run_once()["reasons"]["cooldown"], 1)
        self.refresh.assert_not_called()
        self.oauth.assert_not_called()

    def test_restart_keeps_refresh_wait_then_syncs_new_generation_to_original_ids(self):
        self.monitor._run_once()
        self.monitor = importlib.reload(self.monitor)
        self.assertEqual(self.monitor._run_once()["reasons"]["repair_in_progress"], 1)
        self.refresh.assert_called_once()
        self.content["access_token"] = "renewed-access"
        self.remote = []
        result = self.monitor._run_once()
        self.sync.assert_called_once_with("monitor.json", remote_account_ids=[7], trigger="sub2api_monitor", expected_backend="test-backend")
        self.assertEqual(result["sync_queued"], 1)
        self.assertEqual(self.store.get_repair("test-backend", 42)["stage"], "sync_wait")

    def test_failed_sync_is_retried_before_scan_and_never_relogs(self):
        self.remote[0]["credentials"]["access_token"] = "older-access"
        self.monitor._run_once()
        self.sync.return_value = {"accepted": True, "pending": True, "items": [{"status": "failed"}]}
        self.monitor._run_once()
        self.assertEqual(self.drain.call_count, 2)
        self.assertEqual(self.store.get_repair("test-backend", 42)["stage"], "sync_wait")
        self.refresh.assert_not_called()
        self.oauth.assert_not_called()

    def test_deactivated_and_archived_accounts_never_refresh(self):
        self.account["account_status"] = "deactivated"
        self.assertEqual(self.monitor._run_once()["reasons"]["account_deactivated"], 1)
        self.account.pop("account_status")
        self.account["archived"] = True
        self.assertEqual(self.monitor._run_once()["reasons"]["account_archived"], 1)
        self.refresh.assert_not_called()
        self.oauth.assert_not_called()

    def test_explicit_refresh_reauth_reuses_existing_oauth_entry(self):
        self.refresh.return_value = {"accepted": False, "error_code": "reauth_required"}
        self.monitor._run_once()
        self.oauth.assert_called_once_with(42, trigger="sub2api_monitor", remote_account_ids=[7], backend_identity="test-backend")
        self.assertEqual(self.store.get_repair("test-backend", 42)["stage"], "reauth_wait")
        self.monitor._run_once()
        self.oauth.assert_called_once()

    def test_completed_refresh_reauth_failure_advances_once_after_restart(self):
        self.monitor._run_once()
        self.run.return_value = {"id": 11, "status": "failed", "result_summary": {"error_code": "reauth_required"}}
        self.monitor._run_once()
        self.oauth.assert_called_once()
        self.assertEqual(self.store.get_repair("test-backend", 42)["run_id"], 21)

    def test_missing_automatic_login_material_has_retryable_reason(self):
        self.account["extra_json"] = {}
        self.refresh.return_value = {"accepted": False, "error_code": "reauth_required"}
        self.monitor._run_once()
        self.oauth.assert_not_called()
        self.assertEqual(self.store.get_repair("test-backend", 42)["last_code"], "automatic_login_material_missing")
        self.assertGreater(self.store.get_repair("test-backend", 42)["next_attempt_at"], 1000)

    def test_unrecognized_error_only_syncs_once_without_login(self):
        self.remote[0]["error_message"] = "unexpected upstream state"
        self.sync.return_value = {"accepted": True, "pending": False, "items": [{"status": "success"}]}
        self.assertEqual(self.monitor._run_once()["reasons"]["unrecognized_remote_error"], 1)
        with patch("core.integrations.sub2api.monitor._now", return_value=1400):
            self.monitor._run_once()
        self.sync.assert_called_once()
        self.refresh.assert_not_called()
        self.oauth.assert_not_called()

    def test_remote_rate_limit_is_cooldown_and_refresh_unknown_is_not_replayed(self):
        self.remote[0]["error_message"] = "HTTP 429 too many requests"
        self.assertEqual(self.monitor._run_once()["reasons"]["remote_transient_error"], 1)
        self.refresh.assert_not_called()
        self.remote[0]["error_message"] = "401 unauthorized"
        with patch("core.integrations.sub2api.monitor._now", return_value=1400):
            self.refresh.return_value = {"accepted": False, "error_code": "needs_reconciliation"}
            self.monitor._run_once()
        with patch("core.integrations.sub2api.monitor._now", return_value=1800):
            self.monitor._run_once()
        self.refresh.assert_called_once()
        self.oauth.assert_not_called()

    def test_disabled_monitor_still_drains_failed_uploads_and_status_is_safe(self):
        with patch.object(self.monitor._cfg, "SUB2API_MONITOR_ENABLED", False):
            result = self.monitor._run_once()
        self.drain.assert_called_once()
        self.fetch.assert_not_called()
        self.assertFalse(result["enabled"])
        self.assertNotIn("monitor@example.test", json.dumps(self.monitor.status()))

    def test_missing_remote_id_never_uses_a_general_upload(self):
        self.remote[0].pop("id")
        result = self.monitor._run_once()
        self.assertEqual(result["reasons"].get("remote_account_id_missing"), 1)
        self.sync.assert_not_called()
        self.refresh.assert_not_called()

    def test_known_enabled_mfa_without_saved_secret_cannot_start_automatic_oauth(self):
        self.account["twofa_status"] = "success"
        self.refresh.return_value = {"accepted": False, "error_code": "reauth_required"}
        self.monitor._run_once()
        self.oauth.assert_not_called()
        self.assertEqual(self.store.get_repair("test-backend", 42)["last_code"], "automatic_login_material_missing")

    def test_cooldown_account_does_not_starve_another_account_at_cycle_limit(self):
        second = {"id": 43, "email": "other@example.test"}
        self.remote.append({"id": 9, "credentials": {"email": second["email"]}, "error_message": "401 unauthorized"})
        self.credential["email"] = second["email"]
        self.content["email"] = second["email"]
        self.patch("db.get_account_by_email", side_effect=lambda email: self.account if email == self.account["email"] else second)
        self.store.save_repair("test-backend", 42, stage="cooldown", next_attempt_at=1500)
        with patch.object(self.monitor._cfg, "SUB2API_MONITOR_MAX_PER_CYCLE", 1):
            self.monitor._run_once()
        self.refresh.assert_called_once()

    def test_comma_separated_group_filter_is_parsed_before_remote_scan(self):
        with patch.object(self.monitor._cfg, "SUB2API_UPLOAD_GROUP_IDS", "2,5"):
            self.monitor._run_once()
        self.fetch.assert_called_once_with(group_ids=[2, 5], expected_backend="test-backend")

    def test_backend_change_between_identity_and_scan_never_binds_foreign_ids(self):
        self.fetch.side_effect = self.monitor.client.Sub2ApiSyncError(
            "configuration", "sub2api_backend_changed", "模拟扫描前切换后端")
        result = self.monitor._run_once()
        self.fetch.assert_called_once_with(group_ids=[3], expected_backend="test-backend")
        self.assertEqual(1, result["reasons"].get("remote_scan_failed"))
        self.assertEqual([], self.store.list_repairs("test-backend", active_only=False))
        self.refresh.assert_not_called()
        self.oauth.assert_not_called()
        self.sync.assert_not_called()

    def test_new_remote_target_receives_existing_generation_without_new_login(self):
        self.remote[0]["error_message"] = "unexpected upstream state"
        self.sync.return_value = {"accepted": True, "pending": False, "items": [{"status": "success"}]}
        self.monitor._run_once()
        self.remote.append({**self.remote[0], "id": 8})
        with patch("core.integrations.sub2api.monitor._now", return_value=1400):
            self.monitor._run_once()
        self.assertEqual(self.sync.call_count, 2)
        self.assertEqual(self.sync.call_args.kwargs["remote_account_ids"], [7, 8])
        self.oauth.assert_not_called()

    def test_refresh_unknown_survives_restart_without_new_refresh_or_oauth(self):
        self.monitor._run_once()
        self.run.return_value = {"id": 11, "status": "request_unknown", "result_summary": {"error_code": "request_unknown", "error": "token endpoint HTTP 503"}}
        self.monitor._run_once()
        self.monitor = importlib.reload(self.monitor)
        self.monitor._run_once()
        self.assertEqual(self.store.get_repair("test-backend", 42)["last_code"], "needs_reconciliation")
        self.refresh.assert_called_once()
        self.oauth.assert_not_called()

    def test_cancelled_oauth_sync_receipt_precedes_changed_credential_generation(self):
        self.refresh.return_value = {"accepted": False, "error_code": "reauth_required"}
        self.monitor._run_once(force=True)
        self.content["access_token"] = "reauthorized-but-sync-stopped"
        self.run.return_value = {"id": 21, "status": "success", "result_summary": {
            "sub2api_sync": {"status": "cancelled", "error_code": "sub2api_sync_cancelled"},
        }}
        self.monitor._run_once()
        self.monitor = importlib.reload(self.monitor)
        self.monitor._run_once()
        final = self.store.get_repair("test-backend", 42)
        self.assertEqual("waiting_manual", final["stage"])
        self.assertEqual("sub2api_sync_cancelled", final["last_code"])
        self.assertEqual(self.monitor.jobs.credential_generation(self.content), final["source_generation"])
        self.assertFalse(final["manual_requested"])
        self.sync.assert_not_called()
        self.oauth.assert_called_once()


class ManualSub2ApiContinuationTests(PostgresTestCase):
    """手动巡检的后续阶段走真实任务、凭据和补传表。"""

    def setUp(self):
        from core.integrations.sub2api import monitor
        from core.storage import sub2api
        self.monitor, self.store = monitor, sub2api
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        operation.reset_ready()
        operation.init()
        self.email = "manual-monitor@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {"email": self.email})
        self.filename = "codex-manual-monitor.json"
        self.content = {"email": self.email, "account_id": "stable-chatgpt-account", "access_token": "old-access", "refresh_token": "old-refresh"}
        codex.save_codex_credential_record(self.filename, self.content)
        self.scan = self.stack.enter_context(patch.object(monitor.client, "list_configured_error_accounts", return_value=[
            {"id": remote_id, "credentials": {"email": self.email}, "error_message": "401 unauthorized"} for remote_id in (71, 72)
        ]))
        self.stack.enter_context(patch.object(monitor.client, "configured_backend_identity", return_value="manual-backend"))
        self.stack.enter_context(patch.object(monitor.client, "configured_upload_options", return_value={}))
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.refresh = self.stack.enter_context(patch.object(monitor.token_refresh_service, "enqueue_refresh", side_effect=self.enqueue_refresh))
        self.oauth = self.stack.enter_context(patch.object(monitor.operation_service, "enqueue_oauth"))
        for key in ("SUB2API_MONITOR_ENABLED", "SUB2API_SYNC_RETRY_ENABLED"):
            self.stack.enter_context(patch.object(monitor._cfg, key, False))

    def enqueue_refresh(self, filename, **kwargs):
        return task_gateway.submit_durable_operation(task_type="codex_token_refresh", account_id=self.account_id,
            email=self.email, trigger="sub2api_monitor", dispatch=False)

    def test_manual_refresh_chain_finishes_multiple_targets_without_enabling_new_scans(self):
        self.monitor._run_once(force=True)
        repair = self.store.get_repair("manual-backend", self.account_id)
        self.assertTrue(repair.get("manual_requested"))
        self.assertTrue(self.monitor._periodic_enabled())
        self.content["access_token"] = "refreshed-access"
        codex.save_codex_credential_record(self.filename, self.content)
        operation.finish_run(repair["run_id"], status="success")
        self.monitor = importlib.reload(self.monitor)
        continued = self.monitor._run_once()
        self.assertTrue(self.store.list_jobs(filename=self.filename), continued)
        with patch.object(self.monitor.jobs.client, "update_and_enable_configured_account", side_effect=lambda auth, remote_id, **kw: {
            "uploaded": True, "enabled": True, "sub2api_account_id": remote_id,
        }) as update:
            for _ in range(4):
                for job in self.store.list_jobs(filename=self.filename):
                    if job["status"] == "queued":
                        task_gateway._execute_operation_handler("sub2api_sync", job["run_id"])
                self.monitor._run_once()
        self.assertEqual({71, 72}, {call.args[1] for call in update.call_args_list})
        self.assertEqual(["success", "success"], [row["status"] for row in self.store.list_jobs(filename=self.filename)])
        self.assertFalse(self.store.get_repair("manual-backend", self.account_id).get("manual_requested"))
        self.assertFalse(self.monitor._periodic_enabled())
        self.monitor._run_once()
        self.scan.assert_called_once()
        self.refresh.assert_called_once()
        self.oauth.assert_not_called()

    def test_disabled_monitor_does_not_resume_unmarked_historical_repairs(self):
        self.store.save_repair("manual-backend", self.account_id, stage="refresh_wait", run_id=123,
            remote_account_ids=[71], source_generation="old-generation")
        self.assertFalse(self.monitor._periodic_enabled())
        self.monitor._run_once()
        self.scan.assert_not_called()
        self.refresh.assert_not_called()
        self.assertEqual([], self.store.list_jobs(filename=self.filename))

    def test_manual_chain_stops_at_unknown_refresh_result_without_new_scan(self):
        self.monitor._run_once(force=True)
        repair = self.store.get_repair("manual-backend", self.account_id)
        operation.finish_run(repair["run_id"], status="attention_required", result_summary={"error_code": "request_unknown"})
        self.monitor._run_once()
        final = self.store.get_repair("manual-backend", self.account_id)
        self.assertEqual("waiting_manual", final["stage"])
        self.assertFalse(final.get("manual_requested"))
        self.assertFalse(self.monitor._periodic_enabled())
        self.monitor._run_once()
        self.scan.assert_called_once()
        self.refresh.assert_called_once()
        self.oauth.assert_not_called()

    def test_manual_reauth_chain_preserves_original_targets_without_new_cycle(self):
        self.refresh.side_effect = None
        self.refresh.return_value = {"accepted": False, "error_code": "reauth_required"}
        self.oauth.side_effect = lambda account_id, **kwargs: task_gateway.submit_durable_operation(
            task_type="codex_retry", account_id=account_id, email=self.email, dispatch=False)
        with patch.object(self.monitor, "_automatic_login_ready", return_value=True):
            self.monitor._run_once(force=True)
        repair = self.store.get_repair("manual-backend", self.account_id)
        self.assertEqual("reauth_wait", repair["stage"])
        self.assertTrue(repair["manual_requested"])
        self.content["access_token"] = "reauthorized-access"
        codex.save_codex_credential_record(self.filename, self.content)
        operation.finish_run(repair["run_id"], status="success")
        self.monitor._run_once()
        self.assertEqual({71, 72}, {job["remote_account_id"] for job in self.store.list_jobs(filename=self.filename)})
        self.oauth.assert_called_once()
        self.scan.assert_called_once()

    def test_manual_sync_failure_stops_continuation_without_enabling_retries(self):
        self.monitor._run_once(force=True)
        repair = self.store.get_repair("manual-backend", self.account_id)
        self.content["access_token"] = "refreshed-access"
        codex.save_codex_credential_record(self.filename, self.content)
        operation.finish_run(repair["run_id"], status="success")
        self.monitor._run_once()
        job = next(row for row in self.store.list_jobs(filename=self.filename) if row["status"] == "queued")
        with patch.object(self.monitor.jobs.client, "update_and_enable_configured_account", side_effect=
                          self.monitor.jobs.client.Sub2ApiSyncError("upload", "sub2api_timeout", "模拟超时")):
            task_gateway._execute_operation_handler("sub2api_sync", job["run_id"])
        self.monitor._run_once()
        final = self.store.get_repair("manual-backend", self.account_id)
        self.assertFalse(final["manual_requested"])
        self.assertEqual("waiting_manual", final["stage"])
        self.assertFalse(self.monitor._periodic_enabled())
        self.refresh.assert_called_once()
        self.oauth.assert_not_called()
