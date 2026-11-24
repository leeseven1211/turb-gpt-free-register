"""在调用方事务中集合取消精确 Run 快照，不执行强制结算。"""
from __future__ import annotations

import json
import uuid

from psycopg.pq import TransactionStatus

from core.storage import records
from core.storage.operations import bulk_retry_projection, bulk_runtime, common


def cancel_runs_many(conn, requests: list[dict]) -> dict[int, dict | None]:
    """调用方负责目标资格；本层保持 request_run_cancel 的精确 CAS 与事实。"""
    if not requests:
        return {}
    expected_runs = {int(item["id"]): item for item in requests}
    runs_table = common._table("operation_runs")
    tasks_table = common._table("operation_tasks")
    ids = sorted(expected_runs)
    if conn.info.transaction_status == TransactionStatus.IDLE:
        # 先开启调用方事务，让内层 transaction() 只释放保存点，保留调用方提交权。
        conn.execute("BEGIN")
    with conn.transaction(), conn.cursor() as cur:
        managed = []
        if bulk_runtime._enabled():
            # 与旧 fact_update 一样只按精确 owned link 归属，不检查批次控制资格。
            # 所有 target 锁先于账号/Task/Run，避免与受管执行形成倒序锁。
            from core.storage.operations.bulk_common import OWNED

            cur.execute(
                f"""SELECT target.id AS target_round_id,r.id AS run_id,r.account_id,r.task_id
                FROM {common._table('operation_batch_run_links')} link
                JOIN {common._table('operation_batch_target_rounds')} target ON target.id=link.target_round_id
                JOIN {runs_table} r ON r.id=link.run_id
                WHERE r.id=ANY(%s) AND link.relation=ANY(%s)
                  AND r.data->>'bulk_target_round_id' ~ '^[0-9]*[1-9][0-9]*$'
                ORDER BY target.id,r.id FOR UPDATE OF target""",
                (ids, list(OWNED)),
            )
            managed = list(cur.fetchall())
            managed_accounts = sorted({row["account_id"] for row in managed if row["account_id"]})
            if managed_accounts:
                cur.execute(
                    f"SELECT id FROM {records._qualified(records.ACCOUNTS)} "
                    "WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                    (managed_accounts,),
                )
            if managed:
                cur.execute(
                    f"SELECT id FROM {tasks_table} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                    (sorted({row["task_id"] for row in managed}),),
                )
        cur.execute(f"SELECT * FROM {runs_table} WHERE id=ANY(%s) ORDER BY id FOR UPDATE", (ids,))
        current = {row["id"]: dict(row) for row in cur.fetchall()}
        candidates = [
            {"run_id": run_id, "expected_status": str(expected_runs[run_id]["expected_status"]),
             "event_uuid": uuid.uuid4().hex,
             "reason": common._text(expected_runs[run_id]["reason"], 500),
             "message": common._text(expected_runs[run_id]["reason"], 1400)}
            for run_id in ids if run_id in current
            and current[run_id]["status"] == str(expected_runs[run_id]["expected_status"])
            and current[run_id]["status"] not in common._TERMINAL_STATUSES
        ]
        changed = []
        if candidates:
            cur.execute(
                f"""WITH input AS (
                    SELECT * FROM jsonb_to_recordset(%s::jsonb)
                    AS item(run_id bigint,expected_status text,event_uuid text,reason text,message text)
                ), previous AS MATERIALIZED (
                    SELECT r.*,input.event_uuid,input.reason,input.message FROM {runs_table} r
                    JOIN input ON input.run_id=r.id AND r.status=input.expected_status
                ), changed AS (
                    UPDATE {runs_table} r
                    SET status=CASE WHEN previous.status='queued' THEN 'cancelled' ELSE 'cancelling' END,
                        cancel_requested_at=COALESCE(r.cancel_requested_at,now()),cancel_reason=previous.reason,
                        heartbeat_at=now(),
                        completed_at=CASE WHEN previous.status='queued' THEN now() ELSE r.completed_at END
                    FROM previous WHERE r.id=previous.id
                    RETURNING r.id,r.task_id,r.status,r.batch_id,r.source_system,r.account_id,r.started_at,r.data,
                              previous.status AS previous_status,previous.event_uuid,previous.message
                ), task_changes AS (
                    SELECT DISTINCT ON (task_id) task_id,status FROM changed ORDER BY task_id,id DESC
                ), task_updates AS (
                    UPDATE {tasks_table} task SET status=change.status,
                        current_stage=CASE WHEN change.status='cancelled' THEN 'complete' ELSE 'cancelling' END,
                        updated_at=now(),
                        completed_at=CASE WHEN change.status='cancelled' THEN now() ELSE task.completed_at END
                    FROM task_changes change WHERE task.id=change.task_id
                ), lease_updates AS (
                    UPDATE {common._table('account_operation_leases')} lease SET cancel_requested_at=now()
                    FROM changed WHERE lease.run_id=changed.id
                ), events AS (
                    INSERT INTO {common._table('operation_events')}
                        (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
                    SELECT event_uuid,task_id,id,COALESCE(NULLIF(source_system,''),'native_operations'),event_uuid,'WARNING',
                        CASE WHEN status='cancelled' THEN 'complete' ELSE 'cancelling' END,
                        'run.cancel_requested',message,
                        jsonb_build_object('previous_status',previous_status,'status',status)
                    FROM changed
                ) SELECT id,task_id,status,batch_id,account_id,started_at,data FROM changed""",
                (json.dumps(candidates),),
            )
            changed = list(cur.fetchall())
            release = [
                {"account_id": row["account_id"], "queued_at": str(row["data"]["live_check_queued_at"])}
                for row in changed if row["status"] == "cancelled" and not row["started_at"]
                and row["data"].get("bulk_target_round_id") and row["data"].get("force_refresh") is True
                and row["data"].get("live_check_queued_at") and not row["data"].get("remote_intent")
            ]
            if release:
                cur.execute(
                    f"""UPDATE {records._qualified(records.ACCOUNTS)} account SET
                        live_check_status='cancelled',updated_at=%s,
                        data=account.data || jsonb_build_object(
                            'live_check_ok',false,'live_check_error','批量任务取消未开始',
                            'live_checked_at',now()::text)
                    FROM jsonb_to_recordset(%s::jsonb) AS item(account_id bigint,queued_at text)
                    WHERE account.id=item.account_id AND account.live_check_status='queued'
                      AND account.data->>'live_check_queued_at'=item.queued_at
                      AND account.data->>'live_check_trigger'='manual_bulk'""",
                    (records._now(), json.dumps(release)),
                )
            batch_ids = {row["batch_id"] for row in changed if row["batch_id"]}
            if batch_ids:
                bulk_retry_projection.refresh_batches_many(cur, batch_ids)
        if managed:
            # 旧 fact_update 即使 CAS 跳过也发布链事实；这里保持相同边界并集合追加。
            bulk_runtime.record_managed_changes_many(
                conn, {row["target_round_id"] for row in managed},
            )
    replies = {
        row["id"]: {**{key: row[key] for key in ("id", "task_id", "status", "batch_id")},
                    "log_file": current[row["id"]].get("log_file")}
        for row in changed
    }
    for run_id in ids:
        if run_id in replies:
            continue
        row = current.get(run_id)
        if row is None:
            replies[run_id] = None
        elif row["status"] == str(expected_runs[run_id]["expected_status"]) and row["status"] in common._TERMINAL_STATUSES:
            replies[run_id] = common._row(row)
        else:
            replies[run_id] = {
                "id": run_id, "status": row["status"], "cancel_skipped": True,
                "message": "任务状态已变化，请刷新后重试",
            }
    return replies
