# -*- coding: utf-8 -*-
"""统一任务中心的 PostgreSQL 存储与旧模型兼容投影。

新模型把批次、逻辑任务、执行实例和事件分开。注册尝试独立于执行实例，因而一次
执行失败不会再被误解为远端账号不存在。迁移期保留 registration_jobs 和
account_action_* 作为兼容写入口；本模块幂等同步、校验并为新任务中心提供唯一读模型。
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from core import postgres_store, record_store
from core import task_run_log
from core.operations import task_gateway as account_task_store
from core.task_errors import classify_task_error
from core.task_progress import build_progress_snapshot
from core.task_stages import flow_for, normalize_stage, normalize_step_state


_LOCK = threading.RLock()
_PROJECTION_WORKER_LOCK = threading.Lock()
_PROJECTION_STOP = threading.Event()
_PROJECTION_WAKE = threading.Event()
_PROJECTION_WORKER: threading.Thread | None = None
_READY_KEY = ""
logger = logging.getLogger(__name__)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCHEMA_ENV = "OPERATION_TASK_DB_SCHEMA"
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
_PROJECTION_RETRY_BASE_SECONDS = 5.0
_PROJECTION_LEASE_TIMEOUT_SECONDS = 15 * 60
_PROJECTION_WRITE_RETRY_LIMIT = 3
_PROJECTION_WRITE_RETRY_DELAY_SECONDS = 0.05


def _run_projection_write_with_retry(write, *, operation_name: str = "projection"):
    """Retry only PostgreSQL deadlocks around one idempotent projection write."""
    from psycopg.errors import DeadlockDetected

    for attempt in range(_PROJECTION_WRITE_RETRY_LIMIT):
        try:
            return write()
        except DeadlockDetected:
            if attempt + 1 >= _PROJECTION_WRITE_RETRY_LIMIT:
                raise
            delay = _PROJECTION_WRITE_RETRY_DELAY_SECONDS * (attempt + 1)
            logger.warning(
                "统一任务投影遇到 deadlock，准备重试 (%s/%s): operation=%s",
                attempt + 1,
                _PROJECTION_WRITE_RETRY_LIMIT - 1,
                operation_name,
            )
            time.sleep(delay)
    raise RuntimeError("统一任务投影重试流程异常结束")


def _schema_name() -> str:
    value = str(os.getenv(_SCHEMA_ENV) or postgres_store.schema_name()).strip() or "public"
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError("OPERATION_TASK_DB_SCHEMA 不是合法 PostgreSQL schema 名称")
    return value


def _quote(value: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"非法 PostgreSQL 标识符: {value!r}")
    return f'"{value}"'


def _table(name: str) -> str:
    return f"{_quote(_schema_name())}.{_quote(name)}"


def _connect():
    from psycopg.rows import dict_row

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
    for key in ("next_actions", "progress_steps", "result_summary", "detail", "data"):
        if key in result:
            result[key] = _decode(result[key])
    for key, value in list(result.items()):
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


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
    detail = result["detail"]
    result["has_detail"] = bool(
        isinstance(detail, dict)
        and any(key != "step_state" and value not in (None, "", [], {}) for key, value in detail.items())
    )
    return result


def reset_ready() -> None:
    global _READY_KEY
    with _LOCK:
        _READY_KEY = ""


def init() -> None:
    """幂等创建统一模型；只加表和索引，不改旧表。"""
    global _READY_KEY
    if not postgres_store.enabled():
        raise RuntimeError("统一任务存储需要配置可用的 DATABASE_URL")
    # 原生运行态会更新账号三轴状态，先确保 registered_accounts 已有对应提升列。
    record_store.init()
    # 迁移桥会读取旧账号任务表；全新数据库也必须先具备这三张兼容表。
    account_task_store.init()
    ready_key = f"{postgres_store.database_url()}::{_schema_name()}"
    with _LOCK:
        if _READY_KEY == ready_key:
            return
        schema = _quote(_schema_name())
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('registration_attempts')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    attempt_uuid TEXT NOT NULL UNIQUE,
                    source_root_job_id BIGINT UNIQUE,
                    email_snapshot TEXT NOT NULL DEFAULT '',
                    account_id BIGINT,
                    root_task_id BIGINT,
                    checkpoint TEXT NOT NULL DEFAULT 'unknown',
                    remote_identity_state TEXT NOT NULL DEFAULT 'unknown',
                    remote_account_state TEXT NOT NULL DEFAULT 'unknown',
                    local_account_state TEXT NOT NULL DEFAULT 'missing',
                    target_status TEXT NOT NULL DEFAULT 'unknown',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    completed_at TIMESTAMPTZ,
                    data JSONB NOT NULL DEFAULT '{{}}'::jsonb
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('operation_batches')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    batch_uuid TEXT NOT NULL UNIQUE,
                    source_system TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    batch_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    requested_count INTEGER NOT NULL DEFAULT 0,
                    queued_count INTEGER NOT NULL DEFAULT 0,
                    running_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    partial_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    attention_count INTEGER NOT NULL DEFAULT 0,
                    stopped_count INTEGER NOT NULL DEFAULT 0,
                    cancelled_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    projection_status TEXT NOT NULL DEFAULT 'synced',
                    projection_requested_at TIMESTAMPTZ,
                    projection_started_at TIMESTAMPTZ,
                    projection_updated_at TIMESTAMPTZ,
                    projection_attempts INTEGER NOT NULL DEFAULT 0,
                    projection_next_retry_at TIMESTAMPTZ,
                    projection_error TEXT,
                    created_by TEXT NOT NULL DEFAULT 'migration',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    completed_at TIMESTAMPTZ,
                    data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    UNIQUE(source_system, source_id)
                )
                """
            )
            cur.execute(
                f"ALTER TABLE {_table('operation_batches')} ADD COLUMN IF NOT EXISTS skipped_count INTEGER NOT NULL DEFAULT 0"
            )
            for column_sql in (
                "projection_status TEXT NOT NULL DEFAULT 'synced'",
                "projection_requested_at TIMESTAMPTZ",
                "projection_started_at TIMESTAMPTZ",
                "projection_updated_at TIMESTAMPTZ",
                "projection_attempts INTEGER NOT NULL DEFAULT 0",
                "projection_next_retry_at TIMESTAMPTZ",
                "projection_error TEXT",
            ):
                cur.execute(
                    f"ALTER TABLE {_table('operation_batches')} ADD COLUMN IF NOT EXISTS {column_sql}"
                )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('operation_tasks')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    task_uuid TEXT NOT NULL UNIQUE,
                    source_system TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    batch_id BIGINT REFERENCES {_table('operation_batches')}(id),
                    parent_task_id BIGINT REFERENCES {_table('operation_tasks')}(id),
                    root_task_id BIGINT REFERENCES {_table('operation_tasks')}(id),
                    task_type TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id BIGINT,
                    attempt_id BIGINT REFERENCES {_table('registration_attempts')}(id),
                    account_id BIGINT,
                    email_snapshot TEXT NOT NULL DEFAULT '',
                    requested_action TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    target_status TEXT NOT NULL DEFAULT 'unknown',
                    current_stage TEXT,
                    last_run_id BIGINT,
                    next_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
                    error_category TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    trigger TEXT NOT NULL DEFAULT 'manual',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    completed_at TIMESTAMPTZ,
                    data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    UNIQUE(source_system, source_id)
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('operation_runs')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    run_uuid TEXT NOT NULL UNIQUE,
                    task_id BIGINT NOT NULL REFERENCES {_table('operation_tasks')}(id) ON DELETE CASCADE,
                    run_no INTEGER NOT NULL,
                    source_system TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    next_attempt_at TIMESTAMPTZ,
                    execution_id TEXT,
                    batch_id BIGINT REFERENCES {_table('operation_batches')}(id),
                    account_id BIGINT,
                    resource_family TEXT NOT NULL DEFAULT 'openai_interactive',
                    cancellation_token TEXT NOT NULL DEFAULT '',
                    cancel_requested_at TIMESTAMPTZ,
                    cancel_reason TEXT,
                    settling_at TIMESTAMPTZ,
                    worker_pid INTEGER,
                    heartbeat_at TIMESTAMPTZ,
                    progress_stage TEXT,
                    progress_steps JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    duration_ms BIGINT,
                    error_category TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    result_summary JSONB,
                    log_file TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    UNIQUE(source_system, source_id),
                    UNIQUE(task_id, run_no)
                )
                """
            )
            # operation_runs 可能已经由上一版统一任务中心创建。这里全部使用
            # ADD COLUMN IF NOT EXISTS，保证开发库和已部署库都能原地升级。
            for column_sql in (
                f"batch_id BIGINT REFERENCES {_table('operation_batches')}(id)",
                "account_id BIGINT",
                "next_attempt_at TIMESTAMPTZ",
                "resource_family TEXT NOT NULL DEFAULT 'openai_interactive'",
                "cancellation_token TEXT NOT NULL DEFAULT ''",
                "cancel_requested_at TIMESTAMPTZ",
                "cancel_reason TEXT",
                "settling_at TIMESTAMPTZ",
                "log_file TEXT",
            ):
                cur.execute(
                    f"ALTER TABLE {_table('operation_runs')} ADD COLUMN IF NOT EXISTS {column_sql}"
                )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('operation_events')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    event_uuid TEXT NOT NULL UNIQUE,
                    task_id BIGINT NOT NULL REFERENCES {_table('operation_tasks')}(id) ON DELETE CASCADE,
                    run_id BIGINT REFERENCES {_table('operation_runs')}(id) ON DELETE CASCADE,
                    source_system TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    level TEXT NOT NULL DEFAULT 'INFO',
                    stage TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT 'progress',
                    error_category TEXT,
                    error_code TEXT,
                    message TEXT NOT NULL,
                    detail JSONB,
                    UNIQUE(source_system, source_id)
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('operation_projection_queue')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    batch_id BIGINT NOT NULL REFERENCES {_table('operation_batches')}(id) ON DELETE CASCADE,
                    reason TEXT NOT NULL DEFAULT 'event',
                    source_system TEXT NOT NULL DEFAULT '',
                    source_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    worker_id TEXT,
                    dirty BOOLEAN NOT NULL DEFAULT FALSE,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(batch_id)
                )
                """
            )
            cur.execute(
                f"ALTER TABLE {_table('operation_events')} "
                "ADD COLUMN IF NOT EXISTS event_type TEXT NOT NULL DEFAULT 'progress'"
            )
            for column_sql in (
                f"batch_id BIGINT REFERENCES {_table('operation_batches')}(id) ON DELETE CASCADE",
                "reason TEXT NOT NULL DEFAULT 'event'",
                "source_system TEXT NOT NULL DEFAULT ''",
                "source_id TEXT NOT NULL DEFAULT ''",
                "status TEXT NOT NULL DEFAULT 'queued'",
                "attempts INTEGER NOT NULL DEFAULT 0",
                "requested_at TIMESTAMPTZ NOT NULL DEFAULT now()",
                "available_at TIMESTAMPTZ NOT NULL DEFAULT now()",
                "started_at TIMESTAMPTZ",
                "completed_at TIMESTAMPTZ",
                "worker_id TEXT",
                "dirty BOOLEAN NOT NULL DEFAULT FALSE",
                "last_error TEXT",
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
            ):
                cur.execute(
                    f"ALTER TABLE {_table('operation_projection_queue')} ADD COLUMN IF NOT EXISTS {column_sql}"
                )
            cur.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {_quote('uq_operation_projection_queue_batch')} "
                f"ON {_table('operation_projection_queue')} (batch_id)"
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('operation_batch_items')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    batch_id BIGINT NOT NULL REFERENCES {_table('operation_batches')}(id) ON DELETE CASCADE,
                    task_id BIGINT NOT NULL REFERENCES {_table('operation_tasks')}(id) ON DELETE CASCADE,
                    run_id BIGINT NOT NULL REFERENCES {_table('operation_runs')}(id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(batch_id, run_id),
                    UNIQUE(batch_id, ordinal)
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('account_operation_leases')} (
                    account_id BIGINT NOT NULL,
                    resource_family TEXT NOT NULL,
                    run_id BIGINT NOT NULL REFERENCES {_table('operation_runs')}(id) ON DELETE CASCADE,
                    lease_token TEXT NOT NULL UNIQUE,
                    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    expires_at TIMESTAMPTZ NOT NULL,
                    cancel_requested_at TIMESTAMPTZ,
                    PRIMARY KEY(account_id, resource_family)
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('operation_resources')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    resource_uuid TEXT NOT NULL UNIQUE,
                    run_id BIGINT NOT NULL REFERENCES {_table('operation_runs')}(id) ON DELETE CASCADE,
                    resource_type TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT '',
                    external_id TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL DEFAULT 'acquired',
                    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    released_at TIMESTAMPTZ,
                    detail JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    UNIQUE(run_id, resource_type, external_id)
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_table('operation_task_dependencies')} (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    parent_source_system TEXT NOT NULL,
                    parent_source_id TEXT NOT NULL,
                    child_source_system TEXT NOT NULL,
                    child_source_id TEXT NOT NULL,
                    dependency_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'waiting',
                    child_status TEXT,
                    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    child_result JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    ready_at TIMESTAMPTZ,
                    next_attempt_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    UNIQUE(parent_source_system, parent_source_id, child_source_system, child_source_id, dependency_type)
                )
                """
            )
            cur.execute(
                f"ALTER TABLE {_table('operation_task_dependencies')} "
                "ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ"
            )
            indexes = (
                ("idx_operation_batches_created", "operation_batches", "created_at DESC"),
                ("idx_operation_tasks_created", "operation_tasks", "id DESC"),
                ("idx_operation_tasks_batch", "operation_tasks", "batch_id, id"),
                ("idx_operation_tasks_account", "operation_tasks", "account_id, id DESC"),
                ("idx_operation_tasks_status", "operation_tasks", "status, id DESC"),
                ("idx_operation_tasks_type", "operation_tasks", "task_type, id DESC"),
                ("idx_operation_runs_task", "operation_runs", "task_id, run_no"),
                ("idx_operation_runs_queue", "operation_runs", "status, next_attempt_at, created_at, id"),
                ("idx_operation_runs_account", "operation_runs", "account_id, id DESC"),
                ("idx_operation_events_task", "operation_events", "task_id, id"),
                ("idx_operation_events_run", "operation_events", "run_id, id"),
                ("idx_operation_projection_queue_due", "operation_projection_queue", "status, available_at, id"),
                ("idx_operation_batch_items_task", "operation_batch_items", "task_id, id"),
                ("idx_operation_resources_run", "operation_resources", "run_id, id"),
                ("idx_account_operation_leases_run", "account_operation_leases", "run_id"),
                ("idx_registration_attempts_account", "registration_attempts", "account_id"),
                ("idx_operation_dependencies_ready", "operation_task_dependencies", "status, next_attempt_at, ready_at, id"),
                ("idx_operation_dependencies_child", "operation_task_dependencies", "child_source_system, child_source_id, id"),
            )
            for name, table, columns in indexes:
                cur.execute(f"CREATE INDEX IF NOT EXISTS {_quote(name)} ON {_table(table)} ({columns})")
            # Compatibility runs store the legacy identity as text.  These
            # expression indexes keep source-backed status reads bounded when
            # the task center contains thousands of historical rows.
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {_quote('idx_registration_jobs_id_text')} "
                f"ON {postgres_store.qualified(record_store.JOBS.name)} ((id::text))"
            )
            cur.execute("SELECT to_regclass(%s) AS name", (f"{_schema_name()}.account_action_tasks",))
            if cur.fetchone()["name"]:
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {_quote('idx_account_action_tasks_id_text')} "
                    f"ON {_table('account_action_tasks')} ((id::text))"
                )
            cur.execute(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS {_quote('uq_operation_runs_active_account_family')}
                ON {_table('operation_runs')} (account_id, resource_family)
                WHERE account_id IS NOT NULL
                  AND status IN ('queued', 'running', 'cancelling', 'settling')
                """
            )
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified(record_store.ACCOUNTS.name)} account
                SET codex_credential_state=CASE
                        WHEN account.deactivated THEN 'deactivated'
                        WHEN account.codex_status='success' OR EXISTS (
                            SELECT 1 FROM {postgres_store.qualified(record_store.CODEX_CREDENTIALS.name)} credential
                            WHERE credential.archived IS FALSE
                              AND LOWER(COALESCE(credential.email, ''))=LOWER(account.email)
                        ) THEN 'valid'
                        ELSE 'none'
                    END,
                    codex_execution_status=COALESCE(account.codex_execution_status, 'empty'),
                    codex_last_run_status=COALESCE(
                        account.codex_last_run_status,
                        CASE
                            WHEN account.codex_status='success' THEN 'success'
                            WHEN account.codex_status IN ('failed','stopped','deactivated','interrupted') THEN account.codex_status
                            ELSE NULL
                        END
                    )
                WHERE account.codex_credential_state IS NULL
                   OR account.codex_execution_status IS NULL
                """
            )
        _READY_KEY = ready_key


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


def _error_fields(message: Any, *, stage: str = "", task_type: str = "") -> tuple[str | None, str | None, str | None]:
    raw = _text(message, 1600).strip()
    info = classify_task_error(raw, stage=stage, task_type=task_type) if raw else None
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
        f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
        f"THEN CASE WHEN {registration_alias}.status='pending' THEN 'queued' ELSE {registration_alias}.status END "
        f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
        f"THEN CASE WHEN {account_alias}.status='pending' THEN 'queued' ELSE {account_alias}.status END "
        f"ELSE {run_alias}.status END"
    )


def _compatibility_run_projection_sql(
    *, run_alias: str = "rr", registration_alias: str = "registration_job",
    account_alias: str = "account_task",
) -> str:
    """Expose source-backed status fields without mutating historical rows on reads."""
    status_sql = _compatibility_run_status_sql(
        run_alias=run_alias, registration_alias=registration_alias, account_alias=account_alias,
    )
    stage_sql = (
        f"CASE WHEN ({status_sql})='queued' THEN 'queued' "
        f"WHEN ({status_sql}) IN ({_TERMINAL_STATUS_SQL}) THEN 'complete' "
        f"ELSE {run_alias}.progress_stage END"
    )
    local_offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    offset_seconds = int(local_offset.total_seconds())
    offset_sign = "+" if offset_seconds >= 0 else "-"
    offset_seconds = abs(offset_seconds)
    offset_hours, offset_remainder = divmod(offset_seconds, 3600)
    offset_minutes = offset_remainder // 60
    local_timezone_sql = f"INTERVAL '{offset_sign}{offset_hours:02d}:{offset_minutes:02d}'"

    def legacy_sort_sql(value_sql: str) -> str:
        text_sql = f"NULLIF(({value_sql})::text, '')"
        return (
            f"CASE WHEN {text_sql} IS NULL THEN NULL "
            f"WHEN {text_sql} ~* '(Z|[+-][0-9]{{2}}:?[0-9]{{2}})$' "
            f"THEN {text_sql}::timestamptz "
            f"ELSE ({text_sql}::timestamp AT TIME ZONE {local_timezone_sql}) END"
        )

    created_at_sort_sql = (
        f"CASE "
        f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
        f"THEN {legacy_sort_sql(f'{registration_alias}.created_at')} "
        f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
        f"THEN {legacy_sort_sql(f'{account_alias}.queued_at')} "
        f"ELSE NULL END"
    )
    return (
        f"{status_sql} AS effective_status, "
        f"{stage_sql} AS effective_progress_stage, "
        f"CASE "
        f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
        f"THEN {registration_alias}.created_at "
        f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
        f"THEN {account_alias}.queued_at "
        f"ELSE NULL END AS effective_created_at, "
        f"CASE "
        f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
        f"THEN NULLIF({registration_alias}.data->>'completed_at', '') "
        f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
        f"THEN NULLIF({account_alias}.finished_at, '') "
        f"ELSE {run_alias}.completed_at::text END AS effective_completed_at, "
        f"{created_at_sort_sql} AS effective_created_at_sort, "
        f"CASE "
        f"WHEN {run_alias}.source_system='registration_jobs' AND {registration_alias}.id IS NOT NULL "
        f"THEN {registration_alias}.data->>'error_message' "
        f"WHEN {run_alias}.source_system='account_action_tasks' AND {account_alias}.id IS NOT NULL "
        f"THEN {account_alias}.error "
        f"ELSE {run_alias}.error_message END AS effective_error_message"
    )


def _compatibility_run_joins_sql(*, run_alias: str = "rr") -> str:
    return (
        f"LEFT JOIN {postgres_store.qualified(record_store.JOBS.name)} registration_job "
        f"ON {run_alias}.source_system='registration_jobs' "
        f"AND registration_job.id::text={run_alias}.source_id "
        f"LEFT JOIN {_table('account_action_tasks')} account_task "
        f"ON {run_alias}.source_system='account_action_tasks' "
        f"AND account_task.id::text={run_alias}.source_id"
    )


def _normalize_compatibility_run(run: dict) -> dict:
    """Overlay a compatibility run with its source row, if that row still exists."""
    effective_status = run.pop("effective_status", None)
    effective_stage = run.pop("effective_progress_stage", None)
    effective_created_at = run.pop("effective_created_at", None)
    run.pop("effective_created_at_sort", None)
    effective_completed_at = run.pop("effective_completed_at", None)
    effective_error_message = run.pop("effective_error_message", None)
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
    return run


def _apply_current_run_projection(task: dict, run: dict | None) -> dict:
    """把当前 attempt 的执行态覆盖到逻辑任务读模型上。"""
    if not run:
        return task
    status = str(run.get("status") or task.get("status") or "queued").lower()
    task["last_run_id"] = run.get("id")
    task["status"] = status
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


def _upsert_batch(
    cur,
    *,
    source_system: str,
    source_id: str,
    batch_type: str,
    title: str,
    requested_count: int,
    created_by: str,
    created_at: Any,
    completed_at: Any = None,
    data: dict | None = None,
) -> int:
    cur.execute(
        f"""
        INSERT INTO {_table('operation_batches')} (
            batch_uuid, source_system, source_id, batch_type, title, requested_count,
            created_by, created_at, completed_at, data
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            batch_type=EXCLUDED.batch_type, title=EXCLUDED.title,
            requested_count=GREATEST({_table('operation_batches')}.requested_count, EXCLUDED.requested_count),
            created_at=EXCLUDED.created_at,
            completed_at=COALESCE(EXCLUDED.completed_at, {_table('operation_batches')}.completed_at),
            data={_table('operation_batches')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            _uuid("batch", f"{source_system}:{source_id}"), source_system, source_id,
            batch_type, _text(title, 240), max(0, int(requested_count or 0)), created_by,
            created_at or _now(), completed_at, _json(data or {}),
        ),
    )
    return int(cur.fetchone()["id"])


