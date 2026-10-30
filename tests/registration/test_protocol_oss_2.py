"""开源protocol-2 的真实上游控制流与本地接缝回归。"""
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from requests.cookies import RequestsCookieJar

from core.registration import dispatcher
from core.registration.protocol_oss import ProtocolOssRequestUnknown
from core.registration.protocol_oss_2 import run_protocol_oss_2_registration
from core.registration.protocol_oss_2.runtime import run_upstream_protocol
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow

_VENDOR_WARMUP = AuthFlow.warmup


class Transport:
    def __init__(self):
        self.cookies = RequestsCookieJar()
        self.headers = {}
        self.requests = []
        self.checkpoints = []
        self.password_error = None
        self.password_status = 200
        self.profile_status = 200
        self.profile_payload = None
        self.progress_events = []
        self.otp_payload = {"page": {"type": "about_you"}, "continue_url": "https://auth.openai.com/about-you"}
        self.closed = False

    def close(self):
        self.closed = True

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        if url.endswith("/user/register"):
            assert self.checkpoints[-1]["state"] == "started"
            if self.password_error:
                raise self.password_error
        payload = {}
        if url.endswith("/email-otp/validate"):
            payload = self.otp_payload
        elif url.endswith("/create_account") and self.profile_payload is not None:
            payload = self.profile_payload
        elif url.endswith("/create_account") or url.endswith("/password/verify"):
            payload = {"continue_url": "https://chatgpt.com/api/auth/callback/openai?code=fixture"}
        elif url.endswith("/api/auth/session"):
            payload = {"accessToken": "fixture-at", "sessionToken": "fixture-st", "user": {"id": "fixture-user"}}
        status = self.password_status if url.endswith("/user/register") else 200
        if url.endswith("/create_account"):
            status = self.profile_status
        response = Mock(status_code=status, headers={}, content=b"{}", text="{}")
        if url.endswith("/create_account"):
            response.text = json.dumps(payload)
        response.json.return_value = payload
        return response


@pytest.fixture
def upstream():
    transport = Transport()
    session = Mock(proxy="http://proxy.example:8080", protocol_traffic=None, browser_profile={})

    def auth_init(flow, url):
        flow.result.device_id = "fixture-device"
        flow._authorize_landing_url = "https://auth.openai.com/create-account/password"
        return flow.result.device_id

    with ExitStack() as stack:
        stack.enter_context(patch("core.registration.protocol_oss_2.upstream.http_client_wreq.create_http_session", return_value=transport))
        stack.enter_context(patch("core.registration.protocol_oss_2.upstream.sentinel.get_sentinel_token", return_value=("fixture", "fixture-so")))
        stack.enter_context(patch.object(AuthFlow, "check_proxy", return_value=True))
        stack.enter_context(patch.object(AuthFlow, "warmup", return_value=True))
        stack.enter_context(patch.object(AuthFlow, "get_csrf_token", return_value="fixture-csrf"))
        stack.enter_context(patch.object(AuthFlow, "get_auth_url", return_value="https://auth.openai.com/authorize"))
        stack.enter_context(patch.object(AuthFlow, "auth_oauth_init", auth_init))
        stack.enter_context(patch.object(AuthFlow, "signup", return_value=True))
        stack.enter_context(patch.object(AuthFlow, "fetch_client_auth_session_dump", return_value={}))
        stack.enter_context(patch.object(AuthFlow, "follow_redirect_chain", return_value=(None, "https://chatgpt.com/")))
        stack.enter_context(patch("core.registration.service.check_stop_requested"))
        stack.enter_context(patch("core.registration.service.report_job_progress", side_effect=lambda *event: transport.progress_events.append(event)))
        stack.enter_context(patch("core.registration.service.registration_fact_context", return_value={}))
        stack.enter_context(patch("core.registration.debug.record_protocol_exchange"))
        stack.enter_context(patch("core.registration.checkpoints.save_protocol_password_checkpoint", side_effect=lambda **kw: transport.checkpoints.append(kw)))
        wait = stack.enter_context(patch("core.email.provider.wait_for_otp", return_value="123456"))
        yield session, transport, wait


def run_flow(session, **overrides):
    kwargs = dict(
        email="protocol2@example.test", name="测试姓名", birthday="1992-06-15", otp_code=None,
        email_source="icloud_hide", existing_password=None, existing_totp_secret=None,
        options={"proxy_country": "JP"},
    )
    kwargs.update(overrides)
    return run_upstream_protocol(session, **kwargs)


