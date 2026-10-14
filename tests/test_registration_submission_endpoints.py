"""认证请求证据只关联真实方法与对应业务端点。"""
import unittest
from types import SimpleNamespace

from core.browser_traffic import _SummaryOnlyCDPSession
from core.registration.browser_submission import BrowserSubmissionReceipt
from core.registration.roxy import _unique_submission_receipt_for_endpoint
from core.registration_debug import _RoxyTargetCollector


class RegistrationSubmissionEndpointTests(unittest.TestCase):
    def _observe_request_and_response(self, path, method="POST", *, response_method="same"):
        session = _SummaryOnlyCDPSession("test-profile")
        observed = []
        session.submission_observer = observed.append
        worker = _RoxyTargetCollector(
            SimpleNamespace(session=session), "test-target", "ws://test-only", "page",
        )
        request = {"url": "https://auth.openai.com" + path}
        if method is not None:
            request["method"] = method
        worker._handle({
            "method": "Network.requestWillBeSent",
            "params": {"requestId": "test-request", "request": request, "type": "Fetch"},
        })
        response = {
            "url": request["url"], "status": 200,
            "request_id": "test-request", "target_id": "test-target",
        }
        actual_method = method if response_method == "same" else response_method
        if actual_method is not None:
            response["method"] = actual_method
        session.record_network(response)
        return observed

    def test_validate_and_verify_post_pair_with_original_otp_receipt(self):
        receipt = BrowserSubmissionReceipt(
            kind="otp", stage="email_otp", phase="dispatch_intent", endpoint_kind="otp_submit",
        )
        driver = SimpleNamespace(_browser_submission_receipts=[receipt])
        for action in ("validate", "verify"):
            with self.subTest(action=action):
                observed = self._observe_request_and_response("/api/accounts/email-otp/" + action)
                self.assertEqual(len(observed), 2)
                self.assertEqual([event["endpoint_kind"] for event in observed], ["otp_submit"] * 2)
                self.assertEqual([bool(event.get("response")) for event in observed], [False, True])
                self.assertTrue(all(
                    _unique_submission_receipt_for_endpoint(driver, event["endpoint_kind"]) is receipt
                    for event in observed
                ))

    def test_send_and_resend_post_cannot_pair_with_validate_receipt(self):
        receipt = BrowserSubmissionReceipt(
            kind="otp", stage="email_otp", phase="dispatch_intent", endpoint_kind="otp_submit",
        )
        driver = SimpleNamespace(_browser_submission_receipts=[receipt])
        for action in ("send", "resend"):
            with self.subTest(action=action):
                observed = self._observe_request_and_response("/api/accounts/email-otp/" + action)
                self.assertEqual([event["endpoint_kind"] for event in observed], ["otp_resend"] * 2)
                self.assertTrue(all(
                    _unique_submission_receipt_for_endpoint(driver, event["endpoint_kind"]) is None
                    for event in observed
                ))

    def test_password_post_is_observed_at_request_and_response(self):
        observed = self._observe_request_and_response("/api/accounts/password")
        self.assertEqual([event["endpoint_kind"] for event in observed], ["password_submit"] * 2)
        self.assertEqual([event["http_method"] for event in observed], ["POST"] * 2)

    def test_business_get_cannot_create_dispatch_evidence(self):
        for path in ("/api/accounts/password", "/api/accounts/email-otp/validate",
                     "/api/accounts/email-otp/verify", "/api/accounts/email-otp/send",
                     "/api/accounts/email-otp/resend"):
            with self.subTest(path=path):
                self.assertEqual(self._observe_request_and_response(path, "GET"), [])

    def test_missing_business_method_is_not_defaulted_to_post(self):
        for path in ("/api/accounts/password", "/api/accounts/email-otp/validate",
                     "/api/accounts/email-otp/send"):
            with self.subTest(path=path):
                self.assertEqual(self._observe_request_and_response(path, None), [])

    def test_missing_response_method_cannot_confirm_post_response(self):
        observed = self._observe_request_and_response("/api/accounts/password", response_method=None)
        self.assertEqual(len(observed), 1)
        self.assertFalse(observed[0].get("response"))

    def test_nextauth_preserves_csrf_get_and_signin_post_contracts(self):
        for path, method, endpoint in (
            ("/api/auth/csrf", "GET", "nextauth_csrf"),
            ("/api/auth/signin/openai", "POST", "nextauth_signin"),
        ):
            with self.subTest(endpoint=endpoint):
                observed = self._observe_request_and_response(path, method)
                self.assertEqual([event["endpoint_kind"] for event in observed], [endpoint] * 2)
                self.assertEqual([event["http_method"] for event in observed], [method] * 2)
        self.assertEqual(self._observe_request_and_response("/api/auth/signin/openai", "GET"), [])
        self.assertEqual(self._observe_request_and_response("/api/auth/csrf", "POST"), [])

    def test_submission_callback_exposes_only_metadata_allowlist(self):
        observed = self._observe_request_and_response("/api/accounts/email-otp/verify?private=test-only")
        allowed = {"endpoint_kind", "http_method", "http_status", "duration_ms", "response",
                   "request", "request_id", "target_id"}
        self.assertEqual(len(observed), 2)
        for event in observed:
            self.assertLessEqual(set(event), allowed)
            self.assertEqual((event["request_id"], event["target_id"]), ("test-request", "test-target"))
            self.assertNotIn("private", str(event))


if __name__ == "__main__":
    unittest.main()
