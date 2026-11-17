"""只有显式账号动作适配当前会话，密码拒绝后的新会话也遵守同一边界。"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.accounts.liveness.protocol import v2


def raw_session():
    return SimpleNamespace(proxy="http://fixture.proxy:8080", session=SimpleNamespace(close=Mock()))


def test_explicit_adapter_wraps_before_navigation_and_reaches_authenticated_callback():
    raw = raw_session()
    wrapped = SimpleNamespace(proxy=raw.proxy, session=raw.session)
    adapter = Mock(return_value=wrapped)
    callback = Mock(side_effect=lambda info, current: dict(info, adapted=current is wrapped))
    with (
        patch.object(v2, "get_account_login_credentials", return_value=("fixture-password", "")),
        patch.object(v2, "account_email_is_invalid", return_value=False),
        patch.object(v2, "_network_preflight_with_retry", return_value=(raw, "authorize")),
        patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password") as follow,
        patch.object(v2, "_password_verify", return_value={"continue_url": "https://auth.openai.com/authorize/continue"}),
        patch.object(v2, "_follow_and_fetch", return_value={"accessToken": "fixture-token"}),
    ):
        result = v2.refresh_access_token(
            "adapter@example.test", session_adapter=adapter, on_authenticated=callback,
        )
    assert result["ok"] is True
    assert result["adapted"] is True
    adapter.assert_called_once_with(raw)
    assert follow.call_args.args[0] is wrapped
    raw.session.close.assert_called_once()


def test_password_rejection_adapts_the_new_email_fallback_session_before_navigation():
    raw, fresh = raw_session(), raw_session()
    wrapped = [SimpleNamespace(proxy=item.proxy, session=item.session) for item in (raw, fresh)]
    adapter = Mock(side_effect=wrapped)
    with (
        patch.object(v2, "get_account_login_credentials", return_value=("fixture-password", "")),
        patch.object(v2, "account_email_is_invalid", return_value=False),
        patch.object(v2, "_network_preflight_with_retry", side_effect=[(raw, "password"), (fresh, "email")]),
        patch.object(v2, "follow_authorize", side_effect=[
            "https://auth.openai.com/log-in/password", "https://auth.openai.com/email-verification",
        ]) as follow,
        patch.object(v2, "_password_verify", side_effect=v2.ProtocolV2AuthError("password_rejected")),
        patch.object(v2, "_complete_email_otp", return_value=({"accessToken": "fixture-token"}, "email_otp")),
    ):
        result = v2.refresh_access_token(
            "adapter@example.test", session_adapter=adapter, allow_password_email_fallback=True,
        )
    assert result["ok"] is True
    assert result["fallback_used"] is True
    assert [item.args[0] for item in adapter.call_args_list] == [raw, fresh]
    assert [item.args[0] for item in follow.call_args_list] == wrapped
    raw.session.close.assert_called_once()
    fresh.session.close.assert_called_once()


def test_adapter_control_signal_propagates_and_preflight_transport_is_closed():
    class StopAdapter(BaseException):
        pass

    raw = raw_session()
    with (
        patch.object(v2, "get_account_login_credentials", return_value=("fixture-password", "")),
        patch.object(v2, "account_email_is_invalid", return_value=False),
        patch.object(v2, "_network_preflight_with_retry", return_value=(raw, "authorize")),
        patch.object(v2, "follow_authorize") as follow,
    ):
        with pytest.raises(StopAdapter):
            v2.refresh_access_token(
                "adapter@example.test", session_adapter=Mock(side_effect=StopAdapter()),
            )
    follow.assert_not_called()
    raw.session.close.assert_called_once()
