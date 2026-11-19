# -*- coding: utf-8 -*-
"""旧模型事实映射、批次统计与持久投影队列。队列锁、批次锁和线程状态由本模块统一拥有。"""
from __future__ import annotations

import logging
import json
import os
import threading
import time
from datetime import timedelta
from typing import Any, Iterable
from core.storage import postgres as postgres_store, records as record_store
from core.runtime.periodic import StopBudget, join_stopped
from core.operations import run_log as task_run_log
from core.operations.errors import REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES
from core.operations.stages import normalize_stage, normalize_step_state
from core.storage.operations import common as _common
from core.storage.operations import schema as _schema

logger = logging.getLogger('core.storage.operation')

_PROJECTION_WORKER_LOCK = threading.Lock()


_PROJECTION_STOP = threading.Event()


_PROJECTION_WAKE = threading.Event()


_PROJECTION_WORKER: threading.Thread | None = None


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
        INSERT INTO {_common._table('operation_batches')} (
            batch_uuid, source_system, source_id, batch_type, title, requested_count,
            created_by, created_at, completed_at, data
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            batch_type=EXCLUDED.batch_type, title=EXCLUDED.title,
            requested_count=GREATEST({_common._table('operation_batches')}.requested_count, EXCLUDED.requested_count),
            created_at=EXCLUDED.created_at,
            completed_at=COALESCE(EXCLUDED.completed_at, {_common._table('operation_batches')}.completed_at),
            data={_common._table('operation_batches')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            _common._uuid("batch", f"{source_system}:{source_id}"), source_system, source_id,
            batch_type, _common._text(title, 240), max(0, int(requested_count or 0)), created_by,
            created_at or _common._now(), completed_at, _common._json(data or {}),
        ),
    )
    return int(cur.fetchone()["id"])


