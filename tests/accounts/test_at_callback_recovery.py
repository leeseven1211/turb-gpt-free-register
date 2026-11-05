"""AT 回调的离线故障注入：不访问账号库或外部网络。"""
import base64
import json
import time
import unittest
from types import SimpleNamespace

from core.accounts.liveness.protocol import callback
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost


EMAIL = "callback@example.test"
AUTH_URL = "https://auth.openai.com/authorize/continue?private=fixture"
CALLBACK_URL = "https://chatgpt.com/api/auth/callback/openai?code=private-code&state=private-state"
SESSION_URL = "https://chatgpt.com/api/auth/session"


def session_info(email=EMAIL, *, expiry=None, claim_email=None):
    payload = {"exp": time.time() + 3600 if expiry is None else expiry,
               "https://api.openai.com/profile": {"email": claim_email or email}}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return {"accessToken": "e30." + encoded + ".fixture", "user": {"email": email, "id": "fixture-user"}}


class Response:
    def __init__(self, status=200, payload=None, *, location=None, set_cookie=False):
        self.status_code = status
        self.payload = payload
        self.headers = {"Location": location} if location is not None else {}
        self.set_cookie = set_cookie
        self.closed = False

    @property
    def text(self):
        raise AssertionError("导航不应读取正文")

    @property
    def content(self):
        raise AssertionError("导航不应读取正文")

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def close(self):
        self.closed = True


class TransportError(RuntimeError):
    def __init__(self, code=18):
        self.code = code
        super().__init__(f"curl: ({code}) private-code private-state private-proxy")


class Session:
    def __init__(self, routes):
        self.routes = {url: list(items) for url, items in routes.items()}
        self.calls = []
        self.proxy = "fixture-original-route"
        self.session = SimpleNamespace(cookies=SimpleNamespace(jar=[]))
        self.blocked_until = 0.0

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        values = self.routes.get(url)
        if not values:
            raise AssertionError("出现未安排的离线请求")
        value = values.pop(0)
        if callable(value):
            value = value(self)
        if isinstance(value, BaseException):
            raise value
        if value.set_cookie:
            self.session.cookies.jar.append(SimpleNamespace(
                name="__Secure-next-auth.session-token.0", domain=".chatgpt.com", value="private-cookie"))
        return value

    def get_auth_navigate_headers(self, **kwargs):
        return {"fixture-origin": "auth", **kwargs}

    def get_chatgpt_navigate_headers(self, **kwargs):
        return {"fixture-origin": "chatgpt", **kwargs}

    def get_nextauth_headers(self, **kwargs):
        return kwargs


