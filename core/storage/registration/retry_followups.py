"""注册重试后处理的集合事务；不调用执行器或第三方服务。"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import json
from typing import Mapping
import uuid

from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus
from psycopg.errors import SerializationFailure

from core.operations import run_log, task_gateway
from core.storage import db_legacy, records, registration
from core.storage.operations import common, schema


@dataclass(frozen=True)
class RetryFollowup:
    source: dict
    account: dict
    action: str
    config_snapshot: dict
    data: dict
    config_allowlist: tuple[str, ...]
    trigger: str | None = None
    root: dict | None = None
    attempt: dict | None = None


@dataclass(frozen=True)
class PreparedFollowups:
    rows: list[dict]
    replies: dict[int, dict]
    references: list[dict]
    repairs: list[dict]


_ACTIONS = {
    "plan_check": ("plan_check", "native_operations", "registration_retry_plan_check"),
    "codex": ("codex_retry", "native_operations", "registration_job_retry"),
    "twofa": ("account_setup_retry", "webui_runtime", "registration_job_retry"),
}
_TERMINAL = frozenset({
    "success", "failed", "partial_success", "stopped", "cancelled", "interrupted",
    "request_unknown", "manual_reconcile",
})
_FAMILY_EXCLUSIVE = ("queued", "running", "cancelling", "settling")
_SETUP_REUSABLE = frozenset({"queued", "running", "cancelling", "settling", "waiting"})
_CHUNK_SIZE = 500


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _chunks(rows: list[dict]):
    for offset in range(0, len(rows), _CHUNK_SIZE):
        yield rows[offset:offset + _CHUNK_SIZE]


def _error(message: str, *, busy: bool = False, status: int = 409) -> dict:
    return {"accepted": False, "reused": False, "busy": busy, "error": message, "status": status}


def _email(value) -> str:
    return str(value or "").strip().casefold()


def _parents(cur, source_ids: list[int]) -> dict[int, dict]:
    cur.execute(
        f"""SELECT wanted.id AS source_job_id,parent.*
        FROM unnest(%s::bigint[]) wanted(id)
        JOIN LATERAL (
            SELECT task.* FROM {common._table('operation_tasks')} task
            LEFT JOIN LATERAL (
                SELECT run.id FROM {common._table('operation_runs')} run
                WHERE run.task_id=task.id AND run.source_system='registration_jobs'
                  AND run.source_id=wanted.id::text ORDER BY run.id DESC LIMIT 1
            ) original_run ON TRUE
            WHERE (task.source_system='registration_jobs' AND task.source_id=wanted.id::text)
               OR original_run.id IS NOT NULL
            ORDER BY CASE WHEN task.source_system='registration_jobs'
                AND task.source_id=wanted.id::text THEN 0 ELSE 1 END,original_run.id DESC LIMIT 1
        ) parent ON TRUE""",
        (source_ids,),
    )
    return {int(row["source_job_id"]): dict(row) for row in cur.fetchall()}


def resolve_followup_context_task_ids(conn, specs: list[RetryFollowup]) -> list[int]:
    """只读解析注册来源父 Task 和既有配置任务的实际父 Task。"""
    if not specs:
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        parents = _parents(cur, [int(spec.source["id"]) for spec in specs if spec.action != "plan_check"])
        setup_sources = [f"registration-account-setup:{spec.source['id']}" for spec in specs if spec.action == "twofa"]
        cur.execute(f"""SELECT parent_task_id FROM {common._table('operation_tasks')}
            WHERE source_system='webui_runtime' AND source_id=ANY(%s)
              AND parent_task_id IS NOT NULL""", (setup_sources,))
        return sorted({int(parent["id"]) for parent in parents.values()}
                      | {int(row["parent_task_id"]) for row in cur.fetchall()})


def _caller_transaction(conn) -> None:
    if conn.autocommit:
        raise ValueError("注册后处理集合需要调用方事务连接")
    if conn.info.transaction_status == TransactionStatus.IDLE:
        conn.execute("BEGIN")


def _source_facts(cur, specs: list[RetryFollowup]):
    source_ids = sorted({int(spec.source["id"]) for spec in specs})
    job_ids = sorted(set(source_ids) | {
        int(spec.source.get("root_job_id") or spec.source["id"]) for spec in specs
    })
    attempt_ids = sorted({
        int(item["attempt_id"]) for spec in specs for item in (spec.source, spec.root or {})
        if item.get("attempt_id")
    } | {int(spec.attempt["id"]) for spec in specs if spec.attempt is not None})
    attempts = {}
    if attempt_ids:
        cur.execute(f"""SELECT * FROM {registration._table('registration_attempts')}
            WHERE id=ANY(%s) ORDER BY id FOR UPDATE""", (attempt_ids,))
        attempts = {int(row["id"]): registration._row(row) for row in cur.fetchall()}
    cur.execute(f"""SELECT * FROM {records._qualified(records.JOBS)}
        WHERE id=ANY(%s) ORDER BY id FOR NO KEY UPDATE""", (job_ids,))
    sources = {int(row["id"]): records.merge_row(records.JOBS, row) for row in cur.fetchall()}
    return sources, attempts


def prelock_followup_sources(conn, specs: list[RetryFollowup]) -> None:
    """跨来源波次在全局账号锁之前，按原顺序集合锁定 Attempt 和 Job。"""
    if specs:
        _caller_transaction(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            _source_facts(cur, specs)


def _read(cur, specs: list[RetryFollowup], *, locked_parent_contexts: dict[int, int] | None = None):
    setup_sources = [f"registration-account-setup:{spec.source['id']}" for spec in specs if spec.action == "twofa"]
    cur.execute(f"""SELECT * FROM {common._table('operation_tasks')}
        WHERE source_system='webui_runtime' AND source_id=ANY(%s) ORDER BY id""", (setup_sources,))
    existing = {row["source_id"]: dict(row) for row in cur.fetchall()}
    parents = _parents(cur, [int(spec.source["id"]) for spec in specs if spec.action != "plan_check"])
    contexts = {parent["id"]: parent for parent in parents.values()}
    existing_parent_ids = sorted({task["parent_task_id"] for task in existing.values()
                                  if task.get("parent_task_id")} - contexts.keys())
    cur.execute(f"SELECT * FROM {common._table('operation_tasks')} WHERE id=ANY(%s)",
                (existing_parent_ids,))
    contexts.update({row["id"]: dict(row) for row in cur.fetchall()})
    if locked_parent_contexts is not None:
        for parent_id, parent in contexts.items():
            if (parent_id not in locked_parent_contexts
                    or int(parent.get("last_run_id") or 0) != int(locked_parent_contexts[parent_id] or 0)):
                raise SerializationFailure("注册父任务上下文已变化，请刷新后重试")
            contexts[parent_id] = {**parent, "__lock_acquired": True}
    else:
        batch_ids = sorted({int(row["batch_id"]) for row in contexts.values() if row.get("batch_id")})
        # 与注册投影一致，既有 queue/batch 锁先于 Job/账号和新子 Task。
        if batch_ids:
            cur.execute(f"""SELECT batch_id FROM {common._table('operation_projection_queue')}
                WHERE batch_id=ANY(%s) ORDER BY batch_id FOR UPDATE""", (batch_ids,))
            cur.fetchall()
            cur.execute("SELECT pg_advisory_xact_lock(id) FROM unnest(%s::bigint[]) item(id) ORDER BY id",
                        (batch_ids,))
            cur.fetchall()
            cur.execute(f"""SELECT id FROM {common._table('operation_batches')}
                WHERE id=ANY(%s) ORDER BY id FOR NO KEY UPDATE""", (batch_ids,))
            cur.fetchall()
        cur.execute(f"""SELECT id FROM {common._table('operation_runs')}
            WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED""",
            (sorted({parent["last_run_id"] for parent in contexts.values() if parent.get("last_run_id")}),))
        parent_runs = {row["id"] for row in cur.fetchall()}
        cur.execute(f"""SELECT * FROM {common._table('operation_tasks')}
            WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED""",
            (sorted(contexts),))
        parent_tasks = {row["id"]: dict(row) for row in cur.fetchall()}
        for parent_id, parent in contexts.items():
            locked = parent_tasks.get(parent["id"])
            contexts[parent_id] = {**parent, **(locked or {}), "__lock_acquired": bool(locked
                and locked.get("last_run_id") == parent.get("last_run_id")
                and (not parent.get("last_run_id") or parent["last_run_id"] in parent_runs))}
    parents = {source_id: contexts[parent["id"]] for source_id, parent in parents.items()}
    sources, attempts = _source_facts(cur, specs)
    stage_guard, stage_params = db_legacy._stage_claim_guard("plan_check")
    account_ids = sorted({int(spec.account["id"]) for spec in specs})
    cur.execute(f"""WITH locked AS MATERIALIZED (
            SELECT *,({stage_guard}) AS plan_available FROM {records._qualified(records.ACCOUNTS)}
            WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED
        ) SELECT wanted.id AS wanted_id,locked.*
          FROM unnest(%s::bigint[]) wanted(id) LEFT JOIN locked USING(id)
          ORDER BY wanted.id""", (*stage_params, account_ids, account_ids))
    accounts = {}
    busy_accounts = set()
    for row in cur.fetchall():
        if row["id"] is None:
            busy_accounts.add(int(row["wanted_id"]))
            continue
        accounts[int(row["id"])] = {
            **records.merge_row(records.ACCOUNTS, row), "__plan_available": row["plan_available"],
        }
    # 区分不存在和正在被旧单项路径持有的账号；只读存在性不会反向等待业务锁。
    cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s)",
                (sorted(busy_accounts),))
    busy_accounts = {row["id"] for row in cur.fetchall()}
    cur.execute(f"""SELECT * FROM {common._table('operation_tasks')}
        WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED""",
        (sorted(row["id"] for row in existing.values()),))
    locked_tasks = {row["id"]: dict(row) for row in cur.fetchall()}
    for source_name, task in list(existing.items()):
        locked = locked_tasks.get(task["id"])
        if locked_parent_contexts is not None and locked and locked.get("parent_task_id") != task.get("parent_task_id"):
            raise SerializationFailure("原配置父任务上下文已变化，请刷新后重试")
        actual_parent = contexts.get(task.get("parent_task_id"))
        existing[source_name] = {**(locked or task),
            "__lock_acquired": bool(locked and locked.get("parent_task_id") == task.get("parent_task_id")),
            "__parent_lock_acquired": not task.get("parent_task_id") or bool(
                actual_parent and actual_parent["__lock_acquired"])}
    cur.execute(f"""SELECT latest.*,current_run.id AS current_run_id,current_run.status AS current_status
        FROM (SELECT DISTINCT ON (task_id) * FROM {common._table('operation_runs')}
            WHERE task_id=ANY(%s) ORDER BY task_id,run_no DESC,id DESC) latest
        JOIN LATERAL (
            SELECT id,status FROM {common._table('operation_runs')} current
            WHERE current.task_id=latest.task_id
            ORDER BY (status=ANY(%s)) DESC,run_no DESC,id DESC LIMIT 1
        ) current_run ON TRUE""",
        (sorted(row["id"] for row in existing.values()), list(common._ACTIVE_RUN_STATUSES)))
    latest = {row["task_id"]: dict(row) for row in cur.fetchall()}
    cur.execute(f"""SELECT id,task_id,account_id,resource_family FROM {common._table('operation_runs')}
        WHERE account_id=ANY(%s) AND resource_family='openai_interactive'
          AND status=ANY(%s) ORDER BY id""",
        (sorted(accounts), list(_FAMILY_EXCLUSIVE)))
    active = {}
    for row in cur.fetchall():
        active.setdefault(row["account_id"], dict(row))
    return sources, accounts, parents, existing, latest, active, attempts, busy_accounts


def _receipt(row: Mapping, *, reused: bool) -> dict:
    return {"accepted": True, "reused": reused, "busy": False,
        "task_id": int(row["task_id"]), "run_id": int(row["run_id"]),
        "account_id": int(row["account_id"]), "email": str(row["email"]),
        "state": str(row.get("state") or "queued"), "status": 200,
        **({"log_file": row["log_file"]} if row.get("log_file") else {})}


def admit(specifications: list[RetryFollowup], *, conn=None) -> dict[int, dict]:
    """一次事务受理已冻结的后处理计划，回执按原注册 Job ID 索引。"""
    specs = list(specifications)
    if not specs:
        return {}
    if any(spec.action not in _ACTIONS for spec in specs):
        raise ValueError("不支持的注册后处理动作")
    if conn is None:
        records.init()
        schema.init_operation_schema()
        if any(spec.source.get("attempt_id") or (spec.root or {}).get("attempt_id") or spec.attempt
               for spec in specs):
            registration.init()
    with (common._connect() if conn is None else nullcontext(conn)) as selected:
        if conn is not None:
            _caller_transaction(selected)
        with selected.transaction(), selected.cursor(row_factory=dict_row) as cur:
            prepared = _prepare(cur, specs)
            output, winners, reserved = dict(prepared.replies), [], {}
            for row in prepared.rows:
                key = row["account_id"]
                if key in reserved:
                    output[row["source_job_id"]] = {
                        **_error("账号已有其它操作正在执行，本次缺项尚未入队，可稍后重跑", busy=True),
                        "_reserved_source_job_id": reserved[key],
                    }
                else:
                    winners.append(row)
                    reserved[key] = row["source_job_id"]
            output.update(_commit(cur, prepared, winners))
            for reply in output.values():
                winner = output.get(reply.pop("_reserved_source_job_id", None))
                if winner and winner.get("accepted"):
                    reply.update(task_id=winner["task_id"], run_id=winner["run_id"])
            return output


def prepare_followups(
    conn, specifications: list[RetryFollowup], *, locked_parent_contexts: dict[int, int] | None = None,
) -> PreparedFollowups:
    """完整验证所有候选，保留调用方事务中的锁，不预占账号、不写业务状态。"""
    specs = list(specifications)
    if any(spec.action not in _ACTIONS for spec in specs):
        raise ValueError("不支持的注册后处理动作")
    if not specs:
        return PreparedFollowups([], {}, [], [])
    _caller_transaction(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        return _prepare(cur, specs, locked_parent_contexts=locked_parent_contexts)


def commit_followups(
    conn, prepared: PreparedFollowups, *, winner_source_ids: list[int],
) -> dict[int, dict]:
    """集合写入全来源资格审查后选出的赢家，复用修复与回执同事务落库。"""
    _caller_transaction(conn)
    selected = set(winner_source_ids)
    rows = [dict(row) for row in prepared.rows if row["source_job_id"] in selected]
    with conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        return _commit(cur, prepared, rows)


def _prepare(
    cur, specs: list[RetryFollowup], *, locked_parent_contexts: dict[int, int] | None = None,
) -> PreparedFollowups:
    sources, accounts, parents, existing, latest, active, attempts, busy_accounts = _read(
        cur, specs, locked_parent_contexts=locked_parent_contexts,
    )
    output, rows, references, repairs = {}, [], [], []
    for spec in specs:
        source_id, account_id = int(spec.source["id"]), int(spec.account["id"])
        source, account = sources.get(source_id), accounts.get(account_id)
        parent = parents.get(source_id) if spec.action != "plan_check" else None
        source_name = f"registration-account-setup:{source_id}"
        task = existing.get(source_name) if spec.action == "twofa" else None
        previous = latest.get(task["id"]) if task else None
        if account_id in busy_accounts or parent and not parent["__lock_acquired"]:
            output[source_id] = _error("原账号或父任务正在更新，请刷新后重试", busy=True)
            continue
        if not source or not account:
            output[source_id] = _error("原注册任务或账号不存在", status=404)
            continue
        linked_attempt = attempts.get(int(source["attempt_id"])) if source.get("attempt_id") else None
        root = sources.get(int(source.get("root_job_id") or source_id))
        dispatch_root = root or source
        dispatch_attempt = (attempts.get(int(dispatch_root["attempt_id"])) if dispatch_root.get("attempt_id")
                            else linked_attempt)
        if str((dispatch_attempt or {}).get("target_status") or "").lower() == "deactivated":
            output[source_id] = {**_error("原注册 Attempt 已废号，不能重跑"), "deactivated": True}
            continue
        if (spec.root is not None and dispatch_root != spec.root
                or spec.attempt is not None and dispatch_attempt != spec.attempt):
            output[source_id] = _error("原注册任务状态或身份已变化，请刷新后重试")
            continue
        if source.get("attempt_id"):
            from core.storage.registration.account_links import registration_account_link

            identity = registration_account_link(source, root, linked_attempt)
            if identity is None or identity != (_email(account.get("email")), account_id):
                output[source_id] = _error("原注册 Attempt 与账号身份不一致")
                continue
        if (source.get("status") not in _TERMINAL or any(
                source.get(key) != spec.source.get(key)
                for key in ("status", "email", "email_source", "account_id", "attempt_id", "root_job_id", "updated_at")
            ) or _email(account.get("email")) != _email(spec.account.get("email"))
                or account.get("updated_at") != spec.account.get("updated_at")
                or source.get("account_id") not in (None, account_id)
                or _email(source.get("email")) not in ("", _email(account.get("email")))):
            output[source_id] = _error("原注册任务状态或账号身份已变化，请刷新后重试")
            continue
        if common._account_is_deactivated(account):
            output[source_id] = {**_error("账号已废号，不能重跑"), "deactivated": True}
            continue
        if spec.action == "plan_check" and not str(account.get("access_token") or "").strip():
            output[source_id] = _error("账号缺少 access_token")
            continue
        if spec.action == "plan_check" and not account["__plan_available"]:
            output[source_id] = _error("该账号正在查询套餐", busy=True)
            continue
        if parent and parent.get("account_id") not in (None, account_id):
            output[source_id] = _error("原注册父任务与账号身份不一致")
            continue
        if task and (task.get("account_id") != account_id or task.get("task_type") != "account_setup_retry"):
            output[source_id] = _error("原账号配置任务与注册来源不一致")
            continue
        if task and not task["__lock_acquired"]:
            output[source_id] = _error("原账号配置正在更新，请刷新后重试", busy=True)
            continue
        if task and not task["__parent_lock_acquired"]:
            output[source_id] = _error("原配置父任务正在更新，请刷新后重试", busy=True)
            continue
        if task and not previous:
            output[source_id] = _error("原账号配置执行缺失，请刷新后重试")
            continue
        payload = dict(spec.data)
        payload["config_snapshot"] = task_gateway.normalize_config_snapshot(
            spec.config_snapshot, allowlist=spec.config_allowlist,
        )
        if task and previous.get("current_status") in _SETUP_REUSABLE:
            old_data = previous.get("data") or {}
            old_settings, settings = old_data.get("config_snapshot") or {}, payload["config_snapshot"]
            if (any(old_settings.get(key) != settings.get(key) for key in ("password_driver", "twofa_driver"))
                    or old_data.get("proxy_country_override") != payload.get("proxy_country_override")):
                output[source_id] = _error("原账号已有其他驱动或国家的配置任务，不能中途切换")
                continue
            reused = {"task_id": task["id"], "run_id": previous["current_run_id"], "account_id": account_id,
                      "email": account["email"], "state": previous["current_status"]}
            output[source_id] = _receipt(reused, reused=True)
            references.append({"source_job_id": source_id, **reused})
            if parent and not task.get("parent_task_id"):
                repairs.append({"task_id": task["id"], "parent_task_id": parent["id"],
                                "root_task_id": parent.get("root_task_id") or parent["id"]})
            continue
        if task and (task.get("status") in common._ACTIVE_RUN_STATUSES
                     or previous.get("current_status") in common._ACTIVE_RUN_STATUSES):
            output[source_id] = _error("任务仍在执行", busy=True)
            continue
        if task:
            summary = previous.get("result_summary") or {}
            summary_statuses = {str(summary.get(key) or "").strip().lower()
                                for key in ("status", "requested_status")}
            if (str(task.get("status") or "").lower() == "deactivated"
                    or str(task.get("target_status") or "").lower() in {"deactivated", "account_deactivated"}
                    or "deactivated" in summary_statuses):
                output[source_id] = {**_error("账号已废号，禁止重跑"), "deactivated": True}
                continue
        if account_id in active:
            blocker = active.get(account_id)
            output[source_id] = {**_error("账号已有其它操作正在执行，本次缺项尚未入队，可稍后重跑", busy=True),
                "task_id": blocker["task_id"], "run_id": blocker["id"]}
            continue
        task_type, source_system, default_trigger = _ACTIONS[spec.action]
        data = dict(previous.get("data") or {}) if previous else {}
        data.update(task.get("data") or {} if task else {})
        data.update(payload)
        if task:
            data.update(retry_trigger=spec.trigger or default_trigger)
            data.pop("remote_intent", None)
            data.pop("remote_receipt", None)
        task_uuid = str(task["task_uuid"]) if task else uuid.uuid4().hex
        run_uuid = uuid.uuid4().hex
        effective_parent = task.get("parent_task_id") if task else None
        effective_parent = effective_parent or (parent["id"] if parent else None)
        rows.append({
            "source_job_id": source_id, "action": spec.action, "task_type": task_type,
            "source_system": source_system, "source_id": source_name if spec.action == "twofa" else (
                f"maintenance:plan_check:{account_id}:{uuid.uuid4().hex}" if spec.action == "plan_check" else uuid.uuid4().hex),
            "task_id": task["id"] if task else None, "task_uuid": task_uuid,
            "parent_task_id": effective_parent,
            "reconcile_parent": bool(task and effective_parent),
            "root_task_id": task.get("root_task_id") if task and task.get("parent_task_id") else (
                (parent.get("root_task_id") or parent["id"]) if parent else None),
            "account_id": account_id, "email": str(account["email"]),
            "trigger": spec.trigger or default_trigger, "data": common._scrub(data),
            "run_no": int(previous.get("run_no") or 0) + 1 if previous else 1,
            "run_uuid": run_uuid, "event_uuid": uuid.uuid4().hex,
            "resource_family": str(previous.get("resource_family") or "openai_interactive") if previous else "openai_interactive",
            "batch_id": previous.get("batch_id") if previous else None,
            "cancellation_token": uuid.uuid4().hex,
            "log_file": str(run_log.build_path(task_uuid=task_uuid, run_no=int(previous.get("run_no") or 0) + 1 if previous else 1, run_uuid=run_uuid)),
            "new_task": task is None,
        })
    return PreparedFollowups(rows, output, references, repairs)


def _commit(cur, prepared: PreparedFollowups, rows: list[dict]) -> dict[int, dict]:
    output = dict(prepared.replies)
    references, repairs = list(prepared.references), list(prepared.repairs)
    written = []
    for chunk in _chunks(rows):
        _claim_plans(cur, chunk, output)
        if not chunk:
            continue
        _insert(cur, chunk)
        for row in chunk:
            output[row["source_job_id"]] = _receipt(row, reused=False)
        references.extend(row for row in chunk if row["action"] == "twofa")
        written.extend(chunk)
    for chunk in _chunks(references):
        cur.execute(f"""UPDATE {records._qualified(records.JOBS)} job
            SET data=job.data || jsonb_build_object('registration_account_task_id',item.task_id),
                updated_at=%s
            FROM jsonb_to_recordset(%s::jsonb) item(source_job_id bigint,task_id bigint)
            WHERE job.id=item.source_job_id""", (records._now(), _json(chunk)))
    for chunk in _chunks(repairs):
        cur.execute(f"""UPDATE {common._table('operation_tasks')} task
            SET parent_task_id=item.parent_task_id,root_task_id=item.root_task_id
            FROM jsonb_to_recordset(%s::jsonb) item(task_id bigint,parent_task_id bigint,root_task_id bigint)
            WHERE task.id=item.task_id AND task.parent_task_id IS NULL""", (_json(chunk),))
    changed = [row for row in written if row.get("reconcile_parent")] + repairs
    if changed:
        from core.storage.operations.bulk_retry_reconcile import reconcile_parents_many
        from core.storage.operations.bulk_retry_registration import reconcile_registration_many

        facts = reconcile_parents_many(cur, [row["parent_task_id"] for row in changed],
                                       child_task_ids=[row["task_id"] for row in changed])
        registration_batches = reconcile_registration_many(
            cur, child_task_ids=[], parent_run_ids=facts["registration_run_ids"],
        )
        from core.storage.operations.bulk_retry_projection import refresh_batches_many

        refresh_batches_many(cur, set(facts["batch_ids"]) | set(registration_batches))
    return output


def _claim_plans(cur, rows: list[dict], output: dict) -> None:
    plans = [row for row in rows if row["action"] == "plan_check"]
    if not plans:
        return
    guard, params = db_legacy._stage_claim_guard("plan_check")
    now = records._now()
    cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)}
        SET plan_check_status='queued',updated_at=%s,
            data=data || jsonb_build_object('plan_check_trigger','registration_retry_plan_check',
                'plan_check_queued_at',%s::text,'plan_check_started_at',NULL,
                'plan_check_deadline_at',NULL,'plan_check_completed_at',NULL,'plan_check_error',NULL)
        WHERE id=ANY(%s) AND ({guard}) RETURNING id""",
        (now, now, [row["account_id"] for row in plans], *params))
    allowed = {row["id"] for row in cur.fetchall()}
    rejected = {row["source_job_id"] for row in plans if row["account_id"] not in allowed}
    for source_id in rejected:
        output[source_id] = _error("该账号正在查询套餐", busy=True)
    rows[:] = [row for row in rows if row["source_job_id"] not in rejected]


