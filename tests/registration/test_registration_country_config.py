"""注册国家配置与历史国家迁移共用中央解析契约。"""
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import config
from config import env_loader, register, runtime, schema
from webui import config_editor


class RegistrationCountryConfigTests(unittest.TestCase):
    def test_registration_country_has_independent_runtime_export_and_country_metadata(self):
        field = schema.CONFIG_SCHEMA["REGISTRATION_COUNTRY"]
        self.assertEqual("JP", field.default)
        self.assertEqual("config.register", field.module)
        self.assertEqual("注册主链路", field.group)
        self.assertEqual("注册国家", field.label)
        self.assertEqual("JP", register.REGISTRATION_COUNTRY)
        self.assertIn("REGISTRATION_COUNTRY", config.__all__)
        self.assertEqual(register.REGISTRATION_COUNTRY, config.REGISTRATION_COUNTRY)
        self.assertIn("NA", field.metadata()["country_codes"])
        self.assertEqual(
            schema.CONFIG_SCHEMA["PROXY_POOL_DEFAULT_COUNTRY"].metadata()["country_codes"],
            field.metadata()["country_codes"],
        )
        template = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
        self.assertNotIn("REGISTRATION_COUNTRY=", template)
        self.assertEqual("database", field.storage)

    def test_registration_country_accepts_iso_codes_including_namibia(self):
        for value, expected in (("jp", "JP"), (" US ", "US"), ("na", "NA")):
            with self.subTest(value=value):
                self.assertEqual(expected, schema.validate_value("REGISTRATION_COUNTRY", value))
        for value in ("", "Rand", "XX", "Japan", ["JP"]):
            with self.subTest(value=value), self.assertRaises(schema.ConfigValidationError):
                schema.validate_value("REGISTRATION_COUNTRY", value)
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
            self.assertEqual({"REGISTRATION_COUNTRY": "NA"}, schema.validate_config_updates({"REGISTRATION_COUNTRY": "na"}))

    def test_missing_registration_country_migrates_old_effective_country_consistently(self):
        cases = (
            ({}, "JP", None),
            ({"PROXY_POOL_DEFAULT_COUNTRY": "us", "PROXY_1024_REGION": "GB", "PROXY_1024_API_URL": "https://example.test/api?region=VN"}, "US", "PROXY_POOL_DEFAULT_COUNTRY"),
            ({"PROXY_1024_REGION": "gb", "PROXY_1024_API_URL": "https://example.test/api?region=VN"}, "GB", "PROXY_1024_REGION"),
            ({"PROXY_1024_API_URL": "https://example.test/api?region=vn"}, "VN", "PROXY_1024_API_URL"),
            ({"PROXY_POOL_DEFAULT_COUNTRY": "na"}, "NA", "PROXY_POOL_DEFAULT_COUNTRY"),
        )
        for values, country, source_key in cases:
            with self.subTest(country=country, source_key=source_key):
                resolved = schema.resolve_config(values, strict=True)["REGISTRATION_COUNTRY"]
                self.assertEqual(country, resolved.value)
                self.assertEqual(source_key, resolved.source_key)
                snapshot = schema.build_non_sensitive_snapshot(values)
                self.assertEqual(country, snapshot["REGISTRATION_COUNTRY"])
                namespace = {"__name__": "config.register", "REGISTRATION_COUNTRY": "JP"}
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", **values}, clear=True):
                    env_loader.apply_env_overrides(namespace)
                self.assertEqual(country, namespace["REGISTRATION_COUNTRY"])

    def test_explicit_registration_country_stays_independent_of_pool_default(self):
        for pool_country in ("US", "GB", "VN"):
            values = {"REGISTRATION_COUNTRY": "na", "PROXY_POOL_DEFAULT_COUNTRY": pool_country, "PROXY_1024_REGION": "JP"}
            with self.subTest(pool_country=pool_country):
                resolved = schema.resolve_config(values, strict=True)
                self.assertEqual("NA", resolved["REGISTRATION_COUNTRY"].value)
                self.assertEqual("REGISTRATION_COUNTRY", resolved["REGISTRATION_COUNTRY"].source_key)
                self.assertEqual(pool_country, resolved["PROXY_POOL_DEFAULT_COUNTRY"].value)
                namespace = {"__name__": "config.register", "REGISTRATION_COUNTRY": "JP"}
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", **values}, clear=True):
                    env_loader.apply_env_overrides(namespace)
                self.assertEqual("NA", namespace["REGISTRATION_COUNTRY"])

    def test_migration_preserves_the_actual_old_default_even_with_invalid_old_values(self):
        cases = (
            {"PROXY_POOL_DEFAULT_COUNTRY": "XX", "PROXY_1024_REGION": "GB"},
            {"PROXY_POOL_DEFAULT_COUNTRY": "", "PROXY_1024_REGION": "GB"},
            {"PROXY_1024_REGION": "Rand", "PROXY_1024_API_URL": "https://example.test/api?region=VN"},
        )
        for values in cases:
            with self.subTest(values=values):
                resolved = schema.resolve_config(values)
                self.assertEqual("JP", resolved["REGISTRATION_COUNTRY"].value)
                self.assertEqual(resolved["PROXY_POOL_DEFAULT_COUNTRY"].value, resolved["REGISTRATION_COUNTRY"].value)
                namespace = {"__name__": "config.register", "REGISTRATION_COUNTRY": "JP"}
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", **values}, clear=True):
                    env_loader.apply_env_overrides(namespace)
                self.assertEqual("JP", namespace["REGISTRATION_COUNTRY"])

    def test_explicit_empty_or_invalid_registration_country_never_uses_pool_default(self):
        field = schema.CONFIG_SCHEMA["REGISTRATION_COUNTRY"]
        for value in ("", "Rand"):
            with self.subTest(value=value):
                values = {"REGISTRATION_COUNTRY": value, "PROXY_POOL_DEFAULT_COUNTRY": "US"}
                resolved = schema.resolve_field(field, values)
                self.assertEqual("JP", resolved.value)
                self.assertEqual("REGISTRATION_COUNTRY", resolved.source_key)
                namespace = {"__name__": "config.register", "REGISTRATION_COUNTRY": "JP"}
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", **values}, clear=True):
                    env_loader.apply_env_overrides(namespace)
                self.assertEqual("JP", namespace["REGISTRATION_COUNTRY"])


