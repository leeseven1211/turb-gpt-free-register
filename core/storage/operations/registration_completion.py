"""持久关联注册执行和补密码任务，任务投影可在重启后重新汇总。"""
from __future__ import annotations

import json
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


def _completion_requirements(job: dict) -> dict[str, bool]:
    """读取旧注册 Job 自己冻结的补全要求，不受当前全局开关影响。"""
    data = job.get("data")
    data = data if isinstance(data, dict) else {}
    snapshot = job.get("config_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = data.get("config_snapshot")
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    steps = job.get("progress_steps")
    if not isinstance(steps, dict):
        steps = data.get("progress_steps")
    steps = steps if isinstance(steps, dict) else {}
    requirements: dict[str, bool] = {}
    for key, step in (
        ("password_enabled", "password"),
        ("plan_check_enabled", "plan_check"),
        ("twofa_enabled", "twofa"),
        ("codex_enabled", "codex"),
    ):
        if key in snapshot:
            requirements[key] = bool(snapshot[key])
        else:
            detail = steps.get(step)
            requirements[key] = not (
                isinstance(detail, dict) and str(detail.get("state") or "").strip().lower() == "skipped"
            )
    return requirements


def _account_matches_registration_requirements(account: dict, requirements: dict[str, bool]) -> bool:
    """只按当前账号事实判断收口，旧 Job 的失败步骤仅作为历史证据。"""
    if not str(account.get("access_token") or "").strip():
        return False
    if requirements.get("password_enabled", True) and not password_is_confirmed(account):
        return False
    if requirements.get("plan_check_enabled", True) and str(account.get("plan_check_status") or "").strip().lower() != "success":
        return False
    if requirements.get("twofa_enabled", True):
        if not str(account.get("totp_secret") or "").strip():
            return False
        extra = account.get("extra_json")
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except (TypeError, ValueError, json.JSONDecodeError):
                extra = {}
        if isinstance(extra, dict) and extra.get("totp_setup_pending"):
            return False
    return not requirements.get("codex_enabled", True) or str(account.get("codex_status") or "").strip().lower() == "success"


def reconcile_parent_registration_job(cur, job_id: int, *, account_id: int | None = None) -> bool:
    """账号配置子任务成功的同一事务内，把父注册任务直接收口为成功。

    不再依赖周期对账：子任务结算时父任务仍停在 partial/failed，且账号实际
    已完整（AT、密码、2FA、套餐），就在这里同步改写，避免状态长期不一致。
    """
    from datetime import datetime, timezone
    from core.storage.operations import common

    captured = common.current_settlement_domain() is not None
    job = (
        common._settlement_record(cur, records.JOBS, int(job_id), for_update=True)
        if captured else records.get_row(records.JOBS, int(job_id), conn=cur.connection, for_update=True)
    )
    if not job:
        return False
    if str(job.get("status") or "") not in {"partial_success", "failed"}:
        return False
    job_account_id = int(job.get("account_id") or 0)
    if account_id is not None and job_account_id > 0 and int(account_id) != job_account_id:
        return False
    resolved_account_id = int(account_id or job.get("account_id") or 0)
    if resolved_account_id <= 0:
        return False
    account = (
        common._settlement_account(cur, resolved_account_id)
        if captured else records.get_row(records.ACCOUNTS, resolved_account_id, conn=cur.connection)
    )
    if not account:
        return False
    if not _account_matches_registration_requirements(account, _completion_requirements(job)):
        return False
    completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changes = {"status": "success", "error_message": "", "completed_at": completed_at}
    if captured:
        # 捕获结算域已完成初始化，只使用当前事务，避免就绪缓存漂移后另借连接。
        cur.execute(
            f"""UPDATE {registration._table('registration_jobs')}
                   SET status='success', updated_at=%s, data=data || %s::jsonb WHERE id=%s""",
            (completed_at, common._json({"error_message": "", "completed_at": completed_at}), int(job_id)),
        )
    else:
        records.patch_row(records.JOBS, int(job_id), changes, conn=cur.connection)
    return True


def reconcile_parent_registration_job_for_child(
    cur, child_task_id: int, *, child_run_id: int | None = None,
) -> bool:
    """同步成功补跑的原 Job、当前父任务和批次；锁争用留给周期重试。"""
    from core.storage.operations import projection, store

    child_query = f"""SELECT child.id AS child_task_id, child.last_run_id AS child_last_run_id,
                   child.parent_task_id, child.account_id AS child_account_id, child.data AS child_data,
                   child_run.id AS child_run_id, child_run.status AS child_run_status,
                   child_run.completed_at AS child_completed_at
              FROM {store._table('operation_tasks')} child
              JOIN {store._table('operation_runs')} child_run ON child_run.id=child.last_run_id
             WHERE child.id=%s"""
    cur.execute(child_query, (int(child_task_id),))
    relation = cur.fetchone()
    if not relation or str(relation.get("child_run_status") or "") != "success":
        return False
    if child_run_id is not None and int(relation["child_run_id"]) != int(child_run_id):
        return False

    data = relation.get("child_data")
    data = data if isinstance(data, dict) else {}
    explicit_job_id = data.get("source_job_id")
    registration_run_id = data.get("registration_run_id")
    if explicit_job_id is None and registration_run_id:
        try:
            registration_run_id = int(registration_run_id)
        except (TypeError, ValueError):
            return False
        cur.execute(
            f"SELECT job_id FROM {registration._table('registration_runs')} WHERE id=%s",
            (registration_run_id,),
        )
        registration_run = cur.fetchone()
        explicit_job_id = registration_run.get("job_id") if registration_run else None

    try:
        job_id = int(explicit_job_id or 0)
    except (TypeError, ValueError):
        return False
    if job_id <= 0:
        return False

    # 注册 Run 结束后，父 Task 可能切到 registration_chains 的协调 Run。
    # 只按同一父 Task 上最新的 registration_jobs Run 解析原 Job，
    # 既保留代次 fence，也不会把协调 Run 错当成新注册执行。
    parent_query = f"""SELECT registration_run.id AS registration_run_id,
                   registration_run.task_id AS parent_task_id,
                   parent.last_run_id AS parent_last_run_id,
                   parent.batch_id AS parent_batch_id, parent.status AS parent_status,
                   current_run.id AS current_parent_run_id,
                   current_run.status AS current_parent_run_status
              FROM {store._table('operation_runs')} registration_run
              JOIN {store._table('operation_tasks')} parent
                ON parent.id=registration_run.task_id
              JOIN {store._table('operation_runs')} current_run
                ON current_run.id=parent.last_run_id
             WHERE registration_run.source_system='registration_jobs'
               AND registration_run.source_id=%s
               AND NOT EXISTS (
                   SELECT 1
                     FROM {store._table('operation_runs')} newer
                    WHERE newer.task_id=registration_run.task_id
                      AND newer.source_system='registration_jobs'
                      AND newer.id > registration_run.id
               )
             ORDER BY registration_run.id DESC
             LIMIT 1"""
    cur.execute(parent_query, (str(job_id),))
    parent = cur.fetchone()
    if not parent or not parent.get("current_parent_run_id"):
        return False
    if relation.get("parent_task_id") and int(relation["parent_task_id"]) != int(parent["parent_task_id"]):
        return False
    allowed_statuses = {"success", "partial_success", "failed", "interrupted", "attention_required"}
    if parent["current_parent_run_status"] not in allowed_statuses:
        return False
    if parent["parent_status"] not in allowed_statuses:
        return False

    # 业务重跑按 batch→父 Run/Task→Job→child 加锁。结算调用已持有 child，
    # 此处只尝试取锁，避免反向等待；失败时不写任何状态，周期会再次对账。
    batch_id = parent.get("parent_batch_id")
    if batch_id is not None:
        cur.execute("SELECT pg_try_advisory_xact_lock(%s) AS acquired", (int(batch_id),))
        if not cur.fetchone()["acquired"]:
            return False
        cur.execute(
            f"SELECT id FROM {store._table('operation_batches')} WHERE id=%s "
            "FOR NO KEY UPDATE SKIP LOCKED",
            (int(batch_id),),
        )
        if not cur.fetchone():
            return False

    cur.execute(child_query + " FOR UPDATE OF child, child_run SKIP LOCKED", (int(child_task_id),))
    locked_child = cur.fetchone()
    if not locked_child or locked_child != relation:
        return False
    cur.execute(
        parent_query + " FOR UPDATE OF parent, current_run, registration_run SKIP LOCKED",
        (str(job_id),),
    )
    locked_parent = cur.fetchone()
    if not locked_parent or locked_parent != parent:
        return False
    cur.execute(
        f"SELECT id FROM {registration._table('registration_jobs')} WHERE id=%s "
        "FOR UPDATE SKIP LOCKED",
        (job_id,),
    )
    if not cur.fetchone():
        return False
    if not reconcile_parent_registration_job(
        cur, job_id, account_id=relation.get("child_account_id"),
    ):
        return False

    evidence = {"registration_followup_completed": {
        "source_job_id": job_id, "child_task_id": int(child_task_id),
        "child_run_id": int(relation["child_run_id"]),
    }}
    cur.execute(
        f"""UPDATE {store._table('operation_runs')}
               SET status='success', progress_stage='complete',
                   error_category=NULL, error_code=NULL, error_message=NULL,
                   completed_at=COALESCE(completed_at,%s,now()),
                   result_summary=result_summary || %s::jsonb
             WHERE id=%s""",
        (relation.get("child_completed_at"), store._json(evidence), int(parent["current_parent_run_id"])),
    )
    cur.execute(
        f"""UPDATE {store._table('operation_tasks')}
               SET status='success', target_status='account_available', current_stage='complete',
                   error_category=NULL, error_code=NULL, error_message=NULL,
                   next_actions='[]'::jsonb, completed_at=COALESCE(completed_at,%s,now()),
                   updated_at=now()
             WHERE id=%s AND last_run_id=%s""",
        (relation.get("child_completed_at"), int(parent["parent_task_id"]), int(parent["current_parent_run_id"])),
    )
    if batch_id is not None:
        projection._refresh_batches(cur, [int(batch_id)])
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
    cur.execute(f"SELECT last_run_id,status FROM {store._table('operation_tasks')} WHERE id=%s FOR UPDATE",
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
    if child["status"] not in store._ACTIVE_RUN_STATUSES and locked.get("status") in {"cancelled", "stopped"}:
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
