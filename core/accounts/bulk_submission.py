"""账号执行类批量受理，执行仍由既有领域 handler 持有。"""
from __future__ import annotations

from datetime import datetime
import json
import uuid

from psycopg.rows import dict_row

from core import db
from core.operations import task_gateway
from core.operations.account_receipts import source_prefix
from core.storage import records
from core.storage.operations import bulk_retry_projection, bulk_submission, common, schema

_SETUP = {
    "setup": ("account_setup_retry", {"password", "plan_check", "twofa"}),
    "password": ("password_setup", {"password"}),
    "twofa": ("twofa_setup", {"twofa"}),
    "password_change": ("password_change", {"password"}),
    "twofa_change": ("twofa_change", {"twofa"}),
}
_TASKS = {**{key: value[0] for key, value in _SETUP.items()},
          "complete": "account_completion", "live": "live_check", "token": "token_refresh",
          "plan": "plan_check", "c2a": "c2a_session_reimport"}


def _ids(values, *, strict=False):
    ids, skipped, seen = [], [], set()
    for input_index, raw in enumerate(values or (), 1):
        try:
            if isinstance(raw, (bool, float, dict, list)):
                raise ValueError()
            if strict and isinstance(raw, str) and (
                not 1 <= len(raw) <= 19 or not raw.isascii() or not raw.isdecimal() or raw.startswith("0")
            ):
                raise ValueError()
            value = int(raw)
            if not 0 < value < 2**63:
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            skipped.append(
                {"input_index": input_index, "reason": "账号 ID 必须是正整数", "error_code": "c2a_local_account_id_invalid"}
                if strict else {"id": raw, "reason": "ID 非法", "reason_code": "invalid_target"}
            )
            continue
        if value not in seen:
            ids.append(value)
            seen.add(value)
    return ids, skipped


def _capture(operation):
    if operation in {"live", "token"}:
        from core.accounts.liveness import service
        raw = service.get_config_snapshot()
        snapshot = task_gateway.normalize_config_snapshot(raw, allowlist=service.LIVE_CONFIG_ALLOWLIST)
        return snapshot, tuple(snapshot), snapshot
    if operation == "plan":
        from core.accounts.plans import service
        raw = service.get_config_snapshot()
        snapshot = task_gateway.normalize_config_snapshot(raw, allowlist=service.PLAN_CONFIG_ALLOWLIST)
        return raw, service.PLAN_CONFIG_ALLOWLIST, snapshot
    if operation == "c2a":
        return None, (), {}
    from core.accounts import operation_settings
    from config.account import completion_settings
    raw, allowlist, settings = operation_settings.runtime_execution_settings(completion_settings())
    return raw, allowlist, settings


def _source(task_type, account_id, operation, request_key, trigger):
    if request_key:
        return f"{source_prefix(request_key)}:{task_type}:{trigger}:{account_id}"
    if operation == "c2a":
        return f"c2a-reimport:{uuid.uuid4().hex}"
    prefix = "account-completion" if operation == "complete" else "account-setup" if operation in _SETUP else "maintenance:" + task_type
    return f"{prefix}:{account_id}:{uuid.uuid4().hex}"


def _receipt_details(operation, data):
    snapshot = data.get("config_snapshot") or {}
    result = {"config_snapshot_revision": snapshot.get("config_snapshot_revision")} if snapshot else {}
    if operation in {"live", "token"}:
        from core.accounts.liveness import service
        if operation == "token":
            driver = service._resolve_refresh_driver(data.get("refresh_driver"), config_snapshot=snapshot)
            result.update(token_refresh_driver=driver, refresh_driver=driver,
                          protocol_version=service._refresh_protocol_version(driver))
        else:
            result["live_check_driver"] = data.get("driver")
    return result


