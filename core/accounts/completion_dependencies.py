# -*- coding: utf-8 -*-
"""已领取的账号补全依赖续接与共享执行器提交。"""
from __future__ import annotations

import logging
from collections.abc import Mapping

from core import operation_task_store
from core.accounts import completion_execution
from core.accounts.operation_coordinator import RUNTIME_SOURCE_SYSTEM
from core.codex import retry_service as codex_retry_service
from core.operations import task_gateway
from core.operations import task_gateway as account_task_store
from core.operations.executor import executor as _ACCOUNT_EXECUTOR

logger = logging.getLogger("webui.runtime")


def handle_ready_completion_dependency(dependency: dict) -> None:
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
        if parent_system == RUNTIME_SOURCE_SYSTEM:
            parent_task_id = int(parent_id)
            parent = operation_task_store.get_task(parent_task_id, include_events=False) or {}
            expected_run = int(payload.get("parent_run_id") or 0) or None
            if expected_run is None:
                previous_runs = [row for row in parent.get("runs") or [] if isinstance(row, Mapping)]
                if len(previous_runs) == 1:
                    expected_run = int(previous_runs[0].get("id") or 0) or None
                elif len(previous_runs) > 1:
                    # 历史依赖没有记录执行代际，多个 Run 时不能猜测并覆盖或再启动新代。
                    operation_task_store.complete_task_dependency(dependency_id, success=True)
                    logger.info("历史补全依赖执行代际无法唯一确认，保留当前任务：dependency_id=%s parent_task_id=%s",
                                dependency_id, parent_task_id)
                    return
            if expected_run is not None and int(parent.get("last_run_id") or 0) != expected_run:
                operation_task_store.complete_task_dependency(dependency_id, success=True)
                return
            if str(parent.get("status") or "").lower() in {"cancelled", "cancelling", "stopped"}:
                operation_task_store.complete_task_dependency(dependency_id, success=True)
                return
            if child_status != "success":
                updated = operation_task_store.apply_task_dependency_result(
                    parent_source_system=parent_system,
                    parent_source_id=parent_id,
                    child_status=child_status or "unknown",
                    child_result=claimed.get("child_result") if isinstance(claimed.get("child_result"), dict) else {},
                    **({"expected_parent_run_id": expected_run} if expected_run is not None else {}),
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
                **({"expected_previous_run_id": expected_run} if expected_run is not None else {}),
            )
            if run.get("dependency_stale"):
                operation_task_store.complete_task_dependency(dependency_id, success=True)
                return
            task_gateway.notify_dispatch()
            operation_task_store.complete_task_dependency(dependency_id, success=True)
            logger.info(
                "补全父任务已由持久依赖续接：parent_task_id=%s run_id=%s",
                parent_task_id, run.get("id"),
            )
            return
        if parent_system == "native_operations":
            # The email-change parent is terminal before its follow-up child
            # becomes eligible. This dependency records the handoff; it does
            # not reopen a completed parent operation.
            operation_task_store.complete_task_dependency(dependency_id, success=True)
            return
        if parent_system != "account_action_tasks":
            operation_task_store.complete_task_dependency(
                dependency_id, success=False, error="暂不支持该父任务来源",
            )
            return
        parent_task_id = int(parent_id)
        if child_status != "success":
            message = "子任务未成功，补全父任务保留待对账状态"
            child_result = claimed.get("child_result")
            if not isinstance(child_result, Mapping):
                child_result = {}
            child_context = {
                "child_status": child_status or "unknown",
                "child_task_id": (
                    claimed.get("child_task_id")
                    or claimed.get("child_source_id")
                    or child_result.get("task_id")
                ),
                "child_run_id": (
                    child_result.get("run_id")
                    or child_result.get("child_run_id")
                    or claimed.get("child_run_id")
                ),
                "failure_stage": child_result.get("failure_stage") or child_result.get("stage"),
                "failure_event_id": child_result.get("failure_event_id") or child_result.get("event_id"),
                "failure_message": (
                    child_result.get("failure_message")
                    or child_result.get("error_message")
                    or child_result.get("error")
                    or child_result.get("message")
                ),
            }
            child_context = {
                key: value for key, value in child_context.items()
                if value not in (None, "")
            }
            account_task_store.append_event(
                parent_task_id,
                stage="plan",
                level="WARNING",
                message=message,
                detail=child_context,
                state="failed",
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
        completion_execution.run_account_completion_worker(
            email,
            account_id=int(payload.get("account_id") or 0),
            task_id=parent_task_id,
            task_trigger=str(payload.get("task_trigger") or "manual_account_completion"),
            planned_steps=[str(step) for step in payload.get("remaining_steps") or []],
            settings=dict(payload.get("settings") or {}),
            initial_result_summary=dict(payload.get("result_summary") or {}),
        )
        operation_task_store.complete_task_dependency(dependency_id, success=True)
    except (task_gateway.OperationSettlementPending, task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
        raise
    except Exception as exc:
        logger.exception("补全父任务自动续接失败：dependency_id=%s", dependency_id)
        operation_task_store.complete_task_dependency(
            dependency_id, success=False, error=f"{type(exc).__name__}: {exc}",
        )
        account_task_store.notify_dependency_ready(claimed)


def submit_ready_completion_dependency(dependency: dict):
    """Submit a claimed dependency without executing it on the scanner.

    ``try_submit`` is deliberately non-blocking. If the account-operation
    budget is full, the claimed row is returned to the durable ready queue and
    the next scanner tick can reclaim it after the storage backoff expires.
    """
    dependency_id = int(dependency.get("id") or 0)
    if not dependency_id:
        return None
    from core.operations import concurrency

    admission = dependency.get("_execution_context")
    if admission is None:
        # 兼容调用入口也须持真实账号配置许可，旧回调可能直接执行后续业务。
        result = concurrency.try_admit_and_claim(
            execution_key=f"operation_dependency:{dependency_id}", task_type="account_setup_retry",
            claim=lambda conn, execution_id: dict(dependency),
            metadata={key: dependency.get(key) for key in ("parent_source_system", "parent_source_id")},
            extra_scopes=[{"kind": "account", "key": f"{int(dependency['payload']['account_id'])}:openai_interactive", "limit": 1}]
            if isinstance(dependency.get("payload"), Mapping) and dependency["payload"].get("account_id") else [],
        )
        if not result.admitted:
            operation_task_store.complete_task_dependency(dependency_id, success=False,
                                                         error="等待业务执行许可")
            account_task_store.notify_dependency_ready(dependency)
            return None
        admission = result.context
    try:
        future = _ACCOUNT_EXECUTOR.try_submit(
            task_gateway.execute_admitted, admission,
            lambda: handle_ready_completion_dependency({key: value for key, value in dependency.items() if key != "_execution_context"}),
        )
    except (task_gateway.OperationSettlementPending, task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
        raise
    except Exception as exc:
        logger.exception("补全依赖提交到共享 executor 失败：dependency_id=%s", dependency_id)
        task_gateway.rollback_admission(admission, reason="executor_submit_failed")
        return None
    if future is None:
        task_gateway.rollback_admission(admission, reason="executor_submit_failed")
    elif hasattr(future, "add_done_callback"):
        future.add_done_callback(lambda completed: task_gateway.rollback_admission(
            admission, reason="submission_cancelled") if completed.cancelled() else None)
    return future
