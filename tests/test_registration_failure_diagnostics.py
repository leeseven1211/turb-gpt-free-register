"""注册外围只按受控请求证据分类，不改变驱动结果与邮箱收口。"""
import json
from unittest.mock import Mock, patch

import pytest

from core.registration.protocol import _safe_protocol_registration_error
from core.registration.protocol_oss import ProtocolOssRequestUnknown, run_protocol_oss_registration
from core.task_errors import classify_task_error


@pytest.mark.parametrize("diagnostics,cause_code", [
    ({"operation": "preauth", "failure_kind": "transport_error", "exception_type": "ProxyConnectionError",
      "failure_stage": "browser", "last_confirmed_stage": "", "otp_received": False, "profile_confirmed": False},
     "protocol_preauth_transport_failed"),
    ({"operation": "otp_validate", "failure_kind": "transport_error", "exception_type": "ConnectionError",
      "failure_stage": "email_otp", "last_confirmed_stage": "password", "otp_received": True, "profile_confirmed": False},
     "protocol_post_otp_transport_failed"),
    ({"operation": "password_submit", "failure_kind": "transport_error", "exception_type": "ReadTimeout",
      "failure_stage": "password", "last_confirmed_stage": "auth_redirect", "otp_received": False, "profile_confirmed": False},
     "protocol_auth_transport_failed"),
    ({"operation": "password_submit", "failure_kind": "http_error", "http_status": 403,
      "auth_error": {"code": "access_denied", "type": "permission_error"},
      "failure_stage": "password", "last_confirmed_stage": "auth_redirect", "otp_received": False, "profile_confirmed": False},
     "protocol_auth_rejected_before_password"),
    ({"operation": "otp_validate", "failure_kind": "http_error", "http_status": 500,
      "failure_stage": "email_otp", "last_confirmed_stage": "password", "otp_received": True, "profile_confirmed": False},
     "protocol_auth_http_failed"),
    ({"operation": "session", "failure_kind": "missing_session", "exception_type": "RuntimeError",
      "failure_stage": "token", "last_confirmed_stage": "profile", "otp_received": True, "profile_confirmed": True},
     "protocol_session_incomplete"),
])
@pytest.mark.parametrize("request_unknown", [False, True])
def test_driver_failure_keeps_safe_diagnostics_and_existing_outcome(diagnostics, cause_code, request_unknown):
    exc = ProtocolOssRequestUnknown("不应输出的正文 HTTP 401") if request_unknown else RuntimeError("不应输出的正文 HTTP 401")
    exc.registration_diagnostics = diagnostics
    session = Mock(proxy="http://proxy.example:8080")
    with (
        patch("core.registration_service.report_job_progress"),
        patch("core.email_provider.validate_email_source", return_value="outlook"),
        patch("core.email_provider.retain_email") as retain,
        patch("core.email_provider.mark_email_permanently_unusable") as mark,
    ):
        result = run_protocol_oss_registration(
            email="fixture@example.test", name="测试", proxy=session.proxy, email_source="outlook",
            _flow_runner=Mock(side_effect=exc), _session_factory=Mock(return_value=session),
        )
    assert result["success"] is False
    assert result["request_unknown"] is request_unknown
    assert result["manual_reconcile"] is False
    assert result["error_code"] == ("request_unknown" if request_unknown else "registration_failed")
    assert result["cause_code"] == cause_code
    assert result["registration_diagnostics"]["operation"] == diagnostics["operation"]
    assert result["registration_diagnostics"]["otp_received"] is diagnostics["otp_received"]
    assert result["registration_diagnostics"]["profile_confirmed"] is diagnostics["profile_confirmed"]
    assert cause_code in result["error"]
    assert "不应输出" not in result["error"]
    assert "HTTP 401" not in result["error"]
    retain.assert_called_once()
    mark.assert_not_called()
    for summary in ({}, result):
        info = classify_task_error(result["error"], task_type="registration", result_summary=summary)
        assert info["code"] == cause_code
        assert info["display_code"] != "UNK-000"


