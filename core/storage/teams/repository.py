# -*- coding: utf-8 -*-
"""Team 事务仓储；远端请求由执行层完成，持久 outbox 保证受理可恢复。"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row

from core.storage import postgres, records
from core.storage.teams.schema import init, ensure_schema, reset_ready
from core.teams.errors import TeamError

UNSET = object()
ACTIVE_STATUSES = frozenset({"queued", "running", "waiting", "cancelling", "settling", "stopping"})


def table(name):
    return postgres.qualified(name)


def _connection(conn=None):
    return nullcontext(conn) if conn is not None else postgres.connect(row_factory=dict_row)


@contextmanager
def transaction():
    """业务事务的唯一持久提交边界；调用方可以同时写入原生 Task/Run。"""
    init()
    with _connection() as conn:
        yield conn


def _write_connection(conn=None):
    if conn is not None:
        return nullcontext(conn)
    return transaction()


def _one(conn, sql, values=()):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, values)
        row = cur.fetchone()
        return dict(row) if row is not None else None


def _all(conn, sql, values=()):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, values)
        return [dict(row) for row in cur.fetchall()]


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"无法序列化 {type(value).__name__}")


def _now():
    return datetime.now(timezone.utc)


def _error(code, message, *, status=409, **details):
    raise TeamError(code, message, status=status, details=details)


def _lock_account(conn, account_id):
    # 同一个账号的跨工作区业务占用先串行，再取得 Team 行锁，避免跨 Team 写入竞态。
    records.advisory_xact_lock(conn, f"team-account:{postgres.schema_name()}:{int(account_id)}")


def _require_team(conn, team_id, *, lock=False):
    row = _one(conn, f"SELECT * FROM {table('team_workspaces')} WHERE id=%s" +
               (" FOR UPDATE" if lock else ""), (int(team_id),))
    if row is None:
        _error("team_not_found", "Team 不存在", status=404)
    return row


def _claim_ownership(conn, account_id, team_id, *, kind, invitation_id=None):
    _lock_account(conn, account_id)
    if _unlinked_email_conflict(conn, account_id, team_id=team_id):
        return False
    conflict = _one(conn, f"""
        SELECT team_id FROM {table('team_account_ownership')} WHERE account_id=%s AND team_id<>%s
        UNION ALL SELECT id AS team_id FROM {table('team_workspaces')}
          WHERE manager_account_id=%s AND id<>%s
        UNION ALL SELECT team_id FROM {table('team_members')}
          WHERE account_id=%s AND team_id<>%s AND membership_state='joined'
        UNION ALL SELECT team_id FROM {table('team_invitations')}
          WHERE account_id=%s AND team_id<>%s
            AND (active OR invitation_state='pending' OR membership_state='joined' OR seat_reserved OR
              execution_status IN ('queued','running','waiting','cancelling','settling','stopping'))
        LIMIT 1
    """, (int(account_id), int(team_id), int(account_id), int(team_id), int(account_id), int(team_id),
          int(account_id), int(team_id)))
    if conflict:
        return False
    claimed = _one(conn, f"""
        INSERT INTO {table('team_account_ownership')} (account_id,team_id,kind,invitation_id)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT(account_id) DO UPDATE SET kind=EXCLUDED.kind,
          invitation_id=COALESCE(EXCLUDED.invitation_id,{table('team_account_ownership')}.invitation_id),
          absent_complete_count=0,updated_at=now()
        WHERE {table('team_account_ownership')}.team_id=EXCLUDED.team_id RETURNING *
    """, (int(account_id), int(team_id), kind, invitation_id))
    return claimed is not None


def request_receipt(key, *, path, fingerprint, conn=None):
    """先读原回执再验证业务环境；请求键在所有 Team 写接口间唯一。"""
    with _write_connection(conn) as db:
        records.advisory_xact_lock(db, f"team-request:{postgres.schema_name()}:{key}")
        row = _one(db, f"SELECT * FROM {table('team_request_receipts')} WHERE idempotency_key=%s", (str(key),))
        if row and (row["path"] != path or row["fingerprint"] != fingerprint):
            _error("idempotency_conflict", "幂等键已用于其他请求")
        return row


def save_request_receipt(key, *, path, fingerprint, response, status_code, conn=None):
    with _write_connection(conn) as db:
        old = request_receipt(key, path=path, fingerprint=fingerprint, conn=db)
        if old is not None:
            return old
        return _one(db, f"""
            INSERT INTO {table('team_request_receipts')}
            (idempotency_key,path,fingerprint,response_json,status_code)
            VALUES (%s,%s,%s,%s::jsonb,%s) RETURNING *
        """, (str(key), path, fingerprint, _json(response), int(status_code)))


def enqueue_outbox(kind, aggregate_type, aggregate_id, payload, *, dedupe_key, conn=None):
    with _write_connection(conn) as db:
        return _one(db, f"""
            INSERT INTO {table('team_outbox')}(kind,aggregate_type,aggregate_id,payload,dedupe_key)
            VALUES (%s,%s,%s,%s::jsonb,%s)
            ON CONFLICT(dedupe_key) DO UPDATE SET dedupe_key=EXCLUDED.dedupe_key RETURNING *
        """, (kind, aggregate_type, int(aggregate_id), _json(payload), dedupe_key))


def claim_outbox(*, limit=20, lease_seconds=60, worker_id=None, kinds=None):
    with transaction() as conn:
        token = f"{worker_id or 'worker'}:{uuid.uuid4().hex}"
        return _all(conn, f"""
            WITH ready AS (
                SELECT id FROM {table('team_outbox')}
                WHERE ((status='pending' AND available_at<=now())
                   OR (status='processing' AND lease_until<=now()))
                  AND (%s::text[] IS NULL OR kind=ANY(%s::text[]))
                ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT %s
            )
            UPDATE {table('team_outbox')} o SET status='processing',lease_token=%s,
              lease_until=now()+(%s * interval '1 second'),attempts=attempts+1,updated_at=now()
            FROM ready WHERE o.id=ready.id RETURNING o.*
        """, (list(kinds) if kinds else None, list(kinds) if kinds else None,
              int(limit), token, int(lease_seconds)))


def complete_outbox(outbox_id, lease_token, *, result=None, conn=None):
    with _write_connection(conn) as db:
        return _one(db, f"""
            UPDATE {table('team_outbox')} SET status='completed',lease_token=NULL,lease_until=NULL,updated_at=now()
            WHERE id=%s AND status='processing' AND lease_token=%s AND lease_until>now() RETURNING id
        """, (int(outbox_id), lease_token)) is not None


def release_outbox(outbox_id, lease_token, *, error=None, delay_seconds=5, conn=None):
    with _write_connection(conn) as db:
        return _one(db, f"""
            UPDATE {table('team_outbox')} SET status='pending',lease_token=NULL,lease_until=NULL,
              available_at=now()+(%s * interval '1 second'),last_error=%s,updated_at=now()
            WHERE id=%s AND status='processing' AND lease_token=%s AND lease_until>now() RETURNING id
        """, (float(delay_seconds), str(error)[:1200] if error else None, int(outbox_id), lease_token)) is not None


def _task_and_outbox(db, kind, aggregate_type, aggregate_id, payload, *, task_factory=None, dedupe_key=None):
    payload = {**payload, "request_key": payload.get("request_key") or f"{kind}:{aggregate_id}"}
    refs = dict(task_factory(db, kind, payload) or {}) if task_factory else {}
    payload.update({key: refs[key] for key in ("task_id", "run_id", "batch_id") if refs.get(key) is not None})
    outbox = enqueue_outbox(kind, aggregate_type, aggregate_id, payload,
                            dedupe_key=dedupe_key or payload["request_key"], conn=db)
    return refs, outbox


def create_probe(*, manager_account_id, target_workspace_id=None, task_id=None, run_id=None,
                 task_factory=None, conn=None):
    with _write_connection(conn) as db:
        account = _one(db, f"SELECT id FROM {table(records.ACCOUNTS.name)} WHERE id=%s", (int(manager_account_id),))
        if account is None:
            _error("account_not_found", "母账号不存在", status=404)
        row = _one(db, f"""
            INSERT INTO {table('team_binding_probes')}(manager_account_id,target_workspace_id,task_id,run_id)
            VALUES (%s,%s,%s,%s) RETURNING *
        """, (int(manager_account_id), target_workspace_id, task_id, run_id))
        if task_factory:
            refs, _ = _task_and_outbox(db, "team_probe", "probe", row["id"],
                                       {"probe_id": row["id"], "manager_account_id": int(manager_account_id),
                                        "target_workspace_id": target_workspace_id}, task_factory=task_factory)
            row = _one(db, f"UPDATE {table('team_binding_probes')} SET task_id=%s,run_id=%s WHERE id=%s RETURNING *",
                       (refs.get("task_id"), refs.get("run_id"), row["id"]))
        return row


def get_probe(probe_id, *, conn=None):
    with _connection(conn) as db:
        return _one(db, f"""
            SELECT p.*,a.email AS manager_email,a.archived AS manager_archived
            FROM {table('team_binding_probes')} p JOIN {table(records.ACCOUNTS.name)} a
            ON a.id=p.manager_account_id WHERE p.id=%s
        """, (int(probe_id),))


def update_probe(probe_id, *, status, stage=None, workspaces=None, task_id=None, run_id=None,
                 error_info=None, expected_revision=None, conn=None):
    with _write_connection(conn) as db:
        row = _one(db, f"SELECT * FROM {table('team_binding_probes')} WHERE id=%s FOR UPDATE", (int(probe_id),))
        if row is None:
            _error("probe_not_found", "探测不存在", status=404)
        if expected_revision is not None and row["revision"] != int(expected_revision):
            _error("probe_revision_conflict", "探测版本变化")
        completed = _now() if status in {"success", "failed", "cancelled", "interrupted"} else None
        workspaces = workspaces if workspaces is not None else row["workspaces"]
        candidates = [item for item in workspaces if item.get("workspace_type") == "team" and item.get("can_manage") is True]
        suggested = candidates[0]["workspace_id"] if status == "success" and len(candidates) == 1 else None
        return _one(db, f"""
            UPDATE {table('team_binding_probes')} SET status=%s,stage=COALESCE(%s,stage),
              workspaces=%s::jsonb,task_id=COALESCE(%s,task_id),run_id=COALESCE(%s,run_id),
              error_info=%s::jsonb,suggested_workspace_id=%s,completed_at=%s,expires_at=%s,
              revision=revision+1,updated_at=now() WHERE id=%s RETURNING *
        """, (status, stage, _json(workspaces), task_id, run_id, _json(error_info), suggested,
              completed, completed + timedelta(minutes=10) if status == "success" else None, int(probe_id)))


def _validate_probe(db, *, probe_id, probe_revision, manager_account_id, workspace_id):
    probe = _one(db, f"SELECT * FROM {table('team_binding_probes')} WHERE id=%s FOR SHARE", (int(probe_id),))
    if probe is None:
        _error("probe_not_found", "探测不存在", status=404)
    if probe["revision"] != int(probe_revision):
        _error("probe_revision_conflict", "探测版本变化")
    if probe["status"] != "success":
        _error("probe_not_ready", "等待探测完成")
    if not probe["expires_at"] or probe["expires_at"] <= _now():
        _error("probe_expired", "探测已过期")
    if probe["manager_account_id"] != int(manager_account_id):
        _error("probe_identity_mismatch", "探测身份不符")
    workspace = next((item for item in probe["workspaces"] if item.get("workspace_id") == workspace_id), None)
    if not workspace or workspace.get("workspace_type") != "team":
        _error("probe_identity_mismatch", "探测工作区不符")
    if workspace.get("can_manage") is not True:
        _error("manager_permission_unconfirmed", "管理权限待核验")
    return workspace, probe


def bind_team(*, manager_account_id, workspace_id, probe_id, probe_revision, display_name=None,
              planned_member_limit=None, task_factory=None, conn=None):
    with _write_connection(conn) as db:
        _lock_account(db, manager_account_id)
        records.advisory_xact_lock(db, f"team-workspace:{postgres.schema_name()}:{workspace_id}")
        workspace, probe = _validate_probe(db, probe_id=probe_id, probe_revision=probe_revision,
                                            manager_account_id=manager_account_id, workspace_id=workspace_id)
        existing = _one(db, f"SELECT id FROM {table('team_workspaces')} WHERE workspace_id=%s", (workspace_id,))
        if existing:
            _error("team_already_bound", "工作区已绑定", existing_team_id=str(existing["id"]))
        # 先核验账号已有关系，再创建工作区，避免暂时创建的新行影响归属查询。
        if not _claim_ownership_available(db, manager_account_id):
            _error("already_in_another_team", "母账号已属其他Team")
        row = _one(db, f"""
            INSERT INTO {table('team_workspaces')} (workspace_id,manager_account_id,name,display_name,
              role,purchased_seats,planned_member_limit,last_sync_status,permission_verified_at,permissions)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s::jsonb) RETURNING *
        """, (workspace_id, int(manager_account_id), workspace.get("name"), display_name,
              workspace.get("role", "unknown"), workspace.get("purchased_seats"), planned_member_limit,
              probe["completed_at"], _json(workspace.get("capabilities") or {})))
        if not _claim_ownership(db, manager_account_id, row["id"], kind="manager"):
            _error("already_in_another_team", "母账号已属其他Team")
        payload = {"team_id": row["id"], "workspace_id": workspace_id,
                   "manager_account_id": int(manager_account_id), "manager_revision": row["manager_revision"]}
        refs, outbox = _task_and_outbox(db, "team_sync", "team", row["id"], payload,
                                       task_factory=task_factory, dedupe_key=f"team-initial-sync:{row['id']}")
        return {"team": row, "outbox": outbox, "sync": refs}


def _claim_ownership_available(db, account_id):
    if _unlinked_email_conflict(db, account_id):
        return False
    return _one(db, f"""
        SELECT 1 FROM {table('team_account_ownership')} WHERE account_id=%s
        UNION ALL SELECT 1 FROM {table('team_workspaces')} WHERE manager_account_id=%s
        UNION ALL SELECT 1 FROM {table('team_members')} WHERE account_id=%s AND membership_state='joined'
        UNION ALL SELECT 1 FROM {table('team_invitations')} WHERE account_id=%s AND
          (active OR invitation_state='pending' OR membership_state='joined' OR seat_reserved OR
           execution_status IN ('queued','running','waiting','cancelling','settling','stopping'))
        LIMIT 1
    """, (int(account_id), int(account_id), int(account_id), int(account_id))) is None


def _unlinked_email_conflict(db, account_id, *, team_id=None):
    """账号晚于远端事实入库时，按唯一规范邮箱补足跨 Team 原子占用检查。"""
    return _one(db, f"""
        WITH target AS (
          SELECT lower(btrim(COALESCE(email,''))) AS email FROM {table(records.ACCOUNTS.name)} WHERE id=%s
        ), unique_target AS (
          SELECT t.email FROM target t WHERE (
            SELECT count(*) FROM {table(records.ACCOUNTS.name)} a WHERE lower(btrim(COALESCE(a.email,'')))=t.email
          )=1
        )
        SELECT 1 FROM {table('team_members')} m JOIN unique_target t ON lower(btrim(COALESCE(m.email,'')))=t.email
          WHERE m.account_id IS NULL AND m.membership_state='joined' AND (%s::bigint IS NULL OR m.team_id<>%s)
        UNION ALL
        SELECT 1 FROM {table('team_invitations')} i JOIN unique_target t ON lower(btrim(COALESCE(i.email_snapshot,'')))=t.email
          WHERE i.account_id IS NULL AND (%s::bigint IS NULL OR i.team_id<>%s)
            AND (i.active OR i.seat_reserved OR i.invitation_state='pending' OR i.membership_state='joined')
        LIMIT 1
    """, (int(account_id), team_id, team_id, team_id, team_id)) is not None


def patch_team(team_id, *, expected_revision, changes, probe_id=None, probe_revision=None, conn=None):
    with _write_connection(conn) as db:
        if changes.get("manager_account_id") is not None:
            _lock_account(db, changes["manager_account_id"])
        team = _require_team(db, team_id, lock=True)
        if team["revision"] != int(expected_revision):
            _error("revision_conflict", "Team 版本变化", revision=team["revision"])
        values = {key: changes[key] for key in ("display_name", "planned_member_limit") if key in changes}
        manager = changes.get("manager_account_id")
        if manager is not None and int(manager) != team["manager_account_id"]:
            workspace, probe = _validate_probe(db, probe_id=probe_id, probe_revision=probe_revision,
                                                manager_account_id=manager, workspace_id=team["workspace_id"])
            if not _claim_ownership(db, manager, team_id, kind="manager"):
                _error("already_in_another_team", "母账号已属其他Team")
            values.update(manager_account_id=int(manager), manager_revision=team["manager_revision"] + 1,
                          role=workspace.get("role", "unknown"), permissions=workspace.get("capabilities") or {},
                          permission_verified_at=probe["completed_at"])
        assignments, parameters = [], []
        for key, value in values.items():
            assignments.append(f"{key}=%s" + ("::jsonb" if key == "permissions" else ""))
            parameters.append(_json(value) if key == "permissions" else value)
        assignments.extend(["revision=revision+1", "updated_at=now()"])
        return _one(db, f"UPDATE {table('team_workspaces')} SET {','.join(assignments)} WHERE id=%s RETURNING *",
                    (*parameters, int(team_id)))


def update_team_runtime(team_id, *, changes, manager_revision=None, conn=None):
    allowed = {"last_sync_status", "permission_verified_at", "permissions", "role"}
    if set(changes) - allowed:
        raise ValueError("运行更新包含未授权字段")
    with _write_connection(conn) as db:
        team = _require_team(db, team_id, lock=True)
        if manager_revision is not None and team["manager_revision"] != int(manager_revision):
            return team
        assignments, values = [], []
        for key, value in changes.items():
            assignments.append(f"{key}=%s" + ("::jsonb" if key == "permissions" else ""))
            values.append(_json(value) if key == "permissions" else value)
        if not assignments:
            return team
        return _one(db, f"UPDATE {table('team_workspaces')} SET {','.join(assignments)},updated_at=now() WHERE id=%s RETURNING *",
                    (*values, int(team_id)))


def put_auth_context(team_id, account_id, *, workspace_id, identity_ref, encrypted_context, verified_at=None, conn=None):
    with _write_connection(conn) as db:
        team = _require_team(db, team_id)
        if workspace_id != team["workspace_id"]:
            _error("team_workspace_mismatch", "认证工作区不符")
        return _one(db, f"""
            INSERT INTO {table('team_auth_contexts')}
              (team_id,account_id,workspace_id,identity_ref,encrypted_context,verified_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT(account_id,team_id) DO UPDATE SET
              identity_ref=EXCLUDED.identity_ref,encrypted_context=EXCLUDED.encrypted_context,
              verified_at=EXCLUDED.verified_at,revision={table('team_auth_contexts')}.revision+1,updated_at=now()
            RETURNING *
        """, (int(team_id), int(account_id), workspace_id, identity_ref, encrypted_context, verified_at))


def get_auth_context(team_id, account_id, *, conn=None):
    with _connection(conn) as db:
        return _one(db, f"SELECT * FROM {table('team_auth_contexts')} WHERE team_id=%s AND account_id=%s",
                    (int(team_id), int(account_id)))


def find_auth_context(account_id, workspace_id, *, conn=None):
    with _connection(conn) as db:
        return _one(db, f"SELECT * FROM {table('team_auth_contexts')} WHERE account_id=%s AND workspace_id=%s",
                    (int(account_id), workspace_id))


# 读取实现与写入共享表结构，但不调用初始化，避免 GET 产生 DDL 或投影写入。
from core.storage.teams.reads import (  # noqa: E402
    get_team, list_teams, list_members, list_invitations, get_invitation,
    get_account_states, get_account_memberships,
)
from core.storage.teams.joins import (  # noqa: E402
    create_join_request, create_retry_join_request, get_join_request, update_join_request, list_join_items, get_pending_join_items,
    accept_join_item, accept_join_window, mark_join_item, get_capacity, reserve_capacity,
    update_invitation, start_invitation_execution, apply_sync_snapshot, save_execution_receipt,
    summarize_join_execution,
)
