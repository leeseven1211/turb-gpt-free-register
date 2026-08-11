# -*- coding: utf-8 -*-
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from webui.app import create_app


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {
        "display_status": "partial_success" if row.get("status") == "failed" else row.get("status")
    })
    @patch("core.proxy_provider.registration_proxy_mode", return_value="1024")
    @patch("core.proxy_provider.active_proxy_leases", return_value=[{"provider": "1024proxy", "endpoint": "1.2.*.*:80"}])
    @patch("webui.app.db.codex_accounts_summary", return_value={"total": 2, "exported": 1, "pending": 1})
    @patch("webui.app.db.icloud_hide_email_pool_summary", return_value={"total": 4, "available": 3, "used": 1})
    @patch("webui.app.db.domain_email_pool_summary", return_value={"total": 3, "available": 2, "used": 1})
    @patch("webui.app.db.generic_api_email_pool_summary", return_value={"total": 2, "available": 2})
    @patch("webui.app.db.outlook_pool_summary", return_value={"total": 5, "available": 4, "used": 1})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 8, "status": "success", "email": "a@example.com", "created_at": datetime.now().isoformat()},
        {"id": 7, "status": "failed", "created_at": datetime.now().isoformat()},
    ])
    @patch("webui.app.db.list_accounts", return_value=[
        {"id": 1, "plan_type": "free", "codex_status": "success"},
        {"id": 2, "plan_type": "free", "plus_trial_eligible": True},
        {"id": 3, "plan_type": "plus", "archived": True},
    ])
    def test_dashboard_returns_aggregates_without_account_secrets(self, *_mocks):
        response = self.client.get("/api/dashboard", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["accounts"]["total"], 3)
        self.assertEqual(payload["accounts"]["active"], 2)
        self.assertEqual(payload["accounts"]["plans"], {"free": 1, "free_trial_eligible": 1})
        self.assertEqual(payload["email"]["local_available"], 11)
        self.assertEqual(payload["jobs"]["today_counts"], {"success": 1, "partial_success": 1, "failed": 0})
        self.assertEqual(payload["proxy"]["active_leases"], 1)
        self.assertEqual(payload["proxy"]["platform"], "1024")
        self.assertNotIn("access_token", str(payload))
        self.assertNotIn("api_key", str(payload).lower())

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 3, "status": "success"},
        {"id": 2, "status": "failed"},
        {"id": 1, "status": "failed"},
    ])
    def test_jobs_status_filter_keeps_global_counts(self, *_mocks):
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&status=failed",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 2)
        self.assertTrue(all(item["status"] == "failed" for item in payload["items"]))
        self.assertEqual(payload["status_counts"], {"success": 1, "failed": 2, "active": 0})

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 3, "status": "failed", "email": "target@example.com", "email_source": "email_butler"},
        {"id": 2, "status": "success", "email": "other@example.com", "email_source": "email_butler"},
        {"id": 1, "status": "failed", "email": "target@elsewhere.com", "email_source": "outlook"},
    ])
    def test_jobs_query_and_email_source_filters(self, *_mocks):
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&q=target&email_source=email_butler",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "target@example.com")
        self.assertEqual(payload["status_counts"], {"failed": 1, "active": 0})

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 3, "status": "success", "created_at": "2026-08-11T10:00:00"},
        {"id": 2, "status": "failed", "created_at": "2026-08-10T10:00:00"},
    ])
    def test_jobs_date_range_filter(self, *_mocks):
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&date_from=2026-08-11&date_to=2026-08-11",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], 3)

    def test_modern_ui_contains_overview_and_no_external_sidebar_links(self):
        response = self.client.get("/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="tab-overview"', html)
        self.assertIn('class="accounts-command-deck"', html)
        self.assertIn('id="butlerLeasePanel"', html)
        self.assertIn('data-module-subnav="register"', html)
        self.assertIn('data-module-subnav="codex"', html)
        self.assertIn('data-module-subnav="outlook"', html)
        self.assertIn('id="btnCodexUploadSub2V2"', html)
        self.assertNotIn('id="configOverviewV2"', html)
        self.assertIn("activateTab(localStorage.getItem('gpt_console_active_tab') || 'overview', false)", html)
        self.assertIn('id="jobDateFromV2"', html)
        self.assertIn('id="btnResetJobFiltersV2"', html)
        self.assertNotIn("TG 交流群", html)
        self.assertNotIn("切换老 UI", html)


class EmailButlerLeaseApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    @patch("core.email_butler_client.active_mailbox_leases", return_value=[{"email": "lease@example.com", "mailbox_id": "m-1"}])
    def test_list_leases(self, _active):
        response = self.client.get("/api/email-butler/leases", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["email"], "lease@example.com")

    @patch("core.email_butler_client.active_mailbox_leases", return_value=[{"email": "lease@example.com", "mailbox_id": "m-1"}])
    @patch("core.email_butler_client.pick_account", return_value=SimpleNamespace(email="lease@example.com", mailbox_id="m-1"))
    def test_create_lease(self, _pick, _active):
        response = self.client.post("/api/email-butler/leases", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["mailbox_id"], "m-1")

    @patch("core.email_butler_client.release_account")
    @patch("core.email_butler_client.get_account_context", return_value=SimpleNamespace(email="lease@example.com"))
    def test_release_lease(self, _context, release):
        response = self.client.post(
            "/api/email-butler/leases/release",
            json={"email": "lease@example.com", "status": "available"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        release.assert_called_once_with("lease@example.com", status="available", note="WebUI 手动释放")

    def test_release_rejects_invalid_email(self):
        response = self.client.post(
            "/api/email-butler/leases/release",
            json={"email": "not-an-email"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
