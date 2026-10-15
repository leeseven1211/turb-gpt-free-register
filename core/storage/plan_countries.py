"""账号多国家套餐结果的行锁合并与逐国检查点。"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta
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


def begin_country_checks(account_id: int, countries: list[str], *, fence: dict | None = None, budget_seconds: float = 120) -> list[dict]:
    def begin(rows):
        previous = {row["country"]: row for row in rows}
        current = [dict(previous.get(country) or {"country": country, "result": None}) for country in countries]
        for row in current:
            row.update(status="queued", error=None)
            # Token 失效属于本次请求证据，不能从上次失败带入新的查询。
            row.pop("token_expired", None)
            row.pop("token_expires_at", None)
        return current, {"plan_check_countries": list(countries), "plan_check_partial": False,
                         "plan_check_deadline_at": (datetime.now() + timedelta(seconds=max(120, budget_seconds))).isoformat(timespec="seconds")}
    return _update(account_id, begin, fence=fence)


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
