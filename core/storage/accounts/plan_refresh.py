"""独立套餐任务的单次 AT 恢复记录与受围栏保护的账号写回。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from core.storage.accounts.plan_countries import _transaction
from core.storage import records


def _read(conn, fence):
    from core.storage.operations import store
    with conn.cursor() as cur:
        cur.execute(f"SELECT data->'plan_auto_refresh_at' AS state FROM {store._table('operation_runs')} WHERE id=%s", (fence["run_id"],))
        row = cur.fetchone()
    state = row.get("state") if row else None
    return dict(state) if isinstance(state, dict) and state.get("run_id") == fence["run_id"] else {}


def _write(conn, fence, state):
    from core.storage.operations import store
    with conn.cursor() as cur:
        cur.execute(f"UPDATE {store._table('operation_runs')} SET data=data || %s::jsonb WHERE id=%s",
                    (json.dumps({"plan_auto_refresh_at": state}, ensure_ascii=False), fence["run_id"]))


def begin(account_id, *, fence, reason, budget_seconds):
    """远端认证前记录一次额度；同 Run 恢复不会再次提交认证。"""
    with _transaction(account_id, fence) as (conn, account):
        state = _read(conn, fence)
        if state.get("attempted"):
            return state, False
        state = {"run_id": fence["run_id"], "attempted": True, "ok": False,
                 "status": "running", "reason": reason, "started_at": datetime.now().isoformat(timespec="seconds")}
        _write(conn, fence, state)
        # 单国没有逐国检查点，也需要防止长认证被旧的 120 秒阈值误判失联。
        if not account.get("plan_check_deadline_at"):
            records.patch_row(records.ACCOUNTS, account_id, {
                "plan_check_deadline_at": (datetime.now() + timedelta(seconds=budget_seconds)).isoformat(timespec="seconds")}, conn=conn)
    return state, True


def finish(account_id, *, fence, summary):
    with _transaction(account_id, fence) as (conn, _account):
        state = _read(conn, fence)
        state.update(summary, completed_at=datetime.now().isoformat(timespec="seconds"))
        _write(conn, fence, state)
    return state


def save_liveness(account_id, result, *, fence, expected_email, expected_token):
    """AT 与会话在同事务内保存，旧 worker 或换绑前的响应不能覆盖新账号状态。"""
    from core.storage import accounts
    from core.operations.task_gateway import OperationLeaseLost
    with _transaction(account_id, fence) as (conn, account):
        if account.get("email") != expected_email or str(account.get("access_token") or "") != expected_token:
            raise OperationLeaseLost("套餐刷新 AT 时账号邮箱或 Token 已改变，拒绝旧结果")
        return accounts.update_account_liveness(account_id, result, conn=conn)
