"""重试子任务后集合收口父任务；保留每次父执行的审计边界。"""
from __future__ import annotations

from collections import defaultdict
import json
import uuid

from core.operations import run_log
from core.storage.operations import common

_CHUNK = 500


def _mapping(value) -> dict:
    decoded = common._decode(value)
    return dict(decoded) if isinstance(decoded, dict) else {}


def _ordinary_state(children: list[dict]) -> dict:
    if any(str(child.get("status") or "") in common._ACTIVE_RUN_STATUSES for child in children):
        return {"status": "waiting", "stage": "waiting", "target_status": "pending",
            "actions": [{"action": "await_child", "label": "等待子任务完成"}],
            "event_type": "task.waiting_for_child", "message": "父任务等待子任务完成，未占用账号操作租约", "level": "INFO"}
    statuses = {str(child.get("status") or "") for child in children}
    if statuses and statuses <= {"success"}:
        status, target, actions, message, level = (
            "success", "completed", [], "所有子任务已完成，父任务自动收口", "INFO")
    elif "deactivated" in statuses:
        status, target, actions, message, level = (
            "deactivated", "account_deactivated", [], "子任务已确认废号，父任务停止重跑", "WARNING")
    elif "attention_required" in statuses or any(
        str(child.get("status") or "") == "failed"
        and str(child.get("task_type") or "") in {"token_refresh", "live_check"}
        and (summary := _mapping(child.get("result_summary"))).get("outcome") == "request_unknown"
        and summary.get("cause_code") in {"password_change_required", "password_page_error"}
        for child in children
    ):
        status, target, actions, message, level = (
            "attention_required", "attention_required", [{"action": "reconcile", "label": "确认远端结果后继续"}],
            "子任务需要确认，父任务保留待对账状态", "WARNING")
    else:
        status, target, actions, message, level = (
            "partial_success", "attention_required", [{"action": "retry", "label": "重试失败子任务"}],
            "子任务已结束，父任务保留部分成功结果", "WARNING")
    return {"status": status, "stage": "complete", "target_status": target, "actions": actions,
        "event_type": "task.children_reconciled", "message": message, "level": level}


def _child_summary(children: list[dict]) -> dict:
    summaries = []
    for child in children:
        summary, data = _mapping(child.get("result_summary")), _mapping(child.get("data"))
        summaries.append({"task_id": int(child["id"]), "run_id": child.get("last_run_id"),
            "task_type": child.get("task_type"), "status": child.get("status"),
            "failure_stage": summary.get("failure_stage") or data.get("failure_stage"),
            "failure_event_id": summary.get("failure_event_id") or data.get("failure_event_id"),
            "error_code": child.get("error_code") or summary.get("error_code") or data.get("error_code"),
            "error_message": run_log.redact_text(child.get("error_message")
                or summary.get("error_message") or data.get("failure_message") or "", 500)})
    return {"children": {str(child["id"]): str(child.get("status") or "") for child in children},
            "child_tasks": summaries}


def _inspection_state(parent: dict, children: list[dict]) -> dict:
    active = sum(str(child.get("status") or "") in common._ACTIVE_RUN_STATUSES for child in children)
    failed = sum(str(child.get("status") or "") != "success"
                 and str(child.get("status") or "") not in common._ACTIVE_RUN_STATUSES for child in children)
    waiting = active > 0
    return {"status": "waiting" if waiting else "success", "stage": "waiting" if waiting else "complete",
        "target_status": "pending" if waiting else "completed",
        "actions": [{"action": "cancel", "label": "停止巡检"}] if waiting else [{"action": "retry", "label": "再次巡检"}],
        "summary": {"child_count": len(children), "processed_count": len(children) - active, "failed_count": failed},
        "event_type": "inspection.reconciled", "level": "INFO",
        "message": "等待本轮巡检子任务" if waiting else "本轮巡检处理完成，阶段结果见巡检历史",
        "emit": str(parent.get("status") or "") != ("waiting" if waiting else "success")}


def reconcile_parents_many(cur, parent_task_ids: list[int], *, child_task_ids=()) -> dict:
    """调用者同事务已更新子 Task/Run；返回批次及应交注册收口的父 Run。

    注册链先只读分流，由注册 helper 取得 queue→batch→Run→Task 锁。
    普通父任务按旧单项路径的 Run→Task 顺序集合锁定，并复核 last_run_id；
    不在这里提交、刷新批次或执行远端动作。SQL 每块最多接受 500 个父目标。
    """
    ids = sorted({int(value) for value in parent_task_ids if value})
    children = {int(value) for value in child_task_ids if value}
    batches, registrations = set(), set()
    for offset in range(0, len(ids), _CHUNK):
        result = _reconcile_chunk(cur, ids[offset:offset + _CHUNK], children)
        batches.update(result["batch_ids"])
        registrations.update(result["registration_run_ids"])
    return {"batch_ids": batches, "registration_run_ids": registrations}


