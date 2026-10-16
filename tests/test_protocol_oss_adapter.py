from unittest.mock import Mock, patch

import pytest

from core.registration.protocol_oss import (
    _classify_upstream_continuation,
    _run_local_postprocessing,
    run_protocol_oss_registration,
)


def test_protocol_oss_requires_the_task_proxy_before_opening_a_session():
    with patch("core.registration.protocol_oss.BrowserSession") as browser_session:
        with pytest.raises(RuntimeError, match="统一代理池"):
            run_protocol_oss_registration(
                email="protocol-oss@example.test",
                name="Test User",
                proxy=None,
            )

    browser_session.assert_not_called()


def test_protocol_oss_classifies_existing_new_and_unknown_auth_continuations():
    assert _classify_upstream_continuation(
        "external_url", "https://chatgpt.com/api/auth/callback/openai"
    ) == "existing"
    assert _classify_upstream_continuation(
        "login_password", "https://auth.openai.com/log-in/password"
    ) == "existing"
    assert _classify_upstream_continuation(
        "about_you", "https://auth.openai.com/about-you"
    ) == "new_candidate"
    assert _classify_upstream_continuation("", "") == "unknown"


def test_protocol_oss_maps_existing_identity_to_local_manual_reconcile():
    from core.registration.protocol_oss import ProtocolOssManualReconcile

    session = Mock(proxy="http://proxy.example:8080")
    with (
        patch("core.registration.protocol_oss.BrowserSession", return_value=session),
        patch("core.email_provider.validate_email_source", return_value="outlook"),
        patch("core.email_provider.resolve_email_source", return_value="outlook"),
        patch(
            "core.registration.protocol_oss._run_upstream_protocol",
            side_effect=ProtocolOssManualReconcile("已有账号需要本地密码核验"),
        ),
        patch("core.registration.protocol._protocol_registration_cause_code", return_value="remote_identity_existing"),
        patch("core.registration.protocol._safe_protocol_registration_error", return_value="已有账号需要核验"),
        patch("core.email_provider.retain_email") as retain_email,
        patch("core.registration_service.report_job_progress"),
    ):
        result = run_protocol_oss_registration(
            email="protocol-oss@example.test",
            name="Test User",
            proxy=session.proxy,
            email_source="outlook",
        )

    assert result["manual_reconcile"] is True
    assert result["request_unknown"] is False
    assert result["error_code"] == "manual_reconcile"
    assert result["remote_identity"] == "existing"
    retain_email.assert_called_once()
    session.close.assert_called_once_with()


def test_protocol_oss_reports_missing_module_name_without_exposing_exception_text():
    session = Mock(proxy="http://proxy.example:8080")
    missing_module = ModuleNotFoundError("No module named 'safe_probe_dependency'", name="safe_probe_dependency")
    with (
        patch("core.registration.protocol_oss.BrowserSession", return_value=session),
        patch("core.email_provider.validate_email_source", return_value="icloud_hide"),
        patch("core.email_provider.resolve_email_source", return_value="icloud_hide"),
        patch("core.registration.protocol_oss._run_upstream_protocol", side_effect=missing_module),
        patch("core.email_provider.retain_email"),
        patch("core.registration_service.report_job_progress"),
    ):
        result = run_protocol_oss_registration(
            email="protocol-oss@example.test",
            name="Test User",
            proxy=session.proxy,
            email_source="icloud_hide",
        )

    assert result["cause_code"] == "python_module_missing"
    assert result["error"] == "开源 Protocol 缺少 Python 依赖：safe_probe_dependency"
    assert "No module named" not in result["error"]
    assert result["request_unknown"] is False
    session.close.assert_called_once_with()