def _upsert_attempt(cur, *, root_job_id: int, job: dict, account: dict | None) -> int:
    state = _common._account_state(account)
    extra = _common._account_extra(account)
    raw_checkpoint = str(extra.get("registration_checkpoint") or "").strip().lower()
    attempt_data = {"legacy_root_job_id": root_job_id}
    if raw_checkpoint in _common._LEGACY_REGISTRATION_CHECKPOINT_MAP:
        attempt_data.update({
            "legacy_registration_checkpoint": raw_checkpoint,
            "legacy_checkpoint": raw_checkpoint,
            "checkpoint_migration": {
                "from": raw_checkpoint,
                "to": _common._LEGACY_REGISTRATION_CHECKPOINT_MAP[raw_checkpoint],
                "source": "operation_projection",
            },
        })
    cur.execute(
        f"""
        INSERT INTO {_common._table('registration_attempts')} (
            attempt_uuid, source_root_job_id, email_snapshot, account_id, checkpoint,
            remote_identity_state, remote_account_state, local_account_state, target_status,
            created_at, updated_at, completed_at, data
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_root_job_id) DO UPDATE SET
            email_snapshot=CASE WHEN EXCLUDED.email_snapshot <> '' THEN EXCLUDED.email_snapshot
                ELSE {_common._table('registration_attempts')}.email_snapshot END,
            account_id=COALESCE(EXCLUDED.account_id, {_common._table('registration_attempts')}.account_id),
            checkpoint=CASE WHEN COALESCE(array_position(ARRAY['created','email_claimed','auth_started','password_request_started','password_confirmed','otp_started','otp_confirmed','account_request_started','account_confirmed','token_obtained','core_persisted','postprocessing','completed','manual_reconcile','failed']::text[], {_common._table('registration_attempts')}.checkpoint), 0) >= COALESCE(array_position(ARRAY['created','email_claimed','auth_started','password_request_started','password_confirmed','otp_started','otp_confirmed','account_request_started','account_confirmed','token_obtained','core_persisted','postprocessing','completed','manual_reconcile','failed']::text[], EXCLUDED.checkpoint), 0) THEN {_common._table('registration_attempts')}.checkpoint ELSE EXCLUDED.checkpoint END,
            remote_identity_state=CASE WHEN
                {_common._table('registration_attempts')}.remote_identity_state='confirmed'
                AND EXCLUDED.remote_identity_state<>'confirmed'
                THEN {_common._table('registration_attempts')}.remote_identity_state
                WHEN {_common._table('registration_attempts')}.remote_identity_state='request_unknown'
                AND EXCLUDED.remote_identity_state IN ('unknown','','not_started')
                THEN {_common._table('registration_attempts')}.remote_identity_state
                WHEN EXCLUDED.remote_identity_state IN ('unknown','')
                THEN {_common._table('registration_attempts')}.remote_identity_state
                ELSE EXCLUDED.remote_identity_state END,
            remote_account_state=CASE WHEN
                {_common._table('registration_attempts')}.remote_account_state='confirmed'
                AND EXCLUDED.remote_account_state<>'confirmed'
                THEN {_common._table('registration_attempts')}.remote_account_state
                WHEN {_common._table('registration_attempts')}.remote_account_state='request_unknown'
                AND EXCLUDED.remote_account_state IN ('unknown','','not_started')
                THEN {_common._table('registration_attempts')}.remote_account_state
                WHEN EXCLUDED.remote_account_state IN ('unknown','')
                THEN {_common._table('registration_attempts')}.remote_account_state
                ELSE EXCLUDED.remote_account_state END,
            local_account_state=CASE WHEN {_common._table('registration_attempts')}.local_account_state IN ('persisted','saved') AND EXCLUDED.local_account_state IN ('missing','checkpoint_saved') THEN {_common._table('registration_attempts')}.local_account_state ELSE EXCLUDED.local_account_state END,
            -- 永久失效是不可逆事实。兼容任务同步时没有 account 行，不能把
            -- 已停用 Attempt 回写成 not_created 并重新开放注册重试。
            target_status=CASE
                WHEN {_common._table('registration_attempts')}.target_status='deactivated'
                THEN {_common._table('registration_attempts')}.target_status
                WHEN {_common._table('registration_attempts')}.target_status='request_unknown'
                    AND (
                        %s NOT IN ('success','partial_success')
                        OR EXCLUDED.target_status IN ('not_created','attention_required','request_unknown')
                    )
                THEN {_common._table('registration_attempts')}.target_status
                ELSE EXCLUDED.target_status END,
            updated_at=EXCLUDED.updated_at,
            completed_at=COALESCE(EXCLUDED.completed_at, {_common._table('registration_attempts')}.completed_at),
            data={_common._table('registration_attempts')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            _common._uuid("attempt", root_job_id), root_job_id,
            str((account or {}).get("email") or job.get("email") or "")[:320],
            int(account["id"]) if account and account.get("id") is not None else None,
            state["checkpoint"], state["remote_identity_state"], state["remote_account_state"],
            state["local_account_state"], state["target_status"],
            _common._legacy_registration_timestamp(job.get("created_at")) or _common._now(),
            _common._legacy_registration_timestamp(job.get("updated_at"))
            or _common._legacy_registration_timestamp(job.get("completed_at")) or _common._now(),
            _common._legacy_registration_timestamp(job.get("completed_at"))
            if state["target_status"] == "account_available" else None,
            _common._json(attempt_data), _common._status(job.get("status")),
        ),
    )
    return int(cur.fetchone()["id"])


def _registration_task_type(job: dict) -> str:
    value = str(job.get("job_type") or "registration").strip().lower()
    return value if value in {"registration", "registration_resume", "codex_retry", "twofa_retry"} else "registration"


def _next_registration_actions(
    job: dict,
    account: dict | None,
    target_status: str,
    *,
    remote_identity_state: str = "not_started",
    remote_account_state: str = "not_started",
) -> list[dict[str, Any]]:
    if str(target_status or "").strip().lower() in {
        "request_unknown", "attention_required", "manual_reconcile",
    }:
        return []
    if _common._status(job.get("status")) not in _common._TERMINAL_STATUSES:
        return []
    if str(target_status or "").strip().lower() == "deactivated" or _common._account_is_deactivated(account):
        return []
    source_job_id = int(job.get("id") or 0)
    if target_status == "email_verification_pending":
        return [{"action": "registration_resume", "label": "继续邮箱验证", "source_job_id": source_job_id}]
    if not account:
        if remote_identity_state in {"confirmed", "request_unknown"} or remote_account_state in {
            "confirmed", "request_unknown",
        }:
            return []
        return [{"action": "registration_retry", "label": "重新执行注册", "source_job_id": source_job_id}]
    snapshot = job.get("config_snapshot")
    if not isinstance(snapshot, dict):
        raw_data = job.get("data")
        snapshot = raw_data.get("config_snapshot") if isinstance(raw_data, dict) else None
    has_snapshot = isinstance(snapshot, dict)
    codex_enabled = bool(snapshot.get("codex_enabled", True)) if has_snapshot else True
    if codex_enabled and str(account.get("codex_status") or "") != "success":
        return [{"action": "codex_retry", "label": "补跑 Codex", "source_job_id": source_job_id}]
    extra = _common._account_extra(account)
    missing_setup = False
    from core.accounts.password_evidence import password_is_confirmed

    if (not has_snapshot or bool(snapshot.get("password_enabled", True))) and not password_is_confirmed(account):
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
        f"SELECT id FROM {_common._table('operation_tasks')} WHERE source_system=%s AND source_id=%s",
        (source_system, source_id),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


def _registration_run_cause_summary(cur, job_id: int, *, job_status: str) -> dict[str, Any]:
    """只投影 RegistrationRun 中已持久化的固定原因事实。"""
    if job_status not in {"request_unknown", "failed"}:
        return {}
    # 旧任务可早于 RegistrationRun 表，缺少原因事实时保持原失败投影。
    cur.execute("SELECT to_regclass(%s) AS name", (f"{_common._schema_name()}.registration_runs",))
    if not cur.fetchone()["name"]:
        return {}
    cur.execute(
        f"SELECT status, result_summary FROM {_common._table('registration_runs')} WHERE job_id=%s",
        (int(job_id),),
    )
    row = cur.fetchone()
    if not row or str(row.get("status") or "") not in {"request_unknown", "failed"}:
        return {}
    source = _common._decode(row.get("result_summary"))
    source = source if isinstance(source, dict) else {}
    if str(row.get("status") or "") == "failed" and source.get("outcome") != "request_unknown":
        return {}
    safe: dict[str, Any] = {"outcome": "request_unknown"}
    cause_code = source.get("cause_code")
    if isinstance(cause_code, str) and cause_code in REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES:
        safe["cause_code"] = cause_code
    if type(source.get("register_response_confirmed")) is bool:
        safe["register_response_confirmed"] = source["register_response_confirmed"]
    return safe


def _upsert_registration_job(cur, job: dict, accounts_by_id: dict[int, dict], accounts_by_email: dict[str, dict]) -> int:
    job_id = int(job["id"])
    root_job_id = int(job.get("root_job_id") or job_id)
    task_type = _registration_task_type(job)
    task_source_id = f"{root_job_id}:{task_type}"
    task_table = _common._table("operation_tasks")
    account = None
    if job.get("account_id") is not None:
        account = accounts_by_id.get(int(job["account_id"]))
    if account is None and job.get("email"):
        account = accounts_by_email.get(str(job.get("email") or "").strip().lower())
    attempt_id = _upsert_attempt(cur, root_job_id=root_job_id, job=job, account=account)
    # Attempt 是已确认远端事实的来源。兼容旧 job 的 account=None 推断
    # 不能覆盖 confirmed/request_unknown/deactivated 等持久化状态。
    cur.execute(
        f"""SELECT checkpoint, remote_identity_state, remote_account_state,
                   local_account_state, target_status
              FROM {_common._table('registration_attempts')} WHERE id=%s""",
        (attempt_id,),
    )
    persisted_attempt = cur.fetchone()
    state = dict(persisted_attempt) if persisted_attempt else _common._account_state(account)
    projection_data = {
        "legacy_root_job_id": root_job_id,
        "latest_legacy_job_id": job_id,
        # 线路号属于本次 Run 的上下文；投影器据此隔离晚到的旧线路事件。
        "route_attempt_no": max(1, int(job.get("route_attempt_no") or 1)),
        "selected_route_attempt_no": max(1, int(job.get("route_attempt_no") or 1)),
    }
    if isinstance(job.get("config_snapshot"), dict):
        projection_data["config_snapshot"] = dict(job["config_snapshot"])
    cur.execute(
        f"UPDATE {postgres_store.qualified('registration_jobs')} SET attempt_id=%s WHERE id=%s",
        (attempt_id, job_id),
    )
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
            created_at=_common._legacy_registration_timestamp(job.get("created_at")),
            data={"legacy_batch_id": legacy_batch_id, "workers": job.get("batch_workers")},
        )
    parent_task_id = None
    if task_type != "registration":
        parent_task_id = _lookup_task(cur, "registration_chains", f"{root_job_id}:registration")
    status = _common._status(job.get("status"))
    safe_run_summary = _registration_run_cause_summary(cur, job_id, job_status=status)
    error_category, error_code, error_message = _common._error_fields(
        job.get("error_message"), stage=str(job.get("progress_stage") or ""), task_type=task_type,
        result_summary=safe_run_summary, task_status=status,
    )
    created_at = _common._legacy_registration_timestamp(job.get("created_at")) or _common._now()
    completed_at = (
        _common._legacy_registration_timestamp(job.get("completed_at"))
        if status in _common._TERMINAL_STATUSES else None
    )
    updated_at = _common._legacy_registration_timestamp(job.get("updated_at")) or completed_at or _common._now()
    started_at = _common._legacy_registration_timestamp(job.get("started_at"))
    source_system = "registration_chains"
    task_uuid = _common._uuid("task", f"{source_system}:{task_source_id}")
    next_actions = _next_registration_actions(
        job, account, state["target_status"],
        remote_identity_state=state["remote_identity_state"],
        remote_account_state=state["remote_account_state"],
    )
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_tasks')} (
            task_uuid, source_system, source_id, batch_id, parent_task_id, task_type,
            target_type, target_id, attempt_id, account_id, email_snapshot, requested_action,
            status, target_status, current_stage, next_actions, error_category, error_code,
            error_message, trigger, created_at, updated_at, completed_at, data
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            batch_id=COALESCE(EXCLUDED.batch_id, {_common._table('operation_tasks')}.batch_id),
            parent_task_id=COALESCE(EXCLUDED.parent_task_id, {_common._table('operation_tasks')}.parent_task_id),
            attempt_id=EXCLUDED.attempt_id,
            account_id=COALESCE(EXCLUDED.account_id, {_common._table('operation_tasks')}.account_id),
            email_snapshot=CASE WHEN EXCLUDED.email_snapshot <> '' THEN EXCLUDED.email_snapshot
                ELSE {_common._table('operation_tasks')}.email_snapshot END,
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
            status, state["target_status"], normalize_stage(job.get("progress_stage")), _common._json(next_actions),
            error_category, error_code, error_message,
            "manual_retry" if job.get("parent_job_id") else "manual",
            created_at, updated_at, completed_at,
            _common._json(projection_data),
        ),
    )
    task_id = int(cur.fetchone()["id"])
    if task_type == "registration":
        cur.execute(
            f"UPDATE {_common._table('operation_tasks')} SET root_task_id=id WHERE id=%s AND root_task_id IS NULL",
            (task_id,),
        )
        cur.execute(
            f"UPDATE {_common._table('registration_attempts')} SET root_task_id=%s WHERE id=%s",
            (task_id, attempt_id),
        )
    else:
        root_task_id = parent_task_id or task_id
        cur.execute(
            f"UPDATE {_common._table('operation_tasks')} SET root_task_id=%s WHERE id=%s",
            (root_task_id, task_id),
        )
    retry_attempt = int(job.get("retry_attempt") or 0)
    run_no = max(1, retry_attempt + 1)
    run_uuid = _common._uuid("run", f"registration_jobs:{job_id}")
    progress_steps = job.get("progress_steps") if isinstance(job.get("progress_steps"), dict) else {}
    cur.execute(
        f"SELECT id FROM {_common._table('operation_runs')} WHERE source_system='registration_jobs' AND source_id=%s",
        (str(job_id),),
    )
    existing_run = cur.fetchone()
    if existing_run:
        run_no_clause = "run_no=operation_runs.run_no,"
    else:
        cur.execute(f"SELECT COALESCE(MAX(run_no),0)+1 AS n FROM {_common._table('operation_runs')} WHERE task_id=%s", (task_id,))
        run_no = max(run_no, int(cur.fetchone()["n"]))
        run_no_clause = "run_no=EXCLUDED.run_no,"
    run_log_file = str(job.get("log_file") or "").strip() or task_run_log.build_path(
        task_uuid=task_uuid, run_no=run_no, run_uuid=run_uuid,
    )
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_runs')} (
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
            data={_common._table('operation_runs')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            run_uuid, task_id, run_no, str(job_id), status,
            str(job.get("job_uuid") or "") or None, normalize_stage(job.get("progress_stage")),
            _common._json(progress_steps), started_at, completed_at,
            _common._duration(started_at, completed_at), error_category, error_code,
            error_message, _common._json({
                "account_id": (account or {}).get("id"),
                "retry_action": job.get("retry_action"),
                **safe_run_summary,
            }),
            run_log_file, created_at,
            _common._json({
                "legacy_job_id": job_id,
                "parent_job_id": job.get("parent_job_id"),
                "route_attempt_no": max(1, int(job.get("route_attempt_no") or 1)),
                "selected_route_attempt_no": max(1, int(job.get("route_attempt_no") or 1)),
                "route_attempts": job.get("route_attempts") or [],
                "failure_stage": job.get("failure_stage"),
                **({"config_snapshot": dict(job["config_snapshot"])} if isinstance(job.get("config_snapshot"), dict) else {}),
            }),
        ),
    )
    run_id = int(cur.fetchone()["id"])
    for raw_stage, current_step in progress_steps.items():
        current_step = current_step if isinstance(current_step, dict) else {}
        transitions = [dict(item) for item in current_step.get("transitions") or [] if isinstance(item, dict)]
        if not transitions or current_step.get("transition_id") not in {item.get("transition_id") for item in transitions}:
            transitions.append(current_step)
        for raw_step in transitions:
            step = raw_step if isinstance(raw_step, dict) else {}
            stage = normalize_stage(raw_stage)
            state_value = str(step.get("state") or "pending")
            level = "ERROR" if state_value in {"failed", "stopped"} else "INFO"
            category, code, _ = _common._error_fields(
                step.get("detail") if level == "ERROR" else None, stage=stage, task_type=task_type,
            )
            transition_id = str(step.get("transition_id") or "")
            event_source_system = "registration_progress_events" if transition_id else "registration_progress"
            event_source_id = f"{job_id}:stage:{raw_stage}" + (f":{transition_id}" if transition_id else "")
            occurred_at = _common._registration_progress_occurrence(step, state_value)
            cur.execute(
                f"""
                INSERT INTO {_common._table('operation_events')} (
                    event_uuid, task_id, run_id, source_system, source_id, created_at, level,
                    stage, event_type, error_category, error_code, message, detail
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (source_system, source_id) DO UPDATE SET
                    task_id=EXCLUDED.task_id, run_id=EXCLUDED.run_id,
                    created_at=CASE WHEN EXCLUDED.detail->>'event_time_known'='true'
                                    THEN EXCLUDED.created_at ELSE {_common._table('operation_events')}.created_at END,
                    level=EXCLUDED.level, stage=EXCLUDED.stage, event_type=EXCLUDED.event_type,
                    error_category=EXCLUDED.error_category, error_code=EXCLUDED.error_code,
                    message=EXCLUDED.message, detail=EXCLUDED.detail
                """,
                (
                    transition_id or _common._uuid("event", f"registration_progress:{event_source_id}"), task_id, run_id,
                    event_source_system,
                    event_source_id,
                    occurred_at or _common._legacy_registration_timestamp(step.get("started_at"))
                    or updated_at or _common._now(),
                    level, stage, f"stage.{state_value}", category, code,
                    _common._text(step.get("detail") or state_value, 1200),
                    _common._json({
                        "state": state_value, "step_state": state_value, "raw_stage": raw_stage,
                        "started_at": step.get("started_at"), "completed_at": step.get("completed_at"),
                        "occurred_at": step.get("occurred_at"),
                        "event_time_known": occurred_at is not None,
                        "evidence": step.get("evidence") or "legacy_derived",
                        "route_attempt_no": step.get("route_attempt_no"),
                        "step_instance_id": step.get("step_instance_id") or step.get("transition_id"),
                    }),
                ),
            )
    # A retry shares the logical task with its parent.  An older sync callback
    # may arrive after the newer attempt has started, so selecting by run_no
    # alone can temporarily put the task back into a historical terminal state.
    # Prefer any active run first, then fall back to the newest terminal run.
    cur.execute(
        f"""
        SELECT id, run_no, source_id, status, progress_stage, data,
               error_category, error_code, error_message, completed_at
        FROM {_common._table('operation_runs')}
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
        [] if latest_status in _common._ACTIVE_RUN_STATUSES
        else _next_registration_actions(
            latest_job, account, state["target_status"],
            remote_identity_state=state["remote_identity_state"],
            remote_account_state=state["remote_account_state"],
        )
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
            _common._json(latest_next_actions),
            latest["id"], latest_status, latest["progress_stage"], latest["error_category"],
            latest["error_code"], latest["error_message"], latest["completed_at"],
            _common._json(latest_next_actions), task_id,
        ),
    )
    if task_type == "registration_resume" and (_common._decode(latest.get("data")) or {}).get("completion_handoff"):
        from core.storage.operations import registration_completion

        registration_completion.reconcile(cur, int(latest["id"]), enqueue_projection=False)
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
        created_at=_common._legacy_account_timestamp(batch.get("created_at")),
        completed_at=_common._legacy_account_timestamp(batch.get("completed_at")),
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
    status = _common._status(task.get("status"))
    category, code, error = _common._error_fields(
        task.get("error"), stage="complete", task_type=task_type,
        result_summary=task.get("result_summary"), task_status=status,
    )
    batch_id = batch_map.get(str(task.get("batch_id") or ""))
    account_id = int(task["account_id"]) if task.get("account_id") is not None else None
    account = (accounts_by_id or {}).get(account_id) if account_id is not None else None
    account_state = _common._account_state(account)
    account_deactivated = status == "deactivated" or _common._account_is_deactivated(account)
    target_status = "account_deactivated" if account_deactivated else account_state["target_status"]
    next_actions: list[dict[str, Any]] = []
    if target_status == "email_verification_pending" and account_id is not None:
        cur.execute(
            f"""
            SELECT next_actions FROM {_common._table('operation_tasks')}
            WHERE account_id=%s AND task_type='registration'
              AND target_status='email_verification_pending'
            ORDER BY id DESC LIMIT 1
            """,
            (account_id,),
        )
        registration_task = cur.fetchone()
        if registration_task:
            next_actions = _common._decode(registration_task["next_actions"]) or []
    elif status != "success" and not account_deactivated:
        next_actions = [{"action": "retry", "label": "重新执行", "source_task_id": legacy_id}]
    source_id = str(legacy_id)
    task_uuid = _common._uuid("task", f"account_action_tasks:{legacy_id}")
    run_uuid = _common._uuid("run", f"account_action_tasks:{legacy_id}")
    run_log_file = str(task.get("log_file") or "").strip() or task_run_log.build_path(
        task_uuid=task_uuid, run_no=1, run_uuid=run_uuid,
    )
    queued_at = _common._legacy_account_timestamp(task.get("queued_at")) or _common._now()
    started_at = _common._legacy_account_timestamp(task.get("started_at"))
    finished_at = _common._legacy_account_timestamp(task.get("finished_at"))
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_tasks')} (
            task_uuid, source_system, source_id, batch_id, task_type, target_type, target_id,
            account_id, email_snapshot, requested_action, status, target_status, current_stage,
            next_actions, error_category, error_code, error_message, trigger,
            created_at, updated_at, completed_at, data
        ) VALUES (%s,'account_action_tasks',%s,%s,%s,'account',%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (source_system, source_id) DO UPDATE SET
            batch_id=COALESCE(EXCLUDED.batch_id, {_common._table('operation_tasks')}.batch_id),
            task_type=EXCLUDED.task_type, account_id=EXCLUDED.account_id,
            target_id=EXCLUDED.target_id, email_snapshot=EXCLUDED.email_snapshot,
            status=EXCLUDED.status, target_status=EXCLUDED.target_status,
            current_stage=EXCLUDED.current_stage, next_actions=EXCLUDED.next_actions,
            error_category=EXCLUDED.error_category, error_code=EXCLUDED.error_code,
            error_message=EXCLUDED.error_message, created_at=EXCLUDED.created_at,
            updated_at=EXCLUDED.updated_at,
            completed_at=EXCLUDED.completed_at,
            data={_common._table('operation_tasks')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            task_uuid, source_id, batch_id, task_type,
            account_id, account_id, str(task.get("email_snapshot") or "")[:320], task_type,
            status, target_status, "complete" if status in _common._TERMINAL_STATUSES else "queued",
            _common._json(next_actions),
            category, code, error, str(task.get("trigger") or "manual"),
            queued_at, finished_at or started_at or queued_at,
            finished_at, _common._json({"legacy_account_task_id": legacy_id}),
        ),
    )
    operation_task_id = int(cur.fetchone()["id"])
    cur.execute(
        f"UPDATE {_common._table('operation_tasks')} SET root_task_id=id WHERE id=%s AND root_task_id IS NULL",
        (operation_task_id,),
    )
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_runs')} (
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
            result_summary=EXCLUDED.result_summary, log_file=COALESCE(EXCLUDED.log_file, {_common._table('operation_runs')}.log_file),
            data={_common._table('operation_runs')}.data || EXCLUDED.data
        RETURNING id
        """,
        (
            run_uuid, operation_task_id, source_id, status,
            "complete" if status in _common._TERMINAL_STATUSES else "queued",
            started_at, finished_at, task.get("duration_ms"),
            category, code, error, _common._json(task.get("result_summary") or {}),
            run_log_file, queued_at,
            _common._json({
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
        f"UPDATE {_common._table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
        (run_id, operation_task_id),
    )
    return operation_task_id


def _upsert_account_event(cur, event: dict, task_map: dict[int, int]) -> None:
    legacy_task_id = int(event["task_id"])
    operation_task_id = task_map.get(legacy_task_id)
    if not operation_task_id:
        return
    cur.execute(
        f"SELECT id FROM {_common._table('operation_runs')} WHERE source_system='account_action_tasks' AND source_id=%s",
        (str(legacy_task_id),),
    )
    run = cur.fetchone()
    level = str(event.get("level") or "INFO").upper()
    raw_stage = str(event.get("stage") or "event")
    stage = normalize_stage(raw_stage)
    detail = dict(event.get("detail")) if isinstance(event.get("detail"), dict) else {}
    detail.setdefault("raw_stage", raw_stage)
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
    category, code, _ = _common._error_fields(
        event.get("message") if level == "ERROR" else None, stage=stage,
    )
    source_id = str(event["id"])
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_events')} (
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
            _common._uuid("event", f"account_action_events:{source_id}"), operation_task_id,
            int(run["id"]) if run else None, source_id,
            _common._legacy_account_timestamp(event.get("created_at")) or _common._now(),
            level, stage, event_type, category, code, _common._text(event.get("message"), 1600),
            _common._json(detail),
        ),
    )
    if run and event_type.startswith("stage."):
        state_value = normalize_step_state(event_type.removeprefix("stage."))
        if state_value is not None:
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')}
                SET progress_steps=jsonb_set(progress_steps, %s, to_jsonb(%s::text), true)
                WHERE id=%s
                """,
                ([stage], state_value, int(run["id"])),
            )
            if state_value == "running":
                cur.execute(
                    f"UPDATE {_common._table('operation_runs')} SET progress_stage=%s WHERE id=%s",
                    (stage, int(run["id"])),
                )
                cur.execute(
                    f"UPDATE {_common._table('operation_tasks')} SET current_stage=%s WHERE id=%s",
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
            FROM {_common._table('operation_tasks')}
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
        f"SELECT id FROM {_common._table('operation_projection_queue')} WHERE batch_id=%s FOR UPDATE",
        (int(batch_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _refresh_batch(cur, batch_id: int) -> None:
    from core.storage.operations import bulk_schema
    if bulk_schema._READY_KEY == f"{postgres_store.database_url()}::{_common._schema_name()}":
        cur.execute(f"SELECT 1 FROM {_common._table('operation_batch_controls')} WHERE batch_id=%s", (int(batch_id),))
        if cur.fetchone():
            return
    batch_id = int(batch_id)
    _lock_projection_batch(cur, batch_id)
    cur.execute(
        f"SELECT skipped_count FROM {_common._table('operation_batches')} WHERE id=%s FOR NO KEY UPDATE",
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
        completed_at = _common._now()
    elif partial:
        status = "partial_success"
        completed_at = _common._now()
    elif success:
        status = "success"
        completed_at = _common._now()
    elif stopped or cancelled:
        status = "stopped"
        completed_at = _common._now()
    else:
        status = "queued"
        completed_at = None
    cur.execute(
        f"""
        UPDATE {_common._table('operation_batches')} SET status=%s, queued_count=%s,
            running_count=%s, success_count=%s, partial_count=%s, failed_count=%s,
            attention_count=%s, stopped_count=%s, cancelled_count=%s,
            completed_at=%s
        WHERE id=%s
        """,
        (status, queued, running, success, partial, failed, attention, stopped, cancelled, completed_at, batch_id),
    )


def _refresh_batches(cur, batch_ids: Iterable[int] | None = None) -> None:
    """Refresh only selected batches; ``None`` is reserved for full reconcile."""
    if batch_ids is None:
        cur.execute(f"SELECT id FROM {_common._table('operation_batches')} ORDER BY id")
        ids = [int(row["id"]) for row in cur.fetchall()]
    else:
        ids = sorted({int(value) for value in batch_ids if value is not None})
    for batch_id in ids:
        _refresh_batch(cur, batch_id)


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
    requested = requested_at or _common._now()
    cur.execute(
        f"SELECT id FROM {_common._table('operation_batches')} WHERE id=%s",
        (batch_id,),
    )
    if not cur.fetchone():
        raise LookupError(f"投影批次不存在: {batch_id}")
    # queue row is the first lock in the worker path; an event arriving while a
    # writer is running marks the row dirty so the writer runs once more.
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_projection_queue')} AS queue (
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
            batch_id, _common._text(reason, 120), _common._text(source_system, 120), _common._text(source_id, 240),
            requested, requested,
        ),
    )
    queue_row = dict(cur.fetchone())
    cur.execute(
        f"""
        UPDATE {_common._table('operation_batches')}
        SET projection_status=CASE WHEN projection_status='running' THEN 'running' ELSE 'queued' END,
            projection_requested_at=%s,
            projection_next_retry_at=NULL,
            projection_error=CASE WHEN projection_status='running' THEN projection_error ELSE NULL END
        WHERE id=%s
        """,
        (requested, batch_id),
    )
    return _common._row(queue_row) or {}


def enqueue_batch_projection(
    batch_id: int,
    *,
    reason: str = "event",
    source_system: str = "",
    source_id: str = "",
    requested_at: Any = None,
) -> dict:
    """Persist one coalesced projection request for a specific batch."""
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
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
        UPDATE {_common._table('operation_projection_queue')}
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
        FROM {_common._table('operation_projection_queue')} q
        JOIN {_common._table('operation_batches')} b ON b.id=q.batch_id
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
        f"SELECT id FROM {_common._table('operation_batches')} WHERE id=%s FOR UPDATE",
        (batch_id,),
    )
    if not cur.fetchone():
        return None
    now = _common._now()
    attempts = int(row.get("attempts") or 0) + 1
    cur.execute(
        f"""
        UPDATE {_common._table('operation_projection_queue')}
        SET status='running', attempts=%s, started_at=%s, worker_id=%s,
            updated_at=%s, last_error=NULL
        WHERE id=%s
        RETURNING *
        """,
        (attempts, now, _common._text(worker_id, 160), now, int(row["id"])),
    )
    claimed = dict(cur.fetchone())
    cur.execute(
        f"""
        UPDATE {_common._table('operation_batches')}
        SET projection_status='running', projection_started_at=%s,
            projection_attempts=%s, projection_next_retry_at=NULL
        WHERE id=%s
        """,
        (now, attempts, batch_id),
    )
    claimed.update({"batch_uuid": row.get("batch_uuid"), "batch_source_system": row.get("batch_source_system"), "batch_source_id": row.get("batch_source_id")})
    return _common._row(claimed) or {}


def claim_projection(*, worker_id: str | None = None) -> dict | None:
    """Atomically claim one due batch; concurrent workers skip locked rows."""
    _schema.init_operation_schema()
    identifier = str(worker_id or f"pid-{os.getpid()}-thread-{threading.get_ident()}")
    with _common._connect() as conn, conn.cursor() as cur:
        return _claim_projection_cur(cur, worker_id=identifier)


def _complete_projection(batch_id: int, queue_id: int) -> dict:
    with _common._connect() as conn, conn.cursor() as cur:
        # Completion uses the same queue -> batch lock order as claim/failure.
        cur.execute(
            f"SELECT * FROM {_common._table('operation_projection_queue')} WHERE id=%s FOR UPDATE",
            (int(queue_id),),
        )
        queue_row = cur.fetchone()
        if not queue_row:
            raise LookupError(f"投影队列记录不存在: {queue_id}")
        cur.execute(
            f"SELECT id FROM {_common._table('operation_batches')} WHERE id=%s FOR UPDATE",
            (int(batch_id),),
        )
        if not cur.fetchone():
            raise LookupError(f"投影批次不存在: {batch_id}")
        now = _common._now()
        if bool(queue_row.get("dirty")):
            cur.execute(
                f"""
                UPDATE {_common._table('operation_projection_queue')}
                SET status='queued', dirty=FALSE, available_at=%s,
                    completed_at=NULL, worker_id=NULL, updated_at=%s
                WHERE id=%s RETURNING *
                """,
                (now, now, int(queue_id)),
            )
            updated_queue = dict(cur.fetchone())
            cur.execute(
                f"""
                UPDATE {_common._table('operation_batches')}
                SET projection_status='queued', projection_updated_at=%s,
                    projection_next_retry_at=NULL, projection_error=NULL
                WHERE id=%s
                """,
                (now, int(batch_id)),
            )
        else:
            cur.execute(
                f"""
                UPDATE {_common._table('operation_projection_queue')}
                SET status='succeeded', dirty=FALSE, completed_at=%s,
                    worker_id=NULL, updated_at=%s
                WHERE id=%s RETURNING *
                """,
                (now, now, int(queue_id)),
            )
            updated_queue = dict(cur.fetchone())
            cur.execute(
                f"""
                UPDATE {_common._table('operation_batches')}
                SET projection_status='succeeded', projection_updated_at=%s,
                    projection_next_retry_at=NULL, projection_error=NULL
                WHERE id=%s
                """,
                (now, int(batch_id)),
            )
        return _common._row(updated_queue) or {}


def _fail_projection(batch_id: int, queue_id: int, error: BaseException) -> dict:
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {_common._table('operation_projection_queue')} WHERE id=%s FOR UPDATE",
            (int(queue_id),),
        )
        queue_row = cur.fetchone()
        if not queue_row:
            raise LookupError(f"投影队列记录不存在: {queue_id}")
        cur.execute(
            f"SELECT id FROM {_common._table('operation_batches')} WHERE id=%s FOR UPDATE",
            (int(batch_id),),
        )
        if not cur.fetchone():
            raise LookupError(f"投影批次不存在: {batch_id}")
        attempts = int(queue_row.get("attempts") or 1)
        now = _common._now()
        retry_at = now + timedelta(seconds=_projection_backoff(attempts))
        message = _common._text(f"{type(error).__name__}: {error}", 1000)
        cur.execute(
            f"""
            UPDATE {_common._table('operation_projection_queue')}
            SET status='failed', dirty=FALSE, available_at=%s, worker_id=NULL,
                last_error=%s, updated_at=%s
            WHERE id=%s RETURNING *
            """,
            (retry_at, message, now, int(queue_id)),
        )
        updated_queue = dict(cur.fetchone())
        cur.execute(
            f"""
            UPDATE {_common._table('operation_batches')}
            SET projection_status='failed', projection_updated_at=%s,
                projection_next_retry_at=%s, projection_error=%s
            WHERE id=%s
            """,
            (now, retry_at, message, int(batch_id)),
        )
        return _common._row(updated_queue) or {}


