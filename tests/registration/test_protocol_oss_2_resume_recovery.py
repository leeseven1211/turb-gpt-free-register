"""原身份的确定认证死路只恢复一次，并保留同一会话和原提交事实。"""
from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

from core.network.response_diagnostics import auth_error_from_body
from core.registration.protocol_oss_2.lifecycle import ProtocolOssRequestUnknown
from core.registration.protocol_oss_2.runtime import ProtocolSessionResponseError
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
from tests.registration.test_protocol_oss_2 import (
    _VENDOR_SIGNUP,
    registration_run_context,
    run_flow,
    upstream as upstream,
)


def _response(url, status, payload):
    response = Mock(status_code=status, url=url, headers={}, content=b"{}")
    response.text = json.dumps(payload)
    response.json.return_value = payload
    return response


def _resume_transport(transport, *, mismatch=False, login_page="login_password", password_status=200):
    request = transport.request
    state = {"login_probes": 0}
    transport.authorize_landing_url = "https://auth.openai.com/email-verification"

    def respond(method, url, **kwargs):
        if url.endswith("/authorize/continue"):
            state["login_probes"] += 1
            transport.requests.append((method, url, kwargs))
            target = {
                "login_password": "/log-in/password",
                "email_otp_verification": "/email-verification",
                "about_you": "/about-you",
                "create_account_password": "/create-account/password",
                "external_url": "https://chatgpt.com/api/auth/callback/openai?code=fresh",
            }[login_page]
            return _response(url, 200, {"page": {"type": login_page}, "continue_url": target})
        if mismatch and not state["login_probes"] and url.endswith("/email-otp/validate"):
            transport.requests.append((method, url, kwargs))
            return _response(url, 400, {"error": {
                "code": "identity_provider_mismatch", "type": "invalid_request_error",
                "message": "private@example.test private-token",
            }})
        if password_status != 200 and url.endswith("/password/verify"):
            transport.requests.append((method, url, kwargs))
            return _response(url, password_status, {"error": {
                "code": "incorrect_password", "type": "authentication_error",
            }})
        response = request(method, url, **kwargs)
        if url.endswith("/api/auth/session") and not state["login_probes"]:
            response.json.return_value = {}
        if state["login_probes"] and url.endswith("/email-otp/validate"):
            response.json.return_value = {
                "page": {"type": "external_url"},
                "continue_url": "https://chatgpt.com/api/auth/callback/openai?code=fresh",
            }
        return response

    transport.request = respond
    return state


def test_method_mismatch_retains_its_safe_error_code_without_message():
    diagnostic = auth_error_from_body(json.dumps({"error": {
        "code": "identity_provider_mismatch", "type": "invalid_request_error",
        "message": "private@example.test private-token",
    }}))
    assert diagnostic == {
        "code": "identity_provider_mismatch", "type": "invalid_request_error", "category": "auth_state",
    }


def test_current_method_mismatch_recovers_original_password_in_the_same_transport(upstream):
    session, transport, wait = upstream
    state = _resume_transport(transport, mismatch=True)
    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch(
            "core.registration.protocol_oss_2.upstream.http_client_wreq.create_http_session",
            return_value=transport,
        ) as factory,
    ):
        result = run_flow(session, existing_password="original-password")

    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is True
    assert state["login_probes"] == 1
    assert factory.call_count == 1
    assert transport.closed is False
    assert wait.call_count == 1
    assert sum(url.endswith("/email-otp/validate") for _, url, _ in transport.requests) == 1
    assert sum(url.endswith("/password/verify") for _, url, _ in transport.requests) == 1
    assert not any(url.endswith(("/user/register", "/create_account")) for _, url, _ in transport.requests)
    assert transport.checkpoints == []


@pytest.mark.parametrize("login_page", ["login_password", "external_url"])
def test_empty_session_recovers_without_submitting_confirmed_profile_again(upstream, login_page):
    session, transport, _ = upstream
    state = _resume_transport(transport, login_page=login_page)
    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
    ):
        result = run_flow(session, existing_password="original-password")

    assert result["access_token"] == "fixture-at"
    assert state["login_probes"] == 1
    assert sum(url.endswith("/create_account") for _, url, _ in transport.requests) == 1
    assert not any(url.endswith(("/user/register", "/oauth/token")) for _, url, _ in transport.requests)
    assert result["password_validated"] is (login_page == "login_password")