def _upsert_attempt(cur, *, root_job_id: int, job: dict, account: dict | None) -> int:
    state = _account_state(account)
    extra = _account_extra(account)
    raw_checkpoint = str(extra.get("registration_checkpoint") or "").strip().lower()
    attempt_data = {"legacy_root_job_id": root_job_id}
    if raw_checkpoint in _LEGACY_REGISTRATION_CHECKPOINT_MAP:
        attempt_data.update({
            "legacy_registration_checkpoint": raw_checkpoint,
            "legacy_checkpoint": raw_checkpoint,
            "checkpoint_migration": {
                "from": raw_checkpoint,
                "to": _LEGACY_REGISTRATION_CHECKPOINT_MAP[raw_checkpoint],
                "source": "operation_projection",
            },
        })
    cur.execute(
        f"""
        INSERT INTO {_table('registration_attempts')} (
            attempt_uuid, source_root_job_id, email_snapshot, account_id, checkpoint,
            remote_identity_state, remote_account_state, local_account_state, target_status,
            created_at, updated_at, completed_at, data
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_root_job_id) DO UPDATE SET
            email_snapshot=CASE WHEN EXCLUDED.email_snapshot <> '' THEN EXCLUDED.email_snapshot
                ELSE {_table('registration_attempts')}.email_snapshot END,
            account_id=COALESCE(EXCLUDED.account_id, {_table('registration_attempts')}.account_id),
            checkpoint=CASE WHEN COALESCE(array_position(ARRAY['created','email_claimed','auth_started','password_request_started','password_confirmed','otp_started','otp_confirmed','account_request_started','account_confirmed','token_obtained','core_persisted','postprocessing','completed','manual_reconcile','failed']::text[], {_table('registration_attempts')}.checkpoint), 0) >= COALESCE(array_position(ARRAY['created','email_claimed','auth_started','password_request_started','password_confirmed','otp_started','otp_confirmed','account_request_started','account_confirmed','token_obtained','core_persisted','postprocessing','completed','manual_reconcile','failed']::text[], EXCLUDED.checkpoint), 0) THEN {_table('registration_attempts')}.checkpoint ELSE EXCLUDED.checkpoint END,
            remote_identity_state=CASE WHEN EXCLUDED.remote_identity_state IN ('unknown','') OR ({_table('registration_attempts')}.remote_identity_state='request_unknown' AND EXCLUDED.remote_identity_state='unknown') THEN {_table('registration_attempts')}.remote_identity_state ELSE EXCLUDED.remote_identity_state END,
            remote_account_state=CASE WHEN EXCLUDED.remote_account_state IN ('unknown','') OR ({_table('registration_attempts')}.remote_account_state='request_unknown' AND EXCLUDED.remote_account_state='unknown') THEN {_table('registration_attempts')}.remote_account_state ELSE EXCLUDED.remote_account_state END,
            local_account_state=CASE WHEN {_table('registration_attempts')}.local_account_state IN ('persisted','saved') AND EXCLUDED.local_account_state IN ('missing','checkpoint_saved') THEN {_table('registration_attempts')}.local_account_state ELSE EXCLUDED.local_account_state END,
            target_status=EXCLUDED.target_status,
            updated_at=EXCLUDED.updated_at,
            completed_at=COALESCE(EXCLUDED.completed_at, {_table('registration_attempts')}.completed_at),
            data={_table('registration_attempts')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            _uuid("attempt", root_job_id), root_job_id,
            str((account or {}).get("email") or job.get("email") or "")[:320],
            int(account["id"]) if account and account.get("id") is not None else None,
            state["checkpoint"], state["remote_identity_state"], state["remote_account_state"],
            state["local_account_state"], state["target_status"],
            _legacy_registration_timestamp(job.get("created_at")) or _now(),
            _legacy_registration_timestamp(job.get("updated_at"))
            or _legacy_registration_timestamp(job.get("completed_at")) or _now(),
            _legacy_registration_timestamp(job.get("completed_at"))
            if state["target_status"] == "account_available" else None,
            _json(attempt_data),
        ),
    )
    return int(cur.fetchone()["id"])


def _registration_task_type(job: dict) -> str:
    value = str(job.get("job_type") or "registration").strip().lower()
    return value if value in {"registration", "registration_resume", "codex_retry", "twofa_retry"} else "registration"


def _next_registration_actions(job: dict, account: dict | None, target_status: str) -> list[dict[str, Any]]:
    if _status(job.get("status")) not in _TERMINAL_STATUSES:
        return []
    source_job_id = int(job.get("id") or 0)
    if target_status == "email_verification_pending":
        return [{"action": "registration_resume", "label": "继续邮箱验证", "source_job_id": source_job_id}]
    if not account:
        return [{"action": "registration_retry", "label": "重新执行注册", "source_job_id": source_job_id}]
    snapshot = job.get("config_snapshot")
    if not isinstance(snapshot, dict):
        raw_data = job.get("data")
        snapshot = raw_data.get("config_snapshot") if isinstance(raw_data, dict) else None
    has_snapshot = isinstance(snapshot, dict)
    codex_enabled = bool(snapshot.get("codex_enabled", True)) if has_snapshot else True
    if codex_enabled and str(account.get("codex_status") or "") != "success":
        return [{"action": "codex_retry", "label": "补跑 Codex", "source_job_id": source_job_id}]
    extra = _account_extra(account)
    missing_setup = False
    if (not has_snapshot or bool(snapshot.get("password_enabled", True))) and not str(
        extra.get("account_password") or extra.get("login_password") or ""
    ).strip():
        missing_setup = True
    if (not has_snapshot or bool(snapshot.get("twofa_enabled", True))) and (
        not str(account.get("totp_secret") or "").strip() or bool(extra.get("totp_setup_pending"))
    ):
        missing_setup = True
    if (not has_snapshot or bool(snapshot.get("plan_check_enabled", True))) and str(
        account.get("plan_check_status") or ""
    ).lower() != "success":
        missing_setup = True
    if missing_setup:
        return [{"action": "twofa_retry", "label": "补齐账号配置", "source_job_id": source_job_id}]
    return []


def _lookup_task(cur, source_system: str, source_id: str) -> int | None:
    cur.execute(
        f"SELECT id FROM {_table('operation_tasks')} WHERE source_system=%s AND source_id=%s",
        (source_system, source_id),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


def _upsert_registration_job(cur, job: dict, accounts_by_id: dict[int, dict], accounts_by_email: dict[str, dict]) -> int:
    job_id = int(job["id"])
    root_job_id = int(job.get("root_job_id") or job_id)
    task_type = _registration_task_type(job)
    task_source_id = f"{root_job_id}:{task_type}"
    task_table = _table("operation_tasks")
    account = None
    if job.get("account_id") is not None:
        account = accounts_by_id.get(int(job["account_id"]))
    if account is None and job.get("email"):
        account = accounts_by_email.get(str(job.get("email") or "").strip().lower())
    attempt_id = _upsert_attempt(cur, root_job_id=root_job_id, job=job, account=account)
    projection_data = {
        "legacy_root_job_id": root_job_id,
        "latest_legacy_job_id": job_id,
    }
    if isinstance(job.get("config_snapshot"), dict):
        projection_data["config_snapshot"] = dict(job["config_snapshot"])
    cur.execute(
        f"UPDATE {postgres_store.qualified('registration_jobs')} SET attempt_id=%s WHERE id=%s",
        (attempt_id, job_id),
    )
    state = _account_state(account)
    batch_id = None
    legacy_batch_id = str(job.get("batch_id") or "").strip()
    if legacy_batch_id:
        batch_id = _upsert_batch(
            cur,
            source_system="registration_batches",
            source_id=legacy_batch_id,
            batch_type="registration" if task_type == "registration" else "retry",
            title="注册批次" if task_type == "registration" else "注册补跑批次",
            requested_count=int(job.get("batch_size") or 1),
            created_by="webui",
            created_at=_legacy_registration_timestamp(job.get("created_at")),
            data={"legacy_batch_id": legacy_batch_id, "workers": job.get("batch_workers")},
        )
    parent_task_id = None
    if task_type != "registration":
        parent_task_id = _lookup_task(cur, "registration_chains", f"{root_job_id}:registration")
    error_category, error_code, error_message = _error_fields(
        job.get("error_message"), stage=str(job.get("progress_stage") or ""), task_type=task_type,
    )
    status = _status(job.get("status"))
    created_at = _legacy_registration_timestamp(job.get("created_at")) or _now()
    completed_at = (
        _legacy_registration_timestamp(job.get("completed_at"))
        if status in _TERMINAL_STATUSES else None
    )
    updated_at = _legacy_registration_timestamp(job.get("updated_at")) or completed_at or _now()
    started_at = _legacy_registration_timestamp(job.get("started_at"))
    source_system = "registration_chains"
    task_uuid = _uuid("task", f"{source_system}:{task_source_id}")
    next_actions = _next_registration_actions(job, account, state["target_status"])
    cur.execute(
        f"""
        INSERT INTO {_table('operation_tasks')} (
            task_uuid, source_system, source_id, batch_id, parent_task_id, task_type,
            target_type, target_id, attempt_id, account_id, email_snapshot, requested_action,
            status, target_status, current_stage, next_actions, error_category, error_code,
            error_message, trigger, created_at, updated_at, completed_at, data
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            batch_id=COALESCE(EXCLUDED.batch_id, {_table('operation_tasks')}.batch_id),
            parent_task_id=COALESCE(EXCLUDED.parent_task_id, {_table('operation_tasks')}.parent_task_id),
            attempt_id=EXCLUDED.attempt_id,
            account_id=COALESCE(EXCLUDED.account_id, {_table('operation_tasks')}.account_id),
            email_snapshot=CASE WHEN EXCLUDED.email_snapshot <> '' THEN EXCLUDED.email_snapshot
                ELSE {_table('operation_tasks')}.email_snapshot END,
            status=EXCLUDED.status, target_status=EXCLUDED.target_status,
            current_stage=EXCLUDED.current_stage, next_actions=EXCLUDED.next_actions,
            error_category=EXCLUDED.error_category, error_code=EXCLUDED.error_code,
            error_message=EXCLUDED.error_message,
            updated_at=CASE WHEN
                {task_table}.batch_id IS DISTINCT FROM COALESCE(EXCLUDED.batch_id, {task_table}.batch_id)
                OR {task_table}.parent_task_id IS DISTINCT FROM COALESCE(EXCLUDED.parent_task_id, {task_table}.parent_task_id)
                OR {task_table}.attempt_id IS DISTINCT FROM EXCLUDED.attempt_id
                OR {task_table}.account_id IS DISTINCT FROM COALESCE(EXCLUDED.account_id, {task_table}.account_id)
                OR {task_table}.email_snapshot IS DISTINCT FROM CASE
                    WHEN EXCLUDED.email_snapshot <> '' THEN EXCLUDED.email_snapshot
                    ELSE {task_table}.email_snapshot
                END
                OR {task_table}.status IS DISTINCT FROM EXCLUDED.status
                OR {task_table}.target_status IS DISTINCT FROM EXCLUDED.target_status
                OR {task_table}.current_stage IS DISTINCT FROM EXCLUDED.current_stage
                OR {task_table}.next_actions IS DISTINCT FROM EXCLUDED.next_actions
                OR {task_table}.error_category IS DISTINCT FROM EXCLUDED.error_category
                OR {task_table}.error_code IS DISTINCT FROM EXCLUDED.error_code
                OR {task_table}.error_message IS DISTINCT FROM EXCLUDED.error_message
                OR {task_table}.completed_at IS DISTINCT FROM EXCLUDED.completed_at
                OR {task_table}.data IS DISTINCT FROM ({task_table}.data || EXCLUDED.data)
                THEN now() ELSE {task_table}.updated_at END,
            completed_at=EXCLUDED.completed_at,
            data={task_table}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            task_uuid, source_system, task_source_id,
            batch_id, parent_task_id, task_type,
            "account" if task_type in {"codex_retry", "twofa_retry"} and account else "registration_attempt",
            int(account["id"]) if account and task_type in {"codex_retry", "twofa_retry"} else attempt_id,
            attempt_id, int(account["id"]) if account else None,
            str((account or {}).get("email") or job.get("email") or "")[:320], task_type,
            status, state["target_status"], normalize_stage(job.get("progress_stage")), _json(next_actions),
            error_category, error_code, error_message,
            "manual_retry" if job.get("parent_job_id") else "manual",
            created_at, updated_at, completed_at,
            _json(projection_data),
        ),
    )
    task_id = int(cur.fetchone()["id"])
    if task_type == "registration":
        cur.execute(
            f"UPDATE {_table('operation_tasks')} SET root_task_id=id WHERE id=%s AND root_task_id IS NULL",
            (task_id,),
        )
        cur.execute(
            f"UPDATE {_table('registration_attempts')} SET root_task_id=%s WHERE id=%s",
            (task_id, attempt_id),
        )
    else:
        root_task_id = parent_task_id or task_id
        cur.execute(
            f"UPDATE {_table('operation_tasks')} SET root_task_id=%s WHERE id=%s",
            (root_task_id, task_id),
        )
    retry_attempt = int(job.get("retry_attempt") or 0)
    run_no = max(1, retry_attempt + 1)
    run_uuid = _uuid("run", f"registration_jobs:{job_id}")
    progress_steps = job.get("progress_steps") if isinstance(job.get("progress_steps"), dict) else {}
    cur.execute(
        f"SELECT id FROM {_table('operation_runs')} WHERE source_system='registration_jobs' AND source_id=%s",
        (str(job_id),),
    )
    existing_run = cur.fetchone()
    if existing_run:
        run_no_clause = "run_no=operation_runs.run_no,"
    else:
        cur.execute(f"SELECT COALESCE(MAX(run_no),0)+1 AS n FROM {_table('operation_runs')} WHERE task_id=%s", (task_id,))
        run_no = max(run_no, int(cur.fetchone()["n"]))
        run_no_clause = "run_no=EXCLUDED.run_no,"
    run_log_file = str(job.get("log_file") or "").strip() or task_run_log.build_path(
        task_uuid=task_uuid, run_no=run_no, run_uuid=run_uuid,
    )
    cur.execute(
        f"""
        INSERT INTO {_table('operation_runs')} (
            run_uuid, task_id, run_no, source_system, source_id, status, execution_id,
            progress_stage, progress_steps, started_at, completed_at, duration_ms,
            error_category, error_code, error_message, result_summary, log_file, created_at, data
        ) VALUES (%s,%s,%s,'registration_jobs',%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            task_id=EXCLUDED.task_id, {run_no_clause} status=EXCLUDED.status,
            progress_stage=EXCLUDED.progress_stage, progress_steps=EXCLUDED.progress_steps,
            started_at=EXCLUDED.started_at, completed_at=EXCLUDED.completed_at,
            duration_ms=EXCLUDED.duration_ms, error_category=EXCLUDED.error_category,
            error_code=EXCLUDED.error_code, error_message=EXCLUDED.error_message,
            result_summary=EXCLUDED.result_summary, log_file=EXCLUDED.log_file,
            data={_table('operation_runs')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            run_uuid, task_id, run_no, str(job_id), status,
            str(job.get("job_uuid") or "") or None, normalize_stage(job.get("progress_stage")),
            _json(progress_steps), started_at, completed_at,
            _duration(started_at, completed_at), error_category, error_code,
            error_message, _json({"account_id": (account or {}).get("id"), "retry_action": job.get("retry_action")}),
            run_log_file, created_at,
            _json({
                "legacy_job_id": job_id,
                "parent_job_id": job.get("parent_job_id"),
                **({"config_snapshot": dict(job["config_snapshot"])} if isinstance(job.get("config_snapshot"), dict) else {}),
            }),
        ),
    )
    run_id = int(cur.fetchone()["id"])
    for raw_stage, raw_step in progress_steps.items():
        step = raw_step if isinstance(raw_step, dict) else {}
        stage = normalize_stage(raw_stage)
        state_value = str(step.get("state") or "pending")
        level = "ERROR" if state_value in {"failed", "stopped"} else "INFO"
        category, code, _ = _error_fields(
            step.get("detail") if level == "ERROR" else None, stage=stage, task_type=task_type,
        )
        event_source_id = f"{job_id}:stage:{raw_stage}"
        cur.execute(
            f"""
            INSERT INTO {_table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id, created_at, level,
                stage, event_type, error_category, error_code, message, detail
            ) VALUES (%s,%s,%s,'registration_progress',%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (source_system, source_id) DO UPDATE SET
                task_id=EXCLUDED.task_id, run_id=EXCLUDED.run_id, created_at=EXCLUDED.created_at,
                level=EXCLUDED.level, stage=EXCLUDED.stage, event_type=EXCLUDED.event_type,
                error_category=EXCLUDED.error_category, error_code=EXCLUDED.error_code,
                message=EXCLUDED.message, detail=EXCLUDED.detail
            """,
            (
                _uuid("event", f"registration_progress:{event_source_id}"), task_id, run_id,
                event_source_id,
                _legacy_registration_timestamp(step.get("completed_at"))
                or _legacy_registration_timestamp(step.get("started_at"))
                or updated_at or _now(),
                level, stage, f"stage.{state_value}", category, code,
                _text(step.get("detail") or state_value, 1200),
                _json({"state": state_value, "started_at": step.get("started_at"), "completed_at": step.get("completed_at")}),
            ),
        )
    # A retry shares the logical task with its parent.  An older sync callback
    # may arrive after the newer attempt has started, so selecting by run_no
    # alone can temporarily put the task back into a historical terminal state.
    # Prefer any active run first, then fall back to the newest terminal run.
    cur.execute(
        f"""
        SELECT id, run_no, source_id, status, progress_stage,
               error_category, error_code, error_message, completed_at
        FROM {_table('operation_runs')}
        WHERE task_id=%s
        ORDER BY CASE WHEN status IN ('queued','running','cancelling','settling') THEN 0 ELSE 1 END,
                 run_no DESC, id DESC
        LIMIT 1
        """,
        (task_id,),
    )
    latest = cur.fetchone()
    latest_job = job
    latest_source_id = str(latest.get("source_id") or "") if latest else ""
    if latest and latest_source_id.isdigit() and latest_source_id != str(job_id):
        cur.execute(
            f"SELECT * FROM {postgres_store.qualified(record_store.JOBS.name)} WHERE id=%s",
            (int(latest_source_id),),
        )
        raw_latest_job = cur.fetchone()
        if raw_latest_job:
            latest_job = record_store.merge_row(record_store.JOBS, dict(raw_latest_job)) or dict(raw_latest_job)
    latest_status = str(latest["status"] or "queued") if latest else status
    latest_next_actions = (
        [] if latest_status in _ACTIVE_RUN_STATUSES
        else _next_registration_actions(latest_job, account, state["target_status"])
    )
    cur.execute(
        f"""
        UPDATE {task_table} SET
            updated_at=CASE WHEN
                {task_table}.last_run_id IS DISTINCT FROM %s
                OR {task_table}.status IS DISTINCT FROM %s
                OR {task_table}.current_stage IS DISTINCT FROM %s
                OR {task_table}.error_category IS DISTINCT FROM %s
                OR {task_table}.error_code IS DISTINCT FROM %s
                OR {task_table}.error_message IS DISTINCT FROM %s
                OR {task_table}.completed_at IS DISTINCT FROM %s
                OR {task_table}.next_actions IS DISTINCT FROM %s::jsonb
                THEN now() ELSE {task_table}.updated_at END,
            last_run_id=%s, status=%s, current_stage=%s,
            error_category=%s, error_code=%s, error_message=%s,
            completed_at=%s, next_actions=%s::jsonb
        WHERE id=%s
        """,
        (
            latest["id"], latest_status, latest["progress_stage"], latest["error_category"],
            latest["error_code"], latest["error_message"], latest["completed_at"],
            _json(latest_next_actions),
            latest["id"], latest_status, latest["progress_stage"], latest["error_category"],
            latest["error_code"], latest["error_message"], latest["completed_at"],
            _json(latest_next_actions), task_id,
        ),
    )
    return task_id


def _upsert_account_batch(cur, batch: dict) -> int:
    return _upsert_batch(
        cur,
        source_system="account_action_batches",
        source_id=str(batch["id"]),
        batch_type="account_action",
        title=str(batch.get("action_type") or "账号操作批次"),
        requested_count=int(batch.get("total_count") or 0),
        created_by=str(batch.get("trigger") or "manual"),
        created_at=_legacy_account_timestamp(batch.get("created_at")),
        completed_at=_legacy_account_timestamp(batch.get("completed_at")),
        data={"legacy_action_type": batch.get("action_type")},
    )


def _upsert_account_task(
    cur,
    task: dict,
    batch_map: dict[str, int],
    accounts_by_id: dict[int, dict] | None = None,
) -> int:
    legacy_id = int(task["id"])
    task_type = str(task.get("task_type") or "unknown")
    status = _status(task.get("status"))
    category, code, error = _error_fields(task.get("error"), stage="complete", task_type=task_type)
    batch_id = batch_map.get(str(task.get("batch_id") or ""))
    account_id = int(task["account_id"]) if task.get("account_id") is not None else None
    account = (accounts_by_id or {}).get(account_id) if account_id is not None else None
    account_state = _account_state(account)
    target_status = "deactivated" if status == "deactivated" else account_state["target_status"]
    next_actions: list[dict[str, Any]] = []
    if target_status == "email_verification_pending" and account_id is not None:
        cur.execute(
            f"""
            SELECT next_actions FROM {_table('operation_tasks')}
            WHERE account_id=%s AND task_type='registration'
              AND target_status='email_verification_pending'
            ORDER BY id DESC LIMIT 1
            """,
            (account_id,),
        )
        registration_task = cur.fetchone()
        if registration_task:
            next_actions = _decode(registration_task["next_actions"]) or []
    elif status != "success":
        next_actions = [{"action": "retry", "label": "重新执行", "source_task_id": legacy_id}]
    source_id = str(legacy_id)
    task_uuid = _uuid("task", f"account_action_tasks:{legacy_id}")
    run_uuid = _uuid("run", f"account_action_tasks:{legacy_id}")
    run_log_file = str(task.get("log_file") or "").strip() or task_run_log.build_path(
        task_uuid=task_uuid, run_no=1, run_uuid=run_uuid,
    )
    queued_at = _legacy_account_timestamp(task.get("queued_at")) or _now()
    started_at = _legacy_account_timestamp(task.get("started_at"))
    finished_at = _legacy_account_timestamp(task.get("finished_at"))
    cur.execute(
        f"""
        INSERT INTO {_table('operation_tasks')} (
            task_uuid, source_system, source_id, batch_id, task_type, target_type, target_id,
            account_id, email_snapshot, requested_action, status, target_status, current_stage,
            next_actions, error_category, error_code, error_message, trigger,
            created_at, updated_at, completed_at, data
        ) VALUES (%s,'account_action_tasks',%s,%s,%s,'account',%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            batch_id=COALESCE(EXCLUDED.batch_id, {_table('operation_tasks')}.batch_id),
            task_type=EXCLUDED.task_type, account_id=EXCLUDED.account_id,
            target_id=EXCLUDED.target_id, email_snapshot=EXCLUDED.email_snapshot,
            status=EXCLUDED.status, target_status=EXCLUDED.target_status,
            current_stage=EXCLUDED.current_stage, next_actions=EXCLUDED.next_actions,
            error_category=EXCLUDED.error_category, error_code=EXCLUDED.error_code,
            error_message=EXCLUDED.error_message, created_at=EXCLUDED.created_at,
            updated_at=EXCLUDED.updated_at,
            completed_at=EXCLUDED.completed_at,
            data={_table('operation_tasks')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            task_uuid, source_id, batch_id, task_type,
            account_id, account_id, str(task.get("email_snapshot") or "")[:320], task_type,
            status, target_status, "complete" if status in _TERMINAL_STATUSES else "queued",
            _json(next_actions),
            category, code, error, str(task.get("trigger") or "manual"),
            queued_at, finished_at or started_at or queued_at,
            finished_at, _json({"legacy_account_task_id": legacy_id}),
        ),
    )
    operation_task_id = int(cur.fetchone()["id"])
    cur.execute(
        f"UPDATE {_table('operation_tasks')} SET root_task_id=id WHERE id=%s AND root_task_id IS NULL",
        (operation_task_id,),
    )
    cur.execute(
        f"""
        INSERT INTO {_table('operation_runs')} (
            run_uuid, task_id, run_no, source_system, source_id, status, progress_stage,
            started_at, completed_at, duration_ms, error_category, error_code, error_message,
            result_summary, log_file, created_at, data
        ) VALUES (%s,%s,1,'account_action_tasks',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            task_id=EXCLUDED.task_id, status=EXCLUDED.status, progress_stage=EXCLUDED.progress_stage,
            started_at=EXCLUDED.started_at, completed_at=EXCLUDED.completed_at,
            created_at=EXCLUDED.created_at,
            duration_ms=EXCLUDED.duration_ms, error_category=EXCLUDED.error_category,
            error_code=EXCLUDED.error_code, error_message=EXCLUDED.error_message,
            result_summary=EXCLUDED.result_summary, log_file=COALESCE(EXCLUDED.log_file, {_table('operation_runs')}.log_file),
            data={_table('operation_runs')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            run_uuid, operation_task_id, source_id, status,
            "complete" if status in _TERMINAL_STATUSES else "queued",
            started_at, finished_at, task.get("duration_ms"),
            category, code, error, _json(task.get("result_summary") or {}),
            run_log_file, queued_at,
            _json({
                "validation_method": task.get("validation_method"),
                "network_route": task.get("network_route"),
                "proxy_mode": task.get("proxy_mode"),
                "proxy_provider": task.get("proxy_provider"),
                "proxy_region": task.get("proxy_region"),
                "proxy_used": task.get("proxy_used"),
            }),
        ),
    )
    run_id = int(cur.fetchone()["id"])
    cur.execute(
        f"UPDATE {_table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
        (run_id, operation_task_id),
    )
    return operation_task_id


def _upsert_account_event(cur, event: dict, task_map: dict[int, int]) -> None:
    legacy_task_id = int(event["task_id"])
    operation_task_id = task_map.get(legacy_task_id)
    if not operation_task_id:
        return
    cur.execute(
        f"SELECT id FROM {_table('operation_runs')} WHERE source_system='account_action_tasks' AND source_id=%s",
        (str(legacy_task_id),),
    )
    run = cur.fetchone()
    level = str(event.get("level") or "INFO").upper()
    raw_stage = str(event.get("stage") or "event")
    stage = normalize_stage(raw_stage)
    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    explicit_state = normalize_step_state(detail.get("step_state"))
    stored_event_type = str(event.get("event_type") or "").strip()
    if explicit_state is not None:
        event_type = f"stage.{explicit_state}"
    elif stored_event_type:
        event_type = stored_event_type[:120]
    elif level == "ERROR":
        event_type = "stage.failed"
    else:
        message = str(event.get("message") or "")
        if raw_stage in {"queued", "running"}:
            event_type = "run.queued" if raw_stage == "queued" else "run.running"
        elif any(marker in message for marker in ("跳过", "无需", "暂时无法")):
            event_type = "stage.skipped"
        elif raw_stage.endswith("_result"):
            event_type = (
                "stage.failed"
                if level == "WARNING" or any(marker in message for marker in ("失败", "异常", "未完成"))
                else "stage.success"
            )
        elif raw_stage == "complete":
            event_type = "stage.success"
        elif any(marker in message for marker in ("已分配", "已启用", "已完成", "已写回", "已保存")):
            event_type = "stage.success"
        else:
            event_type = "note.info"
    category, code, _ = _error_fields(
        event.get("message") if level == "ERROR" else None, stage=stage,
    )
    source_id = str(event["id"])
    cur.execute(
        f"""
        INSERT INTO {_table('operation_events')} (
            event_uuid, task_id, run_id, source_system, source_id, created_at, level,
            stage, event_type, error_category, error_code, message, detail
        ) VALUES (%s,%s,%s,'account_action_events',%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            task_id=EXCLUDED.task_id, run_id=EXCLUDED.run_id, created_at=EXCLUDED.created_at,
            level=EXCLUDED.level, stage=EXCLUDED.stage, event_type=EXCLUDED.event_type,
            error_category=EXCLUDED.error_category,
            error_code=EXCLUDED.error_code, message=EXCLUDED.message, detail=EXCLUDED.detail
        """,
        (
            _uuid("event", f"account_action_events:{source_id}"), operation_task_id,
            int(run["id"]) if run else None, source_id,
            _legacy_account_timestamp(event.get("created_at")) or _now(),
            level, stage, event_type, category, code, _text(event.get("message"), 1600),
            _json(detail),
        ),
    )
    if run and event_type.startswith("stage."):
        state_value = normalize_step_state(event_type.removeprefix("stage."))
        if state_value is not None:
            cur.execute(
                f"""
                UPDATE {_table('operation_runs')}
                SET progress_steps=jsonb_set(progress_steps, %s, to_jsonb(%s::text), true)
                WHERE id=%s
                """,
                ([stage], state_value, int(run["id"])),
            )
            if state_value == "running":
                cur.execute(
                    f"UPDATE {_table('operation_runs')} SET progress_stage=%s WHERE id=%s",
                    (stage, int(run["id"])),
                )
                cur.execute(
                    f"UPDATE {_table('operation_tasks')} SET current_stage=%s WHERE id=%s",
                    (stage, operation_task_id),
                )


def _lock_projection_batch(cur, batch_id: int) -> None:
    """Acquire the database writer lock for exactly one batch.

    Queue consumers and direct runtime updates use this same advisory lock.  A
    multi-batch caller must invoke it in ascending batch-id order; this is the
    lock-order contract that keeps two batch refreshes from deadlocking.
    """
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (int(batch_id),))


def _effective_batch_status_counts(cur, batch_id: int) -> dict[str, int]:
    """Count one effective status per logical root task, including child retries."""
    cur.execute(
        f"""
        WITH task_rows AS (
            SELECT id, COALESCE(root_task_id, id) AS root_id, status, updated_at
            FROM {_table('operation_tasks')}
            WHERE batch_id=%s
        ), root_tasks AS (
            SELECT DISTINCT ON (root_id) root_id, id, status
            FROM task_rows
            ORDER BY root_id, (id = root_id) DESC, updated_at DESC, id DESC
        ), latest_children AS (
            SELECT DISTINCT ON (root_id) root_id, status
            FROM task_rows
            WHERE id <> root_id
            ORDER BY root_id, updated_at DESC, id DESC
        ), effective AS (
            SELECT root_tasks.root_id,
                   CASE
                       WHEN latest_children.status IS NULL THEN root_tasks.status
                       WHEN latest_children.status='failed'
                            AND root_tasks.status IN ('success','partial_success')
                           THEN 'partial_success'
                       ELSE latest_children.status
                   END AS status
            FROM root_tasks
            LEFT JOIN latest_children USING (root_id)
        )
        SELECT status, COUNT(*) AS n
        FROM effective
        GROUP BY status
        """,
        (int(batch_id),),
    )
    return {str(row["status"]): int(row["n"]) for row in cur.fetchall()}


def _lock_existing_projection_queue(cur, batch_id: int) -> dict | None:
    """Lock an existing queue row before touching its operation batch.

    Projection workers always lock queue rows before batch rows. Compatibility
    writers must follow the same order when a batch has already been queued;
    a new batch has no visible queue row and is safe to create in this
    transaction before enqueueing it.
    """
    cur.execute(
        f"SELECT id FROM {_table('operation_projection_queue')} WHERE batch_id=%s FOR UPDATE",
        (int(batch_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _refresh_batch(cur, batch_id: int) -> None:
    batch_id = int(batch_id)
    _lock_projection_batch(cur, batch_id)
    cur.execute(
        f"SELECT skipped_count FROM {_table('operation_batches')} WHERE id=%s FOR UPDATE",
        (batch_id,),
    )
    raw = cur.fetchone()
    if not raw:
        return
    skipped = int(raw.get("skipped_count") or 0)
    counts = _effective_batch_status_counts(cur, batch_id)
    queued = counts.get("queued", 0)
    running = (
        counts.get("running", 0) + counts.get("stopping", 0)
        + counts.get("cancelling", 0) + counts.get("settling", 0)
        + counts.get("waiting", 0)
    )
    success = counts.get("success", 0)
    partial = counts.get("partial_success", 0)
    failed = counts.get("failed", 0) + counts.get("deactivated", 0) + counts.get("unsupported", 0)
    attention = (
        counts.get("attention_required", 0)
        + counts.get("interrupted", 0)
        + counts.get("request_unknown", 0)
        + counts.get("manual_reconcile", 0)
    )
    stopped = counts.get("stopped", 0)
    cancelled = counts.get("cancelled", 0)
    if running:
        status = "running"
        completed_at = None
    elif queued:
        status = "queued"
        completed_at = None
    elif failed or attention or skipped:
        status = "partial_success" if success or partial else "failed"
        completed_at = _now()
    elif partial:
        status = "partial_success"
        completed_at = _now()
    elif success:
        status = "success"
        completed_at = _now()
    elif stopped or cancelled:
        status = "stopped"
        completed_at = _now()
    else:
        status = "queued"
        completed_at = None
    cur.execute(
        f"""
        UPDATE {_table('operation_batches')} SET status=%s, queued_count=%s,
            running_count=%s, success_count=%s, partial_count=%s, failed_count=%s,
            attention_count=%s, stopped_count=%s, cancelled_count=%s,
            completed_at=COALESCE(%s, completed_at)
        WHERE id=%s
        """,
        (status, queued, running, success, partial, failed, attention, stopped, cancelled, completed_at, batch_id),
    )


def _refresh_batches(cur, batch_ids: Iterable[int] | None = None) -> None:
    """Refresh only selected batches; ``None`` is reserved for full reconcile."""
    if batch_ids is None:
        cur.execute(f"SELECT id FROM {_table('operation_batches')} ORDER BY id")
        ids = [int(row["id"]) for row in cur.fetchall()]
    else:
        ids = sorted({int(value) for value in batch_ids if value is not None})
    for batch_id in ids:
        _refresh_batch(cur, batch_id)


# ============================================================
# 异步批次投影队列
# ============================================================

def _projection_backoff(attempts: int) -> int:
    """Bounded exponential delay for a failed batch projection."""
    return min(15 * 60, max(1, int(_PROJECTION_RETRY_BASE_SECONDS * (2 ** max(0, int(attempts) - 1)))))


def _enqueue_batch_projection_cur(
    cur,
    batch_id: int,
    *,
    reason: str = "event",
    source_system: str = "",
    source_id: str = "",
    requested_at: Any = None,
) -> dict:
    batch_id = int(batch_id)
    requested = requested_at or _now()
    cur.execute(
        f"SELECT id FROM {_table('operation_batches')} WHERE id=%s",
        (batch_id,),
    )
    if not cur.fetchone():
        raise LookupError(f"投影批次不存在: {batch_id}")
    # queue row is the first lock in the worker path; an event arriving while a
    # writer is running marks the row dirty so the writer runs once more.
    cur.execute(
        f"""
        INSERT INTO {_table('operation_projection_queue')} AS queue (
            batch_id, reason, source_system, source_id, status, requested_at, available_at
        ) VALUES (%s,%s,%s,%s,'queued',%s,%s)
        ON CONFLICT (batch_id) DO UPDATE SET
            reason=EXCLUDED.reason,
            source_system=EXCLUDED.source_system,
            source_id=EXCLUDED.source_id,
            requested_at=EXCLUDED.requested_at,
            status=CASE WHEN queue.status='running'
                        THEN 'running' ELSE 'queued' END,
            dirty=CASE WHEN queue.status='running'
                       THEN TRUE ELSE FALSE END,
            available_at=CASE WHEN queue.status='running'
                              THEN queue.available_at ELSE EXCLUDED.available_at END,
            completed_at=CASE WHEN queue.status='running'
                              THEN queue.completed_at ELSE NULL END,
            last_error=CASE WHEN queue.status='running'
                            THEN queue.last_error ELSE NULL END,
            updated_at=now()
        RETURNING *
        """,
        (
            batch_id, _text(reason, 120), _text(source_system, 120), _text(source_id, 240),
            requested, requested,
        ),
    )
    queue_row = dict(cur.fetchone())
    cur.execute(
        f"""
        UPDATE {_table('operation_batches')}
        SET projection_status=CASE WHEN projection_status='running' THEN 'running' ELSE 'queued' END,
            projection_requested_at=%s,
            projection_next_retry_at=NULL,
            projection_error=CASE WHEN projection_status='running' THEN projection_error ELSE NULL END
        WHERE id=%s
        """,
        (requested, batch_id),
    )
    return _row(queue_row) or {}


def enqueue_batch_projection(
    batch_id: int,
    *,
    reason: str = "event",
    source_system: str = "",
    source_id: str = "",
    requested_at: Any = None,
) -> dict:
    """Persist one coalesced projection request for a specific batch."""
    init()
    with _connect() as conn, conn.cursor() as cur:
        return _enqueue_batch_projection_cur(
            cur, int(batch_id), reason=reason, source_system=source_system,
            source_id=source_id, requested_at=requested_at,
        )


def _claim_projection_cur(cur, *, worker_id: str) -> dict | None:
    # Fixed lock order: projection_queue row -> operation_batches row.
    # A process crash can leave a queue row in ``running`` forever.  Reclassify
    # only expired leases before claiming so a later worker can retry it.
    cur.execute(
        f"""
        UPDATE {_table('operation_projection_queue')}
        SET status='failed', available_at=now(), worker_id=NULL,
            last_error=COALESCE(last_error, 'projection worker lease expired'), updated_at=now()
        WHERE status='running'
          AND started_at IS NOT NULL
          AND started_at < now() - (%s * interval '1 second')
        """,
        (_PROJECTION_LEASE_TIMEOUT_SECONDS,),
    )
    cur.execute(
        f"""
        SELECT q.*, b.batch_uuid, b.source_system AS batch_source_system,
               b.source_id AS batch_source_id
        FROM {_table('operation_projection_queue')} q
        JOIN {_table('operation_batches')} b ON b.id=q.batch_id
        WHERE q.status IN ('queued','failed')
          AND q.available_at <= now()
        ORDER BY q.batch_id, q.id
        FOR UPDATE OF q SKIP LOCKED
        LIMIT 1
        """
    )
    found = cur.fetchone()
    if not found:
        return None
    row = dict(found)
    batch_id = int(row["batch_id"])
    cur.execute(
        f"SELECT id FROM {_table('operation_batches')} WHERE id=%s FOR UPDATE",
        (batch_id,),
    )
    if not cur.fetchone():
        return None
    now = _now()
    attempts = int(row.get("attempts") or 0) + 1
    cur.execute(
        f"""
        UPDATE {_table('operation_projection_queue')}
        SET status='running', attempts=%s, started_at=%s, worker_id=%s,
            updated_at=%s, last_error=NULL
        WHERE id=%s
        RETURNING *
        """,
        (attempts, now, _text(worker_id, 160), now, int(row["id"])),
    )
    claimed = dict(cur.fetchone())
    cur.execute(
        f"""
        UPDATE {_table('operation_batches')}
        SET projection_status='running', projection_started_at=%s,
            projection_attempts=%s, projection_next_retry_at=NULL
        WHERE id=%s
        """,
        (now, attempts, batch_id),
    )
    claimed.update({"batch_uuid": row.get("batch_uuid"), "batch_source_system": row.get("batch_source_system"), "batch_source_id": row.get("batch_source_id")})
    return _row(claimed) or {}


def claim_projection(*, worker_id: str | None = None) -> dict | None:
    """Atomically claim one due batch; concurrent workers skip locked rows."""
    init()
    identifier = str(worker_id or f"pid-{os.getpid()}-thread-{threading.get_ident()}")
    with _connect() as conn, conn.cursor() as cur:
        return _claim_projection_cur(cur, worker_id=identifier)


def _complete_projection(batch_id: int, queue_id: int) -> dict:
    with _connect() as conn, conn.cursor() as cur:
        # Completion uses the same queue -> batch lock order as claim/failure.
        cur.execute(
            f"SELECT * FROM {_table('operation_projection_queue')} WHERE id=%s FOR UPDATE",
            (int(queue_id),),
        )
        queue_row = cur.fetchone()
        if not queue_row:
            raise LookupError(f"投影队列记录不存在: {queue_id}")
        cur.execute(
            f"SELECT id FROM {_table('operation_batches')} WHERE id=%s FOR UPDATE",
            (int(batch_id),),
        )
        if not cur.fetchone():
            raise LookupError(f"投影批次不存在: {batch_id}")
        now = _now()
        if bool(queue_row.get("dirty")):
            cur.execute(
                f"""
                UPDATE {_table('operation_projection_queue')}
                SET status='queued', dirty=FALSE, available_at=%s,
                    completed_at=NULL, worker_id=NULL, updated_at=%s
                WHERE id=%s RETURNING *
                """,
                (now, now, int(queue_id)),
            )
            updated_queue = dict(cur.fetchone())
            cur.execute(
                f"""
                UPDATE {_table('operation_batches')}
                SET projection_status='queued', projection_updated_at=%s,
                    projection_next_retry_at=NULL, projection_error=NULL
                WHERE id=%s
                """,
                (now, int(batch_id)),
            )
        else:
            cur.execute(
                f"""
                UPDATE {_table('operation_projection_queue')}
                SET status='succeeded', dirty=FALSE, completed_at=%s,
                    worker_id=NULL, updated_at=%s
                WHERE id=%s RETURNING *
                """,
                (now, now, int(queue_id)),
            )
            updated_queue = dict(cur.fetchone())
            cur.execute(
                f"""
                UPDATE {_table('operation_batches')}
                SET projection_status='succeeded', projection_updated_at=%s,
                    projection_next_retry_at=NULL, projection_error=NULL
                WHERE id=%s
                """,
                (now, int(batch_id)),
            )
        return _row(updated_queue) or {}


def _fail_projection(batch_id: int, queue_id: int, error: BaseException) -> dict:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {_table('operation_projection_queue')} WHERE id=%s FOR UPDATE",
            (int(queue_id),),
        )
        queue_row = cur.fetchone()
        if not queue_row:
            raise LookupError(f"投影队列记录不存在: {queue_id}")
        cur.execute(
            f"SELECT id FROM {_table('operation_batches')} WHERE id=%s FOR UPDATE",
            (int(batch_id),),
        )
        if not cur.fetchone():
            raise LookupError(f"投影批次不存在: {batch_id}")
        attempts = int(queue_row.get("attempts") or 1)
        now = _now()
        retry_at = now + timedelta(seconds=_projection_backoff(attempts))
        message = _text(f"{type(error).__name__}: {error}", 1000)
        cur.execute(
            f"""
            UPDATE {_table('operation_projection_queue')}
            SET status='failed', dirty=FALSE, available_at=%s, worker_id=NULL,
                last_error=%s, updated_at=%s
            WHERE id=%s RETURNING *
            """,
            (retry_at, message, now, int(queue_id)),
        )
        updated_queue = dict(cur.fetchone())
        cur.execute(
            f"""
            UPDATE {_table('operation_batches')}
            SET projection_status='failed', projection_updated_at=%s,
                projection_next_retry_at=%s, projection_error=%s
            WHERE id=%s
            """,
            (now, retry_at, message, int(batch_id)),
        )
        return _row(updated_queue) or {}


def _compat_registration_event_detail(event: dict) -> tuple[str, str, dict, str | None, str | None]:
    raw_detail = _decode(event.get("detail"))
    detail = dict(raw_detail) if isinstance(raw_detail, dict) else {}
    event_type = str(event.get("event_type") or "checkpoint")[:120]
    level = str(event.get("level") or "INFO").upper()
    stage = str(detail.get("stage") or detail.get("current_stage") or event.get("checkpoint") or "event")
    # D's fields are additive compatibility keys inside the existing detail JSONB.
    compatibility = {
        "stage": stage,
        "state_before": detail.get("state_before"),
        "state_after": detail.get("state_after"),
        "duration_ms": detail.get("duration_ms"),
        "wait_reason": detail.get("wait_reason"),
        "error": detail.get("error"),
    }
    detail.update(compatibility)
    error_value = compatibility["error"]
    if isinstance(error_value, dict):
        error_value = error_value.get("message") or error_value.get("code") or str(error_value)
    error_value = str(error_value or "").strip() or (str(event.get("message") or "").strip() if level == "ERROR" else "")
    return normalize_stage(stage), event_type, detail, error_value or None, level


def _project_registration_fact_events(cur, batch_id: int) -> int:
    """Project B facts for one registration batch; absent tables are tolerated."""
    source_system = ""
    source_id = ""
    cur.execute(
        f"SELECT source_system, source_id FROM {_table('operation_batches')} WHERE id=%s",
        (int(batch_id),),
    )
    batch = cur.fetchone()
    if not batch or str(batch.get("source_system") or "") != "registration_batches":
        return 0
    source_id = str(batch.get("source_id") or "")
    cur.execute("SELECT to_regclass(%s) AS name", (f"{_schema_name()}.registration_events",))
    if not cur.fetchone()["name"]:
        return 0
    # B's tables are read-only inputs here.  The legacy batch_id remains the
    # only selector, so unrelated batches are never scanned or updated.
    cur.execute(
        f"""
        SELECT e.*, rr.job_id AS run_job_id
        FROM {_table('registration_events')} e
        LEFT JOIN {_table('registration_runs')} rr ON rr.id=e.run_id
        LEFT JOIN {_table('registration_attempts')} a ON a.id=e.attempt_id
        LEFT JOIN {_table('registration_jobs')} direct_job
          ON direct_job.id=COALESCE(e.job_id, rr.job_id)
        LEFT JOIN {_table('registration_jobs')} root_job
          ON root_job.id=COALESCE(a.root_job_id, a.source_root_job_id)
        WHERE COALESCE(direct_job.batch_id, root_job.batch_id)=%s
        ORDER BY e.created_at, e.id
        """,
        (source_id,),
    )
    projected = 0
    for raw in cur.fetchall():
        event = dict(raw)
        cur.execute(
            f"""
            SELECT t.id, t.last_run_id
            FROM {_table('operation_tasks')} t
            WHERE t.attempt_id=%s
            ORDER BY CASE WHEN t.task_type='registration' THEN 0 ELSE 1 END, t.id DESC
            LIMIT 1
            """,
            (int(event["attempt_id"]),),
        )
        task = cur.fetchone()
        if not task:
            continue
        event_run_id = None
        job_id = event.get("job_id") or event.get("run_job_id")
        if job_id is not None:
            cur.execute(
                f"SELECT id FROM {_table('operation_runs')} WHERE source_system='registration_jobs' AND source_id=%s ORDER BY id DESC LIMIT 1",
                (str(job_id),),
            )
            operation_run = cur.fetchone()
            event_run_id = int(operation_run["id"]) if operation_run else None
        event_run_id = event_run_id or (int(task["last_run_id"]) if task.get("last_run_id") else None)
        stage, event_type, detail, error, level = _compat_registration_event_detail(event)
        category, code, _ = _error_fields(error, stage=stage, task_type="registration")
        source_event_id = str(event.get("event_uuid") or event.get("id"))
        cur.execute(
            f"""
            INSERT INTO {_table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id, created_at, level,
                stage, event_type, error_category, error_code, message, detail
            ) VALUES (%s,%s,%s,'registration_events',%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (source_system, source_id) DO UPDATE SET
                task_id=EXCLUDED.task_id, run_id=EXCLUDED.run_id, created_at=EXCLUDED.created_at,
                level=EXCLUDED.level, stage=EXCLUDED.stage, event_type=EXCLUDED.event_type,
                error_category=EXCLUDED.error_category, error_code=EXCLUDED.error_code,
                message=EXCLUDED.message, detail=EXCLUDED.detail
            """,
            (
                _uuid("event", f"registration_events:{source_event_id}"), int(task["id"]), event_run_id,
                source_event_id, event.get("created_at") or _now(), level, stage, event_type,
                category, code, _text(event.get("message") or error or event_type, 1600), _json(detail),
            ),
        )
        projected += 1
    return projected


def _repair_terminal_task_projection(cur, batch_id: int) -> int:
    """收口已有终态 Run 对应的卡住任务，只修改统一投影表。"""
    terminal_statuses = tuple(sorted(_TERMINAL_STATUSES))
    placeholders = ", ".join("%s" for _ in terminal_statuses)
    cur.execute("SELECT to_regclass(%s) AS name", (f"{_schema_name()}.registration_runs",))
    if cur.fetchone()["name"]:
        fact_statuses = (
            "success", "partial_success", "failed", "stopped", "cancelled", "interrupted",
            "request_unknown", "manual_reconcile",
        )
        fact_placeholders = ", ".join("%s" for _ in fact_statuses)
        cur.execute(
            f"""
            WITH latest_fact AS (
                SELECT DISTINCT ON (task.id)
                       task.id AS task_id, run.id AS operation_run_id,
                       rr.status AS fact_status, rr.completed_at AS fact_completed_at,
                       rr.error_message AS fact_error_message
                FROM {_table('operation_tasks')} task
                JOIN {_table('registration_runs')} rr ON rr.attempt_id=task.attempt_id
                JOIN {_table('operation_runs')} run ON run.task_id=task.id
                WHERE task.batch_id=%s
                  AND rr.status IN ({fact_placeholders})
                ORDER BY task.id, rr.run_no DESC, rr.id DESC, run.run_no DESC, run.id DESC
            )
            UPDATE {_table('operation_runs')} run
            SET status=CASE latest_fact.fact_status
                           WHEN 'request_unknown' THEN 'attention_required'
                           WHEN 'manual_reconcile' THEN 'attention_required'
                           ELSE latest_fact.fact_status END,
                completed_at=COALESCE(run.completed_at, latest_fact.fact_completed_at, now()),
                error_message=COALESCE(run.error_message, latest_fact.fact_error_message), heartbeat_at=now()
            FROM latest_fact
            WHERE run.id=latest_fact.operation_run_id
              AND run.status IN ('queued','running','cancelling','settling')
            """,
            (int(batch_id), *fact_statuses),
        )
    cur.execute(
        f"""
        WITH latest AS (
            SELECT DISTINCT ON (run.task_id)
                   run.task_id, run.status, run.completed_at, run.error_message
            FROM {_table('operation_runs')} run
            JOIN {_table('operation_tasks')} task ON task.id=run.task_id
            WHERE task.batch_id=%s
            ORDER BY run.task_id, run.run_no DESC, run.id DESC
        )
        UPDATE {_table('operation_tasks')} task
        SET status=latest.status, current_stage='complete',
            completed_at=COALESCE(task.completed_at, latest.completed_at),
            error_message=COALESCE(task.error_message, latest.error_message), updated_at=now()
        FROM latest
        WHERE task.id=latest.task_id
          AND latest.status IN ({placeholders})
          AND task.status IN ('queued','running','stopping','cancelling','settling','waiting')
        RETURNING task.id
        """,
        (int(batch_id), *terminal_statuses),
    )
    return len(cur.fetchall())


def _project_claimed_batch(claimed: dict) -> None:
    batch_id = int(claimed["batch_id"])
    if str(claimed.get("batch_source_system") or "") == "registration_batches":
        try:
            from core.storage import registration

            registration.init()
        except Exception:
            # A deployment may still be on the legacy schema; refresh counts
            # anyway and let the queue retry when the additive tables appear.
            logger.debug("注册事实表尚未就绪，跳过事实事件投影", exc_info=True)
    with _connect() as conn, conn.cursor() as cur:
        _repair_terminal_task_projection(cur, batch_id)
        _project_registration_fact_events(cur, batch_id)
        _refresh_batches(cur, [batch_id])


def run_projection_once(*, worker_id: str | None = None) -> dict | None:
    """Claim, project and settle one batch; projection errors are durable."""
    claimed = claim_projection(worker_id=worker_id)
    if not claimed:
        return None
    batch_id = int(claimed["batch_id"])
    queue_id = int(claimed["id"])
    try:
        _project_claimed_batch(claimed)
    except Exception as exc:
        logger.exception("统一任务中心批次投影失败：batch_id=%s", batch_id)
        return _fail_projection(batch_id, queue_id, exc)
    return _complete_projection(batch_id, queue_id)


def drain_projection_queue(*, limit: int = 100, worker_id: str | None = None) -> list[dict]:
    results: list[dict] = []
    for _ in range(max(0, min(5000, int(limit or 100)))):
        result = run_projection_once(worker_id=worker_id)
        if result is None:
            break
        results.append(result)
    return results


def _projection_worker_loop(interval_seconds: float) -> None:
    identifier = f"projection-{os.getpid()}-{threading.get_ident()}"
    while not _PROJECTION_STOP.is_set():
        try:
            if run_projection_once(worker_id=identifier) is None:
                _PROJECTION_WAKE.wait(max(0.05, float(interval_seconds)))
                _PROJECTION_WAKE.clear()
        except Exception:
            logger.exception("统一任务中心投影 worker 轮询失败")
            _PROJECTION_STOP.wait(max(0.1, float(interval_seconds)))


def start_projection_worker(*, interval_seconds: float = 1.0) -> bool:
    global _PROJECTION_WORKER
    with _PROJECTION_WORKER_LOCK:
        if _PROJECTION_WORKER is not None and _PROJECTION_WORKER.is_alive():
            return False
        _PROJECTION_STOP.clear()
        _PROJECTION_WAKE.clear()
        _PROJECTION_WORKER = threading.Thread(
            target=_projection_worker_loop,
            args=(max(0.05, float(interval_seconds)),),
            name="operation-projection",
            daemon=True,
        )
        _PROJECTION_WORKER.start()
        return True


def stop_projection_worker(*, timeout: float = 2.0) -> bool:
    global _PROJECTION_WORKER
    with _PROJECTION_WORKER_LOCK:
        worker = _PROJECTION_WORKER
        if worker is None:
            return False
        _PROJECTION_STOP.set()
        _PROJECTION_WAKE.set()
    worker.join(max(0.05, float(timeout)))
    with _PROJECTION_WORKER_LOCK:
        if _PROJECTION_WORKER is worker:
            _PROJECTION_WORKER = None
    return True


def projection_worker_status() -> dict[str, object]:
    """Return process-local projection worker state for readiness checks.

    This deliberately does not query PostgreSQL or expose queue payloads.  A
    health endpoint can combine this liveness signal with its own database
    check without making the status function mutate storage.
    """
    with _PROJECTION_WORKER_LOCK:
        worker = _PROJECTION_WORKER
        return {
            "started": worker is not None,
            "alive": bool(worker and worker.is_alive()),
            "name": worker.name if worker is not None else None,
        }


def reconcile_all() -> dict[str, int]:
    """从两套旧表幂等回填统一模型；不会删除旧数据，也不会改账号业务字段。"""
    init()
    record_store.init()
    with _LOCK, _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {postgres_store.qualified('registered_accounts')} ORDER BY id")
        accounts = [record_store.merge_row(record_store.ACCOUNTS, dict(row)) or {} for row in cur.fetchall()]
        accounts_by_id = {int(row["id"]): row for row in accounts if row.get("id") is not None}
        accounts_by_email = {
            str(row.get("email") or "").strip().lower(): row for row in accounts if str(row.get("email") or "").strip()
        }
        cur.execute(f"SELECT * FROM {postgres_store.qualified('registration_jobs')} ORDER BY id")
        jobs = [record_store.merge_row(record_store.JOBS, dict(row)) or {} for row in cur.fetchall()]
        for job in jobs:
            _upsert_registration_job(cur, job, accounts_by_id, accounts_by_email)

        cur.execute(f"SELECT * FROM {_table('account_action_batches')} ORDER BY created_at, id")
        account_batches = [dict(row) for row in cur.fetchall()]
        batch_map = {str(row["id"]): _upsert_account_batch(cur, row) for row in account_batches}
        cur.execute(f"SELECT * FROM {_table('account_action_tasks')} ORDER BY id")
        account_tasks = [dict(row) for row in cur.fetchall()]
        task_map = {
            int(row["id"]): _upsert_account_task(cur, row, batch_map, accounts_by_id)
            for row in account_tasks
        }
        cur.execute(f"SELECT * FROM {_table('account_action_events')} ORDER BY id")
        account_events = [dict(row) for row in cur.fetchall()]
        for event in account_events:
            _upsert_account_event(cur, event, task_map)
        _refresh_batches(cur)
        return {
            "registration_jobs": len(jobs),
            "account_action_batches": len(account_batches),
            "account_action_tasks": len(account_tasks),
            "account_action_events": len(account_events),
        }


def repair_stale_compatibility_projections(*, limit: int = 500) -> int:
    """收口旧任务已结束、统一执行实例仍显示活动的投影。"""
    init()
    record_store.init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT run.source_system, run.source_id
            FROM {_table('operation_runs')} run
            LEFT JOIN {_table('account_action_tasks')} account_task
              ON run.source_system='account_action_tasks'
             AND account_task.id::text=run.source_id
            LEFT JOIN {postgres_store.qualified(record_store.JOBS.name)} registration_job
              ON run.source_system='registration_jobs'
             AND registration_job.id::text=run.source_id
            WHERE run.status IN ({_ACTIVE_RUN_STATUS_SQL})
              AND (
                    (run.source_system='account_action_tasks'
                     AND account_task.id IS NOT NULL
                     AND account_task.status NOT IN ('queued','running'))
                 OR (run.source_system='registration_jobs'
                     AND registration_job.id IS NOT NULL
                     AND registration_job.status NOT IN ('pending','queued','running','cancelling','settling','stopping'))
              )
            ORDER BY run.source_system, run.source_id
            LIMIT %s
            """,
            (max(1, min(5000, int(limit or 500))),),
        )
        stale = [(str(row["source_system"]), str(row["source_id"])) for row in cur.fetchall()]

    repaired = 0
    for source_system, source_id in stale:
        try:
            if source_system == "account_action_tasks":
                sync_account_task(int(source_id))
            elif source_system == "registration_jobs":
                sync_registration_job(int(source_id))
            else:
                continue
            repaired += 1
        except Exception:
            logger.exception(
                "收口兼容任务投影失败：source_system=%s source_id=%s",
                source_system,
                source_id,
            )
    return repaired


def sync_registration_job(job_id: int) -> None:
    """同步一条注册执行。调用方可在每次旧表更新后调用，失败应显式暴露。"""
    init()
    record_store.init()
    job = record_store.get_row(record_store.JOBS, int(job_id))
    if not job:
        mark_registration_jobs_deleted([int(job_id)])
        return
    account = None
    if job.get("account_id") is not None:
        account = record_store.get_row(record_store.ACCOUNTS, int(job["account_id"]))
    if account is None and job.get("email"):
        rows = record_store.list_rows(
            record_store.ACCOUNTS,
            where="lower(email)=lower(%s)", params=(str(job["email"]),), order_by="id DESC", limit=1,
        )
        account = rows[0] if rows else None
    accounts_by_id = {int(account["id"]): account} if account and account.get("id") is not None else {}
    accounts_by_email = {
        str(account.get("email") or "").strip().lower(): account
    } if account else {}

    def _write_once():
        with _connect() as conn, conn.cursor() as cur:
            legacy_batch_id = str(job.get("batch_id") or "").strip()
            if legacy_batch_id:
                cur.execute(
                    f"SELECT id FROM {_table('operation_batches')} "
                    "WHERE source_system='registration_batches' AND source_id=%s",
                    (legacy_batch_id,),
                )
                existing_batch = cur.fetchone()
                if existing_batch:
                    _lock_existing_projection_queue(cur, int(existing_batch["id"]))
            operation_task_id = _upsert_registration_job(cur, job, accounts_by_id, accounts_by_email)
            cur.execute(
                f"SELECT batch_id FROM {_table('operation_tasks')} WHERE id=%s",
                (int(operation_task_id),),
            )
            projected = cur.fetchone()
            if projected and projected.get("batch_id"):
                _enqueue_batch_projection_cur(
                    cur,
                    int(projected["batch_id"]),
                    reason="registration_job_updated",
                    source_system="registration_jobs",
                    source_id=str(job_id),
                )

    _run_projection_write_with_retry(_write_once, operation_name=f"registration_job:{job_id}")


def sync_account_task(task_id: int) -> None:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table('account_action_tasks')} WHERE id=%s", (int(task_id),))
        task = cur.fetchone()
        if not task:
            return
        batch_map: dict[str, int] = {}
        if task.get("batch_id"):
            cur.execute(
                f"SELECT * FROM {_table('account_action_batches')} WHERE id=%s",
                (str(task["batch_id"]),),
            )
            batch = cur.fetchone()
            if batch:
                cur.execute(
                    f"SELECT id FROM {_table('operation_batches')} "
                    "WHERE source_system='account_action_batches' AND source_id=%s",
                    (str(task["batch_id"]),),
                )
                existing_batch = cur.fetchone()
                if existing_batch:
                    _lock_existing_projection_queue(cur, int(existing_batch["id"]))
                batch_map[str(task["batch_id"])] = _upsert_account_batch(cur, dict(batch))
        accounts_by_id: dict[int, dict] = {}
        if task.get("account_id") is not None:
            cur.execute(
                f"SELECT * FROM {postgres_store.qualified('registered_accounts')} WHERE id=%s",
                (int(task["account_id"]),),
            )
            raw_account = cur.fetchone()
            if raw_account:
                account = record_store.merge_row(record_store.ACCOUNTS, dict(raw_account)) or {}
                accounts_by_id[int(account["id"])] = account
        operation_task_id = _upsert_account_task(cur, dict(task), batch_map, accounts_by_id)
        cur.execute(f"SELECT * FROM {_table('account_action_events')} WHERE task_id=%s ORDER BY id", (int(task_id),))
        task_map = {int(task_id): operation_task_id}
        for event in cur.fetchall():
            _upsert_account_event(cur, dict(event), task_map)
        if task.get("batch_id") and batch_map.get(str(task["batch_id"])):
            _enqueue_batch_projection_cur(
                cur,
                batch_map[str(task["batch_id"])],
                reason="account_task_updated",
                source_system="account_action_tasks",
                source_id=str(task_id),
            )


def mark_registration_jobs_deleted(job_ids: Iterable[int]) -> None:
    ids = [str(int(value)) for value in job_ids]
    if not ids:
        return
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')} SET data=data || '{{"source_deleted":true}}'::jsonb
            WHERE source_system='registration_jobs' AND source_id = ANY(%s)
            """,
            (ids,),
        )


def list_batches(*, limit: int = 50) -> list[dict]:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT b.*, q.status AS projection_queue_status,
                   q.attempts AS projection_queue_attempts,
                   CASE WHEN q.status='failed' THEN q.available_at ELSE NULL END AS projection_queue_next_retry_at,
                   q.last_error AS projection_queue_error,
                   CASE WHEN q.requested_at IS NULL THEN NULL
                        ELSE GREATEST(0, EXTRACT(EPOCH FROM (COALESCE(q.completed_at, now()) - q.requested_at)) * 1000)::BIGINT
                   END AS projection_lag_ms
            FROM {_table('operation_batches')} b
            LEFT JOIN {_table('operation_projection_queue')} q ON q.batch_id=b.id
            ORDER BY b.created_at DESC, b.id DESC LIMIT %s
            """,
            (max(1, min(200, int(limit or 50))),),
        )
        batches = []
        for raw in cur.fetchall():
            batch = _row(dict(raw)) or {}
            projection_status = str(batch.get("projection_status") or "synced")
            batch["projection_delayed"] = projection_status not in {"synced", "succeeded"}
            batches.append(batch)
        return batches


def _operation_task_where(
    *, task_type: str = "", status: str = "", source: str = "", q: str = "",
    batch_id: int | None = None, task_id: str = "", target: str = "",
    target_status: str = "", batch: str = "", run_count: str = "",
    stage: str = "", created_from: str = "", created_to: str = "", result: str = "",
    exclude: str = "",
) -> tuple[list[str], list[Any]]:
    """Build the shared task-list predicate, optionally leaving one facet unfiltered."""
    where: list[str] = []
    params: list[Any] = []

    def add(name: str, expression: str, *values: Any) -> None:
        if exclude != name:
            where.append(expression)
            params.extend(values)

    add("task_type", "t.task_type=%s", str(task_type)) if task_type else None
    # ``r`` is the current run selected by the list query below.  Filtering on
    # it keeps a logical task out of terminal facets while a retry is active.
    add("status", "COALESCE(r.effective_status, t.status)=%s", str(status)) if status else None
    add("source", "t.source_system=%s", str(source)) if source else None
    add("batch_id", "t.batch_id=%s", int(batch_id)) if batch_id else None

    if q:
        needle = f"%{str(q).strip()}%"
        add(
            "q",
            "("
            "t.email_snapshot ILIKE %s OR CAST(t.account_id AS TEXT) ILIKE %s "
            "OR CAST(t.attempt_id AS TEXT) ILIKE %s OR CAST(t.target_id AS TEXT) ILIKE %s "
            "OR CAST(t.id AS TEXT) ILIKE %s OR COALESCE(t.error_message, '') ILIKE %s "
            "OR COALESCE(b.title, '') ILIKE %s OR COALESCE(t.trigger, '') ILIKE %s "
            "OR COALESCE(r.effective_error_message, '') ILIKE %s "
            "OR COALESCE(r.result_summary::text, '') ILIKE %s"
            ")",
            needle, needle, needle, needle, needle, needle, needle, needle, needle, needle,
        )
    if task_id:
        value = str(task_id).strip().lstrip("#")
        add("task_id", "CAST(t.id AS TEXT) ILIKE %s", f"%{value}%") if value else None
    if target:
        needle = f"%{str(target).strip()}%"
        add(
            "target",
            "("
            "COALESCE(t.email_snapshot, '') ILIKE %s OR CAST(t.account_id AS TEXT) ILIKE %s "
            "OR CAST(t.attempt_id AS TEXT) ILIKE %s OR CAST(t.target_id AS TEXT) ILIKE %s"
            ")",
            needle, needle, needle, needle,
        )
    if target_status:
        add("target_status", "t.target_status=%s", str(target_status))
    if batch:
        needle = f"%{str(batch).strip()}%"
        add(
            "batch",
            "(COALESCE(b.title, '') ILIKE %s OR COALESCE(b.batch_uuid, '') ILIKE %s OR COALESCE(t.trigger, '') ILIKE %s)",
            needle, needle, needle,
        )
    if run_count:
        value = str(run_count).strip().lower()
        run_count_expr = f"(SELECT COUNT(*) FROM {_table('operation_runs')} rr WHERE rr.task_id=t.id)"
        if value in {"4+", "4plus", "4_plus"}:
            add("run_count", f"{run_count_expr} >= %s", 4)
        elif value.isdigit():
            add("run_count", f"{run_count_expr} = %s", int(value))
    if stage:
        add(
            "stage",
            "LOWER(COALESCE(r.effective_progress_stage, CASE WHEN r.effective_status='queued' THEN 'queued' ELSE t.current_stage END, ''))=%s",
            str(stage).lower(),
        )
    if created_from:
        add("created_from", "t.created_at::date >= %s", str(created_from)[:10])
    if created_to:
        add("created_to", "t.created_at::date <= %s", str(created_to)[:10])
    if result:
        needle = f"%{str(result).strip()}%"
        add(
            "result",
            "(COALESCE(t.error_message, '') ILIKE %s OR COALESCE(r.effective_error_message, '') ILIKE %s "
            "OR COALESCE(r.result_summary::text, '') ILIKE %s)",
            needle, needle, needle,
        )
    return where, params


def list_tasks(
    *, page: int = 1, page_size: int = 50, task_type: str = "", status: str = "",
    source: str = "", q: str = "", batch_id: int | None = None, task_id: str = "",
    target: str = "", target_status: str = "", batch: str = "", run_count: str = "",
    stage: str = "", created_from: str = "", created_to: str = "", result: str = "",
) -> dict:
    init()
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))
    where, params = _operation_task_where(
        task_type=task_type, status=status, source=source, q=q, batch_id=batch_id,
        task_id=task_id, target=target, target_status=target_status, batch=batch,
        run_count=run_count, stage=stage, created_from=created_from,
        created_to=created_to, result=result,
    )
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    from_sql = (
        f"FROM {_table('operation_tasks')} t "
        f"LEFT JOIN {_table('operation_batches')} b ON b.id=t.batch_id "
        f"LEFT JOIN LATERAL ("
        f"SELECT current_run.* FROM ("
        f"SELECT rr.*, {_compatibility_run_projection_sql()} "
        f"FROM {_table('operation_runs')} rr {_compatibility_run_joins_sql()} "
        f"WHERE rr.task_id=t.id"
        f") current_run "
        f"ORDER BY CASE WHEN current_run.effective_status IN ({_ACTIVE_RUN_STATUS_SQL}) THEN 0 ELSE 1 END, "
        f"current_run.run_no DESC, current_run.id DESC LIMIT 1"
        f") r ON TRUE"
    )
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n {from_sql}{clause}", params)
        total = int(cur.fetchone()["n"])
        cur.execute(
            f"""
            SELECT t.*, b.batch_uuid, b.title AS batch_title, b.batch_type,
                   r.id AS __current_run_id, r.effective_status AS __current_run_status,
                   r.effective_progress_stage AS __current_run_stage,
                   r.effective_created_at AS __current_run_created_at,
                   r.effective_completed_at AS __current_run_completed_at,
                   r.error_category AS __current_run_error_category,
                   r.error_code AS __current_run_error_code,
                   r.effective_error_message AS __current_run_error_message,
                   r.run_no AS last_run_no, r.duration_ms, r.result_summary,
                   r.source_system AS run_source_system, r.source_id AS run_source_id,
                   (SELECT COUNT(*) FROM {_table('operation_runs')} rr WHERE rr.task_id=t.id) AS run_count
            {from_sql}
            {clause}
            ORDER BY COALESCE(r.effective_created_at_sort, t.created_at) DESC, t.id DESC LIMIT %s OFFSET %s
            """,
            (*params, page_size, (page - 1) * page_size),
        )
        items = []
        for raw_row in cur.fetchall():
            item = _row(dict(raw_row)) or {}
            current_run = {
                "id": item.pop("__current_run_id", None),
                "source_system": item.pop("run_source_system", None),
                "source_id": item.pop("run_source_id", None),
                "status": item.pop("__current_run_status", None),
                "progress_stage": item.pop("__current_run_stage", None),
                "effective_created_at": item.pop("__current_run_created_at", None),
                "effective_completed_at": item.pop("__current_run_completed_at", None),
                "error_category": item.pop("__current_run_error_category", None),
                "error_code": item.pop("__current_run_error_code", None),
                "error_message": item.pop("__current_run_error_message", None),
            }
            if current_run["id"] is not None:
                current_run = _normalize_compatibility_run(current_run)
                _apply_current_run_projection(item, current_run)
            items.append(item)
        facet_specs = (
            ("task_type", "t.task_type", "task_type"),
            ("status", "COALESCE(r.effective_status, t.status)", "status"),
            ("target_status", "t.target_status", "target_status"),
            (
                "stage",
                "LOWER(COALESCE(r.effective_progress_stage, CASE WHEN r.effective_status='queued' THEN 'queued' ELSE t.current_stage END, ''))",
                "stage",
            ),
            (
                "run_count",
                f"CASE WHEN (SELECT COUNT(*) FROM {_table('operation_runs')} rr WHERE rr.task_id=t.id) >= 4 "
                f"THEN '4+' ELSE CAST((SELECT COUNT(*) FROM {_table('operation_runs')} rr WHERE rr.task_id=t.id) AS TEXT) END",
                "run_count",
            ),
        )
        facets: dict[str, list[dict[str, Any]]] = {}
        for facet_name, expression, exclude in facet_specs:
            facet_where, facet_params = _operation_task_where(
                task_type=task_type, status=status, source=source, q=q, batch_id=batch_id,
                task_id=task_id, target=target, target_status=target_status, batch=batch,
                run_count=run_count, stage=stage, created_from=created_from,
                created_to=created_to, result=result, exclude=exclude,
            )
            facet_where.append(f"NULLIF({expression}, '') IS NOT NULL")
            facet_clause = f" WHERE {' AND '.join(facet_where)}"
            cur.execute(
                f"SELECT {facet_name!r} AS facet, {expression} AS value, COUNT(*) AS count "
                f"{from_sql}{facet_clause} GROUP BY 2 ORDER BY 2",
                facet_params,
            )
            facets[facet_name] = [
                {"value": str(row["value"] or ""), "count": int(row["count"] or 0)}
                for row in cur.fetchall()
            ]
    return {"ok": True, "items": items, "total": total, "page": page, "page_size": page_size, "facets": facets}


