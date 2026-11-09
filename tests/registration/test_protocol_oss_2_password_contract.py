"""协议二新注册先创建密码，原身份恢复按认证步骤继续且独立确认密码。"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.registration.protocol_oss_2.lifecycle import ProtocolOssRequestUnknown
from core.registration.protocol_oss_2 import run_protocol_oss_2_registration
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
from tests.registration.test_protocol_oss_2 import (
    _VENDOR_AUTH_INIT,
    _VENDOR_SIGNUP,
    registration_run_context,
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


def _assert_password_before_fresh_otp(transport):
    """密码创建会切换认证状态，必须重新发码后再验证并提交资料。"""
    order = [
        (method, next((suffix for suffix in (
            "/create-account/password", "/user/register", "/email-otp/send",
            "/email-otp/validate", "/create_account", "/api/auth/session",
        ) if url.endswith(suffix)), None))
        for method, url, _ in transport.requests
    ]
    expected = [
        ("GET", "/create-account/password"),
        ("POST", "/user/register"),
        ("GET", "/email-otp/send"),
        ("POST", "/email-otp/validate"),
        ("POST", "/create_account"),
    ]
    observed = [event for event in order if event[1] and event[1] != "/api/auth/session"]
    assert observed == expected
    assert order.index(expected[-1]) < order.index(("GET", "/api/auth/session"))


@pytest.mark.parametrize("html", [
    "",
    '<button data-href="/create-account/password">继续使用密码</button>',
])
def test_new_registration_without_static_links_creates_password_before_otp(upstream, html):
    session, transport, wait = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, html)),
    ):
        result = run_flow(session)
    _assert_password_before_fresh_otp(transport)
    assert [row["state"] for row in transport.checkpoints] == ["prepared", "started", "confirmed"]
    created = next(kwargs["json"]["password"] for _, url, kwargs in transport.requests if url.endswith("/user/register"))
    assert all(row["password"] == created for row in transport.checkpoints)
    assert wait.call_count == 1
    assert wait.call_args.kwargs["after_ts"] > 0
    assert result["password_validated"] is True
    assert result["registration_password"] == created
    assert result["remote_identity"] == "new"


@pytest.mark.parametrize("saved_password", [None, "original-password"])
@pytest.mark.parametrize("action_type,run_no,creates_password", [
    ("registration", 1, True),
    ("registration", 2, True),
    ("registration_resume", 1, False),
])
def test_password_presence_does_not_replace_durable_registration_intent(
    upstream, saved_password, action_type, run_no, creates_password,
):
    session, transport, _ = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE)),
        registration_run_context(action_type=action_type, run_no=run_no, password=saved_password),
    ):
        result = run_flow(session, existing_password=saved_password)
    assert _count(transport, "/user/register") == int(creates_password)
    assert result["password_validated"] is creates_password
    if creates_password:
        _assert_password_before_fresh_otp(transport)
        if saved_password:
            created = next(kwargs["json"]["password"] for _, url, kwargs in transport.requests if url.endswith("/user/register"))
            assert created == saved_password
            assert [row["state"] for row in transport.checkpoints] == ["started", "confirmed"]
    else:
        assert not any(method == "GET" and url == CREATE_PAGE for method, url, _ in transport.requests)
        assert transport.checkpoints == []
        assert result["registration_password"] == saved_password


def test_new_passwordless_signup_creates_password_then_requests_a_fresh_otp(upstream):
    session, transport, _ = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing("https://auth.openai.com/unknown")),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "email_otp_verification", "payload": {"email_verification_mode": "passwordless_signup"}},
            "continue_url": "/email-verification",
        }),
    ):
        result = run_flow(session)
    _assert_password_before_fresh_otp(transport)
    assert result["password_validated"] is True
    assert result["password_state"] == "confirmed"
    assert result["remote_identity"] == "new"


@pytest.mark.parametrize("mismatch", [
    {"attempt_id": 43},
    {"execution_id": "another-execution"},
    {"job_id": 91},
    {"action_type": "account_setup_retry"},
    {"run_no": 0},
    {"run_no": "invalid"},
    {"run_no": None},
])
def test_mismatched_run_facts_cannot_turn_a_resume_into_new_registration(upstream, mismatch):
    from core.registration.protocol_oss_2.runtime import ProtocolRegistrationContextError

    session, transport, _ = upstream
    facts = {"attempt_id": 42, "run_id": 71, "execution_id": "fixture-execution", "job_id": None}
    run = {"id": 71, "attempt_id": 42, "execution_id": "fixture-execution",
           "action_type": "registration_resume", "run_no": 1, **mismatch}
    with (
        patch("core.registration.service.registration_fact_context", return_value=facts),
        patch("core.storage.registration.get_run", return_value=run),
        pytest.raises(ProtocolRegistrationContextError) as raised,
    ):
        run_flow(session)
    assert raised.value.cause_code == "registration_checkpoint_failed"
    assert transport.requests == []
    assert transport.checkpoints == []


@pytest.mark.parametrize("facts", [
    {"attempt_id": 42},
    {"attempt_id": 42, "run_id": 71},
    {"run_id": 71, "execution_id": "fixture-execution"},
])
def test_incomplete_execution_context_does_not_fall_back_to_new_registration(upstream, facts):
    from core.registration.protocol_oss_2.runtime import ProtocolRegistrationContextError

    session, transport, _ = upstream
    with (
        patch("core.registration.service.registration_fact_context", return_value=facts),
        pytest.raises(ProtocolRegistrationContextError) as raised,
    ):
        run_flow(session)
    assert raised.value.cause_code == "registration_checkpoint_failed"
    assert transport.requests == []


def test_call_options_cannot_override_the_durable_resume_intent(upstream):
    session, transport, _ = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE)),
        registration_run_context(),
    ):
        result = run_flow(session, options={"registration_intent": "signup", "_registration_intent": "signup"})
    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert _count(transport, "/user/register") == 0


@pytest.mark.parametrize("status,code", [(400, "invalid_auth_step"), (429, "rate_limit_exceeded")])
def test_password_rejection_survives_otp_success_with_safe_http_details(upstream, status, code):
    from core.operations.errors import classify_task_error
    from core.registration.service import _persisted_result_error

    session, transport, _ = upstream
    transport.password_status = status
    transport.password_payload = {"error": {
        "code": code, "type": "invalid_request_error", "message": "private-response-body password=private-value",
    }}
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE)),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.registration.protocol_oss_2.lifecycle._upstream_config.CHATGPT_AUTH_BOOTSTRAP_ENABLED", False),
        patch("core.registration.service.persist_registration_core", return_value=42) as persist,
        patch("core.db.update_account_codex_status"),
        patch("core.integrations.flow_trigger.trigger_flow", return_value={"status": "skipped"}),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="离线测试", proxy=session.proxy, email_source="icloud_hide",
            registration_options={"twofa_enabled": False, "codex_enabled": False, "plan_check_enabled": False},
        )
    assert result["registration_success"] is True
    assert result["core_persisted"] is True
    assert result["partial_success"] is True
    assert result["cause_code"] == "registration_password_create_rejected"
    assert result["error_code"] == "registration_password_create_rejected"
    assert f"HTTP {status}" in result["error"]
    assert code in result["error"]
    assert "private" not in result["error"]
    assert "原密码尚未确认生效" not in result["error"]
    assert persist.call_args.kwargs["extra"]["account_password_state"] == "candidate"
    assert [row["state"] for row in transport.checkpoints] == ["prepared", "started"]
    assert _count(transport, "/user/register") == 1
    assert _count(transport, "/email-otp/validate") == 1
    failed_step = next(detail for stage, state, detail in transport.progress_events if stage == "password" and state == "failed")
    assert f"HTTP {status}" in failed_step and code in failed_step
    assert "private" not in failed_step
    classified = classify_task_error(result["error"], task_type="registration", result_summary=result)
    assert classified["code"] == "registration_password_create_rejected"
    persisted_error = _persisted_result_error(result, result["error"])
    restored = classify_task_error(persisted_error, task_type="registration", task_status="partial_success")
    assert restored["code"] == "registration_password_create_rejected"
    assert f"HTTP {status}" in persisted_error and code in persisted_error
    assert "private" not in persisted_error


def test_real_password_entry_retry_reuses_the_saved_candidate(upstream):
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
        registration_run_context(password=saved["password"], password_state="confirmed"),
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
        registration_run_context(password="original-password", password_state=historical_state),
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
        registration_run_context(password=saved_password),
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
        registration_run_context(password="original-password"),
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
        registration_run_context(),
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
    '<button data-href="/create-account/password">创建密码</button>',
    '<form action="/create-account/password"><button>创建密码</button></form>',
    '<script type="application/json">{"passwordPath":"/create-account/password"}</script>',
])
def test_unavailable_or_external_password_links_do_not_create_password(upstream, html):
    session, transport, _ = upstream
    _finish_with_callback(transport)
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, html)),
        registration_run_context(password="original-password"),
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
        registration_run_context(password="original-password"),
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
        registration_run_context(password="original-password"),
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
        registration_run_context(password="original-password"),
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
    expected = "identity_mismatch" if user else "registration_session_invalid_response"
    assert result["cause_code"] == expected
    assert result["core_persisted"] is False
    assert result["success"] is False
    assert not any(stage == "password" and state == "success" for stage, state, _ in transport.progress_events)
    persist.assert_not_called()
    assert classify_task_error(result["error"], task_type="registration", result_summary=result)["code"] == expected


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


@pytest.mark.parametrize("landing", [EMAIL_PAGE, "https://auth.openai.com/about-you"])
@pytest.mark.parametrize("saved_password", [None, "original-password"])
def test_otp_or_profile_landing_without_a_password_link_does_not_force_creation(upstream, landing, saved_password):
    session, transport, _ = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(landing)),
        registration_run_context(password=saved_password),
    ):
        result = run_flow(session, existing_password=saved_password)
    assert not any(method == "GET" and url == CREATE_PAGE for method, url, _ in transport.requests)
    assert _count(transport, "/user/register") == 0
    assert _count(transport, "/password/verify") == 0
    assert _count(transport, "/create_account") == 1
    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert result["password_state"] == "candidate"
    assert result["registration_password"] == saved_password
    assert transport.checkpoints == []


def test_passwordless_signup_resume_continues_otp_without_creating_password(upstream):
    session, transport, _ = upstream
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing("https://auth.openai.com/unknown")),
        registration_run_context(),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "email_otp_verification", "payload": {"email_verification_mode": "passwordless_signup"}},
            "continue_url": "/email-verification",
        }),
    ):
        result = run_flow(session)
    assert _count(transport, "/user/register") == 0
    assert _count(transport, "/email-otp/send") == 0
    assert _count(transport, "/email-otp/validate") == 1
    assert _count(transport, "/create_account") == 1
    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert result["remote_identity"] == "new"


def test_real_create_link_redirecting_to_login_verifies_original_candidate(upstream):
    session, transport, _ = upstream
    transport.navigation_redirects[CREATE_PAGE] = LOGIN_PAGE
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE, '<a href="/create-account/password">创建密码</a>')),
        registration_run_context(password="original-password"),
    ):
        result = run_flow(session, existing_password="original-password")
    assert _count(transport, "/user/register") == 0
    assert _count(transport, "/password/verify") == 1
    assert result["password_validated"] is True
    assert result["remote_identity"] == "existing"
    assert transport.checkpoints == []


@pytest.mark.parametrize("continuation", [
    {"page": {"type": "about_you"}, "continue_url": "/about-you"},
    {"page": {"type": "external_url"}, "continue_url": CALLBACK},
])
def test_original_candidate_otp_continues_profile_or_callback_without_password_creation(upstream, continuation):
    session, transport, _ = upstream
    transport.otp_payload = continuation
    with (
        patch.object(AuthFlow, "signup", _VENDOR_SIGNUP),
        patch.object(AuthFlow, "auth_oauth_init", _landing(EMAIL_PAGE)),
        registration_run_context(password="original-password"),
    ):
        result = run_flow(session, existing_password="original-password")
    assert _count(transport, "/email-otp/validate") == 1
    assert _count(transport, "/create_account") == (1 if continuation["continue_url"] == "/about-you" else 0)
    assert _count(transport, "/user/register") == 0
    assert not any(method == "GET" and url == CREATE_PAGE for method, url, _ in transport.requests)
    assert result["access_token"] == "fixture-at"
    assert result["registration_password"] == "original-password"
    assert result["password_state"] == "candidate"
    assert result["password_validated"] is False
    assert transport.checkpoints == []


@pytest.mark.parametrize("status", [400, 500])
def test_profile_rejection_preserves_original_diagnostics_without_unrelated_reauthorization(upstream, status):
    session, transport, _ = upstream
    transport.profile_status = status
    transport.profile_payload = {"error": {"code": "invalid_state", "type": "invalid_request_error"}}
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
        patch.object(AuthFlow, "_reauthorize_for_session") as recover,
    ):
        result = run_protocol_oss_2_registration(email="protocol2@example.test", name="离线测试", proxy=session.proxy, email_source="icloud_hide")
    assert result["success"] is False
    assert result["cause_diagnostics"]["http_status"] == status
    assert result["registration_diagnostics"]["operation"] == "profile_submit"
    recover.assert_not_called()


@pytest.mark.parametrize("second", [{}, {"accessToken": ""}, {"user": {"email": "protocol2@example.test"}}])
def test_later_empty_session_preserves_complete_identity_and_token(upstream, second):
    session, transport, _ = upstream
    transport.session_payloads = [
        {"accessToken": "fixture-at", "sessionToken": "fixture-st", "user": {"email": "protocol2@example.test"}},
        second,
    ]
    result = run_flow(session)
    assert _count(transport, "/api/auth/session") == 2
    assert result["access_token"] == result["session_info"]["accessToken"] == "fixture-at"
    assert result["session_info"]["user"]["email"] == "protocol2@example.test"
    assert result["password_validated"] is True


def test_snake_case_token_is_normalized_before_identity_confirmation(upstream):
    session, transport, _ = upstream
    payload = {"access_token": "fixture-at", "sessionToken": "fixture-st", "user": {"email": "protocol2@example.test"}}
    transport.session_payloads = [payload, payload]
    result = run_flow(session)
    assert result["access_token"] == result["session_info"]["accessToken"] == "fixture-at"
    assert result["password_validated"] is True


def test_complete_but_conflicting_later_session_is_never_replaced_by_old_success(upstream):
    session, transport, _ = upstream
    transport.session_payloads = [
        {"accessToken": "fixture-at", "user": {"email": "protocol2@example.test"}},
        {"accessToken": "other-at", "user": {"email": "different@example.test"}},
    ]
    with pytest.raises(ProtocolOssRequestUnknown) as raised:
        run_flow(session)
    assert raised.value.cause_code == "identity_mismatch"


def test_conflicting_token_spellings_are_not_silently_normalized(upstream):
    session, transport, _ = upstream
    transport.session_payloads = [{
        "accessToken": "fixture-at", "access_token": "other-at", "user": {"email": "protocol2@example.test"},
    }]
    with pytest.raises(ProtocolOssRequestUnknown) as raised:
        run_flow(session)
    assert raised.value.cause_code == "identity_mismatch"


def test_all_empty_session_responses_have_specific_retryable_cause(upstream):
    session, transport, _ = upstream
    transport.session_payloads = [{}, {}]
    with pytest.raises(ProtocolOssRequestUnknown) as raised:
        run_flow(session)
    assert raised.value.cause_code == "registration_session_invalid_response"


def test_protocol_login_signup_without_registration_flag_keeps_original_dispatch():
    flow = AuthFlow.__new__(AuthFlow)
    flow.result = SimpleNamespace(password="original-password")
    flow.authorize_continue = Mock(return_value={
        "page": {"type": "email_otp_verification", "payload": {"email_verification_mode": "passwordless_login"}},
    })
    result = _VENDOR_SIGNUP(flow, "fixture@example.test")
    assert result is False
    assert flow._existing_email_verification_mode == "passwordless_login"
    assert not getattr(flow, "_registration_password_required", False)
