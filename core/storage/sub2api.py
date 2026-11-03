"""Sub2API 补传与巡检状态；只保存引用、摘要和阶段，不复制凭证。"""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from psycopg.rows import dict_row

from core.storage import postgres

_READY = set()
_INIT_LOCK = threading.Lock()
ACTIVE = ("queued", "running", "waiting", "cancelling", "settling", "stopping")
_REPAIR_FIELDS = frozenset(
    {
        "stage",
        "remote_account_ids",
        "source_generation",
        "run_id",
        "task_id",
        "next_attempt_at",
        "last_code",
        "attempt_count",
        "last_sync_generation",
        "last_sync_at",
        "manual_requested",
    }
)


def _table():
    return postgres.qualified("sub2api_sync_jobs")


def init():
    """建表跟随现有 PostgreSQL 的数据库保护和 schema 隔离。"""
    postgres.ensure_schema()
    key = (postgres.database_url(), postgres.schema_name())
    with _INIT_LOCK:
        if key in _READY:
            return
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (_table() + ":init",))
            cur.execute(f"""CREATE TABLE IF NOT EXISTS {_table()} (
                id BIGSERIAL PRIMARY KEY, filename TEXT NOT NULL, backend TEXT NOT NULL,
                target_key BIGINT NOT NULL DEFAULT 0, remote_account_id BIGINT,
                account_id BIGINT, credential_id BIGINT, email TEXT NOT NULL DEFAULT '', generation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', stage TEXT NOT NULL DEFAULT 'pending',
                error_code TEXT, error TEXT, trigger TEXT NOT NULL DEFAULT 'manual',
                attempt_count INTEGER NOT NULL DEFAULT 0, dispatch_no INTEGER NOT NULL DEFAULT 0,
                dispatch_requested BOOLEAN NOT NULL DEFAULT TRUE,
                task_id BIGINT, run_id BIGINT, next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(filename,backend,target_key))""")
            cur.execute(
                f"ALTER TABLE {_table()} ADD COLUMN IF NOT EXISTS dispatch_requested BOOLEAN NOT NULL DEFAULT TRUE"
            )
            cur.execute(f"ALTER TABLE {_table()} ADD COLUMN IF NOT EXISTS credential_id BIGINT")
            cur.execute(f"""CREATE UNIQUE INDEX IF NOT EXISTS sub2api_sync_credential_target
                ON {_table()} (credential_id,backend,target_key) WHERE credential_id IS NOT NULL""")
            cur.execute(f"CREATE INDEX IF NOT EXISTS sub2api_sync_jobs_due ON {_table()} (status,next_attempt_at)")
            cur.execute(f"""CREATE TABLE IF NOT EXISTS {postgres.qualified("sub2api_monitor_repairs")} (
                backend TEXT NOT NULL, account_id BIGINT NOT NULL, data JSONB NOT NULL DEFAULT '{{}}',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(backend,account_id))""")
        _READY.add(key)


