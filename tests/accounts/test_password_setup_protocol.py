"""补密码协议的请求边界、明确结果与未知结果。"""
import json
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Queue
from threading import Thread
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from core.accounts.password_setup import protocol
from core.email import mailbox_wait


AUTH = "https://auth.openai.com"
CHATGPT = "https://chatgpt.com"
AUTHORIZE = AUTH + "/authorize?state=fixture-state"
PASSWORD_PAGE = AUTH + "/reset-password/new-password"
CALLBACK = CHATGPT + "/api/auth/callback/openai?code=fixture-code&state=fixture-state"
EMAIL_PAGE = AUTH + "/email-verification"
SEND_PAGE = {"page": {"type": "email_otp_verification"}}


def email_context(*, pending=True, **changes):
    return Response({"client_auth_session": {"session_id": "fixture-auth-session", "email": "user@example.test",
        "email_verification_mode": "passwordless_login", "passwordless_email_otp_send_pending": pending, **changes}})


class Response:
    def __init__(self, payload=None, *, url="", status=200, location=None):
        self.payload, self.url, self.status_code = payload, url, status
        self.headers = {"location": location} if location else {}
        self.text = json.dumps(payload) if not isinstance(payload, Exception) else ""

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

    def test_transport_fault_flag_preserves_unknown_submission_without_private_error(self):
        for final in (False, True):
            with self.subTest(final=final):
                session = FakeSession([], [RuntimeError("curl: (56) Proxy CONNECT aborted; private-token")])
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as caught:
                    protocol._request(session, "post", AUTH + "/api/accounts/password/add", final=final)
                self.assertEqual(final, caught.exception.request_unknown)
                self.assertTrue(caught.exception.proxy_transport_failed)
                self.assertNotIn("private-token", str(caught.exception))


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

    def send_code(self, session, **kwargs):
        return protocol._send_email_verification_code(session, "user@example.test", referer=EMAIL_PAGE,
                                                      after_ts=123.5, **kwargs)

    def test_initial_send_uses_pending_context_and_authorize_sentinel_without_body(self):
        session = FakeSession([email_context(), email_context()], [Response(SEND_PAGE)])
        rotate = session.rotate_document_navigation_id = Mock()
        with self.assertLogs(protocol.logger, level="INFO") as logs:
            self.assertEqual(123.5, self.send_code(session))
        self.assertEqual(["GET", "GET", "POST"], [item[0] for item in session.events])
        self.assertEqual(AUTH + "/api/accounts/passwordless/send-otp", session.events[-1][1])
        self.assertNotIn("data", session.events[-1][2])
        self.assertIsNone(session.events[-1][2]["headers"]["content-type"])
        self.assertEqual("fixture-otp-token", session.events[-1][2]["headers"]["openai-sentinel-token"])
        self.assertTrue(session.events[-1][2]["headers"]["x-access-flow-invocation-id"])
        self.assertEqual("authorize_continue", protocol.build_sentinel_header.call_args.args[2])
        self.generate.assert_not_called()
        rotate.assert_called_once_with()
        self.assertNotIn("user@example.test", " ".join(logs.output))
        self.assertNotIn("fixture-auth-session", " ".join(logs.output))

    def test_pending_with_undefined_mode_uses_initial_send(self):
        context = email_context().payload
        context["client_auth_session"].pop("email_verification_mode")
        session = FakeSession([Response(context), Response(context)], [Response(SEND_PAGE)])
        self.send_code(session)
        self.assertTrue(session.events[-1][1].endswith("/passwordless/send-otp"))

    def test_explicit_resend_uses_post_and_accepts_empty_http_ok_without_sentinel(self):
        for status in (200, 204):
            with self.subTest(status=status):
                session = FakeSession([email_context(pending=False)], [Response(status=status)])
                with patch.object(protocol.time, "time", return_value=234.5):
                    self.assertEqual(234.5, self.send_code(session))
                sent = session.events[-1]
                self.assertEqual(("POST", AUTH + "/api/accounts/email-otp/resend"), sent[:2])
                self.assertNotIn("openai-sentinel-token", sent[2]["headers"])
                self.assertNotIn("openai-sentinel-so-token", sent[2]["headers"])
                self.assertIsNone(sent[2]["headers"]["content-type"])
                self.assertNotIn("data", sent[2])
        protocol.request_sentinel_token.assert_not_called()

    def test_initial_and_resend_transport_omit_content_type_and_keep_empty_body(self):
        from curl_cffi import CurlOpt
        from curl_cffi.requests import Session

        observed = Queue()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                observed.put({"content_type": self.headers.get("Content-Type"),
                              "content_length": self.headers.get("Content-Length"), "body_bytes": len(body)})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(SEND_PAGE).encode())

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with Session(impersonate="chrome", trust_env=False, curl_options={CurlOpt.PROXY: ""}) as transport:
                for initial in (True, False):
                    with self.subTest(initial=initial):
                        session = FakeSession([email_context(), email_context()] if initial else
                                              [email_context(pending=False)], [])
                        def post(url, **kwargs):
                            session.events.append(("POST", url, kwargs))
                            return transport.post(f"http://127.0.0.1:{server.server_port}/", **kwargs, timeout=5)
                        session.post = post
                        self.send_code(session)
                        self.assertEqual({"content_type": None, "content_length": "0", "body_bytes": 0},
                                         observed.get(timeout=5))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_pending_unsupported_mode_and_missing_pending_use_the_page_resend_action(self):
        missing_pending = email_context()
        missing_pending.payload["client_auth_session"].pop("passwordless_email_otp_send_pending")
        for context in (email_context(email_verification_mode="post_auth_email_verification"), missing_pending):
            with self.subTest(context=context.payload):
                session = FakeSession([context], [Response(status=204)])
                self.send_code(session)
                self.assertTrue(session.events[-1][1].endswith("/email-otp/resend"))

    def test_context_requires_nested_target_identity_and_valid_field_types(self):
        cases = (Response({"session_id": "fixture", "email": "user@example.test"}),
                 email_context(session_id=""), email_context(email="other@example.test"),
                 email_context(email_verification_mode=[]), email_context(pending=1),
                 email_context(email_verification_mode=None), email_context(pending=None))
        for response in cases:
            with self.subTest(payload=response.payload):
                session = FakeSession([response], [])
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as caught:
                    self.send_code(session)
                self.assertEqual("password_setup_otp_context_invalid", caught.exception.code)
                self.assertFalse(any(item[0] == "POST" for item in session.events))
                self.assertNotIn("other@example.test", str(caught.exception))

    def test_context_rechecked_after_sentinel_and_changes_stop_before_send(self):
        for changes in ({"session_id": "different-session"}, {"email_verification_mode": "passwordless_signup"}):
            with self.subTest(changes=changes):
                session = FakeSession([email_context(), email_context(**changes)], [])
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as caught:
                    self.send_code(session)
                self.assertEqual("password_setup_otp_context_changed", caught.exception.code)
                self.assertFalse(caught.exception.request_unknown)
                self.assertFalse(any(item[0] == "POST" for item in session.events))

    def test_pending_cleared_during_sentinel_does_not_send_twice(self):
        session = FakeSession([email_context(), email_context(pending=False)], [])
        self.assertEqual(123.5, self.send_code(session))
        self.assertFalse(any(item[0] == "POST" for item in session.events))

    def test_initial_send_requires_real_json_receipt_not_a_document_page_or_error_payload(self):
        for response in (Response({}, url=EMAIL_PAGE), Response(ValueError("private-body")),
                         Response({"page": {"type": "email_otp_verification", "payload": {"errors": {"formErrors": ["private-body"]}}}}),
                         Response({"page": {"type": "password"}}),
                         Response({"page": {"type": "email_verification"}}), Response({"page": {"type": "email_otp"}})):
            with self.subTest(payload_type=type(response.payload).__name__):
                session = FakeSession([email_context(), email_context()], [response])
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as caught:
                    self.send_code(session)
                self.assertIn(caught.exception.code, {"password_setup_otp_send_unconfirmed", "password_setup_response_invalid"})
                self.assertFalse(caught.exception.request_unknown)
                self.assertEqual(1, len([item for item in session.events if item[0] == "POST"]))
                self.assertNotIn("private-body", str(caught.exception))

    def test_send_http_rejection_keeps_classification_and_never_auto_switches_to_resend(self):
        for status, expected in ((403, "password_setup_security_check"), (429, "password_setup_rate_limited"),
                                 (503, "password_setup_http_rejected")):
            with self.subTest(status=status):
                session = FakeSession([email_context(), email_context()], [Response({}, status=status)])
                with self.assertRaises(protocol.ProtocolPasswordSetupError) as caught:
                    self.send_code(session)
                self.assertEqual(expected, caught.exception.code)
                self.assertFalse(caught.exception.request_unknown)
                self.assertEqual(1, len([item for item in session.events if item[0] == "POST"]))

    def test_cancel_after_context_recheck_stops_before_initial_post(self):
        for control in (protocol.OperationCancelled, protocol.OperationLeaseLost, protocol.CancellationRequested):
            with self.subTest(control=control):
                session = FakeSession([email_context(), email_context()], [])
                signal = control("fixture-stop")
                def checkpoint():
                    if len(session.events) == 2:
                        raise signal
                with self.assertRaises(control) as caught:
                    self.send_code(session, checkpoint=checkpoint)
                self.assertIs(signal, caught.exception)
                self.assertFalse(any(item[0] == "POST" for item in session.events))

    def test_initial_send_transport_error_preserves_proxy_fault_without_password_unknown(self):
        session = FakeSession([email_context(), email_context()], [RuntimeError("Proxy CONNECT aborted private-route")])
        with self.assertRaises(protocol.ProtocolPasswordSetupError) as caught:
            self.send_code(session)
        self.assertEqual("password_setup_network_failed", caught.exception.code)
        self.assertTrue(caught.exception.proxy_transport_failed)
        self.assertFalse(caught.exception.request_unknown)
        self.assertNotIn("private-route", str(caught.exception))

    def test_response_diagnostics_distinguish_context_recheck_and_initial_post_failure(self):
        cases = (([email_context(), Response({"error": {"code": "invalid_request"}}, status=400)], [],
                  "operation=otp_context_recheck status=400", "otp_initial_send"),
                 ([email_context(), email_context()], [Response({"error": {"code": "invalid_auth_step"}}, status=400)],
                  "operation=otp_initial_send status=400", None))
        for gets, posts, expected, absent in cases:
            with self.subTest(expected=expected):
                session = FakeSession(gets, posts)
                with self.assertLogs(protocol.logger, level="INFO") as logs:
                    with self.assertRaises(protocol.ProtocolPasswordSetupError):
                        self.send_code(session)
                output = " ".join(logs.output)
                self.assertIn("operation=otp_context status=200", output)
                self.assertIn(expected, output)
                if absent:
                    self.assertNotIn(absent, output)

    def test_response_diagnostics_only_log_safe_page_and_error_enums(self):
        payloads = (({"page": {"type": "email_otp_verification"}, "error": {"code": "invalid_state"}},
                     "page.type=email_otp_verification remote.error.code=invalid_state"),
                    ({"page": {"type": "private-page"}, "error": {"code": "private-code", "message": "private-body"}},
                     "page.type=other remote.error.code=other"),
                    ({"page": {"type": None}, "error": {"code": None}}, "page.type=other remote.error.code=other"),
                    ({}, "page.type=missing remote.error.code=missing"))
        for payload, expected in payloads:
            with self.subTest(expected=expected):
                response = Response({**payload, "email": "private@example.test", "token": "private-token"}, status=400)
                with self.assertLogs(protocol.logger, level="INFO") as logs:
                    protocol._log_otp_response("otp_resend", response)
                output = " ".join(logs.output)
                self.assertIn("operation=otp_resend status=400", output)
                self.assertIn(expected, output)
                for private in ("private-page", "private-code", "private-body", "private@example.test", "private-token"):
                    self.assertNotIn(private, output)

    def test_response_diagnostics_reject_ambiguous_or_oversized_json(self):
        bodies = ('{"error":{"code":"invalid_state","code":"private-code"}}',
                  '{"error":{"code":"invalid_state"},"extra":"' + "x" * 65536 + '"}')
        for body in bodies:
            with self.subTest(bytes=len(body)):
                response = Response({}, status=400)
                response.text = body
                with self.assertLogs(protocol.logger, level="INFO") as logs:
                    protocol._log_otp_response("otp_context", response)
                self.assertIn("remote.error.code=missing", " ".join(logs.output))
                self.assertNotIn("invalid_state", " ".join(logs.output))

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
             email_context(), email_context(), Response(url=PASSWORD_PAGE)],
            [Response({"url": AUTHORIZE}), Response(SEND_PAGE), Response({"continue_url": PASSWORD_PAGE}), Response({"page": {"type": "external_url"}, "continue_url": CALLBACK})],
        )
        checkpoint = Mock()
        def clock():
            self.assertFalse(any(item[1] == AUTHORIZE for item in session.events))
            self.assertFalse(any(item[1].endswith("/passwordless/send-otp") for item in session.events))
            return 123.5
        def received(*_args, **_kwargs):
            self.assertTrue(any(item[1].endswith("/passwordless/send-otp") for item in session.events))
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
        sent = next(item for item in session.events if item[1].endswith("/passwordless/send-otp"))
        self.assertEqual("POST", sent[0])
        self.assertNotIn("data", sent[2])
        self.assertFalse(any(item[1].endswith("/email-otp/send") for item in session.events))

    def test_custom_provider_uses_new_request_generation(self):
        session = FakeSession([Response({"csrfToken": "fixture-csrf"}), Response(url=EMAIL_PAGE), email_context(), email_context(), Response(url=PASSWORD_PAGE)], [Response({"url": AUTHORIZE}), Response(SEND_PAGE), Response({"continue_url": PASSWORD_PAGE}), Response({"page": {"type": "external_url"}, "continue_url": CALLBACK})])
        provider = Mock(return_value="123456")
        with patch.object(protocol.time, "time", return_value=456.0):
            self.run_driver(session, otp_provider=provider)
        provider.assert_called_once_with("user@example.test", after_ts=456.0)

    def test_rejected_send_does_not_wait_or_submit_password(self):
        for response in (Response({}, status=403), Response(status=302, location=AUTH + "/error")):
            with self.subTest(status=response.status_code):
                session = self.session(landing=AUTH + "/email-verification")
                session.gets.append(email_context(pending=False))
                session.posts.insert(1, response)
                provider, dispatched = Mock(), Mock()
                with self.assertRaises(protocol.ProtocolPasswordSetupError):
                    self.run_driver(session, otp_provider=provider, on_dispatched=dispatched)
                provider.assert_not_called()
                dispatched.assert_not_called()

    def test_email_otp_then_existing_totp_can_reach_password_add(self):
        mfa = AUTH + "/mfa-challenge/factor-1"
        session = FakeSession(
            [Response({"csrfToken": "fixture-csrf"}), Response(url=AUTH + "/email-verification"),
             email_context(), email_context(), Response(url=PASSWORD_PAGE)],
            [Response({"url": AUTHORIZE}), Response(SEND_PAGE), Response({"page": {"type": "mfa_challenge"}, "continue_url": mfa}),
             Response({}), Response({"continue_url": PASSWORD_PAGE}),
             Response({"page": {"type": "external_url"}, "continue_url": CALLBACK})],
        )
        with patch.object(protocol.protocol_auth, "_totp_code", return_value="654321") as code:
            result = self.run_driver(session, otp_provider=Mock(return_value="123456"), totp_secret="fixture-secret")
        self.assertTrue(result["password_added"])
        code.assert_called_once_with("fixture-secret")
        posts = [item for item in session.events if item[0] == "POST"]
        self.assertEqual([urlsplit(item[1]).path for item in posts], [
            "/api/auth/signin/openai", "/api/accounts/passwordless/send-otp", "/api/accounts/email-otp/validate", "/api/accounts/mfa/issue_challenge",
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
        session.gets.append(email_context(pending=False))
        session.posts.insert(1, Response(status=204))
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