def _reconcile_chunk(cur, ids: list[int], retried_children: set[int]) -> dict:
    cur.execute(f"""SELECT t.*,r.data AS observed_run_data FROM {common._table('operation_tasks')} t
        LEFT JOIN {common._table('operation_runs')} r ON r.id=t.last_run_id
        WHERE t.id=ANY(%s) ORDER BY t.id""", (ids,))
    observed = {int(row["id"]): dict(row) for row in cur.fetchall()}
    registration_parents = {task_id for task_id, task in observed.items()
                            if task["source_system"] == "registration_chains"}
    automatic = set()
    if registration_parents and retried_children:
        cur.execute(f"""SELECT id,parent_task_id FROM {common._table('operation_tasks')}
            WHERE parent_task_id=ANY(%s) AND data->>'registration_completion'='true'""",
            (sorted(registration_parents),))
        automatic = {int(row["parent_task_id"]) for row in cur.fetchall() if int(row["id"]) in retried_children}
    registration_runs = set()
    for task_id in registration_parents:
        parent = observed[task_id]
        if task_id in automatic or _mapping(parent.get("observed_run_data")).get("completion_handoff"):
            if parent.get("last_run_id"):
                registration_runs.add(int(parent["last_run_id"]))
            del observed[task_id]
    if not observed:
        return {"batch_ids": set(), "registration_run_ids": registration_runs}
    run_ids = sorted({int(task["last_run_id"]) for task in observed.values() if task.get("last_run_id")})
    cur.execute(f"""SELECT * FROM {common._table('operation_runs')}
        WHERE id=ANY(%s) ORDER BY id FOR UPDATE""", (run_ids,))
    runs = {int(row["id"]): dict(row) for row in cur.fetchall()}
    cur.execute(f"""SELECT * FROM {common._table('operation_tasks')}
        WHERE id=ANY(%s) ORDER BY id FOR UPDATE""", (sorted(observed),))
    parents = {int(row["id"]): dict(row) for row in cur.fetchall()
               if int(row.get("last_run_id") or 0) == int(observed[int(row["id"])].get("last_run_id") or 0)}
    if not parents:
        return {"batch_ids": set(), "registration_run_ids": registration_runs}
    cur.execute(f"""SELECT t.id,t.parent_task_id,t.status,t.task_type,t.last_run_id,
            r.result_summary,r.error_message,r.error_code,r.data
        FROM {common._table('operation_tasks')} t
        LEFT JOIN {common._table('operation_runs')} r ON r.id=t.last_run_id
        WHERE t.parent_task_id=ANY(%s) ORDER BY t.id""", (sorted(parents),))
    grouped = defaultdict(list)
    for row in cur.fetchall():
        grouped[int(row["parent_task_id"])].append(dict(row))
    changes, reopen = [], []
    batches = set()
    for task_id, parent in parents.items():
        children = grouped[task_id]
        if not children:
            continue
        inspection = parent["task_type"] == "account_inspection_batch"
        state = _inspection_state(parent, children) if inspection else _ordinary_state(children)
        run = runs.get(int(parent.get("last_run_id") or 0))
        waiting = state["status"] == "waiting"
        replacement = bool(run and waiting and (
            run["status"] not in common._ACTIVE_RUN_STATUSES if inspection
            else run["status"] in common._TERMINAL_STATUSES))
        write_run = bool(run and (inspection or replacement or run["status"] not in common._TERMINAL_STATUSES))
        summary = _mapping(run.get("result_summary")) if run and not replacement and not inspection else {}
        summary.update(state["summary"] if inspection else _child_summary(children))
        change = {"task_id": task_id, "run_id": int(run["id"]) if run else None,
            **state, "summary": common._scrub(summary), "source_system": str(parent.get("source_system") or "native_operations"),
            "inspection": inspection, "write_run": write_run,
            "emit": write_run and (state.get("emit", True)), "event_uuid": uuid.uuid4().hex}
        changes.append(change)
        if parent.get("batch_id"):
            batches.add(int(parent["batch_id"]))
        if replacement:
            run_uuid = uuid.uuid4().hex
            data = _mapping(parent.get("data")) if inspection else (_mapping(run.get("data")) or _mapping(parent.get("data")))
            reopen.append({"task_id": task_id, "task_uuid": parent["task_uuid"], "run_uuid": run_uuid,
                "source_system": "native_operations" if inspection else change["source_system"],
                "account_id": None if inspection else parent.get("account_id"),
                "batch_id": parent.get("batch_id") if inspection else run.get("batch_id") or parent.get("batch_id"),
                "resource_family": "inspection_coordinator" if inspection else run.get("resource_family") or "completion_coordinator",
                "data": common._scrub(data), "cancellation_token": uuid.uuid4().hex, "event_uuid": uuid.uuid4().hex})
    if not changes:
        return {"batch_ids": batches, "registration_run_ids": registration_runs}
    if reopen:
        _append_waiting_runs(cur, reopen, changes)
    _write_changes(cur, changes)
    return {"batch_ids": batches, "registration_run_ids": registration_runs}


