"""内核身份只投影已解析的选择，不授予跨操作能力或解析业务策略。"""
from dataclasses import FrozenInstanceError
from importlib import import_module
from importlib.util import find_spec
import inspect
import sys
from types import ModuleType

import pytest


_CASES = [
    ("registration", "roxy", "v1", "browser", "roxy", None),
    ("registration", "protocol_oss_2", "v1", "protocol", "protocol_oss_2", None),
    ("registration", "sentinel_rs", "v1", "rust", "sentinel_rs", None),
    ("refresh_at", "protocol", "v1", "protocol", "local", "v1"),
    ("refresh_at", "protocol", "v2", "protocol", "local", "v2"),
    ("refresh_at", "protocol", "v3", "protocol", "local", "v3"),
    ("refresh_at", "browser_roxy", "v1", "browser", "roxy", None),
    ("password_setup", "protocol", "v1", "protocol", "local", None),
    ("password_setup", "roxy", "v1", "browser", "roxy", None),
    ("twofa", "protocol", "v1", "protocol", "local", None),
    ("twofa", "browser", "v1", "browser", "roxy", None),
    ("codex_oauth", "protocol", "v1", "protocol", "local", None),
    ("codex_oauth", "roxy", "v1", "browser", "roxy", None),
    ("live_check", "protocol_current", "v1", "protocol", "local", None),
    ("live_check", "browser_roxy", "v1", "browser", "roxy", None),
    ("plan_check", "protocol", "v1", "protocol", "local", None),
]


def _catalog():
    assert find_spec("contracts.kernel_catalog") is not None, "缺少纯内核目录 API"
    return import_module("contracts.kernel_catalog")


@pytest.mark.parametrize("operation,driver,version,kernel,implementation,variant", _CASES)
def test_resolved_canonical_choices_keep_their_operation_and_implementation(
    operation, driver, version, kernel, implementation, variant,
):
    catalog = _catalog()
    binding = catalog.operation_binding(operation, driver, protocol_version=version)
    assert (binding.operation, binding.kernel, binding.implementation, binding.variant) == (
        operation, kernel, implementation, variant,
    )
    assert catalog.operation_selection_policy(operation, driver) == "fixed"


def test_rust_kernel_owns_registration_and_explicit_refresh():
    catalog = _catalog()
    assert set(catalog.KERNELS) == {"browser", "protocol", "rust"}
    assert set(catalog.IMPLEMENTATIONS) == {
        ("browser", "roxy"), ("protocol", "local"),
        ("protocol", "protocol_oss_2"), ("rust", "sentinel_rs"),
    }
    rust_bindings = {binding for binding in catalog.OPERATION_BINDINGS if binding.kernel == "rust"}
    assert rust_bindings == {
        catalog.OperationBinding("registration", "rust", "sentinel_rs"),
        catalog.OperationBinding("refresh_at", "rust", "sentinel_rs"),
    }
    # Rust 刷新是固定身份，版本字段只影响协议内核。
    assert catalog.operation_binding("refresh_at", "rust", protocol_version="v3") == (
        catalog.OperationBinding("refresh_at", "rust", "sentinel_rs")
    )


@pytest.mark.parametrize("operation,driver,policy", [
    ("twofa", "auto", "auto"),
    ("codex_oauth", "same_as_registration", "same_as_registration"),
])
def test_selection_policies_require_business_resolution_before_binding(operation, driver, policy):
    catalog = _catalog()
    assert catalog.operation_selection_policy(operation, driver) == policy
    with pytest.raises(KeyError):
        catalog.operation_binding(operation, driver)


@pytest.mark.parametrize("operation,driver", [
    ("registration", "protocol"),
    ("registration", "roxy_oss"),
    ("refresh_at", "legacy"),
    ("refresh_at", "protocol_v2"),
    ("password_setup", "browser"),
    ("twofa", "roxy"),
    ("twofa", "same_as_registration"),
    ("codex_oauth", "protocol_oss_2"),
    ("live_check", "protocol"),
    ("plan_check", "roxy"),
    ("plan_check", "sentinel_rs"),
    ("unknown", "protocol"),
])
def test_aliases_unknown_values_and_other_operation_choices_are_not_reinterpreted(operation, driver):
    catalog = _catalog()
    with pytest.raises(KeyError):
        catalog.operation_binding(operation, driver)
    with pytest.raises(KeyError):
        catalog.operation_selection_policy(operation, driver)


def test_refresh_variants_do_not_change_fixed_operations_or_their_capabilities():
    catalog = _catalog()
    for operation, driver in [
        ("registration", "protocol_oss_2"), ("password_setup", "protocol"),
        ("twofa", "protocol"), ("codex_oauth", "protocol"),
        ("live_check", "protocol_current"), ("plan_check", "protocol"),
    ]:
        assert catalog.operation_binding(operation, driver, protocol_version="v3") == (
            catalog.operation_binding(operation, driver, protocol_version="v1")
        )
    with pytest.raises(KeyError):
        catalog.operation_binding("refresh_at", "protocol", protocol_version="protocol_v2")
    with pytest.raises(KeyError):
        catalog.operation_binding("refresh_at", "protocol", protocol_version="v4")


