"""协议 HTTP 传输与本机 curl_cffi 能力的兼容性回归测试。"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from curl_cffi.requests import BrowserType

from config.browser import (
    IMPERSONATE,
    build_browser_environment,
    resolve_chrome_identity,
    resolve_impersonate,
)
from core import openai_auth


def test_configured_impersonate_falls_back_to_runtime_chrome_alias_when_needed():
    supported = {item.value for item in BrowserType}
    resolved = resolve_impersonate("chrome999")

    assert resolved in supported
    assert resolved.startswith("chrome")


def test_supported_impersonate_value_is_preserved():
    supported = next(item.value for item in BrowserType if item.value.startswith("chrome"))

    assert resolve_impersonate(supported) == supported
    assert resolve_impersonate(IMPERSONATE) in {item.value for item in BrowserType}


def test_runtime_chrome_fallback_keeps_tls_http_and_sentinel_versions_equal():
    identity = resolve_chrome_identity("chrome999")
    profile = build_browser_environment(chrome_identity=identity)

    assert identity["impersonate"] in {item.value for item in BrowserType}
    assert f'Chrome/{identity["full_version"]}' in profile["user_agent"]
    assert f'v="{identity["major"]}"' in profile["sec_ch_ua"]
    assert profile["chrome_major"] == identity["major"]


def test_authorize_continue_uses_raw_session_observer_token_header():
    session = SimpleNamespace(
        device_id="device-id",
        browser_profile={"user_agent": "Mozilla/5.0"},
        sentinel_sid="sentinel-sid",
        auth_cookie_header=lambda: "oai-did=device-id",
    )
    runner_output = json.dumps(
        {
            "p": "proof",
            "c": "challenge",
            "id": "device-id",
            "flow": "authorize_continue",
            "_so": '{"so":"raw-session-observer-token","c":"challenge"}',
        }
    )

    with patch.object(openai_auth, "generate_sentinel_token", return_value=runner_output):
        sentinel_header, so_header = openai_auth.build_sentinel_header(
            session,
            {"token": "challenge"},
            "authorize_continue",
        )

    assert json.loads(sentinel_header) == {
        "p": "proof",
        "c": "challenge",
        "id": "device-id",
        "flow": "authorize_continue",
    }
    assert so_header == '{"so":"raw-session-observer-token","c":"challenge"}'


def test_registration_flows_wrap_session_observer_token_but_authorize_continue_does_not():
    session = SimpleNamespace(
        device_id="device-id",
        browser_profile={"user_agent": "Mozilla/5.0"},
        sentinel_sid="sentinel-sid",
        sentinel_iframe_sid="iframe-sid",
        auth_cookie_header=lambda: "oai-did=device-id",
    )
    complete_so_token = '{"so":"raw-session-observer-token","c":"challenge"}'
    runner_output = json.dumps(
        {
            "p": "proof",
            "c": "challenge",
            "_so": complete_so_token,
        }
    )

    with patch.object(openai_auth, "generate_sentinel_token", return_value=runner_output):
        for flow in ("username_password_create", "email_otp_validate", "oauth_create_account"):
            _sentinel_header, so_header = openai_auth.build_sentinel_header(
                session,
                {"token": "challenge"},
                flow,
            )
            wrapped = json.loads(so_header)
            assert wrapped == {
                "so": complete_so_token,
                "c": "challenge",
                "id": "device-id",
                "flow": flow,
            }

        _sentinel_header, so_header = openai_auth.build_sentinel_header(
            session,
            {"token": "challenge"},
            "authorize_continue",
        )
        assert so_header == complete_so_token
