# -*- coding: utf-8 -*-
"""Per-run JSONL task logs with write-time redaction and bounded reads."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_LOG_ROOT = Path(tempfile.gettempdir()) / "turb-task-logs" if "unittest" in sys.modules else _PROJECT_ROOT / "注册日志"
_LOG_ROOT = Path(os.getenv("TASK_RUN_LOG_ROOT") or _DEFAULT_LOG_ROOT)
_TASK_LOG_ROOT = _LOG_ROOT / "tasks"
_LOCK = threading.RLock()
_SECRET_PARTS = ("password", "otp", "secret", "authorization", "cookie", "token")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}")
_PROXY_RE = re.compile(r"(?P<scheme>https?://)[^/@\s]+@", re.IGNORECASE)
_TEXT_SECRET_RE = re.compile(
    r"(?i)\b(password|passcode|otp|one[-_ ]time[ -]code|secret|token|access[_ -]?token|refresh[_ -]?token|authorization|cookie)\b"
    r"\s*[:=]\s*([^\s,;]+)"
)


def _safe_component(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "").strip()).strip("-")
    return text[:96] or "unknown"


def build_path(*, task_uuid: str, run_no: int, run_uuid: str) -> str:
    path = (
        _TASK_LOG_ROOT
        / _safe_component(task_uuid)
        / "runs"
        / f"{max(1, int(run_no or 1))}-{_safe_component(run_uuid)}"
        / "run.jsonl"
    )
    return str(path)


def redact_text(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    text = _JWT_RE.sub("[REDACTED_TOKEN]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _PROXY_RE.sub(r"\g<scheme>***@", text)
    text = _TEXT_SECRET_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text[: max(0, int(limit))]


def scrub(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return "[truncated]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:100]:
            key = str(raw_key)[:100]
            lowered = key.lower()
            if any(part in lowered for part in _SECRET_PARTS):
                continue
            if lowered in {"proxy", "proxy_url", "proxy_used"}:
                result[key] = redact_text(raw_value, 500)
            else:
                result[key] = scrub(raw_value, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [scrub(item, depth + 1) for item in list(value)[:100]]
    if isinstance(value, (str, bytes)):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(value, 1000)


def _validated_path(log_file: str | Path) -> Path:
    path = Path(str(log_file or "")).expanduser()
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    resolved = path.resolve()
    root = _LOG_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("任务日志路径不在受控目录内")
    return resolved


def append(
    log_file: str | Path | None,
    *,
    level: str,
    message: str,
    task_id: int | None = None,
    run_id: int | None = None,
    stage: str = "event",
    event_type: str = "note.info",
    fields: dict | None = None,
    created_at: datetime | str | None = None,
) -> bool:
    """Append one redacted JSONL record; logging failure never changes task result."""
    if not log_file:
        return False
    try:
        path = _validated_path(log_file)
        if isinstance(created_at, datetime):
            ts = created_at.astimezone(timezone.utc).isoformat()
        else:
            ts = str(created_at or datetime.now(timezone.utc).isoformat())
        record = {
            "ts": ts,
            "level": str(level or "INFO").upper()[:16],
            "task_id": int(task_id) if task_id is not None else None,
            "run_id": int(run_id) if run_id is not None else None,
            "stage": str(stage or "event")[:80],
            "event_type": str(event_type or "note.info")[:120],
            "message": redact_text(message, 4000),
            "fields": scrub(fields or {}),
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        return True
    except Exception:
        return False


class TaskRunLogHandler(logging.Handler):
    """Logging handler that writes redacted JSONL into one Run log."""

    def __init__(
        self,
        log_file: str | Path,
        *,
        task_id: int | None = None,
        run_id: int | None = None,
        stage: str = "runtime",
    ):
        super().__init__(level=logging.DEBUG)
        self.log_file = str(log_file)
        self.task_id = int(task_id) if task_id is not None else None
        self.run_id = int(run_id) if run_id is not None else None
        self.stage = str(stage or "runtime")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info:
                message = f"{message}\n{logging.Formatter().formatException(record.exc_info)}"
            append(
                self.log_file,
                level=record.levelname,
                message=message,
                task_id=self.task_id,
                run_id=self.run_id,
                stage=self.stage,
                event_type="log.record",
                fields={"logger": record.name, "thread": record.threadName},
                created_at=datetime.fromtimestamp(record.created, tz=timezone.utc),
            )
        except Exception:
            self.handleError(record)


def read_incremental(
    log_file: str | Path | None,
    *,
    cursor: int | None = None,
    limit: int = 500,
    max_bytes: int = 256_000,
) -> dict[str, Any]:
    """Read a bounded JSONL page. Without a cursor, return the latest lines."""
    if not log_file:
        return {"items": [], "next_cursor": 0, "has_more": False, "available": False}
    try:
        path = _validated_path(log_file)
    except ValueError:
        return {"items": [], "next_cursor": 0, "has_more": False, "available": False}
    if not path.exists() or not path.is_file():
        return {"items": [], "next_cursor": 0, "has_more": False, "available": False}
    size = path.stat().st_size
    line_limit = max(1, min(2000, int(limit or 500)))
    byte_limit = max(4096, min(2_000_000, int(max_bytes or 256_000)))
    requested = None if cursor is None else max(0, min(size, int(cursor)))
    start = max(0, size - byte_limit) if requested is None else requested
    with path.open("rb") as handle:
        handle.seek(start)
        if start > 0 and requested is None:
            handle.readline()
        if requested is None:
            raw = handle.read(byte_limit)
            lines = raw.decode("utf-8", errors="replace").splitlines()
            if len(lines) > line_limit:
                lines = lines[-line_limit:]
        else:
            chunks: list[bytes] = []
            consumed = 0
            while len(chunks) < line_limit and consumed < byte_limit:
                line = handle.readline(min(64_000, byte_limit - consumed))
                if not line:
                    break
                chunks.append(line)
                consumed += len(line)
            lines = b"".join(chunks).decode("utf-8", errors="replace").splitlines()
        next_cursor = handle.tell()
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except (TypeError, ValueError, json.JSONDecodeError):
            value = {"level": "INFO", "message": redact_text(line), "event_type": "log.text"}
        if isinstance(value, dict):
            items.append(scrub(value))
    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": next_cursor < size,
        "available": True,
        "size": size,
    }
