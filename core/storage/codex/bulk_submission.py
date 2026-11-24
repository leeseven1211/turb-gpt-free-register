"""Codex 执行任务集合受理的 PostgreSQL 原语，调用方拥有事务。"""
from __future__ import annotations

import json
import uuid

from core.operations import run_log
from core.storage import records
from core.storage.operations import common


def credentials(conn, *, filenames=(), emails=()):
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {records._qualified(records.CODEX_CREDENTIALS)} "
            "WHERE filename=ANY(%s) OR LOWER(BTRIM(email))=ANY(%s) "
            "ORDER BY COALESCE(mtime,updated_at) DESC,id DESC",
            (list(filenames), list(emails)),
        )
        return [records.merge_row(records.CODEX_CREDENTIALS, row) for row in cur.fetchall()]


def accounts(conn, *, account_ids=(), emails=(), for_update=True):
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {records._qualified(records.ACCOUNTS)} "
            "WHERE id=ANY(%s) OR LOWER(BTRIM(email))=ANY(%s) ORDER BY id"
            + (" FOR UPDATE" if for_update else ""),
            (list(account_ids), list(emails)),
        )
        return [records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()]


def active_runs(conn, account_ids):
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id,task_id,account_id,status FROM {common._table('operation_runs')} "
            "WHERE account_id=ANY(%s) AND resource_family='openai_interactive' AND status=ANY(%s)",
            (list(account_ids), list(common._ACTIVE_RUN_STATUSES)),
        )
        return {row["account_id"]: dict(row) for row in cur.fetchall()}


def reauthorization_runs(conn, account_ids):
    """停止仅选择原生 Codex 授权任务，不触及其他账号任务或历史来源。"""
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT r.id,r.task_id,r.account_id,r.status FROM {common._table('operation_runs')} r
            JOIN {common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.account_id=ANY(%s) AND r.resource_family='openai_interactive'
              AND r.status=ANY(%s) AND t.task_type='codex_retry'
              AND t.source_system='native_operations' AND r.source_system='native_operations'
            ORDER BY r.id""", (list(account_ids), list(common._ACTIVE_RUN_STATUSES)),
        )
        return {row["account_id"]: dict(row) for row in cur.fetchall()}


def project_cancel_requested(conn, stopped):
    if not stopped:
        return
    with conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {records._qualified(records.ACCOUNTS)} a SET
                codex_execution_status=CASE WHEN s.running THEN 'cancelling' ELSE 'empty' END,
                codex_active_run_id=CASE WHEN s.running THEN s.run_id ELSE NULL END,
                codex_last_run_status=CASE WHEN s.running THEN a.codex_last_run_status ELSE 'cancelled' END,
                data=a.data || jsonb_build_object('codex_error','用户手动停止 Codex 补跑')
            FROM jsonb_to_recordset(%s::jsonb) AS s(id BIGINT,run_id BIGINT,running BOOLEAN)
            WHERE a.id=s.id AND a.codex_active_run_id=s.run_id""",
            (json.dumps(stopped, ensure_ascii=False),),
        )


def refresh_fences(conn, account_ids):
    """与既有 durable producer fence 相同，当前 run 未核验就禁止新 grant。"""
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT DISTINCT t.account_id FROM {common._table('operation_tasks')} t
            JOIN {common._table('operation_runs')} r ON r.id=t.last_run_id
            WHERE t.account_id=ANY(%s) AND t.task_type='codex_token_refresh'
            AND t.source_system='native_operations' AND (
                t.status='attention_required' OR r.status='attention_required'
                OR COALESCE(r.result_summary->>'outcome','')='request_unknown'
                OR COALESCE(r.result_summary->>'reconcile_required','false')='true'
                OR (r.status NOT IN ('success','partial_success','failed','stopped','cancelled',
                    'interrupted','deactivated','unsupported','attention_required')
                    AND r.data->'remote_intent'->>'kind'='remote_write'
                    AND COALESCE(r.data->'remote_intent'->>'receipt_state',
                        r.data->'remote_intent'->>'state','started') NOT IN ('rejected','not_submitted'))
            )""", (list(account_ids),),
        )
        return {row["account_id"] for row in cur.fetchall()}


def create_batch(conn, task_type, requested_count, trigger, title):
    identity = uuid.uuid4().hex
    with conn.cursor() as cur:
        cur.execute(f"""INSERT INTO {common._table('operation_batches')}
            (batch_uuid,source_system,source_id,batch_type,title,status,requested_count,created_by,data)
            VALUES (%s,'native_operations',%s,%s,%s,'queued',%s,%s,'{{}}'::jsonb) RETURNING id,batch_uuid""",
            (identity, identity, task_type, title, requested_count, trigger))
        return dict(cur.fetchone())


def create_tasks(conn, specs, batch_id):
    from core.storage.operations.bulk_submission import create_specs
    enriched = []
    for ordinal, spec in enumerate(specs, 1):
        item = dict(spec)
        item["batch_id"] = batch_id
        item["batch_ordinal"] = ordinal
        enriched.append(item)
    return create_specs(enriched, conn=conn)


def project_queued(conn, rows):
    values = [{"account_id": row["account_id"], "run_id": row["run_id"]} for row in rows if not row["reused"]]
    if not values:
        return
    with conn.cursor() as cur:
        cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} a
            SET codex_execution_status='queued',codex_active_run_id=s.run_id,
                codex_status=CASE WHEN a.codex_credential_state='valid' THEN 'success'
                    WHEN a.codex_credential_state='pending_confirmation' THEN 'pending_confirmation'
                    WHEN a.codex_credential_state='deactivated' THEN 'deactivated'
                    WHEN a.codex_status='success' THEN a.codex_status ELSE 'retrying' END,
                updated_at=CURRENT_TIMESTAMP::text
            FROM jsonb_to_recordset(%s::jsonb) AS s(account_id BIGINT,run_id BIGINT) WHERE a.id=s.account_id""",
            (json.dumps(values),))


def finish_batch(conn, batch_id, skipped, accepted):
    with conn.cursor() as cur:
        cur.execute(f"""UPDATE {common._table('operation_batches')} SET
            data=data || %s::jsonb, status=CASE WHEN %s THEN status ELSE 'failed' END WHERE id=%s""",
            (json.dumps({"skipped": skipped, "skipped_count": len(skipped)}, ensure_ascii=False), accepted, batch_id))
