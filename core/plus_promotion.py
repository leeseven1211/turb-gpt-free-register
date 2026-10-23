# -*- coding: utf-8 -*-
"""Go / Plus 促销活动的统一分类、有限证据与 Plus 兼容读取。"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping


FREE_TRIAL = "free_trial"
DISCOUNT = "discount"
OTHER_PROMO = "other_promo"
NO_PROMO = "none"
UNKNOWN = "unknown"

PROMO_KINDS = frozenset({FREE_TRIAL, DISCOUNT, OTHER_PROMO, NO_PROMO, UNKNOWN})
ELIGIBLE_PROMO_KINDS = frozenset({FREE_TRIAL, DISCOUNT, OTHER_PROMO})
PROMOTION_PLANS = ("go", "plus")
MAX_CAMPAIGNS_PER_PLAN = 16
_MAX_TEXT_LENGTH = 512
_MAX_DIAGNOSTIC_FIELDS = 32
_MAX_EVIDENCE_CAMPAIGNS = 64
_METADATA_FIELDS = ("title", "summary", "promotion_type", "promotion_type_label")


def sanitize_promotion_text(value: Any) -> str | None:
    """证据只接收有限文本，并移除夹带在文案里的凭据与邮箱。"""
    if not isinstance(value, str):
        return None
    text = value[:_MAX_TEXT_LENGTH]
    text = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "[已脱敏]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*", "[已脱敏]", text)
    text = re.sub(r"(?i)\b(?:access_token|refresh_token|token|password|cookie|otp)\s*[:=]\s*[^\s,;]+", "[已脱敏]", text)
    text = re.sub(r"(?i)\bsk-[A-Za-z0-9_-]{8,}", "[已脱敏]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已脱敏]", text)
    text = re.sub(r"(?i)(https?://)[^\s/@]+:[^\s/@]+@", r"\1[已脱敏]@", text)
    return text


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return sanitize_promotion_text(value)
    if isinstance(value, int):
        return value if value.bit_length() <= 1024 else None
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _field_names(value: Mapping[str, Any]) -> list[str]:
    """只保留字段名，未知结构的值不进入诊断证据。"""
    return [
        key for key in value
        if isinstance(key, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", key)
        and sanitize_promotion_text(key) == key
    ][:_MAX_DIAGNOSTIC_FIELDS]


def _value_type(value: Any) -> str:
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    return "null" if value is None else ("string" if isinstance(value, str) else "scalar")


def _campaign_shape(plan: str, value: Any, *, index: int | None = None) -> dict:
    """诊断形状保持扁平，避免任务摘要的深度裁剪丢失活动证据。"""
    shape = {"plan": plan, "type": _value_type(value)}
    if index is not None:
        shape["index"] = index
    if isinstance(value, list):
        shape["length"] = len(value)
    if isinstance(value, Mapping):
        shape["fields"] = _field_names(value)
        metadata = value.get("metadata")
        shape["metadata_type"] = _value_type(metadata)
        if isinstance(metadata, Mapping):
            shape["metadata_fields"] = _field_names(metadata)
            for key in ("discount", "duration"):
                nested = metadata.get(key)
                shape[f"{key}_type"] = _value_type(nested)
                if isinstance(nested, Mapping):
                    shape[f"{key}_fields"] = _field_names(nested)
    return shape


def _flat_campaign_evidence(plan: str, campaign: Mapping[str, Any], *, index: int | None = None) -> dict:
    """白名单证据保留原标量类型，活动文本只保存有限脱敏内容。"""
    result = {"plan": plan}
    if index is not None:
        result["index"] = index
    if "id" in campaign:
        result["campaign_id"] = _safe_scalar(campaign["id"])
    metadata = campaign.get("metadata")
    if isinstance(metadata, Mapping):
        result.update({key: _safe_scalar(metadata[key]) for key in _METADATA_FIELDS if key in metadata})
        discount = metadata.get("discount")
        if isinstance(discount, Mapping) and "percentage" in discount:
            result["discount_percentage"] = _safe_scalar(discount["percentage"])
        duration = metadata.get("duration")
        if isinstance(duration, Mapping):
            for field in ("num_periods", "period"):
                if field in duration:
                    result[f"duration_{field}"] = _safe_scalar(duration[field])
    return result


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
    if not math.isfinite(number) or number < 0 or number > 100:
        return None
    # 不能把 99.999% 舍入到 100%，也不能把很小的折扣舍入成无优惠。
    return int(number) if number.is_integer() else number


def normalize_duration_num_periods(value: Any) -> int | float | None:
    """期限数量必须是有限正数，布尔值不能被当作一个周期。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return int(number) if number.is_integer() else number


