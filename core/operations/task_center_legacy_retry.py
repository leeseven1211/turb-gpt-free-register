"""任务中心历史账号来源的集合预检和新任务重建。"""
from __future__ import annotations

import json
import uuid

from core import db
from core.accounts import bulk_submission as account_submission
from core.operations import run_log, task_gateway
from core.storage import records
from core.storage.email.bulk_mutations import _patch_many
from core.storage.operations import bulk_submission, legacy_task_store, store

_OPERATIONS = {
    "live_check": "live", "token_refresh": "token", "plan_check": "plan",
    "account_setup_retry": "setup", "password_setup": "password", "password_change": "password_change",
    "twofa_setup": "twofa", "twofa_change": "twofa_change", "account_completion": "complete",
}
_CHUNK_SIZE = 500


def _reply(payload):
    result = dict(payload)
    result.setdefault("ok", bool(result.get("accepted")))
    return result, 409 if result.get("busy") else 202 if result.get("accepted") else 400


def select_retries(tasks, *, excluded=()):
    """按单项入口优先级纯分类，并保留用户输入顺序。"""
    from core.operations import action_service

    selected = {}
    for task_id, task in tasks.items():
        if (task_id in excluded or task.get("_managed_target_round_id")
                or task_gateway.operation_is_deactivated(task)
                or task.get("status") in action_service.active_operation_statuses):
            continue
        handler = task_gateway.operation_action(task.get("task_type") or "", "retry",
            source_system=task.get("source_system"))
        if (handler is not None or task.get("source_system") == "native_operations" and task.get("task_type") == "codex_retry"
                or action_service._registration_retry_job_id(task) is not None):
            continue
        runs = task.get("runs") or []
        last = runs[-1] if runs else {}
        source_id = str(last.get("source_id") or "")
        if last.get("source_system") == "account_action_tasks" and source_id.isdigit():
            selected[task_id] = int(source_id)
    return selected


def read_sources(conn, selected):
    if not selected:
        return {}
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {legacy_task_store._table('account_action_tasks')} WHERE id=ANY(%s)",
            (sorted(set(selected.values())),))
        sources = {int(row["id"]): legacy_task_store._decode_row(dict(row)) for row in cur.fetchall()}
    return {task_id: sources.get(source_id) for task_id, source_id in selected.items()}


def classify_sources(sources, accounts):
    regular, mail, refresh, replies = {}, {}, {}, {}
    for task_id, row in sources.items():
        if not row:
            replies[task_id] = ({"ok": False, "error": "任务实例不存在"}, 404)
        elif row.get("status") in {"queued", "running"}:
            replies[task_id] = ({"ok": False, "error": "任务仍在执行"}, 409)
        elif not (account := accounts.get(int(row.get("account_id") or 0))):
            replies[task_id] = ({"ok": False, "error": "关联账号不存在"}, 404)
        elif db.account_is_deactivated(account):
            replies[task_id] = ({"ok": False, "deactivated": True, "error": "账号已废号，不能重跑"}, 409)
        elif row["task_type"] == "deactivation_mail":
            mail[task_id] = row
        elif row["task_type"] == "codex_token_refresh":
            refresh[task_id] = row
        elif row["task_type"] in {*_OPERATIONS, "extract_link", "codex_retry"}:
            regular[task_id] = row
        else:
            replies[task_id] = ({"ok": False, "error": "该任务类型暂不支持重跑"}, 400)
    return {"regular": regular, "mail": mail, "refresh": refresh, "replies": replies}


def _stage(spec):
    kind = spec["task_type"]
    return ("plan_check" if kind == "plan_check" else "live_check"
        if kind in {"live_check", "token_refresh"} else "extract_link" if kind == "extract_link" else None)


def _stage_busy(stage):
    return _reply({"accepted": False, "busy": True, "error": "该账号正在查询套餐" if stage == "plan_check"
        else "该账号正在提链中" if stage == "extract_link" else "该账号正在查活"})


