"""Offline policy tests: no challenge script or account endpoint is contacted."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from http.cookiejar import Cookie, CookieJar
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.auth.challenge import AuthCancelledError
from core.auth.state_machine import CancellationRequested, StageBudget
from core.network import cloudflare


LOGIN = "https://chatgpt.com/auth/login"
CHALLENGE = "https://chatgpt.com/cdn-cgi/challenge-platform/h/g/orchestrate/chl_page/v1"
FRAME = "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/if/ov2/test"
LOGIN_HTML = b'<html><title>ChatGPT</title><main><button>Log in</button></main><script src="/assets/login.js"></script></html>'


class Response:
    def __init__(self, status=200, body=LOGIN_HTML, *, url=LOGIN, headers=None):
        self.status_code = status
        self.content = body
        self.url = url
        self.headers = headers or {"content-type": "text/html"}
        self.closed = False

    def iter_content(self, chunk_size=8192):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset:offset + chunk_size]

    def close(self):
        self.closed = True


def challenge():
    return Response(403, b'<html><script src="/cdn-cgi/challenge-platform/a.js"></script></html>',
                    headers={"CF-Mitigated": "challenge", "Content-Type": "text/html"})


def cookie(name, value, *, domain="chatgpt.com", path="/", http_only=False, secure=True):
    return Cookie(0, name, value, None, False, domain, domain.startswith("."), domain.startswith("."),
                  path, True, secure, None, True, None, None,
                  {"HttpOnly": None} if http_only else {}, False)


class Transport:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.calls = []
        self.cookies = SimpleNamespace(jar=CookieJar())
        self.headers = {"User-Agent": "test Chrome", "Accept-Language": "en-US"}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        if callable(result):
            return result(self)
        return result


class CloudflareRecoveryTests(unittest.TestCase):
    def solve(self, transport=None, response=None, runtime=None, **kwargs):
        return cloudflare.solve_challenge(
            transport or Transport(), response or challenge(), url=kwargs.pop("url", LOGIN),
            headers=kwargs.pop("headers", {"User-Agent": "test Chrome"}),
            profile=kwargs.pop("profile", {"user_agent": "test Chrome", "navigator_language": "en-US"}),
            budget=kwargs.pop("budget", StageBudget.start(20)), runtime_factory=runtime, **kwargs)

    def test_only_explicit_403_challenge_is_classified(self):
        self.assertTrue(cloudflare.classify_challenge(challenge()).confirmed)
        for status, headers in ((403, {"server": "cloudflare", "cf-ray": "123"}),
                                (403, {}), (429, {"cf-mitigated": "challenge"}),
                                (200, {"cf-mitigated": "challenge"})):
            with self.subTest(status=status, headers=headers):
                self.assertFalse(cloudflare.classify_challenge(Response(status, headers=headers)).confirmed)

    def test_actual_wreq_headers_wrapper_supports_repeated_server_cookie_headers(self):
        from core.registration.protocol_oss_2.upstream.http_client_wreq import _Headers
        response = challenge()
        response.headers = _Headers([(b"CF-Mitigated", b"challenge"), (b"Content-Type", b"text/html"),
                                     (b"Set-Cookie", b"a=private; HttpOnly"), (b"Set-Cookie", b"b=private; HttpOnly")])
        self.assertTrue(cloudflare.classify_challenge(response).confirmed)
        class TooManyHeaders:
            def items(self):
                for index in range(1000):
                    yield ("X-Fixture-" + str(index), "value")
        response.headers = TooManyHeaders()
        self.assertFalse(cloudflare.classify_challenge(response).confirmed)

    def test_ordinary_rejections_do_not_launch_runtime_or_io(self):
        transport = Transport()
        for status in (403, 429, 200):
            original = Response(status)
            result = self.solve(transport, original, lambda *_: self.fail("unexpected runtime"))
            self.assertIs(result.response, original)
            self.assertEqual("unchanged", result.status)
        self.assertEqual([], transport.calls)

    def test_explicit_interactive_challenge_stops_before_runtime_or_io(self):
        for script in ("_cf_chl_opt.cType='interactive';", "window._cf_chl_opt = {cType:'interactive'};",
                       'window._cf_chl_opt = {"cType":"interactive"};',
                       'window._cf_chl_opt["cType"] = "interactive";'):
            with self.subTest(script=script):
                original = challenge()
                original.content = ("<html><script>" + script + "</script></html>").encode()
                transport = Transport()
                result = self.solve(transport, original, lambda *_: self.fail("unexpected runtime"))
                self.assertEqual("unsupported", result.status)
                self.assertEqual("interactive_challenge", result.reason)
                self.assertIs(result.response, original)
                self.assertEqual(0, result.request_count)
                self.assertEqual([], transport.calls)

    def test_managed_turnstile_is_not_rejected_as_explicit_interactive(self):
        original = challenge()
        original.content = (b"<html><script>window._cf_chl_opt={cType:'managed'};</script>"
                            b'<div class="cf-turnstile"></div></html>')
        transport = Transport([Response()])
        invoked = []
        def runtime(*_):
            invoked.append(True)
            return True
        self.assertEqual("verified", self.solve(transport, original, runtime).status)
        self.assertEqual([True], invoked)

    def test_exact_anonymous_url_and_headers_are_required(self):
        bad_urls = (LOGIN + "?email=secret", LOGIN + "#next", LOGIN + "/", LOGIN.replace("https", "http"),
                    LOGIN.replace("chatgpt.com", "chatgpt.com.evil.test"), LOGIN.replace("chatgpt.com", "chatgpt.com:8443"),
                    "https://auth.openai.com/api/accounts/email-otp/send", "https://chatgpt.com/")
        for url in bad_urls:
            with self.subTest(url=url):
                result = self.solve(runtime=lambda *_: self.fail("unexpected runtime"), url=url)
                self.assertEqual("blocked", result.status)
        for headers in ({"Authorization": "Bearer secret"}, {"Cookie": "session=secret"}):
            self.assertEqual("blocked", self.solve(headers=headers, runtime=lambda *_: True).status)

    def test_authenticated_cookie_store_is_ineligible(self):
        transport = Transport()
        transport.cookies.jar.set_cookie(cookie("__Secure-next-auth.session-token", "private", http_only=True))
        result = self.solve(transport, runtime=lambda *_: self.fail("unexpected runtime"))
        self.assertEqual("blocked", result.status)
        self.assertEqual([], transport.calls)

    def test_cookie_metadata_must_be_available_to_establish_anonymous_scope(self):
        transport = Transport()
        transport.cookies = {"__Secure-next-auth.session-token": "private"}
        result = self.solve(transport, runtime=lambda *_: self.fail("unexpected runtime"))
        self.assertEqual("unsupported", result.status)
        self.assertEqual([], transport.calls)

    def test_original_mutation_response_and_inherited_credentials_are_ineligible(self):
        original = challenge()
        original.request = SimpleNamespace(method="POST")
        self.assertEqual("blocked", self.solve(response=original, runtime=lambda *_: self.fail("unexpected runtime")).status)
        transport = Transport()
        transport.headers["Authorization"] = "private"
        self.assertEqual("blocked", self.solve(transport, runtime=lambda *_: self.fail("unexpected runtime")).status)

    def test_bridge_uses_original_transport_without_redirects_and_verifies_login_once(self):
        transport = Transport([Response(body=b"javascript", url=CHALLENGE, headers={"content-type": "application/javascript"}), Response()])
        def runtime(payload, bridge, budget):
            self.assertEqual(LOGIN, payload["url"])
            self.assertGreater(payload["waitMs"], 0)
            self.assertLessEqual(payload["waitMs"], 12000)
            result = bridge({"method": "GET", "url": CHALLENGE, "headers": {}, "body": None, "kind": "script"})
            self.assertEqual(b"javascript", base64.b64decode(result["body"]))
            return True
        result = self.solve(transport, runtime=runtime)
        self.assertEqual("verified", result.status)
        self.assertEqual(2, result.request_count)
        self.assertEqual([CHALLENGE, LOGIN], [call[1] for call in transport.calls])
        for _, _, kwargs in transport.calls:
            self.assertFalse(kwargs["allow_redirects"])
            self.assertLessEqual(kwargs["timeout"], 12)

    def test_business_urls_methods_and_runtime_verification_are_denied_before_io(self):
        for method, url, kind in (("POST", LOGIN, "fetch"), ("GET", LOGIN, "verification"),
                                  ("GET", "https://chatgpt.com/api/auth/csrf", "fetch"),
                                  ("GET", "https://auth.openai.com/cdn-cgi/challenge-platform/x", "script"),
                                  ("GET", "https://chatgpt.com.evil.test/cdn-cgi/challenge-platform/x", "fetch"),
                                  ("DELETE", CHALLENGE, "xhr"),
                                  ("GET", CHALLENGE.replace("/h/g", "/../api"), "fetch"),
                                  ("GET", CHALLENGE + "#fragment", "fetch"),
                                  ("GET", CHALLENGE.replace("https://", "https://user@"), "fetch")):
            with self.subTest(method=method, url=url, kind=kind):
                transport = Transport()
                def runtime(_payload, bridge, _budget):
                    bridge({"method": method, "url": url, "kind": kind})
                    return True
                result = self.solve(transport, runtime=runtime)
                self.assertEqual("blocked", result.status)
                self.assertEqual([], transport.calls)

    def test_generated_sensitive_headers_are_denied_and_cross_origin_defaults_are_minimal(self):
        for name in ("Authorization", "Cookie", "Host", "Proxy-Authorization", "X-Forwarded-For", "User-Agent"):
            with self.subTest(name=name):
                transport = Transport()
                result = self.solve(transport, runtime=lambda _p, bridge, _b: bridge(
                    {"method": "GET", "url": FRAME, "headers": {name: "private"}, "kind": "iframe"}))
                self.assertEqual("blocked", result.status)
                self.assertEqual([], transport.calls)
        transport = Transport([Response(url=FRAME), Response()])
        transport.headers["X-Private-Trace"] = "private"
        def runtime(_p, bridge, _b):
            bridge({"method": "POST", "url": FRAME, "headers": {"Content-Type": "text/plain"}, "body": "proof", "kind": "xhr"})
            return True
        self.assertEqual("verified", self.solve(transport, runtime=runtime).status)
        self.assertNotIn("X-Private-Trace", transport.calls[0][2]["headers"])
        self.assertEqual("proof", transport.calls[0][2]["data"])

    def test_redirects_are_never_followed_or_returned_to_runtime(self):
        for target in (LOGIN, CHALLENGE, "https://evil.test/"):
            transport = Transport([Response(302, url=CHALLENGE, headers={"Location": target})])
            original = challenge()
            result = self.solve(transport, original, lambda _p, bridge, _b: bridge(
                {"method": "GET", "url": CHALLENGE, "kind": "fetch"}))
            self.assertEqual("blocked", result.status)
            self.assertIs(result.response, original)
            self.assertEqual(1, len(transport.calls))

    def test_changed_effective_response_url_is_rejected(self):
        transport = Transport([Response(url="https://evil.test/")])
        result = self.solve(transport, runtime=lambda _p, bridge, _b: bridge(
            {"method": "GET", "url": CHALLENGE, "kind": "script"}))
        self.assertEqual("blocked", result.status)

    def test_subrequest_rate_limit_stops_before_any_further_io(self):
        transport = Transport([Response(429, url=CHALLENGE, headers={"Retry-After": "300"}), Response()])
        def runtime(_p, bridge, _b):
            try:
                bridge({"method": "GET", "url": CHALLENGE, "kind": "fetch"})
            except Exception:
                pass
            return True
        result = self.solve(transport, runtime=runtime)
        self.assertEqual("blocked", result.status)
        self.assertEqual("rate_limited", result.reason)
        self.assertEqual(1, len(transport.calls))

    def test_policy_failure_cannot_be_ignored_by_runtime(self):
        transport = Transport()
        def runtime(_p, bridge, _b):
            for url in ("https://evil.test/", CHALLENGE):
                try:
                    bridge({"method": "GET", "url": url, "kind": "fetch"})
                except Exception:
                    pass
            return True
        self.assertEqual("blocked", self.solve(transport, runtime=runtime).status)
        self.assertEqual([], transport.calls)

    def test_cookie_visibility_respects_domain_path_secure_and_httponly(self):
        transport = Transport([Response(url=FRAME), Response()])
        for item in (cookie("visible", "yes"), cookie("private", "secret", http_only=True),
                     cookie("scoped", "secret", path="/api"), cookie("other", "secret", domain="evil.test"),
                     cookie("frame", "frame-only", domain="challenges.cloudflare.com")):
            transport.cookies.jar.set_cookie(item)
        def runtime(payload, bridge, _b):
            self.assertEqual(["visible"], [item["name"] for item in payload["cookies"]])
            response = bridge({"method": "GET", "url": FRAME, "kind": "iframe"})
            self.assertEqual(["frame"], [item["name"] for item in response["cookies"]])
            return True
        self.assertEqual("verified", self.solve(transport, runtime=runtime).status)

    def test_actual_wreq_expired_datetime_cookie_is_not_exposed_or_authentication_evidence(self):
        import wreq
        transport = Transport([Response()])
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        transport.cookies.jar = [wreq.Cookie("__Secure-next-auth.session-token", "private", domain="chatgpt.com",
                                             path="/", expires=expired, http_only=True),
                                 wreq.Cookie("visible", "public", domain="chatgpt.com", path="/")]
        def runtime(payload, _bridge, _budget):
            self.assertEqual(["visible"], [item["name"] for item in payload["cookies"]])
            return True
        self.assertEqual("verified", self.solve(transport, runtime=runtime).status)

    def test_profile_only_exposes_browser_data_and_result_repr_excludes_secrets(self):
        original = challenge()
        original.content += b"secret-account-token"
        profile = {"user_agent": "test Chrome", "navigator_language": "en-US", "access_token": "private", "proxy": "private"}
        def runtime(payload, _bridge, _budget):
            self.assertNotIn("access_token", payload["browserIdentity"])
            self.assertNotIn("proxy", payload["browserIdentity"])
            return False
        result = self.solve(response=original, runtime=runtime, profile=profile)
        self.assertNotIn("secret-account-token", repr(result))

    def test_clearance_without_expected_content_is_not_verified(self):
        for body in (b"welcome", b"<title>ChatGPT</title>Not found", challenge().content):
            transport = Transport()
            def issue_clearance(_payload, _bridge, _budget):
                transport.cookies.jar.set_cookie(cookie("cf_clearance", "private", http_only=True))
                return True
            transport.responses = [Response(body=body)]
            original = challenge()
            result = self.solve(transport, original, issue_clearance)
            self.assertEqual("clearance_issued", result.status)
            self.assertIs(result.response, original)

    def test_expected_content_with_challenge_header_remains_unsolved(self):
        transport = Transport([Response(headers={"cf-mitigated": "challenge", "content-type": "text/html"})])
        self.assertEqual("unchanged", self.solve(transport, runtime=lambda *_: True).status)

    def test_device_identity_changes_are_not_verified(self):
        transport = Transport([Response()])
        transport.cookies.jar.set_cookie(cookie("oai-did", "before"))
        def runtime(*_):
            transport.cookies.jar.set_cookie(cookie("oai-did", "after"))
            return True
        self.assertEqual("blocked", self.solve(transport, runtime=runtime).status)

    def test_runtime_unavailable_and_optional_errors_preserve_original(self):
        for exception in (ImportError("private"), RuntimeError("private")):
            original = challenge()
            def runtime(*_):
                raise exception
            result = self.solve(response=original, runtime=runtime)
            self.assertIs(result.response, original)
            self.assertNotIn("private", result.reason)
            self.assertIn(result.status, ("unsupported", "unchanged"))

    def test_cancelled_budget_and_runtime_and_transport_cancellation_propagate(self):
        with self.assertRaises(CancellationRequested):
            self.solve(budget=StageBudget.start(10, cancel=lambda: True), runtime=lambda *_: True)
        def cancel(*_):
            raise AuthCancelledError("cancel")
        with self.assertRaises(AuthCancelledError):
            self.solve(runtime=cancel)
        transport = Transport([AuthCancelledError("cancel")])
        with self.assertRaises(AuthCancelledError):
            self.solve(transport, runtime=lambda _p, bridge, _b: bridge(
                {"method": "GET", "url": CHALLENGE, "kind": "fetch"}))

    def test_transport_cancellation_cannot_be_swallowed_by_runtime(self):
        transport = Transport([AuthCancelledError("cancel")])
        def runtime(_p, bridge, _b):
            try:
                bridge({"method": "GET", "url": CHALLENGE, "kind": "fetch"})
            except Exception:
                pass
            return True
        with self.assertRaises(AuthCancelledError):
            self.solve(transport, runtime=runtime)

    def test_registration_stop_requested_and_stream_cancellation_propagate(self):
        from core.registration.service import StopRequested
        def stop(*_):
            raise StopRequested()
        with self.assertRaises(StopRequested):
            self.solve(runtime=stop)
        cancelled = [False]
        response = Response(url=CHALLENGE)
        def chunks(chunk_size=8192):
            cancelled[0] = True
            yield b"javascript"
        response.iter_content = chunks
        transport = Transport([response])
        with self.assertRaises(CancellationRequested):
            self.solve(transport, runtime=lambda _p, bridge, _b: bridge(
                {"method": "GET", "url": CHALLENGE, "kind": "script"}),
                budget=StageBudget.start(10, cancel=lambda: cancelled[0]))
        self.assertTrue(response.closed)
        self.assertEqual(1, len(transport.calls))

    def test_response_cleanup_error_does_not_hide_cancellation(self):
        response = Response(url=CHALLENGE)
        def chunks(chunk_size=8192):
            raise AuthCancelledError()
            yield b""
        def broken_close():
            raise RuntimeError("private cleanup failure")
        response.iter_content, response.close = chunks, broken_close
        transport = Transport([response])
        with self.assertRaises(AuthCancelledError):
            self.solve(transport, runtime=lambda _p, bridge, _b: bridge(
                {"method": "GET", "url": CHALLENGE, "kind": "script"}))

    def test_expired_budget_and_post_io_deadline_prevent_verification(self):
        transport = Transport()
        result = self.solve(transport, budget=StageBudget.start(0), runtime=lambda *_: self.fail("unexpected runtime"))
        self.assertEqual("timeout", result.status)
        clock = [0.0]
        def runtime(*_):
            clock[0] = 21
            return True
        result = self.solve(transport, runtime=runtime, budget=StageBudget.start(20, clock=lambda: clock[0]))
        self.assertEqual("timeout", result.status)
        self.assertEqual([], transport.calls)

    def test_runtime_wait_reserves_shared_budget_for_verification(self):
        clock = [0.0]
        transport = Transport([Response()])
        def runtime(payload, _bridge, _budget):
            clock[0] += payload["waitMs"] / 1000
            return True
        result = self.solve(transport, runtime=runtime, budget=StageBudget.start(6, clock=lambda: clock[0]))
        self.assertEqual("verified", result.status)
        self.assertGreaterEqual(transport.calls[0][2]["timeout"], 1.5)

    def test_deadline_is_checked_after_final_stream_completion(self):
        clock = [0.0]
        response = Response()
        def chunks(chunk_size=8192):
            yield LOGIN_HTML
            clock[0] = 20
        response.iter_content = chunks
        result = self.solve(Transport([response]), runtime=lambda *_: True,
                            budget=StageBudget.start(6, clock=lambda: clock[0]))
        self.assertEqual("timeout", result.status)

    def test_request_count_and_body_bounds_stop_without_business_replay(self):
        transport = Transport([Response(url=CHALLENGE)] * 10)
        def runtime(_p, bridge, _b):
            for _ in range(10):
                bridge({"method": "GET", "url": CHALLENGE, "kind": "fetch"})
            return True
        with patch.object(cloudflare, "MAX_REQUESTS", 2):
            result = self.solve(transport, runtime=runtime)
        self.assertEqual("blocked", result.status)
        self.assertEqual(2, result.request_count)
        self.assertEqual(2, len(transport.calls))
        transport = Transport()
        with patch.object(cloudflare, "MAX_REQUEST_BODY_BYTES", 4):
            result = self.solve(transport, runtime=lambda _p, bridge, _b: bridge(
                {"method": "POST", "url": CHALLENGE, "body": "oversized", "kind": "xhr"}))
        self.assertEqual("blocked", result.status)
        self.assertEqual([], transport.calls)

    def test_streamed_response_and_total_bytes_are_bounded(self):
        oversized = Response(body=b"x" * 200, url=CHALLENGE)
        transport = Transport([oversized])
        with patch.object(cloudflare, "MAX_RESPONSE_BYTES", 128):
            result = self.solve(transport, runtime=lambda _p, bridge, _b: bridge(
                {"method": "GET", "url": CHALLENGE, "kind": "script"}))
        self.assertEqual("blocked", result.status)
        self.assertTrue(oversized.closed)
        transport = Transport([Response(body=b"x" * 20, url=CHALLENGE)] * 4)
        def runtime(_p, bridge, _b):
            for _ in range(4):
                bridge({"method": "GET", "url": CHALLENGE, "kind": "fetch"})
            return True
        with patch.object(cloudflare, "MAX_TOTAL_BYTES", 50):
            result = self.solve(transport, runtime=runtime)
        self.assertEqual("blocked", result.status)
        self.assertEqual(3, len(transport.calls))

    def test_oversized_initial_html_never_launches_runtime(self):
        with patch.object(cloudflare, "MAX_RESPONSE_BYTES", 5):
            result = self.solve(runtime=lambda *_: self.fail("unexpected runtime"))
        self.assertEqual("blocked", result.status)


if __name__ == "__main__":
    unittest.main()
