"""Team 持久执行编排，复用统一网关、账号互斥和 Run 恢复。"""
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone

from core.operations import task_gateway as gateway
from core.operations.runtime import OperationCancelled
from core.teams.errors import TeamError

logger = logging.getLogger(__name__)
SOURCE_SYSTEM = "team_management"
RESOURCE_FAMILY = "openai_interactive"
TASK_TYPES = (
    "team_probe", "team_sync", "team_reverify", "team_join_request",
    "team_join", "team_invite", "team_accept", "team_outbox_drain",
)
_OUTBOX_KINDS = (
    "team_probe", "team_sync", "team_reverify", "team_permission_verify",
    "team_join_request", "team_join_target",
)
_ACTIVE = frozenset({"queued", "running", "waiting", "cancelling", "settling", "stopping"})
_WAIT_SECONDS = 2


def _store():
    from core.storage.teams import repository
    return repository


def _operations():
    from core.storage.operations import store
    return store


def _operation_table(name):
    from core.storage.operations import common
    return common._table(name)


def remote_adapter():
    """远端适配器只读取账号材料，工作区会话由本模块独立保存。"""
    from core.teams.remote import TeamRemoteAdapter
    return TeamRemoteAdapter()


def _data(context) -> dict:
    value = context.run.get("data")
    return dict(value) if isinstance(value, Mapping) else {}


def _required(row, code, message):
    if not row:
        raise TeamError(code, message, status=404)
    return row


def _team(team_id, *, conn=None):
    return _required(_store().get_team(int(team_id), conn=conn),
                     "team_not_found", "Team 不存在")


def enqueue_operation(conn, kind: str, payload: Mapping) -> dict:
    """供 HTTP 仓储的 task_factory 在同一事务保存 Task/Run。

    outbox 重投使用同一 source_id；业务事务提交后统一 dispatcher 才能读取。
    """
    from core.storage import records

    data = dict(payload)
    if data.get("parent_task_id"):
        if conn is None:
            with _store().transaction() as db:
                return enqueue_operation(db, kind, payload)
        _lock_parent_chain(conn, int(data["parent_task_id"]))
    name = {"team_join_target": "team_join", "team_permission_verify": "team_reverify"}.get(kind, kind)
    if name not in TASK_TYPES:
        raise TeamError("parameter_invalid", "不支持的 Team 任务类型", status=422)
    team_id = int(data["team_id"]) if data.get("team_id") else None
    team = _team(team_id, conn=conn) if team_id else {}
    account_id = None
    if name == "team_invite" or (name in {"team_probe", "team_sync", "team_reverify"}
                                and data.get("identity_child") is True):
        account_id = data.get("manager_account_id") or team.get("manager_account_id")
    elif name == "team_accept":
        account_id = data.get("account_id")
    account_id = int(account_id) if account_id else None
    account = records.get_row(records.ACCOUNTS, account_id, conn=conn) if account_id else {}
    if account_id and not account:
        raise TeamError("account_not_found", "账号不存在", status=404)
    identity = next((data.get(key) for key in
                     ("probe_id", "request_id", "join_request_id", "invitation_id", "team_id")
                     if data.get(key) is not None), "system")
    key = str(data.get("request_key") or data.get("idempotency_key") or
              data.get("dedupe_key") or f"{kind}:{identity}")
    source_id = str(data.get("source_id") or f"team:{kind}:{identity}:{key}")
    if team:
        data.setdefault("workspace_id", team["workspace_id"])
        data.setdefault("manager_account_id", team["manager_account_id"])
        data.setdefault("manager_revision", team["manager_revision"])
    data.setdefault("request_key", key)
    submitted = gateway.submit_durable_operation(
        task_type=name, account_id=account_id, email=str((account or {}).get("email") or ""),
        source_system=SOURCE_SYSTEM, source_id=source_id, idempotency_key=source_id,
        parent_task_id=int(data["parent_task_id"]) if data.get("parent_task_id") else None,
        batch_id=int(data["batch_id"]) if data.get("batch_id") else None,
        team_id=team_id, resource_family=RESOURCE_FAMILY, data=data, dispatch=False, conn=conn,
    )
    if not submitted.get("accepted"):
        if submitted.get("busy"):
            raise TeamError("team_account_busy", "账号暂忙，保留 Team 任务等待",
                            status=503, retryable=True)
        raise TeamError("team_store_unavailable", "Team 任务尚未完成持久受理",
                        status=503, retryable=True)
    if name == "team_join_request":
        submitted = _ensure_join_batch(conn, data, submitted)
    return submitted