def get_task(task_id: int, *, include_events: bool = True) -> dict | None:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.*, b.batch_uuid, b.title AS batch_title, b.batch_type
            FROM {_table('operation_tasks')} t
            LEFT JOIN {_table('operation_batches')} b ON b.id=t.batch_id
            WHERE t.id=%s
            """,
            (int(task_id),),
        )
        task = cur.fetchone()
        if not task:
            return None
        cur.execute(
            f"SELECT rr.*, {_compatibility_run_projection_sql()} "
            f"FROM {_table('operation_runs')} rr {_compatibility_run_joins_sql()} "
            f"WHERE rr.task_id=%s ORDER BY rr.run_no, rr.id",
            (int(task_id),),
        )
        runs = [_normalize_compatibility_run(_row(dict(row)) or {}) for row in cur.fetchall()]
        events: list[dict] = []
        if include_events:
            cur.execute(
                f"""
                SELECT e.*, r.run_no
                FROM {_table('operation_events')} e
                LEFT JOIN {_table('operation_runs')} r ON r.id=e.run_id
                WHERE e.task_id=%s ORDER BY e.created_at, e.id
                """,
                (int(task_id),),
            )
            events = [_read_event(dict(row)) for row in cur.fetchall()]
        cur.execute(
            f"""
            SELECT resource.*
            FROM {_table('operation_resources')} resource
            JOIN {_table('operation_runs')} run ON run.id=resource.run_id
            WHERE run.task_id=%s ORDER BY resource.acquired_at, resource.id
            """,
            (int(task_id),),
        )
        resources = [_row(dict(row)) or {} for row in cur.fetchall()]
        attempt = None
        if task.get("attempt_id"):
            cur.execute(f"SELECT * FROM {_table('registration_attempts')} WHERE id=%s", (int(task["attempt_id"]),))
            raw_attempt = cur.fetchone()
            attempt = _row(dict(raw_attempt)) if raw_attempt else None
        parent = None
        if task.get("parent_task_id"):
            cur.execute(
                f"SELECT id, task_uuid, task_type, status, target_status FROM {_table('operation_tasks')} WHERE id=%s",
                (int(task["parent_task_id"]),),
            )
            raw_parent = cur.fetchone()
            parent = _row(dict(raw_parent)) if raw_parent else None
    result = _row(dict(task)) or {}
    _apply_current_run_projection(result, _select_current_run(runs))
    result.update({
        "runs": runs,
        "events": events,
        "resources": resources,
        "attempt": attempt,
        "parent": parent,
        "flow": flow_for(result.get("task_type")),
    })
    return result


def get_run_progress(task_id: int, run_id: int) -> dict:
    """Build progress from the complete selected Run, independent of event pages."""
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT id, task_type FROM {_table('operation_tasks')} WHERE id=%s",
            (int(task_id),),
        )
        task = cur.fetchone()
        if not task:
            raise LookupError("任务不存在")
        cur.execute(
            f"SELECT rr.*, {_compatibility_run_projection_sql()} "
            f"FROM {_table('operation_runs')} rr {_compatibility_run_joins_sql()} "
            f"WHERE rr.id=%s AND rr.task_id=%s",
            (int(run_id), int(task_id)),
        )
        run_row = cur.fetchone()
        if not run_row:
            raise LookupError("执行实例不存在")
        cur.execute(
            f"""
            SELECT e.*, r.run_no
            FROM {_table('operation_events')} e
            LEFT JOIN {_table('operation_runs')} r ON r.id=e.run_id
            WHERE e.task_id=%s AND e.run_id=%s
            ORDER BY e.created_at, e.id
            """,
            (int(task_id), int(run_id)),
        )
        events = [_read_event(dict(row)) for row in cur.fetchall()]
    run = _normalize_compatibility_run(_row(dict(run_row)) or {})
    return build_progress_snapshot(
        int(task["id"]),
        int(run["id"]),
        str(task["task_type"] or ""),
        run,
        events,
    )


def list_task_events(
    task_id: int,
    *,
    run_id: int | None = None,
    after_id: int | None = None,
    limit: int = 200,
) -> dict:
    """Return one bounded event page; omitted ``after_id`` means latest page."""
    init()
    page_size = max(1, min(1000, int(limit or 200)))
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {_table('operation_tasks')} WHERE id=%s", (int(task_id),))
        if not cur.fetchone():
            raise LookupError("任务不存在")
        params: list[Any] = [int(task_id)]
        where = ["e.task_id=%s"]
        if run_id is not None:
            where.append("e.run_id=%s")
            params.append(int(run_id))
        if after_id is not None:
            where.append("e.id>%s")
            params.append(max(0, int(after_id)))
            order = "e.id ASC"
        else:
            order = "e.id DESC"
        cur.execute(
            f"""
            SELECT e.*, r.run_no
            FROM {_table('operation_events')} e
            LEFT JOIN {_table('operation_runs')} r ON r.id=e.run_id
            WHERE {' AND '.join(where)}
            ORDER BY {order}
            LIMIT %s
            """,
            (*params, page_size + 1),
        )
        rows = list(cur.fetchall())
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    if after_id is None:
        rows.reverse()
    items = [_read_event(dict(row)) for row in rows]
    return {
        "items": items,
        "next_after_id": max([int(item["id"]) for item in items] or [int(after_id or 0)]),
        "has_more": has_more,
    }


def read_task_run_log(
    task_id: int,
    run_id: int,
    *,
    cursor: int | None = None,
    limit: int = 500,
) -> dict:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT log_file, status FROM {_table('operation_runs')} WHERE id=%s AND task_id=%s",
            (int(run_id), int(task_id)),
        )
        run = cur.fetchone()
        if not run:
            raise LookupError("执行实例不存在")
    result = task_run_log.read_incremental(run.get("log_file"), cursor=cursor, limit=limit)
    result["run_terminal"] = str(run.get("status") or "") in _TERMINAL_STATUSES
    return result


def find_task_by_source(source_system: str, source_id: str) -> dict | None:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {_table('operation_tasks')} WHERE source_system=%s AND source_id=%s",
            (str(source_system), str(source_id)),
        )
        raw = cur.fetchone()
        return _row(dict(raw)) if raw else None


# ============================================================
# 跨兼容模型的持久依赖
# ============================================================

def register_task_dependency(
    *,
    parent_source_system: str,
    parent_source_id: str,
    child_source_system: str,
    child_source_id: str,
    dependency_type: str,
    payload: dict | None = None,
) -> dict:
    """Persist a parent/child handoff without coupling two ID namespaces.

    During the migration window a completion coordinator may still be a
    legacy ``account_action_tasks`` row while its Codex child is a native
    operation.  The dependency table is intentionally source-keyed instead
    of using a misleading cross-table foreign key.  Repeating the registration
    is idempotent and never resets an already-ready/completed child.
    """
    init()
    parent_system = _text(parent_source_system, 120)
    parent_id = _text(parent_source_id, 240)
    child_system = _text(child_source_system, 120)
    child_id = _text(child_source_id, 240)
    dependency = _text(dependency_type, 120)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {_table('operation_task_dependencies')} (
                parent_source_system, parent_source_id, child_source_system,
                child_source_id, dependency_type, payload
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (
                parent_source_system, parent_source_id, child_source_system,
                child_source_id, dependency_type
            ) DO UPDATE SET
                payload=EXCLUDED.payload,
                updated_at=now()
            RETURNING *
            """,
            (parent_system, parent_id, child_system, child_id, dependency, _json(payload or {})),
        )
        row = dict(cur.fetchone())
        # A fast child can reach a terminal state before the parent finishes
        # recording this handoff. Resolve that race at registration time so a
        # completed child never leaves a permanent ``waiting`` dependency.
        child = None
        try:
            child_number = int(child_id)
        except (TypeError, ValueError):
            child_number = None
        if child_system == "native_operations" and child_number is not None:
            cur.execute(
                f"""
                SELECT t.status AS task_status, r.status AS run_status,
                       r.result_summary
                FROM {_table('operation_tasks')} t
                LEFT JOIN {_table('operation_runs')} r ON r.id=t.last_run_id
                WHERE t.id=%s
                """,
                (child_number,),
            )
            child = cur.fetchone()
        elif child_system == "account_action_tasks" and child_number is not None:
            cur.execute(
                f"SELECT status, result_summary FROM {_table('account_action_tasks')} WHERE id=%s",
                (child_number,),
            )
            child = cur.fetchone()
        else:
            cur.execute(
                f"""
                SELECT t.status AS task_status, r.status AS run_status,
                       r.result_summary
                FROM {_table('operation_tasks')} t
                LEFT JOIN {_table('operation_runs')} r ON r.id=t.last_run_id
                WHERE t.source_system=%s AND t.source_id=%s
                """,
                (child_system, child_id),
            )
            child = cur.fetchone()
        if child:
            child_status = _status(child.get("run_status") or child.get("task_status") or child.get("status"))
            if child_status in _TERMINAL_STATUSES and str(row.get("status") or "") == "waiting":
                cur.execute(
                    f"""
                    UPDATE {_table('operation_task_dependencies')}
                    SET status='ready', child_status=%s, child_result=%s::jsonb,
                        ready_at=now(), next_attempt_at=NULL, updated_at=now()
                    WHERE id=%s AND status='waiting'
                    RETURNING *
                    """,
                    (
                        child_status,
                        _json(_decode(child.get("result_summary")) or {}),
                        int(row["id"]),
                    ),
                )
                row = dict(cur.fetchone() or row)
        return _row(row) or {}


