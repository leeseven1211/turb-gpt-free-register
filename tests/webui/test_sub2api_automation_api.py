"""Sub2API 自动化接口沿用授权校验，不接收草稿凭据。"""
import unittest
from unittest.mock import patch

from webui.app import create_app


class Sub2ApiAutomationApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def test_status_requires_login_and_returns_only_service_summary(self):
        self.assertEqual(401, self.client.get("/api/sub2api/automation").status_code)
        with patch("core.integrations.sub2api.monitor.status", return_value={"enabled": False}), patch(
            "core.integrations.sub2api.jobs.status", return_value={"pending": 2}
        ):
            response = self.client.get("/api/sub2api/automation", headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "monitor": {"enabled": False}, "sync": {"pending": 2}}, response.json)

    def test_manual_check_uses_saved_configuration(self):
        with patch("core.integrations.sub2api.monitor.run_once", return_value={"sync_queued": 1}) as check:
            response = self.client.post("/api/sub2api/automation/check", headers=self.headers, json={})
        self.assertEqual(200, response.status_code)
        check.assert_called_once_with(force=True)
        with patch("core.integrations.sub2api.monitor.run_once") as check:
            response = self.client.post("/api/sub2api/automation/check", headers=self.headers, json={"api_key": "draft"})
        self.assertEqual(400, response.status_code)
        check.assert_not_called()

    def test_manual_check_exposes_classified_scan_failure(self):
        with patch("core.integrations.sub2api.monitor.run_once", return_value={"reasons": {"remote_scan_failed": 1}}):
            response = self.client.post("/api/sub2api/automation/check", headers=self.headers, json={})
        self.assertEqual(503, response.status_code)
        self.assertFalse(response.json["ok"])
        self.assertEqual("remote_scan_failed", response.json["error_code"])
