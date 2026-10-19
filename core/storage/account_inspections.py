"""巡检沿用 PostgreSQL operation 批次、父子任务和原始 Run 快照。"""
from __future__ import annotations

import uuid
import json
from datetime import datetime
from core import postgres_store, record_store, task_run_log
from core.storage import operation

PARENT_TYPE = "account_inspection_batch"
ITEM_TYPE = "account_inspection"
ACTIVE = ("queued", "running", "waiting", "cancelling", "settling", "stopping")


def validate_scope(archived):
    if archived not in ("0", "only", "all"):
        raise ValueError("归档范围必须为 0（未归档）、only（已归档）或 all（全部）")
    return archived


def _task(cur, *, kind, batch_id, parent_id=None, account_id=None, email="", data=None, status="queued", resource_family=None):
    key = uuid.uuid4().hex
    cur.execute(f"""INSERT INTO {operation._table('operation_tasks')}
        (task_uuid,source_system,source_id,batch_id,parent_task_id,task_type,target_type,
         target_id,account_id,email_snapshot,requested_action,status,target_status,current_stage,trigger,data)
        VALUES (%s,'native_operations',%s,%s,%s,%s,'account',%s,%s,%s,%s,%s,'pending',%s,'inspection',%s::jsonb)
        RETURNING id""", (key,key,batch_id,parent_id,kind,account_id,account_id,email,kind,status,status,operation._json(data or {})))
    task_id = int(cur.fetchone()["id"])
    cur.execute(f"UPDATE {operation._table('operation_tasks')} SET root_task_id=%s WHERE id=%s",
                (parent_id or task_id,task_id))
    run = operation._insert_runtime_run(cur, task_id=task_id,run_no=1,source_system="native_operations",
        account_id=account_id,batch_id=batch_id,resource_family=resource_family or ("openai_interactive" if account_id else "inspection_coordinator"),
        data=data or {},initial_status=status)
    cur.execute(f"UPDATE {operation._table('operation_tasks')} SET last_run_id=%s WHERE id=%s",(run["id"],task_id))
    return task_id, int(run["id"])