def _compat_registration_event_detail(event: dict) -> tuple[str, str, dict, str | None, str | None]:
    raw_detail = _common._decode(event.get("detail"))
    detail = dict(raw_detail) if isinstance(raw_detail, dict) else {}
    event_type = str(event.get("event_type") or "checkpoint")[:120]
    level = str(event.get("level") or "INFO").upper()
    stage = str(detail.get("stage") or detail.get("current_stage") or event.get("checkpoint") or "event")
    # D's fields are additive compatibility keys inside the existing detail JSONB.
    compatibility = {
        "stage": stage, "raw_stage": stage,
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
        f"SELECT source_system, source_id FROM {_common._table('operation_batches')} WHERE id=%s",
        (int(batch_id),),
    )
    batch = cur.fetchone()
    if not batch or str(batch.get("source_system") or "") != "registration_batches":
        return 0
    source_id = str(batch.get("source_id") or "")
    cur.execute("SELECT to_regclass(%s) AS name", (f"{_common._schema_name()}.registration_events",))
    if not cur.fetchone()["name"]:
        return 0
    # B's tables are read-only inputs here.  The legacy batch_id remains the
    # only selector, so unrelated batches are never scanned or updated.
    cur.execute(
        f"""
        SELECT e.*, rr.job_id AS run_job_id
        FROM {_common._table('registration_events')} e
        LEFT JOIN {_common._table('registration_runs')} rr ON rr.id=e.run_id
        LEFT JOIN {_common._table('registration_attempts')} a ON a.id=e.attempt_id
        LEFT JOIN {_common._table('registration_jobs')} direct_job
          ON direct_job.id=COALESCE(e.job_id, rr.job_id)
        LEFT JOIN {_common._table('registration_jobs')} root_job
          ON root_job.id=COALESCE(a.root_job_id, a.source_root_job_id)
        WHERE COALESCE(direct_job.batch_id, root_job.batch_id)=%s
        ORDER BY e.created_at, e.id
        """,
        (source_id,),
    )
    events = [dict(raw) for raw in cur.fetchall()]
    if not events:
        return 0
    attempt_ids = sorted({int(event["attempt_id"]) for event in events})
    tasks = {}
    for offset in range(0, len(attempt_ids), 1000):
        cur.execute(
            f"""
            SELECT DISTINCT ON (t.attempt_id) t.attempt_id, t.id
            FROM {_common._table('operation_tasks')} t
            WHERE t.attempt_id=ANY(%s::bigint[])
            ORDER BY t.attempt_id, CASE WHEN t.task_type='registration' THEN 0 ELSE 1 END, t.id DESC
            """,
            (attempt_ids[offset:offset + 1000],),
        )
        tasks.update((int(row["attempt_id"]), int(row["id"])) for row in cur.fetchall())
    # Preserve the historical job lookup, including a missing/unattributed Run.
    # Do not use task.last_run_id or limit the lookup to the selected Task.
    job_ids = sorted({str(job_id) for event in events
                      if int(event["attempt_id"]) in tasks
                      and (job_id := event.get("job_id") or event.get("run_job_id")) is not None})
    runs = {}
    for offset in range(0, len(job_ids), 1000):
        cur.execute(
            f"""
            SELECT DISTINCT ON (source_id) source_id, id
            FROM {_common._table('operation_runs')}
            WHERE source_system='registration_jobs' AND source_id=ANY(%s::text[])
            ORDER BY source_id, id DESC
            """,
            (job_ids[offset:offset + 1000],),
        )
        runs.update((str(row["source_id"]), int(row["id"])) for row in cur.fetchall())
    projected = 0
    for event in events:
        task_id = tasks.get(int(event["attempt_id"]))
        if task_id is None:
            continue
        job_id = event.get("job_id") or event.get("run_job_id")
        event_run_id = runs.get(str(job_id)) if job_id is not None else None
        # registration_events 可能来自旧导出，缺少 job/run 关联时只能保留
        # 未知归属；不能把迟到事件借当前 task.last_run_id 伪装成当前 Run。
        # 否则历史线路的回调会在下一次执行中显示为当前步骤事实。
        stage, event_type, detail, error, level = _compat_registration_event_detail(event)
        category, code, _ = _common._error_fields(error, stage=stage, task_type="registration")
        source_event_id = str(event.get("event_uuid") or event.get("id"))
        cur.execute(
            f"""
            INSERT INTO {_common._table('operation_events')} AS current_event (
                event_uuid, task_id, run_id, source_system, source_id, created_at, level,
                stage, event_type, error_category, error_code, message, detail
            ) VALUES (%s,%s,%s,'registration_events',%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (source_system, source_id) DO UPDATE SET
                task_id=EXCLUDED.task_id, run_id=EXCLUDED.run_id, created_at=EXCLUDED.created_at,
                level=EXCLUDED.level, stage=EXCLUDED.stage, event_type=EXCLUDED.event_type,
                error_category=EXCLUDED.error_category, error_code=EXCLUDED.error_code,
                message=EXCLUDED.message, detail=EXCLUDED.detail
            WHERE (current_event.task_id, current_event.run_id, current_event.created_at,
                   current_event.level, current_event.stage, current_event.event_type,
                   current_event.error_category, current_event.error_code,
                   current_event.message, current_event.detail)
              IS DISTINCT FROM
                  (EXCLUDED.task_id, EXCLUDED.run_id, EXCLUDED.created_at,
                   EXCLUDED.level, EXCLUDED.stage, EXCLUDED.event_type,
                   EXCLUDED.error_category, EXCLUDED.error_code,
                   EXCLUDED.message, EXCLUDED.detail)
            """,
            (
                _common._uuid("event", f"registration_events:{source_event_id}"), task_id, event_run_id,
                source_event_id, event.get("created_at") or _common._now(), level, stage, event_type,
                category, code, _common._text(event.get("message") or error or event_type, 1600), _common._json(detail),
            ),
        )
        projected += 1
    return projected


