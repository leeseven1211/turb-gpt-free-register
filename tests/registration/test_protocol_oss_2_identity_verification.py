"""资料接受后仍需身份核验时，准确报告原因并保留原身份供重跑。"""
from unittest.mock import patch

import pytest

from core.operations.errors import classify_task_error
from core.registration.protocol_oss_2 import run_protocol_oss_2_registration
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
from tests.registration.test_protocol_oss_2 import (
    _VENDOR_SIGNUP,
    registration_run_context,
    run_flow,
    upstream as upstream,
)


@pytest.mark.parametrize("existing_authentication", [False, True])
def test_identity_verification_keeps_a_specific_retryable_failure(upstream, existing_authentication):
    session, transport, _ = upstream
    transport.profile_payload = {
        "page": {"type": "identity_verification", "payload": {}},
        "continue_url": "https://auth.openai.com/verify-your-identity",
        "method": "GET",
    }
    if existing_authentication:
        transport.authorize_landing_url = "https://auth.openai.com/email-verification"
    with (
        registration_run_context(
            action_type="registration_resume" if existing_authentication else "registration",
            password="original-password",
        ),
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP) if existing_authentication else patch.object(
            AuthFlow, "signup", return_value=True,
        ),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email") as retain,
        patch("core.email.provider.mark_email_permanently_unusable") as mark_unusable,
        patch("core.registration.service.persist_registration_core") as persist,
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", proxy=session.proxy,
            email_source="icloud_hide", existing_password="original-password",
        )

    assert result["cause_code"] == "registration_identity_verification_required"
    assert result["request_unknown"] is True
    assert result["registration_pending"] is True
    assert result["manual_reconcile"] is False
    assert result["core_persisted"] is False
    assert "身份验证" in result["error"]
    assert sum(url.endswith("/create_account") for _, url, _ in transport.requests) == 1
    assert not any(url.endswith("/api/auth/session") for _, url, _ in transport.requests)
    retain.assert_called_once()
    mark_unusable.assert_not_called()
    persist.assert_not_called()
    for summary in ({}, result):
        info = classify_task_error(result["error"], task_type="registration", result_summary=summary)
        assert info["cause_code"] == "registration_identity_verification_required"
        assert info["display_code"] == "AUTH-REG-IDENTITY-001"


@pytest.mark.parametrize("continue_url", [
    "https://chatgpt.com/api/auth/callback/openai?next=/verify-your-identity",
    "https://auth.openai.com/about-you?next=/verify-your-identity",
    "https://auth.openai.com.example.test/verify-your-identity",
    "http://auth.openai.com/verify-your-identity",
    "https://auth.openai.com:8443/verify-your-identity",
    "https://user@auth.openai.com/verify-your-identity",
])
def test_other_continuations_are_not_misclassified_as_identity_verification(upstream, continue_url):
    session, transport, _ = upstream
    transport.profile_payload = {"page": {"type": "external_url"}, "continue_url": continue_url}

    result = run_flow(session)

    assert result["access_token"] == "fixture-at"
