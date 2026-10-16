"""账号多国家套餐结果的行锁合并与逐国检查点。"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from copy import deepcopy
import json
import time
from datetime import datetime
from psycopg.rows import dict_row

from core import postgres_store, record_store
from core.plan_check_countries import now_iso, public_country_results, safe_country_result
from core.plus_promotion import sanitize_promotion_text


@contextmanager
def _transaction(account_id: int, fence: dict | None, *, conn=None):
    """先校验并锁 Run，再锁账号，防止过期 worker 覆盖新执行。"""
    record_store.init()
    manager = nullcontext(conn) if conn is not None else postgres_store.connect(row_factory=dict_row)
    with manager as conn:
        if fence is not None:
            from core.storage import operation
            from core.operations.task_gateway import OperationLeaseLost
            try:
                with conn.cursor() as cur:
                    run = operation.fence_execution(cur, **fence)
                if int(run.get("account_id") or 0) != account_id:
                    raise PermissionError("执行实例与目标账号不匹配")
            except (PermissionError, LookupError) as exc:
                raise OperationLeaseLost("当前执行或账号租约已失效，国家结果未写入") from exc
        account = record_store.get_row(record_store.ACCOUNTS, account_id, conn=conn, for_update=True)
        if account is None:
            raise ValueError("账号已删除，不能保存国家查询结果")
        yield conn, account


def _update(account_id: int, transform, *, fence: dict | None = None, conn=None) -> list[dict]:
    with _transaction(account_id, fence, conn=conn) as (conn, account):
        rows = public_country_results(account.get("plan_check_country_results"))
        rows, extra = transform(rows)
        record_store.patch_row(record_store.ACCOUNTS, account_id, {
            "plan_check_country_results": rows, "updated_at": now_iso(), **extra,
        }, conn=conn)
    return rows


def _read_progress(conn, fence: dict | None) -> dict | None:
    if fence is None:
        return None
    from core.storage import operation
    with conn.cursor() as cur:
        cur.execute(f"SELECT data->'plan_country_progress' AS progress FROM {operation._table('operation_runs')} WHERE id=%s",
                    (int(fence["run_id"]),))
        row = cur.fetchone()
    progress = row.get("progress") if row else None
    # 手动重跑会复制上一 Run.data；执行预算只属于其原 Run。
    if not isinstance(progress, dict) or progress.get("run_id") != int(fence["run_id"]):
        return None
    return deepcopy(progress)


def _write_progress(conn, fence: dict | None, progress: dict) -> None:
    if fence is None:
        return
    from core.storage import operation
    with conn.cursor() as cur:
        cur.execute(f"UPDATE {operation._table('operation_runs')} SET data=data || %s::jsonb WHERE id=%s",
                    (json.dumps({"plan_country_progress": progress}, ensure_ascii=False), int(fence["run_id"])))


def _settle_slice(state: dict, now: float, *, timed_out: bool = False) -> None:
    started, deadline = state.get("wait_slice_started_at"), state.get("wait_slice_deadline_at")
    if started is not None and deadline is not None:
        # 超时切片保留到原截止时刻的退避，立即返回的缺货也不会形成忙循环。
        ended = deadline if timed_out else min(now, deadline)
        state["wait_used"] += max(0.0, ended - started)
        if timed_out:
            state["retry_not_before"] = deadline
    state.update(wait_slice_started_at=None, wait_slice_deadline_at=None)


def initialize_country_checks(account_id: int, countries: list[str], *, fence: dict | None = None,
                              budget_seconds: float = 120, wait_seconds: float = 60,
                              max_attempts: int = 2) -> tuple[list[dict], dict]:
    """冻结本 Run 预算；恢复先结算中断切片，成功国家不会重新排队。"""
    with _transaction(account_id, fence) as (conn, account):
        now = time.time()
        progress = _read_progress(conn, fence)
        previous = {row["country"]: row for row in public_country_results(account.get("plan_check_country_results"))}
        if progress is None:
            progress = {"run_id": int(fence["run_id"]) if fence else None,
                        "deadline_at": now + max(120, budget_seconds), "wait_limit": max(0, wait_seconds),
                        "max_attempts": max_attempts, "countries": {}}
            rows = []
            for country in countries:
                row = dict(previous.get(country) or {"country": country, "result": None})
                row.update(status="queued", error=None)
                for key in ("token_expired", "token_expires_at"):
                    row.pop(key, None)
                rows.append(row)
                progress["countries"][country] = {
                    "wait_used": 0.0, "wait_slice_started_at": None, "wait_slice_deadline_at": None,
                    "http_attempts": 0, "pending": True, "success": False, "history": [],
                    "retry_not_before": 0, "status": "queued",
                }
        else:
            # 国家列表来自 Run 原始快照；调用方的新配置不能扩大本 Run。
            countries = list(progress["countries"])
            rows = [dict(previous.get(country) or {"country": country, "result": None}) for country in countries]
            for row in rows:
                state = progress["countries"][row["country"]]
                _settle_slice(state, now)
                if state["success"]:
                    row.update(status="success", error=None)
                elif state["pending"]:
                    row.update(status="queued", error=None)
        _write_progress(conn, fence, progress)
        record_store.patch_row(record_store.ACCOUNTS, account_id, {
            "plan_check_country_results": rows, "plan_check_countries": countries,
            "plan_check_partial": False, "plan_check_deadline_at": datetime.fromtimestamp(progress["deadline_at"]).isoformat(timespec="seconds"),
            "updated_at": now_iso(),
        }, conn=conn)
    return rows, progress


def begin_country_checks(account_id: int, countries: list[str], *, fence: dict | None = None, budget_seconds: float = 120) -> list[dict]:
    return initialize_country_checks(account_id, countries, fence=fence, budget_seconds=budget_seconds)[0]


def update_country_progress(account_id: int, country: str, progress: dict, *, action: str,
                            fence: dict | None = None, slice_seconds: float = 5,
                            result: dict | None = None, retry: bool = False,
                            retry_delay: float = 0) -> tuple[list[dict], dict]:
    """在相同执行 fence、Run 锁与账号事务内更新预算及结果投影。"""
    with _transaction(account_id, fence) as (conn, account):
        progress = _read_progress(conn, fence) or deepcopy(progress)
        state = progress["countries"][country]
        now = time.time()
        rows = public_country_results(account.get("plan_check_country_results"))
        row = next(row for row in rows if row["country"] == country)
        if action == "wait_start":
            remaining = min(progress["wait_limit"] - state["wait_used"], progress["deadline_at"] - now)
            state.update(wait_slice_started_at=now, wait_slice_deadline_at=now + max(0, min(slice_seconds, remaining)), status="running")
            row.update(status="running", error=None)
        elif action in {"wait_end", "wait_timeout"}:
            _settle_slice(state, now, timed_out=action == "wait_timeout")
            state["status"] = "queued"
            row.update(status="queued", error=None)
        elif action == "http_start":
            if state["http_attempts"] >= progress["max_attempts"]:
                raise ValueError("该国家请求次数已耗尽")
            state["http_attempts"] += 1
            state["status"] = "running"
            row.update(status="running", error=None)
        elif action == "result":
            _settle_slice(state, now)
            result = result or {"ok": False, "error": "该国家查询失败"}
            state.update(success=bool(result.get("ok")), pending=retry, status="success" if result.get("ok") else "queued" if retry else "failed",
                         retry_not_before=now + max(0, retry_delay))
            stamp = result.get("checked_at") or now_iso()
            row.update(status=state["status"], checked_at=stamp, http_status=result.get("http_status"),
                       error=None if result.get("ok") else sanitize_promotion_text(result.get("error")) or "该国家查询失败")
            for key in ("token_expired", "token_expires_at"):
                row.pop(key, None)
                if key in result:
                    row[key] = result[key]
            safe = safe_country_result(result)
            if result.get("ok"):
                row.update(result=safe, last_success_at=stamp)
            state["history"].append({"phase": "initial", "country": country, "ok": bool(result.get("ok")),
                                     "http_status": result.get("http_status"), "checked_at": stamp,
                                     "current_plan_type": safe.get("current_plan_type"),
                                     **({"error": sanitize_promotion_text(result.get("error"))} if not result.get("ok") else {}),
                                     **{key: safe[key] for key in ("account_promotions", "promotion_query_snapshot") if key in safe}})
        else:
            raise ValueError("不支持的国家进度动作")
        _write_progress(conn, fence, progress)
        record_store.patch_row(record_store.ACCOUNTS, account_id, {
            "plan_check_country_results": rows, "updated_at": now_iso(),
        }, conn=conn)
    return rows, progress


def set_country_running(account_id: int, country: str, *, fence: dict | None = None) -> list[dict]:
    def update(rows):
        for row in rows:
            if row["country"] == country:
                row.update(status="running", error=None)
        return rows, {"plan_check_started_at": now_iso()}
    return _update(account_id, update, fence=fence)


def record_country_result(account_id: int, country: str, result: dict, *, fence: dict | None = None) -> list[dict]:
    def update(rows):
        for row in rows:
            if row["country"] != country:
                continue
            stamp = result.get("checked_at") or now_iso()
            row.update({"status": "success" if result.get("ok") else "failed", "checked_at": stamp,
                        "http_status": result.get("http_status"),
                        "error": None if result.get("ok") else sanitize_promotion_text(result.get("error")) or "该国家查询失败"})
            for key in ("token_expired", "token_expires_at"):
                row.pop(key, None)
                if key in result:
                    row[key] = result[key]
            if result.get("ok"):
                row.update(result=safe_country_result(result), last_success_at=stamp)
        return rows, {}
    return _update(account_id, update, fence=fence)


def finish_unfinished_countries(account_id: int, *, status: str, error: str, fence: dict | None = None, conn=None) -> list[dict]:
    def update(rows):
        for row in rows:
            if row.get("status") in {"queued", "running"}:
                row.update(status=status, error=sanitize_promotion_text(error), checked_at=now_iso())
        return rows, {}
    return _update(account_id, update, fence=fence, conn=conn)


def mark_country_task_running(account_id: int, *, fence: dict | None = None) -> bool:
    with _transaction(account_id, fence) as (conn, account):
        if account.get("plan_check_status") not in {"queued", "running"}:
            return False
        return record_store.patch_row(record_store.ACCOUNTS, account_id, {
            "plan_check_status": "running", "plan_check_started_at": now_iso(), "plan_check_error": None,
        }, conn=conn)


def save_country_summary(account_id: int, result: dict, *, fence: dict | None = None) -> bool:
    from core.storage.accounts import update_account_plan_check
    with _transaction(account_id, fence) as (conn, _):
        return update_account_plan_check(acc_id=account_id, result=result, conn=conn)
