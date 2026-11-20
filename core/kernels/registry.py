"""已解析操作身份到执行函数的懒绑定，不解析策略或执行可用性预检。"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from types import MappingProxyType
from typing import Any

from contracts.kernel_catalog import OperationBinding

# 绑定原公开操作门面，保留输入契约、领域上下文和调用时 patch 点。
# 门面将纯执行委托给对应 kernel；注册生命周期仍由原 package 持有。
_RUNNER_TARGETS: Mapping[OperationBinding, str] = MappingProxyType({
    OperationBinding("registration", "browser", "roxy"):
        "core.registration.roxy:run_roxy_registration",
    OperationBinding("registration", "protocol", "protocol_oss_2"):
        "core.registration.protocol_oss_2:run_protocol_oss_2_registration",
    OperationBinding("refresh_at", "protocol", "local", "v1"):
        "core.accounts.liveness.protocol.legacy:check_account_liveness",
    OperationBinding("refresh_at", "protocol", "local", "v2"):
        "core.accounts.liveness.protocol.v2:refresh_access_token",
    OperationBinding("refresh_at", "protocol", "local", "v3"):
        "core.accounts.liveness.protocol.v3:refresh_access_token",
    OperationBinding("refresh_at", "browser", "roxy"):
        "core.accounts.liveness.roxy.flow:refresh_access_token",
    OperationBinding("password_setup", "protocol", "local"):
        "core.accounts.password_setup.protocol:add_password",
    OperationBinding("password_setup", "browser", "roxy"):
        "core.auth.browser.password_auth:set_roxy_login_password",
    OperationBinding("twofa", "protocol", "local"):
        "core.accounts.export:setup_2fa_protocol",
    OperationBinding("twofa", "browser", "roxy"):
        "core.auth.browser.mfa_auth:setup_roxy_2fa",
    OperationBinding("codex_oauth", "protocol", "local"):
        "core.codex.oauth:run_codex_oauth",
    OperationBinding("codex_oauth", "browser", "roxy"):
        "core.codex.roxy.oauth:run_roxy_codex_oauth",
    OperationBinding("live_check", "protocol", "local"):
        "core.accounts.plans.client:check_account_plan",
    OperationBinding("live_check", "browser", "roxy"):
        "core.accounts.liveness.roxy.probe:run_probe",
    OperationBinding("plan_check", "protocol", "local"):
        "core.accounts.plans.client:check_account_plan",
})


def resolve_operation_runner(binding: OperationBinding) -> Callable[..., Any]:
    """取得已选执行函数本身，保留操作签名、异常和现有 monkeypatch 入口。"""
    module_name, function_name = _RUNNER_TARGETS[binding].split(":", 1)
    return getattr(import_module(module_name), function_name)


__all__ = ["resolve_operation_runner"]
