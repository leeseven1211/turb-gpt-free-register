# -*- coding: utf-8 -*-
"""Remail 来源的提交、配置可用性与总览展示契约。"""
from unittest.mock import patch

from config import email as email_config
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class RemailWebUiTests(PostgresTestCase):
    def setUp(self):
        configuration = patch.multiple(
            email_config,
            USE_EMAIL_SERVICE=True,
            EMAIL_SOURCE="remail",
            REMAIL_API_BASE="https://remail.example.test",
            REMAIL_API_KEY="fixture-remail-key",
            REMAIL_PROJECT_ID=2,
            REMAIL_EMAIL_SUFFIX="outlook.com",
            REMAIL_SERVICE_MODE="purchase",
            REMAIL_SUPPLY_POLICY="public_only",
        )
        configuration.start()
        self.addCleanup(configuration.stop)
        no_network = patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("配置检查和任务提交不能调用远端 Remail 服务"),
        )
        no_network.start()
        self.addCleanup(no_network.stop)
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    def test_historical_configuration_cannot_reenable_remail_registration(self):
        for key, value in (("REMAIL_API_BASE", ""), ("REMAIL_API_KEY", ""),
                           ("REMAIL_PROJECT_ID", 0), ("REMAIL_EMAIL_SUFFIX", ""),
                           ("REMAIL_SERVICE_MODE", "unknown"), ("REMAIL_SUPPLY_POLICY", "unknown")):
            with self.subTest(key=key), patch.object(email_config, key, value), patch(
                "webui.app.svc.submit_registration"
            ) as submit:
                sources_response = self.client.get("/api/email-sources")
                self.assertEqual(sources_response.status_code, 200)
                sources = sources_response.get_json()["sources"]
                self.assertNotIn("remail", [source["value"] for source in sources])
                self.assertNotIn("fixture-remail-key", sources_response.get_data(as_text=True))
                response = self.client.post("/api/jobs", json={"count": 1, "workers": 1, "email_source": "remail"})
                self.assertEqual(response.status_code, 400)
                self.assertIn("新注册只使用本地邮箱列表", response.get_json()["error"])
                submit.assert_not_called()

    def test_legacy_source_config_does_not_replace_local_inventory_choices(self):
        with patch.object(email_config, "EMAIL_SOURCE", "gptmail,remail"):
            response = self.client.get("/api/email-sources")
        self.assertEqual(response.status_code, 200)
        sources = response.get_json()["sources"]
        self.assertEqual([source["value"] for source in sources],
                         ["outlook", "generic_api", "cloudflare_domain", "icloud_hide", "email_butler"])
        self.assertTrue(all(not source["enabled"] for source in sources))
        self.assertNotIn("fixture-remail-key", response.get_data(as_text=True))

    def test_valid_remail_configuration_still_rejects_new_jobs_without_inventory_reads(self):
        with patch("webui.app.svc.submit_registration") as submit, patch(
            "core.email.inventory.summary", side_effect=AssertionError("拒绝来源后不能查询库存")
        ) as inventory:
            response = self.client.post("/api/jobs", json={"count": 2, "workers": 2, "email_source": "remail"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("新注册只使用本地邮箱列表", response.get_json()["error"])
        inventory.assert_not_called()
        submit.assert_not_called()

    def test_unconfigured_remail_source_is_rejected_even_with_valid_credentials(self):
        with patch.object(email_config, "EMAIL_SOURCE", "outlook"), patch(
            "webui.app.svc.submit_registration"
        ) as submit:
            response = self.client.post(
                "/api/jobs", json={"count": 1, "workers": 1, "email_source": "remail"}
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("新注册只使用本地邮箱列表", response.get_json()["error"])
        submit.assert_not_called()

    def test_summary_does_not_count_remail_as_outlook_pool(self):
        with patch("webui.app.db.outlook_pool_summary") as outlook_pool:
            response = self.client.get("/api/summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["outlook_total"], 0)
        self.assertEqual(response.get_json()["outlook_available"], 0)
        outlook_pool.assert_not_called()

    def test_dashboard_excludes_retired_remail_from_local_capacity(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        email_summary = response.get_json()["email"]
        self.assertNotIn("remail", [source["source"] for source in email_summary["sources"]])
        self.assertTrue(all(source["kind"] == "local_pool" for source in email_summary["sources"]))
        self.assertEqual(email_summary["local_total"], 0)
        self.assertEqual(email_summary["local_available"], 0)
        self.assertNotIn("fixture-remail-key", response.get_data(as_text=True))