def mark_task_dependency_ready(
    *,
    child_source_system: str,
    child_source_id: str,
    child_status: str,
    child_result: dict | None = None,
) -> list[dict]:
    """Make all waiting parents recoverably ready after a child reaches a terminal state."""
    init()
    status_value = _status(child_status)
    if status_value not in _TERMINAL_STATUSES:
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_task_dependencies')}
            SET status='ready', child_status=%s, child_result=%s::jsonb,
                ready_at=now(), next_attempt_at=NULL, last_error=NULL, updated_at=now()
            WHERE status='waiting' AND child_source_system=%s AND child_source_id=%s
            RETURNING *
            """,
            (
                status_value, _json(child_result or {}), _text(child_source_system, 120),
                _text(child_source_id, 240),
            ),
        )
        return [_row(dict(row)) or {} for row in cur.fetchall()]


def list_ready_task_dependencies(*, limit: int = 100, initialize: bool = True) -> list[dict]:
    """Read ready handoffs; callers claim them with :func:`claim_task_dependency`."""
    if initialize:
        init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT * FROM {_table('operation_task_dependencies')}
            WHERE status='ready'
              AND (next_attempt_at IS NULL OR next_attempt_at <= now())
            ORDER BY next_attempt_at NULLS FIRST, ready_at NULLS FIRST, id
            LIMIT %s
            """,
            (max(1, min(5000, int(limit or 100))),),
        )
        return [_row(dict(row)) or {} for row in cur.fetchall()]