def normalize_duration_period(value: Any) -> str | None:
    """周期单位只接收非空字符串，异常值不进入界面文案。"""
    text = sanitize_promotion_text(value)
    return text.strip() or None if text is not None else None


def classify_campaign(campaign: Any, *, legacy_plus_trial: bool = False) -> str:
    """以数值折扣为准；未知形状和无效数值不得推测成免费。"""
    if campaign is None or (isinstance(campaign, Mapping) and not campaign):
        return NO_PROMO
    if not isinstance(campaign, Mapping):
        return UNKNOWN

    metadata = campaign.get("metadata")
    if metadata is not None and not isinstance(metadata, Mapping):
        return UNKNOWN
    metadata = metadata if isinstance(metadata, Mapping) else {}
    duration = metadata.get("duration")
    if duration is not None and not isinstance(duration, Mapping):
        return UNKNOWN
    discount = metadata.get("discount")
    if discount is not None and not isinstance(discount, Mapping):
        return UNKNOWN
    discount = discount if isinstance(discount, Mapping) else {}
    percentage = normalize_percentage(discount.get("percentage"))
    if "percentage" in discount:
        if percentage is None:
            return UNKNOWN
        if percentage == 100:
            return FREE_TRIAL
        if percentage > 0:
            return DISCOUNT
        return NO_PROMO
    text_values = (campaign.get("id"), *(metadata.get(key) for key in _METADATA_FIELDS))
    if any(value is not None and not isinstance(value, str) for value in text_values):
        return UNKNOWN
    campaign_id = _text(campaign.get("id")).lower()
    title = _text(metadata.get("title")).lower()
    promotion_type = _text(metadata.get("promotion_type")).lower()
    promotion_label = _text(metadata.get("promotion_type_label")).lower()
    searchable = " ".join((campaign_id, title, promotion_type, promotion_label))

    if not any((campaign_id, title, promotion_type, promotion_label)):
        return UNKNOWN
    if (
        "free trial" in searchable or "-free" in campaign_id
        or promotion_type in {"free_trial", "free"}
        or (legacy_plus_trial and "trial" in campaign_id)
    ):
        return FREE_TRIAL
    if "pct-off" in campaign_id or "discount" in searchable or "% off" in searchable:
        return DISCOUNT
    return OTHER_PROMO


def classify_plus_campaign(campaign: Any) -> str:
    """保留 Plus 已有活动标识的兼容分类；Go 不继承模糊 trial 规则。"""
    return classify_campaign(campaign, legacy_plus_trial=True)


def _normalize_campaign(plan: str, campaign: Any, *, is_free: bool) -> dict:
    safe = _flat_campaign_evidence(plan, campaign) if isinstance(campaign, Mapping) else {}
    kind = classify_campaign(campaign, legacy_plus_trial=plan == "plus") if is_free else NO_PROMO
    return {
        "plan": plan,
        "kind": kind,
        "eligible": kind in ELIGIBLE_PROMO_KINDS,
        "campaign_id": sanitize_promotion_text(safe.get("campaign_id")),
        "title": sanitize_promotion_text(safe.get("title")),
        "summary": sanitize_promotion_text(safe.get("summary")),
        "discount_percentage": normalize_percentage(safe.get("discount_percentage")),
        "duration_num_periods": normalize_duration_num_periods(safe.get("duration_num_periods")),
        "duration_period": normalize_duration_period(safe.get("duration_period")),
        "promotion_type": sanitize_promotion_text(safe.get("promotion_type")),
        "promotion_type_label": sanitize_promotion_text(safe.get("promotion_type_label")),
    }


