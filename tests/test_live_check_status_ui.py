# -*- coding: utf-8 -*-
from core import record_store
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class LiveCheckStatusUiTests(PostgresTestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def test_accounts_api_exposes_failed_probe_http_status(self):
        self.seed(record_store.ACCOUNTS, [{
            "email": "rejected@example.com",
            "access_token": "still-present",
            "token_expires_at": "2099-01-01T00:00:00Z",
            "token_expired": False,
            "live_check_status": "failed",
            "live_check_http_status": 401,
            "live_check_error": "现有 accessToken 已过期或失效，请点击“刷新AT”",
        }])

        response = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&q=rejected@example.com",
            headers=self.headers,
        )

        self.assertEqual(200, response.status_code)
        account = response.get_json()["items"][0]
        self.assertFalse(account["token_expired"])
        self.assertEqual("failed", account["live_check_status"])
        self.assertEqual(401, account["live_check_http_status"])

    def test_both_account_uis_render_clickable_token_states(self):
        for asset in ("modern/accounts.js", "legacy/accounts.js"):
            with self.subTest(asset=asset):
                response = self.client.get(f"/static/js/{asset}")
                try:
                    source = response.get_data(as_text=True)
                    self.assertIn("live_check_http_status", source)
                    self.assertIn("data-account-copy-secret=\"access_token\"", source)
                    self.assertIn("失效 ·", source)
                    self.assertIn("Token 到期：", source)
                finally:
                    response.close()

        modern = self.client.get("/static/js/modern/accounts.js")
        foundation = self.client.get("/static/css/ui-foundation.css")
        try:
            modern_source = modern.get_data(as_text=True)
            foundation_source = foundation.get_data(as_text=True)
            self.assertIn("acc-v2-token-state", modern_source)
            self.assertNotIn("acc-v2-token-alert", modern_source)
            self.assertIn(".accounts-table-v2 .acc-v2-token-state.is-normal", foundation_source)
            self.assertIn(".accounts-table-v2 .acc-v2-token-state.is-expired", foundation_source)
            self.assertIn(".accounts-table-v2 .acc-v2-token-state.is-invalid", foundation_source)
            for token_filter in ("'has'", "'expired'", "'invalid_401'", "'invalid_403'", "'invalid_other'", "'none'"):
                self.assertIn(token_filter, modern_source)
        finally:
            modern.close()
            foundation.close()

    def test_both_account_uis_render_account_status_as_a_separate_column(self):
        modern = self.client.get("/", headers=self.headers).get_data(as_text=True)
        legacy = self.client.get("/?ui=legacy", headers=self.headers).get_data(as_text=True)
        self.assertIn('data-column-filter="accountStatusFilterV2"', modern)
        self.assertIn(">账号状态</th>", modern)
        self.assertIn(">账号状态</th>", legacy)

        for asset in ("modern/accounts.js", "legacy/accounts.js"):
            with self.subTest(asset=asset):
                response = self.client.get(f"/static/js/{asset}")
                try:
                    source = response.get_data(as_text=True)
                    self.assertIn("accountStatus", source)
                    self.assertIn("已废号", source)
                finally:
                    response.close()
