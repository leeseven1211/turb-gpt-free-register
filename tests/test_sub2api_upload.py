# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import Mock, patch

from core.sub2api_client import upload_codex_oauth_credential
from webui.app import create_app


class Sub2ApiUploadTests(unittest.TestCase):
    @patch("core.sub2api_client.requests.post")
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

    @patch("core.sub2api_client.requests.post")
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


class Sub2ApiWebUploadTests(unittest.TestCase):
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
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch("webui.app.db.get_account", return_value=account),
            patch("webui.app.db.list_codex_accounts", return_value=[{
                "email": "codex@example.com",
                "filename": "codex-codex@example.com-free.json",
            }]),
            patch("webui.app.db.read_codex_credential", return_value=(credential, "codex-codex@example.com-free.json")),
            patch("webui.app.db.mark_codex_exported") as mark_exported,
            patch("webui.app.db.mark_codex_sub2_uploaded") as mark_sub2_uploaded,
            patch("core.sub2api_client.upload_codex_oauth_credential", return_value={
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

    def test_codex_management_bulk_uploads_selected_credentials(self):
        credential = json.dumps({
            "type": "codex",
            "email": "manage@example.com",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        })
        with (
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch("webui.app.db.read_codex_credential", return_value=(credential, "codex-manage@example.com-free.json")),
            patch("webui.app.db.mark_codex_exported") as mark_exported,
            patch("webui.app.db.mark_codex_sub2_uploaded") as mark_sub2_uploaded,
            patch("core.sub2api_client.upload_codex_oauth_credential", return_value={
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
