# -*- coding: utf-8 -*-
"""WebUI request context and explicit process lifecycle."""
from __future__ import annotations

import logging
import json
import os
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from flask import Flask

from core import (
    codex_operation_service,
    codex_retry_service,
    codex_token_refresh_service,
    db,
    deactivation_mail_service,
    extract_link_service,
    live_check_service,
    operation_task_store,
    plan_check_service,
    sms_provider,
)
from core.operations import task_gateway
from core.operations import task_gateway as account_task_store
from core.account_operation_executor import executor as _ACCOUNT_EXECUTOR

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
_RUNTIME_HANDLER_TYPES = frozenset({
    "account_setup_retry", "password_setup", "password_change",
    "twofa_setup", "twofa_change", "account_completion", "registration_resume",
})
_LEGACY_DURABLE_TASK_TYPES = frozenset({
    *_RUNTIME_HANDLER_TYPES,
    "live_check", "token_refresh", "plan_check", "deactivation_mail",
    "extract_link", "codex_token_refresh", "codex_retry",
})
_RUNTIME_HANDLER_LOCK = threading.RLock()
_RUNTIME_HANDLERS_REGISTERED = False


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


def _account_setup_readback(
    account_id: int,
    email: str,
    steps: set[str],
    result: Mapping[str, Any],
) -> tuple[bool, dict[str, bool]]:
    """Verify local business persistence before publishing remote confirmed."""
    account = db.get_account(int(account_id)) or db.get_account_by_email(email) or {}
    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    extra = raw_extra if isinstance(raw_extra, Mapping) else {}
    checks: dict[str, bool] = {}
    if "password" in steps:
        checks["password"] = bool(str(
            extra.get("account_password")
            or extra.get("login_password")
            or extra.get("registration_password")
            or account.get("password")
            or account.get("login_password")
            or account.get("registration_password")
            or ""
        ).strip())
    if "twofa" in steps:
        checks["twofa"] = bool(str(account.get("totp_secret") or "").strip()) and not bool(
            extra.get("totp_setup_pending")
        )
    if "plan_check" in steps:
        checks["plan_check"] = str(account.get("plan_check_status") or "").strip().lower() == "success"
    status = str(result.get("status") or "").strip().lower()
    if status == "deactivated":
        checks["account_status"] = str(account.get("account_status") or "").strip().lower() == "deactivated"
    return bool(checks) and all(checks.values()), checks


