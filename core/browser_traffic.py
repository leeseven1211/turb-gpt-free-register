# -*- coding: utf-8 -*-
"""Small, summary-only browser traffic accounting boundary.

This module accepts already-observed Roxy/CDP event metadata and persists only
byte counters, request counters, timing, availability, and durable
correlation IDs.  It deliberately has no dependency on the raw diagnostic
capture implementation, whose purpose and retention rules are different.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from core import record_store


TRAFFIC_SUMMARIES = record_store.BROWSER_TRAFFIC
_HTTP_KINDS = {"http", "http_request", "network_request", "request"}
_WEBSOCKET_KINDS = {"websocket_frame", "websocket_message"}


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
            if bool(event.get("failed")) or status >= 400:
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
    return record_store.upsert_row_by(TRAFFIC_SUMMARIES, "summary_key", payload)


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


def list_summaries(*, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    return record_store.list_rows(
        TRAFFIC_SUMMARIES,
        order_by="id DESC",
        limit=max(1, min(500, int(limit or 200))),
        offset=max(0, int(offset or 0)),
    )


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


__all__ = [
    "TRAFFIC_SUMMARIES",
    "aggregate_summaries",
    "list_summaries",
    "persist_summary",
    "record_unavailable",
    "summarize_cdp_events",
]