def create_specs_many(conn, specifications):
    """大集合每条写入语句最多 500 项，所有分块仍属于调用方同一事务。"""
    rows, created = list(specifications), []
    for offset in range(0, len(rows), _CHUNK_SIZE):
        created.extend(bulk_submission.create_specs(rows[offset:offset + _CHUNK_SIZE], conn=conn))
    return created


def prepare_regular(conn, tasks, accounts, logger):
    """完成原 submit 资格检查；阶段被拒绝项不能预占资源族。"""
    from core.storage import db_legacy

    output, specs, captures = {}, {}, {}
    if not tasks:
        return {"specs": specs, "replies": output}
    account_ids = sorted({int(row["account_id"]) for row in tasks.values()})
    with conn.cursor() as cur:
        # 原普通 submit 唯一约束仅覆盖四状态，不增加 waiting/stopping 限制。
        cur.execute(f"""SELECT account_id,resource_family,task_id,id AS run_id,status
            FROM {store._table('operation_runs')} WHERE account_id=ANY(%s)
              AND status IN ('queued','running','cancelling','settling') ORDER BY id DESC""", (account_ids,))
        active = {}
        for row in cur.fetchall():
            active.setdefault((row["account_id"], row["resource_family"]), dict(row))
        complete = {int(row["account_id"]) for row in tasks.values() if row["task_type"] == "account_completion"}
        registration_ids, registration_emails = set(), set()
        if complete:
            emails = [str(accounts[number].get("email") or "").strip().lower() for number in complete if number in accounts]
            cur.execute(f"""SELECT account_id,lower(btrim(email)) AS email FROM {records._qualified(records.JOBS)}
                WHERE COALESCE(NULLIF(job_type,''),'registration') IN ('registration','registration_resume')
                  AND status=ANY(%s) AND (account_id=ANY(%s) OR lower(btrim(email))=ANY(%s))""",
                (["pending", "queued", "running", "stopping", "cancelling", "settling", "waiting", "debug_paused"],
                 sorted(complete), emails))
            for row in cur.fetchall():
                registration_ids.add(row["account_id"])
                registration_emails.add(row["email"])
        for task_id, task in tasks.items():
            account = accounts.get(int(task["account_id"]))
            if not account:
                output[task_id] = ({"ok": False, "error": "关联账号不存在"}, 404)
                continue
            family = "completion_coordinator" if task["task_type"] == "account_completion" else "openai_interactive"
            blocker = active.get((account["id"], family))
            if blocker:
                output[task_id] = _reply({"accepted": False, "busy": True,
                    "error": "该账号已有排队或运行中的账号操作", **blocker})
                continue
            if task["task_type"] == "account_completion" and (account["id"] in registration_ids
                    or str(account.get("email") or "").strip().lower() in registration_emails):
                output[task_id] = _reply({"accepted": False, "busy": True,
                    "error": "该账号仍有注册任务正在执行，请等待结束后补全账号"})
                continue
            try:
                spec, rejection = _prepare(task, account, captures)
            except Exception as exc:
                logger.exception("历史来源重跑预检失败：task_id=%s", task_id)
                output[task_id] = ({"ok": False, "error": f"重试入口异常：{type(exc).__name__}: {exc}"}, 503)
                continue
            if rejection:
                output[task_id] = _reply(rejection)
            else:
                specs[task_id] = spec
        for stage in ("plan_check", "live_check", "extract_link"):
            candidates = [spec["account_id"] for spec in specs.values() if _stage(spec) == stage]
            if not candidates:
                continue
            guard, params = db_legacy._stage_claim_guard(stage, require_alive=stage == "live_check")
            cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s) AND ({guard})",
                (candidates, *params))
            allowed = {row["id"] for row in cur.fetchall()}
            for task_id, spec in list(specs.items()):
                if _stage(spec) == stage and spec["account_id"] not in allowed:
                    output[task_id] = _stage_busy(stage)
                    specs.pop(task_id)
    return {"specs": specs, "replies": output}