def credential_generation(auth_json):
    """内容摘要只用于比较凭证代际，原始凭证不写入补传表。"""
    return hashlib.sha256(
        json.dumps(auth_json, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def _public(row):
    if row is None:
        return None
    item = dict(row)
    due = item.get("next_attempt_at")
    item["retry_in_seconds"] = max(0, (due - datetime.now(timezone.utc)).total_seconds()) if due else 0
    for name, value in item.items():
        if isinstance(value, datetime):
            item[name] = value.isoformat()
    return item


def list_jobs(*, filename=None, backend=None):
    init()
    clauses, args = [], []
    for key, value in (("filename", filename), ("backend", backend)):
        if value is not None:
            clauses.append(f"{key}=%s")
            args.append(value)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table()}{where} ORDER BY id", args)
        return [_public(row) for row in cur.fetchall()]


def queue(
    filename,
    *,
    backend,
    generation,
    account_id,
    email,
    credential_id=None,
    remote_account_ids=None,
    trigger="manual",
    delay_seconds=0,
    failure=None,
):
    """同后端逐目标幂等更新；新代际覆盖待同步状态，旧 Run 只保留在任务历史。"""
    init()
    remote_ids = None if remote_account_ids is None else list(dict.fromkeys(remote_account_ids))
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (_table() + str(credential_id or filename) + backend,),
        )
        cur.execute(
            f"""SELECT * FROM {_table()} WHERE (filename=%s OR credential_id=%s)
            AND backend=%s ORDER BY id FOR UPDATE""",
            (filename, credential_id, backend),
        )
        existing = list(cur.fetchall())
        targets = remote_ids or [row["remote_account_id"] or row["target_key"] for row in existing] or [0]
        results = []
        for target in dict.fromkeys(targets):
            row = next((r for r in existing if r["target_key"] == target or r["remote_account_id"] == target), None)
            if row is None:
                cur.execute(
                    f"""INSERT INTO {_table()}
                    (filename,backend,target_key,remote_account_id,account_id,credential_id,email,generation,trigger,next_attempt_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,now()+(%s*interval '1 second')) RETURNING *""",
                    (
                        filename,
                        backend,
                        target,
                        target or None,
                        account_id,
                        credential_id,
                        email,
                        generation,
                        trigger,
                        max(0, delay_seconds),
                    ),
                )
                row = cur.fetchone()
            else:
                if row["filename"] != filename or row["credential_id"] != credential_id:
                    cur.execute(
                        f"UPDATE {_table()} SET filename=%s,credential_id=%s WHERE id=%s RETURNING *",
                        (filename, credential_id, row["id"]),
                    )
                    row = cur.fetchone()
                changed = row["generation"] != generation
                # 成功和活跃 Run 在同一代际幂等；巡检反复查询不会重复上传。
                if changed or (row["status"] not in (*ACTIVE, "success") and trigger == "manual"):
                    cur.execute(
                        f"""UPDATE {_table()} SET generation=%s,account_id=%s,email=%s,
                        status='pending',stage='pending',error_code=NULL,error=NULL,trigger=%s,
                        dispatch_requested=TRUE,
                        attempt_count=CASE WHEN generation<>%s THEN 0 ELSE attempt_count END,
                        task_id=NULL,run_id=NULL,next_attempt_at=now()+(%s*interval '1 second'),updated_at=now()
                        WHERE id=%s RETURNING *""",
                        (generation, account_id, email, trigger, generation, max(0, delay_seconds), row["id"]),
                    )
                    row = cur.fetchone()
                elif account_id and not row["account_id"]:
                    cur.execute(
                        f"""UPDATE {_table()} SET account_id=%s,email=%s,stage='pending',
                        error_code=NULL,error=NULL,next_attempt_at=now(),updated_at=now() WHERE id=%s RETURNING *""",
                        (account_id, email, row["id"]),
                    )
                    row = cur.fetchone()
            if not failure and row["status"] in ("pending", "blocked_backend"):
                cur.execute(f"UPDATE {_table()} SET dispatch_requested=TRUE WHERE id=%s RETURNING *", (row["id"],))
                row = cur.fetchone()
            if failure and row["status"] not in ACTIVE:
                cur.execute(
                    f"""UPDATE {_table()} SET status='pending',stage=%s,error_code=%s,error=%s,
                    dispatch_requested=FALSE,
                    attempt_count=attempt_count+1,next_attempt_at=now()+(%s*interval '1 second'),updated_at=now()
                    WHERE id=%s AND generation=%s RETURNING *""",
                    (
                        failure.get("stage", "upload"),
                        failure.get("error_code", "sub2api_sync_failed"),
                        failure.get("error", "Sub2API 同步失败"),
                        max(1, delay_seconds),
                        row["id"],
                        generation,
                    ),
                )
                row = cur.fetchone()
            results.append(_public(row))
        return results


