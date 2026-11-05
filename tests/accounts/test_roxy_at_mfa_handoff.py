"""AT 专用的本地化 MFA 识别与邮箱 OTP 后交接，不连接真实浏览器。"""
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.accounts.liveness.roxy import flow
from core.auth.browser import email_otp
from core.auth.challenge import AuthCancelledError, MfaSecretMissingError
from core.auth.state_machine import PageState, StageBudget, StageTimeout, classify_page
from core.codex.roxy import oauth
from core.network.at_transport_recovery import AtRecoveryTimeout
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost


EMAIL = "mfa-handoff@example.test"
EMAIL_URL = "https://auth.openai.com/email-verification"
MFA_URL = "https://auth.openai.com/mfa-challenge/fixture-factor"
TOTP_SECRET = "fixture-totp-secret"


def mfa_snapshot():
    # 保留真实页面的结构和日文提示，地址、factor、输入值均为离线测试占位。
    return {
        "url": MFA_URL, "title": "認証アプリを確認してください - OpenAI",
        "text": "認証アプリを確認してください 本人確認のため、アプリに表示されているワンタイム認証コードを入力してください。",
        "inputs": [{"name": "code", "id": "fixture-code", "autocomplete": "one-time-code",
                    "inputmode": "numeric", "type": "text", "otpFieldVisible": True,
                    "otpFieldDisabled": False, "otpFieldReadOnly": False, "ariaInvalid": ""}],
        "buttons": [{"type": "submit", "text": "続行"}], "errors": [], "challengePresent": False,
        "initialization": {"ready": "complete", "pending": 0},
    }


def email_snapshot():
    return {"url": EMAIL_URL, "title": "OpenAI", "text": "Enter the verification code",
            "inputs": [{"name": "code", "autocomplete": "one-time-code", "type": "text"}],
            "buttons": [{"type": "submit", "text": "Continue"}], "errors": []}


class _Clock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.0, seconds)


class AtMfaClassificationTests(unittest.TestCase):
    def test_japanese_mfa_snapshot_is_overridden_only_by_the_at_adapter(self):
        state = mfa_snapshot()
        original = deepcopy(state)
        self.assertEqual(PageState.OTP_EMAIL, classify_page(state))
        self.assertTrue(oauth._is_totp_login_page(None, state))
        self.assertEqual(PageState.MFA_TOTP, flow._classify_at_login_page(state))
        self.assertEqual(original, state)
        self.assertEqual(PageState.OTP_EMAIL, classify_page(state))

    def test_adapter_requires_trusted_route_and_current_usable_code_field(self):
        candidates = []
        for url in (
            EMAIL_URL, "https://example.test/mfa-challenge/fixture-factor",
            "http://auth.openai.com/mfa-challenge/fixture-factor",
            "https://auth.openai.com:444/mfa-challenge/fixture-factor",
            "https://fixture@auth.openai.com/mfa-challenge/fixture-factor",
            "https://auth.openai.com/mfa-challenge/", "https://auth.openai.com/mfa/settings",
        ):
            candidates.append({**mfa_snapshot(), "url": url})
        for changes in ({"visible": False}, {"otpFieldVisible": False}, {"otpFieldDisabled": True},
                        {"otpFieldReadOnly": True}, {"type": "hidden"}):
            state = mfa_snapshot()
            state["inputs"][0].update(changes)
            candidates.append(state)
        candidates.append({**mfa_snapshot(), "inputs": []})
        candidates.append({**mfa_snapshot(), "inputs": [{"type": "email", "name": "email"}]})
        state = mfa_snapshot()
        state["inputs"].append({"type": "password", "name": "password"})
        candidates.append(state)
        for state in candidates:
            with self.subTest(url=state["url"], inputs=state["inputs"]):
                self.assertFalse(flow._is_at_totp_login_page(state))
                self.assertEqual(classify_page(state), flow._classify_at_login_page(state))

    def test_explicit_error_and_session_expiry_keep_their_original_classification(self):
        for text in ("Operation timed out", "Your session has expired"):
            with self.subTest(text=text):
                state = {**mfa_snapshot(), "text": text}
                self.assertFalse(flow._is_at_totp_login_page(state))
                self.assertEqual(classify_page(state), flow._classify_at_login_page(state))

    def test_default_mfa_label_does_not_bypass_strict_early_entry_evidence(self):
        state = {**mfa_snapshot(), "url": "https://example.test/mfa-challenge/fixture-factor",
                 "text": "Authenticator code"}
        self.assertEqual(PageState.MFA_TOTP, flow._classify_at_login_page(state))
        self.assertFalse(flow._is_at_totp_login_page(state))