def _account_setup_receipt(
    account_id: int,
    email: str,
    steps: set[str],
    result: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Map an adapter result to the common remote receipt safety states."""
    status = str(result.get("status") or "").strip().lower()
    detail: dict[str, Any] = {
        "remote_response_received": True,
        "remote_result_confirmed": status in {"success", "completed", "deactivated"}
        or bool(result.get("ok")),
    }
    if status == "unsupported":
        return "rejected", detail
    if status not in {"success", "completed", "deactivated"} and not result.get("ok"):
        return "unknown", detail
    local_confirmed, checks = _account_setup_readback(
        account_id, email, steps, result,
    )
    detail.update({
        "local_business_writeback_confirmed": local_confirmed,
        "local_readback_confirmed": local_confirmed,
        "local_readback_checks": checks,
    })
    return ("confirmed" if local_confirmed else "local_commit_required"), detail


def _submit_native_account_setup_child(
    context: task_gateway.OperationHandlerContext,
    *,
    steps: set[str],
    task_trigger: str,
) -> dict[str, Any]:
    """Persist setup writes as a child before the coordinator becomes partial.

    A completion coordinator may have to wait for an AT/Codex child.  It must
    not also perform a password/MFA remote write in that coordinator Run: the
    shared terminal guard quite correctly treats a later partial/failure as a
    follow-up boundary.  The setup child owns that remote intent and its
    confirmed receipt; the parent only resumes with the steps that remain
    after the child has durably succeeded.
    """
    source_id = f"account-completion-setup:{context.task_id}:{context.run_id}"
    snapshot = context.config_snapshot
    allowlist: tuple[str, ...] | None = None
    if isinstance(snapshot, Mapping):
        # The context already contains the lower-case execution projection.
        # Re-projecting with the uppercase C schema mapping would silently
        # drop it, so use the projected names as the child input contract.
        allowlist = tuple(_RUNTIME_CONFIG_ALLOWLIST)
    queued = account_task_store.submit_durable_operation(
        task_type="account_setup_retry",
        account_id=int(context.account_id or 0) or None,
        email=context.email,
        trigger=f"{task_trigger}_account_setup",
        source_system=_RUNTIME_SOURCE_SYSTEM,
        source_id=source_id,
        idempotency_key=source_id,
        resource_family="openai_interactive",
        data={
            "steps": sorted(steps),
            "task_trigger": f"{task_trigger}_account_setup",
            "force_password_reset": "password" in steps and "change" in task_trigger.lower(),
            "force_twofa_change": "twofa" in steps and "change" in task_trigger.lower(),
        },
        config_snapshot=snapshot if isinstance(snapshot, Mapping) else None,
        config_allowlist=allowlist,
    )
    # A resource-family conflict can return only the active task/run ids.  A
    # dependency is keyed by source namespace/id, so resolve that read model
    # before making a parent partial; otherwise the parent would wait on a
    # numeric id that the dependency scanner cannot resolve.
    if queued.get("busy") and not queued.get("source_id") and queued.get("task_id"):
        try:
            existing = account_task_store.get_task(int(queued["task_id"]), include_events=False)
        except (LookupError, TypeError, ValueError):
            existing = None
        if isinstance(existing, Mapping):
            queued = {
                **queued,
                "source_system": existing.get("source_system"),
                "source_id": existing.get("source_id"),
                "task_type": existing.get("task_type"),
            }
    queued["_setup_child_source_id"] = source_id
    return queued


def _safe_operation_result(
    value: Any,
    *,
    default_message: str = "账号操作未完成",
) -> task_gateway.OperationResult:
    """Map service results to the durable terminal contract without secrets."""
    if isinstance(value, task_gateway.OperationResult):
        return value
    result = dict(value) if isinstance(value, Mapping) else {}
    status = str(result.get("status") or "").strip().lower()
    message = str(result.get("message") or default_message)
    summary = {
        key: result.get(key)
        for key in (
            "status", "ok", "message", "plan_check", "twofa_driver", "auth_source",
            "browser_opened", "account_status_persisted", "proxy_provider",
            "proxy_region", "proxy_mode", "credential_confirmed",
        )
        if key in result and result.get(key) is not None
    }
    if status in {"unknown", "request_unknown", "pending_confirmation", "attention_required"}:
        return task_gateway.OperationResult.request_unknown(message, summary)
    if status in {"success", "completed"} or bool(result.get("ok")):
        return task_gateway.OperationResult.success(summary, message=message)
    if status in {"cancelled", "stopped"}:
        return task_gateway.OperationResult.cancelled(message)
    if status == "deactivated":
        return task_gateway.OperationResult("deactivated", summary, message, message)
    if status == "unsupported":
        return task_gateway.OperationResult("unsupported", summary, message, message)
    return task_gateway.OperationResult.failed(message, summary)


class _NativeTaskLifecycle:
    """Legacy-service-shaped reporter backed by one durable Run context."""

    def __init__(self, context: task_gateway.OperationHandlerContext) -> None:
        self.context = context

    def start_task(self, _task_id: int | None, *, message: str = "开始执行") -> None:
        self.context.report(stage="plan", state="running", message=message)

    def append_event(self, _task_id: int | None, **event: Any) -> None:
        payload = dict(event)
        stage = str(payload.pop("stage", "event") or "event")
        message = str(payload.pop("message") or "处理中")
        state = payload.pop("state", None)
        level = str(payload.pop("level", None) or "INFO")
        event_type = payload.pop("event_type", None)
        detail = payload.pop("detail", None)
        if payload:
            detail = {**(dict(detail) if isinstance(detail, Mapping) else {}), **payload}
        self.context.report(
            stage=stage, message=message, level=level,
            state=state, event_type=event_type, detail=detail,
        )

    def finish_task(self, _task_id: int | None, **kwargs: Any) -> dict:
        status = str(kwargs.get("status") or "failed").strip().lower()
        summary = kwargs.get("result_summary")
        summary = dict(summary) if isinstance(summary, Mapping) else {}
        if str(summary.get("outcome") or "").lower() == "request_unknown":
            result = task_gateway.OperationResult.request_unknown(
                str(kwargs.get("message") or "远端请求结果待确认"), summary,
            )
        elif status == "cancelled":
            result = task_gateway.OperationResult.cancelled(
                str(kwargs.get("message") or "任务已取消"),
            )
        elif status == "attention_required":
            summary.update({"outcome": "request_unknown", "reconcile_required": True})
            result = task_gateway.OperationResult.request_unknown(
                str(kwargs.get("message") or "远端请求结果待确认"), summary,
            )
        else:
            result = task_gateway.OperationResult(
                status,
                summary,
                str(kwargs.get("message") or ""),
                str(kwargs.get("error") or "") or None,
            )
        return self.context.finish(result)

    def register_task_dependency(self, **kwargs: Any) -> dict:
        return operation_task_store.register_task_dependency(**kwargs)


def _run_codex_retry_worker(
    email: str,
    *,
    batch_label: str | None = None,
    clear_log: bool = True,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> None:
    """Execute one Codex retry; callers must reserve the account first."""
    codex_retry_service.run_worker(
        email,
        batch_label=batch_label,
        clear_log=clear_log,
        task_id=task_id,
        task_trigger=task_trigger,
    )


def _run_account_setup_worker(
    email: str,
    *,
    task_id: int,
    task_trigger: str,
    steps: set[str] | tuple[str, ...] | list[str] | None = None,
    force_password_reset: bool = False,
    force_twofa_change: bool = False,
) -> dict:
    """Execute selected account configuration repair without starting Codex OAuth."""
    return codex_retry_service.run_twofa_worker(
        email,
        task_id=task_id,
        task_trigger=task_trigger,
        steps=steps,
        force_password_reset=force_password_reset,
        force_twofa_change=force_twofa_change,
    )


def _run_account_completion_worker(
    email: str,
    *,
    account_id: int,
    task_id: int,
    task_trigger: str,
    planned_steps: list[str],
    settings: dict[str, object],
    initial_result_summary: dict[str, Any] | None = None,
    context: task_gateway.OperationHandlerContext | None = None,
    reservation_held: bool | None = None,
) -> task_gateway.OperationResult | None:
    """Execute a config-driven completion plan and record one coordinator task."""
    from core.account_completion_service import STEP_LABELS, completion_plan

    started = False
    result_summary: dict[str, Any] = dict(initial_result_summary or {})
    result_summary["planned_steps"] = list(planned_steps)
    task_store = _NativeTaskLifecycle(context) if context is not None else account_task_store
    reservation_held = (context is None) if reservation_held is None else bool(reservation_held)
    remote_write_started = False
    remote_receipt_state: str | None = None

    def release_parent_reservation() -> None:
        nonlocal reservation_held
        if reservation_held:
            # Compatibility callers may still hold the old process-local
            # reservation; native handlers never reserve it at enqueue time.
            codex_retry_service.release(email)
            reservation_held = False
        if context is not None:
            # A coordinator must release its DB lease before handing control
            # to a child that uses the openai_interactive resource family.
            context.release_lease()

    def register_child_dependency(
        *, child_source_system: str, child_source_id: object, payload: dict[str, Any],
    ) -> None:
        if not child_source_id:
            return
        try:
            operation_task_store.register_task_dependency(
                parent_source_system=(
                    getattr(context, "source_system", _RUNTIME_SOURCE_SYSTEM)
                    if context is not None else "account_action_tasks"
                ),
                parent_source_id=str(int(task_id)),
                child_source_system=child_source_system,
                child_source_id=str(child_source_id),
                dependency_type="account_completion",
                payload=payload,
            )
        except Exception:
            # The child remains independently durable.  Keep the parent
            # partial result visible and let the next reconciliation pass
            # recreate/repair the handoff rather than duplicating the child.
            logger.exception(
                "补全父子依赖写入失败：parent_task_id=%s child=%s:%s",
                task_id, child_source_system, child_source_id,
            )

    try:
        task_store.start_task(
            task_id,
            message=f"开始补全账号：{'、'.join(STEP_LABELS.get(step, step) for step in planned_steps)}",
        )
        started = True
        task_store.append_event(
            task_id,
            stage="plan",
            message="已按当前配置生成账号补全计划",
            detail={"steps": list(planned_steps)},
            state="success",
        )
        remaining = set(planned_steps)

        if "refresh_at" in remaining:
            account = db.get_account(int(account_id)) or {}
            # A queued completion task contains a plan snapshot, but the
            # destructive boundary is the actual refresh enqueue.  Recheck the
            # current switch and registration state immediately before it so a
            # config change cannot make an old task refresh a pending account.
            from config.account import completion_settings

            current_plan = completion_plan(account, settings)
            if "refresh_at" not in current_plan["missing_steps"]:
                if current_plan.get("registration_resume"):
                    stale_message = "账号注册尚未完成，旧补全计划已取消，请重新点击补全账号继续注册"
                else:
                    stale_message = "补全时刷新 AT 已关闭，旧补全计划已失效，请重新点击补全账号"
                result_summary["stale_plan"] = True
                task_store.finish_task(
                    task_id,
                    status="cancelled",
                    message=stale_message,
                    result_summary=result_summary,
                    validation_method="account_completion_plan",
                )
                return
            queued = live_check_service.enqueue_account_live_check(
                account_id=int(account_id),
                email=str(account.get("email") or email),
                trigger=f"{task_trigger}_refresh_at",
                proxy=None,
                force_refresh=True,
            )
            result_summary["refresh_at"] = {
                "accepted": bool(queued.get("accepted")),
                "busy": bool(queued.get("busy")),
                "task_id": queued.get("task_id"),
                "message": queued.get("error") or "刷新 AT 已入队",
            }
            task_store.append_event(
                task_id,
                stage="refresh_token",
                message="补全计划中的刷新 AT 已作为独立操作入队",
                detail={"accepted": bool(queued.get("accepted")), "busy": bool(queued.get("busy"))},
                state="success" if queued.get("accepted") or queued.get("busy") else "failed",
            )
            remaining.discard("refresh_at")
            if not queued.get("accepted") and not queued.get("busy"):
                raise RuntimeError(queued.get("error") or "刷新 AT 入队失败")
            if remaining:
                result_summary["deferred_steps"] = [step for step in planned_steps if step in remaining]
                task_store.append_event(
                    task_id,
                    stage="plan",
                    message="等待刷新 AT 完成后再执行其余补全步骤，请在刷新完成后重新点击补全账号",
                    detail={"deferred_steps": result_summary["deferred_steps"]},
                    state="skipped",
                )
            result_summary["awaiting_steps"] = ["refresh_at"]
            result_summary["continuation_steps"] = [
                step for step in planned_steps if step in remaining
            ]
            dependency_payload = {
                "account_id": int(account_id),
                "email": str(account.get("email") or email),
                "task_trigger": task_trigger,
                "remaining_steps": [step for step in planned_steps if step in remaining],
                "settings": dict(settings or {}),
                "result_summary": result_summary,
            }
            release_parent_reservation()
            task_store.finish_task(
                task_id,
                status="partial_success",
                message="刷新 AT 已提交，成功后系统将自动继续补全步骤",
                result_summary=result_summary,
                validation_method="account_completion_plan",
            )
            # Persist the parent partial state before making a fast child
            # eligible for the continuation scanner.  Otherwise a child that
            # completes during enqueue could race the parent's final write.
            register_child_dependency(
                child_source_system=str(
                    queued.get("source_system") or "account_action_tasks"
                ),
                child_source_id=queued.get("source_id") or queued.get("task_id"),
                payload=dependency_payload,
            )
            return context.last_result if context is not None else None

        setup_steps = remaining & {"password", "plan_check", "twofa"}
        if setup_steps:
            if context is not None:
                queued_setup = _submit_native_account_setup_child(
                    context,
                    steps=set(setup_steps),
                    task_trigger=task_trigger,
                )
                result_summary["account_setup"] = {
                    "accepted": bool(queued_setup.get("accepted")),
                    "busy": bool(queued_setup.get("busy")),
                    "task_id": queued_setup.get("task_id"),
                    "run_id": queued_setup.get("run_id"),
                    "message": queued_setup.get("error") or "账号配置已入队",
                }
                if not queued_setup.get("accepted") and not queued_setup.get("busy"):
                    raise RuntimeError(queued_setup.get("error") or "账号配置入队失败")
                child_source_id = str(queued_setup.get("source_id") or "")
                setup_child_matches = child_source_id == str(
                    queued_setup.get("_setup_child_source_id") or ""
                )
                if queued_setup.get("busy") and not child_source_id:
                    # No durable blocker could be resolved. Requeue the
                    # coordinator attempt; do not publish a partial state that
                    # has no recoverable dependency edge.
                    raise task_gateway.OperationLeaseUnavailable(
                        "账号配置 child 暂时被占用，等待下一轮 durable dispatcher"
                    )
                if setup_child_matches:
                    remaining -= setup_steps
                result_summary["awaiting_steps"] = ["account_setup"]
                result_summary["continuation_steps"] = [
                    step for step in planned_steps if step in remaining
                ]
                task_store.append_event(
                    task_id,
                    stage="account_setup",
                    message=(
                        "账号密码/2FA 已作为独立 durable child 入队，成功后自动继续"
                    ),
                    detail={
                        "accepted": bool(queued_setup.get("accepted")),
                        "busy": bool(queued_setup.get("busy")),
                        "task_id": queued_setup.get("task_id"),
                        "blocked_by_existing": not setup_child_matches,
                    },
                    state="success" if queued_setup.get("accepted") or queued_setup.get("busy") else "failed",
                )
                dependency_payload = {
                    "account_id": int(account_id),
                    "email": email,
                    "task_trigger": task_trigger,
                    "remaining_steps": [step for step in planned_steps if step in remaining],
                    "settings": dict(settings or {}),
                    "result_summary": result_summary,
                }
                release_parent_reservation()
                task_store.finish_task(
                    task_id,
                    status="partial_success",
                    message="账号配置已提交，成功后系统将自动继续补全步骤",
                    result_summary=result_summary,
                    validation_method="account_completion_plan",
                )
                register_child_dependency(
                    child_source_system=str(
                        queued_setup.get("source_system") or _RUNTIME_SOURCE_SYSTEM
                    ),
                    child_source_id=child_source_id or queued_setup.get("task_id"),
                    payload=dependency_payload,
                )
                return context.last_result
            task_store.append_event(
                task_id,
                stage="account_setup",
                message=f"开始执行账号配置步骤：{'、'.join(STEP_LABELS[step] for step in planned_steps if step in setup_steps)}",
                detail={"steps": sorted(setup_steps)},
                state="running",
            )
            if context is not None:
                remote_write_started = True
                context.remote_request_started(
                    "account_setup",
                    intent_kind="remote_write",
                    request_id=f"account-setup:{context.run_id}",
                    detail={"steps": sorted(setup_steps), "checkpoint": "setup_dispatch"},
                )
            try:
                setup_result = codex_retry_service.run_twofa_worker(
                    email,
                    clear_log=False,
                    # The service remains a business adapter. ``0`` prevents
                    # its legacy task/event writer from creating a second
                    # logical task; the durable context owns lifecycle data.
                    task_id=0 if context is not None else task_id,
                    task_trigger=task_trigger,
                    steps=setup_steps,
                    manage_task=False,
                    twofa_driver_override=str(settings.get("twofa_driver") or "auto"),
                    password_driver_override=str(settings.get("password_driver") or "roxy"),
                    plan_driver_override=str(settings.get("plan_check_driver") or "protocol"),
                )
            except Exception:
                if context is not None and remote_write_started and remote_receipt_state is None:
                    try:
                        context.remote_request_receipt(
                            outcome="unknown",
                            action="account_setup",
                            request_id=f"account-setup:{context.run_id}",
                            detail={"remote_response_received": False},
                        )
                        remote_receipt_state = "unknown"
                    except Exception:
                        logger.exception(
                            "账号配置 remote intent 未能写入 unknown：run_id=%s",
                            context.run_id,
                        )
                raise
            if context is not None and remote_write_started:
                remote_receipt_state, receipt_detail = _account_setup_receipt(
                    int(account_id), email, set(setup_steps), setup_result,
                )
                context.remote_request_receipt(
                    outcome=remote_receipt_state,
                    action="account_setup",
                    request_id=f"account-setup:{context.run_id}",
                    detail=receipt_detail,
                )
                if remote_receipt_state not in {"confirmed", "rejected"}:
                    result_summary.update({
                        "outcome": "request_unknown",
                        "reconcile_required": True,
                        "remote_receipt_state": remote_receipt_state,
                        "local_readback_checks": receipt_detail.get("local_readback_checks") or {},
                    })
                    task_store.finish_task(
                        task_id,
                        status="attention_required",
                        message="账号配置本地写回仍待确认，禁止自动重做",
                        error="remote_write receipt 未达到 confirmed",
                        result_summary=result_summary,
                        validation_method="account_completion_plan",
                    )
                    return context.last_result if context is not None else None
            result_summary["account_setup"] = {
                "ok": bool(setup_result.get("ok")),
                "status": setup_result.get("status"),
                "message": setup_result.get("message"),
                "plan_check": setup_result.get("plan_check"),
                "twofa_driver": setup_result.get("twofa_driver"),
                "auth_source": setup_result.get("auth_source"),
                "browser_opened": setup_result.get("browser_opened"),
                "account_status_persisted": setup_result.get("account_status_persisted"),
            }
            setup_status = str(setup_result.get("status") or "").lower()
            if setup_status == "deactivated":
                task_store.finish_task(
                    task_id,
                    status="deactivated",
                    message="账号已废号，已停止补全",
                    error=str(setup_result.get("message") or "account_deactivated"),
                    result_summary=result_summary,
                    validation_method="account_completion_plan",
                )
                return
            if setup_status == "unsupported":
                task_store.finish_task(
                    task_id,
                    status="unsupported",
                    message="账号配置包含当前不支持的步骤",
                    error=str(setup_result.get("message") or "账号配置步骤当前不支持"),
                    result_summary=result_summary,
                    validation_method="account_completion_plan",
                )
                return
            if not setup_result.get("ok"):
                raise RuntimeError(setup_result.get("message") or "账号配置步骤未完成")
            plan_outcome = setup_result.get("plan_check") or {}
            remaining -= setup_steps
            if "plan_check" in setup_steps and not bool(plan_outcome.get("ok")):
                # 套餐查询依赖独立的 AT/接口状态；它失败时不应把已经完成
                # 的密码或 2FA 重新标成整任务失败。保留待处理步骤，供后续
                # 单独重试套餐查询。
                result_summary["pending_steps"] = ["plan_check"]
                result_summary["plan_check_error"] = plan_outcome.get("message") or "套餐补全未完成"
                task_store.append_event(
                    task_id,
                    stage="plan_check",
                    message="密码/2FA 已完成，套餐查询待后续单独重试",
                    level="WARNING",
                    detail={"error": result_summary["plan_check_error"]},
                    state="skipped",
                )

        codex_dependency_payload: dict[str, Any] | None = None
        codex_child_task_id: object | None = None
        if "codex" in remaining:
            task_store.append_event(
                task_id,
                stage="codex",
                message="开始提交 Codex OAuth 独立操作",
                state="running",
            )
            queued = codex_operation_service.submit(
                email,
                trigger=f"{task_trigger}_codex",
                driver=str(settings.get("codex_driver") or "same_as_registration"),
            )
            result_summary["codex"] = {
                "accepted": bool(queued.get("accepted")),
                "busy": bool(queued.get("busy")),
                "task_id": queued.get("task_id"),
                "run_id": queued.get("run_id"),
                "message": queued.get("error") or "Codex OAuth 已入队",
            }
            task_store.append_event(
                task_id,
                stage="codex",
                message="Codex OAuth 已作为独立操作入队" if queued.get("accepted") or queued.get("busy") else "Codex OAuth 入队失败",
                detail={"accepted": bool(queued.get("accepted")), "busy": bool(queued.get("busy"))},
                state="success" if queued.get("accepted") or queued.get("busy") else "failed",
            )
            if not queued.get("accepted") and not queued.get("busy"):
                raise RuntimeError(queued.get("error") or "Codex OAuth 入队失败")
            remaining.discard("codex")
            result_summary["awaiting_steps"] = ["codex"]
            result_summary["continuation_steps"] = [
                step for step in planned_steps if step in remaining
            ]
            codex_child_task_id = queued.get("task_id")
            codex_dependency_payload = {
                "account_id": int(account_id),
                "email": email,
                "task_trigger": task_trigger,
                "remaining_steps": [step for step in planned_steps if step in remaining],
                "settings": dict(settings or {}),
                "result_summary": result_summary,
            }
            release_parent_reservation()

        pending_steps = set(result_summary.get("pending_steps") or [])
        result_summary["completed_steps"] = [
            step for step in planned_steps
            if step not in remaining and step not in pending_steps
        ]
        task_status = "partial_success" if (
            result_summary.get("pending_steps") or result_summary.get("awaiting_steps")
        ) else "success"
        task_store.finish_task(
            task_id,
            status=task_status,
            message=(
                "补全步骤已完成，等待子任务成功后系统自动继续"
                if result_summary.get("awaiting_steps")
                else "密码/2FA 已完成，套餐查询待后续单独重试"
                if task_status == "partial_success"
                else "补全计划已提交，独立操作将在任务中心继续执行"
            ),
            result_summary=result_summary,
            validation_method="account_completion_plan",
        )
        if codex_dependency_payload is not None:
            # As with refresh_at, the parent partial result is durable before
            # a terminal child can wake and execute the continuation.
            register_child_dependency(
                child_source_system=str(queued.get("source_system") or "native_operations"),
                child_source_id=queued.get("source_id") or queued.get("task_id") or codex_child_task_id,
                payload=codex_dependency_payload,
            )
        return context.last_result if context is not None else None
    except Exception as exc:
        result_summary["error"] = f"{type(exc).__name__}: {str(exc)[:220]}"
        if (
            context is not None
            and remote_write_started
            and remote_receipt_state != "rejected"
        ):
            result_summary.update({
                "outcome": "request_unknown",
                "reconcile_required": True,
            })
            task_store.finish_task(
                task_id,
                status="attention_required",
                message="账号配置远端结果待核验，禁止自动重做",
                error=result_summary["error"],
                result_summary=result_summary,
                validation_method="account_completion_plan",
            )
            logger.exception("账号补全远端写入结果待核验：email=%s", email)
            return context.last_result if context is not None else None
        task_store.finish_task(
            task_id,
            status="failed",
            message="账号补全计划执行失败",
            error=result_summary["error"],
            result_summary=result_summary,
            validation_method="account_completion_plan",
        )
        logger.exception("账号补全失败：email=%s", email)
        return context.last_result if context is not None else None
    finally:
        # 账号配置子步骤在 manage_task=False 时会保留租约，直到这里完成；
        # handoff 分支已经在提交 child 前释放，避免父任务占住 semaphore。
        release_parent_reservation()


def _native_task_data(context: task_gateway.OperationHandlerContext) -> dict[str, Any]:
    data = context.run.get("data")
    return dict(data) if isinstance(data, Mapping) else {}


def _finish_native_context(
    context: task_gateway.OperationHandlerContext,
    result: task_gateway.OperationResult,
) -> task_gateway.OperationResult:
    if not context.finished:
        context.finish(result)
    return context.last_result or result


def _handle_native_account_setup(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    data = _native_task_data(context)
    steps = {
        str(item or "").strip().lower()
        for item in data.get("steps") or []
    } & {"password", "plan_check", "twofa"}
    if not steps:
        steps = {
            "password", "plan_check", "twofa",
        }
    settings = _completion_settings_from_snapshot(context.config_snapshot)
    task_trigger = str(data.get("task_trigger") or context.run.get("trigger") or "manual_account_setup")
    force_password_reset = bool(data.get("force_password_reset"))
    force_twofa_change = bool(data.get("force_twofa_change"))
    context.report(
        stage="account_setup", state="running",
        message=f"开始执行账号配置步骤：{ '、'.join(sorted(steps)) }",
        detail={"steps": sorted(steps)},
    )
    request_id = f"account-setup:{context.run_id}"
    with context.lease(resource_family="openai_interactive"):
        context.remote_request_started(
            "account_setup",
            intent_kind="remote_write",
            request_id=request_id,
            detail={"steps": sorted(steps), "checkpoint": "setup_dispatch"},
        )
        try:
            result = codex_retry_service.run_twofa_worker(
                context.email,
                clear_log=False,
                target_log_path=context.run.get("log_file"),
                task_id=0,
                task_trigger=task_trigger,
                steps=steps,
                manage_task=False,
                twofa_driver_override=str(settings.get("twofa_driver") or "auto"),
                password_driver_override=str(settings.get("password_driver") or "roxy"),
                plan_driver_override=str(settings.get("plan_check_driver") or "protocol"),
                force_password_reset=force_password_reset,
                force_twofa_change=force_twofa_change,
            )
        except Exception as exc:
            try:
                context.remote_request_receipt(
                    outcome="unknown", action="account_setup", request_id=request_id,
                    detail={"remote_response_received": False},
                )
            except Exception:
                logger.exception("账号配置 remote receipt 写入失败：run_id=%s", context.run_id)
            return _finish_native_context(
                context,
                task_gateway.OperationResult.request_unknown(
                    f"账号配置执行异常，远端结果待核验：{type(exc).__name__}",
                    {"error_type": type(exc).__name__},
                ),
            )
        normalized = _safe_operation_result(result, default_message="账号配置未完成")
        receipt_state, receipt_detail = _account_setup_receipt(
            int(context.account_id or 0), context.email, steps, result,
        )
        context.remote_request_receipt(
            outcome=receipt_state,
            action="account_setup",
            request_id=request_id,
            detail=receipt_detail,
        )
        if receipt_state not in {"confirmed", "rejected"}:
            normalized = task_gateway.OperationResult.request_unknown(
                str((result or {}).get("message") or "账号配置远端结果待核验"),
                {
                    "status": str((result or {}).get("status") or "failed"),
                    "remote_receipt_state": receipt_state,
                    "local_readback_checks": receipt_detail.get("local_readback_checks") or {},
                },
            )
        return _finish_native_context(context, normalized)


def _handle_native_account_completion(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    data = _native_task_data(context)
    continuation = data.get("continuation_payload")
    continuation = dict(continuation) if isinstance(continuation, Mapping) else {}
    planned_steps = [
        str(step or "").strip().lower()
        for step in (
            continuation.get("remaining_steps")
            or data.get("planned_steps")
            or []
        )
        if str(step or "").strip()
    ]
    settings = _completion_settings_from_snapshot(
        context.config_snapshot,
        fallback=continuation.get("settings") if isinstance(continuation.get("settings"), Mapping) else None,
    )
    if not planned_steps:
        account = db.get_account(int(context.account_id or 0)) or {}
        from core.account_completion_service import completion_plan

        planned_steps = list(completion_plan(account, settings).get("missing_steps") or [])
    initial_summary = continuation.get("result_summary")
    initial_summary = dict(initial_summary) if isinstance(initial_summary, Mapping) else None
    worker_kwargs = {
        "email": context.email,
        "account_id": int(context.account_id or 0),
        "task_id": context.task_id,
        "task_trigger": str(data.get("task_trigger") or context.run.get("trigger") or "manual_account_completion"),
        "planned_steps": planned_steps,
        "settings": settings,
        "initial_result_summary": initial_summary,
        "context": context,
        "reservation_held": False,
    }
    if set(planned_steps) & {"password", "plan_check", "twofa"}:
        with context.lease(resource_family="openai_interactive"):
            _run_account_completion_worker(**worker_kwargs)
    else:
        _run_account_completion_worker(**worker_kwargs)
    if context.last_result is not None:
        return context.last_result
    return _finish_native_context(
        context,
        task_gateway.OperationResult.failed("账号补全 handler 未报告终态"),
    )


def _handle_native_registration_resume(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    data = _native_task_data(context)
    remote_state = str(
        data.get("remote_account_state") or data.get("registration_remote_account_state") or ""
    ).strip().lower()
    if remote_state in {"request_unknown", "unknown", "pending_confirmation"}:
        return _finish_native_context(
            context,
            task_gateway.OperationResult.request_unknown(
                "注册远端账号状态待核验，禁止盲目继续注册",
                {"remote_account_state": remote_state},
            ),
        )
    source_job_id = int(data.get("source_job_id") or 0)
    if not source_job_id:
        return _finish_native_context(
            context,
            task_gateway.OperationResult.failed("缺少可继续的原注册任务"),
        )
    context.report(
        stage="preflight", state="running",
        message="准备继续原注册任务",
        detail={"source_job_id": source_job_id},
    )
    try:
        from core import registration_service

        resumed = registration_service.retry_job(source_job_id)
    except Exception as exc:
        return _finish_native_context(
            context,
            task_gateway.OperationResult.failed(
                f"继续注册任务入队异常：{type(exc).__name__}",
                {"source_job_id": source_job_id},
            ),
        )
    if not resumed.get("ok"):
        return _finish_native_context(
            context,
            task_gateway.OperationResult.failed(
                str(resumed.get("error") or "继续注册任务未能入队"),
                {"source_job_id": source_job_id},
            ),
        )
    job = resumed.get("job") if isinstance(resumed.get("job"), Mapping) else {}
    result = task_gateway.OperationResult.success(
        {
            "source_job_id": source_job_id,
            "job_id": job.get("id"),
            "created": bool(resumed.get("created")),
        },
        message=str(resumed.get("message") or "已继续原注册任务"),
    )
    return _finish_native_context(context, result)


def _retry_native_runtime_task(task: Mapping[str, Any]) -> dict[str, Any]:
    if str(task.get("source_system") or "") != _RUNTIME_SOURCE_SYSTEM:
        return {"accepted": False, "busy": False, "error": "任务来源不属于 WebUI runtime"}
    if task_gateway.operation_requires_reconciliation(task):
        return {
            "accepted": False,
            "busy": False,
            "reconcile_required": True,
            "error": "远端结果待核验，禁止盲目重试",
        }
    if str(task.get("status") or "").lower() in {
        "queued", "running", "cancelling", "settling", "stopping", "waiting",
    }:
        return {"accepted": False, "busy": True, "error": "任务仍在执行"}
    try:
        run = operation_task_store.retry_runtime_task(
            int(task["id"]),
            trigger="manual_retry",
            data={"retry_action": "manual_retry"},
        )
    except (LookupError, ValueError) as exc:
        return {"accepted": False, "busy": False, "error": str(exc)}
    task_gateway.notify_dispatch()
    return {
        "accepted": True,
        "busy": False,
        "reused": False,
        "task_id": int(task["id"]),
        "run_id": int(run["id"]),
        "account_id": int(task.get("account_id") or 0) or None,
        "email": str(task.get("email_snapshot") or ""),
        "status": "queued",
        "source_system": _RUNTIME_SOURCE_SYSTEM,
    }


def _cancel_native_runtime_task(task: Mapping[str, Any]) -> dict[str, Any]:
    if str(task.get("source_system") or "") != _RUNTIME_SOURCE_SYSTEM:
        return {"ok": False, "error": "任务来源不属于 WebUI runtime"}
    active = next(
        (
            run for run in reversed(task.get("runs") or [])
            if str(run.get("status") or "") in {
                "queued", "running", "cancelling", "settling", "stopping", "waiting",
            }
        ),
        None,
    )
    if not active:
        return {"ok": True, "running": False, "state": "empty", "message": "任务没有活跃 attempt"}
    try:
        run = operation_task_store.request_run_cancel(
            int(active["id"]), reason="用户手动停止 WebUI durable operation",
        )
    except LookupError as exc:
        return {"ok": False, "error": str(exc)}
    task_gateway.notify_dispatch()
    return {
        "ok": True,
        "run_id": int(active["id"]),
        "running": str(run.get("status") or "") != "cancelled",
        "state": str(run.get("status") or "cancelling"),
        "message": "已记录停止请求，任务将在安全检查点收口",
    }


def _register_runtime_handlers() -> None:
    global _RUNTIME_HANDLERS_REGISTERED
    with _RUNTIME_HANDLER_LOCK:
        registered = set(task_gateway.registered_dispatch_types())
        if _RUNTIME_HANDLERS_REGISTERED and _RUNTIME_HANDLER_TYPES <= registered:
            return
        for task_type in sorted(_RUNTIME_HANDLER_TYPES):
            if task_type == "registration_resume":
                handler = _handle_native_registration_resume
            elif task_type == "account_completion":
                handler = _handle_native_account_completion
            else:
                handler = _handle_native_account_setup
            task_gateway.register_operation_handler(
                task_type,
                handler,
                source_systems=(_RUNTIME_SOURCE_SYSTEM,),
                config_allowlist=_RUNTIME_CONFIG_ALLOWLIST,
                retry_handler=_retry_native_runtime_task,
                cancel_handler=_cancel_native_runtime_task,
            )
        _RUNTIME_HANDLERS_REGISTERED = True


def _legacy_recovery_exclusions(
    task_types: set[str] | frozenset[str] | tuple[str, ...],
    *,
    legacy_source_systems: tuple[str, ...] | list[str] | set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Return row-level fences for legacy recovery.

    A category-wide ``has_active`` bit is unsafe during the migration: an
    active native Run for account A must not leave an unrelated legacy row for
    account B running forever.  A failed safety query deliberately returns
    ``skip_all`` so startup cannot clear a durable worker while its ownership
    is uncertain.
    """
    normalized = tuple(sorted({str(item).strip() for item in task_types if str(item).strip()}))
    target_source_systems = None if legacy_source_systems is None else {
        str(item).strip() for item in legacy_source_systems if str(item).strip()
    }
    empty = {
        "skip_all": False,
        "account_ids": [],
        "source_ids": [],
        "source_fences": [],
    }
    try:
        result = operation_task_store.list_active_runtime_recovery_exclusions(
            task_types=normalized,
        )
    except AttributeError:
        # Keep a safe rolling-upgrade fallback for an older coordinator facade.
        # It may over-skip, but it can never clear a row belonging to an active
        # durable operation.
        try:
            active = operation_task_store.has_active_runtime_operations(task_types=normalized)
        except Exception:
            logger.exception("无法确认 durable Run 是否活跃，跳过本次 legacy recovery")
            return {**empty, "skip_all": True}
        return {
            "skip_all": bool(active),
            "account_ids": [],
            "source_ids": [],
            "source_fences": [],
        }
    except Exception:
        # A failed safety query must not let the old recovery code clear a
        # durable worker that may be alive in another process.
        logger.exception("无法读取 durable Run 行级恢复排除项，跳过本次 legacy recovery")
        return {**empty, "skip_all": True}

    if not isinstance(result, Mapping):
        logger.error("durable Run 行级恢复排除项格式无效，跳过本次 legacy recovery")
        return {**empty, "skip_all": True}
    try:
        account_ids = sorted({int(item) for item in (result.get("account_ids") or ())})
        raw_fences = result.get("source_fences") or ()
        source_fences: list[dict[str, str]] = []
        for item in raw_fences:
            if not isinstance(item, Mapping):
                raise ValueError("source fence 不是对象")
            source_system = str(item.get("source_system") or "").strip()
            source_id = str(item.get("source_id") or "").strip()
            if not source_system or not source_id:
                raise ValueError("source fence 缺少 namespace/id")
            source_fences.append({"source_system": source_system, "source_id": source_id})
        source_fences = sorted(
            source_fences,
            key=lambda item: (item["source_system"], item["source_id"]),
        )
        if target_source_systems is None:
            # Callers that only need a boolean must not receive an
            # unqualified id list that can later be applied to another table.
            source_ids = []
        else:
            source_ids = sorted({
                item["source_id"] for item in source_fences
                if item["source_system"] in target_source_systems
            })
            # A non-empty legacy source_ids response without namespaces is an
            # unsafe partial rollout. Do not clear any legacy category when
            # the exact source fence cannot be reconstructed.
            if not source_fences and result.get("source_ids"):
                return {**empty, "skip_all": True}
    except (TypeError, ValueError):
        logger.exception("durable Run 行级恢复排除项包含非法标识，跳过本次 legacy recovery")
        return {**empty, "skip_all": True}
    if account_ids or source_fences:
        logger.info(
            "按 durable active Run 行级保留 legacy 状态：types=%s accounts=%s source_fences=%s",
            list(normalized), account_ids, source_fences,
        )
    return {
        "skip_all": False,
        "account_ids": account_ids,
        "source_ids": source_ids,
        "source_fences": source_fences,
    }


def _legacy_recovery_allowed(task_types: set[str] | frozenset[str] | tuple[str, ...]) -> bool:
    """Compatibility predicate; startup uses row-level exclusions directly."""
    exclusions = _legacy_recovery_exclusions(task_types)
    return (
        not exclusions["skip_all"]
        and not exclusions["account_ids"]
        and not exclusions["source_ids"]
        and not exclusions.get("source_fences")
    )


def _handle_ready_completion_dependency(dependency: dict) -> None:
    """Run one already-claimed completion continuation in the common pool.

    ``task_gateway`` is the sole owner of the ready->running claim. This
    function is intentionally a worker body and never claims again.
    """
    dependency_id = int(dependency.get("id") or 0)
    if not dependency_id:
        return
    claimed = dependency
    payload = claimed.get("payload") if isinstance(claimed.get("payload"), dict) else {}
    parent_system = str(claimed.get("parent_source_system") or "")
    parent_id = str(claimed.get("parent_source_id") or "")
    child_status = str(claimed.get("child_status") or "").lower()
    try:
        if parent_system == _RUNTIME_SOURCE_SYSTEM:
            parent_task_id = int(parent_id)
            parent = operation_task_store.get_task(parent_task_id, include_events=False) or {}
            if str(parent.get("status") or "").lower() in {"cancelled", "cancelling", "stopped"}:
                operation_task_store.complete_task_dependency(dependency_id, success=True)
                return
            if child_status != "success":
                updated = operation_task_store.apply_task_dependency_result(
                    parent_source_system=parent_system,
                    parent_source_id=parent_id,
                    child_status=child_status or "unknown",
                    child_result=claimed.get("child_result") if isinstance(claimed.get("child_result"), dict) else {},
                )
                if updated is None:
                    raise LookupError("补全父任务不存在")
                operation_task_store.complete_task_dependency(dependency_id, success=True)
                return
            continuation_payload = {
                "remaining_steps": [
                    str(step) for step in payload.get("remaining_steps") or []
                ],
                "settings": dict(payload.get("settings") or {}),
                "result_summary": dict(payload.get("result_summary") or {}),
                "child_source_system": str(claimed.get("child_source_system") or ""),
                "child_source_id": str(claimed.get("child_source_id") or ""),
            }
            run = operation_task_store.retry_runtime_task(
                parent_task_id,
                trigger="dependency_resume",
                data={
                    "retry_action": "dependency_resume",
                    "continuation_payload": continuation_payload,
                },
            )
            task_gateway.notify_dispatch()
            operation_task_store.complete_task_dependency(dependency_id, success=True)
            logger.info(
                "补全父任务已由持久依赖续接：parent_task_id=%s run_id=%s",
                parent_task_id, run.get("id"),
            )
            return
        if parent_system != "account_action_tasks":
            operation_task_store.complete_task_dependency(
                dependency_id, success=False, error="暂不支持该父任务来源",
            )
            return
        parent_task_id = int(parent_id)
        if child_status != "success":
            message = "子任务未成功，补全父任务保留待对账状态"
            account_task_store.append_event(
                parent_task_id,
                stage="plan",
                level="WARNING",
                message=message,
                detail={"child_status": child_status, "child_task_id": claimed.get("child_source_id")},
                state="skipped",
            )
            account_task_store.finish_task(
                parent_task_id,
                status="partial_success",
                message=message,
                error=f"child_status={child_status or 'unknown'}",
                result_summary={
                    "awaiting_steps": payload.get("remaining_steps") or [],
                    "child_status": child_status or "unknown",
                    "child_result": claimed.get("child_result") or {},
                },
                validation_method="account_completion_dependency",
            )
            operation_task_store.complete_task_dependency(dependency_id, success=True)
            return

        email = str(payload.get("email") or "").strip()
        if not email:
            raise ValueError("父任务续接缺少 email")
        if not codex_retry_service.reserve(email):
            # Return to the durable queue with storage-level backoff. A Timer
            # per busy dependency would create an unbounded thread population
            # during a long-running account operation.
            operation_task_store.complete_task_dependency(
                dependency_id, success=False, error="账号仍被其它操作占用",
            )
            account_task_store.notify_dependency_ready(claimed)
            return
        _run_account_completion_worker(
            email,
            account_id=int(payload.get("account_id") or 0),
            task_id=parent_task_id,
            task_trigger=str(payload.get("task_trigger") or "manual_account_completion"),
            planned_steps=[str(step) for step in payload.get("remaining_steps") or []],
            settings=dict(payload.get("settings") or {}),
            initial_result_summary=dict(payload.get("result_summary") or {}),
        )
        operation_task_store.complete_task_dependency(dependency_id, success=True)
    except Exception as exc:
        logger.exception("补全父任务自动续接失败：dependency_id=%s", dependency_id)
        operation_task_store.complete_task_dependency(
            dependency_id, success=False, error=f"{type(exc).__name__}: {exc}",
        )
        account_task_store.notify_dependency_ready(claimed)


def _submit_ready_completion_dependency(dependency: dict):
    """Submit a claimed dependency without executing it on the scanner.

    ``try_submit`` is deliberately non-blocking. If the account-operation
    budget is full, the claimed row is returned to the durable ready queue and
    the next scanner tick can reclaim it after the storage backoff expires.
    """
    dependency_id = int(dependency.get("id") or 0)
    if not dependency_id:
        return None
    try:
        future = _ACCOUNT_EXECUTOR.try_submit(
            _handle_ready_completion_dependency,
            dict(dependency),
        )
    except Exception as exc:
        logger.exception("补全依赖提交到共享 executor 失败：dependency_id=%s", dependency_id)
        operation_task_store.complete_task_dependency(
            dependency_id,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        account_task_store.notify_dependency_ready(dependency)
        return None
    if future is None:
        operation_task_store.complete_task_dependency(
            dependency_id,
            success=False,
            error="账号操作共享并发预算已满",
        )
        account_task_store.notify_dependency_ready(dependency)
    return future


@dataclass
class WebUIContext:
    """Explicit dependencies shared by route groups."""

    app: Flask
    logger: logging.Logger
    prepared_downloads: dict[str, dict[str, Any]] = field(default_factory=dict)

    def put_prepared_download(
        self,
        content: bytes,
        filename: str,
        mimetype: str = "application/zip",
    ) -> str:
        now = time.time()
        # Prune short-lived downloads before adding the next one.
        for key, value in list(self.prepared_downloads.items()):
            if now - float(value.get("created_at") or 0) > 600:
                self.prepared_downloads.pop(key, None)
        download_id = uuid.uuid4().hex
        self.prepared_downloads[download_id] = {
            "content": bytes(content),
            "filename": filename,
            "mimetype": mimetype,
            "created_at": now,
        }
        return download_id

    def enqueue_codex_retry(self, email: str, *, trigger: str = "manual") -> dict:
        """Compatibility name for the unified Codex operation coordinator."""
        return codex_operation_service.submit(email, trigger=trigger)

    def enqueue_account_setup(
        self,
        account_id: int,
        *,
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
        if str(account.get("account_status") or "").lower() == "deactivated":
            return {"accepted": False, "error": "账号已废号，不能补齐配置"}

        requested_steps = {"password", "plan_check", "twofa"} if steps is None else {
            str(item or "").strip().lower() for item in steps
        }
        requested_steps &= {"password", "plan_check", "twofa"}
        if not requested_steps:
            return {"accepted": False, "error": "没有可执行的账号配置步骤"}
        if requested_steps == {"password"} and str(operation or "").strip().lower() != "password_change":
            from core.account_completion_service import completion_plan

            from config.account import completion_settings

            base_settings = completion_settings()
            _raw_snapshot, _allowlist, execution_settings = _runtime_execution_settings(base_settings)
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
        snapshot, allowlist, settings = _runtime_execution_settings(base_settings)
        _register_runtime_handlers()
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
            self.logger.exception("创建账号配置 durable task 失败：email=%s", email)
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
        self,
        account_id: int,
        *,
        trigger: str = "manual_account_completion",
    ) -> dict:
        """Generate and queue the configured missing-account completion plan."""
        from core.account_completion_service import completion_plan
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
        if str(account.get("account_status") or "").lower() == "deactivated":
            return {"accepted": False, "error": "账号已废号，不能补全账号"}
        # registered_accounts is created before registration is fully complete.
        # Enrich the account row with the durable Attempt state so a missing
        # Token cannot be mistaken for a refreshable, already-registered account.
        try:
            from core.storage import registration as registration_store

            attempt = registration_store.get_latest_attempt_by_account(int(account["id"]))
            if attempt:
                account = dict(account)
                account["registration_target_status"] = attempt.get("target_status")
                account["registration_remote_account_state"] = attempt.get("remote_account_state")
                account["registration_checkpoint"] = account.get("registration_checkpoint") or attempt.get("checkpoint")
        except Exception:
            logger.exception("读取账号注册 Attempt 状态失败：account_id=%s", account_id)
        base_settings = completion_settings()
        snapshot, allowlist, settings = _runtime_execution_settings(base_settings)
        plan = completion_plan(account, settings)
        if "registration_resume" in plan["missing_steps"]:
            source_job = db.get_latest_registration_job_for_account(int(account["id"]))
            if not source_job:
                reason = "账号注册尚未完成，但找不到可继续的原注册任务；为避免误注册，请先从注册任务中心处理"
                return {
                    "accepted": False,
                    "blocked": [{"step": "registration_resume", "reason": reason}],
                    "plan": plan,
                    "error": reason,
                }
            _register_runtime_handlers()
            source_job_id = int(source_job["id"])
            remote_account_state = str(
                account.get("registration_remote_account_state")
                or account.get("remote_account_state")
                or ""
            ).strip().lower()
            try:
                queued = account_task_store.submit_durable_operation(
                    task_type="registration_resume",
                    account_id=int(account["id"]),
                    email=email,
                    trigger=str(trigger or "manual_account_completion"),
                    source_system=_RUNTIME_SOURCE_SYSTEM,
                    source_id=f"registration-resume:{int(account['id'])}:{source_job_id}",
                    idempotency_key=f"registration-resume:{int(account['id'])}:{source_job_id}",
                    resource_family="openai_interactive",
                    data={
                        "source_job_id": source_job_id,
                        "remote_account_state": remote_account_state,
                        "registration_checkpoint": str(
                            account.get("registration_checkpoint") or ""
                        ),
                        "task_trigger": str(trigger or "manual_account_completion"),
                    },
                    config_snapshot=snapshot,
                    config_allowlist=allowlist,
                )
            except Exception as exc:
                logger.exception("创建注册续跑 durable task 失败：account_id=%s", account_id)
                return {
                    "accepted": False,
                    "blocked": [{"step": "registration_resume", "reason": f"继续注册入队异常：{type(exc).__name__}"}],
                    "plan": plan,
                    "error": f"继续注册入队异常：{type(exc).__name__}: {exc}",
                }
            return {
                **queued,
                "registration_resume": True,
                "job_id": source_job_id,
                "source_job_id": source_job_id,
                "plan": plan,
                "message": "已将原注册任务续跑请求持久化，不执行 AT 刷新",
            }
        # 一个步骤被账号能力明确阻塞时，仍允许执行其它未完成步骤。
        # 例如密码资格为 false，但 Authenticator 2FA 仍然可以补齐。
        if plan["blocked"] and not plan["missing_steps"]:
            return {"accepted": False, "blocked": plan["blocked"], "plan": plan, "error": plan["blocked"][0]["reason"]}
        if not plan["missing_steps"]:
            return {"accepted": False, "ready": True, "plan": plan, "message": "账号已满足当前补全配置"}
        task_trigger = str(trigger or "manual_account_completion")
        _register_runtime_handlers()
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
                    "task_trigger": task_trigger,
                },
                config_snapshot=snapshot,
                config_allowlist=allowlist,
            )
        except Exception as exc:
            self.logger.exception("创建账号补全 durable task 失败：email=%s", email)
            return {"accepted": False, "error": f"任务实例创建失败：{type(exc).__name__}: {exc}"}
        return {
            **queued,
            "account_id": int(account["id"]),
            "email": email,
            "trigger": task_trigger,
            "plan": plan,
        }

    def retry_account_task_result(self, task_id: int) -> tuple[dict, int]:
        """Resolve a historical account task to its current retry service."""
        task = account_task_store.get_task(task_id)
        if not task:
            return {"ok": False, "error": "任务实例不存在"}, 404
        if task.get("status") in {"queued", "running"}:
            return {"ok": False, "error": "任务仍在执行"}, 409
        account = db.get_account(int(task.get("account_id") or 0))
        if not account:
            return {"ok": False, "error": "关联账号不存在"}, 404
        task_type = str(task.get("task_type") or "")
        if task_type in {"live_check", "token_refresh"}:
            queued = live_check_service.enqueue_account_live_check(
                account_id=int(account["id"]),
                email=str(account.get("email") or ""),
                trigger="token_refresh_manual_retry" if task_type == "token_refresh" else "manual_retry",
                proxy=None,
                force_refresh=task_type == "token_refresh",
            )
        elif task_type == "plan_check":
            queued = plan_check_service.enqueue_account_plan_check(
                account_id=int(account["id"]),
                email=str(account.get("email") or ""),
                access_token=str(account.get("access_token") or ""),
                trigger="manual_retry",
                proxy=None,
            )
        elif task_type == "deactivation_mail":
            queued = deactivation_mail_service.enqueue(int(account["id"]), trigger="manual_retry")
        elif task_type == "extract_link":
            result_summary = task.get("result_summary") if isinstance(task.get("result_summary"), dict) else {}
            queued = extract_link_service.enqueue_account_extract(
                account_id=int(account["id"]),
                email=str(account.get("email") or ""),
                access_token=str(account.get("access_token") or ""),
                trigger="manual_retry",
                # 失败类型会由提炼服务重新检查并自动换下一个可用类型。
                link_type=str(result_summary.get("link_type") or "") or None,
            )
        elif task_type == "codex_retry":
            queued = self.enqueue_codex_retry(
                email=str(account.get("email") or ""),
                trigger="manual_retry",
            )
        elif task_type in {"account_setup_retry", "password_setup", "password_change", "twofa_setup", "twofa_change"}:
            step_map = {
                "account_setup_retry": None,
                "password_setup": {"password"},
                "password_change": {"password"},
                "twofa_setup": {"twofa"},
                "twofa_change": {"twofa"},
            }
            operation_map = {
                "password_change": "password_change",
                "twofa_change": "twofa_change",
            }
            queued = self.enqueue_account_setup(
                int(account["id"]),
                trigger="manual_retry",
                steps=step_map[task_type],
                task_type=task_type,
                operation=operation_map.get(task_type),
            )
        elif task_type == "account_completion":
            queued = self.enqueue_account_completion(
                int(account["id"]),
                trigger="manual_retry_completion",
            )
        elif task_type == "codex_token_refresh":
            filename = str((task.get("result_summary") or {}).get("filename") or "")
            queued = codex_token_refresh_service.enqueue_refresh(filename, trigger="manual_retry")
        else:
            return {"ok": False, "error": "该任务类型暂不支持重跑"}, 400
        if queued.get("busy"):
            return {"ok": False, **queued}, 409
        if not queued.get("accepted"):
            return {"ok": False, **queued}, 400
        return {"ok": True, **queued}, 202


