# -*- coding: utf-8 -*-
"""总览注册任务按日只读聚合。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from core.accounts.query import normalize_query
from core.operations.presentation import public_result_status_sql
from core.storage import admin_repository, postgres as postgres_store, records as record_store
from core.storage.task_query_context import readonly_task_query
from core.storage.registration import init as init_registration_schema


TIMEZONE = ZoneInfo("Asia/Shanghai")
MAX_DAYS = 366


class RegistrationDailyAnalyticsError(ValueError):
    """注册日统计请求参数错误。"""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


def _date_value(value: str | None, field: str) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise RegistrationDailyAnalyticsError("date_invalid", f"{field}必须使用 YYYY-MM-DD。")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise RegistrationDailyAnalyticsError("date_invalid", f"{field}必须使用 YYYY-MM-DD。") from None
    if parsed.isoformat() != value:
        raise RegistrationDailyAnalyticsError("date_invalid", f"{field}必须使用 YYYY-MM-DD。")
    return parsed


def normalize_registration_date_range(
    date_from: str | None = None,
    date_to: str | None = None,
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    instant = now or datetime.now(TIMEZONE)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=TIMEZONE)
    instant = instant.astimezone(TIMEZONE)
    default_end = instant.date()
    start = _date_value(date_from, "开始日期")
    end = _date_value(date_to, "结束日期")
    try:
        if start is None and end is None:
            end = default_end
            start = end - timedelta(days=6)
        elif start is None:
            start = end - timedelta(days=6)
        elif end is None:
            end = start + timedelta(days=6)
    except OverflowError:
        raise RegistrationDailyAnalyticsError(
            "date_invalid", "日期范围超出可处理的日期边界。"
        ) from None
    if start > end:
        raise RegistrationDailyAnalyticsError("date_range_reversed", "开始日期不能晚于结束日期。")
    if (end - start).days + 1 > MAX_DAYS:
        raise RegistrationDailyAnalyticsError("date_range_too_large", "日期范围不能超过 366 天。")
    return start.isoformat(), end.isoformat()


def _query_for_range(start: str, end: str) -> dict:
    return normalize_query({
        "schema_version": 1,
        "entity": "account",
        "archived": "0",
        "q": f"注册任务日期:{start}..{end}",
        "filters": {"promotion": ["none"]},
        "order": [{"field": "id", "direction": "desc"}],
        "limit": None,
    })


def _rows_by_date(start: date, end: date) -> list[dict]:
    return [{"date": (start + timedelta(days=index)).isoformat(),
             "total": 0, "counts": {}, "accounts_total": 0, "plans": {},
             "unpromoted_count": 0,
             "query": _query_for_range((start + timedelta(days=index)).isoformat(),
                                       (start + timedelta(days=index)).isoformat())}
            for index in range((end - start).days + 1)]


def _decode_json(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def registration_daily_analytics(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    now: datetime | None = None,
) -> dict:
    start_text, end_text = normalize_registration_date_range(date_from, date_to, now=now)
    start = date.fromisoformat(start_text)
    end = date.fromisoformat(end_text)
    rows = _rows_by_date(start, end)
    row_by_date = {row["date"]: row for row in rows}
    source = admin_repository._registration_cohort_source_sql(
        date_range=(start_text, end_text),
    )
    jobs = admin_repository._q(record_store.JOBS)
    accounts = admin_repository._q(record_store.ACCOUNTS)
    compatible_display_status_sql = (
        admin_repository._JOB_DISPLAY_STATUS
        .replace("j.account_id", "cohort.job_account_id")
        .replace("j.", "cohort.")
        .replace("a.", "account.")
    )
    display_status_sql = f"""CASE
        WHEN LOWER(BTRIM(COALESCE(cohort.status, ''))) IN
             ('success', 'partial_success')
        THEN ({compatible_display_status_sql})
        ELSE LOWER(BTRIM(COALESCE(cohort.status, '')))
    END"""
    status_sql = public_result_status_sql(
        display_status_sql,
        requested_status_expression="cohort.requested_status",
    )
    promo_kind_sql = admin_repository._ACCOUNT_PROMO_KIND.replace("a.", "scoped.")
    promotion_sql = admin_repository._account_facet_expressions()["promotion"].replace("a.", "unique_accounts.")
    plan_sql = f"""CASE
        WHEN LOWER(COALESCE(scoped.current_plan_type, scoped.plan_type, '')) = 'free'
             AND ({promo_kind_sql}) = 'free_trial' THEN 'free_trial_eligible'
        WHEN LOWER(COALESCE(scoped.current_plan_type, scoped.plan_type, '')) = 'free'
             AND ({promo_kind_sql}) = 'discount'
             AND scoped.plus_promo_discount_percentage = 50 THEN 'free_half_price_eligible'
        WHEN LOWER(COALESCE(scoped.current_plan_type, scoped.plan_type, '')) = 'free'
             AND ({promo_kind_sql}) = 'discount' THEN 'free_discount_eligible'
        WHEN LOWER(COALESCE(scoped.current_plan_type, scoped.plan_type, '')) = 'free'
             AND ({promo_kind_sql}) IN ('other_promo', 'unknown') THEN 'free_promo_unknown'
        ELSE COALESCE(NULLIF(LOWER(COALESCE(scoped.current_plan_type, scoped.plan_type, '')), ''), 'unknown')
    END"""
    # 每日任务、账号归属、套餐分布和无优惠数量共用一条 SQL，
    # 不把任务或凭据 JSON 加载到 Python。
    sql = f"""
        WITH cohort AS MATERIALIZED ({source}),
        scoped AS MATERIALIZED (
            SELECT cohort.*, {status_sql} AS public_status,
                   account.current_plan_type, account.plan_type,
                   account.plus_promo_kind, account.plus_discount_eligible,
                   account.plus_promo_eligible, account.plus_trial_eligible,
                   account.plus_promo_discount_percentage,
                   account.account_promotion_value, account.plan_check_status, account.archived
              FROM cohort
              LEFT JOIN {accounts} account ON account.id = cohort.account_id
        ),
        task_daily AS (
            SELECT task_date, SUM(count) AS total,
                   jsonb_object_agg(public_status, count ORDER BY public_status) AS counts
              FROM (
                  SELECT task_date, public_status, COUNT(*) AS count
                    FROM scoped GROUP BY task_date, public_status
              ) grouped
             GROUP BY task_date
        ),
        account_daily AS (
            SELECT task_date, COUNT(*) AS accounts_total
              FROM (SELECT DISTINCT task_date, account_id FROM scoped WHERE account_id IS NOT NULL) unique_accounts
             GROUP BY task_date
        ),
        plan_daily AS (
            SELECT task_date, {plan_sql} AS plan, COUNT(*) AS count
              FROM (SELECT DISTINCT task_date, account_id, current_plan_type, plan_type,
                                   plus_promo_kind, plus_discount_eligible, plus_promo_eligible,
                                   plus_trial_eligible, plus_promo_discount_percentage
                      FROM scoped WHERE account_id IS NOT NULL) scoped
             GROUP BY task_date, plan
        ),
        unpromoted_daily AS (
            SELECT task_date, COUNT(*) AS count
              FROM (SELECT DISTINCT task_date, account_id, account_promotion_value, plan_check_status, archived
                      FROM scoped WHERE account_id IS NOT NULL) unique_accounts
             WHERE ({promotion_sql}) = 'none' AND archived IS FALSE
             GROUP BY task_date
        ),
        summary_tasks AS (
            SELECT SUM(count) AS total,
                   jsonb_object_agg(public_status, count ORDER BY public_status) AS counts
              FROM (
                  SELECT public_status, COUNT(*) AS count FROM scoped GROUP BY public_status
              ) grouped
        ),
        summary_accounts AS (
            SELECT COUNT(*) AS accounts_total
              FROM (SELECT DISTINCT account_id FROM scoped WHERE account_id IS NOT NULL) unique_accounts
        ),
        summary_plans AS (
            SELECT {plan_sql} AS plan, COUNT(*) AS count
              FROM (SELECT DISTINCT account_id, current_plan_type, plan_type, plus_promo_kind,
                                   plus_discount_eligible, plus_promo_eligible, plus_trial_eligible,
                                   plus_promo_discount_percentage
                      FROM scoped WHERE account_id IS NOT NULL) scoped
             GROUP BY plan
        ),
        summary_unpromoted AS (
            SELECT COUNT(*) AS count
              FROM (SELECT DISTINCT account_id, account_promotion_value, plan_check_status, archived
                      FROM scoped WHERE account_id IS NOT NULL) unique_accounts
             WHERE ({promotion_sql}) = 'none' AND archived IS FALSE
        )
        SELECT 'task_daily' AS kind, task_date::text AS day, jsonb_build_object(
                   'total', total, 'counts', counts) AS payload FROM task_daily
        UNION ALL SELECT 'account_daily', task_date::text, jsonb_build_object(
                   'accounts_total', accounts_total) FROM account_daily
        UNION ALL SELECT 'plan_daily', task_date::text, jsonb_build_object(
                   'plan', plan, 'count', count) FROM plan_daily
        UNION ALL SELECT 'unpromoted_daily', task_date::text, jsonb_build_object(
                   'count', count) FROM unpromoted_daily
        UNION ALL SELECT 'summary_tasks', NULL, jsonb_build_object(
                   'total', total, 'counts', counts) FROM summary_tasks
        UNION ALL SELECT 'summary_accounts', NULL, jsonb_build_object(
                   'accounts_total', accounts_total) FROM summary_accounts
        UNION ALL SELECT 'summary_plan', NULL, jsonb_build_object(
                   'plan', plan, 'count', count) FROM summary_plans
        UNION ALL SELECT 'summary_unpromoted', NULL, jsonb_build_object(
                   'count', count) FROM summary_unpromoted
    """
    # registration.init() 幂等执行，确保旧安装在准备共享归属 SQL 前已有
    # 可选的 Attempt 表。
    if not readonly_task_query():
        init_registration_schema()
    with admin_repository._connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (start_text, end_text))
        result_rows = cur.fetchall()
    summary = {"total": 0, "counts": {}, "accounts_total": 0, "plans": {}, "unpromoted_count": 0}
    for item in result_rows:
        kind = item["kind"]
        day = item.get("day")
        payload = _decode_json(item.get("payload"))
        if kind == "task_daily" and day in row_by_date:
            row_by_date[day]["total"] = int(payload.get("total") or 0)
            row_by_date[day]["counts"] = {str(k): int(v or 0) for k, v in (payload.get("counts") or {}).items()}
        elif kind == "account_daily" and day in row_by_date:
            row_by_date[day]["accounts_total"] = int(payload.get("accounts_total") or 0)
        elif kind == "plan_daily" and day in row_by_date:
            row_by_date[day]["plans"][str(payload.get("plan") or "unknown")] = int(payload.get("count") or 0)
        elif kind == "unpromoted_daily" and day in row_by_date:
            row_by_date[day]["unpromoted_count"] = int(payload.get("count") or 0)
        elif kind == "summary_tasks":
            summary["total"] = int(payload.get("total") or 0)
            summary["counts"] = {str(k): int(v or 0) for k, v in (payload.get("counts") or {}).items()}
        elif kind == "summary_accounts":
            summary["accounts_total"] = int(payload.get("accounts_total") or 0)
        elif kind == "summary_plan":
            summary["plans"][str(payload.get("plan") or "unknown")] = int(payload.get("count") or 0)
        elif kind == "summary_unpromoted":
            summary["unpromoted_count"] = int(payload.get("count") or 0)
    summary["query"] = _query_for_range(start_text, end_text)
    instant = (now or datetime.now(TIMEZONE))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=TIMEZONE)
    return {
        "ok": True,
        "timezone": "Asia/Shanghai",
        "date_from": start_text,
        "date_to": end_text,
        "updated_at": instant.astimezone(TIMEZONE).isoformat(),
        "rows": rows,
        "summary": summary,
    }


daily_registration_analytics = registration_daily_analytics