def test_real_upstream_flow_saves_password_before_write_and_reuses_local_mail(upstream):
    session, transport, wait = upstream
    result = run_flow(session)
    assert [row["state"] for row in transport.checkpoints] == ["prepared", "started", "confirmed"]
    assert len({row["password"] for row in transport.checkpoints}) == 1
    assert all(row["email_source"] == "icloud_hide" for row in transport.checkpoints)
    assert wait.call_args.kwargs["email_source"] == "icloud_hide"
    assert wait.call_args.kwargs["max_wait"] == 240
    assert wait.call_args.kwargs["after_ts"] > 0
    profile = next(kw["json"] for _, url, kw in transport.requests if url.endswith("/create_account"))
    assert profile == {"name": "测试姓名", "birthdate": "1992-06-15"}
    assert result["access_token"] == "fixture-at"
    assert result["session_info"]["user"] == {"id": "fixture-user"}
    assert result["password_validated"] is True
    assert session.device_id == "fixture-device"
    assert session.browser_profile["country_code"] == "JP"
    assert transport.closed is False


@pytest.mark.parametrize("cancel_type", ["stop", "auth"])
def test_real_vendor_warmup_does_not_swallow_cancellation_as_a_network_failure(upstream, cancel_type):
    from core.auth.challenge import AuthCancelledError
    from core.registration.service import StopRequested

    session, transport, _ = upstream
    stopped = StopRequested("stopped fixture") if cancel_type == "stop" else AuthCancelledError("auth stop fixture")
    in_warmup = False

    def warmup(flow):
        nonlocal in_warmup
        in_warmup = True
        return _VENDOR_WARMUP(flow)

    def checkpoint():
        if in_warmup:
            raise stopped

    with (
        patch.object(AuthFlow, "warmup", warmup),
        patch("core.registration.service.check_stop_requested", side_effect=checkpoint),
        patch("core.registration.protocol_oss_2.upstream.auth_flow.time.sleep") as backoff,
        pytest.raises(type(stopped)) as raised,
    ):
        run_flow(session)
    assert raised.value is stopped
    assert transport.requests == []
    assert transport.closed is True
    backoff.assert_not_called()


def test_warmup_session_rebuild_checks_stop_before_opening_a_new_transport(upstream):
    from core.registration.service import StopRequested

    session, transport, _ = upstream
    stopped = StopRequested("stop during warmup retry")
    stop_during_backoff = False

    def fail_first_request(*args, **kwargs):
        transport.requests.append((args, kwargs))
        raise TimeoutError("ordinary warmup network failure")

    def checkpoint():
        if stop_during_backoff:
            raise stopped

    def backoff_stopped(seconds):
        nonlocal stop_during_backoff
        stop_during_backoff = True

    with (
        patch.object(AuthFlow, "warmup", _VENDOR_WARMUP),
        patch.object(transport, "request", side_effect=fail_first_request),
        patch("core.registration.service.check_stop_requested", side_effect=checkpoint),
        patch("core.registration.protocol_oss_2.upstream.auth_flow.time.sleep", side_effect=backoff_stopped) as backoff,
        patch("core.registration.protocol_oss_2.upstream.http_client_wreq.create_http_session", return_value=transport) as create,
        pytest.raises(StopRequested) as raised,
    ):
        run_flow(session)
    assert raised.value is stopped
    assert len(transport.requests) == 1
    assert create.call_count == 1
    assert backoff.call_args_list == [((5,), {})]
    assert transport.closed is True


@pytest.mark.parametrize("cancel_type", ["stop", "auth"])
def test_vendor_otp_retry_does_not_turn_cancellation_into_resend_or_unknown(upstream, cancel_type):
    from core.auth.challenge import AuthCancelledError
    from core.registration.service import StopRequested

    session, transport, wait = upstream
    stopped = StopRequested("mailbox stopped") if cancel_type == "stop" else AuthCancelledError("mailbox auth stopped")
    wait.side_effect = stopped
    with pytest.raises(type(stopped)) as raised:
        run_flow(session)
    assert raised.value is stopped
    assert [item["state"] for item in transport.checkpoints] == ["prepared", "started", "confirmed"]
    assert wait.call_count == 1
    assert not any("resend" in url for _, url, _ in transport.requests)
    assert transport.closed is True


