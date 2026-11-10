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


class ParameterError(ValueError):
    code = "parameter_invalid"


def normalize_parameters(operation_key: str, parameters: Mapping | None = None) -> dict:
    if operation_key not in OPERATIONS:
        raise ParameterError("不支持的批量操作")
    if parameters is not None and not isinstance(parameters, Mapping):
        raise ParameterError("操作参数必须为对象")
    result = dict(parameters or {})
    allowed = {"timezone_offset_min"} if operation_key == "plan_check" else {"driver"} if operation_key == "codex_retry" else set()
    if set(result) - allowed:
        raise ParameterError("操作包含未支持的参数")
    if "timezone_offset_min" in result:
        value = result["timezone_offset_min"]
        if isinstance(value, bool) or not isinstance(value, int) or not -840 <= value <= 840:
            raise ParameterError("时区偏移必须为 -840 到 840 的整数")
    if "driver" in result and result["driver"] not in {"roxy", "protocol"}:
        raise ParameterError("Codex driver 只能为 roxy 或 protocol")
    return result


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
        snapshot = normalize_config_snapshot(schema.non_sensitive_snapshot(), allowlist=PLAN_CONFIG_ALLOWLIST)
    elif operation_key == "token_refresh":
        from core.accounts.liveness import service as live_service
        from core.proxy.account_routes import proxy_configuration_status
        snapshot = normalize_config_snapshot(schema.non_sensitive_snapshot(), allowlist=live_service.LIVE_CONFIG_ALLOWLIST)
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
        captured = schema.non_sensitive_snapshot()
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
        parameter_schema = {}
        if key == "plan_check":
            parameter_schema = {"timezone_offset_min": {"type": "integer", "minimum": -840, "maximum": 840, "optional": True}}
        elif key == "codex_retry":
            parameter_schema = {"driver": {"type": "string", "enum": ["roxy", "protocol"], "optional": True}}
        operations.append({"key": key, "version": 1, "label": label, "target_kind": "account",
                           "availability": settings["availability"], "parameter_schema": parameter_schema,
                           "effective_settings": settings["effective_settings"],
                           "capabilities": {"cancel_not_started": True, "request_stop": True, "country_override": False},
                           "result_schema_version": 1, "result_panel": key})
    return {"catalog_revision": "2", "query_schema": {"version": 1, "entity": "account"},
            "limits": {"explicit_ids_max": 10000, "target_limit_max": 100000,
                       "page_size_max": 100, "concurrency_max": 128, "selection_ttl_seconds": 1800},
            "operations": operations}


get_catalog = catalog