def _repair_terminal_task_projection(cur, batch_id: int) -> int:
    """收口已有终态 Run 对应的卡住任务，只修改统一投影表。"""
    terminal_statuses = tuple(sorted(_common._TERMINAL_STATUSES))
    placeholders = ", ".join("%s" for _ in terminal_statuses)
    cur.execute("SELECT to_regclass(%s) AS name", (f"{_common._schema_name()}.registration_runs",))
    if cur.fetchone()["name"]:
        fact_statuses = (
            "success", "partial_success", "failed", "stopped", "cancelled", "interrupted",
            "request_unknown", "manual_reconcile",
        )
        fact_placeholders = ", ".join("%s" for _ in fact_statuses)
        # 同一 Attempt 的旧终态只能收口同一 Job 的投影，不能套到新重跑。
        # 缺少 job_id 的历史事实无法确认归属，保留原投影等待明确来源。
        cur.execute(
            f"""
            WITH latest_fact AS (
                SELECT
                       task.id AS task_id, run.id AS operation_run_id,
                       rr.status AS fact_status, rr.completed_at AS fact_completed_at,
                       rr.error_message AS fact_error_message
                FROM {_common._table('operation_tasks')} task
                JOIN {_common._table('operation_runs')} run ON run.task_id=task.id
                    AND run.source_system='registration_jobs'
                JOIN {_common._table('registration_runs')} rr ON rr.attempt_id=task.attempt_id
                    AND rr.job_id::text=run.source_id
                WHERE task.batch_id=%s
                  AND rr.status IN ({fact_placeholders})
            )
            UPDATE {_common._table('operation_runs')} run
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
            FROM {_common._table('operation_runs')} run
            JOIN {_common._table('operation_tasks')} task ON task.id=run.task_id
            WHERE task.batch_id=%s
            ORDER BY run.task_id, run.run_no DESC, run.id DESC
        )
        UPDATE {_common._table('operation_tasks')} task
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
    with _common._connect() as conn, conn.cursor() as cur:
        _repair_terminal_task_projection(cur, batch_id)
        _project_registration_fact_events(cur, batch_id)
        _refresh_batches(cur, [batch_id])


def run_projection_once(*, worker_id: str | None = None) -> dict | None:
    """Claim, project and settle one batch; projection errors are durable."""
    from core.runtime.execution_access import execution_owner_valid
    if not execution_owner_valid():
        return None
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
    from core.runtime.execution_access import component_start_allowed
    if not component_start_allowed():
        return False
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
    budget = StopBudget(timeout)
    if not _PROJECTION_WORKER_LOCK.acquire(timeout=budget.remaining()):
        return False
    try:
        worker = _PROJECTION_WORKER
        _PROJECTION_STOP.set()
        _PROJECTION_WAKE.set()
    finally:
        _PROJECTION_WORKER_LOCK.release()
    if not join_stopped(worker, budget):
        return False
    if not _PROJECTION_WORKER_LOCK.acquire(timeout=budget.remaining()):
        return False
    try:
        if _PROJECTION_WORKER is worker:
            _PROJECTION_WORKER = None
        return not bool(_PROJECTION_WORKER and _PROJECTION_WORKER.is_alive())
    finally:
        _PROJECTION_WORKER_LOCK.release()


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
            "stopping": bool(worker and worker.is_alive() and _PROJECTION_STOP.is_set()),
            "name": worker.name if worker is not None else None,
        }


def reconcile_all() -> dict[str, int]:
    """从两套旧表幂等回填统一模型；不会删除旧数据，也不会改账号业务字段。"""
    _schema.init_operation_schema()
    record_store.init()
    with _schema._LOCK, _common._connect() as conn, conn.cursor() as cur:
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

        cur.execute(f"SELECT * FROM {_common._table('account_action_batches')} ORDER BY created_at, id")
        account_batches = [dict(row) for row in cur.fetchall()]
        batch_map = {str(row["id"]): _upsert_account_batch(cur, row) for row in account_batches}
        cur.execute(f"SELECT * FROM {_common._table('account_action_tasks')} ORDER BY id")
        account_tasks = [dict(row) for row in cur.fetchall()]
        task_map = {
            int(row["id"]): _upsert_account_task(cur, row, batch_map, accounts_by_id)
            for row in account_tasks
        }
        cur.execute(f"SELECT * FROM {_common._table('account_action_events')} ORDER BY id")
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
    _schema.init_operation_schema()
    record_store.init()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT run.source_system, run.source_id
            FROM {_common._table('operation_runs')} run
            LEFT JOIN {_common._table('account_action_tasks')} account_task
              ON run.source_system='account_action_tasks'
             AND account_task.id::text=run.source_id
            LEFT JOIN {postgres_store.qualified(record_store.JOBS.name)} registration_job
              ON run.source_system='registration_jobs'
             AND registration_job.id::text=run.source_id
            WHERE run.status IN ({_common._ACTIVE_RUN_STATUS_SQL})
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


def _correct_registration_failure_projection(
    cur, *, job_id: int, error_message: str, diagnostic_summary: dict,
) -> None:
    """在调用方事务内只更正现有错误投影，不重建任务或推导账号状态。"""
    cur.execute(
        "SELECT to_regclass(%s) AS runs, to_regclass(%s) AS tasks",
        (f"{_common._schema_name()}.operation_runs", f"{_common._schema_name()}.operation_tasks"),
    )
    tables = cur.fetchone()
    if not tables["runs"] or not tables["tasks"]:
        return
    cur.execute(
        f"SELECT id, task_id FROM {_common._table('operation_runs')} "
        "WHERE source_system='registration_jobs' AND source_id=%s",
        (str(int(job_id)),),
    )
    run = cur.fetchone()
    if not run:
        return
    # 与常规投影保持任务先于执行实例的加锁顺序。
    cur.execute(f"SELECT id FROM {_common._table('operation_tasks')} WHERE id=%s FOR UPDATE", (run["task_id"],))
    category, code, message = _common._error_fields(
        error_message, stage="email_otp", task_type="registration",
        result_summary=diagnostic_summary, task_status="failed",
    )
    # 受控字段已由注册更正入口验证；不用 _json 重新过滤原恢复事实。
    patch = {key: diagnostic_summary[key] for key in ("cause_code", "registration_diagnostics")}
    cur.execute(
        f"UPDATE {_common._table('operation_runs')} SET "
        "error_category=%s, error_code=%s, error_message=%s, "
        "result_summary=COALESCE(result_summary,'{}'::jsonb) || %s::jsonb, "
        "progress_steps=CASE WHEN progress_steps->'email_otp'->>'state'='failed' "
        "THEN jsonb_set(progress_steps, '{email_otp,detail}', %s::jsonb) ELSE progress_steps END "
        "WHERE id=%s",
        (category, code, message, json.dumps(patch, ensure_ascii=False),
         json.dumps(message, ensure_ascii=False), run["id"]),
    )
    # 历史 Run 的诊断不能覆盖新一轮执行的当前任务错误。
    cur.execute(
        f"UPDATE {_common._table('operation_tasks')} SET error_category=%s, error_code=%s, error_message=%s "
        "WHERE id=%s AND last_run_id=%s",
        (category, code, message, run["task_id"], run["id"]),
    )


def sync_registration_job(job_id: int) -> None:
    """同步一条注册执行。调用方可在每次旧表更新后调用，失败应显式暴露。"""
    _schema.init_operation_schema()
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
        with _common._connect() as conn, conn.cursor() as cur:
            legacy_batch_id = str(job.get("batch_id") or "").strip()
            if legacy_batch_id:
                cur.execute(
                    f"SELECT id FROM {_common._table('operation_batches')} "
                    "WHERE source_system='registration_batches' AND source_id=%s",
                    (legacy_batch_id,),
                )
                existing_batch = cur.fetchone()
                if existing_batch:
                    _lock_existing_projection_queue(cur, int(existing_batch["id"]))
            operation_task_id = _upsert_registration_job(cur, job, accounts_by_id, accounts_by_email)
            cur.execute(
                f"SELECT batch_id FROM {_common._table('operation_tasks')} WHERE id=%s",
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
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_common._table('account_action_tasks')} WHERE id=%s", (int(task_id),))
        task = cur.fetchone()
        if not task:
            return
        batch_map: dict[str, int] = {}
        if task.get("batch_id"):
            cur.execute(
                f"SELECT * FROM {_common._table('account_action_batches')} WHERE id=%s",
                (str(task["batch_id"]),),
            )
            batch = cur.fetchone()
            if batch:
                cur.execute(
                    f"SELECT id FROM {_common._table('operation_batches')} "
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
        cur.execute(f"SELECT * FROM {_common._table('account_action_events')} WHERE task_id=%s ORDER BY id", (int(task_id),))
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
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')} SET data=data || '{{"source_deleted":true}}'::jsonb
            WHERE source_system='registration_jobs' AND source_id = ANY(%s)
            """,
            (ids,),
        )


