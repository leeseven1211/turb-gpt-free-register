"""只读判断最近成功的套餐快照及其有效优惠，不查询存储。"""
from __future__ import annotations

import json
from typing import Literal


_PLANS = frozenset(("go", "plus", "team"))
_ELIGIBLE_KINDS = frozenset(("free_trial", "discount", "other_promo"))
PromotionPresence = Literal["eligible", "none", "unknown"]


def _fresh(item: dict) -> bool:
    return all(item.get(field) is None or item.get(field) is False for field in ("stale", "expired"))


def _fresh_offers(result: dict) -> list[dict]:
    rows = result.get("account_promotions")
    if not isinstance(rows, list):
        return []
    return [
        item for item in rows
        if isinstance(item, dict)
        and isinstance(item.get("plan"), str)
        and item.get("plan") in _PLANS
        and isinstance(item.get("kind"), str)
        and item.get("kind") in _ELIGIBLE_KINDS
        and item.get("eligible") is True
        and _fresh(item)
    ]


def _complete_none(result: dict) -> bool:
    snapshot = result.get("promotion_query_snapshot")
    rows = result.get("account_promotions")
    if (
        result.get("ok") is not True
        or not isinstance(snapshot, dict)
        or snapshot.get("truncated") is not False
        or not isinstance(rows, list)
        or not rows
    ):
        return False
    covered = set()
    for item in rows:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("plan"), str)
            or item.get("plan") not in _PLANS
            or item.get("kind") != "none"
            or item.get("eligible") is not False
            or not _fresh(item)
        ):
            return False
        covered.add(item["plan"])
    return covered == _PLANS


def _country(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    return code if len(code) == 2 and code.isascii() and code.isalpha() else None


def _has_country_evidence(result: dict) -> bool:
    if result.get("plan_check_countries") not in (None, []):
        return True
    if result.get("plan_check_country_results") not in (None, []):
        return True
    rows = result.get("account_promotions")
    return isinstance(rows, list) and any(
        isinstance(item, dict) and item.get("country") not in (None, "")
        for item in rows
    )


def _snapshot(value: object) -> dict | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return None
    return value if isinstance(value, dict) else None


def fresh_promotion_offers_from_snapshot(value: object) -> list[dict]:
    """提取成功快照中的有效优惠原条目，供调用方分组和去重。

    读取顶层优惠及成功国家的成功结果。仅返回未过期、未标记历史、
    明确 eligible=True 且类别已知的 Go/Plus/Team 项；保留原字段和重复项。
    """
    value = _snapshot(value)
    if value is None or value.get("ok") is not True:
        return []
    offers = _fresh_offers(value)
    country_rows = value.get("plan_check_country_results")
    if isinstance(country_rows, list):
        for row in country_rows:
            if not isinstance(row, dict) or row.get("status") != "success":
                continue
            result = row.get("result")
            if isinstance(result, dict) and result.get("ok") is True:
                offers.extend(_fresh_offers(result))
    return offers


def promotion_presence_from_snapshot(value: object) -> PromotionPresence:
    """从字典或 JSON 套餐结果判断 eligible、none 或 unknown。

    明确有效优惠优先于不完整证据。确认无优惠时，每个目标国家均须成功、
    未截断，且显式返回未过期的 Go/Plus/Team 无优惠记录。
    本函数描述传入的最近成功快照，忽略账号当前执行状态。
    """
    value = _snapshot(value)
    if value is None or value.get("ok") is not True:
        return "unknown"
    if fresh_promotion_offers_from_snapshot(value):
        return "eligible"
    if value.get("plan_check_partial") is not None and value.get("plan_check_partial") is not False:
        return "unknown"
    if not _has_country_evidence(value):
        return "none" if _complete_none(value) else "unknown"

    requested = value.get("plan_check_countries")
    country_rows = value.get("plan_check_country_results")
    if not isinstance(requested, list) or not requested or not isinstance(country_rows, list):
        return "unknown"
    countries = [_country(country) for country in requested]
    if None in countries or len(set(countries)) != len(countries) or len(country_rows) != len(countries):
        return "unknown"
    observed = set()
    for row in country_rows:
        if not isinstance(row, dict):
            return "unknown"
        country = _country(row.get("country"))
        result = row.get("result")
        if (
            country not in countries
            or country in observed
            or row.get("status") != "success"
            or not isinstance(result, dict)
            or not _complete_none(result)
        ):
            return "unknown"
        observed.add(country)
    return "none" if observed == set(countries) else "unknown"
