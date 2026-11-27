# -*- coding: utf-8 -*-
"""Team 固定名单、加入意图、容量与远端证据写入。"""
from __future__ import annotations

from core.storage.teams import repository as r
from core.teams.domain import classify, capacity as evaluate_capacity


def _invitation(db, team_id, invitation_id, *, lock=False):
    row = r._one(db, f"SELECT * FROM {r.table('team_invitations')} WHERE team_id=%s AND id=%s" +
                 (" FOR UPDATE" if lock else ""), (int(team_id), int(invitation_id)))
    if row is None:
        r._error("invitation_not_found", "邀请不存在", status=404)
    return row


def _counts(db, request):
    counts = r._one(db, f"""
        SELECT count(*) FILTER (WHERE acceptance_status='pending') AS pending_count,
          count(*) FILTER (WHERE acceptance_status IN ('accepted','reused')) AS accepted_count,
          count(*) FILTER (WHERE acceptance_status='reused') AS reused_count,
          count(*) FILTER (WHERE acceptance_status='skipped') AS skipped_count,
          count(*) FILTER (WHERE acceptance_status='failed') AS failed_count
        FROM {r.table('team_join_request_items')} WHERE request_id=%s
    """, (request["id"],))
    return {**{name: request[name] for name in ("requested_count", "unique_count", "duplicate_count")}, **counts}


def create_join_request(team_id, *, operation="join", targets, requested_count=None, selection_id=None,
                        selection_revision=None, task_id=None, run_id=None, batch_id=None, capacity=None,
                        task_factory=None, conn=None):
    with r._write_connection(conn) as db:
        team = r._require_team(db, team_id, lock=True)
        if operation == "join" and team["purchased_seats"] is None and team["planned_member_limit"] is None:
            r._error("team_limit_required", "缺人数上限")
        unique, seen = [], set()
        for target in targets:
            identity = ("account", str(target.get("account_id"))) if target.get("account_id") else (
                "invitation", str(target.get("input_invitation_id")))
            if identity not in seen:
                seen.add(identity)
                unique.append(dict(target))
        requested = int(requested_count if requested_count is not None else len(targets))
        if requested < len(unique):
            raise ValueError("原始数量小于去重数量")
        if selection_id is not None:
            r.records.advisory_xact_lock(db, f"team-selection:{r.postgres.schema_name()}:{int(selection_id)}")
            old = r._one(db, f"SELECT id FROM {r.table('team_join_requests')} WHERE selection_id=%s", (int(selection_id),))
            if old:
                r._error("selection_consumed", "名单已使用", existing_join_request_id=str(old["id"]))
        row = r._one(db, f"""
            INSERT INTO {r.table('team_join_requests')} (team_id,operation,selection_id,selection_revision,
              requested_count,unique_count,duplicate_count,task_id,run_id,batch_id,capacity)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *
        """, (int(team_id), operation, int(selection_id) if selection_id is not None else None,
              selection_revision, requested, len(unique), requested - len(unique), task_id, run_id, batch_id,
              r._json(capacity or {})))
        if unique:
            with db.cursor() as cur:
                cur.executemany(f"""
                    INSERT INTO {r.table('team_join_request_items')}
                      (request_id,ordinal,account_id,email_snapshot,input_invitation_id)
                    VALUES (%s,%s,%s,%s,%s)
                """, [(row["id"], ordinal, int(target["account_id"]) if target.get("account_id") else None,
                       target.get("email_snapshot"), target.get("input_invitation_id"))
                      for ordinal, target in enumerate(unique)])
        if selection_id is not None:
            from core.storage.operations import bulk_common
            qualified_selection = bulk_common.table("operation_selections")
            selection_table = r._one(db, "SELECT to_regclass(%s) AS name", (qualified_selection,))
            if selection_table["name"]:
                with db.cursor() as cur:
                    cur.execute(f"UPDATE {qualified_selection} SET status='consumed',updated_at=now() WHERE id=%s",
                                (int(selection_id),))
        refs, _ = r._task_and_outbox(
            db, "team_join_request", "join_request", row["id"],
            {"team_id": int(team_id), "request_id": row["id"], "manager_account_id": team["manager_account_id"],
             "manager_revision": team["manager_revision"], "operation": operation},
            task_factory=task_factory,
        )
        if refs:
            row = update_join_request(team_id, row["id"], changes={
                "task_id": refs.get("task_id"), "run_id": refs.get("run_id"), "batch_id": refs.get("batch_id"),
            }, conn=db)
        row["counts"] = _counts(db, row)
        return row


def get_join_request(team_id, request_id, *, conn=None):
    with r._connection(conn) as db:
        row = r._one(db, f"SELECT * FROM {r.table('team_join_requests')} WHERE team_id=%s AND id=%s",
                     (int(team_id), int(request_id)))
        if row:
            row["counts"] = _counts(db, row)
        return row


