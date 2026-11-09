"""套餐失败的无副作用诊断投影，列表和执行详情共用同一口径。"""
from __future__ import annotations

from typing import Any

from config.countries import ISO_3166_ALPHA2


_CAUSES = {
    "token_http_401": "套餐接口返回 HTTP 401，AT 未通过验证",
    "token_local_expired": "本地检查发现 AT 已过期，未发起套餐请求",
    "token_missing": "账号缺少 AT，未发起套餐请求",
    "token_expired_or_rejected": "AT 已过期或未通过验证，历史记录缺少 HTTP 状态",
    "plan_http_forbidden": "套餐接口返回 HTTP 403，请求被拒绝",
    "plan_http_rate_limited": "套餐接口返回 HTTP 429，请求受到限流",
    "proxy_tunnel_failed": "代理隧道连接失败",
    "proxy_connect_failed": "代理连接失败",
    "proxy_supply_exhausted": "该国代理库存暂缺，累计等待预算已耗尽",
    "proxy_country_mismatch": "代理实际出口国家与查询国家不一致，未发起套餐请求",
    "country_deadline_exhausted": "国家查询总期限已到",
    "country_attempts_exhausted": "该国家套餐请求次数已耗尽",
    "response_invalid": "套餐接口响应格式异常，未返回 JSON 对象",
    "response_missing": "套餐接口响应缺失，本次查询结果未确认",
    "timeout": "套餐查询超时",
    "network_dns_failed": "套餐查询域名解析失败",
    "network_tls_failed": "套餐查询 TLS 连接失败",
    "network_connection_failed": "套餐查询网络连接失败",
    "plan_config_invalid": "套餐查询配置异常",
    "at_refresh_failed": "自动刷新 AT 失败，未发起本轮套餐请求",
    "detail_incomplete": "诊断记录不完整，缺少可确认的套餐失败原因",
}


def classify_plan_failure(detail: dict[str, Any], *, country: str | None = None,
                          local_check_observed: bool = False) -> dict[str, Any]:
    """只使用当前失败回执；缺少 HTTP 证据时不推断本地过期或远端拒绝。"""
    detail = detail if isinstance(detail, dict) else {}
    raw = str(detail.get("error") or "").strip()
    text = raw.lower()
    status = detail.get("http_status")
    status = status if type(status) is int and 100 <= status <= 599 else None
    if status == 401:
        code = "token_http_401"
    elif status == 403:
        code = "plan_http_forbidden"
    elif status == 429:
        code = "plan_http_rate_limited"
    elif status is not None and not 200 <= status < 300:
        code = "plan_http_server_error" if status >= 500 else "plan_http_error"
    elif text in {"token 为空", "账号缺少 access_token", "账号缺少 at", "access_token_missing"}:
        code = "token_missing"
    elif raw in {"AT已过期/失效，请手动查活刷新", "AT已失效", "AT已过期"}:
        local = local_check_observed and "http_status" in detail and (
            raw == "AT已过期/失效，请手动查活刷新" or detail.get("token_expired") is True)
        code = "token_local_expired" if local else "token_expired_or_rejected"
    elif raw.startswith("自动刷新 AT 失败："):
        code = "at_refresh_failed"
    elif "国家查询总期限已到" in raw:
        code = "country_deadline_exhausted"
    elif "请求次数已耗尽" in raw:
        code = "country_attempts_exhausted"
    elif any(marker in raw for marker in ("库存暂缺", "库存不足", "累计等待预算已耗尽")):
        code = "proxy_supply_exhausted"
    elif "实际检测为" in raw and "出口" in raw:
        code = "proxy_country_mismatch"
    elif any(marker in text for marker in ("connect tunnel failed", "err_tunnel_connection_failed")):
        code = "proxy_tunnel_failed"
    elif any(marker in text for marker in ("proxyerror", "proxy connect aborted", "err_proxy_connection_failed")):
        code = "proxy_connect_failed"
    elif any(marker in text for marker in ("不是 json 对象", "响应格式", "jsondecodeerror", "invalid json")):
        code = "response_invalid"
    elif any(marker in text for marker in ("响应缺失", "空响应", "empty response", "no response")):
        code = "response_missing"
    elif any(marker in text for marker in ("timeout", "timed out", "超时", "curl: (28)")):
        code = "timeout"
    elif any(marker in text for marker in ("could not resolve", "name resolution", "curl: (6)", "域名解析")):
        code = "network_dns_failed"
    elif any(marker in text for marker in ("tls", "ssl", "curl: (35)", "curl: (60)")):
        code = "network_tls_failed"
    elif any(marker in text for marker in ("connectionerror", "connecterror", "connection reset", "curl: (7)", "curl: (56)")):
        code = "network_connection_failed"
    elif any(marker in raw for marker in ("网络配置错误", "重试配置错误")):
        code = "plan_config_invalid"
    else:
        code = "detail_incomplete"
    summary = _CAUSES.get(code) or f"套餐接口返回 HTTP {status}"
    result = {"code": code, "summary": summary, "http_status": status}
    country = str(country or detail.get("country") or "").upper().strip()
    if country in ISO_3166_ALPHA2:
        result["country"] = country
    return result


