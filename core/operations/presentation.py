"""公开任务结果与内部远端回执状态的展示边界。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy


UNCONFIRMED_RESULT_STATUSES = frozenset({
    "attention_required", "request_unknown", "manual_reconcile", "unknown",
    "unconfirmed", "password_result_unknown", "password_confirmation_pending",
    "credential_pending_confirmation",
})


def public_result_status(status, summary: Mapping | None = None) -> str:
    """公开结果必须明确失败；已记录的部分成功保留独立成果。"""
    value = str(status or "").strip().lower()
    if value not in UNCONFIRMED_RESULT_STATUSES:
        return value
    requested = str((summary or {}).get("requested_status") or "").strip().lower()
    return "partial_success" if requested == "partial_success" else "failed"


def public_result_status_sql(expression: str, summary_expression: str | None = None) -> str:
    """生成与 Python 投影等价的 SQL，保证分页、筛选和统计一致。"""
    statuses = ",".join(repr(value) for value in sorted(UNCONFIRMED_RESULT_STATUSES))
    partial = (
        f"LOWER(BTRIM(COALESCE(({summary_expression})->>'requested_status','')))='partial_success'"
        if summary_expression else "FALSE"
    )
    return (
        f"CASE WHEN LOWER(BTRIM(COALESCE(({expression})::text,''))) IN ({statuses}) "
        f"THEN CASE WHEN {partial} THEN 'partial_success' ELSE 'failed' END "
        f"ELSE LOWER(BTRIM(COALESCE(({expression})::text,''))) END"
    )


def public_progress_snapshot(value):
    """公开进度副本只转换执行状态，原始回执、证据枚举和恢复字段保持原样。"""
    if isinstance(value, Mapping):
        summary = value.get("result_summary")
        summary = summary if isinstance(summary, Mapping) else value
        result = {
            key: (deepcopy(item) if key in {
                "result_summary", "data", "remote_raw", "remote_intent", "remote_receipt",
                "auth_diagnostics", "cause_diagnostics",
            } else public_result_status(item, summary)
                  if key in {"status", "state", "display_status", "run_status"}
                  and isinstance(item, str) and item.strip().lower() in UNCONFIRMED_RESULT_STATUSES
                  else public_progress_snapshot(item))
            for key, item in value.items()
        }
        terminal = next((result[key] for key in ("status", "display_status")
                         if isinstance(value.get(key), str)
                         and value[key].strip().lower() in UNCONFIRMED_RESULT_STATUSES), None)
        if terminal and str(value.get("state") or "").strip().lower() in {
            "pending", *UNCONFIRMED_RESULT_STATUSES,
        }:
            result["state"] = "success" if terminal == "partial_success" else "failed"
        return result
    if isinstance(value, list):
        return [public_progress_snapshot(item) for item in value]
    if isinstance(value, tuple):
        return tuple(public_progress_snapshot(item) for item in value)
    return value