def create_inspection(*, archived="0", workers=3, config_snapshot=None, idempotency_key=None):
    """创建快照与全部子任务必须同事务提交，dispatch 仅在提交后唤醒。"""
    validate_scope(archived)
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("巡检并发必须为 1–16 的整数")
    operation.init()
    records = postgres_store.qualified(record_store.ACCOUNTS.name)
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(operation._table('operation_tasks')+":inspection",))
        cur.execute(f"SELECT id FROM {operation._table('operation_tasks')} WHERE task_type=%s AND status=ANY(%s) ORDER BY id DESC LIMIT 1",
                    (PARENT_TYPE,list(ACTIVE)))
        active = cur.fetchone()
        if active:
            return int(active["id"]), False
        if idempotency_key:
            cur.execute(f"SELECT id FROM {operation._table('operation_tasks')} WHERE task_type=%s AND data->>'submission_key'=%s LIMIT 1",
                        (PARENT_TYPE,str(idempotency_key)))
            existing = cur.fetchone()
            if existing:
                return int(existing["id"]), False
        where, params = ("",()) if archived == "all" else (" WHERE archived=%s",(archived == "only",))
        cur.execute(f"SELECT id,email,deactivated,live_check_status,data->>'live_check_error' AS original_error FROM {records}{where} ORDER BY id FOR UPDATE",params)
        accounts = list(cur.fetchall())
        key = uuid.uuid4().hex
        data = {"archived":archived,"workers":workers,"total_count":len(accounts),"submission_key":str(idempotency_key or key)}
        cur.execute(f"""INSERT INTO {operation._table('operation_batches')}
            (batch_uuid,source_system,source_id,batch_type,title,status,requested_count,created_by,data)
            VALUES (%s,'native_operations',%s,%s,'账号巡检','queued',%s,'inspection',%s::jsonb) RETURNING id""",
            (key,key,PARENT_TYPE,len(accounts),operation._json(data)))
        batch_id = int(cur.fetchone()["id"])
        parent_id, parent_run = _task(cur,kind=PARENT_TYPE,batch_id=batch_id,data=data,status="waiting")
        for ordinal, account in enumerate(accounts,1):
            account_id = int(account["id"])
            cur.execute(f"SELECT 1 FROM {operation._table('operation_runs')} WHERE account_id=%s AND resource_family='openai_interactive' AND status=ANY(%s) LIMIT 1",
                        (account_id,list(ACTIVE)))
            busy = bool(cur.fetchone())
            dead = bool(account["deactivated"]) or str(account.get("live_check_status") or "").strip().lower() == "deactivated"
            item = {"inspection_id":parent_id,"target_account_id":account_id,"config_snapshot":config_snapshot or {}}
            task_id, run_id = _task(cur,kind=ITEM_TYPE,batch_id=batch_id,parent_id=parent_id,
                account_id=account_id,email=account["email"],data=item,
                resource_family="inspection_snapshot" if dead or busy else "openai_interactive")
            cur.execute(f"INSERT INTO {operation._table('operation_batch_items')} (batch_id,task_id,run_id,ordinal) VALUES (%s,%s,%s,%s)",
                        (batch_id,task_id,run_id,ordinal))
            if dead or busy:
                reason = "账号已标记为已废，跳过 AT 检查、刷新及套餐查询" if dead else "账号已有排队或运行中的操作，本次未能入队"
                if dead and account.get("original_error"):
                    reason += "；原因：" + task_run_log.redact_text(account["original_error"], 1500)
                summary = {"inspection_outcome":"deactivated_skipped" if dead else "rejected",
                           "checked":False,"invalid":False,"error":reason}
                terminal = "success" if dead else "failed"
                cur.execute(f"UPDATE {operation._table('operation_runs')} SET status=%s,resource_family='openai_interactive',completed_at=now(),result_summary=%s::jsonb,error_message=%s WHERE id=%s",
                            (terminal,operation._json(summary),None if dead else reason,run_id))
                cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status=%s,completed_at=now(),error_message=%s WHERE id=%s",(terminal,None if dead else reason,task_id))
        if accounts:
            operation._reconcile_parent_task_cur(cur,parent_id)
        else:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status='success',completed_at=now() WHERE id=%s",(parent_id,))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='success',completed_at=now() WHERE id=%s",(parent_run,))
        operation._refresh_batches(cur,[batch_id])
        return parent_id, True


def reconcile_parent_cur(cur, parent, *, child_task_id=None):
    """巡检协调只存定长计数；单个失败/废号不阻断整轮再次巡检。"""
    parent_id = int(parent["id"])
    cur.execute(f"""SELECT count(*) AS total,
        count(*) FILTER (WHERE status=ANY(%s)) AS active,
        count(*) FILTER (WHERE status NOT IN ('success') AND status<>ALL(%s)) AS failed
        FROM {operation._table('operation_tasks')} WHERE parent_task_id=%s""", (list(ACTIVE),list(ACTIVE),parent_id))
    counts = cur.fetchone()
    if not counts or not int(counts["total"]):
        return None
    waiting = int(counts["active"]) > 0
    desired = "waiting" if waiting else "success"
    run_id = int(parent.get("last_run_id") or 0)
    cur.execute(f"SELECT * FROM {operation._table('operation_runs')} WHERE id=%s FOR UPDATE",(run_id,))
    run = cur.fetchone()
    if run and waiting and run["status"] not in ACTIVE:
        cur.execute(f"SELECT max(run_no)+1 AS n FROM {operation._table('operation_runs')} WHERE task_id=%s",(parent_id,))
        number = int(cur.fetchone()["n"])
        run = operation._insert_runtime_run(cur,task_id=parent_id,run_no=number,source_system="native_operations",
            account_id=None,batch_id=parent["batch_id"],resource_family="inspection_coordinator",data=parent.get("data") or {},initial_status="waiting")
        run_id = int(run["id"])
    summary = {"child_count":int(counts["total"]),"processed_count":int(counts["total"])-int(counts["active"]),
               "failed_count":int(counts["failed"])}
    actions = [{"action":"cancel","label":"停止巡检"}] if waiting else [{"action":"retry","label":"再次巡检"}]
    cur.execute(f"""UPDATE {operation._table('operation_tasks')}
        SET status=%s,target_status=%s,current_stage=%s,next_actions=%s::jsonb,last_run_id=%s,
            completed_at=CASE WHEN %s THEN NULL ELSE now() END,updated_at=now() WHERE id=%s""",
        (desired,"pending" if waiting else "completed",desired if waiting else "complete",operation._json(actions),run_id,waiting,parent_id))
    cur.execute(f"""UPDATE {operation._table('operation_runs')} SET status=%s,progress_stage=%s,heartbeat_at=now(),
        completed_at=CASE WHEN %s THEN NULL ELSE COALESCE(completed_at,now()) END,result_summary=%s::jsonb
        WHERE id=%s""",(desired,desired if waiting else "complete",waiting,operation._json(summary),run_id))
    if str(parent.get("status") or "") != desired:
        key = uuid.uuid4().hex
        cur.execute(f"""INSERT INTO {operation._table('operation_events')}
            (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
            VALUES (%s,%s,%s,'native_operations',%s,'INFO',%s,'inspection.reconciled',%s,%s::jsonb)""",
            (key,parent_id,run_id,key,"waiting" if waiting else "complete",
             "等待本轮巡检子任务" if waiting else "本轮巡检处理完成，阶段结果见巡检历史",operation._json(summary)))
    if parent.get("batch_id"):
        operation._refresh_batches(cur,[int(parent["batch_id"])])
    return {"parent_task_id":parent_id,"child_task_id":child_task_id,"status":desired,**summary}