def test_empty_session_cannot_resubmit_profile_when_recovery_returns_about_you(upstream):
    session, transport, _ = upstream
    state = _resume_transport(transport, login_page="about_you")
    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        pytest.raises(ProtocolOssRequestUnknown) as raised,
    ):
        run_flow(session, existing_password="original-password")

    assert state["login_probes"] == 1
    assert sum(url.endswith("/create_account") for _, url, _ in transport.requests) == 1
    assert raised.value.cause_code == "registration_profile_submission_unresolved"


def test_new_challenge_discards_even_an_unused_caller_supplied_code(upstream):
    session, transport, wait = upstream
    state = _resume_transport(transport, login_page="email_otp_verification")

    def empty_session(flow, mailbox):
        flow.get_auth_session()
        raise ProtocolSessionResponseError("本轮会话不完整")

    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "run_register", empty_session),
    ):
        result = run_flow(session, existing_password="original-password", otp_code="654321")

    assert result["access_token"] == "fixture-at"
    assert state["login_probes"] == 1
    submitted = [kwargs["json"]["code"] for _, url, kwargs in transport.requests
                 if url.endswith("/email-otp/validate")]
    assert submitted == ["123456"]
    assert wait.call_count == 1
    assert wait.call_args.kwargs["after_ts"] > 0


def test_recovery_password_rejection_stops_once_and_keeps_the_current_cause(upstream):
    session, transport, _ = upstream
    state = _resume_transport(transport, mismatch=True, password_status=401)
    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        pytest.raises(ProtocolOssRequestUnknown) as raised,
    ):
        run_flow(session, existing_password="original-password")

    assert state["login_probes"] == 1
    assert raised.value.registration_diagnostics["http_status"] == 401
    assert raised.value.registration_diagnostics["auth_error"]["code"] == "incorrect_password"
    audit = raised.value.registration_recovery_audit
    assert audit[-1]["registration_diagnostics"]["http_status"] == 400
    assert "private" not in json.dumps(audit)
    assert transport.checkpoints == []


@pytest.mark.parametrize("terminal", ["method_mismatch", "empty_session"])
def test_a_prior_password_rejection_blocks_both_nonnetwork_recovery_triggers(upstream, terminal):
    session, transport, _ = upstream
    state = _resume_transport(transport, mismatch=True)
    transport.password_status = 400
    transport.password_payload = {"error": {
        "code": "invalid_state", "type": "invalid_request_error",
    }}

    def rejected_password_then_auth_failure(flow, mailbox):
        flow.before_password_submit("protocol2@example.test", "original-password")
        response = flow.session.post(
            "https://auth.openai.com/api/accounts/user/register",
            json={"email": "protocol2@example.test", "password": "original-password"},
        )
        assert response.status_code == 400
        if terminal == "method_mismatch":
            return flow.verify_otp("123456")
        flow.get_auth_session()
        raise ProtocolSessionResponseError("本轮会话不完整")

    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "run_register", rejected_password_then_auth_failure),
        pytest.raises(ProtocolOssRequestUnknown),
    ):
        run_flow(session, existing_password="original-password")

    assert state["login_probes"] == 0
    assert not any(url.endswith("/password/verify") for _, url, _ in transport.requests)
    assert len(transport.checkpoints) == 1


@pytest.mark.parametrize("initial_kind", [
    "new_registration", "no_candidate", "unknown_otp", "profile_rejected", "profile_invalid_response",
])
def test_nonnetwork_recovery_does_not_broaden_registration_or_unknown_write_policy(upstream, initial_kind):
    session, transport, _ = upstream
    state = _resume_transport(transport, mismatch=initial_kind in {"new_registration", "no_candidate"})
    if initial_kind == "unknown_otp":
        request = transport.request

        def unknown_otp(method, url, **kwargs):
            if url.endswith("/email-otp/validate"):
                transport.requests.append((method, url, kwargs))
                raise TimeoutError("原验码回执缺失")
            return request(method, url, **kwargs)

        transport.request = unknown_otp
    if initial_kind == "profile_rejected":
        transport.profile_status = 409
        transport.profile_payload = {"error": {"code": "invalid_state", "type": "invalid_request_error"}}
    if initial_kind == "profile_invalid_response":
        transport.profile_payload = {}
    password = None if initial_kind == "no_candidate" else "original-password"
    with (
        registration_run_context(
            action_type="registration" if initial_kind == "new_registration" else "registration_resume",
            password=password,
        ),
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        pytest.raises((ProtocolOssRequestUnknown, RuntimeError)),
    ):
        run_flow(session, existing_password=password)

    assert state["login_probes"] == 0


