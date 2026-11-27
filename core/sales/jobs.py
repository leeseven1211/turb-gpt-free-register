"""销售持久任务提交、恢复查询与执行边界。"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

from core.operations import task_gateway
from core.operations.runtime import OperationCancelled
from core.storage import postgres, records
from core.storage.operations import store as operations

from .errors import SalesError

TASK_TYPE = "sales_sync"
SOURCE_SYSTEM = "native_operations"
MAX_ITEMS = 5000
CHUNK_SIZE = 100
_EXECUTION = ContextVar("sales_execution", default=None)


def chunks(values):
    return [values[offset:offset + CHUNK_SIZE] for offset in range(0, len(values), CHUNK_SIZE)]


def item_ids(payload):
    return [value for group in payload.get("item_chunks", ()) for value in group]


def ids(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_ITEMS:
        raise SalesError("sales_invalid_ids", f"账号或条目列表必须包含 1 至 {MAX_ITEMS} 个 ID")
    if any(type(item) is not int or not 0 < item <= 2**63 - 1 for item in value):
        raise SalesError("sales_invalid_ids", "账号或条目 ID 必须是正整数")
    return sorted(set(value))


def positive_id(value):
    return ids([value])[0]


def digest(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_id(key):
    if key is None:
        key = uuid4().hex
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise SalesError("sales_invalid_request_key", "request_key 必须是 1 至 200 字符的请求标识")
    return f"sales-request:{digest(key.strip())}"


def lock(conn, key):
    records.advisory_xact_lock(conn, f"sales:{postgres.schema_name()}:{key}")


def receipt(source_id, intent, *, conn):
    """读取原请求回执，在事务内拒绝同键不同目标。"""
    tasks = operations._table("operation_tasks")
    runs = operations._table("operation_runs")
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT t.id AS task_id, t.data, r.id AS run_id, r.status
            FROM {tasks} t LEFT JOIN LATERAL (
                SELECT id, status FROM {runs} WHERE task_id=t.id ORDER BY run_no DESC LIMIT 1
            ) r ON TRUE
            WHERE t.source_system=%s AND t.source_id=%s
            """, (SOURCE_SYSTEM, source_id))
        prior = cur.fetchone()
    if prior is None:
        return None
    if (prior["data"] or {}).get("intent_digest") != intent:
        raise SalesError("sales_request_conflict", "相同请求标识已经用于不同的销售操作", 409)
    response = {key: prior[key] for key in ("task_id", "run_id", "status")}
    response.update(accepted=True, reused=True)
    prepared = prior["data"].get("preflight")
    if isinstance(prepared, dict):
        response.update(unpack_result(prepared))
    return response


def submit(payload, *, conn, source_id=None, trigger="manual"):
    result = task_gateway.submit_durable_operation(
        task_type=TASK_TYPE, account_id=None, email="", trigger=trigger,
        source_id=source_id, resource_family=TASK_TYPE, data=payload, conn=conn, dispatch=False,
    )
    if not result.get("accepted") or not result.get("task_id") or not result.get("run_id"):
        raise SalesError("sales_task_submission_failed", "销售任务入队失败，请重试", 503)
    return {key: result[key] for key in ("accepted", "task_id", "run_id", "status", "reused")}


def active_payloads(*, conn):
    tasks = operations._table("operation_tasks")
    runs = operations._table("operation_runs")
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT t.data
            FROM {tasks} t JOIN {runs} r ON r.task_id=t.id
            WHERE t.task_type=%s AND t.source_system=%s
              AND r.status IN ('queued','running','cancelling','settling','waiting')
            """, (TASK_TYPE, SOURCE_SYSTEM))
        return [row["data"] for row in cur.fetchall()]


def pack_result(result):
    return {
        **{key: value for key, value in result.items() if key != "items"},
        "item_results": chunks(result.get("items", [])),
    }


def unpack_result(result):
    return {
        **{key: value for key, value in result.items() if key not in {"item_results", "execution_id", "lease_owner"}},
        "items": [value for group in result.get("item_results", ()) for value in group],
    }


def list_jobs(*, limit=20):
    operations.init()
    tasks = operations._table("operation_tasks")
    runs = operations._table("operation_runs")
    with records.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT t.id, t.data, r.id AS run_id, r.status, r.result_summary,
                   r.error_code, r.error_message, t.created_at, t.updated_at
            FROM {tasks} t JOIN LATERAL (
                SELECT id, status, result_summary, error_code, error_message, created_at
                FROM {runs} WHERE task_id=t.id ORDER BY run_no DESC LIMIT 1
            ) r ON TRUE
            WHERE t.task_type=%s AND t.source_system=%s AND t.task_deleted_by_user IS FALSE
            ORDER BY r.created_at DESC, r.id DESC LIMIT %s
            """, (TASK_TYPE, SOURCE_SYSTEM, limit))
        tasks_found = cur.fetchall()
    jobs = []
    for task in tasks_found:
        payload = task.get("data") or {}
        summary = task.get("result_summary") or {}
        jobs.append({
            "id": task["id"], "task_id": task["id"],
            "run_id": task["run_id"],
            "status": task["status"], "action": payload.get("action"),
            "archive_only": bool(payload.get("archive_only")),
            "shop_id": payload.get("shop_id"), "product_id": payload.get("product_id"),
            "result_summary": unpack_result(summary) if summary else None,
            "error_code": summary.get("error_code") or task.get("error_code") or "",
            "error_message": summary.get("error_message") or task.get("error_message") or "",
            "created_at": task["created_at"].isoformat(), "updated_at": task["updated_at"].isoformat(),
        })
    return jobs


@contextmanager
def execution(context):
    token = _EXECUTION.set(context)
    try:
        yield
    finally:
        _EXECUTION.reset(token)


def checkpoint():
    context = _EXECUTION.get()
    if context is not None:
        context.checkpoint()


@contextmanager
def transaction():
    """执行中的写入持有 Run 行锁。账号为空的销售任务无需账号租约。"""
    context = _EXECUTION.get()
    checkpoint()
    with records.transaction() as conn:
        if context is not None:
            with conn.cursor() as cur:
                run = operations._remote_checkpoint_fence(
                    cur, context.run_id, execution_id=context.execution_id, lease_token=None, require_lease=False,
                )
                if run.get("cancel_requested_at") or run["status"] == "cancelling":
                    raise OperationCancelled("销售任务已收到取消请求")
                if run["status"] != "running" or run["task_id"] != context.task_id:
                    raise PermissionError("销售任务已失去执行权")
        yield conn
