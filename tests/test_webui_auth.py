# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from webui.app import create_app
from tests.support_pg import PostgresTestCase


class WebUiAuthTests(PostgresTestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()

    def test_api_requires_auth_code(self):
        r = self.client.get("/api/summary")
        self.assertEqual(r.status_code, 401)
        self.assertIn("未授权", r.get_json()["error"])

    def test_api_accepts_auth_header(self):
        r = self.client.get("/api/summary", headers={"X-Auth-Code": "test-auth"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("accounts", r.get_json())


    def test_query_auth_code_is_not_accepted(self):
        r = self.client.get("/api/summary?auth_code=test-auth")
        self.assertEqual(r.status_code, 401)

    def test_json_body_auth_code_is_not_accepted(self):
        r = self.client.post("/api/jobs/cancel-pending", json={"auth_code": "test-auth"})
        self.assertEqual(r.status_code, 401)

    def test_login_remember_sets_persistent_session(self):
        r = self.client.post("/login", data={"auth_code": "test-auth", "next": "/", "remember": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("Expires=", r.headers.get("Set-Cookie") or "")

    def test_login_sets_session_cookie(self):
        r = self.client.post("/login", data={"auth_code": "test-auth", "next": "/"})
        self.assertEqual(r.status_code, 302)
        r = self.client.get("/api/summary")
        self.assertEqual(r.status_code, 200)

    def test_favicon_is_public(self):
        r = self.client.get("/favicon.ico")
        self.assertEqual(r.status_code, 308)
        self.assertIn("/static/favicon.svg", r.headers.get("Location") or "")

        r = self.client.get("/static/favicon.svg")
        try:
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.mimetype, "image/svg+xml")
        finally:
            r.close()

    @patch("core.proxy_provider.release_proxy")
    @patch("core.proxy_provider.acquire_1024_proxy")
    def test_proxy_provider_test_endpoint(self, acquire, release):
        lease = SimpleNamespace(public_dict=lambda: {
            "provider": "1024proxy",
            "endpoint": "1.2.*.*:8080",
            "exit_ip": "8.8.*.*",
            "region": "US",
            "state": "leased",
        })
        acquire.return_value = lease
        r = self.client.post(
            "/api/proxy-provider/test",
            json={
                "api_url": "https://white.1024proxy.com/white/api?num=1&time=10",
                "protocol": "http",
                "session_minutes": 30,
                "validate": True,
            },
            headers={"X-Auth-Code": "test-auth"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
        acquire.assert_called_once()
        release.assert_called_once_with(lease, reason="webui_test")

    @patch("core.icloud_hme_client.test_connection")
    def test_icloud_hme_test_endpoint(self, test_connection):
        test_connection.return_value = {
            "account_id": "acc-1",
            "remote_aliases": 67,
            "remote_active": 67,
            "inbox_method": "imap",
            "pool": {"available": 67, "used": 0, "total": 67},
            "sync": {"inserted": 67, "updated": 0},
        }
        r = self.client.post(
            "/api/icloud-hme/test",
            json={"api_base": "http://127.0.0.1:8081", "account_id": "acc-1", "timeout": 35},
            headers={"X-Auth-Code": "test-auth"},
        )
        self.assertEqual(r.status_code, 200)
        payload = r.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["remote_aliases"], 67)
        self.assertEqual(payload["inbox_method"], "imap")
        test_connection.assert_called_once_with(
            api_base="http://127.0.0.1:8081", account_id="acc-1", timeout=35
        )


if __name__ == "__main__":
    unittest.main()
