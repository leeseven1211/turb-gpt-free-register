"""任务中心原生 Task 的同事务集合重试；不改变原来的执行资格。"""
from __future__ import annotations

import json
import uuid

from psycopg.errors import SerializationFailure
from psycopg.pq import TransactionStatus

from core.operations import run_log
from core.storage import records
from core.storage.operations import common

_CHUNK_SIZE = 500


class _ParentChanged(Exception):
    """父 Task 代次在取得锁前变化，必须释放本波锁后重读。"""


def _mapping(value) -> dict:
    decoded = common._decode(value)
    return dict(decoded) if isinstance(decoded, dict) else {}


def _rejected(task_id: int, message: str, **extra) -> dict:
    return {"accepted": False, "busy": False, "task_id": task_id, "error": message, **extra}


def lock_retry_parents_many(conn, task_ids, *, additional_parent_task_ids=()) -> dict[int, int]:
    """在账号和子 Task 锁之前锁定精确父上下文，返回父 Task 的 Run 代次。

    调用者拥有完整受理保存点并负责竞争重试；返回后须在后续 Task 锁内核对代次。
    锁冲突或代次变化抛 PostgreSQL 序列化异常，不能忽略该异常继续写入事实。
    注册后处理解析出的父 Task 可一并传入，批次及父 Run/Task 按全局顺序预锁。
    """
    specs = [{"task_id": int(value)} for value in dict.fromkeys(task_ids)]
    additional = {int(value) for value in additional_parent_task_ids}
    if not specs and not additional:
        return {}
    try:
        return _prelock_selected_parents(conn, specs, additional_parent_task_ids=additional)
    except _ParentChanged:
        raise SerializationFailure("父任务状态已变化，请刷新后重试") from None


def prepare_retry_tasks_many(
    conn, specifications: list[dict], *, selected_parents: dict[int, int] | None = None,
) -> dict:
    """锁定并完整验证原生重试，供跨来源规划器在写入之前挑选账号/资源赢家。

    本函数不追加 Run、不重置账号排队投影，也不替候选预占资源名额。调用者必须
    在同一事务保留返回行对应的 Task/账号锁，并把最终赢家传给 commit 接口。
    已先锁全部来源父上下文的调用者可传 selected_parents，避免反向补拿父锁。
    """
    selected = {}
    for spec in specifications:
        selected.setdefault(int(spec["task_id"]), dict(spec))
    specs = list(selected.values())
    try:
        parents = (_prelock_selected_parents(conn, specs) if specs else {}) if selected_parents is None else dict(selected_parents)
        rows, replies = [], {}
        for offset in range(0, len(specs), _CHUNK_SIZE):
            prepared = _prepare_chunk(conn, specs[offset:offset + _CHUNK_SIZE], selected_parents=parents)
            rows.extend(prepared["rows"])
            replies.update(prepared["replies"])
        return {"rows": rows, "replies": replies, "selected_parents": parents}
    except _ParentChanged:
        raise SerializationFailure("父任务状态已变化，请刷新后重试") from None


def commit_retry_tasks_many(conn, rows: list[dict]) -> dict[int, dict]:
    """只写入已准备行中的最终赢家；与调用方事实及整波回执保持同一事务。"""
    selected = {}
    for row in rows:
        selected.setdefault(int(row["task_id"]), dict(row))
    planned = list(selected.values())
    if not planned:
        return {}
    if conn.info.transaction_status == TransactionStatus.IDLE:
        conn.execute("BEGIN")
    output = {}
    with conn.transaction():
        for offset in range(0, len(planned), _CHUNK_SIZE):
            output.update(_commit_chunk(conn, planned[offset:offset + _CHUNK_SIZE]))
    return output