def reserve_pipeline(context):
    """每轮并发与共享账号操作预算同时生效；没有空位时交还 durable 队列。"""
    parent_id = int(context.run["parent_task_id"])
    with operation._connect() as conn, conn.cursor() as cur:
        # 与 finish_run 一致，先 Run 后父任务，避免取消/收口与并发领取锁序反转。
        cur.execute(f"SELECT execution_id,status FROM {operation._table('operation_runs')} WHERE id=%s FOR UPDATE",(context.run_id,))
        owned = cur.fetchone()
        if not owned or owned["execution_id"] != context.execution_id or owned["status"] != "running":
            return False
        cur.execute(f"SELECT data,status FROM {operation._table('operation_tasks')} WHERE id=%s FOR UPDATE",(parent_id,))
        parent = cur.fetchone()
        if not parent or parent["status"] not in ACTIVE:
            return False
        cur.execute(f"""SELECT count(*) AS n FROM {operation._table('operation_runs')} r
            JOIN {operation._table('operation_tasks')} t ON t.id=r.task_id
            WHERE t.parent_task_id=%s AND r.status IN ('running','cancelling','settling')
              AND r.data->>'inspection_execution'=r.execution_id AND r.id<>%s""",(parent_id,context.run_id))
        if int(cur.fetchone()["n"]) >= int(parent["data"].get("workers",3)):
            return False
        cur.execute(f"UPDATE {operation._table('operation_runs')} SET data=data || %s::jsonb WHERE id=%s AND execution_id=%s AND status='running'",
                    (operation._json({"inspection_execution":context.execution_id}),context.run_id,context.execution_id))
        return cur.rowcount == 1


def _original_runs_sql():
    return f"""FROM {operation._table('operation_tasks')} t
        JOIN {operation._table('operation_batch_items')} i ON i.task_id=t.id AND i.batch_id=t.batch_id
        JOIN {operation._table('operation_runs')} r ON r.id=i.run_id"""


