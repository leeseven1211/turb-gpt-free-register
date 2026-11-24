"""在控制结算原事务内集合取消精确归属的 Run。"""
from __future__ import annotations

import uuid

from core.storage import records
from core.storage.operations import common
from core.storage.operations.bulk_common import ACTIVE_RUNS, OWNED, dumps, table


def cancel_owned_runs_many(conn, target_round_ids: list[int], *, reason: str) -> set[int]:
    """调用方先持 controls/target 锁；随后依次取得账号、Task、Run 锁。"""
    ids = sorted(set(target_round_ids))
    if not ids:
        return set()
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT l.target_round_id,r.id,r.account_id,r.task_id
            FROM {table('operation_batch_run_links')} l
            JOIN {table('operation_runs')} r ON r.id=l.run_id
            WHERE l.target_round_id=ANY(%s) AND l.relation=ANY(%s) AND r.status=ANY(%s)
            ORDER BY r.task_id,r.id""",
            (ids, list(OWNED), list(ACTIVE_RUNS)),
        )
        linked = list(cur.fetchall())
        if not linked:
            return set()
        account_ids = sorted({row["account_id"] for row in linked if row["account_id"]})
        if account_ids:
            cur.execute(
                f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                (account_ids,),
            )
        cur.execute(
            f"SELECT id FROM {table('operation_tasks')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            (sorted({row["task_id"] for row in linked}),),
        )
        cur.execute(
            f"SELECT id,status FROM {table('operation_runs')} WHERE id=ANY(%s) ORDER BY task_id,id FOR UPDATE",
            (sorted({row["id"] for row in linked}),),
        )
        active = {row["id"] for row in cur.fetchall() if row["status"] in ACTIVE_RUNS}
        if not active:
            return {row["target_round_id"] for row in linked}
        selected = [
            {"run_id": run_id, "event_uuid": uuid.uuid4().hex}
            for run_id in sorted(active)
        ]
        # 一个 statement 写 Run/Task/lease/event，失败时由控制事务整体回滚。
        cur.execute(
            f"""WITH input AS (
                SELECT * FROM jsonb_to_recordset(%s::jsonb) AS item(run_id bigint,event_uuid text)
            ), previous AS MATERIALIZED (
                SELECT r.*,input.event_uuid FROM {table('operation_runs')} r
                JOIN input ON input.run_id=r.id
            ), changed AS (
                UPDATE {table('operation_runs')} r
                SET status=CASE WHEN p.status='queued' THEN 'cancelled' ELSE 'cancelling' END,
                    cancel_requested_at=COALESCE(r.cancel_requested_at,now()),cancel_reason=%s,
                    heartbeat_at=now(),completed_at=CASE WHEN p.status='queued' THEN now() ELSE r.completed_at END
                FROM previous p WHERE r.id=p.id
                RETURNING r.id,r.task_id,r.account_id,r.status,r.source_system,r.started_at,r.data,
                          p.status AS previous_status,p.event_uuid
            ), task_changes AS (
                SELECT DISTINCT ON (task_id) task_id,status FROM changed ORDER BY task_id,id DESC
            ), task_updates AS (
                UPDATE {table('operation_tasks')} t SET
                    status=task_changes.status,
                    current_stage=CASE WHEN task_changes.status='cancelled' THEN 'complete' ELSE 'cancelling' END,
                    updated_at=now(),
                    completed_at=CASE WHEN task_changes.status='cancelled' THEN now() ELSE t.completed_at END
                FROM task_changes WHERE t.id=task_changes.task_id
            ), lease_updates AS (
                UPDATE {table('account_operation_leases')} lease SET cancel_requested_at=now()
                FROM changed WHERE lease.run_id=changed.id
            ), events AS (
                INSERT INTO {table('operation_events')}
                    (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
                SELECT event_uuid,task_id,id,COALESCE(NULLIF(source_system,''),'native_operations'),event_uuid,
                    'WARNING',CASE WHEN status='cancelled' THEN 'complete' ELSE 'cancelling' END,
                    'run.cancel_requested',%s,
                    jsonb_build_object('previous_status',previous_status,'status',status)
                FROM changed
            )
            SELECT id,account_id,status,started_at,data FROM changed""",
            (dumps(selected), common._text(reason, 500), common._text(reason, 1400)),
        )
        changed = list(cur.fetchall())
        release = []
        for run in changed:
            data = run.get("data") or {}
            queued_at = data.get("live_check_queued_at")
            if (data.get("bulk_target_round_id") and data.get("force_refresh") is True and queued_at
                    and run["status"] == "cancelled" and not run["started_at"] and not data.get("remote_intent")):
                release.append({"account_id": run["account_id"], "queued_at": str(queued_at)})
        if release:
            cur.execute(
                f"""UPDATE {records._qualified(records.ACCOUNTS)} account
                SET live_check_status='cancelled',
                    updated_at=%s,
                    data=account.data || jsonb_build_object(
                        'live_check_ok',false,'live_check_error','批量任务取消未开始',
                        'live_checked_at',now()::text)
                FROM jsonb_to_recordset(%s::jsonb) AS item(account_id bigint,queued_at text)
                WHERE account.id=item.account_id AND account.live_check_status='queued'
                  AND account.data->>'live_check_queued_at'=item.queued_at
                  AND account.data->>'live_check_trigger'='manual_bulk'""",
                (records._now(), dumps(release)),
            )
        return {row["target_round_id"] for row in linked}
