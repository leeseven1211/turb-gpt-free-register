"""持久关联注册执行和补密码任务，任务投影可在重启后重新汇总。"""
from __future__ import annotations

import uuid

from core.accounts.password_evidence import password_is_confirmed
from core.operations import task_gateway
from core.storage import records
from core.storage import registration

_SETUP_CONFIG_KEYS = (
    "password_enabled", "password_reset_enabled", "password_driver", "password_proxy_mode",
    "protocol_version", "auth_password_email_fallback", "auth_raw_context_enabled",
    "twofa_driver", "twofa_browser_fallback_enabled", "twofa_protocol_reauth_enabled",
)


def enqueue(*, registration_run_id: int, account: dict, settings: dict, remaining_error: str) -> dict:
    """同一注册 Run 只衔接一次，活动补密码任务可被多个续跑共同等待。"""
    from core.storage.operations import store

    store.init()
    with store._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {registration._table('registration_runs')} WHERE id=%s FOR UPDATE",
                    (int(registration_run_id),))
        source = cur.fetchone()
        if not source:
            raise LookupError("原注册执行不存在")
        source = dict(source)
        data = dict(store._decode(source.get("data")) or {})
        handoff = data.get("completion_handoff")
        if isinstance(handoff, dict) and handoff.get("task_id"):
            return {**handoff, "accepted": True, "reused": True}
        if source["action_type"] != "registration_resume" or source["status"] != "running":
            raise ValueError("原注册续跑已结束，不能创建新的自动补密码任务")
        if source.get("job_id"):
            job = records.get_row(records.JOBS, int(source["job_id"]), conn=conn)
            if not job or job.get("status") in {"stopping", "stopped", "cancelled"}:
                return {"accepted": False, "cancelled": True}
        current = records.get_row(records.ACCOUNTS, int(account["id"]), conn=conn, for_update=True)
        if not current or not current.get("access_token") or password_is_confirmed(current):
            return {"accepted": False, "ready": bool(current and password_is_confirmed(current))}
        cur.execute(
            f"SELECT id,task_id FROM {store._table('operation_runs')} "
            "WHERE source_system='registration_jobs' AND source_id=%s",
            (str(source["job_id"]),),
        )
        parent = cur.fetchone() if source.get("job_id") else None
        cur.execute(
            f"""SELECT r.id AS run_id,t.id AS task_id FROM {store._table('operation_runs')} r
                JOIN {store._table('operation_tasks')} t ON t.id=r.task_id AND t.last_run_id=r.id
                WHERE r.account_id=%s AND t.task_type='password_setup'
                  AND r.status IN ('queued','running','waiting','cancelling','settling')
                ORDER BY r.id LIMIT 1""", (int(account["id"]),),
        )
        active = cur.fetchone()
        if active:
            queued = {"accepted": True, "task_id": int(active["task_id"]),
                      "run_id": int(active["run_id"]), "reused": True}
        else:
            source_id = f"registration-resume-completion:{registration_run_id}"
            queued = task_gateway.submit_durable_operation(
                task_type="password_setup", account_id=int(account["id"]), email=str(account["email"]),
                trigger="registration_resume_completion", source_system="webui_runtime", source_id=source_id,
                parent_task_id=int(parent["task_id"]) if parent else None,
                # 排队身份独立；执行仍申请 openai_interactive 许可及账号租约。
                resource_family="registration_completion",
                data={"steps": ["password"], "completion_auth": True,
                      "registration_completion": True, "registration_run_id": int(registration_run_id),
                      "task_trigger": "registration_resume_completion"},
                config_snapshot=settings, config_allowlist=_SETUP_CONFIG_KEYS, dispatch=False, conn=conn,
            )
            if not queued.get("accepted"):
                raise RuntimeError("自动补密码任务未能持久入队")
        handoff = {
            "task_id": int(queued["task_id"]), "run_id": int(queued["run_id"]),
            "registration_run_id": int(registration_run_id),
            "remaining_error": store._text(remaining_error, 1400),
        }
        cur.execute(f"UPDATE {registration._table('registration_runs')} SET data=data || %s::jsonb WHERE id=%s",
                    (store._json({"completion_handoff": handoff}), int(registration_run_id)))
        if parent:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET data=data || %s::jsonb WHERE id=%s",
                        (store._json({"completion_handoff": handoff}), int(parent["id"])))
        return {**handoff, "accepted": True, "reused": bool(queued.get("reused"))}