def verify() -> dict[str, Any]:
    """返回迁移不变量；ok=False 时不得切换生产 UI。"""
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        checks: dict[str, int] = {}
        queries = {
            "legacy_registration_jobs": f"SELECT COUNT(*) FROM {postgres_store.qualified('registration_jobs')}",
            "mapped_registration_runs": f"SELECT COUNT(*) FROM {_common._table('operation_runs')} WHERE source_system='registration_jobs'",
            "legacy_account_tasks": f"SELECT COUNT(*) FROM {_common._table('account_action_tasks')}",
            "mapped_account_runs": f"SELECT COUNT(*) FROM {_common._table('operation_runs')} WHERE source_system='account_action_tasks'",
            "legacy_account_events": f"SELECT COUNT(*) FROM {_common._table('account_action_events')}",
            "mapped_account_events": f"SELECT COUNT(*) FROM {_common._table('operation_events')} WHERE source_system='account_action_events'",
            "orphan_runs": f"SELECT COUNT(*) FROM {_common._table('operation_runs')} r LEFT JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id WHERE t.id IS NULL",
            "orphan_events": f"SELECT COUNT(*) FROM {_common._table('operation_events')} e LEFT JOIN {_common._table('operation_tasks')} t ON t.id=e.task_id WHERE t.id IS NULL",
            "duplicate_active_account_families": f"SELECT COUNT(*) FROM (SELECT account_id, resource_family FROM {_common._table('operation_runs')} WHERE account_id IS NOT NULL AND status IN ('queued','running','cancelling','settling','waiting') GROUP BY account_id, resource_family HAVING COUNT(*) > 1) AS duplicates",
            "terminal_run_leases": f"SELECT COUNT(*) FROM {_common._table('account_operation_leases')} lease JOIN {_common._table('operation_runs')} run ON run.id=lease.run_id WHERE run.status NOT IN ('queued','running','cancelling','settling','waiting')",
            "terminal_acquired_resources": f"SELECT COUNT(*) FROM {_common._table('operation_resources')} resource JOIN {_common._table('operation_runs')} run ON run.id=resource.run_id WHERE run.status NOT IN ('queued','running','cancelling','settling','waiting') AND resource.state='acquired'",
            "projection_queue_invalid_status": f"SELECT COUNT(*) FROM {_common._table('operation_projection_queue')} WHERE status NOT IN ('queued','running','succeeded','failed')",
            "projection_queue_orphans": f"SELECT COUNT(*) FROM {_common._table('operation_projection_queue')} q LEFT JOIN {_common._table('operation_batches')} b ON b.id=q.batch_id WHERE b.id IS NULL",
        }
        for key, sql in queries.items():
            cur.execute(sql)
            checks[key] = int(cur.fetchone()["count"])
        cur.execute(
            f"SELECT COUNT(*) FROM {_common._table('registration_attempts')} WHERE target_status='email_verification_pending'"
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


__all__ = ['enqueue_batch_projection', 'claim_projection', 'run_projection_once', 'drain_projection_queue', 'start_projection_worker', 'stop_projection_worker', 'projection_worker_status', 'reconcile_all', 'repair_stale_compatibility_projections', 'sync_registration_job', 'sync_account_task', 'mark_registration_jobs_deleted', 'verify']
