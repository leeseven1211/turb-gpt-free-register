"""Sub2API 一轮巡检的集合快照、修复阶段及补传受理。"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import json

from psycopg.rows import dict_row

from core.storage import postgres as pg, records, sub2api
from core.storage.operations import bulk_submission, common, schema

_INTERACTIVE_ACTIVE = ("queued", "running", "cancelling", "settling", "stopping")


def initialize():
    records.init()
    sub2api.init()
    schema.init_operation_schema()


def accounts(account_ids, emails):
    if not account_ids and not emails:
        return []
    with pg.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {pg.qualified(records.ACCOUNTS.name)} "
                    "WHERE id=ANY(%s) OR lower(email)=ANY(%s) ORDER BY id",
                    (list(account_ids), list(emails)))
        return [records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()]


@contextmanager
def repair_locks(backend, account_ids):
    """同一批会话锁保留旧的逐账号互斥语义，一条 SQL 尝试全部锁。"""
    keys = {int(value): pg.qualified("sub2api_monitor_repairs") + str(backend) + ":" + str(int(value))
            for value in sorted(set(account_ids))}
    with pg.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute("SELECT id,pg_try_advisory_lock(hashtextextended(key,0)) AS acquired "
                    "FROM jsonb_to_recordset(%s::jsonb) AS s(id bigint,key text) ORDER BY id",
                    (json.dumps([{"id": key, "key": value} for key, value in keys.items()]),))
        acquired = {row["id"] for row in cur.fetchall() if row["acquired"]}
        try:
            yield acquired
        finally:
            if acquired:
                cur.execute("SELECT pg_advisory_unlock(hashtextextended(key,0)) "
                            "FROM unnest(%s::text[]) AS key ORDER BY key",
                            ([keys[value] for value in sorted(acquired)],))


def snapshot(backend, account_ids):
    ids = sorted(set(account_ids))
    with pg.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {pg.qualified('sub2api_monitor_repairs')} "
                    "WHERE backend=%s AND account_id=ANY(%s)", (backend, ids))
        states = {row["account_id"]: sub2api._repair_row(row) for row in cur.fetchall()}
        cur.execute(f"SELECT c.* FROM {pg.qualified(records.CODEX_CREDENTIALS.name)} c "
                    f"JOIN {pg.qualified(records.ACCOUNTS.name)} a ON lower(c.email)=lower(a.email) "
                    "WHERE a.id=ANY(%s) ORDER BY COALESCE(c.mtime,c.updated_at) DESC,c.id DESC", (ids,))
        credentials = [records.merge_row(records.CODEX_CREDENTIALS, row) for row in cur.fetchall()]
        cur.execute(f"SELECT * FROM {common._table('operation_runs')} WHERE id=ANY(%s)",
                    ([int(row.get("run_id") or 0) for row in states.values()],))
        runs = {row["id"]: dict(row) for row in cur.fetchall()}
        cur.execute(f"SELECT * FROM {common._table('operation_runs')} "
                    "WHERE account_id=ANY(%s) AND resource_family='openai_interactive' AND status=ANY(%s) ORDER BY id DESC",
                    (ids, list(_INTERACTIVE_ACTIVE)))
        active = {}
        for row in cur.fetchall():
            active.setdefault(row["account_id"], dict(row))
        cur.execute(f"SELECT * FROM {sub2api._table()} WHERE backend=%s AND account_id=ANY(%s) ORDER BY id",
                    (backend, ids))
        jobs = [sub2api._public(row) for row in cur.fetchall()]
    return {"states": states, "credentials": credentials, "runs": runs, "active": active, "jobs": jobs}


def login_material(selected):
    """一次集合预取所有需 OTP 的本地收件资料；不领取地址或修改租约。"""
    from core.email.inventory import TABLES

    emails = sorted({str(row.get("email") or "").strip().lower() for row in selected})
    pools, profiles, bindings, orders = defaultdict(dict), {}, set(), []
    sources = {str(row.get("email_source") or "").strip() for row in selected}
    with pg.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT address_norm FROM {pg.qualified(records.EMAIL_ADDRESS_ALLOCATIONS.name)} "
                    "WHERE address_norm=ANY(%s)", (emails,))
        bindings = {row["address_norm"] for row in cur.fetchall()}
        for source in sorted(sources & set(TABLES)):
            spec = TABLES[source]
            cur.execute(f"SELECT * FROM {pg.qualified(spec.name)} WHERE lower(email)=ANY(%s)", (emails,))
            pools[source] = {str(row["email"]).lower(): records.merge_row(spec, row) for row in cur.fetchall()}
        profile_ids = {int(row.get("local_inbox_profile_id") or row.get("inbox_profile_id") or 0)
                       for row in pools["email_butler"].values()}
        if profile_ids - {0}:
            cur.execute(f"SELECT * FROM {pg.qualified(records.EMAIL_INBOX_PROFILES.name)} WHERE id=ANY(%s)",
                        (list(profile_ids - {0}),))
            profiles = {row["id"]: records.merge_row(records.EMAIL_INBOX_PROFILES, row) for row in cur.fetchall()}
        if sources & {"mailcode", "xigua"}:
            from core.storage.email import provider_orders

            provider_orders.init()
            cur.execute(f"SELECT * FROM {provider_orders._table()} WHERE lower(email)=ANY(%s) "
                        "AND provider=ANY(%s) ORDER BY id DESC", (emails, list(sources & {"mailcode", "xigua"})))
            orders = list(cur.fetchall())
    return {"pools": pools, "profiles": profiles, "bindings": bindings, "orders": orders}


def save_repairs(conn, backend, states):
    if not states:
        return
    payload = [{"account_id": int(account_id),
                "data": {key: value for key, value in state.items() if key in sub2api._REPAIR_FIELDS}}
               for account_id, state in states.items()]
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {pg.qualified('sub2api_monitor_repairs')} (backend,account_id,data) "
                    "SELECT %s,s.account_id,s.data FROM jsonb_to_recordset(%s::jsonb) AS s(account_id bigint,data jsonb) "
                    "ON CONFLICT(backend,account_id) DO UPDATE "
                    f"SET data={pg.qualified('sub2api_monitor_repairs')}.data || EXCLUDED.data,updated_at=now()",
                    (backend, json.dumps(payload, ensure_ascii=False, default=str)))


def _update_jobs(conn, patches):
    if not patches:
        return
    fields = ("filename", "credential_id", "account_id", "email", "generation", "status", "stage",
              "error_code", "error", "trigger", "dispatch_requested", "attempt_count", "dispatch_no",
              "task_id", "run_id", "next_attempt_at")
    assignments = ",".join(f"{name}=s.{name}" for name in fields)
    declarations = ("id bigint,filename text,credential_id bigint,account_id bigint,email text,generation text,"
                    "status text,stage text,error_code text,error text,trigger text,dispatch_requested boolean,"
                    "attempt_count integer,dispatch_no integer,task_id bigint,run_id bigint,next_attempt_at timestamptz")
    with conn.cursor() as cur:
        cur.execute(f"UPDATE {sub2api._table()} j SET {assignments},updated_at=now() "
                    f"FROM jsonb_to_recordset(%s::jsonb) AS s({declarations}) WHERE j.id=s.id",
                    (json.dumps(patches, ensure_ascii=False, default=str),))


def queue_sync_many(conn, backend, intents):
    """集合保存原凭证行、后端、目标和代际；保持同代际成功与取消的幂等性。"""
    if not intents:
        return
    by_credential = {int(item["credential_id"]): item for item in intents}
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(value,0)) "
                    "FROM unnest(%s::text[]) AS value ORDER BY value",
                    ([sub2api._table() + str(key) + backend for key in sorted(by_credential)],))
        cur.execute(f"SELECT * FROM {sub2api._table()} WHERE backend=%s AND "
                    "(credential_id=ANY(%s) OR filename=ANY(%s)) ORDER BY id FOR UPDATE",
                    (backend, list(by_credential), [item["filename"] for item in intents]))
        existing = list(cur.fetchall())
        patches, fresh = [], []
        now = datetime.now(timezone.utc)
        for item in intents:
            candidates = [row for row in existing if row["credential_id"] == item["credential_id"]
                          or row["filename"] == item["filename"]]
            for target in item["remote_account_ids"]:
                prior = next((row for row in candidates if row["target_key"] == target
                              or row["remote_account_id"] == target), None)
                if prior is None:
                    fresh.append({**item, "target": target})
                    continue
                row = dict(prior)
                row.update(filename=item["filename"], credential_id=item["credential_id"])
                if row["generation"] != item["generation"]:
                    row.update(generation=item["generation"], account_id=item["account_id"], email=item["email"],
                               status="pending", stage="pending", error_code=None, error=None,
                               trigger="sub2api_monitor", dispatch_requested=True, attempt_count=0,
                               task_id=None, run_id=None, next_attempt_at=now)
                elif item["account_id"] and not row["account_id"]:
                    row.update(account_id=item["account_id"], email=item["email"], stage="pending",
                               error_code=None, error=None, next_attempt_at=now)
                if row["status"] in {"pending", "blocked_backend"}:
                    row["dispatch_requested"] = True
                patches.append(row)
        _update_jobs(conn, patches)
        if fresh:
            cur.execute(f"INSERT INTO {sub2api._table()} "
                        "(filename,backend,target_key,remote_account_id,account_id,credential_id,email,generation,trigger) "
                        "SELECT s.filename,%s,s.target,s.target,s.account_id,s.credential_id,s.email,s.generation,'sub2api_monitor' "
                        "FROM jsonb_to_recordset(%s::jsonb) AS s(filename text,target bigint,account_id bigint,"
                        "credential_id bigint,email text,generation text)",
                        (backend, json.dumps(fresh, ensure_ascii=False)))


def active_runs(conn, account_ids):
    if not account_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(f"SELECT id,task_id,account_id,status FROM {common._table('operation_runs')} "
                    "WHERE account_id=ANY(%s) AND resource_family='openai_interactive' AND status=ANY(%s) ORDER BY id",
                    (list(account_ids), list(_INTERACTIVE_ACTIVE)))
        return {row["account_id"]: dict(row) for row in cur.fetchall()}


def locked_accounts(conn, account_ids):
    if not account_ids:
        return {}, set()
    with conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {pg.qualified(records.ACCOUNTS.name)} WHERE id=ANY(%s)",
                    (sorted(set(account_ids)),))
        existing = {row["id"] for row in cur.fetchall()}
        # 旧 Worker 收尾按 Run→账号→sync Job 取锁；持 Job 的生产者不得反向等待账号锁。
        cur.execute(f"SELECT * FROM {pg.qualified(records.ACCOUNTS.name)} WHERE id=ANY(%s) "
                    "ORDER BY id FOR UPDATE SKIP LOCKED", (sorted(set(account_ids)),))
        locked = {row["id"]: records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()}
        return locked, existing - set(locked)


def enqueue_due_many(backend, *, include_retries, conn=None, held_accounts=()):
    """补传生产者的本地准入集合化，远端返回仍由原 sub2api_sync handler 保存。"""
    if conn is None:
        initialize()
        with pg.connect(row_factory=dict_row) as current:
            return enqueue_due_many(backend, include_retries=include_retries, conn=current)
    with conn.cursor() as cur:
        cur.execute(f"UPDATE {sub2api._table()} SET status='blocked_backend',stage='configuration',"
                    "error_code='sub2api_backend_changed',error='Sub2API 后端已变化，旧目标保留等待原后端',updated_at=now() "
                    "WHERE backend<>%s AND status='pending'", (backend,))
        cur.execute(f"UPDATE {sub2api._table()} j SET status='cancelled',stage='cancelled',dispatch_requested=FALSE,"
                    "error_code='sub2api_sync_cancelled',error='用户已停止补传，可手动再次排队',updated_at=now() "
                    f"FROM {common._table('operation_runs')} r WHERE r.id=j.run_id AND j.status=ANY(%s) "
                    "AND r.status IN ('cancelled','stopped','terminated')",
                    (list((*sub2api.ACTIVE, "pending", "blocked_backend")),))
        cur.execute(f"UPDATE {sub2api._table()} j SET status='pending',stage='recovered',task_id=NULL,run_id=NULL,"
                    "dispatch_requested=TRUE,next_attempt_at=now(),updated_at=now() WHERE j.status=ANY(%s) AND NOT EXISTS "
                    f"(SELECT 1 FROM {common._table('operation_runs')} r WHERE r.id=j.run_id AND r.status=ANY(%s))",
                    (list(sub2api.ACTIVE), list(sub2api.ACTIVE)))
        cur.execute(f"SELECT * FROM {sub2api._table()} WHERE backend=%s AND status IN ('pending','blocked_backend') "
                    "AND (dispatch_requested OR %s) AND next_attempt_at<=now() "
                    "ORDER BY next_attempt_at,id FOR UPDATE SKIP LOCKED LIMIT 100", (backend, bool(include_retries)))
        rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            return {"queued": 0, "pending": 0}
        owners = [row["account_id"] for row in rows if row["account_id"]]
        accounts, unavailable = locked_accounts(conn, owners)
        active = active_runs(conn, owners)
        taken = set(active) | set(held_accounts)
        cur.execute(f"SELECT * FROM {pg.qualified(records.CODEX_CREDENTIALS.name)} "
                    "WHERE id=ANY(%s) OR filename=ANY(%s)",
                    ([row["credential_id"] for row in rows if row["credential_id"]], [row["filename"] for row in rows]))
        credentials = [records.merge_row(records.CODEX_CREDENTIALS, row) for row in cur.fetchall()]
        by_id = {row["id"]: row for row in credentials}
        by_name = {row["filename"]: row for row in credentials}
        specs, accepted, patches = [], [], []
        for row in rows:
            credential = by_id.get(row["credential_id"]) if row["credential_id"] else by_name.get(row["filename"])
            blocked, code, message = None, None, None
            if not row["account_id"]:
                code, message = "sub2api_local_account_missing", "本地账号暂不存在，等待账号恢复后继续补传"
                row["stage"] = "waiting_account"
            elif row["account_id"] in unavailable:
                code, message = "sub2api_account_busy", "账号正在收口，稍后补传"
            elif not credential or not isinstance(credential.get("content"), dict):
                blocked, code, message = "blocked_missing_credential", "sub2api_credential_missing", "本地凭证已不存在"
            elif credential.get("archived"):
                blocked, code, message = "blocked_archived", "sub2api_target_archived", "凭证已归档，已停止补传"
            elif str(credential["content"].get("email") or "").casefold() != str(row["email"]).casefold():
                blocked, code, message = "blocked_credential_identity", "sub2api_credential_identity_mismatch", "本地凭证身份已变化"
            elif common._account_is_deactivated(accounts.get(row["account_id"])):
                code, message = "account_deactivated", "账号已废号，禁止创建任务"
            elif row["account_id"] in taken:
                code, message = "sub2api_account_busy", "账号已有操作，稍后补传"
            if code:
                row.update(error_code=code, error=message)
                if blocked:
                    row.update(status=blocked, stage="blocked", dispatch_requested=False)
                elif row["account_id"]:
                    row["stage"] = "waiting_lease"
                patches.append(row)
                continue
            taken.add(row["account_id"])
            generation = sub2api.credential_generation(credential["content"])
            key = f"sub2api:{row['id']}:{generation}:{row['dispatch_no'] + 1}"
            specs.append({"task_type": "sub2api_sync", "account_id": row["account_id"], "email": row["email"],
                          "trigger": row["trigger"], "source_id": key, "idempotency_key": key,
                          "resource_family": "openai_interactive", "data": {"sync_job_id": row["id"], "generation": generation}})
            accepted.append((row, credential, generation))
        receipts = bulk_submission.create_specs(specs, conn=conn)
        for (row, credential, generation), result in zip(accepted, receipts, strict=True):
            row.update(status="queued", stage="queued", task_id=result["task_id"], run_id=result["run_id"],
                       filename=credential["filename"], credential_id=credential["id"],
                       attempt_count=0 if row["generation"] != generation else row["attempt_count"],
                       generation=generation, dispatch_requested=False, dispatch_no=row["dispatch_no"] + 1)
            patches.append(row)
        _update_jobs(conn, patches)
        return {"queued": len(receipts), "pending": len(rows) - len(receipts)}