def _insert(cur, rows: list[dict]) -> None:
    fresh = [row for row in rows if row["new_task"]]
    if fresh:
        cur.execute(f"""INSERT INTO {common._table('operation_tasks')}
            (task_uuid,source_system,source_id,task_type,target_type,target_id,account_id,email_snapshot,
             requested_action,status,target_status,current_stage,next_actions,trigger,data,parent_task_id,root_task_id)
            SELECT task_uuid,source_system,source_id,task_type,'account',account_id,account_id,email,
                task_type,'queued','pending','queued','[]'::jsonb,trigger,data,parent_task_id,root_task_id
            FROM jsonb_to_recordset(%s::jsonb) item(task_uuid text,source_system text,source_id text,
                task_type text,account_id bigint,email text,trigger text,data jsonb,parent_task_id bigint,root_task_id bigint)
            RETURNING id,task_uuid""", (_json(fresh),))
        created = {row["task_uuid"]: row["id"] for row in cur.fetchall()}
        for row in fresh:
            row["task_id"] = created[row["task_uuid"]]
    cur.execute(f"""INSERT INTO {common._table('operation_runs')}
        (run_uuid,task_id,run_no,source_system,source_id,status,account_id,resource_family,
         batch_id,cancellation_token,log_file,data)
        SELECT run_uuid,task_id,run_no,source_system,run_uuid,'queued',account_id,resource_family,
            batch_id,cancellation_token,log_file,data
        FROM jsonb_to_recordset(%s::jsonb) item(run_uuid text,task_id bigint,run_no int,source_system text,
            account_id bigint,resource_family text,batch_id bigint,cancellation_token text,log_file text,data jsonb)
        RETURNING id,task_id""", (_json(rows),))
    created_runs = {row["task_id"]: row["id"] for row in cur.fetchall()}
    for row in rows:
        row["run_id"] = created_runs[row["task_id"]]
    payload = _json(rows)
    cur.execute(f"""UPDATE {common._table('operation_tasks')} task
        SET status='queued',target_status='pending',current_stage='queued',last_run_id=item.run_id,
            error_category=NULL,error_code=NULL,error_message=NULL,completed_at=NULL,
            next_actions='[]'::jsonb,updated_at=now(),trigger=item.trigger,
            parent_task_id=COALESCE(task.parent_task_id,item.parent_task_id),
            root_task_id=COALESCE(item.root_task_id,task.root_task_id,task.id)
        FROM jsonb_to_recordset(%s::jsonb) item(task_id bigint,run_id bigint,trigger text,
            parent_task_id bigint,root_task_id bigint)
        WHERE task.id=item.task_id""", (payload,))
    cur.execute(f"""INSERT INTO {common._table('operation_events')}
        (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
        SELECT event_uuid,task_id,run_id,source_system,event_uuid,'INFO','queued',
            'run.queued','任务已加入队列','{{}}'::jsonb
        FROM jsonb_to_recordset(%s::jsonb) item(event_uuid text,task_id bigint,run_id bigint,source_system text)""",
        (payload,))
    codex = [row for row in rows if row["action"] == "codex"]
    if codex:
        cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} account
            SET codex_execution_status='queued',codex_active_run_id=item.run_id,updated_at=%s,
                codex_status=CASE
                    WHEN account.codex_credential_state='valid' THEN 'success'
                    WHEN account.codex_credential_state='pending_confirmation' THEN 'pending_confirmation'
                    WHEN account.codex_status='success' THEN account.codex_status ELSE 'retrying' END
            FROM jsonb_to_recordset(%s::jsonb) item(account_id bigint,run_id bigint)
            WHERE account.id=item.account_id""", (records._now(), _json(codex)))
