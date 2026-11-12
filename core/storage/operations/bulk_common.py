# -*- coding: utf-8 -*-
"""批量仓储共用契约、计数和事务工具。"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from core.operations.presentation import public_result_status, public_result_status_sql
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
    result.update(counts=public_counts(row.get("counts", {})), metrics=public_metrics(row.get("metrics", {})))
    result["summary"] = {"counts": result["counts"], "metrics": result["metrics"]}
    return result


def public_counts(values: dict) -> dict:
    """历史结果归入对应失败统计，不改变持久化增量计数。"""
    result: dict = {}
    for key, value in values.items():
        state = public_result_status(key)
        result[state] = result.get(state, 0) + int(value or 0)
    return result


def public_metrics(values: dict) -> dict:
    result: dict = {}
    for key, value in values.items():
        metric = "account.token_refresh.failed" if key == "account.token_refresh.unconfirmed" else key
        result[metric] = result.get(metric, 0) + int(value or 0)
    return result


def public_round(row: dict) -> dict:
    return dict(row, counts=public_counts(row.get("counts") or {}), metrics=public_metrics(row.get("metrics") or {}))


def source_summary_sql(alias: str = "tr") -> str:
    """只引用目标原轮最近的所属 Run，后续账号状态不参与历史结果。"""
    return f"""(SELECT r.result_summary FROM {table('operation_batch_run_links')} l
      JOIN {table('operation_runs')} r ON r.id=l.run_id_snapshot
      WHERE l.target_round_id={alias}.id AND l.relation IN ('owned_root','owned_continuation')
      ORDER BY l.execution_generation DESC,l.id DESC LIMIT 1)"""


def target_status_sql(expression: str, alias: str = "tr") -> str:
    return public_result_status_sql(expression, source_summary_sql(alias))


def plan_query_outcome_sql(state_expression: str, summary_expression: str) -> str:
    """按套餐投影的成功国家事实还原旧查询结果，仅供公开读取筛选。"""
    active = "'queued','running','waiting','settling','cancelling','stopping','pending_submit','waiting_account'"
    return f"""(SELECT CASE WHEN state IN ({active}) THEN 'pending'
      WHEN eligible AND total>0 AND succeeded=total AND NOT partial THEN 'success'
      WHEN eligible THEN 'partial_success'
      WHEN state IN ('not_executed','cancelled') THEN 'not_executed' ELSE 'failed' END
      FROM (SELECT facts.*,
        CASE WHEN eligible AND initial_total=0 THEN 1 ELSE initial_total END AS total,
        CASE WHEN eligible AND initial_total=0 THEN 1
          WHEN eligible AND NOT has_success_count AND NOT partial AND state='success' THEN initial_total
          ELSE initial_succeeded END AS succeeded
        FROM (SELECT original.*,
          state IN ('success','partial_success') AND
            COALESCE(summary->'ok' NOT IN ('null'::jsonb,'false'::jsonb,'0'::jsonb,'\"\"'::jsonb,'[]'::jsonb,'{{}}'::jsonb),FALSE) AS eligible,
          COALESCE(summary->'plan_check_partial' NOT IN
            ('null'::jsonb,'false'::jsonb,'0'::jsonb,'\"\"'::jsonb,'[]'::jsonb,'{{}}'::jsonb),FALSE) AS partial,
          COALESCE(NULLIF(COALESCE(NULLIF(summary->>'country_total_count','')::bigint,0),0),
            jsonb_array_length(CASE WHEN jsonb_typeof(summary->'plan_check_countries')='array'
              THEN summary->'plan_check_countries' ELSE '[]'::jsonb END)) AS initial_total,
          COALESCE(NULLIF(summary->>'country_success_count','')::bigint,0) AS initial_succeeded,
          summary->'country_success_count' IS NOT NULL AND summary->'country_success_count'<>'null'::jsonb AS has_success_count
          FROM (SELECT ({state_expression}) AS state,COALESCE(({summary_expression}),'{{}}'::jsonb) AS summary) original
        ) facts
      ) completed)"""


def public_reason_target_ids(cur, batch_id: int, reason_codes) -> list[int]:
    """只有按原因筛选时读取本批证据，筛选采用与页面相同的分类结果。"""
    wanted = set(reason_codes)
    cur.execute(f"""SELECT tr.id,tr.outcome,tr.result,tr.reason_code,
      source.result_summary,source.error_message,source.error_code
      FROM {table('operation_batch_target_rounds')} tr
      LEFT JOIN LATERAL (SELECT r.result_summary,r.error_message,r.error_code
        FROM {table('operation_batch_run_links')} l JOIN {table('operation_runs')} r ON r.id=l.run_id_snapshot
        WHERE l.target_round_id=tr.id AND l.relation IN ('owned_root','owned_continuation')
        ORDER BY l.execution_generation DESC,l.id DESC LIMIT 1) source ON TRUE
      WHERE tr.batch_id=%s""", (batch_id,))
    matched = []
    while rows := cur.fetchmany(500):
        for row in rows:
            value = public_target_result(dict(row["result"] or {}, state=row["outcome"]),
                summary=row["result_summary"], message=row["error_message"], error_code=row["error_code"] or row["reason_code"])
            if (value.get("reason") or {}).get("code") in wanted:
                matched.append(row["id"])
    return matched


def preserve_partial_counts(cur, row: dict, *, round_id=None) -> dict:
    """旧汇总只存回执状态时，从同次 Run 找回明确的部分成功数量。"""
    if not int((row.get("counts") or {}).get("attention_required", 0)):
        return row
    batch_id = row.get("batch_id") or row.get("id")
    scope = "tr.round_id=%s" if round_id else "tr.batch_id=%s AND tr.round_id=COALESCE(root.latest_requested_round_id,c.initial_round_id)"
    cur.execute(f"""SELECT count(*) AS n FROM {table('operation_batch_target_rounds')} tr
      JOIN {table('operation_selection_targets')} root ON root.id=tr.canonical_target_id
      JOIN {table('operation_batch_controls')} c ON c.batch_id=tr.batch_id
      WHERE {scope} AND tr.outcome='attention_required'
      AND ({source_summary_sql()})->>'requested_status'='partial_success'""", (round_id or batch_id,))
    partial = int(cur.fetchone()["n"])
    if partial:
        row = dict(row, counts=dict(row["counts"]))
        row["counts"]["attention_required"] -= partial
        row["counts"]["partial_success"] = row["counts"].get("partial_success", 0) + partial
    return row


def public_target_result(value: dict, *, summary=None, message=None, error_code=None) -> dict:
    """历史物化结果按当前公开契约读取，具体原因从原 Run 取证。"""
    from core.operations.errors import classify_task_error

    result = dict(value)
    summary = summary or {}
    state = public_result_status(result.get("state"), summary)
    result["state"] = state
    if "source_status" in result:
        result["source_status"] = public_result_status(result["source_status"], summary)
    fields = dict(result.get("result") or {})
    for key in ("refresh_outcome", "query_outcome", "attempt_outcome", "confirmation", "credential_confirmation", "after_state"):
        if fields.get(key) in {"attention_required", "request_unknown", "unconfirmed", "unknown", "not_confirmed"}:
            if key == "query_outcome":
                from core.bulk_operations.results import _plan

                fields[key] = _plan(summary, state, {})["query_outcome"]
            elif key == "attempt_outcome":
                fields[key] = state
            elif state in {"queued", "running", "waiting", "pending_submit", "waiting_account"}:
                fields[key] = "pending"
            elif state == "not_executed" and key in {"refresh_outcome", "confirmation"}:
                fields[key] = "not_executed"
            elif state == "cancelled" and (key == "refresh_outcome" or (
                key == "confirmation" and str(result.get("schema") or "").startswith("token_refresh.")
            )):
                fields[key] = "not_executed"
            else:
                fields[key] = "failed"
    result["result"] = fields
    contribution = dict(result.get("contribution") or {})
    if contribution:
        contribution.update(state=state, dimensions=public_metrics(contribution.get("dimensions") or {}))
        result["contribution"] = contribution
    if result.get("_metrics") is not None:
        result["_metrics"] = public_metrics(result["_metrics"])
    reason = dict(result.get("reason") or {})
    if state in {"failed", "partial_success"}:
        code = error_code or reason.get("code") or summary.get("cause_code") or "diagnostic_cause_unresolved"
        info = classify_task_error(message or code, error_code=code,
            task_type=str(result.get("schema") or "").split(".")[0],
            stage=summary.get("failure_stage") or reason.get("stage") or fields.get("failure_stage") or "",
            result_summary=summary, task_status=state) or {}
        reason.update(code=info.get("code") or code, summary=info.get("summary"), display_code=info.get("display_code"),
                      stage=info.get("stage") or reason.get("stage"))
        if "failure_stage" in fields:
            fields["failure_stage"] = reason["stage"]
        result["reason"] = reason
    return result