def _lock_parent_chain(conn, task_id):
    """创建后续任务与停止请求按同一父链 Run 行锁串行。"""
    from core.storage import postgres
    from psycopg.rows import dict_row

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            WITH RECURSIVE parents AS (
              SELECT id,parent_task_id,last_run_id FROM {_operation_table('operation_tasks')} WHERE id=%s
              UNION ALL
              SELECT p.id,p.parent_task_id,p.last_run_id FROM {_operation_table('operation_tasks')} p
              JOIN parents ON p.id=parents.parent_task_id
            ) SELECT r.id,r.status,r.cancel_requested_at FROM {_operation_table('operation_runs')} r
              WHERE r.id IN (SELECT last_run_id FROM parents) ORDER BY r.id FOR UPDATE
        """, (int(task_id),))
        parents = cur.fetchall()
    if any(row["cancel_requested_at"] is not None or row["status"] in {"cancelled", "stopped"}
           for row in parents):
        raise OperationCancelled("Team 父任务已停止，后续子动作未创建")


def _ensure_join_batch(conn, data, submitted):
    from core.storage import postgres
    from psycopg.rows import dict_row

    # 正常由仓储同事务调用；outbox 仅重投已有引用，不产生第二份批次。
    if conn is None:
        with _store().transaction() as db:
            return _ensure_join_batch(db, data, submitted)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT batch_id FROM {_operation_table('operation_tasks')} WHERE id=%s FOR UPDATE",
                    (int(submitted["task_id"]),))
        row = cur.fetchone()
        batch_id = row["batch_id"]
        if batch_id is None:
            request_id = int(data.get("request_id") or data["join_request_id"])
            request = _store().get_join_request(int(data["team_id"]), request_id, conn=conn)
            batch = _operations().create_runtime_batch(
                batch_type="team_join", title="Team 批量加入",
                requested_count=int(request["requested_count"]), data={"team_id": int(data["team_id"]),
                                                                        "join_request_id": request_id}, conn=conn,
            )
            batch_id = int(batch["id"])
            cur.execute(f"UPDATE {_operation_table('operation_tasks')} SET batch_id=%s WHERE id=%s",
                        (batch_id, int(submitted["task_id"])))
            cur.execute(f"UPDATE {_operation_table('operation_runs')} SET batch_id=%s WHERE id=%s",
                        (batch_id, int(submitted["run_id"])))
            cur.execute(f"INSERT INTO {_operation_table('operation_batch_items')} (batch_id,task_id,run_id,ordinal) "
                        "VALUES (%s,%s,%s,1)", (batch_id, int(submitted["task_id"]), int(submitted["run_id"])))
    return {**submitted, "batch_id": int(batch_id)}


def enqueue_team_action(conn, kind: str, team_id: int) -> dict:
    """Team 行锁保护同类任务复用，保留不同类型及不同身份的独立运行。"""
    from core.storage import postgres
    from psycopg.rows import dict_row

    team = _store().get_team(int(team_id), for_update=True, conn=conn)
    _required(team, "team_not_found", "Team 不存在")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT t.id AS task_id,r.id AS run_id,r.status "
            f"FROM {_operation_table('operation_tasks')} t "
            f"JOIN {_operation_table('operation_runs')} r ON r.id=t.last_run_id "
            "WHERE t.source_system=%s AND t.team_id=%s AND t.task_type=%s "
            "AND t.account_id IS NULL "
            "AND r.status=ANY(%s) ORDER BY t.id DESC LIMIT 1",
            (SOURCE_SYSTEM, int(team_id), kind, list(_ACTIVE)),
        )
        existing = cur.fetchone()
    if existing:
        return {**dict(existing), "accepted": True, "reused": True}
    key = f"{kind}:{team_id}:{uuid.uuid4().hex}"
    payload = {
        "team_id": int(team_id), "manager_account_id": team["manager_account_id"],
        "manager_revision": team["manager_revision"], "request_key": key,
    }
    submitted = enqueue_operation(conn, kind, payload)
    _store().enqueue_outbox(kind, "team", int(team_id),
                            {**payload, "task_id": submitted["task_id"], "run_id": submitted["run_id"]},
                            dedupe_key=key, conn=conn)
    if kind == "team_sync":
        _store().update_team_runtime(int(team_id), changes={"last_sync_status": "queued"},
                                     manager_revision=team["manager_revision"], conn=conn)
    return submitted


def enqueue_sync_batch(conn, team_ids) -> dict:
    batch = _operations().create_runtime_batch(
        batch_type="team_sync", title="Team 批量同步", requested_count=len(team_ids),
        data={"team_ids": [int(value) for value in team_ids]}, conn=conn,
    )
    return {"batch_id": int(batch["id"])}


def attach_sync_batch(conn, batch_id: int, items) -> None:
    """同一执行可属于多次同步受理，原有 Task 批次引用保持准确。"""
    from core.storage import postgres
    from core.storage.operations import projection
    from psycopg.rows import dict_row

    accepted = [item for item in items if item.get("task_id") and item.get("run_id")]
    skipped = [item for item in items if not item.get("task_id")]
    with conn.cursor(row_factory=dict_row) as cur:
        for ordinal, item in enumerate(accepted, 1):
            cur.execute(
                f"INSERT INTO {_operation_table('operation_batch_items')} (batch_id,task_id,run_id,ordinal) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT(batch_id,run_id) DO NOTHING",
                (int(batch_id), int(item["task_id"]), int(item["run_id"]), ordinal),
            )
            cur.execute(f"UPDATE {_operation_table('operation_tasks')} SET batch_id=%s "
                        "WHERE id=%s AND batch_id IS NULL", (int(batch_id), int(item["task_id"])))
            cur.execute(f"UPDATE {_operation_table('operation_runs')} SET batch_id=%s "
                        "WHERE id=%s AND batch_id IS NULL", (int(batch_id), int(item["run_id"])))
        cur.execute(f"UPDATE {_operation_table('operation_batches')} "
                    "SET skipped_count=%s,data=data || %s::jsonb WHERE id=%s",
                    (len(skipped), json.dumps({"skipped": [
                        {"team_id": item.get("team_id"), "reason_code": item.get("reason_code")}
                        for item in skipped]}, ensure_ascii=False), int(batch_id)))
        projection._refresh_batches(cur, [int(batch_id)])


def _attach_outbox_result(kind: str, payload: Mapping, submitted: Mapping, *, conn):
    store = _store()
    task_id, run_id = int(submitted["task_id"]), int(submitted["run_id"])
    if kind == "team_probe":
        probe = store.get_probe(int(payload["probe_id"]), conn=conn)
        if probe and not probe.get("task_id"):
            store.update_probe(probe["id"], status="queued", task_id=task_id, run_id=run_id, conn=conn)
    elif kind == "team_join_request":
        request_id = payload.get("request_id") or payload.get("join_request_id")
        if request_id:
            store.update_join_request(int(payload["team_id"]), int(request_id),
                                      changes={"task_id": task_id, "run_id": run_id}, conn=conn)
    elif kind == "team_join_target" and payload.get("invitation_id"):
        invitation = store.get_invitation(int(payload["team_id"]), int(payload["invitation_id"]), conn=conn)
        if invitation and not invitation.get("last_run_id"):
            store.update_invitation(int(payload["team_id"]), int(payload["invitation_id"]),
                                    changes={"last_task_id": task_id, "last_run_id": run_id,
                                             "execution_status": "queued"}, conn=conn)


def process_pending_outbox(*, limit: int = 100) -> int:
    """按准确租约消费，重复投递只复用原 Task/Run，不另建调度线程。"""
    store = _store()
    processed = 0
    for event in store.claim_outbox(limit=limit, kinds=list(_OUTBOX_KINDS)):
        try:
            payload = dict(event.get("payload") or {})
            payload.setdefault("dedupe_key", event["dedupe_key"])
            with store.transaction() as conn:
                submitted = enqueue_operation(conn, str(event["kind"]), payload)
                _attach_outbox_result(str(event["kind"]), payload, submitted, conn=conn)
                if not store.complete_outbox(event["id"], event["lease_token"],
                                              result={"task_id": submitted["task_id"],
                                                      "run_id": submitted["run_id"]}, conn=conn):
                    raise TeamError("team_execution_lost", "出站任务租约已变化", retryable=True)
            processed += 1
        except OperationCancelled:
            if store.complete_outbox(event["id"], event["lease_token"], result={"cancelled": True}):
                processed += 1
        except Exception as exc:
            code = str(getattr(exc, "code", "team_outbox_store_failed"))
            store.release_outbox(event["id"], event["lease_token"],
                                 error={"code": code, "type": type(exc).__name__}, delay_seconds=5)
            logger.warning("Team 出站任务稍后重试：outbox_id=%s code=%s", event["id"], code)
    if processed:
        gateway.notify_dispatch()
    return processed


def ensure_outbox_drain() -> dict:
    """唯一的持久扫描 Run 在共享 dispatcher 内短时消费并延后重入。"""
    submitted = enqueue_operation(None, "team_outbox_drain", {
        "source_id": "team:outbox-drain:v1", "request_key": "team-outbox-drain-v1",
    })
    run = _operations().get_run(submitted["run_id"]) or {}
    if run.get("status") not in _ACTIVE:
        retry = _operations().retry_runtime_task(
            submitted["task_id"], trigger="startup_recovery",
            expected_previous_run_id=submitted["run_id"],
        )
        submitted["run_id"] = retry["id"]
    gateway.notify_dispatch()
    return submitted


def wake_outbox() -> None:
    """写请求提交后的轻量唤醒，不在 HTTP 中访问远端或遍历目标。"""
    ensure_outbox_drain()


def recover_pending(runtime_logger=None) -> int:
    store = _store()
    store.init()
    reconcile_execution_projections(recover=True)
    processed = process_pending_outbox()
    ensure_outbox_drain()
    if runtime_logger is not None:
        runtime_logger.info("Team 持久任务恢复完成：outbox=%s", processed)
    return processed


def reconcile_execution_projections(*, recover=False) -> int:
    """从持久当前 Run 收口业务执行投影，保留账号归属与未知结果占位。"""
    from core.storage import postgres
    from psycopg.rows import dict_row

    changed = 0
    with _store().transaction() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            SELECT i.team_id,i.id,i.execution_status AS old_status,r.status,r.error_code,r.error_message
            FROM {postgres.qualified('team_invitations')} i
            JOIN {_operation_table('operation_runs')} r ON r.id=i.last_run_id
            WHERE i.execution_status IN ('none','queued','running','waiting','cancelling','settling','stopping')
              AND r.status NOT IN ('queued','running','waiting','cancelling','settling','stopping')
        """)
        for row in cur.fetchall():
            status = _public_execution_status(row["status"])
            _store().update_invitation(row["team_id"], row["id"], changes={
                "execution_status": status, "active": False, "waiting_reason_code": None,
                "reason_code": row["error_code"] or ("team_execution_lost" if status == "interrupted" else None),
                "error_message": None,
            }, conn=conn)
            changed += 1
        cur.execute(f"""
            UPDATE {postgres.qualified('team_binding_probes')} p
            SET status=CASE WHEN r.status IN ('success','failed','cancelled','interrupted') THEN r.status
                            ELSE 'interrupted' END,
                stage='complete',updated_at=now()
            FROM {_operation_table('operation_runs')} r
            WHERE r.id=p.run_id AND p.status IN ('queued','running')
              AND r.status NOT IN ('queued','running','waiting','cancelling','settling','stopping')
        """)
        changed += cur.rowcount
        cur.execute(f"""
            UPDATE {postgres.qualified('team_join_requests')} j SET
                status=CASE WHEN r.status IN ('success','partial_success','failed','stopped','cancelled','interrupted')
                            THEN r.status ELSE 'failed' END,
                waiting_reason_code=NULL,updated_at=now()
            FROM {_operation_table('operation_runs')} r
            WHERE r.id=j.run_id AND j.status IN ('preparing','queued','running','waiting')
              AND r.status NOT IN ('queued','running','waiting','cancelling','settling','stopping')
        """)
        changed += cur.rowcount
        cur.execute(f"""
            UPDATE {postgres.qualified('team_members')} m SET execution_status=
              CASE WHEN r.status='attention_required' THEN 'failed' ELSE r.status END
            FROM {_operation_table('operation_runs')} r
            WHERE r.id=m.last_run_id
              AND r.status IN ('success','partial_success','failed','stopped','cancelled','interrupted','deactivated','unsupported','attention_required')
              AND m.execution_status IS DISTINCT FROM CASE WHEN r.status='attention_required' THEN 'failed' ELSE r.status END
        """)
        changed += cur.rowcount
        # 复用的同步 Run 可以关联新批次；其 terminal 写入只自动刷新原始批次。
        cur.execute(f"""
            SELECT b.id FROM {_operation_table('operation_batches')} b
            WHERE b.batch_type='team_sync' AND b.status IN ('queued','running')
              AND EXISTS (
                SELECT 1 FROM {_operation_table('operation_batch_items')} item
                JOIN {_operation_table('operation_runs')} r ON r.id=item.run_id
                WHERE item.batch_id=b.id AND r.status<>'queued'
              )
            ORDER BY b.id LIMIT 100
        """)
        batch_ids = [int(row["id"]) for row in cur.fetchall()]
        if batch_ids:
            from core.storage.operations import projection
            projection._refresh_batches(cur, batch_ids)
        if recover:
            # generic recovery 已先把失去 worker 的 Run 终态化；新 Run 会重新核对远端。
            cur.execute(f"""
                SELECT t.id,t.task_type,t.team_id,t.data,r.id AS run_id
                FROM {_operation_table('operation_tasks')} t
                JOIN {_operation_table('operation_runs')} r ON r.id=t.last_run_id
                WHERE t.source_system=%s AND r.status='interrupted'
                  AND t.task_type IN ('team_probe','team_sync','team_reverify','team_join_request','team_join')
                  AND COALESCE(t.data->>'identity_child','false')<>'true'
                ORDER BY t.id
            """, (SOURCE_SYSTEM,))
            for task in cur.fetchall():
                data = dict(task.get("data") or {})
                run = _operations().retry_runtime_task(task["id"], trigger="startup_recovery",
                    expected_previous_run_id=task["run_id"],
                    data={"identity_run_id": None, "identity_task_id": None, "intent_fence": None,
                          "invite_run_id": None, "accept_run_id": None}, conn=conn)
                if task["task_type"] == "team_join":
                    _store().update_invitation(task["team_id"], int(data["invitation_id"]), changes={
                        "last_task_id": task["id"], "last_run_id": run["id"], "execution_status": "queued", "active": True,
                    }, conn=conn)
                elif task["task_type"] == "team_probe":
                    _store().update_probe(int(data["probe_id"]), status="queued",
                                          task_id=task["id"], run_id=run["id"], conn=conn)
                elif task["task_type"] == "team_sync":
                    _store().update_team_runtime(task["team_id"], changes={"last_sync_status": "queued"}, conn=conn)
                elif task["task_type"] == "team_join_request":
                    _store().update_join_request(task["team_id"], int(data.get("request_id") or data["join_request_id"]),
                                                 changes={"task_id": task["id"], "run_id": run["id"], "status": "queued"}, conn=conn)
                changed += 1
    return changed