def test_password_checkpoint_failure_prevents_the_remote_write(upstream):
    session, transport, _ = upstream
    with patch("core.registration.checkpoints.save_protocol_password_checkpoint", side_effect=RuntimeError("checkpoint fixture")):
        with pytest.raises(RuntimeError, match="checkpoint fixture"):
            run_flow(session)
    assert not any(url.endswith("/user/register") for _, url, _ in transport.requests)
    assert transport.closed is True


def test_password_transport_failure_retains_original_password_for_retry(upstream):
    session, transport, _ = upstream
    transport.password_error = TimeoutError("password result fixture")
    with pytest.raises(ProtocolOssRequestUnknown):
        run_flow(session)
    assert [row["state"] for row in transport.checkpoints] == ["prepared", "started"]
    assert sum(url.endswith("/user/register") for _, url, _ in transport.requests) == 1
    assert [state for stage, state, _ in transport.progress_events if stage == "password"] == ["running"]
    assert transport.closed is True


@pytest.mark.parametrize("response_confirmed", [False, True])
def test_unknown_registration_result_does_not_invent_a_checkpoint_failure_or_response(upstream, response_confirmed):
    session, transport, wait = upstream
    private_error = "private-response-body token=fixture-secret"
    if response_confirmed:
        # The password response was received; the later mailbox wait failed.
        wait.side_effect = RuntimeError(private_error)
    else:
        # The password POST was started but no response was received.
        transport.password_error = TimeoutError(private_error)
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", birthday="1992-06-15",
            proxy=session.proxy, email_source="icloud_hide",
        )
    assert result["cause_code"] == (
        "protocol_failure_evidence_missing" if response_confirmed else "protocol_auth_transport_failed"
    )
    assert result["request_unknown"] is True
    assert result["register_response_confirmed"] is response_confirmed
    assert result["registration_pending"] is True
    assert result["core_persisted"] is False
    assert result["email"] == "protocol2@example.test"
    assert result["account_id"] is None
    assert "本地写入失败" not in result["error"]
    assert "private-response-body" not in result["error"]
    assert "fixture-secret" not in result["error"]
    assert "protocol2@example.test" not in result["error"]


@pytest.mark.parametrize("status,code,category,cause_code,description", [
    (409, "invalid_state", "auth_state", "account_create_invalid_state", "资料提交时认证会话已失效"),
    (400, "user_already_exists", "email_conflict", "account_create_user_already_exists", "远端提示账号已存在，完整登录态尚未确认"),
])
def test_known_profile_rejection_preserves_safe_cause_and_unknown_account_result(
    upstream, status, code, category, cause_code, description,
):
    from core.registration.service import _registration_request_unknown_facts
    from core.operations.errors import classify_task_error

    session, transport, _ = upstream
    transport.profile_status = status
    transport.profile_payload = {"error": {
        "code": code, "type": "invalid_request_error",
        "message": "Your sign-in session is no longer valid. private@example.test token=fixture-private",
        "redirect_uri": "https://chatgpt.com/auth/login_with?callback_path=/&private=fixture-private",
    }}
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email") as retain,
        patch("core.email.provider.mark_email_permanently_unusable") as mark_unusable,
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", birthday="1992-06-15",
            proxy=session.proxy, email_source="icloud_hide",
        )

    assert result["cause_code"] == cause_code
    assert result["cause_diagnostics"] == {
        "operation": "profile_submit", "http_status": status,
        "auth_error": {"code": code, "type": "invalid_request_error", "category": category},
    }
    assert result["request_unknown"] is True
    assert result["error_code"] == "request_unknown"
    assert result["manual_reconcile"] is False
    assert result["registration_pending"] is True
    assert result["register_response_confirmed"] is True
    assert result["remote_account_state"] == "request_unknown"
    assert result["core_persisted"] is False
    assert result["account_id"] is None
    assert f"HTTP {status}" in result["error"]
    assert cause_code in result["error"]
    assert description in result["error"]
    for private in ("fixture-private", "private@example.test", "redirect_uri", "login_with", "Your sign-in session"):
        assert private not in json.dumps(result)
    assert sum(url.endswith("/create_account") for _, url, _ in transport.requests) == 1
    retain.assert_called_once()
    mark_unusable.assert_not_called()
    assert _registration_request_unknown_facts(result)["cause_code"] == cause_code
    for summary in ({}, result):
        info = classify_task_error(result["error"], task_type="registration", result_summary=summary)
        assert info["code"] == cause_code
        assert info["summary"] == description


