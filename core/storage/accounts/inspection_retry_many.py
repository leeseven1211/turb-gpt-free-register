"""集合创建任务中心请求的新巡检轮次，保留全局活动轮次的复用顺序。"""
from __future__ import annotations

import json
import uuid

from core.operations import run_log
from core.storage import records
from core.storage.accounts import inspections
from core.storage.operations import common

_CHUNK = 500


def _chunks(rows):
    for offset in range(0, len(rows), _CHUNK):
        yield rows[offset:offset + _CHUNK]


def create_retries_many(conn, specifications: list[dict], *, config_snapshot: dict) -> tuple[dict[int, dict], list[dict]]:
    """调用方拥有事务；不提交、不唤醒调度器，也不执行远端检查。"""
    if not specifications:
        return {}, []
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (common._table("operation_tasks") + ":inspection",))
        cur.execute(f"""SELECT id FROM {common._table('operation_tasks')}
            WHERE task_type=%s AND status=ANY(%s) ORDER BY id DESC LIMIT 1""",
            (inspections.PARENT_TYPE, list(inspections.ACTIVE)))
        active = cur.fetchone()
        if active:
            return {spec["task_id"]: {"id": int(active["id"]), "task_id": int(active["id"]), "created": False}
                    for spec in specifications}, []
        scopes = {spec["archived"] for spec in specifications}
        conditions = []
        if "all" in scopes or {"0", "only"} <= scopes:
            conditions.append("TRUE")
        else:
            conditions.append("archived" if "only" in scopes else "NOT archived")
        cur.execute(f"""SELECT id,email,archived,deactivated,live_check_status,
                data->>'live_check_error' AS original_error
            FROM {records._qualified(records.ACCOUNTS)}
            WHERE {' OR '.join(conditions)} ORDER BY id FOR UPDATE""")
        accounts = list(cur.fetchall())
        cur.execute(f"""SELECT DISTINCT account_id FROM {common._table('operation_runs')}
            WHERE account_id=ANY(%s) AND resource_family='openai_interactive' AND status=ANY(%s)""",
            ([int(row["id"]) for row in accounts], list(inspections.ACTIVE)))
        busy = {int(row["account_id"]) for row in cur.fetchall()}
        by_scope = {"all": accounts, "0": [row for row in accounts if not row["archived"]],
                    "only": [row for row in accounts if row["archived"]]}
        parents, children, replies = [], [], {}
        live_parent = None
        for spec in specifications:
            if live_parent is not None:
                replies[spec["task_id"]] = {"reference": live_parent, "created": False}
                continue
            population = by_scope[spec["archived"]]
            key, task_uuid, run_uuid = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
            parent = {"key": key, "task_uuid": task_uuid, "run_uuid": run_uuid,
                "event_uuid": uuid.uuid4().hex, "cancellation_token": uuid.uuid4().hex,
                "log_file": str(run_log.build_path(task_uuid=task_uuid, run_no=1, run_uuid=run_uuid)),
                "data": {"archived": spec["archived"], "workers": spec["workers"],
                         "total_count": len(population), "submission_key": key},
                "total": len(population), "active": 0, "failed": 0}
            for ordinal, account in enumerate(population, 1):
                account_id = int(account["id"])
                dead = bool(account["deactivated"]) or str(account.get("live_check_status") or "").strip().lower() == "deactivated"
                occupied = account_id in busy
                child_task_uuid, child_run_uuid = uuid.uuid4().hex, uuid.uuid4().hex
                child = {"parent_key": key, "task_uuid": child_task_uuid, "run_uuid": child_run_uuid,
                    "event_uuid": uuid.uuid4().hex, "cancellation_token": uuid.uuid4().hex,
                    "account_id": account_id, "email": account["email"], "ordinal": ordinal,
                    "log_file": str(run_log.build_path(task_uuid=child_task_uuid, run_no=1, run_uuid=child_run_uuid)),
                    "config_snapshot": config_snapshot, "status": "queued", "error_message": None,
                    "result_summary": None}
                if dead or occupied:
                    reason = ("账号已标记为已废，跳过 AT 检查、刷新及套餐查询" if dead
                              else "账号已有排队或运行中的操作，本次未能入队")
                    if dead and account.get("original_error"):
                        reason += "；原因：" + run_log.redact_text(account["original_error"], 1500)
                    child.update(status="success" if dead else "failed",
                        error_message=None if dead else reason,
                        result_summary={"inspection_outcome": "deactivated_skipped" if dead else "rejected",
                                        "checked": False, "invalid": False, "error": reason})
                    parent["failed"] += int(not dead)
                else:
                    parent["active"] += 1
                children.append(child)
            parent["status"] = "waiting" if parent["active"] else "success"
            parents.append(parent)
            replies[spec["task_id"]] = {"reference": key, "created": True}
            if parent["active"]:
                live_parent = key
        _write_parents(cur, parents)
        by_key = {row["key"]: row for row in parents}
        for child in children:
            parent = by_key[child["parent_key"]]
            child.update(batch_id=parent["batch_id"], parent_id=parent["task_id"],
                data=json.loads(common._json({"inspection_id": parent["task_id"],
                    "target_account_id": child["account_id"], "config_snapshot": child["config_snapshot"]})))
        _write_children(cur, children)
        _finish_parents(cur, parents)
        from core.storage.operations.bulk_retry_projection import refresh_batches_many
        refresh_batches_many(cur, [row["batch_id"] for row in parents])
        for reply in replies.values():
            parent_id = by_key[reply.pop("reference")]["task_id"]
            reply.update(id=parent_id, task_id=parent_id)
        logs = [{"log_file": row["log_file"], "task_id": row["task_id"], "run_id": row["run_id"],
                 "stage": stage, "message": message, "event_type": event}
                for rows, stage, message, event in (
                    (parents, "waiting", "任务等待子任务完成", "run.waiting"),
                    (children, "queued", "任务已加入队列", "run.queued"))
                for row in rows]
        return replies, logs


