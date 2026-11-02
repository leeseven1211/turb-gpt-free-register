"""验证码重发仅凭同一请求的明确业务成功回执收口。"""
import base64
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.auth.browser.browser_submission import (
    BrowserSubmissionReceipt, record_browser_submission_fact, unresolved_submission_ids,
)
from core.browser.traffic import _SummaryOnlyCDPSession
from core.registration.debug import _RoxyTargetCollector
from core.registration.roxy import _make_submission_observer
from core.storage import registration
from tests.support_pg import PostgresTestCase


class _ResendCapture:
    """向真实 CDP 采集器注入事件，只替代外部 WebSocket 连接。"""

    def __init__(self, driver, *, full=False):
        self.events = []
        self.session = (SimpleNamespace(job_id=991, current_stage="email_otp", body_capture_enabled=True,
                                        record_network=Mock())
                        if full else _SummaryOnlyCDPSession("otp-resend-test"))
        observer = _make_submission_observer(driver, monitor_otp_network=True)

        def observe(meta):
            self.events.append(meta)
            observer(meta)

        self.session.submission_observer = observe
        self.worker = _RoxyTargetCollector(
            SimpleNamespace(session=self.session), "test-target", "ws://test-only", "page",
        )
        self.worker._ws = Mock()

    def request(self, *, request_id="resend", path="/api/accounts/email-otp/resend"):
        self.worker._handle({"method": "Network.requestWillBeSent", "params": {
            "requestId": request_id, "timestamp": 1.0, "type": "Fetch",
            "request": {"url": "https://auth.openai.com" + path, "method": "POST"},
        }})

    def response(self, body='{"success":true}', *, status=200, mime="application/json",
                 request_id="resend", body_error=False, timeout=False):
        self.worker._handle({"method": "Network.responseReceived", "params": {
            "requestId": request_id, "response": {
                "status": status, "mimeType": mime, "headers": {"content-type": mime},
            },
        }})
        self.worker._handle({"method": "Network.loadingFinished", "params": {
            "requestId": request_id, "timestamp": 1.2, "encodedDataLength": 256,
        }})
        if not self.worker._ws.send.call_args_list:
            return
        command = json.loads(self.worker._ws.send.call_args.args[0])
        if timeout:
            with patch("core.registration.debug.time.monotonic", return_value=float("inf")):
                self.worker._expire_auth_error_reads()
        if body_error:
            self.worker._handle({"id": command["id"], "error": {"message": "No resource"}})
        else:
            self.worker._handle({"id": command["id"], "result": {
                "body": base64.b64encode(body.encode()).decode(), "base64Encoded": True,
            }})


