# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from core import feature_availability
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class FeatureAvailabilityTests(PostgresTestCase):
    def test_account_features_disabled_when_1024_api_missing(self):
        with (
            patch("core.account_proxy.registration_proxy_mode", return_value="1024"),
            patch.multiple(
                "config.proxy",
                ACCOUNT_ACTION_PROXY_MODE="registration",
                PROXY_1024_API_URL="",
                PROXY_1024_VALIDATE=True,
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
