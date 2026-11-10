"""五类账号操作的集合预检与同事务提交适配。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from core.accounts.completion import completion_plan
from core.bulk_operations.catalog import normalize_parameters
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import store


class _ItemWaiting(Exception):
    pass


class _ItemRejected(Exception):
    def __init__(self, result):
        self.result = result


def _identity(target: Mapping) -> int:
    return int(target.get("account_id") or target.get("entity_id") or target.get("target_id") or 0)


def _target_round_id(target: Mapping) -> int:
    return int(target.get("target_round_id") or target.get("id") or 0)


def _settings(context: Mapping) -> dict:
    raw = context.get("config_snapshot") or {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _key(context: Mapping) -> str:
    operation = context.get("operation") or {}
    return str(context.get("operation_key") or context.get("action_key") or operation.get("key") or "")


def prepare_many(targets: Sequence[Mapping], *, context: Mapping, conn, preflight_only: bool = False) -> list[dict]:
    """三次集合查询读取账号、活跃 Run 和注册占用；返回材料仅在调用栈使用。"""
    account_ids = sorted({_identity(target) for target in targets if _identity(target) > 0})
    if not account_ids:
        return [{"target": dict(target), "disposition": "not_executable", "reason_code": "account_missing"} for target in targets]
    key, snapshot = _key(context), _settings(context)
    if preflight_only and key in {"plan_check", "codex_retry"}:
        # 只读资格不需要解压账号会话、历史结果或凭据；与执行时重检分开。
        with conn.cursor() as cur:
            cur.execute(f"""SELECT id,email,codex_status,codex_credential_state,
                data->>'account_status' AS account_status,
                CASE WHEN account_has_access_token THEN 'present' ELSE '' END AS access_token
                FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s)""", (account_ids,))
            accounts = {int(row["id"]): dict(row) for row in cur.fetchall()}
    else:
        accounts = {int(row["id"]): row for row in records.list_rows(records.ACCOUNTS, where="id=ANY(%s)", params=(account_ids,), conn=conn)}
    active = {}
    with conn.cursor() as cur:
        cur.execute(f"SELECT id,task_id,account_id,resource_family FROM {store._table('operation_runs')} WHERE account_id=ANY(%s) AND status=ANY(%s)",
                    (account_ids, list(store._ACTIVE_RUN_STATUSES)))
        for row in cur.fetchall():
            active.setdefault(int(row["account_id"]), dict(row))
    emails = [str(row.get("email") or "").strip().lower() for row in accounts.values() if row.get("email")]
    with conn.cursor() as cur:
        cur.execute(f"""SELECT account_id,email FROM {records._qualified(records.JOBS)}
            WHERE COALESCE(NULLIF(job_type,''),'registration') IN ('registration','registration_resume')
            AND status=ANY(%s) AND (account_id=ANY(%s) OR LOWER(BTRIM(email))=ANY(%s))""",
            (["pending", "queued", "running", "stopping", "cancelling", "settling", "waiting", "debug_paused"], account_ids, emails))
        jobs = list(cur.fetchall())
    busy_accounts = {int(row.get("account_id") or 0) for row in jobs}
    busy_emails = {str(row.get("email") or "").strip().lower() for row in jobs}
    availability = {}
    prepared = []
    for target in targets:
        account = accounts.get(_identity(target))
        item = {"target": dict(target), "account": account, "disposition": "ready", "reason_code": None, "blocker_run_id": None}
        if not account:
            item.update(disposition="not_executable", reason_code="account_missing")
        elif store._account_is_deactivated(account):
            item.update(disposition="not_executable", reason_code="account_deactivated")
        elif not str(account.get("email") or "").strip():
            item.update(disposition="not_executable", reason_code="account_email_missing")
        elif _identity(target) in active:
            item.update(disposition="waiting_account", reason_code="account_busy", blocker_run_id=int(active[_identity(target)]["id"]))
        elif _identity(target) in busy_accounts or str(account.get("email") or "").strip().lower() in busy_emails:
            item.update(disposition="waiting_account", reason_code="registration_in_progress")
        elif key == "plan_check" and not account.get("access_token") and not snapshot.get("auto_refresh_at_enabled", True):
            item.update(disposition="not_executable", reason_code="access_token_missing")
        elif key in {"password_setup", "twofa_setup", "account_completion"}:
            from core.accounts import operation_coordinator as coordinator
            from core.runtime.capabilities import account_setup_unavailable
            plan = completion_plan(account, snapshot)
            item["plan"] = plan
            steps = set(plan["missing_steps"]) if key == "account_completion" else {"password" if key == "password_setup" else "twofa"}
            scope = tuple(sorted(steps))
            if scope not in availability:
                availability[scope] = coordinator._completion_deployment_unavailable(steps, snapshot) if key == "account_completion" else account_setup_unavailable(steps, snapshot)
            unavailable = availability[scope]
            if unavailable:
                item.update(disposition="not_executable", reason_code=unavailable.get("error_code") or "operation_unavailable")
            elif key == "account_completion" and not plan["missing_steps"]:
                item.update(disposition="not_executable", reason_code="completion_blocked" if plan["blocked"] else "already_satisfied")
            elif key == "password_setup" and any(value.get("step") == "password" for value in plan["blocked"]):
                item.update(disposition="not_executable", reason_code="password_setup_blocked")
        elif key == "codex_retry":
            from core.codex import operation_service
            if "codex" not in availability:
                unavailable = operation_service._deployment_unavailable(snapshot)
                enabled, _reason = operation_service._feature_ready(snapshot)
                availability["codex"] = unavailable, enabled
            unavailable, enabled = availability["codex"]
            if unavailable or not enabled:
                item.update(disposition="not_executable", reason_code=(unavailable or {}).get("error_code") or "operation_unavailable")
        prepared.append(item)
    return prepared


def preflight_many(targets: Sequence[Mapping], *, operation_key: str, settings: Mapping, conn) -> list[dict]:
    context = {**settings, "operation_key": operation_key}
    if "config_snapshot" not in context:
        context["config_snapshot"] = dict(settings)
    now = datetime.now(timezone.utc).isoformat()
    return [{"target_id": item["target"].get("id") or item["target"].get("target_id"),
             "status": "not_executable" if item["disposition"] == "not_executable" else item["disposition"],
             "reason_code": item["reason_code"], "checked_at": now, "blocker_run_id": item.get("blocker_run_id")}
            for item in prepare_many(targets, context=context, conn=conn, preflight_only=True)]


def _task_data(key: str, item: Mapping, context: Mapping) -> dict:
    parameters = normalize_parameters(key, context.get("parameters"))
    snapshot = _settings(context)
    data = {"bulk_target_round_id": _target_round_id(item["target"])}
    if key == "plan_check":
        data.update(timezone_offset_min=str(parameters.get("timezone_offset_min", "-")), countries=list(snapshot.get("countries") or []), proxy_source="pool")
    elif key in {"password_setup", "twofa_setup"}:
        data.update(steps=["password" if key == "password_setup" else "twofa"], task_trigger="manual_bulk", force_password_reset=False, force_twofa_change=False)
    elif key == "account_completion":
        plan = item["plan"]
        data.update(planned_steps=list(plan["missing_steps"]), configured_steps=list(plan["configured_steps"]), required_steps=list(plan["required_steps"]), blocked=list(plan["blocked"]), task_trigger="manual_bulk")
    return data


def submit_chunk(conn, targets: Sequence[Mapping], context: Mapping) -> list[dict]:
    """调用者持 control/target/account 锁；本函数不提交事务、不唤醒或执行远端。"""
    key, snapshot = _key(context), _settings(context)
    normalize_parameters(key, context.get("parameters"))
    prepared = prepare_many(targets, context=context, conn=conn)
    receipts = []
    fresh = [item for item in prepared if item["disposition"] == "ready" and not item["target"].get("source_task_id")]
    fresh_receipts = _submit_fresh(conn, fresh, context) if fresh else {}
    for item in prepared:
        target = item["target"]
        receipt = {"target_round_id": _target_round_id(target), "disposition": item["disposition"], "reason_code": item["reason_code"],
                   "blocker_run_id": item.get("blocker_run_id"), "task_id": None, "run_id": None, "step_key": key, "relation": "owned_root", "generation": 1}
        if item["disposition"] != "ready":
            receipt["disposition"] = "waiting_account" if item["disposition"] == "waiting_account" else "not_executed"
            receipts.append(receipt)
            continue
        if not target.get("source_task_id"):
            receipts.append(fresh_receipts[_target_round_id(target)])
            continue
        try:
            with conn.transaction():
                account = item["account"]
                data = _task_data(key, item, context)
                source_task_id = target.get("source_task_id")
                if key == "plan_check":
                    from core.storage import db_legacy
                    if not db_legacy._claim_account_stage(int(account["id"]), "plan_check", {
                        "plan_check_status": "queued", "plan_check_trigger": "manual_bulk",
                        "plan_check_queued_at": datetime.now(timezone.utc).isoformat(),
                        "plan_check_started_at": None, "plan_check_deadline_at": None,
                        "plan_check_completed_at": None, "plan_check_error": None,
                    }, conn=conn):
                        raise _ItemWaiting("plan_check_busy")
                if source_task_id:
                    run = store.retry_runtime_task(int(source_task_id), trigger="manual_bulk_retry", data={**data, "config_snapshot": snapshot}, conn=conn)
                    submitted = {"accepted": True, "task_id": int(source_task_id), "run_id": int(run["id"])}
                else:
                    submitted = task_gateway.submit_durable_operation(
                        task_type=key, account_id=int(account["id"]), email=str(account["email"]), trigger="manual_bulk",
                        source_system="webui_runtime" if key in {"password_setup", "twofa_setup", "account_completion"} else "native_operations",
                        source_id=f"bulk:{context['batch_id']}:{target.get('canonical_target_id') or target.get('member_target_id') or _target_round_id(target)}:{key}", resource_family="completion_coordinator" if key == "account_completion" else "openai_interactive",
                        data=data, config_snapshot=snapshot, config_allowlist=tuple(snapshot), dispatch=False, conn=conn,
                    )
                if not submitted.get("accepted"):
                    raise _ItemRejected(submitted)
                now = datetime.now(timezone.utc).isoformat()
                if key == "plan_check":
                    records.patch_row(records.ACCOUNTS, int(account["id"]), changes={"plan_check_status": "queued", "plan_check_ok": False,
                        "plan_check_trigger": "manual_bulk", "plan_check_queued_at": now, "plan_check_started_at": None,
                        "plan_check_deadline_at": None, "plan_check_completed_at": None, "plan_check_error": None, "updated_at": now}, conn=conn)
                elif key == "codex_retry":
                    changes = {"codex_execution_status": "queued", "codex_active_run_id": submitted["run_id"], "updated_at": now}
                    if account.get("codex_status") != "success" and account.get("codex_credential_state") not in {"valid", "pending_confirmation"}:
                        changes["codex_status"] = "retrying"
                    records.patch_row(records.ACCOUNTS, int(account["id"]), changes=changes, conn=conn)
                receipt.update(disposition="idempotent_owned" if submitted.get("reused") else "created", task_id=submitted["task_id"], run_id=submitted["run_id"], reason_code=None)
        except _ItemWaiting as exc:
            receipt.update(disposition="waiting_account", reason_code=str(exc))
        except _ItemRejected as exc:
            submitted = exc.result
            receipt.update(disposition="waiting_account" if submitted.get("busy") else "not_executed",
                           reason_code="account_busy" if submitted.get("busy") else submitted.get("error_code") or "operation_rejected",
                           blocker_run_id=submitted.get("run_id"))
        except (LookupError, ValueError):
            receipt.update(disposition="not_executed", reason_code="operation_precondition_changed")
        receipts.append(receipt)
    return receipts


def _submit_fresh(conn, items: Sequence[Mapping], context: Mapping) -> dict[int, dict]:
    """五功能共用集合写入；正常路径 SQL 数量不随目标数增长。"""
    import json
    key, snapshot = _key(context), _settings(context)
    eligible = list(items)
    output = {}
    now = datetime.now(timezone.utc).isoformat()
    if key == "plan_check":
        from core.storage import db_legacy
        guard, guard_params = db_legacy._stage_claim_guard("plan_check")
        claimed = records.patch_rows_where_returning(records.ACCOUNTS, changes={
            "plan_check_status": "queued", "plan_check_ok": False, "plan_check_trigger": "manual_bulk",
            "plan_check_queued_at": now, "plan_check_started_at": None, "plan_check_deadline_at": None,
            "plan_check_completed_at": None, "plan_check_error": None, "updated_at": now,
        }, where=f"id=ANY(%s) AND ({guard})", params=([int(item["account"]["id"]) for item in eligible], *guard_params), conn=conn)
        allowed = {int(row["id"]) for row in claimed}
        for item in eligible:
            if int(item["account"]["id"]) not in allowed:
                output[_target_round_id(item["target"])] = {
                    "target_round_id": _target_round_id(item["target"]), "disposition": "waiting_account", "reason_code": "plan_check_busy",
                    "blocker_run_id": None, "task_id": None, "run_id": None, "step_key": key, "relation": "owned_root", "generation": 1}
        eligible = [item for item in eligible if int(item["account"]["id"]) in allowed]
    specs = []
    for item in eligible:
        target, account = item["target"], item["account"]
        specs.append({"task_type": key, "account_id": int(account["id"]), "email": str(account["email"]),
            "source_system": "webui_runtime" if key in {"password_setup", "twofa_setup", "account_completion"} else "native_operations",
            "source_id": f"bulk:{context['batch_id']}:{target.get('canonical_target_id') or target.get('member_target_id') or _target_round_id(target)}:{key}",
            "resource_family": "completion_coordinator" if key == "account_completion" else "openai_interactive",
            "data": {**_task_data(key, item, context), "config_snapshot": snapshot}})
    submitted = store.create_runtime_tasks_many(specs, conn=conn)
    for item, receipt in zip(eligible, submitted, strict=True):
        target_id = _target_round_id(item["target"])
        output[target_id] = {"target_round_id": target_id, "disposition": "idempotent_owned" if receipt.get("reused") else "created",
            "task_id": receipt["task_id"], "run_id": receipt["run_id"], "reason_code": None, "blocker_run_id": None,
            "step_key": key, "relation": "owned_root", "generation": 1}
    if key == "codex_retry" and eligible:
        # 账号队列投影与Run同事务，资产态及旧成功结论独立保存。
        changes = [{"account_id": int(item["account"]["id"]), "run_id": receipt["run_id"]} for item, receipt in zip(eligible, submitted, strict=True)]
        with conn.cursor() as cur:
            cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} a
              SET codex_execution_status='queued',codex_active_run_id=s.run_id,
                  codex_status=CASE WHEN a.codex_status='success' OR a.codex_credential_state IN ('valid','pending_confirmation')
                    THEN a.codex_status ELSE 'retrying' END,
                  data=a.data || %s::jsonb
              FROM jsonb_to_recordset(%s::jsonb) s(account_id BIGINT,run_id BIGINT) WHERE a.id=s.account_id""",
              (json.dumps({"updated_at": now}), json.dumps(changes)))
    return output


def retry_many(conn, targets: Sequence[Mapping], context: Mapping) -> list[dict]:
    return submit_chunk(conn, targets, context)