def claim_task_dependency(dependency_id: int, *, initialize: bool = True) -> dict | None:
    """Atomically claim one ready handoff so restart/reconcile cannot double-run it."""
    if initialize:
        init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_task_dependencies')}
            SET status='ready', next_attempt_at=NULL, updated_at=now()
            WHERE status='running' AND updated_at < now() - interval '15 minutes'
            """
        )
        cur.execute(
            f"""
            UPDATE {_table('operation_task_dependencies')}
            SET status='running', attempts=attempts + 1, next_attempt_at=NULL, updated_at=now()
            WHERE id=%s AND status='ready'
              AND (next_attempt_at IS NULL OR next_attempt_at <= now())
            RETURNING *
            """,
            (int(dependency_id),),
        )
        row = cur.fetchone()
        return _row(dict(row)) if row else None


def recover_stale_task_dependencies(*, stale_after_seconds: int = 15 * 60) -> int:
    """Return abandoned dependency claims to the ready queue after restart."""
    init()
    age = max(1, int(stale_after_seconds))
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_task_dependencies')}
            SET status='ready', next_attempt_at=now(), updated_at=now(),
                last_error=COALESCE(last_error, 'dispatcher claim timed out')
            WHERE status='running'
              AND updated_at < now() - (%s * interval '1 second')
            """,
            (age,),
        )
        return cur.rowcount


def complete_task_dependency(
    dependency_id: int,
    *,
    success: bool,
    error: str | None = None,
) -> bool:
    """Ack a claimed handoff; failed continuation remains retryable as ``ready``."""
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_task_dependencies')}
            SET status=%s, last_error=%s,
                completed_at=CASE WHEN %s THEN now() ELSE NULL END,
                next_attempt_at=CASE WHEN %s THEN NULL ELSE now() + interval '1 second' END,
                ready_at=CASE WHEN %s THEN ready_at ELSE COALESCE(ready_at, now()) END,
                updated_at=now()
            WHERE id=%s AND status='running'
            """,
            (
                "completed" if success else "ready", _text(error, 1200) or None,
                bool(success), bool(success), bool(success), int(dependency_id),
            ),
        )
        return cur.rowcount > 0


def apply_task_dependency_result(
    *,
    parent_source_system: str,
    parent_source_id: str,
    child_status: str,
    child_result: dict | None = None,
) -> dict | None:
    """Persist a dependency failure/unknown outcome on its parent task.

    Runtime coordinators use their numeric logical task id as the parent
    source id while the task itself remains in its source namespace.  Other
    adapters may use the normal ``source_system/source_id`` pair.
    """
    init()
    parent_system = _text(parent_source_system, 120)
    parent_id = _text(parent_source_id, 240)
    child_status_value = _status(child_status)
    child_payload = dict(child_result or {})
    unknown = child_status_value in {"request_unknown", "attention_required"} or (
        str(child_payload.get("outcome") or "").lower() == "request_unknown"
    )
    desired = "attention_required" if unknown else "partial_success"
    target_status = "attention_required"
    next_actions = (
        [{"action": "reconcile", "label": "确认远端结果后继续"}]
        if unknown else [{"action": "retry", "label": "重试失败子任务"}]
    )
    with _connect() as conn, conn.cursor() as cur:
        if parent_system == "webui_runtime" and parent_id.isdigit():
            cur.execute(
                f"SELECT * FROM {_table('operation_tasks')} WHERE id=%s FOR UPDATE",
                (int(parent_id),),
            )
        else:
            cur.execute(
                f"""
                SELECT * FROM {_table('operation_tasks')}
                WHERE source_system=%s AND source_id=%s
                FOR UPDATE
                """,
                (parent_system, parent_id),
            )
        parent = cur.fetchone()
        if not parent:
            return None
        parent = dict(parent)
        parent_task_id = int(parent["id"])
        cur.execute(
            f"SELECT * FROM {_table('operation_runs')} WHERE id=%s FOR UPDATE",
            (int(parent.get("last_run_id") or 0),),
        )
        parent_run = cur.fetchone()
        parent_summary = _decode(parent_run.get("result_summary")) if parent_run else {}
        parent_summary = dict(parent_summary) if isinstance(parent_summary, dict) else {}
        parent_summary.update({
            "child_status": child_status_value,
            "child_result": _scrub(child_payload),
        })
        if unknown:
            parent_summary.update({"outcome": "request_unknown", "reconcile_required": True})
        cur.execute(
            f"""
            UPDATE {_table('operation_tasks')}
            SET status=%s, target_status=%s, current_stage='complete',
                next_actions=%s::jsonb, completed_at=COALESCE(completed_at, now()),
                updated_at=now(), error_message=%s
            WHERE id=%s
            """,
            (
                desired, target_status, _json(next_actions),
                _text(
                    "子任务远端结果待核验，父任务禁止自动重做"
                    if unknown else "子任务失败，父任务保留部分成功结果",
                    1400,
                ),
                parent_task_id,
            ),
        )
        if parent_run:
            cur.execute(
                f"""
                UPDATE {_table('operation_runs')}
                SET status=%s, progress_stage='complete', completed_at=COALESCE(completed_at, now()),
                    heartbeat_at=now(), result_summary=%s::jsonb,
                    error_message=%s
                WHERE id=%s
                """,
                (
                    desired, _json(parent_summary),
                    "子任务远端结果待核验，父任务禁止自动重做"
                    if unknown else "子任务失败，父任务保留部分成功结果",
                    int(parent_run["id"]),
                ),
            )
        event_uuid = uuid.uuid4().hex
        cur.execute(
            f"""
            INSERT INTO {_table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s,%s,%s,%s,%s,'WARNING','complete',%s,%s,%s::jsonb)
            """,
            (
                event_uuid, parent_task_id,
                int(parent_run["id"]) if parent_run else None,
                parent_system, event_uuid,
                "task.dependency_unknown" if unknown else "task.dependency_failed",
                "子任务结果待核验，父任务暂停续接" if unknown else "子任务失败，父任务保留部分成功结果",
                _json({"child_status": child_status_value, "child_result": child_payload}),
            ),
        )
        return _row(parent) or {}


def _reconcile_parent_task_cur(cur, parent_task_id: int, *, child_task_id: int | None = None) -> dict | None:
    """Advance a native parent from child states while holding one DB transaction."""
    cur.execute(
        f"SELECT * FROM {_table('operation_tasks')} WHERE id=%s FOR UPDATE",
        (int(parent_task_id),),
    )
    parent = cur.fetchone()
    if not parent:
        return None
    cur.execute(
        f"""
        SELECT id, status, task_type, last_run_id
        FROM {_table('operation_tasks')}
        WHERE parent_task_id=%s
        ORDER BY id
        FOR UPDATE
        """,
        (int(parent_task_id),),
    )
    children = [dict(row) for row in cur.fetchall()]
    if not children:
        return None
    active = [
        child for child in children
        if str(child.get("status") or "") in _ACTIVE_RUN_STATUSES
    ]
    if active:
        desired = "waiting"
        current_stage = "waiting"
        target_status = "pending"
        next_actions = [{"action": "await_child", "label": "等待子任务完成"}]
        completed_at_sql = "NULL"
        event_type = "task.waiting_for_child"
        message = "父任务等待子任务完成，未占用账号操作租约"
        level = "INFO"
    else:
        statuses = {str(child.get("status") or "") for child in children}
        if statuses and statuses <= {"success"}:
            desired = "success"
            target_status = "completed"
            next_actions = []
            message = "所有子任务已完成，父任务自动收口"
            level = "INFO"
        elif "attention_required" in statuses:
            desired = "attention_required"
            target_status = "attention_required"
            next_actions = [{"action": "reconcile", "label": "确认远端结果后继续"}]
            message = "子任务需要确认，父任务保留待对账状态"
            level = "WARNING"
        else:
            desired = "partial_success"
            target_status = "attention_required"
            next_actions = [{"action": "retry", "label": "重试失败子任务"}]
            message = "子任务已结束，父任务保留部分成功结果"
            level = "WARNING"
        current_stage = "complete"
        completed_at_sql = "now()"
        event_type = "task.children_reconciled"
    cur.execute(
        f"""
        UPDATE {_table('operation_tasks')}
        SET status=%s, target_status=%s, current_stage=%s,
            next_actions=%s::jsonb, completed_at={completed_at_sql}, updated_at=now()
        WHERE id=%s
        """,
        (desired, target_status, current_stage, _json(next_actions), int(parent_task_id)),
    )
    parent_run_id = int(parent.get("last_run_id") or 0) or None
    parent_source_system = str(parent.get("source_system") or "native_operations")
    if parent_run_id:
        cur.execute(
            f"SELECT status, result_summary FROM {_table('operation_runs')} WHERE id=%s FOR UPDATE",
            (parent_run_id,),
        )
        parent_run = cur.fetchone()
        if parent_run and str(parent_run.get("status") or "") not in _TERMINAL_STATUSES:
            summary = _decode(parent_run.get("result_summary"))
            summary = dict(summary) if isinstance(summary, dict) else {}
            summary["children"] = {
                str(child["id"]): str(child.get("status") or "") for child in children
            }
            cur.execute(
                f"""
                UPDATE {_table('operation_runs')}
                SET status=%s, progress_stage=%s, heartbeat_at=now(),
                    completed_at=CASE WHEN %s THEN now() ELSE NULL END,
                    result_summary=%s::jsonb,
                    duration_ms=CASE WHEN %s THEN GREATEST(0,
                        (EXTRACT(EPOCH FROM (now() - COALESCE(started_at, created_at))) * 1000)::BIGINT)
                        ELSE duration_ms END
                WHERE id=%s
                """,
                (
                    desired, current_stage, desired != "waiting", _json(summary),
                    desired != "waiting", parent_run_id,
                ),
            )
            if desired == "waiting":
                # A coordinator must release any accidentally retained account
                # lease before its child can acquire that account/family.
                cur.execute(
                    f"DELETE FROM {_table('account_operation_leases')} WHERE run_id=%s",
                    (parent_run_id,),
                )
            event_uuid = uuid.uuid4().hex
            cur.execute(
                f"""
                INSERT INTO {_table('operation_events')} (
                    event_uuid, task_id, run_id, source_system, source_id,
                    level, stage, event_type, message, detail
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'{{}}'::jsonb)
                """,
                (
                    event_uuid, int(parent_task_id), parent_run_id, parent_source_system,
                    event_uuid, level,
                    current_stage, event_type, _text(message, 1400),
                ),
            )
    batch_id = parent.get("batch_id")
    if batch_id:
        _refresh_batches(cur, [int(batch_id)])
    return {
        "parent_task_id": int(parent_task_id),
        "status": desired,
        "child_task_id": int(child_task_id) if child_task_id else None,
        "children": [{"id": int(child["id"]), "status": child.get("status")} for child in children],
    }


def reconcile_parent_task(parent_task_id: int) -> dict | None:
    """Public transaction boundary for a native parent/child reconciliation."""
    init()
    with _connect() as conn, conn.cursor() as cur:
        return _reconcile_parent_task_cur(cur, int(parent_task_id))


# ============================================================
# 原生运行时写模型
# ============================================================

def create_runtime_batch(
    *, batch_type: str, title: str, requested_count: int, trigger: str = "manual",
    data: dict | None = None,
) -> dict:
    """创建真正参与调度的批次；批次只持有 run 引用，不预占账号资源。"""
    init()
    batch_uuid = uuid.uuid4().hex
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {_table('operation_batches')} (
                batch_uuid, source_system, source_id, batch_type, title, status,
                requested_count, created_by, data
            ) VALUES (%s, 'native_operations', %s, %s, %s, 'queued', %s, %s, %s::jsonb)
            RETURNING *
            """,
            (
                batch_uuid, batch_uuid, str(batch_type), _text(title, 240),
                max(0, int(requested_count or 0)), str(trigger or "manual"), _json(data or {}),
            ),
        )
        return _row(dict(cur.fetchone())) or {}


