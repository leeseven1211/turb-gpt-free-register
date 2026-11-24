"""任务中心普通原生重跑的集合预检和事务受理。"""
from __future__ import annotations

import json
from collections.abc import Mapping

from core.accounts import operation_settings
from core.accounts.completion import completion_plan
from core.accounts.liveness import service as liveness
from core.accounts.plans import service as plans
from core.codex import operation_service as codex
from core.operations import run_log, task_gateway
from core.storage import records
from core.storage.operations import store


def _data(task: Mapping) -> dict:
    raw = task.get("data")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _latest(task: Mapping) -> dict:
    runs = task.get("runs") or []
    return dict(runs[-1]) if runs else {}


def _settings_key(value) -> str:
    return json.dumps(value or {}, sort_keys=True, ensure_ascii=False, default=str)


def _reply(payload: Mapping) -> tuple[dict, int]:
    result = dict(payload)
    result.setdefault("ok", bool(result.get("accepted", True)))
    status = 409 if result.get("busy") else (
        202 if result.get("accepted", result["ok"]) else 503 if result.get("unavailable") else 409
    )
    return result, status


def accept_retries(tasks: dict[int, dict], *, excluded=(), request_key=None, operation_logger=None) -> dict:
    """只接管已知原生 retry handler；领域扩展仍由原分发入口负责。"""
    if request_key and len(request_key) > 128:
        return {}
    from core.operations import action_service

    handlers = {
        task_gateway.default_operation_retry: "default",
        action_service.retry_runtime_task: "runtime",
        plans._retry_plan_operation: "plan",
        liveness._retry_live_check_operation: "live",
        liveness._retry_token_refresh_operation: "refresh",
        codex._retry_operation_action: "codex",
    }
    selected, output = {}, {}
    for task_id, task in tasks.items():
        if task_id in excluded or task.get("_managed_target_round_id"):
            continue
        if (task_gateway.operation_is_deactivated(task)
                or str(task.get("status") or "").strip().lower() in store._ACTIVE_RUN_STATUSES):
            continue
        handler = task_gateway.operation_action(
            str(task.get("task_type") or ""), "retry", source_system=str(task.get("source_system") or ""),
        )
        kind = handlers.get(handler)
        if kind is None:
            # 单项分发也把未注册的原生Codex交给它自己的重试服务。
            if (handler is None and task.get("source_system") == "native_operations"
                    and task.get("task_type") == "codex_retry" and _latest(task).get("id")):
                kind = "codex"
            else:
                continue
        selected[task_id] = (task, kind)
    if not selected:
        return output
    specs, kinds = [], {}
    logger = operation_logger or action_service.action_logger
    try:
        with store._connect() as conn:
            account_ids = sorted({int(task.get("account_id") or 0) for task, _ in selected.values()})
            account_ids = [value for value in account_ids if value > 0]
            accounts = {}
            if account_ids:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT * FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s) ORDER BY id",
                        (account_ids,),
                    )
                    accounts = {row["id"]: records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()}
            codex_accounts = [int(task.get("account_id") or 0) for task, kind in selected.values() if kind == "codex"]
            active = {}
            if codex_accounts:
                with conn.cursor() as cur:
                    cur.execute(f"""SELECT id,task_id,account_id,status FROM {store._table('operation_runs')}
                        WHERE account_id=ANY(%s) AND resource_family='openai_interactive'
                          AND status IN ('queued','running','cancelling','settling','stopping')
                        ORDER BY id DESC""", (codex_accounts,))
                    for row in cur.fetchall():
                        active.setdefault(row["account_id"], dict(row))
            shared = {}
            job_ids = sorted({int(_data(task).get("source_job_id") or 0)
                for task, kind in selected.values()
                if kind == "runtime" and task.get("task_type") == "registration_resume"})
            job_ids = [value for value in job_ids if value > 0]
            if job_ids:
                shared["registration_sources"] = {int(job["id"]): job for job in records.list_rows(
                    records.JOBS, where="id=ANY(%s)", params=(job_ids,), conn=conn)}
            for task_id, (task, kind) in selected.items():
                account = accounts.get(int(task.get("account_id") or 0))
                if kind == "runtime" and store._account_is_deactivated(account):
                    output[task_id] = _reply({"accepted": False, "deactivated": True, "error": "账号已废号，不能重跑"})
                    continue
                try:
                    data, unavailable = _prepare(task, kind, account, active, shared)
                except Exception as exc:
                    logger.exception("任务中心重试预检失败：task_id=%s type=%s", task_id, task.get("task_type"))
                    output[task_id] = ({"ok": False, "error": f"重试入口异常：{type(exc).__name__}: {exc}"}, 503)
                    continue
                if unavailable:
                    output[task_id] = _reply(unavailable)
                    continue
                specs.append({"task_id": task_id, "data": data, "trigger": "manual_retry",
                    "codex_state": kind == "codex"})
                kinds[task_id] = kind
            if specs:
                from core.storage.operations.bulk_retry_tasks import retry_tasks_many
                replies = retry_tasks_many(conn, specs)
            else:
                replies = {}
    except Exception:
        logger.exception("任务中心原生任务批量重跑事务失败")
        output.update({task_id: ({"ok": False, "error": "重试入口异常，请刷新任务状态后重试"}, 503)
            for task_id in selected if task_id not in output})
        return output
    accepted = []
    for task_id, raw in replies.items():
        payload = dict(raw)
        output[task_id] = _reply(payload)
        if payload.get("accepted"):
            accepted.append(payload)
    # 文件日志与进程内调度在事实事务提交后执行，不扩大数据库事务数量。
    for payload in accepted:
        run_log.append(payload.get("log_file"), level="INFO", message="任务已加入队列",
            task_id=payload["task_id"], run_id=payload["run_id"], stage="queued", event_type="run.queued",
            event_id=payload.get("event_id"), event_uuid=payload.get("event_uuid"),
            created_at=payload.get("event_created_at"))
        if kinds[payload["task_id"]] == "codex":
            run_log.append(payload.get("log_file"), level="INFO", message="Codex operation 作为新 Run 进入队列",
                task_id=payload["task_id"], run_id=payload["run_id"], stage="queued", event_type="retry.scheduled")
    if accepted:
        if any(kinds[payload["task_id"]] == "codex" for payload in accepted):
            codex.start_dispatcher()
        task_gateway.notify_dispatch()
    return output