def _prepare(account, *, operation, trigger, parameters, settings, raw_snapshot):
    """只做纯内存预检和现有策略解析；不得在这里逐账号访问存储。"""
    task_type = _TASKS[operation]
    email = str(account.get("email") or "").strip()
    if operation == "c2a":
        from core.integrations.c2a import manual_sync
        try:
            manual_sync._account_reference(account)
        except ValueError as exc:
            return None, {"reason": str(exc), "error": str(exc), "error_code": getattr(exc, "code", "c2a_manual_queue_failed"),
                          "submission_failed": True}
        if parameters.get("backend_error"):
            return None, {**parameters["backend_error"], "submission_failed": True}
        return {"backend_identity": parameters["backend_identity"]}, {}
    if not email:
        return None, {"reason": "账号邮箱为空"}
    if db.account_is_deactivated(account):
        return None, {"reason": "账号已废号"}
    if operation in _SETUP:
        from core.accounts.completion import completion_plan
        from core.runtime.capabilities import account_setup_unavailable
        steps = _SETUP[operation][1]
        if operation == "password":
            plan = completion_plan(account, settings)
            blocked = [item for item in plan.get("blocked") or [] if item.get("step") == "password"]
            if blocked:
                return None, {"reason": blocked[0].get("reason") or "账号密码补全当前不可用", "blocked": blocked, "plan": plan}
        unavailable = account_setup_unavailable(
            steps, settings, force_twofa_change=operation == "twofa_change",
            force_password_reset=operation == "password_change",
        )
        if unavailable:
            return None, {"reason": unavailable.get("error") or "账号配置不可用", **unavailable}
        return {"steps": sorted(steps), "task_trigger": trigger,
                "force_password_reset": operation == "password_change", "force_twofa_change": operation == "twofa_change"}, {}
    if operation == "complete":
        from core.accounts.completion import completion_plan
        from core.accounts.operation_settings import completion_deployment_unavailable
        plan = completion_plan(account, settings)
        unavailable = completion_deployment_unavailable(set(plan["missing_steps"]), settings)
        if unavailable:
            return None, {"reason": unavailable.get("error") or "账号补全不可用", "plan": plan, **unavailable}
        if plan["blocked"] and not plan["missing_steps"]:
            return None, {"reason": plan["blocked"][0]["reason"], "blocked": plan["blocked"], "plan": plan}
        if not plan["missing_steps"]:
            return None, {"ready": True, "plan": plan, "message": "账号已满足当前补全配置"}
        return {"planned_steps": list(plan["missing_steps"]), "configured_steps": list(plan["configured_steps"]),
                "required_steps": list(plan.get("required_steps") or plan["configured_steps"]),
                "blocked": list(plan["blocked"]), "task_trigger": trigger}, {"plan": plan}
    if operation in {"live", "token"}:
        from core.accounts.liveness import service
        refresh = operation == "token"
        selected = service._resolve_refresh_driver(parameters.get("driver"), config_snapshot=settings) if refresh else service.resolve_driver(parameters.get("driver"))
        unavailable = service.deployment_unavailable(force_refresh=refresh, driver=selected, config_snapshot=settings)
        if unavailable:
            return None, {"reason": unavailable.get("error") or "操作部署不可用", **unavailable,
                          "submission_failed": True}
        if refresh and not str(account.get("access_token") or "").strip():
            reason = "账号没有现有 access_token，拒绝刷新 AT；请先完成账号注册或执行注册续跑"
            return None, {"reason": reason, "error": reason, "submission_failed": True}
        if refresh and account.get("email_invalid") is True and selected not in {"browser_roxy", "protocol_v3"}:
            selected = "protocol_v2"
        return {"force_refresh": refresh, "driver": None if refresh else selected,
                "refresh_driver": service._refresh_driver_request(selected) if refresh else None,
                "proxy_source": parameters["proxy_source"], "explicit_proxy_requested": False}, {
                    **({"token_refresh_driver": selected, "refresh_driver": selected, "protocol_version": service._refresh_protocol_version(selected)} if refresh else {"live_check_driver": selected}),
                }
    if operation == "plan":
        from config.countries import normalize_plan_check_countries
        from core.accounts.plans import service
        if not str(account.get("access_token") or "").strip() and not bool(settings.get("auto_refresh_at_enabled", True)):
            return None, {"reason": "缺少 access_token"}
        return {"countries": normalize_plan_check_countries(settings.get("countries", [])),
                "timezone_offset_min": str(parameters.get("timezone_offset_min") or "-"),
                "proxy_source": service._country_proxy_source(raw_snapshot)}, {}
    raise ValueError("不支持的账号批量操作")


