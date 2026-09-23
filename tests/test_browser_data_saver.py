import unittest
from unittest.mock import patch
from types import SimpleNamespace

from core.browser_data_saver import BrowserDataSaver, configured_resource_types
from core.browser_traffic import _SummaryOnlyCDPSession
from core.roxybrowser_client import _apply_data_saver_open_args
from config.schema import CONFIG_SCHEMA, resolve_field, validate_value
from core.browser_flow_policy import (
    AUTH_SAFE_URL_PATTERNS,
    flow_enabled,
    install_for_flow,
    opening_resource_types,
)


class _Driver:
    def __init__(self):
        self.commands = []

    def execute_cdp_cmd(self, command, params):
        self.commands.append((command, params))
        return {}


class _Capture:
    def __init__(self):
        self.data_saver = None

    def set_data_saver(self, data_saver):
        self.data_saver = data_saver


class BrowserDataSaverTests(unittest.TestCase):
    def test_disabled_mode_is_a_noop(self):
        driver = _Driver()
        with patch("core.browser_data_saver._cfg.BROWSER_DATA_SAVER_MODE", False):
            saver = BrowserDataSaver(label="test")
            saver.install_selenium(driver)
        self.assertEqual(driver.commands, [])
        self.assertEqual(saver.snapshot()["data_saver_blocked_count"], 0)

    def test_selenium_blocks_optional_extensions_and_configured_urls(self):
        driver = _Driver()
        with patch("core.browser_data_saver._cfg.BROWSER_DATA_SAVER_MODE", True), patch(
            "core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["image", "media"]
        ), patch(
            "core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS", ["**://metrics.example/**"]
        ):
            saver = BrowserDataSaver(label="test")
            saver.install_selenium(driver)
        self.assertEqual(driver.commands[0][0], "Network.enable")
        patterns = driver.commands[1][1]["urls"]
        self.assertIn("*.png*", patterns)
        self.assertIn("*.mp4*", patterns)
        self.assertIn("*://metrics.example/*", patterns)
        self.assertNotIn("*.js*", patterns)

    def test_post_auth_adds_spa_rules_without_replacing_optional_rules(self):
        driver = _Driver()
        with patch("core.browser_data_saver._cfg.BROWSER_DATA_SAVER_MODE", True), patch(
            "core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["image"]
        ), patch(
            "core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS", ["**://metrics.example/**"]
        ):
            saver = BrowserDataSaver(label="test")
            saver.install_selenium(driver)
            self.assertTrue(saver.activate_post_auth())
            self.assertFalse(saver.activate_post_auth())
        patterns = driver.commands[-1][1]["urls"]
        self.assertIn("*.png*", patterns)
        self.assertIn("*://metrics.example/*", patterns)
        self.assertIn("*://chatgpt.com/cdn/assets/*", patterns)
        self.assertIn("*://auth-cdn.oaistatic.com/assets/*", patterns)
        self.assertTrue(saver.snapshot()["data_saver_post_auth_activated"])

    def test_inspector_block_is_counted_only_for_installed_rule(self):
        driver = _Driver()
        blocked_request = {"url": "https://cdn.example/a.png", "resource_type": "Image"}
        with patch("core.browser_data_saver._cfg.BROWSER_DATA_SAVER_MODE", True), patch(
            "core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["image"]
        ), patch("core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS", []):
            saver = BrowserDataSaver(label="test")
            saver.install_selenium(driver)
            self.assertTrue(saver.observe_cdp_event(
                "Network.loadingFailed", {"blockedReason": "inspector"},
                blocked_request,
            ))
            self.assertFalse(saver.observe_cdp_event(
                "Network.loadingFailed", {"blockedReason": "inspector"},
                {"url": "https://cdn.example/app.js", "resource_type": "Script"},
            ))
        self.assertTrue(blocked_request["_data_saver_blocked"])
        self.assertEqual(saver.snapshot()["data_saver_blocked_by_type"], {"image": 1})

    def test_open_args_disable_images_only_when_selected(self):
        params = {"args": ["--lang=ja"]}
        with patch("config.browser.BROWSER_DATA_SAVER_MODE", True), patch(
            "config.browser.BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["image", "media", "font"]
        ):
            _apply_data_saver_open_args(params)
        self.assertIn("--blink-settings=imagesEnabled=false", params["args"])
        self.assertIn("--disable-remote-fonts", params["args"])

    def test_resource_type_aliases_are_normalized(self):
        with patch("core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["images", "font", "invalid", "image"]):
            self.assertEqual(configured_resource_types(), ["image", "font"])

    def test_explicit_constructor_configuration_overrides_runtime_config(self):
        with patch("core.browser_data_saver._cfg.BROWSER_DATA_SAVER_MODE", False), patch(
            "core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["script"]
        ), patch(
            "core.browser_data_saver._cfg.BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS", ["**://unsafe.example/**"]
        ):
            saver = BrowserDataSaver(
                label="认证",
                enabled=True,
                resource_types=["image", "media"],
                url_patterns=["**://telemetry.example/**"],
            )
        self.assertTrue(saver.enabled)
        self.assertEqual(saver.resource_types, ["image", "media"])
        self.assertEqual(saver.url_patterns, ["**://telemetry.example/**"])

    def test_auth_flow_uses_safe_rules_and_ignores_registration_rules(self):
        with patch("core.browser_flow_policy._cfg.BROWSER_DATA_SAVER_MODE", True), patch(
            "core.browser_flow_policy._cfg.BROWSER_DATA_SAVER_AUTH_FLOWS", ["token_refresh"]
        ), patch(
            "core.browser_flow_policy._cfg.BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["script", "font"]
        ), patch(
            "core.browser_flow_policy._cfg.BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS",
            ["**://auth-cdn.oaistatic.com/**", "**://chatgpt.com/ces/v1/rgstr**", "**://bad.example/**"],
        ):
            self.assertTrue(flow_enabled("token_refresh"))
            self.assertFalse(flow_enabled("live_check"))
            self.assertEqual(opening_resource_types("token_refresh"), ["image", "media"])
            opened = SimpleNamespace(traffic_capture=_Capture())
            driver = _Driver()
            saver = install_for_flow("token_refresh", opened, driver, label="AT刷新")
        self.assertIs(opened.traffic_capture.data_saver, saver)
        self.assertEqual(saver.resource_types, ["image", "media"])
        patterns = driver.commands[-1][1]["urls"]
        self.assertTrue(set(AUTH_SAFE_URL_PATTERNS).issubset(set(saver.url_patterns)))
        self.assertNotIn("*://auth-cdn.oaistatic.com/*", patterns)
        self.assertNotIn("*://chatgpt.com/ces/v1/rgstr*", patterns)
        self.assertNotIn("*.js*", patterns)

    def test_disabled_auth_flow_clears_previous_cdp_blocklist(self):
        with patch("core.browser_flow_policy._cfg.BROWSER_DATA_SAVER_MODE", True), patch(
            "core.browser_flow_policy._cfg.BROWSER_DATA_SAVER_AUTH_FLOWS", []
        ):
            driver = _Driver()
            opened = SimpleNamespace(traffic_capture=_Capture())
            saver = install_for_flow("account_action", opened, driver)
        self.assertFalse(saver.enabled)
        self.assertEqual(driver.commands[-1], ("Network.setBlockedURLs", {"urls": []}))
        self.assertIs(opened.traffic_capture.data_saver, saver)

    def test_flow_specific_open_args_follow_same_policy(self):
        auth_params = {"args": []}
        registration_params = {"args": []}
        with patch("config.browser.BROWSER_DATA_SAVER_MODE", True), patch(
            "config.browser.BROWSER_DATA_SAVER_AUTH_FLOWS", ["token_refresh"]
        ), patch(
            "config.browser.BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["image", "font"]
        ):
            _apply_data_saver_open_args(auth_params, "token_refresh")
            _apply_data_saver_open_args(registration_params, "registration")
        self.assertIn("--blink-settings=imagesEnabled=false", auth_params["args"])
        self.assertNotIn("--disable-remote-fonts", auth_params["args"])
        self.assertIn("--disable-remote-fonts", registration_params["args"])

    def test_auth_flow_empty_list_is_valid_for_webui_and_reload_resolution(self):
        self.assertEqual(validate_value("BROWSER_DATA_SAVER_AUTH_FLOWS", []), [])
        resolution = resolve_field(
            CONFIG_SCHEMA["BROWSER_DATA_SAVER_AUTH_FLOWS"],
            {"BROWSER_DATA_SAVER_AUTH_FLOWS": "[]"},
        )
        self.assertEqual(resolution.value, [])
        self.assertTrue(resolution.configured)

    def test_blocked_request_body_is_not_counted_as_provider_traffic(self):
        session = _SummaryOnlyCDPSession("profile-test")
        session.record_network({
            "url": "https://auth.openai.com/awe/api/v2/rum",
            "resource_type": "XHR",
            "request_body_bytes": 123456,
            "encoded_data_length": 0,
            "_data_saver_blocked": True,
        })
        summary = session.summary()
        self.assertEqual(summary["total_bytes"], 0)
        self.assertEqual(summary["request_count"], 1)
        self.assertEqual(summary["resource_type_bytes"], {"xhr": 0})

    def test_loopback_browser_resources_are_not_counted_as_provider_traffic(self):
        session = _SummaryOnlyCDPSession("profile-test")
        session.record_network({
            "url": "http://127.0.0.1/assets/roxy-shell.js",
            "resource_type": "Script",
            "request_body_bytes": 100,
            "encoded_data_length": 640000,
        })
        summary = session.summary()
        self.assertEqual(summary["total_bytes"], 0)
        self.assertEqual(summary["request_count"], 1)


if __name__ == "__main__":
    unittest.main()
