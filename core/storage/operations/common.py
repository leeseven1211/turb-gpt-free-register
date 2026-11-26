# -*- coding: utf-8 -*-
"""统一任务仓储共享连接、序列化、状态与读模型归一工具。此层不拥有运行态写入。"""
from __future__ import annotations

import json
import os
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from core.storage import postgres as postgres_store, records as record_store
from core.operations import task_gateway as account_task_store
from core.operations.errors import classify_task_error
from core.operations.stages import normalize_step_state, resolve_step, stage_label

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


_SCHEMA_ENV = "OPERATION_TASK_DB_SCHEMA"
_SETTLEMENT_DOMAIN = ContextVar("operation_settlement_domain", default=None)
_SETTLEMENT_DEADLINE = ContextVar("operation_settlement_deadline", default=None)
_SETTLEMENT_CONNECTION = ContextVar("operation_settlement_connection", default=None)


@contextmanager
def settlement_scope(domain, *, deadline=None, conn=None):
    """Bind the captured origin locally; never redirect other request threads."""
    inherited_deadline = postgres_store._SCOPED_DEADLINE.get()
    if inherited_deadline is not None:
        deadline = min(deadline, inherited_deadline) if deadline is not None else inherited_deadline
    tokens = [
        (postgres_store._SCOPED_DOMAIN, postgres_store._SCOPED_DOMAIN.set(domain)),
        (postgres_store._SCOPED_DEADLINE, postgres_store._SCOPED_DEADLINE.set(deadline)),
        (_SETTLEMENT_DOMAIN, _SETTLEMENT_DOMAIN.set(domain)),
        (_SETTLEMENT_DEADLINE, _SETTLEMENT_DEADLINE.set(deadline)),
        (_SETTLEMENT_CONNECTION, _SETTLEMENT_CONNECTION.set(conn)),
    ]
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def current_settlement_domain():
    return _SETTLEMENT_DOMAIN.get()


_TERMINAL_STATUSES = {
    "success", "partial_success", "failed", "stopped", "cancelled", "interrupted",
    "deactivated", "unsupported", "attention_required",
}


_ACTIVE_RUN_STATUSES = frozenset({"queued", "running", "cancelling", "settling", "stopping", "waiting"})


_ACTIVE_RUN_STATUS_SQL = "'queued','running','cancelling','settling','stopping','waiting'"


_TERMINAL_STATUS_SQL = "'success','partial_success','failed','stopped','cancelled','interrupted','deactivated','unsupported','attention_required'"


_REGISTRATION_CHECKPOINTS = (
    "created", "email_claimed", "auth_started", "password_request_started",
    "password_confirmed", "otp_started", "otp_confirmed", "account_request_started",
    "account_confirmed", "token_obtained", "core_persisted", "postprocessing",
    "completed", "manual_reconcile", "failed",
)


_LEGACY_REGISTRATION_CHECKPOINT_MAP = {
    "registered": "core_persisted",
    "email_verification_pending": "account_request_started",
}


_SECRET_PARTS = ("password", "otp", "secret", "authorization", "cookie", "token")


_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\b")


_PROXY_RE = re.compile(r"(?P<scheme>https?://)[^/@\s]+@", re.IGNORECASE)


def _schema_name() -> str:
    domain = _SETTLEMENT_DOMAIN.get()
    value = str(domain.operation_schema if domain else os.getenv(_SCHEMA_ENV) or postgres_store.schema_name()).strip() or "public"
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError("OPERATION_TASK_DB_SCHEMA 不是合法 PostgreSQL schema 名称")
    return value


def _quote(value: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"非法 PostgreSQL 标识符: {value!r}")
    return f'"{value}"'


def _table(name: str) -> str:
    return f"{_quote(_schema_name())}.{_quote(name)}"


def _permit_table() -> str:
    domain = _SETTLEMENT_DOMAIN.get()
    schema = domain.permit_schema if domain is not None else postgres_store.schema_name()
    return f"{_quote(schema)}.{_quote('operation_execution_permits')}"


def _settlement_record(cur, spec: record_store.TableSpec, row_id: int, *, for_update=False):
    """Read the already initialized original record table without migrations."""
    sql = f"SELECT * FROM {postgres_store.qualified(spec.name)} WHERE id=%s"
    if for_update:
        sql += " FOR UPDATE"
    cur.execute(sql, (int(row_id),))
    return record_store.merge_row(spec, cur.fetchone())


