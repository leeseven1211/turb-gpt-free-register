"""验证查套餐代理复用配置的编辑入口与热加载。"""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import config
from config import env_loader
from config import proxy as proxy_config
from config import schema
from webui import config_editor


KEY = "PLAN_CHECK_PROXY_ALLOW_REUSE"
LIMIT_KEY = "PLAN_CHECK_PROXY_REUSE_LIMIT"


class PlanProxyConfigTests(unittest.TestCase):
    def test_reuse_limit_has_safe_editable_metadata_and_bounds(self):
        field = schema.CONFIG_SCHEMA[LIMIT_KEY]
        self.assertEqual("int", field.type)
        self.assertEqual(3, field.default)
        self.assertEqual("proxy.py", field.file)
        self.assertEqual("代理与网络", field.group)
        self.assertEqual("查询套餐同一 IP 租用次数上限", field.label)
        self.assertEqual({"min": 1, "max": 100}, field.range)
        self.assertEqual("safe", field.hot_edit)
        self.assertFalse(field.secret)
        self.assertNotIn(LIMIT_KEY, config_editor.RESTART_REQUIRED_KEYS)
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn(LIMIT_KEY, fields)
        self.assertIn("含首次", fields[LIMIT_KEY]["help"])
        self.assertIn("实际出口 IP", fields[LIMIT_KEY]["help"])
        self.assertIn("有效期", fields[LIMIT_KEY]["help"])
        self.assertIn("静态代理池", fields[LIMIT_KEY]["help"])

    def test_reuse_switch_has_safe_editable_metadata(self):
        field = schema.CONFIG_SCHEMA[KEY]
        self.assertEqual("bool", field.type)
        self.assertIs(True, field.default)
        self.assertEqual("proxy.py", field.file)
        self.assertEqual("代理与网络", field.group)
        self.assertEqual("查询套餐允许复用 IP", field.label)
        self.assertEqual("safe", field.hot_edit)
        self.assertFalse(field.secret)
        self.assertNotIn(KEY, config_editor.RESTART_REQUIRED_KEYS)
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn(KEY, fields)
        self.assertIn("1024", fields[KEY]["help"])
        self.assertIn("出口国家", fields[KEY]["help"])
        self.assertIn("静态代理池", fields[KEY]["help"])

    def test_env_bool_override_hot_reloads_module_package_and_snapshot(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-plan-proxy-config-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(path.unlink)

        with (
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True),
            patch.object(env_loader, "_ENV_PATH", path),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        ):
            try:
                config.reload_all()
                before = schema.non_sensitive_snapshot()
                self.assertIs(True, before[KEY])
                for raw, expected in (("False", False), ("True", True)):
                    with self.subTest(raw=raw):
                        path.write_text(f"{KEY}={raw}\n", encoding="utf-8")
                        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "0"}):
                            modules = config.reload_all()
                        self.assertIn("config.proxy", modules)
                        self.assertIs(expected, getattr(proxy_config, KEY))
                        self.assertIs(expected, getattr(config, KEY))
                        self.assertIs(expected, schema.non_sensitive_snapshot()[KEY])
                        self.assertIs(True, before[KEY])
                self.assertIs(True, before[KEY])
                self.assertGreater(schema.non_sensitive_snapshot().revision, before.revision)
            finally:
                os.environ.pop(KEY, None)
                config.reload_all()

    def test_env_reuse_limit_override_hot_reloads_module_package_and_snapshot(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-plan-proxy-limit-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(path.unlink)

        with (
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True),
            patch.object(env_loader, "_ENV_PATH", path),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        ):
            try:
                config.reload_all()
                before = schema.non_sensitive_snapshot()
                self.assertEqual(3, before[LIMIT_KEY])
                path.write_text(f"{LIMIT_KEY}=5\n", encoding="utf-8")
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "0"}):
                    modules = config.reload_all()
                self.assertIn("config.proxy", modules)
                self.assertEqual(5, getattr(proxy_config, LIMIT_KEY))
                self.assertEqual(5, getattr(config, LIMIT_KEY))
                self.assertEqual(5, schema.non_sensitive_snapshot()[LIMIT_KEY])
                self.assertGreater(schema.non_sensitive_snapshot().revision, before.revision)
            finally:
                os.environ.pop(LIMIT_KEY, None)
                config.reload_all()

    def test_webui_save_bool_publishes_effective_value_without_restart(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-plan-proxy-save-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(path.unlink)

        with (
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True),
            patch.object(env_loader, "_ENV_PATH", path),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        ):
            try:
                result = config_editor.update_config({KEY: False})
                self.assertEqual([KEY], result["updated"])
                self.assertTrue(result["reloaded"])
                self.assertEqual([], result["restart_required"])
                self.assertEqual("False", env_loader.read_env_file()[KEY])
                self.assertIs(False, getattr(proxy_config, KEY))
                self.assertIs(False, getattr(config, KEY))
                self.assertIs(False, schema.non_sensitive_snapshot()[KEY])
            finally:
                os.environ.pop(KEY, None)
                config.reload_all()

    def test_webui_save_reuse_limit_publishes_effective_value_without_restart(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-plan-proxy-limit-save-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(path.unlink)

        with (
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True),
            patch.object(env_loader, "_ENV_PATH", path),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        ):
            try:
                result = config_editor.update_config({LIMIT_KEY: 5})
                self.assertEqual([LIMIT_KEY], result["updated"])
                self.assertTrue(result["reloaded"])
                self.assertEqual([], result["restart_required"])
                self.assertEqual("5", env_loader.read_env_file()[LIMIT_KEY])
                self.assertEqual(5, getattr(proxy_config, LIMIT_KEY))
                self.assertEqual(5, getattr(config, LIMIT_KEY))
                self.assertEqual(5, schema.non_sensitive_snapshot()[LIMIT_KEY])
            finally:
                os.environ.pop(LIMIT_KEY, None)
                config.reload_all()

    def test_webui_save_reuse_limit_rejects_values_outside_schema_range(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-plan-proxy-limit-range-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(path.unlink)

        with (
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True),
            patch.object(env_loader, "_ENV_PATH", path),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        ):
            try:
                config.reload_all()
                for value in (0, 101, -1):
                    with self.subTest(value=value):
                        with self.assertRaises(schema.ConfigValidationError) as ctx:
                            config_editor.update_config({LIMIT_KEY: value})
                        self.assertIn(LIMIT_KEY, ctx.exception.errors)
                        self.assertNotIn(LIMIT_KEY, env_loader.read_env_file())
            finally:
                os.environ.pop(LIMIT_KEY, None)
                config.reload_all()


if __name__ == "__main__":
    unittest.main()