def retry_tasks_many(conn, specifications: list[dict]) -> dict[int, dict]:
    """集合追加各原生逻辑任务的新 Run，不提交事务或发送调度通知。

    调用者先完成领域配置检查并拥有事务。规格包含 task_id、可选 data/trigger、
    expected_previous_run_id 和 codex_state；同一 Task 只使用首次规格。
    """
    selected = {}
    for spec in specifications:
        selected.setdefault(int(spec["task_id"]), dict(spec))
    output = {}
    specs = list(selected.values())
    if not specs:
        return output
    if conn.info.transaction_status == TransactionStatus.IDLE:
        # 先进入调用方事务，再创建内层保存点；IDLE 上直接 transaction() 会提前提交。
        conn.execute("BEGIN")
    # 调用方即使捕获异常，整次集合追加也不能留下半条 Task/Run/账号投影。
    for attempt in range(3):
        try:
            with conn.transaction():
                group_results = {}
                selected_parents = _prelock_selected_parents(conn, specs)
                for offset in range(0, len(specs), _CHUNK_SIZE):
                    output.update(_retry_chunk(conn, specs[offset:offset + _CHUNK_SIZE],
                                               selected_parents=selected_parents, group_results=group_results))
            return output
        except _ParentChanged:
            output.clear()
            if attempt == 2:
                raise SerializationFailure("父任务状态已变化，请刷新后重试") from None
    return output


