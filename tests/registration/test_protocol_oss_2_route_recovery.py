"""协议二只在当前注册动作边界换线，保留现场与未知提交事实。"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.registration.protocol_oss_2 import runtime
from core.registration.protocol_oss_2.runtime import _ObservedSession
from core.registration.protocol_oss_2.lifecycle import ProtocolOssRequestUnknown
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
from tests.registration.test_protocol_oss_2 import (
    _VENDOR_WARMUP,
    registration_run_context,
    run_flow,
    upstream as upstream,
)


OLD_PROXY = "http://route-old.example.test:8080"
NEW_PROXY = "http://route-new.example.test:8080"


class Response:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.headers = {}
        self.content = b"{}"
        self.text = "{}"
        self._payload = payload or {}

    def json(self):
        return self._payload

    def close(self):
        pass


class Transport:
    """仅替代网络边界，保留真实请求封装和换线决策。"""

    def __init__(self, replies):
        self.replies = iter(replies)
        self.proxies = {"https": OLD_PROXY}
        self.requests = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, dict(kwargs), dict(self.proxies)))
        reply = next(self.replies)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    def close(self):
        self.closed = True

    def pause_for_route_recovery(self):
        self.close()


@pytest.fixture(autouse=True)
def no_external_observers():
    with (
        patch("core.registration.service.check_stop_requested"),
        patch("core.registration.debug.record_protocol_exchange"),
    ):
        yield


def _scope(monkeypatch, callback):
    monkeypatch.setattr(runtime, "current_route_recovery", lambda: callback, raising=False)


@pytest.mark.parametrize("first", [Response(403), TimeoutError("当前线路超时")])
def test_current_safe_request_replays_on_the_new_route_without_restarting_signup(monkeypatch, first):
    """漏掉原栈重放或继续使用旧代理都会使本测试失败。"""
    transport = Transport([first, Response(200)])
    parent = SimpleNamespace(proxy=OLD_PROXY, protocol_traffic=None)
    context = {"proxy": OLD_PROXY, "capture": None, "parent_session": parent}
    observed = []

    def recover(failure, proxy_url):
        assert transport.closed, "交还旧租约前必须停止旧连接"
        observed.append((failure.operation, failure.http_status, failure.replay_safe, proxy_url))
        return SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease")

    _scope(monkeypatch, recover)
    result = _ObservedSession(transport, context).get("https://chatgpt.com/api/auth/csrf", timeout=7)

    assert result.status_code == 200
    assert observed == [("preauth", 403 if isinstance(first, Response) else None, True, OLD_PROXY)]
    assert [row[1] for row in transport.requests] == ["https://chatgpt.com/api/auth/csrf"] * 2
    assert [row[3]["https"] for row in transport.requests] == [OLD_PROXY, NEW_PROXY]
    assert transport.requests[0][2] == transport.requests[1][2] == {"timeout": 7}
    assert parent.proxy == context["proxy"] == NEW_PROXY


def test_noncritical_403_does_not_consume_registration_route_budget(monkeypatch):
    transport = Transport([Response(403)])
    observed = []
    _scope(monkeypatch, lambda *args: observed.append(args))

    result = _ObservedSession(transport, {"proxy": OLD_PROXY}).post("https://chatgpt.com/backend-api/telemetry")

    assert result.status_code == 403
    assert observed == []
    assert len(transport.requests) == 1


def test_unrelated_post_transport_error_does_not_invent_an_unknown_identity_write(monkeypatch):
    transport = Transport([TimeoutError("旁路超时")])
    context = {"proxy": OLD_PROXY}
    _scope(monkeypatch, None)
    with pytest.raises(TimeoutError):
        _ObservedSession(transport, context).post("https://chatgpt.com/backend-api/telemetry")
    assert context.get("write_unknown") is not True


@pytest.mark.parametrize("path", ["/user/register", "/create_account"])
def test_explicit_403_rejection_replays_the_same_creation_payload_without_inventing_unknown(monkeypatch, path):
    transport = Transport([Response(403), Response(200)])
    context = {"proxy": OLD_PROXY}
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    result = _ObservedSession(transport, context).post(
        "https://auth.openai.com/api/accounts" + path, json={"original": "same-candidate"}, timeout=11,
    )
    assert result.status_code == 200
    assert [row[2] for row in transport.requests] == [
        {"json": {"original": "same-candidate"}, "timeout": 11},
        {"json": {"original": "same-candidate"}, "timeout": 11},
    ]
    assert not context.get("write_unknown")


def test_callback_403_uses_read_only_session_recovery_without_consuming_the_code_again(upstream, monkeypatch):
    session, transport, _ = upstream
    callback = "https://chatgpt.com/api/auth/callback/openai?code=once"
    request = transport.request

    def reject_callback(method, url, **kwargs):
        if url == callback:
            transport.requests.append((method, url, kwargs))
            return Response(403)
        return request(method, url, **kwargs)

    transport.request = reject_callback
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with patch.object(AuthFlow, "run_register", lambda flow, mailbox: flow.session.get(callback)):
        result = run_flow(session, existing_password="original")
    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert [(method, url) for method, url, _ in transport.requests] == [
        ("GET", callback), ("GET", "https://chatgpt.com/api/auth/session"),
    ]


def test_recovered_callback_403_does_not_override_a_later_identity_verification(upstream, monkeypatch):
    from core.operations.errors import classify_task_error
    from core.registration.protocol_oss_2 import run_protocol_oss_2_registration

    session, transport, _ = upstream
    callback = "https://chatgpt.com/api/auth/callback/openai?code=once"
    request = transport.request
    facts = []
    transport.session_payloads = [{}]
    transport.profile_payload = {
        "page": {"type": "identity_verification", "payload": {}},
        "continue_url": "https://auth.openai.com/verify-your-identity",
        "method": "GET",
    }

    def reject_callback(method, url, **kwargs):
        if url == callback:
            transport.requests.append((method, url, kwargs))
            return Response(403)
        return request(method, url, **kwargs)

    transport.request = reject_callback
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with (
        registration_run_context(action_type="registration_resume", password="original-password"),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
        patch("core.email.provider.mark_email_permanently_unusable"),
        patch("core.registration.service.persist_registration_core") as persist,
        patch("core.storage.registration.record_submission_fact", side_effect=lambda *args, **kw: facts.append(kw)),
        patch.object(AuthFlow, "run_register", lambda flow, mailbox: flow.session.get(callback)),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "email_otp_verification"}, "continue_url": "/email-verification",
        }),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", proxy=session.proxy,
            email_source="icloud_hide", existing_password="original-password",
        )

    assert result["cause_code"] == "registration_identity_verification_required"
    assert result["request_unknown"] is True
    assert "route_failure" not in result
    assert sum(url == callback for _, url, _ in transport.requests) == 1
    assert sum(url.endswith("/create_account") for _, url, _ in transport.requests) == 1
    assert [(fact["kind"], fact["phase"], fact["result"]) for fact in facts] == [
        ("callback", "unknown", "unknown"),
    ]
    classified = classify_task_error(result["error"], task_type="registration", result_summary=result)
    assert classified["cause_code"] == "registration_identity_verification_required"
    assert classified["display_code"] == "AUTH-REG-IDENTITY-001"
    persist.assert_not_called()


@pytest.mark.parametrize("method,url", [
    ("POST", "https://auth.openai.com/api/accounts/user/register"),
    ("POST", "https://auth.openai.com/api/accounts/create_account"),
    ("GET", "https://chatgpt.com/api/auth/callback/openai?code=once"),
])
def test_unanswered_mutation_and_one_time_callback_are_not_replayed_directly(monkeypatch, method, url):
    transport = Transport([TimeoutError("未取得响应"), Response(200)])
    observed = []

    def recover(failure, proxy_url):
        observed.append((failure.operation, failure.replay_safe))
        return SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease")

    _scope(monkeypatch, recover)
    context = {"proxy": OLD_PROXY}
    try:
        _ObservedSession(transport, context).request(method, url)
    except BaseException:
        pass

    assert len(observed) == 1
    assert observed[0][1] is False
    assert len(transport.requests) == 1
    assert context["proxy"] == NEW_PROXY
    assert bool(context.get("write_unknown")) is (method == "POST")


def test_route_budget_exhaustion_cannot_be_swallowed_by_vendor_warmup(monkeypatch):
    from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow

    transport = Transport([Response(403)] * 20)
    observed = []
    _scope(monkeypatch, lambda failure, proxy: observed.append(failure))
    flow = AuthFlow.__new__(AuthFlow)
    flow._env_overrides = {"WARMUP_ATTEMPTS": "20"}
    flow._navigation_headers = lambda: {}
    flow.session = _ObservedSession(transport, {"proxy": OLD_PROXY})
    flow._next_proxy = lambda: OLD_PROXY
    flow._impersonate_candidates = ["chrome152"]
    flow._impersonate_idx = 0
    flow._ua = "fixture"
    flow._tls_fp = flow._akamai_fp = None
    with patch("core.registration.protocol_oss_2.upstream.auth_flow.time.sleep"):
        try:
            flow.warmup()
        except BaseException:
            pass

    assert len(observed) == 1
    assert len(transport.requests) == 1


def test_route_callback_cancellation_is_never_retried_by_vendor(monkeypatch):
    from core.registration.service import StopRequested

    transport = Transport([Response(403), Response(200)])
    stopped = StopRequested("换线时停止")

    def recover(*_args):
        raise stopped

    _scope(monkeypatch, recover)
    try:
        _ObservedSession(transport, {"proxy": OLD_PROXY}).get("https://chatgpt.com/api/auth/csrf")
    except BaseException as exc:
        reason = getattr(exc, "reason", exc)
        assert reason is stopped
    else:
        pytest.fail("换线回调中的取消必须终止当前认证栈")
    assert len(transport.requests) == 1


def test_real_wreq_route_rebuild_retains_full_native_multidomain_cookie_jar():
    """只保留扁平Cookie镜像会丢失同名不同域和path属性，本测试会失败。"""
    wreq = pytest.importorskip("wreq")
    from core.registration.protocol_oss_2.upstream.http_client_wreq import WreqSession

    transport = WreqSession(proxy=OLD_PROXY, impersonate="chrome152", user_agent="same-profile")
    jar = transport._jar()
    fixtures = [
        ("same", "chat", ".chatgpt.com", "/", "https://chatgpt.com/"),
        ("same", "auth", "auth.openai.com", "/api", "https://auth.openai.com/api/"),
        ("same", "deep", "auth.openai.com", "/api/accounts", "https://auth.openai.com/api/accounts/"),
    ]
    for name, value, domain, path, origin in fixtures:
        jar.add(wreq.Cookie(
            name=name, value=value, domain=domain, path=path,
            secure=True, http_only=True, same_site=wreq.SameSite.Strict,
            expires=datetime(2030, 1, 1, tzinfo=timezone.utc),
        ), origin)

    def snapshot():
        return sorted((c.name, c.value, c.domain, c.path, c.secure, c.http_only, c.same_site_strict, c.expires)
                      for c in transport._jar().get_all())

    before = snapshot()
    profile = (transport._emulation, transport._impersonate, dict(transport.headers))
    try:
        transport.pause_for_route_recovery()
        transport.proxies = {"https": NEW_PROXY}
        assert len(before) == 3
        assert snapshot() == before
        assert (transport._emulation, transport._impersonate, dict(transport.headers)) == profile
        assert transport.proxies["https"] == NEW_PROXY
    finally:
        transport.close()


def test_same_proxy_address_after_reallocation_still_rebuilds_a_closed_native_client():
    pytest.importorskip("wreq")
    from core.registration.protocol_oss_2.upstream.http_client_wreq import WreqSession

    transport = WreqSession(proxy=OLD_PROXY)
    try:
        previous = transport._client
        transport.pause_for_route_recovery()
        transport.proxies = {"https": OLD_PROXY}
        assert transport._client is not previous
    finally:
        transport.close()


def test_old_client_close_failure_never_hands_the_lease_back_to_business(monkeypatch):
    pytest.importorskip("wreq")
    from core.registration.protocol_oss_2.upstream.http_client_wreq import WreqSession

    transport = WreqSession(proxy=OLD_PROXY)
    transport.close()
    closed = []
    callbacks = []

    def refuse_close():
        closed.append(True)
        raise RuntimeError("底层旧连接关闭失败")

    transport._client = SimpleNamespace(
        get=lambda *a, **kw: SimpleNamespace(status=403, cookies=[], headers={}),
        close=refuse_close, cookie_jar=None,
    )
    _scope(monkeypatch, lambda *_args: callbacks.append(True))
    try:
        with pytest.raises(runtime._VendorRouteRecovery) as caught:
            _ObservedSession(transport, {"proxy": OLD_PROXY}).get("https://chatgpt.com/api/auth/csrf")
        assert caught.value.stage == "close_previous_connection"
        assert callbacks == []
        assert closed == [True]
        assert transport._route_suspended is False
    finally:
        transport.close()


@pytest.mark.parametrize("stage", ["preauth", "password", "profile"])
def test_old_connection_close_failure_is_classified_and_does_not_rotate_the_registration_lease(upstream, monkeypatch, stage):
    from core.registration.protocol_oss_2 import run_protocol_oss_2_registration

    session, transport, _ = upstream
    callbacks = []

    def refuse_close():
        raise RuntimeError("旧连接关闭失败")

    transport.pause_for_route_recovery = refuse_close
    request = transport.request

    def reject(method, url, **kwargs):
        suffix = {"preauth": "/api/auth/csrf", "password": "/user/register", "profile": "/create_account"}[stage]
        return Response(403) if url.endswith(suffix) else request(method, url, **kwargs)

    transport.request = reject
    _scope(monkeypatch, lambda *_args: callbacks.append(True))
    with (
        patch.object(AuthFlow, "warmup", _VENDOR_WARMUP if stage == "preauth" else lambda self: True),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", proxy=session.proxy, email_source="icloud_hide",
        )
    assert callbacks == []
    assert result["cause_code"] == "registration_route_close_failed"
    assert result["route_failure"]["http_status"] == 403
    assert session.proxy == "http://proxy.example:8080"


def test_route_replay_splits_old_and_new_lease_traffic(monkeypatch):
    from core.network.protocol_traffic import ProtocolTrafficCapture, correlation_context

    old = ProtocolTrafficCapture({"proxy_lease_id": "old-lease", "route_attempt_no": 2})
    parent = SimpleNamespace(proxy=OLD_PROXY, protocol_traffic=old)
    context = {"proxy": OLD_PROXY, "capture": old, "parent_session": parent}
    transport = Transport([Response(403), Response(200)])
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with (
        patch("core.browser.traffic.persist_summary"),
        correlation_context(route_attempt_no=3),
    ):
        _ObservedSession(transport, context).get("https://chatgpt.com/api/auth/csrf")

    assert old.correlation == {"proxy_lease_id": "old-lease", "route_attempt_no": 2}
    assert old.snapshot()["request_count"] == 1
    assert old.snapshot()["failed_count"] == 1
    assert parent.protocol_traffic is context["capture"]
    assert parent.protocol_traffic is not old
    assert parent.protocol_traffic.correlation == {"proxy_lease_id": "new-lease", "route_attempt_no": 3}
    assert parent.protocol_traffic.snapshot()["request_count"] == 1
    assert parent.protocol_traffic.snapshot()["failed_count"] == 0


@pytest.mark.parametrize("operation", ["password_create", "profile_submit"])
def test_unknown_identity_recovers_with_original_candidate_and_preserves_unknown_fact(upstream, monkeypatch, operation):
    session, transport, _ = upstream
    request = transport.request
    path = "/user/register" if operation == "password_create" else "/create_account"
    failed = False
    facts = []

    def fail_once(method, url, **kwargs):
        nonlocal failed
        if url.endswith(path) and not failed:
            failed = True
            transport.requests.append((method, url, kwargs))
            raise TimeoutError("创建请求已派发但未取得响应")
        return request(method, url, **kwargs)

    transport.request = fail_once
    transport.session_payloads = [{}]
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with (
        registration_run_context(action_type="registration"),
        patch("core.storage.registration.record_submission_fact", side_effect=lambda *args, **kw: facts.append(kw)),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "login_password"}, "continue_url": "/log-in/password",
        }),
    ):
        result = run_flow(session)

    assert sum(url.endswith(path) for _, url, _ in transport.requests) == 1
    created = next(kw["json"]["password"] for _, url, kw in transport.requests if url.endswith("/user/register"))
    verified = next(kw["json"]["password"] for _, url, kw in transport.requests if url.endswith("/password/verify"))
    assert created == verified == result["registration_password"]
    assert result["password_validated"] is True
    assert result["remote_identity"] == "existing"
    assert result["route_unknown_operations"] == [operation]
    assert [(fact["kind"], fact["phase"], fact["result"]) for fact in facts] == [
        ("password" if operation == "password_create" else "profile", "unknown", "unknown"),
    ]
    assert session.proxy == NEW_PROXY


@pytest.mark.parametrize("unknown_operation,profile_count,succeeds", [
    ("password_create", 1, True),
    ("profile_submit", 1, False),
])
def test_login_about_you_only_completes_profile_when_no_profile_submission_is_unknown(
    upstream, monkeypatch, unknown_operation, profile_count, succeeds,
):
    session, transport, _ = upstream
    request = transport.request
    failing_path = "/user/register" if unknown_operation == "password_create" else "/create_account"
    failed = False

    def fail_once(method, url, **kwargs):
        nonlocal failed
        if url.endswith(failing_path) and not failed:
            failed = True
            transport.requests.append((method, url, kwargs))
            raise TimeoutError("写入无响应")
        return request(method, url, **kwargs)

    transport.request = fail_once
    transport.session_payloads = [{}]
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with (
        registration_run_context(action_type="registration"),
        patch("core.storage.registration.record_submission_fact"),
        patch.object(AuthFlow, "authorize_continue", return_value={
            "page": {"type": "email_otp_verification"}, "continue_url": "/email-verification",
        }),
    ):
        if succeeds:
            result = run_flow(session)
            assert result["access_token"] == "fixture-at"
            assert result["password_validated"] is False
        else:
            with pytest.raises(ProtocolOssRequestUnknown):
                run_flow(session)
    assert sum(url.endswith("/create_account") for _, url, _ in transport.requests) == profile_count
    assert sum(url.endswith("/user/register") for _, url, _ in transport.requests) == 1


def test_unknown_identity_login_never_falls_back_to_signup_or_a_second_password_create(upstream, monkeypatch):
    session, transport, _ = upstream
    transport.password_error = TimeoutError("创建结果未知")
    transport.session_payloads = [{}]
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with (
        registration_run_context(action_type="registration"),
        patch("core.storage.registration.record_submission_fact"),
        patch.object(AuthFlow, "authorize_continue", return_value={"page": {"type": "signup"}}),
        pytest.raises(ProtocolOssRequestUnknown),
    ):
        run_flow(session)
    assert sum(url.endswith("/user/register") for _, url, _ in transport.requests) == 1
    assert not any(url.endswith("/create_account") for _, url, _ in transport.requests)


@pytest.mark.parametrize("operation", ["password_create", "profile_submit"])
def test_failed_identity_login_keeps_original_unknown_action_and_current_run_fact(upstream, monkeypatch, operation):
    from core.registration.protocol_oss_2 import run_protocol_oss_2_registration

    session, transport, _ = upstream
    request = transport.request
    path = "/user/register" if operation == "password_create" else "/create_account"
    saved = []

    def fail_identity(method, url, **kwargs):
        if url.endswith(path):
            transport.requests.append((method, url, kwargs))
            raise TimeoutError("原创建请求未取得响应")
        return request(method, url, **kwargs)

    transport.request = fail_identity
    transport.session_payloads = [{}]
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with (
        registration_run_context(action_type="registration"),
        patch("core.storage.registration.record_submission_fact", side_effect=lambda *a, **kw: saved.append(kw)),
        patch.object(AuthFlow, "authorize_continue", side_effect=RuntimeError("原身份登录恢复失败")),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="测试姓名", proxy=session.proxy, email_source="icloud_hide",
        )
    assert result["success"] is False
    assert result["request_unknown"] is True
    assert "route_failure" not in result
    assert saved[0]["run_id"] == 71
    assert saved[0]["execution_id"] == "fixture-execution"
    assert saved[0]["phase"] == "unknown"
    assert len(saved) == 1
    assert sum(url.endswith(path) for _, url, _ in transport.requests) == 1
    assert result["registration_diagnostics"]["failure_kind"] == "transport_error"
    assert result["registration_diagnostics"]["operation"] == (
        "password_submit" if operation == "password_create" else "profile_submit"
    )


def test_vendor_route_exhaustion_returns_a_classified_error_to_the_registration_boundary(upstream, monkeypatch):
    session, transport, _ = upstream
    transport.request = lambda method, url, **kw: (
        transport.requests.append((method, url, kw)) or Response(403)
    )
    _scope(monkeypatch, lambda *_args: None)
    with (
        patch.object(AuthFlow, "warmup", _VENDOR_WARMUP),
        pytest.raises(RuntimeError) as caught,
    ):
        run_flow(session)
    assert caught.value.route_failure.http_status == 403
    assert caught.value.registration_diagnostics["http_status"] == 403
    assert len(transport.requests) == 1


@pytest.mark.parametrize("method,url,expected_attempts", [
    ("post", "https://auth.openai.com/api/accounts/user/register", 1),
    ("post", "https://auth.openai.com/api/accounts/create_account", 1),
    ("get", "https://chatgpt.com/api/auth/callback/openai?code=once", 1),
    ("get", "https://chatgpt.com/api/auth/csrf", 3),
])
def test_bounded_transport_retries_do_not_repeat_an_unanswered_identity_mutation(method, url, expected_attempts):
    pytest.importorskip("wreq")
    from core.registration.protocol_oss_2.upstream.http_client_wreq import WreqSession

    transport = WreqSession(proxy=OLD_PROXY, retries=2)
    transport.close()
    attempts = []

    def send(*_args, **_kwargs):
        attempts.append(url)
        raise TimeoutError("请求未取得响应")

    transport._client = SimpleNamespace(get=send, post=send, close=lambda: None)
    try:
        with (
            patch("core.registration.protocol_oss_2.upstream.http_client_wreq.time.sleep"),
            pytest.raises(TimeoutError),
        ):
            transport.request(method, url)
        assert len(attempts) == expected_attempts
    finally:
        transport.close()


@pytest.mark.parametrize("path", [
    "/backend-api/accounts/mfa/enroll",
    "/backend-api/accounts/mfa/user/activate_enrollment",
])
def test_only_registration_twofa_scope_replays_403_and_restores_disabled_recovery(monkeypatch, path):
    transport = Transport([Response(403), Response(200), Response(403)])
    parent = SimpleNamespace(proxy=OLD_PROXY, protocol_traffic=None)
    context = {
        "proxy": OLD_PROXY, "capture": None, "parent_session": parent,
        "route_recovery_enabled": False, "observing": False,
    }
    parent.session = _ObservedSession(transport, context)
    observed = []

    def recover(failure, proxy):
        observed.append((failure.operation, proxy))
        return SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease")

    _scope(monkeypatch, recover)
    with runtime.registration_twofa_route_recovery(parent):
        result = parent.session.post("https://chatgpt.com" + path)
    assert result.status_code == 200
    assert len(observed) == 1
    assert observed[0][0] == ("twofa_enroll" if path.endswith("enroll") else "twofa_activate")
    assert context["route_recovery_enabled"] is False
    assert context["observing"] is False
    assert parent.protocol_traffic is context["capture"]
    assert parent.session.get("https://chatgpt.com/api/auth/csrf").status_code == 403
    assert len(observed) == 1


@pytest.mark.parametrize("enabled", [True, False])
def test_unanswered_registration_twofa_activation_reads_state_without_confirming_candidate(monkeypatch, enabled):
    transport = Transport([TimeoutError("激活请求结果未知"), Response(200, {
        "mfa_enabled": enabled, "mfa_enabled_v2": enabled,
    })])
    parent = SimpleNamespace(proxy=OLD_PROXY, protocol_traffic=None)
    context = {
        "proxy": OLD_PROXY, "capture": None, "parent_session": parent,
        "route_recovery_enabled": False, "observing": False,
    }
    parent.session = _ObservedSession(transport, context)
    parent.get = parent.session.get
    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with pytest.raises(RuntimeError) as caught:
        with runtime.registration_twofa_route_recovery(parent, access_token="fixture-access"):
            parent.session.post("https://chatgpt.com/backend-api/accounts/mfa/user/activate_enrollment")
    assert [(method, url) for method, url, _, _ in transport.requests] == [
        ("POST", "https://chatgpt.com/backend-api/accounts/mfa/user/activate_enrollment"),
        ("GET", "https://chatgpt.com/backend-api/accounts/mfa_info"),
    ]
    assert caught.value.twofa_recovery == {
        "operation": "twofa_activate", "http_status": 200,
        "state": "enabled_candidate_unverified" if enabled else "not_enabled",
    }
    assert parent.proxy == NEW_PROXY
    assert context["route_recovery_enabled"] is False


def test_twofa_read_only_recovery_never_promotes_the_saved_pending_secret(monkeypatch):
    from core.registration.protocol_oss_2.lifecycle import _run_local_postprocessing

    transport = Transport([TimeoutError("激活请求结果未知"), Response(200, {
        "mfa_enabled": True, "mfa_enabled_v2": True,
    })])
    parent = SimpleNamespace(proxy=OLD_PROXY, protocol_traffic=None)
    context = {
        "proxy": OLD_PROXY, "capture": None, "parent_session": parent,
        "route_recovery_enabled": False, "observing": False,
    }
    parent.session = _ObservedSession(transport, context)
    parent.get = parent.session.get
    saved = []

    def setup(session, _token, *, on_secret):
        on_secret("candidate-secret")
        session.session.post("https://chatgpt.com/backend-api/accounts/mfa/user/activate_enrollment")
        return "candidate-secret"

    _scope(monkeypatch, lambda *_args: SimpleNamespace(proxy_url=NEW_PROXY, lease_id="new-lease"))
    with (
        patch("core.registration.protocol_oss_2.lifecycle._upstream_config.CHATGPT_AUTH_BOOTSTRAP_ENABLED", False),
        patch("config.twofa.get_twofa_driver_for_options", return_value="protocol"),
        patch("core.accounts.export.setup_2fa_protocol", side_effect=setup),
        patch("core.registration.checkpoints.save_protocol_totp_checkpoint", side_effect=lambda **kw: saved.append(kw)),
        patch("core.registration.service.report_job_progress"),
        patch("core.db.update_account_codex_status"),
        patch("core.integrations.flow_trigger.trigger_flow", return_value={"status": "skipped"}),
    ):
        result = _run_local_postprocessing(
            session=parent, email="protocol2@example.test", access_token="fixture-access",
            account_id=42, session_info={}, registration_password="original",
            email_source="icloud_hide", password_confirmed=True,
            options={"password_enabled": True, "twofa_enabled": True, "codex_enabled": False, "plan_check_enabled": False},
        )
    assert result["postprocess_success"] is False
    assert result["totp_secret"] is None
    assert [row["confirmed"] for row in saved] == [False]
    assert result["twofa_route_recovery"]["state"] == "enabled_candidate_unverified"
    assert "候选密钥尚未核验" in result["error"]
    assert result["cause_code"] == "twofa_setup_failed"


def test_lifecycle_preserves_the_current_route_failure_as_plain_json_metadata(upstream, monkeypatch):
    from core.registration.protocol_oss_2 import run_protocol_oss_2_registration

    session, transport, _ = upstream
    transport.request = lambda method, url, **kw: (
        transport.requests.append((method, url, kw)) or Response(403)
    )
    _scope(monkeypatch, lambda *_args: None)
    with (
        patch.object(AuthFlow, "warmup", _VENDOR_WARMUP),
        patch("core.auth.protocol.session.BrowserSession", return_value=session),
        patch("core.email.provider.retain_email"),
    ):
        result = run_protocol_oss_2_registration(
            email="protocol2@example.test", name="离线测试", proxy=session.proxy,
            email_source="icloud_hide",
        )
    assert result["route_failure"] == {
        "operation": "preauth", "http_status": 403, "transport_kind": "",
        "response_received": True, "replay_safe": True,
    }
    assert result["cause_code"] == "protocol_auth_http_failed"
