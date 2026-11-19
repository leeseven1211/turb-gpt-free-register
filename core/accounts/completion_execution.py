# -*- coding: utf-8 -*-
"""账号补全计划的执行编排与原生任务入口。"""
from __future__ import annotations

import logging
from copy import deepcopy
from collections.abc import Mapping
from typing import Any

from core import db, operation_task_store
from core.accounts import operation_results, operation_settings, setup_execution
from core.accounts.liveness import service as live_check_service
from core.accounts.operation_coordinator import RUNTIME_SOURCE_SYSTEM
from core.codex import operation_service as codex_operation_service
from core.codex import retry_service as codex_retry_service
from core.operations import task_gateway
from core.operations import task_gateway as account_task_store

logger = logging.getLogger("webui.runtime")


def apply_settlement_dependency(payload: Mapping[str, Any], *, deadline=None) -> bool:
    """Deliver the already-created child edge after the parent receipt exists.

    The storage cleanup dispatcher binds the original database domain and
    deadline before calling this narrow local operation. No child is queued
    here, including when the child completed before the parent was settled.
    """
    del deadline
    parent_id = int(payload["parent_source_id"])
    parent_run_id = int(payload["parent_run_id"])
    parent = operation_task_store.get_task(parent_id, include_events=False) or {}
    if int(parent.get("last_run_id") or 0) != parent_run_id:
        # A new explicit Run has superseded this continuation.
        return True
    if str(parent.get("status") or "").lower() not in {
        "partial_success", "success", "failed", "attention_required", "cancelled",
        "deactivated", "unsupported",
    }:
        return False
    dependency = operation_task_store.register_task_dependency(
        parent_source_system=str(payload["parent_source_system"]),
        parent_source_id=str(parent_id),
        child_source_system=str(payload["child_source_system"]),
        child_source_id=str(payload["child_source_id"]),
        dependency_type=str(payload["dependency_type"]),
        payload=deepcopy(dict(payload.get("payload") or {})),
        expected_parent_run_id=parent_run_id,
    )
    if dependency.get("dependency_stale"):
        return True
    if dependency.get("status") == "ready":
        task_gateway.notify_dependency_ready(dependency)
    elif (
        dependency.get("status") == "waiting"
        and payload["child_source_system"] in {"native_operations", RUNTIME_SOURCE_SYSTEM}
        and str(payload["child_source_id"]).isdigit()
    ):
        child = operation_task_store.get_task(
            int(payload["child_source_id"]), include_events=False,
        ) or {}
        ready = operation_task_store.mark_task_dependency_ready(
            child_source_system=str(payload["child_source_system"]),
            child_source_id=str(payload["child_source_id"]),
            child_status=str(child.get("status") or ""),
            child_result=child.get("result_summary") or {},
        )
        for item in ready:
            task_gateway.notify_dependency_ready(item)
    return True