def _prelock_selected_parents(conn, specs: list[dict], *, additional_parent_task_ids=()) -> dict[int, int]:
    """先锁需要收口的父上下文，避免持账号/子 Task 再反向等待父 Run。"""
    ids = sorted(int(spec["task_id"]) for spec in specs)
    additional = {int(value) for value in additional_parent_task_ids}
    observed = {}
    with conn.cursor() as cur:
        for offset in range(0, len(ids), _CHUNK_SIZE):
            cur.execute(f"""SELECT t.id,t.task_type,t.parent_task_id,t.last_run_id,t.source_system,t.batch_id,t.data,
                    r.data AS run_data
                FROM {common._table('operation_tasks')} t
                LEFT JOIN {common._table('operation_runs')} r ON r.id=t.last_run_id
                WHERE t.id=ANY(%s) ORDER BY t.id""", (ids[offset:offset + _CHUNK_SIZE],))
            observed.update({int(row["id"]): dict(row) for row in cur.fetchall()})
        parent_ids = sorted(additional | {
            int(row["parent_task_id"]) for row in observed.values() if row["parent_task_id"]})
        password_ids = sorted(str(row["id"]) for row in observed.values() if row["task_type"] == "password_setup")
        if not parent_ids and not password_ids:
            return {}
        parents = {}
        for offset in range(0, max(len(parent_ids), len(password_ids)), _CHUNK_SIZE):
            cur.execute(f"""SELECT t.id,t.task_type,t.parent_task_id,t.last_run_id,t.source_system,t.batch_id,t.data,
                    r.data AS run_data
                FROM {common._table('operation_tasks')} t
                LEFT JOIN {common._table('operation_runs')} r ON r.id=t.last_run_id
                WHERE t.id=ANY(%s) OR (t.task_type='registration_resume' AND r.data ? 'completion_handoff'
                    AND r.data->'completion_handoff'->>'task_id'=ANY(%s))
                ORDER BY t.id""", (parent_ids[offset:offset + _CHUNK_SIZE],
                                   password_ids[offset:offset + _CHUNK_SIZE]))
            parents.update({int(row["id"]): dict(row) for row in cur.fetchall()})
        if not parents:
            return {}
        registrations = [row for task_id, row in parents.items()
            if task_id in additional
            or (row["task_type"] == "registration_resume" and _mapping(row.get("run_data")).get("completion_handoff"))
            or (row["source_system"] == "registration_chains" and any(
                int(child.get("parent_task_id") or 0) == task_id
                and _mapping(child.get("data")).get("registration_completion") is True
                for child in observed.values()))]
        batches = sorted({int(row["batch_id"]) for row in registrations if row["batch_id"]})
        if batches:
            cur.execute(f"""INSERT INTO {common._table('operation_projection_queue')}
                    (batch_id,reason,source_system,source_id,status,requested_at,available_at)
                SELECT id,'registration_completion','registration_completion','','queued',now(),now()
                FROM unnest(%s::bigint[]) AS batch(id) ORDER BY id
                ON CONFLICT(batch_id) DO NOTHING""", (batches,))
            cur.execute(f"SELECT id FROM {common._table('operation_projection_queue')} WHERE batch_id=ANY(%s) ORDER BY batch_id FOR UPDATE",
                        (batches,))
            cur.fetchall()
            cur.execute("SELECT pg_advisory_xact_lock(id) FROM unnest(%s::bigint[]) AS batch(id) ORDER BY id",
                        (batches,))
            cur.fetchall()
            cur.execute(f"SELECT id FROM {common._table('operation_batches')} WHERE id=ANY(%s) ORDER BY id FOR NO KEY UPDATE",
                        (batches,))
            cur.fetchall()
        expected = {task_id: int(row.get("last_run_id") or 0) for task_id, row in parents.items()}
        run_ids = sorted({value for value in expected.values() if value})
        if run_ids:
            cur.execute(f"SELECT id FROM {common._table('operation_runs')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                        (run_ids,))
            cur.fetchall()
        # 不等待旧单项 retry 的 Task→account 锁；冲突整波回滚重读。
        cur.execute(f"SELECT id,last_run_id FROM {common._table('operation_tasks')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED",
                    (sorted(parents),))
        locked = {int(row["id"]): int(row.get("last_run_id") or 0) for row in cur.fetchall()}
        if locked != expected:
            raise _ParentChanged()
        return expected


def _retry_chunk(conn, specs: list[dict], *, selected_parents: dict[int, int], group_results: dict) -> dict[int, dict]:
    prepared = _prepare_chunk(conn, specs, selected_parents=selected_parents, group_results=group_results)
    output = prepared["replies"]
    output.update(_commit_chunk(conn, prepared["rows"]))
    for key, winner in prepared["planned_groups"].items():
        if output[winner].get("accepted"):
            group_results[key] = output[winner]
    for task_id, winner in prepared["reuse"].items():
        output[task_id] = {**output[winner], **({"reused": True} if output[winner].get("accepted") else {})}
    return output


def _prepare_chunk(
    conn, specs: list[dict], *, selected_parents: dict[int, int], group_results: dict | None = None,
) -> dict:
    ids = sorted(int(spec["task_id"]) for spec in specs)
    output = {}
    with conn.cursor() as cur:
        cur.execute(f"SELECT id,account_id FROM {common._table('operation_tasks')} WHERE id=ANY(%s)", (ids,))
        identities = {int(row["id"]): row for row in cur.fetchall()}
        account_ids = sorted({int(row["account_id"]) for row in identities.values() if row["account_id"]})
        accounts = {}
        busy_accounts = set()
        if account_ids:
            cur.execute(f"""WITH locked AS MATERIALIZED (
                    SELECT * FROM {records._qualified(records.ACCOUNTS)}
                    WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED
                ) SELECT account.id AS existing_account_id,locked.*
                FROM {records._qualified(records.ACCOUNTS)} account
                LEFT JOIN locked ON locked.id=account.id WHERE account.id=ANY(%s) ORDER BY account.id""",
                (account_ids, account_ids))
            for row in cur.fetchall():
                account_id = int(row["existing_account_id"])
                if row["id"] is None:
                    busy_accounts.add(account_id)
                else:
                    accounts[account_id] = records.merge_row(records.ACCOUNTS, row)
        cur.execute(f"SELECT * FROM {common._table('operation_tasks')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED", (ids,))
        tasks = {int(row["id"]): dict(row) for row in cur.fetchall()}
        for task_id, previous_run_id in selected_parents.items():
            if task_id in tasks and int(tasks[task_id].get("last_run_id") or 0) != previous_run_id:
                raise _ParentChanged()
        # 旧单项路径可在预读后补挂父任务，不能持有账号/子 Task 再去补拿未知父 Run。
        if any(task.get("parent_task_id") and int(task["parent_task_id"]) not in selected_parents
               for task in tasks.values()):
            raise _ParentChanged()
        # Task 串行化追加；最新 Run 在取得 Task 锁之后普通读取，避免旧 Run→Task 反锁。
        cur.execute(f"""SELECT DISTINCT ON (task_id) * FROM {common._table('operation_runs')}
            WHERE task_id=ANY(%s) ORDER BY task_id,run_no DESC,id DESC""", (ids,))
        previous = {int(row["task_id"]): dict(row) for row in cur.fetchall()}
        queued_at = common._now().isoformat(timespec="seconds")
        rows = []
        planned_groups, reuse = {}, {}
        for spec in specs:
            task_id = int(spec["task_id"])
            # 旧一体入口保留历史归组；公开准备接口把所有资格成立候选交给外层统一规划。
            group_key = spec.get("group_key") if group_results is not None else None
            if group_key is not None and group_key in group_results:
                output[task_id] = {**group_results[group_key], "reused": True}
                continue
            if group_key is not None and group_key in planned_groups:
                reuse[task_id] = planned_groups[group_key]
                continue
            task = tasks.get(task_id)
            if not task:
                output[task_id] = (_rejected(task_id, "任务正在变更，请稍后重试", busy=True)
                                   if task_id in identities else _rejected(task_id, "任务不存在"))
                continue
            if (task_id not in identities or int(task.get("account_id") or 0)
                    != int(identities[task_id].get("account_id") or 0)):
                output[task_id] = _rejected(task_id, "任务账号已变化，请刷新后重试", busy=True)
                continue
            expected = spec.get("expected_previous_run_id")
            if expected is not None and int(task.get("last_run_id") or 0) != int(expected):
                output[task_id] = {"accepted": False, "task_id": task_id, "dependency_stale": True,
                                   "run_id": task.get("last_run_id"), "id": task.get("last_run_id")}
                continue
            if task.get("source_system") in {"registration_jobs", "account_action_tasks"}:
                output[task_id] = _rejected(task_id, "历史兼容任务需先迁移为原生任务后再重跑")
                continue
            prior = previous.get(task_id) or {}
            task_data, prior_data = _mapping(task.get("data")), _mapping(prior.get("data"))
            if task_data.get("bulk_target_round_id") or prior_data.get("bulk_target_round_id"):
                output[task_id] = _rejected(task_id, "受管批量任务应通过新轮次重跑", managed=True)
                continue
            task_status = str(task.get("status") or "").strip().lower()
            prior_status = str(prior.get("status") or "").strip().lower()
            if task_status in common._ACTIVE_RUN_STATUSES or prior_status in common._ACTIVE_RUN_STATUSES:
                output[task_id] = _rejected(task_id, "任务仍在执行", busy=True)
                continue
            account_id = int(task.get("account_id") or 0)
            if account_id in busy_accounts:
                output[task_id] = _rejected(task_id, "账号正在变更，请稍后重试", busy=True)
                continue
            account = accounts.get(account_id)
            summary = _mapping(prior.get("result_summary"))
            summary_states = {str(summary.get(key) or "").strip().lower() for key in ("status", "requested_status")}
            if (task_status == "deactivated"
                    or str(task.get("target_status") or "").strip().lower() in {"deactivated", "account_deactivated"}
                    or "deactivated" in summary_states or common._account_is_deactivated(account)):
                output[task_id] = _rejected(task_id, "账号已废号，禁止重跑", deactivated=True)
                continue
            data = {**prior_data, **task_data, **dict(spec.get("data") or {})}
            trigger = str(spec.get("trigger") or "manual_retry")
            data["retry_trigger"] = trigger
            data.pop("remote_intent", None)
            data.pop("remote_receipt", None)
            run_no = int(prior.get("run_no") or 0) + 1
            run_uuid = uuid.uuid4().hex
            row = {"task_id": task_id, "task_type": task["task_type"], "run_no": run_no,
                "run_uuid": run_uuid, "source_system": str(task.get("source_system") or "native_operations"),
                "batch_id": prior.get("batch_id"), "account_id": account_id or None,
                "resource_family": str(prior.get("resource_family") or "openai_interactive"),
                "cancellation_token": uuid.uuid4().hex, "event_uuid": uuid.uuid4().hex,
                "log_file": str(run_log.build_path(task_uuid=task["task_uuid"], run_no=run_no, run_uuid=run_uuid)),
                "data": common._scrub(data), "trigger": trigger,
                "email": str(task.get("email_snapshot") or ""), "account_exists": bool(account),
                "codex_state": spec.get("codex_state") is True,
                "previous_batch_id": prior.get("batch_id"), "task_batch_id": task.get("batch_id"),
                "parent_task_id": task.get("parent_task_id"), "queued_at": queued_at}
            rows.append(row)
            if group_key is not None:
                planned_groups[group_key] = task_id
            if (task["task_type"] == "extract_link" and task["source_system"] == "native_operations"
                    and data.get("workbench_action") == "sync_status"):
                try:
                    source_run_id = int(data.get("provider_job_run_id") or prior.get("id") or 0)
                except (TypeError, ValueError, OverflowError):
                    source_run_id = 0
                provider = str(data.get("provider_id") or "").strip()
                if source_run_id > 0 and provider:
                    row["provider_copy"] = {"task_id": task_id, "source_run_id": source_run_id, "provider_id": provider}
        return {"rows": rows, "replies": output, "planned_groups": planned_groups, "reuse": reuse}


def _commit_chunk(conn, prepared_rows: list[dict]) -> dict[int, dict]:
    if not prepared_rows:
        return {}
    rows = [dict(row) for row in prepared_rows]
    output = {}
    with conn.cursor() as cur:
        payload = json.dumps(rows, ensure_ascii=False)
        cur.execute(f"""INSERT INTO {common._table('operation_runs')}
            (run_uuid,task_id,run_no,source_system,source_id,status,batch_id,account_id,
             resource_family,cancellation_token,log_file,data)
            SELECT s.run_uuid,s.task_id,s.run_no,s.source_system,s.run_uuid,'queued',
                s.batch_id,s.account_id,s.resource_family,s.cancellation_token,s.log_file,s.data
            FROM jsonb_to_recordset(%s::jsonb) s(run_uuid TEXT,task_id BIGINT,run_no INTEGER,
                source_system TEXT,batch_id BIGINT,account_id BIGINT,resource_family TEXT,
                cancellation_token TEXT,log_file TEXT,data JSONB)
            ON CONFLICT DO NOTHING RETURNING *""", (payload,))
        inserted = {int(row["task_id"]): dict(row) for row in cur.fetchall()}
        for row in rows:
            if row["task_id"] not in inserted:
                output[row["task_id"]] = _rejected(row["task_id"], "账号操作仍在执行，请稍后重试", busy=True)
        rows = [row for row in rows if row["task_id"] in inserted]
        if not rows:
            return output
        copies = [dict(row["provider_copy"]) for row in rows if row.get("provider_copy")]
        batches = {int(value) for row in rows
                   for value in (row["task_batch_id"], row["previous_batch_id"]) if value}
        parents = {int(row["parent_task_id"]) for row in rows if row["parent_task_id"]}
        passwords = {row["task_id"] for row in rows if row["task_type"] == "password_setup"}
        for row in rows:
            row["run_id"] = int(inserted[row["task_id"]]["id"])
        payload = json.dumps(rows, ensure_ascii=False)
        cur.execute(f"""UPDATE {common._table('operation_tasks')} t
            SET status='queued',target_status='pending',current_stage='queued',last_run_id=s.run_id,
                error_category=NULL,error_code=NULL,error_message=NULL,completed_at=NULL,
                next_actions='[]'::jsonb,updated_at=now(),trigger=s.trigger
            FROM jsonb_to_recordset(%s::jsonb) s(task_id BIGINT,run_id BIGINT,trigger TEXT)
            WHERE t.id=s.task_id""", (payload,))
        cur.execute(f"""INSERT INTO {common._table('operation_events')}
            (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
            SELECT s.event_uuid,s.task_id,s.run_id,s.source_system,s.event_uuid,'INFO','queued',
                'run.queued','任务已加入队列','{{}}'::jsonb
            FROM jsonb_to_recordset(%s::jsonb) s(event_uuid TEXT,task_id BIGINT,run_id BIGINT,source_system TEXT)
            RETURNING id,run_id,event_uuid,created_at""", (payload,))
        events = {int(row["run_id"]): common._row(dict(row)) for row in cur.fetchall()}
        _update_accounts(cur, rows)
        if copies:
            for copy in copies:
                copy["run_id"] = int(inserted[copy["task_id"]]["id"])
            cur.execute(f"""INSERT INTO {common._table('extract_link_provider_jobs')}
                (run_id,provider_id,job_id,extraction_state,payment_state,public_state,private_data)
                SELECT s.run_id,job.provider_id,job.job_id,job.extraction_state,job.payment_state,
                    job.public_state,job.private_data
                FROM jsonb_to_recordset(%s::jsonb) s(run_id BIGINT,task_id BIGINT,source_run_id BIGINT,provider_id TEXT)
                JOIN {common._table('operation_runs')} source ON source.id=s.source_run_id AND source.task_id=s.task_id
                JOIN {common._table('extract_link_provider_jobs')} job
                    ON job.run_id=source.id AND job.provider_id=s.provider_id""", (json.dumps(copies),))
        registration_runs = set()
        if parents:
            from core.storage.operations.bulk_retry_reconcile import reconcile_parents_many
            facts = reconcile_parents_many(cur, sorted(parents), child_task_ids=[row["task_id"] for row in rows])
            batches.update(facts["batch_ids"])
            registration_runs.update(facts["registration_run_ids"])
        if passwords or registration_runs:
            from core.storage.operations.bulk_retry_registration import reconcile_registration_many
            batches.update(reconcile_registration_many(cur, child_task_ids=sorted(passwords),
                                                       parent_run_ids=sorted(registration_runs)))
        if batches:
            from core.storage.operations.bulk_retry_projection import refresh_batches_many
            refresh_batches_many(cur, sorted(batches))
        for row in rows:
            run = common._row(inserted[row["task_id"]])
            event = events[row["run_id"]]
            output[row["task_id"]] = {**run, "accepted": True, "busy": False, "reused": False,
                "task_id": row["task_id"], "run_id": row["run_id"], "account_id": row["account_id"],
                "email": row["email"], "source_system": row["source_system"], "status": "queued",
                "event_id": event["id"], "event_uuid": event["event_uuid"], "event_created_at": event["created_at"]}
        return output


def _update_accounts(cur, rows: list[dict]) -> None:
    stage_changes = {}
    for row in rows:
        if not row["account_exists"]:
            continue
        task_type, account_id = row["task_type"], row["account_id"]
        stage = ("plan_check" if task_type == "plan_check" else "live_check"
                 if task_type in {"live_check", "token_refresh"} else None)
        if not stage:
            continue
        queued_at = row["queued_at"]
        item = stage_changes.setdefault(account_id, {"account_id": account_id, "data": {},
            "plan_check": False, "live_check": False})
        item["queued_at"] = queued_at
        item[stage] = True
        item["data"].update({f"{stage}_ok": False, f"{stage}_trigger": row["trigger"],
            f"{stage}_queued_at": queued_at, f"{stage}_started_at": None,
            f"{stage}_error": None, f"{stage}_http_status": None})
        if stage == "plan_check":
            item["data"].update(plan_check_deadline_at=None, plan_check_completed_at=None)
        else:
            item["data"]["live_checked_at"] = None
    if stage_changes:
        # 原单项重试只重置账号排队投影，不增加 stage 占用判断。
        cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} account
            SET plan_check_status=CASE WHEN s.plan_check THEN 'queued' ELSE account.plan_check_status END,
                live_check_status=CASE WHEN s.live_check THEN 'queued' ELSE account.live_check_status END,
                plan_check_ok=CASE WHEN s.plan_check THEN false ELSE account.plan_check_ok END,
                updated_at=s.queued_at,data=account.data || s.data
            FROM jsonb_to_recordset(%s::jsonb) s(account_id BIGINT,plan_check BOOLEAN,live_check BOOLEAN,data JSONB,queued_at TEXT)
            WHERE account.id=s.account_id""", (json.dumps(list(stage_changes.values()), ensure_ascii=False),))
    codex = {row["account_id"]: row for row in rows if row["codex_state"] and row["account_exists"]}
    if codex:
        cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} account
            SET codex_execution_status='queued',codex_active_run_id=s.run_id,updated_at=s.queued_at,
                codex_status=CASE
                    WHEN lower(COALESCE(account.codex_credential_state,''))='valid' THEN 'success'
                    WHEN lower(COALESCE(account.codex_credential_state,''))='pending_confirmation' THEN 'pending_confirmation'
                    WHEN lower(COALESCE(account.codex_credential_state,''))='deactivated' THEN 'deactivated'
                    WHEN lower(COALESCE(account.codex_status,''))<>'success' THEN 'retrying'
                    ELSE account.codex_status END
            FROM jsonb_to_recordset(%s::jsonb) s(account_id BIGINT,run_id BIGINT,queued_at TEXT)
            WHERE account.id=s.account_id""", (json.dumps(list(codex.values()), ensure_ascii=False),))
