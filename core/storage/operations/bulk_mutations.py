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
                outcome TEXT NOT NULL DEFAULT 'updated',
                committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (command_id, chunk_index)
            )''')
            cur.execute(f"ALTER TABLE {common._table(_RECEIPTS)} ADD COLUMN IF NOT EXISTS outcome TEXT NOT NULL DEFAULT 'updated'")
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


def _chunk_command(cur, command_id: int, chunk_index: int) -> dict:
    """只返回所需块与小元数据，避免逐块反序列化全部输入集合。"""
    cur.execute(f'''SELECT id,task_id,chunk_size,
        jsonb_path_query_array(targets,
            format('$[%%s to %%s]',%s * chunk_size,(%s + 1) * chunk_size - 1)::jsonpath) AS chunk
        FROM {common._table(_COMMANDS)} WHERE id=%s FOR UPDATE''',
        (int(chunk_index),int(chunk_index),int(command_id)))
    row = cur.fetchone()
    if row is None:
        raise LookupError('bulk_command_not_found')
    return dict(row)


def execute_chunk(command_id: int, chunk_index: int, *, run_id: int, execution_id: str,
                  apply_chunk: Callable[..., list[dict]], parameters: Mapping[str, Any],
                  outcome: str | None = None) -> tuple[list[dict], bool, str]:
    """重入只读已提交回执；新增业务变更和完整回执在同一事务内提交。"""
    with common._connect() as conn, conn.cursor() as cur:
        command = _chunk_command(cur, command_id, chunk_index)
        _execution_fence(cur, command, run_id, execution_id)
        cur.execute(f'SELECT items,outcome FROM {common._table(_RECEIPTS)} WHERE command_id=%s AND chunk_index=%s',
            (int(command_id), int(chunk_index)))
        receipt = cur.fetchone()
        if receipt is not None:
            return receipt['items'], True, receipt['outcome']
        chunk = tuple(command['chunk'])
        if not chunk:
            raise ValueError('bulk_chunk_out_of_range')
        items = apply_chunk(chunk, parameters, conn=conn)
        chunk_outcome = outcome or ('failed' if any(item['status']=='failed' for item in items) else 'updated')
        _execution_fence(cur, command, run_id, execution_id)
        cur.execute(f'''INSERT INTO {common._table(_RECEIPTS)}
            (command_id,chunk_index,run_id,execution_id,items,outcome) VALUES (%s,%s,%s,%s,%s::jsonb,%s)''',
            (int(command_id),int(chunk_index),int(run_id),str(execution_id),_json(items),chunk_outcome))
        return items, False, chunk_outcome


def save_result(command_id: int, result: Mapping[str, Any], *, run_id: int, execution_id: str) -> None:
    """保存完整最终结果；通用 Run 只保存计数和命令引用。"""
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f'SELECT id,task_id FROM {common._table(_COMMANDS)} WHERE id=%s FOR UPDATE', (int(command_id),))
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


def read_receipt_page(command_id: int, *, offset: int, limit: int) -> dict:
    """Read the current Run and item page from the same PostgreSQL snapshot."""
    init()
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""
            WITH command AS (
                SELECT c.id AS command_id, c.operation, c.task_id, r.id AS run_id,
                       CASE
                           WHEN r.status = 'interrupted' AND r.cancel_requested_at IS NULL
                               AND r.result_summary->>'recovery_reason' = 'worker_restart' THEN 'queued'
                           WHEN r.status IS NOT NULL THEN r.status
                           WHEN (c.result->>'failed_count')::integer = 0 THEN 'success'
                           WHEN (c.result->>'updated_count')::integer > 0 THEN 'partial_success'
                           ELSE 'failed'
                       END AS status,
                       jsonb_array_length(c.input_targets) AS requested_count,
                       jsonb_array_length(c.targets) AS unique_count,
                       c.duplicate_count, c.result
                FROM {common._table(_COMMANDS)} c
                LEFT JOIN {common._table('operation_tasks')} t ON t.id = c.task_id
                LEFT JOIN {common._table('operation_runs')} r ON r.id = t.last_run_id
                WHERE c.id = %s
            ), running_items AS MATERIALIZED (
                SELECT receipt.chunk_index, item.value, item.position
                FROM command c
                JOIN {common._table(_RECEIPTS)} receipt USING (command_id)
                CROSS JOIN LATERAL jsonb_array_elements(receipt.items)
                    WITH ORDINALITY AS item(value, position)
                WHERE c.result IS NULL
            ), running_counts AS (
                SELECT count(*) AS item_count,
                       count(*) FILTER (WHERE value->>'status' = 'updated') AS updated_count,
                       count(*) FILTER (WHERE value->>'status' = 'skipped') AS skipped_count,
                       count(*) FILTER (WHERE value->>'status' = 'failed') AS failed_count
                FROM running_items
            ), page AS (
                SELECT page_items.value, page_items.chunk_index, page_items.position
                FROM (
                    SELECT value, chunk_index, position FROM running_items
                    UNION ALL
                    SELECT item.value, 0, item.position FROM command c
                    CROSS JOIN LATERAL jsonb_array_elements(c.result->'items')
                        WITH ORDINALITY AS item(value, position)
                ) page_items
                ORDER BY chunk_index, position
                LIMIT %s OFFSET %s
            )
            SELECT command_id, operation, task_id, run_id, status, requested_count, unique_count, duplicate_count,
                   COALESCE(jsonb_array_length(result->'items'), item_count) AS item_count,
                   COALESCE((result->>'updated_count')::integer, updated_count) AS updated_count,
                   COALESCE((result->>'skipped_count')::integer, skipped_count) AS skipped_count,
                   COALESCE((result->>'failed_count')::integer, failed_count) AS failed_count,
                   COALESCE((SELECT jsonb_agg(value ORDER BY chunk_index, position) FROM page), '[]'::jsonb) AS items
            FROM command CROSS JOIN running_counts
        """, (command_id, limit, offset))
        row = cur.fetchone()
        if row is None:
            raise LookupError("bulk_command_not_found")
        return dict(row)


def list_recoverable_commands(operations: tuple[str, ...], *, limit: int = 100) -> list[dict]:
    """Only the current attempt of a native orphan with released ownership may resume."""
    init()
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT c.task_id, r.id AS run_id
            FROM {common._table('operation_tasks')} t
            JOIN {common._table('operation_runs')} r ON r.id = t.last_run_id AND r.task_id = t.id
            JOIN {common._table(_COMMANDS)} c ON c.task_id = t.id
                AND r.data->>'command_id' = c.id::text
            WHERE t.task_type = 'bulk_mutation' AND t.source_system = 'native_operations'
              AND t.status = 'interrupted' AND r.status = 'interrupted'
              AND r.result_summary->>'recovery_reason' = 'worker_restart'
              AND r.cancel_requested_at IS NULL AND c.operation = ANY(%s)
              AND NOT EXISTS (
                  SELECT 1 FROM {common._permit_table()} p
                  WHERE p.run_id = r.id AND p.released_at IS NULL
              )
              AND NOT EXISTS (
                  SELECT 1 FROM {common._table('account_operation_leases')} lease
                  WHERE lease.run_id = r.id AND lease.expires_at > now()
              )
            ORDER BY r.id LIMIT %s
        """, (list(operations), limit))
        return list(cur.fetchall())


def queue_counts() -> dict:
    """Aggregate live queue facts without fetching command payloads or receipts."""
    init()
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT count(*) FILTER (WHERE status = 'queued') AS queued_commands,
                   count(*) FILTER (
                       WHERE status IN ('running', 'cancelling', 'settling', 'stopping')
                   ) AS active_commands
            FROM {common._table('operation_tasks')}
            WHERE task_type = 'bulk_mutation' AND source_system = 'native_operations'
              AND status IN ('queued', 'running', 'cancelling', 'settling', 'stopping')
        """)
        return dict(cur.fetchone())