def create_retry_join_request(team_id, request_id, *, task_factory=None, conn=None):
    """集合复制原固定名单，新请求重新受理，保留原请求与逐项回执。"""
    with r._write_connection(conn) as db:
        team = r._require_team(db, team_id, lock=True)
        original = r._one(db, f"SELECT * FROM {r.table('team_join_requests')} "
                          "WHERE team_id=%s AND id=%s FOR SHARE", (int(team_id), int(request_id)))
        if original is None:
            r._error("join_request_not_found", "加入请求不存在", status=404)
        copied = r._one(db, f"""
            INSERT INTO {r.table('team_join_requests')}
              (team_id,operation,requested_count,unique_count,duplicate_count,capacity)
            SELECT team_id,'retry',requested_count,unique_count,duplicate_count,capacity
            FROM {r.table('team_join_requests')} WHERE id=%s RETURNING *
        """, (int(request_id),))
        with db.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {r.table('team_join_request_items')}
                  (request_id,ordinal,account_id,email_snapshot,input_invitation_id)
                SELECT %s,ordinal,account_id,email_snapshot,
                  COALESCE(invitation_id,input_invitation_id)
                FROM {r.table('team_join_request_items')} WHERE request_id=%s ORDER BY ordinal
            """, (copied["id"], int(request_id)))
        refs, _ = r._task_and_outbox(db, "team_join_request", "join_request", copied["id"],
            {"team_id": int(team_id), "request_id": copied["id"], "manager_account_id": team["manager_account_id"],
             "manager_revision": team["manager_revision"], "operation": "retry"},
            task_factory=task_factory)
        if refs:
            copied = update_join_request(team_id, copied["id"], changes={
                "task_id": refs.get("task_id"), "run_id": refs.get("run_id"), "batch_id": refs.get("batch_id"),
            }, conn=db)
        copied["counts"] = _counts(db, copied)
        return copied


def update_join_request(team_id, request_id, *, changes, conn=None):
    allowed = {"task_id", "run_id", "batch_id", "status", "waiting_reason_code", "capacity"}
    if set(changes) - allowed:
        raise ValueError("加入请求更新包含未授权字段")
    with r._write_connection(conn) as db:
        assignments, values = [], []
        for key, value in changes.items():
            assignments.append(f"{key}=%s" + ("::jsonb" if key == "capacity" else ""))
            values.append(r._json(value) if key == "capacity" else value)
        if not assignments:
            return get_join_request(team_id, request_id, conn=db)
        return r._one(db, f"UPDATE {r.table('team_join_requests')} SET {','.join(assignments)},updated_at=now() "
                      "WHERE team_id=%s AND id=%s RETURNING *", (*values, int(team_id), int(request_id)))


def list_join_items(team_id, request_id, query=None, *, conn=None):
    query = query or {}
    with r._connection(conn) as db:
        request = get_join_request(team_id, request_id, conn=db)
        if request is None:
            r._error("join_request_not_found", "加入请求不存在", status=404)
        where, values = ["request_id=%s"], [int(request_id)]
        for field in ("acceptance_status", "execution_status", "reason_code"):
            if query.get(field) is not None:
                where.append(f"{field}=%s")
                values.append(query[field])
        predicate = " AND ".join(where)
        total = r._one(db, f"SELECT count(*) AS count FROM {r.table('team_join_request_items')} WHERE {predicate}",
                       values)["count"]
        page, size = int(query.get("page", 1)), int(query.get("page_size", 20))
        items = r._all(db, f"SELECT * FROM {r.table('team_join_request_items')} WHERE {predicate} "
                      "ORDER BY ordinal LIMIT %s OFFSET %s", (*values, size, (page-1)*size))
        return {"request": request, "items": items, "total": total, "page": page, "page_size": size,
                "revision": f"{request_id}:{request['updated_at'].isoformat()}:{request['counts']}"}


def get_pending_join_items(request_id, *, limit=100, conn=None):
    with r._connection(conn) as db:
        return r._all(db, f"SELECT * FROM {r.table('team_join_request_items')} "
                      "WHERE request_id=%s AND acceptance_status='pending' ORDER BY ordinal LIMIT %s",
                      (int(request_id), int(limit)))


def mark_join_item(team_id, request_id, ordinal, *, changes, conn=None):
    allowed = {"account_id", "invitation_id", "acceptance_status", "task_id", "run_id",
               "execution_status", "reason_code", "message"}
    if set(changes) - allowed:
        raise ValueError("受理项目更新包含未授权字段")
    with r._write_connection(conn) as db:
        if get_join_request(team_id, request_id, conn=db) is None:
            r._error("join_request_not_found", "加入请求不存在", status=404)
        assignments, values = [], []
        for key, value in changes.items():
            assignments.append(f"{key}=%s")
            values.append(value)
        if not assignments:
            return r._one(db, f"SELECT * FROM {r.table('team_join_request_items')} WHERE request_id=%s AND ordinal=%s",
                          (int(request_id), int(ordinal)))
        row = r._one(db, f"UPDATE {r.table('team_join_request_items')} SET {','.join(assignments)},updated_at=now() "
                     "WHERE request_id=%s AND ordinal=%s RETURNING *", (*values, int(request_id), int(ordinal)))
        with db.cursor() as cur:
            cur.execute(f"UPDATE {r.table('team_join_requests')} SET updated_at=now() WHERE id=%s", (int(request_id),))
        return row


def _find_intent(db, team_id, *, account_id=None, email=None, remote_id=None):
    conditions, values = [], [int(team_id)]
    if account_id is not None:
        conditions.append("account_id=%s")
        values.append(int(account_id))
    if email:
        conditions.append("lower(btrim(COALESCE(email_snapshot,'')))=%s")
        values.append(str(email).strip().casefold())
    if remote_id:
        conditions.append("remote_invitation_id=%s")
        values.append(remote_id)
    if not conditions:
        return None
    return r._one(db, f"SELECT * FROM {r.table('team_invitations')} WHERE team_id=%s AND ({' OR '.join(conditions)}) "
                  "ORDER BY (account_id IS NOT NULL) DESC,id LIMIT 1 FOR UPDATE", values)


def accept_join_item(team_id, request_id, ordinal, *, task_factory=None, conn=None):
    with r._write_connection(conn) as db:
        request = get_join_request(team_id, request_id, conn=db)
        if request is None:
            r._error("join_request_not_found", "加入请求不存在", status=404)
        _lock_request_execution(db, request)
        item = r._one(db, f"SELECT * FROM {r.table('team_join_request_items')} WHERE request_id=%s AND ordinal=%s FOR UPDATE",
                      (int(request_id), int(ordinal)))
        if item is None or item["acceptance_status"] != "pending":
            return item
        supplied = None
        if item.get("input_invitation_id") is not None:
            supplied = r._one(db, f"SELECT * FROM {r.table('team_invitations')} WHERE team_id=%s AND id=%s",
                              (int(team_id), item["input_invitation_id"]))
            if supplied is None:
                return mark_join_item(team_id, request_id, ordinal, changes={
                    "acceptance_status": "skipped", "reason_code": "invitation_not_found",
                    "message": "邀请不存在或不属于此Team"}, conn=db)
            resolved_account_id = supplied["account_id"] or _account_by_email(db, supplied["email_snapshot"])
            if (item["account_id"] != resolved_account_id or
                (item["email_snapshot"] or "").strip().casefold() !=
                (supplied["email_snapshot"] or "").strip().casefold()):
                return mark_join_item(team_id, request_id, ordinal, changes={
                    "acceptance_status": "skipped", "reason_code": "account_identity_changed",
                    "message": "账号身份变化"}, conn=db)
        account_id = item["account_id"]
        if account_id is not None:
            r._lock_account(db, account_id)
        team = r._require_team(db, team_id, lock=True)
        states = r.get_account_states(team_id, [account_id] if account_id else [], conn=db)
        state = states.get(account_id)
        category, reason = classify(state, item.get("email_snapshot"))
        # 已加入但本地保存未完成的目标，只补保存，不伪造第二次远端加入。
        save_pending = bool(supplied and supplied["membership_state"] == "joined" and not supplied["local_saved"])
        if category in {"unavailable", "another_team", "already_member", "missing_auth"} and not (
            category == "already_member" and save_pending
        ):
            return mark_join_item(team_id, request_id, ordinal, changes={
                "account_id": account_id, "invitation_id": supplied["id"] if supplied else None,
                "acceptance_status": "skipped", "reason_code": reason, "message": reason,
            }, conn=db)
        if not r._claim_ownership(db, account_id, team_id, kind="intent"):
            return mark_join_item(team_id, request_id, ordinal, changes={
                "acceptance_status": "skipped", "reason_code": "already_in_another_team",
                "message": "已属其他Team"}, conn=db)
        intent = supplied or _find_intent(db, team_id, account_id=account_id, email=state["email"])
        if intent and intent["account_id"] is None:
            intent = r._one(db, f"UPDATE {r.table('team_invitations')} SET account_id=%s,updated_at=now() "
                            "WHERE team_id=%s AND id=%s AND account_id IS NULL RETURNING *",
                            (int(account_id), int(team_id), intent["id"]))
        if intent and intent["execution_status"] in r.ACTIVE_STATUSES:
            return mark_join_item(team_id, request_id, ordinal, changes={
                "account_id": account_id, "invitation_id": intent["id"], "acceptance_status": "reused",
                "task_id": intent["last_task_id"], "run_id": intent["last_run_id"],
                "execution_status": intent["execution_status"], "reason_code": None,
            }, conn=db)
        if intent is None:
            intent = r._one(db, f"""
                INSERT INTO {r.table('team_invitations')}
                  (team_id,target_key,account_id,email_snapshot,execution_status,manager_revision)
                VALUES (%s,%s,%s,%s,'queued',%s) RETURNING *
            """, (int(team_id), f"account:{account_id}", account_id,
                  item["email_snapshot"] or state["email"], team["manager_revision"]))
        r._claim_ownership(db, account_id, team_id, kind="intent", invitation_id=intent["id"])
        capacity = get_capacity(team_id, conn=db)
        waiting = "waiting_sync" if capacity["occupied_count"] is None else None
        if waiting is None and not intent["seat_reserved"] and intent["invitation_state"] != "pending":
            limit = capacity["effective_limit"]
            if limit is None or capacity["occupied_count"] >= limit:
                waiting = "waiting_capacity"
        refs, _ = r._task_and_outbox(db, "team_join_target", "invitation", intent["id"],
            {"team_id": int(team_id), "request_id": int(request_id), "invitation_id": intent["id"],
             "account_id": account_id, "manager_account_id": team["manager_account_id"],
             "manager_revision": team["manager_revision"], "parent_task_id": request["task_id"],
             "parent_run_id": request["run_id"], "operation": request["operation"],
             "request_key": f"team-join-item:{request_id}:{ordinal}"},
            task_factory=task_factory)
        intent = update_invitation(team_id, intent["id"], changes={
            "active": True, "execution_status": "waiting" if waiting else "queued",
            "waiting_reason_code": waiting, "last_task_id": refs.get("task_id"),
            "last_run_id": refs.get("run_id"), "manager_revision": team["manager_revision"],
            "reason_code": None, "error_message": None,
        }, conn=db)
        return mark_join_item(team_id, request_id, ordinal, changes={
            "account_id": account_id, "invitation_id": intent["id"], "acceptance_status": "accepted",
            "task_id": refs.get("task_id"), "run_id": refs.get("run_id"),
            "execution_status": intent["execution_status"], "reason_code": None,
        }, conn=db)


def _lock_request_execution(db, request):
    """先锁集合父链，再取业务锁，与停止请求和子任务入队保持相同顺序。"""
    if request.get("task_id") is None:
        return
    from core.storage.operations.common import _table as operation_table
    parents = r._all(db, f"""
        WITH RECURSIVE parents AS (
          SELECT id,parent_task_id,last_run_id FROM {operation_table('operation_tasks')} WHERE id=%s
          UNION ALL
          SELECT t.id,t.parent_task_id,t.last_run_id FROM {operation_table('operation_tasks')} t
          JOIN parents ON t.id=parents.parent_task_id
        ) SELECT run.id,run.status,run.cancel_requested_at FROM {operation_table('operation_runs')} run
          WHERE run.id IN (SELECT last_run_id FROM parents) ORDER BY run.id FOR UPDATE
    """, (request["task_id"],))
    if any(row["cancel_requested_at"] is not None or row["status"] in {"cancelled", "stopped"} for row in parents):
        from core.operations.runtime import OperationCancelled
        raise OperationCancelled("Team 集合父任务已停止，目标未继续受理")


def accept_join_window(request_id, *, limit=100, task_factory=None):
    with r._connection() as db:
        request = r._one(db, f"SELECT team_id FROM {r.table('team_join_requests')} WHERE id=%s", (int(request_id),))
        if request is None:
            return []
        items = get_pending_join_items(request_id, limit=limit, conn=db)
    return [accept_join_item(request["team_id"], request_id, item["ordinal"], task_factory=task_factory)
            for item in items]


def _occupancy_sql():
    # 已关联账号使用稳定本地 ID；未关联的相同邮箱也映射到此 ID，再对远端身份去重。
    return f"""
        WITH raw_facts AS MATERIALIZED (
          SELECT m.account_id,lower(btrim(COALESCE(m.email,''))) AS email,m.identity_key AS identity
          FROM {r.table('team_members')} m
          WHERE m.team_id=%s AND m.membership_state='joined'
          UNION ALL
          SELECT i.account_id,lower(btrim(COALESCE(i.email_snapshot,''))),i.target_key
          FROM {r.table('team_invitations')} i
          WHERE i.team_id=%s AND (i.invitation_state='pending' OR i.seat_reserved OR i.membership_state='joined')
        ), target_emails AS (
          SELECT DISTINCT email FROM raw_facts WHERE account_id IS NULL AND email<>''
        ), identity_accounts AS MATERIALIZED (
          SELECT e.email,a.account_id FROM target_emails e LEFT JOIN LATERAL (
            SELECT min(matched.id) AS account_id FROM (
              SELECT id FROM {r.table(r.records.ACCOUNTS.name)}
              WHERE lower(btrim(COALESCE(email,'')))=e.email LIMIT 2
            ) matched HAVING count(*)=1
          ) a ON TRUE
        )
        SELECT count(DISTINCT COALESCE('account:'||COALESCE(f.account_id,a.account_id)::text,
          'email:'||NULLIF(f.email,''),f.identity)) AS occupied_count
        FROM raw_facts f LEFT JOIN identity_accounts a ON a.email=f.email
    """


def get_capacity(team_id, *, team=None, conn=None):
    """读取容量事实；调用方可复用同一只读事务已取得的 Team 窄快照。"""
    if team is not None and int(team["id"]) != int(team_id):
        raise ValueError("Team 快照标识不符")
    with r._connection(conn) as db:
        if team is None:
            team = r._require_team(db, team_id)
        complete = team["members_complete"] and team["invitations_complete"]
        occupied = r._one(db, _occupancy_sql(), (int(team_id), int(team_id)))["occupied_count"] if complete else None
        facts = {key: team[key] for key in ("purchased_seats", "planned_member_limit",
                                          "members_complete", "invitations_complete")}
        facts["occupied_count"] = occupied
        return {**facts, **evaluate_capacity(facts, additional_required=None, eligible_count=1),
                "requires_sync": not complete}


def reserve_capacity(team_id, invitation_id, *, for_invite=True, conn=None):
    with r._write_connection(conn) as db:
        # 受理时已取得跨 Team 账号占用；容量只在工作区锁内计算并预留。
        team = r._require_team(db, team_id, lock=True)
        invitation = _invitation(db, team_id, invitation_id, lock=True)
        capacity = get_capacity(team_id, conn=db)
        if invitation["account_id"] is not None:
            owner = r._one(db, f"SELECT team_id FROM {r.table('team_account_ownership')} WHERE account_id=%s",
                           (invitation["account_id"],))
            if owner is None or owner["team_id"] != int(team_id):
                return {"reserved": False, "reason_code": "already_in_another_team", "capacity": capacity}
        own_place = invitation["seat_reserved"] or invitation["invitation_state"] == "pending" or invitation["membership_state"] == "joined"
        if not for_invite:
            return {"reserved": True, "reason_code": None, "capacity": capacity}
        if capacity["effective_limit"] is None:
            return {"reserved": False, "reason_code": "team_limit_required", "capacity": capacity}
        if capacity["occupied_count"] is None:
            return {"reserved": False, "reason_code": "waiting_sync", "capacity": capacity}
        limit, occupied = capacity["effective_limit"], capacity["occupied_count"]
        if occupied > limit or (not own_place and occupied >= limit):
            return {"reserved": False, "reason_code": "waiting_capacity", "capacity": capacity}
        if not invitation["seat_reserved"]:
            update_invitation(team_id, invitation_id, changes={"seat_reserved": True}, conn=db)
        return {"reserved": True, "reason_code": None, "capacity": get_capacity(team_id, conn=db)}


def update_invitation(team_id, invitation_id, *, changes, execution_fence=None, conn=None):
    allowed = {"remote_invitation_id", "invitation_state", "membership_state", "execution_status", "stage",
               "waiting_reason_code", "reason_code", "error_message", "last_task_id", "last_run_id", "active",
               "seat_reserved", "manager_revision", "local_saved", "last_verified_at"}
    if set(changes) - allowed:
        raise ValueError("邀请更新包含未授权字段")
    with r._write_connection(conn) as db:
        # 同步以 Team→成员→邀请的顺序写入，所有跨表执行投影沿用同一 Team 围栏。
        r._require_team(db, team_id, lock=True)
        old = _invitation(db, team_id, invitation_id, lock=True)
        if execution_fence is not None and int(execution_fence) != old["execution_fence"]:
            return old
        if not changes:
            return old
        fields, values = zip(*changes.items())
        row = r._one(db, f"UPDATE {r.table('team_invitations')} SET " +
                      ",".join(f"{field}=%s" for field in fields) +
                      ",updated_at=now() WHERE team_id=%s AND id=%s RETURNING *",
                      (*values, int(team_id), int(invitation_id)))
        if old["last_run_id"] is None and row["last_run_id"] is not None:
            # outbox 恢复首次创建执行时，把此前尚无引用的受理回执绑定到同一 Run。
            with db.cursor() as cur:
                cur.execute(f"""
                    UPDATE {r.table('team_join_request_items')} SET task_id=%s,run_id=%s,updated_at=now()
                    WHERE invitation_id=%s AND acceptance_status IN ('accepted','reused')
                      AND task_id IS NULL AND run_id IS NULL
                """, (row["last_task_id"], row["last_run_id"], int(invitation_id)))
        if set(changes) & {"execution_status", "reason_code", "error_message"}:
            # 请求回执跟随它实际引用的 Run；人工重跑的新 Run 不改写旧批次结果。
            with db.cursor() as cur:
                cur.execute(f"""
                    UPDATE {r.table('team_join_request_items')} SET execution_status=%s,
                      reason_code=%s,message=%s,updated_at=now()
                    WHERE invitation_id=%s AND acceptance_status IN ('accepted','reused')
                      AND task_id IS NOT DISTINCT FROM %s AND run_id IS NOT DISTINCT FROM %s
                """, (row["execution_status"], row["reason_code"], row["error_message"], int(invitation_id),
                      row["last_task_id"], row["last_run_id"]))
                if "execution_status" in changes:
                    cur.execute(f"""
                        UPDATE {r.table('team_members')} SET execution_status=%s,updated_at=now()
                        WHERE team_id=%s AND account_id=%s
                          AND last_task_id IS NOT DISTINCT FROM %s AND last_run_id IS NOT DISTINCT FROM %s
                    """, (row["execution_status"], int(team_id), row["account_id"],
                          row["last_task_id"], row["last_run_id"]))
        return row


def start_invitation_execution(team_id, invitation_id, *, task_id, run_id, conn=None):
    with r._write_connection(conn) as db:
        r._require_team(db, team_id, lock=True)
        return r._one(db, f"""
            UPDATE {r.table('team_invitations')} SET execution_fence=execution_fence+1,
              last_task_id=%s,last_run_id=%s,execution_status='running',active=TRUE,updated_at=now()
            WHERE team_id=%s AND id=%s RETURNING *
        """, (int(task_id), int(run_id), int(team_id), int(invitation_id)))


def _member_key(item):
    if item.get("remote_user_id"):
        return "remote:" + str(item["remote_user_id"])
    if item.get("email"):
        return "email:" + str(item["email"]).strip().casefold()
    if item.get("account_id"):
        return "account:" + str(item["account_id"])
    raise ValueError("成员缺少可识别身份")


def _apply_member(db, team_id, item, *, at, source_revision=0, task_id=None, run_id=None):
    identity = _member_key(item)
    account_id = item.get("account_id")
    if account_id is None and item.get("email"):
        account_id = _account_by_email(db, item["email"])
    existing = r._one(db, f"SELECT * FROM {r.table('team_members')} WHERE team_id=%s AND "
                     "(identity_key=%s OR (remote_user_id IS NOT NULL AND remote_user_id=%s) "
                     "OR ((remote_user_id IS NULL OR %s::text IS NULL) AND account_id=%s)) ORDER BY id LIMIT 1 FOR UPDATE",
                     (int(team_id), identity, item.get("remote_user_id"), item.get("remote_user_id"), account_id))
    if existing is not None and existing["last_verified_at"] is not None and at < existing["last_verified_at"]:
        return existing
    # 远端身份已关联本地账号后，邮箱显示变化不改换关联。
    if existing and existing["account_id"] is not None:
        account_id = existing["account_id"]
    state = item.get("membership_state", "joined")
    row = r._one(db, f"""
        INSERT INTO {r.table('team_members')}
          (team_id,identity_key,remote_user_id,email,account_id,role,membership_state,joined_at,
           last_verified_at,last_task_id,last_run_id,source_revision,execution_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(team_id,identity_key) DO UPDATE SET
          remote_user_id=COALESCE(EXCLUDED.remote_user_id,{r.table('team_members')}.remote_user_id),
          email=COALESCE(EXCLUDED.email,{r.table('team_members')}.email),
          account_id=COALESCE({r.table('team_members')}.account_id,EXCLUDED.account_id),
          role=EXCLUDED.role,membership_state=EXCLUDED.membership_state,
          joined_at=COALESCE({r.table('team_members')}.joined_at,EXCLUDED.joined_at),
          last_verified_at=EXCLUDED.last_verified_at,last_task_id=COALESCE(EXCLUDED.last_task_id,{r.table('team_members')}.last_task_id),
          last_run_id=COALESCE(EXCLUDED.last_run_id,{r.table('team_members')}.last_run_id),
          source_revision=EXCLUDED.source_revision,absent_complete_count=0,
          execution_status=CASE WHEN EXCLUDED.last_task_id IS NULL THEN {r.table('team_members')}.execution_status
                                ELSE EXCLUDED.execution_status END,updated_at=now() RETURNING *
    """, (int(team_id), existing["identity_key"] if existing else identity, item.get("remote_user_id"),
          item.get("email"), account_id, item.get("role", "unknown"), state, item.get("joined_at"),
          at, task_id, run_id, int(source_revision), item.get("execution_status", "running" if task_id is not None else "none")))
    if state == "joined" and account_id is not None:
        # 历史多 Team 事实都保存；业务占用冲突不覆盖原 owner。
        r._one(db, f"""
            INSERT INTO {r.table('team_account_ownership')}(account_id,team_id,kind)
            VALUES (%s,%s,'member') ON CONFLICT(account_id) DO NOTHING RETURNING account_id
        """, (account_id, int(team_id)))
    return row


def _account_by_email(db, email):
    if not email:
        return None
    accounts = r._all(db, f"SELECT id FROM {r.table(r.records.ACCOUNTS.name)} WHERE lower(btrim(COALESCE(email,'')))=%s LIMIT 2",
                      (str(email).strip().casefold(),))
    return accounts[0]["id"] if len(accounts) == 1 else None


def _timestamp(value):
    return r.datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value


def apply_sync_snapshot(team_id, *, workspace_id, manager_account_id, manager_revision, members=None,
                        invitations=None, purchased_seats=r.UNSET, name=r.UNSET, members_complete=False,
                        invitations_complete=False, observed_at=None, snapshot_sequence=None,
                        task_id=None, run_id=None, conn=None):
    with r._write_connection(conn) as db:
        team = r._require_team(db, team_id, lock=True)
        if team["workspace_id"] != workspace_id:
            r._error("team_workspace_mismatch", "同步工作区不符")
        if int(manager_account_id) != team["manager_account_id"] or int(manager_revision) != team["manager_revision"]:
            return team
        at = observed_at or r._now()
        if isinstance(at, str):
            at = r.datetime.fromisoformat(at.replace("Z", "+00:00"))
        if (snapshot_sequence is not None and int(snapshot_sequence) <= team["snapshot_sequence"]) or (
            team["last_snapshot_at"] is not None and at < team["last_snapshot_at"]
        ):
            return team
        sequence = int(snapshot_sequence) if snapshot_sequence is not None else team["snapshot_sequence"] + 1
        seen_members, seen_invitations = [], []
        if members is not None:
            for item in members:
                member = _apply_member(db, team_id, item, at=at, source_revision=sequence, task_id=task_id, run_id=run_id)
                seen_members.append(member["id"])
        if invitations is not None:
            for item in invitations:
                email = item.get("email_snapshot") or item.get("email")
                account_id = item.get("account_id") or _account_by_email(db, email)
                intent = _find_intent(db, team_id, account_id=account_id, email=email,
                                      remote_id=item.get("remote_invitation_id"))
                if intent is None:
                    key = f"account:{account_id}" if account_id is not None else (
                        f"email:{str(email).strip().casefold()}" if email else "remote:" + str(item["remote_invitation_id"]))
                    intent = r._one(db, f"""
                        INSERT INTO {r.table('team_invitations')}(team_id,target_key,account_id,email_snapshot)
                        VALUES (%s,%s,%s,%s) RETURNING *
                    """, (int(team_id), key, account_id, email))
                elif intent["account_id"] is None and account_id is not None:
                    # 尚未关联的远端记录可按唯一邮箱关联；已有账号关联不随显示邮箱变化改换。
                    with db.cursor() as cur:
                        cur.execute(f"UPDATE {r.table('team_invitations')} SET account_id=%s WHERE id=%s",
                                    (account_id, intent["id"]))
                seen_invitations.append(intent["id"])
                with db.cursor() as cur:
                    cur.execute(f"UPDATE {r.table('team_invitations')} SET absent_complete_count=0 WHERE id=%s",
                                (intent["id"],))
                if intent["last_verified_at"] is not None and at < intent["last_verified_at"]:
                    continue
                update_invitation(team_id, intent["id"], changes={
                    "remote_invitation_id": item.get("remote_invitation_id") or intent["remote_invitation_id"],
                    "invitation_state": item.get("invitation_state", "pending"),
                    "membership_state": item.get("membership_state", intent["membership_state"]),
                    "last_verified_at": at,
                }, conn=db)
        # 首次完整缺项只增加证据；后续完整读取再次确认缺项，才消退当前关系。
        # 邀请缺项并不证明具体撤回原因，保留历史接受事实并将 pending 改为 unconfirmed。
        if members_complete and members is not None:
            with db.cursor() as cur:
                cur.execute(f"""
                    UPDATE {r.table('team_members')} SET
                      absent_complete_count=absent_complete_count+1,
                      membership_state=CASE WHEN absent_complete_count>=1 AND membership_state='joined'
                        THEN 'left' ELSE membership_state END,updated_at=now()
                    WHERE team_id=%s AND NOT (id=ANY(%s::bigint[]))
                      AND (last_verified_at IS NULL OR last_verified_at<=%s)
                """, (int(team_id), seen_members, at))
        if invitations_complete and invitations is not None:
            with db.cursor() as cur:
                cur.execute(f"""
                    UPDATE {r.table('team_invitations')} SET absent_complete_count=0
                    WHERE team_id=%s AND id=ANY(%s::bigint[])
                """, (int(team_id), seen_invitations))
                cur.execute(f"""
                    UPDATE {r.table('team_invitations')} SET
                      absent_complete_count=absent_complete_count+1,
                      invitation_state=CASE WHEN absent_complete_count>=1 AND invitation_state='pending'
                        THEN 'unconfirmed' ELSE invitation_state END,updated_at=now()
                    WHERE team_id=%s AND NOT (id=ANY(%s::bigint[]))
                      AND (last_verified_at IS NULL OR last_verified_at<=%s)
                """, (int(team_id), seen_invitations, at))
        if members_complete and invitations_complete and members is not None and invitations is not None:
            _release_confirmed_absent(db, team_id)
        changes = {"members_complete": bool(members_complete), "invitations_complete": bool(invitations_complete),
                   "last_snapshot_at": at, "snapshot_sequence": sequence,
                   "last_sync_status": "success" if members_complete and invitations_complete else "partial_success"}
        if members is not None:
            changes["members_synced_at"] = at
        if invitations is not None:
            changes["invitations_synced_at"] = at
        if members_complete and invitations_complete:
            changes["last_synced_at"] = at
        if purchased_seats is not r.UNSET:
            changes["purchased_seats"] = purchased_seats
        if name is not r.UNSET:
            changes["name"] = name
        if members_complete:
            changes["confirmed_member_count"] = r._one(db, f"SELECT count(DISTINCT identity_key) AS count "
                f"FROM {r.table('team_members')} WHERE team_id=%s AND membership_state='joined'", (int(team_id),))["count"]
        if invitations_complete:
            changes["pending_invite_count"] = r._one(db, f"SELECT count(*) AS count "
                f"FROM {r.table('team_invitations')} WHERE team_id=%s AND invitation_state='pending'", (int(team_id),))["count"]
        fields, values = zip(*changes.items())
        return r._one(db, f"UPDATE {r.table('team_workspaces')} SET " + ",".join(f"{key}=%s" for key in fields) +
                      ",updated_at=now() WHERE id=%s RETURNING *", (*values, int(team_id)))


def _release_confirmed_absent(db, team_id):
    """仅双完整缺项、执行已终态且无当前远端关系时释放意图名额与业务占用。"""
    with db.cursor() as cur:
        cur.execute(f"""
            UPDATE {r.table('team_account_ownership')} o SET absent_complete_count=CASE
              WHEN EXISTS (SELECT 1 FROM {r.table('team_workspaces')} t
                    WHERE t.id=o.team_id AND t.manager_account_id=o.account_id)
                OR EXISTS (SELECT 1 FROM {r.table('team_members')} m
                    WHERE m.team_id=o.team_id AND m.account_id=o.account_id
                      AND m.membership_state='joined' AND m.absent_complete_count=0)
                OR EXISTS (SELECT 1 FROM {r.table('team_invitations')} i
                    WHERE i.team_id=o.team_id AND i.account_id=o.account_id
                      AND i.invitation_state='pending' AND i.absent_complete_count=0)
              THEN 0 ELSE absent_complete_count+1 END,updated_at=now()
            WHERE o.team_id=%s
        """, (int(team_id),))
        cur.execute(f"""
            UPDATE {r.table('team_invitations')} i SET seat_reserved=FALSE,active=FALSE,
              membership_state=CASE WHEN membership_state='joined' THEN 'left' ELSE membership_state END,updated_at=now()
            WHERE i.team_id=%s
              AND (i.absent_complete_count>=2 OR i.invitation_state IN ('revoked','expired'))
              AND i.invitation_state<>'pending'
              AND i.execution_status NOT IN ('queued','running','waiting','cancelling','settling','stopping')
              AND NOT EXISTS (
                SELECT 1 FROM {r.table('team_members')} m WHERE m.team_id=i.team_id AND m.membership_state='joined'
                  AND ((i.account_id IS NOT NULL AND m.account_id=i.account_id) OR
                       (i.email_snapshot IS NOT NULL AND lower(btrim(m.email))=lower(btrim(i.email_snapshot))))
              )
        """, (int(team_id),))
        cur.execute(f"""
            DELETE FROM {r.table('team_account_ownership')} o
            WHERE o.team_id=%s AND o.absent_complete_count>=2
              AND NOT EXISTS (SELECT 1 FROM {r.table('team_workspaces')} t
                WHERE t.id=o.team_id AND t.manager_account_id=o.account_id)
              AND NOT EXISTS (SELECT 1 FROM {r.table('team_members')} m
                WHERE m.team_id=o.team_id AND m.account_id=o.account_id AND m.membership_state='joined')
              AND NOT EXISTS (SELECT 1 FROM {r.table('team_invitations')} i
                WHERE i.team_id=o.team_id AND i.account_id=o.account_id AND
                  (i.active OR i.invitation_state='pending' OR i.membership_state='joined' OR i.seat_reserved OR
                   i.execution_status IN ('queued','running','waiting','cancelling','settling','stopping')))
        """, (int(team_id),))


def save_execution_receipt(team_id, *, request_key, workspace_id, manager_account_id, manager_revision,
                           execution_fence, kind, facts, invitation_id=None, conn=None):
    with r._write_connection(conn) as db:
        team = r._require_team(db, team_id, lock=True)
        if workspace_id != team["workspace_id"]:
            r._error("team_workspace_mismatch", "回执工作区不符")
        r.records.advisory_xact_lock(db, f"team-receipt:{r.postgres.schema_name()}:{request_key}")
        old = r._one(db, f"SELECT * FROM {r.table('team_execution_receipts')} WHERE request_key=%s", (request_key,))
        if old is not None:
            if (old["team_id"], old["invitation_id"], old["workspace_id"], old["kind"],
                old["manager_account_id"], old["manager_revision"], old["execution_fence"]) != (
                int(team_id), invitation_id, workspace_id, kind,
                int(manager_account_id), int(manager_revision), int(execution_fence)
            ):
                r._error("idempotency_conflict", "远端回执键冲突")
            return old
        intent = _invitation(db, team_id, invitation_id, lock=True) if invitation_id is not None else None
        row = r._one(db, f"""
            INSERT INTO {r.table('team_execution_receipts')}
              (team_id,invitation_id,request_key,workspace_id,manager_account_id,manager_revision,execution_fence,kind,facts)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *
        """, (int(team_id), invitation_id, request_key, workspace_id, int(manager_account_id),
              int(manager_revision), int(execution_fence), kind, r._json(facts)))
        # 回执总保留。当前事实只接受相同执行围栏，管理配置版本变化不抹掉原动作成果。
        observed_at = _timestamp(facts.get("observed_at") or facts.get("last_verified_at"))
        newer_fact = intent is not None and observed_at is not None and intent["last_verified_at"] is not None and (
            observed_at < intent["last_verified_at"]
        )
        if (intent is not None and intent["execution_fence"] == int(execution_fence)
            and not newer_fact):
            changes = {key: facts[key] for key in ("remote_invitation_id", "invitation_state", "membership_state",
                                                   "local_saved", "last_verified_at") if key in facts}
            # 已确认加入不能被较弱的迟到结果降级。
            if intent["membership_state"] == "joined" and changes.get("membership_state") == "unconfirmed":
                changes.pop("membership_state")
            if changes:
                changes.setdefault("last_verified_at", observed_at or r._now())
                update_invitation(team_id, intent["id"], changes=changes, execution_fence=execution_fence, conn=db)
            if facts.get("membership_state") == "joined" and intent["account_id"] is not None:
                _apply_member(db, team_id, {
                    "remote_user_id": facts.get("remote_user_id"), "email": intent["email_snapshot"],
                    "account_id": intent["account_id"], "membership_state": "joined",
                    "role": facts.get("role", "member"), "execution_status": intent["execution_status"],
                }, at=_timestamp(facts.get("last_verified_at")) or r._now(),
                    task_id=intent["last_task_id"], run_id=intent["last_run_id"])
            _refresh_known_counts(db, team_id)
        return row


def _refresh_known_counts(db, team_id):
    """逐目标成果只更新已建立的计数，不虚构完整远端同步时间或未知数量。"""
    with db.cursor() as cur:
        cur.execute(f"""
            UPDATE {r.table('team_workspaces')} w SET
              confirmed_member_count=CASE WHEN confirmed_member_count IS NULL THEN NULL ELSE (
                SELECT count(DISTINCT identity_key) FROM {r.table('team_members')}
                WHERE team_id=w.id AND membership_state='joined') END,
              pending_invite_count=CASE WHEN pending_invite_count IS NULL THEN NULL ELSE (
                SELECT count(*) FROM {r.table('team_invitations')}
                WHERE team_id=w.id AND invitation_state='pending') END,
              updated_at=now()
            WHERE w.id=%s
        """, (int(team_id),))


def summarize_join_execution(team_id, request_id, *, conn=None):
    with r._connection(conn) as db:
        if get_join_request(team_id, request_id, conn=db) is None:
            r._error("join_request_not_found", "加入请求不存在", status=404)
        return r._one(db, f"""
            SELECT count(*) FILTER (WHERE acceptance_status='pending') AS pending_count,
              count(*) FILTER (WHERE acceptance_status IN ('accepted','reused')
                AND execution_status IN ('none','queued','running','waiting','cancelling','settling','stopping')) AS active_count,
              count(*) FILTER (WHERE acceptance_status IN ('accepted','reused')
                AND execution_status='success') AS success_count,
              count(*) FILTER (WHERE acceptance_status='failed' OR
                (acceptance_status IN ('accepted','reused') AND execution_status IN
                  ('partial_success','failed','stopped','cancelled','interrupted','deactivated','unsupported'))) AS failed_count,
              count(*) FILTER (WHERE acceptance_status='skipped') AS skipped_count
            FROM {r.table('team_join_request_items')} WHERE request_id=%s
        """, (int(request_id),))
