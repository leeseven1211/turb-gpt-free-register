"""已持新轮 target/account 锁时，集合追加普通原生任务的重试执行。"""
from __future__ import annotations

from collections import Counter
import json
import uuid

from core.operations import run_log
from core.storage import records
from core.storage.operations import common
from core.storage.operations.bulk_retry_projection import refresh_batches_many

_CHUNK_SIZE = 500
_NATIVE_TYPES = frozenset({
    "plan_check", "token_refresh", "password_setup", "twofa_setup",
    "account_completion", "codex_retry",
})


def _receipt(spec: dict, *, disposition: str, reason_code: str | None = None) -> dict:
    return {"target_round_id": spec["target_round_id"], "disposition": disposition,
            "reason_code": reason_code, "task_id": None, "run_id": None}


def _claim_stage(conn, specs: list[dict], *, operation_key: str, queued_at: str) -> set[int]:
    """同一条件 UPDATE 完成占用检查和本轮队列投影，不领取已被拒绝的 Task。"""
    ids = [spec["account_id"] for spec in specs]
    if operation_key not in {"plan_check", "token_refresh"}:
        return set(ids)
    from core.storage import db_legacy

    prefix = "plan_check" if operation_key == "plan_check" else "live_check"
    guard, params = db_legacy._stage_claim_guard(prefix, require_alive=prefix == "live_check")
    changes = {f"{prefix}_status": "queued", f"{prefix}_ok": False,
        f"{prefix}_trigger": "manual_bulk", f"{prefix}_queued_at": queued_at,
        f"{prefix}_started_at": None, f"{prefix}_error": None,
        f"{prefix}_http_status": None, "updated_at": queued_at}
    if prefix == "plan_check":
        changes.update(plan_check_deadline_at=None, plan_check_completed_at=None)
    else:
        changes["live_checked_at"] = None
    claimed = records.patch_rows_where_returning(records.ACCOUNTS, changes=changes,
        where=f"id=ANY(%s) AND ({guard})", params=(ids, *params), conn=conn, id_only=True)
    return {int(row["id"]) for row in claimed}


def _refresh_previous_batches(cur, batch_ids: set[int]) -> None:
    refresh_batches_many(cur, batch_ids)


def retry_native_many(conn, specifications: list[dict], *, operation_key: str) -> dict[int, dict]:
    """集合追加新执行并收口父任务，返回每个已识别原生目标的回执。

    调用方已持新轮 control/target/account 锁。这里不锁或继承旧轮 target，
    不提交事务、不触发外部执行；新 Run 的归属与 outbox 仍由提交方保存回执。
    """
    if not specifications:
        return {}
    task_counts = Counter(int(spec["task_id"]) for spec in specifications)
    output = {}
    for offset in range(0, len(specifications), _CHUNK_SIZE):
        specs = specifications[offset:offset + _CHUNK_SIZE]
        output.update(_retry_chunk(conn, specs, operation_key=operation_key, task_counts=task_counts))
    return output


