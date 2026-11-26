# -*- coding: utf-8 -*-
"""按账号首次入库日只读聚合最近成功查询的套餐优惠。"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from core.accounts.query import normalize_query
from core.storage import admin_repository, records as record_store
from core.storage.account_dates import account_created_date_sql
from core.storage.accounts import promotion_offers
from core.storage.registration.promotion_presence import (
    fresh_promotion_offers_from_snapshot,
    promotion_presence_from_snapshot,
)


TIMEZONE = ZoneInfo("Asia/Shanghai")
MAX_DAYS = 366


class RegistrationDailyAnalyticsError(ValueError):
    """账号日统计请求参数错误。"""

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
    start = _date_value(date_from, "开始日期")
    end = _date_value(date_to, "结束日期")
    try:
        if start is None and end is None:
            end = instant.date()
            start = end - timedelta(days=2)
        elif start is None:
            start = end - timedelta(days=2)
        elif end is None:
            end = start + timedelta(days=2)
    except OverflowError:
        raise RegistrationDailyAnalyticsError("date_invalid", "日期范围超出可处理的日期边界。") from None
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
        "q": "",
        "date_from": start,
        "date_to": end,
        "filters": {"promotion": ["none"]},
        "order": [{"field": "id", "direction": "desc"}],
        "limit": None,
    })


def _empty_stats() -> dict:
    return {
        "total": 0, "counts": {}, "accounts_total": 0, "plans": {},
        "unpromoted_count": 0, "offers": [], "promoted_accounts_total": 0,
        "promotion_presence": {"eligible": 0, "none": 0, "unknown": 0},
    }


def _rows_by_date(start: date, end: date) -> list[dict]:
    result = []
    for index in range((end - start).days + 1):
        day = (start + timedelta(days=index)).isoformat()
        result.append({"date": day, **_empty_stats(), "query": _query_for_range(day, day)})
    return result


def _account_promotions_sql() -> str:
    """先过滤入库日期，仅读取本次账号的轻量优惠及必要的一个成功快照字段。"""
    accounts = admin_repository._q(record_store.ACCOUNTS)
    offers = admin_repository._promotion_table()
    created_date = account_created_date_sql("a")
    promotion = admin_repository._account_facet_expressions()["promotion"]
    return f"""
        WITH account_cohort AS MATERIALIZED (
            SELECT a.id, ({created_date}) AS account_date,
                   COALESCE(NULLIF(LOWER(BTRIM(a.current_plan_type)), ''),
                            NULLIF(LOWER(BTRIM(a.plan_type)), ''), 'unknown') AS plan,
                   (a.archived IS FALSE AND ({promotion}) = 'none') AS unpromoted
              FROM {accounts} a
             WHERE ({created_date}) >= %s::date AND ({created_date}) <= %s::date
        )
        SELECT member.account_date::text AS day, member.plan, member.unpromoted,
               COALESCE(fresh.offers, '[]'::jsonb) AS offers,
               CASE WHEN fresh.offers IS NULL AND a.account_has_plan_snapshot IS TRUE
                    THEN a.data->'plan_last_success_result_json' END AS promotion_snapshot
          FROM account_cohort member
          LEFT JOIN LATERAL (
              SELECT jsonb_agg(jsonb_build_object(
                         'key', grouped.offer_key, 'plan', grouped.plan, 'kind', grouped.kind,
                         'discount_percentage', grouped.discount_percentage::text,
                         'duration_num_periods', grouped.duration_num_periods::text,
                         'duration_period', grouped.duration_period
                     ) ORDER BY grouped.offer_key) AS offers
                FROM (
                    SELECT offer.offer_key, MAX(offer.plan) AS plan, MAX(offer.kind) AS kind,
                           MAX(offer.discount_percentage) AS discount_percentage,
                           MAX(offer.duration_num_periods) AS duration_num_periods,
                           MAX(offer.duration_period) AS duration_period
                      FROM {offers} offer
                     WHERE offer.account_id = member.id AND offer.eligible IS TRUE
                       AND offer.stale IS FALSE
                       AND offer.kind IN ('free_trial', 'discount', 'other_promo')
                     GROUP BY offer.offer_key
                ) grouped
          ) fresh ON TRUE
          LEFT JOIN {accounts} a ON a.id = member.id
    """


def _add_account(stats: dict, item: dict, presence: str, offers: list[dict], offer_counts: dict) -> None:
    stats["accounts_total"] += 1
    stats["total"] += 1
    plan = str(item.get("plan") or "unknown")
    stats["plans"][plan] = stats["plans"].get(plan, 0) + 1
    stats["unpromoted_count"] += int(bool(item.get("unpromoted")))
    stats["promotion_presence"][presence] += 1
    stats["promoted_accounts_total"] += int(presence == "eligible")
    for offer in offers:
        key = str(offer["key"])
        projected = offer_counts.get(key)
        if projected is None:
            projected = {
                "key": key, "plan": str(offer["plan"]),
                "label": promotion_offers.offer_label(offer), "count": 0, "stale_count": 0,
            }
            offer_counts[key] = projected
        projected["count"] += 1


def _snapshot_offers(snapshot: object) -> list[dict]:
    """成功快照旧数据没有轻量投影时，按相同组合键补齐优惠明细。"""
    offers = {}
    for item in fresh_promotion_offers_from_snapshot(snapshot):
        key = promotion_offers.offer_key(
            item.get("plan"), item.get("kind"), item.get("discount_percentage"),
            item.get("duration_num_periods"), item.get("duration_period"),
        )
        # 只留下标签需要的有限字段，不把快照中的其他证据带入响应。
        offers.setdefault(key, {
            "key": key,
            **{field: item.get(field) for field in (
                "plan", "kind", "discount_percentage", "duration_num_periods", "duration_period",
            )},
        })
    return list(offers.values())


def registration_daily_analytics(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    now: datetime | None = None,
) -> dict:
    start_text, end_text = normalize_registration_date_range(date_from, date_to, now=now)
    rows = _rows_by_date(date.fromisoformat(start_text), date.fromisoformat(end_text))
    by_date = {row["date"]: row for row in rows}
    day_offers = {row["date"]: {} for row in rows}
    summary = _empty_stats()
    summary_offers = {}
    # 命名游标只保留一批账号。无任务关联、无整段账号/凭据 JSON，
    # 当前优惠已明确的账号连成功快照也不解压；其余每个账号最多读取一次该字段。
    with admin_repository._connect() as conn, conn.cursor(name="daily_account_promotions") as cur:
        cur.execute(_account_promotions_sql(), (start_text, end_text))
        while batch := cur.fetchmany(256):
            for item in batch:
                day = item["day"]
                offers = item.get("offers") or []
                snapshot = item.get("promotion_snapshot")
                if not offers:
                    if isinstance(snapshot, str):
                        try:
                            snapshot = json.loads(snapshot)
                        except (ValueError, RecursionError):
                            snapshot = None
                    offers = _snapshot_offers(snapshot)
                presence = "eligible" if offers else promotion_presence_from_snapshot(snapshot)
                _add_account(by_date[day], item, presence, offers, day_offers[day])
                _add_account(summary, item, presence, offers, summary_offers)
    for row in rows:
        row["offers"] = sorted(day_offers[row["date"]].values(), key=lambda offer: (offer["plan"], offer["key"]))
    summary["offers"] = sorted(summary_offers.values(), key=lambda offer: (offer["plan"], offer["key"]))
    summary["query"] = _query_for_range(start_text, end_text)
    instant = now or datetime.now(TIMEZONE)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=TIMEZONE)
    return {
        "ok": True,
        "timezone": "Asia/Shanghai",
        "cohort_basis": "account_created_at",
        "cohort_basis_label": "按账号首次入库日期统计",
        "date_from": start_text,
        "date_to": end_text,
        "updated_at": instant.astimezone(TIMEZONE).isoformat(),
        "rows": rows,
        "summary": summary,
    }


daily_registration_analytics = registration_daily_analytics
