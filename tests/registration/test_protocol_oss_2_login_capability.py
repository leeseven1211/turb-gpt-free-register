"""原身份登录只依据当前响应明确提供的密码能力切换入口。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.registration.protocol_oss_2 import runtime
from core.registration.protocol_oss_2.lifecycle import ProtocolOssRequestUnknown
from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
from tests.registration.test_protocol_oss_2 import run_flow, upstream as upstream


PASSWORD_URL = "https://auth.openai.com/log-in/password"
CALLBACK_URL = "https://chatgpt.com/api/auth/callback/openai?code=fixture"
_VENDOR_REDIRECT = AuthFlow.follow_redirect_chain


@pytest.fixture
def strict_login(upstream, monkeypatch):
    """仅替换网络回执；保留登录、导航、密码校验及 Session 处理。"""
    session, transport, wait = upstream
    transport.otp_payload = {"page": {"type": "external_url"}, "continue_url": CALLBACK_URL}
    scenario = SimpleNamespace(
        session=session, transport=transport, wait=wait, flows=[],
        page_type="email_otp_verification",
        payload={"email_verification_mode": "passwordless_login", "login_methods": [{"type": "password"}]},
        continue_url="https://auth.openai.com/email-verification",
        landing_url=PASSWORD_URL, navigation_status=200, navigation_error=None,
        strict=True, candidate="original-password", password_payload=None, totp_secret="",
    )
    request = transport.request

    def reply(method, url, **kwargs):
        if url == PASSWORD_URL and scenario.navigation_error is not None:
            transport.requests.append((method, url, kwargs))
            raise scenario.navigation_error
        response = request(method, url, **kwargs)
        if url.endswith("/authorize/continue"):
            response.json.return_value = {
                "page": {"type": scenario.page_type, "payload": scenario.payload},
                "continue_url": scenario.continue_url,
            }
        if url == PASSWORD_URL:
            response.url = scenario.landing_url
            response.status_code = scenario.navigation_status
        if url.endswith("/password/verify") and scenario.password_payload is not None:
            response.json.return_value = scenario.password_payload
        return response

    def login(flow, mailbox):
        scenario.flows.append((flow, flow.session))
        flow.result.totp_secret = scenario.totp_secret
        return flow.run_protocol_login(
            mailbox, "protocol2@example.test", scenario.candidate,
            strict_identity_resume=scenario.strict,
        )

    transport.request = reply
    monkeypatch.setattr(AuthFlow, "run_register", login)
    scenario.run = lambda: run_flow(session, existing_password=scenario.candidate or None)
    with patch.object(AuthFlow, "follow_redirect_chain", _VENDOR_REDIRECT):
        yield scenario


def test_strict_login_prefers_offered_password_before_waiting_for_another_otp(strict_login):
    """忽略当前 password 能力或先重复 OTP 都会错过原候选校验。"""
    scenario = strict_login

    with patch(
        "core.registration.protocol_oss_2.upstream.http_client_wreq.create_http_session",
        return_value=scenario.transport,
    ) as create:
        result = scenario.run()

    requests = scenario.transport.requests
    urls = [url for _, url, _ in requests]
    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is True
    assert result["registration_password"] == "original-password"
    assert urls.index(PASSWORD_URL) < urls.index("https://auth.openai.com/api/accounts/password/verify")
    submitted = next(kwargs["json"] for _, url, kwargs in requests if url.endswith("/password/verify"))
    assert submitted == {"password": "original-password"}
    navigation = next(kwargs for _, url, kwargs in requests if url == PASSWORD_URL)
    assert navigation["headers"]["sec-fetch-mode"] == "navigate"
    assert navigation["headers"]["sec-fetch-site"] == "same-origin"
    assert navigation["headers"]["Referer"] == "https://auth.openai.com/email-verification"
    assert navigation["allow_redirects"] is True
    assert not any("/email-otp/" in url or "/passwordless/" in url for url in urls)
    assert not any(url.endswith("/user/register") or url.endswith("/create_account") for url in urls)
    scenario.wait.assert_not_called()
    assert create.call_count == 1
    assert len(scenario.flows) == 1
    flow, original_session = scenario.flows[0]
    assert flow.session is original_session is scenario.session.session
    assert scenario.transport.closed is False
    callback_index = urls.index(CALLBACK_URL)
    assert urls[callback_index + 1].endswith("/api/auth/session")
    assert urls.count(CALLBACK_URL) == 1
    assert not any(url.endswith("/oauth/token") for url in urls)


@pytest.mark.parametrize("methods", [
    None, [], ["password"], {"type": "password"}, [{"type": "Password"}],
    [{"type": "passwordless"}], [{"type": "email_otp"}], [{"type": None}],
])
def test_strict_login_does_not_guess_password_capability(strict_login, methods):
    scenario = strict_login
    scenario.payload["login_methods"] = methods

    result = scenario.run()

    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert result["registration_password"] == "original-password"
    assert not any(url == PASSWORD_URL or url.endswith("/password/verify") for _, url, _ in scenario.transport.requests)
    assert any(url.endswith("/email-otp/validate") for _, url, _ in scenario.transport.requests)
    assert scenario.wait.call_count == 1


def test_offered_password_without_original_candidate_keeps_otp_and_never_creates_password(strict_login):
    scenario = strict_login
    scenario.candidate = ""

    result = scenario.run()

    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert result["registration_password"] is None
    assert not any(
        url == PASSWORD_URL or url.endswith("/password/verify") or url.endswith("/user/register")
        for _, url, _ in scenario.transport.requests
    )
    assert scenario.wait.call_count == 1


def test_password_capability_is_not_selected_for_non_strict_login(strict_login):
    scenario = strict_login
    scenario.strict = False

    result = scenario.run()

    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    assert not any(url == PASSWORD_URL or url.endswith("/password/verify") for _, url, _ in scenario.transport.requests)
    assert scenario.wait.call_count == 1


@pytest.mark.parametrize("landing_url", [
    "", "/log-in/password", "https://auth.openai.com/email-verification",
    "https://auth.openai.com/create-account/password",
    "https://auth.openai.com/log-in/password/extra",
    "https://auth.openai.com.example.test/log-in/password",
    "https://example.test/log-in/password",
    "http://auth.openai.com/log-in/password",
    "https://auth.openai.com:8443/log-in/password",
    "https://user@auth.openai.com/log-in/password",
])
def test_password_capability_navigation_rejects_wrong_or_untrusted_landing(strict_login, landing_url):
    scenario = strict_login
    scenario.landing_url = landing_url

    with pytest.raises(ProtocolOssRequestUnknown) as raised:
        scenario.run()

    assert raised.value.cause_code == "password_entry_navigation_failed"
    assert sum(url == PASSWORD_URL for _, url, _ in scenario.transport.requests) == 1
    assert not any(
        url.endswith("/password/verify") or url.endswith("/user/register") or "/email-otp/" in url
        for _, url, _ in scenario.transport.requests
    )
    scenario.wait.assert_not_called()


@pytest.mark.parametrize("failure", ["403", "timeout"])
def test_password_navigation_route_failures_reach_the_existing_route_handler(strict_login, monkeypatch, failure):
    scenario = strict_login
    if failure == "403":
        scenario.navigation_status = 403
    else:
        scenario.navigation_error = TimeoutError("fixture password entry timeout")
    observed = []
    monkeypatch.setattr(runtime, "current_route_recovery", lambda: lambda route, proxy: observed.append(route))

    with pytest.raises(ProtocolOssRequestUnknown) as raised:
        scenario.run()

    assert len(observed) == 1
    assert observed[0].operation == "preauth"
    assert observed[0].http_status == (403 if failure == "403" else None)
    assert observed[0].transport_kind == ("" if failure == "403" else "timeout")
    assert raised.value.route_failure == observed[0]
    assert raised.value.route_recovery_blocked is False
    assert sum(url == PASSWORD_URL for _, url, _ in scenario.transport.requests) == 1
    assert not any(url.endswith("/password/verify") or "/email-otp/" in url for _, url, _ in scenario.transport.requests)
    scenario.wait.assert_not_called()


@pytest.mark.parametrize("signal", ["stop", "auth", "lease"])
def test_password_navigation_does_not_swallow_cancellation_or_lost_lease(strict_login, signal):
    from core.auth.challenge import AuthCancelledError
    from core.operations.task_gateway import OperationLeaseLost
    from core.registration.service import StopRequested

    scenario = strict_login
    error = {
        "stop": StopRequested("fixture stop"),
        "auth": AuthCancelledError("fixture cancelled"),
        "lease": OperationLeaseLost("fixture lease lost"),
    }[signal]
    scenario.navigation_error = error

    with pytest.raises(type(error)) as raised:
        scenario.run()

    assert raised.value is error
    assert not any(url.endswith("/password/verify") or "/email-otp/" in url for _, url, _ in scenario.transport.requests)
    scenario.wait.assert_not_called()


def test_current_callback_takes_precedence_over_optional_password_capability(strict_login):
    scenario = strict_login
    scenario.continue_url = CALLBACK_URL

    result = scenario.run()

    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    urls = [url for _, url, _ in scenario.transport.requests]
    assert PASSWORD_URL not in urls
    assert urls.count(CALLBACK_URL) == 1
    assert urls[urls.index(CALLBACK_URL) + 1].endswith("/api/auth/session")
    scenario.wait.assert_not_called()


@pytest.mark.parametrize("next_page", [
    "/log-in/password", "/email-verification", "/about-you", "/workspace&workspace_id=fixture",
])
def test_callback_query_does_not_become_an_auth_step(strict_login, next_page):
    scenario = strict_login
    scenario.continue_url = CALLBACK_URL + "&next=" + next_page

    result = scenario.run()

    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    urls = [url for _, url, _ in scenario.transport.requests]
    assert not any(
        url == PASSWORD_URL or url.endswith("/password/verify") or url.endswith("/workspace/select")
        or url.endswith("/create_account") or "/email-otp/" in url
        for url in urls
    )
    assert urls.count(scenario.continue_url) == 1
    assert urls[urls.index(scenario.continue_url) + 1].endswith("/api/auth/session")
    scenario.wait.assert_not_called()


def test_password_verified_callback_query_does_not_submit_an_mfa_challenge(strict_login):
    scenario = strict_login
    callback = CALLBACK_URL + "&next=/mfa-challenge/fixture"
    scenario.password_payload = {"page": {"type": "external_url"}, "continue_url": callback}
    scenario.totp_secret = "JBSWY3DPEHPK3PXP"

    result = scenario.run()

    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is True
    urls = [url for _, url, _ in scenario.transport.requests]
    assert not any(url.endswith("/mfa/verify") for url in urls)
    assert urls.count(callback) == 1
    assert urls[urls.index(callback) + 1].endswith("/api/auth/session")
    scenario.wait.assert_not_called()


def test_otp_verified_callback_query_does_not_send_a_phone_challenge(strict_login, monkeypatch):
    scenario = strict_login
    callback = CALLBACK_URL + "&next=/add-phone"
    scenario.payload["login_methods"] = []
    scenario.transport.otp_payload = {"page": {"type": "external_url"}, "continue_url": callback}
    monkeypatch.setenv("OPENAI_PHONE_NUMBER", "+15550001111")
    monkeypatch.setenv("OPENAI_PHONE_OTP", "123456")

    result = scenario.run()

    assert result["access_token"] == "fixture-at"
    assert result["password_validated"] is False
    urls = [url for _, url, _ in scenario.transport.requests]
    assert not any("/add-phone/" in url for url in urls)
    assert urls.count(callback) == 1
    assert urls[urls.index(callback) + 1].endswith("/api/auth/session")
    assert scenario.wait.call_count == 1


@pytest.mark.parametrize("landing_url", ["https:/log-in/password", "https:///log-in/password"])
def test_password_navigation_requires_an_absolute_origin(strict_login, landing_url):
    scenario = strict_login
    scenario.landing_url = landing_url

    with pytest.raises(ProtocolOssRequestUnknown) as raised:
        scenario.run()

    assert raised.value.cause_code == "password_entry_navigation_failed"
    assert not any(url.endswith("/password/verify") for _, url, _ in scenario.transport.requests)
    scenario.wait.assert_not_called()


@pytest.mark.parametrize("methods", [None, [], [{"type": "email_otp"}]])
def test_otp_page_with_password_continuation_requires_explicit_password_capability(strict_login, methods):
    scenario = strict_login
    scenario.continue_url = PASSWORD_URL
    scenario.payload["login_methods"] = methods

    with pytest.raises(ProtocolOssRequestUnknown) as raised:
        scenario.run()

    assert raised.value.cause_code == "registration_auth_state_unrecognized"
    assert not any(
        url == PASSWORD_URL or url.endswith("/password/verify") or "/email-otp/" in url
        for _, url, _ in scenario.transport.requests
    )
    scenario.wait.assert_not_called()


@pytest.mark.parametrize("continue_url", [
    "https://example.test/log-in/password",
    "https://auth.openai.com.example.test/log-in/password",
    "http://auth.openai.com/log-in/password",
    "https://auth.openai.com:8443/log-in/password",
    "https://user@auth.openai.com/log-in/password",
    "https://auth.openai.com/email-verification?next=/log-in/password",
])
def test_strict_login_never_accepts_password_path_substrings_as_trusted_entry(strict_login, continue_url):
    scenario = strict_login
    scenario.continue_url = continue_url
    scenario.payload["login_methods"] = []

    with pytest.raises(ProtocolOssRequestUnknown) as raised:
        scenario.run()

    assert raised.value.cause_code == "registration_auth_state_unrecognized"
    assert not any(
        url == PASSWORD_URL or url.endswith("/password/verify") or "/email-otp/" in url
        for _, url, _ in scenario.transport.requests
    )
    scenario.wait.assert_not_called()
