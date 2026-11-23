"""C2A 巡检修复进度，复用同库中的账号、任务和调度事实。"""
from __future__ import annotations

from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from core.storage import postgres, records
from core.storage.operations import common as operation

_TABLE = "c2a_monitor_repairs"
ACTIVE_STAGES = ("refresh_pending", "refresh_wait", "refresh_retry", "sync_wait")
_FIELDS = (
    "stage", "email", "source_generation", "refresh_key", "refresh_workers",
    "selection_id", "batch_id", "round_id", "refresh_task_id", "refresh_run_id",
    "next_attempt_at", "last_code", "attempt_count", "targets",
    "refresh_failure_count", "refresh_observed_run_id",
)
_TARGET_FIELDS = ("state", "key", "task_id", "run_id", "observed_run_id", "next_attempt_at", "last_code", "token_generation")


def init() -> bool:
    """由执行进程初始化。状态查询直接读取已迁移的表。"""
    postgres.ensure_schema()
    table = postgres.qualified(_TABLE)
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{table}:init",))
        cur.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
            backend TEXT NOT NULL,
            account_id BIGINT NOT NULL,
            data JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (backend, account_id)
        )""")
    return True


@contextmanager
def scan_lock(backend: str):
    """同一目标每次只推进一轮，事务间的提交意图仍留在表中。"""
    key = f"{postgres.qualified(_TABLE)}:{backend}"
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (key,))
        acquired = bool(cur.fetchone()[0])
        conn.commit()
        try:
            yield acquired
        finally:
            if acquired:
                cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (key,))


def list_repairs(backend: str) -> list[dict]:
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT account_id,data FROM {postgres.qualified(_TABLE)} WHERE backend=%s ORDER BY account_id",
            (backend,),
        )
        return [dict(row["data"], account_id=row["account_id"]) for row in cur.fetchall()]


def save_repairs(backend: str, rows) -> None:
    """整批写入阶段和受理引用。表中只保留指定字段及 AT 摘要。"""
    payload = {}
    for row in rows:
        data = {name: row[name] for name in _FIELDS if name in row}
        data["targets"] = {
            remote_id: {name: target[name] for name in _TARGET_FIELDS if name in target}
            for remote_id, target in (row.get("targets") or {}).items()
        }
        account_id = int(row["account_id"])
        payload[account_id] = {"account_id": account_id, "data": data}
    if not payload:
        return
    table = postgres.qualified(_TABLE)
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(f"""INSERT INTO {table} (backend,account_id,data)
            SELECT %s, account_id, data FROM jsonb_to_recordset(%s) AS row(account_id BIGINT,data JSONB)
            ON CONFLICT (backend,account_id) DO UPDATE SET data=EXCLUDED.data,updated_at=now()""",
            (backend, Jsonb(list(payload.values()))),
        )


def has_pending(backend: str) -> bool:
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT EXISTS (
            SELECT 1 FROM {postgres.qualified(_TABLE)} WHERE backend=%s AND data->>'stage'=ANY(%s)
        )""", (backend, list(ACTIVE_STAGES)))
        return bool(cur.fetchone()[0])


def status_facts(backend: str | None, task: str) -> tuple[dict, str | None]:
    """读调度时间和阶段计数，供 Web 查询。"""
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT payload->%s->>'last_run_at'
            FROM {postgres.qualified('app_collections')} WHERE name='scheduler_state'""", (task,))
        last_run = cur.fetchone()
        counts = {}
        if backend:
            cur.execute(f"""SELECT data->>'stage', count(*) FROM {postgres.qualified(_TABLE)}
                WHERE backend=%s GROUP BY data->>'stage'""", (backend,))
            counts = dict(cur.fetchall())
        return counts, last_run[0] if last_run else None


def account_material(account_ids, emails) -> list[dict]:
    """一次读取命中账号及 AT，避免解包会话、密码和其他业务字段。"""
    if not (account_ids or emails):
        return []
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT id,email,archived,deactivated,codex_status,codex_credential_state,
                data->>'account_status' AS account_status,data->>'access_token' AS access_token
            FROM {postgres.qualified(records.ACCOUNTS.name)}
            WHERE id=ANY(%s) OR LOWER(BTRIM(email))=ANY(%s)""", (list(account_ids), list(emails)))
        return list(cur.fetchall())


def upload_runs(task_ids) -> dict[int, dict]:
    """只读巡检拥有的上传任务，任务中心显式重跑仍沿用原任务 ID。"""
    if not task_ids:
        return {}
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT t.id AS task_id,t.account_id,t.email_snapshot,r.id,r.status,
                r.cancel_requested_at,r.error_code,r.progress_stage,r.result_summary,
                r.data->>'backend_identity' AS backend,r.data->>'remote_account_id' AS remote_id,
                r.data->'monitor_managed' AS monitor_managed
            FROM {operation._table('operation_tasks')} t
            JOIN {operation._table('operation_runs')} r ON r.id=t.last_run_id
            WHERE t.id=ANY(%s) AND t.task_type='c2a_session_reimport'""", (list(task_ids),))
        return {row["task_id"]: dict(row) for row in cur.fetchall()}


def cancelled_refresh_runs(run_ids) -> set[int]:
    """批量读取精确执行的取消事实，避免公开失败投影掩盖用户取消。"""
    if not run_ids:
        return set()
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT id FROM {operation._table('operation_runs')}
            WHERE id=ANY(%s) AND (
                cancel_requested_at IS NOT NULL OR status IN ('cancelled','canceled','stopped','terminated')
                OR result_summary->>'requested_status' IN ('cancelled','canceled','stopped','terminated')
            )""", (list(run_ids),))
        return {row["id"] for row in cur.fetchall()}
