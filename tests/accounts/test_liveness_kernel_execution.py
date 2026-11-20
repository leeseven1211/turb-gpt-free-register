"""Execution must live in kernels while legacy patch and domain boundaries survive."""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


ROOT = Path(__file__).resolve().parents[2]


def caller_module():
    frame = inspect.currentframe().f_back
    while frame is not None:
        module = frame.f_globals["__name__"]
        if module not in {__name__, "unittest.mock"}:
            return module
        frame = frame.f_back
    raise AssertionError("execution frame missing")


def test_roxy_probe_fetch_executes_in_kernel_and_keeps_legacy_header_patch():
    from core.accounts.liveness.roxy import probe

    observed = []

    class Driver:
        def execute_script(self, script):
            return -480

        def execute_async_script(self, script, endpoint, headers):
            observed.append((caller_module(), script, endpoint, headers))
            return {"status": 401, "body": "expired"}

    with patch.object(probe, "_headers", return_value={"fixture": "old-patch"}) as headers:
        result = probe._execute_probe(Driver(), "synthetic-token", "synthetic-proxy")
    headers.assert_called_once_with("synthetic-token")
    assert observed[0][0] == "core.kernels.browser.roxy.live_check"
    assert "credentials: 'omit'" in observed[0][1]
    assert "redirect: 'manual'" in observed[0][1]
    assert observed[0][2].endswith("?timezone_offset_min=-480")
    assert observed[0][3] == {"fixture": "old-patch"}
    assert result["http_status"] == 401
    assert result["needs_live_check"] is True


