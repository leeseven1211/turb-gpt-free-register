# -*- coding: utf-8 -*-
"""Small, summary-only browser traffic accounting boundary.

This module accepts already-observed Roxy/CDP event metadata and persists only
byte counters, request counters, timing, availability, and durable
correlation IDs.  It deliberately has no dependency on the raw diagnostic
capture implementation, whose purpose and retention rules are different.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from core import record_store

logger = logging.getLogger(__name__)

TRAFFIC_SUMMARIES = record_store.BROWSER_TRAFFIC
_HTTP_KINDS = {"http", "http_request", "network_request", "request"}
_WEBSOCKET_KINDS = {"websocket_frame", "websocket_message"}
_TRAFFIC_WINDOWS = frozenset({"all", "1h", "24h", "7d"})
_BEIJING = timezone(timedelta(hours=8))
_CACHE_COUNTER_KEYS = (
    "cache_local_request_count", "cache_native_request_count",
    "cache_local_served_bytes", "cache_avoided_upstream_bytes",
    "cache_fill_download_bytes", "cache_fill_request_count",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _int_value(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _event_bytes(event: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = event.get(key)
        if value is not None:
            if isinstance(value, (bytes, bytearray, memoryview)):
                return len(value)
            if key in {"payloadData", "payload", "body"} and isinstance(value, str):
                # Count the observation but never copy the payload into the
                # durable summary or any API response.
                return len(value.encode("utf-8"))
            return _int_value(value)
    return 0


def _event_kind(event: Mapping[str, Any]) -> str:
    return str(event.get("kind") or event.get("type") or "").strip().lower()


def summarize_cdp_events(
    events: Iterable[Mapping[str, Any]],
    *,
    source: str = "roxy_cdp",
    method: str = "cdp",
    started_at: str | None = None,
    ended_at: str | None = None,
) -> dict[str, Any]:
    """Reduce HTTP/WebSocket observations to counters without retaining content."""
    upload_bytes = 0
    download_bytes = 0
    request_count = 0
    failed_count = 0
    unfinished_count = 0
    unknown_count = 0

    for raw_event in events or ():
        event = raw_event if isinstance(raw_event, Mapping) else {}
        kind = _event_kind(event)
        if kind in _HTTP_KINDS:
            request_count += 1
            upload_bytes += _event_bytes(
                event,
                "request_bytes",
                "upload_bytes",
                "request_body_bytes",
            )
            download_bytes += _event_bytes(
                event,
                "response_bytes",
                "download_bytes",
                "response_body_bytes",
                "encoded_data_length",
            )
            status = _int_value(event.get("status") or event.get("response_status"))
            if not event.get("_data_saver_blocked") and (bool(event.get("failed")) or status >= 400):
                failed_count += 1
            if bool(event.get("unfinished")) or (
                "finished" in event and event.get("finished") is False and not event.get("failed")
            ):
                unfinished_count += 1
            continue
        if kind in _WEBSOCKET_KINDS:
            frame_bytes = _event_bytes(event, "bytes", "payload_bytes", "payloadData", "payload")
            direction = str(event.get("direction") or "").strip().lower()
            if direction in {"out", "outgoing", "send", "sent", "upload"}:
                upload_bytes += frame_bytes
            elif direction in {"in", "incoming", "receive", "received", "download"}:
                download_bytes += frame_bytes
            else:
                unknown_count += 1
            continue
        if kind or event:
            unknown_count += 1

    return {
        "source": str(source or "roxy_cdp").strip()[:80] or "roxy_cdp",
        "method": str(method or "cdp").strip()[:80] or "cdp",
        "availability": "available",
        "unavailable_reason": None,
        "started_at": started_at or _now_iso(),
        "ended_at": ended_at or _now_iso(),
        "upload_bytes": upload_bytes,
        "download_bytes": download_bytes,
        "total_bytes": upload_bytes + download_bytes,
        "request_count": request_count,
        "failed_count": failed_count,
        "unfinished_count": unfinished_count,
        "unknown_count": unknown_count,
    }


def _correlation_payload(
    *,
    proxy_lease_id: str | None = None,
    account_id: int | None = None,
    purpose: str | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    registration_job_id: int | None = None,
    route_attempt_no: int | None = None,
) -> dict[str, Any]:
    def optional_int(value: int | None) -> int | None:
        if value is None or str(value).strip() == "":
            return None
        return int(value)

    return {
        "proxy_lease_id": str(proxy_lease_id or "").strip()[:160] or None,
        "account_id": optional_int(account_id),
        "purpose": str(purpose or "").strip()[:80] or None,
        "operation_task_id": optional_int(operation_task_id),
        "operation_run_id": optional_int(operation_run_id),
        "registration_job_id": optional_int(registration_job_id),
        "route_attempt_no": optional_int(route_attempt_no),
    }


def persist_summary(
    *,
    summary_key: str,
    summary: Mapping[str, Any],
    proxy_lease_id: str | None = None,
    account_id: int | None = None,
    purpose: str | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    registration_job_id: int | None = None,
    route_attempt_no: int | None = None,
) -> int:
    """Idempotently persist a summary allowlist; raw event fields are ignored."""
    if not str(summary_key or "").strip():
        raise ValueError("traffic summary_key 不能为空")
    upload = _int_value(summary.get("upload_bytes"))
    download = _int_value(summary.get("download_bytes"))
    payload = {
        "summary_key": str(summary_key).strip()[:240],
        "source": str(summary.get("source") or "roxy_cdp").strip()[:80] or "roxy_cdp",
        "method": str(summary.get("method") or "cdp").strip()[:80] or "cdp",
        "availability": str(summary.get("availability") or "available").strip()[:40] or "available",
        "unavailable_reason": str(summary.get("unavailable_reason") or "").strip()[:240] or None,
        "started_at": summary.get("started_at") or _now_iso(),
        "ended_at": summary.get("ended_at") or _now_iso(),
        "upload_bytes": upload,
        "download_bytes": download,
        "total_bytes": upload + download,
        "request_count": _int_value(summary.get("request_count")),
        "failed_count": _int_value(summary.get("failed_count")),
        "unfinished_count": _int_value(summary.get("unfinished_count")),
        "unknown_count": _int_value(summary.get("unknown_count")),
    }
    payload.update(_correlation_payload(
        proxy_lease_id=proxy_lease_id,
        account_id=account_id,
        purpose=purpose,
        operation_task_id=operation_task_id,
        operation_run_id=operation_run_id,
        registration_job_id=registration_job_id,
        route_attempt_no=route_attempt_no,
    ))
    payload.update({key: _int_value(summary.get(key)) for key in _CACHE_COUNTER_KEYS})
    if isinstance(summary.get("proxy_transport"), Mapping):
        payload["proxy_transport"] = _safe_proxy_transport(summary["proxy_transport"])
    for key in ("resource_details", "js_coverage"):
        if key in summary:
            # 诊断对象由有界采集器构造；只保留其固定元数据投影。
            from core.browser_traffic_diagnostics import sanitize_diagnostics
            payload.update(sanitize_diagnostics({key: summary[key]}))
    if payload["source"] == "protocol_http":
        # 协议统计只接受固定数值/枚举；原始诊断字段不能进入普通汇总。
        payload.update({key: _int_value(summary.get(key)) for key in (
            "duration_ms", "redirect_count", "decoded_response_bytes",
            "upload_observed_count", "download_observed_count", "byte_unknown_count",
        )})
        families = summary.get("status_families")
        payload["status_families"] = {
            family: _int_value(families.get(family)) if isinstance(families, Mapping) else 0
            for family in ("1xx", "2xx", "3xx", "4xx", "5xx", "unknown")
        }
        payload["byte_semantics"] = "http_transfer_body_without_headers_tls"
        for field in ("registration_attempt_id", "registration_run_id"):
            identifier = summary.get(field)
            payload[field] = int(identifier) if identifier is not None else None
    return record_store.upsert_row_by(TRAFFIC_SUMMARIES, "summary_key", payload)


def _safe_proxy_transport(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    fields = ("upload_bytes", "download_bytes", "connection_count", "failed_connection_count",
              "blocked_connection_count", "connect_retry_count", "recovered_connection_count")
    result = {key: _int_value(snapshot.get(key)) for key in fields}
    result.update(available=bool(snapshot.get("available")),
                  total_bytes=result["upload_bytes"] + result["download_bytes"],
                  attribution="proxy_connection_destination",
                  byte_semantics="tunnel_payload_including_tls_without_tcp_ip",
                  note="隧道传输含 TLS、浏览器启动和后台请求；与页面字节重叠，不相加；不含代理握手、TCP/IP 开销、缓存匿名填充或代理商账单")
    destinations = []
    for item in list(snapshot.get("destinations") or [])[:10000]:
        if not isinstance(item, Mapping):
            continue
        host = str(item.get("host") or "").lower().rstrip(".")
        if not re.fullmatch(r"[a-z0-9_.:\[\]-]{1,253}", host):
            continue
        row = {key: _int_value(item.get(key)) for key in fields}
        row.update(host=host, port=min(65535, _int_value(item.get("port"))),
                   total_bytes=row["upload_bytes"] + row["download_bytes"])
        destinations.append(row)
    result["destinations"] = destinations
    for key in fields[2:]:
        result[key] = sum(row[key] for row in destinations)
    return result


def _transport_window(snapshot, baseline):
    """保留窗口再次使用时仅计新窗口，避免重复累计历史隧道字节。"""
    fields = ("upload_bytes", "download_bytes", "connection_count", "failed_connection_count",
              "blocked_connection_count", "connect_retry_count", "recovered_connection_count")
    result = dict(snapshot)
    for key in fields:
        result[key] = max(0, _int_value(snapshot.get(key)) - _int_value(baseline.get(key)))
    prior = {(row.get("host"), row.get("port")): row for row in baseline.get("destinations", [])}
    result["destinations"] = []
    for row in snapshot.get("destinations", []):
        before = prior.get((row.get("host"), row.get("port")), {})
        delta = {key: max(0, _int_value(row.get(key)) - _int_value(before.get(key))) for key in fields}
        if any(delta.values()):
            result["destinations"].append(dict(delta, host=row.get("host"), port=row.get("port")))
    return _safe_proxy_transport(result)


def record_unavailable(
    *,
    summary_key: str,
    source: str,
    method: str,
    reason: str,
    proxy_lease_id: str | None = None,
    account_id: int | None = None,
    purpose: str | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    registration_job_id: int | None = None,
    route_attempt_no: int | None = None,
) -> int:
    return persist_summary(
        summary_key=summary_key,
        summary={
            "source": source,
            "method": method,
            "availability": "unavailable",
            "unavailable_reason": reason,
            "upload_bytes": 0,
            "download_bytes": 0,
            "request_count": 0,
            "failed_count": 0,
            "unfinished_count": 0,
            "unknown_count": 1,
        },
        proxy_lease_id=proxy_lease_id,
        account_id=account_id,
        purpose=purpose,
        operation_task_id=operation_task_id,
        operation_run_id=operation_run_id,
        registration_job_id=registration_job_id,
        route_attempt_no=route_attempt_no,
    )


def _traffic_window_cutoff(window: str | None) -> datetime | None:
    value = str(window or "all").strip().lower()
    if value not in _TRAFFIC_WINDOWS:
        raise ValueError("流量时间范围必须是 all、1h、24h 或 7d")
    hours = {"1h": 1, "24h": 24, "7d": 24 * 7}.get(value)
    return datetime.now(timezone.utc) - timedelta(hours=hours) if hours else None


def _traffic_filter_where(
    *,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
    available_only: bool = False,
) -> tuple[str, list[Any]]:
    where = ["1 = 1"]
    params: list[Any] = []
    if available_only:
        where.append('"availability" = %s')
        params.append("available")
    state_value = str(state or "all").strip().lower()[:40]
    if state_value not in {"", "all"}:
        state_value = "available" if state_value == "observed" else state_value
        where.append('"availability" = %s')
        params.append(state_value)
    purpose_value = str(purpose or "").strip()[:80]
    if purpose_value and purpose_value.lower() != "all":
        where.append('"purpose" = %s')
        params.append(purpose_value)
    search_value = str(search or "").strip()[:160]
    if search_value:
        pattern = f"%{search_value}%"
        where.append(
            "(" + " OR ".join(
                f'CAST("{column}" AS TEXT) ILIKE %s'
                for column in (
                    "summary_key", "source", "method", "proxy_lease_id", "account_id",
                    "purpose", "operation_task_id", "operation_run_id", "registration_job_id",
                )
            ) + ")"
        )
        params.extend([pattern] * 9)
    cutoff = _traffic_window_cutoff(window)
    if cutoff is not None:
        where.append(
            "(NULLIF(\"started_at\", '')::timestamptz >= %s "
            "OR NULLIF(\"ended_at\", '')::timestamptz >= %s)"
        )
        params.extend([cutoff, cutoff])
    return " AND ".join(where), params


def list_summaries(
    *,
    limit: int = 200,
    offset: int = 0,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
    available_only: bool = False,
) -> list[dict[str, Any]]:
    where, params = _traffic_filter_where(
        window=window,
        state=state,
        purpose=purpose,
        search=search,
        available_only=available_only,
    )
    return record_store.list_rows(
        TRAFFIC_SUMMARIES,
        where=where,
        params=params,
        order_by="id DESC",
        limit=max(1, min(500, int(limit or 200))),
        offset=max(0, int(offset or 0)),
    )


def list_summaries_with_total(
    *,
    limit: int = 200,
    offset: int = 0,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
    available_only: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """在同一事务快照内读取流量页面和筛选后总数。"""
    from core import postgres_store
    from psycopg.rows import dict_row

    where, params = _traffic_filter_where(
        window=window,
        state=state,
        purpose=purpose,
        search=search,
        available_only=available_only,
    )
    record_store.init()
    page_limit = max(1, min(500, int(limit or 200)))
    page_offset = max(0, int(offset or 0))
    table = postgres_store.qualified(TRAFFIC_SUMMARIES.name)
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        # 列表和总数必须读取同一数据库快照，避免记录变化造成页数与总数不一致。
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cur.execute(
            f"SELECT * FROM {table} WHERE {where} ORDER BY id DESC LIMIT %s OFFSET %s",
            (*params, page_limit, page_offset),
        )
        items = [record_store.merge_row(TRAFFIC_SUMMARIES, row) for row in cur.fetchall()]
        cur.execute(f"SELECT count(*) AS n FROM {table} WHERE {where}", params)
        total = int(cur.fetchone()["n"])
        return items, total


def count_summaries(
    *,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
    available_only: bool = False,
) -> int:
    where, params = _traffic_filter_where(
        window=window,
        state=state,
        purpose=purpose,
        search=search,
        available_only=available_only,
    )
    return record_store.count_rows(TRAFFIC_SUMMARIES, where=where, params=params)


def summary_metrics() -> dict[str, Any]:
    """从可观测记录返回累计指标和北京时间当天指标。"""
    from core import postgres_store
    from psycopg.rows import dict_row

    beijing_now = datetime.now(timezone.utc).astimezone(_BEIJING)
    day_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_utc = day_start.astimezone(timezone.utc)
    day_end_utc = day_start_utc + timedelta(days=1)
    record_store.init()
    table = postgres_store.qualified(TRAFFIC_SUMMARIES.name)
    time_expr = 'NULLIF("started_at", \'\')::timestamptz'
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                COALESCE(SUM("total_bytes"), 0) AS total_observed_bytes,
                COALESCE(SUM("total_bytes") FILTER (
                    WHERE {time_expr} >= %s AND {time_expr} < %s
                ), 0) AS today_observed_bytes,
                COUNT(*) FILTER (
                    WHERE {time_expr} >= %s AND {time_expr} < %s
                    AND "source" <> 'protocol_http'
                ) AS today_observed_browser_records,
                COUNT(*) FILTER (
                    WHERE {time_expr} >= %s AND {time_expr} < %s
                ) AS today_observed_request_records,
                COUNT(*) FILTER (
                    WHERE {time_expr} >= %s AND {time_expr} < %s
                    AND "source" = 'protocol_http'
                ) AS today_observed_protocol_records
              FROM {table}
             WHERE "availability" = %s
            """,
            (day_start_utc, day_end_utc, day_start_utc, day_end_utc,
             day_start_utc, day_end_utc, day_start_utc, day_end_utc, "available"),
        )
        traffic = cur.fetchone()
    from core import proxy_lease_store

    return {
        "total_bytes": int(traffic["total_observed_bytes"] or 0),
        "today_bytes": int(traffic["today_observed_bytes"] or 0),
        "today_browser_count": int(traffic["today_observed_browser_records"] or 0),
        "today_request_count": int(traffic["today_observed_request_records"] or 0),
        "today_protocol_count": int(traffic["today_observed_protocol_records"] or 0),
        # proxy_leases 历史上按北京时间本地无时区时间保存。
        "today_route_count": proxy_lease_store.count_leases(
            acquired_since=day_start.replace(tzinfo=None),
            acquired_before=(day_start + timedelta(days=1)).replace(tzinfo=None),
        ),
    }


