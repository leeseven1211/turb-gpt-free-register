"""Sub2API 自动化仅连接已有授权和同步入口。"""
import unittest
from unittest.mock import Mock, patch

from core.codex import operation_service, sub2api_sync, token_refresh_service
from core.integrations.sub2api import client


class Sub2ApiAutomationIntegrationTests(unittest.TestCase):
    def test_monitor_refresh_defers_sync_to_original_remote_targets(self):
        original = {"email": "refresh@example.test", "access_token": "old", "refresh_token": "refresh"}
        updated = {**original, "access_token": "new"}
        with patch.object(token_refresh_service, "_load_credential", return_value=(original, "test.json", "refresh")), patch.object(
            token_refresh_service, "_request_refresh", return_value={"access_token": "new", "expires_in": 3600}
        ), patch.object(token_refresh_service, "_persist_refreshed_credential"), patch.object(
            token_refresh_service, "_build_updated_credential", return_value=(updated, False)
        ), patch.object(token_refresh_service, "_sync_sub2_if_needed") as generic_sync:
            result = token_refresh_service._perform_refresh("test.json", persist_pending=False, sync_sub2api=False)
        self.assertTrue(result["credential_persisted"])
        generic_sync.assert_not_called()
        self.assertEqual("deferred_to_original_targets", result["sub2_sync"])

    def test_monitor_refresh_submission_persists_deferred_sync(self):
        row = {"filename": "test.json", "email": "refresh@example.test", "oauth_refreshable": True}
        with patch.object(token_refresh_service.db, "list_codex_accounts", return_value=[row]), patch.object(
            token_refresh_service.db, "get_account_by_email", return_value={"id": 12}
        ), patch.object(token_refresh_service, "decorate_row", return_value=row), patch.object(
            token_refresh_service.operation_runtime_store, "active_run_for_account", return_value=None
        ), patch.object(token_refresh_service.operation_runtime_store, "list_reconciliation_accounts", return_value=[]), patch.object(
            token_refresh_service, "_register_worker"
        ), patch.object(token_refresh_service, "_update_account_state"), patch.object(
            token_refresh_service, "_durable_submit", return_value={"accepted": True, "run_id": 8}
        ) as submit:
            result = token_refresh_service.enqueue_refresh("test.json", trigger="sub2api_monitor")
        self.assertTrue(result["accepted"])
        self.assertTrue(submit.call_args.kwargs["data"]["sub2api_sync_deferred"])

    def test_monitor_oauth_records_fixed_targets_without_account_completion(self):
        account = {"id": 12, "email": "monitor@example.test"}
        with patch.object(operation_service.db, "get_account", return_value=account), patch.object(
            operation_service, "submit", return_value={"accepted": True, "run_id": 8}
        ) as submit, patch.object(client, "configured_backend_identity", return_value="backend-test", create=True):
            result = operation_service.enqueue_oauth(account_id=12, remote_account_ids=[41, 42])
        self.assertTrue(result["accepted"])
        self.assertFalse(submit.call_args.kwargs.get("completion_auth", False))
        self.assertEqual({"backend_identity": "backend-test", "remote_account_ids": [41, 42]},
                         submit.call_args.kwargs["sub2api_targets"])

    def test_refresh_sync_uses_upload_reset_and_enable(self):
        row = {"filename": "test.json", "email": "refresh@example.test", "sub2_uploaded_count": 1}
        with patch.object(token_refresh_service.db, "list_codex_accounts", return_value=[row]), patch.object(
            token_refresh_service.db, "get_account_by_email", return_value={}
        ), patch.object(token_refresh_service.db, "read_codex_credential", return_value=(
            '{"email":"refresh@example.test","access_token":"synthetic-token"}', "test.json"
        )), patch.object(token_refresh_service.db, "mark_codex_sub2_uploaded"), patch.object(
            client, "upload_and_enable_configured_codex_oauth_credential",
            return_value={"uploaded": True, "enabled": True, "sub2api_account_id": 41},
        ) as sync:
            result = token_refresh_service._sync_sub2_if_needed("test.json")
        sync.assert_called_once()
        self.assertEqual("success", result["status"])
        self.assertTrue(result["enabled"])

    def test_failed_oauth_sync_saves_retry_without_repeating_authorization(self):
        from core.integrations.sub2api import jobs
        failure = client.Sub2ApiSyncError("enable_scheduling", "sub2api_timeout", "模拟超时",
                                         uploaded=True, sub2api_account_id=41)
        with patch.object(sub2api_sync.codex_store, "read_codex_credential", return_value=(
            '{"email":"sync@example.test","access_token":"synthetic-token"}', "test.json"
        )), patch.object(sub2api_sync.codex_store, "mark_codex_sub2_uploaded"), patch.object(
            sub2api_sync.codex_store, "mark_codex_sub2_sync_error"
        ), patch.object(client, "upload_and_enable_configured_codex_oauth_credential", side_effect=failure), patch.object(
            jobs, "record_sync_failure", return_value={"pending": True}
        ) as retry:
            result = sub2api_sync.sync_confirmed_credential(
                {"file_path": "/logical/test.json"}, email="sync@example.test",
                checkpoint=Mock(), assert_lease=Mock(),
            )
        self.assertEqual("failed", result["status"])
        retry.assert_called_once()
        self.assertEqual(41, retry.call_args.args[1]["sub2api_account_id"])
