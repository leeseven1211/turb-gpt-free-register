# -*- coding: utf-8 -*-
"""账号操作配置的唯一投影与能力组合入口，不定义配置 schema。"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from core.accounts.liveness import service as live_check_service
from core.codex import operation_service as codex_operation_service
from core.operations import task_gateway

logger = logging.getLogger(__name__)

# 只列出账号操作需要的执行字段，配置定义仍由 config/schema.py 持有。
RUNTIME_CONFIG_ALLOWLIST = {
    "password_enabled": "ACCOUNT_COMPLETION_PASSWORD_ENABLED",
    "password_reset_enabled": "ACCOUNT_PASSWORD_RESET_ENABLED",
    "plan_check_enabled": "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED",
    "twofa_enabled": "ACCOUNT_COMPLETION_2FA_ENABLED",
    "codex_enabled": "ACCOUNT_COMPLETION_CODEX_ENABLED",
    "refresh_at_enabled": "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED",
    "password_driver": "ACCOUNT_PASSWORD_DRIVER",
    "plan_check_driver": "ACCOUNT_PLAN_CHECK_DRIVER",
    "password_proxy_mode": "ACCOUNT_PASSWORD_PROXY_MODE",
    "twofa_proxy_mode": "ACCOUNT_2FA_PROXY_MODE",
    "plan_check_proxy_mode": "ACCOUNT_PLAN_CHECK_PROXY_MODE",
    "live_check_proxy_mode": "ACCOUNT_LIVE_CHECK_PROXY_MODE",
    "refresh_at_proxy_mode": "ACCOUNT_REFRESH_AT_PROXY_MODE",
    "codex_proxy_mode": "ACCOUNT_CODEX_PROXY_MODE",
    "twofa_driver": "ACCOUNT_2FA_DRIVER",
    "twofa_browser_fallback_enabled": "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED",
    "twofa_protocol_reauth_enabled": "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED",
    "codex_driver": "ACCOUNT_CODEX_DRIVER",
    "protocol_version": "OPENAI_PROTOCOL_VERSION",
}


def runtime_config_snapshot() -> Any | None:
    """读取配置 schema 的原子快照，不另行定义或缓存配置。"""
    try:
        from config import schema
    except ImportError:
        return None
    provider = getattr(schema, "non_sensitive_snapshot", None)
    return provider() if callable(provider) else None


def legacy_runtime_snapshot(settings: Mapping[str, Any]) -> dict[str, Any]:
    """配置快照提供者不可用时，保留既有执行设置的兼容快照。"""
    result = dict(settings)
    result["config_snapshot_revision"] = "legacy"
    return result


def completion_settings_from_snapshot(
    snapshot: Mapping[str, Any] | None,
    *,
    fallback: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """将已捕获的执行快照投影为账号补全设置。"""
    from config.account import completion_settings

    values = dict(fallback or completion_settings())
    if isinstance(snapshot, Mapping):
        values.update({
            str(key): value for key, value in snapshot.items()
            if str(key) != "config_snapshot_revision"
        })
    bool_keys = {
        "password_enabled", "password_reset_enabled", "plan_check_enabled",
        "twofa_enabled", "codex_enabled", "refresh_at_enabled",
        "twofa_browser_fallback_enabled", "twofa_protocol_reauth_enabled",
        "auth_raw_context_enabled",
    }
    for key in bool_keys:
        if key in values and isinstance(values[key], str):
            values[key] = values[key].strip().lower() in {"1", "true", "yes", "on"}
    for key in (
        "password_driver", "plan_check_driver", "password_proxy_mode",
        "twofa_proxy_mode", "plan_check_proxy_mode", "live_check_proxy_mode",
        "refresh_at_proxy_mode", "codex_proxy_mode", "twofa_driver", "codex_driver",
        "protocol_version",
    ):
        if key in values and values[key] is not None:
            values[key] = str(values[key]).strip().lower()
    return values


def runtime_submission_snapshot(settings: Mapping[str, Any]) -> tuple[Any, Mapping[str, str]]:
    snapshot = runtime_config_snapshot()
    if snapshot is not None:
        return snapshot, RUNTIME_CONFIG_ALLOWLIST
    return legacy_runtime_snapshot(settings), tuple(RUNTIME_CONFIG_ALLOWLIST)


def runtime_execution_settings(
    settings: Mapping[str, Any],
    *,
    operation_logger: logging.Logger | None = None,
) -> tuple[Any, Mapping[str, str], dict[str, object]]:
    """捕获一次配置快照，并投影现有执行字段；日志沿用调用入口。"""
    snapshot, allowlist = runtime_submission_snapshot(settings)
    try:
        projected = task_gateway.normalize_config_snapshot(
            snapshot, allowlist=allowlist,
        )
    except (TypeError, ValueError):
        # 兼容回退仅保留调用方已加载的执行设置，不把未过滤对象作为执行设置。
        (operation_logger or logger).exception("读取账号操作 config snapshot 失败，使用当前执行设置")
        projected = dict(settings)
    return snapshot, allowlist, completion_settings_from_snapshot(
        projected, fallback=settings,
    )


def completion_deployment_unavailable(steps: set[str], settings: dict) -> dict | None:
    """补全只检查实际缺项，套餐与账号配置由协调器分别执行。"""
    from core.runtime.capabilities import account_setup_unavailable, browser_operation_unavailable

    unavailable = account_setup_unavailable(steps & {"password", "twofa"}, settings)
    if unavailable:
        return unavailable
    if "codex" in steps:
        children = settings.get("child_execution") or {}
        frozen = children.get("codex") if isinstance(children, Mapping) else None
        snapshot = dict(frozen) if isinstance(frozen, Mapping) else codex_operation_service._config_snapshot(driver_override=str(settings.get("codex_driver") or "same_as_registration"))
        unavailable = browser_operation_unavailable(snapshot.get("oauth_driver"))
        if unavailable:
            return unavailable
    if "refresh_at" in steps:
        children = settings.get("child_execution") or {}
        frozen = children.get("refresh_at") if isinstance(children, Mapping) else None
        return live_check_service.deployment_unavailable(force_refresh=True,
            **({"config_snapshot": dict(frozen)} if isinstance(frozen, Mapping) else {}))
    return None
