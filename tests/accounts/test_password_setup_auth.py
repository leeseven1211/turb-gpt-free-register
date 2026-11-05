"""补密码独立登录按真实挑战完成邮箱和已有 MFA，不进入注册。"""
import json
import unittest
from contextlib import ExitStack
from http.cookiejar import CookieJar
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.accounts.password_setup import auth
from core.auth.state_machine import CancellationRequested
from core.email import mailbox_wait
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost

EMAIL = "password-auth@example.test"
AUTH = "https://auth.openai.com"
CHAT = "https://chatgpt.com"
CALLBACK = CHAT + "/api/auth/callback/openai"
INFO = {"accessToken": "fixture-at", "user": {"email": EMAIL, "id": "fixture-user"},
        "account": {"id": "fixture-account"}}


class Response:
    def __init__(self, payload=None, status=200, location=None, text=None):
        self.payload, self.status_code = payload, status
        self.headers = {"location": location} if location else {}
        self.text, self.url = text if text is not None else json.dumps(payload or {}), ""

    def json(self):
        return self.payload


class Session:
    def __init__(self, landing="/email-verification", routes=None):
        self.proxy = "fixture-route"
        self.session = SimpleNamespace(cookies=CookieJar(), close=Mock())
        self.calls = []
        self.routes = {
            ("GET", AUTH + "/authorize/start"): Response(status=302, location=AUTH + landing),
            ("GET", AUTH + landing): Response({}),
            ("GET", AUTH + "/api/accounts/email-otp/send"): Response({}),
            ("POST", AUTH + "/api/accounts/email-otp/validate"): Response({"continue_url": CALLBACK}),
            ("GET", CALLBACK): Response({}),
            ("GET", CHAT + "/api/auth/session"): Response(INFO),
            ("POST", AUTH + "/api/accounts/mfa/issue_challenge"): Response({}),
            ("POST", AUTH + "/api/accounts/mfa/verify"): Response({"continue_url": CALLBACK}),
        }
        self.routes.update(routes or {})

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if (method, url) not in self.routes:
            raise AssertionError(f"非预期请求：{method} {url}")
        response = self.routes[(method, url)]
        if isinstance(response, Exception):
            raise response
        response.url = url
        return response

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get_auth_headers(self, **kwargs):
        return {}

    get_auth_navigate_headers = get_auth_headers
    get_chatgpt_navigate_headers = get_auth_headers
    get_nextauth_headers = get_auth_headers


class PasswordSetupAuthTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.credentials = self.stack.enter_context(patch.object(auth, "get_account_login_credentials",
                                                                 return_value=("", "fixture-secret")))
        self.stack.enter_context(patch.object(auth.db, "get_account_by_email", return_value={"id": 7, "email": EMAIL,
            "user_id": "fixture-user", "chatgpt_account_id": "fixture-account"}))
        self.stack.enter_context(patch.object(auth.v3, "account_email_is_invalid", return_value=False))
        self.wait = self.stack.enter_context(patch.object(auth.v3, "wait_for_otp", return_value="123456"))
        self.totp = self.stack.enter_context(patch.object(auth.v3, "_totp_code", return_value="654321"))
        self.preflight = self.stack.enter_context(patch.object(auth.legacy, "_network_preflight_with_retry"))
        self.delegate = self.stack.enter_context(patch.object(auth.v2, "refresh_access_token", return_value={"ok": True}))

    def run_flow(self, session, **kwargs):
        self.preflight.return_value = (session, AUTH + "/authorize/start")
        return auth.refresh_access_token(EMAIL, proxy="fixture-route", **kwargs)

    def test_password_path_delegates_all_existing_v2_arguments(self):
        self.credentials.return_value = ("fixture-password", "fixture-secret")
        supplier, network_failed, completed = Mock(), Mock(), Mock()
        result = auth.refresh_access_token(EMAIL, proxy="fixture-route", on_authenticated=completed,
            allow_password_email_fallback=False, proxy_supplier=supplier, on_network_failure=network_failed)
        self.assertEqual({"ok": True}, result)
        self.delegate.assert_called_once_with(EMAIL, proxy="fixture-route", on_authenticated=completed,
            allow_password_email_fallback=False, proxy_supplier=supplier, on_network_failure=network_failed)
        self.preflight.assert_not_called()

    def test_email_login_sends_new_code_before_waiting_and_completes_callback(self):
        session = Session()
        events = []
        def clock():
            events.append("clock")
            self.assertFalse(any(url.endswith("/email-otp/send") for _, url, _ in session.calls))
            return 123.5
        def received(*args, **kwargs):
            events.append("wait")
            self.assertTrue(any(url.endswith("/email-otp/send") for _, url, _ in session.calls))
            self.assertEqual(5, mailbox_wait.cooperative_poll_limit(75))
            self.assertEqual(10, mailbox_wait.bounded_timeout(30))
            return "123456"
        self.wait.side_effect = received
        with patch.object(auth.v3, "time", SimpleNamespace(time=clock)), \
                patch.object(auth.v2, "_success", side_effect=AssertionError("无密码认证不能记录密码成功")), \
                self.assertLogs(auth.logger, level="INFO") as logs:
            result = self.run_flow(session)
        self.assertTrue(result["ok"])
        self.assertEqual("email_otp", result["auth_method"])
        self.assertEqual("skipped", result["password_auth_status"])
        self.assertEqual("success", result["email_otp_status"])
        self.assertEqual("skipped", result["mfa_status"])
        self.assertIn("邮箱验证码=已通过", " ".join(logs.output))
        self.assertNotIn("密码认证成功", " ".join(logs.output))
        self.assertEqual(["clock", "wait"], events)
        self.wait.assert_called_once_with(EMAIL, after_ts=123.5)
        self.assertEqual([AUTH + "/api/accounts/email-otp/validate"],
                         [url for method, url, _ in session.calls if method == "POST"])
        session.session.close.assert_called_once_with()
        self.delegate.assert_not_called()

    def test_email_login_completes_existing_mfa_before_authenticated_callback(self):
        session = Session(routes={("POST", AUTH + "/api/accounts/email-otp/validate"): Response({
            "page": {"type": "mfa_challenge"}, "continue_url": AUTH + "/mfa-challenge/factor-1"})})
        def completed(result, client):
            self.assertIs(session, client)
            self.assertFalse(session.session.close.called)
            self.assertEqual("email_otp_mfa", result["auth_method"])
            self.assertEqual("success", result["mfa_status"])
            return {"ok": True, "password_added": True}
        result = self.run_flow(session, on_authenticated=completed)
        self.assertTrue(result["password_added"])
        posts = [(url, json.loads(kwargs["data"])) for method, url, kwargs in session.calls if method == "POST"]
        self.assertEqual([AUTH + "/api/accounts/email-otp/validate", AUTH + "/api/accounts/mfa/issue_challenge",
                          AUTH + "/api/accounts/mfa/verify"], [url for url, _ in posts])
        self.assertEqual({"id": "factor-1", "type": "totp", "code": "654321"}, posts[-1][1])
        self.totp.assert_called_once_with("fixture-secret")
        session.session.close.assert_called_once_with()

    def test_direct_mfa_does_not_send_email_code(self):
        session = Session(landing="/mfa-challenge/factor-2")
        result = self.run_flow(session)
        self.assertEqual("mfa", result["auth_method"])
        self.wait.assert_not_called()
        self.assertFalse(any(url.endswith("/email-otp/send") for _, url, _ in session.calls))

    def test_missing_secret_or_rejected_mfa_does_not_authenticate(self):
        completed = Mock()
        self.credentials.return_value = ("", "")
        session = Session(landing="/mfa-challenge/factor-2")
        with self.assertRaises(auth.ProtocolPasswordSetupError) as caught:
            self.run_flow(session, on_authenticated=completed)
        self.assertEqual("password_setup_mfa_secret_missing", caught.exception.code)
        self.assertFalse(any(method == "POST" for method, _, _ in session.calls))
        self.credentials.return_value = ("", "fixture-secret")
        session = Session(landing="/mfa-challenge/factor-2", routes={
            ("POST", AUTH + "/api/accounts/mfa/verify"): Response({"error": {"code": "invalid_totp"}}, status=400)})
        with self.assertRaises(auth.ProtocolPasswordSetupError) as caught:
            self.run_flow(session, on_authenticated=completed)
        self.assertEqual("password_setup_mfa_rejected", caught.exception.code)
        completed.assert_not_called()

    def test_profile_or_create_account_page_never_submits_registration(self):
        for landing in ("/about-you", "/create-account/password", "/create-account"):
            with self.subTest(landing=landing):
                session = Session(landing=landing)
                with self.assertRaises(auth.ProtocolPasswordSetupError) as caught:
                    self.run_flow(session)
                self.assertEqual("password_setup_page_unexpected", caught.exception.code)
                self.assertFalse(any(method == "POST" for method, _, _ in session.calls))

    def test_authenticated_callback_without_new_challenges_is_allowed(self):
        session = Session(routes={("GET", AUTH + "/authorize/start"): Response(status=302, location=CALLBACK)})
        result = self.run_flow(session)
        self.assertEqual("existing_session", result["auth_method"])
        self.wait.assert_not_called()
        self.assertFalse(any(method == "POST" for method, _, _ in session.calls))

    def test_wrong_session_identity_never_calls_authenticated_callback(self):
        session = Session(routes={("GET", CHAT + "/api/auth/session"): Response({**INFO,
            "user": {"email": "different@example.test", "id": "fixture-user"}})})
        completed = Mock()
        with self.assertRaises(auth.ProtocolPasswordSetupError) as caught:
            self.run_flow(session, on_authenticated=completed)
        self.assertEqual("password_setup_auth_failed", caught.exception.code)
        completed.assert_not_called()

    def test_preflight_keeps_route_supplier_and_failure_callback(self):
        supplier, failed = Mock(), Mock()
        self.run_flow(Session(), proxy_supplier=supplier, on_network_failure=failed)
        self.preflight.assert_called_once_with(EMAIL, "fixture-route", proxy_supplier=supplier,
                                              on_preflight_failure=failed)

    def test_network_failure_is_classified_and_reports_proxy_fault(self):
        session = Session(routes={("GET", AUTH + "/authorize/start"):
                                  RuntimeError("Proxy CONNECT aborted private-route")})
        failed = Mock()
        with self.assertRaises(auth.ProtocolPasswordSetupError) as caught:
            self.run_flow(session, on_network_failure=failed)
        self.assertEqual("password_setup_network_failed", caught.exception.code)
        self.assertTrue(caught.exception.proxy_transport_failed)
        self.assertNotIn("private-route", str(caught.exception))
        failed.assert_called_once()
        session.session.close.assert_called_once_with()

    def test_wrapped_cancellation_and_lease_errors_are_propagated(self):
        for control in (CancellationRequested, OperationCancelled, OperationLeaseLost):
            with self.subTest(control=control):
                signal = control("fixture-stop")
                session = Session(routes={("POST", AUTH + "/api/accounts/email-otp/validate"): signal})
                with self.assertRaises(control) as caught:
                    self.run_flow(session)
                self.assertIs(signal, caught.exception)
                session.session.close.assert_called_once_with()

    def test_otp_send_security_and_rate_limit_errors_keep_their_classification(self):
        for status, expected in ((403, "password_setup_security_check"), (429, "password_setup_rate_limited")):
            with self.subTest(status=status):
                session = Session(routes={("GET", AUTH + "/api/accounts/email-otp/send"): Response({}, status=status)})
                with self.assertRaises(auth.ProtocolPasswordSetupError) as caught:
                    self.run_flow(session)
                self.assertEqual(expected, caught.exception.code)
        self.wait.assert_not_called()

    def test_otp_response_classification_does_not_blame_code_for_network_or_identity_errors(self):
        cases = ((TimeoutError("private-route"), "password_setup_network_failed"),
                 (Response({"error": {"code": "invalid_code"}}, status=400), "password_setup_otp_rejected"),
                 (Response({"error": {"code": "wrong_email_otp_code"}}, status=400), "password_setup_otp_rejected"),
                 (Response({"error": {"code": "otp_expired"}}, status=400), "password_setup_otp_rejected"),
                 (Response({"error": {"code": "identity_provider_mismatch"}}, status=400), "password_setup_auth_failed"),
                 (Response({"error": {"code": "other_remote_rejection"}}, status=400), "password_setup_http_rejected"),
                 (Response(status=400, text='{"error":{"code":"invalid_code","code":"identity_provider_mismatch"}}'),
                  "password_setup_http_rejected"),
                 (Response(status=400, text='{"error":{"code":"invalid_code"},"extra":"' + "x" * 65536 + '"}'),
                  "password_setup_http_rejected"))
        for response, expected in cases:
            with self.subTest(expected=expected):
                session = Session(routes={("POST", AUTH + "/api/accounts/email-otp/validate"): response})
                with self.assertRaises(auth.ProtocolPasswordSetupError) as caught:
                    self.run_flow(session)
                self.assertEqual(expected, caught.exception.code)
                self.assertNotIn("private-route", str(caught.exception))

    def test_known_diagnostic_code_takes_precedence_over_wrapped_response(self):
        error = auth.v2.ProtocolV2AuthError("email_otp_validate_failed")
        error.diagnostics = {"http_status": 400, "auth_error": {"code": "invalid_otp"}}
        cause = RuntimeError("响应不可直接输出")
        cause.response = Response({"error": {"code": "identity_provider_mismatch"}}, status=400)
        error.__cause__ = cause
        self.assertEqual("password_setup_otp_rejected", auth._auth_error(error).code)

    def test_transport_close_does_not_swallow_cancellation(self):
        signal = CancellationRequested("fixture-stop")
        session = Session()
        session.session.close.side_effect = signal
        with self.assertRaises(CancellationRequested) as caught:
            self.run_flow(session)
        self.assertIs(signal, caught.exception)

    def test_deactivated_account_keeps_its_status(self):
        session = Session(routes={("POST", AUTH + "/api/accounts/email-otp/validate"):
                                  Response({"error": {"code": "account_deactivated"}}, status=403)})
        result = self.run_flow(session)
        self.assertEqual("deactivated", result["status"])
        self.assertEqual("account_deactivated", result["error"])
