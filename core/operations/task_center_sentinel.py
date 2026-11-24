"""Sentinel 维护重跑按缓存身份集合互斥，不触碰执行期文件租约。"""
from __future__ import annotations

from core.maintenance import sentinel
from core.operations import task_gateway
from core.storage.email.collections import lock_keys
from core.storage.operations import bulk_retry_tasks, common, sentinel_checks


def accept_retries(tasks: dict[int, dict]) -> dict[int, tuple[dict, int]]:
    groups, output = {}, {}
    for task_id, task in tasks.items():
        handler = task_gateway.operation_action(
            task.get("task_type") or "", "retry", source_system=task.get("source_system"))
        if handler is not sentinel._retry_check:
            continue
        if task_gateway.operation_is_deactivated(task) or task.get("status") in common._ACTIVE_RUN_STATUSES:
            continue
        try:
            key = sentinel_checks._key(str((task.get("data") or {}).get("cache_key") or ""))
        except ValueError as exc:
            output[task_id] = ({"accepted": False, "busy": False, "error": str(exc), "ok": False}, 409)
            continue
        groups.setdefault(key, []).append(task_id)
    if not groups:
        return output
    try:
        output.update(_submit_groups(groups))
    except Exception:
        from core.operations import action_service
        action_service.action_logger.exception("Sentinel 批量维护重试受理失败")
        output.update({task_id: ({"ok": False, "accepted": False,
            "error": "重试入口异常，请刷新任务状态后重试"}, 503)
            for members in groups.values() for task_id in members})
    return output


def _submit_groups(groups):
    output = {}
    with common._connect() as conn:
        lock_keys(conn, ["sentinel-maintenance:" + key for key in groups])
        with conn.cursor() as cur:
            cur.execute(f"""SELECT DISTINCT ON (r.data->>'cache_key') r.task_id,r.id AS run_id,r.status,
                    r.data->>'cache_key' AS cache_key
                FROM {common._table('operation_tasks')} task
                JOIN {common._table('operation_runs')} r ON r.task_id=task.id
                WHERE task.task_type='sentinel_maintenance_check'
                  AND r.data->>'cache_key'=ANY(%s)
                  AND r.status=ANY(%s)
                ORDER BY r.data->>'cache_key',r.id DESC""",
                (list(groups), list(common._ACTIVE_RUN_STATUSES)))
            active = {row["cache_key"]: dict(row) for row in cur.fetchall()}
        pending = [(key, member) for key, members in groups.items() if key not in active for member in members]
        results = bulk_retry_tasks.retry_tasks_many(conn, [
            {"task_id": task_id, "trigger": "manual_retry", "data": {"retry_action": "manual_retry"},
             "group_key": key}
            for key, task_id in pending])
        accepted = False
        for key, members in groups.items():
            prior = active.get(key)
            if prior:
                payload = {"accepted": True, "reused": True, "ok": True,
                    "task_id": int(prior["task_id"]), "run_id": int(prior["run_id"]), "status": prior["status"]}
            for task_id in members:
                # 原串行入口在首项排队后复用该缓存的活动 Run；来源 Task 不变更。
                reply = dict(payload if prior else results[task_id])
                reply.setdefault("ok", bool(reply.get("accepted")))
                output[task_id] = reply, 202 if reply.get("accepted") else 409
                accepted = accepted or bool(reply.get("accepted"))
    if accepted:
        task_gateway.notify_dispatch()
    return output