def _settlement_account(cur, account_id: int, *, for_update=False):
    return _settlement_record(cur, record_store.ACCOUNTS, account_id, for_update=for_update)


def _connect():
    from psycopg.rows import dict_row
    from contextlib import nullcontext
    conn = _SETTLEMENT_CONNECTION.get()
    if conn is not None:
        return nullcontext(conn)
    domain = _SETTLEMENT_DOMAIN.get()
    if domain is not None:
        return postgres_store.connect(domain.database_url, row_factory=dict_row, deadline=_SETTLEMENT_DEADLINE.get())
    return postgres_store.connect(row_factory=dict_row)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _legacy_timestamp(value: Any) -> datetime | None:
    """Normalize legacy local-wall-clock text before writing or returning UTC.

    Older compatibility rows were written with ``datetime.now().isoformat()``
    and therefore contain local wall-clock time without an offset.  PostgreSQL
    interprets those strings in its UTC session timezone, while the browser
    converts the result to local time and adds the offset a second time.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone(timezone.utc)


def _legacy_account_timestamp(value: Any) -> datetime | None:
    return _legacy_timestamp(value)


def _legacy_registration_timestamp(value: Any) -> datetime | None:
    return _legacy_timestamp(value)


def _uuid(kind: str, source: object) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"turb-console:{kind}:{source}").hex


def _text(value: Any, limit: int = 1200) -> str:
    text = _JWT_RE.sub("[REDACTED_TOKEN]", str(value or ""))
    text = _PROXY_RE.sub(r"\g<scheme>***@", text)
    return text[:limit]


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return "[truncated]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:120]:
            key = str(raw_key)[:100]
            lowered = key.lower()
            if any(part in lowered for part in _SECRET_PARTS):
                if key in account_task_store._SAFE_PASSWORD_POLICY_KEYS:
                    valid_driver = lowered.endswith("driver") and isinstance(raw_value, str) and raw_value in {"protocol", "roxy", "roxybrowser", "browser"}
                    valid_mode = lowered.endswith("proxy_mode") and isinstance(raw_value, str) and raw_value in {"direct", "registration", "pool"}
                    if not (isinstance(raw_value, bool) or valid_driver or valid_mode):
                        continue
                elif lowered == "password_setup" and isinstance(raw_value, dict):
                    raw_value = {k: v for k, v in raw_value.items() if k in {
                        "ok", "status", "message", "error", "error_code", "cause_code", "failure_stage",
                        "remote_receipt_state", "mutation_submitted", "action_dispatched", "reconcile_required",
                        "browser_opened", "password_driver",
                    }}
                elif lowered != "password" or not isinstance(raw_value, bool):
                    continue
            out[key] = _scrub(raw_value, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_scrub(item, depth + 1) for item in list(value)[:120]]
    if isinstance(value, (str, bytes)):
        return _text(value, 2000)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _text(value, 500)


def _json(value: Any) -> str:
    return json.dumps(_scrub(value), ensure_ascii=False, separators=(",", ":"))


def _decode(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _row(row: dict | None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    result.pop("private_context", None)
    for key in ("next_actions", "progress_steps", "result_summary", "detail", "data"):
        if key in result:
            result[key] = _decode(result[key])
    for key, value in list(result.items()):
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


def _task_is_user_deleted(row: dict | None) -> bool:
    """判断任务是否被用户从任务中心隐藏，保留审计数据。"""
    if not row:
        return False
    data = _decode(row.get("data"))
    return isinstance(data, dict) and str(data.get("deleted_by_user") or "").lower() == "true"


def _legacy_event_type_for_read(event: dict) -> str:
    """Normalize pre-contract account events without mutating historical rows."""
    event_type = str(event.get("event_type") or "").strip()
    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    if str(event.get("source_system") or "") != "account_action_events":
        return event_type or "note.info"
    detail_state = normalize_step_state(detail.get("step_state"))
    if detail_state:
        return f"stage.{detail_state}"
    if event_type and event_type not in {"stage.running", "progress"}:
        # Rows with a terminal stage state, or a previously normalized run/note
        # event, already carry the new contract.
        return event_type
    raw_stage = str(event.get("stage") or "event").strip().lower()
    level = str(event.get("level") or "INFO").upper()
    if raw_stage == "queued":
        return "run.queued" if "加入队列" in str(event.get("message") or "") else "run.running"
    if raw_stage == "running":
        return "run.running"
    if raw_stage in {"network_route", "network"}:
        return "resource.acquired"
    if raw_stage == "complete":
        return "stage.failed" if level == "ERROR" else "stage.success"
    return "note.warning" if level == "WARNING" else "note.error" if level == "ERROR" else "note.info"


def _read_event(row: dict) -> dict:
    result = _row(row) or {}
    result["detail"] = _scrub(result.get("detail") if isinstance(result.get("detail"), dict) else {})
    result["event_type"] = _legacy_event_type_for_read(result)
    if result.get("source_system") == "account_action_events":
        result["source_event_id"] = int(result["source_id"]) if str(result.get("source_id") or "").isdigit() else result.get("source_id")
    detail = result["detail"]
    result["has_detail"] = bool(
        isinstance(detail, dict)
        and any(key != "step_state" and value not in (None, "", [], {}) for key, value in detail.items())
    )
    return result


def _annotate_stage(record: dict, task_type: str, run: dict | None = None) -> dict:
    """事件和 JSONL 共用步骤关联，普通无上下文日志明确保持未关联。"""
    detail = record.get("detail") or record.get("fields") or {}
    if not isinstance(detail, dict):
        detail = {}
    raw_stage = str(detail.get("raw_stage") or record.get("stage") or "event")
    record["raw_stage"] = raw_stage
    record["stage_label"] = stage_label(raw_stage)
    if raw_stage not in {"runtime", "registration", "event", "diagnostic"}:
        record["main_step_id"] = resolve_step(task_type, raw_stage, detail, run)
    else:
        record["main_step_id"] = None
    return record


def _registration_progress_occurrence(detail: dict, state: str) -> datetime | None:
    """只采用事件自身的时间；阶段开始不能代表后续每条消息发生的时刻。"""
    if state == "pending" and detail.get("evidence") == "unconfirmed" and detail.get("event_time_known") is not True:
        # 旧任务收尾曾继承 running 的 occurred_at，没有独立结束时间可用于恢复。
        return None
    keys = ("completed_at", "occurred_at") if not state or state in {"success", "failed", "skipped", "stopped"} else ("occurred_at",)
    for key in keys:
        try:
            value = _legacy_registration_timestamp(detail.get(key))
        except (TypeError, ValueError, OverflowError):
            continue
        if value is not None:
            return value
    return None


def _normalize_compatibility_event(event: dict) -> dict:
    """只归一化由旧 registration_jobs progress_steps 派生的事件。"""
    if str(event.get("source_system") or "") not in {"registration_progress", "registration_progress_events"}:
        return event
    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    state = str(detail.get("step_state") or detail.get("state") or str(event.get("event_type") or "").removeprefix("stage.")).strip().lower()
    normalized = _registration_progress_occurrence(detail, state)
    if normalized is not None:
        event["created_at"] = normalized.isoformat()
        event["event_time_known"] = True
        return event
    # 旧投影曾把阶段起止时间写进 created_at。原行另有独立事件时间时保留；
    # 与旧合成值相同的记录无法证明真实发生时间，只保留内部排序依据。
    try:
        stored = _legacy_timestamp(event.get("created_at"))
        started = _legacy_registration_timestamp(detail.get("started_at"))
        boundaries = {_legacy_registration_timestamp(detail.get(key)) for key in ("started_at", "completed_at")}
        for key in ("started_at", "completed_at"):
            if detail.get(key):
                raw = datetime.fromisoformat(str(detail[key]).replace("Z", "+00:00"))
                if raw.tzinfo is None:
                    # 更早的行曾把本地墙钟误按 UTC 落库，同样不能当成独立事件时间。
                    boundaries.add(raw.replace(tzinfo=timezone.utc))
    except (TypeError, ValueError, OverflowError):
        stored, started, boundaries = None, None, set()
    if (not (state == "pending" and detail.get("evidence") == "unconfirmed")
            and event.get("source_system") == "registration_progress_events"
            and stored is not None and started is not None and stored >= started and stored not in boundaries):
        event["event_time_known"] = True
    else:
        event["_sort_created_at"] = event.get("created_at") or event.get("_sort_created_at")
        event["created_at"] = None
        event["event_time_known"] = False
    return event


def _event_time_sort_key(event: dict) -> tuple[datetime, int]:
    raw = event.get("created_at") or event.get("_sort_created_at")
    try:
        parsed = _legacy_timestamp(raw)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    return (
        parsed or datetime.min.replace(tzinfo=timezone.utc),
        int(event.get("id") or 0),
    )


def _account_extra(account: dict | None) -> dict:
    raw = (account or {}).get("extra_json") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = {}
    return dict(raw) if isinstance(raw, dict) else {}


def _account_state(account: dict | None) -> dict[str, str]:
    if not account:
        return {
            "checkpoint": "created", "remote_identity_state": "not_started",
            "remote_account_state": "not_started", "local_account_state": "none",
            "target_status": "not_created",
        }
    account_status = str(account.get("account_status") or "").strip().lower()
    if account_status == "deactivated" or account.get("deactivated") is True:
        return {
            "checkpoint": "failed", "remote_identity_state": "confirmed",
            "remote_account_state": "confirmed", "local_account_state": "persisted",
            "target_status": "deactivated",
        }
    extra = _account_extra(account)
    legacy_checkpoint = str(extra.get("registration_checkpoint") or "").strip().lower()
    checkpoint = _LEGACY_REGISTRATION_CHECKPOINT_MAP.get(legacy_checkpoint, legacy_checkpoint)
    has_token = bool(str(account.get("access_token") or "").strip())
    if has_token:
        return {
            "checkpoint": checkpoint if checkpoint in _REGISTRATION_CHECKPOINTS else "core_persisted",
            "remote_identity_state": "confirmed", "remote_account_state": "confirmed",
            "local_account_state": "persisted", "target_status": "account_available",
        }
    if legacy_checkpoint == "email_verification_pending":
        return {
            "checkpoint": "account_request_started", "remote_identity_state": "confirmed",
            "remote_account_state": "request_unknown", "local_account_state": "none",
            "target_status": "email_verification_pending",
        }
    return {
        "checkpoint": checkpoint if checkpoint in _REGISTRATION_CHECKPOINTS else "created",
        "remote_identity_state": "not_started", "remote_account_state": "not_started",
        "local_account_state": "none",
        "target_status": "attention_required",
    }


def _account_is_deactivated(account: dict | None) -> bool:
    return any(
        str((account or {}).get(key) or "").strip().lower() == "deactivated"
        for key in ("account_status", "codex_status", "codex_credential_state")
    )


def _error_fields(
    message: Any, *, stage: str = "", task_type: str = "",
    result_summary: dict | None = None, task_status: str = "",
) -> tuple[str | None, str | None, str | None]:
    raw = _text(message, 1600).strip()
    info = classify_task_error(
        raw, stage=stage, task_type=task_type,
        result_summary=result_summary, task_status=task_status,
    ) if raw else None
    return (
        str((info or {}).get("source") or "") or None,
        str((info or {}).get("code") or "") or None,
        raw or None,
    )


def _status(value: Any) -> str:
    status = str(value or "queued").strip().lower()
    return "queued" if status == "pending" else status


def _select_current_run(runs: Iterable[dict]) -> dict | None:
    """选择任务当前执行实例，活动 attempt 永远优先于历史终态。"""
    candidates = [dict(run) for run in runs if run]
    if not candidates:
        return None
    active = [run for run in candidates if str(run.get("status") or "").lower() in _ACTIVE_RUN_STATUSES]
    candidates = active or candidates
    return max(
        candidates,
        key=lambda run: (int(run.get("run_no") or 0), int(run.get("id") or 0)),
    )


def _compatibility_run_status_sql(
    *, run_alias: str = "rr", registration_alias: str = "registration_job",
    account_alias: str = "account_task",
) -> str:
    """Read the source status for compatibility runs before trusting projection rows."""
    return (
        f"CASE "
        f"WHEN {_registration_completion_overlay_sql(run_alias, registration_alias)} THEN {run_alias}.status "
        f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
        f"THEN CASE WHEN {registration_alias}.status='pending' THEN 'queued' ELSE {registration_alias}.status END "
        f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
        f"THEN CASE WHEN {account_alias}.status='pending' THEN 'queued' ELSE {account_alias}.status END "
        f"ELSE {run_alias}.status END"
    )


def _registration_completion_overlay_sql(run_alias: str, registration_alias: str) -> str:
    """注册主体终态后，已关联子任务的执行汇总优先于旧 Job 状态。"""
    return (
        f"({run_alias}.source_system='registration_jobs' "
        f"AND {registration_alias}.status IN ('success','partial_success') "
        f"AND {run_alias}.data ? 'completion_handoff' "
        f"AND {run_alias}.result_summary ? 'completion_handoff' "
        f"AND NOT EXISTS (SELECT 1 FROM {_table('operation_runs')} completion_newer "
        f"WHERE completion_newer.task_id={run_alias}.task_id "
        f"AND (completion_newer.run_no,completion_newer.id)>({run_alias}.run_no,{run_alias}.id)))"
    )


def _compatibility_created_at_sort_sql(value_sql: str) -> str:
    """将兼容来源的时间文本按原时区约定转换成排序时间。"""
    local_offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    offset_seconds = int(local_offset.total_seconds())
    offset_sign = "+" if offset_seconds >= 0 else "-"
    offset_seconds = abs(offset_seconds)
    offset_hours, offset_remainder = divmod(offset_seconds, 3600)
    offset_minutes = offset_remainder // 60
    local_timezone_sql = f"INTERVAL '{offset_sign}{offset_hours:02d}:{offset_minutes:02d}'"
    text_sql = f"NULLIF(({value_sql})::text, '')"
    return (
        f"CASE WHEN {text_sql} IS NULL THEN NULL "
        f"WHEN {text_sql} ~* '(Z|[+-][0-9]{{2}}:?[0-9]{{2}})$' "
        f"THEN {text_sql}::timestamptz "
        f"ELSE ({text_sql}::timestamp AT TIME ZONE {local_timezone_sql}) END"
    )


def _compatibility_run_projection_sql(
    *, run_alias: str = "rr", registration_alias: str = "registration_job",
    account_alias: str = "account_task", fields: Iterable[str] | None = None,
) -> str:
    """Project requested source-backed fields, keeping one definition per field."""
    status_sql = _compatibility_run_status_sql(
        run_alias=run_alias, registration_alias=registration_alias, account_alias=account_alias,
    )
    stage_sql = (
        f"CASE WHEN ({status_sql})='queued' THEN 'queued' "
        f"WHEN ({status_sql}) IN ({_TERMINAL_STATUS_SQL}) THEN 'complete' "
        f"ELSE {run_alias}.progress_stage END"
    )
    created_at_sql = (
        f"CASE "
        f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
        f"THEN {registration_alias}.created_at "
        f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
        f"THEN {account_alias}.queued_at "
        f"ELSE NULL END"
    )
    expressions = {
        "effective_status": status_sql,
        "effective_progress_stage": stage_sql,
        "effective_created_at": created_at_sql,
        "effective_started_at": (
            f"CASE "
            f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
            f"THEN COALESCE(NULLIF({registration_alias}.data->>'started_at', ''), {run_alias}.started_at::text) "
            f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
            f"THEN COALESCE(NULLIF({account_alias}.started_at, ''), {run_alias}.started_at::text) "
            f"ELSE {run_alias}.started_at::text END"
        ),
        "effective_completed_at": (
            f"CASE "
            f"WHEN {_registration_completion_overlay_sql(run_alias, registration_alias)} "
            f"THEN {run_alias}.completed_at::text "
            f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
            f"THEN NULLIF({registration_alias}.data->>'completed_at', '') "
            f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
            f"THEN NULLIF({account_alias}.finished_at, '') "
            f"ELSE {run_alias}.completed_at::text END"
        ),
        "effective_created_at_sort": _compatibility_created_at_sort_sql(created_at_sql),
        "effective_error_message": (
            f"CASE "
            f"WHEN {_registration_completion_overlay_sql(run_alias, registration_alias)} "
            f"THEN {run_alias}.error_message "
            f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
            f"THEN {registration_alias}.data->>'error_message' "
            f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
            f"THEN {account_alias}.error "
            f"ELSE {run_alias}.error_message END"
        ),
        "effective_debug_pause": (
            f"CASE WHEN {run_alias}.source_system='registration_jobs' "
            f"AND {registration_alias}.data->>'debug_state'='paused' "
            f"THEN jsonb_build_object('state', 'paused', "
            f"'paused_at', {registration_alias}.data->>'debug_paused_at', "
            f"'hold_until', {registration_alias}.data->>'debug_hold_until') "
            f"ELSE NULL END"
        ),
    }
    selected = expressions if fields is None else dict.fromkeys(fields)
    return ", ".join(f"{expressions[name]} AS {name}" for name in selected)


def _compatibility_source_bigint_sql(run_alias: str, source_system: str) -> str:
    """将兼容来源 ID 安全转为 BIGINT，保持主键索引可用且与文本精确匹配等价。"""
    return (
        f"CASE WHEN {run_alias}.source_system='{source_system}' "
        f"AND {run_alias}.source_id ~ '^-?(0|[1-9][0-9]{{0,18}})$' "
        f"AND pg_input_is_valid({run_alias}.source_id, 'bigint') "
        f"THEN ({run_alias}.source_id)::bigint END"
    )


def _compatibility_run_joins_sql(*, run_alias: str = "rr") -> str:
    registration_id_sql = _compatibility_source_bigint_sql(run_alias, "registration_jobs")
    account_task_id_sql = _compatibility_source_bigint_sql(run_alias, "account_action_tasks")
    return (
        f"LEFT JOIN {postgres_store.qualified(record_store.JOBS.name)} registration_job "
        f"ON registration_job.id={registration_id_sql} "
        f"LEFT JOIN {_table('account_action_tasks')} account_task "
        f"ON account_task.id={account_task_id_sql}"
    )


def _normalize_compatibility_run(run: dict) -> dict:
    """Overlay a compatibility run with its source row, if that row still exists."""
    effective_status = run.pop("effective_status", None)
    effective_stage = run.pop("effective_progress_stage", None)
    effective_created_at = run.pop("effective_created_at", None)
    effective_started_at = run.pop("effective_started_at", None)
    run.pop("effective_created_at_sort", None)
    effective_completed_at = run.pop("effective_completed_at", None)
    # 列表已用 SQL 投影错误正文，重复归一化不能把该正文清空；显式 NULL 仍按来源事实清空。
    effective_error_message = run.pop("effective_error_message", run.get("error_message"))
    debug_pause = run.pop("effective_debug_pause", None)
    run.pop("debug_pause", None)
    if effective_status:
        run["status"] = _status(effective_status)
    if effective_stage is not None:
        run["progress_stage"] = effective_stage
    source_system = str(run.get("source_system") or "")
    timestamp_normalizer = (
        _legacy_registration_timestamp
        if source_system == "registration_jobs"
        else _legacy_account_timestamp
        if source_system == "account_action_tasks"
        else None
    )
    if effective_created_at is not None and timestamp_normalizer:
        normalized_created_at = timestamp_normalizer(effective_created_at)
        if normalized_created_at is not None:
            run["created_at"] = normalized_created_at.isoformat()
    if effective_started_at is not None:
        normalized_started_at = (
            timestamp_normalizer(effective_started_at)
            if timestamp_normalizer else None
        )
        run["started_at"] = (
            normalized_started_at.isoformat()
            if normalized_started_at is not None else effective_started_at
        )
    if source_system == "registration_jobs":
        run["progress_steps"] = _normalize_legacy_registration_progress_steps(
            run.get("progress_steps")
        )
    if effective_completed_at is not None:
        normalized_completed_at = (
            timestamp_normalizer(effective_completed_at)
            if timestamp_normalizer else None
        )
        run["completed_at"] = (
            normalized_completed_at.isoformat()
            if normalized_completed_at is not None else effective_completed_at
        )
    elif source_system in {"registration_jobs", "account_action_tasks"}:
        run["completed_at"] = None
    if source_system in {"registration_jobs", "account_action_tasks"}:
        run["error_message"] = effective_error_message
        if run.get("status") in _ACTIVE_RUN_STATUSES:
            run["error_category"] = None
            run["error_code"] = None
    if source_system == "registration_jobs" and run.get("status") in _ACTIVE_RUN_STATUSES and isinstance(debug_pause, dict):
        pause = {"state": "paused"}
        for key in ("paused_at", "hold_until"):
            try:
                stamp = _legacy_registration_timestamp(debug_pause.get(key))
            except (TypeError, ValueError, OverflowError):
                stamp = None
            pause[key] = stamp.isoformat() if stamp is not None else None
        run["debug_pause"] = pause
    return run


def _normalize_legacy_registration_progress_steps(value: Any) -> Any:
    """仅在统一读模型中归一化旧注册阶段的时间字段。"""
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    for key, raw_step in value.items():
        if not isinstance(raw_step, dict):
            continue
        step = dict(raw_step)
        for stamp_key in ("started_at", "completed_at"):
            try:
                parsed = _legacy_registration_timestamp(step.get(stamp_key))
            except (TypeError, ValueError, OverflowError):
                parsed = None
            if parsed is not None:
                step[stamp_key] = parsed.isoformat()
        normalized[key] = step
    return normalized


def _apply_current_run_projection(task: dict, run: dict | None) -> dict:
    """把当前 attempt 的执行态覆盖到逻辑任务读模型上。"""
    if not run:
        return task
    status = str(run.get("status") or task.get("status") or "queued").lower()
    task["last_run_id"] = run.get("id")
    task["status"] = status
    task.pop("debug_pause", None)
    if run.get("debug_pause"):
        task["debug_pause"] = dict(run["debug_pause"])
    if str(run.get("source_system") or "") in {"registration_jobs", "account_action_tasks"} and run.get("created_at"):
        task["created_at"] = run["created_at"]
    if run.get("progress_stage"):
        task["current_stage"] = run.get("progress_stage")
    elif status == "queued":
        task["current_stage"] = "queued"
    if status in _ACTIVE_RUN_STATUSES:
        task["completed_at"] = None
        task["error_category"] = None
        task["error_code"] = None
        task["error_message"] = None
        task["next_actions"] = []
    else:
        task["completed_at"] = run.get("completed_at")
        task["error_category"] = run.get("error_category")
        task["error_code"] = run.get("error_code")
        task["error_message"] = run.get("error_message")
    task["result_summary"] = run.get("result_summary")
    summary = run.get("result_summary") if isinstance(run.get("result_summary"), dict) else {}
    data = run.get("data") if isinstance(run.get("data"), dict) else {}
    task["failure_stage"] = summary.get("failure_stage") or data.get("failure_stage")
    task["failure_event_id"] = summary.get("failure_event_id") or data.get("failure_event_id")
    task["current_stage_label"] = stage_label(task.get("current_stage"))
    task["failure_stage_label"] = stage_label(task["failure_stage"]) if task["failure_stage"] else None
    return task


def _duration(started: Any, completed: Any, explicit: Any = None) -> int | None:
    if explicit not in (None, ""):
        try:
            return max(0, int(explicit))
        except (TypeError, ValueError):
            pass
    if not started or not completed:
        return None
    try:
        left = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        right = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
        return max(0, int((right - left).total_seconds() * 1000))
    except (TypeError, ValueError):
        return None


def _attach_admission_wait(rows: list[dict], *, conn, run_rows: bool = False) -> None:
    """等待原因来自准入器事实，不让前端推测任务失败或容量状态。"""
    from core.storage.operations import permits

    keys = {}
    for row in rows:
        if str(row.get("status") or "") not in {"queued", "pending"}:
            continue
        if row.get("source_system") == "registration_jobs":
            key = f"registration_job:{row.get('source_id')}"
        else:
            run_id = row.get("id") if run_rows else row.get("last_run_id")
            if not run_id:
                continue
            key = f"operation_run:{run_id}"
        keys[key] = row
    details = permits.wait_details(list(keys), conn=conn)
    for key, row in keys.items():
        reasons = details.get(key) or []
        if not reasons and row.get("next_attempt_at"):
            try:
                if _legacy_timestamp(row["next_attempt_at"]) > _now():
                    reasons = [{"code": "not_due"}]
            except (TypeError, ValueError):
                pass
        row["admission_wait_reasons"] = reasons
        row["admission_wait_reason"] = reasons[0]["code"] if reasons else None
