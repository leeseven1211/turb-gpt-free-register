"""The old preflight path is preserved when recovery is disabled/unneeded."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.protocol import openai_auth


def session_with(response):
    return SimpleNamespace(get=Mock(return_value=response), get_chatgpt_navigate_headers=lambda referer: {"nav": "same"})


def test_disabled_login_preflight_keeps_original_request_shape():
    result = SimpleNamespace(status_code=200)
    session = session_with(result)
    with patch("core.network.cloudflare_adapters.recover_browser_preflight") as recovery:
        assert openai_auth._login_preflight_get(session, timeout=12, enabled=False) is result
    session.get.assert_called_once_with("https://chatgpt.com/auth/login", headers={"nav": "same"},
                                        allow_redirects=True, timeout=12)
    recovery.assert_not_called()


def test_enabled_login_preflight_optional_error_preserves_good_result():
    result = SimpleNamespace(status_code=200)
    session = session_with(result)
    with patch("core.network.cloudflare_adapters.recover_browser_preflight", side_effect=RuntimeError("unavailable")):
        assert openai_auth._login_preflight_get(session, timeout=12, enabled=True) is result
    assert session.get.call_count == 1


def test_enabled_login_preflight_preserves_original_network_failure():
    session = session_with(None)
    session.get.side_effect = ConnectionError("fixture")
    with patch("core.network.cloudflare_adapters.recover_browser_preflight") as recovery:
        with pytest.raises(ConnectionError):
            openai_auth._login_preflight_get(session, timeout=12, enabled=True)
    recovery.assert_not_called()


def test_enabled_preflight_propagates_cancelled_task():
    from core.auth.challenge import AuthCancelledError
    session = session_with(SimpleNamespace(status_code=403))
    with patch("core.network.cloudflare_adapters.recover_browser_preflight", side_effect=AuthCancelledError("stop")):
        with pytest.raises(AuthCancelledError):
            openai_auth._login_preflight_get(session, timeout=12, enabled=True)


def test_local_protocol_recovery_config_defaults_off():
    from config import openai_protocol, schema
    assert schema.schema_default("OPENAI_CF_PREFLIGHT_ENABLED") is False
    assert openai_protocol.OPENAI_CF_PREFLIGHT_ENABLED is False


def test_withdrawn_protocol2_recovery_flag_is_not_editable_or_exposed_in_config():
    from config import schema

    removed_key = "OPENAI_CF_PROTO2_PREFLIGHT_ENABLED"
    assert removed_key not in {field["key"] for field in schema.CONFIG_SCHEMA.editor_metadata()}
    with pytest.raises(schema.ConfigValidationError) as rejected:
        schema.validate_config_updates({removed_key: True})
    assert removed_key in rejected.value.errors
    assert schema.validate_config_updates({"OPENAI_CF_PREFLIGHT_ENABLED": False}) == {
        "OPENAI_CF_PREFLIGHT_ENABLED": False,
    }
