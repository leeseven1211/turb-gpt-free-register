"""现行注册分发、历史来源执行映射与统一凭据契约。"""
from unittest.mock import Mock, patch

import pytest

from core.registration import dispatcher


@pytest.mark.parametrize("historical,current", [
    ("protocol_oss_2", "protocol_oss_2"), ("protocol", "protocol_oss_2"),
    ("protocol_oss", "protocol_oss_2"), ("api", "protocol_oss_2"),
    ("roxy", "roxy"), ("roxy_oss", "roxy"), ("browser_use", "roxy"),
])
def test_history_routes_to_current_driver_without_mutating_source(historical, current):
    snapshot = {"registration_driver": historical, "proxy_country": "JP"}
    target = ("core.registration.roxy.run_roxy_registration" if current == "roxy"
              else "core.registration.protocol_oss_2.run_protocol_oss_2_registration")
    expected = {"success": True}
    with patch(target, return_value=expected) as runner, patch(
        "core.registration.standalone.run_registration_in_context", return_value=expected,
    ) as lifecycle:
        result = dispatcher.run_registration(
            "fixture@example.test", "测试", "1990-01-01", proxy="http://pool.example:8080",
            existing_password="fixture-original", existing_totp_secret="fixture-totp", profile_id="fixture-profile",
            registration_options=snapshot, email_source="email_butler",
        )
    assert result is expected
    call = lifecycle.call_args
    assert call.args[0] is runner
    kwargs = call.args[1]
    assert kwargs["existing_password"] == "fixture-original"
    assert kwargs["existing_totp_secret"] == "fixture-totp"
    assert kwargs["profile_id"] == "fixture-profile"
    assert kwargs["email_source"] == "email_butler"
    assert kwargs["registration_options"]["registration_driver"] == current
    assert call.kwargs["driver_name"] == current
    assert snapshot["registration_driver"] == historical
    if current == "protocol_oss_2":
        assert kwargs["registration_options"]["password_enabled"] is True


def test_live_legacy_default_is_mapped_before_importing_driver():
    with patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "protocol"), patch(
        "core.registration.protocol_oss_2.run_protocol_oss_2_registration", return_value={"success": True},
    ), patch("core.registration.standalone.run_registration_in_context", return_value={"success": True}) as lifecycle:
        dispatcher.run_registration("fixture@example.test", "测试", "1990-01-01")
    assert lifecycle.call_args.kwargs["driver_name"] == "protocol_oss_2"


def test_unknown_driver_is_rejected_before_execution():
    with patch("core.registration.standalone.run_registration_in_context") as lifecycle:
        with pytest.raises(RuntimeError, match="仅支持 protocol_oss_2 / roxy"):
            dispatcher.run_registration("fixture@example.test", "测试", registration_options={"registration_driver": "unknown"})
    lifecycle.assert_not_called()
