# -*- coding: utf-8 -*-
"""显式解封入口只解除本地停用，不绕过认证或宣称凭证有效。"""
from unittest import TestCase
from unittest.mock import patch

from webui.app import create_app


class AccountReactivationApiTests(TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.headers = {"X-Auth-Code": "test-auth"}
        self.url = "/api/accounts/7/restore"
        self.payload = {"reason": "已收到 OpenAI 恢复访问通知"}

    def test_restore_requires_authentication(self):
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(401, response.status_code)

    def test_restore_requires_explicit_nonempty_reason(self):
        for payload in ({}, {"reason": " "}, {"reason": True}, {"reason": "解" * 301}, []):
            with self.subTest(payload=payload), patch(
                "webui.routes.accounts.db.restore_account_after_deactivation", create=True,
            ) as restore:
                response = self.client.post(self.url, json=payload, headers=self.headers)
                self.assertEqual(400, response.status_code)
                restore.assert_not_called()

    def test_restore_uses_dedicated_storage_command(self):
        with patch(
            "webui.routes.accounts.db.restore_account_after_deactivation",
            return_value=True, create=True,
        ) as restore:
            response = self.client.post(self.url, json=self.payload, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.get_json()["ok"])
        self.assertIn("重新验证", response.get_json()["message"])
        restore.assert_called_once_with(7, reason=self.payload["reason"])

    def test_missing_account_is_not_reported_as_restored(self):
        with patch(
            "webui.routes.accounts.db.restore_account_after_deactivation",
            return_value=False, create=True,
        ):
            response = self.client.post(self.url, json=self.payload, headers=self.headers)
        self.assertEqual(404, response.status_code)
        self.assertFalse(response.get_json()["ok"])

    def test_busy_account_returns_conflict(self):
        with patch(
            "webui.routes.accounts.db.restore_account_after_deactivation",
            side_effect=ValueError("该账号仍有操作进行中，请稍后重试"), create=True,
        ):
            response = self.client.post(self.url, json=self.payload, headers=self.headers)
        self.assertEqual(409, response.status_code)
        self.assertIn("操作进行中", response.get_json()["error"])

    def test_restored_credential_requires_reauthorization_before_upload(self):
        filename = "codex-restored@example.test-free.json"
        row = {
            "filename": filename, "email": "restored@example.test",
            "oauth_account_status": "active", "oauth_status": "valid",
            "oauth_refresh_error": "account_restored_reauth_required: 解封后需重新授权",
        }
        with (
            patch("webui.routes.accounts._feature_unavailable", return_value=None),
            patch("webui.routes.accounts.db.list_codex_accounts", return_value=[row]),
            patch("webui.routes.accounts.db.get_account_by_email", return_value={"account_status": "active"}),
            patch("webui.routes.accounts.db.read_codex_credential") as read,
        ):
            response = self.client.post(
                "/api/codex/upload-sub2-bulk", json={"filenames": [filename]}, headers=self.headers,
            )
        result = response.get_json()
        self.assertEqual(0, result["uploaded_count"])
        self.assertEqual(1, result["failed_count"])
        self.assertIn("重新授权", result["failed"][0]["error"])
        read.assert_not_called()
