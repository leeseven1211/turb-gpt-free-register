"""批量终止的不可变 Run 范围；实际安全结算不借用此仓储事务。"""
from __future__ import annotations

import json

from core.storage import records
from core.storage.operations import bulk_facts, bulk_mutations as commands, common

TABLE = "operation_bulk_terminate_targets"


def init():
    commands.init()
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""CREATE TABLE IF NOT EXISTS {common._table(TABLE)} (
            command_id BIGINT NOT NULL REFERENCES {common._table(commands._COMMANDS)}(id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL,
            task_id BIGINT NOT NULL,
            run_id BIGINT,
            task_type TEXT NOT NULL,
            source_system TEXT NOT NULL,
            initial_status TEXT NOT NULL,
            reason_code TEXT,
            children JSONB NOT NULL DEFAULT '[]'::jsonb,
            PRIMARY KEY(command_id,ordinal)
        )""")


def freeze(command_id, task_ids, *, conn):
    tasks = bulk_facts.get_action_tasks_many(task_ids, conn=conn)
    children = {}
    parent_ids = [task_id for task_id, task in tasks.items() if task["task_type"] == "account_inspection_batch"]
    with conn.cursor() as cur:
        if parent_ids:
            cur.execute(f"""SELECT t.parent_task_id,r.id AS run_id,r.status
                FROM {common._table('operation_tasks')} t
                JOIN {common._table('operation_runs')} r ON r.task_id=t.id
                WHERE t.parent_task_id=ANY(%s) AND r.status=ANY(%s) ORDER BY r.id""",
                (parent_ids, list(common._ACTIVE_RUN_STATUSES)))
            for row in cur.fetchall():
                children.setdefault(row["parent_task_id"], []).append(
                    {"run_id": row["run_id"], "status": row["status"]})
        rows = []
        for ordinal, task_id in enumerate(task_ids):
            task = tasks.get(task_id) or {}
            active = next((run for run in reversed(task.get("runs") or [])
                           if run["status"] in common._ACTIVE_RUN_STATUSES), None)
            state = str(task.get("status") or "")
            reason = "task_not_found" if not task else (
                "target_not_running" if task.get("source_system") != "native_operations"
                or state not in common._ACTIVE_RUN_STATUSES or state == "queued" or not active else None)
            rows.append({
                "ordinal": ordinal, "task_id": task_id, "run_id": active["id"] if active else None,
                "task_type": task.get("task_type") or "", "source_system": task.get("source_system") or "",
                "initial_status": state, "reason_code": reason, "children": children.get(task_id, []),
            })
        cur.execute(f"""INSERT INTO {common._table(TABLE)}
            (command_id,ordinal,task_id,run_id,task_type,source_system,initial_status,reason_code,children)
            SELECT %s,s.ordinal,s.task_id,s.run_id,s.task_type,s.source_system,s.initial_status,s.reason_code,s.children
            FROM jsonb_to_recordset(%s::jsonb) AS s(ordinal INTEGER,task_id BIGINT,run_id BIGINT,
                task_type TEXT,source_system TEXT,initial_status TEXT,reason_code TEXT,children JSONB)""",
            (command_id, json.dumps(rows, ensure_ascii=False)))


def targets(command_id):
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {common._table(TABLE)} WHERE command_id=%s ORDER BY ordinal", (command_id,))
        return [dict(row) for row in cur.fetchall()]


def read_target(task_id, run_id):
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT r.*,t.last_run_id,t.task_type,t.source_system AS task_source,t.parent_task_id,t.email_snapshot
            FROM {common._table('operation_runs')} r
            JOIN {common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=%s AND t.id=%s""", (run_id, task_id))
        row = cur.fetchone()
        return dict(row) if row else None


def receipt_items(command_id):
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT chunk_index,items FROM {common._table(commands._RECEIPTS)}
            WHERE command_id=%s ORDER BY chunk_index""", (command_id,))
        return {int(row["chunk_index"]): row["items"][0] for row in cur.fetchall()}


def assert_owner(command_id, *, run_id, execution_id):
    with common._connect() as conn, conn.cursor() as cur:
        command = commands.get_command(command_id, conn=conn)
        commands._execution_fence(cur, command, run_id, execution_id)


def project_codex(run):
    """补齐原 Codex 终止的账号投影；旧 Run 永不清空后续执行的引用。"""
    state = str(run["status"])
    terminal = state not in common._ACTIVE_RUN_STATUSES
    with common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} a SET
            codex_execution_status=%s,
            codex_last_run_status=CASE WHEN %s THEN %s ELSE a.codex_last_run_status END,
            codex_active_run_id=CASE WHEN %s THEN NULL ELSE %s END,
            codex_status=CASE
                WHEN LOWER(COALESCE(a.codex_credential_state,''))='valid' THEN 'success'
                WHEN LOWER(COALESCE(a.codex_credential_state,''))='pending_confirmation' THEN 'pending_confirmation'
                WHEN LOWER(COALESCE(a.codex_credential_state,''))='deactivated' OR %s='deactivated' THEN 'deactivated'
                WHEN LOWER(COALESCE(a.codex_status,''))<>'success' AND %s=ANY(%s)
                    THEN CASE WHEN %s='cancelled' THEN 'stopped' ELSE %s END
                WHEN LOWER(COALESCE(a.codex_status,''))<>'success' AND %s=ANY(%s) THEN 'retrying'
                ELSE a.codex_status END,
            data=a.data || jsonb_build_object('codex_error','用户手动终止 Codex 补跑'),
            updated_at=CURRENT_TIMESTAMP::text
            WHERE (a.id=%s OR (%s::bigint IS NULL AND LOWER(a.email)=LOWER(%s)))
              AND (a.codex_active_run_id IS NULL OR a.codex_active_run_id=%s)
              AND NOT EXISTS (SELECT 1 FROM {common._table('operation_runs')} r
                  WHERE r.account_id=a.id AND r.id<>%s AND r.resource_family='openai_interactive'
                    AND r.status=ANY(%s))""",
            ("empty" if terminal else state, terminal, state, terminal, int(run["id"]),
             state, state, ["failed", "cancelled", "interrupted", "attention_required"], state, state,
             "empty" if terminal else state, ["queued", "running", "cancelling"],
             run.get("account_id"), run.get("account_id"), run.get("email_snapshot") or "",
             int(run["id"]), int(run["id"]), list(common._ACTIVE_RUN_STATUSES)))


def cancel_children(children):
    """集合取消冻结的精确子 Run；已提交取消意图不重复写事件。"""
    from core.storage.operations import cancellation
    ids = [int(child["run_id"]) for child in children]
    if not ids:
        return True
    with common._connect() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(f"""SELECT id,status,cancel_requested_at FROM {common._table('operation_runs')}
            WHERE id=ANY(%s) ORDER BY id""", (ids,))
        current = list(cur.fetchall())
        requests = [{"id": row["id"], "expected_status": row["status"], "reason": "用户停止本次账号巡检"}
                    for row in current if row["status"] in common._ACTIVE_RUN_STATUSES
                    and row["cancel_requested_at"] is None]
        replies = cancellation.cancel_runs_many(conn, requests)
        # 排队到运行的竞争交给同一命令下一次精确重放，不遗漏刚被认领的子 Run。
        return not any(
            reply and reply.get("cancel_skipped") and reply["status"] in common._ACTIVE_RUN_STATUSES
            for reply in replies.values()
        )
