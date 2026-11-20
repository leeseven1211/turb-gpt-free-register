"""领域先解析策略，再按内核绑定读取当前的兼容执行入口。"""
from unittest.mock import patch, sentinel

import pytest

from contracts.kernel_catalog import operation_binding
from core.kernels import registry


@pytest.mark.parametrize("driver,entrypoint", [
    ("roxy", "roxy_cli"),
    ("protocol_oss_2", "protocol_cli"),
])
def test_registration_resolves_selected_kernel_before_loading_runner(driver, entrypoint):
    from core.registration.registry import resolve_registration_runner

    with patch.object(registry, "resolve_operation_runner", return_value=sentinel.runner) as resolve:
        runner, cli_entrypoint = resolve_registration_runner(driver)
    assert runner is sentinel.runner
    assert cli_entrypoint == entrypoint
    resolve.assert_called_once_with(operation_binding("registration", driver))


@pytest.mark.parametrize("driver,canonical,version", [
    ("browser_roxy", "browser_roxy", "v1"),
    ("protocol_v2", "protocol", "v2"),
    ("protocol_v3", "protocol", "v3"),
])
def test_refresh_uses_resolved_version_without_reinterpreting_configuration(driver, canonical, version):
    from core.accounts.liveness import service

    assert hasattr(service, "_refresh_execution_runner"), "缺少已解析刷新身份的执行入口"
    with patch.object(registry, "resolve_operation_runner", return_value=sentinel.runner) as resolve:
        assert service._refresh_execution_runner(driver) is sentinel.runner
    resolve.assert_called_once_with(operation_binding("refresh_at", canonical, protocol_version=version))


def test_legacy_refresh_keeps_injected_public_probe():
    from core.accounts.liveness import service

    assert hasattr(service, "_refresh_execution_runner"), "缺少已解析刷新身份的执行入口"
    with patch.object(service, "check_account_liveness", sentinel.runner):
        assert service._refresh_execution_runner("legacy") is sentinel.runner
