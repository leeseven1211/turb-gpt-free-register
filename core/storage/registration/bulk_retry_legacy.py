"""补齐旧注册链的本地事实，供同一批量重试事务继续使用。"""
from __future__ import annotations

import uuid

from core.storage import postgres, registration
from core.storage.operations import common
from core.storage.registration.bulk_submission import _json


def prepare(cur, plans, *, attempts, projected, batch_ids, run_state) -> None:
    """只补缺少的稳定身份与投影，不重建历史执行或覆盖已关联邮箱。"""
    selected = {}
    for plan in plans:
        selected.setdefault(plan.root_id, plan)
    if not selected:
        return
    facts = [{
        "root": root, "attempt_uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"turb-registration-attempt:{root}")),
        "email": plan.email or "", "email_source": plan.email_source,
        "created_at": plan.root.get("created_at"), "batch_id": plan.batch_id,
        "batch_size": int(plan.batch_size or 1), "workers": plan.workers,
        "batch_uuid": common._uuid("batch", f"registration_batches:{plan.batch_id}"),
        "task_uuid": common._uuid("task", f"registration_chains:{root}:registration"),
        "status": common._status(plan.root.get("status")),
        "config_snapshot": common._scrub(plan.root.get("config_snapshot") or {}),
        "legacy_unlinked": plan.source.get("attempt_id") is None or plan.root.get("attempt_id") is None,
    } for root, plan in selected.items()]
    payload = _json(facts)
    fact_type = """root bigint,attempt_uuid text,email text,email_source text,created_at timestamptz,
        batch_id text,batch_size integer,workers integer,batch_uuid text,task_uuid text,status text,
        config_snapshot jsonb,legacy_unlinked boolean"""
    src = f"jsonb_to_recordset(%s::jsonb) f({fact_type})"
    table = postgres.qualified("registration_attempts")
    cur.execute(f"""INSERT INTO {table}
        (attempt_uuid,source_root_job_id,root_job_id,email_snapshot,email,email_source,data)
        SELECT attempt_uuid,root,root,email,email,email_source,
               jsonb_build_object('legacy_root_job_id',root)
        FROM {src}
        WHERE NOT EXISTS (SELECT 1 FROM {table} a WHERE a.source_root_job_id=f.root OR a.root_job_id=f.root)
        ON CONFLICT (source_root_job_id) DO NOTHING""", (payload,))
    # ensure_attempt_for_job fills additive columns when an unlinked old Job
    # reuses its root Attempt. An already linked Attempt keeps its email identity.
    cur.execute(f"""UPDATE {table} a SET root_job_id=COALESCE(a.root_job_id,f.root),
        email_snapshot=CASE WHEN a.email_snapshot='' THEN f.email ELSE a.email_snapshot END,
        email=COALESCE(NULLIF(a.email,''),f.email),email_source=COALESCE(a.email_source,f.email_source),
        checkpoint=CASE WHEN a.checkpoint IN ('unknown','') THEN 'created' ELSE a.checkpoint END,
        remote_identity_state=CASE WHEN a.remote_identity_state IN ('unknown','') THEN 'not_started'
                                  ELSE a.remote_identity_state END,
        remote_account_state=CASE WHEN a.remote_account_state IN ('unknown','') THEN 'not_started'
                                 ELSE a.remote_account_state END,
        local_account_state=CASE WHEN a.local_account_state IN ('unknown','missing','') THEN 'none'
                                ELSE a.local_account_state END,
        target_status=CASE WHEN a.target_status IN ('unknown','') THEN 'pending' ELSE a.target_status END
        FROM {src} WHERE COALESCE(a.source_root_job_id,a.root_job_id)=f.root AND f.legacy_unlinked""", (payload,))
    cur.execute(f"SELECT * FROM {table} WHERE source_root_job_id=ANY(%s) OR root_job_id=ANY(%s)",
                (list(selected), list(selected)))
    attempts.update({int(row["source_root_job_id"] or row["root_job_id"]): registration._row(row)
                     for row in cur.fetchall()})
    op_attempts = common._table("registration_attempts")
    projection_root = ("COALESCE(a.source_root_job_id,a.root_job_id)" if common._schema_name() == postgres.schema_name()
                       else "a.source_root_job_id")
    if common._schema_name() != postgres.schema_name():
        mirrored = [{**attempts[root], "attempt_uuid": common._uuid("attempt", root), "source_root_job_id": root}
                    for root in selected]
        cur.execute(f"""INSERT INTO {op_attempts}
            (attempt_uuid,source_root_job_id,email_snapshot,account_id,checkpoint,
             remote_identity_state,remote_account_state,local_account_state,target_status,data)
            SELECT attempt_uuid,source_root_job_id,email_snapshot,account_id,checkpoint,
                   remote_identity_state,remote_account_state,local_account_state,target_status,data
            FROM jsonb_to_recordset(%s::jsonb) a(
                attempt_uuid text,source_root_job_id bigint,email_snapshot text,account_id bigint,checkpoint text,
                remote_identity_state text,remote_account_state text,local_account_state text,target_status text,data jsonb)
            ON CONFLICT (source_root_job_id) DO NOTHING""", (_json(mirrored),))
    batches = common._table("operation_batches")
    cur.execute(f"""INSERT INTO {batches}
        (batch_uuid,source_system,source_id,batch_type,title,requested_count,created_by,created_at,data)
        SELECT DISTINCT ON (batch_id) batch_uuid,'registration_batches',batch_id,'registration','注册批次',
               batch_size,'webui',COALESCE(created_at,now()),jsonb_build_object('legacy_batch_id',batch_id,'workers',workers)
        FROM {src} WHERE batch_id IS NOT NULL
        ON CONFLICT (source_system,source_id) DO NOTHING""", (payload,))
    cur.execute(f"""SELECT id,source_id FROM {batches}
        WHERE source_system='registration_batches' AND source_id=ANY(%s)""",
        ([plan.batch_id for plan in selected.values() if plan.batch_id],))
    batch_ids.update({row["source_id"]: row["id"] for row in cur.fetchall()})
    batch_ids[None] = None
    tasks = common._table("operation_tasks")
    cur.execute(f"""INSERT INTO {tasks}
        (task_uuid,source_system,source_id,batch_id,task_type,target_type,target_id,attempt_id,
         account_id,email_snapshot,requested_action,status,target_status,current_stage,trigger,created_at,data)
        SELECT f.task_uuid,'registration_chains',f.root::text || ':registration',b.id,
               'registration','registration_attempt',a.id,a.id,a.account_id,left(f.email,320),
               'registration',f.status,a.target_status,'queued','webui',COALESCE(f.created_at,now()),
               jsonb_build_object('legacy_root_job_id',f.root,'latest_legacy_job_id',f.root,
                                  'config_snapshot',f.config_snapshot)
        FROM {src}
        JOIN {op_attempts} a ON {projection_root}=f.root
        LEFT JOIN {batches} b ON b.source_system='registration_batches' AND b.source_id=f.batch_id
        ON CONFLICT (source_system,source_id) DO NOTHING""", (payload,))
    cur.execute(f"""UPDATE {tasks} t SET root_task_id=t.id
        WHERE source_system='registration_chains' AND root_task_id IS NULL
          AND source_id=ANY(%s)""", ([f"{root}:registration" for root in selected],))
    cur.execute(f"""SELECT a.id,{projection_root} AS source_root_job_id,
                          a.target_status,t.id AS root_task_id
        FROM {op_attempts} a JOIN {tasks} t ON t.attempt_id=a.id
          AND t.source_system='registration_chains'
          AND t.source_id={projection_root}::text || ':registration'
        WHERE {projection_root}=ANY(%s)""", (list(selected),))
    projected.update({row["source_root_job_id"]: row for row in cur.fetchall()})
    for root in selected:
        run_state.setdefault(attempts[root]["id"], {"next_run_no": 1, "active": False})
