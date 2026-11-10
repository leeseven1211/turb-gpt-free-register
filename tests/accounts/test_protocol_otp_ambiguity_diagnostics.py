"""验证码候选歧义保留具体原因，不改变认证结果或待核验状态。"""

from copy import deepcopy
import json

import pytest

from core.accounts.liveness.protocol.otp_diagnostics import otp_failure_diagnostics
from core.accounts.liveness.service import _safe_refresh_auth_diagnostics
from core.email.email_butler.client import EmailButlerClientError
from core.operations.errors import classify_task_error


PRIVATE_DETAIL = "fixture-private otp-fixture@example.test token=fixture-secret"


def test_butler_ambiguity_keeps_specific_reason_without_exception_text():
    error = EmailButlerClientError(PRIVATE_DETAIL, error_code="inbound_code_ambiguous")

    diagnostics = otp_failure_diagnostics(error)

    assert diagnostics == {
        "operation": "email_otp",
        "failure_kind": "mailbox_error",
        "exception_type": "EmailButlerClientError",
        "mailbox_error_code": "inbound_code_ambiguous",
    }
    assert PRIVATE_DETAIL not in json.dumps(diagnostics)
    assert str(error) == PRIVATE_DETAIL


@pytest.mark.parametrize("fallback", [False, True])
def test_ambiguity_survives_service_and_task_projection(fallback):
    diagnostics = otp_failure_diagnostics(EmailButlerClientError(
        PRIVATE_DETAIL, error_code="inbound_code_ambiguous",
    ))
    code = "email_otp_failed"
    if fallback:
        code = "password_rejected_email_fallback_failed"
        diagnostics.update(
            operation="password_email_fallback", failure_kind="fallback_failed",
            cause_code="email_otp_failed", cause_operation="email_otp", cause_failure_kind="mailbox_error",
        )
    diagnostics["private_message"] = PRIVATE_DETAIL
    original = deepcopy(diagnostics)

    safe = _safe_refresh_auth_diagnostics(diagnostics)

    assert safe["mailbox_error_code"] == "inbound_code_ambiguous"
    assert "private_message" not in safe
    assert diagnostics == original
    summary = {"cause_code": code, "auth_diagnostics": safe, "outcome": "request_unknown"}
    original_summary = deepcopy(summary)

    info = classify_task_error(
        code, task_type="token_refresh", task_status="attention_required", result_summary=summary,
    )

    assert info["display_code"] == "MAIL-BUTLER-V2-AMBIGUOUS"
    assert "多个验证码投递候选" in info["summary"]
    assert info["reconcile_required"] is True
    assert info["next_action"] == "manual_reconcile"
    assert info["remote_state_impact"] == "unknown"
    assert summary == original_summary
    assert PRIVATE_DETAIL not in json.dumps(info)


def test_ambiguity_code_is_only_retained_for_otp_diagnostics():
    safe = _safe_refresh_auth_diagnostics({
        "operation": "password_verify", "failure_kind": "mailbox_error",
        "mailbox_error_code": "inbound_code_ambiguous",
    })

    assert "mailbox_error_code" not in safe


def test_unknown_mailbox_code_and_no_mail_classification_remain_separate():
    unknown = otp_failure_diagnostics(EmailButlerClientError(
        PRIVATE_DETAIL, error_code=PRIVATE_DETAIL,
    ))
    no_mail = otp_failure_diagnostics(EmailButlerClientError(
        PRIVATE_DETAIL, error_code="inbound_code_timeout",
    ))

    assert unknown["mailbox_error_code"] == "unknown"
    assert PRIVATE_DETAIL not in json.dumps(unknown)
    assert no_mail["mailbox_error_code"] == "inbound_code_timeout"
    assert no_mail["failure_kind"] == "no_mail"
