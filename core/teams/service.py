"""Team 本地读取、幂等受理与领域协调，不在 HTTP 请求内访问远端。"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import date, datetime, timezone

from core.teams import domain
from core.teams.errors import TeamError


def _repo():
    from core.storage.teams import repository
    return repository


def _enqueue(conn, kind, payload):
    from core.teams.execution import enqueue_operation
    return enqueue_operation(conn, kind, payload)


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _id(value):
    return str(value) if value is not None else None


@contextmanager
def _read():
    from core.storage import postgres
    from core.storage.task_query_context import task_query
    from psycopg.rows import dict_row
    with task_query(), postgres.connect(row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        yield conn


def _write(path, payload, key, status, action):
    """请求键在同一事务内加锁，重发先复用原回执再检查当前状态。"""
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                           separators=(",", ":")).encode()).hexdigest()
    repo = _repo()
    with repo.transaction() as conn:
        receipt = repo.request_receipt(key, path=path, fingerprint=fingerprint, conn=conn)
        if receipt:
            return receipt["response_json"]
        result = _plain(action(conn))
        repo.save_request_receipt(key, path=path, fingerprint=fingerprint,
                                  response=result, status_code=status, conn=conn)
    from core.operations.task_gateway import notify_dispatch
    notify_dispatch()
    return result


def _team_or_error(team_id, *, conn=None, for_update=False):
    row = _repo().get_team(team_id, for_update=for_update, conn=conn)
    if row is None:
        raise TeamError("team_not_found", "Team 不存在。", status=404)
    return row


def _account(row, prefix="account"):
    if row.get(prefix) is not None:
        value = row[prefix]
        return {"id": _id(value["id"]), "email": value.get("email"),
                "archived": bool(value.get("archived"))}
    account_id = row.get(f"{prefix}_id")
    if account_id is None:
        return None
    display_prefix = "manager" if prefix == "manager_account" else prefix
    return {"id": _id(account_id), "email": row.get(f"{display_prefix}_email"),
            "archived": bool(row.get(f"{display_prefix}_archived"))}


def _team(row):
    result = {key: row.get(key) for key in (
        "workspace_id", "name", "display_name", "role", "purchased_seats", "planned_member_limit",
        "confirmed_member_count", "pending_invite_count", "processing_count",
        "last_synced_at", "last_sync_status", "revision")}
    result.update(id=_id(row["id"]), manager_account=_account(row, "manager_account"))
    if result["manager_account"] is None:
        result["manager_account"] = {
            "id": _id(row["manager_account_id"]), "email": row.get("manager_email"),
            "archived": bool(row.get("manager_archived")),
        }
    return _plain(result)


def _task(row):
    task_id, run_id = row.get("last_task_id"), row.get("last_run_id")
    return None if task_id is None else {
        "task_id": _id(task_id), "run_id": _id(run_id),
        "status": row.get("execution_status") or row.get("task_status") or "none"}


def _member(row):
    return _plain({
        "id": _id(row["id"]), "team_id": _id(row["team_id"]),
        **{key: row.get(key) for key in ("remote_user_id", "email", "role", "membership_state",
                                       "joined_at", "last_verified_at")},
        "account": _account(row), "latest_task": _task(row),
    })


def _invitation(row):
    status = row.get("execution_status") or "none"
    active = status in domain.ACTIVE_STATUSES
    complete = row.get("membership_state") == "joined" and row.get("local_saved")
    reason = "already_member" if complete else (
        "account_not_found" if not row.get("account_id") else None)
    error = None
    if row.get("reason_code") and status in {"failed", "partial_success", "unsupported", "interrupted"}:
        error = {"code": row["reason_code"], "message": row.get("error_message") or row["reason_code"],
                 "stage": row.get("stage") or "queued", "retryable": True}
    return _plain({
        "id": _id(row["id"]), "team_id": _id(row["team_id"]),
        "remote_invitation_id": row.get("remote_invitation_id"), "account": _account(row),
        "email_snapshot": row.get("email_snapshot"), "invitation_state": row["invitation_state"],
        "membership_state": row["membership_state"],
        "latest_execution": {
            "task_id": _id(row.get("last_task_id")), "run_id": _id(row.get("last_run_id")),
            "status": status, "stage": row.get("stage") or "queued",
            "waiting_reason_code": row.get("waiting_reason_code"), "error_info": error,
        },
        "updated_at": row.get("updated_at"), "last_verified_at": row.get("last_verified_at"),
        "actions": {
            "continue": {"enabled": reason is None, "reason_code": reason},
            "retry": {"enabled": reason is None and not active,
                      "reason_code": reason or ("same_team_active" if active else None)},
            "view_task": {"enabled": row.get("last_task_id") is not None, "reason_code": None},
        },
    })


def _page(raw, transform):
    return _plain({**raw, "items": [transform(item) for item in raw["items"]],
                   "revision": str(raw["revision"])})


def list_teams(query):
    with _read() as conn:
        return _page(_repo().list_teams(query, conn=conn), _team)


def get_team(team_id):
    with _read() as conn:
        row = _team_or_error(team_id, conn=conn)
        limited = row.get("purchased_seats") is not None or row.get("planned_member_limit") is not None
        return {
            "team": _team(row), "permission_verified_at": _plain(row.get("permission_verified_at")),
            "actions": {
                "sync": {"enabled": True, "reason_code": None},
                "reverify": {"enabled": True, "reason_code": None},
                "join": {"enabled": limited, "reason_code": None if limited else "team_limit_required"},
            },
        }


def start_probe(payload, key):
    def action(conn):
        row = _repo().create_probe(manager_account_id=int(payload["manager_account_id"]),
                                  target_workspace_id=payload.get("target_workspace_id"),
                                  task_factory=_enqueue, conn=conn)
        return {"probe_id": _id(row["id"]), "status": row["status"],
                "task_id": _id(row.get("task_id")), "run_id": _id(row.get("run_id"))}
    return _write("/api/teams/binding-probes", payload, key, 202, action)


def get_probe(probe_id):
    with _read() as conn:
        row = _repo().get_probe(probe_id, conn=conn)
        if row is None:
            raise TeamError("probe_not_found", "探测不存在。", status=404)
        account = _account(row, "manager_account")
        if account is None:
            from core.teams.queries import account_refs
            account = account_refs([row["manager_account_id"]], conn=conn).get(row["manager_account_id"])
        return _plain({
            "id": _id(row["id"]), "manager_account": account,
            **{name: row.get(name) for name in ("revision", "status", "stage", "workspaces",
                                              "suggested_workspace_id", "completed_at", "expires_at", "error_info")},
            "task_id": _id(row.get("task_id")), "run_id": _id(row.get("run_id")),
        })


def _action_receipt(team_id, refs, *, reused=False):
    return {"accepted": True, "reused": reused, "team_id": _id(team_id),
            "task_id": _id(refs.get("task_id")), "run_id": _id(refs.get("run_id")),
            "status": refs.get("status") or "queued"}


def create_team(payload, key):
    def action(conn):
        result = _repo().bind_team(**{
            name: payload[name] for name in ("manager_account_id", "workspace_id", "probe_id", "probe_revision")
        }, display_name=payload.get("display_name"), planned_member_limit=payload.get("planned_member_limit"),
            task_factory=_enqueue, conn=conn)
        row = result["team"]
        fresh = _team_or_error(row["id"], conn=conn)
        refs = result.get("task") or result.get("sync") or (result.get("outbox") or {}).get("payload") or {}
        return {"team": _team(fresh), "sync": _action_receipt(row["id"], refs)}
    return _write("/api/teams", payload, key, 201, action)


def update_team(team_id, payload, key):
    def action(conn):
        changes = {name: payload[name] for name in ("display_name", "planned_member_limit", "manager_account_id")
                   if name in payload}
        _repo().patch_team(team_id, expected_revision=payload["expected_revision"], changes=changes,
                           probe_id=payload.get("probe_id"), probe_revision=payload.get("probe_revision"), conn=conn)
        return {"team": _team(_team_or_error(team_id, conn=conn))}
    return _write(f"/api/teams/{team_id}", payload, key, 200, action)


def _sync(team_id, kind, conn):
    from core.teams.execution import enqueue_team_action
    _team_or_error(team_id, conn=conn, for_update=True)
    refs = enqueue_team_action(conn, kind, int(team_id))
    return _action_receipt(team_id, refs, reused=bool(refs.get("reused")))


def sync_team(team_id, payload, key):
    return _write(f"/api/teams/{team_id}/sync", payload, key, 202,
                  lambda conn: _sync(team_id, "team_sync", conn))


def reverify(team_id, payload, key):
    return _write(f"/api/teams/{team_id}/reverify", payload, key, 202,
                  lambda conn: _sync(team_id, "team_reverify", conn))


def sync_bulk(payload, key):
    def action(conn):
        from core.teams.execution import attach_sync_batch, enqueue_sync_batch
        unique = list(dict.fromkeys(payload["team_ids"]))
        batch = enqueue_sync_batch(conn, unique)
        items = []
        for team_id in unique:
            if _repo().get_team(team_id, conn=conn) is None:
                items.append({"team_id": team_id, "task_id": None, "run_id": None,
                              "acceptance_status": "skipped", "execution_status": "none",
                              "reason_code": "team_not_found"})
                continue
            receipt = _sync(team_id, "team_sync", conn)
            items.append({"team_id": team_id, "task_id": receipt["task_id"], "run_id": receipt["run_id"],
                          "acceptance_status": "reused" if receipt["reused"] else "accepted",
                          "execution_status": receipt["status"], "reason_code": None})
        accepted = sum(item["acceptance_status"] != "skipped" for item in items)
        attach_sync_batch(conn, int(batch["batch_id"]), items)
        return {"accepted": True, "batch_id": _id(batch["batch_id"]), "requested_count": len(payload["team_ids"]),
                "unique_count": len(unique), "duplicate_count": len(payload["team_ids"]) - len(unique),
                "reused_count": sum(item["acceptance_status"] == "reused" for item in items),
                "accepted_count": accepted, "skipped_count": len(unique) - accepted,
                "failed_count": 0, "items": items}
    return _write("/api/teams/sync-bulk", payload, key, 202, action)


def list_members(team_id, query):
    with _read() as conn:
        _team_or_error(team_id, conn=conn)
        return _page(_repo().list_members(team_id, query, conn=conn), _member)


def list_invitations(team_id, query):
    with _read() as conn:
        _team_or_error(team_id, conn=conn)
        return _page(_repo().list_invitations(team_id, query, conn=conn), _invitation)


def get_invitation(team_id, invitation_id):
    with _read() as conn:
        _team_or_error(team_id, conn=conn)
        row = _repo().get_invitation(team_id, invitation_id, conn=conn)
        if row is None:
            raise TeamError("invitation_not_found", "邀请不存在。", status=404)
        return {"invitation": _invitation(row)}


def list_candidates(team_id, query):
    from core.teams.queries import candidates
    with _read() as conn:
        _team_or_error(team_id, conn=conn)
        return candidates(team_id, query, conn=conn)


def resolve_candidates(team_id, payload):
    from core.teams.queries import resolve
    with _read() as conn:
        _team_or_error(team_id, conn=conn)
        return resolve(team_id, payload["values"], conn=conn)


def _targets(team_id, payload, *, consume=False, conn=None):
    if "selection_id" in payload:
        from core.teams.selection import read_team_selection
        return read_team_selection(payload["selection_id"], payload["selection_revision"], team_id,
                                   for_consumption=consume, conn=conn)
    return {"account_ids": payload["account_ids"], "expected_emails": payload.get("expected_emails", {}),
            "selection_id": None, "selection_revision": None}


def _preview_join(team_id, payload, *, conn):
    from core.storage.teams.preview import snapshot
    if "selection_id" in payload:
        _team_or_error(team_id, conn=conn)
    targets = _targets(team_id, payload, conn=conn)
    evaluated = snapshot(team_id, targets["account_ids"], targets["expected_emails"], conn=conn)
    row, facts = evaluated["team"], evaluated["facts"]
    additional = evaluated["additional_required"]
    result = {
        "counts": evaluated["counts"],
        "capacity": domain.capacity(
            facts, additional_required=None if additional and facts["occupied_count"] is None else additional,
            eligible_count=evaluated["counts"]["eligible_count"],
        ),
        "requires_sync": facts["occupied_count"] is None,
    }
    return _plain({**result, "team_id": _id(team_id), "selection_id": targets["selection_id"],
                   "selection_revision": targets["selection_revision"],
                   "snapshot_revision": str(row.get("snapshot_sequence", 0)),
                   "snapshot_at": datetime.now(timezone.utc), "team_last_synced_at": row.get("last_synced_at")})


def preview_join(team_id, payload):
    with _read() as conn:
        return _preview_join(team_id, payload, conn=conn)


def _request(row):
    return _plain({
        **{name: row.get(name) for name in ("operation", "status", "waiting_reason_code", "selection_revision",
                                          "created_at", "counts", "capacity")},
        **{name: _id(row.get(name)) for name in ("id", "team_id", "selection_id", "batch_id", "task_id", "run_id")},
        "accepted": True, "reused": False,
        "items_url": f"/api/teams/{row['team_id']}/join-requests/{row['id']}",
    })


def submit_join(team_id, payload, key):
    def action(conn):
        row = _team_or_error(team_id, conn=conn, for_update=True)
        if row.get("purchased_seats") is None and row.get("planned_member_limit") is None:
            raise TeamError("team_limit_required", "请先配置含母号的计划人数上限。")
        targets = _targets(team_id, payload, consume=True, conn=conn)
        unique = list(dict.fromkeys(targets["account_ids"]))
        states = _repo().get_account_states(team_id, unique, conn=conn)
        expected = targets["expected_emails"]
        fixed = [{"account_id": account_id,
                  "email_snapshot": expected[account_id] if account_id in expected else
                  (states.get(int(account_id)) or {}).get("email")} for account_id in unique]
        preview = domain.preview(targets["account_ids"], states, _repo().get_capacity(team_id, conn=conn), expected)
        request = _repo().create_join_request(
            team_id, targets=fixed, requested_count=len(targets["account_ids"]),
            selection_id=targets["selection_id"], selection_revision=targets["selection_revision"],
            capacity=preview["capacity"], task_factory=_enqueue, conn=conn)
        return _request(_repo().get_join_request(team_id, request["id"], conn=conn))
    return _write(f"/api/teams/{team_id}/join", payload, key, 202, action)


def get_join_request(team_id, request_id, query):
    with _read() as conn:
        _team_or_error(team_id, conn=conn)
        row = _repo().get_join_request(team_id, request_id, conn=conn)
        if row is None:
            raise TeamError("join_request_not_found", "加入请求不存在。", status=404)
        raw = _repo().list_join_items(team_id, request_id, query, conn=conn)
        def item(value):
            return {**value, **{name: _id(value.get(name)) for name in
                               ("account_id", "invitation_id", "task_id", "run_id")}}
        return {**_page(raw, item), "request": _request(row)}


def invitation_action(team_id, action, payload, key, invitation_id=None, *, _path=None):
    ids = [invitation_id] if invitation_id is not None else payload["invitation_ids"]
    path = _path or (f"/api/teams/{team_id}/invitations/{invitation_id}/{action}" if invitation_id else
                     f"/api/teams/{team_id}/invitations/{action}-bulk")
    def accept(conn):
        _team_or_error(team_id, conn=conn, for_update=True)
        targets = []
        seen_accounts = set()
        for value in dict.fromkeys(ids):
            row = _repo().get_invitation(team_id, value, conn=conn)
            if invitation_id is not None and row is None:
                raise TeamError("invitation_not_found", "邀请不存在。", status=404)
            account_id = row.get("account_id") if row else None
            if account_id is not None and account_id in seen_accounts:
                continue
            if account_id is not None:
                seen_accounts.add(account_id)
            targets.append({"account_id": account_id, "email_snapshot": row.get("email_snapshot") if row else None,
                            "input_invitation_id": value})
        current_capacity = domain.capacity(_repo().get_capacity(team_id, conn=conn),
                                           additional_required=None, eligible_count=len(targets))
        request = _repo().create_join_request(team_id, operation=action, targets=targets,
                                             requested_count=len(ids), capacity=current_capacity,
                                             task_factory=_enqueue, conn=conn)
        return _request(_repo().get_join_request(team_id, request["id"], conn=conn))
    return _write(path, payload, key, 202, accept)


def retry_task(task, key):
    data = task.get("data") or {}
    team_id = task.get("team_id") or data.get("team_id")
    invitation_id = data.get("invitation_id")
    if team_id is None or invitation_id is None:
        raise TeamError("parameter_invalid", "任务没有可重跑的加入目标。", status=422)
    return invitation_action(_id(team_id), "retry", {}, key, invitation_id=_id(invitation_id),
                             _path=f"/api/operations/{task['id']}/retry")
