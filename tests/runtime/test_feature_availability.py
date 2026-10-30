# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from core.runtime import capabilities as feature_availability
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class FeatureAvailabilityTests(PostgresTestCase):
    def test_retired_management_capabilities_are_disabled(self):
        result = feature_availability.feature_availability()
        for name in ('cloudmail_token', 'cloudmail_domains', 'icloud_hme'):
            self.assertFalse(result['features'][name]['enabled'])
            self.assertIn('邮箱服务', result['features'][name]['reason'])
    def test_existing_mailbox_scan_does_not_require_unused_inventory(self):
        empty = {name: {'enabled': False, 'available': 0} for name in
                 ('email_butler', 'cloudflare', 'icloud_hide')}
        with patch.object(feature_availability, '_email_source_features', return_value=empty), patch.multiple(
            'config.email', EMAIL_BUTLER_API_BASE='https://butler.example/v1',
            EMAIL_BUTLER_API_KEY='test-key', ICLOUD_HME_API_BASE='',
        ):
            result = feature_availability.feature_availability()
        self.assertTrue(result['features']['deactivation_mail']['enabled'])
        self.assertFalse(any(row['enabled'] for row in result['email_sources'].values()))

    def test_fixed_read_profile_keeps_historical_scan_available(self):
        from core.storage import records as record_store
        record_store.insert_row(record_store.EMAIL_INBOX_PROFILES, {
            'inbox_key': 'historical-only', 'connector': 'forward_butler',
            'credential_ref': 'HISTORICAL_READ_TEST_KEY', 'revision': 1, 'state': 'active',
            'inbox_locator': {'api_base': 'https://old.example/v1', 'mailbox_email': 'final@example.test'},
        })
        with patch.object(feature_availability, '_email_source_features', return_value={}), patch.multiple(
            'config.email', EMAIL_BUTLER_API_BASE='', EMAIL_BUTLER_API_KEY='',
            CLOUDFLARE_API_BASE='', ICLOUD_HME_API_BASE='',
        ), patch.dict('os.environ', {'HISTORICAL_READ_TEST_KEY': 'test-key'}):
            result = feature_availability.feature_availability()
        self.assertTrue(result['features']['deactivation_mail']['enabled'])

    def test_open_source_registration_driver_does_not_require_roxy_configuration(self):
        for driver in ("protocol_oss", "protocol_oss_2"):
            with self.subTest(driver=driver), patch("config.roxybrowser.REGISTRATION_DRIVER", driver):
                result = feature_availability._registration_driver_status()
            self.assertTrue(result["enabled"])
            self.assertEqual(result["driver"], driver)
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

    def test_icloud_auto_create_cannot_make_empty_local_stock_available(self):
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

        self.assertFalse(result["email_sources"]["icloud_hide"]["enabled"])
        self.assertIn("导入", result["email_sources"]["icloud_hide"]["reason"])

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
            patch("core.proxy.account_routes.registration_proxy_mode", return_value="1024"),
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

        with patch("core.runtime.capabilities.require_feature", return_value=(False, "测试缺少配置")):
            blocked = client.post("/api/accounts/check-plan", json={"account_id": 1}, headers=headers)
        self.assertEqual(blocked.status_code, 503)
        self.assertEqual(blocked.get_json()["error"], "测试缺少配置")


if __name__ == "__main__":
    unittest.main()