def commit_regular(conn, selected, accounts):
    """仅为统一仲裁选中的赢家集合写入阶段和 Task/Run。"""
    from core.storage import db_legacy

    output, eligible = {}, {}
    with conn.cursor() as cur:
        for stage in ("plan_check", "live_check", "extract_link", None):
            candidates = {task_id: spec for task_id, spec in selected.items() if _stage(spec) == stage}
            if not candidates:
                continue
            allowed = {spec["account_id"] for spec in candidates.values()}
            if stage is not None:
                guard, params = db_legacy._stage_claim_guard(stage, require_alive=stage == "live_check")
                at, rows = db_legacy._now(), []
                for spec in candidates.values():
                    changes = {f"{stage}_trigger": spec["trigger"], f"{stage}_queued_at": at,
                        f"{stage}_started_at": None, f"{stage}_error": None}
                    if stage == "plan_check":
                        changes.update(plan_check_deadline_at=None, plan_check_completed_at=None)
                    elif stage == "live_check":
                        changes.update(live_check_ok=False, live_checked_at=None, live_check_http_status=None)
                    else:
                        changes.update(extract_link_ok=False, extract_link_type=spec["data"]["link_type"],
                            extract_link_completed_at=None, extract_link_message="已入队", extract_link_checked_at=at)
                    rows.append({"account_id": spec["account_id"], "patch": changes})
                allowed = set()
                for offset in range(0, len(rows), _CHUNK_SIZE):
                    cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} account
                        SET {stage}_status='queued',updated_at=%s,data=account.data || item.patch
                        FROM jsonb_to_recordset(%s::jsonb) item(account_id BIGINT,patch JSONB)
                        WHERE account.id=item.account_id AND ({guard}) RETURNING account.id""",
                        (at, json.dumps(rows[offset:offset + _CHUNK_SIZE], ensure_ascii=False), *params))
                    allowed.update(row["id"] for row in cur.fetchall())
            for task_id, spec in candidates.items():
                if spec["account_id"] in allowed:
                    eligible[task_id] = spec
                else:
                    output[task_id] = {"accepted": False, "busy": True, "error": _stage_busy(stage)[0]["error"]}
        created = create_specs_many(conn, eligible.values())
        changes = {}
        for task_id, spec, item in zip(eligible, eligible.values(), created, strict=True):
            output[task_id] = item
            if spec["task_type"] == "codex_retry":
                account = accounts[spec["account_id"]]
                asset, legacy = str(account.get("codex_credential_state") or "").lower(), str(account.get("codex_status") or "").lower()
                status = "success" if asset == "valid" else "pending_confirmation" if asset == "pending_confirmation" else (
                    "deactivated" if asset == "deactivated" else "success" if legacy == "success" else "retrying")
                changes[account["id"]] = {"codex_execution_status": "queued",
                    "codex_active_run_id": item["run_id"], "codex_status": status}
        patches = list(changes.items())
        for offset in range(0, len(patches), _CHUNK_SIZE):
            _patch_many(conn, records.ACCOUNTS, dict(patches[offset:offset + _CHUNK_SIZE]))
        if created:
            cur.execute(f"SELECT id,task_id,log_file FROM {store._table('operation_runs')} WHERE id=ANY(%s)",
                ([row["run_id"] for row in created],))
            logs = list(cur.fetchall())
        else:
            logs = []
    return output, logs


def finish_regular(logs):
    for log in logs:
        run_log.append(log["log_file"], level="INFO", message="任务已加入队列",
            task_id=log["task_id"], run_id=log["id"], stage="queued", event_type="run.queued")


def accept_mail(tasks):
    from core.operations import action_service

    if not tasks:
        return {}
    result = action_service.deactivation_mail_service.enqueue_bulk(
        list(dict.fromkeys(int(row["account_id"]) for row in tasks.values())), trigger="manual_retry")
    replies = {}
    for field in ("started", "busy", "skipped"):
        for item in result.get(field) or []:
            account_id = int(item.get("account_id") or item.get("id") or 0)
            replies[account_id] = _reply({**item, "accepted": field == "started",
                "busy": field == "busy", "error": item.get("error") or item.get("reason")})
    return {task_id: replies.get(int(row["account_id"]),
        ({"ok": False, "error": "没有可扫描的账号"}, 400)) for task_id, row in tasks.items()}


def accept_retries(tasks, *, excluded=(), request_key=None, operation_logger=None):
    from core.operations.task_center_retry_wave import accept_retries as accept_wave
    return accept_wave(tasks, excluded=excluded, request_key=request_key,
        operation_logger=operation_logger, include_native=False)

def _prepare(task, account, captures):
    from core.operations import action_service

    kind = task["task_type"]
    operation = _OPERATIONS.get(kind)
    trigger = "token_refresh_manual_retry" if kind == "token_refresh" else "manual_retry_completion" if kind == "account_completion" else "manual_retry"
    email = str(account.get("email") or "").strip()
    if operation:
        if operation not in captures:
            captures[operation] = account_submission._capture(operation)
        raw, allowlist, settings = captures[operation]
        parameters = {}
        if operation in {"live", "token"}:
            parameters["proxy_source"] = action_service.live_check_service._captured_proxy_source(
                "token-refresh" if operation == "token" else "live-check")
        data, rejected = account_submission._prepare(account, operation=operation, trigger=trigger,
            parameters=parameters, settings=settings, raw_snapshot=raw)
        if data is None:
            return None, {"accepted": False, **rejected, "error": rejected.get("error") or rejected.get("reason") or rejected.get("message")}
        source = "webui_runtime" if operation in {*account_submission._SETUP, "complete"} else "native_operations"
        prefix = "account-completion" if operation == "complete" else "account-setup" if source == "webui_runtime" else "maintenance:" + kind
        return {"task_type": kind, "account_id": account["id"], "email": email,
            "source_system": source, "source_id": f"{prefix}:{account['id']}:{uuid.uuid4().hex}",
            "resource_family": "completion_coordinator" if operation == "complete" else "openai_interactive",
            "trigger": trigger, "data": data, "config_snapshot": raw, "config_allowlist": allowlist}, None
    if kind == "extract_link":
        service = action_service.extract_link_service
        if "extract" not in captures:
            if not service._provider_mode_enabled("legacy", "extract_only"):
                captures["extract"] = None
            else:
                service._cdk(None)
                captures["extract"] = (service.get_config_snapshot(), service._paypal_options(None))
        if captures["extract"] is None:
            return None, {"accepted": False, "error": "虾扯蛋链平台或提取能力已关闭"}
        raw, options = captures["extract"]
        summary = task.get("result_summary") or {}
        selected, _ = service._select_account_link_type(account=account, requested=summary.get("link_type") or None)
        return {"task_type": kind, "account_id": account["id"], "email": email,
            "source_system": "native_operations", "source_id": f"maintenance:extract_link:{account['id']}:{uuid.uuid4().hex}",
            "resource_family": "openai_interactive", "trigger": trigger,
            "data": {"link_type": selected, "payment_options": options},
            "config_snapshot": raw, "config_allowlist": service.EXTRACT_CONFIG_ALLOWLIST}, None
    service = action_service.codex_operation_service
    if "codex" not in captures:
        raw = service._config_snapshot()
        unavailable = service._deployment_unavailable(raw)
        if not unavailable:
            enabled, reason = service._feature_ready(raw)
            if not enabled:
                unavailable = {"accepted": False, "unavailable": True, "feature": "codex_retry", "error": reason}
        captures["codex"] = raw, unavailable
    raw, unavailable = captures["codex"]
    return (None, unavailable) if unavailable else ({"task_type": kind, "account_id": account["id"], "email": email,
        "source_system": "native_operations", "source_id": uuid.uuid4().hex,
        "resource_family": "openai_interactive", "trigger": trigger,
        "data": {}, "config_snapshot": raw, "config_allowlist": tuple(raw)}, None)
