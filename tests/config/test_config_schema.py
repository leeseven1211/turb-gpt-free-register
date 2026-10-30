# -*- coding: utf-8 -*-
import json
import importlib
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
    def test_huanguang_xxsyun_configuration_is_reloadable_without_exposing_key(self):
        from config import extract_link

        api_key = "EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY"
        fallback_key = "EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED"
        secret = "xxsyun-config-test-secret"
        self.assertEqual({api_key: secret, fallback_key: True}, validate_config_updates({
            api_key: secret, fallback_key: True,
        }))
        fd, raw_path = tempfile.mkstemp(prefix="turb-config-xxsyun-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        try:
            with patch.object(env_loader, "_ENV_PATH", path), patch.object(
                config_schema, "_PUBLISHED_SNAPSHOT", None
            ), patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
                saved = config_editor.update_config({api_key: secret, fallback_key: True})
                self.assertTrue(saved["reloaded"])
                self.assertEqual([], saved["restart_required"])
                self.assertEqual(secret, extract_link.EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY)
                self.assertTrue(extract_link.EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED)
                metadata = {item["key"]: item for item in config_editor.get_config()}
                key_metadata = metadata[api_key]
                self.assertEqual("XXSYUN API Key", key_metadata["label"])
                self.assertTrue(key_metadata["configured"])
                self.assertTrue(key_metadata["secret"])
                self.assertEqual("", key_metadata["value"])
                self.assertEqual("", key_metadata["configured_value"])
                self.assertNotIn("default", key_metadata)
                self.assertNotIn(secret, json.dumps(metadata, ensure_ascii=False))
                self.assertNotIn(api_key, non_sensitive_snapshot().values)
                self.assertTrue(non_sensitive_snapshot()[fallback_key])

                config_editor.update_config({api_key: "", fallback_key: False})
                self.assertEqual("", extract_link.EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY)
                self.assertFalse(extract_link.EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED)
                persisted = env_loader.read_env_file()
                self.assertEqual("", persisted[api_key])
                self.assertEqual("False", persisted[fallback_key])
        finally:
            config.reload_all()

    def test_legacy_payment_cdk_is_editable_but_not_exposed_in_metadata_or_snapshot(self):
        key = "EXTRACT_LINK_LEGACY_PAYMENT_CDK"
        secret = "legacy-payment-schema-test-secret"
        self.assertEqual({key: secret}, validate_config_updates({key: secret}))
        self.assertEqual("", config_schema.schema_default(key))
        self.assertFalse(config_schema.schema_default("EXTRACT_LINK_LEGACY_AUTO_PAYMENT_ENABLED"))
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {key: secret}, clear=True):
            metadata = {item["key"]: item for item in effective_config_metadata()}
            payment = metadata[key]
            self.assertEqual("虾扯蛋链支付扫码 CDK", payment["label"])
            self.assertEqual("config.extract_link", CONFIG_SCHEMA[key].module)
            self.assertEqual("提链", payment["group"])
            self.assertEqual("str", payment["type"])
            self.assertEqual("safe", payment["hot_edit"])
            self.assertTrue(payment["secret"])
            self.assertTrue(payment["configured"])
            self.assertEqual("", payment["value"])
            self.assertEqual("", payment["configured_value"])
            self.assertNotIn("default", payment)
            self.assertNotIn(key, non_sensitive_snapshot().values)
            self.assertNotIn(secret, json.dumps(metadata, ensure_ascii=False))

    def test_legacy_payment_cdk_hot_save_and_clear_preserves_extract_cdk(self):
        from config import extract_link

        extract_key = "EXTRACT_LINK_CDK"
        payment_key = "EXTRACT_LINK_LEGACY_PAYMENT_CDK"
        extract_secret = "legacy-extract-save-test-secret"
        payment_secret = "legacy-payment-save-test-secret"
        fd, raw_path = tempfile.mkstemp(prefix="turb-config-legacy-payment-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        try:
            with patch.object(env_loader, "_ENV_PATH", path), patch.object(
                config_schema, "_PUBLISHED_SNAPSHOT", None
            ), patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
                saved = config_editor.update_config({extract_key: extract_secret, payment_key: payment_secret})
                self.assertTrue(saved["reloaded"])
                self.assertEqual([], saved["restart_required"])
                self.assertEqual(extract_secret, extract_link.EXTRACT_LINK_CDK)
                self.assertEqual(payment_secret, extract_link.EXTRACT_LINK_LEGACY_PAYMENT_CDK)
                persisted = env_loader.read_env_file()
                self.assertEqual(payment_secret, persisted[payment_key])

                cleared = config_editor.update_config({payment_key: ""})
                self.assertTrue(cleared["reloaded"])
                self.assertEqual("", extract_link.EXTRACT_LINK_LEGACY_PAYMENT_CDK)
                self.assertEqual(extract_secret, extract_link.EXTRACT_LINK_CDK)
                persisted = env_loader.read_env_file()
                self.assertEqual("", persisted[payment_key])
                self.assertEqual(extract_secret, persisted[extract_key])
                metadata = {item["key"]: item for item in config_editor.get_config()}
                self.assertFalse(metadata[payment_key]["configured"])
                self.assertTrue(metadata[extract_key]["configured"])
        finally:
            config.reload_all()

    def test_huanguang_payment_cdk_is_separate_sensitive_configuration(self):
        key = "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK"
        secret = "huanguang-payment-schema-test-secret"
        self.assertEqual({key: secret}, validate_config_updates({key: secret}))
        self.assertEqual("", validate_value(key, ""))
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {key: secret}, clear=True):
            metadata = {item["key"]: item for item in effective_config_metadata()}
            payment = metadata[key]
            self.assertEqual("幻光支付扫码 CDK", payment["label"])
            self.assertEqual("幻光提链 CDK", metadata["EXTRACT_LINK_HUANGUANG_CDK"]["label"])
            self.assertEqual("提链", payment["group"])
            self.assertEqual("str", payment["type"])
            self.assertEqual("safe", payment["hot_edit"])
            self.assertTrue(payment["secret"])
            self.assertTrue(payment["configured"])
            self.assertEqual("", payment["value"])
            self.assertEqual("", payment["configured_value"])
            self.assertNotIn("default", payment)
            self.assertNotIn(key, non_sensitive_snapshot().values)
            self.assertNotIn(secret, json.dumps(metadata, ensure_ascii=False))

    def test_huanguang_payment_cdk_save_and_clear_preserves_extract_cdk(self):
        from config import extract_link

        extract_key = "EXTRACT_LINK_HUANGUANG_CDK"
        payment_key = "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK"
        extract_secret = "huanguang-extract-save-test-secret"
        payment_secret = "huanguang-payment-save-test-secret"
        fd, raw_path = tempfile.mkstemp(prefix="turb-config-huanguang-payment-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        try:
            with patch.object(env_loader, "_ENV_PATH", path), patch.object(
                config_schema, "_PUBLISHED_SNAPSHOT", None
            ), patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
                saved = config_editor.update_config({extract_key: extract_secret, payment_key: payment_secret})
                self.assertTrue(saved["reloaded"])
                self.assertEqual([], saved["restart_required"])
                self.assertEqual(extract_secret, extract_link.EXTRACT_LINK_HUANGUANG_CDK)
                self.assertEqual(payment_secret, extract_link.EXTRACT_LINK_HUANGUANG_PAYMENT_CDK)
                persisted = env_loader.read_env_file()
                self.assertEqual(payment_secret, persisted[payment_key])

                cleared = config_editor.update_config({payment_key: ""})
                self.assertTrue(cleared["reloaded"])
                self.assertEqual("", extract_link.EXTRACT_LINK_HUANGUANG_PAYMENT_CDK)
                self.assertEqual(extract_secret, extract_link.EXTRACT_LINK_HUANGUANG_CDK)
                persisted = env_loader.read_env_file()
                self.assertEqual("", persisted[payment_key])
                self.assertEqual(extract_secret, persisted[extract_key])
                metadata = {item["key"]: item for item in config_editor.get_config()}
                self.assertFalse(metadata[payment_key]["configured"])
                self.assertTrue(metadata[extract_key]["configured"])
                self.assertNotIn(payment_key, non_sensitive_snapshot().values)
        finally:
            config.reload_all()

    def test_huanguang_proxy_candidates_accept_full_urls_and_empty_lists(self):
        candidates = [
            "http://proxy.example.test:8080",
            "https://user:password@secure-proxy.example.test:443",
            "socks5://proxy.example.test:1080",
            "socks5h://user:password@remote-dns.example.test:1080",
        ]
        for key in (
            "EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES",
            "EXTRACT_LINK_HUANGUANG_EXIT_PROXIES",
        ):
            with self.subTest(key=key):
                self.assertEqual({key: candidates}, validate_config_updates({key: "\n".join(candidates)}))
                self.assertEqual({key: []}, validate_config_updates({key: ""}))
                field = CONFIG_SCHEMA[key]
                self.assertEqual("提链", field.group)
                self.assertEqual("config.extract_link", field.module)
                self.assertEqual("list_str_multiline", field.type)
                self.assertEqual([], field.default)
                self.assertTrue(field.secret)
                self.assertEqual("safe", field.hot_edit)

    def test_huanguang_proxy_candidates_report_invalid_line_without_credentials(self):
        for key in (
            "EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES",
            "EXTRACT_LINK_HUANGUANG_EXIT_PROXIES",
        ):
            for invalid_address in (
                "ftp://secret-user:secret-password@proxy.example.test:8080",
                "socks5://secret-user:secret-password@proxy.example.test",
                "http://secret-user:secret-password@proxy.example.test:99999",
            ):
                with self.subTest(key=key):
                    with self.assertRaises(ConfigValidationError) as caught:
                        validate_config_updates({key: ["https://proxy.example.test:443", invalid_address]})
                    message = caught.exception.errors[key]
                    self.assertIn("第 2 条", message)
                    self.assertIn("协议、主机和有效端口", message)
                    self.assertNotIn("secret-user", message)
                    self.assertNotIn("secret-password", message)
                    self.assertNotIn(invalid_address, message)

    def test_huanguang_proxy_candidates_limit_unique_entries_to_500(self):
        candidates = [f"https://proxy-{index}.example.test:443" for index in range(500)]
        for key in (
            "EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES",
            "EXTRACT_LINK_HUANGUANG_EXIT_PROXIES",
        ):
            with self.subTest(key=key):
                self.assertEqual(candidates, validate_value(key, candidates + [candidates[0]]))
                with self.assertRaises(ConfigValidationError) as caught:
                    validate_value(key, candidates + ["https://extra-proxy.example.test:443"])
                self.assertIn("500", caught.exception.errors[key])
                self.assertNotIn("extra-proxy", str(caught.exception))

    def test_huanguang_proxy_candidates_are_hidden_from_metadata_and_snapshots(self):
        keys = (
            "EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES",
            "EXTRACT_LINK_HUANGUANG_EXIT_PROXIES",
        )
        secret = "https://user:huanguang-proxy-test-secret@proxy.example.test:443"
        values = {key: secret for key in keys}
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, values, clear=True):
            metadata = {item["key"]: item for item in effective_config_metadata()}
            snapshot = non_sensitive_snapshot()
            for key in keys:
                self.assertEqual("", metadata[key]["value"])
                self.assertEqual("", metadata[key]["configured_value"])
                self.assertTrue(metadata[key]["configured"])
                self.assertNotIn("default", metadata[key])
                self.assertNotIn(key, snapshot.values)
            self.assertNotIn(secret, json.dumps(metadata, ensure_ascii=False))
            self.assertNotIn(secret, json.dumps(snapshot.as_dict(), ensure_ascii=False))

        empty = config_schema.resolve_config({key: "" for key in keys}, strict=True)
        for key in keys:
            self.assertEqual([], empty[key].value)
            self.assertEqual("env", empty[key].source)
            self.assertFalse(empty[key].configured)

    def test_huanguang_proxy_candidates_save_clear_and_hot_reload(self):
        from config import extract_link

        keys = (
            "EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES",
            "EXTRACT_LINK_HUANGUANG_EXIT_PROXIES",
        )
        candidates = ["https://user:save-test-secret@proxy.example.test:443", "socks5h://proxy.example.test:1080"]
        fd, raw_path = tempfile.mkstemp(prefix="turb-config-huanguang-proxies-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        try:
            with patch.object(env_loader, "_ENV_PATH", path), patch.object(
                config_schema, "_PUBLISHED_SNAPSHOT", None
            ), patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
                saved = config_editor.update_config({key: candidates for key in keys})
                self.assertTrue(saved["reloaded"])
                self.assertEqual([], saved["restart_required"])
                for key in keys:
                    self.assertEqual(candidates, getattr(extract_link, key))
                    self.assertNotIn(key, non_sensitive_snapshot().values)

                cleared = config_editor.update_config({key: [] for key in keys})
                self.assertTrue(cleared["reloaded"])
                persisted = env_loader.read_env_file()
                metadata = {item["key"]: item for item in config_editor.get_config()}
                for key in keys:
                    self.assertEqual("[]", persisted[key])
                    self.assertEqual([], getattr(extract_link, key))
                    self.assertFalse(metadata[key]["configured"])
                    self.assertNotIn(key, non_sensitive_snapshot().values)
        finally:
            config.reload_all()

    def test_protocol_oss_2_is_an_editable_registration_choice(self):
        self.assertEqual(validate_config_updates({"REGISTRATION_DRIVER": "protocol_oss_2"}), {
            "REGISTRATION_DRIVER": "protocol_oss_2",
        })
        field = CONFIG_SCHEMA["REGISTRATION_DRIVER"]
        self.assertEqual({item.value: item.label for item in field.options}["protocol_oss_2"], "开源protocol-2")

    def test_open_source_roxy_is_an_editable_registration_choice(self):
        self.assertEqual(validate_config_updates({"REGISTRATION_DRIVER": "roxy_oss"}), {
            "REGISTRATION_DRIVER": "roxy_oss",
        })
        field = CONFIG_SCHEMA["REGISTRATION_DRIVER"]
        options = {item.value: item.label for item in field.options}
        self.assertEqual(options["roxy_oss"], "开源 Roxy")
        self.assertEqual(options["roxy"], "本地 Roxy")

    def test_schema_owns_unique_fields_and_editor_consumes_it(self):
        fields = CONFIG_SCHEMA.fields
        self.assertEqual(len(fields), len({field.key for field in fields}))
        self.assertTrue(fields)
        canonical = config_schema._legacy_fields()
        self.assertEqual(len(canonical), len({field["key"] for field in canonical}))
        self.assertEqual(
            {field.key for field in CONFIG_SCHEMA.editable_fields},
            {field["key"] for field in config_editor.EDITABLE_FIELDS},
        )
        editor_keys = [field["key"] for field in config_editor.EDITABLE_FIELDS]
        self.assertEqual(len(editor_keys), len(set(editor_keys)))
        runtime_keys = [field["key"] for field in effective_config_metadata()]
        self.assertEqual(editor_keys, runtime_keys)
        schema_source = Path(config_schema.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from webui", schema_source)

        for field in fields:
            with self.subTest(key=field.key):
                self.assertTrue(field.type)
                self.assertIsNotNone(field.file)
                self.assertTrue(field.module)
                self.assertIsInstance(field.default, (str, int, float, bool, list))
                self.assertIsInstance(field.options, tuple)
                self.assertIsInstance(field.range, dict)
                self.assertIsInstance(field.secret, bool)
                self.assertIsInstance(field.aliases, Mapping)
                self.assertIn(field.hot_edit, {"safe", "restart"})
                metadata = field.metadata()
                self.assertIn("default", metadata)
                self.assertEqual(field.module, metadata["module"])
                self.assertIn("type", metadata)
                self.assertIn("secret", metadata)
                self.assertIn("hot_edit", metadata)

    def test_codex_refresh_settings_have_one_complete_scheduled_group(self):
        """定时刷新参数集中维护，开关与调度预算不会散落到其他页面。"""
        refresh_keys = {
            "CODEX_TOKEN_AUTO_REFRESH_ENABLED", "CODEX_TOKEN_REFRESH_BEFORE_HOURS",
            "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", "CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS",
            "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", "CODEX_TOKEN_AUTO_SYNC_SUB2API",
        }
        metadata = CONFIG_SCHEMA.editor_metadata()
        for key in refresh_keys:
            entries = [field for field in metadata if field["key"] == key]
            self.assertEqual(len(entries), 1, key)
            self.assertEqual(entries[0]["group"], "定时任务", key)

    def test_unused_cloudflare_paths_are_removed_from_config_contract(self):
        """不再开放客户端从未调用的预留接口，现有 .env 无需改写。"""
        from config import email

        removed = {"CLOUDFLARE_PATH_DOMAINS", "CLOUDFLARE_PATH_TOKEN"}
        for key in removed:
            self.assertNotIn(key, CONFIG_SCHEMA)
            self.assertNotIn(key, config_schema.DEFAULTS)
            self.assertNotIn(key, config.__all__)
            self.assertFalse(hasattr(email, key))
            self.assertFalse(hasattr(config, key))
        with self.assertRaises(ConfigValidationError):
            validate_config_updates({"CLOUDFLARE_PATH_TOKEN": "/unused"})
        for key in ("CLOUDFLARE_PATH_ACCOUNTS", "CLOUDFLARE_PATH_MESSAGES", "CLOUDFLARE_DEFAULT_DOMAINS"):
            self.assertIn(key, CONFIG_SCHEMA)

    def test_schema_defaults_match_loaded_module_defaults(self):
        for field in CONFIG_SCHEMA.fields:
            module = __import__(field.module, fromlist=[field.key])
            with self.subTest(key=field.key):
                self.assertTrue(
                    hasattr(module, field.key),
                    f"schema field {field.key} missing from {field.module}",
                )
                self.assertEqual(field.default, getattr(module, field.key))

    def test_every_editable_module_is_in_reload_boundary(self):
        reloadable = set(config._RELOADABLE_SUBMODULES)
        self.assertTrue({
            field.module
            for field in CONFIG_SCHEMA.fields
            if field.module
        }.issubset(reloadable))

    def test_shared_account_concurrency_accepts_positive_integers_without_fixed_upper_bound(self):
        key = "ACCOUNT_BATCH_WORKERS"
        for workers in (1, 50, 51, 100, 1000, 1000000):
            with self.subTest(workers=workers):
                self.assertEqual({key: workers}, validate_config_updates({key: workers}))
        for invalid in (0, -1, True, None, 1.5, "1.5", "abc"):
            with self.subTest(invalid=invalid), self.assertRaises(ConfigValidationError):
                validate_config_updates({key: invalid})
        metadata = CONFIG_SCHEMA[key].metadata()
        self.assertEqual({"min": 1}, metadata["range"])
        self.assertNotIn("max", metadata)
        self.assertEqual(3, metadata["default"])

    def test_extract_concurrency_accepts_fifty_and_rejects_fifty_one(self):
        keys = (
            "EXTRACT_LINK_BATCH_WORKERS",
            "EXTRACT_LINK_LEGACY_CONCURRENCY",
            "EXTRACT_LINK_LUMEN_FLOW_CONCURRENCY",
            "EXTRACT_LINK_HUANGUANG_CONCURRENCY",
        )
        values = {key: 50 for key in keys}
        self.assertEqual(values, validate_config_updates(values))
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(1, validate_value(key, 1))
                with self.assertRaises(ConfigValidationError) as caught:
                    validate_config_updates({key: 51})
                self.assertIn(key, caught.exception.errors)
                self.assertIn("50", caught.exception.errors[key])

    def test_invalid_range_option_unknown_and_cross_field_updates_are_rejected(self):
        with self.assertRaises(ConfigValidationError):
            validate_value("ACCOUNT_BATCH_WORKERS", 0)
        with self.assertRaises(ConfigValidationError):
            validate_value("REGISTRATION_PROXY_MODE", "not-a-route")
        with self.assertRaises(ConfigValidationError):
            validate_value("OPENAI_PROTOCOL_VERSION", "explicit-test-v2")
        self.assertEqual("v2", validate_value("OPENAI_PROTOCOL_VERSION", "v2"))
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

    def test_vietnam_locale_profile_is_available_to_the_config_ui(self):
        field = CONFIG_SCHEMA["BROWSER_LOCALE_PROFILE"]

        self.assertIn(
            ("vn", "越南"),
            tuple((option.value, option.label) for option in field.options),
        )
        self.assertEqual("vn", validate_value("BROWSER_LOCALE_PROFILE", "vn"))

    def test_every_schema_default_is_legal_for_its_declared_type_and_options(self):
        for field in CONFIG_SCHEMA.fields:
            with self.subTest(key=field.key):
                self.assertEqual(field.default, validate_value(field.key, field.default))

    def test_effective_metadata_reports_default_and_env_sources(self):
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {}, clear=True):
            defaults = {
                item["key"]: item
                for item in effective_config_metadata()
            }
            self.assertEqual(3, defaults["ACCOUNT_BATCH_WORKERS"]["value"])
            self.assertEqual("default", defaults["ACCOUNT_BATCH_WORKERS"]["source"])

        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {"ACCOUNT_BATCH_WORKERS": "7"}, clear=True):
            values = {
                item["key"]: item
                for item in effective_config_metadata()
            }
            self.assertEqual(7, values["ACCOUNT_BATCH_WORKERS"]["value"])
            self.assertEqual("env", values["ACCOUNT_BATCH_WORKERS"]["source"])
            self.assertEqual("ACCOUNT_BATCH_WORKERS", values["ACCOUNT_BATCH_WORKERS"]["source_key"])

    def test_real_protocol_module_accepts_only_schema_legal_override(self):
        from config import openai_protocol

        old_loaded = env_loader._LOADED
        env_loader._LOADED = True
        try:
            with patch.dict(os.environ, {"OPENAI_PROTOCOL_VERSION": "v2"}, clear=False):
                reloaded = importlib.reload(openai_protocol)
                self.assertEqual("v2", reloaded.OPENAI_PROTOCOL_VERSION)
        finally:
            env_loader._LOADED = old_loaded
            importlib.reload(openai_protocol)

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
        ), patch.dict(os.environ, {"ACCOUNT_BATCH_WORKERS": "9"}, clear=True):
            candidate = build_non_sensitive_snapshot(strict=True)
            published = publish_config_snapshot(candidate)
            current = non_sensitive_snapshot()

            self.assertIs(published, current)
            self.assertEqual(0, current.revision)
            self.assertEqual(9, current["ACCOUNT_BATCH_WORKERS"])
            self.assertEqual("env", current.sources["ACCOUNT_BATCH_WORKERS"])
            self.assertNotIn("PROXY_POOL", current.values)
            with self.assertRaises(TypeError):
                current.values["ACCOUNT_BATCH_WORKERS"] = 1
            with self.assertRaises(TypeError):
                current.sources["ACCOUNT_BATCH_WORKERS"] = "default"
            with self.assertRaises(AttributeError):
                current.revision = 99

    def test_config_metadata_distinguishes_published_and_pending_environment(self):
        with patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None), patch(
            "config.env_loader.read_env_file", return_value={}
        ), patch.dict(os.environ, {"ACCOUNT_BATCH_WORKERS": "3"}, clear=True):
            initial = {
                item["key"]: item
                for item in effective_config_metadata()
            }["ACCOUNT_BATCH_WORKERS"]
            self.assertEqual(3, initial["value"])
            self.assertEqual(3, initial["configured_value"])
            self.assertFalse(initial["pending_reload"])

            os.environ["ACCOUNT_BATCH_WORKERS"] = "9"
            pending = {
                item["key"]: item
                for item in effective_config_metadata()
            }["ACCOUNT_BATCH_WORKERS"]

        self.assertEqual(3, pending["published_effective_value"])
        self.assertEqual("env", pending["published_effective_source"])
        self.assertEqual("ACCOUNT_BATCH_WORKERS", pending["source_key"])
        self.assertEqual("ACCOUNT_BATCH_WORKERS", pending["configured_source_key"])
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
                or field.key in {"PROXY_1024_API_URL", "PLAN_CHECK_PROXY", "ACCOUNT_ACTION_PROXY"}
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
                config_editor.update_config({"ACCOUNT_BATCH_WORKERS": 4})
            self.assertFalse(path.exists())
            self.assertNotIn("ACCOUNT_BATCH_WORKERS", os.environ)
            self.assertEqual("keep", os.environ["UNRELATED_THREAD_ENV"])

    def test_enum_none_survives_save_reload_and_metadata(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-config-enum-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        try:
            with patch.object(env_loader, "_ENV_PATH", path), patch.object(
                config_schema, "_PUBLISHED_SNAPSHOT", None
            ), patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
                result = config_editor.update_config({
                    "REGISTRATION_PROXY_MODE": "none",
                    "CLOUDFLARE_AUTH_MODE": "NONE",
                    "PROXY_1024_REGION": "",
                    "REGISTER_NAME": "-",
                })
                self.assertTrue(result["reloaded"])
                saved = env_loader.read_env_file()
                metadata = {item["key"]: item for item in config_editor.get_config()}
                for key in ("REGISTRATION_PROXY_MODE", "CLOUDFLARE_AUTH_MODE"):
                    self.assertEqual("none", saved[key])
                    self.assertEqual("none", metadata[key]["value"])
                    self.assertFalse(metadata[key]["pending_reload"])
                    module = importlib.import_module(CONFIG_SCHEMA[key].module)
                    self.assertEqual("none", getattr(module, key))
                self.assertEqual("", saved["PROXY_1024_REGION"])
                self.assertEqual("", saved["REGISTER_NAME"])
        finally:
            config.reload_all()

    def test_full_candidate_is_validated_before_env_write(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-config-preflight-")
        os.close(fd)
        path = Path(raw_path)
        path.write_text("ACCOUNT_BATCH_WORKERS=0\n", encoding="utf-8")
        self.addCleanup(lambda: path.unlink() if path.exists() else None)

        with patch.object(env_loader, "_ENV_PATH", path), patch.dict(
            os.environ, {}, clear=True
        ):
            with self.assertRaises(ConfigValidationError):
                config_editor.update_config({"OTP_MAX_WAIT": 600})
            self.assertEqual("ACCOUNT_BATCH_WORKERS=0\n", path.read_text(encoding="utf-8"))
            self.assertNotIn("OTP_MAX_WAIT", os.environ)

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

    def test_dotenv_disabled_explicit_write_does_not_read_file_and_updates_process(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-dotenv-write-disabled-")
        os.close(fd)
        path = Path(raw_path)
        path.write_text("DOTENV_SHOULD_NOT_LOAD=secret\n", encoding="utf-8")
        self.addCleanup(lambda: path.unlink() if path.exists() else None)

        old_loaded = env_loader._LOADED
        try:
            env_loader._LOADED = False
            with patch.object(env_loader, "_ENV_PATH", path), patch.object(
                env_loader, "read_env_file", side_effect=AssertionError("dotenv file was read")
            ), patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
                env_loader.write_env_values({"ACCOUNT_BATCH_WORKERS": "7"})
                self.assertEqual("7", os.environ["ACCOUNT_BATCH_WORKERS"])
                self.assertNotIn("DOTENV_SHOULD_NOT_LOAD", os.environ)
        finally:
            env_loader._LOADED = old_loaded

    def test_env_example_only_contains_bootstrap_editable_fields(self):
        example = Path(".env.example").read_text(encoding="utf-8")
        generated = config_schema.render_env_example_section()
        for field in CONFIG_SCHEMA.editable_fields:
            with self.subTest(key=field.key):
                if field.storage == "env":
                    self.assertRegex(example, rf"(?m)^{field.key}=")
                    self.assertRegex(generated, rf"(?m)^{field.key}=")
                else:
                    self.assertNotRegex(example, rf"(?m)^{field.key}=")
                    self.assertNotRegex(generated, rf"(?m)^{field.key}=")


if __name__ == "__main__":
    unittest.main()
