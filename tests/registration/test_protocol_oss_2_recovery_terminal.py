"""注册身份恢复以当前失败收口，回调必须实际消费后才可取得会话。"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.operations.errors import classify_task_error
from core.registration.protocol_oss_2 import run_protocol_oss_2_registration, runtime
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
from tests.registration.test_protocol_oss_2 import (
    registration_run_context,
    run_flow,
    upstream as upstream,
)
from tests.registration.test_protocol_oss_2_route_recovery import Response


_VENDOR_REDIRECT = AuthFlow.follow_redirect_chain
_NEW_PROXY = "http://recovery.example.test:8080"


def _run_registration(session):
    return run_protocol_oss_2_registration(
        email="protocol2@example.test", name="测试姓名", proxy=session.proxy,
        email_source="icloud_hide", existing_password="original-password",
    )


@pytest.mark.parametrize("operation", ["password_create", "profile_submit"])
def test_strict_recovery_consumes_its_callback_before_session_and_skips_exchange(upstream, monkeypatch, operation):
    session, transport, _ = upstream
    request = transport.request
    initial_url = "https://auth.openai.com/api/accounts/" + (
        "user/register" if operation == "password_create" else "create_account"
    )
    consumed = False
    facts = []

    def conditional_session(method, url, **kwargs):
        nonlocal consumed
        if url == initial_url:
            transport.requests.append((method, url, kwargs))
            raise TimeoutError("原提交未收到响应")
        if "/api/auth/callback/openai" in url:
            assert not consumed, "同一回调只能消费一次"
            consumed = True
        response = request(method, url, **kwargs)
        if url.endswith("/api/auth/session") and not consumed:
            response.json.return_value = {}
        return response

    transport.request = conditional_session
    monkeypatch.setattr(runtime, "current_route_recovery", lambda: lambda *_: SimpleNamespace(
        proxy_url=_NEW_PROXY, lease_id="new-lease",
    ))
    with (
        registration_run_context(action_type="registration", password="original-password"),
        patch("core.storage.registration.record_submission_fact", side_effect=lambda *a, **kw: facts.append(kw)),
        patch.object(AuthFlow, "run_register", lambda flow, mailbox: flow.session.post(initial_url)),
        patch.object(AuthFlow, "follow_redirect_chain", _VENDOR_REDIRECT),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "login_password"}, "continue_url": "/log-in/password",
        }),
    ):
        result = run_flow(session, existing_password="original-password")

    assert result["access_token"] == "fixture-at"
    assert consumed is True
    assert result["route_unknown_operations"] == [operation]
    assert sum(url == initial_url for _, url, _ in transport.requests) == 1
    assert sum("/api/auth/callback/openai" in url for _, url, _ in transport.requests) == 1
    assert not any(url.endswith("/oauth/token") for _, url, _ in transport.requests)
    assert len(facts) == 1 and facts[0]["phase"] == "unknown"
    callback_index = next(i for i, (_, url, _) in enumerate(transport.requests) if "/api/auth/callback/openai" in url)
    assert transport.requests[callback_index + 1][1].endswith("/api/auth/session")


@pytest.mark.parametrize("initial_operation", ["password_create", "profile_submit"])
def test_recovery_password_rejection_is_current_cause_and_old_unknown_stays_audit(
    upstream, monkeypatch, initial_operation,
):
    session, transport, _ = upstream
    request = transport.request
    initial_url = "https://auth.openai.com/api/accounts/" + (
        "user/register" if initial_operation == "password_create" else "create_account"
    )
    transport.session_payloads = [{}]
    saved = []

    def reject_password(method, url, **kwargs):
        if url == initial_url:
            transport.requests.append((method, url, kwargs))
            raise TimeoutError("旧提交连接失败，包含 private@example.test token=private")
        if url.endswith("/password/verify"):
            transport.requests.append((method, url, kwargs))
            response = Response(401)
            response.text = json.dumps({"error": {
                "code": "incorrect_password", "type": "authentication_error",
                "message": "private@example.test token=private",
            }})
            return response
        return request(method, url, **kwargs)

    transport.request = reject_password
    monkeypatch.setattr(runtime, "current_route_recovery", lambda: lambda *_: SimpleNamespace(
        proxy_url=_NEW_PROXY, lease_id="new-lease",
    ))
    with (
        registration_run_context(action_type="registration_resume", password="original-password"),
        patch("core.storage.registration.record_submission_fact", side_effect=lambda *a, **kw: saved.append(kw)),
        patch.object(AuthFlow, "run_register", lambda flow, mailbox: flow.session.post(initial_url)),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "login_password"}, "continue_url": "/log-in/password",
        }),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = _run_registration(session)

    assert result["request_unknown"] is True
    assert result["route_recovery_blocked"] is True
    assert "route_failure" not in result
    assert result["cause_code"] == "protocol_auth_rejected_before_password"
    assert result["registration_diagnostics"]["http_status"] == 401
    assert result["registration_diagnostics"]["failure_kind"] == "http_error"
    assert result["registration_diagnostics"]["auth_error"]["code"] == "incorrect_password"
    assert result["registration_recovery_audit"][-1]["registration_diagnostics"]["exception_type"] == "TimeoutError"
    assert len(saved) == 1 and saved[0]["phase"] == "unknown"
    assert "private" not in json.dumps(result["registration_recovery_audit"])
    info = classify_task_error(result["error"], task_type="registration", result_summary=result)
    assert info["cause_code"] == "protocol_auth_rejected_before_password"


def test_unknown_profile_guard_has_its_own_cause_instead_of_the_old_transport_error(upstream, monkeypatch):
    session, transport, _ = upstream
    request = transport.request
    saved = []
    initial_url = "https://auth.openai.com/api/accounts/create_account"
    transport.session_payloads = [{}]

    def fail_profile(method, url, **kwargs):
        if url == initial_url:
            transport.requests.append((method, url, kwargs))
            raise TimeoutError("原资料提交未知")
        return request(method, url, **kwargs)

    transport.request = fail_profile
    monkeypatch.setattr(runtime, "current_route_recovery", lambda: lambda *_: SimpleNamespace(
        proxy_url=_NEW_PROXY, lease_id="new-lease",
    ))
    with (
        registration_run_context(action_type="registration_resume", password="original-password"),
        patch("core.storage.registration.record_submission_fact", side_effect=lambda *a, **kw: saved.append(kw)),
        patch.object(AuthFlow, "run_register", lambda flow, mailbox: flow.session.post(initial_url)),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "about_you"}, "continue_url": "/about-you",
        }),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = _run_registration(session)

    assert result["cause_code"] == "registration_profile_submission_unresolved"
    assert result["route_recovery_blocked"] is True
    assert result["registration_diagnostics"]["failure_kind"] == "unknown"
    assert "route_failure" not in result
    assert result["registration_recovery_audit"][-1]["route_failure"]["operation"] == "profile_submit"
    assert sum(url == initial_url for _, url, _ in transport.requests) == 1
    assert len(saved) == 1


def test_new_current_transport_failure_keeps_recovery_permission_and_its_own_operation(upstream, monkeypatch):
    session, transport, _ = upstream
    request = transport.request
    initial_url = "https://auth.openai.com/api/accounts/create_account"
    transport.session_payloads = [{}]
    calls = []

    def fail_two_actions(method, url, **kwargs):
        if url in {initial_url, "https://auth.openai.com/api/accounts/password/verify"}:
            transport.requests.append((method, url, kwargs))
            raise TimeoutError("当前请求无响应")
        return request(method, url, **kwargs)

    def recover(failure, proxy):
        calls.append(failure.operation)
        return SimpleNamespace(proxy_url=_NEW_PROXY, lease_id="new-lease") if len(calls) == 1 else None

    transport.request = fail_two_actions
    monkeypatch.setattr(runtime, "current_route_recovery", lambda: recover)
    with (
        registration_run_context(action_type="registration_resume", password="original-password"),
        patch("core.storage.registration.record_submission_fact"),
        patch.object(AuthFlow, "run_register", lambda flow, mailbox: flow.session.post(initial_url)),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "login_password"}, "continue_url": "/log-in/password",
        }),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = _run_registration(session)

    assert result.get("route_recovery_blocked") is not True
    assert result["route_failure"]["operation"] == "password_verify"
    assert result["registration_diagnostics"]["operation"] == "password_submit"
    assert result["registration_diagnostics"]["failure_kind"] == "transport_error"
    assert calls == ["profile_submit", "password_verify"]


def test_empty_session_after_a_caught_profile_rejection_does_not_reuse_its_http_cause(upstream):
    session, transport, _ = upstream
    transport.profile_status = 409
    transport.profile_payload = {"error": {"code": "invalid_state", "type": "invalid_request_error"}}
    transport.session_payloads = [{}]

    def fail_after_profile(flow, mailbox):
        try:
            flow.create_account()
        except RuntimeError:
            pass
        flow.get_auth_session()
        raise RuntimeError("本轮会话没有完整身份")

    with (
        patch.object(AuthFlow, "run_register", fail_after_profile),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = _run_registration(session)

    assert result["cause_code"] == "registration_session_invalid_response"
    assert result["route_recovery_blocked"] is True
    assert "cause_diagnostics" not in result
    assert result["registration_diagnostics"].get("http_status") is None
    assert result["registration_recovery_audit"][0]["registration_diagnostics"]["http_status"] == 409


def test_unmapped_transport_failure_keeps_safe_request_class_without_url_values(upstream):
    session, transport, _ = upstream
    transport.request = lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("private@example.test"))

    def fail_unknown_request(flow, mailbox):
        flow.session.get("https://auth.openai.com/unmapped-private?token=private")

    with (
        patch.object(AuthFlow, "run_register", fail_unknown_request),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = _run_registration(session)

    diagnostics = result["registration_diagnostics"]
    assert diagnostics["request_method"] == "GET"
    assert diagnostics["request_host_class"] == "auth"
    assert diagnostics["request_path_class"] == "unmapped"
    assert result["cause_code"] == "protocol_unmapped_request_transport_failed"
    assert "private" not in json.dumps(diagnostics)


def test_profile_response_without_a_continuation_has_a_specific_response_cause(upstream):
    session, transport, _ = upstream
    transport.profile_payload = {}
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = _run_registration(session)

    assert result["cause_code"] == "user_register_continue_url_missing"
    assert result["route_recovery_blocked"] is True
    assert sum(url.endswith("/create_account") for _, url, _ in transport.requests) == 1


def test_recovery_audit_validates_dataclass_values_before_exporting_them():
    from core.registration.route_recovery import RegistrationRouteFailure, safe_registration_recovery_audit

    private = RegistrationRouteFailure(
        "private@example.test", transport_kind="https://private.example.test/?token=private",
    )
    assert safe_registration_recovery_audit([{"route_failure": private}]) == []