_runtime_lock = threading.Lock()
_runtime_started = False
_runtime_started_at: float | None = None


def runtime_status() -> dict[str, Any]:
    """Read-only process runtime state for the release agent's health route.

    The structure intentionally contains no account, token, proxy or database
    payload.  ``ready`` means WebUI startup completed; component liveness is
    exposed separately so a health route can choose strict or degraded policy.
    """
    with _runtime_lock:
        started = bool(_runtime_started)
        started_at = _runtime_started_at
    try:
        executor_status = _ACCOUNT_EXECUTOR.status()
    except Exception as exc:
        executor_status = {"error": type(exc).__name__}
    try:
        dispatcher_status = codex_operation_service.dispatcher_status()
    except Exception as exc:
        dispatcher_status = {"error": type(exc).__name__}
    try:
        dependency_dispatcher_status = account_task_store.dependency_dispatcher_status()
    except Exception as exc:
        dependency_dispatcher_status = {"error": type(exc).__name__}
    try:
        projection_status = operation_task_store.projection_worker_status()
    except Exception as exc:
        projection_status = {"error": type(exc).__name__}
    return {
        "ready": started,
        "started": started,
        "pid": os.getpid(),
        "started_at": started_at,
        "executor": executor_status,
        "codex_dispatcher": dispatcher_status,
        "dependency_dispatcher": dependency_dispatcher_status,
        "projection_worker": projection_status,
    }