def _public_execution_status(status):
    return "failed" if status in {"attention_required", "request_unknown"} else str(status)


def _error_info(exc, stage):
    from core.operations.error_labels import label_for_code
    from core.storage.runtime_config import RuntimeConfigStoreError
    import psycopg

    if isinstance(exc, RuntimeConfigStoreError):
        code = "team_save_failed"
    elif isinstance(exc, psycopg.Error):
        code = "team_store_unavailable"
    else:
        code = str(getattr(exc, "code", "") or "team_execution_failed")
    message = label_for_code("code", code) or f"Team {stage} 阶段未完成（{type(exc).__name__}）"
    return {"code": code, "message": message[:1000], "stage": stage,
            "retryable": bool(getattr(exc, "retryable", True))}


def _failure(context, exc, stage, *, data=None, remote_started=False, joined=False):
    info = _error_info(exc, stage)
    values = dict(data or {})
    values.update(error_code=info["code"], stage=stage, error_info=info,
                  exception_type=type(exc).__name__)
    if joined:
        values["membership_state"] = "joined"
    context.report(stage=stage, state="failed", message=info["message"],
                   detail={"error_code": info["code"], "exception_type": type(exc).__name__})
    if remote_started:
        return gateway.OperationResult.request_unknown(info["message"], values)
    if joined:
        return gateway.OperationResult("partial_success", values, info["message"], info["message"])
    return gateway.OperationResult.failed(info["message"], values)


def _known_remote_rejection(exc):
    return str(getattr(exc, "code", "")) in {
        "team_invite_rejected", "team_invite_rate_limited", "team_permission_denied",
        "team_workspace_unavailable", "team_workspace_mismatch", "team_invite_unsupported",
        "team_accept_unsupported", "team_invitation_expired", "team_invitation_revoked",
        "parameter_invalid", "missing_auth_materials",
    }


def _probe(context):
    if context.account_id is None:
        return _identity_coordinator(context)
    data = _data(context)
    store = _store()
    probe_id = int(data["probe_id"])
    public_task_id = int(data.get("coordinator_task_id") or context.task_id)
    public_run_id = int(data.get("coordinator_run_id") or context.run_id)
    stage = "manager_auth"
    with context.lease(resource_family=RESOURCE_FAMILY, scope_kind="final"):
        try:
            context.checkpoint()
            store.update_probe(probe_id, status="running", stage=stage,
                               task_id=public_task_id, run_id=public_run_id)
            context.report(stage=stage, state="running", message="正在核验管理账号认证材料")
            stage = "workspace_discovery"
            context.report(stage=stage, state="running", message="正在读取账号可访问的工作区")
            result = remote_adapter().discover(context.account_id, data.get("target_workspace_id"))
            workspaces = list(result.get("workspaces") or [])
            context.checkpoint()
            stage = "permission_check"
            store.update_probe(probe_id, status="success", stage="complete", workspaces=workspaces,
                               task_id=public_task_id, run_id=public_run_id)
            context.report(stage=stage, state="success", message="工作区与权限证据已保存")
            return gateway.OperationResult.success({"probe_id": probe_id,
                                                     "workspace_count": len(workspaces)},
                                                    message="Team 绑定探测完成")
        except OperationCancelled:
            store.update_probe(probe_id, status="cancelled", stage=stage)
            raise
        except (gateway.OperationLeaseLost, *gateway.SETTLEMENT_CONTROL_ERRORS):
            raise
        except Exception as exc:
            store.update_probe(probe_id, status="failed", stage=stage, error_info=_error_info(exc, stage))
            return _failure(context, exc, stage)


