"""准确OTP拒绝只细化诊断，未知结果和恢复提示保持原值。"""
from copy import deepcopy

from core.operations.errors import classify_task_error


def test_exact_otp_rejection_projection_retains_unknown_result_and_input():
    summary = {"cause_code": "email_otp_code_rejected", "attempt_id": 8, "request_unknown": True}
    original = deepcopy(summary)
    info = classify_task_error(
        "request_unknown: otp_request_unconfirmed", task_type="registration_resume", stage="email_otp",
        error_code="request_unknown", result_summary=summary,
    )
    assert info["code"] == "email_otp_code_rejected"
    assert info["display_code"] == "OA-OTP-CODE-001"
    assert info["summary"] == "验证码被远端拒绝（wrong_email_otp_code）"
    assert info["stage"] == "email_otp"
    assert info["reconcile_required"] is True
    assert info["retryability"] == "manual_only"
    assert info["next_action"] == "manual_reconcile"
    assert info["remote_state_impact"] == "unknown"
    assert info["original_error_code"] == "request_unknown"
    assert summary == original


def test_raw_otp_rejection_cause_name_does_not_prove_response():
    info = classify_task_error("email_otp_code_rejected", task_type="registration", stage="email_otp")
    assert info["code"] != "email_otp_code_rejected"
