# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest.mock import patch

import config
from config import env_loader
from config import schema as config_schema
from config.schema import (
    CONFIG_SCHEMA,
    ConfigSnapshot,
    ConfigValidationError,
    build_non_sensitive_snapshot,
    effective_config_metadata,
    non_sensitive_snapshot,
    publish_config_snapshot,
    validate_config_updates,
    validate_value,
)
from webui import config_editor


class ConfigSchemaTests(unittest.TestCase):
    def test_schema_owns_unique_fields_and_editor_consumes_it(self):
        fields = CONFIG_SCHEMA.fields
        self.assertEqual(len(fields), len({field.key for field in fields}))
        self.assertEqual(195, len(fields))
        canonical = config_schema._legacy_fields()
        self.assertEqual(len(canonical), len({field["key"] for field in canonical}))
        self.assertEqual(
            {field.key for field in fields},
            {field["key"] for field in config_editor.EDITABLE_FIELDS},
        )
        schema_source = Path(config_schema.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from webui", schema_source)

        for field in fields:
            with self.subTest(key=field.key):
                self.assertTrue(field.type)
                self.assertIsNotNone(field.file)
                self.assertIsInstance(field.default, (str, int, float, bool, list))
                self.assertIsInstance(field.options, tuple)
                self.assertIsInstance(field.range, dict)
                self.assertIsInstance(field.secret, bool)
                self.assertIsInstance(field.aliases, Mapping)
                self.assertIn(field.hot_edit, {"safe", "restart"})
                metadata = field.metadata()
                self.assertIn("default", metadata)
                self.assertIn("type", metadata)
                self.assertIn("secret", metadata)
                self.assertIn("hot_edit", metadata)

    def test_schema_defaults_match_loaded_module_defaults(self):
        for field in CONFIG_SCHEMA.fields:
            if not field.module:
                continue
            module = __import__(field.module, fromlist=[field.key])
            if not hasattr(module, field.key):
                continue
            with self.subTest(key=field.key):
                self.assertEqual(field.default, getattr(module, field.key))

    def test_every_editable_module_is_in_reload_boundary(self):
        reloadable = set(config._RELOADABLE_SUBMODULES)
        self.assertTrue({
            field.module
            for field in CONFIG_SCHEMA.fields
            if field.module
        }.issubset(reloadable))

    def test_invalid_range_option_unknown_and_cross_field_updates_are_rejected(self):
        with self.assertRaises(ConfigValidationError):
            validate_value("PLAN_CHECK_WORKERS", 0)
        with self.assertRaises(ConfigValidationError):
            validate_value("REGISTRATION_PROXY_MODE", "not-a-route")
        with self.assertRaises(ConfigValidationError):
            validate_config_updates({"NOT_IN_SCHEMA": "x"})
        with self.assertRaises(ConfigValidationError):
            validate_config_updates({"ACCOUNT_LIVE_CHECK_DRIVER": "browser_roxy"})
        self.assertEqual(
            {
                "ACCOUNT_LIVE_CHECK_DRIVER": "browser_roxy",
                "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED": True,
            },
            validate_config_updates({
                "ACCOUNT_LIVE_CHECK_DRIVER": "browser_roxy",
                "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED": True,
            }),
        )

    def test_effective_metadata_reports_default_and_env_sources(self):
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {}, clear=True):
            defaults = {
                item["key"]: item
                for item in effective_config_metadata()
            }
            self.assertEqual(3, defaults["PLAN_CHECK_WORKERS"]["value"])
            self.assertEqual("default", defaults["PLAN_CHECK_WORKERS"]["source"])

        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {"PLAN_CHECK_WORKERS": "7"}, clear=True):
            values = {
                item["key"]: item
                for item in effective_config_metadata()
            }
            self.assertEqual(7, values["PLAN_CHECK_WORKERS"]["value"])
            self.assertEqual("env", values["PLAN_CHECK_WORKERS"]["source"])
            self.assertEqual("PLAN_CHECK_WORKERS", values["PLAN_CHECK_WORKERS"]["source_key"])

    def test_secret_metadata_and_snapshot_never_contain_secret_value(self):
        secret = "schema-test-secret-do-not-return"
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {"ROXY_API_TOKEN": secret}, clear=True):
            metadata = effective_config_metadata()
            token = next(item for item in metadata if item["key"] == "ROXY_API_TOKEN")
            self.assertEqual("", token["value"])
            self.assertTrue(token["configured"])
            self.assertNotIn("default", token)
            self.assertNotIn(secret, json.dumps(metadata, ensure_ascii=False))

            snapshot = non_sensitive_snapshot()
            self.assertNotIn("ROXY_API_TOKEN", snapshot.values)
            self.assertNotIn(secret, json.dumps(snapshot.as_dict(), ensure_ascii=False))

    def test_snapshot_is_immutable_and_published_as_one_versioned_object(self):
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {"PLAN_CHECK_WORKERS": "9"}, clear=True):
            candidate = build_non_sensitive_snapshot(strict=True)
            published = publish_config_snapshot(candidate)
            current = non_sensitive_snapshot()

            self.assertIs(published, current)
            self.assertEqual(0, current.revision)
            self.assertEqual(9, current["PLAN_CHECK_WORKERS"])
            self.assertEqual("env", current.sources["PLAN_CHECK_WORKERS"])
            self.assertNotIn("PROXY_POOL", current.values)
            with self.assertRaises(TypeError):
                current.values["PLAN_CHECK_WORKERS"] = 1
            with self.assertRaises(TypeError):
                current.sources["PLAN_CHECK_WORKERS"] = "default"
            with self.assertRaises(AttributeError):
                current.revision = 99

    def test_config_metadata_distinguishes_published_and_pending_environment(self):
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {"PLAN_CHECK_WORKERS": "3"}, clear=True):
            initial = {
                item["key"]: item
                for item in effective_config_metadata()
            }["PLAN_CHECK_WORKERS"]
            self.assertEqual(3, initial["value"])
            self.assertEqual(3, initial["configured_value"])
            self.assertFalse(initial["pending_reload"])

            os.environ["PLAN_CHECK_WORKERS"] = "9"
            pending = {
                item["key"]: item
                for item in effective_config_metadata()
            }["PLAN_CHECK_WORKERS"]

        self.assertEqual(3, pending["published_effective_value"])
        self.assertEqual("env", pending["published_effective_source"])
        self.assertEqual("PLAN_CHECK_WORKERS", pending["source_key"])
        self.assertEqual("PLAN_CHECK_WORKERS", pending["configured_source_key"])
        self.assertEqual(3, pending["value"])
        self.assertEqual(9, pending["configured_value"])
        self.assertEqual(initial["published_revision"], pending["published_revision"])
        self.assertTrue(pending["pending_reload"])

    def test_non_sensitive_snapshot_redacts_proxy_and_provider_baits(self):
        expected_sensitive = {
            "PROXY_POOL",
            "ACCOUNT_ACTION_PROXY",
            "PROXY_1024_API_URL",
            "ROXY_API_TOKEN",
            "EMAIL_BUTLER_API_KEY",
            "GPTMAIL_API_KEY",
            "CLOUDFLARE_API_KEY",
            "CLOUDFLARE_SIGNAL_API_KEY",
            "CLOUDFLARE_CUSTOM_AUTH",
            "MAIL_NEST_API_KEY",
            "CLOUDMAIL_PASSWORD",
            "CLOUDMAIL_AUTH_TOKEN",
            "ICLOUD_HME_API_TOKEN",
            "ICLOUD_HME_FORWARD_IMAP_PASSWORD",
            "SUB2API_API_KEY",
            "CPA_MANAGEMENT_KEY",
            "SMS_API_KEY",
            "H_ADMIN_AUTH_CODE",
            "L_ADMIN_AUTH_CODE",
        }
        self.assertTrue(
            expected_sensitive.issubset(
                {field.key for field in CONFIG_SCHEMA.fields if field.secret}
            )
        )
        bait_values = {}
        for field in CONFIG_SCHEMA.fields:
            if not field.secret:
                continue
            bait = f"schema-bait-{field.key}"
            bait_values[field.key] = (
                f"https://user:{bait}@proxy.example.test:443"
                if field.type == "list_str_multiline"
                else bait
            )
        bait_values["PROXY_POOL"] = "https://user:schema-bait-proxy-pool@proxy.example.test:443"

        snapshot = build_non_sensitive_snapshot(bait_values, strict=True)
        serialized = json.dumps({
            "revision": snapshot.revision,
            "values": snapshot.as_dict(),
            "sources": dict(snapshot.sources),
        }, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("schema-bait-", serialized)
        for value in bait_values.values():
            self.assertNotIn(value, serialized)
        for key in bait_values:
            self.assertNotIn(key, snapshot.values)

    def test_reload_failure_restores_modules_without_global_env_clear(self):
        import config.browser as browser
        import config.openai_protocol as openai_protocol

        before_browser = dict(browser.__dict__)
        before_protocol = dict(openai_protocol.__dict__)
        calls = []

        def fake_reload(module):
            calls.append(module.__name__)
            module._schema_test_partial = True
            if len(calls) == 2:
                raise RuntimeError("simulated reload failure")
            return module

        with patch.dict(os.environ, {"UNRELATED_THREAD_ENV": "keep"}, clear=True), patch(
            "config.env_loader.load_env"
        ), patch.object(config, "_RELOADABLE_SUBMODULES", (
            "config.browser", "config.openai_protocol"
        )), patch.object(config._importlib, "reload", side_effect=fake_reload), patch.object(
            config, "_refresh_top_level_constants"
        ):
            with self.assertRaises(RuntimeError):
                config.reload_all()

            self.assertEqual("keep", os.environ["UNRELATED_THREAD_ENV"])
            self.assertNotIn("_schema_test_partial", browser.__dict__)
            self.assertNotIn("_schema_test_partial", openai_protocol.__dict__)
            self.assertEqual(before_browser, browser.__dict__)
            self.assertEqual(before_protocol, openai_protocol.__dict__)

    def test_environment_restore_skips_concurrent_unrelated_key(self):
        before = {"CONFIG_KEY": "old"}
        expected = {"CONFIG_KEY": "new"}
        with patch.dict(os.environ, {"CONFIG_KEY": "new", "CONCURRENT_KEY": "keep"}, clear=True):
            env_loader.restore_environment(before, expected)
            self.assertEqual("old", os.environ["CONFIG_KEY"])
            self.assertEqual("keep", os.environ["CONCURRENT_KEY"])

    def test_failed_config_save_restores_file_and_environment(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-config-schema-")
        os.close(fd)
        path = Path(raw_path)
        path.unlink()
        self.addCleanup(lambda: path.unlink() if path.exists() else None)

        with patch.object(env_loader, "_ENV_PATH", path), patch.object(
            config, "reload_all", side_effect=RuntimeError("simulated reload failure")
        ), patch.dict(os.environ, {"UNRELATED_THREAD_ENV": "keep"}, clear=True):
            with self.assertRaises(RuntimeError):
                config_editor.update_config({"PLAN_CHECK_WORKERS": 4})
            self.assertFalse(path.exists())
            self.assertNotIn("PLAN_CHECK_WORKERS", os.environ)
            self.assertEqual("keep", os.environ["UNRELATED_THREAD_ENV"])

    def test_full_candidate_is_validated_before_env_write(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-config-preflight-")
        os.close(fd)
        path = Path(raw_path)
        path.write_text("PLAN_CHECK_WORKERS=0\n", encoding="utf-8")
        self.addCleanup(lambda: path.unlink() if path.exists() else None)

        with patch.object(env_loader, "_ENV_PATH", path), patch.dict(
            os.environ, {}, clear=True
        ):
            with self.assertRaises(ConfigValidationError):
                config_editor.update_config({"PLAN_CHECK_QUEUE_LIMIT": 600})
            self.assertEqual("PLAN_CHECK_WORKERS=0\n", path.read_text(encoding="utf-8"))
            self.assertNotIn("PLAN_CHECK_QUEUE_LIMIT", os.environ)

    def test_dotenv_disabled_short_circuits_before_file_parser(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-dotenv-disabled-")
        os.close(fd)
        path = Path(raw_path)
        path.write_text("DOTENV_SHOULD_NOT_LOAD=secret\n", encoding="utf-8")
        self.addCleanup(lambda: path.unlink() if path.exists() else None)

        old_loaded = env_loader._LOADED
        try:
            env_loader._LOADED = False
            with patch.object(env_loader, "_ENV_PATH", path), patch.dict(
                os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True
            ):
                env_loader.load_env(override=True)
                self.assertNotIn("DOTENV_SHOULD_NOT_LOAD", os.environ)
        finally:
            env_loader._LOADED = old_loaded

    def test_env_example_covers_every_unique_schema_field(self):
        example = Path(".env.example").read_text(encoding="utf-8")
        for field in CONFIG_SCHEMA.fields:
            with self.subTest(key=field.key):
                self.assertRegex(example, rf"(?m)^{field.key}=")


if __name__ == "__main__":
    unittest.main()