def _snapshot(context, team, *, adapter=None):
    """完整远端证据与原身份回执分开保存，旧母号不能覆盖新快照。"""
    store = _store()
    adapter = adapter or remote_adapter()
    context.checkpoint()
    requested_at = datetime.now(timezone.utc)
    result = adapter.snapshot(context.account_id, team["workspace_id"])
    workspace = result.get("workspace") or {}
    returned_workspace = workspace.get("workspace_id") or workspace.get("id") or result.get("workspace_id")
    if returned_workspace and str(returned_workspace) != str(team["workspace_id"]):
        raise TeamError("team_workspace_mismatch", "远端工作区与任务目标不符", retryable=True)
    context.checkpoint()
    kwargs = {}
    if "purchased_seats" in result:
        kwargs["purchased_seats"] = result["purchased_seats"]
    if workspace.get("name") is not None:
        kwargs["name"] = workspace["name"]
    with store.transaction() as conn:
        _validate_gateway_fence(context, conn)
        store.save_execution_receipt(
            team["id"], request_key=f"snapshot:{context.run_id}:{context.execution_id}",
            workspace_id=team["workspace_id"], manager_account_id=context.account_id,
            manager_revision=team["manager_revision"], execution_fence=context.run_id, kind="sync",
            facts={"members_complete": result.get("members_complete") is True,
                   "invitations_complete": result.get("invitations_complete") is True,
                   "members": result.get("members"), "invitations": result.get("invitations"),
                   "purchased_seats": result.get("purchased_seats"),
                   "workspace": result.get("workspace"),
                   "observed_at": requested_at.isoformat(),
                   "run_id": context.run_id, "execution_id": context.execution_id}, conn=conn,
        )
        saved = store.apply_sync_snapshot(
            team["id"], workspace_id=team["workspace_id"], manager_account_id=context.account_id,
            manager_revision=team["manager_revision"], members=result.get("members"),
            invitations=result.get("invitations"), members_complete=result.get("members_complete") is True,
            invitations_complete=result.get("invitations_complete") is True,
            observed_at=requested_at,
            task_id=context.task_id, run_id=context.run_id, conn=conn, **kwargs,
        )
    return {**saved, "_snapshot_result": result}


def _validate_gateway_fence(context, conn):
    from psycopg.rows import dict_row
    with conn.cursor(row_factory=dict_row) as cur:
        if context.account_id is None:
            _operations()._remote_checkpoint_fence(
                cur, context.run_id, execution_id=context.execution_id,
                lease_token=None, require_lease=False,
            )
        else:
            _operations().fence_execution(cur, **context.execution_fence)


def _sync(context):
    if context.account_id is None:
        return _identity_coordinator(context)
    data = _data(context)
    team = _team(data["team_id"])
    stage = "manager_verify"
    with context.lease(resource_family=RESOURCE_FAMILY, scope_kind="final"):
        try:
            # 已发请求固定使用原管理身份；新任务从当前配置取得身份。
            if (context.account_id != int(team["manager_account_id"])
                    or int(data.get("manager_revision") or 0) != int(team["manager_revision"])):
                return gateway.OperationResult.success({"manager_changed": True}, message="母号已更换，交给当前身份")
            _store().update_team_runtime(team["id"], changes={"last_sync_status": "running"},
                                         manager_revision=team["manager_revision"])
            context.report(stage=stage, state="running", message="正在核验管理母号与目标工作区")
            stage = "state_check"
            saved = _snapshot(context, team)
            if (int(saved["manager_account_id"]) != context.account_id
                    or int(saved["manager_revision"]) != int(team["manager_revision"])):
                return gateway.OperationResult.success({"manager_changed": True}, message="旧母号回执已保存，继续核验当前身份")
            complete = saved.get("members_complete") is True and saved.get("invitations_complete") is True
            context.report(stage="persist", state="success", message="Team 成员、邀请及订阅证据已保存")
            return gateway.OperationResult("success" if complete else "partial_success",
                                           {"team_id": team["id"], "snapshot_complete": complete},
                                           "Team 同步完成" if complete else "Team 部分证据已同步")
        except OperationCancelled:
            _store().update_team_runtime(team["id"], changes={"last_sync_status": "interrupted"},
                                         manager_revision=team["manager_revision"])
            raise
        except (gateway.OperationLeaseLost, *gateway.SETTLEMENT_CONTROL_ERRORS):
            raise
        except Exception as exc:
            _store().update_team_runtime(team["id"], changes={"last_sync_status": "failed"},
                                         manager_revision=team["manager_revision"])
            return _failure(context, exc, stage)


def _reverify(context):
    if context.account_id is None:
        return _identity_coordinator(context)
    data = _data(context)
    team = _team(data["team_id"])
    with context.lease(resource_family=RESOURCE_FAMILY, scope_kind="final"):
        try:
            if (context.account_id != int(team["manager_account_id"])
                    or int(data.get("manager_revision") or 0) != int(team["manager_revision"])):
                return gateway.OperationResult.success({"manager_changed": True}, message="母号已更换，交给当前身份")
            context.report(stage="manager_verify", state="running", message="正在重新核验工作区管理权限")
            result = remote_adapter().discover(context.account_id, team["workspace_id"])
            workspace = next((row for row in result.get("workspaces", [])
                              if str(row.get("workspace_id")) == str(team["workspace_id"])), None)
            if not workspace:
                raise TeamError("team_workspace_unavailable", "目标工作区暂不可见", retryable=True)
            context.checkpoint()
            with _store().transaction() as conn:
                _validate_gateway_fence(context, conn)
                _store().save_execution_receipt(
                    team["id"], request_key=f"reverify:{context.run_id}:{context.execution_id}",
                    workspace_id=team["workspace_id"], manager_account_id=context.account_id,
                    manager_revision=int(data["manager_revision"]), execution_fence=context.run_id,
                    kind="reverify", facts={"role": workspace.get("role", "unknown"),
                                           "can_manage": workspace.get("can_manage"),
                                           "capabilities": workspace.get("capabilities") or {}}, conn=conn,
                )
                saved = _store().update_team_runtime(
                    team["id"], changes={"role": workspace.get("role", "unknown"),
                                         "permissions": {"can_manage": workspace.get("can_manage"),
                                                         "capabilities": workspace.get("capabilities") or {}},
                                         "permission_verified_at": datetime.now(timezone.utc)},
                    manager_revision=int(data.get("manager_revision") or team["manager_revision"]), conn=conn,
                )
            if (int(saved["manager_account_id"]) != context.account_id
                    or int(saved["manager_revision"]) != int(team["manager_revision"])):
                return gateway.OperationResult.success({"manager_changed": True}, message="旧母号权限回执已保存，继续当前身份")
            context.report(stage="persist", state="success", message="工作区管理权限证据已保存")
            return gateway.OperationResult.success({"team_id": team["id"]}, message="Team 权限核验完成")
        except (OperationCancelled, gateway.OperationLeaseLost, *gateway.SETTLEMENT_CONTROL_ERRORS):
            raise
        except Exception as exc:
            return _failure(context, exc, "manager_verify")


