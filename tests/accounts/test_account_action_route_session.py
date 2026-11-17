"""独立账号动作在原调用栈换线，未知写入不得被上层重试再次派发。"""
from http.cookiejar import Cookie, CookieJar
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.accounts.password_setup import route_recovery as recovery
from core.operations.runtime import OperationCancelled


def response(status=200):
    return SimpleNamespace(status_code=status, close=Mock(), json=lambda: {})


def session(*outcomes):
    jar = CookieJar()
    for domain, path in (("chatgpt.com", "/"), ("auth.openai.com", "/"), ("auth.openai.com", "/api")):
        jar.set_cookie(Cookie(0, "same-name", domain + path, None, False, domain, True, False,
                              path, True, True, None, True, None, None, {}, False))
    transport = SimpleNamespace(cookies=jar, timeout=21, close=Mock())
    value = SimpleNamespace(
        session=transport, proxy="http://old.example:8080", device_id="same-device",
        browser_profile={"screen_width": 1920}, chrome_identity={"impersonate": "chrome"},
        blocked_until=9876.0, blocked_reason="旧线路已冷却", protocol_traffic=None,
        get=Mock(side_effect=outcomes), post=Mock(side_effect=outcomes),
    )
    return value


def test_authorize_403_retries_only_current_get_on_new_transport_with_original_identity(monkeypatch):
    old, ok = response(403), response()
    current = session(old, ok)
    prior_transport = current.session
    replacement = SimpleNamespace(cookies=None, proxies={}, timeout=None, close=Mock())
    factory = Mock(return_value=replacement)
    monkeypatch.setattr(recovery, "Session", factory)
    recover = Mock(return_value="http://new.example:8080")
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    actual = client.get("https://auth.openai.com/oauth/authorize?state=private")
    assert actual is ok
    assert current.get.call_count == 2
    assert recover.call_args.args[0].http_status == 403
    assert recover.call_args.args[0].operation == "authorize"
    assert recover.call_args.args[1] == "http://old.example:8080"
    assert current.device_id == "same-device"
    assert current.browser_profile == {"screen_width": 1920}
    assert sorted((c.domain, c.path, c.value) for c in replacement.cookies) == sorted(
        (c.domain, c.path, c.value) for c in prior_transport.cookies
    )
    assert current.blocked_until == 0
    assert replacement.proxies == {"http": "http://new.example:8080", "https": "http://new.example:8080"}
    prior_transport.close.assert_called_once()
    old.close.assert_called_once()


@pytest.mark.parametrize("path", [
    "/api/accounts/email-otp/validate", "/api/accounts/passwordless/send-otp",
    "/backend-api/accounts/mfa/enroll", "/backend-api/accounts/mfa/activate",
    "/api/accounts/password/add",
])
def test_unknown_post_latches_before_upper_retry_and_never_replays(path):
    host = "chatgpt.com" if path.startswith("/backend") else "auth.openai.com"
    current = session(TimeoutError("请求超时，可能已送达"))
    recover = Mock(return_value="http://new.example:8080")
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    for _ in range(2):
        with pytest.raises(recovery.AccountActionRouteHalt) as caught:
            client.post(f"https://{host}{path}", data="private")
        assert caught.value.error.code == "account_action_request_unknown"
    assert current.post.call_count == 1
    recover.assert_not_called()


@pytest.mark.parametrize("status", [408, 500, 502, 503])
@pytest.mark.parametrize("path", ["/backend-api/accounts/mfa/enroll", "/api/accounts/email-otp/validate"])
def test_unconfirmed_http_write_response_is_not_replayed_by_upper_retry(status, path):
    host = "chatgpt.com" if path.startswith("/backend") else "auth.openai.com"
    current = session(response(status))
    recover = Mock()
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    for _ in range(2):
        with pytest.raises(recovery.AccountActionRouteHalt) as caught:
            client.post(f"https://{host}{path}")
        assert caught.value.error.request_unknown is True
        assert caught.value.error.failure.http_status == status
    assert current.post.call_count == 1
    recover.assert_not_called()


def test_rate_limited_mfa_does_not_rotate_or_repeat_the_write():
    current = session(response(429))
    recover = Mock()
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    with pytest.raises(recovery.AccountActionRouteHalt) as caught:
        client.post("https://chatgpt.com/backend-api/accounts/mfa/enroll")
    assert caught.value.error.code == "account_action_rate_limited"
    assert caught.value.error.request_unknown is False
    assert current.post.call_count == 1
    recover.assert_not_called()


