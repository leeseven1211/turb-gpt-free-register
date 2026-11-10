"""账号列表和批量固定名单共用的版本化查询契约。"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Mapping

FILTER_FIELDS = (
    "id", "email", "source", "registration_driver", "token", "password",
    "promotion", "totp", "risk", "codex", "account_status", "email_status",
)
FIELD_LABELS = {
    "id": "账号 ID", "email": "邮箱 / 姓名", "source": "来源",
    "registration_driver": "注册驱动", "token": "Token", "password": "密码",
    "promotion": "Plus 优惠", "totp": "2FA", "risk": "封号邮件",
    "codex": "Codex", "account_status": "账号状态", "email_status": "邮箱状态",
}
STATIC_VALUES = {
    "registration_driver": ["roxy", "roxy_oss", "protocol", "protocol_oss", "protocol_oss_2", "cloakbrowser", "unknown"],
    "token": ["has", "none", "expired", "invalid_401", "invalid_403", "invalid_other"],
    "password": ["has", "none"],
    "promotion": ["free_trial", "half_price", "other_discount", "other_promo", "none", "unknown", "pending", "failed", "not_applicable"],
    "totp": ["enabled", "disabled"], "risk": ["detected", "clear", "pending"],
    "email_status": ["invalid", "unmarked"],
}


class AccountQueryError(ValueError):
    """可定位到字段的查询格式错误。"""

    def __init__(self, message: str, field: str = "query"):
        super().__init__(message)
        self.field = field


def _values(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise AccountQueryError("列筛选必须为字符串数组。")
    if len(value) > 100:
        raise AccountQueryError("单列筛选值过多。")
    result = {item.strip().lower() for item in value if item.strip()}
    if any(len(item) > 200 for item in result):
        raise AccountQueryError("筛选值过长。")
    return sorted(result)


def normalize_query(raw: Mapping[str, Any] | None, *, strict: bool = True) -> dict:
    """规范化请求；旧列表兼容入口保留既有宽松日期/归档解析。"""
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise AccountQueryError("账号筛选必须是对象。")
    known = {"schema_version", "entity", "archived", "date_from", "date_to", "q", "plan", "filters", "order", "limit"}
    if strict and set(raw) - known:
        raise AccountQueryError("存在不支持的查询字段。", sorted(set(raw) - known)[0])
    version = raw.get("schema_version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version != 1 or raw.get("entity", "account") != "account":
        raise AccountQueryError("不支持的账号查询版本或实体。")
    archived = str(raw.get("archived", "0")).lower().strip()
    archived = {"1": "only", "true": "only", "yes": "only", "include": "all"}.get(archived, archived)
    if archived not in {"0", "only", "all"}:
        if strict:
            raise AccountQueryError("归档范围无效。", "archived")
        archived = "0"
    dates = {}
    for field in ("date_from", "date_to"):
        value = raw.get(field) or ""
        if not isinstance(value, str):
            raise AccountQueryError("日期必须使用 YYYY-MM-DD。", field)
        if value and strict:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError:
                raise AccountQueryError("日期必须使用 YYYY-MM-DD。", field) from None
        dates[field] = value[:10]
    if strict and dates["date_from"] and dates["date_to"] and dates["date_from"] > dates["date_to"]:
        raise AccountQueryError("开始日期不能晚于结束日期。", "date_to")
    filters = raw.get("filters") or {}
    if not isinstance(filters, Mapping):
        raise AccountQueryError("列筛选必须是对象。", "filters")
    if strict and set(filters) - set(FILTER_FIELDS):
        raise AccountQueryError("存在不支持的列筛选。", "filters")
    clean = {}
    for key in FILTER_FIELDS:
        value = filters.get(key, "" if key in {"id", "email"} else [])
        if key in {"id", "email"}:
            if not isinstance(value, str) or len(value) > 1000:
                raise AccountQueryError("文本筛选格式无效或过长。", key)
            clean[key] = value.strip()
        else:
            clean[key] = _values(value)
    aliases = {"eligible": ["free_trial"], "ineligible": ["none"], "discount": ["half_price", "other_discount"]}
    clean["promotion"] = sorted({v for old in clean["promotion"] for v in aliases.get(old, [old])})
    if strict:
        for key, allowed in STATIC_VALUES.items():
            if set(clean[key]) - set(allowed):
                raise AccountQueryError("列筛选包含不支持的值。", key)
    q = raw.get("q") or ""
    if not isinstance(q, str) or len(q) > 1000:
        raise AccountQueryError("搜索内容格式无效或超过 1,000 字符。", "q")
    from core.accounts.search import parse_account_search
    parse_account_search(q)
    order = raw.get("order") or [{"field": "id", "direction": "desc"}]
    if order != [{"field": "id", "direction": "desc"}]:
        raise AccountQueryError("当前支持按账号 ID 倒序选择。", "order")
    limit = raw.get("limit")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100000):
        raise AccountQueryError("账号范围上限必须为 1 至 100,000 的整数。", "limit")
    return {"schema_version": 1, "entity": "account", "archived": archived, **dates,
            "q": q.strip(), "plan": _values(raw.get("plan")), "filters": clean,
            "order": order, "limit": limit}


def from_legacy(*, archived="0", plan="", q="", date_from="", date_to="", filters=None) -> dict:
    values = dict(filters or {})
    if not values.get("promotion") and values.get("trial"):
        values["promotion"] = values["trial"]
    return normalize_query({"archived": archived, "plan": plan, "q": q,
                            "date_from": date_from, "date_to": date_to, "filters": values}, strict=False)


def compile_query(spec: Mapping[str, Any], *, strict: bool = True) -> tuple[str, list]:
    """只使用现有列表谓词，SQL 中的账号别名固定为 a。"""
    spec = normalize_query(spec, strict=strict)
    from core.storage.admin_repository import _compile_account_predicates
    filters = {key: ",".join(value) if isinstance(value, list) else value for key, value in spec["filters"].items()}
    where, params = _compile_account_predicates(spec["archived"], ",".join(spec["plan"]), spec["q"],
                                                spec["date_from"], spec["date_to"], filters)
    return " AND ".join(where) or "TRUE", params


def query_hash(spec: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(normalize_query(spec), sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def query_schema() -> dict:
    return {"version": 1, "entity": "account", "order": [{"field": "id", "direction": "desc"}],
            "fields": [{"key": key, "label": FIELD_LABELS[key], "type": "text" if key in {"id", "email"} else "multi",
                        "values": STATIC_VALUES.get(key, []), "enum_source": "static" if key in STATIC_VALUES else "facets"}
                       for key in FILTER_FIELDS]}