def test_protocol_oss_persists_core_account_before_local_postprocessing():
    session = Mock()
    session.device_id = "device-fixture"
    session.proxy = "http://proxy.example:8080"
    options = {
        "registration_driver": "protocol_oss",
        "password_enabled": True,
        "twofa_enabled": False,
        "codex_enabled": False,
        "plan_check_enabled": False,
    }
    upstream_result = {
        "session_info": {"accessToken": "token-fixture", "user": {"id": "user-fixture"}},
        "access_token": "token-fixture",
        "registration_password": "password-fixture",
        "remote_identity": "new",
        "challenge_chain": ["password", "email_otp", "profile"],
    }
    postprocess_result = {
        "postprocess_success": True,
        "totp_secret": None,
        "flow": {"status": "skipped", "ok": False},
        "codex": {"status": "skipped", "ok": True},
        "plan_check": {"status": "skipped", "ok": True},
        "next_actions": [],
        "account_readiness": {"ready": True},
        "warnings": [],
    }
    with (
        patch("core.registration.protocol_oss.BrowserSession", return_value=session),
        patch("core.registration.protocol_oss._run_upstream_protocol", return_value=upstream_result) as upstream,
        patch("core.registration.protocol_oss._run_local_postprocessing", return_value=postprocess_result) as postprocess,
        patch("core.registration_service.persist_registration_core", return_value=21) as persist_core,
        patch("core.registration_service.report_job_progress"),
        patch("core.registration_service.check_stop_requested"),
    ):
        result = run_protocol_oss_registration(
            email="protocol-oss@example.test",
            name="Test User",
            birthday="1990-01-01",
            proxy=session.proxy,
            registration_options=options,
            email_source="icloud_hide",
        )

    upstream.assert_called_once_with(
        session,
        email="protocol-oss@example.test",
        name="Test User",
        birthday="1990-01-01",
        otp_code=None,
        email_source="icloud_hide",
        existing_password=None,
        existing_totp_secret=None,
        options=options,
    )
    persist_core.assert_called_once()
    assert persist_core.call_args.kwargs["email_source"] == "icloud_hide"
    assert persist_core.call_args.kwargs["proxy_used"] == session.proxy
    postprocess.assert_called_once_with(
        session=session,
        email="protocol-oss@example.test",
        access_token="token-fixture",
        account_id=21,
        session_info=upstream_result["session_info"],
        registration_password="password-fixture",
        email_source="icloud_hide",
        options=options,
    )
    assert result["registration_success"] is True
    assert result["core_persisted"] is True
    assert result["account_id"] == 21
    session.close.assert_called_once_with()


def test_protocol_oss_postprocessing_propagates_requested_stop():
    from core.registration_service import StopRequested

    session = Mock(proxy="http://proxy.example:8080")
    with (
        patch("config.codex.ENABLE_CODEX_AUTO", False),
        patch("config.twofa.ENABLE_2FA", False),
        patch("core.chatgpt_bootstrap.authenticated_bootstrap", side_effect=StopRequested("stop")),
        pytest.raises(StopRequested, match="stop"),
    ):
        _run_local_postprocessing(
            session=session,
            email="protocol-oss@example.test",
            access_token="token-fixture",
            account_id=21,
            session_info={"accessToken": "token-fixture"},
            registration_password="password-fixture",
            email_source="icloud_hide",
            options={"plan_check_enabled": False, "twofa_enabled": False, "codex_enabled": False},
        )


def test_protocol_oss_same_as_registration_uses_local_protocol_for_codex():
    session = Mock(proxy="http://proxy.example:8080")
    codex_result = {"status": "success", "ok": True, "message": "Codex 已完成"}
    with (
        patch("config.codex.ENABLE_CODEX_AUTO", True),
        patch("config.twofa.ENABLE_2FA", False),
        patch("core.chatgpt_bootstrap.authenticated_bootstrap"),
        patch("core.codex_oauth.run_codex_oauth", return_value=codex_result) as run_codex,
        patch("core.db.update_account_codex_status"),
        patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped", "ok": False}),
    ):
        _run_local_postprocessing(
            session=session,
            email="protocol-oss@example.test",
            access_token="token-fixture",
            account_id=21,
            session_info={"accessToken": "token-fixture"},
            registration_password="password-fixture",
            email_source="icloud_hide",
            options={
                "registration_driver": "protocol_oss",
                "password_enabled": True,
                "twofa_enabled": False,
                "codex_enabled": True,
                "codex_driver": "same_as_registration",
                "plan_check_enabled": False,
            },
        )

    assert run_codex.call_args.kwargs["driver_override"] == "protocol"