class AtCallbackRecoveryTests(unittest.TestCase):
    def run_callback(self, session, url=CALLBACK_URL, **kwargs):
        return callback.complete_callback(session, url, referer="https://auth.openai.com/mfa-challenge/fixture", email=EMAIL, **kwargs)

    def test_redirects_use_headers_only_and_skip_homepage_body(self):
        auth_response = Response(302, location=CALLBACK_URL)
        callback_response = Response(302, location="https://chatgpt.com/", set_cookie=True)
        session_response = Response(payload=session_info())
        session = Session({AUTH_URL: [auth_response], CALLBACK_URL: [callback_response], SESSION_URL: [session_response]})
        self.assertEqual(EMAIL, self.run_callback(session, AUTH_URL)["user"]["email"])
        self.assertEqual([AUTH_URL, CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])
        for _, kwargs in session.calls[:2]:
            self.assertIs(kwargs["allow_redirects"], False)
            self.assertIs(kwargs["stream"], True)
            self.assertIs(kwargs["headers"]["user_initiated"], False)
        self.assertEqual("auth", session.calls[0][1]["headers"]["fixture-origin"])
        self.assertEqual("chatgpt", session.calls[1][1]["headers"]["fixture-origin"])
        self.assertTrue(all(item.closed for item in (auth_response, callback_response, session_response)))

    def test_partial_transfer_recovers_only_failed_get_once(self):
        session = Session({AUTH_URL: [Response(302, location=CALLBACK_URL)],
                           CALLBACK_URL: [TransportError(18), Response(302, location="/", set_cookie=True)],
                           SESSION_URL: [Response(payload={}), Response(payload=session_info())]})
        self.assertEqual(EMAIL, self.run_callback(session, AUTH_URL)["user"]["email"])
        self.assertEqual([AUTH_URL, CALLBACK_URL, SESSION_URL, CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])
        self.assertEqual("fixture-original-route", session.proxy)

    def test_session_cookie_after_partial_callback_avoids_code_replay(self):
        def partially_received(session):
            session.session.cookies.jar.append(SimpleNamespace(
                name="__Secure-next-auth.session-token", domain="chatgpt.com", value="private-cookie"))
            return TransportError(18)
        session = Session({CALLBACK_URL: [partially_received], SESSION_URL: [Response(payload=session_info())]})
        self.assertEqual(EMAIL, self.run_callback(session)["user"]["email"])
        self.assertEqual([CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_session_transport_failure_retries_session_without_replaying_callback(self):
        session = Session({CALLBACK_URL: [Response(302, location="/", set_cookie=True)],
                           SESSION_URL: [TransportError(18), Response(payload=session_info())]})
        self.run_callback(session)
        self.assertEqual([CALLBACK_URL, SESSION_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_session_probe_network_failure_uses_only_recovery_budget(self):
        session = Session({CALLBACK_URL: [TransportError(18)],
                           SESSION_URL: [TransportError(28), Response(payload={})]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session)
        self.assertEqual("oauth_callback_failed", caught.exception.code)
        self.assertEqual([CALLBACK_URL, SESSION_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_session_probe_401_allows_one_failed_callback_recovery(self):
        session = Session({CALLBACK_URL: [TransportError(18), Response(302, location="/", set_cookie=True)],
                           SESSION_URL: [Response(401), Response(payload=session_info())]})
        self.assertEqual(EMAIL, self.run_callback(session)["user"]["email"])
        self.assertEqual([CALLBACK_URL, SESSION_URL, CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_exhausted_probe_keeps_original_callback_error_and_safe_log(self):
        session = Session({CALLBACK_URL: [TransportError(18)],
                           SESSION_URL: [TransportError(28), TransportError(56)]})
        with self.assertLogs(callback.logger.name, level="INFO") as records:
            with self.assertRaises(callback.CallbackRecoveryError) as caught:
                self.run_callback(session)
        self.assertEqual("oauth_callback_failed", caught.exception.code)
        self.assertEqual(18, caught.exception.diagnostics["curl_error_code"])
        self.assertEqual(0, caught.exception.diagnostics["retry_attempt"])
        output = "\n".join(records.output)
        self.assertIn("curl=18", output)
        self.assertIn("exception_type=TransportError", output)
        self.assertNotIn("private-", output)
        self.assertEqual([CALLBACK_URL, SESSION_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_callback_retry_exhaustion_preserves_curl_18_and_safe_target(self):
        session = Session({CALLBACK_URL: [TransportError(18), TransportError(18)],
                           SESSION_URL: [Response(payload={}), Response(payload={})]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session)
        error = caught.exception
        self.assertEqual("oauth_callback_failed", error.code)
        self.assertEqual(18, error.diagnostics["curl_error_code"])
        self.assertEqual(1, error.diagnostics["retry_attempt"])
        self.assertEqual("/api/auth/callback/openai", error.diagnostics["target_path"])
        self.assertFalse(error.diagnostics["response_observed"])
        self.assertNotIn("private-", str(error.diagnostics))
        self.assertEqual(2, len([url for url, _ in session.calls if url == CALLBACK_URL]))

    def test_temporary_callback_http_can_recover_once(self):
        for status in (502, 503, 504):
            with self.subTest(status=status):
                session = Session({CALLBACK_URL: [Response(status), Response(302, location="/", set_cookie=True)],
                                   SESSION_URL: [Response(payload={}), Response(payload=session_info())]})
                self.run_callback(session)
                self.assertEqual(2, len([url for url, _ in session.calls if url == CALLBACK_URL]))

    def test_session_http_can_recover_once(self):
        session = Session({CALLBACK_URL: [Response(302, location="/", set_cookie=True)],
                           SESSION_URL: [Response(503), Response(payload=session_info())]})
        self.run_callback(session)
        self.assertEqual([CALLBACK_URL, SESSION_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_received_callback_cookie_never_replays_when_session_stays_empty(self):
        session = Session({CALLBACK_URL: [Response(503, set_cookie=True)], SESSION_URL: [Response(payload={})]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session)
        self.assertEqual("access_token_missing", caught.exception.code)
        self.assertEqual([CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_business_http_error_is_not_replayed(self):
        session = Session({CALLBACK_URL: [Response(400)], SESSION_URL: [Response(payload={})]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session)
        self.assertEqual(400, caught.exception.diagnostics["http_status"])
        self.assertFalse(caught.exception.retryable)
        self.assertEqual([CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_known_error_redirect_preserves_rejection_without_following_error_page(self):
        errors = [("https://chatgpt.com/api/auth/error", code) for code in
                  ("OAuthCallback", "OAuthSignin", "Configuration", "AccessDenied")]
        errors += [("https://auth.openai.com/error", code) for code in ("invalid_state", "invalid_grant")]
        for target, code in errors:
            with self.subTest(code=code):
                session = Session({CALLBACK_URL: [Response(302, location=target + "?error=" + code + "&private=private-query")],
                                   SESSION_URL: [Response(payload={})]})
                with self.assertLogs(callback.logger.name, level="INFO") as records:
                    with self.assertRaises(callback.CallbackRecoveryError) as caught:
                        self.run_callback(session)
                error = caught.exception
                self.assertEqual("oauth_callback_rejected", error.code)
                self.assertEqual("oauth_callback", error.diagnostics["operation"])
                self.assertEqual("rejected", error.diagnostics["failure_kind"])
                self.assertEqual({"code": code}, error.diagnostics["auth_error"])
                self.assertEqual(302, error.diagnostics["http_status"])
                self.assertFalse(error.retryable)
                self.assertEqual([CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])
                self.assertNotIn("private-", str(error.diagnostics) + "\n".join(records.output))

    def test_valid_session_takes_precedence_over_known_callback_error_redirect(self):
        session = Session({CALLBACK_URL: [Response(302, location="/api/auth/error?error=OAuthCallback", set_cookie=True)],
                           SESSION_URL: [Response(payload=session_info())]})
        self.assertEqual(EMAIL, self.run_callback(session)["user"]["email"])
        self.assertEqual([CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_error_redirect_with_401_or_invalid_session_keeps_callback_rejection(self):
        for response in (Response(401), Response(payload=session_info("other@example.test"))):
            with self.subTest(status=response.status_code):
                session = Session({AUTH_URL: [Response(302, location="https://auth.openai.com/error?error=invalid_state")],
                                   SESSION_URL: [response]})
                with self.assertRaises(callback.CallbackRecoveryError) as caught:
                    self.run_callback(session, AUTH_URL)
                self.assertEqual("oauth_callback_rejected", caught.exception.code)
                self.assertEqual({"code": "invalid_state"}, caught.exception.diagnostics["auth_error"])
                self.assertEqual([AUTH_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_unknown_error_query_is_not_reported_as_known_rejection(self):
        session = Session({CALLBACK_URL: [Response(302, location="/api/auth/error?error=private-unknown")],
                           SESSION_URL: [Response(payload={})]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session)
        self.assertEqual("access_token_missing", caught.exception.code)
        self.assertNotIn("private-unknown", str(caught.exception.diagnostics))
        self.assertEqual([CALLBACK_URL, SESSION_URL], [url for url, _ in session.calls])

    def test_403_and_429_keep_original_circuit_without_more_requests(self):
        for status in (403, 429):
            with self.subTest(status=status):
                def blocked(session):
                    session.blocked_until = time.time() + 300
                    return Response(status)
                session = Session({CALLBACK_URL: [blocked]})
                with self.assertRaises(callback.CallbackRecoveryError) as caught:
                    self.run_callback(session)
                self.assertEqual(status, caught.exception.diagnostics["http_status"])
                self.assertGreater(session.blocked_until, time.time())
                self.assertEqual(1, len(session.calls))

    def test_session_validation_rejects_missing_invalid_expired_and_mismatched_tokens(self):
        cases = [({}, "access_token_missing"),
                 ({"accessToken": "invalid", "user": {"email": EMAIL}}, "session_invalid_response"),
                 (session_info(expiry=time.time() - 60), "access_token_expired"),
                 (session_info("other@example.test"), "session_identity_mismatch"),
                 (session_info(claim_email="other@example.test"), "session_identity_mismatch"),
                 ([], "session_invalid_response")]
        for payload, code in cases:
            with self.subTest(code=code, payload_type=type(payload).__name__):
                session = Session({CALLBACK_URL: [Response(302, location="/", set_cookie=True)], SESSION_URL: [Response(payload=payload)]})
                with self.assertRaises(callback.CallbackRecoveryError) as caught:
                    self.run_callback(session)
                self.assertEqual(code, caught.exception.code)
                self.assertEqual("session_fetch", caught.exception.diagnostics["operation"])
                self.assertTrue(caught.exception.diagnostics["response_observed"])
                self.assertEqual(2, len(session.calls))

    def test_invalid_session_json_does_not_replay_callback(self):
        session = Session({CALLBACK_URL: [Response(302, location="/", set_cookie=True)],
                           SESSION_URL: [Response(payload=ValueError("private-response"))]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session)
        self.assertEqual("session_invalid_response", caught.exception.code)
        self.assertNotIn("private-response", str(caught.exception.diagnostics))
        self.assertEqual(2, len(session.calls))

    def test_untrusted_initial_and_redirect_urls_are_not_requested(self):
        for url in ("http://auth.openai.com/continue", "https://third-party.example.test/callback", "https://user:pass@chatgpt.com/callback"):
            with self.subTest(url=url):
                session = Session({})
                with self.assertRaises(callback.CallbackRecoveryError) as caught:
                    self.run_callback(session, url)
                self.assertEqual("auth_redirect_invalid", caught.exception.code)
                self.assertEqual([], session.calls)
        session = Session({AUTH_URL: [Response(302, location="https://third-party.example.test/callback")]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session, AUTH_URL)
        self.assertEqual("auth_redirect_invalid", caught.exception.code)
        self.assertEqual(1, len(session.calls))

    def test_missing_redirect_and_loop_are_classified(self):
        session = Session({AUTH_URL: [Response(302)]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session, AUTH_URL)
        self.assertEqual("auth_redirect_invalid", caught.exception.code)
        session = Session({AUTH_URL: [Response(302, location=AUTH_URL) for _ in range(12)]})
        with self.assertRaises(callback.CallbackRecoveryError) as caught:
            self.run_callback(session, AUTH_URL)
        self.assertEqual("auth_redirect_limit", caught.exception.code)
        self.assertEqual(12, len(session.calls))

    def test_cancel_and_lease_loss_escape_without_retry(self):
        for control in (OperationCancelled("已取消"), OperationLeaseLost("租约已失效")):
            with self.subTest(control=type(control).__name__):
                session = Session({CALLBACK_URL: [control]})
                with self.assertRaises(type(control)):
                    self.run_callback(session)
                self.assertEqual(1, len(session.calls))
        session = Session({})
        def cancelled():
            raise OperationCancelled("已取消")
        with self.assertRaises(OperationCancelled):
            self.run_callback(session, checkpoint=cancelled)
        self.assertEqual([], session.calls)
