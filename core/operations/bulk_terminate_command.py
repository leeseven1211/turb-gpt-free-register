"""批量终止的持久控制命令；每个 Run 沿原安全结算边界独立提交。"""
from __future__ import annotations

from dataclasses import asdict
import uuid

from core.operations import bulk_mutation_worker as worker, task_gateway
from core.operations.bulk_mutations import execute_chunked_bulk, normalize_bulk_targets
from core.operations.contracts import BulkItemResult
from core.storage.operations import bulk_mutations as commands, bulk_terminate as storage, common

TASK_TYPE = "task_terminate_bulk"
OPERATION = "operation_terminate"


class _CancellationChanged(RuntimeError):
    pass


def register_commands():
    task_gateway.register_operation_actions(
        TASK_TYPE, retry_handler=task_gateway.default_operation_retry,
        cancel_handler=task_gateway.default_operation_cancel,
        terminate_handler=task_gateway.default_operation_terminate, source_systems=("native_operations",))


def register_worker():
    from core.operations import concurrency
    concurrency.register_admission_alias(TASK_TYPE, "maintenance_check")
    task_gateway.register_operation_handler(TASK_TYPE, handle, config_allowlist=())


def submit(task_ids, *, request_key=None):
    key = str(request_key or uuid.uuid4().hex).strip()
    if not key or len(key) > 200:
        raise ValueError("invalid_idempotency_key")
    normalized = normalize_bulk_targets(task_ids, max_targets=100)
    targets = list(normalized.targets)
    request_hash = worker._digest([OPERATION, key])
    payload_hash = worker._digest({"operation": OPERATION, "targets": sorted(targets), "parameters": {}})
    storage.init()
    with common._connect() as conn:
        command, reused = commands.create_command(
            operation=OPERATION, request_key_hash=request_hash, payload_hash=payload_hash,
            input_targets=task_ids, targets=targets, parameters={}, chunk_size=1,
            duplicate_count=normalized.duplicate_count, conn=conn)
        if not reused:
            storage.freeze(int(command["id"]), targets, conn=conn)
        submitted = task_gateway.submit_durable_operation(
            task_type=TASK_TYPE, account_id=None, email="", trigger="manual_bulk",
            source_id=f"bulk-terminate:{command['id']}", resource_family="bulk_control",
            data={"command_id": int(command["id"]), "operation": OPERATION}, dispatch=False, conn=conn)
        if not submitted.get("accepted"):
            raise RuntimeError("bulk_durable_submission_failed")
        commands.attach_task(int(command["id"]), int(submitted["task_id"]), conn=conn)
    if not reused:
        task_gateway.notify_dispatch()
    return {**submitted, "ok": True, "accepted": True, "busy": False,
            "command_id": int(command["id"]), "operation": OPERATION, "reused": reused}


def _checkpoint(context, command_id):
    worker._checkpoint(context)
    storage.assert_owner(command_id, run_id=context.run_id, execution_id=context.execution_id)


def _item(target, status, code=None, reason="", **data):
    return asdict(BulkItemResult(
        target["task_id"], status, code, reason,
        {"task_id": target["task_id"], "run_id": target["run_id"], **data}))


def _cancel_inspection(target, context, command_id):
    """原父巡检终止实为协作取消；范围固定为用户确认时的 child Run。"""
    _checkpoint(context, command_id)
    if not storage.cancel_children(target["children"]):
        raise _CancellationChanged()
    _checkpoint(context, command_id)
    current = storage.read_target(target["task_id"], target["run_id"])
    if current and current["last_run_id"] == target["run_id"]:
        task_gateway._operation().reconcile_parent_task(target["task_id"])
    task_gateway.notify_dispatch()
    return {"ok": True, "state": "cancelling", "message": "已记录停止请求，任务将在安全检查点收口"}


def _terminate_codex(target, run, context, command_id):
    """保留原安全 finish/local token/账号三轴投影，提交缺口可重放。"""
    from core.codex import operation_service as codex
    if run["status"] in common._ACTIVE_RUN_STATUSES:
        _checkpoint(context, command_id)
        task_gateway._operation().terminate_run(target["run_id"], reason="用户手动终止 Codex 补跑")
    _checkpoint(context, command_id)
    with codex._LOCAL_TOKENS_LOCK:
        token = codex._LOCAL_TOKENS.get(target["run_id"])
        if token:
            token.request_local()
    current = storage.read_target(target["task_id"], target["run_id"])
    storage.project_codex(current)
    task_gateway.notify_dispatch()
    return {"ok": True, "state": current["status"], "message": "任务已终止"}