def country_failures_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """优先读取固定分类；旧摘要只能恢复其实际保存的 HTTP 证据。"""
    summary = summary if isinstance(summary, dict) else {}
    rows = summary.get("country_failures")
    if isinstance(rows, list):
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            country = str(row.get("country") or "").upper().strip()
            code = row.get("code")
            if country not in ISO_3166_ALPHA2:
                continue
            if code in _CAUSES:
                item = {"country": country, "code": code, "summary": _CAUSES[code], "http_status": None}
                status = row.get("http_status")
                if type(status) is int and 100 <= status <= 599:
                    item["http_status"] = status
            else:
                item = classify_plan_failure(row, country=country)
            if row.get("event_id") is not None:
                item["event_id"] = row["event_id"]
            result.append(item)
        return result
    latest = {}
    for key in ("promotion_query_history", "plan_check_country_results"):
        for row in summary.get(key) or []:
            if not isinstance(row, dict):
                continue
            country = str(row.get("country") or "").upper().strip()
            if country in ISO_3166_ALPHA2:
                latest[country] = row
    return [classify_plan_failure(row, country=country,
                                 local_check_observed=bool(row.get("error")) and "http_status" in row)
            for country, row in latest.items()
            if row.get("ok") is False or row.get("status") == "failed"]


def country_failures_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """调用方须先限制 Run；逐国仅采用最后一次正式回执，兼容旧 warning。"""
    latest: dict[str, dict] = {}
    fallback: dict[str, dict] = {}
    for event in events:
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        stage = str(detail.get("raw_stage") or event.get("stage") or "").removesuffix("_result")
        if stage != "plan_check":
            continue
        country = str(detail.get("country") or "").upper().strip()
        if country not in ISO_3166_ALPHA2 or type(detail.get("ok")) is not bool:
            continue
        if event.get("event_type") == "promotion.query.recorded":
            latest[country] = event
        elif event.get("event_type") == "note.warning" and detail.get("ok") is False:
            fallback[country] = event
    for country, event in fallback.items():
        latest.setdefault(country, event)
    failures = []
    for country, event in latest.items():
        detail = event["detail"]
        if detail.get("ok") is not False:
            continue
        item = classify_plan_failure(detail, country=country,
                                     local_check_observed=event.get("event_type") == "promotion.query.recorded")
        item["event_id"] = str(event.get("event_id") or event.get("id") or "") or None
        failures.append(item)
    return failures


def summarize_plan_failures(rows: list[dict[str, Any]]) -> str:
    """相同原因合并国家，混合原因逐国展示，保留稳定中文文案。"""
    groups: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        country = str(row.get("country") or "").strip()
        key = (str(row.get("code") or ""), str(row.get("summary") or _CAUSES["detail_incomplete"]))
        groups.setdefault(key, [])
        if country and country not in groups[key]:
            groups[key].append(country)
    return "；".join(("、".join(countries) + "：" if countries else "") + summary
                    for (_, summary), countries in groups.items())
