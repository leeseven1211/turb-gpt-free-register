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

    def test_invalid_configuration_disables_source_and_rejects_job_before_submission(self):
        for key, value in (
            ("REMAIL_API_BASE", ""),
            ("REMAIL_API_KEY", ""),
            ("REMAIL_PROJECT_ID", 0),
            ("REMAIL_EMAIL_SUFFIX", ""),
            ("REMAIL_SERVICE_MODE", "unknown"),
            ("REMAIL_SUPPLY_POLICY", "unknown"),
        ):
            with self.subTest(key=key), patch.object(email_config, key, value), patch(
                "webui.app.svc.submit_registration"
            ) as submit:
                sources_response = self.client.get("/api/email-sources")
                self.assertEqual(sources_response.status_code, 200)
                source = sources_response.get_json()["sources"][0]
                self.assertEqual(source["value"], "remail")
                self.assertFalse(source["enabled"])
                self.assertTrue(source["reason"])
                self.assertNotIn("fixture-remail-key", source["reason"])

                response = self.client.post(
                    "/api/jobs", json={"count": 1, "workers": 1, "email_source": "remail"}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], source["reason"])
                submit.assert_not_called()

    def test_configured_source_is_available_in_selected_order_without_remote_request(self):
        with patch.object(email_config, "EMAIL_SOURCE", "gptmail,remail"):
            response = self.client.get("/api/email-sources")

        self.assertEqual(response.status_code, 200)
        sources = response.get_json()["sources"]
        self.assertEqual([source["value"] for source in sources], ["gptmail", "remail"])
        self.assertEqual(sources[1], {"value": "remail", "label": "Remail", "enabled": True, "reason": ""})
        self.assertNotIn("fixture-remail-key", response.get_data(as_text=True))

    def test_jobs_with_valid_remail_configuration_do_not_check_outlook_pool(self):
        with patch("webui.app.svc.submit_registration", return_value=[{"id": 1}]) as submit, patch(
            "webui.app.db.outlook_pool_summary"
        ) as outlook_pool:
            response = self.client.post(
                "/api/jobs", json={"count": 2, "workers": 2, "email_source": "remail"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["warning"], "")
        self.assertEqual(response.get_json()["email_source"], "remail")
        outlook_pool.assert_not_called()
        submit.assert_called_once_with(count=2, workers=2, email_source="remail")

    def test_unconfigured_remail_source_is_rejected_even_with_valid_credentials(self):
        with patch.object(email_config, "EMAIL_SOURCE", "outlook"), patch(
            "webui.app.svc.submit_registration"
        ) as submit:
            response = self.client.post(
                "/api/jobs", json={"count": 1, "workers": 1, "email_source": "remail"}
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("未在配置页 EMAIL_SOURCE 中启用", response.get_json()["error"])
        submit.assert_not_called()

    def test_summary_does_not_count_remail_as_outlook_pool(self):
        with patch("webui.app.db.outlook_pool_summary") as outlook_pool:
            response = self.client.get("/api/summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["outlook_total"], 0)
        self.assertEqual(response.get_json()["outlook_available"], 0)
        outlook_pool.assert_not_called()

    def test_dashboard_exposes_remail_as_on_demand_without_local_capacity(self):
        response = self.client.get("/api/dashboard")

        self.assertEqual(response.status_code, 200)
        email_summary = response.get_json()["email"]
        remail = next(source for source in email_summary["sources"] if source["source"] == "remail")
        self.assertEqual(remail, {
            "source": "remail", "label": "Remail", "kind": "on_demand", "enabled": True,
            "default_visible": True, "dependency": False, "dependency_reason": "",
            "history_available": False,
        })
        self.assertEqual(email_summary["local_total"], 0)
        self.assertEqual(email_summary["local_available"], 0)
        self.assertNotIn("fixture-remail-key", response.get_data(as_text=True))
