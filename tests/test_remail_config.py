# -*- coding: utf-8 -*-
"""Remail 配置的环境覆盖、校验和密钥保护。"""

import json
import unittest

import config
from config import email
from config.env_loader import SECRET_ENV_KEYS
from config.schema import (
    CONFIG_SCHEMA,
    ConfigValidationError,
    build_non_sensitive_snapshot,
    resolve_config,
    validate_value,
)
from webui.config_editor import EDITABLE_FIELDS


class RemailConfigTests(unittest.TestCase):
    def test_defaults_and_environment_overrides_share_the_schema(self):
        defaults = {
            "REMAIL_API_BASE": "https://remail.aishop6.com",
            "REMAIL_API_KEY": "",
            "REMAIL_PROJECT_ID": 2,
            "REMAIL_EMAIL_SUFFIX": "outlook.com",
            "REMAIL_SERVICE_MODE": "purchase",
            "REMAIL_SUPPLY_POLICY": "public_only",
            "REMAIL_ORDER_WAIT_SECONDS": 30,
            "REMAIL_REQUEST_TIMEOUT": 20,
        }
        resolved = resolve_config({})
        for key, value in defaults.items():
            with self.subTest(key=key):
                self.assertEqual(resolved[key].value, value)
                self.assertTrue(hasattr(email, key))
                self.assertTrue(hasattr(config, key))
                self.assertIn(key, config.__all__)
        overridden = resolve_config({
            "EMAIL_SOURCE": "REMAIL,email_butler",
            "REMAIL_PROJECT_ID": "7",
            "REMAIL_SERVICE_MODE": "CODE",
            "REMAIL_SUPPLY_POLICY": "private_first",
            "REMAIL_REQUEST_TIMEOUT": "45",
        }, strict=True)
        self.assertEqual(overridden["EMAIL_SOURCE"].value, "remail,email_butler")
        self.assertEqual(overridden["REMAIL_PROJECT_ID"].value, 7)
        self.assertEqual(overridden["REMAIL_SERVICE_MODE"].value, "code")
        self.assertEqual(overridden["REMAIL_SUPPLY_POLICY"].value, "private_first")
        self.assertEqual(overridden["REMAIL_REQUEST_TIMEOUT"].value, 45)

    def test_invalid_order_configuration_is_rejected_before_save(self):
        for key, value in (
            ("REMAIL_PROJECT_ID", 0),
            ("REMAIL_PROJECT_ID", "2.5"),
            ("REMAIL_SERVICE_MODE", "unknown"),
            ("REMAIL_SUPPLY_POLICY", "unknown"),
            ("REMAIL_ORDER_WAIT_SECONDS", -1),
            ("REMAIL_ORDER_WAIT_SECONDS", 181),
            ("REMAIL_REQUEST_TIMEOUT", 0),
            ("REMAIL_REQUEST_TIMEOUT", 121),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaises(ConfigValidationError):
                    validate_value(key, value)
        self.assertEqual(validate_value("REMAIL_ORDER_WAIT_SECONDS", 0), 0)
        self.assertEqual(validate_value("REMAIL_ORDER_WAIT_SECONDS", 180), 180)
        self.assertEqual(validate_value("REMAIL_REQUEST_TIMEOUT", 120), 120)

    def test_api_key_is_secret_and_absent_from_public_snapshot(self):
        key = "REMAIL_API_KEY"
        field = CONFIG_SCHEMA[key]
        self.assertTrue(field.secret)
        self.assertEqual(field.storage, "env")
        self.assertEqual(SECRET_ENV_KEYS[key], "Remail API Key")
        bait = "rk-remail-test-bait"
        snapshot = build_non_sensitive_snapshot({key: bait})
        self.assertNotIn(bait, json.dumps(dict(snapshot.values)))
        self.assertNotIn(key, snapshot.values)

    def test_webui_exposes_all_settings_and_source_from_schema(self):
        fields = {item["key"]: item for item in EDITABLE_FIELDS}
        remail = [field for field in CONFIG_SCHEMA.fields if field.key.startswith("REMAIL_")]
        self.assertEqual(len(remail), 8)
        for field in remail:
            with self.subTest(key=field.key):
                self.assertEqual(fields[field.key]["group"], "邮箱 / OTP")
        self.assertIn("remail", CONFIG_SCHEMA["EMAIL_SOURCE"].csv_options)
        self.assertEqual(
            {option.value for option in CONFIG_SCHEMA["REMAIL_SERVICE_MODE"].options},
            {"purchase", "code"},
        )


if __name__ == "__main__":
    unittest.main()
