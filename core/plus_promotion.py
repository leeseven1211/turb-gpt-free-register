# -*- coding: utf-8 -*-
"""Plus 促销活动的统一分类与兼容读取。"""
from __future__ import annotations

from typing import Any, Mapping


FREE_TRIAL = "free_trial"
DISCOUNT = "discount"
OTHER_PROMO = "other_promo"
NO_PROMO = "none"
UNKNOWN = "unknown"

PROMO_KINDS = frozenset({FREE_TRIAL, DISCOUNT, OTHER_PROMO, NO_PROMO, UNKNOWN})
ELIGIBLE_PROMO_KINDS = frozenset({FREE_TRIAL, DISCOUNT, OTHER_PROMO})


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_percentage(value: Any) -> int | float | None:
    """把上游折扣百分比收敛为 0～100 的数字。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if number < 0 or number > 100:
        return None
    return int(number) if number.is_integer() else round(number, 2)


def classify_plus_campaign(campaign: Any) -> str:
    """根据 ``eligible_promo_campaigns.plus`` 区分免费试用和折扣。"""
    if not isinstance(campaign, Mapping) or not campaign:
        return NO_PROMO

    metadata = campaign.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    discount = metadata.get("discount")
    discount = discount if isinstance(discount, Mapping) else {}
    percentage = normalize_percentage(discount.get("percentage"))
    campaign_id = _text(campaign.get("id")).lower()
    title = _text(metadata.get("title")).lower()
    promotion_type = _text(metadata.get("promotion_type")).lower()
    promotion_label = _text(metadata.get("promotion_type_label")).lower()
    searchable = " ".join((campaign_id, title, promotion_type, promotion_label))

    if percentage == 100:
        return FREE_TRIAL
    if percentage is not None and 0 < percentage < 100:
        return DISCOUNT
    if "free trial" in searchable or "-free" in campaign_id or "trial" in campaign_id:
        return FREE_TRIAL
    if "pct-off" in campaign_id or "discount" in searchable or "% off" in searchable:
        return DISCOUNT
    return OTHER_PROMO


def promotion_kind_from_record(record: Mapping[str, Any] | None) -> str:
    """兼容新字段和历史 ``plus_trial_*`` 字段推导当前优惠类型。"""
    row = record or {}
    explicit = _text(row.get("plus_promo_kind")).lower()
    if explicit in PROMO_KINDS:
        return explicit

    percentage = normalize_percentage(
        row.get("plus_promo_discount_percentage", row.get("plus_trial_discount_percentage"))
    )
    campaign_id = _text(row.get("plus_promo_campaign_id") or row.get("plus_trial_campaign_id"))
    title = _text(row.get("plus_promo_title") or row.get("plus_trial_title"))
    promotion_type = _text(row.get("plus_promo_promotion_type"))
    promotion_label = _text(
        row.get("plus_promo_promotion_type_label") or row.get("plus_trial_promotion_type_label")
    )

    synthetic_campaign = {
        "id": campaign_id,
        "metadata": {
            "title": title,
            "promotion_type": promotion_type,
            "promotion_type_label": promotion_label,
            "discount": {"percentage": percentage} if percentage is not None else {},
        },
    }
    if any((campaign_id, title, promotion_type, promotion_label, percentage is not None)):
        return classify_plus_campaign(synthetic_campaign)

    if row.get("plus_discount_eligible") is True:
        return DISCOUNT
    if row.get("plus_promo_eligible") is True or row.get("plus_trial_eligible") is True:
        # 旧记录只有一个布尔值，不能安全猜成免费试用。
        return UNKNOWN
    return NO_PROMO


def is_free_trial_record(record: Mapping[str, Any] | None) -> bool:
    """仅真正免费试用可进入旧的 Plus 试用提链流程。"""
    row = record or {}
    plan = _text(row.get("current_plan_type") or row.get("plan_type")).lower()
    return plan == "free" and promotion_kind_from_record(row) == FREE_TRIAL


def promotion_label(record: Mapping[str, Any] | None) -> str:
    """生成适合任务日志和接口摘要的中文优惠文案。"""
    row = record or {}
    kind = promotion_kind_from_record(row)
    periods = row.get("plus_promo_duration_num_periods", row.get("plus_trial_duration_num_periods"))
    period = _text(row.get("plus_promo_duration_period") or row.get("plus_trial_duration_period")).lower()
    duration = ""
    if periods not in (None, ""):
        unit = "个月" if period == "month" else ("年" if period == "year" else period)
        duration = f" {periods} {unit}".rstrip() if unit else ""
    if kind == FREE_TRIAL:
        return f"免费试用{duration}".strip()
    if kind == DISCOUNT:
        percentage = normalize_percentage(
            row.get("plus_promo_discount_percentage", row.get("plus_trial_discount_percentage"))
        )
        discount = "五折" if percentage == 50 else (f"减 {percentage}%" if percentage is not None else "折扣")
        return f"{discount}{duration}".strip()
    if kind == OTHER_PROMO:
        return "其他优惠"
    if kind == UNKNOWN:
        return "历史优惠待复查"
    return "无优惠"