def aggregate_summaries(rows: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    items = list(rows if rows is not None else list_summaries())
    fields = (
        "upload_bytes",
        "download_bytes",
        "total_bytes",
        "request_count",
        "failed_count",
        "unfinished_count",
        "unknown_count",
    )
    result = {field: sum(_int_value(row.get(field)) for row in items) for field in fields}
    result["summary_count"] = len(items)
    result["unavailable_count"] = sum(
        1 for row in items if str(row.get("availability") or "") == "unavailable"
    )
    return result


def _content_size(value: Any) -> int:
    """Measure one transient CDP value without retaining it in the summary."""
    if value is None:
        return 0
    if isinstance(value, (bytes, bytearray, memoryview)):
        return len(value)
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def _safe_resource_label(url: Any) -> str:
    """Return a bounded host/path label without query strings or identifiers."""
    try:
        parsed = urlsplit(str(url or ""))
        host = str(parsed.hostname or "").strip().lower()
        path = str(parsed.path or "/")
        path = re.sub(r"/[^/]{1,120}@[^/]+", "/<redacted>", path)
        path = re.sub(r"/[A-Fa-f0-9]{24,}(?=/|$)", "/<id>", path)
        path = re.sub(r"/[A-Za-z0-9_-]{40,}(?=/|$)", "/<id>", path)
        label = f"{host}{path}" if host else path
        return label[:180]
    except Exception:
        return "<unknown>"


def _is_local_browser_resource(url: Any) -> bool:
    """Exclude Roxy/Chromium loopback resources from provider traffic bytes."""
    try:
        parsed = urlsplit(str(url or ""))
        return (parsed.scheme or "").lower() in {"devtools", "chrome-extension"} or (
            (parsed.hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}
        )
    except Exception:
        return False


class _SummaryOnlyCDPSession:
    """Adapter consumed by the existing collector that keeps counters only."""

    body_capture_enabled = False
    summary_only = True

    def __init__(self, profile_id: str) -> None:
        from core.browser_traffic_diagnostics import BrowserTrafficDiagnostics
        self.diagnostics = BrowserTrafficDiagnostics()
        self.js_coverage_enabled = self.diagnostics.coverage_enabled
        self.job_id = f"traffic-{str(profile_id or 'roxy')[:32]}"
        self.current_stage = "browser"
        self.websocket_frame_count = 0
        self.started_at = _now_iso()
        self.upload_bytes = 0
        self.download_bytes = 0
        self.request_count = 0
        self.failed_count = 0
        self.unfinished_count = 0
        self.unknown_count = 0
        self.resource_type_bytes: Counter[str] = Counter()
        self.resource_type_requests: Counter[str] = Counter()
        self.cache_local_request_count = 0
        self.cache_native_request_count = 0
        self.cache_local_served_bytes = 0
        # 与现有 CDP 消费者共享同一条事件流，仅向认证回执分发白名单元数据。
        self.submission_observer = None
        self.auth_diagnostic_observer = None

    @staticmethod
    def _submission_endpoint_kind(url: Any) -> str:
        path = str(urlsplit(str(url or "")).path or "").lower()
        if path.endswith("/api/auth/csrf"):
            return "nextauth_csrf"
        if "/api/auth/signin/" in path:
            return "nextauth_signin"
        if path.endswith(("/api/accounts/password", "/api/accounts/user/register")) or "/password" in path and "/api/" in path:
            return "password_submit"
        if "email-otp" in path and path.endswith(("/validate", "/verify")):
            return "otp_submit"
        if "email-otp" in path and path.endswith(("/send", "/resend")):
            return "otp_resend"
        return ""

    def _observe_submission(self, record: Mapping[str, Any], *, response: bool = False) -> None:
        self._observe_auth_diagnostic(record, phase="complete" if response else "request")
        callback = self.submission_observer
        if not callable(callback):
            return
        endpoint_kind = self._submission_endpoint_kind(record.get("url"))
        if not endpoint_kind:
            return
        http_method = str(record.get("method") or "").strip().upper()
        expected_method = "GET" if endpoint_kind == "nextauth_csrf" else "POST"
        # 方法缺失或页面 GET 不能证明业务提交，禁止补成 POST。
        if http_method != expected_method:
            return
        try:
            callback({
                "endpoint_kind": endpoint_kind,
                "http_method": http_method,
                "http_status": record.get("status") if response else None,
                "duration_ms": record.get("duration_ms"),
                "response": bool(response),
                # 仅在当前 CDP 连接内做请求/响应配对；不进入持久事实或公共投影。
                "request_id": record.get("request_id"),
                "target_id": record.get("target_id"),
            })
        except Exception:
            logger.debug("[浏览器流量] 认证提交事实分发失败", exc_info=True)

    def _observe_auth_diagnostic(self, record: Mapping[str, Any], *, phase: str) -> None:
        callback = self.auth_diagnostic_observer
        if callable(callback):
            try:
                callback(record, phase=phase)
            except Exception:
                logger.debug("[浏览器流量] 认证接口诊断分发失败", exc_info=True)

    def record_network(self, record: Mapping[str, Any]) -> None:
        item = record if isinstance(record, Mapping) else {}
        self._observe_submission(item, response=True)
        self.request_count += 1
        blocked_by_data_saver = bool(item.get("_data_saver_blocked"))
        local_resource = _is_local_browser_resource(item.get("url"))
        cache_source = str(item.get("cache_source") or "network")
        locally_fulfilled = cache_source == "local"
        if locally_fulfilled:
            self.cache_local_request_count += 1
            self.cache_local_served_bytes += _int_value(item.get("encoded_data_length"))
        elif cache_source == "native":
            self.cache_native_request_count += 1
        elif cache_source == "unknown":
            self.unknown_count += 1
        upload_bytes = 0 if blocked_by_data_saver or local_resource or locally_fulfilled else (
            _int_value(item.get("request_body_bytes")) or _content_size(item.get("request_body"))
        )
        download_bytes = 0 if blocked_by_data_saver or local_resource or locally_fulfilled else _int_value(item.get("encoded_data_length"))
        self.upload_bytes += upload_bytes
        self.download_bytes += download_bytes
        resource_type = str(item.get("resource_type") or "other").strip().lower() or "other"
        self.resource_type_requests[resource_type] += 1
        self.resource_type_bytes[resource_type] += upload_bytes + download_bytes
        self.diagnostics.record_resource(item, upload_bytes, download_bytes)
        status = _int_value(item.get("status"))
        if not blocked_by_data_saver and (item.get("failure") or status >= 400):
            self.failed_count += 1
        if item.get("response_body_omitted") == "target_closed" and not item.get("failure"):
            self.unfinished_count += 1

    def record(self, event: Mapping[str, Any]) -> None:
        item = event if isinstance(event, Mapping) else {}
        kind = _event_kind(item)
        if kind == "websocket_frame":
            size = _int_value(item.get("payload_bytes")) or _content_size(item.get("payload"))
            direction = str(item.get("direction") or "").strip().lower()
            if direction in {"out", "outgoing", "send", "sent", "upload"}:
                self.upload_bytes += size
            elif direction in {"in", "incoming", "receive", "received", "download"}:
                self.download_bytes += size
            else:
                self.unknown_count += 1
            self.resource_type_requests["websocket"] += 1
            self.resource_type_bytes["websocket"] += size
        elif kind == "capture_warning":
            self.unknown_count += 1

    def summary(self) -> dict[str, Any]:
        return {
            "source": "roxy_cdp",
            "method": "cdp",
            "availability": "available",
            "unavailable_reason": None,
            "started_at": self.started_at,
            "ended_at": _now_iso(),
            "upload_bytes": self.upload_bytes,
            "download_bytes": self.download_bytes,
            "total_bytes": self.upload_bytes + self.download_bytes,
            "request_count": self.request_count,
            "failed_count": self.failed_count,
            "unfinished_count": self.unfinished_count,
            "unknown_count": self.unknown_count,
            "resource_type_bytes": dict(sorted(self.resource_type_bytes.items())),
            "resource_type_requests": dict(sorted(self.resource_type_requests.items())),
            "cache_local_request_count": self.cache_local_request_count,
            "cache_native_request_count": self.cache_native_request_count,
            "cache_local_served_bytes": self.cache_local_served_bytes,
            **self.diagnostics.snapshot(),
        }

    def record_js_coverage(self, payload, *, supported=True):
        self.diagnostics.record_coverage(payload, supported=supported)


def _new_roxy_collector(session: _SummaryOnlyCDPSession, debugger_address: str):
    from core.registration_debug import RoxyCDPCollector

    return RoxyCDPCollector(session, debugger_address)


class RoxyTrafficCapture:
    """Reduce one Roxy lifetime to a durable summary-only traffic row."""

    _CORRELATION_KEYS = frozenset({
        "proxy_lease_id", "account_id", "purpose", "operation_task_id",
        "operation_run_id", "registration_job_id", "route_attempt_no",
    })

    def __init__(self, opened, correlation: Mapping[str, Any] | None = None) -> None:
        self.summary_key = f"roxy:{uuid.uuid4().hex}"
        self.proxy_relay = getattr(opened, "proxy_relay", None)
        # 新端口从浏览器启动前计量；保留窗口重用时从本轮开始计量，排除任务间闲置流量。
        self.transport_baseline = (
            self.proxy_relay.traffic_snapshot()
            if self.proxy_relay is not None and hasattr(self.proxy_relay, "_traffic_capture_baseline") else {}
        )
        self.session = _SummaryOnlyCDPSession(getattr(opened, "profile_id", ""))
        self.data_saver = None
        self.public_asset_cache = None
        self.correlation: dict[str, Any] = {}
        self.update_context(**dict(correlation or {}))
        self.collector = None
        self.unavailable_reason = ""
        self.finished = False
        debugger_address = str(getattr(opened, "debugger_address", "") or "").strip()
        if not debugger_address:
            self.unavailable_reason = "roxy_debugger_address_unavailable"
            return
        try:
            self.collector = _new_roxy_collector(self.session, debugger_address)
            self.collector.start()
        except Exception as exc:
            self.collector = None
            self.unavailable_reason = f"roxy_cdp_start_failed:{type(exc).__name__}"[:240]
            logger.warning("[浏览器流量] Roxy CDP 采集启动失败：%s", type(exc).__name__)

    def set_data_saver(self, data_saver: Any) -> None:
        """Attach the optional-request blocker to the existing CDP observer."""
        self.data_saver = data_saver
        if self.collector is not None:
            self.collector.data_saver = data_saver

    def set_submission_observer(self, callback: Any) -> None:
        """把认证请求元数据分发给同一 CDP 采集连接的回执接收者。"""
        self.session.submission_observer = callback

    def set_auth_diagnostic_observer(self, callback: Any) -> None:
        """共用已有 CDP 连接记录认证接口元数据，回调负责限制字段和容量。"""
        self.session.auth_diagnostic_observer = callback

    def set_public_asset_cache(self, cache: Any) -> None:
        """本地回放与匿名填充分别计量，避免把 CDP 本地传输算成代理下载。"""
        self.public_asset_cache = cache
        if self.collector is not None:
            self.collector.public_asset_cache = cache

    def update_context(self, **correlation: Any) -> None:
        for key in self._CORRELATION_KEYS:
            value = correlation.get(key)
            replaceable = self.correlation.get(key) in (None, "")
            if key == "purpose" and self.correlation.get(key) == "roxy_browser":
                replaceable = True
            if value is not None and str(value).strip() != "" and replaceable:
                self.correlation[key] = value

    def stop(self) -> None:
        if self.finished:
            return
        self.finished = True
        if self.collector is not None:
            try:
                self.collector.stop()
            except Exception as exc:
                self.session.unknown_count += 1
                logger.warning("[浏览器流量] Roxy CDP 采集停止异常：%s", type(exc).__name__)
        try:
            if self.unavailable_reason and self.proxy_relay is None:
                record_unavailable(
                    summary_key=self.summary_key,
                    source="roxy_cdp",
                    method="cdp",
                    reason=self.unavailable_reason,
                    **self.correlation,
                )
            else:
                summary = self.session.summary()
                if self.unavailable_reason:
                    summary.update(availability="unavailable", unavailable_reason=self.unavailable_reason)
                if self.proxy_relay is not None:
                    snapshot = self.proxy_relay.traffic_snapshot()
                    summary["proxy_transport"] = _transport_window(snapshot, self.transport_baseline)
                    self.proxy_relay._traffic_capture_baseline = snapshot
                    logger.info("[浏览器流量] 隧道传输=%s 字节，页面可观测=%s 字节；两者重叠不相加，不等于代理商账单",
                                summary["proxy_transport"]["total_bytes"], summary["total_bytes"])
                if self.public_asset_cache is not None:
                    try:
                        stats = self.public_asset_cache.snapshot()
                    except Exception:
                        stats = {}
                        summary["unknown_count"] += 1
                    if stats.get("anonymous_accounting_complete") is False:
                        summary["unknown_count"] += 1
                        logger.warning("[浏览器流量] 公共缓存填充尚未完全收口，下载字节为已观察下界")
                    if stats.get("replay_accounting_complete") is False:
                        summary["unknown_count"] += 1
                        logger.warning("[浏览器流量] 公共缓存回放未完全确认，保留可观测字节并标记计量未知")
                    fill_bytes = _int_value(stats.get("anonymous_fill_bytes"))
                    summary["download_bytes"] += fill_bytes
                    summary["total_bytes"] += fill_bytes
                    summary["cache_fill_download_bytes"] = fill_bytes
                    summary["cache_fill_request_count"] = _int_value(stats.get("anonymous_requests"))
                    summary["cache_avoided_upstream_bytes"] = _int_value(stats.get("avoided_upstream_bytes"))
                    logger.info(
                        "[浏览器流量] 公共缓存：本地命中=%s，原生命中=%s，填充下载=%s 字节，预计避免上游=%s 字节",
                        summary["cache_local_request_count"], summary["cache_native_request_count"],
                        fill_bytes, summary["cache_avoided_upstream_bytes"],
                    )
                logger.info(
                    "[浏览器流量] Roxy资源类型汇总：bytes=%s requests=%s",
                    summary.get("resource_type_bytes") or {},
                    summary.get("resource_type_requests") or {},
                )
                self.session.diagnostics.log()
                persist_summary(
                    summary_key=self.summary_key,
                    summary=summary,
                    **self.correlation,
                )
        except Exception:
            logger.exception("[浏览器流量] 摘要持久化失败")

    def record_network(self, record: Mapping[str, Any]) -> None:
        self.session.record_network(record)

    def record(self, event: Mapping[str, Any]) -> None:
        self.session.record(event)


def start_roxy_capture(opened, **correlation: Any) -> RoxyTrafficCapture:
    # 普通流量归属独立于原始认证上下文开关；只继承同一 native 执行边界。
    from core.task_run_log import current_context
    from core.protocol_traffic import current_correlation

    inherited = current_correlation()
    correlation = {**{key: value for key, value in inherited.items() if key in RoxyTrafficCapture._CORRELATION_KEYS},
                   **correlation}
    relay = getattr(opened, "proxy_relay", None)
    if relay is not None or getattr(opened, "proxy_route_retained", False) is True:
        # 原窗口仍沿用原线路；本轮刚领取的租约不能冒充实际出口。
        origin = getattr(relay, "origin_lease_id", None)
        correlation["proxy_lease_id"] = origin if isinstance(origin, str) and origin else None

    context = current_context()
    task_id, run_id = context.get("task_id"), context.get("run_id")
    if context.get("identifier_namespace") == "operation" and task_id and run_id and all(
        correlation.get(key) in (None, "") or str(correlation[key]) == str(value)
        for key, value in (("operation_task_id", task_id), ("operation_run_id", run_id))
    ):
        correlation = dict(correlation)
        for key, value in (("operation_task_id", task_id), ("operation_run_id", run_id)):
            if correlation.get(key) in (None, ""):
                correlation[key] = value
    existing = getattr(opened, "traffic_capture", None)
    if isinstance(existing, RoxyTrafficCapture):
        existing.update_context(**correlation)
        return existing
    capture = RoxyTrafficCapture(opened, correlation)
    opened.traffic_capture = capture
    return capture


def bind_roxy_capture(opened, **correlation: Any) -> None:
    capture = getattr(opened, "traffic_capture", None)
    if isinstance(capture, RoxyTrafficCapture):
        capture.update_context(**correlation)


def finish_roxy_capture(opened) -> None:
    capture = getattr(opened, "traffic_capture", None)
    if isinstance(capture, RoxyTrafficCapture):
        capture.stop()


__all__ = [
    "TRAFFIC_SUMMARIES",
    "aggregate_summaries",
    "count_summaries",
    "list_summaries",
    "list_summaries_with_total",
    "persist_summary",
    "record_unavailable",
    "RoxyTrafficCapture",
    "start_roxy_capture",
    "bind_roxy_capture",
    "finish_roxy_capture",
    "summarize_cdp_events",
    "summary_metrics",
]