def test_diagnostic_attributes_cannot_inject_private_values_or_http_status_from_message():
    from core import task_errors

    raw = {
        "operation": "https://private.example.test/path", "http_status": True,
        "auth_error": {"code": "private-code", "type": "private-type", "message": "fixture-private"},
        "failure_kind": "private-failure", "exception_type": "private@example.test",
        "failure_stage": "fixture-private", "last_confirmed_stage": "fixture-private",
        "otp_received": "true", "profile_confirmed": "true", "exception_chain": ["TimeoutError", "fixture-private"] * 9,
        "response_body": "fixture-private", "access_token": "fixture-private",
    }
    sanitizer = getattr(task_errors, "safe_registration_diagnostics", None)
    assert callable(sanitizer)
    cleaned = sanitizer(raw)
    assert "fixture-private" not in json.dumps(cleaned)
    assert "private" not in json.dumps(cleaned)
    assert "http_status" not in cleaned
    assert "otp_received" not in cleaned
    assert "profile_confirmed" not in cleaned
    assert len(cleaned.get("exception_chain", [])) <= 8
    exc = RuntimeError("HTTP 401 access_token=fixture-private")
    exc.status_code = "401"
    exc.registration_diagnostics = cleaned
    rendered = _safe_protocol_registration_error(exc, "protocol_failure_evidence_missing")
    assert "HTTP" not in rendered
    assert "fixture-private" not in rendered


def test_diagnostic_formatter_uses_the_sanitized_exception_type():
    private_type = type("PrivateCredentialFixtureError", (RuntimeError,), {})
    exc = private_type("fixture-private")
    exc.registration_diagnostics = {
        "operation": "preauth", "failure_kind": "transport_error", "exception_type": "PrivateCredentialFixtureError",
    }
    rendered = _safe_protocol_registration_error(exc, "protocol_preauth_transport_failed")
    assert "PrivateCredentialFixtureError" not in rendered
    assert "fixture-private" not in rendered


@pytest.mark.parametrize("summary", [{}, {"cause_code": "user_register_result_unknown"}])
@pytest.mark.parametrize("message", [
    "request_unknown:账号创建请求结果待确认：ProtocolOssRequestUnknown HTTP 401",
    "request_unknown:账号创建请求结果待确认：ProtocolOssRequestUnknown HTTP 409",
])
def test_legacy_unknown_registration_does_not_invent_a_remote_http_cause(message, summary):
    info = classify_task_error(message, task_type="registration", result_summary=summary)
    assert "细项" in info["summary"] or "证据" in info["summary"]
    assert info["code"] not in {"account_create_invalid_state", "protocol_auth_rejected_before_password"}


def test_schema_key_error_is_local_configuration_mismatch_without_assuming_hot_reload():
    info = classify_task_error(
        "KeyError: 'schema 未定义字段: EXTRACT_LINK_LEGACY_PAYMENT_CDK'", task_type="registration",
    )
    assert info["code"] == "local_config_schema_mismatch"
    assert info["source"] == "internal"
    assert info["remote_state_impact"] == "unknown"
    assert info["retryability"] == "conditional"
    assert "schema" in info["summary"]
    assert "热更新" not in info["summary"]


def test_existing_mfa_transport_classification_remains_specific():
    info = classify_task_error("2FA 未完成：TwofaProtocolTransportError: enroll 传输失败，异常类型=ProxyConnectionError", task_type="registration")
    assert info["code"] == "external.network.mfa_transport"


@pytest.mark.parametrize("cause_code", ["registration_checkpoint_failed", "account_create_invalid_state"])
def test_specific_existing_cause_is_not_replaced_by_incomplete_diagnostic_facts(cause_code):
    info = classify_task_error("request_unknown", task_type="registration", result_summary={
        "cause_code": cause_code,
        "registration_diagnostics": {"failure_stage": "profile", "profile_confirmed": False},
    })
    assert info["code"] == cause_code
