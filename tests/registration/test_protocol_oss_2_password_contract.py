"""协议二按本轮密码入口和 Token 确认证据恢复，历史密码只作候选。"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.registration.protocol_oss_2.lifecycle import ProtocolOssRequestUnknown
from core.registration.protocol_oss_2 import run_protocol_oss_2_registration
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
from tests.registration.test_protocol_oss_2 import (
    _VENDOR_AUTH_INIT,
    _VENDOR_SIGNUP,
    run_flow,
    upstream as upstream,
)


EMAIL_PAGE = "https://auth.openai.com/email-verification"
CREATE_PAGE = "https://auth.openai.com/create-account/password"
LOGIN_PAGE = "https://auth.openai.com/log-in/password"
CALLBACK = "https://chatgpt.com/api/auth/callback/openai?code=fixture"


def _landing(page, html=""):
    def initialize(flow, _url):
        flow.result.device_id = "fixture-device"
        flow._authorize_landing_url = page
        flow._authorize_landing_html = html
        return flow.result.device_id
    return initialize


def _count(transport, suffix):
    return sum(url.endswith(suffix) for _, url, _ in transport.requests)


def _finish_with_callback(transport):
    transport.otp_payload = {"page": {"type": "external_url"}, "continue_url": CALLBACK}


def test_password_acceptance_without_token_stays_a_candidate_and_retry_creates_it_again(upstream):
    session, transport, wait = upstream
    wait.side_effect = TimeoutError("离线邮箱验证码超时")
    with pytest.raises(ProtocolOssRequestUnknown):
        run_flow(session)
    saved = transport.checkpoints[-1]
    assert saved["state"] == "confirmed"
    assert not any(stage == "password" and state == "success" for stage, state, _ in transport.progress_events)
    first_request_count = len(transport.requests)
    wait.side_effect = None
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch("core.registration.service.registration_fact_context", return_value={"attempt_id": 42}),
        patch("core.storage.registration.get_private_resume_context", return_value={
            "password": saved["password"], "password_state": "confirmed",
        }),
    ):
        result = run_flow(session, existing_password=saved["password"])
    new_requests = transport.requests[first_request_count:]
    created = [kwargs["json"]["password"] for _, url, kwargs in new_requests if url.endswith("/user/register")]
    assert created == [saved["password"]]
    assert result["password_validated"] is True
    assert result["password_state"] == "confirmed"
    assert result["registration_password"] == saved["password"]


@pytest.mark.parametrize("historical_state", ["prepared", "started", "confirmed"])
def test_otp_only_token_does_not_promote_any_historical_candidate(upstream, historical_state):
    session, transport, _ = upstream
    _finish_with_callback(transport)
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE)),
        patch("core.registration.service.registration_fact_context", return_value={"attempt_id": 42}),
        patch("core.storage.registration.get_private_resume_context", return_value={
            "password": "original-password", "password_state": historical_state,
        }),
    ):
        result = run_flow(session, existing_password="original-password")
    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert result["password_state"] == "candidate"
    assert result["registration_password"] == "original-password"
    assert _count(transport, "/user/register") == 0
    assert _count(transport, "/password/verify") == 0
    assert transport.checkpoints == []


def test_real_login_password_landing_keeps_its_page_type_and_verifies_candidate(upstream):
    session, transport, _ = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(LOGIN_PAGE)),
    ):
        result = run_flow(session, existing_password="original-password")
    assert _count(transport, "/password/verify") == 1
    assert _count(transport, "/user/register") == 0
    assert result["password_validated"] is True
    assert result["password_state"] == "confirmed"


@pytest.mark.parametrize("saved_password", [None, "original-password"])
def test_current_create_link_selects_creation_and_reuses_saved_candidate(upstream, saved_password):
    session, transport, _ = upstream
    html = '<a href="/create-account/password?source=otp">继续设置密码</a>'
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, html)),
    ):
        result = run_flow(session, existing_password=saved_password)
    created = next(kwargs["json"]["password"] for _, url, kwargs in transport.requests if url.endswith("/user/register"))
    assert created == (saved_password or transport.checkpoints[0]["password"])
    assert sum(method == "GET" and url == CREATE_PAGE + "?source=otp" for method, url, _ in transport.requests) == 1
    assert result["password_validated"] is True
    assert result["password_state"] == "confirmed"
    assert _count(transport, "/password/verify") == 0


def test_current_login_link_has_priority_when_a_candidate_exists(upstream):
    session, transport, _ = upstream
    html = '<a href="/create-account/password">创建密码</a><a href="/log-in/password">使用密码登录</a>'
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, html)),
    ):
        result = run_flow(session, existing_password="original-password")
    assert any(method == "GET" and url == LOGIN_PAGE for method, url, _ in transport.requests)
    assert _count(transport, "/password/verify") == 1
    assert _count(transport, "/user/register") == 0
    assert result["password_validated"] is True


def test_login_link_without_a_known_password_continues_otp(upstream):
    session, transport, _ = upstream
    _finish_with_callback(transport)
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, '<a href="/log-in/password">密码登录</a>')),
    ):
        result = run_flow(session)
    assert _count(transport, "/password/verify") == 0
    assert _count(transport, "/user/register") == 0
    assert result["password_validated"] is False
    assert result["registration_password"] is None


@pytest.mark.parametrize("html", [
    '<a href="https://other.example/create-account/password">创建密码</a>',
    '<a href="http://auth.openai.com/create-account/password">创建密码</a>',
    '<div hidden><a href="/create-account/password">创建密码</a></div>',
    '<a aria-disabled="true" href="/create-account/password">创建密码</a>',
    '<script>"<a href=\"/create-account/password\">创建密码</a>"</script>',
    '<template><a href="/create-account/password">创建密码</a></template>',
])
def test_unavailable_or_external_password_links_do_not_create_password(upstream, html):
    session, transport, _ = upstream
    _finish_with_callback(transport)
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, html)),
    ):
        result = run_flow(session, existing_password="original-password")
    assert _count(transport, "/user/register") == 0
    assert _count(transport, "/password/verify") == 0
    assert result["password_validated"] is False


def test_password_link_redirect_is_classified_before_sending_a_password(upstream):
    session, transport, _ = upstream
    _finish_with_callback(transport)
    transport.navigation_redirects[CREATE_PAGE] = EMAIL_PAGE
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, '<a href="/create-account/password">创建密码</a>')),
    ):
        result = run_flow(session, existing_password="original-password")
    assert _count(transport, "/user/register") == 0
    assert result["password_validated"] is False


def test_authorize_document_is_read_once_to_select_its_real_password_link(upstream):
    session, transport, _ = upstream
    authorize = "https://auth.openai.com/authorize"
    transport.navigation_redirects[authorize] = EMAIL_PAGE
    transport.navigation_html[authorize] = '<a href="/log-in/password">密码登录</a>'
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _VENDOR_AUTH_INIT),
    ):
        result = run_flow(session, existing_password="original-password")
    navigations = [kwargs for method, url, kwargs in transport.requests if method == "GET" and url == authorize]
    assert len(navigations) == 1
    assert not navigations[0].get("stream")
    assert _count(transport, "/password/verify") == 1
    assert _count(transport, "/user/register") == 0
    assert result["password_validated"] is True


@pytest.mark.parametrize("page,expected", [(LOGIN_PAGE, "login_password"), (CREATE_PAGE, "create_account_password")])
def test_signup_landing_preserves_the_password_page_type(page, expected):
    flow = AuthFlow.__new__(AuthFlow)
    flow.result = SimpleNamespace(password="original-password")
    flow.authorize_continue = Mock()
    _VENDOR_SIGNUP(flow, "fixture@example.test", landing_url=page)
    assert flow._existing_page_type == expected
    flow.authorize_continue.assert_not_called()


def test_verify_without_token_does_not_report_password_success(upstream):
    session, transport, _ = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(LOGIN_PAGE)),
        patch.object(AuthFlow, "get_auth_session", side_effect=TimeoutError("离线 Token 失败")),
        pytest.raises(ProtocolOssRequestUnknown),
    ):
        run_flow(session, existing_password="original-password")
    assert _count(transport, "/password/verify") == 1
    assert not any(stage == "login_password" and state == "success" for stage, state, _ in transport.progress_events)


@pytest.mark.parametrize("confirmed", [False, True])
def test_lifecycle_persists_candidate_separately_and_passes_confirmation_to_postprocessing(confirmed):
    session = Mock(proxy="http://proxy.example:8080", device_id="fixture-device")
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.validate_email_source", return_value="icloud_hide"),
        patch("core.registration.service.report_job_progress"),
        patch("core.registration.protocol_oss_2.runtime.run_upstream_protocol", return_value={
            "access_token": "fixture-at", "session_info": {"accessToken": "fixture-at"},
            "registration_password": "original-password", "password_validated": confirmed,
        }),
        patch("core.registration.service.persist_registration_core", return_value=42) as persist,
        patch("core.registration.protocol_oss_2.lifecycle._run_local_postprocessing", return_value={
            "postprocess_success": confirmed,
        }) as postprocess,
    ):
        result = run_protocol_oss_2_registration(
            email="fixture@example.test", name="离线测试", proxy=session.proxy, email_source="icloud_hide",
        )
    assert persist.call_args.kwargs["extra"]["account_password"] == "original-password"
    assert persist.call_args.kwargs["extra"]["account_password_state"] == ("confirmed" if confirmed else "candidate")
    assert postprocess.call_args.kwargs["password_confirmed"] is confirmed
    assert result["postprocess_success"] is confirmed


@pytest.mark.parametrize("failure,cause", [
    (TimeoutError("private-password-and-url"), "password_entry_navigation_timeout"),
    (OSError("private-password-and-url"), "password_entry_navigation_failed"),
])
def test_password_entry_failure_has_a_fixed_cause_and_preserves_candidate(upstream, failure, cause):
    from core.operations.errors import classify_task_error

    session, transport, _ = upstream
    request = transport.request

    def fail_entry(method, url, **kwargs):
        if method == "GET" and url == LOGIN_PAGE:
            raise failure
        return request(method, url, **kwargs)

    transport.request = fail_entry
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, '<a href="/log-in/password">密码登录</a>')),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="离线测试", proxy=session.proxy,
            email_source="icloud_hide", existing_password="original-password",
        )
    assert result["cause_code"] == cause
    assert result["request_unknown"] is True
    assert result["register_response_confirmed"] is False
    assert "private" not in result["error"]
    assert _count(transport, "/user/register") == 0
    assert _count(transport, "/password/verify") == 0
    assert classify_task_error(result["error"], task_type="registration", result_summary=result)["code"] == cause


def test_unknown_authentication_response_does_not_guess_a_create_request(upstream):
    from core.operations.errors import classify_task_error

    session, transport, _ = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing("https://auth.openai.com/unrecognized")),
        patch.object(AuthFlow, "authorize_continue", return_value={"page": "malformed"}),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="离线测试", proxy=session.proxy,
            email_source="icloud_hide", existing_password="original-password",
        )
    assert result["cause_code"] == "password_entry_not_offered"
    assert _count(transport, "/user/register") == 0
    assert classify_task_error(result["error"], task_type="registration", result_summary=result)["code"] == "password_entry_not_offered"


@pytest.mark.parametrize("user", [{}, {"email": "different@example.test"}])
def test_token_without_the_original_email_never_confirms_or_persists_password(upstream, user):
    from core.operations.errors import classify_task_error

    session, transport, _ = upstream
    request = transport.request

    def wrong_identity(method, url, **kwargs):
        response = request(method, url, **kwargs)
        if url.endswith("/api/auth/session"):
            response.json.return_value = {"accessToken": "fixture-at", "sessionToken": "fixture-st", "user": user}
        return response

    transport.request = wrong_identity
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
        patch("core.registration.service.persist_registration_core") as persist,
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="离线测试", proxy=session.proxy,
            email_source="icloud_hide", existing_password="original-password",
        )
    assert result["cause_code"] == "identity_mismatch"
    assert result["core_persisted"] is False
    assert result["success"] is False
    assert not any(stage == "password" and state == "success" for stage, state, _ in transport.progress_events)
    persist.assert_not_called()
    assert classify_task_error(result["error"], task_type="registration", result_summary=result)["code"] == "identity_mismatch"


@pytest.mark.parametrize("evidence_kind", ["create", "login"])
def test_new_http_session_drops_previous_password_confirmation(upstream, evidence_kind):
    from core.registration.protocol_oss_2.runtime import create_http_session

    session, _, _ = upstream

    def rebuild_after_password(flow, _mailbox):
        if evidence_kind == "create":
            flow.before_password_submit("protocol2@example.test", "original-password")
            flow.after_password_submit("protocol2@example.test", "original-password")
        else:
            flow.login_password_verify("original-password")
        flow.session = create_http_session()
        flow.get_auth_session()
        return flow.result

    with patch.object(AuthFlow, "run_register", rebuild_after_password):
        result = run_flow(session, existing_password="original-password")
    assert result["access_token"] == "fixture-at"
    assert result["registration_password"] == "original-password"
    assert result["password_state"] == "candidate"
    assert result["password_validated"] is False
