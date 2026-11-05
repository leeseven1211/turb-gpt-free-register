"""AT 只在既有失败收口补充未知页面分类，具体失败及认证执行保持原样。"""
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.accounts.liveness.roxy import flow
from core.auth.challenge import MfaSecretMissingError, PasswordRejectedError
from core.auth.page_errors import AuthPageError
from core.auth.state_machine import PageState, StageTimeout
from core.email.email_butler.client import EmailButlerClientError
from core.network.at_transport_recovery import AtRecoveryScope, AtRecoveryTimeout
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost


EMAIL = "unknown-page@example.test"
UNRECOGNIZED = "浏览器登录未进入已有账号 OTP，最后状态=unknown"
PRIVATE = "fixture-private-content"


def unknown_snapshot():
    return {"url": "https://auth.openai.com/new-check/fixture-private-factor?token=fixture-private-query",
            "title": PRIVATE, "text": PRIVATE,
            "inputs": [{"type": "text", "name": "choice", "value": PRIVATE, "visible": True}],
            "buttons": [{"type": "submit", "text": PRIVATE}], "errors": [],
            "initialization": {"ready": "complete", "pending": 0}}


def mfa_snapshot(text="fixture-language", *, supported=True):
    state = unknown_snapshot()
    state.update(url="https://auth.openai.com/mfa-challenge/fixture-private-factor?token=fixture-private-query",
                 title=text, text=text)
    if supported:
        state["inputs"] = [{"type": "text", "name": "code", "autocomplete": "one-time-code",
                            "inputmode": "numeric", "otpFieldVisible": True,
                            "otpFieldDisabled": False, "otpFieldReadOnly": False}]
    return state