@pytest.mark.parametrize("code", [
    "account_deactivated", "account_suspended", "account_deleted", "account_banned",
])
def test_known_dead_account_403_returns_original_response_without_rotation(code):
    denied = response(403)
    denied.json = lambda: {"error": {"code": code}}
    current = session(denied)
    recover = Mock(return_value=None)
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    assert client.post("https://chatgpt.com/backend-api/accounts/mfa/user/activate_enrollment") is denied
    current.post.assert_called_once()
    recover.assert_not_called()
    current.session.close.assert_not_called()


def test_api_authorize_403_matches_exact_account_auth_endpoint(monkeypatch):
    current = session(response(403), response())
    monkeypatch.setattr(recovery, "Session", Mock(return_value=SimpleNamespace(close=Mock())))
    recover = Mock(return_value="http://new.example:8080")
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    assert client.get("https://auth.openai.com/api/accounts/authorize").status_code == 200
    assert current.get.call_count == 2
    assert recover.call_args.args[0].operation == "authorize"


def test_mfa_proxy_connect_failure_rotates_before_retry_without_new_enrollment_stack(monkeypatch):
    current = session(RuntimeError("curl: (56) Proxy CONNECT aborted; private"), response())
    monkeypatch.setattr(recovery, "Session", Mock(return_value=SimpleNamespace(close=Mock())))
    recover = Mock(return_value="http://new.example:8080")
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    assert client.post("https://chatgpt.com/backend-api/accounts/mfa/enroll").status_code == 200
    assert current.post.call_count == 2
    assert recover.call_args.args[0].proxy_fault is True
    assert recover.call_args.args[0].request_unknown is False


def test_callback_get_transport_failure_is_not_replayed():
    current = session(TimeoutError("请求超时"))
    recover = Mock(return_value="http://new.example:8080")
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    with pytest.raises(recovery.AccountActionRouteHalt) as caught:
        client.get("https://chatgpt.com/api/auth/callback/openai?code=private")
    assert caught.value.error.request_unknown is True
    assert current.get.call_count == 1
    recover.assert_not_called()


def test_budget_exhaustion_latches_failure_and_cancel_is_not_converted():
    current = session(response(403))
    recover = Mock(return_value=None)
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    with pytest.raises(recovery.AccountActionRouteHalt) as caught:
        client.get("https://auth.openai.com/oauth/authorize")
    assert caught.value.error.code == "account_action_route_exhausted"
    with pytest.raises(recovery.AccountActionRouteHalt):
        client.get("https://auth.openai.com/oauth/authorize")
    assert current.get.call_count == 1
    cancelled = recovery.AccountActionSession(
        session(response()), recover=recover, check=Mock(side_effect=OperationCancelled("已取消")),
    )
    with pytest.raises(OperationCancelled):
        cancelled.get("https://auth.openai.com/oauth/authorize")


def test_rotation_callback_cancellation_is_not_converted_to_route_unavailable():
    from core.codex.retry_service import CodexRetryStopped

    current = session(response(403))
    recover = Mock(side_effect=CodexRetryStopped("已取消"))
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    with pytest.raises(CodexRetryStopped):
        client.get("https://auth.openai.com/oauth/authorize")
    current.get.assert_called_once()


def test_new_transport_initialization_failure_never_reopens_the_old_route(monkeypatch):
    current = session(response(403))
    recover = Mock(return_value="http://new.example:8080")
    monkeypatch.setattr(recovery, "Session", Mock(side_effect=RuntimeError("transport init failed")))
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    for _ in range(2):
        with pytest.raises(recovery.AccountActionRouteHalt) as caught:
            client.get("https://auth.openai.com/oauth/authorize")
        assert caught.value.error.code == "account_action_route_unavailable"
    assert current.get.call_count == 1
    recover.assert_called_once()


@pytest.mark.parametrize("url", [
    "https://mailbox.example/api/messages", "http://127.0.0.1:50100/browser/create",
    "https://auth.openai.com/assets/app.js", "https://auth.openai.com:444/oauth/authorize",
])
def test_third_party_and_assets_never_use_account_recovery(url):
    denied = response(403)
    current = session(denied)
    recover = Mock()
    client = recovery.AccountActionSession(current, recover=recover, check=lambda: None)
    assert client.get(url) is denied
    recover.assert_not_called()
