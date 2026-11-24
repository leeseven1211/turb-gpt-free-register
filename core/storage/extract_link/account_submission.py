"""账号页提链受理的集合读取和条件占用，连接由应用事务拥有。"""
from __future__ import annotations

import json

from core import db
from core.storage import records
from core.storage.operations import common


def read_accounts(account_ids, *, conn):
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {records._qualified(records.ACCOUNTS)} "
                    "WHERE id=ANY(%s) ORDER BY id FOR UPDATE", (account_ids,))
        return {int(row["id"]): records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()}


def active_accounts(account_ids, *, conn):
    with conn.cursor() as cur:
        cur.execute(f"SELECT account_id,task_id,id AS run_id FROM {common._table('operation_runs')} "
                    "WHERE account_id=ANY(%s) AND resource_family='openai_interactive' "
                    "AND status=ANY(%s) ORDER BY account_id,id",
                    (account_ids, sorted(common._ACTIVE_RUN_STATUSES)))
        return {int(row["account_id"]): dict(row) for row in cur.fetchall()}


def claim_accounts(targets, *, trigger, conn):
    """一个条件 UPDATE 保存各账号原有阶段字段和各自选择的提链类型。"""
    if not targets:
        return set()
    now = db._now()
    guard, guard_params = db._stage_claim_guard("extract_link")
    facts = {
        "extract_link_ok": False, "extract_link_trigger": trigger,
        "extract_link_queued_at": now, "extract_link_started_at": None,
        "extract_link_completed_at": None, "extract_link_error": None,
        "extract_link_message": "已入队", "extract_link_checked_at": now,
    }
    with conn.cursor() as cur:
        cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} account
            SET extract_link_status='queued',updated_at=%s,
                data=account.data || %s::jsonb || jsonb_build_object('extract_link_type',selected.link_type)
            FROM jsonb_to_recordset(%s::jsonb) AS selected(account_id bigint,link_type text)
            WHERE account.id=selected.account_id AND ({guard})
            RETURNING account.id""",
            (now, json.dumps(facts, ensure_ascii=False), json.dumps([
                {"account_id": item["account_id"], "link_type": item["link_type"]} for item in targets
            ]), *guard_params))
        return {int(row["id"]) for row in cur.fetchall()}


def finish_batch(batch_id, *, started_count, busy_count, failed_count, skipped_count, conn):
    with conn.cursor() as cur:
        cur.execute(f"""UPDATE {common._table('operation_batches')} SET
            status=CASE WHEN %s>0 THEN status ELSE 'failed' END,
            data=data || %s::jsonb WHERE id=%s""",
            (started_count, json.dumps({
                "busy_count": busy_count, "failed_count": failed_count, "skipped_count": skipped_count,
            }), batch_id))