def test_stale_mismatch_cannot_trigger_recovery_for_a_different_later_error(upstream):
    session, transport, _ = upstream
    state = _resume_transport(transport, mismatch=True)

    def replaced_failure(flow, mailbox):
        try:
            flow.verify_otp("123456")
        except RuntimeError:
            pass
        raise ValueError("独立的后续失败")

    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "run_register", replaced_failure),
        pytest.raises(ProtocolOssRequestUnknown),
    ):
        run_flow(session, existing_password="original-password")

    assert state["login_probes"] == 0


@pytest.mark.parametrize("payload", [
    {"accessToken": "one", "access_token": "two"},
    {"user": {"email": "different@example.test"}},
])
def test_incomplete_session_with_conflicting_identity_never_recovers(upstream, payload):
    session, transport, _ = upstream
    state = _resume_transport(transport)
    request = transport.request

    def conflicting_session(method, url, **kwargs):
        response = request(method, url, **kwargs)
        if url.endswith("/api/auth/session"):
            response.json.return_value = payload
        return response

    transport.request = conflicting_session
    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        pytest.raises(ProtocolOssRequestUnknown) as raised,
    ):
        run_flow(session, existing_password="original-password")

    assert state["login_probes"] == 0
    assert raised.value.cause_code == "identity_mismatch"


def test_a_second_empty_session_stops_without_a_second_login(upstream):
    session, transport, _ = upstream
    state = _resume_transport(transport)
    request = transport.request

    def always_empty(method, url, **kwargs):
        response = request(method, url, **kwargs)
        if url.endswith("/api/auth/session"):
            response.json.return_value = {}
        return response

    transport.request = always_empty
    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        pytest.raises(ProtocolOssRequestUnknown),
    ):
        run_flow(session, existing_password="original-password")

    assert state["login_probes"] == 1
    assert sum(url.endswith("/create_account") for _, url, _ in transport.requests) == 1


def test_registration_lifecycle_propagates_a_lost_execution_lease(upstream):
    from core.operations.task_gateway import OperationLeaseLost
    from core.registration.protocol_oss_2.lifecycle import run_protocol_oss_2_lifecycle

    session, _, _ = upstream
    lost = OperationLeaseLost("fixture lease lost")
    with (
        patch("core.email.provider.retain_email"),
        pytest.raises(OperationLeaseLost) as raised,
    ):
        run_protocol_oss_2_lifecycle(
            "protocol2@example.test", "测试姓名", proxy=session.proxy, email_source="icloud_hide",
            _session_factory=lambda **kwargs: session,
            _flow_runner=Mock(side_effect=lost),
        )

    assert raised.value is lost


def test_a_later_unrelated_exception_after_an_empty_session_does_not_start_login(upstream):
    session, transport, _ = upstream
    state = _resume_transport(transport)

    def unrelated_error(flow, mailbox):
        flow.get_auth_session()
        raise ValueError("独立的本地错误")

    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "run_register", unrelated_error),
        pytest.raises(ProtocolOssRequestUnknown),
    ):
        run_flow(session, existing_password="original-password")

    assert state["login_probes"] == 0


def test_empty_session_after_a_caught_unknown_otp_does_not_start_another_login(upstream):
    session, transport, _ = upstream
    state = _resume_transport(transport)
    request = transport.request

    def unanswered_otp(method, url, **kwargs):
        if url.endswith("/email-otp/validate"):
            transport.requests.append((method, url, kwargs))
            raise TimeoutError("验码提交未收到回执")
        return request(method, url, **kwargs)

    transport.request = unanswered_otp

    def caught_timeout(flow, mailbox):
        try:
            flow.verify_otp("123456")
        except TimeoutError:
            pass
        flow.get_auth_session()
        raise ProtocolSessionResponseError("本轮会话不完整")

    with (
        registration_run_context(password="original-password"),
        patch.object(AuthFlow, "run_register", caught_timeout),
        pytest.raises(ProtocolOssRequestUnknown),
    ):
        run_flow(session, existing_password="original-password")

    assert state["login_probes"] == 0
    assert sum(url.endswith("/email-otp/validate") for _, url, _ in transport.requests) == 1
