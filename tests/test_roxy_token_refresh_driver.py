# -*- coding: utf-8 -*-
"""直接使用 Roxy 刷新 AT 的驱动选择、回调与失败采集回归。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from core import live_check_service as service, roxy_liveness
from core.operation_runtime import OperationCancelled


EMAIL = "fixture@example.test"


class RoxyRefreshDriverTests(unittest.TestCase):
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
                acquire = stack.enter_context(patch("core.account_proxy.acquire_account_proxy", return_value=route))
                browser = stack.enter_context(patch.object(roxy_liveness, "refresh_access_token", return_value=browser_result))
                protocol = stack.enter_context(patch("core.protocol_v2_liveness.refresh_access_token"))
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
            patch("core.roxy_profile_binding.account_profile_id_by_email", return_value="profile-fixture"),
            patch("core.roxy_codex_oauth._account_login_credentials", return_value=("fixture-password", "fixture-secret")),
            patch("core.browser_flow_policy.install_for_flow"),
            patch("core.browser_asset_policy.start_auth_asset_cache"),
            patch("core.browser_asset_policy.stop_asset_cache"),
            patch("core.browser_traffic.finish_roxy_capture"),
            patch("core.registration_debug.current_session", return_value=debug_session),
        ):
            stack.enter_context(item)
        attach = stack.enter_context(patch("core.registration_debug.attach_current_roxy", side_effect=lambda *_a: events.append("attach")))
        capture = stack.enter_context(patch("core.registration_debug.capture_current_failure", side_effect=lambda *_a: events.append("capture")))
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

    def test_failure_only_capture_precedes_cleanup_without_retaining_browser(self):
        _, _, client, events, _, capture = self._context(mode="failure_only", failure=RuntimeError("fixture-failure"))

        result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        self.assertFalse(result["ok"])
        capture.assert_called_once()
        self.assertLess(events.index("capture"), events.index("quit"))
        client.cleanup_profile.assert_called_once()

    def test_session_read_failure_has_explicit_cause_and_classification(self):
        from core.task_errors import classify_task_error

        self._context(failure=TimeoutError("读取登录会话超时"))
        result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        self.assertEqual("roxy_session_fetch_failed", result.get("error_code"))
        self.assertEqual("session", result.get("failure_stage"))
        info = classify_task_error(result["error"], task_type="token_refresh", error_code=result["error_code"])
        self.assertEqual("ROXY-REFRESH-005", info["display_code"])

    def test_saved_mfa_requirement_error_keeps_specific_code(self):
        from core.auth_challenge import MfaSecretMissingError

        self._context()
        with patch.object(roxy_liveness, "_enter_existing_account_otp", side_effect=MfaSecretMissingError("本地没有 2FA 密钥")):
            result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

        self.assertEqual("mfa_secret_missing", result.get("error_code"))
        self.assertIn("本地没有 2FA 密钥", result["error"])

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
        from core.registration.selenium_auth import fetch_chatgpt_session

        _, _, client, events, _, capture = self._context(mode="full")
        token = SimpleNamespace(requested=lambda: "login" in events)
        with (
            patch.object(roxy_liveness, "_fetch_chatgpt_session", fetch_chatgpt_session),
            patch("core.operation_runtime.current_token", return_value=token),
        ):
            with self.assertRaises(OperationCancelled):
                roxy_liveness.refresh_access_token(EMAIL)
        self.assertIn("quit", events)
        capture.assert_not_called()
        client.cleanup_profile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
