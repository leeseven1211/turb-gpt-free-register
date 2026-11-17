"""强制密码及逐项补全失败均保留明确原因，可沿原任务继续。"""
import pytest

from core.operations.errors import classify_task_error, REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES
from core.registration.errors import _safe_protocol_registration_error


@pytest.mark.parametrize("code", [
    "registration_password_entry_unavailable", "registration_password_create_rejected",
    "registration_password_unconfirmed", "registration_auth_state_unrecognized",
    "registration_session_invalid_response", "registration_identity_verification_required",
    "registration_profile_submission_unresolved",
    "protocol_unmapped_request_transport_failed",
])
def test_required_registration_failure_keeps_fixed_cause_on_all_surfaces(code):
    assert code in REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES
    safe = _safe_protocol_registration_error(RuntimeError("私有正文不应进入摘要"), code)
    assert code in safe
    assert "私有正文" not in safe
    for raw, summary in ((safe, {}), ("注册未完成", {"cause_code": code})):
        info = classify_task_error(raw, task_type="registration", result_summary=summary)
        assert info["cause_code"] == code
        assert info["display_code"] != "UNK-000"


@pytest.mark.parametrize("code", [
    "account_setup_step_not_executed", "account_setup_step_not_completed",
    "password_setup_unsupported", "password_setup_page_not_ready", "twofa_setup_failed",
    "account_action_route_exhausted", "account_action_request_unknown", "account_action_route_unavailable",
    "account_action_rate_limited", "account_action_http_rejected",
])
def test_requested_setup_step_failure_has_a_specific_classification(code):
    info = classify_task_error(code, task_type="account_setup_retry", result_summary={"cause_code": code})
    assert info["cause_code"] == code
    assert info["display_code"] != "UNK-000"


def test_historical_exact_password_message_is_no_longer_unclassified():
    info = classify_task_error("原密码尚未确认生效", task_type="registration")
    assert info["cause_code"] == "registration_password_unconfirmed"
    assert info["display_code"] != "UNK-000"
