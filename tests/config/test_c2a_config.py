"""C2A 手动导入和巡检配置契约。"""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import config
from config import env_loader
from config import schema
from config.env_loader import SECRET_ENV_KEYS
from webui import config_editor


class C2AConfigTests(unittest.TestCase):
    def test_c2a_fields_are_editable_runtime_configuration(self):
        expected = {
            "C2A_API_BASE": ("", "str", False, "database"),
            "C2A_API_KEY": ("", "str", True, "env"),
            "C2A_API_TIMEOUT": (20, "int", False, "database"),
            "C2A_MONITOR_ENABLED": (False, "bool", False, "database"),
            "C2A_MONITOR_INTERVAL_SECONDS": (300, "int", False, "database"),
            "C2A_MONITOR_COOLDOWN_SECONDS": (300, "int", False, "database"),
            "C2A_MONITOR_MAX_PER_CYCLE": (500, "int", False, "database"),
        }
        fields = {field["key"]: field for field in config_editor.EDITABLE_FIELDS}
        for key, (default, value_type, secret, storage) in expected.items():
            with self.subTest(key=key):
                field = schema.CONFIG_SCHEMA[key]
                self.assertEqual(default, schema.schema_default(key))
                self.assertEqual("config.c2a", field.module)
                self.assertEqual("C2A", field.group)
                self.assertEqual(value_type, field.type)
                self.assertEqual(secret, field.secret)
                self.assertEqual(storage, field.storage)
                self.assertEqual("restart" if key == "C2A_API_KEY" else "safe", field.hot_edit)
                self.assertEqual(key, fields[key]["key"])
                self.assertIn(key, config.__all__)

    def test_key_is_registered_as_secret_and_timeout_is_bounded(self):
        self.assertEqual("C2A（ChatGPT2API）管理员 Key", SECRET_ENV_KEYS["C2A_API_KEY"])
        for value in (1, 20, 3600):
            with self.subTest(value=value):
                self.assertEqual(value, schema.validate_value("C2A_API_TIMEOUT", value))
        for value in (0, 3601, True, "invalid"):
            with self.subTest(value=value), self.assertRaises(schema.ConfigValidationError):
                schema.validate_value("C2A_API_TIMEOUT", value)

    def test_key_change_reports_worker_restart_needed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            try:
                with patch.object(env_loader, "_ENV_PATH", path), patch.dict(
                    os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True
                ):
                    saved = config_editor.update_config({"C2A_API_KEY": "fixture-only"})
                    self.assertEqual(["C2A_API_KEY"], saved["restart_required"])
            finally:
                config.reload_all()

    def test_monitor_batch_size_has_inclusive_limits(self):
        key = "C2A_MONITOR_MAX_PER_CYCLE"
        for value in (1, 500, 5000):
            with self.subTest(value=value):
                self.assertEqual(value, schema.validate_value(key, value))
        for value in (0, 5001, True, "invalid"):
            with self.subTest(value=value), self.assertRaises(schema.ConfigValidationError):
                schema.validate_value(key, value)


if __name__ == "__main__":
    unittest.main()
