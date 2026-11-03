"""账号补密码驱动的默认值及配置选择。"""
import unittest
from unittest.mock import patch

from config import account, schema
from webui import config_editor


class PasswordSetupConfigTests(unittest.TestCase):
    def test_password_driver_keeps_roxy_default_and_offers_protocol(self):
        fields = {field["key"]: field for field in config_editor.EDITABLE_FIELDS}
        field = fields["ACCOUNT_PASSWORD_DRIVER"]
        self.assertEqual("roxy", field["default"])
        self.assertEqual({"roxy", "protocol"}, {
            option.value for option in schema.CONFIG_SCHEMA["ACCOUNT_PASSWORD_DRIVER"].options
        })
        self.assertIn("添加密码", field["help"])
        self.assertIn("修改密码", field["help"])
        self.assertEqual({"ACCOUNT_PASSWORD_DRIVER": "protocol"}, schema.validate_config_updates({
            "ACCOUNT_PASSWORD_DRIVER": "protocol",
        }))
        with self.assertRaises(schema.ConfigValidationError):
            schema.validate_config_updates({"ACCOUNT_PASSWORD_DRIVER": "unsupported"})

    def test_completion_snapshot_preserves_selected_password_driver(self):
        with patch.object(account, "ACCOUNT_PASSWORD_DRIVER", "protocol"):
            self.assertEqual("protocol", account.completion_settings()["password_driver"])
