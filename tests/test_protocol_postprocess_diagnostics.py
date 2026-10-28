"""协议注册后置错误保留可分类证据，不改变认证和重试行为。"""
from unittest.mock import Mock, patch

import pytest

from core.account_export import TwofaProtocolHTTPError, TwofaProtocolTransportError
from core.registration.protocol_oss import _run_local_postprocessing
from core.task_errors import classify_task_error


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (TwofaProtocolTransportError("enroll", "ProxyConnectionError"),
         ("TwofaProtocolTransportError", "enroll", "ProxyConnectionError")),
        (TwofaProtocolHTTPError("activate", 429, detail="不可输出的远端正文"),
         ("TwofaProtocolHTTPError", "activate", "HTTP 429")),
        (RuntimeError("不可输出的远端正文"), ("RuntimeError",)),
    ],
)
def test_twofa_failure_keeps_safe_cause_in_final_result_without_retry(failure, expected):
    events = []
    with (
        patch("core.registration.protocol_oss._upstream_config.CHATGPT_AUTH_BOOTSTRAP_ENABLED", False),
        patch("config.twofa.get_twofa_driver_for_options", return_value="protocol"),
        patch("core.registration_service.report_job_progress", side_effect=lambda *args: events.append(args)),
        patch("core.account_export.setup_2fa_protocol", side_effect=failure) as setup,
        patch("core.db.update_account_codex_status"),
        patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped"}),
    ):
        result = _run_local_postprocessing(
            session=Mock(proxy="http://proxy.example:8080"), email="unit@example.test",
            access_token="fixture-at", account_id=42, session_info={},
            registration_password="fixture-password", email_source="email_butler",
            options={"twofa_enabled": True, "codex_enabled": False, "plan_check_enabled": False},
        )
    assert result["postprocess_success"] is False
    assert result["totp_secret"] is None
    for text in expected:
        assert text in result["error"]
    assert "不可输出的远端正文" not in result["error"]
    assert "不可输出的远端正文" not in str(events)
    setup.assert_called_once()
    if isinstance(failure, TwofaProtocolTransportError):
        assert classify_task_error(result["error"], task_type="registration")["code"] == "external.network.mfa_transport"
