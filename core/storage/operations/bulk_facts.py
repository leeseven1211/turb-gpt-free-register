"""集合读取和变更任务中心及注册的本地事实。"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from core.operations import run_log
from core.storage import postgres, records as record_store, registration
from core.storage.operations import common, projection, schema


def delete_tasks_many(task_ids: Iterable[int]) -> dict[str, Any]:
    """隐藏已结束的任务，保留原始 Run 和事件。"""
    normalized = []
    for raw_id in task_ids:
        try:
            task_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if 0 < task_id <= 2**63 - 1 and task_id not in normalized:
            normalized.append(task_id)
        if len(normalized) == 100:
            break

    deleted = []
    skipped = []
    if normalized:
        schema.init_operation_schema()
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT task.id, task.status, task.data,
                       EXISTS (
                           SELECT 1 FROM {common._table('operation_runs')} run
                           WHERE run.task_id=task.id AND run.status IN ({common._ACTIVE_RUN_STATUS_SQL})
                       ) AS has_active_run
                FROM {common._table('operation_tasks')} task
                WHERE task.id = ANY(%s)
                ORDER BY task.id FOR UPDATE OF task
                """,
                (normalized,),
            )
            rows = {row["id"]: row for row in cur.fetchall()}
            eligible = []
            for task_id in normalized:
                row = rows.get(task_id)
                if not row:
                    error = "任务不存在"
                elif common._task_is_user_deleted(row):
                    error = "任务已删除"
                elif row["has_active_run"] or str(row["status"] or "").strip().lower() in common._ACTIVE_RUN_STATUSES:
                    error = "任务仍在执行，不能删除"
                else:
                    eligible.append(task_id)
                    continue
                skipped.append({"task_id": task_id, "error": error})
            if eligible:
                cur.execute(
                    f"""
                    UPDATE {common._table('operation_tasks')}
                    SET data=COALESCE(data, '{{}}'::jsonb)
                             || jsonb_build_object('deleted_by_user', true, 'deleted_at', now()),
                        updated_at=now()
                    WHERE id = ANY(%s)
                    """,
                    (eligible,),
                )
                deleted.extend(eligible)
    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "skipped": skipped,
        "skipped_count": len(skipped),
    }