def parse_account_promotions(campaigns: Any, *, is_free: bool) -> tuple[list[dict], dict]:
    """统一解析有限 Go / Plus 活动，并留下不含账号凭据的查询证据。"""
    mapping = campaigns if isinstance(campaigns, Mapping) else {}
    promotions = []
    for plan in PROMOTION_PLANS:
        if not isinstance(campaigns, Mapping) and campaigns is not None:
            promotions.append(_normalize_campaign(plan, campaigns, is_free=is_free))
            continue
        campaign = mapping.get(plan)
        if isinstance(campaign, list):
            values = campaign[:MAX_CAMPAIGNS_PER_PLAN] or [None]
        else:
            values = [campaign]
        promotions.extend(_normalize_campaign(plan, value, is_free=is_free) for value in values)
    evidence = []
    shapes = []
    truncated = len(mapping) > _MAX_DIAGNOSTIC_FIELDS
    sources = (
        [(key, mapping[key]) for key in _field_names(mapping)]
        if isinstance(campaigns, Mapping) else [("unknown", campaigns)]
    )
    for plan, campaign in sources:
        shapes.append(_campaign_shape(plan, campaign))
        values = campaign[:MAX_CAMPAIGNS_PER_PLAN] if isinstance(campaign, list) else [campaign]
        truncated = truncated or (isinstance(campaign, list) and len(campaign) > MAX_CAMPAIGNS_PER_PLAN)
        for index, value in enumerate(values):
            if len(evidence) >= _MAX_EVIDENCE_CAMPAIGNS:
                truncated = True
                break
            array_index = index if isinstance(campaign, list) else None
            if array_index is not None:
                shapes.append(_campaign_shape(plan, value, index=array_index))
            if isinstance(value, Mapping):
                evidence.append(_flat_campaign_evidence(plan, value, index=array_index))
    snapshot = {
        "version": 1,
        "source": "accounts_check",
        "campaign_keys": _field_names(mapping),
        "container_type": _value_type(campaigns),
        "campaigns": evidence,
        "campaign_shapes": shapes,
        "truncated": bool(truncated),
    }
    return promotions, snapshot


def primary_plan_promotion(promotions: list[dict], plan: str) -> dict:
    """兼容单项 Plus 字段，优先使用已明确识别的活动。"""
    priority = {FREE_TRIAL: 0, DISCOUNT: 1, OTHER_PROMO: 2, UNKNOWN: 3, NO_PROMO: 4}
    values = [item for item in promotions if item.get("plan") == plan]
    return min(values, key=lambda item: priority.get(item.get("kind"), 3)) if values else _normalize_campaign(plan, None, is_free=True)


def promotion_kind_from_record(record: Mapping[str, Any] | None) -> str:
    """兼容新字段和历史 ``plus_trial_*`` 字段推导当前优惠类型。"""
    row = record or {}
    explicit = _text(row.get("plus_promo_kind")).lower()
    if explicit in PROMO_KINDS:
        return explicit

    raw_percentage = row.get("plus_promo_discount_percentage", row.get("plus_trial_discount_percentage"))
    percentage = normalize_percentage(raw_percentage)
    if raw_percentage is not None and percentage is None:
        return UNKNOWN
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


def is_extract_link_eligible(record: Mapping[str, Any] | None) -> bool:
    """仅确认有明确 Plus 优惠的 free 账号可进入提链流程。"""
    row = record or {}
    plan = _text(row.get("current_plan_type") or row.get("plan_type")).lower()
    return plan == "free" and promotion_kind_from_record(row) in ELIGIBLE_PROMO_KINDS


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
