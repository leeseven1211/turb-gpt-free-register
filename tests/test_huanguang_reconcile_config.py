"""幻光自动续查限额的配置契约。"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from config import env_loader, schema
from webui import config_editor


class HuanguangReconcileConfigurationTests(unittest.TestCase):
    settings = {
        "EXTRACT_LINK_HUANGUANG_RECONCILE_TIMEOUT": (3600, 60, 86400),
        "EXTRACT_LINK_HUANGUANG_NO_PROGRESS_TIMEOUT": (900, 60, 86400),
        "EXTRACT_LINK_HUANGUANG_MAX_QUERY_FAILURES": (12, 3, 100),
    }

    def test_defaults_and_boundaries_are_registered_as_editable_huanguang_fields(self):
        for key, (default, lower, upper) in self.settings.items():
            with self.subTest(key=key):
                self.assertEqual(default, schema.schema_default(key))
                field = schema.CONFIG_SCHEMA[key]
                self.assertEqual("extract_link.py", field.file)
                self.assertEqual("提链", field.group)
                self.assertEqual("int", field.type)
                self.assertFalse(field.secret)
                self.assertEqual(lower, schema.validate_value(key, lower))
                self.assertEqual(upper, schema.validate_value(key, upper))
                for invalid in (lower - 1, upper + 1):
                    with self.assertRaises(schema.ConfigValidationError):
                        schema.validate_value(key, invalid)

    def test_limits_can_reload_without_restart_and_are_saved_only_to_selected_env_file(self):
        from config import extract_link

        fd, raw_path = tempfile.mkstemp(prefix="turb-config-reconcile-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        values = {key: upper for key, (_, _, upper) in self.settings.items()}
        try:
            with patch.object(env_loader, "_ENV_PATH", path), patch.object(
                schema, "_PUBLISHED_SNAPSHOT", None
            ), patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
                saved = config_editor.update_config(values)
                self.assertTrue(saved["reloaded"])
                self.assertEqual([], saved["restart_required"])
                metadata = {item["key"]: item for item in config_editor.get_config()}
                persisted = env_loader.read_env_file()
                for key, value in values.items():
                    self.assertEqual(value, getattr(extract_link, key))
                    self.assertEqual(value, metadata[key]["value"])
                    self.assertEqual(str(value), persisted[key])
        finally:
            config.reload_all()
