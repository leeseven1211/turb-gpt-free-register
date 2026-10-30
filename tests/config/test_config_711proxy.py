"""711Proxy 配置隔离、来源切换与敏感信息契约。"""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from config import proxy
from config import schema


class Proxy711ConfigTests(unittest.TestCase):
    def test_provider_settings_have_database_defaults_without_bootstrap_template_entries(self):
        expected = {
            "PROXY_711_API_URL": "", "PROXY_711_PROTOCOL": "http",
            "PROXY_711_SESSION_MINUTES": 30, "PROXY_711_API_TIMEOUT": 12.0,
            "PROXY_711_ACQUIRE_TIMEOUT": 60.0, "PROXY_711_VALIDATE_ATTEMPTS": 2,
            "PROXY_711_RECENT_TTL": 1800, "PROXY_711_ACQUIRE_INTERVAL": 0.6,
        }
        template = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
        for key, default in expected.items():
            with self.subTest(key=key):
                field = schema.CONFIG_SCHEMA[key]
                self.assertEqual(default, field.default)
                self.assertEqual(default, getattr(proxy, key))
                self.assertEqual("代理与网络", field.group)
                self.assertNotIn(f"{key}=", template)
                self.assertEqual("database", field.storage)
        options = {item.value: item.label for item in schema.CONFIG_SCHEMA["PROXY_POOL_SOURCE"].options}
        self.assertEqual("711Proxy", options["711proxy"])

    def test_session_range_and_protocol_options_match_provider(self):
        for minutes in (1, 30, 180):
            self.assertEqual(minutes, schema.validate_value("PROXY_711_SESSION_MINUTES", minutes))
        for minutes in (0, 181):
            with self.assertRaises(schema.ConfigValidationError):
                schema.validate_value("PROXY_711_SESSION_MINUTES", minutes)
        for protocol in ("http", "socks5", "socks5h"):
            self.assertEqual(protocol, schema.validate_value("PROXY_711_PROTOCOL", protocol))
        with self.assertRaises(schema.ConfigValidationError):
            schema.validate_value("PROXY_711_PROTOCOL", "https")

    def test_switching_to_711_requires_only_its_own_supply(self):
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
            with self.assertRaises(schema.ConfigValidationError) as failure:
                schema.validate_config_updates({"PROXY_POOL_SOURCE": "711proxy"})
            self.assertEqual({"PROXY_711_API_URL"}, set(failure.exception.errors))
            updates = {
                "PROXY_POOL_SOURCE": "711proxy", "PROXY_711_API_URL": "https://proxy.example.test/api?key=private-example",
                "PROXY_1024_API_URL": "", "PROXY_1024_SESSION_MINUTES": 1,
                "PROXY_711_SESSION_MINUTES": 30,
            }
            self.assertEqual(updates, schema.validate_config_updates(updates))

    def test_minimum_ttl_checks_only_the_selected_provider(self):
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
            base = {"PROXY_POOL_SOURCE": "711proxy", "PROXY_711_API_URL": "https://proxy.example.test/api", "PROXY_POOL_MIN_TTL": 300}
            with self.assertRaises(schema.ConfigValidationError) as failure:
                schema.validate_config_updates({**base, "PROXY_711_SESSION_MINUTES": 5})
            self.assertEqual({"PROXY_POOL_MIN_TTL"}, set(failure.exception.errors))
            self.assertIn("711Proxy", failure.exception.errors["PROXY_POOL_MIN_TTL"])
            schema.validate_config_updates({**base, "PROXY_711_SESSION_MINUTES": 6, "PROXY_1024_SESSION_MINUTES": 1})
            schema.validate_config_updates({
                "PROXY_POOL_SOURCE": "manual", "PROXY_POOL": ["http://proxy.example.test:8080"],
                "PROXY_711_SESSION_MINUTES": 1, "PROXY_POOL_MIN_TTL": 300,
            })

    def test_api_key_is_database_secret_and_excluded_from_metadata_and_snapshot(self):
        secret = "https://proxy.example.test/api?key=private-example"
        field = schema.CONFIG_SCHEMA["PROXY_711_API_URL"]
        self.assertTrue(field.secret)
        self.assertEqual("database", field.storage)
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", "PROXY_711_API_URL": secret}, clear=True), patch.object(schema, "_PUBLISHED_SNAPSHOT", None):
            metadata = {item["key"]: item for item in schema.effective_config_metadata()}
            self.assertTrue(metadata[field.key]["configured"])
            self.assertEqual("", metadata[field.key]["value"])
            self.assertNotIn(secret, json.dumps(metadata))
            snapshot = schema.build_non_sensitive_snapshot()
            self.assertNotIn(field.key, snapshot.values)
            self.assertNotIn(secret, json.dumps(snapshot.as_dict()))
