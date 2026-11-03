"""Sub2API 自动化配置的默认关闭、可选覆盖与输入校验。"""
import unittest

from config import schema, sub2api
from webui import config_editor


class Sub2ApiAutomationConfigTests(unittest.TestCase):
    def test_automation_is_disabled_and_upload_overrides_are_empty(self):
        fields = {field["key"]: field for field in config_editor.EDITABLE_FIELDS}
        for key in ("SUB2API_SYNC_RETRY_ENABLED", "SUB2API_MONITOR_ENABLED"):
            with self.subTest(key=key):
                self.assertTrue(key in fields, f"缺少配置字段：{key}")
                self.assertFalse(fields[key]["default"])
                self.assertFalse(getattr(sub2api, key))
                self.assertEqual("定时任务", fields[key]["group"])
        for suffix in ("GROUP_IDS", "PROXY_ID", "CONCURRENCY", "PRIORITY", "LOAD_FACTOR", "MODELS"):
            key = f"SUB2API_UPLOAD_{suffix}"
            with self.subTest(key=key):
                self.assertTrue(key in fields, f"缺少配置字段：{key}")
                self.assertEqual("", fields[key]["default"])
                self.assertEqual("Codex", fields[key]["group"])

    def test_optional_upload_values_are_validated_before_saving(self):
        valid = {
            "SUB2API_UPLOAD_GROUP_IDS": "2,5", "SUB2API_UPLOAD_PROXY_ID": "9",
            "SUB2API_UPLOAD_CONCURRENCY": "4", "SUB2API_UPLOAD_PRIORITY": "0",
            "SUB2API_UPLOAD_LOAD_FACTOR": "2", "SUB2API_UPLOAD_MODELS": "gpt-5\ngpt-5-mini",
        }
        self.assertEqual(valid, schema.validate_config_updates(valid))
        for key, value in (
            ("SUB2API_UPLOAD_GROUP_IDS", "2,invalid"), ("SUB2API_UPLOAD_PROXY_ID", "-1"),
            ("SUB2API_UPLOAD_CONCURRENCY", "0"), ("SUB2API_UPLOAD_PRIORITY", "-1"),
            ("SUB2API_UPLOAD_LOAD_FACTOR", "nan"), ("SUB2API_UPLOAD_LOAD_FACTOR", "1.5"), ("SUB2API_MONITOR_INTERVAL_SECONDS", 0),
        ):
            with self.subTest(key=key):
                with self.assertRaises(schema.ConfigValidationError):
                    schema.validate_config_updates({key: value})
