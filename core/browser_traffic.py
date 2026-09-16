# -*- coding: utf-8 -*-
"""Small, content-free browser traffic summaries.

The collector consumes only CDP event names and byte/status scalars.  It never
stores request URLs, headers, bodies, cookies, or raw diagnostic payloads.
Protocol-only operations use an explicit unavailable row instead of pretending
that HTTP client traffic was observed by a browser.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from core import record_store


TRAFFIC_SUMMARIES = record_store.PROXY_TRAFFIC_SUMMARIES
AVAILABLE = "available"
UNAVAILABLE = "unavailable"
_SAFE_SOURCES = {"roxy", "protocol", "unknown"}
_SAFE_METHODS = {"cdp", "none", "unknown"}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _correlation_from_lease(lease_id: str | None) -> dict[str, Any]:
    if not str(lease_id or "").strip():
        return {}
    try:
        row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", str(lease_id))
    except Exception:
        # In-memory collection remains useful when persistence is unavailable;
        # the caller-provided correlation is still retained in the summary.
        return {}
    if not row:
        return {}
    return {
        key: row.get(key)
        for key in (
            "account_id",
            "purpose",
            "operation_task_id",
            "operation_run_id",
            "registration_job_id",
            "registration_attempt_id",
            "route_attempt_id",
            "route_attempt_no",
        )
        if row.get(key) is not None
    }


def _normalized_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(summary or {})
    lease_id = str(payload.get("lease_id") or "").strip() or None
    correlation = _correlation_from_lease(lease_id)
    for key, value in correlation.items():
        payload.setdefault(key, value)

    availability = str(payload.get("availability") or AVAILABLE).strip().lower()
    if availability not in {AVAILABLE, UNAVAILABLE}:
        availability = UNAVAILABLE
    upload_bytes = _nonnegative_int(payload.get("upload_bytes"))
    download_bytes = _nonnegative_int(payload.get("download_bytes"))
    request_count = _nonnegative_int(payload.get("request_count"))
    failed_count = _nonnegative_int(payload.get("failed_count"))
    unfinished_count = _nonnegative_int(payload.get("unfinished_count"))
    unknown_count = _nonnegative_int(payload.get("unknown_count"))
    source = str(payload.get("source") or "unknown").strip().lower()
    method = str(payload.get("method") or "unknown").strip().lower()
    if availability != AVAILABLE:
        upload_bytes = download_bytes = request_count = failed_count = 0
        unfinished_count = unknown_count = 0

    return {
        "summary_id": str(payload.get("summary_id") or uuid.uuid4().hex)[:160],
        "lease_id": lease_id,
        "account_id": _optional_int(payload.get("account_id")),
        "purpose": str(payload.get("purpose") or "").strip()[:160] or None,
        "operation_task_id": _optional_int(payload.get("operation_task_id")),
        "operation_run_id": _optional_int(payload.get("operation_run_id")),
        "registration_job_id": _optional_int(payload.get("registration_job_id")),
        "registration_attempt_id": _optional_int(payload.get("registration_attempt_id")),
        "route_attempt_id": str(payload.get("route_attempt_id") or "").strip()[:160] or None,
        "route_attempt_no": _optional_int(payload.get("route_attempt_no")),
        "source": source if source in _SAFE_SOURCES else "unknown",
        "method": method if method in _SAFE_METHODS else "unknown",
        "availability": availability,
        "unavailable_reason": str(payload.get("unavailable_reason") or "").strip()[:300] or None,
        "started_at": str(payload.get("started_at") or "").strip()[:80] or None,
        "finished_at": str(payload.get("finished_at") or "").strip()[:80] or None,
        "upload_bytes": upload_bytes,
        "download_bytes": download_bytes,
        "total_bytes": upload_bytes + download_bytes,
        "request_count": request_count,
        "failed_count": failed_count,
        "unfinished_count": unfinished_count,
        "unknown_count": unknown_count,
    }


def persist_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Persist one idempotent fixed-field summary, never arbitrary event data."""
    normalized = _normalized_summary(summary)
    record_store.upsert_row_by(TRAFFIC_SUMMARIES, "summary_id", normalized)
    return normalized


