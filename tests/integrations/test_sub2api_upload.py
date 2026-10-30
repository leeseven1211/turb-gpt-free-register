# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import Mock, patch

import requests

from config import sub2api as sub2api_config
from core.integrations.sub2api import client as sub2api_client
from core.integrations.sub2api.client import upload_codex_oauth_credential
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class Sub2ApiUploadTests(unittest.TestCase):
    @patch("core.integrations.sub2api.client.requests.post")
    def test_codex_oauth_json_uses_top_level_email_for_import_name(self, post):
        response = Mock(status_code=200, text='{"code":0,"message":"success"}')
        response.json.return_value = {
            "code": 0,
            "message": "success",
            "data": {"total": 1, "created": 1, "updated": 0, "failed": 0},
        }
        post.return_value = response
        auth_json = {
            "type": "codex",
            "email": "codex@example.com",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "account_id": "account-1",
        }

        result = upload_codex_oauth_credential(
            auth_json,
            "https://sub2.example/api/v1/admin/accounts/import/codex-session",
            api_token="admin-key",
            auth_header="x-api-key",
            auth_prefix="",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["email"], "codex@example.com")
        _, kwargs = post.call_args
        self.assertEqual(kwargs["headers"]["x-api-key"], "admin-key")
        self.assertEqual(kwargs["json"]["name"], "codex@example.com")
        self.assertTrue(kwargs["json"]["update_existing"])
        imported = json.loads(kwargs["json"]["contents"][0])
        self.assertEqual(imported["refresh_token"], "refresh-token")

    @patch("core.integrations.sub2api.client.requests.post")
    def test_codex_import_failure_inside_http_200_is_raised(self, post):
        response = Mock(status_code=200, text='{"code":0,"message":"success"}')
        response.json.return_value = {
            "code": 0,
            "message": "success",
            "data": {
                "total": 1,
                "created": 0,
                "updated": 0,
                "failed": 1,
                "errors": [{"index": 1, "message": "refresh token invalid"}],
            },
        }
        post.return_value = response

        with self.assertRaisesRegex(RuntimeError, "refresh token invalid"):
            upload_codex_oauth_credential(
                {"email": "bad@example.com", "refresh_token": "invalid"},
                "https://sub2.example/api/v1/admin/accounts/import/codex-session",
            )