def test_shared_identity_and_capabilities_cannot_be_mutated_by_a_caller():
    catalog = _catalog()
    for record, attribute in [
        (catalog.KERNELS["browser"], "key"),
        (catalog.IMPLEMENTATIONS[("protocol", "local")], "kernel"),
        (catalog.operation_binding("registration", "roxy"), "operation"),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(record, attribute, "changed")
    with pytest.raises(TypeError):
        catalog.KERNELS["rust"] = catalog.KERNELS["browser"]
    with pytest.raises(TypeError):
        catalog.IMPLEMENTATIONS[("rust", "sentinel_rs")] = catalog.IMPLEMENTATIONS[("protocol", "local")]
    assert isinstance(catalog.OPERATION_BINDINGS, frozenset)


def test_operation_driver_catalog_reexports_the_same_static_projection():
    catalog = _catalog()
    drivers = import_module("contracts.operation_drivers")
    assert drivers.operation_binding is catalog.operation_binding
    assert drivers.operation_selection_policy is catalog.operation_selection_policy


_TARGETS = [
    ("registration", "roxy", "v1", "core.registration.roxy", "run_roxy_registration"),
    ("registration", "protocol_oss_2", "v1", "core.registration.protocol_oss_2", "run_protocol_oss_2_registration"),
    ("registration", "sentinel_rs", "v1", "core.registration.sentinel_rs", "run_sentinel_rs_registration"),
    ("refresh_at", "protocol", "v1", "core.accounts.liveness.protocol.legacy", "check_account_liveness"),
    ("refresh_at", "protocol", "v2", "core.accounts.liveness.protocol.v2", "refresh_access_token"),
    ("refresh_at", "protocol", "v3", "core.accounts.liveness.protocol.v3", "refresh_access_token"),
    ("refresh_at", "browser_roxy", "v1", "core.accounts.liveness.roxy.flow", "refresh_access_token"),
    ("password_setup", "protocol", "v1", "core.accounts.password_setup.protocol", "add_password"),
    ("password_setup", "roxy", "v1", "core.auth.browser.password_auth", "set_roxy_login_password"),
    ("twofa", "protocol", "v1", "core.accounts.export", "setup_2fa_protocol"),
    ("twofa", "browser", "v1", "core.auth.browser.mfa_auth", "setup_roxy_2fa"),
    ("codex_oauth", "protocol", "v1", "core.codex.oauth", "run_codex_oauth"),
    ("codex_oauth", "roxy", "v1", "core.codex.roxy.oauth", "run_roxy_codex_oauth"),
    ("live_check", "protocol_current", "v1", "core.accounts.plans.client", "check_account_plan"),
    ("live_check", "browser_roxy", "v1", "core.accounts.liveness.roxy.probe", "run_probe"),
    ("plan_check", "protocol", "v1", "core.accounts.plans.client", "check_account_plan"),
]


@pytest.mark.parametrize("operation,driver,version,module_name,function_name", _TARGETS)
def test_lazy_resolution_keeps_the_selected_function_signature_and_public_patch_point(
    monkeypatch, operation, driver, version, module_name, function_name,
):
    catalog = _catalog()
    registry = import_module("core.kernels.registry")
    module = ModuleType(module_name)
    calls = []

    def selected_function(identity, *, checkpoint=None):
        calls.append((identity, checkpoint))
        return {"identity": identity}

    setattr(module, function_name, selected_function)
    monkeypatch.setitem(sys.modules, module_name, module)
    binding = catalog.operation_binding(operation, driver, protocol_version=version)
    runner = registry.resolve_operation_runner(binding)
    assert calls == []
    assert runner is selected_function
    assert inspect.signature(runner) == inspect.signature(selected_function)
    assert runner("selected", checkpoint="current") == {"identity": "selected"}
    assert calls == [("selected", "current")]

    def replacement(identity, *, cancelled=False):
        return {"replacement": identity, "cancelled": cancelled}

    setattr(module, function_name, replacement)
    assert registry.resolve_operation_runner(binding) is replacement


def test_a_missing_selected_dependency_is_not_replaced_by_a_different_binding(monkeypatch):
    catalog = _catalog()
    registry = import_module("core.kernels.registry")
    monkeypatch.setitem(sys.modules, "core.accounts.liveness.protocol.v2", None)
    with pytest.raises(ModuleNotFoundError):
        registry.resolve_operation_runner(catalog.operation_binding("refresh_at", "protocol", protocol_version="v2"))
    assert registry.resolve_operation_runner(
        catalog.OperationBinding("registration", "rust", "sentinel_rs")
    ).__name__ == "run_sentinel_rs_registration"
    with pytest.raises(KeyError):
        registry.resolve_operation_runner(catalog.OperationBinding("twofa", "protocol", "protocol_oss_2"))


@pytest.mark.parametrize("identity", [
    ("registration", "protocol", "roxy", None),
    ("registration", "browser", "protocol_oss_2", None),
    ("refresh_at", "browser", "local", "v2"),
    ("twofa", "protocol", "auto", None),
    ("codex_oauth", "protocol", "same_as_registration", None),
    ("unknown", "browser", "roxy", None),
])
def test_wrong_kernel_unknown_identity_and_policies_fail_before_loading_any_runner(monkeypatch, identity):
    catalog = _catalog()
    registry = import_module("core.kernels.registry")

    def unexpected_import(module_name):
        raise AssertionError(f"不支持的身份不应加载任何执行器: {module_name}")

    monkeypatch.setattr(registry, "import_module", unexpected_import)
    with pytest.raises(KeyError):
        registry.resolve_operation_runner(catalog.OperationBinding(*identity))
