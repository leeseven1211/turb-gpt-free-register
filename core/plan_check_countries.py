"""多国家套餐结果的白名单证据与兼容汇总。"""
from __future__ import annotations

from datetime import datetime
import json

from core.plus_promotion import ELIGIBLE_PROMO_KINDS, _safe_scalar, sanitize_promotion_text

_PROMOTION_FIELDS = (
    "plan", "kind", "eligible", "campaign_id", "title", "summary", "discount_percentage",
    "duration_num_periods", "duration_period", "promotion_type", "promotion_type_label",
)
_RESULT_FIELDS = (
    "ok", "http_status", "checked_at", "current_plan_type", "subscription_plan",
    "has_active_subscription", "expires_at", "renews_at", "cancels_at", "billing_period",
    "billing_currency", "is_delinquent", "token_expired", "token_expires_at",
    "discount_type", "discount_amount", "discount_duration_num_periods", "discount_expires_at",
    "discount_cancellation_policy", "discount_promo_campaign_id", "last_purchase_origin_platform",
    "last_will_renew", "proxy_provider", "proxy_region", "network_route",
    "quota_status", "quota_checked_at", "quota_http_status", "quota_error", "quota_type",
)
_PLUS_FIELDS = (
    "promo_eligible", "promo_kind", "discount_eligible", "promo_campaign_id", "promo_title",
    "promo_summary", "promo_discount_percentage", "promo_duration_num_periods",
    "promo_duration_period", "promo_promotion_type", "promo_promotion_type_label",
    "trial_eligible", "trial_campaign_id", "trial_title", "trial_summary",
    "trial_discount_percentage", "trial_duration_num_periods", "trial_duration_period",
    "trial_promotion_type_label",
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _scalars(value: dict, fields) -> dict:
    return {key: _safe_scalar(value[key]) for key in fields if key in value}


def _items(value) -> list:
    return value if isinstance(value, list) else []


def _public_country_code(value) -> str | None:
    """只接受可公开展示的 ISO 3166-1 alpha-2 国家代码。"""
    country = str(value or "").strip().upper()
    if not country:
        return None
    from config.countries import ISO_3166_ALPHA2
    return country if country in ISO_3166_ALPHA2 else None


def _decode_result_json(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _has_multi_country_evidence(result: dict) -> bool:
    """识别聚合结果，避免把首个国家误当成优惠所属国家。"""
    countries = result.get("plan_check_countries")
    if isinstance(countries, list) and countries:
        return True
    if public_country_results(result.get("plan_check_country_results")):
        return True
    promotions = result.get("account_promotions")
    return isinstance(promotions, list) and any(
        _public_country_code(item.get("country"))
        for item in promotions
        if isinstance(item, dict)
    )


def promotion_country_from_row(row: dict | None) -> str | None:
    """从套餐查询成功证据提取单国优惠展示国家。

    多国结果已有逐国公开证据，交给调用方按国家渲染；不能用单值覆盖它。
    失败的新请求可能仍带失败线路，因此只有 ``last_success`` 或明确成功的
    当前结果可以提供单国国家。
    """
    if not isinstance(row, dict):
        return None

    # 显式空列表表示最新任务关闭多国查询；此时历史多国结果不能遮挡
    # 最新单次成功快照。未明确关闭时，继续保护已有逐国证据。
    multi_country_disabled = (
        isinstance(row.get("plan_check_countries"), list)
        and not row.get("plan_check_countries")
    )
    if not multi_country_disabled:
        country_results = public_country_results(row.get("plan_check_country_results"))
        if country_results:
            return None
        promotions = row.get("account_promotions")
        if isinstance(promotions, list) and any(
            _public_country_code(item.get("country"))
            for item in promotions
            if isinstance(item, dict)
        ):
            return None

    last_success = _decode_result_json(row.get("plan_last_success_result_json"))
    country = (
        None
        if _has_multi_country_evidence(last_success)
        else _public_country_code(last_success.get("proxy_region"))
    )
    if country:
        return country

    # plan_check_result_json 失败时也会写入。只有终态成功且结果明确成功时才读取。
    if str(row.get("plan_check_status") or "").strip().lower() != "success":
        return None
    current = _decode_result_json(row.get("plan_check_result_json"))
    if (
        current.get("ok") is not True
        or row.get("plan_check_ok") is False
        or _has_multi_country_evidence(current)
    ):
        return None
    return _public_country_code(current.get("proxy_region"))


def safe_country_result(result: dict) -> dict:
    """只接收套餐字段与有限活动证据，未知嵌套对象不会进入公开快照。"""
    safe = _scalars(result, (*_RESULT_FIELDS, *(f"plus_{key}" for key in _PLUS_FIELDS)))
    promotions = result.get("account_promotions")
    if isinstance(promotions, list):
        safe["account_promotions"] = [
            _scalars(item, _PROMOTION_FIELDS) for item in promotions[:32] if isinstance(item, dict)
        ]
    snapshot = result.get("promotion_query_snapshot")
    if isinstance(snapshot, dict):
        evidence = _scalars(snapshot, ("version", "source", "container_type", "truncated"))
        evidence["campaign_keys"] = [sanitize_promotion_text(item) for item in _items(snapshot.get("campaign_keys"))[:32] if isinstance(item, str)]
        evidence["campaigns"] = [
            _scalars(item, (*_PROMOTION_FIELDS, "index"))
            for item in _items(snapshot.get("campaigns"))[:64] if isinstance(item, dict)
        ]
        safe["promotion_query_snapshot"] = evidence
    windows = result.get("quota_windows")
    if isinstance(windows, list):
        safe["quota_windows"] = [
            _scalars(item, ("slot", "kind", "label", "used_percent", "remaining_percent", "reset_at", "window_seconds", "window_minutes", "reset_after_seconds", "allowed", "limit_reached"))
            for item in windows[:16] if isinstance(item, dict)
        ]
    return safe


def public_country_results(rows) -> list[dict]:
    """国家结果在存储与列表接口共用同一脱敏边界。"""
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows[:256]:
        if not isinstance(row, dict) or not isinstance(row.get("country"), str):
            continue
        from config.countries import normalize_plan_check_countries
        try:
            country = normalize_plan_check_countries([row["country"]])
        except ValueError:
            continue
        if len(country) != 1:
            continue
        item = _scalars(row, ("country", "status", "checked_at", "http_status", "error", "last_success_at", "token_expired", "token_expires_at"))
        item["country"] = country[0]
        result = row.get("result")
        item["result"] = safe_country_result(result) if isinstance(result, dict) else None
        out.append(item)
    return out


def _promotion_order(item: dict) -> tuple:
    priority = {"free_trial": 0, "discount": 1, "other_promo": 2, "unknown": 3, "none": 4}
    def number(value):
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0
    days = {"day": 1, "week": 7, "month": 30, "year": 365}
    duration = number(item.get("duration_num_periods")) * days.get(item.get("duration_period"), 0)
    return (priority.get(item.get("kind"), 3), -number(item.get("discount_percentage")), -duration, bool(item.get("stale")))


def aggregate_country_results(rows: list[dict]) -> dict:
    """按国家保留证据，汇总最优优惠供现有账号筛选和导出使用。"""
    rows = public_country_results(rows)
    succeeded = [row for row in rows if row.get("status") == "success"]
    failed = [row["country"] for row in rows if row.get("status") != "success"]
    snapshots = [row for row in rows if isinstance(row.get("result"), dict)]
    lead = (succeeded or snapshots or [{}])[0]
    result = dict(lead.get("result") or {})
    result.update({
        "ok": bool(succeeded), "checked_at": now_iso(),
        "plan_check_countries": [row["country"] for row in rows],
        "plan_check_country_results": rows,
        "plan_check_partial": bool(succeeded and failed),
        "country_success_count": len(succeeded), "country_total_count": len(rows),
        "failed_countries": failed,
    })
    result["account_promotions"] = [
        {**promotion, "country": row["country"], "stale": row.get("status") != "success"}
        for row in snapshots for promotion in row["result"].get("account_promotions", [])
    ]
    plus = sorted((p for p in result["account_promotions"] if p.get("plan") == "plus"), key=_promotion_order)
    if plus:
        best = plus[0]
        kind = best.get("kind") or "unknown"
        result.update({"plus_promo_kind": kind, "plus_promo_eligible": kind in ELIGIBLE_PROMO_KINDS,
                       "plus_trial_eligible": kind == "free_trial", "plus_discount_eligible": kind == "discount"})
        for key in ("campaign_id", "title", "summary", "discount_percentage", "duration_num_periods", "duration_period", "promotion_type", "promotion_type_label"):
            result[f"plus_promo_{key}"] = best.get(key)
            if key not in {"promotion_type"}:
                result[f"plus_trial_{key}"] = best.get(key)
    if not succeeded:
        result["http_status"] = None
        result["error"] = "全部国家查询失败：" + "、".join(failed)
        expired = [row for row in rows if row.get("token_expired") is True]
        if expired:
            result["token_expired"] = True
            if expired[0].get("token_expires_at"):
                result["token_expires_at"] = expired[0]["token_expires_at"]
    return result
