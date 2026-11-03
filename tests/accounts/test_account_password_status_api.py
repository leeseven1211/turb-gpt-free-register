# -*- coding: utf-8 -*-
"""账号列表区分本地密码与已记录的远端密码结果。"""
from core.storage import records as rs
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountPasswordStatusApiTests(PostgresTestCase):
    def setUp(self):
        self.client = create_app(auth_code="password-status-test").test_client()
        self.headers = {"X-Auth-Code": "password-status-test"}

    def test_list_returns_recorded_password_result_without_credentials(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "recorded-password@example.test",
            "extra_json": {"account_password": "private-password"},
            "last_password_auth_status": "verified", "live_check_status": "failed",
            "live_check_error": "email_otp_failed", "last_auth_method": "password_email_otp",
        })
        response = self.client.get("/api/accounts?paged=1", headers=self.headers)
        self.assertEqual(200, response.status_code)
        account = next(row for row in response.get_json()["items"] if row["id"] == account_id)
        self.assertTrue(account["has_account_password"])
        self.assertEqual("verified", account.get("last_password_auth_status"))
        self.assertEqual("failed", account["live_check_status"])
        self.assertFalse(account["has_access_token"])
        self.assertNotIn("extra_json", account)
        self.assertNotIn("private-password", response.get_data(as_text=True))

    def test_legacy_saved_password_and_token_do_not_create_a_remote_result(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-password@example.test",
            "extra_json": {"account_password": "private-password"},
            "access_token": "private-token", "last_auth_method": "password",
        })
        response = self.client.get("/api/accounts?paged=1", headers=self.headers)
        self.assertEqual(200, response.status_code)
        account = next(row for row in response.get_json()["items"] if row["id"] == account_id)
        self.assertTrue(account["has_account_password"])
        self.assertTrue(account["has_access_token"])
        self.assertNotIn("last_password_auth_status", account)
        self.assertNotIn("private-password", response.get_data(as_text=True))
        self.assertNotIn("private-token", response.get_data(as_text=True))
