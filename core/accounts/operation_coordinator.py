# -*- coding: utf-8 -*-
"""账号配置与组合补全的提交协调，执行行为沿用既有领域 handler。"""
from __future__ import annotations
import logging
import uuid
from collections.abc import Mapping
from typing import Any
from core import db
from core.accounts import operation_settings
from core.operations import task_gateway as account_task_store
logger = logging.getLogger(__name__)

RUNTIME_SOURCE_SYSTEM = "webui_runtime"
COMPLETION_RESOURCE_FAMILY = "completion_coordinator"

# 保留旧私有名称兼容，持久身份与资源族仅在此定义。
_RUNTIME_SOURCE_SYSTEM = RUNTIME_SOURCE_SYSTEM
_COMPLETION_RESOURCE_FAMILY = COMPLETION_RESOURCE_FAMILY

# 兼容既有调用方；执行字段白名单仅由账号核心模块维护。
_RUNTIME_CONFIG_ALLOWLIST = operation_settings.RUNTIME_CONFIG_ALLOWLIST

def _runtime_config_snapshot() -> Any | None:
    """兼容旧入口，配置快照由账号核心模块提供。"""
    return operation_settings.runtime_config_snapshot()

def _legacy_runtime_snapshot(settings: Mapping[str, Any]) -> dict[str, Any]:
    """兼容旧入口，沿用账号核心模块的旧格式快照。"""
    return operation_settings.legacy_runtime_snapshot(settings)

def _completion_settings_from_snapshot(
    snapshot: Mapping[str, Any] | None,
    *,
    fallback: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """兼容旧入口，由账号核心模块投影补全设置。"""
    return operation_settings.completion_settings_from_snapshot(snapshot, fallback=fallback)

def _runtime_submission_snapshot(settings: Mapping[str, Any]) -> tuple[Any, Mapping[str, str]]:
    """兼容旧入口，由账号核心模块捕获提交快照。"""
    return operation_settings.runtime_submission_snapshot(settings)

def _runtime_execution_settings(
    settings: Mapping[str, Any],
) -> tuple[Any, Mapping[str, str], dict[str, object]]:
    """兼容旧入口，保留配置捕获时机与本入口日志。"""
    return operation_settings.runtime_execution_settings(settings, operation_logger=logger)

def _completion_deployment_unavailable(steps: set[str], settings: dict) -> dict | None:
    """兼容旧入口，补全能力组合由账号核心模块判断。"""
    return operation_settings.completion_deployment_unavailable(steps, settings)

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
