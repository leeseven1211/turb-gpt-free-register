"""认证请求证据只关联真实方法与对应业务端点。"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.browser.traffic import _SummaryOnlyCDPSession
from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.registration.roxy import (
    _make_submission_observer,
    _submission_response_fact,
    _unique_submission_receipt_for_endpoint,
)
from core.registration.debug import _RoxyTargetCollector


class RegistrationSubmissionEndpointTests(unittest.TestCase):
    def _observe_request_and_response(self, path, method="POST", *, response_method="same",
                                      status=200, observer=None):
        session = _SummaryOnlyCDPSession("test-profile")
        observed = []

        def callback(meta):
            observed.append(meta)
            if observer is not None:
                observer(meta)

        session.submission_observer = callback
        worker = _RoxyTargetCollector(
            SimpleNamespace(session=session), "test-target", "ws://test-only", "page",
        )
        origin = "https://chatgpt.com" if path.startswith("/api/auth/") else "https://auth.openai.com"
        request = {"url": origin + path}
        if method is not None:
            request["method"] = method
        worker._handle({
            "method": "Network.requestWillBeSent",
            "params": {"requestId": "test-request", "request": request, "type": "Fetch"},
        })
        response = {
            "url": request["url"], "status": status,
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

    def test_create_password_register_post_pairs_with_original_password_receipt(self):
        receipt = BrowserSubmissionReceipt(
            kind="password", stage="password_create", phase="dispatch_intent", endpoint_kind="password_submit",
        )
        driver = SimpleNamespace(_browser_submission_receipts=[receipt])
        observed = self._observe_request_and_response("/api/accounts/user/register")
        self.assertEqual([event["endpoint_kind"] for event in observed], ["password_submit"] * 2)
        self.assertTrue(all(
            _unique_submission_receipt_for_endpoint(driver, event["endpoint_kind"]) is receipt
            for event in observed
        ))

    def test_business_get_cannot_create_dispatch_evidence(self):
        for path in ("/api/accounts/password", "/api/accounts/user/register", "/api/accounts/email-otp/validate",
                     "/api/accounts/email-otp/verify", "/api/accounts/email-otp/send",
                     "/api/accounts/email-otp/resend"):
            with self.subTest(path=path):
                self.assertEqual(self._observe_request_and_response(path, "GET"), [])

    def test_missing_business_method_is_not_defaulted_to_post(self):
        for path in ("/api/accounts/password", "/api/accounts/user/register", "/api/accounts/email-otp/validate",
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

    def test_ui_email_click_pairs_with_actual_nextauth_signin_post(self):
        receipt = BrowserSubmissionReceipt(
            kind="resume_login", stage="submit_email", phase="ui_dispatched", endpoint_kind="email_submit",
        )
        driver = SimpleNamespace(_browser_submission_receipts=[receipt])
        observed = self._observe_request_and_response("/api/auth/signin/openai")
        self.assertTrue(all(
            _unique_submission_receipt_for_endpoint(driver, event["endpoint_kind"]) is receipt
            for event in observed
        ))

    def test_csrf_preflight_cannot_pair_with_email_or_nextauth_submission(self):
        for endpoint in ("email_submit", "nextauth_signin"):
            with self.subTest(endpoint=endpoint):
                receipt = BrowserSubmissionReceipt(
                    kind="email", stage="submit_email", phase="dispatch_intent", endpoint_kind=endpoint,
                )
                driver = SimpleNamespace(_browser_submission_receipts=[receipt])
                self.assertIsNone(_unique_submission_receipt_for_endpoint(driver, "nextauth_csrf"))

    def test_csrf_success_does_not_mean_auth_submission_success(self):
        self.assertEqual(_submission_response_fact("nextauth_csrf", 200), ("response_observed", ""))

    def test_ui_signin_challenge_is_persisted_on_original_attempt_without_rejection(self):
        receipt = BrowserSubmissionReceipt(
            kind="resume_login", stage="submit_email", phase="ui_dispatched", endpoint_kind="email_submit",
        )
        driver = SimpleNamespace(
            _browser_submission_receipts=[receipt],
            _registration_fact_context={"attempt_id": 11, "run_id": 12, "job_id": 13, "execution_id": "test-run"},
            execute_script=Mock(), get=Mock(),
        )
        with patch("core.storage.registration.record_submission_fact", side_effect=lambda _attempt, **fact: fact) as persist:
            self._observe_request_and_response(
                "/api/auth/signin/openai", status=403, observer=_make_submission_observer(driver),
            )
        self.assertEqual(receipt.phase, "response_observed")
        self.assertEqual(receipt.http_status, 403)
        self.assertEqual(receipt.result, "failure")
        self.assertEqual(persist.call_count, 2)
        for call in persist.call_args_list:
            self.assertEqual(call.args, (11,))
            self.assertEqual(call.kwargs["run_id"], 12)
            self.assertEqual(call.kwargs["job_id"], 13)
            self.assertEqual(call.kwargs["execution_id"], "test-run")
            self.assertEqual(call.kwargs["submission_id"], receipt.submission_id)
        self.assertEqual([call.kwargs["phase"] for call in persist.call_args_list],
                         ["request_observed", "response_observed"])
        driver.execute_script.assert_not_called()
        driver.get.assert_not_called()

    def test_csrf_observation_leaves_submission_untouched_then_signin_can_progress(self):
        receipt = BrowserSubmissionReceipt(
            kind="email", stage="submit_email", phase="ui_dispatched", endpoint_kind="email_submit",
        )
        driver = SimpleNamespace(_browser_submission_receipts=[receipt])
        observer = _make_submission_observer(driver)
        self._observe_request_and_response("/api/auth/csrf", "GET", observer=observer)
        self.assertEqual(receipt.phase, "ui_dispatched")
        self.assertIsNone(receipt.http_status)
        self.assertEqual(receipt.result, "")
        self._observe_request_and_response("/api/auth/signin/openai", observer=observer)
        self.assertEqual(receipt.phase, "response_observed")
        self.assertEqual(receipt.http_status, 200)
        self.assertEqual(receipt.result, "success")

    def test_competing_email_and_nextauth_receipts_keep_request_unmatched(self):
        receipts = [
            BrowserSubmissionReceipt(
                kind="email", stage="submit_email", phase="unknown", endpoint_kind=endpoint,
            )
            for endpoint in ("email_submit", "nextauth_signin")
        ]
        driver = SimpleNamespace(_browser_submission_receipts=receipts)
        self._observe_request_and_response(
            "/api/auth/signin/openai", status=403, observer=_make_submission_observer(driver),
        )
        self.assertEqual([receipt.phase for receipt in receipts], ["unknown", "unknown"])
        self.assertTrue(all(receipt.http_status is None for receipt in receipts))

    def test_delayed_response_keeps_request_binding_and_ignores_duplicate_or_wrong_target(self):
        original = BrowserSubmissionReceipt(
            kind="email", stage="submit_email", phase="ui_dispatched", endpoint_kind="email_submit",
        )
        driver = SimpleNamespace(_browser_submission_receipts=[original])
        observer = _make_submission_observer(driver)
        request = {
            "target_id": "original-target", "request_id": "original-request",
            "endpoint_kind": "nextauth_signin", "http_method": "POST",
        }
        second = BrowserSubmissionReceipt(
            kind="resume_login", stage="submit_email", phase="ui_dispatched", endpoint_kind="email_submit",
        )
        with patch("core.registration.roxy.record_browser_submission_fact", wraps=record_browser_submission_fact) as record:
            observer(request)
            driver._browser_submission_receipts.append(second)
            driver._browser_submission_receipt = second
            response = {**request, "response": True, "http_status": 200}
            observer({**response, "target_id": "other-target"})
            observer(response)
            observer(response)
        self.assertEqual(record.call_count, 2)
        self.assertTrue(all(call.kwargs["receipt"] is original for call in record.call_args_list))
        self.assertEqual(original.phase, "response_observed")
        self.assertEqual(original.http_status, 200)
        self.assertEqual(second.phase, "ui_dispatched")
        self.assertIsNone(second.http_status)

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
