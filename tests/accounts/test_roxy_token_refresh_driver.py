# -*- coding: utf-8 -*-
"""直接使用 Roxy 刷新 AT 的驱动选择、回调与失败采集回归。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from core.accounts.liveness import service as service
from core.accounts.liveness.roxy import flow as roxy_liveness
from core.operations.runtime import OperationCancelled


EMAIL = "fixture@example.test"


class RoxyRefreshDriverTests(unittest.TestCase):
    def test_login_page_timeout_reports_specific_cause_without_changing_unknown_receipt(self):
        reporter = MagicMock()
        context = MagicMock(task_id=2, run_id=3)
        route = MagicMock(proxy_url="http://proxy.example:8080")
        route.public_dict.return_value = {"network_route": "proxy"}
        browser_result = {
            "ok": False,
            "status": "failed",
            "error_code": "roxy_login_page_timeout",
            "error": "Roxy RuntimeError: 邮箱入口未挂载且 NextAuth 兜底失败："
                     "{'ok': False, 'reason': 'nextauth_budget_exhausted', "
                     "'stage': 'timeout', 'not_dispatched': True}",
            "remote_request_started": True,
        }

        def browser(_email, **kwargs):
            kwargs["on_remote_request_started"]()
            return browser_result

        with ExitStack() as stack:
            for item in (
                patch.object(service.db, "mark_account_live_check_running", return_value=True),
                patch.object(service.db, "get_account", return_value={"email_invalid": True, "access_token": "fixture-at"}),
                patch.object(service.db, "update_account_liveness", return_value=True),
                patch.object(service, "_reporter", return_value=reporter),
                patch.object(service, "_append_log"),
                patch.object(service, "_checkpoint"),
                patch.object(service, "token_claims", return_value={}),
                patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            ):
                stack.enter_context(item)
            refresh = stack.enter_context(patch.object(roxy_liveness, "refresh_access_token", side_effect=browser))
            result = service._run_live_check(
                account_id=1, email=EMAIL, trigger="fixture", proxy=None,
                force_refresh=True, refresh_driver="browser_roxy",
                config_snapshot={"auth_raw_context_enabled": False}, operation_context=context,
            )

        refresh.assert_called_once()
        authenticate = [call for call in reporter.stage.call_args_list
                        if call.args[:2] == ("authenticate", "failed")]
        self.assertEqual(1, len(authenticate))
        self.assertEqual("Roxy 登录页未就绪，登录预检请求超时", authenticate[0].args[2])
        reporter.finish.assert_called_once()
        summary = reporter.finish.call_args.kwargs["result_summary"]
        self.assertEqual("roxy_login_page_timeout", summary["cause_code"])
        self.assertTrue(summary["reconcile_required"])
        self.assertTrue(result["remote_request_started"])
        outcomes = [call.kwargs["outcome"] for call in context.remote_request_receipt.call_args_list]
        self.assertIn("unknown", outcomes)
        self.assertNotIn("not_submitted", outcomes)
        self.assertNotIn("rejected", outcomes)

    def test_password_page_error_unknown_receipt_does_not_invent_http_response(self):
        for reconcile in (False, True):
            for response_observed in (None, False, True):
                with self.subTest(reconcile=reconcile, response_observed=response_observed), ExitStack() as stack:
                    reporter = MagicMock()
                    context = MagicMock(task_id=2, run_id=3)
                    route = MagicMock(proxy_url="http://proxy.example:8080")
                    route.public_dict.return_value = {"network_route": "proxy"}
                    result = {"ok": False, "status": "failed", "error_code": "password_change_required",
                              "error": "OpenAI 要求修改密码后重新登录", "reconcile_required": reconcile}
                    if response_observed is not None:
                        result["response_observed"] = response_observed

                    def browser(_email, **kwargs):
                        kwargs["on_remote_request_started"]()
                        return result

                    for item in (
                        patch.object(service.db, "mark_account_live_check_running", return_value=True),
                        patch.object(service.db, "get_account", return_value={"email_invalid": True, "access_token": "fixture-at"}),
                        patch.object(service.db, "update_account_liveness", return_value=True),
                        patch.object(service, "_reporter", return_value=reporter),
                        patch.object(service, "_append_log"),
                        patch.object(service, "_checkpoint"),
                        patch.object(service, "token_claims", return_value={}),
                        patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
                        patch.object(roxy_liveness, "refresh_access_token", side_effect=browser),
                    ):
                        stack.enter_context(item)
                    service._run_live_check(account_id=1, email=EMAIL, trigger="fixture", proxy=None,
                                            force_refresh=True, refresh_driver="browser_roxy",
                                            config_snapshot={"auth_raw_context_enabled": False}, operation_context=context)
                    unknown = [call for call in context.remote_request_receipt.call_args_list
                               if call.kwargs.get("outcome") == "unknown"]
                    self.assertTrue(unknown)
                    self.assertIs(unknown[0].kwargs["detail"]["response_observed"], response_observed is True)

    def test_driver_selection_and_frozen_snapshot_keep_browser_independent_of_protocol_version(self):
        from config import account

        with patch.object(account, "ACCOUNT_AT_REFRESH_DRIVER", "browser_roxy", create=True):
            self.assertEqual("browser_roxy", service._resolve_refresh_driver())
            for alias in ("roxy", "browser_roxy"):
                self.assertEqual("browser_roxy", service._resolve_refresh_driver(alias))
            self.assertIsNone(service._refresh_protocol_version("browser_roxy"))
            self.assertEqual("legacy", service._resolve_refresh_driver(config_snapshot={
                "refresh_driver": "protocol", "refresh_protocol_version": "v1",
            }))
        self.assertEqual("ACCOUNT_AT_REFRESH_DRIVER", service.LIVE_CONFIG_ALLOWLIST["refresh_driver"])
        self.assertEqual("ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED", service.LIVE_CONFIG_ALLOWLIST["refresh_roxy_debug_enabled"])

    def test_enqueue_does_not_replace_browser_driver_for_invalid_email(self):
        from config import account

        with (
            patch.object(account, "ACCOUNT_AT_REFRESH_DRIVER", "browser_roxy", create=True),
            patch.object(service.db, "get_account", return_value={"id": 1, "email_invalid": True, "access_token": "fixture-at"}),
            patch.object(service.db, "account_is_deactivated", return_value=False),
            patch.object(service.db, "claim_account_live_check", return_value=True),
            patch.object(service, "_append_log"),
            patch.object(service, "_submit_native_live", return_value={"accepted": True, "task_id": 2, "run_id": 3}) as submit,
        ):
            result = service.enqueue_account_live_check(account_id=1, email=EMAIL, force_refresh=True)

        self.assertTrue(result["accepted"])
        self.assertEqual("browser_roxy", submit.call_args.kwargs["refresh_driver"])
        self.assertEqual("browser_roxy", result["token_refresh_driver"])
        self.assertIsNone(result["protocol_version"])

    def test_inline_preserves_browser_driver_for_invalid_email(self):
        context = SimpleNamespace(task_id=2)
        with (
            patch.object(service.db, "get_account", return_value={"id": 1, "email_invalid": True, "access_token": "fixture-at"}),
            patch.object(service.db, "account_is_deactivated", return_value=False),
            patch.object(service.db, "claim_account_live_check", return_value=True),
            patch.object(service, "_run_live_check", return_value={"ok": True}) as run,
        ):
            result = service.run_account_live_check_inline(
                account_id=1, email=EMAIL, trigger="fixture", force_refresh=True,
                operation_context=context,
                config_snapshot={"refresh_driver": "browser_roxy", "refresh_protocol_version": "v1"},
            )

        self.assertTrue(result["accepted"])
        self.assertEqual("browser_roxy", run.call_args.kwargs["refresh_driver"])

    def test_direct_browser_worker_acquires_one_route_without_protocol_or_second_fallback(self):
        for success in (True, False):
            with self.subTest(success=success), ExitStack() as stack:
                reporter = MagicMock()
                route = MagicMock(proxy_url="http://proxy.example:8080")
                route.public_dict.return_value = {"network_route": "proxy", "proxy_region": "US"}
                browser_result = ({"ok": True, "status": "live", "access_token": "fixture-fresh", "session": {}}
                                  if success else {"ok": False, "status": "failed", "error": "network_preflight_failed"})
                for item in (
                    patch.object(service.db, "mark_account_live_check_running", return_value=True),
                    patch.object(service.db, "get_account", return_value={"email_invalid": True, "access_token": "fixture-at"}),
                    patch.object(service.db, "update_account_liveness", return_value=True),
                    patch.object(service, "_reporter", return_value=reporter),
                    patch.object(service, "_append_log"),
                    patch.object(service, "token_claims", return_value={}),
                ):
                    stack.enter_context(item)
                acquire = stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", return_value=route))
                browser = stack.enter_context(patch.object(roxy_liveness, "refresh_access_token", return_value=browser_result))
                protocol = stack.enter_context(patch("core.accounts.liveness.protocol.v2.refresh_access_token"))
                legacy = stack.enter_context(patch.object(service, "check_account_liveness"))

                result = service._run_live_check(
                    account_id=1, email=EMAIL, trigger="fixture", proxy=None,
                    force_refresh=True, refresh_driver="browser_roxy",
                    config_snapshot={"auth_raw_context_enabled": False, "roxy_fallback_enabled": True},
                )

                self.assertEqual(success, result["ok"])
                self.assertEqual("browser_roxy", result["token_refresh_driver"])
                self.assertIsNone(result["protocol_version"])
                acquire.assert_called_once()
                browser.assert_called_once()
                protocol.assert_not_called()
                legacy.assert_not_called()
                self.assertTrue(any(call.args[:2] == ("authenticate", "success" if success else "failed")
                                    for call in reporter.stage.call_args_list))
                self.assertFalse(any(call.args[:2] == ("email_otp", "success") for call in reporter.stage.call_args_list))


class RoxyRefreshHookTests(unittest.TestCase):
    def _context(self, *, mode=None, failure=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        events = []
        driver = MagicMock()
        opened = SimpleNamespace(profile_id="profile-fixture", account_bound=True, debugger_address="127.0.0.1:9999")
        client = MagicMock()
        client.open_profile_for_account.return_value = opened
        debug_session = None if mode is None else SimpleNamespace(capture_mode=mode)
        for item in (
            patch.object(roxy_liveness, "available", return_value=True),
            patch.object(roxy_liveness, "check_cancelled"),
            patch.object(roxy_liveness, "RoxyBrowserClient", return_value=client),
            patch.object(roxy_liveness, "_build_driver", side_effect=lambda _opened: events.append("build") or driver),
            patch.object(roxy_liveness, "_center_browser_window"),
            patch.object(roxy_liveness, "_safe_get", side_effect=lambda *_a, **_kw: events.append("navigate")),
            patch.object(roxy_liveness, "_page_warmup"),
            patch.object(roxy_liveness, "_maybe_accept"),
            patch.object(roxy_liveness, "_page_account_unusable_code", return_value=""),
            patch.object(roxy_liveness, "_enter_existing_account_otp", side_effect=lambda *_a, **_kw: events.append("login") or "logged_in"),
            patch.object(roxy_liveness, "_fetch_chatgpt_session", side_effect=failure,
                         return_value={"accessToken": "fixture-fresh", "account": {"planType": "free"}}),
            patch.object(roxy_liveness, "_quit_driver", side_effect=lambda _driver: events.append("quit")),
            patch.object(roxy_liveness.cfg, "ROXY_KEEP_BROWSER_OPEN", False),
            patch("core.browser.roxy.profile_binding.account_profile_id_by_email", return_value="profile-fixture"),
            patch("core.codex.roxy.oauth._account_login_credentials", return_value=("fixture-password", "fixture-secret")),
            patch("core.browser.flow_policy.install_for_flow"),
            patch("core.browser.asset_policy.start_auth_asset_cache"),
            patch("core.browser.asset_policy.stop_asset_cache"),
            patch("core.browser.traffic.finish_roxy_capture"),
            patch("core.registration.debug.current_session", return_value=debug_session),
        ):
            stack.enter_context(item)
        attach = stack.enter_context(patch("core.registration.debug.attach_current_roxy", side_effect=lambda *_a: events.append("attach")))
        capture = stack.enter_context(patch("core.registration.debug.capture_current_failure", side_effect=lambda *_a: events.append("capture")))
        return driver, opened, client, events, attach, capture

    def test_available_uses_roxy_connection_even_when_registration_uses_protocol(self):
        with patch.multiple(roxy_liveness.cfg, REGISTRATION_DRIVER="protocol", ROXY_API_BASE="http://127.0.0.1:50000",
                            ROXY_API_TOKEN="fixture", ROXY_WORKSPACE_ID="fixture"):
            self.assertTrue(roxy_liveness.available())

    def test_remote_boundary_and_authenticated_callback_use_real_result_and_http_bridge(self):
        driver, _, _, events, _, _ = self._context()
        bridge = MagicMock()
        def callback(result, session):
            self.assertIs(session, bridge)
            self.assertEqual("fixture-fresh", result["session"]["accessToken"])
            events.append("authenticated")
            return result

        with patch.object(roxy_liveness, "_authenticated_browser_session", return_value=bridge) as build_bridge:
            result = roxy_liveness.refresh_access_token(
                EMAIL, proxy="http://proxy.example:8080", context_recorder=MagicMock(),
                on_remote_request_started=lambda: events.append("boundary"), on_authenticated=callback,
            )

        self.assertTrue(result["ok"])
        self.assertLess(events.index("navigate"), events.index("boundary"))
        self.assertLess(events.index("boundary"), events.index("login"))
        self.assertLess(events.index("login"), events.index("authenticated"))
        build_bridge.assert_called_once_with(driver, "http://proxy.example:8080")
        bridge.session.close.assert_called_once()

    def test_full_debug_failure_is_attached_before_navigation_and_keeps_browser(self):
        _, opened, client, events, attach, capture = self._context(mode="full", failure=RuntimeError("fixture-failure"))

        result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        self.assertFalse(result["ok"])
        self.assertTrue(result["debug_browser_kept"])
        self.assertIs(client.open_profile_for_account.call_args.kwargs["headless"], False)
        attach.assert_called_once_with(opened.debugger_address)
        self.assertLess(events.index("attach"), events.index("navigate"))
        capture.assert_called_once()
        self.assertNotIn("quit", events)
        client.cleanup_profile.assert_not_called()

    def test_email_wait_reports_actual_stage_and_imap_timeout_cause(self):
        from core.email.forward_imap import ForwardIMAPError
        from core.operations.runtime import CancellationToken, operation_context
        from core.operations.errors import classify_task_error
        from core.operations import run_log as task_run_log

        self._context(mode="full")
        events = []
        token = CancellationToken(9, "fixture", lambda *_args: False)
        stages_at_wait = []

        def fail_mail_wait(*_args, **_kwargs):
            stages_at_wait.append(task_run_log.current_context().get("stage"))
            raise ForwardIMAPError("本机 Gmail IMAP 等待验证码超时（>240s）；读取阶段耗尽总预算")

        with (
            patch.object(roxy_liveness, "_enter_existing_account_otp", return_value="otp"),
            patch.object(roxy_liveness, "_complete_otp", side_effect=fail_mail_wait),
            operation_context(token, reporter=lambda **event: events.append(event)),
        ):
            result = roxy_liveness.refresh_access_token(EMAIL)

        self.assertEqual(["email_otp"], stages_at_wait)
        self.assertTrue(any(event["stage"] == "email_otp" and event["state"] == "running" for event in events))
        self.assertEqual("email_otp_failed", result["error_code"])
        self.assertEqual("imap_error", result["auth_diagnostics"]["failure_kind"])
        info = classify_task_error(
            result["error"], task_type="token_refresh", error_code=result["error_code"],
            result_summary={**result, "cause_code": result["error_code"]},
        )
        self.assertEqual("MAIL-IMAP-001", info["display_code"])

    def test_failure_only_capture_precedes_cleanup_without_retaining_browser(self):
        _, _, client, events, _, capture = self._context(mode="failure_only", failure=RuntimeError("fixture-failure"))

        result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        self.assertFalse(result["ok"])
        capture.assert_called_once()
        self.assertLess(events.index("capture"), events.index("quit"))
        client.cleanup_profile.assert_called_once()

    def test_session_read_failure_has_explicit_cause_and_classification(self):
        from core.operations.errors import classify_task_error

        self._context(failure=TimeoutError("读取登录会话超时"))
        result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        self.assertEqual("roxy_session_fetch_failed", result.get("error_code"))
        self.assertEqual("session", result.get("failure_stage"))
        info = classify_task_error(result["error"], task_type="token_refresh", error_code=result["error_code"])
        self.assertEqual("ROXY-REFRESH-005", info["display_code"])

    def test_saved_mfa_requirement_error_keeps_specific_code(self):
        from core.auth.challenge import MfaSecretMissingError

        self._context()
        with patch.object(roxy_liveness, "_enter_existing_account_otp", side_effect=MfaSecretMissingError("本地没有 2FA 密钥")):
            result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        self.assertEqual("mfa_secret_missing", result.get("error_code"))
        self.assertIn("本地没有 2FA 密钥", result["error"])

    def test_browser_proxy_error_is_reported_without_losing_unknown_submission(self):
        from core.operations.errors import classify_task_error

        driver, _, _, _, _, _ = self._context(failure=RuntimeError("request_unknown: 密码提交结果未确认"))
        driver.current_url = "chrome-error://chromewebdata/"
        driver.execute_script.return_value = "このサイトにアクセスできません ERR_TUNNEL_CONNECTION_FAILED"
        result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        self.assertEqual("roxy_proxy_tunnel_failed", result.get("error_code"))
        self.assertEqual("network", result.get("error_category"))
        self.assertIn("ERR_TUNNEL_CONNECTION_FAILED", result["error"])
        self.assertIn("request_unknown", result["error"])
        self.assertTrue(service._refresh_result_is_unknown(result))
        info = classify_task_error(result["error"], task_type="token_refresh", error_code=result["error_code"])
        self.assertEqual("NET-ROXY-001", info["display_code"])
        self.assertEqual("网络 / 上游服务", info["source_label"])

    def test_cancelled_debug_run_is_cleaned_without_failure_capture(self):
        _, _, client, events, _, capture = self._context(mode="full")
        with patch.object(roxy_liveness, "_enter_existing_account_otp", side_effect=OperationCancelled("模拟取消")), \
             patch.object(roxy_liveness.cfg, "ROXY_KEEP_BROWSER_OPEN", True):
            with self.assertRaises(OperationCancelled):
                roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        capture.assert_not_called()
        self.assertIn("quit", events)
        client.cleanup_profile.assert_called_once()

    def test_window_capacity_wait_can_observe_cancel_before_opening_browser(self):
        _, _, client, events, _, capture = self._context(mode="full")
        def waiting_for_capacity(**kwargs):
            kwargs["stop_checker"]()

        client.open_profile_for_account.side_effect = waiting_for_capacity
        with patch.object(roxy_liveness, "check_cancelled", side_effect=[None, OperationCancelled("容量等待期间取消")]):
            with self.assertRaises(OperationCancelled):
                roxy_liveness.refresh_access_token(EMAIL)
        self.assertNotIn("build", events)
        capture.assert_not_called()

    def test_real_session_reader_observes_native_cancel_context(self):
        from core.auth.browser.selenium_auth import fetch_chatgpt_session

        _, _, client, events, _, capture = self._context(mode="full")
        token = SimpleNamespace(requested=lambda: "login" in events)
        with (
            patch.object(roxy_liveness, "_fetch_chatgpt_session", fetch_chatgpt_session),
            patch("core.operations.runtime.current_token", return_value=token),
        ):
            with self.assertRaises(OperationCancelled):
                roxy_liveness.refresh_access_token(EMAIL)
        self.assertIn("quit", events)
        capture.assert_not_called()
        client.cleanup_profile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
