"""批量命令的 Durable Worker 入口。

批量命令只保存可重放的目标和非敏感参数，真正的业务副作用由调用方注册的
handler 执行。每个已完成分块先写入 operation event，再允许命令进入终态；
Worker 重启后可以从这些事件恢复，跳过已经确认完成的分块。
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict
import hashlib
import inspect
import threading
from typing import Any

from . import task_gateway
from .task_gateway import OperationResult
from .bulk_mutations import execute_chunked_bulk
from .contracts import BulkItemResult, BulkMutationResult

TASK_TYPE = "bulk_mutation"
_SOURCE_SYSTEM = "native_operations"
_SENSITIVE_PARTS = frozenset({"password", "secret", "token", "cookie", "otp", "authorization"})
_HANDLERS: dict[str, Callable[..., Any]] = {}
_HANDLER_LOCK = threading.RLock()
_RUNTIME_REGISTERED = False


def _safe_payload(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """复制命令 payload，并移除外部凭据等敏感字段。"""
    if depth > 5:
        return "[truncated]"
    lowered = str(key).strip().lower()
    if lowered and any(part in lowered for part in _SENSITIVE_PARTS):
        return None
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:120]:
            name = str(raw_key)[:100]
            safe = _safe_payload(raw_value, key=name, depth=depth + 1)
            if safe is not None:
                result[name] = safe
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_payload(item, depth=depth + 1) for item in list(value)[:5000]]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value if not isinstance(value, str) else value[:2000]
    return str(value)[:500]


def _operation_name(operation: str) -> str:
    name = str(operation or "").strip()
    if not name:
        raise ValueError("批量操作名称不能为空")
    if len(name) > 120:
        raise ValueError("批量操作名称过长")
    return name


def registered_bulk_mutation_operations() -> tuple[str, ...]:
    with _HANDLER_LOCK:
        return tuple(sorted(_HANDLERS))


def _dispatch_registered_handler(context) -> OperationResult:
    return _handle_claimed_bulk_mutation(context)


def register_runtime_handler() -> bool:
    """将通用批量命令接入现有 durable dispatcher。"""
    global _RUNTIME_REGISTERED
    with _HANDLER_LOCK:
        if _RUNTIME_REGISTERED:
            return False
        # bulk_mutation 使用已有 maintenance_check 并发预算，避免新增未审计
        # 的并发策略键；Task Gateway 仍负责真实 claim、lease 和恢复。
        from . import concurrency

        concurrency.register_admission_alias(TASK_TYPE, "maintenance_check")
        task_gateway.register_operation_handler(
            TASK_TYPE,
            _dispatch_registered_handler,
            source_systems=(_SOURCE_SYSTEM,),
            config_allowlist=(),
        )
        _RUNTIME_REGISTERED = True
        return True


def register_bulk_mutation_handler(operation: str, handler: Callable[..., Any]) -> None:
    """注册一个 operation handler，handler 接收 ``(chunk, parameters)``。"""
    name = _operation_name(operation)
    if not callable(handler):
        raise TypeError("批量操作 handler 必须可调用")
    with _HANDLER_LOCK:
        _HANDLERS[name] = handler
    register_runtime_handler()


def _idempotency_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def submit_bulk_mutation(
    operation: str,
    targets: Iterable[object],
    parameters: Mapping[str, Any] | None,
    *,
    idempotency_key: str,
    trigger: str,
) -> dict[str, Any]:
    """提交一个可恢复的批量命令；幂等键映射到同一 durable task。"""
    name = _operation_name(operation)
    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError("批量命令必须提供 idempotency_key")
    if isinstance(targets, (str, bytes, Mapping)) or not isinstance(targets, Iterable):
        raise TypeError("targets 必须是可迭代目标集合")
    target_values = list(targets)
    safe_targets = _safe_payload(target_values)
    safe_parameters = _safe_payload(parameters or {})
    digest = _idempotency_digest(key)
    source_id = f"bulk:{name}:{digest}"
    payload = {
        "bulk_mutation": True,
        "operation": name,
        "targets": safe_targets,
        "parameters": safe_parameters,
        "idempotency_key_digest": digest,
    }
    register_runtime_handler()
    return task_gateway.submit_durable_operation(
        task_type=TASK_TYPE,
        account_id=None,
        email="",
        trigger=str(trigger or "manual"),
        source_system=_SOURCE_SYSTEM,
        source_id=source_id,
        idempotency_key=digest,
        resource_family="bulk_mutation",
        data=payload,
    )


def run_bulk_mutation(run_id: int) -> dict[str, Any]:
    """让共享 durable gateway 领取并执行一个批量命令 Run。"""
    register_runtime_handler()
    return task_gateway._execute_operation_handler(TASK_TYPE, int(run_id))


def _invoke_handler(handler: Callable[..., Any], operation: str, chunk: tuple[Any, ...], parameters: Mapping[str, Any]) -> Any:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return handler(chunk, parameters)
    positional = [item for item in signature.parameters.values()
                  if item.kind in (item.POSITIONAL_ONLY, item.POSITIONAL_OR_KEYWORD)]
    has_varargs = any(item.kind == item.VAR_POSITIONAL for item in signature.parameters.values())
    if has_varargs or len(positional) >= 3:
        return handler(operation, chunk, parameters)
    if len(positional) == 1:
        return handler(chunk)
    if len(positional) == 0:
        return handler()
    return handler(chunk, parameters)


def _item_payload(item: BulkItemResult) -> dict[str, Any]:
    raw = asdict(item)
    return _safe_payload(raw)


def _chunk_items(chunk: tuple[Any, ...], raw: Any) -> list[dict[str, Any]]:
    """将 handler 返回值归一化为可写入事件的逐项目回执。"""
    if raw is None:
        return [_item_payload(BulkItemResult(key=target, status="updated")) for target in chunk]
    if isinstance(raw, BulkMutationResult):
        values = raw.items
    elif isinstance(raw, Mapping):
        values = []
        for key, value in raw.items():
            if isinstance(value, (BulkItemResult, Mapping)):
                if isinstance(value, Mapping) and "key" not in value:
                    values.append({**value, "key": key})
                else:
                    values.append(value)
            else:
                values.append(BulkItemResult(key=key, status=str(value or "updated")))
    elif isinstance(raw, BulkItemResult):
        values = [raw]
    elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
        values = list(raw)
    else:
        values = [raw]
    by_key: dict[Any, BulkItemResult] = {}
    for value in values:
        if isinstance(value, BulkItemResult):
            item = value
        elif isinstance(value, Mapping):
            item = BulkItemResult(
                key=value.get("key"),
                status=str(value.get("status") or "updated"),
                reason_code=value.get("reason_code"),
                reason=str(value.get("reason") or ""),
                data=value.get("data"),
            )
        else:
            continue
        if item.key in chunk:
            by_key[item.key] = item
    return [_item_payload(by_key.get(target, BulkItemResult(key=target, status="updated"))) for target in chunk]


def _load_completed_chunks(context) -> dict[int, list[dict[str, Any]]]:
    try:
        operation = task_gateway._operation()
        page = operation.list_task_events(context.task_id, run_id=context.run_id, limit=1000)
        items = page.get("items") if isinstance(page, Mapping) else []
    except Exception:
        # 单元测试和内存适配器可直接提供事件；生产路径始终走 durable store。
        items = getattr(context, "events", [])
    completed: dict[int, list[dict[str, Any]]] = {}
    for event in items or []:
        if not isinstance(event, Mapping) or event.get("event_type") != "bulk.chunk.completed":
            continue
        detail = event.get("detail") if isinstance(event.get("detail"), Mapping) else {}
        try:
            index = int(detail.get("chunk_index"))
        except (TypeError, ValueError):
            continue
        values = detail.get("items")
        if isinstance(values, list):
            completed[index] = values
    return completed


def _result_summary(result: BulkMutationResult) -> dict[str, Any]:
    return _safe_payload({
        "operation": result.operation,
        "idempotency_key": result.idempotency_key,
        "requested_count": result.requested_count,
        "unique_count": result.unique_count,
        "duplicate_count": result.duplicate_count,
        "updated_count": result.updated_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count,
        "items": [_item_payload(item) for item in result.items],
        "chunks": list(result.chunks),
    })


def _handle_claimed_bulk_mutation(context) -> OperationResult:
    run = context.run if isinstance(context.run, Mapping) else {}
    data = run.get("data") if isinstance(run.get("data"), Mapping) else {}
    operation = _operation_name(str(data.get("operation") or ""))
    with _HANDLER_LOCK:
        handler = _HANDLERS.get(operation)
    if handler is None:
        return OperationResult.failed(
            f"批量操作 handler 未注册：{operation}",
            {"reason_code": "bulk_handler_not_registered", "operation": operation},
        )
    targets = data.get("targets") if isinstance(data.get("targets"), list) else []
    parameters = data.get("parameters") if isinstance(data.get("parameters"), Mapping) else {}
    chunk_size = parameters.get("chunk_size", data.get("chunk_size", 500))
    try:
        chunk_size = int(chunk_size)
    except (TypeError, ValueError):
        chunk_size = 500
    completed = _load_completed_chunks(context)
    chunk_index = 0

    def apply_chunk(chunk: tuple[Any, ...]):
        nonlocal chunk_index
        index = chunk_index
        chunk_index += 1
        if index in completed:
            return completed[index]
        raw = _invoke_handler(handler, operation, chunk, parameters)
        items = _chunk_items(chunk, raw)
        context.report(
            stage="bulk_mutation",
            state="success",
            message=f"批量分块 {index} 已完成",
            event_type="bulk.chunk.completed",
            detail={"chunk_index": index, "items": items},
        )
        return items

    result = execute_chunked_bulk(
        operation,
        targets,
        apply_chunk,
        chunk_size=chunk_size,
        idempotency_key=str(data.get("idempotency_key_digest") or "") or None,
    )
    failed = result.failed_count > 0
    if failed and result.updated_count:
        status = "partial_success"
    elif failed:
        status = "failed"
    else:
        status = "success"
    return OperationResult(status, _result_summary(result), "批量命令执行完成")


__all__ = [
    "TASK_TYPE",
    "register_runtime_handler",
    "register_bulk_mutation_handler",
    "registered_bulk_mutation_operations",
    "submit_bulk_mutation",
    "run_bulk_mutation",
]
