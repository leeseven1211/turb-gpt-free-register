"""C2A 巡检定向修复集合入队，远端执行继续由 manual_sync handler 持有。"""
from __future__ import annotations

import hashlib

from psycopg.rows import dict_row

from core.integrations.c2a import client, manual_sync
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import bulk_submission, common, schema


def queue_targets(targets, *, expected_backend: str, trigger: str):
    """按输入返回受理或本地预检异常，一波新 Task/Run 在同一事务中持久化。"""
    if not targets:
        return []
    results = [None] * len(targets)
    prepared = []
    backend = str(expected_backend or "").strip()
    backend_error = None
    try:
        current_backend = client.configured_backend_identity()
    except Exception as exc:
        current_backend, backend_error = None, exc
    for index, (account, remote_id, idempotency_key) in enumerate(targets):
        try:
            account_id, email = manual_sync._account_reference(account)
            target_id = client.validate_remote_account_id(remote_id)
            if not backend:
                raise manual_sync.C2AReimportError("c2a_config_invalid", "定向修复缺少原 C2A 目标摘要")
            if backend_error is not None:
                raise backend_error
            if current_backend != backend:
                raise manual_sync.C2AReimportError("c2a_backend_changed", "C2A 目标已变化，未入队原目标修复")
            key = str(idempotency_key or "").strip()
            if not key:
                raise manual_sync.C2AReimportError("c2a_repair_request_invalid", "定向修复缺少稳定的提交标识")
            digest = hashlib.sha256(f"{backend}\n{target_id}\n{account_id}\n{key}".encode()).hexdigest()
            prepared.append((index, {
                "account_id": account_id, "email": email,
                "task_type": manual_sync.TASK_TYPE, "resource_family": manual_sync.RESOURCE_FAMILY,
                "source_id": f"c2a-repair:{digest}", "trigger": trigger,
                "data": {"backend_identity": backend, "remote_account_id": target_id, "monitor_managed": True},
            }))
        except Exception as exc:
            results[index] = exc
    if not prepared:
        return results
    manual_sync.register_handler()
    records.init()
    schema.init_operation_schema()
    account_ids = sorted({spec["account_id"] for _, spec in prepared})
    with common._connect() as conn, conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT * FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            (account_ids,),
        )
        accounts = {int(row["id"]): records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()}
        cur.execute(
            f"""SELECT t.source_id,t.id AS task_id,t.account_id,t.email_snapshot AS email,
                       r.id AS run_id,r.status
                FROM {common._table('operation_tasks')} t
                JOIN LATERAL (SELECT id,status FROM {common._table('operation_runs')}
                    WHERE task_id=t.id ORDER BY run_no DESC,id DESC LIMIT 1) r ON TRUE
                WHERE t.source_system='native_operations' AND t.source_id=ANY(%s)""",
            ([spec["source_id"] for _, spec in prepared],),
        )
        existing = {row["source_id"]: dict(row) for row in cur.fetchall()}
        cur.execute(
            f"""SELECT id AS run_id,task_id,account_id,status
                FROM {common._table('operation_runs')}
                WHERE account_id=ANY(%s) AND resource_family=%s AND status=ANY(%s)
                ORDER BY account_id,id""",
            (account_ids, manual_sync.RESOURCE_FAMILY, list(common._ACTIVE_RUN_STATUSES)),
        )
        active = {int(row["account_id"]): dict(row) for row in cur.fetchall()}
        fresh, indexes, scheduled = [], [], {}
        for index, spec in prepared:
            account_id = spec["account_id"]
            current = accounts.get(account_id)
            if common._account_is_deactivated(current):
                results[index] = {
                    "accepted": False, "busy": False, "deactivated": True,
                    "error_code": "account_deactivated", "error": "账号已废号，禁止创建任务",
                }
                continue
            prior = existing.get(spec["source_id"])
            if prior is not None:
                results[index] = {
                    **prior, "accepted": True, "reused": True, "busy": prior["status"] in common._ACTIVE_RUN_STATUSES,
                    "source_system": "native_operations", "trigger": trigger,
                }
                continue
            if account_id in active:
                results[index] = {**active[account_id], "accepted": False, "busy": True}
                continue
            # 同账号不同目标在原逐项入口也只能受理第一个；相同请求交由共享原语复用。
            if account_id in scheduled and scheduled[account_id] != spec["source_id"]:
                results[index] = {"accepted": False, "busy": True}
                continue
            scheduled[account_id] = spec["source_id"]
            fresh.append(spec)
            indexes.append(index)
        queued = bulk_submission.create_specs(fresh, conn=conn)
        for index, result in zip(indexes, queued):
            results[index] = result
    if any(not result["reused"] for result in queued):
        task_gateway.notify_dispatch()
    return results
