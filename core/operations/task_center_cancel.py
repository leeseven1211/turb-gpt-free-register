"""任务中心特殊排队取消：集合事实提交后执行本地信号及集合账号投影。"""
from __future__ import annotations

import json

from core.codex import operation_service as codex
from core.operations import run_log, task_gateway
from core.storage import records
from core.storage.operations import cancellation, common


def accept_cancellations(tasks: dict[int, dict]) -> dict[int, tuple[dict, int]]:
    """只接管已知取消入口；任务资格与来源规则仍由原分发器决定。"""
    from core.accounts.inspection import service as inspection
    from core.operations import action_service
    from core.maintenance import sentinel

    reasons = {
        task_gateway.default_operation_cancel: "用户手动停止统一 durable operation",
        action_service.cancel_runtime_task: "用户手动停止 WebUI durable operation",
        codex._cancel_operation_action: "用户手动停止 Codex 补跑",
        inspection._cancel_item: "用户手动停止统一 durable operation",
        sentinel._cancel_check: "用户手动停止统一 durable operation",
    }
    selected, output = {}, {}
    for task_id, task in tasks.items():
        if task.get("status") != "queued":
            continue
        handler = task_gateway.operation_action(
            task.get("task_type") or "", "cancel", source_system=task.get("source_system"))
        if handler is None and task.get("source_system") == "native_operations" and task.get("task_type") == "codex_retry":
            handler = codex._cancel_operation_action
        if handler not in reasons:
            continue
        # 普通默认取消已由原集合路径处理；这里补齐受管与领域自定义取消。
        if handler in {task_gateway.default_operation_cancel, action_service.cancel_runtime_task} and not task.get("_managed_target_round_id"):
            continue
        active = next((run for run in reversed(task.get("runs") or [])
                       if str(run.get("status") or "") in action_service.active_operation_statuses), None)
        if not active:
            output[task_id] = ({"ok": True, "state": "empty", "message": "任务没有活跃 attempt"}, 200)
        else:
            selected[task_id] = (task, active, handler)
    if not selected:
        return output
    try:
        with common._connect() as conn:
            replies = cancellation.cancel_runs_many(conn, [
                {"id": int(run["id"]), "expected_status": "queued", "reason": reasons[handler]}
                for _, run, handler in selected.values()])
    except Exception:
        action_service.action_logger.exception("任务中心集合取消事实保存失败")
        output.update({task_id: ({"ok": False, "error": "停止入口异常，请刷新后重试"}, 503)
                       for task_id in selected})
        return output
    codex_updates, parents = [], set()
    for task_id, (task, run, handler) in selected.items():
        reply = replies.get(int(run["id"]))
        if reply is None:
            output[task_id] = ({"ok": False, "error": "执行实例不存在"}, 409)
        elif reply.get("cancel_skipped"):
            output[task_id] = ({"ok": False, "error": reply.get("message") or "任务状态已变化，请刷新后重试"}, 409)
        else:
            state = str(reply["status"])
            output[task_id] = ({"ok": True, "state": state, "run_id": int(run["id"]),
                "running": state != "cancelled", "message": "已记录停止请求，任务将在安全检查点收口"}, 200)
            if handler is codex._cancel_operation_action:
                with codex._LOCAL_TOKENS_LOCK:
                    token = codex._LOCAL_TOKENS.get(int(run["id"]))
                    if token:
                        token.request_local()
                codex_updates.append({"email": str(task.get("email_snapshot") or ""),
                    "run_id": int(run["id"]), "cancelled": state == "cancelled", "position": len(codex_updates)})
                run_log.append(reply.get("log_file"), level="WARNING", message="已请求协作式取消",
                    task_id=task_id, run_id=int(run["id"]), stage="cancelling", event_type="run.cancel_requested")
            if handler is inspection._cancel_item and task.get("parent_task_id"):
                parents.add(int(task["parent_task_id"]))
    # 原 Codex 控制先提交 Run，再单独投影账号；这里保留边界，账号写入按集合执行。
    if codex_updates:
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""WITH input AS (
                SELECT * FROM jsonb_to_recordset(%s::jsonb)
                    item(email TEXT,run_id BIGINT,cancelled BOOLEAN,position INTEGER)
            ), resolved AS (
                SELECT DISTINCT ON (matched.id) matched.id,input.run_id,input.cancelled
                FROM input CROSS JOIN LATERAL (
                    SELECT id FROM {records._qualified(records.ACCOUNTS)}
                    WHERE lower(email)=lower(input.email) LIMIT 1
                ) matched ORDER BY matched.id,input.position DESC
            ) UPDATE {records._qualified(records.ACCOUNTS)} account SET
                codex_execution_status=CASE WHEN item.cancelled THEN 'empty' ELSE 'cancelling' END,
                codex_active_run_id=CASE WHEN item.cancelled THEN NULL ELSE item.run_id END,
                codex_last_run_status=CASE WHEN item.cancelled THEN 'cancelled' ELSE account.codex_last_run_status END,
                codex_status=CASE
                    WHEN account.codex_credential_state='valid' THEN 'success'
                    WHEN account.codex_credential_state='pending_confirmation' THEN 'pending_confirmation'
                    WHEN account.codex_credential_state='deactivated' THEN 'deactivated'
                    WHEN account.codex_status='success' THEN 'success'
                    WHEN item.cancelled THEN 'stopped' ELSE 'retrying' END,
                updated_at=%s,data=account.data || jsonb_build_object('codex_error','用户手动停止 Codex 补跑')
                FROM resolved item WHERE account.id=item.id""",
                (json.dumps(codex_updates), records._now()))
    if parents:
        from core.storage.operations.bulk_retry_reconcile import reconcile_parents_many
        from core.storage.operations.bulk_retry_registration import reconcile_registration_many
        from core.storage.operations.bulk_retry_projection import refresh_batches_many

        with common._connect() as conn, conn.cursor() as cur:
            facts = reconcile_parents_many(cur, sorted(parents), child_task_ids=selected)
            batches = set(facts["batch_ids"])
            batches.update(reconcile_registration_many(cur, parent_run_ids=facts["registration_run_ids"]))
            refresh_batches_many(cur, batches)
    if any(payload.get("ok") and payload.get("state") != "empty" for payload, _ in output.values()):
        task_gateway.notify_dispatch()
    return output
