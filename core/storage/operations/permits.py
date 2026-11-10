# -*- coding: utf-8 -*-
"""同一 schema 内业务执行许可的原子准入与所有者恢复。"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import uuid
from contextlib import contextmanager, nullcontext
from collections.abc import Callable, Mapping
from typing import Any

from psycopg.rows import dict_row

from core.storage import postgres

_READY: set[str] = set()
_READY_LOCK = threading.RLock()
_OWNER_CACHE: dict[int, dict[str, Any]] = {}
_HOST_ID = f"{socket.gethostname()}:{uuid.getnode():012x}"
_LOCAL_EXITS: set[tuple[str, str]] = set()


def mark_execution_exited(permit_id: str, execution_id: str) -> None:
    _LOCAL_EXITS.add((str(permit_id), str(execution_id)))


def clear_execution_exit(permit_id: str, execution_id: str) -> None:
    _LOCAL_EXITS.discard((str(permit_id), str(execution_id)))


def admission_lock(conn) -> None:
    """统一锁序的第一把锁；调用方不得先持业务行锁或配置写锁。"""
    if conn.autocommit:
        raise RuntimeError("并发准入必须使用数据库事务")
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"operation-execution-admission:{postgres.schema_name()}",))


def ensure_tables() -> None:
    key = f"{postgres.database_url()}::{postgres.schema_name()}"
    with _READY_LOCK:
        # 测试会截断、重建同名 schema；用实际关系核验，不能只依赖进程标志。
        postgres.ensure_schema()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (postgres.qualified("operation_execution_permits"),))
            exists = cur.fetchone()[0] is not None
            if key in _READY and exists:
                return
            admission_lock(conn)
            cur.execute(f"""CREATE TABLE IF NOT EXISTS {postgres.qualified('operation_execution_permits')} (
                permit_id TEXT PRIMARY KEY, execution_key TEXT NOT NULL,
                execution_id TEXT NOT NULL, run_id BIGINT, task_type TEXT NOT NULL,
                owner JSONB NOT NULL, state TEXT NOT NULL DEFAULT 'reserved',
                policy_revision BIGINT NOT NULL DEFAULT 0, metadata JSONB NOT NULL DEFAULT '{{}}',
                acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(), heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                released_at TIMESTAMPTZ, release_reason TEXT, verification_state TEXT NOT NULL DEFAULT 'alive'
            )""")
            cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_permits_active_key ON {postgres.qualified('operation_execution_permits')} (execution_key) WHERE released_at IS NULL")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_execution_permits_active_run ON {postgres.qualified('operation_execution_permits')} (run_id) WHERE released_at IS NULL")
            cur.execute(f"""CREATE TABLE IF NOT EXISTS {postgres.qualified('operation_execution_permit_scopes')} (
                permit_id TEXT NOT NULL REFERENCES {postgres.qualified('operation_execution_permits')}(permit_id),
                scope_kind TEXT NOT NULL, scope_key TEXT NOT NULL, units INTEGER NOT NULL DEFAULT 1 CHECK (units > 0),
                limit_snapshot INTEGER,
                PRIMARY KEY (permit_id, scope_kind, scope_key)
            )""")
            cur.execute(f"ALTER TABLE {postgres.qualified('operation_execution_permit_scopes')} ADD COLUMN IF NOT EXISTS limit_snapshot INTEGER")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_execution_permit_scopes_capacity ON {postgres.qualified('operation_execution_permit_scopes')} (scope_kind, scope_key, permit_id)")
            cur.execute(f"""CREATE TABLE IF NOT EXISTS {postgres.qualified('operation_execution_requests')} (
                execution_key TEXT PRIMARY KEY, task_type TEXT NOT NULL, batch_key TEXT NOT NULL DEFAULT '',
                dispatch_lane TEXT NOT NULL DEFAULT 'new',
                observed_only BOOLEAN NOT NULL DEFAULT FALSE,
                scopes JSONB NOT NULL DEFAULT '[]', blocked_by JSONB NOT NULL DEFAULT '[]',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(), seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
            cur.execute(f"ALTER TABLE {postgres.qualified('operation_execution_requests')} ADD COLUMN IF NOT EXISTS dispatch_lane TEXT NOT NULL DEFAULT 'new'")
            cur.execute(f"ALTER TABLE {postgres.qualified('operation_execution_requests')} ADD COLUMN IF NOT EXISTS observed_only BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute(f"""CREATE TABLE IF NOT EXISTS {postgres.qualified('operation_execution_dispatch_cursor')} (
                id SMALLINT PRIMARY KEY CHECK (id=1), task_type TEXT NOT NULL DEFAULT '',
                batches JSONB NOT NULL DEFAULT '{{}}', lanes JSONB NOT NULL DEFAULT '{{}}'
            )""")
            cur.execute(f"INSERT INTO {postgres.qualified('operation_execution_dispatch_cursor')} (id) VALUES (1) ON CONFLICT DO NOTHING")
        _READY.add(key)


def _process_start(pid: int) -> str | None:
    try:
        result = subprocess.run(["ps", "-p", str(int(pid)), "-o", "lstart="],
                                capture_output=True, text=True, timeout=2, check=False)
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def current_owner() -> dict[str, Any]:
    pid = os.getpid()
    if pid not in _OWNER_CACHE:
        _OWNER_CACHE[pid] = {"host_id": _HOST_ID, "pid": pid,
                             "process_start": _process_start(pid), "instance_id": uuid.uuid4().hex}
    return dict(_OWNER_CACHE[pid])


def owner_liveness(owner: Mapping[str, Any]) -> str:
    """仅确认同主机进程身份；心跳超时与无权访问均不能证明退出。"""
    if owner.get("host_id") != _HOST_ID:
        return "unverified"
    try:
        pid = int(owner.get("pid") or 0)
        if pid <= 0:
            return "unverified"
        os.kill(pid, 0)
    except ProcessLookupError:
        return "exited"
    except (PermissionError, OSError, ValueError):
        return "unverified"
    start = _process_start(pid)
    recorded = owner.get("process_start")
    if start and recorded and start != recorded:
        return "exited"
    if not start or not recorded:
        return "unverified"
    if pid == os.getpid() and owner.get("thread_id"):
        if not any(thread.ident == owner["thread_id"] and thread.is_alive() for thread in threading.enumerate()):
            return "exited"
    return "alive"


def occupied(cur) -> dict[tuple[str, str], int]:
    cur.execute(f"""SELECT s.scope_kind, s.scope_key, SUM(s.units) AS occupied
        FROM {postgres.qualified('operation_execution_permit_scopes')} s
        JOIN {postgres.qualified('operation_execution_permits')} p ON p.permit_id=s.permit_id
        WHERE p.released_at IS NULL GROUP BY s.scope_kind, s.scope_key""")
    return {(row["scope_kind"], row["scope_key"]): int(row["occupied"]) for row in cur.fetchall()}


def dispatch_usage(conn) -> tuple[dict[tuple[str, str], int], set[str]]:
    """只读派发提示；同一快照读取占用和身份，最终容量仍由准入事务裁决。"""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""SELECT p.execution_key, s.scope_kind, s.scope_key, s.units
            FROM {postgres.qualified('operation_execution_permits')} p
            JOIN {postgres.qualified('operation_execution_permit_scopes')} s USING (permit_id)
            WHERE p.released_at IS NULL""")
        counts: dict[tuple[str, str], int] = {}
        active_keys: set[str] = set()
        for row in cur.fetchall():
            key = (row["scope_kind"], row["scope_key"])
            counts[key] = counts.get(key, 0) + int(row["units"])
            active_keys.add(row["execution_key"])
    return counts, active_keys


def _capacity_reasons(scopes, counts) -> list[str]:
    codes = {"global": "global_capacity", "type": "type_capacity", "batch": "batch_capacity",
             "provider": "provider_capacity", "continuation": "provider_capacity", "account": "account_busy"}
    return list(dict.fromkeys(codes.get(scope["kind"], "resource_capacity") for scope in scopes
                             if counts.get((scope["kind"], scope["key"]), 0) + int(scope.get("units", 1)) > int(scope["limit"])))


class _ClaimRejected(Exception):
    pass


class ClaimUnavailable(Exception):
    def __init__(self, code: str):
        self.code = str(code)
        super().__init__(self.code)


def _record_request(cur, *, execution_key, task_type, batch_key, scopes, metadata, reasons=(), observed_only=False):
    cur.execute(f"""INSERT INTO {postgres.qualified('operation_execution_requests')}
        (execution_key,task_type,batch_key,scopes,dispatch_lane,blocked_by,observed_only)
        VALUES (%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s)
        ON CONFLICT (execution_key) DO UPDATE SET task_type=EXCLUDED.task_type,
            batch_key=EXCLUDED.batch_key,scopes=EXCLUDED.scopes,
            dispatch_lane=EXCLUDED.dispatch_lane,blocked_by=EXCLUDED.blocked_by,
            observed_only=EXCLUDED.observed_only,seen_at=now()
        WHERE {postgres.qualified('operation_execution_requests')}.observed_only IS TRUE
           OR EXCLUDED.observed_only IS FALSE""",
                (execution_key,task_type,batch_key,json.dumps(scopes),str(metadata.get("dispatch_lane") or "new"),
                 json.dumps(list(dict.fromkeys(reasons))),bool(observed_only)))


def observe_waiting_many(requests: list[dict], *, policy: Callable[[Any], list[tuple[list[dict], int, list[str]]]]) -> list[dict]:
    """一次只读容量快照观察有界候选；仅原因变化或15秒续期才集合写入。"""
    if not requests:
        return []
    ensure_tables()
    keys = [str(item["execution_key"]) for item in requests]
    if len(keys) != len(set(keys)):
        raise ValueError("同一次等待观察的执行标识不能重复")
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        admission_lock(conn)
        policies = policy(conn)
        if len(policies) != len(requests):
            raise ValueError("等待观察策略未覆盖全部执行")
        counts = occupied(cur)
        cur.execute(f"SELECT execution_key FROM {postgres.qualified('operation_execution_permits')} "
                    "WHERE execution_key=ANY(%s) AND released_at IS NULL", (keys,))
        active = {row["execution_key"] for row in cur.fetchall()}
        cur.execute(f"SELECT *,seen_at < now()-interval '15 seconds' AS renew "
                    f"FROM {postgres.qualified('operation_execution_requests')} WHERE execution_key=ANY(%s)", (keys,))
        existing = {row["execution_key"]: row for row in cur.fetchall()}
        changed, cleared, results = [], [], []
        for request, (scopes, _revision, blocks) in zip(requests, policies):
            key = str(request["execution_key"])
            previous = existing.get(key)
            if key in active:
                if previous and previous["observed_only"]:
                    cleared.append(key)
                results.append({"blocked_by": ["execution_active"]})
                continue
            reasons = list(dict.fromkeys([*blocks, *_capacity_reasons(scopes, counts)])) or ["executor_capacity"]
            row = {"execution_key": key, "task_type": request["task_type"],
                   "batch_key": str(request.get("batch_key") or ""), "scopes": scopes,
                   "dispatch_lane": str((request.get("metadata") or {}).get("dispatch_lane") or "new"),
                   "blocked_by": reasons}
            # 实际准入请求的公平身份、账号阻塞及seen_at均不能被纯观察改写。
            if not previous or (previous["observed_only"] and
                    (previous["renew"] or any(previous[field] != value for field, value in row.items()))):
                changed.append(row)
            results.append({"blocked_by": reasons})
        if cleared:
            cur.execute(f"DELETE FROM {postgres.qualified('operation_execution_requests')} "
                        "WHERE execution_key=ANY(%s) AND observed_only IS TRUE", (cleared,))
        if changed:
            target = postgres.qualified('operation_execution_requests')
            cur.execute(f"""INSERT INTO {target}
                (execution_key,task_type,batch_key,scopes,dispatch_lane,blocked_by,observed_only)
                SELECT execution_key,task_type,batch_key,scopes,dispatch_lane,blocked_by,TRUE
                FROM jsonb_to_recordset(%s::jsonb) AS item(execution_key text,task_type text,
                    batch_key text,scopes jsonb,dispatch_lane text,blocked_by jsonb)
                ON CONFLICT(execution_key) DO UPDATE SET task_type=EXCLUDED.task_type,
                    batch_key=EXCLUDED.batch_key,scopes=EXCLUDED.scopes,dispatch_lane=EXCLUDED.dispatch_lane,
                    blocked_by=EXCLUDED.blocked_by,seen_at=now()
                WHERE {target}.observed_only IS TRUE""", (json.dumps(changed),))
        return results


def observe_waiting(*, execution_key: str, task_type: str, batch_key: str, metadata: Mapping,
                    policy: Callable[[Any], tuple[list[dict], int, list[str]]]) -> dict:
    """单项兼容入口与集合观察使用同一事实和去抖规则。"""
    return observe_waiting_many([dict(execution_key=execution_key,task_type=task_type,
        batch_key=batch_key,metadata=dict(metadata))], policy=lambda conn: [policy(conn)])[0]


def try_admit(*, execution_key: str, task_type: str, execution_id: str, run_id: int | None,
              batch_key: str, owner: Mapping[str, Any], metadata: Mapping[str, Any],
              policy: Callable[[Any], tuple[list[dict], int, list[str]]],
              claim: Callable[[Any, str], Mapping | None]) -> dict[str, Any]:
    """多维检查、持久公平游标、业务认领和许可在同一连接提交。"""
    ensure_tables()
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor(row_factory=dict_row) as cur:
        admission_lock(conn)
        cur.execute(f"INSERT INTO {postgres.qualified('operation_execution_dispatch_cursor')} (id) VALUES (1) ON CONFLICT DO NOTHING")
        scopes, revision, policy_blocks = policy(conn)
        _record_request(cur,execution_key=execution_key,task_type=task_type,batch_key=batch_key,
                        scopes=scopes,metadata=metadata)
        counts = occupied(cur)
        reasons = list(policy_blocks) + _capacity_reasons(scopes, counts)
        cur.execute(f"SELECT 1 FROM {postgres.qualified('operation_execution_permits')} WHERE execution_key=%s AND released_at IS NULL", (execution_key,))
        if cur.fetchone():
            reasons.append("execution_active")
        cur.execute(f"SELECT task_type, batches, lanes FROM {postgres.qualified('operation_execution_dispatch_cursor')} WHERE id=1")
        cursor = cur.fetchone()
        if not reasons:
            # 失去调度器的候选仅退出公平竞争，绝不据此回收活动许可。
            cur.execute(f"""SELECT execution_key,task_type,batch_key,scopes,dispatch_lane,blocked_by
                FROM {postgres.qualified('operation_execution_requests')} request
                WHERE seen_at > now() - interval '5 seconds' AND observed_only IS FALSE AND NOT EXISTS (
                    SELECT 1 FROM {postgres.qualified('operation_execution_permits')} active
                    WHERE active.execution_key=request.execution_key AND active.released_at IS NULL)
                ORDER BY created_at,execution_key""")
            ready = [row for row in cur.fetchall() if not _capacity_reasons(row["scopes"], counts)
                     and (row["execution_key"] == execution_key or not set(row["blocked_by"]) & {"account_busy", "not_claimable"})]
            types = sorted({row["task_type"] for row in ready})
            last_type = str(cursor["task_type"] or "")
            next_type = next((item for item in types if item > last_type), types[0] if types else task_type)
            if task_type != next_type:
                reasons.append("fairness_turn")
            else:
                batches = sorted({row["batch_key"] for row in ready if row["task_type"] == task_type})
                last_batch = str((cursor["batches"] or {}).get(task_type, ""))
                next_batch = next((item for item in batches if item > last_batch), batches[0] if batches else batch_key)
                if batch_key != next_batch:
                    reasons.append("fairness_turn")
                elif task_type == "extract_link":
                    lanes = sorted({row["dispatch_lane"] for row in ready if row["task_type"] == task_type and row["batch_key"] == batch_key})
                    last_lane = str((cursor["lanes"] or {}).get(f"{task_type}:{batch_key}", ""))
                    next_lane = next((item for item in lanes if item > last_lane), lanes[0] if lanes else "new")
                    if str(metadata.get("dispatch_lane") or "new") != next_lane:
                        reasons.append("fairness_turn")
        if reasons:
            cur.execute(f"UPDATE {postgres.qualified('operation_execution_requests')} SET blocked_by=%s::jsonb WHERE execution_key=%s", (json.dumps(list(dict.fromkeys(reasons))), execution_key))
            return {"blocked_by": list(dict.fromkeys(reasons))}
        try:
            with conn.transaction():
                claimed = claim(conn, execution_id)
                if claimed is None:
                    raise _ClaimRejected()
        except ClaimUnavailable as exc:
            cur.execute(f"UPDATE {postgres.qualified('operation_execution_requests')} SET blocked_by=%s::jsonb WHERE execution_key=%s", (json.dumps([exc.code]), execution_key))
            return {"blocked_by": [exc.code]}
        except _ClaimRejected:
            cur.execute(f"DELETE FROM {postgres.qualified('operation_execution_requests')} WHERE execution_key=%s", (execution_key,))
            return {"blocked_by": ["not_claimable"]}
        permit_id = uuid.uuid4().hex
        cur.execute(f"""INSERT INTO {postgres.qualified('operation_execution_permits')}
            (permit_id,execution_key,execution_id,run_id,task_type,owner,policy_revision,metadata)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb)""",
                    (permit_id, execution_key, execution_id, run_id, task_type, json.dumps(dict(owner)), revision, json.dumps(dict(metadata))))
        for scope in scopes:
            cur.execute(f"INSERT INTO {postgres.qualified('operation_execution_permit_scopes')} (permit_id,scope_kind,scope_key,units,limit_snapshot) VALUES (%s,%s,%s,%s,%s)", (permit_id, scope["kind"], scope["key"], int(scope.get("units", 1)), int(scope["limit"])))
        cur.execute(f"""UPDATE {postgres.qualified('operation_execution_dispatch_cursor')}
            SET task_type=%s,batches=batches || %s::jsonb,lanes=lanes || %s::jsonb WHERE id=1""",
                    (task_type, json.dumps({task_type: batch_key}),
                     json.dumps({f"{task_type}:{batch_key}": str(metadata.get("dispatch_lane") or "new")})))
        cur.execute(f"DELETE FROM {postgres.qualified('operation_execution_requests')} WHERE execution_key=%s", (execution_key,))
        return {"permit_id": permit_id, "execution_id": execution_id, "policy_revision": revision, "claimed_run": dict(claimed), "blocked_by": []}


def _permit_table(schema: str | None = None) -> str:
    return f"{postgres.quote_identifier(schema or postgres.schema_name())}.{postgres.quote_identifier('operation_execution_permits')}"


def heartbeat(permit_id: str, execution_id: str, *, state: str | None = None, thread_id: int | None = None,
              schema: str | None = None, database_url: str | None = None) -> bool:
    with postgres.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(f"""UPDATE {_permit_table(schema)}
            SET heartbeat_at=now(), state=COALESCE(%s,state), verification_state='alive',
                owner=owner || %s::jsonb
            WHERE permit_id=%s AND execution_id=%s AND released_at IS NULL""",
                    (state, json.dumps({"thread_id": thread_id} if thread_id is not None else {}), permit_id, execution_id))
        return cur.rowcount > 0


def release(permit_id: str, execution_id: str, *, reason: str = "worker_exit",
            schema: str | None = None, database_url: str | None = None) -> bool:
    with postgres.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"operation-execution-admission:{schema or postgres.schema_name()}",))
        cur.execute("SELECT to_regclass(%s)", (_permit_table(schema),))
        if cur.fetchone()[0] is None:
            return False
        cur.execute(f"""UPDATE {_permit_table(schema)}
            SET released_at=now(), release_reason=%s, state='released'
            WHERE permit_id=%s AND execution_id=%s AND released_at IS NULL""", (reason, permit_id, execution_id))
        return cur.rowcount > 0


