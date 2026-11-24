"""共享普通 native Task/Run 集合提交原语。

调用方负责集合预检、账号锁和业务状态投影；本模块只在同一连接中创建
Task、Run、初始 queued event 与可选 batch item，不触发外部服务。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import uuid

from core.operations import run_log
from core.storage.operations import common
from core.storage.operations import schema
from psycopg.rows import dict_row


def create_specs(specifications: Sequence[Mapping], *, conn) -> list[dict]:
    """集合创建普通 durable Task/Run/Event，按输入顺序返回受理回执。"""
    if not specifications:
        return []
    schema.init_operation_schema()
    rows = []
    for index, raw in enumerate(specifications, 1):
        spec = dict(raw)
        task_type = str(spec.get("task_type") or "").strip()
        source_system = str(spec.get("source_system") or "native_operations").strip() or "native_operations"
        source_id = str(spec.get("source_id") or "").strip() or uuid.uuid4().hex
        account_id = spec.get("account_id")
        account_id = int(account_id) if account_id is not None else None
        task_uuid, run_uuid = uuid.uuid4().hex, uuid.uuid4().hex
        rows.append({
            **spec,
            "task_type": task_type,
            "source_system": source_system,
            "source_id": source_id,
            "account_id": account_id,
            "email": str(spec.get("email") or "").strip(),
            "trigger": str(spec.get("trigger") or "manual_bulk"),
            "resource_family": str(spec.get("resource_family") or "openai_interactive"),
            "task_uuid": task_uuid,
            "run_uuid": run_uuid,
            "cancellation_token": uuid.uuid4().hex,
            "event_uuid": uuid.uuid4().hex,
            "batch_id": int(spec["batch_id"]) if spec.get("batch_id") is not None else None,
            "batch_ordinal": int(spec.get("batch_ordinal") or index),
            "log_file": str(run_log.build_path(task_uuid=task_uuid, run_no=1, run_uuid=run_uuid)),
            "data": common._scrub(dict(spec.get("data") or {})),
        })
    with conn.cursor(row_factory=dict_row) as cur:
        payload = json.dumps(rows, ensure_ascii=False)
        cur.execute(
            f"""SELECT t.id AS task_id,t.source_system,t.source_id,t.account_id,t.task_type,
                       t.last_run_id AS run_id,r.status
                FROM {common._table('operation_tasks')} t
                LEFT JOIN {common._table('operation_runs')} r ON r.id=t.last_run_id
                WHERE (t.source_system,t.source_id) IN (
                    SELECT source_system,source_id
                    FROM jsonb_to_recordset(%s::jsonb) AS s(source_system TEXT,source_id TEXT)
                )""",
            (payload,),
        )
        existing = {(row["source_system"], row["source_id"]): dict(row) for row in cur.fetchall()}
        fresh = [row for row in rows if (row["source_system"], row["source_id"]) not in existing]
        if fresh:
            fresh_payload = json.dumps(fresh, ensure_ascii=False)
            cur.execute(
                f"""INSERT INTO {common._table('operation_tasks')}
                    (task_uuid,source_system,source_id,batch_id,task_type,target_type,target_id,
                     account_id,email_snapshot,requested_action,status,target_status,current_stage,
                     next_actions,trigger,data)
                    SELECT s.task_uuid,s.source_system,s.source_id,s.batch_id,s.task_type,'account',
                           s.account_id,s.account_id,s.email,s.task_type,'queued','pending','queued',
                           '[]'::jsonb,s.trigger,s.data
                    FROM jsonb_to_recordset(%s::jsonb) AS s(
                        task_uuid TEXT,source_system TEXT,source_id TEXT,batch_id BIGINT,
                        task_type TEXT,account_id BIGINT,email TEXT,trigger TEXT,data JSONB)
                    RETURNING id,task_uuid,source_system,source_id""",
                (fresh_payload,),
            )
            task_by_uuid = {row["task_uuid"]: dict(row) for row in cur.fetchall()}
            for row in fresh:
                row["task_id"] = int(task_by_uuid[row["task_uuid"]]["id"])
            fresh_payload = json.dumps(fresh, ensure_ascii=False)
            cur.execute(
                f"""INSERT INTO {common._table('operation_runs')}
                    (run_uuid,task_id,run_no,source_system,source_id,status,batch_id,account_id,
                     resource_family,cancellation_token,log_file,data)
                    SELECT s.run_uuid,s.task_id,1,s.source_system,s.run_uuid,'queued',s.batch_id,
                           s.account_id,s.resource_family,s.cancellation_token,s.log_file,s.data
                    FROM jsonb_to_recordset(%s::jsonb) AS s(
                        run_uuid TEXT,task_id BIGINT,batch_id BIGINT,source_system TEXT,
                        account_id BIGINT,resource_family TEXT,cancellation_token TEXT,
                        log_file TEXT,data JSONB)
                    RETURNING id,task_id""",
                (fresh_payload,),
            )
            run_by_task = {int(row["task_id"]): int(row["id"]) for row in cur.fetchall()}
            for row in fresh:
                row["run_id"] = run_by_task[row["task_id"]]
            cur.execute(
                f"""UPDATE {common._table('operation_tasks')} t
                    SET root_task_id=t.id,last_run_id=s.run_id
                    FROM jsonb_to_recordset(%s::jsonb) AS s(task_id BIGINT,run_id BIGINT)
                    WHERE t.id=s.task_id""",
                (json.dumps([{"task_id": row["task_id"], "run_id": row["run_id"]} for row in fresh]),),
            )
            cur.execute(
                f"""INSERT INTO {common._table('operation_events')}
                    (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
                    SELECT s.event_uuid,s.task_id,s.run_id,s.source_system,s.event_uuid,'INFO','queued',
                           'run.queued','任务已加入队列','{{}}'::jsonb
                    FROM jsonb_to_recordset(%s::jsonb) AS s(
                        event_uuid TEXT,task_id BIGINT,run_id BIGINT,source_system TEXT)""",
                (json.dumps(fresh, ensure_ascii=False),),
            )
        fresh_by_identity = {(row["source_system"], row["source_id"]): row for row in fresh}
        batch_rows = [
            row for row in rows
            if row.get("batch_id") is not None
            and (row["source_system"], row["source_id"]) in fresh_by_identity
        ]
        if batch_rows:
            cur.execute(
                f"""INSERT INTO {common._table('operation_batch_items')}(batch_id,task_id,run_id,ordinal)
                    SELECT s.batch_id,s.task_id,s.run_id,s.ordinal
                    FROM jsonb_to_recordset(%s::jsonb) AS s(
                        batch_id BIGINT,task_id BIGINT,run_id BIGINT,ordinal INTEGER)
                    ON CONFLICT DO NOTHING""",
                (json.dumps([
                    {"batch_id": row["batch_id"], "task_id": fresh_by_identity[(row["source_system"], row["source_id"])]["task_id"],
                     "run_id": fresh_by_identity[(row["source_system"], row["source_id"])]["run_id"],
                     "ordinal": row["batch_ordinal"]}
                    for row in batch_rows
                ]),),
            )
        result = []
        for row in rows:
            prior = existing.get((row["source_system"], row["source_id"]))
            owned = prior or fresh_by_identity[(row["source_system"], row["source_id"])]
            result.append({
                "accepted": True,
                "reused": bool(prior),
                "busy": False,
                "task_id": int(owned["task_id"]),
                "run_id": int(owned["run_id"]),
                "status": str(owned.get("status") or "queued"),
                "account_id": row["account_id"],
                "email": row["email"],
                "source_system": row["source_system"],
                "source_id": row["source_id"],
                "trigger": row["trigger"],
            })
        return result


__all__ = ["create_specs"]
