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

    def test_password_change_refresh_policy_is_frozen_in_execution_snapshot(self):
        from core.accounts import operation_settings
        from core.operations import task_gateway

        with patch.object(account, "ACCOUNT_PASSWORD_CHANGE_REFRESH_BEFORE_RESET", False):
            self.assertIs(
                False, account.completion_settings()["password_change_refresh_before_reset"],
            )
        captured = task_gateway.normalize_config_snapshot(
            {"ACCOUNT_PASSWORD_CHANGE_REFRESH_BEFORE_RESET": False},
            allowlist=operation_settings.RUNTIME_CONFIG_ALLOWLIST,
        )
        self.assertIs(False, captured["password_change_refresh_before_reset"])
        self.assertIs(
            False,
            operation_settings.completion_settings_from_snapshot({
                "password_change_refresh_before_reset": "false",
            })["password_change_refresh_before_reset"],
        )