def _apply(target, context, command_id):
    if target["reason_code"]:
        reason = "任务不存在" if target["reason_code"] == "task_not_found" else "只有原生执行中的任务可以终止"
        return _item(target, "skipped", target["reason_code"], reason)
    run = storage.read_target(target["task_id"], target["run_id"])
    if not run or run["last_run_id"] != target["run_id"]:
        return _item(target, "skipped", "target_run_changed", "任务执行实例已变化，保留后续执行")
    if run["task_type"] != target["task_type"] or run["task_source"] != target["source_system"]:
        return _item(target, "skipped", "target_identity_changed", "任务来源已变化")
    if run["status"] not in common._ACTIVE_RUN_STATUSES:
        summary = run.get("result_summary") or {}
        if (summary.get("termination") == "manual" and summary.get("forced") is True
                and target["task_type"] != "codex_retry"):
            return _item(target, "updated", state=run["status"], message="原执行已终止")
        if target["task_type"] != "account_inspection_batch" and (
                target["task_type"] != "codex_retry" or not summary.get("forced")):
            return _item(target, "skipped", "target_run_changed", "原执行已经结束", state=run["status"])
    _checkpoint(context, command_id)
    if target["task_type"] == "account_inspection_batch":
        payload = _cancel_inspection(target, context, command_id)
        status = 200
    elif target["task_type"] == "codex_retry":
        payload = _terminate_codex(target, run, context, command_id)
        status = 200
    else:
        # handler 只能看见冻结 Run，不能重新选择同 Task 后续重跑的 Run。
        task = {
            "id": target["task_id"], "task_type": target["task_type"], "source_system": target["source_system"],
            "status": run["status"], "parent_task_id": run.get("parent_task_id"), "runs": [run],
        }
        callback = task_gateway.operation_action(target["task_type"], "terminate", source_system=target["source_system"])
        if callback is None:
            payload, status = {"ok": False, "error": "历史兼容任务请使用原任务停止入口"}, 409
        else:
            raw = callback(task)
            payload = dict(raw) if isinstance(raw, dict) else {"ok": bool(raw)}
            payload.setdefault("ok", True)
            status = 200 if payload["ok"] else 409
    if 200 <= status < 300 and payload.get("ok", payload.get("accepted", False)) and payload.get("state") != "empty":
        return _item(target, "updated", state=payload.get("state") or "accepted", message=payload.get("message") or "")
    return _item(target, "failed", "termination_rejected", payload.get("error") or payload.get("message") or "终止未受理")


def handle(context):
    # 当前命令可能运行于捕获的结算域；每个目标仍拥有独立事务，不能借用调用方连接。
    with common.settlement_scope(common.current_settlement_domain(), conn=None):
        try:
            return _handle(context)
        except Exception as exc:
            if worker._retryable_storage_error(exc):
                return context.defer(delay_seconds=1, reason="bulk_storage_retry", stage="bulk_terminate")
            raise


def _handle(context):
    data = context.run.get("data") or {}
    command_id = int(data.get("command_id") or 0)
    if context.run.get("task_type") != TASK_TYPE or context.run.get("source_system") != "native_operations":
        raise PermissionError("bulk_terminate_identity_mismatch")
    command = commands.get_command(command_id)
    if command["operation"] != OPERATION:
        raise PermissionError("bulk_terminate_identity_mismatch")
    stored = storage.receipt_items(command_id)
    control_errors = (
        task_gateway.OperationCancelled, task_gateway.OperationLeaseLost, task_gateway.OperationLeaseUnavailable,
        PermissionError, *task_gateway.SETTLEMENT_CONTROL_ERRORS)
    for target in storage.targets(command_id):
        _checkpoint(context, command_id)
        index = target["ordinal"]
        if index in stored:
            continue
        try:
            item = _apply(target, context, command_id)
        except _CancellationChanged:
            return context.defer(delay_seconds=1, reason="bulk_target_status_changed", stage="bulk_terminate")
        except control_errors:
            raise
        except Exception as exc:
            if worker._retryable_storage_error(exc):
                return context.defer(delay_seconds=1, reason="bulk_storage_retry", stage="bulk_terminate")
            item = _item(target, "failed", "termination_failed", "终止执行失败，请检查原任务")
        _checkpoint(context, command_id)
        # 只有回执写入借用块事务；目标终止早已独立安全提交，恢复时核对原Run补回执。
        try:
            items, _, _ = commands.execute_chunk(
                command_id, index, run_id=context.run_id, execution_id=context.execution_id,
                apply_chunk=lambda chunk, parameters, *, conn: worker._chunk_items(chunk, [item]), parameters={})
        except Exception as exc:
            if worker._retryable_storage_error(exc):
                return context.defer(delay_seconds=1, reason="bulk_storage_retry", stage="bulk_terminate")
            raise
        stored[index] = items[0]
    _checkpoint(context, command_id)
    by_key = {item["key"]: item for _, item in sorted(stored.items())}
    result = execute_chunked_bulk(
        OPERATION, command["input_targets"], lambda chunk: [by_key[key] for key in chunk],
        max_targets=100, chunk_size=1, idempotency_key=command["request_key_hash"])
    complete = {**asdict(result), "command_id": command_id}
    try:
        commands.save_result(command_id, complete, run_id=context.run_id, execution_id=context.execution_id)
    except Exception as exc:
        if worker._retryable_storage_error(exc):
            return context.defer(delay_seconds=1, reason="bulk_storage_retry", stage="bulk_terminate")
        raise
    summary = {key: value for key, value in complete.items() if key not in {"items", "chunks"}}
    status = "partial_success" if result.failed_count and result.updated_count else "failed" if result.failed_count else "success"
    return task_gateway.OperationResult(status, summary, "批量终止命令执行完成")
