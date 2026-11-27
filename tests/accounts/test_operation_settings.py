"""账号执行配置的快照兼容、冻结子配置与准入边界。"""
from unittest import TestCase
from unittest.mock import Mock, call, patch

from core.accounts import operation_coordinator, operation_settings
from webui import runtime


class AccountOperationSettingsTests(TestCase):
    def test_password_change_freezes_existing_refresh_driver_and_protocol_version(self):
        from config import schema

        snapshot = schema.ConfigSnapshot(
            values={"ACCOUNT_AT_REFRESH_DRIVER": "rust", "OPENAI_PROTOCOL_VERSION": "v3"},
            sources={}, revision=7,
        )
        with patch.object(operation_settings, "runtime_config_snapshot", return_value=snapshot):
            _, _, settings = operation_settings.runtime_execution_settings({})
        self.assertEqual("rust", settings["at_refresh_driver"])
        self.assertEqual("v3", settings["protocol_version"])

    def test_legacy_snapshot_keeps_inputs_and_normalizes_execution_values(self):
        settings = {"password_enabled": "false", "twofa_enabled": "yes",
                    "password_driver": " PROTOCOL ", "codex_driver": " ROXY "}
        original = dict(settings)
        with patch.object(operation_settings, "runtime_config_snapshot", return_value=None) as capture:
            captured, allowlist, projected = operation_settings.runtime_execution_settings(settings)
        capture.assert_called_once_with()
        self.assertEqual({**original, "config_snapshot_revision": "legacy"}, captured)
        self.assertEqual(tuple(operation_settings.RUNTIME_CONFIG_ALLOWLIST), allowlist)
        self.assertIsNot(captured, settings)
        self.assertFalse(projected["password_enabled"])
        self.assertTrue(projected["twofa_enabled"])
        self.assertEqual("protocol", projected["password_driver"])
        self.assertEqual("roxy", projected["codex_driver"])
        self.assertNotIn("config_snapshot_revision", projected)
        self.assertEqual(original, settings)

    def test_old_entrypoints_preserve_malformed_snapshot_fallback_and_log_owner(self):
        snapshot = object()
        fallback = {"password_enabled": True, "password_driver": "protocol"}
        for owner in (runtime, operation_coordinator):
            with (
                self.subTest(owner=owner.__name__),
                patch.object(operation_settings, "runtime_config_snapshot", return_value=snapshot) as capture,
                patch.object(operation_settings.task_gateway, "normalize_config_snapshot", side_effect=ValueError("fixture")) as project,
                patch.object(owner, "logger") as logger,
            ):
                captured, allowlist, settings = owner._runtime_execution_settings(fallback)
            capture.assert_called_once_with()
            project.assert_called_once_with(snapshot, allowlist=operation_settings.RUNTIME_CONFIG_ALLOWLIST)
            logger.exception.assert_called_once_with("读取账号操作 config snapshot 失败，使用当前执行设置")
            self.assertIs(snapshot, captured)
            self.assertIs(operation_settings.RUNTIME_CONFIG_ALLOWLIST, allowlist)
            self.assertEqual(fallback, settings)
            self.assertIsNot(fallback, settings)

    def test_frozen_children_check_capabilities_once_in_existing_order(self):
        frozen_refresh = {"refresh_driver": "protocol_v2", "config_snapshot_revision": 42}
        settings = {"codex_driver": "roxy", "child_execution": {
            "codex": {"oauth_driver": "protocol", "config_snapshot_revision": 42},
            "refresh_at": frozen_refresh,
        }}
        calls = Mock()
        with (
            patch("core.runtime.capabilities.account_setup_unavailable", return_value=None) as setup,
            patch("core.runtime.capabilities.browser_operation_unavailable", return_value=None) as browser,
            patch.object(operation_settings.live_check_service, "deployment_unavailable", return_value=None) as refresh,
            patch.object(operation_settings.codex_operation_service, "_config_snapshot") as capture,
        ):
            calls.attach_mock(setup, "setup")
            calls.attach_mock(browser, "browser")
            calls.attach_mock(refresh, "refresh")
            self.assertIsNone(operation_settings.completion_deployment_unavailable(
                {"password", "codex", "refresh_at"}, settings))
        self.assertEqual([
            call.setup({"password"}, settings),
            call.browser("protocol"),
            call.refresh(force_refresh=True, config_snapshot=frozen_refresh),
        ], calls.mock_calls)
        capture.assert_not_called()

    def test_setup_rejection_stops_later_capability_checks(self):
        rejection = {"accepted": False, "error": "当前部署不支持浏览器"}
        with (
            patch("core.runtime.capabilities.account_setup_unavailable", return_value=rejection) as setup,
            patch("core.runtime.capabilities.browser_operation_unavailable") as browser,
            patch.object(operation_settings.live_check_service, "deployment_unavailable") as refresh,
            patch.object(operation_settings.codex_operation_service, "_config_snapshot") as capture,
        ):
            result = operation_settings.completion_deployment_unavailable({"twofa", "codex", "refresh_at"}, {})
        self.assertIs(rejection, result)
        setup.assert_called_once_with({"twofa"}, {})
        browser.assert_not_called()
        refresh.assert_not_called()
        capture.assert_not_called()
