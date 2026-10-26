# -*- coding: utf-8 -*-
"""刷新 AT 驱动及 Roxy 调试配置契约。"""
from __future__ import annotations

import importlib
import os
import unittest
from unittest.mock import patch

import config
from config import account, env_loader, schema


DRIVER = "ACCOUNT_AT_REFRESH_DRIVER"
DEBUG = "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED"


class RoxyRefreshConfigTests(unittest.TestCase):
    def test_defaults_exports_and_editable_choices(self):
        self.assertEqual("protocol", schema.schema_default(DRIVER))
        self.assertIs(False, schema.schema_default(DEBUG))
        self.assertEqual("protocol", getattr(config, DRIVER))
        self.assertIs(False, getattr(config, DEBUG))
        self.assertEqual({"protocol", "browser_roxy"}, {item.value for item in schema.CONFIG_SCHEMA[DRIVER].options})
        for key in (DRIVER, DEBUG):
            field = schema.CONFIG_SCHEMA[key]
            self.assertTrue(field.editable)
            self.assertFalse(field.secret)
            self.assertEqual("账号补全", field.group)
            self.assertEqual("account.py", field.file)
        self.assertNotIn("ACCOUNT_TOKEN_REFRESH_DRIVER", schema.CONFIG_SCHEMA)

    def test_driver_validation_and_debug_boolean_are_independent(self):
        for driver in ("protocol", "browser_roxy"):
            self.assertEqual(driver, schema.validate_value(DRIVER, driver))
        for driver in ("legacy", "protocol_v2", "v2", "browser", "unknown"):
            with self.subTest(driver=driver), self.assertRaises(schema.ConfigValidationError):
                schema.validate_value(DRIVER, driver)
        self.assertTrue(schema.validate_value(DEBUG, "True"))
        self.assertFalse(schema.validate_value(DEBUG, "False"))

    def test_candidate_snapshot_keeps_browser_driver_separate_from_protocol_version(self):
        snapshot = schema.build_non_sensitive_snapshot({
            DRIVER: "browser_roxy", DEBUG: "True", "OPENAI_PROTOCOL_VERSION": "v2",
        })
        self.assertEqual("browser_roxy", snapshot[DRIVER])
        self.assertTrue(snapshot[DEBUG])
        self.assertEqual("v2", snapshot["OPENAI_PROTOCOL_VERSION"])

    def test_environment_overrides_update_account_module_without_legacy_driver(self):
        try:
            with patch.object(env_loader, "_LOADED", True), patch.dict(os.environ, {
                DRIVER: "browser_roxy", DEBUG: "True", "PYTHON_DOTENV_DISABLED": "1",
            }, clear=False):
                importlib.reload(account)
                self.assertEqual("browser_roxy", getattr(account, DRIVER))
                self.assertTrue(getattr(account, DEBUG))
                self.assertEqual("legacy", account.ACCOUNT_TOKEN_REFRESH_DRIVER)
        finally:
            importlib.reload(account)

    def test_completion_snapshot_includes_driver_and_debug_choices(self):
        with patch.object(account, DRIVER, "browser_roxy"), patch.object(account, DEBUG, True):
            settings = account.completion_settings()
        self.assertEqual("browser_roxy", settings["at_refresh_driver"])
        self.assertTrue(settings["at_refresh_roxy_debug_enabled"])

    def test_inline_extract_refresh_freezes_driver_version_and_debug(self):
        from core import extract_link_service

        expected = {"refresh_driver": DRIVER, "refresh_roxy_debug_enabled": DEBUG,
                    "refresh_protocol_version": "OPENAI_PROTOCOL_VERSION"}
        for name, key in expected.items():
            self.assertEqual(key, extract_link_service.EXTRACT_CONFIG_ALLOWLIST.get(name))


if __name__ == "__main__":
    unittest.main()