def enqueue_due(backend, submit, *, include_retries=True):
    """行锁与 durable 提交共用事务；多进程扫描不会重复创建活跃 Run。"""
    from core.storage.operations import store as operation

    operation.init()
    init()
    queued = pending = 0
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {_table()} SET status='blocked_backend',stage='configuration',
            error_code='sub2api_backend_changed',error='Sub2API 后端已变化，旧目标保留等待原后端',updated_at=now()
            WHERE backend<>%s AND status='pending'""",
            (backend,),
        )
        cur.execute(
            f"""UPDATE {_table()} j SET status='cancelled',stage='cancelled',
            dispatch_requested=FALSE,error_code='sub2api_sync_cancelled',error='用户已停止补传，可手动再次排队',updated_at=now()
            FROM {operation._table("operation_runs")} r WHERE r.id=j.run_id AND j.status=ANY(%s)
            AND r.status IN ('cancelled','stopped','terminated')""",
            (list((*ACTIVE, "pending", "blocked_backend")),),
        )
        cur.execute(
            f"""UPDATE {_table()} j SET status='pending',stage='recovered',task_id=NULL,run_id=NULL,
            dispatch_requested=TRUE,next_attempt_at=now(),updated_at=now() WHERE j.status=ANY(%s) AND NOT EXISTS
            (SELECT 1 FROM {operation._table("operation_runs")} r WHERE r.id=j.run_id AND r.status=ANY(%s))""",
            (list(ACTIVE), list(ACTIVE)),
        )
        cur.execute(
            f"""SELECT * FROM {_table()} WHERE backend=%s AND status IN ('pending','blocked_backend')
            AND (dispatch_requested OR %s) AND next_attempt_at<=now()
            ORDER BY next_attempt_at,id FOR UPDATE SKIP LOCKED LIMIT 100""",
            (backend, bool(include_retries)),
        )
        for row in list(cur.fetchall()):
            if not row["account_id"]:
                cur.execute(
                    f"""UPDATE {_table()} SET stage='waiting_account',error_code='sub2api_local_account_missing',
                    error='本地账号暂不存在，等待账号恢复后继续补传',updated_at=now() WHERE id=%s""",
                    (row["id"],),
                )
                pending += 1
                continue
            submitted = submit(row, conn)
            if not submitted.get("accepted"):
                blocked = submitted.get("blocked_status")
                cur.execute(
                    f"""UPDATE {_table()} SET status=COALESCE(%s,status),stage=%s,error_code=%s,error=%s,
                    dispatch_requested=CASE WHEN %s THEN FALSE ELSE dispatch_requested END,
                    updated_at=now() WHERE id=%s""",
                    (
                        blocked,
                        "blocked" if blocked else "waiting_lease",
                        submitted.get("error_code") or "sub2api_account_busy",
                        submitted.get("error")
                        if blocked
                        else (
                            "账号已有操作，稍后补传" if submitted.get("busy") else "账号当前无法入队，保留补传等待重试"
                        ),
                        bool(blocked),
                        row["id"],
                    ),
                )
                pending += 1
                continue
            cur.execute(
                f"""UPDATE {_table()} SET status='queued',stage='queued',task_id=%s,run_id=%s,
                filename=%s,credential_id=%s,attempt_count=CASE WHEN generation<>%s THEN 0 ELSE attempt_count END,generation=%s,
                dispatch_requested=FALSE,dispatch_no=dispatch_no+1,updated_at=now() WHERE id=%s AND generation=%s""",
                (
                    submitted["task_id"],
                    submitted["run_id"],
                    row["filename"],
                    row["credential_id"],
                    row["generation"],
                    row["generation"],
                    row["id"],
                    row.get("previous_generation", row["generation"]),
                ),
            )
            queued += 1
    return {"queued": queued, "pending": pending}


def job_counts():
    """状态页只查询聚合数量，避免将账号引用带到公开运行状态。"""
    init()
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT status,count(*) AS n FROM {_table()} GROUP BY status")
        return {row["status"]: int(row["n"]) for row in cur.fetchall()}


def has_dispatch_requests(backend):
    """已经接受的一次性请求即使全局自动开关关闭也必须完成投递。"""
    init()
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT EXISTS(SELECT 1 FROM {_table()} WHERE backend=%s AND
            ((dispatch_requested AND status IN ('pending','blocked_backend')) OR status=ANY(%s)))""",
            (backend, list(ACTIVE)),
        )
        return bool(cur.fetchone()[0])