def _append_waiting_runs(cur, reopen: list[dict], changes: list[dict]) -> None:
    cur.execute(f"""SELECT task_id,COALESCE(MAX(run_no),0)+1 AS run_no
        FROM {common._table('operation_runs')} WHERE task_id=ANY(%s) GROUP BY task_id""",
        ([row["task_id"] for row in reopen],))
    numbers = {int(row["task_id"]): int(row["run_no"]) for row in cur.fetchall()}
    for row in reopen:
        row["run_no"] = numbers.get(row["task_id"], 1)
        row["log_file"] = str(run_log.build_path(task_uuid=row["task_uuid"], run_no=row["run_no"], run_uuid=row["run_uuid"]))
    cur.execute(f"""INSERT INTO {common._table('operation_runs')}
        (run_uuid,task_id,run_no,source_system,source_id,status,batch_id,account_id,
         resource_family,cancellation_token,log_file,data)
        SELECT s.run_uuid,s.task_id,s.run_no,s.source_system,s.run_uuid,'waiting',s.batch_id,s.account_id,
            s.resource_family,s.cancellation_token,s.log_file,s.data
        FROM jsonb_to_recordset(%s::jsonb) s(run_uuid TEXT,task_id BIGINT,run_no INTEGER,source_system TEXT,
            batch_id BIGINT,account_id BIGINT,resource_family TEXT,cancellation_token TEXT,log_file TEXT,data JSONB)
        RETURNING id,task_id""", (json.dumps(reopen, ensure_ascii=False),))
    new_ids = {int(row["task_id"]): int(row["id"]) for row in cur.fetchall()}
    for change in changes:
        if change["task_id"] in new_ids:
            change["run_id"] = new_ids[change["task_id"]]
    for row in reopen:
        row["run_id"] = new_ids[row["task_id"]]
    cur.execute(f"""INSERT INTO {common._table('operation_events')}
        (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
        SELECT s.event_uuid,s.task_id,s.run_id,s.source_system,s.event_uuid,'INFO','waiting',
            'run.waiting','任务等待子任务完成','{{}}'::jsonb
        FROM jsonb_to_recordset(%s::jsonb) s(event_uuid TEXT,task_id BIGINT,run_id BIGINT,source_system TEXT)""",
        (json.dumps(reopen, ensure_ascii=False),))
    for row in reopen:
        if not row["data"].get("bulk_target_round_id"):
            run_log.append(row["log_file"], level="INFO", message="任务等待子任务完成",
                task_id=row["task_id"], run_id=row["run_id"], stage="waiting", event_type="run.waiting")


def _write_changes(cur, changes: list[dict]) -> None:
    payload = json.dumps(changes, ensure_ascii=False)
    cur.execute(f"""UPDATE {common._table('operation_tasks')} t
        SET status=s.status,target_status=s.target_status,current_stage=s.stage,next_actions=s.actions,
            completed_at=CASE WHEN s.status='waiting' THEN NULL ELSE now() END,updated_at=now(),
            last_run_id=COALESCE(s.run_id,t.last_run_id)
        FROM jsonb_to_recordset(%s::jsonb) s(task_id BIGINT,run_id BIGINT,status TEXT,
            target_status TEXT,stage TEXT,actions JSONB) WHERE t.id=s.task_id""", (payload,))
    cur.execute(f"""UPDATE {common._table('operation_runs')} r
        SET status=s.status,progress_stage=s.stage,heartbeat_at=now(),result_summary=s.summary,
            completed_at=CASE WHEN s.status='waiting' THEN NULL
                WHEN s.inspection THEN COALESCE(r.completed_at,now()) ELSE now() END,
            duration_ms=CASE WHEN s.status<>'waiting' AND NOT s.inspection THEN
                GREATEST(0,(EXTRACT(EPOCH FROM (now()-COALESCE(r.started_at,r.created_at)))*1000)::BIGINT)
                ELSE r.duration_ms END
        FROM jsonb_to_recordset(%s::jsonb) s(run_id BIGINT,status TEXT,stage TEXT,
            summary JSONB,inspection BOOLEAN,write_run BOOLEAN)
        WHERE r.id=s.run_id AND s.write_run""", (payload,))
    waiting = [row["run_id"] for row in changes if row["write_run"] and row["status"] == "waiting" and not row["inspection"]]
    if waiting:
        cur.execute(f"DELETE FROM {common._table('account_operation_leases')} WHERE run_id=ANY(%s)", (waiting,))
    cur.execute(f"""INSERT INTO {common._table('operation_events')}
        (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
        SELECT s.event_uuid,s.task_id,s.run_id,
            CASE WHEN s.inspection THEN 'native_operations' ELSE s.source_system END,
            s.event_uuid,s.level,s.stage,s.event_type,s.message,
            CASE WHEN s.inspection THEN s.summary ELSE '{{}}'::jsonb END
        FROM jsonb_to_recordset(%s::jsonb) s(event_uuid TEXT,task_id BIGINT,run_id BIGINT,
            source_system TEXT,level TEXT,stage TEXT,event_type TEXT,message TEXT,
            inspection BOOLEAN,summary JSONB,emit BOOLEAN) WHERE s.emit""", (payload,))
