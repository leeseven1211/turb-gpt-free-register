"""现行注册分发、历史来源执行映射与统一凭据契约。"""
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

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
        assert kwargs["registration_options"]["password_mode"] == "password"
    else:
        assert kwargs["registration_options"] == {"registration_driver": "roxy", "proxy_country": "JP"}


@pytest.mark.parametrize("default,driver,entrypoint,options", [
    ("protocol", "protocol_oss_2", "protocol_cli",
     {"registration_driver": "protocol_oss_2", "password_enabled": True, "password_mode": "password"}),
    ("roxy", "roxy", "roxy_cli", None),
])
def test_implicit_options_keep_the_driver_specific_cli_contract(default, driver, entrypoint, options):
    with patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", default), patch(
        "core.registration.standalone.run_registration_in_context",
    ) as lifecycle:
        dispatcher.run_registration("fixture@example.test", "测试", "1990-01-01")
    call = lifecycle.call_args
    assert call.kwargs == {"driver_name": driver, "entrypoint": entrypoint}
    if options is None:
        assert "registration_options" not in call.args[1]
    else:
        assert call.args[1]["registration_options"] == options


@pytest.mark.parametrize("driver,entrypoint,module_name,function_name,other_module", [
    ("protocol_oss_2", "protocol_cli", "core.registration.protocol_oss_2",
     "run_protocol_oss_2_registration", "core.registration.roxy"),
    ("roxy", "roxy_cli", "core.registration.roxy",
     "run_roxy_registration", "core.registration.protocol_oss_2"),
])
def test_runner_resolution_is_lazy_isolated_and_observes_module_patches(
    driver, entrypoint, module_name, function_name, other_module,
):
    source = dedent("""
        import importlib
        import importlib.util
        import sys
        from unittest.mock import patch

        driver, entrypoint, module_name, function_name, other_module = sys.argv[1:]
        sys.modules[other_module] = None
        assert importlib.util.find_spec("core.registration.registry") is not None, "缺少注册驱动目录"
        from core.registration.registry import resolve_registration_runner

        assert module_name not in sys.modules
        runner, resolved_entrypoint = resolve_registration_runner(driver)
        module = importlib.import_module(module_name)
        assert runner is getattr(module, function_name)
        assert resolved_entrypoint == entrypoint
        with patch.object(module, function_name) as replacement:
            assert resolve_registration_runner(driver) == (replacement, entrypoint)
    """)
    process = subprocess.run(
        [sys.executable, "-c", source, driver, entrypoint, module_name, function_name, other_module],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=20,
    )
    assert process.returncode == 0, process.stderr


def test_unknown_driver_is_rejected_before_execution():
    with patch("core.registration.standalone.run_registration_in_context") as lifecycle:
        with pytest.raises(RuntimeError, match="仅支持 protocol_oss_2 / roxy"):
            dispatcher.run_registration("fixture@example.test", "测试", registration_options={"registration_driver": "unknown"})
    lifecycle.assert_not_called()
