# -*- coding: utf-8 -*-
import tempfile
import unittest
from unittest.mock import patch

from core import db, deactivation_mail_service
from core.record_store import ACCOUNTS
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class DeactivationMailTests(PostgresTestCase):
    def test_detected_mail_is_durable_and_empty_rescan_does_not_clear_it(self):
        self.seed(ACCOUNTS, [
            {"id": 1, "email": "a@test.com", "email_source": "email_butler"},
        ])
        db.update_account_deactivation_mail(1, {
            "status": "success",
            "detected": True,
            "subject": "Deactivated",
            "sender": "noreply@openai.com",
            "received_at": "2026-08-06T09:00:00Z",
        })
        db.update_account_deactivation_mail(1, {"status": "success", "detected": False})
        row = db.get_account(1)
        self.assertTrue(row["deactivation_mail_detected"])
        self.assertEqual(row["deactivation_mail_subject"], "Deactivated")

    def test_manual_endpoint_queues_without_access_token(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        # 显式声明特性可用：否则这个用例只在"开发机 .env 恰好配了 Email Butler"
        # 时才通过，换台机器或 CI 上会因 503 失败。
        with patch("core.feature_availability.require_feature", return_value=(True, "")), \
             patch.object(
            deactivation_mail_service,
            "enqueue",
            return_value={"accepted": True, "account_id": 7},
        ), patch.object(
            deactivation_mail_service,
            "queue_settings",
            return_value={"enabled": True},
        ):
            response = client.post("/api/accounts/7/check-deactivation-mail")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.get_json()["ok"])

    def test_account_management_ui_has_mail_scan_controls(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        html = client.get("/", headers={"X-Auth-Code": "test-auth"}).get_data(as_text=True)
        response = client.get("/static/js/modern/accounts.js")
        try:
            self.assertEqual(response.status_code, 200)
            html += "\n" + response.get_data(as_text=True)
        finally:
            response.close()
        self.assertIn('class="col-risk-mail column-filter-header"', html)
        self.assertIn('data-column-filter="accountRiskFilterV2"', html)
        self.assertIn("data-deactivation-mail-check", html)
        self.assertIn("btnCheckSelectedDeactivationMailV2", html)

    def test_icloud_hide_is_supported_by_mail_scanner(self):
        self.assertIn("icloud_hide", deactivation_mail_service._SUPPORTED_SOURCES)


if __name__ == "__main__":
    unittest.main()