def start_runtime(runtime_logger: logging.Logger | None = None) -> bool:
    """Start WebUI recovery and periodic workers once per process."""
    global _runtime_started, _runtime_started_at
    active_logger = runtime_logger or logger
    with _runtime_lock:
        if _runtime_started:
            return False

        operation_task_store.init()
        _register_runtime_handlers()
        recovered_operation_runs = operation_task_store.recover_interrupted_runtime_runs()
        if recovered_operation_runs:
            active_logger.warning("已收口 %s 个因 WebUI 重启中断的原生账号操作", recovered_operation_runs)
        repaired_compatibility_projections = operation_task_store.repair_stale_compatibility_projections()
        if repaired_compatibility_projections:
            active_logger.warning(
                "已修复 %s 个底层已结束但统一任务仍显示活动的兼容投影",
                repaired_compatibility_projections,
            )
        registration_recovery = _legacy_recovery_exclusions(
            {"registration_resume"},
            legacy_source_systems=("registration_jobs",),
        )
        if not registration_recovery["skip_all"]:
            recovered_jobs = db.recover_interrupted_registration_jobs(
                excluded_account_ids=registration_recovery["account_ids"],
                excluded_source_ids=registration_recovery["source_ids"],
            )
            if recovered_jobs:
                active_logger.warning("已恢复 %s 个因 WebUI 重启中断的注册/Codex 任务", recovered_jobs)
        else:
            active_logger.info("无法安全读取 durable registration_resume 行级排除项，跳过旧注册状态恢复")
        account_task_recovery = _legacy_recovery_exclusions(
            _LEGACY_DURABLE_TASK_TYPES,
            legacy_source_systems=("account_action_tasks",),
        )
        if not account_task_recovery["skip_all"]:
            recovered_account_tasks = account_task_store.recover_interrupted(
                excluded_account_ids=account_task_recovery["account_ids"],
                excluded_source_ids=account_task_recovery["source_ids"],
            )
            if recovered_account_tasks:
                active_logger.warning("已恢复 %s 个因 WebUI 重启中断的账号任务实例", recovered_account_tasks)
        else:
            active_logger.info("无法安全读取 durable 账号操作行级排除项，跳过兼容账号任务恢复")
        operation_task_store.start_projection_worker()
        account_task_store.start_dispatcher()
        account_task_store.set_dependency_ready_handler(_submit_ready_completion_dependency)
        account_task_store.start_dependency_dispatcher()
        try:
            resumed_dependencies = account_task_store.drain_ready_dependencies(initialized=True)
            if resumed_dependencies:
                active_logger.info("已恢复 %s 个待续接的账号补全父任务", resumed_dependencies)
        except Exception:
            # Dependency recovery is additive.  The durable ready rows remain
            # queryable and will be retried on the next startup/reconcile.
            active_logger.exception("恢复账号补全父子依赖失败；不影响 WebUI 启动")
        try:
            from core.roxybrowser_client import cleanup_orphaned_profiles

            orphan_result = cleanup_orphaned_profiles()
            if orphan_result.get("found"):
                active_logger.warning(
                    "Roxy 孤儿环境恢复完成：found=%s cleaned=%s failed=%s",
                    orphan_result.get("found"),
                    orphan_result.get("cleaned"),
                    orphan_result.get("failed"),
                )
        except Exception:
            active_logger.exception("Roxy 孤儿环境启动恢复失败；登记会保留到下次启动继续重试")

        try:
            from core.registration_debug import cleanup_expired_artifacts

            debug_cleanup = cleanup_expired_artifacts()
            if debug_cleanup.get("removed_files") or debug_cleanup.get("removed_dirs"):
                active_logger.info(
                    "注册调试产物过期清理完成：files=%s dirs=%s",
                    debug_cleanup.get("removed_files", 0),
                    debug_cleanup.get("removed_dirs", 0),
                )
        except Exception:
            active_logger.exception("注册调试产物过期清理失败；不影响 WebUI 启动")

        sms_provider.start_cancel_worker()
        plan_check_recovery = _legacy_recovery_exclusions(
            {"plan_check"}, legacy_source_systems=(),
        )
        if not plan_check_recovery["skip_all"]:
            recovered_plan_checks = db.recover_interrupted_plan_checks(
                excluded_account_ids=plan_check_recovery["account_ids"],
            )
            if recovered_plan_checks:
                active_logger.warning("已恢复 %s 个因 WebUI 重启中断的套餐查询状态", recovered_plan_checks)
        else:
            active_logger.info("无法安全读取 durable plan_check 行级排除项，跳过旧套餐查询恢复")
        extract_link_recovery = _legacy_recovery_exclusions(
            {"extract_link"}, legacy_source_systems=(),
        )
        if not extract_link_recovery["skip_all"]:
            recovered_extract_links = db.recover_interrupted_extract_links(
                excluded_account_ids=extract_link_recovery["account_ids"],
            )
            if recovered_extract_links:
                active_logger.warning("已恢复 %s 个因 WebUI 重启中断的提链状态", recovered_extract_links)
        else:
            active_logger.info("无法安全读取 durable extract_link 行级排除项，跳过旧提链恢复")
        live_check_recovery = _legacy_recovery_exclusions(
            {"live_check", "token_refresh"}, legacy_source_systems=(),
        )
        if not live_check_recovery["skip_all"]:
            recovered_live_checks = db.recover_interrupted_live_checks(
                excluded_account_ids=live_check_recovery["account_ids"],
            )
            if recovered_live_checks:
                active_logger.warning("已恢复 %s 个因 WebUI 重启中断的查活状态", recovered_live_checks)
        else:
            active_logger.info("无法安全读取 durable live_check 行级排除项，跳过旧查活恢复")
        backfilled_proxy_context = db.backfill_account_registration_proxy_context()
        if backfilled_proxy_context:
            active_logger.info("已为 %s 个历史账号补齐注册代理来源/国家", backfilled_proxy_context)

        resumed_codex_runs = codex_operation_service.resume_queued()
        if resumed_codex_runs:
            active_logger.info("已恢复调度 %s 个数据库队列中的 Codex attempt", resumed_codex_runs)
        from core.deactivation_mail_service import start_periodic_scanner
        from core.token_refresh_service import start_periodic_refresher
        from core.codex_token_refresh_service import start_periodic_refresher as start_codex_token_refresher

        start_periodic_scanner()
        start_periodic_refresher()
        start_codex_token_refresher()
        from core.account_auth_context_service import start_periodic_cleanup

        start_periodic_cleanup()
        _runtime_started = True
        _runtime_started_at = time.time()
        return True
