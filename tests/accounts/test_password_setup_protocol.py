"""补密码协议的请求边界、明确结果与未知结果。"""
import json
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from core.accounts.password_setup import protocol
from core.email import mailbox_wait


AUTH = "https://auth.openai.com"
CHATGPT = "https://chatgpt.com"
AUTHORIZE = AUTH + "/authorize?state=fixture-state"
PASSWORD_PAGE = AUTH + "/reset-password/new-password"
CALLBACK = CHATGPT + "/api/auth/callback/openai?code=fixture-code&state=fixture-state"


class Response:
    def __init__(self, payload=None, *, url="", status=200, location=None):
        self.payload, self.url, self.status_code = payload, url, status
        self.headers = {"location": location} if location else {}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    device_id = "fixture-device"
    browser_profile = {"user_agent": "fixture-ua", "build_id": "stale-build"}
    sentinel_sid = "fixture-sentinel-sid"

    def __init__(self, gets, posts):
        self.gets, self.posts, self.events = list(gets), list(posts), []

    def _request(self, method, url, kwargs):
        self.events.append((method, url, kwargs))
        result = (self.gets if method == "GET" else self.posts).pop(0)
        if isinstance(result, Exception):
            raise result
        result.url = result.url or url
        return result

    def get(self, url, **kwargs):
        return self._request("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, kwargs)

    def get_nextauth_headers(self, referer):
        return {"referer": referer, "user-agent": "fixture-ua"}

    def get_auth_headers(self, referer):
        return {"referer": referer, "origin": AUTH, "content-type": "application/json"}

    def get_auth_navigate_headers(self, referer, **kwargs):
        return {"referer": referer}

    def get_chatgpt_navigate_headers(self, referer, **kwargs):
        return {"referer": referer}

    def auth_cookie_header(self):
        return "fixture-cookie"


class PasswordSetupProtocolTests(unittest.TestCase):
    password = "Fixture_Password_4826!"

    def setUp(self):
        self.challenge = patch.object(protocol, "request_sentinel_token", return_value={"token": "fixture-challenge"})
        self.builder = patch.object(protocol, "build_sentinel_header", return_value=("fixture-otp-token", "fixture-otp-so"))
        self.runner = patch.object(protocol, "generate_sentinel_token", return_value=json.dumps({"p": "fixture-proof", "c": "fixture-challenge", "id": "fixture-device", "flow": "password_reset", "_so": "fixture-so"}))
        self.challenge.start()
        self.builder.start()
        self.generate = self.runner.start()
        self.addCleanup(self.challenge.stop)
        self.addCleanup(self.builder.stop)
        self.addCleanup(self.runner.stop)

    def session(self, *, final=None, landing=PASSWORD_PAGE):
        return FakeSession(
            [Response({"csrfToken": "fixture-csrf"}), Response(url=landing)],
            [Response({"url": AUTHORIZE}), final or Response({"page": {"type": "external_url"}, "continue_url": CALLBACK})],
        )

    def run_driver(self, session, **kwargs):
        return protocol.add_password(session, "user@example.test", self.password, **kwargs)

    def test_direct_password_page_uses_independent_signin_and_hooks_in_order(self):
        session = self.session()
        dispatched = lambda: session.events.append(("dispatch",))
        confirmed = lambda: session.events.append(("confirm",))
        result = self.run_driver(session, on_dispatched=dispatched, on_confirmed=confirmed)
        self.assertEqual(result, {"ok": True, "status": "success", "password_added": True})
        signin = next(item for item in session.events if item[0] == "POST")
        self.assertEqual(parse_qs(urlsplit(signin[1]).query), {"connection": ["password"], "login_hint": ["user@example.test"], "reauth": ["password"], "post_login_add_password": ["true"], "max_age": ["0"], "ext-oai-did": ["fixture-device"]})
        self.assertEqual(parse_qs(signin[2]["data"]), {"callbackUrl": [CHATGPT + "/"], "csrfToken": ["fixture-csrf"], "json": ["true"]})
        self.assertEqual(session.events[-3][0], "dispatch")
        self.assertEqual(session.events[-2][1], AUTH + "/api/accounts/password/add")
        self.assertEqual(json.loads(session.events[-2][2]["data"]), {"password": self.password})
        self.assertEqual(session.events[-1][0], "confirm")
        self.assertNotIn(self.password, str(result))
        self.assertEqual(self.generate.call_args.kwargs["page_url"], PASSWORD_PAGE)
        self.assertEqual(self.generate.call_args.kwargs["browser_profile"]["build_id"], "")
        self.assertEqual(session.browser_profile["build_id"], "stale-build")
        sent = session.events[-2][2]["headers"]
        self.assertNotIn("_so", sent["openai-sentinel-token"])
        self.assertEqual(json.loads(sent["openai-sentinel-so-token"])["flow"], "password_reset")

    def test_otp_is_explicitly_sent_before_wait_and_timestamp_precedes_send(self):
        session = FakeSession(
            [Response({"csrfToken": "fixture-csrf"}), Response(url=AUTH + "/email-verification"),
             Response(url=AUTH + "/email-verification"), Response(url=PASSWORD_PAGE)],
            [Response({"url": AUTHORIZE}), Response({"continue_url": PASSWORD_PAGE}), Response({"page": {"type": "external_url"}, "continue_url": CALLBACK})],
        )
        checkpoint = Mock()
        def clock():
            self.assertTrue(any(item[1] == AUTHORIZE for item in session.events))
            self.assertFalse(any(item[1].endswith("/email-otp/send") for item in session.events))
            return 123.5
        def received(*_args, **_kwargs):
            self.assertTrue(any(item[1].endswith("/email-otp/send") for item in session.events))
            self.assertEqual(mailbox_wait.cooperative_poll_limit(75), 5)
            self.assertEqual(mailbox_wait.bounded_timeout(30), 10)
            return "123456"
        with patch.object(protocol.time, "time", side_effect=clock), patch.object(protocol.email_provider, "resolve_email_source", return_value="generic_api") as source, patch.object(protocol.email_provider, "wait_for_otp", side_effect=received) as wait:
            self.run_driver(session, checkpoint=checkpoint)
        wait.assert_called_once_with("user@example.test", after_ts=123.5, email_source="generic_api")
        self.assertEqual(mailbox_wait.bounded_timeout(30), 30)
        source.assert_called_once_with("user@example.test", fallback=False)
        otp = next(item for item in session.events if item[1].endswith("/email-otp/validate"))
        self.assertEqual(json.loads(otp[2]["data"]), {"code": "123456"})
        self.assertEqual(otp[2]["headers"]["openai-sentinel-token"], "fixture-otp-token")
        self.assertGreaterEqual(checkpoint.call_count, 7)

    def test_custom_provider_uses_new_request_generation(self):
        session = FakeSession([Response({"csrfToken": "fixture-csrf"}), Response(url=AUTH + "/email-verification"), Response(url=AUTH + "/email-verification"), Response(url=PASSWORD_PAGE)], [Response({"url": AUTHORIZE}), Response({"continue_url": PASSWORD_PAGE}), Response({"page": {"type": "external_url"}, "continue_url": CALLBACK})])
        provider = Mock(return_value="123456")
        with patch.object(protocol.time, "time", return_value=456.0):
            self.run_driver(session, otp_provider=provider)
        provider.assert_called_once_with("user@example.test", after_ts=456.0)

    def test_rejected_send_does_not_wait_or_submit_password(self):
        for response in (Response({}, status=403), Response(url=AUTH + "/error")):
            with self.subTest(status=response.status_code):
                session = self.session(landing=AUTH + "/email-verification")
                session.gets.append(response)
                provider, dispatched = Mock(), Mock()
                with self.assertRaises(protocol.ProtocolPasswordSetupError):
                    self.run_driver(session, otp_provider=provider, on_dispatched=dispatched)
                provider.assert_not_called()
                dispatched.assert_not_called()

    def test_email_otp_then_existing_totp_can_reach_password_add(self):
        mfa = AUTH + "/mfa-challenge/factor-1"
        session = FakeSession(
            [Response({"csrfToken": "fixture-csrf"}), Response(url=AUTH + "/email-verification"),
             Response(url=AUTH + "/email-verification"), Response(url=PASSWORD_PAGE)],
            [Response({"url": AUTHORIZE}), Response({"page": {"type": "mfa_challenge"}, "continue_url": mfa}),
             Response({}), Response({"continue_url": PASSWORD_PAGE}),
             Response({"page": {"type": "external_url"}, "continue_url": CALLBACK})],
        )
        with patch.object(protocol.protocol_auth, "_totp_code", return_value="654321") as code:
            result = self.run_driver(session, otp_provider=Mock(return_value="123456"), totp_secret="fixture-secret")
        self.assertTrue(result["password_added"])
        code.assert_called_once_with("fixture-secret")
        posts = [item for item in session.events if item[0] == "POST"]
        self.assertEqual([urlsplit(item[1]).path for item in posts], [
            "/api/auth/signin/openai", "/api/accounts/email-otp/validate", "/api/accounts/mfa/issue_challenge",
            "/api/accounts/mfa/verify", "/api/accounts/password/add",
        ])
        self.assertEqual(json.loads(posts[-2][2]["data"]), {"id": "factor-1", "type": "totp", "code": "654321"})
        self.assertNotIn("fixture-secret", str(session.events))

    def test_direct_mfa_landing_uses_existing_totp(self):
        session = self.session(landing=AUTH + "/mfa-challenge/factor-1")
        session.gets.append(Response(url=PASSWORD_PAGE))
        session.posts[1:1] = [Response({}), Response({"continue_url": PASSWORD_PAGE})]
        with patch.object(protocol.protocol_auth, "_totp_code", return_value="654321"):
            self.assertTrue(self.run_driver(session, totp_secret="fixture-secret")["password_added"])

    def test_mfa_authorize_continuation_must_land_on_new_password_page(self):
        for landing in (PASSWORD_PAGE, AUTH + "/email-verification"):
            with self.subTest(landing=landing):
                session = self.session(landing=AUTH + "/mfa-challenge/factor-1")
                session.gets.append(Response(url=landing))
                session.posts[1:1] = [Response({}), Response({"continue_url": AUTH + "/authorize/continue?state=fixture"})]
                with patch.object(protocol.protocol_auth, "_totp_code", return_value="654321"):
                    if landing == PASSWORD_PAGE:
                        self.assertTrue(self.run_driver(session, totp_secret="fixture-secret")["password_added"])
                    else:
                        with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
                            self.run_driver(session, totp_secret="fixture-secret")
                        self.assertFalse(raised.exception.request_unknown)
                        self.assertFalse(any(item[1].endswith("/password/add") for item in session.events))

    def test_mfa_rejection_or_untrusted_continuation_never_submits_password(self):
        for final in (Response({"error": {"code": "invalid_totp"}}, status=400),
                      Response({"continue_url": "https://foreign.example/reset-password/new-password"})):
            with self.subTest(status=final.status_code):
                session = self.session(landing=AUTH + "/mfa-challenge/factor-1")
                session.posts[1:1] = [Response({}), final]
                dispatched = Mock()
                with patch.object(protocol.protocol_auth, "_totp_code", return_value="654321"):
                    with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
                        self.run_driver(session, totp_secret="fixture-secret", on_dispatched=dispatched)
                self.assertFalse(raised.exception.request_unknown)
                dispatched.assert_not_called()

    def test_cancel_after_mfa_challenge_stops_before_code_submission(self):
        session = self.session(landing=AUTH + "/mfa-challenge/factor-1")
        session.posts.insert(1, Response({}))
        def checkpoint():
            if any(item[1].endswith("/mfa/issue_challenge") for item in session.events):
                raise protocol.OperationCancelled("fixture-cancel")
        with self.assertRaises(protocol.OperationCancelled):
            self.run_driver(session, totp_secret="fixture-secret", checkpoint=checkpoint)
        self.assertFalse(any(item[1].endswith("/mfa/verify") for item in session.events))

    def test_only_final_transport_failure_is_request_unknown(self):
        for at_final in (False, True):
            with self.subTest(at_final=at_final):
                session = self.session(final=TimeoutError("fixture-password-and-cookie"))
                if not at_final:
                    session.gets[0] = TimeoutError("fixture-password-and-cookie")
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
                    self.run_driver(session)
                self.assertEqual(raised.exception.request_unknown, at_final)
                self.assertNotIn("fixture-password-and-cookie", str(raised.exception))

    def test_final_invalid_json_or_unfinished_response_never_confirms(self):
        for payload in (ValueError("fixture-private-body"), {}, {"page": {"type": "external_url"}}, {"page": {"type": "external_url"}, "continue_url": PASSWORD_PAGE}, {"page": {"type": "external_url"}, "continue_url": AUTH + "/email-verification"}, {"page": {"type": "external_url"}, "continue_url": "https://foreign.example/callback"}, {"page": {"type": "password"}, "continue_url": CALLBACK}):
            with self.subTest(payload=type(payload).__name__):
                confirmed = Mock()
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
                    self.run_driver(self.session(final=Response(payload)), on_confirmed=confirmed)
                self.assertTrue(raised.exception.request_unknown)
                confirmed.assert_not_called()
                self.assertNotIn("fixture-private-body", str(raised.exception))

    def test_already_set_and_expired_session_are_known_rejections(self):
        for code, expected in (("password_already_exists", "password_setup_already_set"), ("invalid_state", "password_setup_session_expired")):
            with self.subTest(code=code):
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
                    self.run_driver(self.session(final=Response({"error": {"code": code, "message": "fixture-private-body"}}, status=400)))
                self.assertEqual(raised.exception.code, expected)
                self.assertFalse(raised.exception.request_unknown)

    def test_final_server_failure_or_missing_http_status_preserves_unknown_result(self):
        for status in (500, 502, 503, 0):
            for at_final in (False, True):
                with self.subTest(status=status, at_final=at_final):
                    session = self.session(final=Response({}, status=status))
                    if not at_final:
                        session.gets[0] = Response({}, status=status)
                    confirmed = Mock()
                    with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
                        self.run_driver(session, on_confirmed=confirmed)
                    self.assertEqual(raised.exception.request_unknown, at_final)
                    confirmed.assert_not_called()

    def test_explicit_business_rejection_remains_known_even_with_server_error_status(self):
        session = self.session(final=Response({"error": {"code": "password_already_exists"}}, status=500))
        with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
            self.run_driver(session)
        self.assertEqual(raised.exception.code, "password_setup_already_set")
        self.assertFalse(raised.exception.request_unknown)

    def test_expired_login_and_mfa_landing_do_not_dispatch(self):
        for landing, expected in ((AUTH + "/log-in", "password_setup_session_expired"), (AUTH + "/mfa-challenge/fixture", "password_setup_mfa_secret_missing")):
            with self.subTest(landing=landing):
                dispatched = Mock()
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
                    self.run_driver(self.session(landing=landing), on_dispatched=dispatched)
                self.assertEqual(raised.exception.code, expected)
                self.assertFalse(raised.exception.request_unknown)
                dispatched.assert_not_called()

    def test_cancel_before_final_dispatch_preserves_control_exception(self):
        session = self.session()
        dispatched = Mock()
        stopped = RuntimeError("fixture-checkpoint-stopped")
        def checkpoint():
            if self.generate.called:
                raise stopped
        with self.assertRaises(RuntimeError) as raised:
            self.run_driver(session, checkpoint=checkpoint, on_dispatched=dispatched)
        self.assertIs(raised.exception, stopped)
        dispatched.assert_not_called()
        self.assertFalse(any(item[1].endswith("/password/add") for item in session.events))

    def test_trusted_continue_url_requires_completed_landing(self):
        session = self.session(final=Response({"continue_url": AUTH + "/authorize/continue?state=fixture"}))
        session.gets.append(Response(url=CHATGPT + "/"))
        self.assertTrue(self.run_driver(session)["password_added"])
        failed = self.session(final=Response({"continue_url": AUTH + "/authorize/continue?state=fixture"}))
        failed.gets.append(Response(url=AUTH + "/email-verification"))
        with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
            self.run_driver(failed)
        self.assertTrue(raised.exception.request_unknown)

    def test_callback_failure_after_password_response_preserves_unknown_result(self):
        session = self.session(final=Response({"continue_url": AUTH + "/authorize/continue?state=fixture"}))
        session.gets.append(Response({"error": {"code": "forbidden"}}, status=403))
        confirmed = Mock()
        with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
            self.run_driver(session, on_confirmed=confirmed)
        self.assertTrue(raised.exception.request_unknown)
        confirmed.assert_not_called()

    def test_wrong_sentinel_flow_stops_before_password_dispatch(self):
        self.generate.return_value = json.dumps({"p": "fixture-proof", "c": "fixture-challenge", "id": "other-device", "flow": "email_otp_validate"})
        dispatched = Mock()
        with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
            self.run_driver(self.session(), on_dispatched=dispatched)
        self.assertEqual(raised.exception.code, "password_setup_sentinel_failed")
        self.assertFalse(raised.exception.request_unknown)
        dispatched.assert_not_called()

    def test_default_otp_cancellation_is_not_wrapped(self):
        session = self.session(landing=AUTH + "/email-verification")
        session.gets.append(Response(url=AUTH + "/email-verification"))
        cancelled = protocol.OperationCancelled("fixture-cancel")
        with patch.object(protocol.email_provider, "resolve_email_source", return_value="generic_api"), patch.object(protocol.email_provider, "wait_for_otp", side_effect=cancelled):
            with self.assertRaises(protocol.OperationCancelled) as raised:
                self.run_driver(session)
        self.assertIs(raised.exception, cancelled)

    def test_redirect_destination_is_checked_before_sending_the_next_get(self):
        session = self.session()
        session.gets[1] = Response(status=302, location="https://foreign.example/authorize")
        with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
            self.run_driver(session)
        self.assertEqual(raised.exception.code, "password_setup_untrusted_redirect")
        self.assertFalse(any("foreign.example" in item[1] for item in session.events))

    def test_untrusted_signin_url_is_rejected_without_following(self):
        session = self.session()
        session.posts[0] = Response({"url": "https://foreign.example/authorize"})
        with self.assertRaises(protocol.ProtocolPasswordSetupError) as raised:
            self.run_driver(session)
        self.assertEqual(raised.exception.code, "password_setup_untrusted_redirect")
        self.assertFalse(raised.exception.request_unknown)
        self.assertEqual(len([item for item in session.events if item[0] == "GET"]), 1)
