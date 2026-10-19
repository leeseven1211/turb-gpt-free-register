# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from core import feature_availability
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class FeatureAvailabilityTests(PostgresTestCase):
    def test_open_source_registration_driver_does_not_require_roxy_configuration(self):
        with patch("config.roxybrowser.REGISTRATION_DRIVER", "protocol_oss"):
            result = feature_availability._registration_driver_status()

        self.assertTrue(result["enabled"])
        self.assertEqual(result["driver"], "protocol_oss")
        self.assertEqual(result["reason"], "")

    def test_open_source_roxy_requires_the_same_browser_configuration(self):
        for configured in (False, True):
            with self.subTest(configured=configured), patch.multiple(
                "config.roxybrowser",
                REGISTRATION_DRIVER="roxy_oss",
                ROXY_API_BASE="http://127.0.0.1:50000" if configured else "",
                ROXY_API_TOKEN="test-token" if configured else "",
                ROXY_WORKSPACE_ID="test-workspace" if configured else "",
            ):
                result = feature_availability._registration_driver_status()

            self.assertEqual(result["enabled"], configured)
            self.assertEqual(result["driver"], "roxy_oss")
            if not configured:
                self.assertIn("ROXY_API_BASE", result["reason"])

    def test_codex_following_open_source_roxy_requires_browser_configuration(self):
        with patch.multiple(
            "config.roxybrowser",
            REGISTRATION_DRIVER="roxy_oss",
            ROXY_API_BASE="",
            ROXY_API_TOKEN="",
            ROXY_WORKSPACE_ID="",
        ), patch("config.codex.CODEX_OAUTH_DRIVER", "same_as_registration"):
            result = feature_availability._codex_retry_status()

        self.assertFalse(result["enabled"])
        self.assertIn("ROXY_API_BASE", result["reason"])

    def test_icloud_hide_allows_dynamic_account_discovery_without_account_id(self):
        with (
            patch.multiple(
                "config.email",
                EMAIL_SOURCE="icloud_hide",
                ICLOUD_HME_API_BASE="http://127.0.0.1:8081",
                ICLOUD_HME_ACCOUNT_ID="",
                ICLOUD_HME_AUTO_CREATE=True,
            ),
            patch("core.db.outlook_pool_summary", return_value={"available": 0}),
            patch("core.db.generic_api_email_pool_summary", return_value={"available": 0}),
        ):
            result = feature_availability.feature_availability()

        self.assertTrue(result["email_sources"]["icloud_hide"]["enabled"])
        self.assertEqual(result["email_sources"]["icloud_hide"]["reason"], "")

    def test_icloud_hide_requires_local_inventory_when_auto_create_is_disabled(self):
        with (
            patch.multiple(
                "config.email",
                EMAIL_SOURCE="icloud_hide",
                ICLOUD_HME_API_BASE="http://127.0.0.1:8081",
                ICLOUD_HME_ACCOUNT_ID="",
                ICLOUD_HME_AUTO_CREATE=False,
            ),
            patch("core.db.outlook_pool_summary", return_value={"available": 0}),
            patch("core.db.generic_api_email_pool_summary", return_value={"available": 0}),
            patch("core.db.icloud_hide_email_pool_summary", return_value={"available": 0}),
        ):
            result = feature_availability.feature_availability()

        self.assertFalse(result["email_sources"]["icloud_hide"]["enabled"])
        self.assertIn("库存", result["email_sources"]["icloud_hide"]["reason"])

    def test_account_features_disabled_when_1024_api_missing(self):
        with (
            patch("core.account_proxy.registration_proxy_mode", return_value="1024"),
            patch.multiple(
                "config.proxy",
                ACCOUNT_ACTION_PROXY_MODE="registration",
                PROXY_1024_API_URL="",
                PROXY_1024_VALIDATE=True,
            ),
            patch.multiple(
                "config.account",
                ACCOUNT_PLAN_CHECK_PROXY_MODE="registration",
                ACCOUNT_LIVE_CHECK_PROXY_MODE="registration",
            ),
        ):
            result = feature_availability.feature_availability()
        self.assertFalse(result["features"]["plan_check"]["enabled"])
        self.assertFalse(result["features"]["live_check"]["enabled"])
        self.assertIn("1024Proxy", result["features"]["plan_check"]["reason"])

    def test_extract_link_requires_base_and_cdk(self):
        with patch.multiple("config.extract_link", EXTRACT_LINK_API_BASE="", EXTRACT_LINK_CDK=""):
            result = feature_availability.feature_availability()
        self.assertFalse(result["features"]["extract_link"]["enabled"])
        self.assertIn("EXTRACT_LINK_API_BASE", result["features"]["extract_link"]["reason"])

    def test_capabilities_endpoint_and_backend_guard(self):
        client = create_app(auth_code="test-auth").test_client()
        headers = {"X-Auth-Code": "test-auth"}
        response = client.get("/api/capabilities", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("features", response.get_json())

        with patch("core.feature_availability.require_feature", return_value=(False, "测试缺少配置")):
            blocked = client.post("/api/accounts/check-plan", json={"account_id": 1}, headers=headers)
        self.assertEqual(blocked.status_code, 503)
        self.assertEqual(blocked.get_json()["error"], "测试缺少配置")


if __name__ == "__main__":
    unittest.main()