def _join_request(context):
    data = _data(context)
    request_id = int(data.get("request_id") or data["join_request_id"])
    team_id = int(data["team_id"])
    store = _store()
    try:
        context.checkpoint()
        store.update_join_request(team_id, request_id, changes={
            "status": "running", "task_id": context.task_id, "run_id": context.run_id,
        })
        pending = store.get_pending_join_items(request_id, limit=100)
        for item in pending:
            context.checkpoint()
            with store.transaction() as conn:
                _validate_gateway_fence(context, conn)
                store.accept_join_item(team_id, request_id, int(item["ordinal"]),
                                       task_factory=enqueue_operation, conn=conn)
        request = store.get_join_request(team_id, request_id)
        counts = request.get("counts") or {}
        if int(counts.get("pending_count") or 0):
            return context.defer(delay_seconds=0, reason="waiting_child", stage="state_check")
        # 逐账号执行由各自父任务协调，集合父任务只汇总当前固定回执。
        summary = store.summarize_join_execution(team_id, request_id)
        if summary["active_count"]:
            store.update_join_request(team_id, request_id, changes={
                "status": "waiting", "waiting_reason_code": "waiting_child",
            })
            return context.defer(delay_seconds=_WAIT_SECONDS, reason="waiting_child", stage="dispatch")
        failed = int(counts.get("failed_count") or 0) + int(summary["failed_count"])
        status = "partial_success" if failed else "success"
        store.update_join_request(team_id, request_id, changes={
            "status": status, "waiting_reason_code": None,
        })
        return gateway.OperationResult(status, {"team_id": team_id, "join_request_id": request_id},
                                       "Team 加入请求处理完成")
    except OperationCancelled:
        store.update_join_request(team_id, request_id, changes={"status": "cancelled"})
        raise
    except gateway.SETTLEMENT_CONTROL_ERRORS:
        raise
    except Exception as exc:
        store.update_join_request(team_id, request_id, changes={"status": "failed"})
        return _failure(context, exc, "state_check")


def _identity_coordinator(context):
    """HTTP 固定父任务先持久受理，母号暂忙时等空闲再建认证子任务。"""
    data = _data(context)
    try:
        context.checkpoint()
        child_run_id = data.get("identity_run_id")
        child = _operations().get_run(int(child_run_id)) if child_run_id else None
        if child and _restart_recoverable(child):
            retried = _retry_child_after_interrupt(child)
            if retried is None:
                return context.defer(delay_seconds=_WAIT_SECONDS, reason="waiting_account", stage="manager_verify")
            return context.defer(delay_seconds=0, reason="waiting_child", stage="manager_verify",
                                 data={"identity_task_id": int(child["task_id"]),
                                       "identity_run_id": int(retried["id"])})
        manager_changed = bool(child and (child.get("result_summary") or {}).get("manager_changed"))
        if child is None or manager_changed:
            payload = {
                **data, "identity_child": True, "parent_task_id": context.task_id,
                "coordinator_task_id": context.task_id, "coordinator_run_id": context.run_id,
                "source_id": f"team:identity:{context.run_id}",
                "request_key": f"team:identity:{context.run_id}",
            }
            if data.get("team_id"):
                current = _team(data["team_id"])
                payload.update(manager_account_id=current["manager_account_id"],
                               manager_revision=current["manager_revision"])
                payload["source_id"] += f":manager:{current['manager_revision']}"
                payload["request_key"] += f":manager:{current['manager_revision']}"
            try:
                submitted = enqueue_operation(None, context.task_type, payload)
            except TeamError as exc:
                if exc.code != "team_account_busy":
                    raise
                return context.defer(delay_seconds=_WAIT_SECONDS, reason="waiting_account", stage="manager_verify")
            return context.defer(delay_seconds=_WAIT_SECONDS, reason="waiting_child", stage="manager_verify",
                                 data={"identity_task_id": submitted["task_id"],
                                       "identity_run_id": submitted["run_id"]})
        if child["status"] in _ACTIVE:
            return context.defer(delay_seconds=_WAIT_SECONDS, reason="waiting_child", stage="manager_verify")
        summary = child.get("result_summary") or {}
        status = str(child["status"])
        if status == "attention_required":
            return gateway.OperationResult.request_unknown("Team 子任务回执尚待核验", summary)
        if status not in {"success", "partial_success", "failed", "cancelled", "interrupted", "deactivated"}:
            status = "failed"
        return gateway.OperationResult(status, summary,
                                       "Team 后台执行完成" if status == "success" else "Team 后台执行尚未完成",
                                       child.get("error_message"))
    except OperationCancelled:
        raise
    except gateway.SETTLEMENT_CONTROL_ERRORS:
        raise
    except Exception as exc:
        return _failure(context, exc, "manager_verify")


def _join(context):
    data = _data(context)
    store = _store()
    team_id, invitation_id = int(data["team_id"]), int(data["invitation_id"])
    fence = data.get("intent_fence")
    stage = "state_check"
    try:
        context.checkpoint()
        invitation = _required(store.get_invitation(team_id, invitation_id),
                               "invitation_not_found", "邀请不存在")
        if fence is None:
            with store.transaction() as conn:
                _validate_gateway_fence(context, conn)
                invitation = store.start_invitation_execution(
                    team_id, invitation_id, task_id=context.task_id, run_id=context.run_id, conn=conn,
                )
            # 先提交协调围栏，重启后再创建子任务，避免子任务持旧围栏继续写入。
            return context.defer(delay_seconds=0, reason="waiting_child", stage=stage,
                                 data={"intent_fence": invitation["execution_fence"]})
        if (int(invitation["execution_fence"]) != int(fence)
                or int(invitation.get("last_run_id") or 0) != context.run_id):
            raise TeamError("team_execution_lost", "加入执行围栏已变化", retryable=True)
        team = _team(team_id)
        for phase in ("invite", "accept"):
            stage = phase
            if phase == "invite" and invitation["membership_state"] == "joined":
                continue
            if phase == "invite" and invitation["invitation_state"] in {"pending", "accepted"}:
                continue
            child_id = data.get(f"{phase}_run_id")
            child = _operations().get_run(int(child_id)) if child_id else None
            if child and _restart_recoverable(child):
                retried = _retry_child_after_interrupt(child)
                if retried is None:
                    return _wait_intent(context, invitation, int(fence), "waiting_account", phase)
                return _wait_intent(
                    context, invitation, int(fence), "waiting_child", phase,
                    data={f"{phase}_task_id": int(child["task_id"]), f"{phase}_run_id": int(retried["id"])},
                )
            # 母号切换只发生在步骤边界；已经发出的请求继续保留原身份回执。
            manager_changed = phase == "invite" and child and (
                (child.get("result_summary") or {}).get("manager_changed") is True
            )
            if child is None or manager_changed:
                try:
                    submitted = _spawn_join_child(context, phase, team, invitation, int(fence))
                except TeamError as exc:
                    if exc.code != "team_account_busy":
                        raise
                    return _wait_intent(context, invitation, int(fence), "waiting_account", stage)
                return _wait_intent(
                    context, invitation, int(fence), "waiting_child", stage,
                    data={f"{phase}_task_id": submitted["task_id"],
                          f"{phase}_run_id": submitted["run_id"]},
                )
            if child["status"] in _ACTIVE:
                return _wait_intent(context, invitation, int(fence), "waiting_child", stage)
            if child["status"] != "success":
                summary = child.get("result_summary") or {}
                code = child.get("error_code") or summary.get("error_code") or "team_child_failed"
                store.update_invitation(team_id, invitation_id, execution_fence=int(fence), changes={
                    "execution_status": "failed", "active": False, "stage": summary.get("stage") or phase,
                    "waiting_reason_code": None, "reason_code": code,
                    "error_message": str((summary.get("error_info") or {}).get("message") or "Team 子任务未完成"),
                })
                values = {"team_id": team_id, "invitation_id": invitation_id,
                          "error_code": code, "stage": summary.get("stage") or phase,
                          "child_task_id": child["task_id"], "child_run_id": child["id"]}
                return gateway.OperationResult.failed("Team 子任务未完成，可继续或重跑", values)
        invitation = store.get_invitation(team_id, invitation_id)
        if invitation["membership_state"] != "joined" or not invitation["local_saved"]:
            raise TeamError("team_save_failed", "成员核验与保存尚未完整", retryable=True)
        store.update_invitation(team_id, invitation_id, execution_fence=int(fence), changes={
            "execution_status": "success", "stage": "complete", "active": False,
            "waiting_reason_code": None, "reason_code": None, "error_message": None,
        })
        return gateway.OperationResult.success(
            {"team_id": team_id, "invitation_id": invitation_id, "membership_state": "joined",
             "local_saved": True}, message="指定 Team 成员关系已核验并保存",
        )
    except OperationCancelled:
        if fence is not None:
            store.update_invitation(team_id, invitation_id, execution_fence=int(fence), changes={
                "execution_status": "cancelled", "active": False, "waiting_reason_code": None,
            })
        raise
    except gateway.SETTLEMENT_CONTROL_ERRORS:
        raise
    except Exception as exc:
        info = _error_info(exc, stage)
        if fence is not None:
            store.update_invitation(team_id, invitation_id, execution_fence=int(fence), changes={
                "execution_status": "failed", "active": False, "stage": stage,
                "reason_code": info["code"], "error_message": info["message"],
                "waiting_reason_code": None,
            })
        return _failure(context, exc, stage)


