"""批量操作目录与既有领域配置的有限公开快照。"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

OPERATIONS = {
    "plan_check": "查询套餐",
    "token_refresh": "刷新 AT",
    "password_setup": "补密码",
    "twofa_setup": "补 2FA",
    "codex_retry": "补 Codex",
    "account_completion": "组合补全",
}

# 这里只开放本批常用选项，值的定义和校验仍由现有配置 schema 负责。
_PARAMETER_CONFIG = {
    "plan_check": {"countries": "PLAN_CHECK_COUNTRIES", "driver": "ACCOUNT_PLAN_CHECK_DRIVER",
                   "auto_refresh_at_enabled": "PLAN_CHECK_AUTO_REFRESH_AT_ENABLED"},
    "token_refresh": {"refresh_driver": "ACCOUNT_AT_REFRESH_DRIVER", "refresh_protocol_version": "OPENAI_PROTOCOL_VERSION"},
    "password_setup": {"password_driver": "ACCOUNT_PASSWORD_DRIVER"},
    "twofa_setup": {"twofa_driver": "ACCOUNT_2FA_DRIVER"},
    "codex_retry": {"driver": "ACCOUNT_CODEX_DRIVER"},
    "account_completion": {
        "password_enabled": "ACCOUNT_COMPLETION_PASSWORD_ENABLED",
        "plan_check_enabled": "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED",
        "twofa_enabled": "ACCOUNT_COMPLETION_2FA_ENABLED",
        "codex_enabled": "ACCOUNT_COMPLETION_CODEX_ENABLED",
        "refresh_at_enabled": "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED",
        "password_driver": "ACCOUNT_PASSWORD_DRIVER", "twofa_driver": "ACCOUNT_2FA_DRIVER",
        "codex_driver": "ACCOUNT_CODEX_DRIVER",
    },
}
_PARAMETER_LABELS = {
    "countries": "查询国家", "driver": "执行驱动", "auto_refresh_at_enabled": "自动刷新 AT",
    "refresh_driver": "AT 刷新驱动", "refresh_protocol_version": "AT 刷新协议",
    "password_driver": "密码驱动", "twofa_driver": "2FA 驱动", "codex_driver": "Codex 驱动",
    "password_enabled": "补密码", "plan_check_enabled": "查询套餐", "twofa_enabled": "补 2FA",
    "codex_enabled": "补 Codex", "refresh_at_enabled": "刷新 AT",
}


class ParameterError(ValueError):
    code = "parameter_invalid"


def normalize_parameters(operation_key: str, parameters: Mapping | None = None) -> dict:
    from config import schema

    if operation_key not in OPERATIONS:
        raise ParameterError("不支持的批量操作")
    if parameters is not None and not isinstance(parameters, Mapping):
        raise ParameterError("操作参数必须为对象")
    result = dict(parameters or {})
    allowed = set(_PARAMETER_CONFIG[operation_key])
    if operation_key == "plan_check":
        allowed.add("timezone_offset_min")
    if set(result) - allowed:
        raise ParameterError("操作包含未支持的参数")
    if "timezone_offset_min" in result:
        value = result["timezone_offset_min"]
        if isinstance(value, bool) or not isinstance(value, int) or not -840 <= value <= 840:
            raise ParameterError("时区偏移必须为 -840 到 840 的整数")
    for name, config_key in _PARAMETER_CONFIG[operation_key].items():
        if name not in result:
            continue
        field = schema.CONFIG_SCHEMA[config_key]
        value = result[name]
        if field.type == "bool" and not isinstance(value, bool):
            raise ParameterError(f"{_PARAMETER_LABELS[name]}必须为布尔值")
        if field.type == "str" and not isinstance(value, str):
            raise ParameterError(f"{_PARAMETER_LABELS[name]}必须为文本")
        try:
            result[name] = schema.validate_value(config_key, value)
        except schema.ConfigValidationError as exc:
            raise ParameterError(str(exc)) from exc
    return result


def _parameter_schema(operation_key: str, effective: Mapping) -> dict:
    from config import schema

    result = {}
    for name, config_key in _PARAMETER_CONFIG[operation_key].items():
        field = schema.CONFIG_SCHEMA[config_key]
        default_key = "oauth_driver" if operation_key == "codex_retry" and name == "driver" else name
        definition = {"type": {"bool": "boolean", "list_str_multiline": "array"}.get(field.type, "string"),
                      "label": _PARAMETER_LABELS[name], "optional": True,
                      "default": effective.get(default_key, field.clone_default())}
        if field.options:
            definition.update(enum=[option.value for option in field.options],
                              enum_labels={option.value: option.label for option in field.options})
        if definition["type"] == "array":
            definition.update(items={"type": "string"}, help="填写 ISO 两位国家代码，使用逗号或空格分隔；留空沿用账号注册国家。")
        result[name] = definition
    if operation_key == "plan_check":
        result["timezone_offset_min"] = {"type": "integer", "minimum": -840, "maximum": 840, "optional": True}
    return result


def _with_parameters(captured, operation_key: str, parameters: Mapping):
    """从一次全局快照派生本批快照，保持全局版本且不回写配置。"""
    if not parameters or not any(name in parameters for name in _PARAMETER_CONFIG[operation_key]):
        return captured
    from core.codex.operation_service import _snapshot_payload

    values, revision = _snapshot_payload(captured)
    values = dict(values)
    for name, config_key in _PARAMETER_CONFIG[operation_key].items():
        if name in parameters:
            values[config_key] = parameters[name]
    return {"values": values, "revision": revision}


def parameters_hash(parameters: Mapping) -> str:
    return hashlib.sha256(json.dumps(dict(parameters), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def capture_settings(operation_key: str, parameters: Mapping | None = None) -> dict:
    """只捕获现有执行配置，不领取代理、不请求远端、不复制密钥。"""
    from config import schema
    from core.operations.task_gateway import normalize_config_snapshot
    from core.accounts import operation_coordinator as coordinator
    from core.runtime.capabilities import account_setup_unavailable

    parameters = normalize_parameters(operation_key, parameters)
    unavailable = None
    if operation_key == "plan_check":
        from core.accounts.plans.service import PLAN_CONFIG_ALLOWLIST
        captured = _with_parameters(schema.non_sensitive_snapshot(), operation_key, parameters)
        snapshot = normalize_config_snapshot(captured, allowlist=PLAN_CONFIG_ALLOWLIST)
    elif operation_key == "token_refresh":
        from core.accounts.liveness import service as live_service
        from core.proxy.account_routes import proxy_configuration_status
        captured = _with_parameters(schema.non_sensitive_snapshot(), operation_key, parameters)
        snapshot = normalize_config_snapshot(captured, allowlist=live_service.LIVE_CONFIG_ALLOWLIST)
        driver = live_service._resolve_refresh_driver(config_snapshot=snapshot)
        unavailable = live_service.deployment_unavailable(force_refresh=True, driver=driver, config_snapshot=snapshot)
        proxy = proxy_configuration_status("token-refresh")
        if unavailable is None and not proxy.get("ok"):
            unavailable = {"error_code": "proxy_configuration_unavailable", "error": proxy.get("reason") or "刷新 AT 代理尚未配置"}
    elif operation_key == "codex_retry":
        from core.codex import operation_service
        snapshot = operation_service._config_snapshot(driver_override=parameters.get("driver"))
        unavailable = operation_service._deployment_unavailable(snapshot)
        enabled, reason = operation_service._feature_ready(snapshot)
        if not enabled and unavailable is None:
            unavailable = {"error_code": "operation_unavailable", "error": reason}
    else:
        captured = _with_parameters(schema.non_sensitive_snapshot(), operation_key, parameters)
        snapshot = normalize_config_snapshot(captured, allowlist=coordinator._RUNTIME_CONFIG_ALLOWLIST)
        snapshot["bulk_execution_frozen"] = True
        if operation_key == "account_completion":
            from core.accounts.plans.service import PLAN_CONFIG_ALLOWLIST
            from core.accounts.liveness.service import LIVE_CONFIG_ALLOWLIST
            from core.codex import operation_service
            values, revision = operation_service._snapshot_payload(captured)
            snapshot["child_execution"] = {
                "refresh_at": normalize_config_snapshot(captured, allowlist=LIVE_CONFIG_ALLOWLIST),
                "plan_check": normalize_config_snapshot(captured, allowlist=PLAN_CONFIG_ALLOWLIST),
                "codex": operation_service._project_config_snapshot(values, revision,
                    driver_override=str(snapshot.get("codex_driver") or "same_as_registration")),
            }
        if operation_key != "account_completion":
            steps = {"password"} if operation_key == "password_setup" else {"twofa"}
            unavailable = account_setup_unavailable(steps, dict(snapshot))
    revision = str(snapshot.get("config_snapshot_revision", "legacy"))
    return {
        "operation_key": operation_key, "version": 1, "parameters": parameters,
        "parameters_hash": parameters_hash(parameters), "config_revision": revision,
        "config_snapshot": snapshot,
        "effective_settings": {**snapshot, "config_revision": revision},
        "availability": {"available": unavailable is None,
                         "reason_code": unavailable.get("error_code", "operation_unavailable") if unavailable else None,
                         "reason": unavailable.get("error", "") if unavailable else ""},
    }


def catalog() -> dict:
    operations = []
    for key, label in OPERATIONS.items():
        settings = capture_settings(key)
        parameter_schema = _parameter_schema(key, settings["effective_settings"])
        operations.append({"key": key, "version": 1, "label": label, "target_kind": "account",
                           "availability": settings["availability"], "parameter_schema": parameter_schema,
                           "effective_settings": settings["effective_settings"],
                           "capabilities": {"cancel_not_started": True, "request_stop": True, "pause": True,
                                            "resume": True, "country_override": key == "plan_check"},
                           "result_schema_version": 1, "result_panel": key})
    return {"catalog_revision": "3", "query_schema": {"version": 1, "entity": "account"},
            "limits": {"explicit_ids_max": 10000, "target_limit_max": 100000,
                       "page_size_max": 100, "concurrency_max": 128, "selection_ttl_seconds": 1800},
            "operations": operations}


get_catalog = catalog