def submit_accounts(account_ids, *, operation, trigger="manual_bulk", parameters=None, request_key=None):
    operation = str(operation or "").lower()
    if operation not in _TASKS:
        raise ValueError("不支持的账号批量操作")
    if not isinstance(account_ids, (list, tuple)) or not account_ids:
        raise ValueError("account_ids 必须是非空数组")
    if operation != "token" and len(account_ids) > (20 if operation in {"password_change", "twofa_change"} else 500):
        raise ValueError("账号批量操作超过上限")
    ids, skipped = _ids(account_ids, strict=operation == "c2a")
    parameters = dict(parameters or {})
    raw_snapshot, allowlist, settings = _capture(operation)
    captured = task_gateway.normalize_config_snapshot(raw_snapshot, allowlist=allowlist) if raw_snapshot is not None else {}
    task_type = _TASKS[operation]
    family = "completion_coordinator" if operation == "complete" else "openai_interactive"
    source_system = "webui_runtime" if operation in _SETUP or operation == "complete" else "native_operations"
    if operation in {"live", "token"}:
        from core.accounts.liveness import service
        parameters["proxy_source"] = service._captured_proxy_source("token-refresh" if operation == "token" else "live-check")
    elif operation == "c2a":
        from core.integrations.c2a import client
        try:
            parameters["backend_identity"] = client.configured_backend_identity()
        except client.C2AError as exc:
            parameters["backend_error"] = {
                "error_code": exc.code,
                "error": "C2A 配置无效，请检查 API 地址、管理 Key 与请求超时设置",
            }
        except Exception:
            parameters["backend_error"] = {
                "error_code": "c2a_manual_queue_failed", "error": "C2A 重新导入入队失败，请查看服务日志",
            }
    records.init()
    schema.init_operation_schema()
    started, ready, busy, failed = [], [], [], []
    batch = None
    with common._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT * FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s) ORDER BY id FOR UPDATE", (ids,))
        accounts = {int(row["id"]): records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()}
        sources = {value: _source(task_type, value, operation, request_key, trigger) for value in ids}
        # 同一个账号原始请求重发必须先复用原 Run，不会因该 Run 活跃而变 busy。
        prior = {}
        if request_key:
            cur.execute(f"""SELECT t.id AS task_id,t.account_id,t.source_id,t.source_system,t.trigger,
                    t.email_snapshot AS email,t.data,t.status AS task_status,
                    r.id AS run_id,r.status FROM {common._table('operation_tasks')} t
                JOIN LATERAL (SELECT id,status FROM {common._table('operation_runs')}
                    WHERE task_id=t.id ORDER BY run_no,id LIMIT 1) r ON TRUE
                WHERE t.source_system=%s AND t.source_id=ANY(%s)""", (source_system, list(sources.values())))
            prior = {int(row["account_id"]): dict(row) for row in cur.fetchall()}
        cur.execute(f"""SELECT account_id,resource_family,task_id,id AS run_id,status
            FROM {common._table('operation_runs')}
            WHERE account_id=ANY(%s) AND resource_family=%s AND status=ANY(%s)
            ORDER BY account_id,id""", (ids, family, list(common._ACTIVE_RUN_STATUSES)))
        active = {int(row["account_id"]): dict(row) for row in cur.fetchall()}
        registration_ids, registration_emails = set(), set()
        if operation == "complete":
            cur.execute(f"""SELECT account_id,LOWER(BTRIM(email)) AS email FROM {records._qualified(records.JOBS)}
                WHERE status=ANY(%s) AND COALESCE(NULLIF(job_type,''),'registration') IN ('registration','registration_resume')
                  AND (account_id=ANY(%s) OR LOWER(BTRIM(email))=ANY(%s))""",
                (["pending", "queued", "running", "stopping", "cancelling", "settling", "waiting", "debug_paused"],
                 ids, [str(a.get("email") or "").strip().lower() for a in accounts.values()]))
            for row in cur.fetchall():
                if row.get("account_id"):
                    registration_ids.add(int(row["account_id"]))
                registration_emails.add(str(row.get("email") or ""))
        specs, details = [], {}
        for account_id in ids:
            account = accounts.get(account_id)
            if not account:
                skipped.append({"id": account_id, "reason": "账号不存在",
                                **({"error_code": "c2a_local_account_missing"} if operation == "c2a" else {})})
                continue
            email = str(account.get("email") or "").strip()
            if (operation == "complete" and email and not db.account_is_deactivated(account)
                    and (account_id in registration_ids or email.lower() in registration_emails)):
                skipped.append({"id": account_id, "email": email, "error_code": "registration_in_progress",
                                "reason": "该账号仍有注册任务正在执行，请等待结束后补全账号"})
                continue
            data, detail = _prepare(account, operation=operation, trigger=trigger, parameters=parameters, settings=settings, raw_snapshot=raw_snapshot)
            if data is None:
                item = {"id": account_id, "account_id": account_id, "email": email, **detail}
                (ready if detail.get("ready") else failed if detail.get("submission_failed") else skipped).append(item)
                continue
            if account_id in prior:
                owned = prior[account_id]
                if common._task_is_user_deleted({"data": owned.get("data") or {}}):
                    skipped.append({"id": account_id, "reason": "原任务已从任务中心删除，请重新发起操作"})
                else:
                    started.append({"id": account_id, "account_id": account_id, "email": owned["email"], "task_id": owned["task_id"],
                                    "run_id": owned["run_id"], "accepted": True, "reused": True, "busy": False,
                                    "status": owned["status"], "task_type": task_type, "source_system": owned["source_system"],
                                    "source_id": owned["source_id"], "trigger": owned["trigger"],
                                    **_receipt_details(operation, owned.get("data") or {})})
                continue
            if account_id in active:
                item = {"id": account_id, "email": email, "reason": "该账号已有排队或运行中的账号操作", **active[account_id],
                        **({"error_code": "c2a_manual_queue_busy"} if operation == "c2a" else {})}
                busy.append(item)
                if operation != "plan":
                    skipped.append(item)
                continue
            details[account_id] = {**_receipt_details(operation, {**data, "config_snapshot": captured}), **detail}
            specs.append({"task_type": task_type, "account_id": account_id, "email": email,
                          "source_system": source_system, "source_id": sources[account_id], "trigger": trigger,
                          "resource_family": family, "data": data, "config_snapshot": raw_snapshot, "config_allowlist": allowlist})
        if operation in {"live", "token", "plan"} and specs:
            from core.storage import db_legacy
            stage = "plan_check" if operation == "plan" else "live_check"
            guard, guard_args = db_legacy._stage_claim_guard(stage, require_alive=stage == "live_check")
            at = datetime.now().isoformat(timespec="seconds")
            changes = {f"{stage}_status": "queued", f"{stage}_trigger": trigger, f"{stage}_queued_at": at,
                       f"{stage}_started_at": None, f"{stage}_error": None, "updated_at": at}
            if stage == "plan_check":
                changes.update(plan_check_deadline_at=None, plan_check_completed_at=None)
            else:
                changes.update(live_check_ok=False, live_checked_at=None, live_check_http_status=None)
            claimed = records.patch_rows_where_returning(records.ACCOUNTS, changes=changes,
                where=f"id=ANY(%s) AND ({guard})", params=([s["account_id"] for s in specs], *guard_args), conn=conn, id_only=True)
            allowed = {int(row["id"]) for row in claimed}
            for spec in specs:
                if spec["account_id"] not in allowed:
                    item = {"id": spec["account_id"], "email": spec["email"], "reason": "该账号正在查询套餐" if operation == "plan" else "该账号正在查活"}
                    if operation != "plan":
                        skipped.append(item)
                    busy.append(item)
            specs = [spec for spec in specs if spec["account_id"] in allowed]
        if specs:
            batch = bulk_submission.create_batch(conn=conn, task_type=task_type, requested_count=len(ids), trigger=trigger, title=f"批量{task_type}")
            for ordinal, spec in enumerate(specs, 1):
                spec.update(batch_id=int(batch["id"]), batch_ordinal=ordinal)
            created = bulk_submission.create_specs(specs, conn=conn)
            started.extend({**item, "id": item["account_id"], "task_type": task_type, **details[item["account_id"]]} for item in created)
            cur.execute(f"UPDATE {common._table('operation_batches')} "
                        "SET skipped_count=%s,data=data || %s::jsonb WHERE id=%s",
                        (len(skipped), json.dumps({"skipped": skipped, "skipped_count": len(skipped)}, ensure_ascii=False),
                         int(batch["id"])))
            bulk_retry_projection.refresh_batches_many(cur, [int(batch["id"])])
    if any(not item.get("reused") for item in started):
        task_gateway.notify_dispatch()
    order = {account_id: index for index, account_id in enumerate(ids)}
    started.sort(key=lambda item: order[item["account_id"]])
    result = {"accepted": bool(started), "status": "queued", "batch_id": int(batch["id"]) if batch else None,
              "started": started, "started_count": len(started), "ready": ready, "ready_count": len(ready),
              "busy": busy, "busy_count": len(busy), "failed": failed, "failed_count": len(failed),
              "skipped": skipped, "skipped_count": len(skipped)}
    if operation == "c2a":
        result.update(accepted=True, queued=started, queued_count=len(started), updated=[], updated_count=0)
    return result


__all__ = ["submit_accounts"]
