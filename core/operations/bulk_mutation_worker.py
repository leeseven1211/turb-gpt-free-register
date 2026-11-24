"""批量命令的 Durable Worker；业务写入和完整块回执在同一事务提交。"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import math
import re
import threading
from typing import Any

from . import task_gateway
from .bulk_mutations import execute_chunked_bulk, normalize_bulk_targets
from .contracts import BulkItemResult, BulkMutationResult
from .runtime import OperationAccountDeactivated, OperationCancelled
from .task_gateway import OperationResult
from core.storage.operations import bulk_mutations as commands

TASK_TYPE = 'bulk_mutation'
_SOURCE_SYSTEM = 'native_operations'
_MAX_TARGETS = 100_000
_SECRET_PARTS = ('password', 'secret', 'token', 'cookie', 'otp', 'authorization', 'session', 'credential')
_SECRET_VALUE = re.compile(r'(?i)(?:\bbearer\s+\S+|\bsk-[a-z0-9_-]{16,}|\beyJ[a-z0-9_-]{12,}\.[a-z0-9_-]+\.[a-z0-9_-]+|-----BEGIN .*PRIVATE KEY-----)')
_HANDLER_LOCK = threading.RLock()
_RUNTIME_REGISTERED = False
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Handler:
    callback: Callable[..., Any]
    parameter_allowlist: frozenset[str]
    chunk_size: int
    after_commit: Callable[..., Any] | None = None


_HANDLERS: dict[str, _Handler] = {}


def _operation_name(operation: str) -> str:
    if not isinstance(operation, str) or not operation.strip() or len(operation) > 120:
        raise ValueError('invalid_bulk_operation')
    return operation.strip()


def _sensitive_name(key: str) -> bool:
    text = key.lower()
    return text == 'key' or text.endswith('_key') or any(part in text for part in _SECRET_PARTS)


def _json_value(value: Any, *, depth: int = 0) -> Any:
    """只接受完整的非敏感 JSON 值；不把对象转字符串，也不截断集合。"""
    if depth > 12:
        raise ValueError('bulk_payload_too_deep')
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('bulk_payload_not_finite')
        return value
    if isinstance(value, str):
        if _SECRET_VALUE.search(value):
            raise ValueError('bulk_sensitive_value')
        return value
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError('bulk_payload_key_must_be_string')
            if _sensitive_name(key):
                raise ValueError('bulk_sensitive_field')
            result[key] = _json_value(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_json_value(item, depth=depth + 1) for item in value]
    raise TypeError('bulk_payload_must_be_json')


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def registered_bulk_mutation_operations() -> tuple[str, ...]:
    with _HANDLER_LOCK:
        return tuple(sorted(_HANDLERS))


def register_runtime_handler() -> bool:
    global _RUNTIME_REGISTERED
    with _HANDLER_LOCK:
        if _RUNTIME_REGISTERED and TASK_TYPE in task_gateway.registered_operation_types():
            return False
        from . import concurrency
        concurrency.register_admission_alias(TASK_TYPE, 'maintenance_check')
        task_gateway.register_operation_handler(TASK_TYPE, _handle_claimed_bulk_mutation,
            source_systems=(_SOURCE_SYSTEM,), config_allowlist=())
        _RUNTIME_REGISTERED = True
        return True


def register_bulk_mutation_handler(operation: str, handler: Callable[..., Any], *,
        parameter_allowlist: Iterable[str] = (), chunk_size: int = 500,
        after_commit: Callable[..., Any] | None = None) -> None:
    """handler 固定接收 ``(chunk, parameters, *, conn)``，连接由块事务拥有。"""
    name = _operation_name(operation)
    if not callable(handler):
        raise TypeError('bulk_handler_not_callable')
    if after_commit is not None and not callable(after_commit):
        raise TypeError('bulk_after_commit_not_callable')
    if type(chunk_size) is not int or not 1 <= chunk_size <= 500:
        raise ValueError('invalid_bulk_chunk_size')
    allowed = frozenset(parameter_allowlist)
    if any(not isinstance(key, str) for key in allowed):
        raise TypeError('bulk_parameter_allowlist_must_be_strings')
    with _HANDLER_LOCK:
        _HANDLERS[name] = _Handler(handler, allowed, chunk_size, after_commit)


def submit_bulk_mutation(operation: str, targets: Iterable[object], parameters: Mapping[str, Any] | None,
        *, idempotency_key: str, trigger: str) -> dict[str, Any]:
    """完整命令与 durable task/run 在同一事务内创建；同键异内容显式冲突。"""
    name = _operation_name(operation)
    with _HANDLER_LOCK:
        handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError('bulk_handler_not_registered')
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 200:
        raise ValueError('invalid_idempotency_key')
    if parameters is not None and not isinstance(parameters, Mapping):
        raise TypeError('bulk_parameters_must_be_mapping')
    supplied = parameters or {}
    if set(supplied) - handler.parameter_allowlist:
        raise ValueError('bulk_parameter_not_allowed')
    safe_parameters = _json_value(supplied)
    if isinstance(targets, (str, bytes, Mapping)) or not isinstance(targets, Iterable):
        raise TypeError('bulk_targets_must_be_iterable')
    raw = []
    for value in targets:
        raw.append(_json_value(value))
        if len(raw) > _MAX_TARGETS:
            raise ValueError('bulk_target_limit_exceeded')
    normalized = normalize_bulk_targets(raw, max_targets=_MAX_TARGETS)
    request_hash = _digest(idempotency_key.strip())
    payload_hash = _digest({'operation':name,'input_targets':raw,
        'parameters':safe_parameters,'chunk_size':handler.chunk_size})
    commands.init()
    with task_gateway._operation()._connect() as conn:
        command, reused = commands.create_command(operation=name, request_key_hash=request_hash,
            payload_hash=payload_hash,input_targets=raw,targets=list(normalized.targets),
            parameters=safe_parameters,chunk_size=handler.chunk_size,
            duplicate_count=normalized.duplicate_count,conn=conn)
        command_id = int(command['id'])
        submitted = task_gateway.submit_durable_operation(task_type=TASK_TYPE, account_id=None, email='',
            trigger=str(trigger or 'manual'), source_system=_SOURCE_SYSTEM,
            source_id=f'bulk-command:{command_id}', idempotency_key=request_hash,
            resource_family='bulk_mutation', data={'bulk_mutation':True,'command_id':command_id,'operation':name},
            dispatch=False, conn=conn)
        if not submitted.get('accepted') or not submitted.get('task_id'):
            raise RuntimeError('bulk_durable_submission_failed')
        commands.attach_task(command_id, submitted['task_id'], conn=conn)
    if not reused:
        task_gateway.notify_dispatch()
    return {**submitted,'command_id':command_id,'operation':name,'reused':reused,'busy':False}


def run_bulk_mutation(run_id: int) -> dict[str, Any]:
    """校验类型和来源后，才允许共享 gateway 认领批量命令。"""
    run = task_gateway._operation().get_run(int(run_id))
    if not run:
        return {'status':'not_claimed','run_id':int(run_id)}
    if (run.get('task_type') != TASK_TYPE or run.get('source_system') != _SOURCE_SYSTEM
            or not isinstance(run.get('data'), Mapping) or not run['data'].get('command_id')):
        return {'status':'not_bulk_mutation','run_id':int(run_id)}
    register_runtime_handler()
    return task_gateway._execute_operation_handler(TASK_TYPE, int(run_id))


def _chunk_items(chunk: tuple, raw: Any) -> list[dict]:
    """只有 handler 明确确认的目标才成功；漏报目标返回稳定失败原因。"""
    if isinstance(raw, BulkMutationResult):
        values = raw.items
    elif isinstance(raw, BulkItemResult):
        values = [raw]
    elif isinstance(raw, Mapping):
        values = []
        for key, value in raw.items():
            if isinstance(value, BulkItemResult):
                values.append(value)
            elif isinstance(value, Mapping):
                values.append({**value,'key':value.get('key',key)})
            else:
                values.append({'key':key,'status':value})
    elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
        values = raw
    else:
        values = ()
    by_key = {}
    for value in values:
        if isinstance(value, BulkItemResult):
            item = value
        elif isinstance(value, Mapping):
            item = BulkItemResult(key=value.get('key'),status=value.get('status'),
                reason_code=value.get('reason_code'),reason=value.get('reason') or '',data=value.get('data'))
        else:
            continue
        if item.key in chunk:
            by_key[item.key] = item
    result = []
    for target in chunk:
        item = by_key.get(target, BulkItemResult(target,'failed',
            'bulk_result_missing','handler 未返回目标回执'))
        # key 是逐项目契约的目标身份，不是可携带凭据的任意参数字段。
        result.append({
            'key': _json_value(item.key),
            'status': item.status,
            'reason_code': _json_value(item.reason_code),
            'reason': _json_value(item.reason),
            'data': _json_value(item.data),
        })
    return result


def _checkpoint(context) -> None:
    context.checkpoint()
    execution = getattr(context, '_execution', None)
    if execution is not None:
        from . import concurrency
        if not concurrency.validate_execution(execution):
            raise task_gateway.OperationLeaseLost('bulk_execution_permit_lost')


def _handle_claimed_bulk_mutation(context) -> OperationResult:
    data = context.run.get('data') or {}
    if (context.run.get('task_type') != TASK_TYPE or context.run.get('source_system') != _SOURCE_SYSTEM
            or not data.get('command_id')):
        raise PermissionError('bulk_command_identity_mismatch')
    commands.init()
    command_id = int(data['command_id'])
    command = commands.get_command(command_id)
    name = command['operation']
    with _HANDLER_LOCK:
        spec = _HANDLERS.get(name)
    if spec is None:
        return OperationResult.failed('批量操作 handler 未注册',
            {'command_id':command_id,'operation':name,'reason_code':'bulk_handler_not_registered'})
    control_errors = (OperationCancelled, OperationAccountDeactivated, task_gateway.OperationLeaseLost,
        PermissionError, *task_gateway.SETTLEMENT_CONTROL_ERRORS)
    receipts = {}
    total_chunks = (len(command['targets']) + command['chunk_size'] - 1) // command['chunk_size']
    for index in range(total_chunks):
        _checkpoint(context)
        def apply(chunk, parameters, *, conn):
            return _chunk_items(chunk, spec.callback(chunk, parameters, conn=conn))
        try:
            items, reused = commands.execute_chunk(command_id,index,run_id=context.run_id,
                execution_id=context.execution_id,apply_chunk=apply)
        except control_errors:
            raise
        except Exception:
            # 业务异常先回滚整块，再持久化该块失败事实；取消和归属错误始终上抛。
            def failure(chunk, parameters, *, conn):
                return [asdict(BulkItemResult(key,'failed','bulk_chunk_failed','当前分块执行失败')) for key in chunk]
            items, reused = commands.execute_chunk(command_id,index,run_id=context.run_id,
                execution_id=context.execution_id,apply_chunk=failure)
        if spec.after_commit is not None:
            start = index * command['chunk_size']
            chunk = tuple(command['targets'][start:start + command['chunk_size']])
            try:
                # 已提交块重入也重发幂等导出调度，补偿提交后进程退出的通知缺口。
                spec.after_commit(chunk, command['parameters'], items)
            except control_errors:
                raise
            except Exception:
                logger.warning('批量命令提交后通知暂未完成：command_id=%s chunk_index=%s',command_id,index)
        receipts.update({item['key']:item for item in items})
        if not reused:
            try:
                context.report(stage='bulk_mutation', state='success', event_type='bulk.chunk.completed',
                    message=f'批量分块 {index + 1} 已提交', detail={'command_id':command_id,'chunk_index':index,
                        'requested_count':len(items),'failed_count':sum(item['status']=='failed' for item in items)})
            except control_errors:
                raise
            except Exception:
                logger.warning('批量命令摘要事件暂未写入：command_id=%s chunk_index=%s',command_id,index)
    _checkpoint(context)
    # 此处只合并已经提交的回执，不调用业务 handler，控制异常不进入宽泛分块捕获。
    result = execute_chunked_bulk(name,command['input_targets'],
        lambda chunk:[receipts[key] for key in chunk],max_targets=_MAX_TARGETS,
        chunk_size=command['chunk_size'],idempotency_key=command['request_key_hash'])
    complete = {**asdict(result),'command_id':command_id}
    commands.save_result(command_id,complete,run_id=context.run_id,execution_id=context.execution_id)
    summary = {key:value for key,value in complete.items() if key not in {'items','chunks'}}
    summary['chunk_count'] = total_chunks
    status = ('partial_success' if result.updated_count else 'failed') if result.failed_count else 'success'
    return OperationResult(status,summary,'批量命令执行完成')


__all__ = ['TASK_TYPE','register_runtime_handler','register_bulk_mutation_handler',
    'registered_bulk_mutation_operations','submit_bulk_mutation','run_bulk_mutation']