def _aggregate(cur, parent):
    """数据库聚合阶段计数，轮询不传输全部账号的 Run JSON。"""
    source = _original_runs_sql()
    outcome = "r.result_summary->>'inspection_outcome'"
    dead = f"({outcome}='deactivated_skipped' OR (r.status='deactivated' AND {outcome} IS NULL))"
    cur.execute(f"""SELECT
        count(*) FILTER (WHERE r.status=ANY(%s)) AS active_count,
        count(*) FILTER (WHERE r.status IN ('interrupted','cancelled','stopped')) AS interrupted_count,
        count(*) FILTER (WHERE r.result_summary->>'checked'='true') AS checked_count,
        count(*) FILTER (WHERE {dead} OR {outcome}='deleted_skipped') AS skipped_count,
        count(*) FILTER (WHERE {dead}) AS deactivated_skipped_count,
        count(*) FILTER (WHERE r.result_summary->>'invalid'='true') AS invalid_count,
        count(*) FILTER (WHERE r.result_summary->>'live_ok'='true') AS live_success_count,
        count(*) FILTER (WHERE r.result_summary->>'live_ok'='false' OR {outcome}='rejected'
          OR (r.status IN ('failed','attention_required','interrupted') AND {outcome} IS NULL)) AS live_failed_count,
        count(*) FILTER (WHERE r.result_summary->>'plan_ok'='true') AS plan_success_count,
        count(*) FILTER (WHERE r.result_summary->>'plan_ok'='false') AS plan_failed_count,
        max(r.completed_at) AS finished_at
        {source} WHERE t.parent_task_id=%s""", (list(ACTIVE), int(parent["id"])))
    aggregate = dict(cur.fetchone())
    active = int(aggregate.pop("active_count")) > 0
    interrupted = int(aggregate.pop("interrupted_count")) > 0
    finished = aggregate.pop("finished_at")
    finished_at = finished or parent.get("completed_at")
    data = parent.get("data") or {}
    return {"id": int(parent["id"]), "task_id": int(parent["id"]), "batch_id": parent["batch_id"],
        "status": "running" if active else "interrupted" if interrupted else "completed",
        "archived": data.get("archived", "0"), "workers": data.get("workers", 3),
        "total_count": data.get("total_count", 0), "created_at": parent["created_at"].isoformat(),
        "finished_at": None if active or finished_at is None else finished_at.isoformat(),
        **{key: int(value) for key, value in aggregate.items()}}


def list_inspections(*, limit=20, offset=0):
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_tasks')} WHERE task_type=%s", (PARENT_TYPE,))
        total = int(cur.fetchone()["n"])
        cur.execute(f"SELECT * FROM {operation._table('operation_tasks')} WHERE task_type=%s ORDER BY id DESC LIMIT %s OFFSET %s", (PARENT_TYPE, limit, offset))
        parents = list(cur.fetchall())
        values = [_aggregate(cur, parent) for parent in parents]
        cur.execute(f"SELECT * FROM {operation._table('operation_tasks')} WHERE task_type=%s AND status=ANY(%s) ORDER BY id DESC LIMIT 1", (PARENT_TYPE, list(ACTIVE)))
        parent = cur.fetchone()
        active = _aggregate(cur, parent) if parent else None
        return {"items": values, "active": active, "total": total}


def failures(inspection_id, *, limit=20, offset=0):
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute(f"SELECT * FROM {operation._table('operation_tasks')} WHERE id=%s AND task_type=%s", (inspection_id, PARENT_TYPE))
        parent = cur.fetchone()
        if not parent:
            return None
        task = _aggregate(cur, parent)
        source = _original_runs_sql()
        where = """WHERE t.parent_task_id=%s AND (
            r.result_summary->>'inspection_outcome' IN ('deactivated_skipped','rejected')
            OR r.result_summary->>'live_ok'='false'
            OR r.status IN ('deactivated','failed','attention_required','interrupted'))"""
        cur.execute(f"SELECT count(*) AS n {source} {where}", (inspection_id,))
        total = int(cur.fetchone()["n"])
        cur.execute(f"""SELECT t.id AS task_id, t.account_id, t.email_snapshot,
            t.data->>'target_account_id' AS target_account_id, r.id AS run_id, r.status,
            r.result_summary->>'inspection_outcome' AS outcome,
            COALESCE(r.result_summary->>'error', r.error_message, '账号已废，本次跳过') AS error,
            COALESCE(r.completed_at,r.created_at) AS failed_at
            {source} {where} ORDER BY t.id LIMIT %s OFFSET %s""", (inspection_id, limit, offset))
        details = [{"account_id": int(item["target_account_id"] or item["account_id"]),
            "email": item["email_snapshot"], "status": item["outcome"] or ("deactivated_skipped" if item["status"] == "deactivated" else item["status"]),
            "task_id": int(item["task_id"]), "run_id": int(item["run_id"]), "failed_at": item["failed_at"].isoformat(),
            "error": task_run_log.redact_text(item["error"], 2000)} for item in cur.fetchall()]
        return {"task": task, "items": details, "total": total, "details_available": True}