def get_action_tasks_many(task_ids: list[int], *, conn) -> dict[int, dict]:
    """批量读取分发所需的最新 Run 和当前 Run。"""
    if not task_ids:
        return {}
    runs = common._table("operation_runs")
    status = common._compatibility_run_status_sql()
    joins = common._compatibility_run_joins_sql()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.*, b.batch_uuid, b.title AS batch_title, b.batch_type,
                   selected.runs,
                   COALESCE(NULLIF(linked.data->>'bulk_target_round_id', ''),
                            NULLIF(t.data->>'bulk_target_round_id', '')) AS _managed_target_round_id
            FROM {common._table('operation_tasks')} t
            LEFT JOIN {common._table('operation_batches')} b ON b.id=t.batch_id
            LEFT JOIN {runs} linked ON linked.id=t.last_run_id
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(to_jsonb(run) ORDER BY run.run_no, run.id) AS runs
                FROM (
                    SELECT rr.id, rr.run_no, rr.source_system, rr.source_id, rr.status,
                           rr.result_summary, rr.data, rr.progress_stage, rr.error_category, rr.error_code,
                           {common._compatibility_run_projection_sql()}
                    FROM {runs} rr {joins}
                    WHERE rr.id IN (
                        (SELECT latest.id FROM {runs} latest WHERE latest.task_id=t.id
                         ORDER BY latest.run_no DESC, latest.id DESC LIMIT 1),
                        (SELECT rr.id FROM {runs} rr {joins} WHERE rr.task_id=t.id
                         AND ({status}) IN ({common._ACTIVE_RUN_STATUS_SQL})
                         ORDER BY rr.run_no DESC, rr.id DESC LIMIT 1)
                    )
                ) run
            ) selected ON TRUE
            WHERE t.id = ANY(%s)
              AND lower(COALESCE(t.data->>'deleted_by_user', 'false')) <> 'true'
            """,
            (task_ids,),
        )
        tasks = {}
        for row in cur.fetchall():
            task = common._row(row)
            task["runs"] = [common._normalize_compatibility_run(run) for run in task["runs"] or []]
            common._apply_current_run_projection(task, common._select_current_run(task["runs"]))
            tasks[int(task["id"])] = task
    return tasks


def get_managed_retry_targets(target_round_ids: list[int], *, conn) -> dict[int, dict]:
    if not target_round_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id,batch_id,canonical_target_id FROM {common._table('operation_batch_target_rounds')} "
            "WHERE id = ANY(%s)",
            (target_round_ids,),
        )
        return {int(row["id"]): row for row in cur.fetchall()}


def cancel_pending_jobs_many(
    job_ids: Iterable[int] | None = None,
    *,
    batch_id: str | None = None,
) -> int:
    """收口仍待执行的注册 Job 和 RegistrationRun，保留业务 Attempt。"""
    from core import db

    where = '"status" = %s'
    params: list[Any] = ["pending"]
    if job_ids is not None:
        ids = list(dict.fromkeys(int(job_id) for job_id in job_ids))
        if not ids:
            return 0
        where += " AND id = ANY(%s)"
        params.append(ids)
    if batch_id is not None:
        where += ' AND "batch_id" = %s'
        params.append(batch_id)

    completed_at = db._registration_now()
    error_message = "用户手动取消"
    with record_store.transaction() as conn:
        cancelled = record_store.patch_rows_where_returning(
            record_store.JOBS,
            changes={"status": "cancelled", "completed_at": completed_at, "error_message": error_message},
            where=where,
            params=params,
            conn=conn,
            id_only=True,
        )
        ids = [row["id"] for row in cancelled]
        db._cancel_queued_registration_runs(conn, ids, completed_at=completed_at, error_message=error_message)
    if ids:
        _project_cancelled_registration_jobs(ids, completed_at=completed_at, error_message=error_message)
    return len(ids)


def delete_registration_jobs_many(job_ids: list[int]) -> tuple[list[dict], list[dict]]:
    """删除本地 Job，保留已关联的 RegistrationRun 及其历史标识。"""
    ids = sorted(set(job_ids))
    if not ids:
        return [], []

    from core import db

    registration.init()
    jobs = postgres.qualified(record_store.JOBS.name)
    runs = postgres.qualified("registration_runs")
    with record_store.transaction() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT id,status FROM {jobs} WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
            (ids,),
        )
        selected = {row["id"]: row["status"] for row in cur.fetchall()}
        cur.execute(
            f"SELECT job_id,status FROM {runs} WHERE job_id = ANY(%s) ORDER BY job_id FOR UPDATE",
            (ids,),
        )
        run_statuses = {row["job_id"]: row["status"] for row in cur.fetchall()}
        protected = {
            job_id for job_id, status in selected.items()
            if status in {"running", "stopping"} or run_statuses.get(job_id) == "running"
        }
        eligible = selected.keys() - protected
        pending = [job_id for job_id in eligible if selected[job_id] == "pending"]
        completed_at = db._registration_now()
        reason = "用户删除排队任务"
        db._cancel_queued_registration_runs(conn, pending, completed_at=completed_at, error_message=reason)
        if eligible:
            cur.execute(
                f"""UPDATE {runs}
                    SET data=data || jsonb_build_object('deleted_job_id', job_id), job_id=NULL
                    WHERE job_id = ANY(%s)""",
                (sorted(eligible),),
            )
            deleted = record_store.delete_rows_where_returning(
                record_store.JOBS, where="id = ANY(%s)", params=(sorted(eligible),), conn=conn,
            )
        else:
            deleted = []

    if pending:
        _project_cancelled_registration_jobs(pending, completed_at=completed_at, error_message=reason)
    if deleted:
        try:
            projection.mark_registration_jobs_deleted(row["id"] for row in deleted)
        except Exception:
            projection.logger.exception("标记批量注册任务来源已删除失败")
    for row in deleted:
        if row.get("log_file"):
            try:
                run_log.resolve_path(str(row["log_file"])).unlink(missing_ok=True)
            except (OSError, ValueError):
                projection.logger.warning("删除注册任务 #%s 日志失败", row["id"])

    skipped = [
        {"id": job_id, "reason": "运行中，不能删除" if job_id in protected else "任务不存在"}
        for job_id in ids if job_id not in eligible
    ]
    return deleted, skipped


def _project_cancelled_registration_jobs(ids: list[int], *, completed_at: str, error_message: str) -> None:
    """更新已有兼容投影，保持 Job/RegistrationRun 为实际取消来源。"""
    schema.init_operation_schema()
    source_ids = [str(job_id) for job_id in ids]
    task_table = common._table("operation_tasks")
    run_table = common._table("operation_runs")

    def write():
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                WITH locked_tasks AS MATERIALIZED (
                    SELECT task.id
                    FROM {task_table} task
                    WHERE EXISTS (
                        SELECT 1 FROM {run_table} run
                        WHERE run.task_id=task.id AND run.source_system='registration_jobs'
                          AND run.source_id = ANY(%s) AND run.status='queued'
                    )
                    ORDER BY task.id FOR UPDATE OF task
                ), cancelled AS (
                    UPDATE {run_table} run
                    SET status='cancelled', progress_stage='complete',
                        completed_at=%s, error_message=%s
                    FROM locked_tasks task
                    WHERE run.task_id=task.id AND run.source_system='registration_jobs' AND run.source_id = ANY(%s)
                      AND run.status='queued'
                    RETURNING run.id, run.task_id
                )
                UPDATE {task_table} task
                SET status='cancelled', current_stage='complete', completed_at=%s,
                    error_message=%s, updated_at=now()
                FROM cancelled
                WHERE task.id=cancelled.task_id AND task.last_run_id=cancelled.id
                  AND task.status='queued'
                RETURNING task.batch_id
                """,
                (source_ids, completed_at, error_message, source_ids, completed_at, error_message),
            )
            return sorted({int(row["batch_id"]) for row in cur.fetchall() if row["batch_id"] is not None})

    try:
        batch_ids = projection._run_projection_write_with_retry(write, operation_name="cancel_pending_jobs_many")
        for batch_id in batch_ids:
            projection.enqueue_batch_projection(
                batch_id, reason="registration_jobs_cancelled", source_system="registration_jobs",
            )
    except Exception:
        projection.logger.exception("同步批量取消注册任务投影失败")