def _prepare(task, kind, account, active, shared):
    data = _data(task)
    updates = {"retry_action": "manual_retry"}
    if kind == "runtime":
        if task.get("task_type") == "registration_resume":
            from core.registration import service as registration
            source_id = int(data.get("source_job_id") or 0)
            scope = ("registration_resume", source_id)
            if scope not in shared:
                source = shared.get("registration_sources", {}).get(source_id)
                shared[scope] = registration.registration_deployment_unavailable(
                    registration.registration_options_for_job(source))
            return updates, shared[scope]
        key = ("runtime_settings", _settings_key(data.get("config_snapshot")))
        if key not in shared:
            shared[key] = operation_settings.completion_settings_from_snapshot(data.get("config_snapshot"))
        settings = shared[key]
        if task.get("task_type") == "account_completion":
            steps = set(completion_plan(account, settings)["missing_steps"])
            scope = ("completion", key, tuple(sorted(steps)))
            if scope not in shared:
                shared[scope] = operation_settings.completion_deployment_unavailable(steps, settings)
        else:
            from core.runtime.capabilities import account_setup_unavailable
            steps = set(data.get("steps") or {"password", "plan_check", "twofa"})
            force_twofa = bool(data.get("force_twofa_change"))
            force_password = task.get("task_type") == "password_change" or bool(data.get("force_password_reset"))
            scope = ("setup", key, tuple(sorted(steps)), force_twofa, force_password)
            if scope not in shared:
                shared[scope] = account_setup_unavailable(steps, settings,
                    force_twofa_change=force_twofa, force_password_reset=force_password)
        return updates, shared[scope]
    if kind == "plan":
        snapshot = dict((_latest(task).get("data") or {}).get("config_snapshot") or {})
        if "auto_refresh_at_enabled" not in snapshot:
            if "plan_current" not in shared:
                shared["plan_current"] = task_gateway.normalize_config_snapshot(
                    plans.get_config_snapshot(), allowlist=plans.PLAN_CONFIG_ALLOWLIST)
            for key in ("auto_refresh_at_enabled", *plans.LIVE_CONFIG_ALLOWLIST):
                if key not in snapshot and key in shared["plan_current"]:
                    snapshot[key] = shared["plan_current"][key]
            updates["config_snapshot"] = snapshot
        return updates, None
    if kind == "live":
        snapshot = data.get("config_snapshot") if isinstance(data.get("config_snapshot"), dict) else None
        driver = data.get("driver") or liveness._snapshot_value(snapshot, "live_check_driver")
        scope = ("live", str(driver), _settings_key(snapshot))
        if scope not in shared:
            shared[scope] = liveness.deployment_unavailable(
                force_refresh=False, driver=driver, config_snapshot=snapshot)
        return updates, shared[scope]
    if kind == "refresh":
        if "refresh_current" not in shared:
            snapshot = task_gateway.normalize_config_snapshot(
                liveness.get_config_snapshot(), allowlist=liveness.LIVE_CONFIG_ALLOWLIST)
            driver = liveness._resolve_refresh_driver(config_snapshot=snapshot)
            shared["refresh_current"] = (snapshot, driver,
                liveness.deployment_unavailable(force_refresh=True, driver=driver, config_snapshot=snapshot))
        snapshot, driver, unavailable = shared["refresh_current"]
        return {**updates, "force_refresh": True, "refresh_driver": liveness._refresh_driver_request(driver),
            "config_snapshot": snapshot, "proxy_source": snapshot.get("refresh_at_proxy_mode") or ""}, unavailable
    if kind == "codex":
        if store._account_is_deactivated(account):
            return {}, {"accepted": False, "deactivated": True, "error": "账号已废号，不能重跑 Codex"}
        blocker = active.get(int(task.get("account_id") or 0))
        if blocker:
            return {}, {"accepted": False, "busy": True, "error": "该账号已有排队或运行中的账号操作",
                "task_id": blocker["task_id"], "run_id": blocker["id"], "status": blocker["status"]}
        if "codex_current" not in shared:
            snapshot = codex._config_snapshot(driver_override=None)
            unavailable = codex._deployment_unavailable(snapshot)
            if not unavailable:
                enabled, reason = codex._feature_ready(snapshot)
                if not enabled:
                    unavailable = {"accepted": False, "feature": "codex_retry", "error": reason, "unavailable": True}
            shared["codex_current"] = snapshot, unavailable
        snapshot, unavailable = shared["codex_current"]
        return {"config_snapshot": snapshot}, unavailable
    return updates, None