def _insert_runtime_run(
    cur,
    *,
    task_id: int,
    run_no: int,
    source_system: str,
    account_id: int | None,
    batch_id: int | None,
    resource_family: str,
    data: dict | None,
) -> dict:
    run_uuid = uuid.uuid4().hex
    cancellation_token = uuid.uuid4().hex
    cur.execute(f"SELECT task_uuid FROM {_table('operation_tasks')} WHERE id=%s", (int(task_id),))
    task_row = cur.fetchone()
    if not task_row:
        raise LookupError("任务不存在")
    log_file = task_run_log.build_path(
        task_uuid=str(task_row["task_uuid"]), run_no=int(run_no), run_uuid=run_uuid,
    )
    cur.execute(
        f"""
        INSERT INTO {_table('operation_runs')} (
            run_uuid, task_id, run_no, source_system, source_id, status,
            batch_id, account_id, resource_family, cancellation_token, log_file, data
        ) VALUES (%s, %s, %s, %s, %s, 'queued', %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING *
        """,
        (
            run_uuid, int(task_id), int(run_no), str(source_system), run_uuid,
            batch_id, account_id,
            str(resource_family or "openai_interactive"), cancellation_token, log_file, _json(data or {}),
        ),
    )
    run = dict(cur.fetchone())
    event_uuid = uuid.uuid4().hex
    cur.execute(
        f"""
        INSERT INTO {_table('operation_events')} (
            event_uuid, task_id, run_id, source_system, source_id,
            level, stage, event_type, message, detail
        ) VALUES (%s,%s,%s,%s,%s,'INFO','queued','run.queued','任务已加入队列','{{}}'::jsonb)
        """,
        (event_uuid, int(task_id), int(run["id"]), str(source_system), event_uuid),
    )
    task_run_log.append(
        log_file, level="INFO", message="任务已加入队列", task_id=int(task_id),
        run_id=int(run["id"]), stage="queued", event_type="run.queued",
    )
    return run


def create_runtime_task(
    *,
    task_type: str,
    account_id: int | None,
    email: str,
    trigger: str = "manual",
    batch_id: int | None = None,
    batch_ordinal: int | None = None,
    parent_task_id: int | None = None,
    resource_family: str = "openai_interactive",
    data: dict | None = None,
    source_system: str = "native_operations",
    source_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """原子创建逻辑任务和第一次执行。

    ``source_id``/``idempotency_key`` are optional external submission keys.
    When supplied, a retried HTTP request returns the existing logical task and
    current run instead of creating another remote action.  The account/family
    partial unique index remains the second, database-enforced duplicate guard.
    """
    init()
    task_uuid = uuid.uuid4().hex
    source_system_value = str(source_system or "native_operations").strip()[:120] or "native_operations"
    source_value = str(source_id or idempotency_key or "").strip() or task_uuid
    account_value = int(account_id) if account_id else None
    with _connect() as conn, conn.cursor() as cur:
        if source_id or idempotency_key:
            cur.execute(
                f"""
                SELECT * FROM {_table('operation_tasks')}
                WHERE source_system=%s AND source_id=%s
                FOR UPDATE
                """,
                (source_system_value, source_value),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    f"""
                    SELECT * FROM {_table('operation_runs')}
                    WHERE task_id=%s ORDER BY run_no DESC, id DESC LIMIT 1
                    """,
                    (int(existing["id"]),),
                )
                current_run = cur.fetchone()
                result = _row(dict(existing)) or {}
                result["run"] = _row(dict(current_run)) if current_run else None
                result["idempotent"] = True
                return result
        cur.execute(
            f"""
            INSERT INTO {_table('operation_tasks')} (
                task_uuid, source_system, source_id, batch_id, parent_task_id,
                task_type, target_type, target_id, account_id, email_snapshot,
                requested_action, status, target_status, current_stage,
                next_actions, trigger, data
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, 'account', %s, %s, %s,
                %s, 'queued', 'pending', 'queued',
                '[]'::jsonb, %s, %s::jsonb
            ) RETURNING *
            """,
            (
                task_uuid, source_system_value, source_value, batch_id, parent_task_id, str(task_type),
                account_value, account_value, str(email or "").strip(), str(task_type),
                str(trigger or "manual"), _json(data or {}),
            ),
        )
        task = dict(cur.fetchone())
        if not task.get("parent_task_id"):
            cur.execute(
                f"UPDATE {_table('operation_tasks')} SET root_task_id=id WHERE id=%s",
                (int(task["id"]),),
            )
        else:
            cur.execute(
                f"""
                UPDATE {_table('operation_tasks')} child
                SET root_task_id=COALESCE(parent.root_task_id, parent.id)
                FROM {_table('operation_tasks')} parent
                WHERE child.id=%s AND parent.id=child.parent_task_id
                """,
                (int(task["id"]),),
            )
        run = _insert_runtime_run(
            cur,
            task_id=int(task["id"]),
            run_no=1,
            source_system=source_system_value,
            account_id=account_value,
            batch_id=int(batch_id) if batch_id else None,
            resource_family=resource_family,
            data=data,
        )
        cur.execute(
            f"UPDATE {_table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
            (int(run["id"]), int(task["id"])),
        )
        if batch_id:
            ordinal = int(batch_ordinal or 0)
            if ordinal <= 0:
                cur.execute(
                    f"SELECT COALESCE(MAX(ordinal), 0) + 1 AS n FROM {_table('operation_batch_items')} WHERE batch_id=%s",
                    (int(batch_id),),
                )
                ordinal = int(cur.fetchone()["n"])
            cur.execute(
                f"""
                INSERT INTO {_table('operation_batch_items')} (batch_id, task_id, run_id, ordinal)
                VALUES (%s, %s, %s, %s)
                """,
                (int(batch_id), int(task["id"]), int(run["id"]), ordinal),
            )
        task = _row(task) or {}
        task["run"] = _row(run) or {}
        task["idempotent"] = False
        if parent_task_id:
            _reconcile_parent_task_cur(cur, int(parent_task_id), child_task_id=int(task["id"]))
        return task


def _remote_write_checkpoint(data: Any) -> dict:
    payload = _decode(data)
    intent = payload.get("remote_intent") if isinstance(payload, dict) else None
    if isinstance(intent, dict) and intent.get("kind") == "remote_write":
        return intent
    return {}


def retry_runtime_task(task_id: int, *, trigger: str = "manual_retry", data: dict | None = None) -> dict:
    """在同一逻辑任务下新建 attempt；不会制造第二条逻辑任务。"""
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {_table('operation_tasks')} WHERE id=%s FOR UPDATE",
            (int(task_id),),
        )
        task = cur.fetchone()
        if not task:
            raise LookupError("任务不存在")
        if str(task.get("source_system") or "") in {"registration_jobs", "account_action_tasks"}:
            raise ValueError("历史兼容任务需先迁移为原生任务后再重跑")
        cur.execute(
            f"SELECT COALESCE(MAX(run_no), 0) + 1 AS n FROM {_table('operation_runs')} WHERE task_id=%s",
            (int(task_id),),
        )
        run_no = int(cur.fetchone()["n"])
        merged_data = dict(_decode(task.get("data")) or {})
        merged_data.update(data or {})
        merged_data["retry_trigger"] = str(trigger or "manual_retry")
        cur.execute(
            f"""
            SELECT resource_family, batch_id, data, result_summary
            FROM {_table('operation_runs')}
            WHERE task_id=%s ORDER BY run_no DESC, id DESC LIMIT 1
            """,
            (int(task_id),),
        )
        previous_run = cur.fetchone() or {}
        intent = _remote_write_checkpoint(previous_run.get("data"))
        receipt = str(intent.get("receipt_state") or intent.get("state") or "started")
        summary = _decode(previous_run.get("result_summary")) or {}
        if (intent and receipt != "rejected") or (
            isinstance(summary, dict)
            and (summary.get("outcome") == "request_unknown" or summary.get("reconcile_required"))
        ):
            # Guard the storage boundary, not only the HTTP route.  A generic
            # retry cannot establish whether a remote write already happened;
            # reconciliation must use the service's explicit follow-up path.
            raise ValueError("远端写请求结果需先核验，禁止直接重试原操作")
        previous_data = _decode(previous_run.get("data"))
        if isinstance(previous_data, dict):
            previous_data = dict(previous_data)
            previous_data.update(merged_data)
            merged_data = previous_data
        # Clear after merging the previous Run, otherwise its checkpoints are
        # copied back into the supposedly fresh attempt.
        merged_data.pop("remote_intent", None)
        merged_data.pop("remote_receipt", None)
        run = _insert_runtime_run(
            cur,
            task_id=int(task_id),
            run_no=run_no,
            source_system=str(task.get("source_system") or "native_operations"),
            account_id=int(task["account_id"]) if task.get("account_id") else None,
            batch_id=previous_run.get("batch_id"),
            resource_family=str(previous_run.get("resource_family") or "openai_interactive"),
            data=merged_data,
        )
        cur.execute(
            f"""
            UPDATE {_table('operation_tasks')}
            SET status='queued', target_status='pending', current_stage='queued',
                last_run_id=%s, error_category=NULL, error_code=NULL, error_message=NULL,
                completed_at=NULL, updated_at=now(), trigger=%s
            WHERE id=%s
            """,
            (int(run["id"]), str(trigger or "manual_retry"), int(task_id)),
        )
        return _row(run) or {}


def get_run(run_id: int) -> dict | None:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.task_type, t.email_snapshot, t.trigger, t.parent_task_id
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=%s
            """,
            (int(run_id),),
        )
        raw = cur.fetchone()
        return _row(dict(raw)) if raw else None


def active_run_for_account(account_id: int, resource_family: str = "openai_interactive") -> dict | None:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.email_snapshot, t.task_type
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.account_id=%s AND r.resource_family=%s
              AND r.status IN ('queued', 'running', 'cancelling', 'settling', 'stopping')
            ORDER BY r.id DESC LIMIT 1
            """,
            (int(account_id), str(resource_family)),
        )
        raw = cur.fetchone()
        return _row(dict(raw)) if raw else None


def has_active_runtime_operations(
    *,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
) -> bool:
    """Return whether durable active Runs cover a legacy recovery category."""
    init()
    clauses = [f"r.status IN ({_ACTIVE_RUN_STATUS_SQL})"]
    params: list[Any] = []
    if task_types is not None:
        values = [str(item).strip() for item in task_types if str(item).strip()]
        if not values:
            return False
        clauses.append("t.task_type = ANY(%s)")
        params.append(values)
    if source_systems is not None:
        values = [str(item).strip() for item in source_systems if str(item).strip()]
        if not values:
            return False
        clauses.append("t.source_system = ANY(%s)")
        params.append(values)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT 1
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE {' AND '.join(clauses)}
            LIMIT 1
            """,
            tuple(params),
        )
        return cur.fetchone() is not None


def list_reconciliation_accounts(
    *,
    task_type: str,
    account_ids: Iterable[int] | None = None,
    source_systems: Iterable[str] | None = ("native_operations",),
    limit: int = 5000,
) -> list[dict]:
    """List accounts whose current/recent attempt must be reconciled first.

    This is a read-only safety gate for producers that have another durable
    credential source. It treats every non-rejected remote-write checkpoint as
    fenced, including ``started``, ``response_received``,
    ``local_commit_required`` and ``confirmed`` while the attempt is not
    terminal. Explicit ``rejected`` is deliberately not returned.
    """
    init()
    clauses = [
        "t.task_type=%s",
        "("
        "t.status='attention_required' OR r.status='attention_required' "
        "OR COALESCE(r.result_summary->>'outcome','')='request_unknown' "
        "OR COALESCE(r.result_summary->>'reconcile_required','false')='true' "
        "OR ("
        "r.status NOT IN ('success','partial_success','failed','stopped','cancelled',"
        "'interrupted','deactivated','unsupported','attention_required') "
        "AND r.data->'remote_intent'->>'kind'='remote_write' "
        "AND COALESCE(r.data->'remote_intent'->>'receipt_state',"
        "r.data->'remote_intent'->>'state','started') <> 'rejected'"
        ")"
        ")",
    ]
    params: list[Any] = [str(task_type or "").strip()]
    requested_account_ids: list[int] | None = None
    if account_ids is not None:
        requested_account_ids = list(dict.fromkeys(int(item) for item in account_ids))
        if not requested_account_ids:
            return []
        clauses.append("t.account_id = ANY(%s)")
        params.append(requested_account_ids)
    if source_systems is not None:
        values = [str(item).strip() for item in source_systems if str(item).strip()]
        if not values:
            return []
        clauses.append("t.source_system = ANY(%s)")
        params.append(values)
    requested_limit = max(1, int(limit or 5000))
    # A caller that supplies an explicit candidate set is using this as a
    # safety gate, not pagination. Return every requested account even when a
    # small default limit was passed; otherwise a producer could silently
    # skip an account whose older rows happen to sort ahead of it.
    effective_limit = (
        max(requested_limit, len(requested_account_ids))
        if requested_account_ids is not None
        else min(5000, requested_limit)
    )
    params.append(effective_limit)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            WITH candidates AS (
                SELECT DISTINCT ON (t.account_id)
                       t.account_id, t.id AS task_id, t.status AS task_status,
                       r.id AS run_id, r.status AS run_status,
                       r.data->'remote_intent'->>'action' AS remote_action,
                       COALESCE(r.data->'remote_intent'->>'receipt_state',
                                r.data->'remote_intent'->>'state') AS remote_intent_state,
                       r.result_summary
                FROM {_table('operation_tasks')} t
                JOIN {_table('operation_runs')} r ON r.task_id=t.id
                WHERE {' AND '.join(clauses)}
                ORDER BY t.account_id, r.id DESC
            )
            SELECT account_id, task_id, task_status, run_id, run_status,
                   remote_action, remote_intent_state, result_summary
            FROM candidates
            ORDER BY account_id
            LIMIT %s
            """,
            tuple(params),
        )
        rows = []
        seen_accounts: set[int] = set()
        for raw in cur.fetchall():
            row = dict(raw)
            account_id = int(row["account_id"]) if row.get("account_id") else None
            if account_id is None or account_id in seen_accounts:
                continue
            seen_accounts.add(account_id)
            summary = _decode(row.get("result_summary"))
            summary = dict(summary) if isinstance(summary, dict) else {}
            row["result_summary"] = _scrub(summary)
            row["reconcile_required"] = bool(
                str(summary.get("outcome") or "").lower() == "request_unknown"
                or summary.get("reconcile_required")
                or str(row.get("run_status") or "") == "attention_required"
                or str(row.get("task_status") or "") == "attention_required"
                or (
                    str(row.get("remote_intent_state") or "") != "rejected"
                    and str(row.get("remote_intent_state") or "") != ""
                    and str(row.get("run_status") or "") not in _TERMINAL_STATUSES
                )
            )
            rows.append(_row(row) or {})
        return rows


def list_queued_runs(*, limit: int = 500) -> list[dict]:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.email_snapshot, t.task_type
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.source_system='native_operations' AND r.status='queued'
              AND r.cancel_requested_at IS NULL
              AND (r.next_attempt_at IS NULL OR r.next_attempt_at <= now())
            ORDER BY r.created_at, r.id LIMIT %s
            """,
            (max(1, min(5000, int(limit or 500))),),
        )
        return [_row(dict(row)) or {} for row in cur.fetchall()]


def list_dispatchable_runs(
    *,
    limit: int = 500,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
) -> list[dict]:
    """List current queued runs for gateway-registered task handlers.

    Unlike the historical Codex-only query, this is task-type based and only
    applies an optional source allowlist supplied by the gateway. A
    compatibility projection can therefore be migrated one task type at a
    time, while unregistered types remain durable but are not accidentally
    executed by this dispatcher.
    """
    init()
    values = [str(item).strip() for item in (task_types or ()) if str(item).strip()]
    source_values = (
        [str(item).strip() for item in source_systems if str(item).strip()]
        if source_systems is not None else None
    )
    if source_values is not None and not source_values:
        return []
    clauses = [
        "r.status='queued'",
        "r.cancel_requested_at IS NULL",
        "(r.next_attempt_at IS NULL OR r.next_attempt_at <= now())",
        "t.last_run_id=r.id",
    ]
    params: list[Any] = []
    if values:
        clauses.append("t.task_type = ANY(%s)")
        params.append(values)
    if source_values is not None:
        clauses.append("t.source_system = ANY(%s)")
        params.append(source_values)
    params.append(max(1, min(5000, int(limit or 500))))
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.email_snapshot, t.task_type, t.source_system
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at, r.id LIMIT %s
            """,
            tuple(params),
        )
        return [_row(dict(row)) or {} for row in cur.fetchall()]