class Sub2ApiUploadAndEnableTests(unittest.TestCase):
    def setUp(self):
        self.auth = {"email": "codex@example.test", "refresh_token": "private-refresh-token"}
        self.config_patch = patch.multiple(
            sub2api_config,
            SUB2API_API_BASE="https://sub2.example",
            SUB2API_API_URL="",
            SUB2API_API_KEY="private-admin-key",
            SUB2API_API_TIMEOUT=12,
        )
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    @staticmethod
    def response(data, status=200):
        response = Mock(status_code=status, text="private-response-body")
        response.json.return_value = {"code": 0, "data": data}
        return response

    def imported(self, action="updated", account_id=41):
        return self.response({
            "total": 1, "created": int(action == "created"), "updated": int(action == "updated"),
            "failed": 0, "skipped": 0,
            "items": [{"index": 1, "name": "codex@example.test", "action": action, "account_id": account_id}],
        })

    @patch("core.integrations.sub2api.client.requests.post")
    def test_imported_account_is_reset_before_enabling_scheduling(self, post):
        post.side_effect = [self.imported(), self.response({"id": 41, "status": "active"}), self.response({"id": 41, "schedulable": True})]

        result = sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)

        self.assertTrue(result["enabled"])
        self.assertEqual(result["sub2api_account_id"], 41)
        self.assertEqual([call.args[0] for call in post.call_args_list], [
            "https://sub2.example/api/v1/admin/accounts/import/codex-session",
            "https://sub2.example/api/v1/admin/accounts/41/clear-error",
            "https://sub2.example/api/v1/admin/accounts/41/schedulable",
        ])
        self.assertEqual(post.call_args_list[-1].kwargs["json"], {"schedulable": True})
        for call in post.call_args_list:
            self.assertEqual(call.kwargs["headers"]["x-api-key"], "private-admin-key")
            self.assertEqual(call.kwargs["timeout"], 12)
        self.assertNotIn("response", result)
        self.assertNotIn("private-refresh-token", str(result))

    @patch("core.integrations.sub2api.client.requests.post")
    def test_created_account_is_also_enabled(self, post):
        post.side_effect = [self.imported(action="created", account_id=82), self.response({"id": 82}), self.response({"id": 82})]
        result = sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(result["sub2api_account_id"], 82)
        self.assertTrue(result["enabled"])

    @patch("core.integrations.sub2api.client.requests.post")
    def test_config_hot_reload_cannot_mix_upload_and_recovery_servers(self, post):
        post.side_effect = [self.imported(), self.response({"id": 41}), self.response({"id": 41})]

        def reload_config():
            sub2api_config.SUB2API_API_BASE = "https://different.example"
            sub2api_config.SUB2API_API_KEY = "different-key"
            sub2api_config.SUB2API_API_TIMEOUT = 55

        sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth, checkpoint=reload_config)

        self.assertEqual([call.args[0] for call in post.call_args_list], [
            "https://sub2.example/api/v1/admin/accounts/import/codex-session",
            "https://sub2.example/api/v1/admin/accounts/41/clear-error",
            "https://sub2.example/api/v1/admin/accounts/41/schedulable",
        ])
        for call in post.call_args_list:
            self.assertEqual(call.kwargs["headers"]["x-api-key"], "private-admin-key")
            self.assertEqual(call.kwargs["timeout"], 12)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_missing_skipped_or_ambiguous_import_never_resets_account(self, post):
        for data in (
            {"total": 1, "updated": 1, "failed": 0},
            {"total": 1, "updated": 0, "failed": 0, "skipped": 1, "items": [{"index": 1, "action": "skipped", "account_id": 41}]},
            {"total": 1, "updated": 1, "failed": 0, "items": [{"index": 1, "action": "updated"}]},
            {"total": 1, "updated": 1, "failed": 0, "items": [{"index": 1, "action": "updated", "account_id": 41}, {"index": 1, "action": "updated", "account_id": 42}]},
            {"total": 1, "updated": 1, "failed": 0, "items": [{"index": 1, "action": "updated", "account_id": "41/clear-error"}]},
        ):
            with self.subTest(data=data):
                post.reset_mock()
                post.side_effect = None
                post.return_value = self.response(data)
                with self.assertRaises(sub2api_client.Sub2ApiSyncError) as raised:
                    sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
                self.assertEqual(raised.exception.stage, "resolve_account")
                self.assertTrue(raised.exception.code.startswith("sub2api_"))
                self.assertEqual(post.call_count, 1)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_reset_failure_does_not_enable_account_and_has_safe_reason(self, post):
        response = self.response({}, status=403)
        response.json.return_value = {"code": 403, "message": "private-refresh-token"}
        post.side_effect = [self.imported(), response]
        with self.assertRaises(sub2api_client.Sub2ApiSyncError) as raised:
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(raised.exception.stage, "reset_error")
        self.assertEqual(raised.exception.code, "sub2api_auth_rejected")
        self.assertNotIn("private", str(raised.exception))
        self.assertEqual(post.call_count, 2)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_scheduling_failure_keeps_distinct_failure_stage(self, post):
        post.side_effect = [self.imported(), self.response({"id": 41}), requests.Timeout("private-request-token")]
        with self.assertRaises(sub2api_client.Sub2ApiSyncError) as raised:
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(raised.exception.stage, "enable_scheduling")
        self.assertEqual(raised.exception.code, "sub2api_timeout")
        self.assertNotIn("private", str(raised.exception))
        self.assertTrue(raised.exception.uploaded)
        self.assertEqual(raised.exception.sub2api_account_id, 41)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_cancel_checkpoint_is_propagated_before_next_remote_request(self, post):
        class Cancelled(RuntimeError):
            pass

        post.return_value = self.imported()
        cancellation = Cancelled("已取消")
        checkpoint = Mock(side_effect=[None, cancellation])
        with self.assertRaises(Cancelled) as raised:
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth, checkpoint=checkpoint)
        self.assertIs(raised.exception, cancellation)
        self.assertTrue(raised.exception.sub2api_uploaded)
        self.assertEqual(raised.exception.sub2api_account_id, 41)
        self.assertEqual(raised.exception.sub2api_stage, "reset_error")
        self.assertEqual(post.call_count, 1)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_lease_loss_before_enabling_preserves_uploaded_account_and_stage(self, post):
        class LeaseLost(RuntimeError):
            pass

        lease_loss = LeaseLost("租约已失效")
        post.side_effect = [self.imported(), self.response({"id": 41, "status": "active"})]
        checkpoint = Mock(side_effect=[None, None, lease_loss])
        with self.assertRaises(LeaseLost) as raised:
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth, checkpoint=checkpoint)
        self.assertIs(raised.exception, lease_loss)
        self.assertTrue(raised.exception.sub2api_uploaded)
        self.assertEqual(raised.exception.sub2api_account_id, 41)
        self.assertEqual(raised.exception.sub2api_stage, "enable_scheduling")
        self.assertEqual([call.args[0] for call in post.call_args_list], [
            "https://sub2.example/api/v1/admin/accounts/import/codex-session",
            "https://sub2.example/api/v1/admin/accounts/41/clear-error",
        ])

    @patch("core.integrations.sub2api.client.requests.post")
    def test_non_json_reset_response_is_classified_without_private_body(self, post):
        response = self.response({})
        response.json.side_effect = requests.exceptions.JSONDecodeError("private-body", "private-body", 0)
        post.side_effect = [self.imported(), response]
        with self.assertRaises(sub2api_client.Sub2ApiSyncError) as raised:
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(raised.exception.stage, "reset_error")
        self.assertEqual(raised.exception.code, "sub2api_response_invalid")
        self.assertNotIn("private", str(raised.exception))
        self.assertTrue(raised.exception.uploaded)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_http_200_operation_rejection_does_not_enable_account(self, post):
        response = self.response({})
        response.json.return_value = {"code": 500, "message": "private-body"}
        post.side_effect = [self.imported(), response]
        with self.assertRaises(sub2api_client.Sub2ApiSyncError) as raised:
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(raised.exception.stage, "reset_error")
        self.assertEqual(raised.exception.code, "sub2api_operation_rejected")
        self.assertNotIn("private", str(raised.exception))
        self.assertEqual(post.call_count, 2)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_inconsistent_import_index_is_not_used_for_recovery(self, post):
        response = self.imported()
        response.json.return_value["data"]["items"][0]["index"] = 2
        post.return_value = response
        with self.assertRaises(sub2api_client.Sub2ApiSyncError) as raised:
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(raised.exception.stage, "resolve_account")
        self.assertEqual(post.call_count, 1)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_upload_failure_is_safe_and_stops_recovery(self, post):
        post.return_value = self.response({}, status=500)
        with self.assertRaises(sub2api_client.Sub2ApiSyncError) as raised:
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(raised.exception.stage, "upload")
        self.assertEqual(raised.exception.code, "sub2api_http_error")
        self.assertNotIn("private", str(raised.exception))
        self.assertEqual(post.call_count, 1)

    @patch("core.integrations.sub2api.client.requests.post")
    def test_legacy_import_url_uses_its_own_base_for_recovery(self, post):
        with patch.multiple(sub2api_config, SUB2API_API_BASE="", SUB2API_API_URL="https://sub2.example/prefix/api/v1/admin/accounts/import/codex-session"):
            post.side_effect = [self.imported(), self.response({"id": 41}), self.response({"id": 41})]
            sub2api_client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(post.call_args_list[1].args[0], "https://sub2.example/prefix/api/v1/admin/accounts/41/clear-error")