@contextmanager
def admission_transaction():
    ensure_tables()
    with postgres.connect(row_factory=dict_row) as conn:
        admission_lock(conn)
        yield conn


def active_execution_keys(*, prefix: str | None = None, conn=None) -> set[str]:
    if conn is None:
        ensure_tables()
    with (postgres.connect() if conn is None else nullcontext(conn)) as current, current.cursor() as cur:
        cur.execute(f"SELECT execution_key FROM {postgres.qualified('operation_execution_permits')} WHERE released_at IS NULL")
        keys = {row["execution_key"] if isinstance(row, Mapping) else row[0] for row in cur.fetchall()}
        return {key for key in keys if prefix is None or key.startswith(prefix)}


def active_execution_ids(*, conn=None) -> set[str]:
    if conn is None:
        ensure_tables()
    with (postgres.connect() if conn is None else nullcontext(conn)) as current, current.cursor() as cur:
        cur.execute(f"SELECT execution_id FROM {postgres.qualified('operation_execution_permits')} WHERE released_at IS NULL")
        return {row["execution_id"] if isinstance(row, Mapping) else row[0] for row in cur.fetchall()}


def validate(permit_id: str, execution_id: str, *, schema: str | None = None, database_url: str | None = None) -> bool:
    with postgres.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {_permit_table(schema)} WHERE permit_id=%s AND execution_id=%s AND released_at IS NULL", (permit_id, execution_id))
        return cur.fetchone() is not None


