"""密码步骤的成功证据不能由本地凭据或后续 Token 状态代替。"""
from types import SimpleNamespace

import pytest

from core.auth.browser.browser_submission import BrowserSubmissionReceipt


def _receipt(stage="login_password", phase="confirmed", result="success", **kwargs):
    return BrowserSubmissionReceipt(
        kind="password", stage=stage, phase=phase, result=result,
        endpoint_kind="password_submit", http_method="POST", **kwargs,
    )


@pytest.mark.parametrize("stage,expected", [("login_password", "verified"), ("password_create", "accepted")])
def test_confirmed_password_has_its_own_result_after_otp_overwrites_current(stage, expected):
    from core.auth.browser.password_evidence import password_evidence

    receipt = _receipt(stage, http_status=200)
    driver = SimpleNamespace(
        _browser_submission_receipts=[receipt],
        _browser_submission_receipt=BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit"),
    )
    fact = password_evidence(driver)
    assert fact["credential_check"] == expected
    assert fact["submitted"] is True
    assert fact["http_status"] == 200
    assert "password" not in fact and "value" not in fact


@pytest.mark.parametrize("phase", ["dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed", "unknown"])
def test_dispatched_or_http_200_without_confirmed_transition_is_unknown(phase):
    from core.auth.browser.password_evidence import password_evidence

    driver = SimpleNamespace(_browser_submission_receipt=_receipt(phase=phase, http_status=200))
    assert password_evidence(driver)["credential_check"] == "unknown"


def test_old_receipt_and_saved_password_do_not_confirm_this_run():
    from core.auth.browser.password_evidence import password_evidence, password_receipt_ids

    receipt = _receipt()
    driver = SimpleNamespace(_browser_submission_receipts=[receipt], account_password="private")
    old_ids = password_receipt_ids(driver)
    assert password_evidence(driver, exclude_ids=old_ids)["credential_check"] == "skipped"
    driver._browser_submission_receipts.append(_receipt(phase="prepared", result=""))
    assert password_evidence(driver, exclude_ids=old_ids)["credential_check"] == "skipped"


def test_failed_http_response_does_not_confirm_or_reject_password_by_itself():
    from core.auth.browser.password_evidence import password_evidence

    driver = SimpleNamespace(_browser_submission_receipt=_receipt(http_status=401))
    assert password_evidence(driver)["credential_check"] == "unknown"


@pytest.mark.parametrize("code", ["invalid_auth_step", "missing_session", "password_reset_required"])
def test_auth_step_rejection_does_not_claim_saved_password_is_wrong(code):
    from core.auth.browser.password_evidence import password_evidence

    driver = SimpleNamespace(_browser_submission_receipt=_receipt(
        phase="rejected", result="failure", http_status=400, auth_error={"code": code},
    ))
    assert password_evidence(driver)["credential_check"] == "unknown"


@pytest.mark.parametrize("details", [
    {"auth_error": {"code": "incorrect_password"}},
    {"auth_error": {"code": "invalid_password"}},
    {"error_type": "PasswordRejectedError"},
])
def test_explicit_password_rejection_is_reported(details):
    from core.auth.browser.password_evidence import password_evidence

    driver = SimpleNamespace(_browser_submission_receipt=_receipt(
        phase="rejected", result="failure", http_status=400, **details,
    ))
    assert password_evidence(driver)["credential_check"] == "rejected"


@pytest.mark.parametrize("phase", ["prepared", "not_dispatched"])
def test_unsubmitted_next_attempt_does_not_erase_unresolved_dispatch(phase):
    from core.auth.browser.password_evidence import password_evidence

    driver = SimpleNamespace(_browser_submission_receipts=[
        _receipt(phase="unknown", result="unknown"), _receipt(phase=phase, result=""),
    ])
    evidence = password_evidence(driver)
    assert evidence["credential_check"] == "unknown"
    assert evidence["submitted"] is True


def test_latest_password_attempt_does_not_reuse_earlier_success():
    from core.auth.browser.password_evidence import password_evidence

    driver = SimpleNamespace(_browser_submission_receipts=[_receipt(), _receipt(phase="unknown", result="unknown")])
    assert password_evidence(driver)["credential_check"] == "unknown"


def test_foreign_receipt_objects_do_not_become_remote_success():
    from core.auth.browser.password_evidence import password_evidence

    driver = SimpleNamespace(_browser_submission_receipt=SimpleNamespace(endpoint_kind="password_submit", phase="confirmed", result="success"))
    assert password_evidence(driver)["credential_check"] == "skipped"