def _write_parents(cur, parents: list[dict]) -> None:
    for chunk in _chunks(parents):
        payload = json.dumps(chunk, ensure_ascii=False)
        cur.execute(f"""INSERT INTO {common._table('operation_batches')}
            (batch_uuid,source_system,source_id,batch_type,title,status,requested_count,created_by,data)
            SELECT key,'native_operations',key,'account_inspection_batch','账号巡检','queued',total,'inspection',data
            FROM jsonb_to_recordset(%s::jsonb) s(key TEXT,total INTEGER,data JSONB)
            RETURNING id,batch_uuid""", (payload,))
        batches = {row["batch_uuid"]: int(row["id"]) for row in cur.fetchall()}
        for parent in chunk:
            parent["batch_id"] = batches[parent["key"]]
        cur.execute(f"""INSERT INTO {common._table('operation_tasks')}
            (task_uuid,source_system,source_id,batch_id,task_type,target_type,requested_action,
             status,target_status,current_stage,trigger,data)
            SELECT task_uuid,'native_operations',task_uuid,batch_id,'account_inspection_batch','account',
                'account_inspection_batch','waiting','pending','waiting','inspection',data
            FROM jsonb_to_recordset(%s::jsonb) s(task_uuid TEXT,batch_id BIGINT,data JSONB)
            RETURNING id,task_uuid""", (json.dumps(chunk, ensure_ascii=False),))
        tasks = {row["task_uuid"]: int(row["id"]) for row in cur.fetchall()}
        for parent in chunk:
            parent["task_id"] = tasks[parent["task_uuid"]]
        cur.execute(f"""INSERT INTO {common._table('operation_runs')}
            (run_uuid,task_id,run_no,source_system,source_id,status,batch_id,account_id,
             resource_family,cancellation_token,log_file,data)
            SELECT run_uuid,task_id,1,'native_operations',run_uuid,'waiting',batch_id,NULL,
                'inspection_coordinator',cancellation_token,log_file,data
            FROM jsonb_to_recordset(%s::jsonb) s(run_uuid TEXT,task_id BIGINT,batch_id BIGINT,
                cancellation_token TEXT,log_file TEXT,data JSONB) RETURNING id,task_id""",
            (json.dumps(chunk, ensure_ascii=False),))
        runs = {int(row["task_id"]): int(row["id"]) for row in cur.fetchall()}
        for parent in chunk:
            parent["run_id"] = runs[parent["task_id"]]
        payload = json.dumps(chunk, ensure_ascii=False)
        cur.execute(f"""UPDATE {common._table('operation_tasks')} t
            SET root_task_id=s.task_id,last_run_id=s.run_id
            FROM jsonb_to_recordset(%s::jsonb) s(task_id BIGINT,run_id BIGINT) WHERE t.id=s.task_id""",
            (payload,))
        cur.execute(f"""INSERT INTO {common._table('operation_events')}
            (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
            SELECT event_uuid,task_id,run_id,'native_operations',event_uuid,'INFO','waiting',
                'run.waiting','任务等待子任务完成','{{}}'::jsonb
            FROM jsonb_to_recordset(%s::jsonb) s(event_uuid TEXT,task_id BIGINT,run_id BIGINT)""", (payload,))