def run_account_completion_worker(
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
    from core.accounts.completion import STEP_LABELS, completion_plan

    started = False
    result_summary: dict[str, Any] = dict(initial_result_summary or {})
    result_summary["planned_steps"] = list(planned_steps)
    configured = result_summary.setdefault("configured_steps", [
        step for step in STEP_LABELS if bool(settings.get(f"{step}_enabled", step in planned_steps))
    ])
    result_summary.setdefault("required_steps", list(dict.fromkeys([*configured, *planned_steps])))
    result_summary.setdefault("blocked", [])
    task_store = operation_results.NativeTaskLifecycle(context) if context is not None else account_task_store
    reservation_held = (context is None) if reservation_held is None else bool(reservation_held)
    remote_write_started = False
    remote_receipt_state: str | None = None

    def child_config(step: str) -> dict:
        if context is None or not operation_results.native_task_data(context).get("bulk_target_round_id"):
            return {}
        children = (context.config_snapshot or {}).get("child_execution") or {}
        frozen = children.get(step) if isinstance(children, Mapping) else None
        return {"config_snapshot": dict(frozen)} if isinstance(frozen, Mapping) else {}

    def save_handoff(*, child_source_system: str, child_source_id: object, payload: dict) -> None:
        if context is not None:
            result_summary["completion_handoff"] = {
                "child_source_system": child_source_system,
                "child_source_id": str(child_source_id or ""),
                "remaining_steps": list(payload.get("remaining_steps") or []),
            }
            context.add_settlement_obligation(
                "completion_dependency",
                resource_identity=f"completion:{context.run_id}:{child_source_system}:{child_source_id}",
                payload={
                    "parent_source_system": getattr(context, "source_system", RUNTIME_SOURCE_SYSTEM),
                    "parent_source_id": str(int(task_id)),
                    "parent_run_id": context.run_id,
                    "child_source_system": child_source_system,
                    "child_source_id": str(child_source_id or ""),
                    "dependency_type": "account_completion",
                    "payload": deepcopy({**payload, "parent_run_id": context.run_id}),
                },
                blocks_permit=False,
            )

    def refresh_completion_state() -> None:
        """终态按完整原始要求读回，续接剩余步骤不能丢掉已阻塞的缺项。"""
        account = db.get_account(int(account_id)) or {}
        current = completion_plan(account, settings)
        required = list(result_summary.get("required_steps") or [])
        current_blocked = [dict(item) for item in current.get("blocked") or [] if isinstance(item, Mapping)]
        missing = set(current.get("missing_steps") or []) | {item.get("step") for item in current_blocked}
        retained = [dict(item) for item in result_summary.get("blocked") or []
                    if isinstance(item, Mapping) and item.get("step") in missing]
        blocked = {str(item.get("step")): item for item in [*retained, *current_blocked]}
        result_summary["blocked"] = list(blocked.values())
        result_summary["pending_steps"] = [step for step in required if step in missing]
        result_summary["completed_steps"] = [step for step in required if step not in missing]
        result_summary["ready"] = not result_summary["pending_steps"] and not blocked

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
        if context is not None:
            # The original-version obligation owns native delivery, including
            # ordinary (non-bulk) completion and post-ACK process failures.
            return
        try:
            dependency = operation_task_store.register_task_dependency(
                parent_source_system=(
                    getattr(context, "source_system", RUNTIME_SOURCE_SYSTEM)
                    if context is not None else "account_action_tasks"
                ),
                parent_source_id=str(int(task_id)),
                child_source_system=child_source_system,
                child_source_id=str(child_source_id),
                dependency_type="account_completion",
                payload={**payload, **({"parent_run_id": context.run_id} if context is not None else {})},
            )
            if dependency.get("status") == "ready":
                task_gateway.notify_dependency_ready(dependency)
            elif (
                dependency.get("status") == "waiting"
                and child_source_system in {"native_operations", RUNTIME_SOURCE_SYSTEM}
                and str(child_source_id).isdigit()
            ):
                # 完成通知使用逻辑任务 ID；补读已结束的快速子任务，覆盖登记前完成的竞态。
                child = operation_task_store.get_task(int(child_source_id), include_events=False) or {}
                ready = operation_task_store.mark_task_dependency_ready(
                    child_source_system=child_source_system,
                    child_source_id=str(child_source_id),
                    child_status=str(child.get("status") or ""),
                    child_result=child.get("result_summary") or {},
                )
                for item in ready:
                    task_gateway.notify_dependency_ready(item)
        except (task_gateway.OperationSettlementPending, task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
            raise
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
            # 按本次任务冻结的配置执行，历史注册检查点不取消补全计划。
            current_plan = completion_plan(account, settings)
            if "refresh_at" not in current_plan["missing_steps"]:
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
                allow_missing_token=True,
                **child_config("refresh_at"),
            )
            if queued.get("busy") and not (queued.get("source_id") or queued.get("task_id")):
                # 占用尚未对应到持久子任务时退队等待，避免生成无法续接的父任务。
                raise task_gateway.OperationLeaseUnavailable(
                    queued.get("error") or "刷新 AT 暂时被占用，等待下一轮派发"
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
            save_handoff(child_source_system=str(queued.get("source_system") or "account_action_tasks"),
                         child_source_id=queued.get("task_id") or queued.get("source_id"), payload=dependency_payload)
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
                child_source_id=queued.get("task_id") or queued.get("source_id"),
                payload=dependency_payload,
            )
            return context.last_result if context is not None else None

        setup_steps = remaining & {"password", "plan_check", "twofa"}
        if setup_steps:
            if context is not None:
                queued_setup = setup_execution.submit_native_account_setup_child(
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
                save_handoff(child_source_system=str(queued_setup.get("source_system") or RUNTIME_SOURCE_SYSTEM),
                             child_source_id=queued_setup.get("task_id") or child_source_id, payload=dependency_payload)
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
                        queued_setup.get("source_system") or RUNTIME_SOURCE_SYSTEM
                    ),
                    child_source_id=queued_setup.get("task_id") or child_source_id,
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
                    **({"execution_fence": context.execution_fence} if context is not None else {}),
                )
            except (task_gateway.OperationSettlementPending, task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
                raise
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
                    except (task_gateway.OperationSettlementPending, task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
                        raise
                    except Exception:
                        logger.exception(
                            "账号配置 remote intent 未能写入 unknown：run_id=%s",
                            context.run_id,
                        )
                raise
            if context is not None and remote_write_started:
                remote_receipt_state, receipt_detail = operation_results.account_setup_receipt(
                    int(account_id), email, set(setup_steps), setup_result,
                )
                context.remote_request_receipt(
                    outcome=remote_receipt_state,
                    action="account_setup",
                    request_id=f"account-setup:{context.run_id}",
                    detail=receipt_detail,
                )
                if remote_receipt_state not in {"confirmed", "rejected", "not_submitted"}:
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
                "password_setup": setup_result.get("password_setup"),
                "password_driver": setup_result.get("password_driver"),
                "twofa_setup": setup_result.get("twofa_setup"),
                "step_results": setup_result.get("step_results"),
                "setup_step_results": setup_result.get("setup_step_results"),
                "twofa_driver": setup_result.get("twofa_driver"),
                "auth_source": setup_result.get("auth_source"),
                "browser_opened": setup_result.get("browser_opened"),
                "account_status_persisted": setup_result.get("account_status_persisted"),
            }
            setup_status = str(setup_result.get("status") or "").lower()
            if setup_status == "deactivated":
                refresh_completion_state()
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
                refresh_completion_state()
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
            task_store.append_event(
                task_id,
                stage="account_setup",
                message="账号配置实际执行已确认完成",
                detail={"steps": sorted(setup_steps)},
                state="success",
            )
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
                completion_auth=True,
                **child_config("codex"),
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
            save_handoff(child_source_system=str(queued.get("source_system") or "native_operations"),
                         child_source_id=queued.get("task_id") or queued.get("source_id"), payload=codex_dependency_payload)
            release_parent_reservation()

        refresh_completion_state()
        task_status = "partial_success" if (
            result_summary.get("pending_steps") or result_summary.get("blocked") or result_summary.get("awaiting_steps")
        ) else "success"
        task_store.finish_task(
            task_id,
            status=task_status,
            message=(
                "补全步骤已完成，等待子任务成功后系统自动继续"
                if result_summary.get("awaiting_steps")
                else "已保存成功步骤，账号仍有未完成或受阻步骤，可重跑补齐"
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
                child_source_id=queued.get("task_id") or codex_child_task_id or queued.get("source_id"),
                payload=codex_dependency_payload,
            )
        return context.last_result if context is not None else None
    except task_gateway.OperationLeaseUnavailable:
        raise
    except (task_gateway.OperationSettlementPending, task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
        raise
    except Exception as exc:
        result_summary["error"] = f"{type(exc).__name__}: {str(exc)[:220]}"
        refresh_completion_state()
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
            status="partial_success" if result_summary.get("completed_steps") else "failed",
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


def handle_native_account_completion(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    from core.accounts.completion import active_registration_job

    if active_registration_job(int(context.account_id or 0), context.email):
        raise task_gateway.OperationLeaseUnavailable(
            "该账号仍有注册任务正在执行，等待注册结束后补全账号"
        )
    data = operation_results.native_task_data(context)
    continuation = data.get("continuation_payload")
    continuation = dict(continuation) if isinstance(continuation, Mapping) else {}
    has_saved_plan = "remaining_steps" in continuation or "planned_steps" in data
    saved_steps = (
        continuation.get("remaining_steps")
        if "remaining_steps" in continuation
        else data.get("planned_steps")
    )
    planned_steps = [
        str(step or "").strip().lower()
        for step in saved_steps or []
        if str(step or "").strip()
    ]
    settings = operation_settings.completion_settings_from_snapshot(
        context.config_snapshot,
        fallback=continuation.get("settings") if isinstance(continuation.get("settings"), Mapping) else None,
    )
    # 空剩余计划表示子任务已全部消费，只有缺失计划字段的历史任务才重算。
    if not has_saved_plan:
        account = db.get_account(int(context.account_id or 0)) or {}
        from core.accounts.completion import completion_plan

        planned_steps = list(completion_plan(account, settings).get("missing_steps") or [])
    unavailable = operation_settings.completion_deployment_unavailable(set(planned_steps), settings)
    if unavailable:
        return operation_results.finish_native_context(context, task_gateway.OperationResult.failed(unavailable["error"], unavailable))
    initial_summary = continuation.get("result_summary")
    initial_summary = dict(initial_summary) if isinstance(initial_summary, Mapping) else {}
    for key in ("configured_steps", "required_steps", "blocked"):
        if key not in initial_summary and key in data:
            initial_summary[key] = data[key]
    if initial_summary is not None:
        # 已成功完成依赖的等待状态不应带入下一轮，保留各子任务的执行证据。
        for key in ("awaiting_steps", "deferred_steps", "continuation_steps", "completion_handoff"):
            initial_summary.pop(key, None)
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
    # 父任务只编排补全计划，账号交互租约由执行远端操作的独立子任务持有。
    run_account_completion_worker(**worker_kwargs)
    if context.last_result is not None:
        return context.last_result
    return operation_results.finish_native_context(
        context,
        task_gateway.OperationResult.failed("账号补全 handler 未报告终态"),
    )
