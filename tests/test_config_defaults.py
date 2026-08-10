# -*- coding: utf-8 -*-
import os
import importlib
import unittest
from unittest.mock import patch

from config import codex as codex_config
from config import env_loader
from webui import config_editor


class ConfigDefaultFallbackTests(unittest.TestCase):
    def test_blank_env_value_uses_default_for_all_supported_types(self):
        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {
                "BOOL_KEY": "",
                "INT_KEY": "",
                "FLOAT_KEY": "",
                "STR_KEY": "",
                "LIST_KEY": "",
            }, clear=True):
                self.assertTrue(env_loader.env_bool("BOOL_KEY", True))
                self.assertEqual(env_loader.env_int("INT_KEY", 90), 90)
                self.assertEqual(env_loader.env_float("FLOAT_KEY", 1.5), 1.5)
                self.assertEqual(env_loader.env_str("STR_KEY", "default"), "default")
                self.assertEqual(env_loader.env_list("LIST_KEY", ["a"]), ["a"])
        finally:
            env_loader._LOADED = old_loaded

    def test_proxy_pool_blank_env_value_means_empty_list(self):
        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        namespace = {"PROXY_POOL": ["socks5://127.0.0.1:7897"]}
        try:
            with patch.dict(os.environ, {"PROXY_POOL": ""}, clear=True):
                env_loader.apply_env_overrides(namespace, {"PROXY_POOL": "list_str_multiline"})
        finally:
            env_loader._LOADED = old_loaded

        self.assertEqual(namespace["PROXY_POOL"], [])

    def test_config_editor_formats_empty_list_as_literal_empty_list(self):
        self.assertEqual(config_editor._format_env_value([], "list_str_multiline"), "[]")

    def test_apply_env_overrides_does_not_let_blank_values_mask_defaults(self):
        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        namespace = {"FEATURE_ENABLED": True, "BASE_URL": "https://example.test"}
        try:
            with patch.dict(os.environ, {"FEATURE_ENABLED": "", "BASE_URL": ""}, clear=True):
                env_loader.apply_env_overrides(namespace, {"FEATURE_ENABLED": "bool", "BASE_URL": "str"})
        finally:
            env_loader._LOADED = old_loaded

        self.assertTrue(namespace["FEATURE_ENABLED"])
        self.assertEqual(namespace["BASE_URL"], "https://example.test")

    def test_config_editor_parses_env_str_default_from_source(self):
        source = 'API_KEY: str = env_str("API_KEY", "fallback-key")\n'
        self.assertEqual(
            config_editor._parse_value_from_source(source, "API_KEY", "str"),
            "fallback-key",
        )

    def test_config_editor_blank_env_value_falls_back_to_source_default(self):
        self.assertEqual(
            config_editor._coerce_raw_value("", "wss://connect.browser-use.com", "str"),
            "wss://connect.browser-use.com",
        )
        self.assertTrue(config_editor._coerce_raw_value("", True, "bool"))

    def test_sms_max_price_is_env_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn("SMS_MAX_PRICE", fields)
        self.assertEqual(fields["SMS_MAX_PRICE"]["group"], "接码平台")

        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {"SMS_MAX_PRICE": "0.13"}, clear=False):
                reloaded = importlib.reload(codex_config)
                self.assertEqual(reloaded.SMS_MAX_PRICE, "0.13")
        finally:
            env_loader._LOADED = old_loaded
            importlib.reload(codex_config)

    def test_1024proxy_fields_are_webui_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        expected = {
            "REGISTRATION_PROXY_MODE", "PROXY_1024_API_URL", "PROXY_1024_REGION", "PROXY_1024_PROTOCOL",
            "PROXY_1024_SESSION_MINUTES", "PROXY_1024_ROTATE_SESSION_TIME", "PROXY_1024_API_TIMEOUT",
            "PROXY_1024_MAX_ATTEMPTS", "PROXY_1024_VALIDATE",
            "PROXY_1024_RECENT_TTL", "PROXY_1024_ACQUIRE_INTERVAL",
        }
        self.assertTrue(expected.issubset(fields))
        self.assertEqual(fields["PROXY_1024_API_URL"]["group"], "代理平台")
        self.assertTrue(fields["PROXY_1024_API_URL"]["secret"])

    def test_cloak_human_preset_is_webui_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn("CLOAK_HUMAN_PRESET", fields)
        self.assertEqual(fields["CLOAK_HUMAN_PRESET"]["group"], "CloakBrowser")

    def test_icloud_hme_fields_are_webui_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        expected = {
            "ICLOUD_HME_API_BASE", "ICLOUD_HME_ACCOUNT_ID", "ICLOUD_HME_API_TOKEN",
            "ICLOUD_HME_REQUEST_TIMEOUT", "ICLOUD_HME_SYNC_TTL",
            "ICLOUD_HME_INBOX_MODE", "ICLOUD_HME_FORWARD_IMAP_SERVER",
            "ICLOUD_HME_FORWARD_IMAP_PORT", "ICLOUD_HME_FORWARD_IMAP_EMAIL",
            "ICLOUD_HME_FORWARD_IMAP_PASSWORD",
            "ICLOUD_HME_AUTO_CREATE", "ICLOUD_HME_CREATE_LABEL_PREFIX",
        }
        self.assertTrue(expected.issubset(fields))
        self.assertEqual(fields["ICLOUD_HME_API_BASE"]["group"], "邮箱 / OTP")
        self.assertTrue(fields["ICLOUD_HME_API_TOKEN"]["secret"])
        self.assertTrue(fields["ICLOUD_HME_FORWARD_IMAP_PASSWORD"]["secret"])

    def test_deactivation_mail_provider_fields_are_webui_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        expected = {
            "EMAIL_BUTLER_API_BASE",
            "EMAIL_BUTLER_API_KEY",
            "EMAIL_BUTLER_REQUEST_TIMEOUT",
            "CLOUDFLARE_SIGNAL_API_KEY",
            "CLOUDFLARE_SIGNAL_PATH",
        }
        self.assertTrue(expected.issubset(fields))
        self.assertTrue(fields["EMAIL_BUTLER_API_KEY"]["secret"])
        self.assertTrue(fields["CLOUDFLARE_SIGNAL_API_KEY"]["secret"])


if __name__ == "__main__":
    unittest.main()