def claim_next_queued_run(
    *,
    execution_id: str,
    worker_pid: int,
    source_systems: Iterable[str] | None = None,
    task_types: Iterable[str] | None = None,
) -> dict | None:
    """Atomically claim the oldest durable queue row across workers.

    The row lock is held only for the state transition and event insert.  The
    actual account lease is still acquired by the executor immediately before
    remote work, so a queue claim never reserves an account while waiting for a
    thread-pool slot.
    """
    init()
    with _connect() as conn, conn.cursor() as cur:
        clauses = [
            "r.status='queued'",
            "r.cancel_requested_at IS NULL",
            "(r.next_attempt_at IS NULL OR r.next_attempt_at <= now())",
        ]
        params: list[Any] = []
        sources = [str(item).strip() for item in (source_systems or ()) if str(item).strip()]
        types = [str(item).strip() for item in (task_types or ()) if str(item).strip()]
        if source_systems is None:
            clauses.append("r.source_system='native_operations'")
        elif not sources:
            return None
        else:
            clauses.append("t.source_system = ANY(%s)")
            params.append(sources)
        if task_types is not None:
            if not types:
                return None
            clauses.append("t.task_type = ANY(%s)")
            params.append(types)
        cur.execute(
            f"""
            SELECT r.id
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at, r.id
            FOR UPDATE OF r SKIP LOCKED
            LIMIT 1
            """,
            tuple(params),
        )
        selected = cur.fetchone()
        if not selected:
            return None
        run_id = int(selected["id"])
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')}
            SET status='running', execution_id=%s, worker_pid=%s,
                next_attempt_at=NULL,
                started_at=COALESCE(started_at, now()), heartbeat_at=now(),
                progress_stage='preflight'
            WHERE id=%s AND status='queued' AND cancel_requested_at IS NULL
              AND (next_attempt_at IS NULL OR next_attempt_at <= now())
            RETURNING *
            """,
            (str(execution_id), int(worker_pid), run_id),
        )
        raw = cur.fetchone()
        if not raw:
            return None
        run = dict(raw)
        cur.execute(
            f"""
            UPDATE {_table('operation_tasks')}
            SET status='running', current_stage='preflight', updated_at=now()
            WHERE id=%s
            """,
            (int(run["task_id"]),),
        )
        event_uuid = uuid.uuid4().hex
        cur.execute(
            f"""
            INSERT INTO {_table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s,%s,%s,%s,%s,'INFO','queued',
                      'run.running','任务开始执行','{{}}'::jsonb)
            """,
            (
                event_uuid, int(run["task_id"]), run_id,
                str(run.get("source_system") or "native_operations"), event_uuid,
            ),
        )
        cur.execute(
            f"""
            SELECT r.*, t.task_type, t.email_snapshot, t.trigger, t.parent_task_id
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=%s
            """,
            (run_id,),
        )
        result = _row(dict(cur.fetchone())) or {}
    task_run_log.append(
        result.get("log_file"), level="INFO", message="任务开始执行",
        task_id=int(result["task_id"]), run_id=run_id, stage="queued", event_type="run.running",
    )
    return result


def recover_interrupted_runtime_runs(*, stale_after_seconds: int = 15 * 60) -> int:
    """收口真正失去 worker 的 attempt；有效租约和新鲜心跳均保留。

    WebUI 可能只是一个进程，原生 worker 也可能来自另一个进程。启动时
    不能把所有 ``running`` 行当成自己的；只有心跳已经过期且不存在有效
    account lease 的行才属于可恢复的孤儿执行。
    """
    init()
    stale_seconds = max(1, min(7 * 24 * 60 * 60, int(stale_after_seconds or 0)))
    ready_dependencies: list[dict] = []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')} AS run
            SET status=CASE
                    WHEN run.data->'remote_intent'->>'kind'='remote_write'
                     AND COALESCE(
                         run.data->'remote_intent'->>'receipt_state',
                         run.data->'remote_intent'->>'state', 'started'
                     )
                         <> 'rejected'
                    THEN 'attention_required'
                    ELSE 'interrupted'
                END,
                completed_at=now(), heartbeat_at=now(),
                progress_stage=CASE
                    WHEN run.data->'remote_intent'->>'kind'='remote_write'
                     AND COALESCE(
                         run.data->'remote_intent'->>'receipt_state',
                         run.data->'remote_intent'->>'state', 'started'
                     )
                         <> 'rejected'
                    THEN 'reconcile'
                    ELSE 'interrupted'
                END,
                error_message=CASE
                    WHEN run.data->'remote_intent'->>'kind'='remote_write'
                     AND COALESCE(
                         run.data->'remote_intent'->>'receipt_state',
                         run.data->'remote_intent'->>'state', 'started'
                     )
                         <> 'rejected'
                    THEN '远端写请求结果待核验，禁止自动重做'
                    ELSE '执行进程已重启，原 attempt 中断'
                END,
                result_summary=CASE
                    WHEN run.data->'remote_intent'->>'kind'='remote_write'
                     AND COALESCE(
                         run.data->'remote_intent'->>'receipt_state',
                         run.data->'remote_intent'->>'state', 'started'
                     )
                         <> 'rejected'
                    THEN COALESCE(run.result_summary, '{{}}'::jsonb) || jsonb_build_object(
                        'outcome', 'request_unknown',
                        'reconcile_required', true,
                        'execution_id', COALESCE(run.execution_id, ''),
                        'lease_owner', COALESCE(run.execution_id, ''),
                        'remote_action', run.data->'remote_intent'->>'action',
                        'remote_intent_state', COALESCE(
                            run.data->'remote_intent'->>'receipt_state',
                            run.data->'remote_intent'->>'state', 'started'
                        )
                    )
                    ELSE run.result_summary
                END
            FROM {_table('operation_tasks')} task
            WHERE run.task_id=task.id
              AND run.source_system NOT IN ('registration_jobs', 'account_action_tasks')
              AND run.status IN ('running', 'cancelling', 'settling')
              AND (run.heartbeat_at IS NULL OR run.heartbeat_at < now() - (%s * interval '1 second'))
              AND NOT EXISTS (
                  SELECT 1 FROM {_table('account_operation_leases')} lease
                  WHERE lease.run_id=run.id AND lease.expires_at > now()
              )
            RETURNING run.id, run.task_id, run.account_id, run.batch_id,
                      run.status, run.data, run.execution_id, task.source_system,
                      task.task_type
            """,
            (stale_seconds,),
        )
        recovered = list(cur.fetchall())
        run_ids = [int(row["id"]) for row in recovered]
        task_ids = [int(row["task_id"]) for row in recovered]
        current_task_ids: list[int] = []
        source_by_task: dict[int, str] = {}
        status_by_task: dict[int, str] = {
            int(row["task_id"]): str(row.get("status") or "interrupted")
            for row in recovered
        }
        if task_ids:
            cur.execute(
                f"SELECT id, source_system FROM {_table('operation_tasks')} WHERE id = ANY(%s)",
                (task_ids,),
            )
            source_by_task = {
                int(row["id"]): str(row.get("source_system") or "native_operations")
                for row in cur.fetchall()
            }
            for row in recovered:
                recovered_status = status_by_task[int(row["task_id"])]
                cur.execute(
                    f"""
                    UPDATE {_table('operation_tasks')}
                    SET status=%s,
                        current_stage=%s,
                        completed_at=now(),
                        updated_at=now(),
                        error_message=%s,
                        target_status=CASE WHEN %s='attention_required'
                            THEN 'attention_required' ELSE target_status END,
                        next_actions=%s::jsonb
                    WHERE id=%s AND last_run_id=%s
                    """,
                    (
                        recovered_status,
                        "reconcile" if recovered_status == "attention_required" else "interrupted",
                        "远端写请求结果待核验，禁止自动重做"
                        if recovered_status == "attention_required"
                        else "执行进程已重启，原 attempt 中断",
                        recovered_status,
                        _json(
                            [{"action": "reconcile", "label": "确认远端结果后继续"}]
                            if recovered_status == "attention_required"
                            else [{"action": "retry", "label": "重新执行"}]
                        ),
                        int(row["task_id"]), int(row["id"]),
                    ),
                )
                if cur.rowcount:
                    current_task_ids.append(int(row["task_id"]))
            cur.execute(
                f"""
                UPDATE {_table('operation_resources')}
                SET state='reconciliation_required',
                    detail=detail || '{{"reason":"worker_restart"}}'::jsonb
                WHERE run_id = ANY(%s) AND state='acquired'
                """,
                (run_ids,),
            )
            for row in recovered:
                recovered_status = status_by_task[int(row["task_id"])]
                event_uuid = uuid.uuid4().hex
                cur.execute(
                    f"""
                    INSERT INTO {_table('operation_events')} (
                        event_uuid, task_id, run_id, source_system, source_id,
                        level, stage, event_type, message, detail
                    ) VALUES (%s, %s, %s, %s, %s,
                              'WARNING', %s, %s, %s, %s::jsonb)
                    """,
                    (
                        event_uuid, int(row["task_id"]), int(row["id"]),
                        source_by_task.get(int(row["task_id"]), "native_operations"),
                        event_uuid,
                        "reconcile" if recovered_status == "attention_required" else "interrupted",
                        "run.request_unknown" if recovered_status == "attention_required" else "run.interrupted",
                        "远端写请求结果待核验，禁止自动重做"
                        if recovered_status == "attention_required"
                        else "执行进程已重启，原 attempt 中断",
                        _json({
                            "reason": "worker_restart",
                            "outcome": "request_unknown"
                            if recovered_status == "attention_required" else "interrupted",
                            "reconcile_required": recovered_status == "attention_required",
                        }),
                    ),
                )
            if current_task_ids:
                cur.execute(
                    f"""
                    SELECT DISTINCT parent_task_id
                    FROM {_table('operation_tasks')}
                    WHERE id = ANY(%s) AND parent_task_id IS NOT NULL
                    """,
                    (current_task_ids,),
                )
                for parent in cur.fetchall():
                    _reconcile_parent_task_cur(cur, int(parent["parent_task_id"]))
                # A dependency is keyed to the logical child task, but an old
                # attempt must not wake it after a newer retry has become the
                # task's last_run_id. Only tasks whose current attempt was
                # actually interrupted are eligible here.
                for recovered_status in ("interrupted", "attention_required"):
                    for source_system in sorted({source_by_task.get(task_id, "native_operations") for task_id in current_task_ids}):
                        source_task_ids = [
                            str(task_id) for task_id in current_task_ids
                            if status_by_task.get(task_id) == recovered_status
                            and source_by_task.get(task_id, "native_operations") == source_system
                        ]
                        if not source_task_ids:
                            continue
                        cur.execute(
                            f"""
                            UPDATE {_table('operation_task_dependencies')} dependency
                            SET status='ready', child_status=%s,
                                child_result=%s::jsonb, ready_at=now(),
                                next_attempt_at=NULL, last_error=NULL, updated_at=now()
                            WHERE dependency.status='waiting'
                              AND dependency.child_source_system=%s
                              AND dependency.child_source_id = ANY(%s)
                            RETURNING dependency.*
                            """,
                            (
                                recovered_status,
                                _json({
                                    "status": recovered_status,
                                    "reason": "worker_restart",
                                    "outcome": "request_unknown"
                                    if recovered_status == "attention_required" else "interrupted",
                                    "reconcile_required": recovered_status == "attention_required",
                                }),
                                source_system, source_task_ids,
                            ),
                        )
                        ready_dependencies.extend(
                            _row(dict(dependency)) or {} for dependency in cur.fetchall()
                        )
        if run_ids:
            cur.execute(
                f"DELETE FROM {_table('account_operation_leases')} WHERE run_id = ANY(%s)",
                (run_ids,),
            )
        # Only the Codex adapter owns these legacy account columns.  A stale
        # live/refresh/setup run must not clear Codex or other business state
        # merely because the generic durable recovery pass saw its account id.
        codex_status_by_account: dict[int, str] = {}
        for row in recovered:
            if row.get("account_id") and str(row.get("task_type") or "") == "codex_retry":
                account_number = int(row["account_id"])
                codex_status_by_account[account_number] = (
                    "attention_required"
                    if str(row.get("status") or "") == "attention_required"
                    else "interrupted"
                )
        for account_number, last_status in codex_status_by_account.items():
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified(record_store.ACCOUNTS.name)}
                SET codex_execution_status='empty', codex_active_run_id=NULL,
                    codex_last_run_status=%s,
                    codex_status=CASE
                        WHEN codex_status='success' THEN codex_status
                        ELSE %s
                    END,
                    updated_at=%s
                WHERE id=%s
                """,
                (
                    last_status, last_status,
                    datetime.now().isoformat(timespec="seconds"), account_number,
                ),
            )
        _refresh_batches(cur, [row.get("batch_id") for row in recovered])
    if ready_dependencies:
        from core.operations import task_gateway

        for dependency in ready_dependencies:
            task_gateway.notify_dependency_ready(dependency)
    return len(task_ids)


def refresh_runtime_batches(batch_ids: Iterable[int] | None = None) -> None:
    init()
    with _connect() as conn, conn.cursor() as cur:
        _refresh_batches(cur, batch_ids)


def mark_runtime_batch_empty(batch_id: int, *, status: str = "failed") -> None:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_batches')}
            SET status=%s, completed_at=now(),
                skipped_count=GREATEST(skipped_count, requested_count)
            WHERE id=%s AND NOT EXISTS (
                SELECT 1 FROM {_table('operation_batch_items')} item WHERE item.batch_id=%s
            )
            """,
            (str(status), int(batch_id), int(batch_id)),
        )


def set_runtime_batch_skipped(batch_id: int, skipped: list[dict]) -> None:
    """记录提交阶段未创建 run 的条目，避免批次计数看起来凭空少了账号。"""
    init()
    safe_items = list(skipped or [])[:5000]
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_batches')}
            SET skipped_count=%s,
                data=data || %s::jsonb
            WHERE id=%s
            """,
            (len(safe_items), _json({"skipped": safe_items}), int(batch_id)),
        )
        _refresh_batches(cur, [int(batch_id)])


def claim_run(run_id: int, *, execution_id: str, worker_pid: int) -> dict | None:
    """仅一个进程能把 queued attempt 原子认领为 running。"""
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')}
            SET status='running', execution_id=%s, worker_pid=%s,
                next_attempt_at=NULL,
                started_at=COALESCE(started_at, now()), heartbeat_at=now(), progress_stage='preflight'
            WHERE id=%s AND status='queued' AND cancel_requested_at IS NULL
              AND (next_attempt_at IS NULL OR next_attempt_at <= now())
            RETURNING *
            """,
            (str(execution_id), int(worker_pid), int(run_id)),
        )
        run = cur.fetchone()
        if not run:
            return None
        cur.execute(
            f"""
            UPDATE {_table('operation_tasks')}
            SET status='running', current_stage='preflight', updated_at=now()
            WHERE id=%s
            """,
            (int(run["task_id"]),),
        )
        event_uuid = uuid.uuid4().hex
        cur.execute(
            f"""
            INSERT INTO {_table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s,%s,%s,%s,%s,'INFO','queued','run.running','任务开始执行','{{}}'::jsonb)
            """,
            (
                event_uuid, int(run["task_id"]), int(run_id),
                str(run.get("source_system") or "native_operations"), event_uuid,
            ),
        )
        result = _row(dict(run)) or {}
    task_run_log.append(
        result.get("log_file"), level="INFO", message="任务开始执行",
        task_id=int(result["task_id"]), run_id=int(run_id), stage="queued", event_type="run.running",
    )
    return result


def requeue_claimed_run(
    run_id: int,
    *,
    execution_id: str,
    reason: str,
    delay_seconds: float = 1.0,
) -> dict | None:
    """Return a claimed run to the durable queue without creating an attempt.

    A handler can reach this boundary when its account lease is temporarily
    held by another worker.  The transition is guarded by the execution id,
    so a stale worker cannot put a newer claim back into ``queued``.  A cancel
    request wins over requeue and is left for the normal terminal path.
    """
    init()
    delay = max(0.0, min(300.0, float(delay_seconds or 0.0)))
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.task_type, t.email_snapshot, t.trigger
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=%s
            FOR UPDATE OF r
            """,
            (int(run_id),),
        )
        found = cur.fetchone()
        if not found:
            raise LookupError("执行实例不存在")
        if (
            str(found.get("status") or "") not in {"running", "cancelling"}
            or str(found.get("execution_id") or "") != str(execution_id)
            or found.get("cancel_requested_at") is not None
        ):
            return None
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')}
            SET status='queued', execution_id=NULL, worker_pid=NULL,
                heartbeat_at=now(), progress_stage='queued',
                started_at=NULL,
                next_attempt_at=now() + (%s * interval '1 second'),
                data=data || %s::jsonb
            WHERE id=%s AND status IN ('running','cancelling')
              AND execution_id=%s AND cancel_requested_at IS NULL
            RETURNING *
            """,
            (
                delay,
                _json({
                    "last_requeue_reason": _text(reason, 500),
                    "next_attempt_delay_seconds": delay,
                }),
                int(run_id), str(execution_id),
            ),
        )
        row = cur.fetchone()
        if not row:
            return None
        run = dict(row)
        cur.execute(
            f"""
            UPDATE {_table('operation_tasks')}
            SET status='queued', current_stage='queued', updated_at=now(),
                error_category=NULL, error_code=NULL, error_message=NULL
            WHERE id=%s AND last_run_id=%s
            """,
            (int(run["task_id"]), int(run_id)),
        )
        event_uuid = uuid.uuid4().hex
        cur.execute(
            f"""
            INSERT INTO {_table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s,%s,%s,%s,%s,'INFO','queued','run.requeued',%s,%s::jsonb)
            """,
            (
                event_uuid, int(run["task_id"]), int(run_id),
                str(run.get("source_system") or "native_operations"), event_uuid,
                _text(f"任务暂回数据库队列：{reason}", 1400),
                _json({"delay_seconds": delay}),
            ),
        )
        result = _row(run) or {}
    task_run_log.append(
        result.get("log_file"), level="INFO", message=f"任务暂回数据库队列：{reason}",
        task_id=int(result["task_id"]), run_id=int(run_id), stage="queued",
        event_type="run.requeued",
    )
    return result


def append_runtime_event(
    run_id: int,
    *,
    stage: str,
    message: str,
    state: str | None = None,
    level: str = "INFO",
    event_type: str | None = None,
    detail: dict | None = None,
) -> dict:
    init()
    event_uuid = uuid.uuid4().hex
    stage_value = normalize_stage(stage)
    state_value = normalize_step_state(state) if state is not None else None
    if state is not None and state_value is None:
        raise ValueError(f"不支持的任务步骤状态: {state!r}")
    level_value = str(level or "INFO").upper()
    event_type_value = str(event_type or "").strip()[:120]
    if not event_type_value:
        event_type_value = (
            f"stage.{state_value}"
            if state_value is not None
            else "note.error" if level_value == "ERROR"
            else "note.warning" if level_value == "WARNING"
            else "note.info"
        )
    if event_type_value.startswith("stage."):
        event_state = normalize_step_state(event_type_value.removeprefix("stage."))
        if event_state is None:
            raise ValueError(f"不支持的阶段事件类型: {event_type_value!r}")
        if state_value is not None and state_value != event_state:
            raise ValueError("任务步骤状态与事件类型不一致")
        state_value = event_state
    clean_detail = dict(detail or {})
    if state_value is not None:
        clean_detail["step_state"] = state_value
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT task_id, log_file, source_system FROM {_table('operation_runs')} WHERE id=%s",
            (int(run_id),),
        )
        found = cur.fetchone()
        if not found:
            raise LookupError("执行实例不存在")
        task_id = int(found["task_id"])
        cur.execute(
            f"""
            INSERT INTO {_table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING *
            """,
            (
                event_uuid, task_id, int(run_id), str(found.get("source_system") or "native_operations"),
                event_uuid, level_value,
                stage_value, event_type_value, _text(message, 1400), _json(clean_detail),
            ),
        )
        event = dict(cur.fetchone())
        if state_value is not None:
            cur.execute(
                f"""
                UPDATE {_table('operation_runs')}
                SET progress_stage=%s,
                    progress_steps=jsonb_set(progress_steps, %s, to_jsonb(%s::text), true),
                    heartbeat_at=now()
                WHERE id=%s
                """,
                (stage_value, [stage_value], state_value, int(run_id)),
            )
            cur.execute(
                f"UPDATE {_table('operation_tasks')} SET current_stage=%s, updated_at=now() WHERE id=%s",
                (stage_value, task_id),
            )
        else:
            cur.execute(
                f"UPDATE {_table('operation_runs')} SET heartbeat_at=now() WHERE id=%s",
                (int(run_id),),
            )
            cur.execute(
                f"UPDATE {_table('operation_tasks')} SET updated_at=now() WHERE id=%s",
                (task_id,),
            )
        result = _row(event) or {}
        log_file = found.get("log_file")
    task_run_log.append(
        log_file, level=level_value, message=message, task_id=task_id, run_id=int(run_id),
        stage=stage_value, event_type=event_type_value, fields=clean_detail,
    )
    return result


_REMOTE_INTENT_KINDS = frozenset({"remote_write", "read"})
_REMOTE_RECEIPT_OUTCOMES = frozenset({
    "confirmed", "rejected", "unknown", "response_received",
    "local_commit_required",
})


def _remote_checkpoint_fence(
    cur,
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None,
    require_lease: bool,
) -> dict:
    """Load one active run and verify the execution/lease owner.

    Remote intent is a safety checkpoint, not an ordinary progress event.  It
    therefore uses the same fence as terminal result writes and never accepts
    a stale worker's checkpoint after a lease has changed hands.
    """
    execution_value = str(execution_id or "").strip()
    if not execution_value:
        raise ValueError("remote checkpoint 必须携带 execution_id")
    cur.execute(
        f"SELECT * FROM {_table('operation_runs')} WHERE id=%s FOR UPDATE",
        (int(run_id),),
    )
    raw = cur.fetchone()
    if not raw:
        raise LookupError("执行实例不存在")
    run = dict(raw)
    if str(run.get("status") or "") not in {"running", "cancelling", "settling"}:
        raise PermissionError("非活动执行实例不能写入 remote checkpoint")
    if str(run.get("execution_id") or "") != execution_value:
        raise PermissionError("remote checkpoint execution fence 不匹配")
    token = str(lease_token or "").strip()
    if require_lease and not token:
        raise PermissionError("remote write 必须持有账号 lease")
    if token:
        cur.execute(
            f"""
            SELECT 1 FROM {_table('account_operation_leases')}
            WHERE run_id=%s AND lease_token=%s AND expires_at > now()
            """,
            (int(run_id), token),
        )
        if not cur.fetchone():
            raise PermissionError("remote checkpoint lease owner 不匹配或已过期")
    elif run.get("account_id") is not None and require_lease:
        raise PermissionError("账号 remote write 缺少 lease")
    return run


def _remote_checkpoint_event(
    cur,
    run: dict,
    *,
    event_type: str,
    message: str,
    detail: dict[str, Any],
) -> None:
    event_uuid = uuid.uuid4().hex
    cur.execute(
        f"""
        INSERT INTO {_table('operation_events')} (
            event_uuid, task_id, run_id, source_system, source_id,
            level, stage, event_type, message, detail
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        """,
        (
            event_uuid, int(run["task_id"]), int(run["id"]),
            str(run.get("source_system") or "native_operations"), event_uuid,
            "WARNING" if "unknown" in event_type else "INFO",
            "reconcile" if "unknown" in event_type else "remote_request",
            event_type, _text(message, 1400), _json(detail),
        ),
    )


