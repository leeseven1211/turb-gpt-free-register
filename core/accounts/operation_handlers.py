"""账号操作 handler 的组合与注册；调度仍由统一任务网关负责。"""
from __future__ import annotations

import threading
from collections.abc import Mapping

from core.accounts import completion_execution, operation_settings, setup_execution
from core.accounts.operation_coordinator import RUNTIME_SOURCE_SYSTEM
from core.accounts.operation_results import (
    finish_native_context as _finish_native_context,
    native_task_data as _native_task_data,
)
from core.operations import action_service, task_gateway

RUNTIME_HANDLER_TYPES = frozenset({
    "account_setup_retry", "password_setup", "password_change",
    "twofa_setup", "twofa_change", "account_completion", "registration_resume",
})
_RUNTIME_HANDLER_LOCK = threading.RLock()
_RUNTIME_HANDLERS_REGISTERED = False


def handle_native_registration_resume(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    data = _native_task_data(context)
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
        from core.registration import service as registration_service

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
    # This handler is retained only for registration_resume wrappers that were
    # persisted before account completion began dispatching the real retry job
    # directly.  Queuing a child is not the same as that child succeeding, so
    # never leave a misleading green terminal state on the compatibility task.
    result = task_gateway.OperationResult(
        "partial_success",
        {
            "source_job_id": source_job_id,
            "job_id": job.get("id"),
            "created": bool(resumed.get("created")),
            "reused": bool(resumed.get("reused")),
            "child_result_authoritative": True,
        },
        message=(
            f"已转交给真实注册续跑任务 #{job.get('id')}，"
            "请以该任务的最终状态为准"
        ),
    )
    return _finish_native_context(context, result)


def register_actions() -> None:
    """Expose existing runtime controls without registering execution handlers."""
    for task_type in sorted(RUNTIME_HANDLER_TYPES):
        task_gateway.register_operation_actions(
            task_type,
            retry_handler=action_service.retry_runtime_task,
            cancel_handler=action_service.cancel_runtime_task,
            terminate_handler=task_gateway.default_operation_terminate,
            source_systems=(RUNTIME_SOURCE_SYSTEM,),
        )


def register_runtime_handlers() -> None:
    global _RUNTIME_HANDLERS_REGISTERED
    from core.accounts.email_change import service as email_change_service

    register_actions()
    email_change_service.register_operation_handlers()
    with _RUNTIME_HANDLER_LOCK:
        registered = set(task_gateway.registered_dispatch_types())
        if _RUNTIME_HANDLERS_REGISTERED and RUNTIME_HANDLER_TYPES <= registered:
            return
        for task_type in sorted(RUNTIME_HANDLER_TYPES):
            if task_type == "registration_resume":
                handler = handle_native_registration_resume
            elif task_type == "account_completion":
                handler = completion_execution.handle_native_account_completion
            else:
                handler = setup_execution.handle_native_account_setup
            task_gateway.register_operation_handler(
                task_type,
                handler,
                source_systems=(RUNTIME_SOURCE_SYSTEM,),
                config_allowlist=operation_settings.RUNTIME_CONFIG_ALLOWLIST,
                retry_handler=action_service.retry_runtime_task,
                cancel_handler=action_service.cancel_runtime_task,
            )
        _RUNTIME_HANDLERS_REGISTERED = True

