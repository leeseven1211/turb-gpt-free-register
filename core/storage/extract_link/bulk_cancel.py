"""提链工作台排队取消：按块集合变更，本地账号补偿与 Run 归属分开收口。"""
from __future__ import annotations

from datetime import datetime
import json
import logging
import uuid

from core.storage import postgres, records
from core.storage.operations import store as operation
from core.storage.operations import common, projection

logger = logging.getLogger(__name__)
_CHUNK_SIZE = 500
_REASON = "用户取消提链批次的排队任务"


def _snapshot(batch_id):
    """冻结整批目标和取消前账号版本，不随取消后列表缩短而漏项。"""
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT task.id AS task_id,run.id AS run_id,task.account_id,
                    task.status,account.xmin::text AS account_version
                FROM {operation._table('operation_tasks')} task
                JOIN {operation._table('operation_runs')} run ON run.id=task.last_run_id
                JOIN {operation._table('operation_batches')} batch ON batch.id=task.batch_id
                LEFT JOIN {postgres.qualified(records.ACCOUNTS.name)} account ON account.id=task.account_id
                WHERE task.batch_id=%s AND task.task_type='extract_link'
                  AND task.source_system='native_operations' AND run.source_system='native_operations'
                  AND batch.batch_type='extract_link' AND batch.source_system='native_operations'
                  AND batch.data->>'workbench_batch'='true'
                  AND task.status IN ('queued','cancelled')
                  AND lower(COALESCE(task.data->>'deleted_by_user','false')) <> 'true'
                ORDER BY run.id""", (batch_id,))
        return [dict(row) for row in cur.fetchall()]


def _write_cancel_events(cur, rows):
    if not rows:
        return
    payload = [{"event_uuid":uuid.uuid4().hex,"task_id":row['task_id'],"run_id":row['id'],
        "source_system":row['source_system']} for row in rows]
    cur.execute(f"""INSERT INTO {operation._table('operation_events')}
        (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
        SELECT item.event_uuid,item.task_id,item.run_id,item.source_system,item.event_uuid,
               'WARNING','complete','run.cancel_requested',%s,
               '{{"previous_status":"queued","status":"cancelled"}}'::jsonb
        FROM jsonb_to_recordset(%s::jsonb)
            AS item(event_uuid text,task_id bigint,run_id bigint,source_system text)""",
        (_REASON,json.dumps(payload)))


def _cancel_chunk(rows):
    """保持既有 Run→Task 写锁顺序；业务事实和取消事件一次提交。"""
    ids=[row['run_id'] for row in rows]
    if not ids:
        return []
    with operation._connect() as conn,conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {operation._table('operation_runs')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",(ids,))
        cur.fetchall()
        cur.execute(f"""UPDATE {operation._table('operation_runs')} run
            SET status='cancelled',cancel_requested_at=COALESCE(run.cancel_requested_at,now()),
                cancel_reason=%s,heartbeat_at=now(),completed_at=now()
            FROM {operation._table('operation_tasks')} task
            WHERE run.id=ANY(%s) AND run.status='queued' AND task.id=run.task_id
              AND task.last_run_id=run.id AND task.task_type='extract_link'
              AND task.source_system='native_operations' AND run.source_system='native_operations'
            RETURNING run.id,run.task_id,run.account_id,run.batch_id,run.source_system""",(_REASON,ids))
        cancelled=[dict(row) for row in cur.fetchall()]
        if cancelled:
            updated_ids=[row['id'] for row in cancelled]
            cur.execute(f"""UPDATE {operation._table('operation_tasks')} task
                SET status='cancelled',current_stage='complete',updated_at=now(),completed_at=now()
                FROM {operation._table('operation_runs')} run
                WHERE run.id=ANY(%s) AND task.id=run.task_id AND task.last_run_id=run.id""",(updated_ids,))
            cur.execute(f"UPDATE {operation._table('account_operation_leases')} SET cancel_requested_at=now() WHERE run_id=ANY(%s)",(updated_ids,))
            _write_cancel_events(cur,cancelled)
            projection._refresh_batches(cur,sorted({int(row['batch_id']) for row in cancelled if row['batch_id']}))
        return cancelled


def _account_time(account, field, tz):
    try:
        return datetime.fromisoformat(str(account.get(field) or '').replace('Z','+00:00')).astimezone(tz)
    except (TypeError,ValueError,OverflowError):
        return None


def _sync_accounts(rows, *, freshly_cancelled):
    """集合复核最新 Run、账号版本及其他提链占用；成功产物不被取消覆盖。"""
    selected=[row for row in rows if row.get('account_id')]
    if not selected:
        return set()
    ids=[row['run_id'] for row in selected]
    expected={row['run_id']:row.get('account_version') for row in selected}
    with operation._connect() as conn,conn.cursor() as cur:
        # 和既有账号补偿相同，只锁 Task，不持 Run 锁等待账号锁。
        cur.execute(f"""SELECT run.id AS run_id,run.task_id,run.account_id,run.status,run.source_system,
                run.created_at,run.cancel_requested_at,task.task_type,task.last_run_id,task.source_system AS task_source,
                COALESCE(lower(job.extraction_state) IN ('succeeded','success')
                    OR lower(job.public_state->>'extraction_state') IN ('succeeded','success')
                    OR job.public_state->'summary'->'extraction_ever_succeeded'='true'::jsonb,false) AS extraction_succeeded
            FROM {operation._table('operation_runs')} run
            JOIN {operation._table('operation_tasks')} task ON task.id=run.task_id
            LEFT JOIN {operation._table('extract_link_provider_jobs')} job ON job.run_id=run.id
            WHERE run.id=ANY(%s) ORDER BY task.id FOR UPDATE OF task""",(ids,))
        runs=[dict(row) for row in cur.fetchall()]
        account_ids=sorted({int(row['account_id']) for row in runs if row['account_id']})
        cur.execute(f"SELECT *,xmin::text AS __record_version FROM {postgres.qualified(records.ACCOUNTS.name)} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",(account_ids,))
        accounts={row['id']:records.merge_row(records.ACCOUNTS,dict(row)) for row in cur.fetchall()}
        cur.execute(f"""SELECT candidate.id AS run_id
            FROM {operation._table('operation_runs')} candidate
            WHERE candidate.id=ANY(%s) AND EXISTS (
                SELECT 1 FROM {operation._table('operation_tasks')} other
                LEFT JOIN {operation._table('operation_runs')} related ON related.task_id=other.id
                WHERE other.account_id=candidate.account_id AND other.task_type='extract_link'
                  AND (other.id>candidate.task_id OR related.id>candidate.id
                    OR (related.id<>candidate.id AND related.status=ANY(%s))
                    OR (other.id<>candidate.task_id AND other.status=ANY(%s))))""",
            (ids,sorted(common._ACTIVE_RUN_STATUSES),sorted(common._ACTIVE_RUN_STATUSES)))
        protected={row['run_id'] for row in cur.fetchall()}
        failed=set();patches={};now=datetime.now().isoformat(timespec='seconds')
        for run in runs:
            run_id=run['run_id'];account=accounts.get(run['account_id'])
            if (run['source_system']!='native_operations' or run['task_source']!='native_operations'
                    or run['task_type']!='extract_link' or run['status']!='cancelled'
                    or run['cancel_requested_at'] is None or run['last_run_id']!=run_id
                    or not account or str(account.get('extract_link_status') or '').lower() not in {'queued','running'}
                    or run_id in protected):
                continue
            queued_at=_account_time(account,'extract_link_queued_at',run['created_at'].tzinfo)
            version=expected.get(run_id)
            if freshly_cancelled and version is not None:
                if ((str(account['__record_version'])!=str(version))
                        or (queued_at is not None and queued_at>run['created_at'])):
                    failed.add(run_id);continue
            else:
                cutoff=min(run['created_at'],run['cancel_requested_at']).replace(microsecond=0)
                started_at=_account_time(account,'extract_link_started_at',run['created_at'].tzinfo)
                if (queued_at is None or queued_at>=cutoff or
                    (str(account.get('extract_link_status') or '').lower()=='running'
                        and (started_at is None or started_at>=cutoff))):
                    failed.add(run_id);continue
            succeeded=bool(run['extraction_succeeded'])
            patches[run['account_id']]={"id":run['account_id'],"status":"success" if succeeded else "cancelled",
                "facts":{"extract_link_ok":succeeded,"extract_link_error":None,
                    "extract_link_message":"已保留提链成功结果" if succeeded else "用户取消提链任务",
                    "extract_link_completed_at":now}}
        if patches:
            cur.execute(f"""UPDATE {postgres.qualified(records.ACCOUNTS.name)} account
                SET extract_link_status=item.status,data=account.data||item.facts,updated_at=%s
                FROM jsonb_to_recordset(%s::jsonb) AS item(id bigint,status text,facts jsonb)
                WHERE account.id=item.id""",(now,json.dumps(list(patches.values()),ensure_ascii=False)))
        return failed


def cancel_batch(batch_id: int) -> dict:
    """取消整批快照里的排队目标，已完成块保留，失败块可再次取消。"""
    if type(batch_id) is not int or batch_id<1:
        raise ValueError('batch_id 参数无效')
    operation.init()
    rows=_snapshot(batch_id)
    queued=[row for row in rows if row['status']=='queued']
    historical=[row for row in rows if row['status']=='cancelled']
    cancelled=skipped=failed=0
    for offset in range(0,len(queued),_CHUNK_SIZE):
        chunk=queued[offset:offset+_CHUNK_SIZE]
        try:
            changed=_cancel_chunk(chunk)
        except Exception as exc:
            failed+=len(chunk)
            logger.warning('[提链] 批次取消块失败：batch_id=%s count=%s error_type=%s',batch_id,len(chunk),type(exc).__name__)
            continue
        changed_ids={row['id'] for row in changed}
        skipped+=len(chunk)-len(changed_ids)
        try:
            sync_failed=_sync_accounts([row for row in chunk if row['run_id'] in changed_ids],freshly_cancelled=True)
        except Exception as exc:
            sync_failed={row['id'] for row in changed if row.get('account_id')}
            logger.warning('[提链] 批次取消账号补偿失败：batch_id=%s error_type=%s',batch_id,type(exc).__name__)
        failed+=len(sync_failed)
        cancelled+=len(changed_ids)-len(sync_failed)
    for offset in range(0,len(historical),_CHUNK_SIZE):
        chunk=historical[offset:offset+_CHUNK_SIZE]
        try:
            failed+=len(_sync_accounts(chunk,freshly_cancelled=False))
        except Exception as exc:
            failed+=sum(bool(row.get('account_id')) for row in chunk)
            logger.warning('[提链] 历史取消账号补偿失败：batch_id=%s error_type=%s',batch_id,type(exc).__name__)
    return {'batch_id':batch_id,'cancelled':cancelled,'skipped':skipped,'failed':failed}