class AtUnknownPageDiagnosticTests(unittest.TestCase):
    def diagnose(self, error=None, *, cause="roxy_login_failed", state=None, **kwargs):
        with patch.object(flow, "_email_otp_page_state", return_value=deepcopy(state or unknown_snapshot())) as read:
            detail = flow._at_unknown_page_detail(error or RuntimeError(UNRECOGNIZED), cause, object(), **kwargs)
        return detail, read

    def test_unknown_mounted_page_records_only_fixed_state_and_route(self):
        error = RuntimeError(UNRECOGNIZED)
        detail, read = self.diagnose(error)
        self.assertEqual("无法识别认证页面；页面状态=UNKNOWN；路由=/<auth-path>", detail)
        read.assert_called_once()
        self.assertEqual(UNRECOGNIZED, str(error))
        self.assertNotIn(PRIVATE, detail)
        self.assertNotIn("fixture-private-factor", detail)
        self.assertNotIn("fixture-private-query", detail)

    def test_mounted_button_only_unknown_page_is_reported(self):
        state = {**unknown_snapshot(), "url": "https://chatgpt.com/new-verification", "inputs": []}
        detail, _read = self.diagnose(state=state)
        self.assertIn("无法识别认证页面", detail)

    def test_unsupported_mfa_form_masks_factor_and_query(self):
        detail, _read = self.diagnose(
            flow._RoxyOtpSubmissionUnknown("email_submit_unconfirmed: 原提交未确认，state=stuck"),
            cause="email_submit_unconfirmed", state=mfa_snapshot(supported=False))
        self.assertIn("无法识别认证页面", detail)
        self.assertIn("路由=/mfa-challenge/<factor>", detail)
        self.assertNotIn("fixture-private", detail)

    def test_supported_mfa_structure_is_language_independent_and_never_called_unknown(self):
        for text in (
            "Consultez votre application d’authentification", "Introduce el código de tu aplicación",
            "Öffne deine Authentifizierungs-App", "أدخل الرمز من تطبيق المصادقة",
            "認証アプリを確認してください", "fixture-unlisted-language",
        ):
            with self.subTest(language=text):
                state = mfa_snapshot(text)
                self.assertTrue(flow._is_at_totp_login_page(state))
                self.assertEqual(PageState.MFA_TOTP, flow._classify_at_login_page(state))
                detail, _read = self.diagnose(
                    flow._RoxyOtpSubmissionUnknown("email_submit_unconfirmed: 原提交未确认，state=stuck"),
                    cause="email_submit_unconfirmed", state=state)
                self.assertEqual("", detail)

    def test_known_terminal_error_loading_and_empty_pages_keep_the_original_failure(self):
        states = [
            {**unknown_snapshot(), "inputs": [], "buttons": []},
            {**unknown_snapshot(), "initialization": {"ready": "interactive", "pending": 1}},
            {**unknown_snapshot(), "initialization": {"ready": "complete", "recent_activity": True}},
            {**unknown_snapshot(), "text": "Your session has expired"},
            {**unknown_snapshot(), "text": "Operation timed out"},
            {**unknown_snapshot(), "errors": ["明确页面错误"]},
            {**unknown_snapshot(), "authErrorPage": True},
            {**unknown_snapshot(), "challengePresent": True},
            {**unknown_snapshot(), "error": "fixture-read-failure"},
            {**unknown_snapshot(), "url": "chrome-error://chromewebdata/"},
            {**mfa_snapshot(), "text": "利用規約", "inputs": [],
             "buttons": [{"tag": "A", "text": "利用規約"}]},
        ]
        state = unknown_snapshot()
        state["inputs"][0]["ariaInvalid"] = "true"
        states.append(state)
        for state in states:
            with self.subTest(state=state):
                self.assertEqual("", self.diagnose(state=state)[0])

    def test_specific_causes_and_arbitrary_runtime_failures_are_not_reclassified(self):
        mailbox = EmailButlerClientError("收件链路失败", error_code="inbound_code_timeout")
        wrapped_mailbox = RuntimeError(UNRECOGNIZED)
        wrapped_mailbox.__cause__ = mailbox
        candidates = [
            (RuntimeError("inbound_code_timeout"), "email_otp_failed"),
            (RuntimeError("普通本地执行失败"), "roxy_login_failed"),
            (RuntimeError("提交本地 TOTP 后页面 20 秒未继续，已在手机号验证前停止"), "roxy_login_failed"),
            (RuntimeError("邮箱验证码后 TOTP 登录链未完成：state=unknown"), "email_otp_failed"),
            (flow._RoxyOtpSubmissionUnknown("email_submit_unconfirmed: 认证会话已失效，state=session_expired"), "email_submit_unconfirmed"),
            (mailbox, "email_otp_failed"), (wrapped_mailbox, "email_otp_failed"),
            (MfaSecretMissingError("缺少 TOTP 密钥"), "mfa_secret_missing"),
            (PasswordRejectedError("密码被拒绝"), "password_rejected"),
            (AuthPageError("auth_context_missing"), "auth_context_missing"),
            (StageTimeout(UNRECOGNIZED), "roxy_login_failed"),
        ]
        for error, cause in candidates:
            with self.subTest(error=type(error).__name__, cause=cause):
                detail, read = self.diagnose(error, cause=cause)
                self.assertEqual("", detail)
                read.assert_not_called()

    def test_network_evidence_precedes_unknown_snapshot_without_an_additional_read(self):
        for kwargs in ({"browser_error": "ERR_TUNNEL_CONNECTION_FAILED"},
                       {"network_diagnostics": {"failure_kind": "transport_error"}}):
            with self.subTest(kwargs=kwargs):
                detail, read = self.diagnose(**kwargs)
                self.assertEqual("", detail)
                read.assert_not_called()
        with AtRecoveryScope(last_failure={"failure_kind": "transport_error", "recovered": False}).activate():
            detail, read = self.diagnose()
        self.assertEqual("", detail)
        read.assert_not_called()

    def test_diagnostic_read_failure_preserves_original_and_control_errors_escape(self):
        original = RuntimeError(UNRECOGNIZED)
        with patch.object(flow, "_email_otp_page_state", side_effect=ValueError("离线诊断失败")):
            self.assertEqual("", flow._at_unknown_page_detail(original, "roxy_login_failed", object()))
        self.assertEqual(UNRECOGNIZED, str(original))
        for error in (OperationCancelled("离线取消"), OperationLeaseLost("离线租约"), AtRecoveryTimeout("离线总预算")):
            with self.subTest(error=type(error).__name__), patch.object(flow, "_email_otp_page_state", side_effect=error):
                with self.assertRaises(type(error)) as caught:
                    flow._at_unknown_page_detail(original, "roxy_login_failed", object())
                self.assertIs(error, caught.exception)


