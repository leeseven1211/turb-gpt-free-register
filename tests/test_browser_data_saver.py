import unittest
from unittest.mock import patch

from core.browser_data_saver import BrowserDataSaver, configured_resource_types
from core.browser_traffic import _SummaryOnlyCDPSession
from core.roxybrowser_client import _apply_data_saver_open_args


class _Driver:
    def __init__(self):
        self.commands = []

    def execute_cdp_cmd(self, command, params):
        self.commands.append((command, params))
        return {}


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