def _wait_intent(context, invitation, fence, reason, stage, *, data=None):
    _store().update_invitation(invitation["team_id"], invitation["id"], execution_fence=fence, changes={
        "execution_status": "waiting", "stage": stage, "waiting_reason_code": reason,
    })
    return context.defer(delay_seconds=_WAIT_SECONDS, reason=reason, stage=stage, data=data)


def _retry_child_after_interrupt(child):
    from psycopg.errors import UniqueViolation
    try:
        task = _operations().get_task(int(child["task_id"])) or {}
        with _store().transaction() as conn:
            if task.get("parent_task_id"):
                _lock_parent_chain(conn, int(task["parent_task_id"]))
            return _operations().retry_runtime_task(
                int(child["task_id"]), trigger="startup_recovery",
                expected_previous_run_id=int(child["id"]), conn=conn,
            )
    except UniqueViolation as exc:
        if str(getattr(exc.diag, "constraint_name", "")) == "uq_operation_runs_active_account_family":
            return None
        raise


def _restart_recoverable(run):
    summary = run.get("result_summary") or {}
    return (run["status"] == "interrupted" or
            (run["status"] == "attention_required"
             and (summary.get("cause_code") == "worker_interrupted"
                  or summary.get("recovery_reason") == "worker_restart")))


def _spawn_join_child(context, phase, team, invitation, fence):
    payload = {
        "team_id": team["id"], "workspace_id": team["workspace_id"],
        "invitation_id": invitation["id"], "account_id": invitation["account_id"],
        "email_snapshot": invitation["email_snapshot"], "parent_task_id": context.task_id,
        "parent_run_id": context.run_id, "intent_fence": fence,
        "manager_account_id": team["manager_account_id"], "manager_revision": team["manager_revision"],
        "request_key": f"team-join:{context.run_id}:{phase}:manager:{team['manager_revision']}",
    }
    return enqueue_operation(None, f"team_{phase}", payload)


def _validate_target(context, team, invitation):
    from core.teams.domain import classify
    state = _store().get_account_states(team["id"], [invitation["account_id"]]).get(invitation["account_id"])
    category, reason = classify(state, invitation["email_snapshot"])
    if category in {"unavailable", "another_team", "missing_auth"}:
        raise TeamError(reason, "Team 目标账号当前不能执行", retryable=True)
    check = _store().reserve_capacity(team["id"], invitation["id"], for_invite=False)
    if not check["reserved"]:
        raise TeamError(check["reason_code"], "账号 Team 业务归属已变化", retryable=True)
    context.checkpoint()


def _receipt(context, team, invitation, kind, facts):
    data = _data(context)
    with _store().transaction() as conn:
        _validate_gateway_fence(context, conn)
        return _store().save_execution_receipt(
            team["id"], invitation_id=invitation["id"],
            request_key=f"{kind}:{context.run_id}:{context.execution_id}",
            workspace_id=team["workspace_id"], manager_account_id=int(data["manager_account_id"]),
            manager_revision=int(data["manager_revision"]), execution_fence=int(data["intent_fence"]),
            kind=kind, facts={**facts, "observed_at": facts.get("observed_at") or datetime.now(timezone.utc).isoformat(),
                             "run_id": context.run_id, "execution_id": context.execution_id}, conn=conn,
        )


def _invitation_for_child(context):
    data = _data(context)
    team = _team(data["team_id"])
    invitation = _required(_store().get_invitation(team["id"], int(data["invitation_id"])),
                           "invitation_not_found", "邀请不存在")
    if int(invitation["execution_fence"]) != int(data["intent_fence"]):
        raise TeamError("team_execution_lost", "加入执行围栏已变化", retryable=True)
    if str(data.get("workspace_id")) != str(team["workspace_id"]):
        raise TeamError("team_workspace_mismatch", "任务工作区与 Team 不符", retryable=True)
    return team, invitation


def _invite(context):
    data = _data(context)
    stage = "manager_verify"
    remote_started = False
    remote_completed = False
    requested_at = None
    with context.lease(resource_family=RESOURCE_FAMILY, scope_kind="final"):
        try:
            team, invitation = _invitation_for_child(context)
            if (context.account_id != int(team["manager_account_id"])
                    or int(data["manager_revision"]) != int(team["manager_revision"])):
                return gateway.OperationResult.success({"manager_changed": True},
                                                        message="母号已更换，后续动作交给当前母号")
            _validate_target(context, team, invitation)
            context.report(stage=stage, state="running", message="正在核验母号与目标工作区")
            stage = "state_check"
            snapshot = _snapshot(context, team)
            remote = snapshot["_snapshot_result"]
            invitation = _store().get_invitation(team["id"], invitation["id"])
            states = _store().get_account_states(team["id"], [invitation["account_id"]])
            if invitation["membership_state"] == "joined" or states[invitation["account_id"]].get("already_member"):
                return gateway.OperationResult.success({"already_member": True}, message="成员已存在，继续核验保存")
            if invitation["invitation_state"] == "pending":
                return gateway.OperationResult.success({"invitation_exists": True}, message="有效邀请已存在，继续接受")
            if not (remote.get("members_complete") is True and remote.get("invitations_complete") is True):
                return _wait_intent(context, invitation, int(data["intent_fence"]), "waiting_sync", stage)
            stage = "invite"
            with _store().transaction() as conn:
                current = _store().get_team(team["id"], for_update=True, conn=conn)
                if (int(current["manager_revision"]) != int(data["manager_revision"])
                        or int(current["manager_account_id"]) != context.account_id):
                    return gateway.OperationResult.success({"manager_changed": True}, message="母号已更换，重新进入步骤")
                reserved = _store().reserve_capacity(team["id"], invitation["id"], conn=conn)
            if not reserved["reserved"]:
                reason = reserved["reason_code"]
                if reason in {"waiting_sync", "waiting_capacity", "team_limit_required"}:
                    return _wait_intent(context, invitation, int(data["intent_fence"]),
                                        "waiting_capacity" if reason == "team_limit_required" else reason, stage)
                raise TeamError(reason, "Team 邀请前置条件未满足", retryable=True)
            context.checkpoint()
            context.report(stage=stage, state="running", message="正在发送指定工作区的普通成员邀请")
            context.remote_request_started(
                "team_invite", request_id=f"team-invite:{context.run_id}",
                detail={"team_id": team["id"], "workspace_id": team["workspace_id"],
                        "manager_account_id": context.account_id, "manager_revision": data["manager_revision"]},
            )
            requested_at = datetime.now(timezone.utc).isoformat()
            remote_started = True
            result = remote_adapter().invite(context.account_id, team["workspace_id"], invitation["email_snapshot"])
            remote_completed = True
            returned_workspace = result.get("workspace_id")
            if returned_workspace and str(returned_workspace) != str(team["workspace_id"]):
                raise TeamError("team_workspace_mismatch", "邀请回执工作区不符", retryable=True)
            remote_invitation = result.get("invitation") or result
            remote_id = remote_invitation.get("remote_invitation_id") or remote_invitation.get("id")
            if not remote_id and remote_invitation.get("invitation_state") not in {"pending", "accepted"}:
                raise TeamError("team_invite_receipt_missing", "邀请回执尚未确认", retryable=True)
            facts = {"invitation_state": remote_invitation.get("invitation_state") or "pending",
                     "last_verified_at": datetime.now(timezone.utc).isoformat(),
                     "observed_at": requested_at}
            if remote_id:
                facts["remote_invitation_id"] = str(remote_id)
            _receipt(context, team, invitation, "invite", facts)
            persisted_invitation = _store().get_invitation(team["id"], invitation["id"])
            if persisted_invitation["invitation_state"] not in {"pending", "accepted"}:
                raise TeamError("team_save_failed", "邀请事实读回尚未确认", retryable=True)
            context.remote_request_receipt(outcome="confirmed", receipt_state="confirmed",
                                           request_id=f"team-invite:{context.run_id}",
                                           detail={"remote_result_confirmed": True,
                                                   "local_business_writeback_confirmed": True,
                                                   "local_readback_confirmed": True})
            context.report(stage=stage, state="success", message="邀请事实已确认并保存")
            return gateway.OperationResult.success({"team_id": team["id"], "invitation_id": invitation["id"]},
                                                    message="Team 邀请已保存")
        except (OperationCancelled, gateway.OperationLeaseLost, *gateway.SETTLEMENT_CONTROL_ERRORS):
            raise
        except Exception as exc:
            rejected = _known_remote_rejection(exc)
            if remote_started and not remote_completed:
                context.remote_request_receipt(outcome="rejected" if rejected else "unknown",
                                               receipt_state="rejected" if rejected else "unknown",
                                               request_id=f"team-invite:{context.run_id}",
                                               detail={"error_code": getattr(exc, "code", "team_invite_receipt_missing")})
            return _failure(context, exc, stage,
                            remote_started=remote_started and not remote_completed and not rejected)