@pytest.mark.parametrize("status,code", [
    (400, "invalid_state"), (409, "invalid_email"), (409, "private-code"),
    (409, "user_already_exists"), (400, "account_exists"),
])
def test_other_profile_rejections_do_not_invent_an_expired_session_cause(upstream, status, code):
    session, transport, _ = upstream
    transport.profile_status = status
    transport.profile_payload = {"error": {"code": code, "type": "invalid_request_error"}}
    with patch("core.auth.protocol.session.BrowserSession", return_value=session), patch("core.email.provider.retain_email"):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", birthday="1992-06-15",
            proxy=session.proxy, email_source="icloud_hide",
        )
    assert result["cause_code"] == "protocol_auth_http_failed"
    assert result["request_unknown"] is True
    assert result["cause_diagnostics"]["http_status"] == status
    assert "private-code" not in json.dumps(result)


@pytest.mark.parametrize("second_profile_attempt", [False, True])
def test_recovered_profile_error_does_not_mask_a_later_session_failure(upstream, second_profile_attempt):
    session, transport, _ = upstream
    transport.profile_status = 409
    transport.profile_payload = {"error": {"code": "invalid_state", "type": "invalid_request_error"}}

    def recover_profile_then_fail_session(flow, _mailbox):
        try:
            flow.create_account()
        except RuntimeError:
            pass
        if second_profile_attempt:
            with patch.object(AuthFlow, "create_account", side_effect=TimeoutError("profile preparation failure fixture")):
                flow.create_account()
        raise TimeoutError("later session failure fixture")

    with (
        patch.object(AuthFlow, "run_register", recover_profile_then_fail_session),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", birthday="1992-06-15",
            proxy=session.proxy, email_source="icloud_hide", existing_password="original-password",
        )
    assert result["cause_code"] == "protocol_failure_evidence_missing"
    assert result["request_unknown"] is True
    assert "cause_diagnostics" not in result


def test_confirmed_session_followed_by_core_storage_failure_is_a_local_checkpoint_failure(upstream):
    session, _, _ = upstream
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
        patch("core.registration.service.persist_registration_core", side_effect=RuntimeError("private-storage-detail")),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", birthday="1992-06-15",
            proxy=session.proxy, email_source="icloud_hide",
        )
    assert result["cause_code"] == "registration_checkpoint_failed"
    assert result["register_response_confirmed"] is True
    assert result["core_persisted"] is False
    assert result["account_id"] is None
    assert "本地写入失败" in result["error"]
    assert "private-storage-detail" not in result["error"]


@pytest.mark.parametrize("password_state, response_confirmed", [("prepared", False), ("started", False), ("confirmed", True)])
def test_unknown_resume_only_preserves_original_confirmed_password_evidence(upstream, password_state, response_confirmed):
    session, transport, wait = upstream
    transport.password_status = 400
    wait.side_effect = RuntimeError("private-mailbox-failure")
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
        patch("core.registration.service.registration_fact_context", return_value={"attempt_id": 42}),
        patch("core.storage.registration.get_private_resume_context", return_value={
            "password": "original-password", "password_state": password_state,
        }),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", birthday="1992-06-15",
            proxy=session.proxy, email_source="icloud_hide", existing_password="original-password",
        )
    assert result["request_unknown"] is True
    assert result["register_response_confirmed"] is response_confirmed
    assert result["core_persisted"] is False
    assert result["email"] == "protocol2@example.test"


def test_retry_uses_original_password_without_registering_another_password(upstream):
    session, transport, _ = upstream

    def existing(flow, *args, **kwargs):
        flow._is_existing_account = True
        flow._existing_page_type = "login_password"
        flow._existing_email_verification_mode = "existing_login_password"
        return False

    with patch.object(AuthFlow, "signup", existing):
        result = run_flow(session, existing_password="original-password", existing_totp_secret="original-totp")
    assert not transport.checkpoints
    assert not any(url.endswith("/user/register") for _, url, _ in transport.requests)
    login = next(kw["json"] for _, url, kw in transport.requests if url.endswith("/password/verify"))
    assert login["password"] == "original-password"
    assert result["registration_password"] == "original-password"
    assert result["remote_identity"] == "existing"


def test_retry_before_submission_can_register_with_the_original_password(upstream):
    session, transport, _ = upstream
    result = run_flow(session, existing_password="original-password")
    assert [row["state"] for row in transport.checkpoints] == ["started", "confirmed"]
    registration = next(kw["json"] for _, url, kw in transport.requests if url.endswith("/user/register"))
    assert registration["password"] == "original-password"
    assert result["registration_password"] == "original-password"


