# -*- coding: utf-8 -*-
"""账号 setup 的持久子任务提交与执行，沿用原有业务适配器。"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from core import db, operation_task_store
from core.accounts import operation_results, operation_settings
from core.accounts.operation_coordinator import RUNTIME_SOURCE_SYSTEM
from core.codex import retry_service as codex_retry_service
from core.operations import task_gateway
from core.operations import task_gateway as account_task_store

logger = logging.getLogger("webui.runtime")


def submit_native_account_setup_child(
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
        allowlist = (*operation_settings.RUNTIME_CONFIG_ALLOWLIST, "child_execution", "bulk_execution_frozen")
    queued = account_task_store.submit_durable_operation(
        task_type="account_setup_retry",
        account_id=int(context.account_id or 0) or None,
        email=context.email,
        trigger=f"{task_trigger}_account_setup",
        source_system=RUNTIME_SOURCE_SYSTEM,
        source_id=source_id,
        idempotency_key=source_id,
        resource_family="openai_interactive",
        data={
            "steps": sorted(steps),
            "completion_auth": True,
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
            existing = operation_task_store.get_task(int(queued["task_id"]), include_events=False)
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


def handle_native_account_setup(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    data = operation_results.native_task_data(context)
    steps = {
        str(item or "").strip().lower()
        for item in data.get("steps") or []
    } & {"password", "plan_check", "twofa"}
    if not steps:
        steps = {
            "password", "plan_check", "twofa",
        }
    if data.get("registration_completion"):
        from core.storage import registration

        source_run = registration.get_run(int(data.get("registration_run_id") or 0)) or {}
        source_job = db.get_job(int(source_run.get("job_id") or 0)) if source_run.get("job_id") else {}
        if (str(source_run.get("status") or "") in {"stopped", "cancelled"}
                or str((source_job or {}).get("status") or "") in {"stopping", "stopped", "cancelled"}):
            return operation_results.finish_native_context(context, task_gateway.OperationResult.cancelled(
                "原注册续跑已停止，取消尚未执行的自动补密码",
            ))
    settings = operation_settings.completion_settings_from_snapshot(context.config_snapshot)
    task_trigger = str(data.get("task_trigger") or context.run.get("trigger") or "manual_account_setup")
    # 持久化脱敏会移除含 password 的键；改密任务仍须保留其明确操作意图。
    force_password_reset = context.task_type == "password_change" or bool(data.get("force_password_reset"))
    force_twofa_change = bool(data.get("force_twofa_change"))
    country = data.get("proxy_country_override")
    if country is not None:
        from config.countries import ISO_3166_ALPHA2

        if not isinstance(country, str) or country not in ISO_3166_ALPHA2:
            return operation_results.finish_native_context(context, task_gateway.OperationResult.failed("重跑代理国家覆盖无效"))
    from core.runtime.capabilities import account_setup_unavailable

    unavailable = account_setup_unavailable(
        steps, settings, force_twofa_change=force_twofa_change, force_password_reset=force_password_reset,
    )
    if unavailable:
        return operation_results.finish_native_context(context, task_gateway.OperationResult.failed(unavailable["error"], unavailable))
    context.report(
        stage="account_setup", state="running",
        message=f"开始执行账号配置步骤：{ '、'.join(sorted(steps)) }",
        detail={"steps": sorted(steps)},
    )
    request_id = f"account-setup:{context.run_id}"
    with context.lease(resource_family="openai_interactive", scope_kind="final"):
        if data.get("registration_completion") and steps == {"password"}:
            from core.accounts.password_evidence import password_is_confirmed

            if password_is_confirmed(db.get_account(int(context.account_id or 0))):
                return operation_results.finish_native_context(context, task_gateway.OperationResult.success(
                    {"already_confirmed": True}, message="账号密码已确认，自动补密码任务完成",
                ))
        if data.get("completion_auth"):
            from core.accounts.completion import active_registration_job

            if active_registration_job(int(context.account_id or 0), context.email):
                raise task_gateway.OperationLeaseUnavailable(
                    "该账号仍有注册任务正在执行，等待注册结束后补全账号"
                )
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
                execution_fence=context.execution_fence,
                **({"execution_settings": dict(settings)}
                   if (data.get("bulk_target_round_id") or data.get("registration_completion")
                       or context.task_type == "password_change") else {}),
                **({"proxy_country_override": country} if country is not None else {}),
            )
        except (task_gateway.OperationSettlementPending, task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
            raise
        except Exception as exc:
            try:
                context.remote_request_receipt(
                    outcome="unknown", action="account_setup", request_id=request_id,
                    detail={"remote_response_received": False},
                )
            except (task_gateway.OperationSettlementPending, task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
                raise
            except Exception:
                logger.exception("账号配置 remote receipt 写入失败：run_id=%s", context.run_id)
            return operation_results.finish_native_context(
                context,
                task_gateway.OperationResult.request_unknown(
                    f"账号配置执行异常，远端结果待核验：{type(exc).__name__}",
                    {"error_type": type(exc).__name__},
                ),
            )
        normalized = operation_results.safe_operation_result(result, default_message="账号配置未完成")
        receipt_state, receipt_detail = operation_results.account_setup_receipt(
            int(context.account_id or 0), context.email, steps, result,
        )
        context.remote_request_receipt(
            outcome=receipt_state,
            action="account_setup",
            request_id=request_id,
            detail=receipt_detail,
        )
        if receipt_detail.get("setup_step_receipts"):
            normalized.summary["setup_step_receipts"] = receipt_detail["setup_step_receipts"]
        if receipt_state not in {"confirmed", "rejected", "not_submitted"}:
            pending_summary = dict(normalized.summary)
            pending_error = normalized.error
            pending_message = normalized.message
            if receipt_state == "local_commit_required" and not pending_error:
                pending_error = "account_setup_local_commit_failed"
                pending_summary["cause_code"] = pending_error
                pending_message = "账号配置本地写回或读回未完成"
            normalized = task_gateway.OperationResult.request_unknown(
                pending_message or "账号配置步骤未保存完整回执",
                {
                    **pending_summary,
                    "status": str((result or {}).get("status") or "failed"),
                    "remote_receipt_state": receipt_state,
                    "local_readback_checks": receipt_detail.get("local_readback_checks") or {},
                },
                error=pending_error,
            )
        elif receipt_state == "confirmed" and normalized.status == "success":
            context.report(
                stage="account_setup", state="success",
                message="账号配置实际执行与本地写回已确认完成",
                detail={"steps": sorted(steps), "local_readback_confirmed": True},
            )
        elif receipt_state == "rejected" and normalized.status == "failed":
            context.report(
                stage="account_setup", state="failed", level="ERROR",
                message="账号配置已明确失败",
                detail={"steps": sorted(steps), "remote_result_state": "rejected"},
            )
        return operation_results.finish_native_context(context, normalized)