class OtpResendReceiptTests(unittest.TestCase):
    def driver(self, *, target="CDwindow-test-target"):
        receipt = BrowserSubmissionReceipt(kind="otp", stage="otp_resend", endpoint_kind="otp_resend")
        driver = SimpleNamespace(current_window_handle=target)
        record_browser_submission_fact(driver, "dispatch_intent", receipt=receipt)
        return driver, receipt

    def test_success_body_confirms_only_paired_resend_and_does_not_escape_as_raw_body(self):
        for path in ("/api/accounts/email-otp/resend", "/api/accounts/email-otp/send",
                     "/api/accounts/passwordless/send-otp"):
            with self.subTest(path=path):
                driver, receipt = self.driver()
                capture = _ResendCapture(driver)
                capture.request(path=path)
                capture.response('{"success":true,"private":"private-value"}')
                self.assertEqual(receipt.phase, "confirmed")
                self.assertEqual(receipt.result, "success")
                self.assertEqual(receipt.http_status, 200)
                self.assertEqual(capture.worker._ws.send.call_count, 1)
                self.assertEqual(capture.events[-1]["otp_resend_success"], True)
                self.assertNotIn("private-value", json.dumps(capture.events))
                self.assertNotIn("private-value", json.dumps(capture.session.summary()))
                self.assertEqual(capture.session.request_count, 1)

    def test_missing_unknown_and_unsuccessful_results_cannot_confirm_resend(self):
        cases = (
            {"body": "{}"}, {"body": '{"success":false}'}, {"body": '{"success":"true"}'},
            {"body": '{"success":1}'}, {"body": '{"result":{"success":true}}'},
            {"body": '{"success":true,"success":false}'},
            {"body": '{"success":true,"error":{"code":"invalid_otp"}}'},
            {"body": "<html>success</html>"}, {"status": 400}, {"status": 500},
            {"status": 302}, {"mime": "text/html"}, {"body_error": True}, {"timeout": True},
        )
        for options in cases:
            with self.subTest(options=options):
                driver, receipt = self.driver()
                capture = _ResendCapture(driver)
                capture.request()
                capture.response(**options)
                self.assertNotEqual(receipt.phase, "confirmed")
                self.assertFalse(any(event.get("otp_resend_success") for event in capture.events))

    def test_full_capture_extracts_only_explicit_success_without_changing_raw_body(self):
        for payload, expected in (('{"success":true}', True), ('{"success":false}', False),
                                  ('{"success":true,"error":{"code":"invalid_otp"}}', False)):
            with self.subTest(payload=payload):
                driver, _receipt = self.driver()
                capture = _ResendCapture(driver, full=True)
                capture.request()
                capture.response(payload)
                record = capture.session.record_network.call_args.args[0]
                self.assertEqual(record.get("otp_resend_success", False), expected)
                self.assertEqual(record["response_body"], payload)
                self.assertEqual(capture.worker._ws.send.call_count, 1)

    def test_orphan_wrong_target_and_wrong_endpoint_cannot_confirm_current_resend(self):
        for difference in ({"request_id": "orphan"}, {"target_id": "other-target"},
                           {"endpoint_kind": "password_submit"}):
            with self.subTest(difference=difference):
                driver, receipt = self.driver()
                observer = _make_submission_observer(driver)
                request = {"target_id": "test-target", "request_id": "resend",
                           "endpoint_kind": "otp_resend", "http_method": "POST"}
                observer(request)
                observer({**request, **difference, "response": True, "http_status": 200,
                          "otp_resend_success": True})
                self.assertEqual(receipt.phase, "request_observed")

    def test_delayed_success_only_confirms_request_bound_receipt_once(self):
        driver, original = self.driver()
        observer = _make_submission_observer(driver)
        request = {"target_id": "test-target", "request_id": "old-request",
                   "endpoint_kind": "otp_resend", "http_method": "POST"}
        observer(request)
        current = BrowserSubmissionReceipt(
            kind="otp", stage="otp_resend", endpoint_kind="otp_resend", phase="ui_dispatched",
        )
        driver._browser_submission_receipts.append(current)
        driver._browser_submission_receipt = current
        response = {**request, "response": True, "http_status": 200, "otp_resend_success": True}
        with patch("core.registration.roxy.record_browser_submission_fact",
                   wraps=record_browser_submission_fact) as record:
            observer(response)
            observer(response)
        self.assertEqual(original.phase, "confirmed")
        self.assertEqual(current.phase, "ui_dispatched")
        self.assertEqual(record.call_count, 1)
        self.assertIs(record.call_args.kwargs["receipt"], original)

    def test_foreign_or_missing_dispatch_target_cannot_confirm_resend(self):
        for monitor in (False, True):
            for dispatch_target in ("CDwindow-current-target", None):
                with self.subTest(monitor=monitor, dispatch_target=dispatch_target):
                    driver, receipt = self.driver(target=dispatch_target)
                    observer = _make_submission_observer(driver, monitor_otp_network=monitor)
                    request = {"target_id": "unrelated-target", "request_id": "resend",
                               "endpoint_kind": "otp_resend", "http_method": "POST"}
                    observer(request)
                    observer({**request, "response": True, "http_status": 200, "otp_resend_success": True})
                    self.assertEqual(receipt.phase, "dispatch_intent")
                    self.assertIsNone(receipt.request_binding)

    def test_second_resend_in_new_page_pairs_without_reusing_old_request(self):
        driver, original = self.driver()
        observer = _make_submission_observer(driver, monitor_otp_network=True)
        first = {"target_id": "test-target", "request_id": "first",
                 "endpoint_kind": "otp_resend", "http_method": "POST"}
        observer(first)
        observer({**first, "response": True, "http_status": 200, "otp_resend_success": True})
        driver.current_window_handle = "CDwindow-new-target"
        second_receipt = BrowserSubmissionReceipt(kind="otp", stage="otp_resend", endpoint_kind="otp_resend")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=second_receipt)
        observer(first)
        observer({**first, "response": True, "http_status": 200, "otp_resend_success": True})
        self.assertEqual(second_receipt.phase, "dispatch_intent")
        second = {**first, "target_id": "new-target", "request_id": "second"}
        observer(second)
        observer({**second, "response": True, "http_status": 200, "otp_resend_success": True})
        self.assertEqual(original.phase, "confirmed")
        self.assertEqual(original.request_binding, ("test-target", "first"))
        self.assertEqual(second_receipt.phase, "confirmed")
        self.assertEqual(second_receipt.request_binding, ("new-target", "second"))

    def test_confirmed_resend_without_request_binding_keeps_candidates_ambiguous(self):
        driver, current = self.driver()
        old = BrowserSubmissionReceipt(
            kind="otp", stage="otp_resend", endpoint_kind="otp_resend", phase="confirmed",
        )
        driver._browser_submission_receipts.insert(0, old)
        observer = _make_submission_observer(driver)
        request = {"target_id": "test-target", "request_id": "resend",
                   "endpoint_kind": "otp_resend", "http_method": "POST"}
        observer(request)
        observer({**request, "response": True, "http_status": 200, "otp_resend_success": True})
        self.assertEqual(current.phase, "dispatch_intent")
        self.assertIsNone(current.request_binding)


class OtpResendDispatchFenceTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()

    def driver(self, suffix):
        email = "otp-resend-" + suffix + "@example.test"
        attempt = registration.create_attempt(email)
        run = registration.start_run(
            int(attempt["id"]), execution_id=suffix, initial_status="running",
            action_type="registration_resume",
        )
        registration.save_password_checkpoint(
            int(attempt["id"]), email=email, password="SavedPass123!", state="started",
            run_id=int(run["id"]), execution_id=suffix,
        )
        driver = SimpleNamespace(
            current_window_handle="CDwindow-test-target",
            _registration_fact_context={"attempt_id": int(attempt["id"]),
                                        "run_id": int(run["id"]), "execution_id": suffix},
        )
        resend = BrowserSubmissionReceipt(
            kind="resume_login", stage="otp_resend", endpoint_kind="otp_resend",
        )
        record_browser_submission_fact(driver, "dispatch_intent", receipt=resend)
        return driver, resend, email

    def accept_otp(self, driver):
        otp = BrowserSubmissionReceipt(kind="resume_login", stage="email_otp", endpoint_kind="otp_submit")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=otp)
        record_browser_submission_fact(driver, "confirmed", receipt=otp, result="success")

    def test_confirmed_resend_then_accepted_otp_allows_profile_dispatch(self):
        driver, resend, email = self.driver("success")
        capture = _ResendCapture(driver)
        capture.request()
        capture.response()
        self.accept_otp(driver)
        profile = BrowserSubmissionReceipt(kind="profile", stage="profile", endpoint_kind="profile_submit")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=profile)
        facts = registration.get_private_resume_context(
            driver._registration_fact_context["attempt_id"], email=email,
        )["submission_facts"]
        self.assertTrue(any(fact["submission_id"] == resend.submission_id
                            and fact["phase"] == "confirmed" for fact in facts))
        self.assertEqual(unresolved_submission_ids(facts), {profile.submission_id})

    def test_accepted_otp_cannot_resolve_unconfirmed_resend_or_bypass_repeat_guard(self):
        for number, options in enumerate((None, {"body": "{}"}, {"body_error": True}, {"timeout": True})):
            with self.subTest(options=options):
                driver, resend, email = self.driver("unknown-" + str(number))
                capture = _ResendCapture(driver)
                capture.request()
                if options is not None:
                    capture.response(**options)
                duplicate = BrowserSubmissionReceipt(
                    kind="resume_login", stage="otp_resend", endpoint_kind="otp_resend",
                )
                with self.assertRaisesRegex(ValueError, "未决浏览器"):
                    record_browser_submission_fact(driver, "dispatch_intent", receipt=duplicate)
                self.accept_otp(driver)
                profile = BrowserSubmissionReceipt(kind="profile", stage="profile", endpoint_kind="profile_submit")
                with self.assertRaisesRegex(ValueError, "未决浏览器"):
                    record_browser_submission_fact(driver, "dispatch_intent", receipt=profile)
                facts = registration.get_private_resume_context(
                    driver._registration_fact_context["attempt_id"], email=email,
                )["submission_facts"]
                self.assertEqual(unresolved_submission_ids(facts), {resend.submission_id})