def test_protocol_v2_password_post_executes_in_kernel_and_preserves_old_patches():
    from core.accounts.liveness.protocol import v2

    observed = []
    session = SimpleNamespace(get_auth_headers=lambda **kw: {"referer": kw["referer"]})

    def post(url, **kwargs):
        observed.append((caller_module(), url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {"continue_url": "next"})

    session.post = post
    with (
        patch.object(v2, "request_sentinel_token", return_value="synthetic-sentinel") as sentinel,
        patch.object(v2, "build_sentinel_header", return_value=("header", "so")) as header,
    ):
        assert v2._password_verify(session, "synthetic-password") == {"continue_url": "next"}
    sentinel.assert_called_once_with(session, "password_verify")
    header.assert_called_once_with(session, "synthetic-sentinel", "password_verify")
    module, endpoint, kwargs = observed[0]
    assert module == "core.kernels.protocol.local.refresh_at.v2"
    assert endpoint == "https://auth.openai.com/api/accounts/password/verify"
    assert kwargs == {
        "headers": {
            "referer": "https://auth.openai.com/log-in/password",
            "openai-sentinel-token": "header",
            "openai-sentinel-so-token": "so",
        },
        "data": json.dumps({"password": "synthetic-password"}, separators=(",", ":")),
        "allow_redirects": False,
    }
    assert len(observed) == 1


def test_protocol_v1_otp_execution_keeps_retry_window_and_patch_points():
    from core.accounts.liveness.protocol import legacy
    from core.auth.protocol.openai_auth import EmailOtpInvalidError

    observed = []
    session = object()

    def validate(*args, **kwargs):
        observed.append((caller_module(), args, kwargs))
        if len(observed) == 1:
            raise EmailOtpInvalidError("invalid")
        return {"continue_url": "next"}

    with (
        patch("core.network.at_transport_recovery.current_scope", return_value=None),
        patch.object(legacy, "wait_for_otp", side_effect=["code-one", "code-two"]) as wait,
        patch.object(legacy, "validate_email_otp", side_effect=validate),
        patch.object(legacy, "send_email_otp") as resend,
        patch.object(legacy.time, "time", return_value=1234.0),
        patch.object(legacy.time, "sleep"),
    ):
        result = legacy._validate_with_retry(session, "fixture@example.test", 100.0)
    assert result == {"continue_url": "next"}
    assert [item[0] for item in observed] == [
        "core.kernels.protocol.local.refresh_at.v1",
        "core.kernels.protocol.local.refresh_at.v1",
    ]
    assert wait.call_args_list[0].kwargs["after_ts"] == 100.0
    assert wait.call_args_list[1].kwargs["after_ts"] == 1234.0
    resend.assert_called_once_with(session)
    assert all(item[2] == {"sentinel_header": None, "so_header": None} for item in observed)


def test_protocol_v1_authorize_and_callback_execute_in_kernel_before_domain_close(tmp_path):
    from core.accounts.liveness.protocol import legacy

    observed = []
    session = SimpleNamespace(device_id="fixture-device", proxy="", session=MagicMock())
    info = {"accessToken": "synthetic-token", "user": {}, "account": {}}

    def authorize(*args):
        observed.append(("authorize", caller_module()))
        return "https://auth.openai.com/email-verification"

    def callback(*args, **kwargs):
        observed.append(("callback", caller_module()))

    def authenticated(result, active_session):
        assert active_session is session
        active_session.session.close.assert_not_called()
        observed.append(("authenticated", caller_module()))
        return result

    with (
        patch.object(legacy, "account_email_is_invalid", return_value=False),
        patch.object(legacy, "log_path", return_value=tmp_path / "fixture.log"),
        patch.object(legacy, "_network_preflight_with_retry", return_value=(session, "authorize")),
        patch.object(legacy, "follow_authorize", side_effect=authorize),
        patch.object(legacy, "_validate_with_retry", return_value={"continue_url": "https://chatgpt.com/api/auth/callback/openai"}),
        patch.object(legacy, "follow_oauth_callback", side_effect=callback),
        patch.object(legacy, "fetch_session", return_value=info),
    ):
        result = legacy.check_account_liveness("fixture@example.test", on_authenticated=authenticated)
    assert result["access_token"] == "synthetic-token"
    assert observed[:2] == [
        ("authorize", "core.kernels.protocol.local.refresh_at.v1"),
        ("callback", "core.kernels.protocol.local.refresh_at.v1"),
    ]
    assert observed[2] == ("authenticated", "core.accounts.liveness.protocol.legacy")
    session.session.close.assert_called_once()


def test_protocol_v3_redirect_http_executes_in_kernel_and_rejects_foreign_next_hop():
    from core.accounts.liveness.protocol import v3

    observed = []

    def get(url, **kwargs):
        observed.append((caller_module(), url, kwargs))
        return SimpleNamespace(status_code=302, headers={"location": "https://foreign.example.test/"})

    session = SimpleNamespace(get=get, get_auth_navigate_headers=lambda **kw: kw)
    with pytest.raises(v3.ProtocolV3AuthError, match="untrusted_auth_url"):
        v3._follow(session, "https://auth.openai.com/authorize")
    assert observed == [(
        "core.kernels.protocol.local.refresh_at.v3",
        "https://auth.openai.com/authorize",
        {"headers": {"referer": "https://chatgpt.com/"}, "allow_redirects": False},
    )]


def test_roxy_login_navigation_executes_in_kernel_and_keeps_selenium_patch():
    from core.accounts.liveness.roxy import flow

    observed = []
    driver = SimpleNamespace(current_url="https://auth.openai.com/log-in/password")

    def navigate(*args, **kwargs):
        observed.append((caller_module(), args, kwargs))

    with patch.object(flow, "_safe_get", side_effect=navigate), patch.object(flow, "_find_any") as find:
        assert flow._open_standard_password_login(driver) is True
    assert observed[0][0] == "core.kernels.browser.roxy.refresh_at"
    assert observed[0][1] == (driver, "https://auth.openai.com/log-in/password")
    assert observed[0][2] == {"timeout": 10, "attempts": 1, "accept_hosts": ("auth.openai.com",)}
    find.assert_called_once_with(driver, ["input[type='password']"], timeout=8)


@pytest.mark.parametrize("relative", [
    "browser/roxy/live_check.py",
    "browser/roxy/refresh_at.py",
    "protocol/local/refresh_at/v1.py",
    "protocol/local/refresh_at/v2.py",
    "protocol/local/refresh_at/v3.py",
])
def test_kernel_execution_has_no_domain_import_or_module_dictionary_escape(relative):
    source = ROOT / "core/kernels" / relative
    assert source.is_file(), f"execution kernel missing: {relative}"
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("core.accounts", "core.storage", "core.registration", "core.codex"))
        elif isinstance(node, ast.Import):
            assert all(not alias.name.startswith(("core.accounts", "core.storage", "core.registration", "core.codex")) for alias in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"globals", "exec", "eval", "__import__"}
    dependencies = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name.endswith("Dependencies")]
    assert dependencies, "explicit frozen callback dependencies required"
    assert all(any(isinstance(decorator, ast.Call) and any(
        item.arg == "frozen" and isinstance(item.value, ast.Constant) and item.value.value is True
        for item in decorator.keywords
    ) for decorator in node.decorator_list) for node in dependencies)
