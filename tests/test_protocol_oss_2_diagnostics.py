"""开源 protocol-2 外围诊断不得改变认证请求或泄露原始数据。"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.registration.protocol_oss import ProtocolOssRequestUnknown
from core.registration.protocol_oss_2 import runtime
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
from tests.test_protocol_oss_2 import run_flow, upstream as upstream


def test_preauth_transport_cause_survives_without_debug_or_remote_write(upstream):
    session, transport, _ = upstream
    root_error = OSError("private@example.test proxy=http://private:secret@proxy.test")
    network_error = TimeoutError("token=private-token")
    network_error.__cause__ = root_error

    def run(flow, _mailbox):
        try:
            flow.session.get("https://chatgpt.com/?private=secret", timeout=7)
        except TimeoutError as exc:
            raise RuntimeError("预认证失败，原文不得进入诊断") from exc

    transport.request = Mock(side_effect=network_error)
    with patch.object(AuthFlow, "run_register", run), pytest.raises(RuntimeError) as caught:
        run_flow(session)
    assert type(caught.value) is RuntimeError
    diagnostics = caught.value.registration_diagnostics
    assert diagnostics["operation"] == "preauth"
    assert diagnostics["failure_kind"] == "transport_error"
    assert diagnostics["http_status"] is None
    assert diagnostics["exception_chain"] == ["RuntimeError", "TimeoutError", "OSError"]
    assert diagnostics["otp_received"] is False
    assert diagnostics["profile_confirmed"] is False
    assert transport.request.call_args_list == [(("GET", "https://chatgpt.com/?private=secret"), {"timeout": 7})]
    assert not any(value in json.dumps(diagnostics) for value in ("private", "secret", "token=", "http" + "://"))


def test_otp_transport_failure_records_received_code_without_changing_request_sequence(upstream):
    session, transport, _ = upstream
    request = transport.request
    failure = TimeoutError("验证码和令牌原值不得进入诊断")

    def fail_validate(method, url, **kwargs):
        if url.endswith("/email-otp/validate"):
            transport.requests.append((method, url, kwargs))
            raise failure
        return request(method, url, **kwargs)

    transport.request = fail_validate
    with pytest.raises(ProtocolOssRequestUnknown) as caught:
        run_flow(session)
    assert caught.value.__cause__ is failure
    diagnostics = caught.value.registration_diagnostics
    assert diagnostics["operation"] == "otp_validate"
    assert diagnostics["failure_kind"] == "transport_error"
    assert diagnostics["exception_type"] == "TimeoutError"
    assert diagnostics["failure_stage"] == "email_otp"
    assert diagnostics["last_confirmed_stage"] == "password"
    assert diagnostics["otp_received"] is True
    assert diagnostics["profile_confirmed"] is False
    assert [(method, url.rsplit("/", 1)[-1]) for method, url, _ in transport.requests] == [
        ("GET", "password"), ("POST", "register"), ("GET", "send"), ("POST", "validate"),
    ]


def test_profile_confirmation_moves_progress_to_session_before_transport_failure(upstream):
    session, transport, _ = upstream
    request = transport.request
    failure = ConnectionError("private-cookie")

    def fail_session(method, url, **kwargs):
        if url.endswith("/api/auth/session"):
            transport.requests.append((method, url, kwargs))
            raise failure
        return request(method, url, **kwargs)

    transport.request = fail_session
    with pytest.raises(ProtocolOssRequestUnknown) as caught:
        run_flow(session)
    diagnostics = caught.value.registration_diagnostics
    assert diagnostics["operation"] == "session"
    assert diagnostics["failure_kind"] == "transport_error"
    assert diagnostics["profile_confirmed"] is True
    assert diagnostics["failure_stage"] == "token"
    assert diagnostics["last_confirmed_stage"] == "profile"
    profile = transport.progress_events.index(("profile", "success", "上游已确认注册资料"))
    assert transport.progress_events[profile + 1] == ("token", "running", "资料已确认，正在完成回调和登录态")
    assert [(method, url.rsplit("/", 1)[-1]) for method, url, _ in transport.requests] == [
        ("GET", "password"), ("POST", "register"), ("GET", "send"), ("POST", "validate"),
        ("POST", "create_account"), ("GET", "session"),
    ]


def test_new_session_progress_failure_does_not_change_the_registration_result(upstream):
    session, transport, _ = upstream

    def report(stage, state, detail):
        if stage == "token":
            raise OSError("进度写入失败")
        transport.progress_events.append((stage, state, detail))

    with patch("core.registration_service.report_job_progress", side_effect=report):
        assert run_flow(session)["access_token"] == "fixture-at"
    assert transport.requests[-1][1] == "https://chatgpt.com/api/auth/session"


def test_final_http_rejection_keeps_only_endpoint_status_and_allowlisted_auth_error(upstream):
    session, transport, _ = upstream
    transport.profile_status = 409
    transport.profile_payload = {"error": {"code": "invalid_state", "type": "invalid_request_error", "message": "private-secret"}}
    with pytest.raises(ProtocolOssRequestUnknown) as caught:
        run_flow(session)
    diagnostics = caught.value.registration_diagnostics
    assert diagnostics["operation"] == "profile_submit"
    assert diagnostics["http_status"] == 409
    assert diagnostics["auth_error"]["code"] == "invalid_state"
    assert diagnostics["failure_kind"] == "http_error"
    assert diagnostics["profile_confirmed"] is False
    assert "private-secret" not in json.dumps(diagnostics)


def test_recovered_http_error_does_not_become_cause_of_a_later_local_failure(upstream):
    session, transport, _ = upstream
    transport.password_status = 400
    later = ValueError("later-local-private")

    def run(flow, _mailbox):
        assert flow.register_password("protocol2@example.test") is False
        raise later

    with patch.object(AuthFlow, "run_register", run), pytest.raises(ProtocolOssRequestUnknown) as caught:
        run_flow(session)
    diagnostics = caught.value.registration_diagnostics
    assert caught.value.__cause__ is later
    assert diagnostics["http_status"] is None
    assert diagnostics["auth_error"] == {}
    assert diagnostics["failure_kind"] == "unknown"
    assert diagnostics["exception_type"] == "ValueError"


def test_http_rejection_in_original_otp_send_is_bound_to_the_terminal_exception(upstream):
    session, transport, _ = upstream
    failure_response = SimpleNamespace(status_code=403, text='{"error":{"code":"access_denied","message":"private"}}')

    def run(flow, _mailbox):
        flow.session._transport = Mock(request=Mock(return_value=failure_response))
        flow.send_otp()

    with patch.object(AuthFlow, "run_register", run), pytest.raises(RuntimeError) as caught:
        run_flow(session)
    diagnostics = caught.value.registration_diagnostics
    assert diagnostics["operation"] == "otp_send"
    assert diagnostics["http_status"] == 403
    assert diagnostics["failure_kind"] == "http_error"
    assert diagnostics["auth_error"]["code"] == "access_denied"


@pytest.mark.parametrize("positional", [False, True])
def test_otp_send_preserves_original_custom_referer(upstream, positional):
    session, transport, _ = upstream
    referer = "https://auth.openai.com/email-verification"

    def run(flow, _mailbox):
        if positional:
            flow.send_otp(referer)
        else:
            flow.send_otp(referer=referer)
        flow.result.access_token = "fixture-at"
        return flow.result

    with patch.object(AuthFlow, "run_register", run):
        assert run_flow(session)["access_token"] == "fixture-at"
    assert len(transport.requests) == 1
    method, url, kwargs = transport.requests[0]
    assert (method, url) == ("GET", "https://auth.openai.com/api/accounts/email-otp/send")
    assert kwargs["headers"]["Referer"] == referer


def test_diagnostic_failure_does_not_change_original_response_or_exception(upstream):
    session, transport, _ = upstream
    with patch("core.registration.failure_diagnostics.RegistrationFailureDiagnostics.observe_request", side_effect=ValueError("observer failed")):
        assert run_flow(session)["access_token"] == "fixture-at"
    transport.password_error = TimeoutError("original-error")
    with (
        patch("core.registration.failure_diagnostics.RegistrationFailureDiagnostics.failure", side_effect=ValueError("observer failed")),
        pytest.raises(ProtocolOssRequestUnknown) as caught,
    ):
        run_flow(session)
    assert caught.value.__cause__ is transport.password_error


def test_diagnostic_sequence_read_failure_does_not_change_original_flow(upstream):
    session, _, _ = upstream

    class BrokenDiagnostics:
        @property
        def sequence(self):
            raise ValueError("诊断自身失败")

    with patch.object(runtime, "RegistrationFailureDiagnostics", BrokenDiagnostics):
        assert run_flow(session)["access_token"] == "fixture-at"


def test_unreadable_error_body_preserves_the_confirmed_http_status():
    from core.registration.failure_diagnostics import RegistrationFailureDiagnostics

    class Response:
        status_code = 403

        @property
        def text(self):
            raise ValueError("错误正文不可读")

    observer = RegistrationFailureDiagnostics()
    error = RuntimeError("原动作失败")
    observer.observe_request("POST", "https://auth.openai.com/api/accounts/email-otp/validate", response=Response())
    observer.bind_failure(error, "otp_validate", 0)
    diagnostics = observer.failure(error)
    assert diagnostics["http_status"] == 403
    assert diagnostics["failure_kind"] == "http_error"
    assert diagnostics["auth_error"] == {}


def test_action_binding_keeps_the_exact_transport_exception_operation():
    from core.registration.failure_diagnostics import RegistrationFailureDiagnostics

    observer = RegistrationFailureDiagnostics()
    error = TimeoutError("前置请求网络失败")
    observer.observe_request("POST", "https://sentinel.openai.com/backend-api/sentinel/req", error=error)
    observer.bind_failure(error, "profile_submit", 0)
    diagnostics = observer.failure(error)
    assert diagnostics["operation"] == "preauth"
    assert diagnostics["failure_kind"] == "transport_error"


@pytest.mark.parametrize("stream", [False, True])
def test_safe_observer_never_reads_untrusted_or_streaming_error_body(stream):
    from core.registration.failure_diagnostics import RegistrationFailureDiagnostics

    class Response:
        status_code = 403

        @property
        def text(self):
            raise AssertionError("流式或非可信请求不得读取正文")

        @property
        def content(self):
            raise AssertionError("流式或非可信请求不得读取正文")

    observer = RegistrationFailureDiagnostics()
    for url in (
        "https://private@auth.openai.com/api/accounts/email-otp/validate",
        "https://auth.openai.com.evil.test/api/accounts/email-otp/validate",
        *(["https://auth.openai.com/api/accounts/email-otp/validate"] if stream else []),
    ):
        response = Response()
        observer.observe_request("POST", url, response=response, error=None, stream=stream)
    assert observer.failure(RuntimeError("unrelated"))["auth_error"] == {}


def test_exception_chain_has_fixed_names_and_is_bounded_without_private_class_names():
    from core.registration.failure_diagnostics import RegistrationFailureDiagnostics

    secret_type = type("PrivateAccountToken", (RuntimeError,), {})
    error = secret_type("private@example.test")
    error.__cause__ = error
    diagnostics = RegistrationFailureDiagnostics().failure(error)
    assert diagnostics["exception_type"] == "Exception"
    assert diagnostics["exception_chain"] == ["Exception"]
    assert "Private" not in json.dumps(diagnostics)


def test_cancelled_mailbox_keeps_original_exception_and_does_not_enter_diagnostics(upstream):
    from core.registration_service import StopRequested

    session, transport, wait = upstream
    stopped = StopRequested("用户停止")
    wait.side_effect = stopped
    with pytest.raises(StopRequested) as caught:
        run_flow(session)
    assert caught.value is stopped
    assert not hasattr(stopped, "registration_diagnostics")
    assert not any("resend" in url for _, url, _ in transport.requests)