class Sub2ApiWebUploadTests(PostgresTestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    def test_codex_success_account_uploads_local_oauth_json(self):
        account = {
            "id": 23,
            "email": "codex@example.com",
            "codex_status": "success",
        }
        credential = json.dumps({
            "type": "codex",
            "email": "codex@example.com",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        })
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch("webui.app.db.get_account", return_value=account),
            patch("webui.app.db.list_codex_accounts", return_value=[{
                "email": "codex@example.com",
                "filename": "codex-codex@example.com-free.json",
            }]),
            patch("webui.app.db.read_codex_credential", return_value=(credential, "codex-codex@example.com-free.json")),
            patch("webui.app.db.mark_codex_exported") as mark_exported,
            patch("webui.app.db.mark_codex_sub2_uploaded") as mark_sub2_uploaded,
            patch("core.integrations.sub2api.client.upload_codex_oauth_credential", return_value={
                "ok": True,
                "url": "https://sub2.example/api/v1/admin/accounts/import/codex-session",
                "status_code": 200,
            }) as upload,
        ):
            response = self.client.post("/api/accounts/23/codex/upload-sub2")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(upload.call_args.args[0]["refresh_token"], "refresh-token")
        mark_exported.assert_called_once_with("codex-codex@example.com-free.json")
        mark_sub2_uploaded.assert_called_once_with("codex-codex@example.com-free.json")

    def test_codex_account_upload_rejects_deactivated_account_before_remote(self):
        account = {
            "id": 23,
            "email": "dead-upload@example.com",
            "codex_status": "success",
            "account_status": "deactivated",
        }
        credential = json.dumps({
            "type": "codex",
            "email": "dead-upload@example.com",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        })
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch("webui.app.db.get_account", return_value=account),
            patch("webui.app.db.list_codex_accounts", return_value=[{
                "email": "dead-upload@example.com",
                "filename": "codex-dead-upload@example.com-free.json",
            }]),
            patch("webui.app.db.read_codex_credential", return_value=(credential, "codex-dead-upload@example.com-free.json")),
            patch("webui.app.db.mark_codex_exported"),
            patch("webui.app.db.mark_codex_sub2_uploaded"),
            patch("core.integrations.sub2api.client.upload_codex_oauth_credential", return_value={
                "ok": True,
                "url": "https://sub2.example/api/v1/admin/accounts/import/codex-session",
                "status_code": 200,
            }) as upload,
        ):
            response = self.client.post("/api/accounts/23/codex/upload-sub2")

        self.assertEqual(response.status_code, 400)
        self.assertIn("停用", response.get_json()["error"])
        upload.assert_not_called()

    def test_codex_management_upload_rejects_stale_deactivated_account_before_remote(self):
        filename = "codex-stale-upload@example.com-free.json"
        credential = json.dumps({
            "type": "codex",
            "email": "stale-upload@example.com",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        })
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch("webui.app.db.list_codex_accounts", return_value=[{
                "email": "stale-upload@example.com",
                "filename": filename,
            }]),
            patch("webui.app.db.get_account_by_email", return_value={
                "email": "stale-upload@example.com",
                "account_status": "deactivated",
            }),
            patch("webui.app.db.read_codex_credential", return_value=(credential, filename)),
            patch("webui.app.db.mark_codex_exported"),
            patch("webui.app.db.mark_codex_sub2_uploaded"),
            patch("core.integrations.sub2api.client.upload_codex_oauth_credential", return_value={
                "ok": True,
                "url": "https://sub2.example/api/v1/admin/accounts/import/codex-session",
                "status_code": 200,
            }) as upload,
        ):
            response = self.client.post("/api/codex/upload-sub2-bulk", json={"filenames": [filename]})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(0, body["uploaded_count"])
        self.assertEqual(1, body["failed_count"])
        self.assertIn("停用", body["failed"][0]["error"])
        upload.assert_not_called()

    def test_codex_management_bulk_uploads_selected_credentials(self):
        credential = json.dumps({
            "type": "codex",
            "email": "manage@example.com",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        })
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch("webui.app.db.read_codex_credential", return_value=(credential, "codex-manage@example.com-free.json")),
            patch("webui.app.db.mark_codex_exported") as mark_exported,
            patch("webui.app.db.mark_codex_sub2_uploaded") as mark_sub2_uploaded,
            patch("core.integrations.sub2api.client.upload_codex_oauth_credential", return_value={
                "ok": True,
                "url": "https://sub2.example/api/v1/admin/accounts/import/codex-session",
                "status_code": 200,
            }) as upload,
        ):
            response = self.client.post(
                "/api/codex/upload-sub2-bulk",
                json={"filenames": ["codex-manage@example.com-free.json"]},
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["uploaded_count"], 1)
        self.assertEqual(upload.call_args.args[0]["email"], "manage@example.com")
        mark_exported.assert_called_once_with("codex-manage@example.com-free.json")
        mark_sub2_uploaded.assert_called_once_with("codex-manage@example.com-free.json")

    def test_removed_agent_routes_are_not_registered(self):
        self.assertEqual(self.client.post("/api/accounts/codex-agent", json={"account_id": 23}).status_code, 404)
        self.assertEqual(self.client.post("/api/accounts/codex-agent-bulk", json={"account_ids": [23]}).status_code, 404)
        self.assertEqual(self.client.get("/api/accounts/23/codex-agent/download").status_code, 404)


if __name__ == "__main__":
    unittest.main()