def _write_children(cur, children: list[dict]) -> None:
    for chunk in _chunks(children):
        payload = json.dumps(chunk, ensure_ascii=False)
        cur.execute(f"""INSERT INTO {common._table('operation_tasks')}
            (task_uuid,source_system,source_id,batch_id,parent_task_id,root_task_id,task_type,
             target_type,target_id,account_id,email_snapshot,requested_action,status,target_status,current_stage,trigger,data)
            SELECT task_uuid,'native_operations',task_uuid,batch_id,parent_id,parent_id,'account_inspection',
                'account',account_id,account_id,email,'account_inspection','queued','pending','queued','inspection',data
            FROM jsonb_to_recordset(%s::jsonb) s(task_uuid TEXT,batch_id BIGINT,parent_id BIGINT,
                account_id BIGINT,email TEXT,data JSONB) RETURNING id,task_uuid""", (payload,))
        tasks = {row["task_uuid"]: int(row["id"]) for row in cur.fetchall()}
        for child in chunk:
            child["task_id"] = tasks[child["task_uuid"]]
        cur.execute(f"""INSERT INTO {common._table('operation_runs')}
            (run_uuid,task_id,run_no,source_system,source_id,status,batch_id,account_id,
             resource_family,cancellation_token,log_file,data)
            SELECT run_uuid,task_id,1,'native_operations',run_uuid,
                CASE WHEN status='queued' THEN 'queued' ELSE status END,batch_id,account_id,
                'openai_interactive',cancellation_token,log_file,data
            FROM jsonb_to_recordset(%s::jsonb) s(run_uuid TEXT,task_id BIGINT,status TEXT,batch_id BIGINT,
                account_id BIGINT,cancellation_token TEXT,log_file TEXT,data JSONB) RETURNING id,task_id""",
            (json.dumps(chunk, ensure_ascii=False),))
        runs = {int(row["task_id"]): int(row["id"]) for row in cur.fetchall()}
        for child in chunk:
            child["run_id"] = runs[child["task_id"]]
        payload = json.dumps(chunk, ensure_ascii=False)
        cur.execute(f"""UPDATE {common._table('operation_tasks')} t
            SET last_run_id=s.run_id,status=s.status,error_message=s.error_message,
                completed_at=CASE WHEN s.status='queued' THEN NULL ELSE now() END
            FROM jsonb_to_recordset(%s::jsonb) s(task_id BIGINT,run_id BIGINT,status TEXT,error_message TEXT)
            WHERE t.id=s.task_id""", (payload,))
        cur.execute(f"""UPDATE {common._table('operation_runs')} r
            SET completed_at=CASE WHEN s.status='queued' THEN NULL ELSE now() END,
                result_summary=s.result_summary,error_message=s.error_message
            FROM jsonb_to_recordset(%s::jsonb) s(run_id BIGINT,status TEXT,result_summary JSONB,error_message TEXT)
            WHERE r.id=s.run_id""", (payload,))
        cur.execute(f"""INSERT INTO {common._table('operation_batch_items')} (batch_id,task_id,run_id,ordinal)
            SELECT batch_id,task_id,run_id,ordinal FROM jsonb_to_recordset(%s::jsonb)
            s(batch_id BIGINT,task_id BIGINT,run_id BIGINT,ordinal INTEGER)""", (payload,))
        cur.execute(f"""INSERT INTO {common._table('operation_events')}
            (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
            SELECT event_uuid,task_id,run_id,'native_operations',event_uuid,'INFO','queued',
                'run.queued','任务已加入队列','{{}}'::jsonb
            FROM jsonb_to_recordset(%s::jsonb) s(event_uuid TEXT,task_id BIGINT,run_id BIGINT)""", (payload,))


