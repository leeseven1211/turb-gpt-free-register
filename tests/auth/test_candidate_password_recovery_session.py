"""候选认证会话在进入事务前校验私有归属与真实网络配对。"""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.browser.password_recovery import PasswordRecoverySession
from core.storage.accounts import password_recovery as store


@pytest.fixture
def candidate_context():
    owner = dict(email="candidate@example.test", account_id=8, purpose="registration",
        operation_run_id=10, operation_execution_id="operation-execution", operation_lease_token=None,
        attempt_id=20, registration_run_id=30, registration_execution_id="registration-execution")
    session = PasswordRecoverySession(**owner)
    session._checkpoint = store.PrivateCheckpoint(recovery_id=1, state="unknown", version=3,
        **{key: value for key, value in owner.items() if key != "operation_lease_token"},
        account_password_version="private-version", old_password="old-password", password="candidate-password")
    driver = SimpleNamespace(_registration_resume_login=True, _registration_fact_context={
        "attempt_id": 20, "run_id": 30, "execution_id": "registration-execution", "job_id": 40})
    receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", phase="confirmed",
        endpoint_kind="password_submit", http_method="POST", http_status=200, result="success",
        dispatch_target_id="fixture-target", request_binding=("fixture-target", "request-memory-only"),
        response_binding=("fixture-target", "request-memory-only"))
    return session, driver, receipt


@pytest.mark.parametrize("change", [
    "missing_checkpoint", "manual", "email", "candidate", "resume", "attempt", "run", "execution", "job",
    "receipt_kind", "receipt_stage", "receipt_endpoint", "receipt_method", "receipt_phase", "receipt_result",
    "receipt_status", "receipt_binding", "receipt_target", "receipt_auth_error", "receipt_missing_request",
])
def test_invalid_candidate_identity_or_network_evidence_stops_before_transaction(candidate_context, change):
    session, driver, receipt = candidate_context
    email, password = "candidate@example.test", "candidate-password"
    if change == "missing_checkpoint":
        session._checkpoint = None
    elif change == "manual":
        session._checkpoint = replace(session.checkpoint, purpose="manual")
    elif change == "email":
        email = "other@example.test"
    elif change == "candidate":
        password = "other-password"
    elif change == "resume":
        driver._registration_resume_login = False
    elif change in {"attempt", "run", "execution", "job"}:
        driver._registration_fact_context[{"attempt": "attempt_id", "run": "run_id", "execution": "execution_id", "job": "job_id"}[change]] = None
    else:
        field, value = {
            "receipt_kind": ("kind", "password"), "receipt_stage": ("stage", "password_create"),
            "receipt_endpoint": ("endpoint_kind", "otp_submit"), "receipt_method": ("http_method", "GET"),
            "receipt_phase": ("phase", "unknown"), "receipt_result": ("result", "failure"),
            "receipt_status": ("http_status", 401), "receipt_binding": ("response_binding", ("fixture-target", "different-request")),
            "receipt_target": ("dispatch_target_id", "other-target"), "receipt_auth_error": ("auth_error", {"code": "denied"}),
            "receipt_missing_request": ("request_binding", None),
        }[change]
        setattr(receipt, field, value)
    with patch.object(store, "transition_password_recovery", side_effect=AssertionError("无效确认进入了事务")):
        with pytest.raises(store.PasswordRecoveryError):
            session.confirm_candidate_login(driver, email=email, password=password, receipt=receipt)


def test_mixed_case_owner_and_input_email_use_persisted_normalized_identity(candidate_context):
    session, driver, receipt = candidate_context
    session._owner["email"] = " Candidate@Example.Test "
    confirmed = replace(session.checkpoint, state="confirmed", version=4)
    with patch.object(store, "transition_password_recovery", return_value=confirmed):
        assert session.confirm_candidate_login(driver, email=" CANDIDATE@example.TEST ",
            password="candidate-password", receipt=receipt) == "candidate-password"
    assert session.checkpoint.state == "confirmed"


@pytest.mark.parametrize("field", ["account_id", "operation_run_id", "operation_execution_id", "attempt_id",
                                    "registration_run_id", "registration_execution_id"])
def test_mixed_case_email_does_not_relax_other_owner_identity(candidate_context, field):
    session, driver, receipt = candidate_context
    session._owner["email"] = " Candidate@Example.Test "
    session._owner[field] = "different-owner"
    with patch.object(store, "transition_password_recovery", side_effect=AssertionError("不同归属进入了事务")):
        with pytest.raises(store.PasswordRecoveryError, match="candidate_login_context_invalid"):
            session.confirm_candidate_login(driver, email="candidate@example.test", password="candidate-password", receipt=receipt)