def reconcile_parent_registration_job(cur, job_id: int, *, account_id: int | None = None) -> bool:
    """账号配置子任务成功的同一事务内，把父注册任务直接收口为成功。

    不再依赖周期对账：子任务结算时父任务仍停在 partial/failed，且账号实际
    已完整（AT、密码、2FA、套餐），就在这里同步改写，避免状态长期不一致。
    """
    from datetime import datetime, timezone

    from core.accounts.completion import completion_plan

    job = records.get_row(records.JOBS, int(job_id), conn=cur, for_update=True)
    if not job:
        return False
    if str(job.get("status") or "") not in {"partial_success", "failed"}:
        return False
    resolved_account_id = int(account_id or job.get("account_id") or 0)
    if resolved_account_id <= 0:
        return False
    account = records.get_row(records.ACCOUNTS, resolved_account_id, conn=cur)
    if not account or not str(account.get("access_token") or "").strip():
        return False
    if completion_plan(account)["missing_steps"]:
        return False
    records.patch_row(
        records.JOBS, int(job_id),
        {"status": "success", "error_message": "",
         "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        conn=cur,
    )
    return True


def reconcile(cur, parent_run_id: int, *, enqueue_projection: bool = True) -> dict | None:
    """只更新关联代次的投影，不改写原注册认证事实，也不覆盖新的续跑。"""
    from core.storage.operations import common, store

    cur.execute(f"""SELECT r.*,t.last_run_id,t.task_type,t.account_id AS resolved_account_id,
        t.batch_id AS resolved_batch_id FROM {store._table('operation_runs')} r
        JOIN {store._table('operation_tasks')} t ON t.id=r.task_id WHERE r.id=%s""", (int(parent_run_id),))
    parent = cur.fetchone()
    if not parent or parent["task_type"] != "registration_resume" or int(parent["last_run_id"] or 0) != int(parent_run_id):
        return None
    data = dict(store._decode(parent.get("data")) or {})
    handoff = data.get("completion_handoff")
    if not isinstance(handoff, dict) or not handoff.get("task_id"):
        return None
    captured = common.current_settlement_domain() is not None
    job = (
        common._settlement_record(cur, records.JOBS, int(parent["source_id"]))
        if captured else records.get_row(records.JOBS, int(parent["source_id"]), conn=cur.connection)
    )
    if not job or job.get("status") not in {"success", "partial_success"}:
        return None
    # 与兼容投影写入保持 queue→batch→Run→Task 的锁顺序。
    if enqueue_projection and parent.get("resolved_batch_id"):
        store._enqueue_batch_projection_cur(
            cur, int(parent["resolved_batch_id"]), reason="registration_completion",
            source_system="registration_completion", source_id=str(parent_run_id),
        )
    cur.execute(f"SELECT id FROM {store._table('operation_runs')} WHERE id=%s FOR UPDATE", (int(parent_run_id),))
    cur.execute(f"SELECT last_run_id FROM {store._table('operation_tasks')} WHERE id=%s FOR UPDATE",
                (int(parent["task_id"]),))
    locked = cur.fetchone()
    if not locked or int(locked["last_run_id"] or 0) != int(parent_run_id):
        return None
    cur.execute(f"""SELECT t.id,t.task_type,r.id AS run_id,r.status,r.error_category,r.error_code,
        r.error_message,r.result_summary,r.completed_at FROM {store._table('operation_tasks')} t
        JOIN {store._table('operation_runs')} r ON r.id=t.last_run_id WHERE t.id=%s""",
                (int(handoff["task_id"]),))
    child = cur.fetchone()
    if not child:
        return None
    remaining = str(handoff.get("remaining_error") or "")
    account_id = parent.get("resolved_account_id") or parent.get("account_id")
    account = (
        common._settlement_account(cur, int(account_id)) if captured
        else records.get_row(records.ACCOUNTS, int(account_id), conn=cur.connection)
    ) if account_id else None
    waiting = child["status"] in store._ACTIVE_RUN_STATUSES
    complete = child["status"] == "success" and password_is_confirmed(account)
    error = remaining
    if waiting:
        status, message = "waiting", "注册认证已成功，正在自动补密码"
    elif complete:
        status = "partial_success" if remaining else "success"
        message = "自动补密码已完成，其他注册后处理仍待补齐" if remaining else "注册续跑和自动补密码均已完成"
    else:
        status, message = "partial_success", "自动补密码未完成，账号 Token 已保留"
        error = "; ".join(item for item in (
            remaining, child.get("error_message") or "registration_completion_incomplete: 自动补密码未完成",
        ) if item)
    category, code, safe_error = store._error_fields(
        error or None, task_type="registration_resume", task_status=status,
    )
    if not waiting and not complete and child.get("error_code"):
        category, code = child.get("error_category"), child["error_code"]
    summary = dict(store._decode(parent.get("result_summary")) or {})
    summary["completion_handoff"] = {
        **handoff, "run_id": int(child["run_id"]), "status": str(child["status"]), "message": message,
    }
    summary["child_tasks"] = [{
        "task_id": int(child["id"]), "run_id": int(child["run_id"]), "task_type": child["task_type"],
        "status": child["status"], "error_code": child.get("error_code"),
        "error_message": store._text(child.get("error_message") or "", 500),
    }]
    stage = "waiting" if waiting else "complete"
    actions = ([{"action": "await_child", "label": "等待自动补密码"}] if waiting else []
               if status == "success" else [{"action": "retry", "label": "重试未完成步骤"}])
    cur.execute(f"""UPDATE {store._table('operation_runs')} SET status=%s,progress_stage=%s,
        completed_at=CASE WHEN %s THEN NULL ELSE COALESCE(%s,now()) END,
        error_category=%s,error_code=%s,error_message=%s,result_summary=%s::jsonb WHERE id=%s""",
                (status, stage, waiting, child.get("completed_at"), category, code, safe_error,
                 store._json(summary), int(parent_run_id)))
    cur.execute(f"""UPDATE {store._table('operation_tasks')} SET status=%s,current_stage=%s,
        target_status='account_available',completed_at=CASE WHEN %s THEN NULL ELSE COALESCE(%s,now()) END,
        error_category=%s,error_code=%s,error_message=%s,next_actions=%s::jsonb,updated_at=now()
        WHERE id=%s AND last_run_id=%s""",
                (status, stage, waiting, child.get("completed_at"), category, code, safe_error, store._json(actions),
                 int(parent["task_id"]), int(parent_run_id)))
    if str(parent["status"]) != status or parent.get("error_message") != safe_error:
        event_uuid = uuid.uuid5(
            uuid.NAMESPACE_URL, f"registration-completion:{parent_run_id}:{child['run_id']}:{status}",
        ).hex
        cur.execute(f"""INSERT INTO {store._table('operation_events')}
            (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
            VALUES (%s,%s,%s,'registration_completion',%s,%s,%s,'task.completion_updated',%s,%s::jsonb)
            ON CONFLICT DO NOTHING""",
                    (event_uuid, int(parent["task_id"]), int(parent_run_id), event_uuid,
                     "INFO" if waiting or status == "success" else "WARNING", stage, message,
                     store._json({"child_task_id": int(child["id"]), "child_status": str(child["status"])})))
    return {"parent_task_id": int(parent["task_id"]), "status": status}


def reconcile_for_child(cur, child_task_id: int) -> None:
    """子任务重跑或结束后，在同一事务内刷新全部等待它的原续跑。"""
    from core.storage.operations import store

    cur.execute(f"""SELECT id FROM {store._table('operation_runs')}
        WHERE data ? 'completion_handoff' AND data->'completion_handoff'->>'task_id'=%s ORDER BY id""",
                (str(int(child_task_id)),))
    for row in cur.fetchall():
        reconcile(cur, int(row["id"]))
