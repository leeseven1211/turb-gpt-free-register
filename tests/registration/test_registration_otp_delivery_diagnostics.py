"""用真实 CDP 事件链验证重发接受证据只细化收码失败展示。"""
import base64
from copy import deepcopy
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.registration.debug import RegistrationDebugSession, _RoxyTargetCollector
from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from tests.registration.test_registration_otp_resend_receipt import _ResendCapture


NO_MAIL = "RuntimeError: otp_request_unconfirmed: 验证码请求缺少页面或网络确认；不能断言服务端已经发信"


class Capture:
    def __init__(self, **changes):
        job = {
            "id": 991, "job_uuid": "unit-otp-delivery", "job_type": "registration_resume",
            "debug_enabled": True, "config_snapshot": {"registration_driver": "roxy"},
            "progress_stage": "email_otp", "run_id": 17, "execution_id": "unit-execution",
            **changes,
        }
        mode = job.pop("capture_mode", "full")
        with patch.object(RegistrationDebugSession, "_start_capture"):
            self.session = RegistrationDebugSession(job, capture_mode=mode)
        self.worker = _RoxyTargetCollector(
            SimpleNamespace(session=self.session), "test-target", "ws://test-only", "page",
        )
        self.worker._ws = Mock()
        self.started = time.time()
        self.driver = SimpleNamespace(
            current_window_handle="CDwindow-test-target",
        )
        self.receipt_capture = _ResendCapture(self.driver)

    def request(self, request_id="resend", *, path="/api/accounts/email-otp/resend", method="POST", order=0):
        if method == "POST" and path == "/api/accounts/email-otp/resend":
            receipt = BrowserSubmissionReceipt(kind="resume_login", stage="otp_resend", endpoint_kind="otp_resend")
            record_browser_submission_fact(self.driver, "dispatch_intent", receipt=receipt)
            self.driver._browser_submission_receipt = receipt
            self.receipt_capture.request(request_id=request_id)
        self.worker._handle({"method": "Network.requestWillBeSent", "params": {
            "requestId": request_id, "timestamp": 1 + order, "wallTime": self.started + order / 100,
            "type": "Fetch", "request": {"url": "https://auth.openai.com" + path, "method": method},
        }})

    def response(self, request_id="resend", *, body='{"success":true}', status=200, mime="application/json"):
        self.receipt_capture.response(request_id=request_id, body=body, status=status, mime=mime)
        self.worker._handle({"method": "Network.responseReceived", "params": {
            "requestId": request_id, "response": {
                "status": status, "mimeType": mime, "headers": {"content-type": mime},
            },
        }})
        before = self.worker._ws.send.call_count
        self.worker._handle({"method": "Network.loadingFinished", "params": {
            "requestId": request_id, "timestamp": 5, "encodedDataLength": 256,
        }})
        if self.worker._ws.send.call_count == before:
            return
        command = json.loads(self.worker._ws.send.call_args.args[0])
        self.worker._handle({"id": command["id"], "result": {
            "body": base64.b64encode(body.encode()).decode(), "base64Encoded": True,
        }})

    def classify(self, reason=NO_MAIL):
        self.driver._registration_fact_context = {
            "job_id": self.session.job_id, "run_id": 17, "execution_id": "unit-execution",
        }
        try:
            return self.session._classify_failure(reason, driver=self.driver)
        finally:
            del self.driver._registration_fact_context


def test_delayed_explicit_resend_acceptance_refines_no_mail_without_changing_job():
    capture = Capture()
    original = deepcopy(capture.session.job)
    capture.request()
    assert capture.classify()["code"] != "email_otp_no_mail"
    capture.response(body='{"success":true,"private":"private-value"}')
    info = capture.classify()
    assert info["code"] == "email_otp_no_mail"
    assert info["cause_code"] == "email_otp_no_mail"
    assert info["display_code"] == "MAIL-OTP-005"
    assert info["otp_request_accepted"] is True
    assert info["stage"] == "email_otp"
    assert capture.session.job == original
    assert "private-value" not in json.dumps(capture.session.summary())


@pytest.mark.parametrize("options", [
    {"body": "{}"}, {"body": '{"success":false}'}, {"body": '{"success":"true"}'},
    {"body": '{"success":1}'}, {"body": '{"result":{"success":true}}'},
    {"body": '{"success":true,"error":null}'},
    {"body": '{"success":true,"success":false}'},
    {"status": 400}, {"status": 500}, {"status": 302}, {"mime": "text/html"},
])
def test_nonexplicit_or_failed_resend_response_does_not_claim_request_acceptance(options):
    capture = Capture()
    capture.request()
    capture.response(**options)
    assert capture.classify()["code"] != "email_otp_no_mail"


