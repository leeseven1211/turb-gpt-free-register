"""批量变更命令及完整分块回执；业务变更与回执共享同一块事务。"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import threading
from typing import Any

from core.operations.runtime import OperationCancelled
from core.storage.operations import common, schema

_LOCK = threading.RLock()
_READY: set[tuple[str, str]] = set()
_COMMANDS = 'operation_bulk_mutation_commands'
_RECEIPTS = 'operation_bulk_mutation_receipts'


def _json(value: Any) -> str:
    # 参数和回执已由专用命令边界逐字段验证；完整集合不能经过通用日志截断。
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def init() -> None:
    schema.init_operation_schema()
    from core.storage import postgres
    key = (postgres.database_url(), common._schema_name())
    with _LOCK:
        if key in _READY:
            return
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                (f'{key[1]}:bulk-mutation-schema',))
            cur.execute(f'''CREATE TABLE IF NOT EXISTS {common._table(_COMMANDS)} (
                id BIGSERIAL PRIMARY KEY,
                request_key_hash TEXT NOT NULL UNIQUE,
                operation TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                input_targets JSONB NOT NULL,
                targets JSONB NOT NULL,
                parameters JSONB NOT NULL,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                chunk_size INTEGER NOT NULL CHECK (chunk_size BETWEEN 1 AND 500),
                task_id BIGINT REFERENCES {common._table('operation_tasks')}(id) ON DELETE SET NULL,
                result JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                completed_at TIMESTAMPTZ
            )''')
            cur.execute(f'ALTER TABLE {common._table(_COMMANDS)} ADD COLUMN IF NOT EXISTS duplicate_count INTEGER NOT NULL DEFAULT 0')
            cur.execute(f'''CREATE TABLE IF NOT EXISTS {common._table(_RECEIPTS)} (
                command_id BIGINT NOT NULL REFERENCES {common._table(_COMMANDS)}(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
                run_id BIGINT,
                execution_id TEXT NOT NULL,
                items JSONB NOT NULL,
                committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (command_id, chunk_index)
            )''')
        _READY.add(key)


def create_command(*, operation: str, request_key_hash: str, payload_hash: str,
                   input_targets: list, targets: list, parameters: Mapping[str, Any],
                   chunk_size: int, duplicate_count: int, conn) -> tuple[dict, bool]:
    """同一请求串行比较指纹；调用者负责在本事务中继续 durable 入队。"""
    with conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
            (f'{common._schema_name()}:bulk-mutation-request:{request_key_hash}',))
        cur.execute(f'SELECT * FROM {common._table(_COMMANDS)} WHERE request_key_hash=%s FOR UPDATE',
            (request_key_hash,))
        prior = cur.fetchone()
        if prior:
            if prior['payload_hash'] != payload_hash or prior['operation'] != operation:
                raise ValueError('idempotency_key_conflict')
            return dict(prior), True
        cur.execute(f'''INSERT INTO {common._table(_COMMANDS)}
            (request_key_hash,operation,payload_hash,input_targets,targets,parameters,chunk_size,duplicate_count)
            VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s) RETURNING *''',
            (request_key_hash,operation,payload_hash,_json(input_targets),_json(targets),_json(parameters),chunk_size,duplicate_count))
        return dict(cur.fetchone()), False


def attach_task(command_id: int, task_id: int, *, conn) -> None:
    with conn.cursor() as cur:
        cur.execute(f'UPDATE {common._table(_COMMANDS)} SET task_id=%s WHERE id=%s',
            (int(task_id), int(command_id)))


def get_command(command_id: int, *, conn=None) -> dict:
    if conn is None:
        init()
        with common._connect() as own:
            return get_command(command_id, conn=own)
    with conn.cursor() as cur:
        cur.execute(f'SELECT * FROM {common._table(_COMMANDS)} WHERE id=%s', (int(command_id),))
        row = cur.fetchone()
        if row is None:
            raise LookupError('bulk_command_not_found')
        return dict(row)


def _execution_fence(cur, command: Mapping[str, Any], run_id: int, execution_id: str) -> None:
    """持 Run 锁直到业务与回执共同提交，阻止旧执行覆盖新 owner。"""
    cur.execute(f'''SELECT r.status,r.execution_id,r.cancel_requested_at,r.task_id,r.data
        FROM {common._table('operation_runs')} r WHERE id=%s FOR UPDATE''', (int(run_id),))
    run = cur.fetchone()
    if (run is None or run['execution_id'] != execution_id
            or run['task_id'] != command['task_id']
            or (run['data'] or {}).get('command_id') != command['id']):
        raise PermissionError('bulk_execution_fenced')
    if run['cancel_requested_at'] is not None or run['status'] == 'cancelling':
        raise OperationCancelled('批量命令已收到取消请求')
    if run['status'] != 'running':
        raise PermissionError('bulk_execution_fenced')


def execute_chunk(command_id: int, chunk_index: int, *, run_id: int, execution_id: str,
                  apply_chunk: Callable[..., list[dict]]) -> tuple[list[dict], bool]:
    """重入只读已提交回执；新增业务变更和完整回执在同一事务内提交。"""
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f'SELECT * FROM {common._table(_COMMANDS)} WHERE id=%s FOR UPDATE', (int(command_id),))
        row = cur.fetchone()
        if row is None:
            raise LookupError('bulk_command_not_found')
        command = dict(row)
        _execution_fence(cur, command, run_id, execution_id)
        cur.execute(f'SELECT items FROM {common._table(_RECEIPTS)} WHERE command_id=%s AND chunk_index=%s',
            (int(command_id), int(chunk_index)))
        receipt = cur.fetchone()
        if receipt is not None:
            return receipt['items'], True
        start = int(chunk_index) * command['chunk_size']
        chunk = tuple(command['targets'][start:start + command['chunk_size']])
        if not chunk:
            raise ValueError('bulk_chunk_out_of_range')
        items = apply_chunk(chunk, command['parameters'], conn=conn)
        _execution_fence(cur, command, run_id, execution_id)
        cur.execute(f'''INSERT INTO {common._table(_RECEIPTS)}
            (command_id,chunk_index,run_id,execution_id,items) VALUES (%s,%s,%s,%s,%s::jsonb)''',
            (int(command_id),int(chunk_index),int(run_id),str(execution_id),_json(items)))
        return items, False


def save_result(command_id: int, result: Mapping[str, Any], *, run_id: int, execution_id: str) -> None:
    """保存完整最终结果；通用 Run 只保存计数和命令引用。"""
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f'SELECT * FROM {common._table(_COMMANDS)} WHERE id=%s FOR UPDATE', (int(command_id),))
        command = cur.fetchone()
        if command is None:
            raise LookupError('bulk_command_not_found')
        _execution_fence(cur, command, run_id, execution_id)
        cur.execute(f'UPDATE {common._table(_COMMANDS)} SET result=%s::jsonb,completed_at=now() WHERE id=%s',
            (_json(result),int(command_id)))


def get_command_result(command_id: int) -> dict:
    init()
    with common._connect() as conn:
        command = get_command(command_id, conn=conn)
        if command['result'] is not None:
            return command['result']
        with conn.cursor() as cur:
            cur.execute(f'SELECT chunk_index,items FROM {common._table(_RECEIPTS)} WHERE command_id=%s ORDER BY chunk_index',
                (int(command_id),))
            receipts = list(cur.fetchall())
        items = [item for receipt in receipts for item in receipt['items']]
        return {'command_id':int(command_id),'operation':command['operation'],'items':items,
            'requested_count':len(command['input_targets']),'unique_count':len(command['targets']),
            'duplicate_count':command['duplicate_count'],
            'updated_count':sum(item['status']=='updated' for item in items),
            'failed_count':sum(item['status']=='failed' for item in items),
            'skipped_count':sum(item['status']=='skipped' for item in items)}
