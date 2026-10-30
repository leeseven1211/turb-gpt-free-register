"""统一代理池和结构化配置在保存、重载时保持相同语义。"""
import os
import unittest
from unittest.mock import patch

from config import schema


class PoolConfigMigrationTests(unittest.TestCase):
    def test_legacy_values_migrate_only_without_new_keys(self):
        legacy = {"REGISTRATION_PROXY_MODE": "pool", "PROXY_1024_REGION": "us"}
        resolved = schema.resolve_config(legacy)
        self.assertEqual(resolved["PROXY_POOL_SOURCE"].value, "manual")
        self.assertEqual(resolved["PROXY_POOL_DEFAULT_COUNTRY"].value, "US")
        legacy.update(PROXY_POOL_SOURCE="1024proxy", PROXY_POOL_DEFAULT_COUNTRY="JP")
        resolved = schema.resolve_config(legacy)
        self.assertEqual(resolved["PROXY_POOL_SOURCE"].value, "1024proxy")
        self.assertEqual(resolved["PROXY_POOL_DEFAULT_COUNTRY"].value, "JP")

    def test_runtime_namespace_uses_same_legacy_resolution(self):
        namespace = {"__name__": "config.proxy", "PROXY_POOL_SOURCE": "1024proxy", "PROXY_POOL_DEFAULT_COUNTRY": "JP"}
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", "REGISTRATION_PROXY_MODE": "pool", "PROXY_1024_API_URL": "https://proxy.example.test/api?region=GB"}, clear=True):
            schema.apply_env_namespace(namespace)
        self.assertEqual(namespace["PROXY_POOL_SOURCE"], "manual")
        self.assertEqual(namespace["PROXY_POOL_DEFAULT_COUNTRY"], "GB")

    def test_default_country_is_fixed_and_validated(self):
        self.assertEqual(schema.validate_value("PROXY_POOL_DEFAULT_COUNTRY", "na"), "NA")
        for value in ("Rand", "XX", "", "Japan"):
            with self.subTest(value=value), self.assertRaises(schema.ConfigValidationError):
                schema.validate_value("PROXY_POOL_DEFAULT_COUNTRY", value)

    def test_ordered_multiselect_values_are_validated(self):
        self.assertEqual(schema.validate_value("ROXY_RANDOM_OS_CHOICES", "macos,Windows,macOS"), "macOS,Windows")
        self.assertEqual(schema.validate_value("BROWSER_DATA_SAVER_AUTH_FLOWS", ["live_check", "live_check", "codex_oauth"]), ["live_check", "codex_oauth"])
        with self.assertRaises(schema.ConfigValidationError):
            schema.validate_value("BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ["script"])

    def test_empty_email_source_is_preserved_in_manual_mode(self):
        values = {"USE_EMAIL_SERVICE": "false", "EMAIL_SOURCE": ""}
        self.assertEqual(schema.resolve_config(values, strict=True)["EMAIL_SOURCE"].value, "")
        namespace = {"__name__": "config.email", "EMAIL_SOURCE": "outlook"}
        with patch.dict(os.environ, {**values, "PYTHON_DOTENV_DISABLED": "1"}, clear=True):
            schema.apply_env_namespace(namespace)
        self.assertEqual(namespace["EMAIL_SOURCE"], "")
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
            with self.assertRaises(schema.ConfigValidationError):
                schema.validate_config_updates({"USE_EMAIL_SERVICE": True, "EMAIL_SOURCE": ""})
            result = schema.validate_config_updates({"USE_EMAIL_SERVICE": False, "EMAIL_SOURCE": ""})
        self.assertEqual(result["EMAIL_SOURCE"], "")

    def test_manual_source_does_not_validate_unused_supplier_ttl(self):
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
            schema.validate_config_updates({
                "PROXY_POOL_SOURCE": "manual",
                "PROXY_POOL": ["http://proxy.example.test:8080"],
                "PROXY_1024_SESSION_MINUTES": 1,
                "PROXY_POOL_MIN_TTL": 300,
            })

    def test_selected_proxy_source_requires_its_supply_when_related_fields_change(self):
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
            cases = (
                ({"PROXY_POOL_SOURCE": "manual", "PROXY_POOL": []}, "PROXY_POOL"),
                ({"PROXY_POOL_SOURCE": "1024proxy", "PROXY_1024_API_URL": ""}, "PROXY_1024_API_URL"),
            )
            for updates, expected_field in cases:
                with self.subTest(source=updates["PROXY_POOL_SOURCE"]):
                    with self.assertRaises(schema.ConfigValidationError) as failure:
                        schema.validate_config_updates(updates)
                    self.assertEqual(set(failure.exception.errors), {expected_field})
                    self.assertNotIn("proxy.example", str(failure.exception))

    def test_unconfigured_proxy_does_not_block_unrelated_config_updates(self):
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
            result = schema.validate_config_updates({"ACCOUNT_BATCH_WORKERS": 4})
        self.assertEqual(result, {"ACCOUNT_BATCH_WORKERS": 4})

    def test_manual_addresses_require_protocol_host_and_port_without_echoing_credentials(self):
        self.assertFalse(schema.resolve_config({"PROXY_POOL": "[]"})["PROXY_POOL"].configured)
        valid = "socks5h://user:example@proxy.example.test:1080"
        self.assertEqual(schema.validate_value("PROXY_POOL", [valid, valid]), [valid])
        for value in ("192.0.2.1", "http://user:private@host:not-a-port", "ftp://host:21"):
            with self.subTest(value=value):
                with self.assertRaises(schema.ConfigValidationError) as failure:
                    schema.validate_value("PROXY_POOL", [value])
                self.assertNotIn(value, str(failure.exception))
                self.assertNotIn("private", str(failure.exception))


if __name__ == "__main__":
    unittest.main()