def child_runs(inspection_id):
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT r.id AS run_id,r.status {_original_runs_sql()} WHERE t.parent_task_id=%s",(int(inspection_id),))
        return [(int(item["run_id"]),item["status"]) for item in cur.fetchall()]


def active_child_runs(inspection_id):
    """控制面查当前活动 Run；历史查询仍固定使用批次原始 Run。"""
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT r.id AS run_id,r.status
            FROM {operation._table('operation_tasks')} t
            JOIN {operation._table('operation_runs')} r ON r.task_id=t.id
            WHERE t.parent_task_id=%s AND r.status=ANY(%s) ORDER BY r.id""",
            (int(inspection_id),list(ACTIVE)))
        return [(int(item["run_id"]),item["status"]) for item in cur.fetchall()]


def delete_deactivated(archived):
    """在账号行锁内按最新状态删除；不修改邮箱池与 operation 审计。"""
    validate_scope(archived)
    record_store.init()
    table=postgres_store.qualified(record_store.ACCOUNTS.name)
    where="(deactivated OR lower(trim(COALESCE(live_check_status,'')))='deactivated')"
    params=()
    if archived != "all":
        where += " AND archived=%s"
        params=(archived == "only",)
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE {where} RETURNING id",params)
        return len(cur.fetchall())


def save_liveness(account_id, result, *, fence, expected_email, expected_token):
    """原会话回调先保存 AT；执行、账号快照和业务写回使用同一个事务。"""
    from core.chatgpt_plan import token_claims
    from core.operations.task_gateway import OperationLeaseLost
    now=datetime.now().isoformat(timespec="seconds")
    with operation._connect() as conn, conn.cursor() as cur:
        try:
            operation.fence_execution(cur,**fence)
        except (PermissionError,LookupError) as exc:
            raise OperationLeaseLost("巡检已失去执行租约，拒绝写回账号") from exc
        account=record_store.get_row(record_store.ACCOUNTS,account_id,conn=conn,for_update=True)
        if account is None or account.get("email") != expected_email or str(account.get("access_token") or "") != expected_token:
            raise OperationLeaseLost("账号已删除、换绑或 AT 已改变，拒绝巡检旧结果")
        ok=bool(result.get("ok"))
        status=str(result.get("status") or ("live" if ok else "failed"))
        changes={"live_check_status":status,"live_check_ok":ok,"live_checked_at":result.get("checked_at") or now,
                 "live_check_error":None if ok else task_run_log.redact_text(result.get("error") or "查活失败",2000),"updated_at":now}
        if ok and result.get("access_token"):
            token=str(result["access_token"])
            claims=token_claims(token)
            changes.update(access_token=token,token_expires_at=claims.get("token_expires_at"),token_expired=claims.get("token_expired"))
            if isinstance(result.get("session"),dict) and result["session"].get("accessToken"):
                changes["chatgpt_session"]=json.dumps(result["session"],ensure_ascii=False)
        if status == "deactivated":
            changes.update(account_status="deactivated",account_status_reason=changes["live_check_error"],account_status_at=now,
                           codex_status="deactivated",codex_error=changes["live_check_error"])
        for source,target in (("auth_method","last_auth_method"),("password_auth_status","last_password_auth_status"),("fallback_used","last_auth_fallback_used")):
            if source in result:
                changes[target]=result[source]
        record_store.patch_row(record_store.ACCOUNTS,account_id,changes,conn=conn)
    return True


def save_plan(account_id,result,*,fence,expected_email,expected_token):
    from core.storage import accounts
    from core.operations.task_gateway import OperationLeaseLost
    with operation._connect() as conn, conn.cursor() as cur:
        try:
            operation.fence_execution(cur,**fence)
        except (PermissionError,LookupError) as exc:
            raise OperationLeaseLost("巡检套餐结果已失去执行租约") from exc
        account=record_store.get_row(record_store.ACCOUNTS,account_id,conn=conn,for_update=True)
        if account is None or account.get("email") != expected_email or str(account.get("access_token") or "") != expected_token:
            raise OperationLeaseLost("账号快照已变化，拒绝巡检旧套餐结果")
        return accounts.update_account_plan_check(acc_id=account_id,result=result,conn=conn)
