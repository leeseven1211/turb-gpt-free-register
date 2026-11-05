"""AT 国家配置支持跟随注册国家、固定国家及清空恢复。"""
import os
import unittest
from unittest.mock import patch

from config import schema
from config.countries import ISO_3166_ALPHA2


KEY = "ACCOUNT_AT_REFRESH_COUNTRY"


class AtRefreshCountryConfigTests(unittest.TestCase):
    def test_default_and_metadata_offer_country_selection_without_restart(self):
        field = schema.CONFIG_SCHEMA[KEY]
        self.assertEqual("", field.default)
        metadata = field.metadata()
        self.assertEqual("account.py", metadata["file"])
        self.assertEqual("账号补全", metadata["group"])
        self.assertEqual("str", metadata["type"])
        self.assertFalse(metadata["secret"])
        self.assertFalse(metadata["restart"])
        self.assertEqual(sorted(ISO_3166_ALPHA2), metadata["country_codes"])
        self.assertIn("NA", metadata["country_codes"])

    def test_country_validation_preserves_follow_and_namibia(self):
        for raw, expected in (("", ""), (None, ""), ("   ", ""), ("jp", "JP"), (" NA ", "NA")):
            with self.subTest(raw=raw):
                self.assertEqual(expected, schema.validate_value(KEY, raw))
        for raw in ("Rand", "XX", "日本", "JP,IN", ["JP"], {"country": "JP"}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                schema.validate_value(KEY, raw)

    def test_empty_update_is_persistable_and_does_not_change_registration_country(self):
        with patch.object(schema, "resolve_config", return_value={}):
            self.assertEqual({KEY: ""}, schema.validate_config_updates({KEY: ""}))
            self.assertEqual({KEY: "JP"}, schema.validate_config_updates({KEY: "jp"}))
        self.assertEqual("", schema.resolve_field(schema.CONFIG_SCHEMA[KEY], {}).value)
        values = {KEY: "", "REGISTRATION_COUNTRY": "IN", "PROXY_POOL_DEFAULT_COUNTRY": "VN"}
        self.assertEqual("", schema.resolve_field(schema.CONFIG_SCHEMA[KEY], values).value)
        self.assertEqual("IN", schema.resolve_field(schema.CONFIG_SCHEMA["REGISTRATION_COUNTRY"], values).value)

    def test_clearing_country_removes_previous_module_override(self):
        namespace = {"__name__": "config.account", KEY: "JP"}
        with patch.dict(os.environ, {KEY: ""}), patch("config.env_loader.ensure_loaded"):
            schema.apply_env_namespace(namespace)
        self.assertEqual("", namespace[KEY])

    def test_nested_at_refresh_tasks_keep_country_in_their_snapshot(self):
        from core.accounts.inspection.service import CONFIG_ALLOWLIST
        from core.extract_link.service import EXTRACT_CONFIG_ALLOWLIST
        from core.operations.task_gateway import normalize_config_snapshot

        for allowlist in (CONFIG_ALLOWLIST, EXTRACT_CONFIG_ALLOWLIST):
            with self.subTest(allowlist=tuple(allowlist)):
                snapshot = normalize_config_snapshot({KEY: "JP"}, allowlist=allowlist)
                self.assertEqual("JP", snapshot["refresh_at_country"])

    def test_at_network_recovery_limits_are_editable_and_bounded(self):
        expected = {
            "ACCOUNT_AT_REFRESH_NETWORK_RETRIES": (2, 0, 5),
            "ACCOUNT_AT_REFRESH_NETWORK_TIMEOUT_SECONDS": (900, 60, 3600),
        }
        for key, (default, minimum, maximum) in expected.items():
            with self.subTest(key=key):
                field = schema.CONFIG_SCHEMA[key]
                self.assertEqual(default, field.default)
                self.assertEqual("账号补全", field.group)
                self.assertFalse(field.restart)
                self.assertEqual(minimum, schema.validate_value(key, minimum))
                self.assertEqual(maximum, schema.validate_value(key, maximum))
                for invalid in (minimum - 1, maximum + 1):
                    with self.assertRaises(ValueError):
                        schema.validate_value(key, invalid)

        from core.extract_link.service import EXTRACT_CONFIG_ALLOWLIST
        from core.operations.task_gateway import normalize_config_snapshot

        snapshot = normalize_config_snapshot({key: value[0] for key, value in expected.items()},
                                             allowlist=EXTRACT_CONFIG_ALLOWLIST)
        self.assertEqual(2, snapshot["network_retry_limit"])
        self.assertEqual(900, snapshot["network_timeout_seconds"])
