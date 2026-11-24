"""提链工作台的集合本地读取和排队事实；不调用远端平台。"""
from __future__ import annotations

from contextlib import nullcontext
import json
import uuid

from core.operations import run_log
from core.storage import records, postgres
from core.storage.operations import common, projection, store as operation


def _lock_sync_sources(cur, conn, ids):
    """受管目标先锁，随后统一按账号、Task 顺序锁；等待后还要核验来源 Run。"""
    cur.execute(f"""SELECT task.id,task.account_id,latest.id AS source_run_id,
        latest.data->>'bulk_target_round_id' AS target_id
        FROM {operation._table('operation_tasks')} task
        LEFT JOIN LATERAL (SELECT id,data FROM {operation._table('operation_runs')}
            WHERE task_id=task.id ORDER BY run_no DESC,id DESC LIMIT 1) latest ON TRUE
        WHERE task.id=ANY(%s) ORDER BY task.id""",(ids,))
    identities = [dict(row) for row in cur.fetchall()]
    managed = sorted((row for row in identities if str(row.get('target_id') or '').isdigit()),
        key=lambda row:(int(row['target_id']),row['source_run_id']))
    if managed:
        from core.storage.operations import bulk
        for row in managed:
            bulk.lock_managed_target(conn,row['source_run_id'])
    account_ids = sorted({row['account_id'] for row in identities if row.get('account_id')})
    if account_ids:
        cur.execute(f"SELECT id FROM {postgres.qualified(records.ACCOUNTS.name)} "
            "WHERE id=ANY(%s) ORDER BY id FOR UPDATE",(account_ids,))
        cur.fetchall()
    cur.execute(f"SELECT id FROM {operation._table('operation_tasks')} "
        "WHERE id=ANY(%s) ORDER BY id FOR UPDATE",(ids,))
    cur.fetchall()
    return {row['id']:(row['source_run_id'],row['account_id']) for row in identities}


def read_snapshots(task_ids, *, conn=None, lock=False, use_latest=True):
    """一次读取最新 Run、公开原单和付款意图；私有凭据只在 SQL 内复制。"""
    ids = list(dict.fromkeys(int(value) for value in task_ids))
    if not ids:
        return {}
    operation.init()
    with (operation._connect() if conn is None else nullcontext(conn)) as connection, connection.cursor() as cur:
        expected_sources = _lock_sync_sources(cur,connection,ids) if lock else {}
        selected_run = "run.task_id=task.id" if use_latest else "run.id=task.last_run_id AND run.task_id=task.id"
        cur.execute(f"""
            SELECT task.*, to_jsonb(latest) AS latest_run,
                   CASE WHEN job.run_id IS NOT NULL THEN
                       jsonb_build_object('run_id',job.run_id,'provider_id',job.provider_id,
                           'job_id',job.job_id,'public_state',job.public_state) END AS provider_job,
                   CASE WHEN payment.id IS NOT NULL THEN
                       jsonb_build_object('id',payment.id,'payment_state',payment.payment_state,
                           'summary',payment.summary) END AS payment_order,
                   account.deactivated AS account_deactivated,
                   account.data->>'extract_link_job_id' AS legacy_job_id,
                   account.data->>'extract_link_long_url' AS legacy_link,
                   EXISTS (SELECT 1 FROM {operation._table('operation_runs')} active
                           WHERE active.task_id=task.id
                             AND active.status=ANY(%s)) AS has_active_run
            FROM {operation._table('operation_tasks')} task
            LEFT JOIN LATERAL (
                SELECT run.id,run.run_no,run.status,run.data,run.result_summary,run.resource_family,
                       run.batch_id FROM {operation._table('operation_runs')} run
                WHERE {selected_run} ORDER BY run.run_no DESC,run.id DESC LIMIT 1
            ) latest ON TRUE
            LEFT JOIN {operation._table('extract_link_provider_jobs')} job ON job.run_id=latest.id
            LEFT JOIN LATERAL (
                SELECT id,payment_state,summary FROM {operation._table('extract_link_payment_orders')}
                WHERE task_id=task.id ORDER BY attempt_no DESC LIMIT 1
            ) payment ON TRUE
            LEFT JOIN {postgres.qualified(records.ACCOUNTS.name)} account ON account.id=task.account_id
            WHERE task.id=ANY(%s)
              AND lower(COALESCE(task.data->>'deleted_by_user','false')) <> 'true'
            """, (sorted(common._ACTIVE_RUN_STATUSES), ids))
        rows = {int(row["id"]): dict(row) for row in cur.fetchall()}
        if lock:
            for row in rows.values():
                identity = ((row.get('latest_run') or {}).get('id'),row.get('account_id'))
                if identity != expected_sources.get(row['id']):
                    # 等待锁时另一入口已经创建下一 Run，旧身份不能继续集合重试。
                    row['has_active_run'] = True
            account_ids = sorted({int(row["account_id"]) for row in rows.values() if row["account_id"]})
            if account_ids:
                cur.execute(f"SELECT id,deactivated FROM {postgres.qualified(records.ACCOUNTS.name)} "
                            "WHERE id=ANY(%s) ORDER BY id", (account_ids,))
                locked_accounts = {int(row["id"]): row for row in cur.fetchall()}
                cur.execute(f"SELECT account_id FROM {operation._table('operation_runs')} "
                            "WHERE account_id=ANY(%s) AND resource_family='openai_interactive' "
                            "AND status=ANY(%s)", (account_ids, sorted(common._ACTIVE_RUN_STATUSES)))
                busy = {int(row["account_id"]) for row in cur.fetchall()}
                for row in rows.values():
                    row["account_busy"] = row["account_id"] in busy
                    if row["account_id"] in locked_accounts:
                        row["account_deactivated"] = locked_accounts[row["account_id"]]["deactivated"]
        return rows


