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
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from core import record_store

logger = logging.getLogger(__name__)

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

    def record_network(self, record: Mapping[str, Any]) -> None:
        item = record if isinstance(record, Mapping) else {}
        self.request_count += 1
        blocked_by_data_saver = bool(item.get("_data_saver_blocked"))
        local_resource = _is_local_browser_resource(item.get("url"))
        upload_bytes = 0 if blocked_by_data_saver or local_resource else (
            _int_value(item.get("request_body_bytes")) or _content_size(item.get("request_body"))
        )
        download_bytes = 0 if blocked_by_data_saver or local_resource else _int_value(item.get("encoded_data_length"))
        self.upload_bytes += upload_bytes
        self.download_bytes += download_bytes
        resource_type = str(item.get("resource_type") or "other").strip().lower() or "other"
        self.resource_type_requests[resource_type] += 1
        self.resource_type_bytes[resource_type] += upload_bytes + download_bytes
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
        }


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
        self.session = _SummaryOnlyCDPSession(getattr(opened, "profile_id", ""))
        self.data_saver = None
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
            if self.unavailable_reason:
                record_unavailable(
                    summary_key=self.summary_key,
                    source="roxy_cdp",
                    method="cdp",
                    reason=self.unavailable_reason,
                    **self.correlation,
                )
            else:
                summary = self.session.summary()
                logger.info(
                    "[浏览器流量] Roxy资源类型汇总：bytes=%s requests=%s",
                    summary.get("resource_type_bytes") or {},
                    summary.get("resource_type_requests") or {},
                )
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
    "list_summaries",
    "persist_summary",
    "record_unavailable",
    "RoxyTrafficCapture",
    "start_roxy_capture",
    "bind_roxy_capture",
    "finish_roxy_capture",
    "summarize_cdp_events",
]
