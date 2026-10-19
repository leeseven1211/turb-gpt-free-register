"""认证接口的响应头诊断只保留安全证据，并兼容 CDP 事件乱序。"""
import json
from types import SimpleNamespace
import unittest

from core.browser_traffic import _SummaryOnlyCDPSession
from core.registration.submission_recovery import SubmissionDiagnostics
from core.registration_debug import _RoxyTargetCollector


_MISSING = object()
_SIGNIN = "https://chatgpt.com/api/auth/signin/openai"
_CF_HEADERS = {
    "Server": "cloudflare",
    "CF-Mitigated": "challenge",
    "CF-Ray": "0123456789abcdef-SJC",
    "Content-Type": "text/html; charset=UTF-8",
}


class _Capture:
    """只向真实采集器注入事件，不建立浏览器连接或发起请求。"""

    def __init__(self):
        self.diagnostics = SubmissionDiagnostics()
        self.session = _SummaryOnlyCDPSession("unit-auth-headers")
        self.session.auth_diagnostic_observer = self.diagnostics.observe_network
        self.collectors = {}

    def collector(self, target="target"):
        if target not in self.collectors:
            self.collectors[target] = _RoxyTargetCollector(
                SimpleNamespace(session=self.session), target, "ws://unit-only", "page",
            )
        return self.collectors[target]

    def emit(self, method, params, *, target="target"):
        self.collector(target)._handle({"method": "Network." + method, "params": params})

    def request(self, request="request", *, target="target", url=_SIGNIN, redirect=None):
        params = {
            "requestId": request, "timestamp": 1.0, "type": "Fetch",
            "request": {"url": url, "method": "POST"},
        }
        if redirect is not None:
            params["redirectResponse"] = redirect
            params["redirectHasExtraInfo"] = True
        self.emit("requestWillBeSent", params, target=target)

    def response(self, request="request", *, target="target", status=403, headers=_MISSING):
        response = {"status": status, "mimeType": "text/html"}
        if headers is not _MISSING:
            response["headers"] = headers
        self.emit("responseReceived", {"requestId": request, "response": response}, target=target)

    def extra(self, request="request", *, target="target", status=403, headers=None):
        self.emit("responseReceivedExtraInfo", {
            "requestId": request, "statusCode": status,
            "headers": dict(_CF_HEADERS) if headers is None else headers,
        }, target=target)

    def finish(self, request="request", *, target="target"):
        self.emit("loadingFinished", {
            "requestId": request, "timestamp": 1.25, "encodedDataLength": 64,
        }, target=target)

    def latest(self):
        return self.diagnostics.recent_network()[-1]