def _retry_chunk(conn, specs: list[dict], *, operation_key: str, task_counts: Counter) -> dict[int, dict]:
    output = {}
    task_ids = sorted({int(spec["task_id"]) for spec in specs})
    with conn.cursor() as cur:
        cur.execute(f"""SELECT * FROM {common._table('operation_tasks')}
            WHERE id=ANY(%s) ORDER BY id FOR UPDATE""", (task_ids,))
        tasks = {int(row["id"]): dict(row) for row in cur.fetchall()}
        # 沿用单项 retry：Task 锁串行化新 attempt，锁后读取 latest Run。
        # 不反向锁旧 Run；普通终态/迟到事件可能正持 Run 锁等待更新 Task。
        cur.execute(f"""SELECT r.* FROM {common._table('operation_runs')} r
            JOIN (SELECT DISTINCT ON (task_id) id FROM {common._table('operation_runs')}
                WHERE task_id=ANY(%s) ORDER BY task_id,run_no DESC,id DESC) latest ON latest.id=r.id
            ORDER BY r.task_id,r.id""", (task_ids,))
        previous = {int(row["task_id"]): dict(row) for row in cur.fetchall()}
        eligible = []
        for spec in specs:
            task_id = int(spec["task_id"])
            task = tasks.get(task_id)
            if not task:
                output[spec["target_round_id"]] = _receipt(spec, disposition="not_executed",
                    reason_code="operation_precondition_changed")
                continue
            # 其他领域及异常重复身份仍沿原身份处理；父/注册收口在写后集合执行。
            if (task_counts[task_id] > 1 or task.get("task_type") not in _NATIVE_TYPES or task.get("task_type") != operation_key
                    or int(task.get("account_id") or 0) != spec["account_id"]):
                continue
            prior = previous.get(task_id) or {}
            summary = common._decode(prior.get("result_summary")) or {}
            task_status = str(task.get("status") or "").strip().lower()
            prior_status = str(prior.get("status") or "").strip().lower()
            target_status = str(task.get("target_status") or "").strip().lower()
            summary_statuses = {str(summary.get(name) or "").strip().lower()
                               for name in ("status", "requested_status")} if isinstance(summary, dict) else set()
            rejected = (str(task.get("source_system") or "") in {"registration_jobs", "account_action_tasks"}
                or task_status in common._ACTIVE_RUN_STATUSES or prior_status in common._ACTIVE_RUN_STATUSES
                or task_status == "deactivated" or target_status in {"deactivated", "account_deactivated"}
                or "deactivated" in summary_statuses or common._account_is_deactivated(spec["account"]))
            if rejected:
                output[spec["target_round_id"]] = _receipt(spec, disposition="not_executed",
                    reason_code="operation_precondition_changed")
            else:
                eligible.append(spec)
        if not eligible:
            return output
        queued_at = common._now().isoformat()
        allowed = _claim_stage(conn, eligible, operation_key=operation_key, queued_at=queued_at)
        rows, batch_ids = [], set()
        for spec in eligible:
            if spec["account_id"] not in allowed:
                output[spec["target_round_id"]] = _receipt(spec, disposition="waiting_account",
                    reason_code="plan_check_busy" if operation_key == "plan_check" else "live_check_busy")
                continue
            task, prior = tasks[spec["task_id"]], previous.get(spec["task_id"]) or {}
            data = dict(common._decode(prior.get("data")) or {})
            data.update(common._decode(task.get("data")) or {})
            data.update(spec["data"])
            data["retry_trigger"] = "manual_bulk_retry"
            if operation_key == "token_refresh":
                data["live_check_queued_at"] = queued_at
            data.pop("remote_intent", None)
            data.pop("remote_receipt", None)
            run_no = int(prior.get("run_no") or 0) + 1
            run_uuid = uuid.uuid4().hex
            rows.append({"target_round_id": spec["target_round_id"], "task_id": spec["task_id"],
                "run_no": run_no, "run_uuid": run_uuid,
                "source_system": str(task.get("source_system") or "native_operations"),
                "account_id": spec["account_id"], "batch_id": prior.get("batch_id"),
                "resource_family": str(prior.get("resource_family") or "openai_interactive"),
                "cancellation_token": uuid.uuid4().hex,
                "log_file": str(run_log.build_path(task_uuid=task["task_uuid"], run_no=run_no, run_uuid=run_uuid)),
                "data": common._scrub(data), "event_uuid": uuid.uuid4().hex})
            batch_ids.update(int(value) for value in (task.get("batch_id"), prior.get("batch_id")) if value)
        if not rows:
            return output
        payload = json.dumps(rows, ensure_ascii=False)
        cur.execute(f"""INSERT INTO {common._table('operation_runs')}
            (run_uuid,task_id,run_no,source_system,source_id,status,batch_id,account_id,
             resource_family,cancellation_token,log_file,data)
            SELECT s.run_uuid,s.task_id,s.run_no,s.source_system,s.run_uuid,'queued',
                s.batch_id,s.account_id,s.resource_family,s.cancellation_token,s.log_file,s.data
            FROM jsonb_to_recordset(%s::jsonb) s(run_uuid TEXT,task_id BIGINT,run_no INTEGER,
                source_system TEXT,batch_id BIGINT,account_id BIGINT,resource_family TEXT,
                cancellation_token TEXT,log_file TEXT,data JSONB)
            RETURNING id,task_id""", (payload,))
        runs = {int(row["task_id"]): int(row["id"]) for row in cur.fetchall()}
        for row in rows:
            row["run_id"] = runs[row["task_id"]]
        payload = json.dumps(rows, ensure_ascii=False)
        cur.execute(f"""UPDATE {common._table('operation_tasks')} t
            SET status='queued',target_status='pending',current_stage='queued',last_run_id=s.run_id,
                error_category=NULL,error_code=NULL,error_message=NULL,completed_at=NULL,
                next_actions='[]'::jsonb,updated_at=now(),trigger='manual_bulk_retry'
            FROM jsonb_to_recordset(%s::jsonb) s(task_id BIGINT,run_id BIGINT)
            WHERE t.id=s.task_id""", (payload,))
        cur.execute(f"""INSERT INTO {common._table('operation_events')}
            (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
            SELECT s.event_uuid,s.task_id,s.run_id,s.source_system,s.event_uuid,'INFO','queued',
                'run.queued','任务已加入队列','{{}}'::jsonb
            FROM jsonb_to_recordset(%s::jsonb) s(event_uuid TEXT,task_id BIGINT,run_id BIGINT,source_system TEXT)""",
            (payload,))
        if operation_key == "codex_retry":
            cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} a
                SET codex_execution_status='queued',codex_active_run_id=s.run_id,
                    codex_status=CASE WHEN a.codex_status='success'
                        OR a.codex_credential_state IN ('valid','pending_confirmation')
                        THEN a.codex_status ELSE 'retrying' END,updated_at=%s,data=a.data || %s::jsonb
                FROM jsonb_to_recordset(%s::jsonb) s(account_id BIGINT,run_id BIGINT)
                WHERE a.id=s.account_id""", (queued_at, json.dumps({"updated_at": queued_at}), payload))
        parent_ids = sorted({int(tasks[row["task_id"]]["parent_task_id"]) for row in rows
                             if tasks[row["task_id"]].get("parent_task_id")})
        registration_ids = set()
        if parent_ids:
            from core.storage.operations.bulk_retry_reconcile import reconcile_parents_many
            reconciled = reconcile_parents_many(cur, parent_ids, child_task_ids=[row["task_id"] for row in rows])
            batch_ids.update(reconciled["batch_ids"])
            registration_ids.update(reconciled["registration_run_ids"])
        password_ids = [row["task_id"] for row in rows if tasks[row["task_id"]]["task_type"] == "password_setup"]
        if password_ids or registration_ids:
            from core.storage.operations.bulk_retry_registration import reconcile_registration_many
            batch_ids.update(reconcile_registration_many(cur, child_task_ids=password_ids,
                                                         parent_run_ids=registration_ids))
        _refresh_previous_batches(cur, batch_ids)
        for row in rows:
            output[row["target_round_id"]] = {"target_round_id": row["target_round_id"],
                "disposition": "created", "reason_code": None, "task_id": row["task_id"], "run_id": row["run_id"]}
        return output