def recover_execution_permits() -> dict[str, int]:
    ensure_tables()
    with postgres.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT permit_id, execution_id, owner FROM {postgres.qualified('operation_execution_permits')} WHERE released_at IS NULL")
        rows = list(cur.fetchall())
    result = {"released": 0, "alive": 0, "unverified": 0}
    for row in rows:
        state = "exited" if (row["permit_id"], row["execution_id"]) in _LOCAL_EXITS else owner_liveness(row["owner"])
        if state == "exited":
            result["released"] += int(release(row["permit_id"], row["execution_id"], reason="owner_exit_confirmed"))
        else:
            result[state] += 1
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {postgres.qualified('operation_execution_permits')} SET verification_state=%s WHERE permit_id=%s AND execution_id=%s AND released_at IS NULL", (state, row["permit_id"], row["execution_id"]))
    return result


def status_rows() -> tuple[list[dict], list[dict], list[dict]]:
    ensure_tables()
    with postgres.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT * FROM {postgres.qualified('operation_execution_permits')} WHERE released_at IS NULL")
        permits = list(cur.fetchall())
        cur.execute(f"SELECT s.* FROM {postgres.qualified('operation_execution_permit_scopes')} s JOIN {postgres.qualified('operation_execution_permits')} p ON p.permit_id=s.permit_id WHERE p.released_at IS NULL")
        scopes = list(cur.fetchall())
        cur.execute("SELECT to_regclass(%s) AS relation", (postgres.qualified("operation_runs"),))
        queue_filter = ""
        if cur.fetchone()["relation"] is not None:
            queue_filter = f"""AND (execution_key NOT LIKE 'operation_run:%%' OR EXISTS (
                SELECT 1 FROM {postgres.qualified('operation_runs')} run
                WHERE execution_key='operation_run:' || run.id::text
                  AND run.status='queued' AND run.cancel_requested_at IS NULL))"""
        cur.execute(f"SELECT * FROM {postgres.qualified('operation_execution_requests')} WHERE seen_at > now() - interval '30 seconds' {queue_filter}")
        requests = list(cur.fetchall())
        return permits, scopes, requests