def test_rejected_password_is_not_presented_as_a_confirmed_credential(upstream):
    session, transport, _ = upstream
    transport.password_status = 400
    result = run_flow(session)
    assert result["access_token"] == "fixture-at"
    assert result["registration_password"] is None
    assert result["password_validated"] is False
    assert [state for stage, state, _ in transport.progress_events if stage == "password"] == ["running", "failed"]


@pytest.mark.parametrize("password_state, validated", [("prepared", False), ("started", False), ("confirmed", True)])
def test_resume_only_inherits_a_matching_confirmed_password(upstream, password_state, validated):
    session, transport, _ = upstream
    transport.password_status = 400
    transport.otp_payload = {
        "page": {"type": "external_url"},
        "continue_url": "https://chatgpt.com/api/auth/callback/openai?code=fixture",
    }
    with (
        patch("core.registration.service.registration_fact_context", return_value={"attempt_id": 42}),
        patch("core.storage.registration.get_private_resume_context", return_value={
            "password": "original-password", "password_state": password_state,
        }),
    ):
        result = run_flow(session, existing_password="original-password")
    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is validated
    assert result["registration_password"] == ("original-password" if validated else None)
    writes = [request for request in transport.requests if request[1].endswith("/user/register")]
    assert len(writes) == (0 if validated else 1)
    assert [state for stage, state, _ in transport.progress_events if stage == "password"] == (
        ["skipped"] if validated else ["running", "failed"]
    )


def test_resume_rejects_a_password_that_does_not_match_the_original_attempt(upstream):
    session, transport, _ = upstream
    with (
        patch("core.registration.service.registration_fact_context", return_value={"attempt_id": 42}),
        patch("core.storage.registration.get_private_resume_context", return_value={
            "password": "another-password", "password_state": "confirmed",
        }),
    ):
        with pytest.raises(RuntimeError, match="恢复密码不一致"):
            run_flow(session, existing_password="original-password")
    assert transport.requests == []


def test_existing_password_without_confirmation_stays_unconfirmed_on_otp_login(upstream):
    session, transport, _ = upstream

    def existing(flow, *args, **kwargs):
        flow._is_existing_account = True
        flow._existing_email_verification_mode = "passwordless_login"
        return False

    with patch.object(AuthFlow, "signup", existing):
        result = run_flow(session, existing_password="original-password")
    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert result["registration_password"] is None


def test_login_callback_after_password_rejection_does_not_create_account_again(upstream):
    session, transport, _ = upstream
    transport.password_status = 400
    transport.otp_payload = {
        "page": {"type": "external_url"},
        "continue_url": "https://chatgpt.com/api/auth/callback/openai?code=fixture",
    }
    result = run_flow(session, existing_password="original-password")
    assert not any(url.endswith("/create_account") for _, url, _ in transport.requests)
    assert result["access_token"] == "fixture-at"


def test_initial_callback_url_is_consumed_only_once():
    callback = "https://chatgpt.com/api/auth/callback/openai?code=fixture"
    flow = AuthFlow.__new__(AuthFlow)
    flow._ua = "fixture-user-agent"
    flow._navigation_headers = Mock(return_value={})
    flow._sniff_login_verifier = Mock()
    flow.session = Mock()
    flow.session.cookies = RequestsCookieJar()
    flow.session.cookies.set("__Secure-next-auth.session-token", "fixture-session")
    flow.session.get.side_effect = lambda url, **kwargs: Mock(
        status_code=302 if url == callback else 200,
        headers={"Location": "https://chatgpt.com/"} if url == callback else {},
    )
    captured, _ = flow.follow_redirect_chain(callback)
    assert flow._consume_callback_for_session(captured) is True
    callback_requests = [call.args[0] for call in flow.session.get.call_args_list if call.args[0] == callback]
    assert callback_requests == [callback]


@pytest.mark.parametrize("initial_url", [False, True])
@pytest.mark.parametrize("invalid_callback", [
    "https://example.test/api/auth/callback/openai?code=fixture",
    "https://chatgpt.com/api/auth/callback/openai?code=",
    "https://chatgpt.com/api/auth/callback/openai/other?code=fixture",
])
def test_invalid_callback_is_not_consumed_as_a_login_callback(initial_url, invalid_callback):
    start = "https://auth.openai.com/continue"
    flow = AuthFlow.__new__(AuthFlow)
    flow._ua = "fixture-user-agent"
    flow._navigation_headers = Mock(return_value={})
    flow._sniff_login_verifier = Mock()
    flow.session = Mock()
    flow.session.get.side_effect = lambda url, **kwargs: Mock(
        status_code=302 if url == start else 200,
        headers={"Location": invalid_callback} if url == start else {},
    )
    captured, _ = flow.follow_redirect_chain(invalid_callback if initial_url else start)
    assert captured == ""
    assert flow._consume_callback_for_session(captured) is False
    callback_requests = [call.args[0] for call in flow.session.get.call_args_list if call.args[0] == invalid_callback]
    assert callback_requests == [invalid_callback]