def begin(job_id, *, generation, run_id):
    init()
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {_table()} SET status='running',stage='upload',attempt_count=attempt_count+1,
            updated_at=now() WHERE id=%s AND generation=%s AND run_id=%s AND status=ANY(%s) RETURNING *""",
            (job_id, generation, run_id, list(ACTIVE)),
        )
        return _public(cur.fetchone())


def rename_reference(job_id, *, filename, generation, run_id):
    init()
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE {_table()} SET filename=%s,updated_at=now() WHERE id=%s AND generation=%s AND run_id=%s",
            (filename, job_id, generation, run_id),
        )


def cancel(job_id, *, generation, run_id, execution_id):
    """取消只收口匹配的执行，不写凭证元数据，也不替代账号租约。"""
    from core.storage.operations import store as operation

    init()
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {_table()} j SET status='cancelled',stage='cancelled',
            dispatch_requested=FALSE,error_code='sub2api_sync_cancelled',error='用户已停止补传，可手动再次排队',updated_at=now()
            FROM {operation._table("operation_runs")} r WHERE j.id=%s AND j.generation=%s AND j.run_id=%s
            AND r.id=j.run_id AND r.execution_id=%s""",
            (job_id, generation, run_id, execution_id),
        )
        return cur.rowcount == 1


def finish(
    job_id,
    *,
    generation,
    run_id,
    status,
    stage,
    error_code=None,
    error=None,
    remote_account_id=None,
    delay_seconds=0,
    write_metadata=None,
    fence=None,
):
    """旧代际/旧 Run 不可回写；元数据在持有该目标行锁期间一起确认。"""
    init()
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        if fence is not None:
            from core.storage.operations import store as operation

            operation.fence_execution(cur, run_id, execution_id=fence["execution_id"], lease_token=fence["lease_token"])
        cur.execute(
            f"SELECT * FROM {_table()} WHERE id=%s AND generation=%s AND run_id=%s FOR UPDATE",
            (job_id, generation, run_id),
        )
        if not cur.fetchone():
            return False
        if write_metadata is not None:
            write_metadata()
        cur.execute(
            f"""UPDATE {_table()} SET status=%s,stage=%s,error_code=%s,error=%s,
            dispatch_requested=%s,
            remote_account_id=COALESCE(%s,remote_account_id),next_attempt_at=now()+(%s*interval '1 second'),
            updated_at=now() WHERE id=%s""",
            (
                status,
                stage,
                error_code,
                error,
                status == "blocked_backend",
                remote_account_id,
                max(0, delay_seconds),
                job_id,
            ),
        )
        return True


def save_repair(backend_key, account_id, **fields):
    """巡检阶段白名单，不接收凭证或任意远端正文。"""
    unknown = set(fields) - _REPAIR_FIELDS
    if unknown:
        raise ValueError("巡检状态包含未允许字段：" + ",".join(sorted(unknown)))
    init()
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {postgres.qualified("sub2api_monitor_repairs")} (backend,account_id,data)
            VALUES (%s,%s,%s::jsonb) ON CONFLICT(backend,account_id) DO UPDATE
            SET data={postgres.qualified("sub2api_monitor_repairs")}.data || EXCLUDED.data,updated_at=now() RETURNING *""",
            (backend_key, int(account_id), json.dumps(fields, ensure_ascii=False, default=str)),
        )
        return _repair_row(cur.fetchone())


def _repair_row(row):
    if row is None:
        return None
    return {
        **dict(row.get("data") or {}),
        "backend": row["backend"],
        "account_id": int(row["account_id"]),
        "updated_at": row["updated_at"].isoformat(),
    }


def get_repair(backend_key, account_id):
    init()
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {postgres.qualified('sub2api_monitor_repairs')} WHERE backend=%s AND account_id=%s",
            (backend_key, int(account_id)),
        )
        return _repair_row(cur.fetchone())


def list_repairs(backend_key, active_only=True):
    init()
    where = " AND COALESCE(data->>'stage','idle') NOT IN ('idle','done')" if active_only else ""
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {postgres.qualified('sub2api_monitor_repairs')} WHERE backend=%s{where} ORDER BY account_id",
            (backend_key,),
        )
        return [_repair_row(row) for row in cur.fetchall()]


@contextmanager
def repair_lock(backend_key, account_id):
    """会话级 PostgreSQL 锁覆盖整轮决策；其他进程可直接跳过占用账号。"""
    init()
    key = postgres.qualified("sub2api_monitor_repairs") + str(backend_key) + ":" + str(int(account_id))
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (key,))
        acquired = bool(cur.fetchone()[0])
        try:
            yield acquired
        finally:
            if acquired:
                cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (key,))
