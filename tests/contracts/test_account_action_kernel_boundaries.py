"""内核执行入口保留真实请求与检查点顺序，领域写回由调用方注入。"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def require_kernel(name):
    parts = name.split(".")
    path = Path(__file__).resolve().parents[2].joinpath(*parts).with_suffix(".py")
    assert path.is_file(), f"缺少纯执行内核: {name}"
    return __import__(name, fromlist=["*"])


def test_password_protocol_execution_keeps_legacy_helper_patch(monkeypatch):
    kernel = require_kernel("core.kernels.protocol.local.password_setup.protocol")
    from core.accounts.password_setup import protocol

    events = []
    response = object()
    monkeypatch.setattr(protocol, "_check", lambda check: events.append(check))
    session = SimpleNamespace(post=lambda url, **kwargs: (events.append((url, kwargs)), response)[1])
    assert (
        protocol._request(
            session,
            "post",
            "https://auth.openai.com/example",
            checkpoint="check",
            data="payload",
            allow_redirects=False,
        )
        is response
    )
    assert events == ["check", ("https://auth.openai.com/example", {"data": "payload", "allow_redirects": False})]
    with pytest.raises(kernel.ProtocolPasswordSetupError) as error:
        kernel._trusted_url("https://unexpected.example/password")
    assert error.value.code == "password_setup_untrusted_redirect"
    assert error.value.request_unknown is False


def test_protocol_twofa_saves_secret_before_activation_and_preserves_payloads():
    kernel = require_kernel("core.kernels.protocol.local.twofa")
    events = []
    responses = iter(
        [
            {"secret": "SYNTHETICKEY", "session_id": "enrollment-1"},
            {"success": True},
        ]
    )

    def post(url, **kwargs):
        events.append((url, json.loads(kwargs["data"])))
        return SimpleNamespace(status_code=200, json=lambda: next(responses))

    env = SimpleNamespace(
        post=post,
        device_id="device-1",
        navigator_language=lambda: "zh-CN",
        get_chatgpt_headers=lambda **kw: {"referer": kw["referer"]},
    )
    secret = kernel.setup_2fa_protocol(
        env,
        "synthetic-at",
        on_secret=lambda value: events.append(("saved", value)),
        totp_factory=lambda value: SimpleNamespace(now=lambda: "123456"),
        clock=SimpleNamespace(time=lambda: 10.0, sleep=lambda duration: events.append(("sleep", duration))),
    )
    assert secret == "SYNTHETICKEY"
    assert events == [
        ("https://chatgpt.com/backend-api/accounts/mfa/enroll", {"factor_type": "totp"}),
        ("saved", "SYNTHETICKEY"),
        (
            "https://chatgpt.com/backend-api/accounts/mfa/user/activate_enrollment",
            {"code": "123456", "factor_type": "totp", "session_id": "enrollment-1"},
        ),
    ]


def test_plan_request_uses_existing_session_once_with_supplied_timeout():
    kernel = require_kernel("core.kernels.protocol.local.plan_check")
    calls = []
    response = object()
    env = SimpleNamespace(
        js_timezone_offset_min=lambda: -480,
        get=lambda url, **kwargs: (calls.append((url, kwargs)), response)[1],
    )
    actual = kernel.request_accounts_check(
        env, headers={"authorization": "Bearer synthetic-at"}, timezone_offset_min="-", timeout=7.5
    )
    assert actual is response
    assert calls == [
        (
            "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27?timezone_offset_min=-480",
            {"headers": {"authorization": "Bearer synthetic-at"}, "allow_redirects": False, "timeout": 7.5},
        )
    ]


def test_browser_password_confirmation_executes_in_kernel():
    kernel = require_kernel("core.kernels.browser.roxy.password_setup")
    assert kernel.set_roxy_login_password.__module__ == kernel.__name__
    assert (
        kernel._password_setup_success_marker(
            {
                "url": "https://chatgpt.com/#settings/Security",
                "body": "Password has not been added",
            }
        )
        == ""
    )
    assert (
        kernel._password_setup_success_marker(
            {
                "url": "https://chatgpt.com/#settings/Security",
                "body": "Password added",
            }
        )
        == "password added"
    )


def test_browser_totp_probe_keeps_identity_boundary_in_kernel():
    kernel = require_kernel("core.kernels.browser.roxy.twofa")
    assert kernel._probe_existing_roxy_totp.__module__ == kernel.__name__
    driver = SimpleNamespace(current_url="https://untrusted.example/")
    assert kernel._probe_existing_roxy_totp(driver, "synthetic@example.test") == {
        "confirmed": False,
        "reason": "untrusted_origin",
    }


def test_saved_session_conversion_keeps_only_cookie_credentials():
    kernel = require_kernel("core.kernels.protocol.local.password_setup.session")
    account = {
        "chatgpt_session": {
            "sessionToken": "synthetic-cookie",
            "accessToken": "not-a-cookie",
            "user": {"id": "user-1"},
            "account": {"id": "account-1"},
        },
        "extra_json": {"device_id": "device-1"},
    }
    source = kernel.saved_token_session(account)
    assert source == {
        "device_id": "device-1",
        "user_id": "user-1",
        "chatgpt_account_id": "account-1",
        "cookies": [
            {
                "name": "__Secure-next-auth.session-token",
                "value": "synthetic-cookie",
                "domain": "chatgpt.com",
                "path": "/",
                "secure": True,
                "expires": None,
            }
        ],
    }
    assert kernel.saved_token_session({"chatgpt_session": {"accessToken": "not-a-cookie"}}) is None


def test_passwordless_authentication_checks_identity_before_returning_token():
    kernel = require_kernel("core.kernels.protocol.local.password_setup.auth")
    events = []
    info = {"accessToken": "synthetic-at", "user": {"email": "synthetic@example.test"}}
    session = SimpleNamespace(proxy="synthetic-route")

    def authenticate(current, authorize, **kwargs):
        assert current is session
        assert authorize == "https://auth.openai.com/authorize"
        assert kwargs["password"] == ""
        events.append("authenticate")
        return info, ["email_otp"]

    def verify_identity(current, email, target):
        assert current is info
        assert email == "synthetic@example.test"
        assert target == {"id": 7}
        events.append("identity")

    result = kernel.authenticate_passwordless_session(
        session,
        "https://auth.openai.com/authorize",
        email="synthetic@example.test",
        target={"id": 7},
        secret="",
        progress={"methods": [], "attempted": ""},
        authenticate=authenticate,
        verify_identity=verify_identity,
        checkpoint=lambda: events.append("checkpoint"),
        now=lambda: "checked-now",
    )
    assert events == ["checkpoint", "authenticate", "checkpoint", "checkpoint", "identity"]
    assert result["access_token"] == "synthetic-at"
    assert result["checked_at"] == "checked-now"
    assert result["password_auth_status"] == "skipped"


def test_browser_security_navigation_uses_facade_timeout_and_existing_toggle(monkeypatch):
    from core.auth.browser import mfa_auth

    calls = []
    toggle = object()
    driver = SimpleNamespace()
    monkeypatch.setattr(mfa_auth._cfg, "ROXY_SELENIUM_TIMEOUT", 19)
    monkeypatch.setattr(mfa_auth, "_safe_get", lambda current, url, **kwargs: calls.append((current, url, kwargs)))
    monkeypatch.setattr(mfa_auth, "_page_warmup", lambda *args, **kwargs: None)
    monkeypatch.setattr(mfa_auth, "_refresh_chatgpt_settings_shell_if_needed", lambda *args, **kwargs: None)
    monkeypatch.setattr(mfa_auth, "_check_manual_stop", lambda: None)
    monkeypatch.setattr(mfa_auth, "_dismiss_chatgpt_pricing_modal", lambda current: False)
    monkeypatch.setattr(mfa_auth, "_dismiss_single_action_dialog", lambda current: False)
    monkeypatch.setattr(mfa_auth, "_find_authenticator_toggle", lambda current: toggle)
    assert mfa_auth._open_chatgpt_security_settings(driver) is toggle
    assert calls == [
        (
            driver,
            "https://chatgpt.com/#settings/Security",
            {
                "timeout": 19,
                "attempts": 2,
                "accept_hosts": ("chatgpt.com",),
            },
        )
    ]


def test_browser_mfa_whole_clock_patch_controls_existing_wait_loop(monkeypatch):
    from core.auth.browser import mfa_auth

    current_time = [100.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        current_time[0] += seconds

    monkeypatch.setattr(mfa_auth, "time", SimpleNamespace(time=lambda: current_time[0], sleep=sleep))
    monkeypatch.setattr(mfa_auth, "_check_manual_stop", lambda: None)
    monkeypatch.setattr(mfa_auth, "_first_visible_css", lambda *args: None)
    with pytest.raises(RuntimeError):
        mfa_auth._wait_visible_css(
            SimpleNamespace(current_url="https://chatgpt.com/"), "#missing", timeout=1, label="fixture"
        )
    assert current_time[0] >= 101
    assert sleeps


def test_browser_mfa_whole_clock_patch_controls_monotonic_deadline(monkeypatch):
    from core.auth.browser import mfa_auth

    ticks = iter([100.0, 104.0])
    sleeps = []
    observations = []
    monkeypatch.setattr(mfa_auth, "time", SimpleNamespace(monotonic=lambda: next(ticks), sleep=sleeps.append))
    monkeypatch.setattr(mfa_auth, "_check_manual_stop", lambda: None)
    monkeypatch.setattr(
        mfa_auth,
        "_detect_mfa_enrollment_step",
        lambda *args, **kwargs: (observations.append("probe"), ("totp", object()))[1],
    )
    with pytest.raises(RuntimeError):
        mfa_auth._wait_after_mfa_email_submit(SimpleNamespace(current_url="https://chatgpt.com/"), timeout=3)
    assert observations == []
    assert sleeps == []