def _finish_parents(cur, parents: list[dict]) -> None:
    for chunk in _chunks(parents):
        for parent in chunk:
            parent["summary"] = {"child_count": parent["total"], "processed_count": parent["total"] - parent["active"],
                                 "failed_count": parent["failed"]}
        payload = json.dumps(chunk, ensure_ascii=False)
        cur.execute(f"""UPDATE {common._table('operation_tasks')} t
            SET status=s.status,
                target_status=CASE WHEN s.total=0 THEN t.target_status WHEN s.active>0 THEN 'pending' ELSE 'completed' END,
                current_stage=CASE WHEN s.total=0 THEN t.current_stage WHEN s.active>0 THEN 'waiting' ELSE 'complete' END,
                next_actions=CASE WHEN s.total=0 THEN t.next_actions WHEN s.active>0
                    THEN '[{{"action":"cancel","label":"停止巡检"}}]'::jsonb
                    ELSE '[{{"action":"retry","label":"再次巡检"}}]'::jsonb END,
                completed_at=CASE WHEN s.active>0 THEN NULL ELSE now() END,updated_at=now()
            FROM jsonb_to_recordset(%s::jsonb) s(task_id BIGINT,status TEXT,total INTEGER,active INTEGER)
            WHERE t.id=s.task_id""", (payload,))
        cur.execute(f"""UPDATE {common._table('operation_runs')} r
            SET status=s.status,
                progress_stage=CASE WHEN s.total=0 THEN r.progress_stage WHEN s.active>0 THEN 'waiting' ELSE 'complete' END,
                heartbeat_at=CASE WHEN s.total=0 THEN r.heartbeat_at ELSE now() END,
                completed_at=CASE WHEN s.active>0 THEN NULL ELSE now() END,
                result_summary=CASE WHEN s.total=0 THEN r.result_summary ELSE s.summary END
            FROM jsonb_to_recordset(%s::jsonb) s(run_id BIGINT,status TEXT,total INTEGER,active INTEGER,summary JSONB)
            WHERE r.id=s.run_id""", (payload,))
        terminal = [row for row in chunk if row["total"] and not row["active"]]
        if terminal:
            for row in terminal:
                row["reconciled_uuid"] = uuid.uuid4().hex
            cur.execute(f"""INSERT INTO {common._table('operation_events')}
                (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
                SELECT reconciled_uuid,task_id,run_id,'native_operations',reconciled_uuid,'INFO','complete',
                    'inspection.reconciled','本轮巡检处理完成，阶段结果见巡检历史',summary
                FROM jsonb_to_recordset(%s::jsonb) s(reconciled_uuid TEXT,task_id BIGINT,run_id BIGINT,summary JSONB)""",
                (json.dumps(terminal, ensure_ascii=False),))
