"""C2A 本地 AT 重新导入的运行配置契约。"""
from __future__ import annotations

import unittest

import config
from config import schema
from config.env_loader import SECRET_ENV_KEYS
from webui import config_editor


class C2AConfigTests(unittest.TestCase):
    def test_c2a_fields_are_editable_runtime_configuration(self):
        expected = {
            "C2A_API_BASE": ("", "str", False, "database"),
            "C2A_API_KEY": ("", "str", True, "env"),
            "C2A_API_TIMEOUT": (20, "int", False, "database"),
        }
        fields = {field["key"]: field for field in config_editor.EDITABLE_FIELDS}
        for key, (default, value_type, secret, storage) in expected.items():
            with self.subTest(key=key):
                field = schema.CONFIG_SCHEMA[key]
                self.assertEqual(default, schema.schema_default(key))
                self.assertEqual("config.c2a", field.module)
                self.assertEqual("Codex", field.group)
                self.assertEqual(value_type, field.type)
                self.assertEqual(secret, field.secret)
                self.assertEqual(storage, field.storage)
                self.assertEqual("safe", field.hot_edit)
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


if __name__ == "__main__":
    unittest.main()