class AtUnknownPageFailureTests(unittest.TestCase):
    def run_failure(self, error, *, stage="login", state=None, read_error=None, network_diagnostics=None):
        snapshot = deepcopy(state or unknown_snapshot())
        driver = Mock(current_url=snapshot["url"])
        driver.execute_script.return_value = {"url": snapshot["url"], "text": ""}
        opened = SimpleNamespace(profile_id="fixture-current-profile", account_bound=True,
                                 created_by_run=False, debugger_address="127.0.0.1:9999")
        client = Mock()
        client.open_profile_for_account.return_value = opened
        debug = SimpleNamespace(capture_mode="full")
        started = Mock()
        with ExitStack() as stack:
            for item in (
                patch.object(flow, "available", return_value=True),
                patch.object(flow, "current_token", return_value=None),
                patch.object(flow, "check_cancelled"),
                patch.object(flow, "RoxyBrowserClient", return_value=client),
                patch.object(flow, "_build_driver", return_value=driver),
                patch.object(flow, "_center_browser_window"), patch.object(flow, "_safe_get"),
                patch.object(flow, "_page_warmup"), patch.object(flow, "_maybe_accept"),
                patch.object(flow, "_page_account_unusable_code", return_value=""),
                patch.object(flow, "password_receipt_ids", return_value=frozenset()),
                patch.object(flow, "password_evidence", return_value={"credential_check": "unverified", "submitted": False}),
                patch.object(flow.cfg, "ROXY_KEEP_BROWSER_OPEN", True),
                patch("core.browser.roxy.profile_binding.account_profile_id_by_email", return_value=opened.profile_id),
                patch("core.codex.roxy.oauth._account_login_credentials", return_value=("fixture-password", "")),
                patch("core.browser.flow_policy.install_for_flow"),
                patch("core.browser.asset_policy.start_auth_asset_cache"),
                patch("core.browser.asset_policy.stop_asset_cache"),
                patch("core.browser.traffic.bind_roxy_capture"), patch("core.browser.traffic.finish_roxy_capture"),
                patch("core.registration.debug.current_session", return_value=debug),
                patch("core.registration.debug.attach_current_roxy"),
            ):
                stack.enter_context(item)
            login = stack.enter_context(patch.object(flow, "_login_existing_account_with_recovery",
                side_effect=error if stage == "login" else None, return_value="otp"))
            otp = stack.enter_context(patch.object(flow, "_complete_otp", side_effect=error if stage == "email_otp" else None))
            read = stack.enter_context(patch.object(flow, "_email_otp_page_state", side_effect=read_error, return_value=snapshot))
            capture = stack.enter_context(patch("core.registration.debug.capture_current_failure"))
            quit_driver = stack.enter_context(patch.object(flow, "_quit_driver"))
            if network_diagnostics is not None:
                stack.enter_context(patch.object(flow, "_at_network_diagnostics", return_value=network_diagnostics))
            with AtRecoveryScope().activate():
                try:
                    result = flow.refresh_access_token(EMAIL, proxy="http://fixture.invalid:8080",
                                                       on_remote_request_started=started)
                finally:
                    self.calls = SimpleNamespace(login=login, otp=otp, read=read, capture=capture,
                                                 quit_driver=quit_driver, client=client, started=started)
        return result

    def test_existing_failure_gets_clear_unknown_page_and_keeps_submission_facts_and_capture(self):
        for stage, error in (
            ("login", RuntimeError(UNRECOGNIZED)),
            ("email_otp", flow._RoxyOtpSubmissionUnknown("email_submit_unconfirmed: 原提交未确认，state=stuck")),
        ):
            with self.subTest(stage=stage):
                original = str(error)
                result = self.run_failure(error, stage=stage)
                self.assertEqual("auth_page_unknown", result["error_code"])
                self.assertIn("无法识别认证页面", result["error"])
                self.assertIn(original, result["error"])
                self.assertEqual(original, str(error))
                self.assertTrue(result["remote_request_started"])
                self.assertNotIn("action_dispatched", result)
                self.assertFalse(result["auth_facts"]["session_acquired"])
                self.assertNotIn(PRIVATE, result["error"])
                self.assertNotIn("fixture-private-factor", result["error"])
                self.calls.login.assert_called_once()
                self.calls.read.assert_called_once()
                self.calls.started.assert_called_once()
                self.calls.capture.assert_called_once()

    def test_real_transport_evidence_and_read_failure_keep_the_original_cause(self):
        failure = {"failure_kind": "transport_error", "network_error": "ERR_CONNECTION_RESET",
                   "transport_kind": "connection", "response_observed": False}
        result = self.run_failure(RuntimeError(UNRECOGNIZED), network_diagnostics=failure)
        self.assertEqual("roxy_login_failed", result["error_code"])
        self.assertEqual("ERR_CONNECTION_RESET", result["auth_diagnostics"]["network_error"])
        self.calls.read.assert_not_called()
        result = self.run_failure(RuntimeError(UNRECOGNIZED), read_error=ValueError("离线诊断失败"))
        self.assertEqual("roxy_login_failed", result["error_code"])
        self.assertNotIn("离线诊断失败", result["error"])

    def test_diagnostic_cancellation_and_budget_keep_existing_cleanup(self):
        for error in (OperationCancelled("离线取消"), OperationLeaseLost("离线租约"), AtRecoveryTimeout("离线总预算")):
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)) as caught:
                self.run_failure(RuntimeError(UNRECOGNIZED), read_error=error)
            self.assertIs(error, caught.exception)
            self.calls.capture.assert_not_called()
            self.calls.quit_driver.assert_called_once()
            self.calls.client.cleanup_profile.assert_called_once()
            if isinstance(error, AtRecoveryTimeout):
                self.calls.client.close_profile.assert_called_once_with("fixture-current-profile")


if __name__ == "__main__":
    unittest.main()
