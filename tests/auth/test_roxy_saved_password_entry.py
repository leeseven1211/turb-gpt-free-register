import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.browser.password_auth import _PasswordTransitionTimeout
from core.auth.challenge import PasswordRejectedError
from core.codex.roxy import oauth


class RoxySavedPasswordEntryTests(unittest.TestCase):
    def _resolve(self, *, offered="/log-in/password", initial="/email-verification",
                 existing_receipt=None, submit_error=None, browser_kind="Roxy",
                 submit_receipt=False, after_submit="/email-verification", allow_profile_handoff=False,
                 allow_password_reset=False, force_password_reset=False,
                 submit_phase="confirmed", submit_result="success", submit_error_code=None,
                 local_roxy_marker=None, legacy_offered=None):
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com" + initial
        driver._browser_submission_receipt = existing_receipt
        driver._browser_submission_receipts = [existing_receipt] if existing_receipt else []
        driver._test_stages = []
        if local_roxy_marker is not None:
            driver._registration_local_roxy_password_entry = local_roxy_marker
        driver.get.side_effect = lambda url: setattr(driver, "current_url", url)
        now = [100.0]

        def snapshot(_driver):
            if driver.current_url.endswith("/about-you"):
                return {"url": driver.current_url, "inputs": [{"name": "name", "visible": True}],
                        "errors": [], "buttons": [{"visible": True}]}
            is_password = driver.current_url.endswith("/password")
            return {"url": driver.current_url, "inputs": [{
                "name": "password" if is_password else "code",
                "type": "password" if is_password else "text", "visible": True,
                "autocomplete": "new-password" if "/create-account/" in driver.current_url else "current-password",
            }], "errors": [], "buttons": []}

        def click_entry(_driver, **_kwargs):
            if offered:
                driver.current_url = "https://auth.openai.com" + offered
            return offered

        def submit(_driver, _email, **_kwargs):
            if submit_error is not None:
                raise submit_error
            if submit_receipt:
                receipt = BrowserSubmissionReceipt(
                    kind="password", stage="password_create" if "/create-account/" in driver.current_url else "login_password",
                    endpoint_kind="password_submit", http_method="POST", http_status=200,
                )
                receipt.transition(submit_phase, result=submit_result)
                if submit_error_code:
                    receipt.auth_error = {"code": submit_error_code}
                driver._browser_submission_receipt = receipt
                driver._browser_submission_receipts.append(receipt)
            driver.current_url = "https://auth.openai.com" + after_submit

        with ExitStack() as stack:
            token = oauth._CODEX_BROWSER_KIND.set(browser_kind)
            stack.callback(oauth._CODEX_BROWSER_KIND.reset, token)
            for name, kwargs in {
                "check_cancelled": {}, "_auth_checkpoint": {}, "human_delay": {},
                "_login_challenge_state": {"side_effect": snapshot},
                "_is_totp_login_page": {"return_value": False},
                "_is_login_password_page": {"side_effect": lambda _d: "/log-in/password" in driver.current_url},
                "_is_email_verification_page": {"side_effect": lambda _d: driver.current_url.endswith("/email-verification")},
                "_is_login_advanced": {"return_value": False},
                "_has_access_token": {"return_value": False},
                "_refresh_auth_challenge_after_submit": {},
                "_fill_password_page_if_present": {"side_effect": submit},
            }.items():
                mock = stack.enter_context(patch.object(oauth, name, **kwargs))
                if name == "_fill_password_page_if_present":
                    fill = mock
            entry = stack.enter_context(patch.object(oauth, "open_offered_password_entry", side_effect=click_entry, create=True))
            stack.enter_context(patch("core.auth.browser.password_auth._resume_login_password_url", return_value=legacy_offered))
            stack.enter_context(patch.object(oauth, "time", SimpleNamespace(
                time=lambda: now[0], monotonic=lambda: now[0],
                sleep=lambda value: now.__setitem__(0, now[0] + value),
            )))
            result = oauth.complete_openai_login_challenge(
                driver, "unit@example.test", "saved-password", "", timeout=5,
                stage_reporter=lambda **stage: driver._test_stages.append(stage),
                allow_profile_handoff=allow_profile_handoff,
                allow_password_reset=allow_password_reset, force_password_reset=force_password_reset,
                otp_provider=MagicMock() if allow_password_reset or force_password_reset else None,
            )
        return result, driver, entry, fill

    def test_initial_otp_clicks_offered_login_once_then_keeps_following_otp(self):
        result, driver, entry, fill = self._resolve()
        self.assertEqual(result, "email_otp")
        entry.assert_called_once()
        driver.get.assert_not_called()
        fill.assert_called_once()
        self.assertEqual(fill.call_args.kwargs["existing_password"], "saved-password")
        self.assertTrue(fill.call_args.kwargs["prefer_saved_password_entry"])

    def test_offered_create_page_submits_original_saved_password(self):
        result, driver, entry, fill = self._resolve(offered="/create-account/password")
        self.assertEqual(result, "email_otp")
        entry.assert_called_once()
        driver.get.assert_not_called()
        fill.assert_called_once()
        self.assertEqual(fill.call_args.kwargs["existing_password"], "saved-password")

    def test_unknown_create_submit_does_not_enter_login_retry(self):
        with self.assertRaises(_PasswordTransitionTimeout):
            self._resolve(offered="/create-account/password", submit_error=_PasswordTransitionTimeout("request_unknown"))

    def test_create_rejection_does_not_start_login_password_reset(self):
        with patch.object(oauth, "_reset_password_via_email") as reset:
            with self.assertRaises(PasswordRejectedError):
                self._resolve(offered="/create-account/password", allow_password_reset=True,
                              submit_error=PasswordRejectedError("保存密码未通过创建页面校验"))
        reset.assert_not_called()

    def test_create_password_page_uses_saved_password_even_with_login_reset_flag(self):
        with patch.object(oauth, "_reset_password_via_email") as reset:
            result, _driver, _entry, fill = self._resolve(
                offered="/create-account/password", force_password_reset=True,
            )
        self.assertEqual(result, "email_otp")
        fill.assert_called_once()
        self.assertEqual(fill.call_args.kwargs["existing_password"], "saved-password")
        reset.assert_not_called()

    def test_cloak_keeps_legacy_entry_selection(self):
        result, _driver, entry, fill = self._resolve(browser_kind="Cloak")
        self.assertEqual(result, "email_otp")
        entry.assert_not_called()
        fill.assert_not_called()

    def test_roxy_oss_marker_keeps_legacy_login_entry_selection(self):
        target = "https://auth.openai.com/log-in/password?flow=fixture"
        result, driver, entry, fill = self._resolve(local_roxy_marker=False, legacy_offered=target)
        self.assertEqual(result, "email_otp")
        entry.assert_not_called()
        driver.get.assert_called_once_with(target)
        fill.assert_called_once()
        self.assertEqual(fill.call_args.kwargs["existing_password"], "saved-password")
        self.assertNotIn("prefer_saved_password_entry", fill.call_args.kwargs)

    def test_roxy_oss_marker_does_not_select_new_create_entry(self):
        result, driver, entry, fill = self._resolve(
            local_roxy_marker=False, offered="/create-account/password",
        )
        self.assertEqual(result, "email_otp")
        entry.assert_not_called()
        driver.get.assert_not_called()
        fill.assert_not_called()

    def test_old_confirmed_password_does_not_suppress_new_session_entry(self):
        receipt = BrowserSubmissionReceipt(
            kind="password", stage="password_create", endpoint_kind="password_submit", http_method="POST",
        )
        receipt.transition("confirmed", result="success")
        result, _driver, entry, fill = self._resolve(existing_receipt=receipt)
        self.assertEqual(result, "email_otp")
        entry.assert_called_once()
        fill.assert_called_once()

    def test_create_acceptance_and_login_verification_are_reported_separately(self):
        for path, expected, message in (
            ("/create-account/password", "accepted", "账号密码设置已被接受"),
            ("/log-in/password", "verified", "账号密码验证通过"),
        ):
            with self.subTest(path=path):
                result, driver, _entry, _fill = self._resolve(offered=path, submit_receipt=True)
                self.assertEqual(result, "email_otp")
                evidence = driver._test_stages[-1]["detail"]["auth_facts"]
                self.assertEqual(evidence["credential_check"], expected)
                self.assertEqual(driver._test_stages[-1]["message"], message)
                self.assertEqual(driver._test_stages[-1]["state"], "success")

    def test_unknown_and_rejected_receipts_finish_password_stage_as_failed(self):
        for phase, result, code, status, message in (
            ("unknown", "unknown", None, "unknown", "本次密码提交结果未确认"),
            ("rejected", "failure", "incorrect_password", "rejected", "远端拒绝本次账号密码提交"),
        ):
            with self.subTest(status=status):
                outcome, driver, _entry, fill = self._resolve(
                    submit_receipt=True, submit_phase=phase,
                    submit_result=result, submit_error_code=code,
                )
                self.assertEqual(outcome, "email_otp")
                fill.assert_called_once()
                stage = driver._test_stages[-1]
                self.assertEqual(stage["state"], "failed")
                self.assertEqual(stage["message"], message)
                self.assertEqual(stage["detail"]["auth_facts"]["credential_check"], status)

    def test_create_to_profile_requires_explicit_handoff_authorization(self):
        with self.assertRaisesRegex(RuntimeError, "profile_completion_required") as raised:
            self._resolve(offered="/create-account/password", submit_receipt=True, after_submit="/about-you")
        from core.accounts.liveness.roxy.flow import _refresh_failure_cause

        self.assertEqual(_refresh_failure_cause(raised.exception, "login"), ("profile_completion_required", "auth"))

    def test_create_to_profile_preserves_explicit_handoff_authorization(self):
        result, _driver, entry, fill = self._resolve(
            offered="/create-account/password", submit_receipt=True,
            after_submit="/about-you", allow_profile_handoff=True,
        )
        self.assertEqual(result, "profile_handoff")
        entry.assert_called_once()
        fill.assert_called_once()

    def test_roxy_observer_is_bound_without_password_recovery(self):
        opened = SimpleNamespace(traffic_capture=MagicMock())
        driver = MagicMock()
        observer = object()
        with patch("core.registration.roxy._make_submission_observer", return_value=observer):
            oauth._bind_password_submission_observer(opened, driver)
        opened.traffic_capture.set_submission_observer.assert_called_once_with(observer)

    def test_reused_roxy_oss_driver_does_not_enable_new_oauth_strategy_or_observer(self):
        driver = MagicMock()
        driver._registration_local_roxy_password_entry = False
        opened = SimpleNamespace(traffic_capture=MagicMock())
        self.assertFalse(oauth._uses_roxy_saved_password_entry(driver))
        oauth._bind_password_submission_observer(opened, driver)
        opened.traffic_capture.set_submission_observer.assert_not_called()

    def test_cloak_driver_class_does_not_enable_roxy_strategy_or_observer(self):
        driver = type("CloakSeleniumDriver", (), {})()
        opened = SimpleNamespace(traffic_capture=MagicMock())
        self.assertFalse(oauth._uses_roxy_saved_password_entry(driver))
        oauth._bind_password_submission_observer(opened, driver)
        opened.traffic_capture.set_submission_observer.assert_not_called()

    def test_cloak_explicit_password_recovery_keeps_existing_observer(self):
        driver = type("CloakSeleniumDriver", (), {})()
        opened = SimpleNamespace(traffic_capture=MagicMock())
        observer = object()
        with patch("core.registration.roxy._make_submission_observer", return_value=observer):
            oauth._bind_password_submission_observer(opened, driver, force_for_recovery=True)
        opened.traffic_capture.set_submission_observer.assert_called_once_with(observer)
        self.assertFalse(oauth._uses_roxy_saved_password_entry(driver))

    def test_create_password_branch_rejects_untrusted_origin(self):
        driver = MagicMock()
        for origin, expected in (("https://auth.openai.com", True), ("https://example.test", False)):
            with self.subTest(origin=origin):
                state = {"url": origin + "/create-account/password", "inputs": [{
                    "name": "password", "type": "password", "autocomplete": "new-password", "visible": True,
                }]}
                self.assertEqual(oauth._is_saved_create_password_page(driver, state), expected)

    def test_roxy_entry_does_not_click_after_budget_expires(self):
        driver = MagicMock()
        with patch.object(oauth.time, "time", return_value=100.0), patch.object(
            oauth, "open_offered_password_entry", create=True,
        ) as entry:
            self.assertFalse(oauth._open_offered_saved_password(driver, 99.0))
        entry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
