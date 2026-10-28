"""账号配置补跑的浏览器抓包必须在登录前启动、在清理前保存失败现场。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import roxy_codex_oauth as oauth
from core.task_errors import classify_task_error


class AccountActionDebugTests(unittest.TestCase):
    def _failed_action(self, error, *, capture=True):
        events = []
        opened = SimpleNamespace(profile_id="unit-profile", debugger_address="127.0.0.1:9222",
                                 raw={}, account_bound=True)
        driver = Mock()
        client = Mock()
        client.open_profile_for_account.return_value = opened
        with ExitStack() as stack:
            stack.enter_context(patch.object(oauth, "RoxyBrowserClient", return_value=client))
            stack.enter_context(patch("core.roxy_profile_binding.account_profile_id_by_email", return_value="unit-profile"))
            stack.enter_context(patch.object(oauth, "_build_driver", return_value=driver))
            stack.enter_context(patch.object(oauth, "_center_browser_window"))
            stack.enter_context(patch.object(oauth, "clear_roxy_browser_auth_state"))
            stack.enter_context(patch.object(oauth, "_detect_browser_kind", return_value="roxy"))
            stack.enter_context(patch.object(oauth, "_quit_driver", side_effect=lambda *_: events.append("cleanup")))
            stack.enter_context(patch.object(oauth._roxy_cfg, "ROXY_KEEP_BROWSER_OPEN", False))
            stack.enter_context(patch("core.browser_traffic.bind_roxy_capture"))
            stack.enter_context(patch("core.browser_traffic.finish_roxy_capture"))
            stack.enter_context(patch("core.browser_flow_policy.install_for_flow"))
            stack.enter_context(patch("core.browser_asset_policy.start_auth_asset_cache"))
            stack.enter_context(patch("core.browser_asset_policy.stop_asset_cache"))
            stack.enter_context(patch("core.registration_debug.current_session", return_value=SimpleNamespace(capture_mode="full")))
            attach = stack.enter_context(patch("core.registration_debug.attach_current_roxy", side_effect=lambda *_: events.append("attach")))
            pause = stack.enter_context(patch("core.registration_debug.pause_current_failure", side_effect=lambda *_: events.append("capture")))

            def fail_login(*_args, **_kwargs):
                events.append("login")
                raise error

            stack.enter_context(patch.object(oauth, "_fill_email_and_otp", side_effect=fail_login))
            with self.assertRaises(type(error)) as raised:
                oauth.run_roxy_chatgpt_account_action("unit@example.test", action=Mock())
            self.assertIs(raised.exception, error)
        self.assertEqual(client.open_profile_for_account.call_args.kwargs.get("headless"), False)
        attach.assert_called_once_with(opened.debugger_address)
        if capture:
            self.assertIs(pause.call_args.args[0], driver)
            self.assertEqual(events, ["attach", "login", "capture", "cleanup"])
            return pause.call_args.args[1]
        else:
            pause.assert_not_called()
            self.assertEqual(events, ["attach", "login", "cleanup"])

    def test_full_debug_attaches_before_login_and_preserves_failure_before_cleanup(self):
        self._failed_action(RuntimeError("模拟账号登录失败"))

    def test_pause_keeps_email_entry_failure_message_with_existing_redaction(self):
        reason = self._failed_action(RuntimeError(
            "找不到邮箱输入框/邮箱入口（未使用文字识别），state={'inputs': []} "
            "password=fixture-private Bearer fixture-bearer-token"
        ))
        self.assertIn("RuntimeError: 找不到邮箱输入框/邮箱入口", reason)
        self.assertNotIn("fixture-private", reason)
        self.assertNotIn("fixture-bearer-token", reason)
        info = classify_task_error(reason, task_type="twofa_retry")
        self.assertEqual("email_entry_not_ready", info["code"])
        self.assertEqual("FLOW-EMAIL-003", info["display_code"])

    def test_pause_keeps_existing_password_result_unknown_cause(self):
        from core.registration.password_auth import _PasswordTransitionTimeout

        reason = self._failed_action(_PasswordTransitionTimeout(
            "request_unknown: 已触发密码提交操作，等待仍未确认远端结果"
        ))
        self.assertIn("_PasswordTransitionTimeout: request_unknown:", reason)
        info = classify_task_error(reason, task_type="twofa_retry")
        self.assertEqual("password_result_unknown", info["code"])
        self.assertTrue(info["reconcile_required"])

    def test_pause_preserves_proxy_tunnel_failure_for_real_twofa_retry_task(self):
        from selenium.common.exceptions import WebDriverException

        reason = self._failed_action(WebDriverException(
            "unknown error: net::ERR_TUNNEL_CONNECTION_FAILED"
        ))
        self.assertIn("WebDriverException:", reason)
        self.assertIn("net::ERR_TUNNEL_CONNECTION_FAILED", reason)
        info = classify_task_error(reason, task_type="twofa_retry")
        self.assertEqual("roxy_proxy_tunnel_failed", info["code"])
        self.assertEqual("NET-ROXY-001", info["display_code"])

    def test_user_stop_does_not_enter_failure_debug_hold(self):
        from core.codex_retry_service import CodexRetryStopped
        from core.operation_runtime import OperationCancelled
        from core.registration.state_machine import CancellationRequested
        from core.registration_service import StopRequested
        for error_type in (CodexRetryStopped, OperationCancelled, CancellationRequested, StopRequested):
            with self.subTest(error_type=error_type):
                self._failed_action(error_type("用户停止"), capture=False)
