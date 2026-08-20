# -*- coding: utf-8 -*-
import os
import importlib
import unittest
from unittest.mock import patch

from config import codex as codex_config
from config import register as register_config
from config import twofa as twofa_config
from config import env_loader
from core import account_export
from webui import config_editor
from core import roxy_registration


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

    def test_twofa_driver_is_webui_editable_and_env_driven(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertEqual(fields["TWOFA_DRIVER"]["group"], "功能开关")
        self.assertEqual(fields["TWOFA_DRIVER"]["type"], "str")
        self.assertEqual(twofa_config.get_twofa_driver("roxy"), "browser")

        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {"TWOFA_DRIVER": "browser"}, clear=False):
                reloaded = importlib.reload(twofa_config)
                self.assertEqual(reloaded.TWOFA_DRIVER, "browser")
                self.assertEqual(reloaded.get_twofa_driver(), "browser")
        finally:
            env_loader._LOADED = old_loaded
            importlib.reload(twofa_config)

    def test_protocol_twofa_checkpoints_secret_before_activation(self):
        events = []
        secret = "JBSWY3DPEHPK3PXP"
        with patch.object(
            account_export,
            "_enroll_totp",
            side_effect=lambda *_: (events.append("enroll") or (secret, "session-1")),
        ), patch.object(
            account_export,
            "_activate_totp",
            side_effect=lambda *_: events.append("activate"),
        ), patch.object(account_export.time, "time", return_value=100.0):
            result = account_export.setup_2fa_protocol(
                object(),
                "fresh-token",
                on_secret=lambda _secret: events.append("checkpoint"),
            )

        self.assertEqual(result, secret)
        self.assertEqual(events, ["enroll", "checkpoint", "activate"])

    def test_grizzly_auto_country_fields_are_env_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn("SMS_AUTO_SELECT_COUNTRY", fields)
        self.assertIn("SMS_AUTO_COUNTRY_MIN_RATIO", fields)
        self.assertEqual(fields["SMS_AUTO_SELECT_COUNTRY"]["group"], "接码平台")

        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {
                "SMS_AUTO_SELECT_COUNTRY": "False",
                "SMS_AUTO_COUNTRY_MIN_RATIO": "50",
            }, clear=False):
                reloaded = importlib.reload(codex_config)
                self.assertFalse(reloaded.SMS_AUTO_SELECT_COUNTRY)
                self.assertEqual(reloaded.SMS_AUTO_COUNTRY_MIN_RATIO, 50)
        finally:
            env_loader._LOADED = old_loaded
            importlib.reload(codex_config)

    def test_codex_phone_total_timeout_is_env_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn("CODEX_PHONE_TOTAL_TIMEOUT", fields)
        self.assertEqual(fields["CODEX_PHONE_TOTAL_TIMEOUT"]["group"], "接码平台")

        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {"CODEX_PHONE_TOTAL_TIMEOUT": "240"}, clear=False):
                reloaded = importlib.reload(codex_config)
                self.assertEqual(reloaded.CODEX_PHONE_TOTAL_TIMEOUT, 240)
        finally:
            env_loader._LOADED = old_loaded
            importlib.reload(codex_config)

    def test_account_batch_workers_are_managed_in_general_config(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn("ACCOUNT_BATCH_WORKERS", fields)
        self.assertEqual(fields["ACCOUNT_BATCH_WORKERS"]["group"], "通用配置")

        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {"ACCOUNT_BATCH_WORKERS": "7"}, clear=False):
                reloaded = importlib.reload(codex_config)
                self.assertEqual(reloaded.ACCOUNT_BATCH_WORKERS, 7)
        finally:
            env_loader._LOADED = old_loaded
            importlib.reload(codex_config)

    def test_codex_token_refresh_fields_are_webui_editable_and_env_driven(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        expected = {
            "CODEX_TOKEN_AUTO_REFRESH_ENABLED",
            "CODEX_TOKEN_REFRESH_BEFORE_HOURS",
            "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS",
            "CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS",
            "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE",
            "CODEX_TOKEN_AUTO_SYNC_SUB2API",
        }
        self.assertTrue(expected.issubset(fields))
        self.assertTrue(all(fields[key]["group"] == "Codex" for key in expected))

        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {
                "CODEX_TOKEN_AUTO_REFRESH_ENABLED": "False",
                "CODEX_TOKEN_REFRESH_BEFORE_HOURS": "36",
            }, clear=False):
                reloaded = importlib.reload(codex_config)
                self.assertFalse(reloaded.CODEX_TOKEN_AUTO_REFRESH_ENABLED)
                self.assertEqual(reloaded.CODEX_TOKEN_REFRESH_BEFORE_HOURS, 36)
        finally:
            env_loader._LOADED = old_loaded
            importlib.reload(codex_config)

    def test_registration_password_mode_is_webui_editable_and_env_driven(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertEqual(fields["REGISTRATION_AUTH_MODE"]["group"], "注册方式")
        self.assertNotIn("REGISTER_PASSWORD", fields)

        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {"REGISTRATION_AUTH_MODE": "password"}, clear=False):
                reloaded = importlib.reload(register_config)
                self.assertEqual(reloaded.REGISTRATION_AUTH_MODE, "password")
        finally:
            env_loader._LOADED = old_loaded
            importlib.reload(register_config)

    def test_password_mode_always_generates_independent_random_passwords(self):
        first = roxy_registration._registration_password()
        second = roxy_registration._registration_password()
        self.assertEqual(len(first), 14)
        self.assertEqual(len(second), 14)
        self.assertNotEqual(first, second)

    def test_registration_auth_mode_defaults_safely_and_accepts_password(self):
        with patch.object(register_config, "REGISTRATION_AUTH_MODE", "password"):
            self.assertEqual(roxy_registration._registration_auth_mode(), "password")
        with patch.object(register_config, "REGISTRATION_AUTH_MODE", "unexpected"):
            self.assertEqual(roxy_registration._registration_auth_mode(), "otp")

    def test_1024proxy_fields_are_webui_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        expected = {
            "REGISTRATION_PROXY_MODE", "PROXY_1024_API_URL", "PROXY_1024_REGION", "PROXY_1024_PROTOCOL",
            "PROXY_1024_SESSION_MINUTES", "PROXY_1024_ROTATE_SESSION_TIME", "PROXY_1024_API_TIMEOUT",
            "PROXY_1024_MAX_ATTEMPTS", "PROXY_1024_ACQUIRE_TIMEOUT", "PROXY_1024_VALIDATE",
            "PROXY_1024_VALIDATE_ATTEMPTS",
            "PROXY_1024_RECENT_TTL", "PROXY_1024_ACQUIRE_INTERVAL",
            "ACCOUNT_ACTION_PROXY_MODE", "ACCOUNT_ACTION_PROXY",
        }
        self.assertTrue(expected.issubset(fields))
        self.assertEqual(fields["PROXY_1024_API_URL"]["group"], "代理平台")
        self.assertTrue(fields["PROXY_1024_API_URL"]["secret"])

    def test_cloak_human_preset_is_webui_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn("CLOAK_HUMAN_PRESET", fields)
        self.assertEqual(fields["CLOAK_HUMAN_PRESET"]["group"], "CloakBrowser")

    def test_roxy_capacity_wait_fields_are_webui_editable(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn("ROXY_WINDOW_WAIT_TIMEOUT", fields)
        self.assertIn("ROXY_WINDOW_WAIT_INTERVAL", fields)
        self.assertEqual(fields["ROXY_WINDOW_WAIT_TIMEOUT"]["group"], "RoxyBrowser")

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

    def test_scheduled_task_fields_are_webui_editable(self):
        """三个定时任务的开关与间隔都必须能在 WebUI 改。

        改造前它们只能通过环境变量控制，UI 上完全找不到。
        """
        from webui.config_editor import EDITABLE_FIELDS
        keys = {f["key"] for f in EDITABLE_FIELDS if f.get("group") == "定时任务"}
        self.assertEqual(keys, {
            "EMAIL_BUTLER_RISK_SCAN_ENABLED", "EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS",
            "AT_AUTO_REFRESH_ENABLED", "AT_REFRESH_SCAN_INTERVAL_SECONDS",
            "CODEX_TOKEN_AUTO_REFRESH_ENABLED", "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS",
        })

    def test_scheduled_task_switches_are_env_overridable(self):
        for key, module in [
            ("EMAIL_BUTLER_RISK_SCAN_ENABLED", "config.email"),
            ("AT_AUTO_REFRESH_ENABLED", "config.codex"),
            ("CODEX_TOKEN_AUTO_REFRESH_ENABLED", "config.codex"),
        ]:
            with self.subTest(key=key):
                with patch.dict(os.environ, {key: "False"}):
                    module_obj = importlib.reload(importlib.import_module(module))
                    self.assertFalse(getattr(module_obj, key))
                importlib.reload(importlib.import_module(module))

    def test_scheduler_reads_config_at_call_time_not_import_time(self):
        """间隔必须每轮重新读，否则 WebUI 改完要重启才生效。"""
        from core import token_refresh_service as svc
        from config import codex as codex_cfg
        with patch.object(codex_cfg, "AT_REFRESH_SCAN_INTERVAL_SECONDS", 7200):
            self.assertEqual(svc.scheduler_interval_seconds(), 7200)
        with patch.object(codex_cfg, "AT_AUTO_REFRESH_ENABLED", False):
            self.assertFalse(svc.scheduler_enabled())

    def test_scheduler_interval_is_clamped_to_a_sane_range(self):
        from core import token_refresh_service as svc
        from config import codex as codex_cfg
        with patch.object(codex_cfg, "AT_REFRESH_SCAN_INTERVAL_SECONDS", 1):
            self.assertGreaterEqual(svc.scheduler_interval_seconds(), 300)
        with patch.object(codex_cfg, "AT_REFRESH_SCAN_INTERVAL_SECONDS", 10 ** 9):
            self.assertLessEqual(svc.scheduler_interval_seconds(), 86400)


if __name__ == "__main__":
    unittest.main()