def record_remote_intent(
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None = None,
    action: str,
    intent_kind: str = "remote_write",
    request_id: str | None = None,
    detail: dict | None = None,
) -> dict:
    """Persist the start of a remote request before crossing the API boundary.

    ``remote_write`` checkpoints are lease-fenced.  The payload deliberately
    contains only an action, a caller-supplied correlation id and scrubbed
    metadata; credentials and full remote responses never belong here.
    """
    kind = str(intent_kind or "remote_write").strip().lower()
    if kind not in _REMOTE_INTENT_KINDS:
        raise ValueError(f"不支持的 remote intent 类型: {kind!r}")
    action_value = _text(action, 160).strip() or "remote_operation"
    request_value = _text(request_id, 240).strip() if request_id else ""
    safe_detail = _scrub(detail or {})
    with _connect() as conn, conn.cursor() as cur:
        run = _remote_checkpoint_fence(
            cur, int(run_id), execution_id=execution_id, lease_token=lease_token,
            require_lease=kind == "remote_write",
        )
        previous_intent = _remote_write_checkpoint(run.get("data"))
        previous_receipt = str(
            previous_intent.get("receipt_state") or previous_intent.get("state") or "started"
        )
        if previous_intent and previous_receipt not in {"confirmed", "rejected"}:
            raise ValueError("前一个远端写请求尚未核验，不能覆盖其 checkpoint")
        intent = {
            "action": action_value,
            "kind": kind,
            "state": "started",
            "receipt_state": "started",
            "started_at": _now().isoformat(),
        }
        if request_value:
            intent["request_id"] = request_value
        if safe_detail:
            intent["detail"] = safe_detail
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')}
            SET data=data || %s::jsonb, heartbeat_at=now()
            WHERE id=%s AND execution_id=%s
            RETURNING *
            """,
            (_json({"remote_intent": intent}), int(run_id), str(execution_id)),
        )
        updated = dict(cur.fetchone())
        _remote_checkpoint_event(
            cur, updated,
            event_type="remote.request_started",
            message=f"远端请求边界已记录：{action_value}",
            detail={
                "action": action_value,
                "intent_kind": kind,
                "request_id": request_value or None,
                "execution_id": str(execution_id),
            },
        )
    return _row(updated) or {}


def record_remote_receipt(
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None = None,
    outcome: str | None = None,
    receipt_state: str | None = None,
    action: str | None = None,
    request_id: str | None = None,
    detail: dict | None = None,
) -> dict:
    """Persist a remote response without closing the Run.

    ``response_received`` (with ``received``/``response_observed``/``accepted``
    aliases) means only that an HTTP response was observed.  A positive
    response whose local writeback has not completed is represented by
    ``local_commit_required``.  ``confirmed`` is accepted only when the caller
    explicitly proves remote confirmation, local business writeback, and a
    local readback.  A crash before :func:`finish_run` still requires
    reconciliation for every non-rejected write checkpoint, including
    ``confirmed``; the receipt never makes a Run terminal by itself.
    """
    outcome_value = str(receipt_state or outcome or "unknown").strip().lower()
    outcome_value = {
        "received": "response_received",
        "response_observed": "response_received",
        "accepted": "response_received",
    }.get(outcome_value, outcome_value)
    if outcome_value not in _REMOTE_RECEIPT_OUTCOMES:
        raise ValueError(f"不支持的 remote receipt outcome: {outcome_value!r}")
    action_value = _text(action, 160).strip() if action else ""
    request_value = _text(request_id, 240).strip() if request_id else ""
    raw_detail = dict(detail or {})
    if outcome_value == "confirmed":
        def _confirmed_marker(*names: str) -> bool:
            for name in names:
                value = raw_detail.get(name)
                if value is True:
                    return True
                if isinstance(value, str) and value.strip().lower() in {
                    "1", "true", "yes", "confirmed",
                }:
                    return True
            return False

        if not _confirmed_marker(
            "remote_result_confirmed", "remote_response_confirmed", "remote_confirmed",
        ):
            raise ValueError(
                "confirmed receipt 必须明确 remote_result_confirmed=true"
            )
        if not _confirmed_marker(
            "local_business_writeback_confirmed", "local_writeback_confirmed",
            "local_commit_confirmed",
        ):
            raise ValueError(
                "confirmed receipt 必须明确 local_business_writeback_confirmed=true"
            )
        if not _confirmed_marker("local_readback_confirmed", "local_readback"):
            raise ValueError(
                "confirmed receipt 必须明确 local_readback_confirmed=true"
            )
    safe_detail = _scrub(raw_detail)
    with _connect() as conn, conn.cursor() as cur:
        run = _remote_checkpoint_fence(
            cur, int(run_id), execution_id=execution_id, lease_token=lease_token,
            require_lease=False,
        )
        data = _decode(run.get("data"))
        data = dict(data) if isinstance(data, dict) else {}
        intent = data.get("remote_intent")
        if not isinstance(intent, dict):
            raise ValueError("remote receipt 缺少对应的 remote_request_started")
        intent = dict(intent)
        if intent.get("kind") == "remote_write" and not str(lease_token or "").strip():
            raise PermissionError("remote write receipt 必须持有账号 lease")
        intent_action = str(intent.get("action") or "")
        if action_value and intent_action and action_value != intent_action:
            raise ValueError("remote receipt action 与 intent 不匹配")
        action_value = action_value or intent_action or "remote_operation"
        if request_value and intent.get("request_id") and request_value != str(intent["request_id"]):
            raise ValueError("remote receipt request_id 与 intent 不匹配")
        if not request_value:
            request_value = str(intent.get("request_id") or "")
        if intent.get("receipt_state") == "confirmed" and outcome_value != "confirmed":
            raise ValueError("已确认的远端写回执不能降级或改为 rejected")
        intent["state"] = outcome_value
        intent["receipt_state"] = outcome_value
        intent["receipt_at"] = _now().isoformat()
        receipt = {
            "action": action_value,
            "outcome": outcome_value,
            "receipt_state": outcome_value,
            "received_at": _now().isoformat(),
        }
        if request_value:
            receipt["request_id"] = request_value
        if safe_detail:
            receipt["detail"] = safe_detail
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')}
            SET data=data || %s::jsonb, heartbeat_at=now()
            WHERE id=%s AND execution_id=%s
            RETURNING *
            """,
            (
                _json({"remote_intent": intent, "remote_receipt": receipt}),
                int(run_id), str(execution_id),
            ),
        )
        updated = dict(cur.fetchone())
        _remote_checkpoint_event(
            cur, updated,
            event_type=(
                "remote.receipt_unknown"
                if outcome_value == "unknown" else "remote.receipt_received"
            ),
            message=(
                f"远端请求回执待核验：{action_value}"
                if outcome_value == "unknown"
                else f"已记录远端请求回执：{action_value}/{outcome_value}"
            ),
            detail={
                "action": action_value,
                "outcome": outcome_value,
                "request_id": request_value or None,
                "execution_id": str(execution_id),
            },
        )
    return _row(updated) or {}


def heartbeat_run(run_id: int, lease_token: str = "", *, ttl_seconds: int = 600) -> bool:
    init()
    ttl = max(60, min(24 * 60 * 60, int(ttl_seconds or 600)))
    with _connect() as conn, conn.cursor() as cur:
        token = str(lease_token or "").strip()
        if token:
            cur.execute(
                f"""
                UPDATE {_table('operation_runs')} AS run
                SET heartbeat_at=now()
                WHERE run.id=%s AND run.status IN ('running','cancelling','settling')
                  AND EXISTS (
                      SELECT 1 FROM {_table('account_operation_leases')} lease
                      WHERE lease.run_id=run.id AND lease.lease_token=%s
                        AND lease.expires_at > now()
                  )
                """,
                (int(run_id), token),
            )
            changed = cur.rowcount > 0
            if changed:
                cur.execute(
                    f"""
                    UPDATE {_table('account_operation_leases')}
                    SET heartbeat_at=now(), expires_at=now() + (%s * interval '1 second')
                    WHERE run_id=%s AND lease_token=%s AND expires_at > now()
                    """,
                    (ttl, int(run_id), token),
                )
                changed = cur.rowcount > 0
            return changed
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')}
            SET heartbeat_at=now()
            WHERE id=%s AND account_id IS NULL
              AND status IN ('running','cancelling','settling')
            """,
            (int(run_id),),
        )
        return cur.rowcount > 0


def acquire_account_lease(
    *, account_id: int, run_id: int, resource_family: str = "openai_interactive",
    ttl_seconds: int = 600,
) -> str | None:
    init()
    lease_token = uuid.uuid4().hex
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT status, account_id, resource_family
            FROM {_table('operation_runs')}
            WHERE id=%s
            FOR UPDATE
            """,
            (int(run_id),),
        )
        run = cur.fetchone()
        if not run or str(run.get("status") or "") not in {"running", "cancelling", "settling"}:
            return None
        if int(run.get("account_id") or 0) != int(account_id):
            return None
        if str(run.get("resource_family") or "openai_interactive") != str(resource_family):
            return None
        cur.execute(
            f"DELETE FROM {_table('account_operation_leases')} WHERE expires_at < now()",
        )
        cur.execute(
            f"""
            INSERT INTO {_table('account_operation_leases')} (
                account_id, resource_family, run_id, lease_token, expires_at
            ) VALUES (%s, %s, %s, %s, now() + (%s * interval '1 second'))
            ON CONFLICT (account_id, resource_family) DO NOTHING
            RETURNING lease_token
            """,
            (int(account_id), str(resource_family), int(run_id), lease_token, max(60, int(ttl_seconds))),
        )
        row = cur.fetchone()
        return str(row["lease_token"]) if row else None


def release_account_lease(run_id: int, lease_token: str = "") -> bool:
    init()
    with _connect() as conn, conn.cursor() as cur:
        if lease_token:
            cur.execute(
                f"DELETE FROM {_table('account_operation_leases')} WHERE run_id=%s AND lease_token=%s",
                (int(run_id), str(lease_token)),
            )
        else:
            cur.execute(
                f"DELETE FROM {_table('account_operation_leases')} WHERE run_id=%s",
                (int(run_id),),
            )
        return cur.rowcount > 0


def request_run_cancel(run_id: int, *, reason: str = "用户手动停止") -> dict:
    """协作式取消：排队任务立即取消；运行任务进入 cancelling 等待检查点收口。"""
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {_table('operation_runs')} WHERE id=%s FOR UPDATE",
            (int(run_id),),
        )
        run = cur.fetchone()
        if not run:
            raise LookupError("执行实例不存在")
        status = str(run.get("status") or "")
        if status in _TERMINAL_STATUSES:
            return _row(dict(run)) or {}
        target = "cancelled" if status == "queued" else "cancelling"
        completed_sql = ", completed_at=now()" if target == "cancelled" else ""
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')}
            SET status=%s, cancel_requested_at=COALESCE(cancel_requested_at, now()),
                cancel_reason=%s, heartbeat_at=now(){completed_sql}
            WHERE id=%s RETURNING *
            """,
            (target, _text(reason, 500), int(run_id)),
        )
        updated = dict(cur.fetchone())
        task_status = "cancelled" if target == "cancelled" else "cancelling"
        task_stage = "complete" if target == "cancelled" else "cancelling"
        cur.execute(
            f"""
            UPDATE {_table('operation_tasks')}
            SET status=%s, current_stage=%s, updated_at=now(),
                completed_at=CASE WHEN %s='cancelled' THEN now() ELSE completed_at END
            WHERE id=%s
            """,
            (task_status, task_stage, task_status, int(run["task_id"])),
        )
        cur.execute(
            f"UPDATE {_table('account_operation_leases')} SET cancel_requested_at=now() WHERE run_id=%s",
            (int(run_id),),
        )
        event_uuid = uuid.uuid4().hex
        cur.execute(
            f"""
            INSERT INTO {_table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s, %s, %s, %s, %s,
                      'WARNING', %s, 'run.cancel_requested', %s, %s::jsonb)
            """,
            (
                event_uuid, int(run["task_id"]), int(run_id),
                str(run.get("source_system") or "native_operations"), event_uuid,
                task_stage, _text(reason, 1400),
                _json({"previous_status": status, "status": target}),
            ),
        )
        if run.get("batch_id"):
            _refresh_batches(cur, [int(run["batch_id"])])
        return _row(updated) or {}


def is_run_cancel_requested(run_id: int, cancellation_token: str = "") -> bool:
    init()
    with _connect() as conn, conn.cursor() as cur:
        params: list[Any] = [int(run_id)]
        token_clause = ""
        if cancellation_token:
            token_clause = " AND cancellation_token=%s"
            params.append(str(cancellation_token))
        cur.execute(
            f"""
            SELECT cancel_requested_at IS NOT NULL OR status IN ('cancelling','cancelled') AS requested
            FROM {_table('operation_runs')} WHERE id=%s{token_clause}
            """,
            params,
        )
        row = cur.fetchone()
        return not row or bool(row["requested"])


def mark_run_settling(run_id: int) -> bool:
    """Callback 已交给远端后进入有界对账阶段；保留 cancel_requested_at。"""
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_runs')}
            SET status='settling', settling_at=COALESCE(settling_at, now()),
                progress_stage='credential_confirm', heartbeat_at=now()
            WHERE id=%s AND status IN ('running', 'cancelling')
            RETURNING task_id
            """,
            (int(run_id),),
        )
        row = cur.fetchone()
        if not row:
            return False
        cur.execute(
            f"""
            UPDATE {_table('operation_tasks')}
            SET status='settling', current_stage='credential_confirm', updated_at=now()
            WHERE id=%s
            """,
            (int(row["task_id"]),),
        )
        return True


def register_resource(
    run_id: int, *, resource_type: str, provider: str = "", external_id: str = "",
    detail: dict | None = None,
) -> dict:
    init()
    resource_uuid = uuid.uuid4().hex
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {_table('operation_resources')} (
                resource_uuid, run_id, resource_type, provider, external_id, detail
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (run_id, resource_type, external_id) DO UPDATE
            SET state='acquired', released_at=NULL, detail=EXCLUDED.detail
            RETURNING *
            """,
            (
                resource_uuid, int(run_id), str(resource_type), str(provider),
                _text(external_id, 300), _json(detail or {}),
            ),
        )
        return _row(dict(cur.fetchone())) or {}


def release_resource(resource_id: int, *, state: str = "released", detail: dict | None = None) -> bool:
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_table('operation_resources')}
            SET state=%s, released_at=now(),
                detail=CASE WHEN %s::jsonb = '{{}}'::jsonb THEN detail ELSE detail || %s::jsonb END
            WHERE id=%s
            """,
            (str(state), _json(detail or {}), _json(detail or {}), int(resource_id)),
        )
        return cur.rowcount > 0


def finish_run(
    run_id: int,
    *,
    status: str,
    message: str = "",
    result_summary: dict | None = None,
    error: str | None = None,
    execution_id: str | None = None,
    lease_token: str | None = None,
) -> dict:
    init()
    status_value = _status(status)
    if status_value not in _TERMINAL_STATUSES:
        raise ValueError(f"非法终态: {status_value}")
    parent_task_id: int | None = None
    dependency_result = dict(result_summary or {})
    idempotent = False
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.task_type, t.parent_task_id, t.email_snapshot, t.trigger
            FROM {_table('operation_runs')} r
            JOIN {_table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=%s
            FOR UPDATE OF r
            """,
            (int(run_id),),
        )
        found = cur.fetchone()
        if not found:
            raise LookupError("执行实例不存在")
        found = dict(found)
        parent_task_id = int(found["parent_task_id"]) if found.get("parent_task_id") else None
        if execution_id and str(found.get("execution_id") or "") != str(execution_id):
            raise PermissionError("执行实例 fence 不匹配，拒绝覆盖其他 worker 的结果")
        if lease_token:
            cur.execute(
                f"""
                SELECT 1 FROM {_table('account_operation_leases')}
                WHERE run_id=%s AND lease_token=%s AND expires_at > now()
                """,
                (int(run_id), str(lease_token)),
            )
            if not cur.fetchone():
                raise PermissionError("账号 lease owner 不匹配，拒绝写入结果")
        if str(found.get("status") or "") in _TERMINAL_STATUSES:
            result = _row(found) or {}
            idempotent = True
        else:
            intent = _remote_write_checkpoint(found.get("data"))
            receipt = str(intent.get("receipt_state") or intent.get("state") or "started")
            if intent and receipt != "rejected" and (
                status_value != "success" or receipt != "confirmed"
            ):
                # Exceptions/cancellation after the request boundary must not
                # evade crash recovery by becoming a retryable terminal Run.
                # Even a confirmed write followed by another failure needs a
                # follow-up, not replay of the already completed remote write.
                dependency_result.update({
                    "outcome": "request_unknown",
                    "reconcile_required": True,
                    "requested_status": status_value,
                    "remote_action": intent.get("action"),
                    "remote_intent_state": receipt,
                })
                status_value = "attention_required"
                error = "远端写请求尚未完成整条任务核验，禁止直接重试" + (
                    f"：{error}" if error else ""
                )
                message = error
            task_type = str(found.get("task_type") or "")
            category, code, error_message = _error_fields(
                error or "", stage="complete", task_type=task_type,
            )
            cur.execute(
                f"""
                UPDATE {_table('operation_runs')}
            SET status=%s, completed_at=now(), heartbeat_at=now(), progress_stage='complete',
                duration_ms=GREATEST(0, (EXTRACT(EPOCH FROM (now() - COALESCE(started_at, created_at))) * 1000)::BIGINT),
                error_category=%s, error_code=%s, error_message=%s, result_summary=%s::jsonb
                WHERE id=%s RETURNING *
                """,
                (status_value, category, code, error_message, _json(dependency_result), int(run_id)),
            )
            run = dict(cur.fetchone())
            target_status = {
                "success": "credential_valid" if task_type == "codex_retry" else "completed",
                "attention_required": "credential_pending_confirmation" if task_type == "codex_retry" else "attention_required",
                "deactivated": "account_deactivated",
                "cancelled": "cancelled",
                "stopped": "cancelled",
            }.get(status_value, "failed")
            cur.execute(
                f"""
                UPDATE {_table('operation_tasks')}
                SET status=%s, target_status=%s, current_stage='complete', updated_at=now(),
                    completed_at=now(), error_category=%s, error_code=%s, error_message=%s,
                    next_actions=%s::jsonb
                WHERE id=%s AND last_run_id=%s
                """,
                (
                    status_value, target_status, category, code, error_message,
                    _json(
                        [] if status_value == "success" else
                        [{"action": "reconcile", "label": "确认远端结果后继续"}]
                        if status_value == "attention_required"
                        and str(dependency_result.get("outcome") or "") == "request_unknown"
                        else [{"action": "retry", "label": "重新执行"}]
                    ),
                    int(run["task_id"]), int(run_id),
                ),
            )
            event_uuid = uuid.uuid4().hex
            final_message = message or error_message or {
                "success": "Codex 凭证已确认并保存",
                "attention_required": "OAuth callback 已提交，凭证仍待确认",
                "cancelled": "执行已在安全检查点取消",
                "deactivated": "账号已确认不可用",
            }.get(status_value, f"执行结束：{status_value}")
            cur.execute(
                f"""
                INSERT INTO {_table('operation_events')} (
                    event_uuid, task_id, run_id, source_system, source_id,
                    level, stage, event_type, error_category, error_code, message, detail
                ) VALUES (%s, %s, %s, %s, %s, %s, 'complete', %s,
                          %s, %s, %s, %s::jsonb)
                """,
                (
                    event_uuid, int(run["task_id"]), int(run_id),
                    str(run.get("source_system") or "native_operations"), event_uuid,
                    "INFO" if status_value == "success" else "WARNING",
                    f"run.{status_value}", category, code, _text(final_message, 1400),
                    _json({"status": status_value}),
                ),
            )
            cur.execute(
                f"""
                UPDATE {_table('operation_resources')}
                SET state='reconciliation_required',
                    detail=detail || %s::jsonb
                WHERE run_id=%s AND state='acquired'
                """,
                (_json({"terminal_run_status": status_value}), int(run_id)),
            )
            cur.execute(f"DELETE FROM {_table('account_operation_leases')} WHERE run_id=%s", (int(run_id),))
            if run.get("batch_id"):
                _refresh_batches(cur, [int(run["batch_id"])])
            result = _row(run) or {}
            result["task_type"] = task_type
            result["parent_task_id"] = parent_task_id
        if parent_task_id:
            # Child terminal state is reflected in the same transaction.  The
            # helper is idempotent and also works when finish_run is retried.
            _reconcile_parent_task_cur(cur, parent_task_id, child_task_id=int(found["task_id"]))
    task_run_log.append(
        result.get("log_file"),
        level="INFO" if str(result.get("status") or status_value) == "success" else "WARNING",
        message=message or result.get("error_message") or f"执行结束：{result.get('status') or status_value}",
        task_id=int(result["task_id"]),
        run_id=int(run_id),
        stage="complete",
        event_type=f"run.{result.get('status') or status_value}",
        fields={"status": result.get("status") or status_value, "idempotent": idempotent},
    )
    try:
        ready_dependencies = mark_task_dependency_ready(
            child_source_system=str(result.get("source_system") or "native_operations"),
            child_source_id=str(result["task_id"]),
            child_status=str(result.get("status") or status_value),
            child_result=dependency_result,
        )
        if ready_dependencies:
            from core.operations import task_gateway

            for dependency in ready_dependencies:
                task_gateway.notify_dependency_ready(dependency)
    except Exception:
        # A dependency projection is a follow-up; never turn a completed
        # remote operation into a failure merely because its wakeup failed.
        logger.exception("写入父任务依赖 ready 状态失败：run_id=%s", run_id)
    return result


def verify() -> dict[str, Any]:
    """返回迁移不变量；ok=False 时不得切换生产 UI。"""
    init()
    with _connect() as conn, conn.cursor() as cur:
        checks: dict[str, int] = {}
        queries = {
            "legacy_registration_jobs": f"SELECT COUNT(*) FROM {postgres_store.qualified('registration_jobs')}",
            "mapped_registration_runs": f"SELECT COUNT(*) FROM {_table('operation_runs')} WHERE source_system='registration_jobs'",
            "legacy_account_tasks": f"SELECT COUNT(*) FROM {_table('account_action_tasks')}",
            "mapped_account_runs": f"SELECT COUNT(*) FROM {_table('operation_runs')} WHERE source_system='account_action_tasks'",
            "legacy_account_events": f"SELECT COUNT(*) FROM {_table('account_action_events')}",
            "mapped_account_events": f"SELECT COUNT(*) FROM {_table('operation_events')} WHERE source_system='account_action_events'",
            "orphan_runs": f"SELECT COUNT(*) FROM {_table('operation_runs')} r LEFT JOIN {_table('operation_tasks')} t ON t.id=r.task_id WHERE t.id IS NULL",
            "orphan_events": f"SELECT COUNT(*) FROM {_table('operation_events')} e LEFT JOIN {_table('operation_tasks')} t ON t.id=e.task_id WHERE t.id IS NULL",
            "duplicate_active_account_families": f"SELECT COUNT(*) FROM (SELECT account_id, resource_family FROM {_table('operation_runs')} WHERE account_id IS NOT NULL AND status IN ('queued','running','cancelling','settling','waiting') GROUP BY account_id, resource_family HAVING COUNT(*) > 1) AS duplicates",
            "terminal_run_leases": f"SELECT COUNT(*) FROM {_table('account_operation_leases')} lease JOIN {_table('operation_runs')} run ON run.id=lease.run_id WHERE run.status NOT IN ('queued','running','cancelling','settling','waiting')",
            "terminal_acquired_resources": f"SELECT COUNT(*) FROM {_table('operation_resources')} resource JOIN {_table('operation_runs')} run ON run.id=resource.run_id WHERE run.status NOT IN ('queued','running','cancelling','settling','waiting') AND resource.state='acquired'",
            "projection_queue_invalid_status": f"SELECT COUNT(*) FROM {_table('operation_projection_queue')} WHERE status NOT IN ('queued','running','succeeded','failed')",
            "projection_queue_orphans": f"SELECT COUNT(*) FROM {_table('operation_projection_queue')} q LEFT JOIN {_table('operation_batches')} b ON b.id=q.batch_id WHERE b.id IS NULL",
        }
        for key, sql in queries.items():
            cur.execute(sql)
            checks[key] = int(cur.fetchone()["count"])
        cur.execute(
            f"SELECT COUNT(*) FROM {_table('registration_attempts')} WHERE target_status='email_verification_pending'"
        )
        checks["pending_email_verification_attempts"] = int(cur.fetchone()["count"])
    ok = (
        checks["legacy_registration_jobs"] == checks["mapped_registration_runs"]
        and checks["legacy_account_tasks"] == checks["mapped_account_runs"]
        and checks["legacy_account_events"] == checks["mapped_account_events"]
        and checks["orphan_runs"] == 0
        and checks["orphan_events"] == 0
        and checks["duplicate_active_account_families"] == 0
        and checks["terminal_run_leases"] == 0
        and checks["terminal_acquired_resources"] == 0
        and checks["projection_queue_invalid_status"] == 0
        and checks["projection_queue_orphans"] == 0
    )
    return {"ok": ok, "checks": checks}
