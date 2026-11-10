# -*- coding: utf-8 -*-
"""账号配置与组合补全的提交协调，执行行为沿用既有领域 handler。"""
from __future__ import annotations
import logging
import uuid
from collections.abc import Mapping
from typing import Any
from core import db
from core.codex import operation_service as codex_operation_service
from core.accounts.liveness import service as live_check_service
from core.operations import task_gateway
from core.operations import task_gateway as account_task_store
logger = logging.getLogger(__name__)

_RUNTIME_SOURCE_SYSTEM = "webui_runtime"
_COMPLETION_RESOURCE_FAMILY = "completion_coordinator"

# This is an execution allowlist, not a second configuration definition.  C
# owns the immutable snapshot and its uppercase schema keys; runtime stores
# only the choices needed by the setup/completion handlers.
_RUNTIME_CONFIG_ALLOWLIST = {
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

def _runtime_config_snapshot() -> Any | None:
    """Get C's atomic snapshot without defining or caching configuration."""
    try:
        from config import schema
    except ImportError:
        return None
    provider = getattr(schema, "non_sensitive_snapshot", None)
    return provider() if callable(provider) else None

def _legacy_runtime_snapshot(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Compatibility snapshot used only when C's provider is unavailable."""
    result = dict(settings)
    result["config_snapshot_revision"] = "legacy"
    return result

def _completion_settings_from_snapshot(
    snapshot: Mapping[str, Any] | None,
    *,
    fallback: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Project the already-captured execution shape into completion settings."""
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

def _runtime_submission_snapshot(settings: Mapping[str, Any]) -> tuple[Any, Mapping[str, str]]:
    snapshot = _runtime_config_snapshot()
    if snapshot is not None:
        return snapshot, _RUNTIME_CONFIG_ALLOWLIST
    return _legacy_runtime_snapshot(settings), tuple(_RUNTIME_CONFIG_ALLOWLIST)

def _runtime_execution_settings(
    settings: Mapping[str, Any],
) -> tuple[Any, Mapping[str, str], dict[str, object]]:
    """Capture C's snapshot and project only runtime execution settings."""
    snapshot, allowlist = _runtime_submission_snapshot(settings)
    try:
        projected = task_gateway.normalize_config_snapshot(
            snapshot, allowlist=allowlist,
        )
    except (TypeError, ValueError):
        # The legacy fallback is intentionally narrow. If a rolling provider
        # is malformed, keep the caller's already-loaded settings for the
        # current request but do not persist an unfiltered object.
        logger.exception("读取账号操作 config snapshot 失败，使用当前执行设置")
        projected = dict(settings)
    return snapshot, allowlist, _completion_settings_from_snapshot(
        projected, fallback=settings,
    )

def _completion_deployment_unavailable(steps: set[str], settings: dict) -> dict | None:
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

def enqueue_account_setup(
    account_id: int,
    *,
    snapshot_bundle=None,
    register_handlers=None,
    operation_logger=None,
    trigger: str = "manual_account_setup",
    steps: set[str] | tuple[str, ...] | list[str] | None = None,
    task_type: str | None = None,
    operation: str | None = None,
) -> dict:
    """Queue selected account configuration repair (legacy setup by default)."""
    try:
        account = db.get_account(int(account_id))
    except (TypeError, ValueError):
        account = None
    if account is None:
        return {"accepted": False, "error": "账号不存在"}
    email = str(account.get("email") or "").strip()
    if not email:
        return {"accepted": False, "error": "账号邮箱为空"}
    if db.account_is_deactivated(account):
        return {"accepted": False, "error": "账号已废号，不能补齐配置"}

    requested_steps = {"password", "plan_check", "twofa"} if steps is None else {
        str(item or "").strip().lower() for item in steps
    }
    requested_steps &= {"password", "plan_check", "twofa"}
    if not requested_steps:
        return {"accepted": False, "error": "没有可执行的账号配置步骤"}
    if requested_steps == {"password"} and str(operation or "").strip().lower() != "password_change":
        from core.accounts.completion import completion_plan

        from config.account import completion_settings

        base_settings = completion_settings()
        _raw_snapshot, _allowlist, execution_settings = (snapshot_bundle or _runtime_execution_settings(base_settings))
        password_plan = completion_plan(account, execution_settings)
        blocked = [
            item for item in password_plan.get("blocked") or []
            if item.get("step") == "password"
        ]
        if blocked:
            return {
                "accepted": False,
                "blocked": blocked,
                "plan": password_plan,
                "error": blocked[0].get("reason") or "账号密码补全当前不可用",
            }
    inferred_task_type = (
        "password_change" if str(operation or "").strip().lower() == "password_change"
        else "twofa_change" if str(operation or "").strip().lower() == "twofa_change"
        else "password_setup" if requested_steps == {"password"}
        else "twofa_setup" if requested_steps == {"twofa"}
        else "account_setup_retry"
    )
    task_name = str(task_type or inferred_task_type)
    task_trigger = str(trigger or "manual_account_setup")
    from config.account import completion_settings

    base_settings = completion_settings()
    snapshot, allowlist, settings = (snapshot_bundle or _runtime_execution_settings(base_settings))
    from core.runtime.capabilities import account_setup_unavailable

    unavailable = account_setup_unavailable(
        requested_steps, settings, force_twofa_change=str(operation or "").strip().lower() == "twofa_change",
        force_password_reset=str(operation or "").strip().lower() == "password_change",
    )
    if unavailable:
        return unavailable
    if register_handlers is not None:
        register_handlers()
    try:
        queued = account_task_store.submit_durable_operation(
            task_type=task_name,
            account_id=int(account.get("id") or 0) or None,
            email=email,
            trigger=task_trigger,
            source_system=_RUNTIME_SOURCE_SYSTEM,
            source_id=f"account-setup:{int(account['id'])}:{uuid.uuid4().hex}",
            resource_family="openai_interactive",
            data={
                "steps": sorted(requested_steps),
                "task_trigger": task_trigger,
                "force_password_reset": str(operation or "").strip().lower() == "password_change",
                "force_twofa_change": str(operation or "").strip().lower() == "twofa_change",
            },
            config_snapshot=snapshot,
            config_allowlist=allowlist,
        )
    except Exception as exc:
        (operation_logger or logger).exception("创建账号配置 durable task 失败：email=%s", email)
        return {"accepted": False, "error": f"任务实例创建失败：{type(exc).__name__}: {exc}"}
    return {
        **queued,
        "task_type": task_name,
        "account_id": int(account.get("id") or 0) or None,
        "email": email,
        "trigger": task_trigger,
        "steps": sorted(requested_steps),
    }

def enqueue_account_completion(
    account_id: int,
    *,
    snapshot_bundle=None,
    register_handlers=None,
    operation_logger=None,
    trigger: str = "manual_account_completion",
) -> dict:
    """Generate and queue the configured missing-account completion plan."""
    from core.accounts.completion import active_registration_job, completion_plan
    from config.account import completion_settings

    try:
        account = db.get_account(int(account_id))
    except (TypeError, ValueError):
        account = None
    if account is None:
        return {"accepted": False, "error": "账号不存在"}
    email = str(account.get("email") or "").strip()
    if not email:
        return {"accepted": False, "error": "账号邮箱为空"}
    if db.account_is_deactivated(account):
        return {"accepted": False, "error": "账号已废号，不能补全账号"}
    if active_registration_job(int(account["id"]), email):
        return {
            "accepted": False, "busy": True, "error_code": "registration_in_progress",
            "error": "该账号仍有注册任务正在执行，请等待结束后补全账号",
        }
    base_settings = completion_settings()
    snapshot, allowlist, settings = (snapshot_bundle or _runtime_execution_settings(base_settings))
    plan = completion_plan(account, settings)
    unavailable = _completion_deployment_unavailable(set(plan["missing_steps"]), settings)
    if unavailable:
        return {**unavailable, "plan": plan}
    # 一个步骤被账号能力明确阻塞时，仍允许执行其它未完成步骤。
    # 例如密码资格为 false，但 Authenticator 2FA 仍然可以补齐。
    if plan["blocked"] and not plan["missing_steps"]:
        return {"accepted": False, "blocked": plan["blocked"], "plan": plan, "error": plan["blocked"][0]["reason"]}
    if not plan["missing_steps"]:
        return {"accepted": False, "ready": True, "plan": plan, "message": "账号已满足当前补全配置"}
    task_trigger = str(trigger or "manual_account_completion")
    if register_handlers is not None:
        register_handlers()
    try:
        queued = account_task_store.submit_durable_operation(
            task_type="account_completion",
            account_id=int(account.get("id") or 0) or None,
            email=email,
            trigger=task_trigger,
            source_system=_RUNTIME_SOURCE_SYSTEM,
            source_id=f"account-completion:{int(account['id'])}:{uuid.uuid4().hex}",
            resource_family=_COMPLETION_RESOURCE_FAMILY,
            data={
                "planned_steps": list(plan["missing_steps"]),
                "configured_steps": list(plan["configured_steps"]),
                "required_steps": list(plan.get("required_steps") or plan["configured_steps"]),
                "blocked": list(plan["blocked"]),
                "task_trigger": task_trigger,
            },
            config_snapshot=snapshot,
            config_allowlist=allowlist,
        )
    except Exception as exc:
        (operation_logger or logger).exception("创建账号补全 durable task 失败：email=%s", email)
        return {"accepted": False, "error": f"任务实例创建失败：{type(exc).__name__}: {exc}"}
    return {
        **queued,
        "account_id": int(account["id"]),
        "email": email,
        "trigger": task_trigger,
        "plan": plan,
    }