class AuthResponseHeadersTests(unittest.TestCase):
    def assert_rejection(self, row, kind):
        self.assertEqual(row["status"], 403)
        self.assertEqual(row["rejection"]["kind"], kind)
        self.assertRegex(row["rejection"]["label"], r"[\u4e00-\u9fff]")

    def test_response_headers_are_available_before_body_finishes(self):
        capture = _Capture()
        capture.request()
        capture.response(headers=_CF_HEADERS)

        row = capture.latest()
        self.assertEqual(row["phase"], "response")
        self.assertTrue(row["response_headers_observed"])
        self.assertEqual(row["response_headers"], {
            "server": "cloudflare", "cf-mitigated": "challenge",
            "cf-ray": "0123456789abcdef-SJC", "content-type": "text/html",
        })
        self.assert_rejection(row, "cloudflare_challenge")
        self.assertIn("request", capture.collector()._requests)
        self.assertEqual(capture.session.request_count, 0)

    def test_header_whitelist_drops_private_data_from_names_and_values(self):
        capture = _Capture()
        capture.request(url=_SIGNIN + "?login_hint=private@example.test&token=private-token")
        capture.response(headers={
            "SERVER": "Cloudflare", "CF-MITIGATED": "challenge",
            "Cf-Ray": "0123456789abcdef-SJC",
            "Content-Type": "application/json; private=private-parameter",
            "Retry-After": "120",
            "Set-Cookie": "private-cookie", "Authorization": "Bearer private-token",
            "Location": "https://chatgpt.com/?token=private-location",
            "X-Private": "private-header",
        })

        row = capture.latest()
        self.assertEqual(row["response_headers"], {
            "server": "cloudflare", "cf-mitigated": "challenge",
            "cf-ray": "0123456789abcdef-SJC", "content-type": "application/json",
            "retry-after": "120",
        })
        encoded = json.dumps(capture.diagnostics.recent_network(), ensure_ascii=False)
        for private in (
            "private@example.test", "private-token", "private-cookie", "private-location",
            "private-header", "private-parameter", "Set-Cookie", "Authorization",
        ):
            self.assertNotIn(private, encoded)

    def test_malformed_header_values_cannot_become_diagnostic_evidence(self):
        invalid_cases = (
            {"server": "private-server", "cf-mitigated": "challenge private-token",
             "cf-ray": "not-a-ray-private-token", "content-type": "text/private-token",
             "retry-after": "private-token"},
            {"server": "cloudflare\nprivate-token", "cf-mitigated": "challenge\nprivate-token",
             "cf-ray": "0123456789abcdef-sjc", "content-type": "text/html\nprivate-token",
             "retry-after": "120\nprivate-token"},
            {"cf-ray": "0123456789abcde", "retry-after": "-1"},
            {"cf-ray": "0123456789abcdef" * 3,
             "retry-after": "Wed, 99 Oct 2015 07:28:00 GMT"},
        )
        for headers in invalid_cases:
            with self.subTest(headers=headers):
                capture = _Capture()
                capture.request()
                capture.response(headers=headers)
                row = capture.latest()
                self.assertTrue(row["response_headers_observed"])
                self.assertLessEqual(set(row["response_headers"]), {"server"})
                if "server" in row["response_headers"]:
                    self.assertIn(row["response_headers"]["server"], {"other", "其他"})
                self.assert_rejection(row, "http_403_unconfirmed")
                self.assertNotIn("private-", json.dumps(row, ensure_ascii=False))

    def test_cf_pass_through_headers_and_retry_after_remain_conservative(self):
        cases = (
            ({"server": "cloudflare", "retry-after": "120"}, "120"),
            ({"cf-ray": "0123456789abcdef0123456789abcdef",
              "retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}, "Wed, 21 Oct 2015 07:28:00 GMT"),
        )
        for headers, expected_retry in cases:
            with self.subTest(headers=headers):
                capture = _Capture()
                capture.request()
                capture.response(headers=headers)
                row = capture.latest()
                self.assertEqual(row["response_headers"]["retry-after"], expected_retry)
                self.assert_rejection(row, "cloudflare_unconfirmed")

    def test_extra_info_order_preserves_evidence_without_double_counting(self):
        for order in ("before_request", "before_response", "after_response", "after_finish"):
            with self.subTest(order=order):
                capture = _Capture()
                if order == "before_request":
                    capture.extra()
                    self.assertEqual(capture.diagnostics.recent_network(), [])
                capture.request()
                if order == "before_response":
                    capture.extra()
                capture.response()
                if order == "after_response":
                    capture.extra()
                capture.finish()
                if order == "after_finish":
                    capture.extra()

                row = capture.latest()
                self.assertTrue(row["response_headers_observed"])
                self.assertEqual(row["response_headers"]["cf-mitigated"], "challenge")
                self.assert_rejection(row, "cloudflare_challenge")
                self.assertEqual(len(capture.diagnostics.recent_network()), 1)
                self.assertEqual(capture.session.request_count, 1)
                self.assertEqual(capture.session.failed_count, 1)
                self.assertEqual(capture.session.download_bytes, 64)

    def test_extra_info_alone_can_report_a_403_without_response_received(self):
        capture = _Capture()
        capture.request()
        capture.extra()

        self.assert_rejection(capture.latest(), "cloudflare_challenge")
        self.assertEqual(capture.session.request_count, 0)
        capture.finish()
        self.assert_rejection(capture.latest(), "cloudflare_challenge")
        self.assertEqual(capture.session.request_count, 1)
        self.assertEqual(capture.session.failed_count, 1)

    def test_missing_headers_leave_the_403_reason_unconfirmed(self):
        capture = _Capture()
        capture.request()
        capture.response()

        row = capture.latest()
        self.assertFalse(row["response_headers_observed"])
        self.assertEqual(row["response_headers"], {})
        self.assert_rejection(row, "http_403_unconfirmed")
        capture.finish()
        self.assert_rejection(capture.latest(), "http_403_unconfirmed")
        self.assertFalse(capture.latest()["response_headers_observed"])

    def test_extra_info_isolated_by_target_and_request(self):
        capture = _Capture()
        cases = (
            ("first", "same", _SIGNIN),
            ("second", "same", "https://chatgpt.com/api/auth/session"),
            ("first", "other", "https://chatgpt.com/api/auth/csrf"),
        )
        for target, request, url in cases:
            capture.request(request, target=target, url=url)
            capture.response(request, target=target)
        capture.extra("same", target="first")
        capture.extra("orphan", target="second")

        rows = {row["path"]: row for row in capture.diagnostics.recent_network()}
        self.assertEqual(len(rows), 3)
        self.assert_rejection(rows["/api/auth/signin/openai"], "cloudflare_challenge")
        for path in ("/api/auth/session", "/api/auth/csrf"):
            self.assertFalse(rows[path]["response_headers_observed"])
            self.assert_rejection(rows[path], "http_403_unconfirmed")
        for target, request, _url in cases:
            capture.finish(request, target=target)
        self.assertEqual(capture.session.request_count, 3)
        self.assertEqual(capture.session.failed_count, 3)

    def test_redirect_reused_request_id_does_not_inherit_cf_headers(self):
        capture = _Capture()
        capture.request()
        capture.request(
            url="https://auth.openai.com/api/accounts/authorize",
            redirect={"status": 302, "headers": dict(_CF_HEADERS)},
        )
        # 重定向链无法可靠分配迟到的 ExtraInfo，不能把它当作新一跳的证据。
        capture.extra()
        capture.response(headers={"content-type": "application/json"})
        capture.finish()
        capture.extra()

        row = capture.latest()
        self.assertEqual(row["path"], "/api/accounts/authorize")
        self.assertEqual(row["response_headers"], {"content-type": "application/json"})
        self.assertTrue(row["response_headers_observed"])
        self.assert_rejection(row, "http_403_unconfirmed")
        self.assertEqual(capture.session.request_count, 2)
        self.assertEqual(capture.session.failed_count, 1)

    def test_capture_started_mid_redirect_cannot_attach_previous_hop_headers(self):
        capture = _Capture()
        capture.extra(status=302)
        capture.request(
            url="https://auth.openai.com/api/accounts/authorize",
            redirect={"status": 302, "headers": {"server": "cloudflare"}},
        )
        capture.response(headers={"server": "nginx"})
        capture.extra(status=302)
        capture.finish()

        row = capture.latest()
        self.assertEqual(row["response_headers"], {"server": "nginx"})
        self.assert_rejection(row, "http_403_unconfirmed")
        self.assertEqual(capture.session.request_count, 1)
        self.assertEqual(capture.session.failed_count, 1)


if __name__ == "__main__":
    unittest.main()
