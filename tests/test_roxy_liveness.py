import unittest
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch
from contextlib import ExitStack

from core import browser_flow_policy, roxy_liveness


class RoxyLivenessFlowPolicyTests(unittest.TestCase):
    def test_open_source_roxy_keeps_browser_refresh_available_when_configured(self):
        with patch.multiple(
            roxy_liveness.cfg,
            REGISTRATION_DRIVER="roxy_oss",
            ROXY_API_BASE="http://127.0.0.1:50000",
            ROXY_API_TOKEN="test-token",
            ROXY_WORKSPACE_ID="test-workspace",
        ):
            self.assertTrue(roxy_liveness.available())

    def test_auth_cache_and_traffic_finish_before_cleanup_including_kept_browser(self):
        from core import browser_asset_policy
        for keep_open in (False, True):
            with self.subTest(keep_open=keep_open):
                events = []
                opened = SimpleNamespace(profile_id="profile-1", account_bound=True)
                client, driver, cache = MagicMock(), MagicMock(), MagicMock()
                client.open_profile_for_account.return_value = opened
                client.cleanup_profile.side_effect = lambda *args: events.append("cleanup")
                cache.stop.side_effect = lambda: events.append("cache") or {}
                dependencies = self._patch_refresh_dependencies(
                    client=client, opened=opened, driver=driver, install=MagicMock(),
                )
                with ExitStack() as stack:
                    for dependency in dependencies:
                        stack.enter_context(dependency)
                    stack.enter_context(patch.object(browser_asset_policy, "start_auth_asset_cache", create=True, return_value=cache))
                    stack.enter_context(patch("core.browser_traffic.finish_roxy_capture", side_effect=lambda *args: events.append("traffic")))
                    stack.enter_context(patch.object(roxy_liveness, "_quit_driver", side_effect=lambda *args: events.append("quit")))
                    stack.enter_context(patch.object(roxy_liveness.cfg, "ROXY_KEEP_BROWSER_OPEN", keep_open))
                    result = roxy_liveness.refresh_access_token("account@example.test")
                self.assertTrue(result["ok"])
                self.assertEqual(events, ["cache", "traffic"] if keep_open else ["cache", "traffic", "quit", "cleanup"])

    def _patch_refresh_dependencies(self, *, client, opened, driver, install):
        return (
            patch.object(roxy_liveness, "available", return_value=True),
            patch.object(roxy_liveness, "RoxyBrowserClient", return_value=client),
            patch.object(roxy_liveness, "_build_driver", return_value=driver),
            patch.object(roxy_liveness, "_center_browser_window"),
            patch.object(roxy_liveness, "_safe_get"),
            patch.object(roxy_liveness, "_page_warmup"),
            patch.object(roxy_liveness, "_maybe_accept"),
            patch.object(roxy_liveness, "_page_account_unusable_code", return_value=""),
            patch.object(roxy_liveness, "_enter_existing_account_otp", return_value="logged_in"),
            patch.object(roxy_liveness, "_fetch_chatgpt_session", return_value={"accessToken": "new-at"}),
            patch("core.roxy_profile_binding.account_profile_id_by_email", return_value="profile-1"),
            patch("core.roxy_codex_oauth._account_login_credentials", return_value=("saved-password", "saved-totp")),
            patch.object(browser_flow_policy, "install_for_flow", install),
        )

    def test_refresh_binds_existing_auth_context_and_installs_token_refresh_policy(self):
        opened = SimpleNamespace(profile_id="profile-1", account_bound=True)
        driver = MagicMock()
        client = MagicMock()
        client.open_profile_for_account.return_value = opened
        recorder = MagicMock()
        saver = MagicMock()
        install = MagicMock(return_value=saver)

        patches = self._patch_refresh_dependencies(
            client=client, opened=opened, driver=driver, install=install,
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12]:
            result = roxy_liveness.refresh_access_token(
                "account@example.com",
                proxy="proxy",
                context_recorder=recorder,
            )

        self.assertTrue(result["ok"])
        client.open_profile_for_account.assert_called_once_with(
            profile_id="profile-1",
            proxy_url="proxy",
            data_saver_flow="token_refresh",
            stop_checker=ANY,
        )
        recorder.open_roxy_profile.assert_called_once_with(
            opened,
            route_attempt_no=1,
            proxy_url=None,
            proxy_context=None,
        )
        recorder.finish_roxy_profile.assert_called_once_with(
            opened,
            status="success",
            result_code="authenticated",
        )
        install.assert_called_once_with("token_refresh", opened, driver)
        saver.stop.assert_called_once_with()

    def test_refresh_closes_auth_context_with_safe_failure_code(self):
        opened = SimpleNamespace(profile_id="profile-1", account_bound=True)
        driver = MagicMock()
        client = MagicMock()
        client.open_profile_for_account.return_value = opened
        recorder = MagicMock()
        saver = MagicMock()
        install = MagicMock(return_value=saver)

        patches = self._patch_refresh_dependencies(
            client=client, opened=opened, driver=driver, install=install,
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patch.object(
            roxy_liveness,
            "_fetch_chatgpt_session",
            side_effect=RuntimeError("browser session unavailable"),
        ):
            result = roxy_liveness.refresh_access_token(
                "account@example.com",
                context_recorder=recorder,
            )

        self.assertFalse(result["ok"])
        recorder.finish_roxy_profile.assert_called_once_with(
            opened,
            status="failed",
            result_code="roxy_session_fetch_failed",
        )
        saver.stop.assert_called_once_with()

    def test_refresh_without_auth_context_binds_token_refresh_capture(self):
        opened = SimpleNamespace(profile_id="profile-1", account_bound=True)
        driver = MagicMock()
        client = MagicMock()
        client.open_profile_for_account.return_value = opened
        saver = MagicMock()
        install = MagicMock(return_value=saver)

        patches = self._patch_refresh_dependencies(
            client=client, opened=opened, driver=driver, install=install,
        )
        with (
            patches[0], patches[1], patches[2], patches[3], patches[4], patches[5],
            patches[6], patches[7], patches[8], patches[9], patches[10], patches[11],
            patches[12], patch("core.browser_traffic.bind_roxy_capture") as bind_capture,
        ):
            result = roxy_liveness.refresh_access_token("account@example.com", proxy="proxy")

        self.assertTrue(result["ok"])
        bind_capture.assert_called_once_with(opened, purpose="token_refresh")
        saver.stop.assert_called_once_with()


class RoxyEmailOtpConfirmationTests(unittest.TestCase):
    def _otp_context(self, *, outcome):
        stack = ExitStack()
        self.addCleanup(stack.close)
        baseline = {"url": "https://auth.openai.com/email-verification", "errors": ["无法发送验证码"]}
        fetch = stack.enter_context(patch.object(roxy_liveness, "wait_for_otp", return_value="123456"))
        stack.enter_context(patch.object(roxy_liveness, "_email_otp_page_state", create=True, return_value=baseline))
        stack.enter_context(patch.object(roxy_liveness, "_clear_otp_inputs"))
        stack.enter_context(patch.object(roxy_liveness, "_type_otp"))
        click = stack.enter_context(patch.object(roxy_liveness, "_click_continue"))
        wait = stack.enter_context(patch.object(roxy_liveness, "_wait_after_email_otp_submit", return_value=outcome))
        resend = stack.enter_context(patch.object(roxy_liveness, "_click_resend_email_otp", return_value={"requested_after_ts": 200.0}))
        return baseline, fetch, click, wait, resend

    def test_unconfirmed_or_expired_submission_does_not_start_another_mail_wait(self):
        for outcome in ("stuck", "session_expired"):
            with self.subTest(outcome=outcome):
                baseline, fetch, _click, wait, resend = self._otp_context(outcome=outcome)
                with self.assertRaisesRegex(RuntimeError, "email_submit_unconfirmed"):
                    roxy_liveness._complete_otp(MagicMock(), "account@example.test", 100.0)
                self.assertEqual(1, fetch.call_count)
                self.assertEqual(baseline, wait.call_args.kwargs.get("baseline_state"))
                resend.assert_not_called()

    def test_verified_page_and_auto_submit_click_error_finish_without_resend(self):
        _baseline, fetch, click, _wait, resend = self._otp_context(outcome="email_verified")
        click.side_effect = RuntimeError("自动提交后原按钮已卸载")
        roxy_liveness._complete_otp(MagicMock(), "account@example.test", 100.0)
        self.assertEqual(1, fetch.call_count)
        resend.assert_not_called()

    def test_cancel_during_click_is_not_swallowed(self):
        from core.operation_runtime import OperationCancelled

        _baseline, _fetch, click, wait, resend = self._otp_context(outcome="accepted")
        click.side_effect = OperationCancelled("用户停止")
        with self.assertRaises(OperationCancelled):
            roxy_liveness._complete_otp(MagicMock(), "account@example.test", 100.0)
        wait.assert_not_called()
        resend.assert_not_called()

    def test_explicit_invalid_code_resends_once_and_uses_new_request_time(self):
        _baseline, fetch, _click, wait, resend = self._otp_context(outcome="accepted")
        wait.side_effect = ["invalid", "accepted"]
        roxy_liveness._complete_otp(MagicMock(), "account@example.test", 100.0)
        resend.assert_called_once()
        self.assertEqual([100.0, 200.0], [call.kwargs["after_ts"] for call in fetch.call_args_list])


if __name__ == "__main__":
    unittest.main()