def list_traffic_summaries(
    *,
    lease_id: str | None = None,
    account_id: int | None = None,
    purpose: str | None = None,
    registration_job_id: int | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    record_store.init()
    clauses: list[str] = []
    params: list[Any] = []
    if lease_id:
        clauses.append('"lease_id" = %s')
        params.append(str(lease_id))
    if account_id is not None:
        clauses.append('"account_id" = %s')
        params.append(_optional_int(account_id))
    if purpose:
        clauses.append('"purpose" = %s')
        params.append(str(purpose).strip()[:160])
    if registration_job_id is not None:
        clauses.append('"registration_job_id" = %s')
        params.append(_optional_int(registration_job_id))
    if operation_task_id is not None:
        clauses.append('"operation_task_id" = %s')
        params.append(_optional_int(operation_task_id))
    if operation_run_id is not None:
        clauses.append('"operation_run_id" = %s')
        params.append(_optional_int(operation_run_id))
    rows = record_store.list_rows(
        TRAFFIC_SUMMARIES,
        where=" AND ".join(clauses),
        params=params,
        order_by='"id" DESC',
        limit=max(1, min(1000, int(limit or 200))),
    )
    # Do not expose the generic JSONB extension field even if a legacy writer
    # inserted extra event data into the traffic table.
    return [_normalized_summary(row) for row in rows]


def query_traffic(
    *,
    lease_id: str | None = None,
    account_id: int | None = None,
    purpose: str | None = None,
    registration_job_id: int | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    items = list_traffic_summaries(
        lease_id=lease_id,
        account_id=account_id,
        purpose=purpose,
        registration_job_id=registration_job_id,
        operation_task_id=operation_task_id,
        operation_run_id=operation_run_id,
        limit=limit,
    )
    availability = {str(item.get("availability") or "unknown") for item in items}
    if availability == {AVAILABLE}:
        aggregate_availability = AVAILABLE
    elif availability == {UNAVAILABLE}:
        aggregate_availability = UNAVAILABLE
    elif availability:
        aggregate_availability = "mixed"
    else:
        aggregate_availability = "unknown"
    totals = {
        "total_upload_bytes": sum(_nonnegative_int(item.get("upload_bytes")) for item in items),
        "total_download_bytes": sum(_nonnegative_int(item.get("download_bytes")) for item in items),
        "request_count": sum(_nonnegative_int(item.get("request_count")) for item in items),
        "failed_count": sum(_nonnegative_int(item.get("failed_count")) for item in items),
        "unfinished_count": sum(_nonnegative_int(item.get("unfinished_count")) for item in items),
        "unknown_count": sum(_nonnegative_int(item.get("unknown_count")) for item in items),
    }
    return {
        "items": items,
        "summary_count": len(items),
        "availability": aggregate_availability,
        **totals,
        "total_bytes": totals["total_upload_bytes"] + totals["total_download_bytes"],
    }


class RoxyCdpTrafficCollector:
    """Count safe CDP byte/status scalars while discarding event contents."""

    def __init__(
        self,
        *,
        lease_id: str | None = None,
        account_id: int | None = None,
        purpose: str | None = "registration",
        operation_task_id: int | None = None,
        operation_run_id: int | None = None,
        registration_job_id: int | None = None,
        registration_attempt_id: int | None = None,
        route_attempt_id: str | None = None,
        route_attempt_no: int | None = None,
    ):
        self._base = {
            "lease_id": lease_id,
            "account_id": account_id,
            "purpose": purpose,
            "operation_task_id": operation_task_id,
            "operation_run_id": operation_run_id,
            "registration_job_id": registration_job_id,
            "registration_attempt_id": registration_attempt_id,
            "route_attempt_id": route_attempt_id,
            "route_attempt_no": route_attempt_no,
        }
        self.summary_id = uuid.uuid4().hex
        self.started_at = _now()
        self._finished_at: str | None = None
        self._inflight: set[str] = set()
        self._seen_ids: set[str] = set()
        self._failed_ids: set[str] = set()
        self.upload_bytes = 0
        self.download_bytes = 0
        self.request_count = 0
        self.failed_count = 0
        self.unknown_count = 0

    @staticmethod
    def _event_id(params: Mapping[str, Any]) -> str | None:
        value = str(params.get("requestId") or "").strip()
        return value or None

    def _ensure_id(self, params: Mapping[str, Any], *, count_request: bool = False) -> str | None:
        event_id = self._event_id(params)
        if event_id is None:
            self.unknown_count += 1
            return None
        if event_id not in self._seen_ids:
            self._seen_ids.add(event_id)
            if count_request:
                self.request_count += 1
        return event_id

    def _mark_failed(self, event_id: str | None) -> None:
        if event_id is None:
            self.failed_count += 1
            return
        if event_id not in self._failed_ids:
            self._failed_ids.add(event_id)
            self.failed_count += 1

    def observe_cdp_event(self, method: str, params: Mapping[str, Any] | None = None) -> None:
        """Observe one CDP event; only scalar counters are retained."""
        name = str(method or "").strip()
        data = params if isinstance(params, Mapping) else {}
        if not data and params is not None:
            self.unknown_count += 1

        if name == "Network.requestWillBeSent":
            event_id = self._ensure_id(data, count_request=True)
            if event_id:
                self._inflight.add(event_id)
                request = data.get("request")
                request_size = 0
                if isinstance(request, Mapping):
                    request_size = _nonnegative_int(
                        request.get("bodySize") or request.get("encodedDataLength")
                    )
                self.upload_bytes += request_size or _nonnegative_int(data.get("requestBodySize"))
            return
        if name == "Network.responseReceived":
            event_id = self._ensure_id(data)
            response = data.get("response")
            status = _optional_int(response.get("status")) if isinstance(response, Mapping) else None
            if status is not None and status >= 400:
                self._mark_failed(event_id)
            return
        if name == "Network.loadingFinished":
            event_id = self._ensure_id(data)
            self.download_bytes += _nonnegative_int(data.get("encodedDataLength"))
            if event_id:
                self._inflight.discard(event_id)
            return
        if name == "Network.loadingFailed":
            event_id = self._ensure_id(data)
            self._mark_failed(event_id)
            if event_id:
                self._inflight.discard(event_id)
            return
        if name == "Network.webSocketCreated":
            event_id = self._ensure_id(data, count_request=True)
            if event_id:
                self._inflight.add(event_id)
            return
        if name in {"Network.webSocketFrameSent", "Network.webSocketFrameReceived"}:
            event_id = self._ensure_id(data)
            frame = data.get("response")
            size = _nonnegative_int(frame.get("encodedDataLength")) if isinstance(frame, Mapping) else 0
            if not size and isinstance(frame, Mapping):
                payload_data = frame.get("payloadData")
                if isinstance(payload_data, str):
                    size = len(payload_data.encode("utf-8", errors="replace"))
            if name.endswith("Sent"):
                self.upload_bytes += size
            else:
                self.download_bytes += size
            return
        if name == "Network.webSocketClosed":
            event_id = self._ensure_id(data)
            if event_id:
                self._inflight.discard(event_id)
            return
        if name == "Network.webSocketFrameError":
            self._mark_failed(self._ensure_id(data))
            return
        self.unknown_count += 1

    def finish(self) -> dict[str, Any]:
        if self._finished_at is None:
            self._finished_at = _now()
        return _normalized_summary(
            {
                "summary_id": self.summary_id,
                **self._base,
                "source": "roxy",
                "method": "cdp",
                "availability": AVAILABLE,
                "started_at": self.started_at,
                "finished_at": self._finished_at,
                "upload_bytes": self.upload_bytes,
                "download_bytes": self.download_bytes,
                "request_count": self.request_count,
                "failed_count": self.failed_count,
                "unfinished_count": len(self._inflight),
                "unknown_count": self.unknown_count,
            }
        )

    def persist(self) -> dict[str, Any]:
        return persist_summary(self.finish())


def record_protocol_traffic_unavailable(
    *,
    summary_id: str | None = None,
    lease_id: str | None = None,
    account_id: int | None = None,
    purpose: str | None = "email-change",
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    registration_job_id: int | None = None,
    registration_attempt_id: int | None = None,
    route_attempt_id: str | None = None,
    route_attempt_no: int | None = None,
    reason: str = "protocol task has no browser/CDP traffic",
) -> dict[str, Any]:
    return persist_summary(
        {
            "summary_id": summary_id,
            "lease_id": lease_id,
            "account_id": account_id,
            "purpose": purpose,
            "operation_task_id": operation_task_id,
            "operation_run_id": operation_run_id,
            "registration_job_id": registration_job_id,
            "registration_attempt_id": registration_attempt_id,
            "route_attempt_id": route_attempt_id,
            "route_attempt_no": route_attempt_no,
            "source": "protocol",
            "method": "none",
            "availability": UNAVAILABLE,
            "unavailable_reason": reason,
        }
    )


mark_protocol_traffic_unavailable = record_protocol_traffic_unavailable
