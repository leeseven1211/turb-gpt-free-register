# -*- coding: utf-8 -*-
"""批量仓储共用契约、计数和事务工具。"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from core.storage.operations import store

BUCKETS = (
    "pending_submit",
    "waiting_account",
    "queued",
    "running",
    "waiting",
    "success",
    "partial_success",
    "failed",
    "not_executed",
    "cancelled",
    "attention_required",
)
TERMINAL = frozenset(BUCKETS[5:])
ACTIVE_RUNS = ("queued", "running", "waiting", "cancelling", "settling", "stopping")
OWNED = ("owned_root", "owned_child", "owned_continuation")
table = store._table
connect = store._connect


class BulkError(ValueError):
    def __init__(self, code: str, message: str, status: int = 409, detail: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.detail = code, message, status, detail or {}


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def counts(bucket: str = "pending_submit", total: int = 0) -> dict:
    result = dict.fromkeys(BUCKETS, 0)
    result[bucket] = total
    return result


def add_counts(original: dict, deltas: dict) -> dict:
    result = {key: int(original.get(key, 0)) + int(deltas.get(key, 0)) for key in BUCKETS}
    if any(value < 0 for value in result.values()):
        raise BulkError("projection_invariant_failed", "批次计数出现负数，事务已回滚", 500)
    return result


def receipt(row: dict | None, request_hash: str) -> dict | None:
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise BulkError("idempotency_key_conflict", "该幂等键已经用于不同请求")
    return dict(row, reused=True)


def validate_key(key: str) -> str:
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise BulkError("invalid_idempotency_key", "必须提供不超过200字符的幂等键", 422)
    return key


def positive_ids(values) -> list[int]:
    result = []
    seen = set()
    for raw in values:
        if isinstance(raw, bool) or not str(raw).isdigit() or int(raw) <= 0 or int(raw) > 9223372036854775807:
            raise BulkError("invalid_target_id", "账号ID必须为正整数", 422)
        value = int(raw)
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def guard(cur, batch_id: int) -> None:
    cur.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"bulk_projection:{store._schema_name()}:{batch_id}",)
    )


def request_guard(cur, kind: str, key: str) -> None:
    # 仅序列化同一逻辑请求，避免唯一约束错误后事务已失效。
    cur.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"bulk_request:{store._schema_name()}:{kind}:{key}",)
    )


def require_row(cur, sql: str, params=(), *, code="not_found") -> dict:
    cur.execute(sql, params)
    row = cur.fetchone()
    if not row:
        raise BulkError(code, "请求的批量资源不存在", 404)
    return dict(row)


def public_selection(row: dict) -> dict:
    return dict(
        row,
        state=row["status"],
        target_count=row.get("total_count"),
        matched_count=None,
        basis_revision=row.get("basis_summary_revision"),
        preflight={"counts": row.get("preflight_summary", {}), "checked_at": row.get("preflight_at")},
    )


def public_batch(row: dict) -> dict:
    result = dict(row)
    result["id"] = row["batch_id"]
    result["control_state"] = row["state"]
    result["round_id"] = row.get("initial_round_id")
    result["target_count"] = sum(int(row.get("counts", {}).get(key, 0)) for key in BUCKETS)
    result["operation"] = {"key": row["action_key"], "version": row["action_version"]}
    result["execution_state"] = "completed" if row["state"] == "ended" else "running"
    result["summary"] = {"counts": row.get("counts", {}), "metrics": row.get("metrics", {})}
    return result