@pytest.mark.parametrize("following", ["pending_resend", "validate", "progress", "later_stage", "other_run"])
def test_accepted_resend_cannot_cross_a_new_request_run_or_progress(following):
    capture = Capture()
    capture.request()
    capture.response()
    if following == "pending_resend":
        capture.request("next", order=1)
    elif following == "validate":
        capture.request("next", path="/api/accounts/email-otp/validate", order=1)
    elif following == "progress":
        capture.session.update_stage("email_otp", state="success")
        capture.session.update_stage("email_otp", state="running")
    elif following == "later_stage":
        capture.session.update_stage("profile", state="running")
    else:
        capture.session.update_context(run_id=18, execution_id="other-execution")
    assert capture.classify()["code"] != "email_otp_no_mail"


def test_late_old_request_completion_cannot_hide_newer_accepted_resend():
    capture = Capture(progress_stage="auth_redirect")
    capture.request("old", path="/api/accounts/passwordless/send-otp")
    capture.session.update_stage("email_otp", state="running")
    capture.request("current", order=1)
    capture.response("current")
    capture.worker._handle({"method": "Network.loadingFailed", "params": {
        "requestId": "old", "errorText": "net::ERR_ABORTED",
    }})
    assert capture.classify()["code"] == "email_otp_no_mail"


def test_late_old_success_cannot_hide_a_new_unconfirmed_resend():
    capture = Capture()
    capture.request("old")
    capture.request("current", order=1)
    capture.response("old")
    assert capture.classify()["code"] != "email_otp_no_mail"


def test_orphan_success_without_this_run_request_cannot_refine_delivery_failure():
    capture = Capture()
    capture.session.record_network({
        "target_id": "test-target", "request_id": "orphan", "stage": "email_otp",
        "method": "POST", "url": "https://auth.openai.com/api/accounts/email-otp/resend",
        "status": 200, "otp_resend_success": True,
    })
    assert capture.classify()["code"] != "email_otp_no_mail"


@pytest.mark.parametrize("change", ["missing_receipt", "unconfirmed", "other_target", "other_request", "unpaired"])
def test_full_capture_success_requires_the_current_confirmed_submission(change):
    capture = Capture()
    capture.request()
    capture.response()
    receipt = capture.driver._browser_submission_receipt
    if change == "missing_receipt":
        del capture.driver._browser_submission_receipt
    elif change == "unconfirmed":
        receipt.phase = "response_observed"
    elif change == "other_target":
        receipt.dispatch_target_id = "other-target"
    elif change == "other_request":
        receipt.request_binding = receipt.response_binding = ("test-target", "other-request")
    else:
        receipt.response_binding = None
    assert capture.classify()["code"] != "email_otp_no_mail"


def test_confirmed_receipt_without_response_body_evidence_cannot_refine_delivery_failure():
    capture = Capture()
    capture.request()
    capture.receipt_capture.response()
    capture.worker._finish_request("resend", body_unavailable="body_unavailable")
    assert capture.classify()["code"] != "email_otp_no_mail"


@pytest.mark.parametrize("following", ["resend", "validate", "progress"])
def test_new_request_during_submission_pairing_invalidates_previously_confirmed_snapshot(following):
    capture = Capture()
    capture.request()
    capture.response()
    assert capture.classify()["code"] == "email_otp_no_mail"

    class ConcurrentDriver(SimpleNamespace):
        def __getattribute__(self, name):
            if name == "_browser_submission_receipt":
                if following == "resend":
                    capture.request("next", order=1)
                elif following == "validate":
                    capture.request("next", path="/api/accounts/email-otp/validate", order=1)
                else:
                    capture.session.update_stage("profile", state="running")
            return super().__getattribute__(name)

    driver = ConcurrentDriver(**vars(capture.driver))
    driver._registration_fact_context = {"job_id": 991, "run_id": 17, "execution_id": "unit-execution"}
    assert capture.session._classify_failure(NO_MAIL, driver=driver)["code"] != "email_otp_no_mail"


@pytest.mark.parametrize("changes", [
    {"debug_enabled": False}, {"capture_mode": "failure_only"}, {"job_type": "twofa_retry"},
    {"config_snapshot": {"registration_driver": "protocol_oss_2"}}, {"run_id": None},
])
def test_no_mail_refinement_requires_current_roxy_debug_run(changes):
    capture = Capture(**changes)
    capture.request()
    capture.response()
    assert capture.classify()["code"] != "email_otp_no_mail"


@pytest.mark.parametrize("reason", [
    "request_unknown: otp_request_unconfirmed: 原验证码提交仍未确认",
    "otp_mailbox_unavailable: 验证码收件链路不可用", "password_rejected",
    "otp_invalid_or_expired: 验证码无效", "RuntimeError: 本地异常",
])
def test_resend_success_does_not_replace_another_terminal_failure(reason):
    capture = Capture()
    capture.request()
    capture.response()
    assert capture.classify(reason)["code"] != "email_otp_no_mail"