class RegistrationCountrySaveMigrationTests(unittest.TestCase):
    @contextmanager
    def temporary_editor_environment(self, text):
        from tests.config.test_runtime_config_loading import _Repository
        fd, raw_path = tempfile.mkstemp(prefix="turb-registration-country-")
        os.close(fd)
        path = Path(raw_path)
        path.write_text(text, encoding="utf-8")
        with patch.object(env_loader, "_ENV_PATH", path):
            repository = _Repository(env_loader.read_env_file())
        try:
            with patch.object(env_loader, "_ENV_PATH", path), patch.object(
                schema, "_PUBLISHED_SNAPSHOT", None
            ), patch.object(config, "reload_all", return_value=[]) as reload_all, patch.dict(
                os.environ, {"PYTHON_DOTENV_DISABLED": "0", "UNRELATED_THREAD_ENV": "keep"}, clear=True
            ), patch.object(runtime, "_repository", return_value=repository), patch.object(
                runtime, "_automatic_database_allowed", return_value=True
            ):
                runtime.reset_cache()
                yield path, reload_all
        finally:
            runtime.reset_cache()
            path.unlink(missing_ok=True)

    def test_first_pool_country_change_freezes_previous_registration_country_in_same_save(self):
        with self.temporary_editor_environment("PROXY_POOL_DEFAULT_COUNTRY=US\n"):
            result = config_editor.update_config({"PROXY_POOL_DEFAULT_COUNTRY": "GB"})
            saved = runtime.read_persisted_values()
            self.assertEqual({"PROXY_POOL_DEFAULT_COUNTRY", "REGISTRATION_COUNTRY"}, set(result["updated"]))
            self.assertEqual("GB", saved["PROXY_POOL_DEFAULT_COUNTRY"])
            self.assertEqual("US", saved["REGISTRATION_COUNTRY"])
            self.assertEqual("US", os.environ["REGISTRATION_COUNTRY"])
            self.assertEqual("US", schema.resolve_config(saved, strict=True)["REGISTRATION_COUNTRY"].value)

    def test_explicit_registration_country_is_never_overwritten_by_pool_change(self):
        with self.temporary_editor_environment("REGISTRATION_COUNTRY=NA\nPROXY_POOL_DEFAULT_COUNTRY=US\n"):
            result = config_editor.update_config({"PROXY_POOL_DEFAULT_COUNTRY": "GB"})
            saved = runtime.read_persisted_values()
            self.assertEqual(["PROXY_POOL_DEFAULT_COUNTRY"], result["updated"])
            self.assertEqual("NA", saved["REGISTRATION_COUNTRY"])

    def test_explicit_registration_update_in_same_request_wins_over_migration(self):
        with self.temporary_editor_environment("PROXY_POOL_DEFAULT_COUNTRY=US\n"):
            config_editor.update_config({"PROXY_POOL_DEFAULT_COUNTRY": "GB", "REGISTRATION_COUNTRY": "na"})
            saved = runtime.read_persisted_values()
            self.assertEqual("GB", saved["PROXY_POOL_DEFAULT_COUNTRY"])
            self.assertEqual("NA", saved["REGISTRATION_COUNTRY"])

    def test_failed_reload_rolls_back_both_country_fields_and_original_file(self):
        original = "# 保留原文件\nPROXY_POOL_DEFAULT_COUNTRY=US\n"
        with self.temporary_editor_environment(original) as (path, reload_all):
            # 模拟真实保存前已加载的旧环境，失败后应恢复这些值。
            env_loader.load_env(override=True)
            reload_all.side_effect = RuntimeError("模拟重载失败")
            with self.assertRaises(RuntimeError):
                config_editor.update_config({"PROXY_POOL_DEFAULT_COUNTRY": "GB"})
            self.assertEqual(original, path.read_text(encoding="utf-8"))
            self.assertEqual("US", os.environ["PROXY_POOL_DEFAULT_COUNTRY"])
            self.assertNotIn("REGISTRATION_COUNTRY", os.environ)
            self.assertEqual("keep", os.environ["UNRELATED_THREAD_ENV"])

    def test_unrelated_config_change_does_not_persist_a_registration_country(self):
        with self.temporary_editor_environment("PROXY_POOL_DEFAULT_COUNTRY=US\n"):
            result = config_editor.update_config({"ACCOUNT_BATCH_WORKERS": 4})
            self.assertEqual(["ACCOUNT_BATCH_WORKERS"], result["updated"])
            self.assertNotIn("REGISTRATION_COUNTRY", runtime.read_persisted_values())

    def test_old_supplier_country_fields_also_freeze_the_previous_country(self):
        cases = (
            ("PROXY_1024_REGION=US\n", {"PROXY_1024_REGION": "GB"}),
            ("PROXY_1024_API_URL=https://example.test/api?region=US\n", {"PROXY_1024_API_URL": "https://example.test/api?region=GB"}),
        )
        for original, updates in cases:
            with self.subTest(updates=updates), self.temporary_editor_environment(original):
                config_editor.update_config(updates)
                self.assertEqual("US", runtime.read_persisted_values()["REGISTRATION_COUNTRY"])
