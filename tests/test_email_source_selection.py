# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import email as email_config
from core import email_provider
from webui.app import create_app


class EmailSourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    def test_single_source_validation_rejects_empty_and_multiple_values(self):
        with self.assertRaisesRegex(ValueError, "请选择"):
            email_provider.validate_email_source("")
        with self.assertRaisesRegex(ValueError, "只能明确选择一个"):
            email_provider.validate_email_source("email_butler,icloud_hide")

    def test_explicit_acquire_does_not_fall_back_to_another_source(self):
        with patch.object(
            email_provider,
            "_pick_from_source",
            side_effect=RuntimeError("butler unavailable"),
        ) as pick:
            with self.assertRaisesRegex(RuntimeError, "所选邮箱来源 email_butler 领取失败"):
                email_provider.acquire_email("email_butler")

        pick.assert_called_once_with("email_butler")

    def test_email_sources_endpoint_returns_enabled_choices_without_default_selection(self):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True), patch.object(
            email_config, "EMAIL_SOURCE", "email_butler,icloud_hide"
        ):
            response = self.client.get("/api/email-sources")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["sources"],
            [
                {"value": "email_butler", "label": "Email Butler"},
                {"value": "icloud_hide", "label": "iCloud 隐藏邮箱"},
            ],
        )

    @patch("webui.app.svc.submit_registration")
    def test_jobs_require_explicit_source_in_automatic_mode(self, submit_registration):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True), patch.object(
            email_config, "EMAIL_SOURCE", "email_butler,icloud_hide"
        ):
            response = self.client.post("/api/jobs", json={"count": 1, "workers": 1})

        self.assertEqual(response.status_code, 400)
        self.assertIn("请选择本次注册使用的邮箱来源", response.get_json()["error"])
        submit_registration.assert_not_called()

    @patch("core.icloud_hme_client.sync_aliases")
    @patch("webui.app.svc.submit_registration", return_value=[{"id": 123}])
    def test_jobs_submit_only_the_selected_enabled_source(self, submit_registration, sync_aliases):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True), patch.object(
            email_config, "EMAIL_SOURCE", "email_butler,icloud_hide"
        ), patch.object(
            email_config, "EMAIL_BUTLER_API_BASE", "https://mail.example.com/v1"
        ), patch.object(email_config, "EMAIL_BUTLER_API_KEY", "secret"):
            response = self.client.post(
                "/api/jobs",
                json={"count": 1, "workers": 2, "email_source": "email_butler"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["email_source"], "email_butler")
        submit_registration.assert_called_once_with(
            count=1,
            email_source="email_butler",
            workers=2,
        )
        sync_aliases.assert_not_called()


if __name__ == "__main__":
    unittest.main()