def test_supplied_otp_is_consumed_without_polling_another_mail_source(upstream):
    session, _, wait = upstream
    assert run_flow(session, otp_code="654321")["access_token"] == "fixture-at"
    wait.assert_not_called()


def test_dispatcher_preserves_protocol2_identity_and_resume_parameters():
    kwargs = dict(
        email="protocol2@example.test", name="测试姓名", birthday="1992-06-15",
        proxy="http://proxy.example:8080", otp_code=None, profile_id=None,
        existing_password="original-password", existing_totp_secret="original-totp",
        email_source="icloud_hide", registration_options={"registration_driver": "protocol_oss_2"},
    )
    with patch("core.registration.standalone.run_registration_in_context", return_value={"success": True}) as run:
        assert dispatcher.run_registration(**kwargs)["success"]
    run.assert_called_once_with(
        run_protocol_oss_2_registration, kwargs, entrypoint="protocol_cli", driver_name="protocol_oss_2",
    )


def test_core_persists_before_local_postprocessing_and_keeps_driver_identity():
    session = Mock(proxy="http://proxy.example:8080", device_id="fixture-device")
    order = []
    with (
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.validate_email_source", return_value="icloud_hide"),
        patch("core.registration.service.report_job_progress"),
        patch("core.registration.protocol_oss_2.runtime.run_upstream_protocol", return_value={
            "access_token": "fixture-at", "session_info": {"accessToken": "fixture-at"},
            "registration_password": "fixture-password", "password_validated": True,
        }),
        patch("core.registration.service.persist_registration_core", side_effect=lambda **kw: order.append(("persist", kw)) or 42),
        patch("core.registration.protocol_oss._run_local_postprocessing", side_effect=lambda **kw: order.append(("postprocess", kw)) or {"postprocess_success": True}),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", proxy=session.proxy, email_source="icloud_hide",
        )
    assert [row[0] for row in order] == ["persist", "postprocess"]
    assert order[0][1]["extra"]["registration_driver"] == "protocol_oss_2"
    assert result["registration_success"] is True
    session.close.assert_called_once_with()


def test_vendor_keeps_license_and_has_no_top_level_config_or_webui_imports():
    root = Path(__file__).resolve().parents[2] / "core/registration/protocol_oss_2/upstream"
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in (root / "LICENSE").read_text()
    for path in root.glob("*.py"):
        text = path.read_text()
        assert "from webui" not in text
        assert "from config import" not in text
        assert "sys.path.insert" not in text
        assert "sqlite3" not in text


def test_protocol2_codex_mapping_and_account_search_are_independent():
    from core.registration.service import codex_driver_for_registration
    from core.accounts.search import parse_account_search

    assert codex_driver_for_registration({"registration_driver": "protocol_oss_2", "codex_driver": "same_as_registration"}) == "protocol"
    search = parse_account_search("开源protocol-2")
    assert search[0].value == "protocol_oss_2"


def test_retry_reuses_confirmed_totp_instead_of_enrolling_again():
    from core.registration.protocol_oss import _run_local_postprocessing

    with (
        patch("core.registration.protocol_oss._upstream_config.CHATGPT_AUTH_BOOTSTRAP_ENABLED", False),
        patch("core.registration.service.report_job_progress"),
        patch("core.accounts.export.setup_2fa_protocol") as setup,
        patch("core.db.update_account_codex_status"),
        patch("core.integrations.flow_trigger.trigger_flow", return_value={"status": "skipped"}),
    ):
        result = _run_local_postprocessing(
            session=Mock(proxy="http://proxy.example:8080"), email="protocol2@example.test",
            access_token="fixture-at", account_id=42, session_info={"accessToken": "fixture-at"},
            registration_password="original-password", email_source="icloud_hide",
            existing_totp_secret="original-totp",
            options={"registration_driver": "protocol_oss_2", "twofa_enabled": True, "codex_enabled": False, "plan_check_enabled": False},
        )
    assert result["totp_secret"] == "original-totp"
    assert result["postprocess_success"] is True
    setup.assert_not_called()