def _accept(context):
    from core.storage.runtime_config import encrypt_private_text

    data = _data(context)
    stage = "member_auth"
    remote_started = False
    remote_completed = False
    joined = False
    requested_at = None
    with context.lease(resource_family=RESOURCE_FAMILY, scope_kind="final"):
        try:
            team, invitation = _invitation_for_child(context)
            _validate_target(context, team, invitation)
            context.report(stage=stage, state="running", message="正在核验成员账号与指定工作区")
            adapter = remote_adapter()
            verification_started_at = datetime.now(timezone.utc).isoformat()
            verification = adapter.verify_member(context.account_id, team["workspace_id"])
            joined = _verified_joined(verification, team["workspace_id"])
            if not joined:
                stage = "accept"
                if invitation["invitation_state"] != "pending":
                    raise TeamError("team_member_unconfirmed", "未发现可接受的目标工作区邀请", retryable=True)
                context.checkpoint()
                context.remote_request_started(
                    "team_accept", request_id=f"team-accept:{context.run_id}",
                    detail={"team_id": team["id"], "workspace_id": team["workspace_id"]},
                )
                requested_at = datetime.now(timezone.utc).isoformat()
                remote_started = True
                result = adapter.accept(context.account_id, team["workspace_id"], invitation)
                remote_completed = True
                returned_workspace = result.get("workspace_id")
                if returned_workspace and str(returned_workspace) != str(team["workspace_id"]):
                    raise TeamError("team_workspace_mismatch", "接受回执工作区不符", retryable=True)
                _receipt(context, team, invitation, "accept", {
                    "invitation_state": "accepted", "last_verified_at": datetime.now(timezone.utc).isoformat(),
                    "observed_at": requested_at,
                })
                persisted_invitation = _store().get_invitation(team["id"], invitation["id"])
                if persisted_invitation["invitation_state"] != "accepted":
                    raise TeamError("team_save_failed", "接受事实读回尚未确认", retryable=True)
                context.remote_request_receipt(outcome="confirmed", receipt_state="confirmed",
                                               request_id=f"team-accept:{context.run_id}",
                                               detail={"remote_result_confirmed": True,
                                                       "local_business_writeback_confirmed": True,
                                                       "local_readback_confirmed": True})
                stage = "member_verify"
                context.checkpoint()
                verification_started_at = datetime.now(timezone.utc).isoformat()
                verification = adapter.verify_member(context.account_id, team["workspace_id"])
                joined = _verified_joined(verification, team["workspace_id"])
            if not joined:
                raise TeamError("team_member_unconfirmed", "指定工作区成员关系尚未确认", retryable=True)
            stage = "member_verify"
            member = verification.get("member") or {}
            verified_at = datetime.now(timezone.utc).isoformat()
            facts = {"membership_state": "joined", "last_verified_at": verified_at,
                     "observed_at": verification_started_at,
                     "remote_user_id": member.get("remote_user_id") or member.get("id"),
                     "role": member.get("role") or "member"}
            # 远端加入事实先独立持久；随后加密或上下文保存失败仍保留 joined。
            _receipt(context, team, invitation, "member_verify", facts)
            stage = "persist"
            auth_context = verification.get("auth_context")
            if not isinstance(auth_context, Mapping) or not auth_context:
                raise TeamError("team_save_failed", "工作区认证上下文尚未取得", retryable=True)
            auth_workspace = auth_context.get("workspace_id")
            auth_email = str(auth_context.get("email") or "").strip().casefold()
            if (str(auth_workspace) != str(team["workspace_id"])
                    or (auth_email and auth_email != str(invitation["email_snapshot"]).strip().casefold())
                    or (auth_context.get("account_id") is not None
                        and int(auth_context["account_id"]) != context.account_id)):
                raise TeamError("team_workspace_mismatch", "工作区认证身份不符", retryable=True)
            identity = str(auth_context.get("user_id") or auth_context.get("identity_ref")
                           or facts.get("remote_user_id") or context.account_id)
            encrypted = encrypt_private_text(json.dumps(dict(auth_context), ensure_ascii=False))
            context.checkpoint()
            with _store().transaction() as conn:
                _validate_gateway_fence(context, conn)
                _store().get_team(team["id"], for_update=True, conn=conn)
                current = _store()._one(
                    conn, f"SELECT * FROM {_store().table('team_invitations')} WHERE team_id=%s AND id=%s FOR UPDATE",
                    (team["id"], invitation["id"]),
                )
                if int(current["execution_fence"]) != int(data["intent_fence"]):
                    raise TeamError("team_execution_lost", "结果保存执行围栏已变化", retryable=True)
                _store().put_auth_context(team["id"], context.account_id, workspace_id=team["workspace_id"],
                                          identity_ref=identity, encrypted_context=encrypted,
                                          verified_at=verified_at, conn=conn)
                _store().update_invitation(team["id"], invitation["id"], execution_fence=int(data["intent_fence"]),
                                           changes={"local_saved": True, "stage": "persist"}, conn=conn)
            context.report(stage=stage, state="success", message="成员关系与工作区认证上下文已保存")
            return gateway.OperationResult.success(
                {"team_id": team["id"], "invitation_id": invitation["id"], "membership_state": "joined",
                 "local_saved": True}, message="Team 成员已核验并保存",
            )
        except (OperationCancelled, gateway.OperationLeaseLost, *gateway.SETTLEMENT_CONTROL_ERRORS):
            raise
        except Exception as exc:
            rejected = _known_remote_rejection(exc)
            if remote_started and not remote_completed:
                context.remote_request_receipt(outcome="rejected" if rejected else "unknown",
                                               receipt_state="rejected" if rejected else "unknown",
                                               request_id=f"team-accept:{context.run_id}",
                                               detail={"error_code": getattr(exc, "code", "team_accept_receipt_missing")})
            return _failure(context, exc, stage,
                            remote_started=remote_started and not remote_completed and not rejected,
                            joined=joined)


