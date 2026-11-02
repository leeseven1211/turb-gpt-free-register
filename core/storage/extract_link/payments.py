"""跨提链 Run 的独立支付意图，私有请求及查询凭据始终加密。"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

from psycopg.errors import UniqueViolation

from core.payments.xxsyun import safe_message, validate_api_base
from core.storage import runtime_config
from core.storage.operations import store as operation

_SUBMISSION_STATES = {"reserved", "submitting", "submitted", "unknown", "rejected"}
_PAYMENT_STATES = {"pending", "unknown", "succeeded", "failed"}
_SUMMARY_FIELDS = {
    "remote_status", "failure_code", "failure_message", "message", "can_cancel", "cost_points",
    "retry_after_seconds", "plus_verification_status", "plus_status", "payment_confirmation_source",
    "payment_confirmed_plan_checked_at", "platform_plus_checked_at", "platform_plus_status",
    "payment_check_status", "payment_source", "submission_unknown", "local_reconcile_halted",
    "local_reconcile_reason", "local_reconcile_halted_at", "last_query_at", "query_failures",
    "amount_due_minor", "currency", "error_category",
    "plus_failure_code", "plus_failure_message",
}


class PaymentCapacityUnavailable(RuntimeError):
    """共享支付名额不足，由持久调度器延期而非占用线程等待。"""
    code = "PAYMENT_CAPACITY_UNAVAILABLE"

    def __init__(self):
        super().__init__("XXSYUN 独立支付并发名额已满，等待已有订单结束")


def _table():
    return operation._table("extract_link_payment_orders")


def _lock(cur):
    # 所有提链平台、Key 和 API 地址共享平台名额；读写使用同一事务锁。
    cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"{operation._schema_name()}:independent-payment:xxsyun",))


def _owner(cur, *, run_id, task_id=None, account_id=None, check_account=False, execution_fence=None):
    if execution_fence is not None:
        from core.operations.task_gateway import OperationLeaseLost
        try:
            if int(execution_fence.get("run_id") or 0) != int(run_id):
                raise PermissionError("执行围栏与支付 Run 不匹配")
            operation.fence_execution(cur, **execution_fence)
        except (PermissionError, LookupError, ValueError, TypeError) as exc:
            raise OperationLeaseLost("当前执行或租约失效，支付状态未写入") from exc
    cur.execute(f"SELECT task_id, account_id FROM {operation._table('operation_runs')} WHERE id=%s FOR UPDATE", (int(run_id),))
    run = cur.fetchone()
    if not run:
        raise LookupError("支付执行实例不存在")
    if task_id is not None and int(run["task_id"]) != int(task_id):
        raise ValueError("支付 Run 不属于当前任务")
    cur.execute(f"SELECT last_run_id, account_id FROM {operation._table('operation_tasks')} WHERE id=%s", (run["task_id"],))
    task = cur.fetchone()
    if not task or int(task["last_run_id"] or 0) != int(run_id):
        raise ValueError("支付写入必须使用当前 Run")
    if check_account and (run["account_id"] != account_id or task["account_id"] != account_id):
        raise ValueError("支付账号与当前任务不匹配")
    return int(run["task_id"])


def _private(row):
    return json.loads(runtime_config.decrypt_private_text(row["private_encrypted"]))


def _public(row, *, include_private=False):
    if row is None:
        return None
    result = {key: value for key, value in row.items() if key != "private_encrypted"}
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if include_private:
        result["private"] = _private(row)
    return result


def _text(value, *, name, optional=False):
    if optional and value is None:
        return ""
    if not isinstance(value, (str, int)) or not str(value).strip() or len(str(value)) > 240 or any(ord(ch) < 32 for ch in str(value)):
        raise ValueError(f"{name} 无效")
    return str(value).strip()


def reserve_payment_order(*, task_id, run_id, account_id, extract_provider_id,
                          extract_job_id, material_job_id, payment_provider,
                          material_fingerprint, api_base, api_key, request_body,
                          concurrency, new_attempt=False, execution_fence=None) -> dict:
    """原子预约稳定意图；已有非失败订单始终沿原地址、Key 和请求恢复。"""
    operation.init()
    if str(payment_provider) != "xxsyun":
        raise ValueError("未知独立支付平台")
    with operation._connect() as conn, conn.cursor() as cur:
        _lock(cur)
        _owner(cur, run_id=run_id, task_id=task_id, account_id=account_id, check_account=True, execution_fence=execution_fence)
        cur.execute(f"SELECT * FROM {_table()} WHERE task_id=%s ORDER BY attempt_no DESC LIMIT 1 FOR UPDATE", (int(task_id),))
        previous = cur.fetchone()
        if previous and (not new_attempt or previous["payment_state"] != "failed"):
            return _public(previous)
        try:
            limit = max(1, min(50, int(concurrency)))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("支付并发必须是有效整数") from None
        cur.execute(f"SELECT count(*) AS count FROM {_table()} WHERE payment_provider=%s AND payment_state IN ('pending','unknown')", (payment_provider,))
        if cur.fetchone()["count"] >= limit:
            raise PaymentCapacityUnavailable()
        base = validate_api_base(api_base)
        if not isinstance(api_key, str) or not api_key.strip() or not isinstance(request_body, dict):
            raise ValueError("支付凭据或原始请求无效")
        private = runtime_config.encrypt_private_text(json.dumps({"api_key": api_key, "body": request_body}, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False))
        args = (int(task_id), int(run_id), account_id,
                _text(extract_provider_id, name="extract_provider_id"), _text(extract_job_id, name="extract_job_id"),
                _text(material_job_id, name="material_job_id", optional=True), payment_provider,
                int(previous["attempt_no"]) + 1 if previous else 1, base, "turb-payment-" + uuid.uuid4().hex,
                _text(material_fingerprint, name="material_fingerprint"), private)
        cur.execute(f"""INSERT INTO {_table()} (task_id, origin_run_id, account_id, extract_provider_id,
            extract_job_id, material_job_id, payment_provider, attempt_no, api_base, idempotency_key,
            material_fingerprint, private_encrypted) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""", args)
        return _public(cur.fetchone())


def get_payment_order(order_id: int, *, include_private=False) -> dict | None:
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table()} WHERE id=%s", (int(order_id),))
        return _public(cur.fetchone(), include_private=include_private)


def get_task_payment_order(task_id: int, *, include_private=False) -> dict | None:
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table()} WHERE task_id=%s ORDER BY attempt_no DESC LIMIT 1", (int(task_id),))
        return _public(cur.fetchone(), include_private=include_private)


def _summary(value, row):
    if not isinstance(value, dict):
        raise ValueError("支付摘要必须是对象")
    private = _private(row)
    secrets = (private["api_key"], *(item.get("at", "") for item in private["body"].get("items", []) if isinstance(item, dict)))
    result = {}
    for key, value in value.items():
        if key not in _SUMMARY_FIELDS:
            continue
        if isinstance(value, str):
            result[key] = safe_message(value, secrets=secrets)
        elif type(value) in (bool, int, float) or value is None:
            result[key] = value
    return result


def update_payment_order(order_id: int, *, run_id: int, execution_fence=None, **changes) -> dict:
    operation.init()
    allowed = {"submission_state", "payment_state", "remote_order_id", "summary", "submitted_at", "next_poll_at"}
    if changes.keys() - allowed:
        raise ValueError("不可修改支付身份或私有请求")
    try:
        with operation._connect() as conn, conn.cursor() as cur:
            _lock(cur)
            task_id = _owner(cur, run_id=run_id, execution_fence=execution_fence)
            cur.execute(f"SELECT * FROM {_table()} WHERE id=%s FOR UPDATE", (int(order_id),))
            row = cur.fetchone()
            if not row:
                raise LookupError("独立支付订单不存在")
            if int(row["task_id"]) != task_id:
                raise ValueError("支付订单不属于当前 Run 的任务")
            if "submission_state" in changes and changes["submission_state"] not in _SUBMISSION_STATES:
                raise ValueError("支付提交状态无效")
            if "payment_state" in changes:
                if changes["payment_state"] not in _PAYMENT_STATES:
                    raise ValueError("支付状态无效")
                if row["payment_state"] in {"succeeded", "failed"} and changes["payment_state"] != row["payment_state"]:
                    raise ValueError("已结束支付订单不可改写终态")
            if "remote_order_id" in changes:
                remote = _text(changes["remote_order_id"], name="remote_order_id")
                if row["remote_order_id"] and row["remote_order_id"] != remote:
                    raise ValueError("不可替换原支付订单身份")
                changes["remote_order_id"] = remote
            for key in ("submitted_at", "next_poll_at"):
                if key in changes and changes[key] is not None:
                    value = changes[key]
                    if isinstance(value, str):
                        try:
                            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        except ValueError:
                            raise ValueError("支付时间无效") from None
                    if not isinstance(value, datetime) or value.tzinfo is None:
                        raise ValueError("支付时间必须包含时区")
                    if key == "submitted_at" and row["submitted_at"] is not None and value != row["submitted_at"]:
                        raise ValueError("不可替换首次支付提交时间")
                    changes[key] = value
            if "submitted_at" in changes and changes["submitted_at"] is None and row["submitted_at"] is not None:
                raise ValueError("不可清除支付提交时间")
            if not changes:
                return _public(row)
            assignments, values = [], []
            for key, value in changes.items():
                if key == "summary":
                    assignments.append("summary=summary || %s::jsonb")
                    values.append(json.dumps(_summary(value, row), ensure_ascii=False, allow_nan=False))
                else:
                    assignments.append(f"{key}=%s")
                    values.append(value)
            cur.execute(f"UPDATE {_table()} SET {', '.join(assignments)}, updated_at=now() WHERE id=%s RETURNING *", (*values, int(order_id)))
            return _public(cur.fetchone())
    except UniqueViolation:
        raise ValueError("支付远端订单身份已由其他意图占用") from None


def list_recoverable_payment_orders() -> list[dict]:
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT payment.*, task.last_run_id AS latest_run_id,
                task.status AS task_status, run.status AS latest_run_status,
                batch.status AS batch_status, run.cancel_requested_at
            FROM {_table()} payment
            JOIN {operation._table('operation_tasks')} task ON task.id=payment.task_id
            LEFT JOIN {operation._table('operation_runs')} run ON run.id=task.last_run_id
            LEFT JOIN {operation._table('operation_batches')} batch ON batch.id=task.batch_id
            WHERE payment.payment_state <> 'failed'
              AND COALESCE(payment.summary->>'plus_verification_status', '') NOT IN ('confirmed','not_applicable')
              AND NOT EXISTS (SELECT 1 FROM {_table()} newer WHERE newer.task_id=payment.task_id AND newer.attempt_no>payment.attempt_no)
            ORDER BY payment.updated_at, payment.id""")
        return [_public(row) for row in cur.fetchall()]