def retry_sync_many(prepared, *, conn):
    """在调用方事务内集合新建 Run，并原子复制同任务同平台的私有原单快照。"""
    if not prepared:
        return {}
    rows = []
    managed_sources = {}
    for item in prepared:
        row = dict(item)
        row.update(run_uuid=uuid.uuid4().hex, cancellation_token=uuid.uuid4().hex,
                   event_uuid=uuid.uuid4().hex)
        row["log_file"] = run_log.build_path(task_uuid=row["task_uuid"], run_no=row["run_no"],
                                             run_uuid=row["run_uuid"])
        row["data"] = common._scrub(row["data"])
        if row['data'].get('bulk_target_round_id'):
            from core.bulk_operations import execution as bulk_execution
            managed = bulk_execution.lock_run(conn,int(row['source_run_id']))
            if managed:
                managed_sources[row['task_id']] = managed
                row['data']['bulk_target_round_id'] = int(managed['id'])
            else:
                row['data'].pop('bulk_target_round_id',None)
        rows.append(row)
    payload = json.dumps(rows, ensure_ascii=False)
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {operation._table('operation_runs')}
                (run_uuid,task_id,run_no,source_system,source_id,status,batch_id,account_id,
                 resource_family,cancellation_token,log_file,data)
            SELECT run_uuid,task_id,run_no,'native_operations',run_uuid,'queued',batch_id,account_id,
                   resource_family,cancellation_token,log_file,data
            FROM jsonb_to_recordset(%s::jsonb) AS item(run_uuid TEXT,task_id BIGINT,run_no INTEGER,
                batch_id BIGINT,account_id BIGINT,resource_family TEXT,cancellation_token TEXT,
                log_file TEXT,data JSONB)
            RETURNING id,task_id
            """, (payload,))
        runs = {int(row["task_id"]): int(row["id"]) for row in cur.fetchall()}
        for row in rows:
            row["run_id"] = runs[row["task_id"]]
            if row['task_id'] in managed_sources:
                from core.bulk_operations import execution as bulk_execution
                bulk_execution.inherit(conn,row['run_id'],source_run_id=int(row['source_run_id']),
                    step_key='extract_link')
                bulk_execution.changed(conn,managed_sources[row['task_id']])
        payload = json.dumps(rows, ensure_ascii=False)
        cur.execute(f"""
            INSERT INTO {operation._table('extract_link_provider_jobs')}
                (run_id,provider_id,job_id,extraction_state,payment_state,public_state,private_data)
            SELECT item.run_id,job.provider_id,job.job_id,job.extraction_state,job.payment_state,
                   job.public_state,job.private_data
            FROM jsonb_to_recordset(%s::jsonb) AS item(run_id BIGINT,task_id BIGINT,
                source_run_id BIGINT,provider_id TEXT)
            JOIN {operation._table('operation_runs')} source_run
              ON source_run.id=item.source_run_id AND source_run.task_id=item.task_id
            JOIN {operation._table('extract_link_provider_jobs')} job
              ON job.run_id=source_run.id AND job.provider_id=item.provider_id
            """, (payload,))
        cur.execute(f"""
            INSERT INTO {operation._table('operation_events')}
                (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
            SELECT event_uuid,task_id,run_id,'native_operations',event_uuid,'INFO','queued',
                   'run.queued','任务已加入队列','{{}}'::jsonb
            FROM jsonb_to_recordset(%s::jsonb) AS item(event_uuid TEXT,task_id BIGINT,run_id BIGINT)
            """, (payload,))
        cur.execute(f"""
            UPDATE {operation._table('operation_tasks')} task
            SET status='queued',target_status='pending',current_stage='queued',last_run_id=item.run_id,
                error_category=NULL,error_code=NULL,error_message=NULL,completed_at=NULL,
                next_actions='[]'::jsonb,updated_at=now(),trigger='extract_workbench_sync_status'
            FROM jsonb_to_recordset(%s::jsonb) AS item(task_id BIGINT,run_id BIGINT)
            WHERE task.id=item.task_id
            """, (payload,))
        batch_ids = sorted({int(row["batch_id"]) for row in rows if row.get("batch_id")})
        if batch_ids:
            projection._refresh_batches(cur, batch_ids)
        # 提链自身没有父级编排；兼容历史带父任务的记录仍沿原协调规则更新一次。
        parents = sorted({int(row["parent_task_id"]) for row in rows if row.get("parent_task_id")})
        if parents:
            from core.storage.operations.runtime import _reconcile_parent_task_cur
            for parent_id in parents:
                _reconcile_parent_task_cur(cur, parent_id)
        return runs