class AtMfaHandoffTests(unittest.TestCase):
    def wait_context(self, state=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        clock = _Clock()
        driver = SimpleNamespace(snapshot=deepcopy(state or mfa_snapshot()), current_url=MFA_URL,
                                 get=Mock(), refresh=Mock())
        driver.execute_script = Mock(side_effect=lambda *_args: deepcopy(driver.snapshot))
        stack.enter_context(patch.object(email_otp, "time", clock))
        stack.enter_context(patch.object(email_otp, "auth_session_unavailable", return_value=False))
        stack.enter_context(patch.object(email_otp, "log_submission_diagnostics"))
        recover = stack.enter_context(patch.object(email_otp, "recover_submission_page", return_value=None))
        return stack, clock, driver, recover

    def run_wait(self, driver, clock, **kwargs):
        return email_otp._wait_after_email_otp_submit(driver, timeout=1,
            budget=StageBudget.start(10, clock=clock.monotonic), expected_email=EMAIL, **kwargs)

    def test_real_wait_hands_japanese_mfa_to_totp_with_no_navigation_or_resend(self):
        _stack, clock, driver, recover = self.wait_context()
        self.assertEqual("totp_required", self.run_wait(driver, clock, page_classifier=flow._classify_at_login_page))
        recover.assert_not_called()
        driver.get.assert_not_called()
        driver.refresh.assert_not_called()

    def test_real_wait_without_opt_in_preserves_the_existing_default_result(self):
        _stack, clock, driver, _recover = self.wait_context()
        self.assertEqual("stuck", self.run_wait(driver, clock))

    def test_recovery_observer_also_uses_the_same_at_classifier(self):
        stack, clock, driver, recover = self.wait_context(email_snapshot())
        driver.current_url = EMAIL_URL

        def recover_page(_driver, _stage, observer, **kwargs):
            driver.snapshot = mfa_snapshot()
            driver.current_url = MFA_URL
            return observer(kwargs["budget"])

        recover.side_effect = recover_page
        stack.enter_context(patch.object(email_otp, "_email_otp_page_recovery_reason", return_value="route_server_error"))
        self.assertEqual("totp_required", self.run_wait(driver, clock, page_classifier=flow._classify_at_login_page))
        recover.assert_called_once()
        driver.get.assert_not_called()

    def prepare_at_otp(self, stack, driver):
        fetch = stack.enter_context(patch.object(flow, "wait_for_otp", return_value="fixture-email-code"))
        stack.enter_context(patch.object(flow, "_email_otp_page_state", return_value=email_snapshot()))
        stack.enter_context(patch.object(flow, "_clear_otp_inputs"))
        stack.enter_context(patch.object(flow, "_type_otp"))
        stack.enter_context(patch.object(flow, "_click_continue"))
        stack.enter_context(patch.object(flow, "_wait_after_email_otp_submit", wraps=email_otp._wait_after_email_otp_submit))
        resend = stack.enter_context(patch.object(flow, "_click_resend_email_otp"))
        return fetch, resend

    def prepare_challenge(self, stack, driver, *, failure=None):
        clock = _Clock()
        stack.enter_context(patch.object(oauth, "time", clock))
        stack.enter_context(patch.object(oauth, "human_delay"))
        stack.enter_context(patch.object(oauth, "_uses_roxy_saved_password_entry", return_value=False))
        stack.enter_context(patch.object(oauth, "_email_ui_submission_state", return_value=""))
        stack.enter_context(patch.object(oauth, "_login_challenge_state", side_effect=lambda _driver: deepcopy(driver.snapshot)))
        stack.enter_context(patch.object(oauth, "_has_access_token", side_effect=lambda _driver: driver.current_url == "https://chatgpt.com/"))

        def submit(_driver, _email, _secret):
            if failure is not None:
                raise failure
            driver.snapshot = {"url": "https://chatgpt.com/", "inputs": [], "buttons": [], "text": ""}
            driver.current_url = "https://chatgpt.com/"

        return stack.enter_context(patch.object(oauth, "_submit_saved_login_totp", side_effect=submit))

    def test_email_otp_to_real_challenge_submits_saved_totp_once_without_another_mail_wait(self):
        stack, _clock, driver, _recover = self.wait_context()
        fetch, resend = self.prepare_at_otp(stack, driver)
        submit = self.prepare_challenge(stack, driver)
        confirmed = Mock()
        with self.assertLogs(oauth.logger.name, level="INFO") as logs:
            flow._complete_otp(driver, EMAIL, 50.0, totp_secret=TOTP_SECRET, on_email_confirmed=confirmed)
        fetch.assert_called_once_with(EMAIL, after_ts=50.0)
        submit.assert_called_once_with(driver, EMAIL, TOTP_SECRET)
        confirmed.assert_called_once()
        resend.assert_not_called()
        driver.get.assert_not_called()
        driver.refresh.assert_not_called()
        self.assertTrue(any("页面状态=MFA_TOTP" in line for line in logs.output))

    def test_initial_at_login_can_handoff_direct_mfa_without_password_or_email_wait(self):
        stack, _clock, driver, _recover = self.wait_context()
        submit = self.prepare_challenge(stack, driver)
        for name in ("_type_email_address", "_submit_email_step"):
            stack.enter_context(patch.object(flow, name))
        stack.enter_context(patch.object(flow, "_page_account_unusable_code", return_value=""))
        stack.enter_context(patch.object(flow, "_wait_email_submit_next_state", return_value="otp"))
        stack.enter_context(patch.object(flow, "_has_access_token", return_value=False))
        fetch = stack.enter_context(patch.object(flow, "wait_for_otp"))
        self.assertEqual("logged_in", flow._enter_existing_account_otp(driver, EMAIL, totp_secret=TOTP_SECRET))
        submit.assert_called_once_with(driver, EMAIL, TOTP_SECRET)
        fetch.assert_not_called()

    def test_missing_totp_secret_and_totp_rejection_do_not_restart_email_otp(self):
        for error in (MfaSecretMissingError("离线缺少密钥"), RuntimeError("离线 TOTP 被拒绝")):
            with self.subTest(error=type(error).__name__):
                stack, _clock, driver, _recover = self.wait_context()
                with stack:
                    fetch, resend = self.prepare_at_otp(stack, driver)
                    submit = self.prepare_challenge(stack, driver, failure=error)
                    confirmed = Mock()
                    with self.assertRaises(type(error)) as caught:
                        flow._complete_otp(driver, EMAIL, 50.0, on_email_confirmed=confirmed)
                    self.assertIs(error, caught.exception)
                    fetch.assert_called_once()
                    submit.assert_called_once()
                    confirmed.assert_called_once()
                    resend.assert_not_called()

    def test_wait_and_totp_handoff_preserve_cancellation_lease_and_budget_errors(self):
        for stage in ("wait", "totp"):
            for error in (OperationCancelled("离线取消"), AuthCancelledError("离线取消"),
                          OperationLeaseLost("离线租约失效"), StageTimeout("离线阶段预算"),
                          AtRecoveryTimeout("离线 AT 总预算")):
                with self.subTest(stage=stage, error=type(error).__name__):
                    stack, _clock, driver, _recover = self.wait_context()
                    with stack:
                        fetch, resend = self.prepare_at_otp(stack, driver)
                        submit = self.prepare_challenge(stack, driver)
                        if stage == "wait":
                            stack.enter_context(patch.object(email_otp, "_check_manual_stop", side_effect=error))
                        else:
                            stack.enter_context(patch.object(oauth, "_auth_checkpoint", side_effect=error))
                        with self.assertRaises(type(error)) as caught:
                            flow._complete_otp(driver, EMAIL, 50.0, totp_secret=TOTP_SECRET)
                        self.assertIs(error, caught.exception)
                        fetch.assert_called_once()
                        submit.assert_not_called()
                        resend.assert_not_called()

    def test_public_challenge_default_does_not_forward_an_extra_classifier_keyword(self):
        driver = SimpleNamespace()
        with patch.object(oauth, "_complete_login_challenge_after_email", return_value="advanced") as complete:
            self.assertEqual("advanced", oauth.complete_openai_login_challenge(driver, EMAIL, "", "", timeout=17))
        complete.assert_called_once_with(driver, EMAIL, "", "", timeout=17)


if __name__ == "__main__":
    unittest.main()