def _verified_joined(verification, workspace_id):
    returned_workspace = verification.get("workspace_id")
    if returned_workspace is not None and str(returned_workspace) != str(workspace_id):
        raise TeamError("team_workspace_mismatch", "成员核验工作区不符", retryable=True)
    return verification.get("joined") is True and returned_workspace is not None


def _drain(context):
    context.checkpoint()
    reconcile_execution_projections(recover=True)
    process_pending_outbox()
    return context.defer(delay_seconds=_WAIT_SECONDS, reason="waiting_remote", stage="dispatch")


def retry_task(task, *, request_key=None):
    """任务中心与邀请 HTTP 共用同一持久幂等协调层。"""
    from core.teams import service
    data = dict(task.get("data") or {})
    if not data:
        latest = next((run for run in reversed(task.get("runs") or [])
                       if int(run.get("id") or 0) == int(task.get("last_run_id") or 0)), {})
        data = dict(latest.get("data") or {})
    if data.get("identity_child") and task.get("parent_task_id"):
        parent = _operations().get_task(int(task["parent_task_id"]))
        if parent:
            return retry_task(parent, request_key=request_key)
    if data.get("invitation_id"):
        return service.retry_task({**task, "data": data}, request_key)
    task_type = str(task.get("task_type") or "")
    if task_type not in {"team_probe", "team_sync", "team_reverify", "team_join_request"}:
        raise TeamError("parameter_invalid", "此 Team 任务不支持手动重跑", status=422)
    task_id = int(task["id"])
    path = f"/api/operations/{task_id}/retry"

    def action(conn):
        from core.storage import postgres
        from psycopg.rows import dict_row
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT * FROM {_operation_table('operation_tasks')} WHERE id=%s FOR UPDATE", (task_id,))
            current = dict(cur.fetchone())
            cur.execute(f"SELECT * FROM {_operation_table('operation_runs')} WHERE id=%s",
                        (current["last_run_id"],))
            run = dict(cur.fetchone())
        if run["status"] in _ACTIVE:
            return {"accepted": True, "reused": True, "task_id": task_id,
                    "run_id": int(run["id"]), "status": run["status"]}
        if task_type == "team_join_request":
            request_id = int(data.get("request_id") or data["join_request_id"])
            request = _store().create_retry_join_request(
                int(data["team_id"]), request_id, task_factory=enqueue_operation, conn=conn,
            )
            return service._request(_store().get_join_request(int(data["team_id"]), request["id"], conn=conn))
        retried = _operations().retry_runtime_task(
            task_id, trigger="manual_retry", expected_previous_run_id=int(run["id"]),
            data={"retry_action": "manual_retry", "identity_task_id": None, "identity_run_id": None},
            conn=conn,
        )
        if task_type == "team_probe":
            _store().update_probe(int(data["probe_id"]), status="queued", stage="queued",
                                  task_id=task_id, run_id=int(retried["id"]), conn=conn)
        elif task_type == "team_sync":
            _store().update_team_runtime(int(data["team_id"]), changes={"last_sync_status": "queued"}, conn=conn)
        return {"accepted": True, "reused": False, "task_id": task_id,
                "run_id": int(retried["id"]), "status": "queued"}

    result = service._write(path, {"task_id": str(task_id)}, request_key, 202, action)
    gateway.notify_dispatch()
    return result


def _cancel_descendants(task_id, *, conn):
    from core.storage import postgres
    from psycopg.rows import dict_row

    with conn.cursor(row_factory=dict_row) as cur:
        # 子任务入队同样先锁父链；拿到锁后再读取后代，覆盖并发创建边界。
        cur.execute(f"SELECT r.id FROM {_operation_table('operation_runs')} r "
                    f"JOIN {_operation_table('operation_tasks')} t ON t.last_run_id=r.id "
                    "WHERE t.id=%s FOR UPDATE OF r", (int(task_id),))
        cur.fetchall()
        cur.execute(f"""
            WITH RECURSIVE family AS (
              SELECT id,last_run_id,task_type,data FROM {_operation_table('operation_tasks')} WHERE id=%s
              UNION ALL
              SELECT child.id,child.last_run_id,child.task_type,child.data
              FROM {_operation_table('operation_tasks')} child JOIN family ON child.parent_task_id=family.id
              WHERE child.source_system=%s
            ) SELECT family.*,r.status FROM family
              JOIN {_operation_table('operation_runs')} r ON r.id=family.last_run_id
              ORDER BY family.id DESC
        """, (int(task_id), SOURCE_SYSTEM))
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        if row["status"] in _ACTIVE:
            cancelled = _operations().request_run_cancel(
                int(row["last_run_id"]), reason="用户停止 Team 任务", conn=conn,
            )
            data = dict(row.get("data") or {})
            status = "cancelled" if cancelled["status"] == "cancelled" else "cancelling"
            if row["task_type"] == "team_join" and data.get("invitation_id"):
                invitation = _store().get_invitation(int(data["team_id"]), int(data["invitation_id"]), conn=conn)
                if invitation and int(invitation.get("last_run_id") or 0) == int(row["last_run_id"]):
                    _store().update_invitation(int(data["team_id"]), int(data["invitation_id"]), changes={
                        "execution_status": status, "active": status != "cancelled",
                        "waiting_reason_code": None,
                    }, conn=conn)
            elif row["task_type"] == "team_probe":
                _store().update_probe(int(data["probe_id"]), status="cancelled", conn=conn)
            elif row["task_type"] == "team_sync":
                _store().update_team_runtime(int(data["team_id"]),
                                             changes={"last_sync_status": "interrupted"}, conn=conn)
            elif row["task_type"] == "team_join_request":
                request_id = int(data.get("request_id") or data["join_request_id"])
                _store().update_join_request(int(data["team_id"]), request_id,
                                             changes={"status": "cancelled"}, conn=conn)
    return rows


def cancel_task(task):
    with _store().transaction() as conn:
        rows = _cancel_descendants(int(task["id"]), conn=conn)
    gateway.notify_dispatch()
    return {"ok": True, "state": "cancelling", "running": any(row["status"] == "running" for row in rows),
            "message": "已记录 Team 停止请求，已确认成果与业务占用保留"}


def terminate_task(task):
    # 子动作协作式停止，当前任务沿用统一明确终止及资源回收语义。
    cancel_task(task)
    return gateway.default_operation_terminate(_operations().get_task(int(task["id"])) or task)


def register_handlers():
    from core.operations.concurrency import register_admission_alias
    handlers = {
        "team_probe": _probe, "team_sync": _sync, "team_reverify": _reverify,
        "team_join_request": _join_request, "team_join": _join,
        "team_invite": _invite, "team_accept": _accept, "team_outbox_drain": _drain,
    }
    for name, handler in handlers.items():
        register_admission_alias(name, "account_setup_retry")
        gateway.register_operation_handler(
            name, handler, source_systems=(SOURCE_SYSTEM,), retry_handler=retry_task,
            cancel_handler=cancel_task, terminate_handler=terminate_task,
        )
    return tuple(handlers)