def wait_details(execution_keys: list[str], *, conn) -> dict[str, list[dict]]:
    if not execution_keys:
        return {}
    result = {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT execution_key,scopes,blocked_by,observed_only FROM {postgres.qualified('operation_execution_requests')} WHERE execution_key=ANY(%s)", (execution_keys,))
        rows = list(cur.fetchall())
        counts = occupied(cur)
    codes = {"global": "global_capacity", "type": "type_capacity", "batch": "batch_capacity",
             "provider": "provider_capacity", "continuation": "provider_capacity", "account": "account_busy",
             "resource": "resource_capacity", "registration_attempt": "resource_capacity"}
    for row in rows:
        details = []
        for code in row["blocked_by"]:
            matching = [scope for scope in row["scopes"] if codes.get(scope["kind"]) == code
                        and counts.get((scope["kind"], scope["key"]), 0) >= int(scope["limit"])]
            details.extend({"code": code, "scope_kind": scope["kind"], "scope_key": scope["key"],
                            "limit": scope["limit"], "occupied": counts.get((scope["kind"], scope["key"]), 0)} for scope in matching)
            if not matching and (code not in set(codes.values()) or (code == "account_busy" and not row["observed_only"])):
                details.append({"code": code})
        result[row["execution_key"]] = details
    return result


def dispatch_cursor() -> dict:
    ensure_tables()
    with postgres.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT task_type,batches,lanes FROM {postgres.qualified('operation_execution_dispatch_cursor')} WHERE id=1")
        return dict(cur.fetchone() or {"task_type": "", "batches": {}, "lanes": {}})
