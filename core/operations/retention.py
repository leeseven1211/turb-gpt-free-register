# -*- coding: utf-8 -*-
"""Daily, archive-first retention for unified task-center history."""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import operation_task_store
from core.runtime import scheduler_state
from core.operations import run_log as task_run_log


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ARCHIVE_ROOT = _PROJECT_ROOT / "logs" / "task-center-archives"
_DELETE_BATCH_SIZE = 500
_MAX_BATCHES_PER_RUN = 20
SCHEDULER_TASK = "task_center_retention"
_INTERVAL_SECONDS = 24 * 60 * 60
_INITIAL_DELAY_SECONDS = 60
logger = logging.getLogger('core.task_center_retention')
_LOCK = threading.RLock()
_SCHEDULER_STARTED = False


def _archive_scrub(value: Any, depth: int = 0) -> Any:
    """Redact archive values without truncating candidate rows or collections."""
    if depth > 20:
        return "[truncated]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)[:200]
            lowered = key.lower()
            if (
                lowered in task_run_log._PRIVATE_IDENTIFIER_KEYS
                or any(part in lowered for part in task_run_log._SECRET_PARTS)
            ):
                continue
            if lowered in {"proxy", "proxy_url", "proxy_used"}:
                result[key] = task_run_log.redact_text(raw_value, 100_000)
            else:
                result[key] = _archive_scrub(raw_value, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_archive_scrub(item, depth + 1) for item in value]
    if isinstance(value, (str, bytes)):
        return task_run_log.redact_text(value, 1_000_000)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return task_run_log.redact_text(value, 100_000)


def archive_snapshot(snapshot: dict[str, Any], *, archive_root: Path | None = None) -> dict[str, Any]:
    """Write, reread, and verify one redacted gzip archive atomically."""
    root = Path(archive_root or _ARCHIVE_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    safe_payload = _archive_scrub(snapshot)
    created = datetime.now(timezone.utc)
    final_path = root / (
        f"task-center-{created.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}.json.gz"
    )
    tmp_handle = tempfile.NamedTemporaryFile(
        prefix=".task-center-", suffix=".json.gz.tmp", dir=root, delete=False,
    )
    tmp_path = Path(tmp_handle.name)
    tmp_handle.close()
    try:
        with gzip.open(tmp_path, "wt", encoding="utf-8") as handle:
            json.dump(safe_payload, handle, ensure_ascii=False, separators=(",", ":"))
        with gzip.open(tmp_path, "rt", encoding="utf-8") as handle:
            verified = json.load(handle)
        if verified != safe_payload:
            raise RuntimeError("任务中心清理归档回读校验不一致")
        raw = tmp_path.read_bytes()
        tmp_path.replace(final_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    counts = {
        str(key): len(value)
        for key, value in safe_payload.items()
        if isinstance(value, list)
    }
    return {
        "path": str(final_path),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "counts": counts,
    }


def cleanup_once() -> dict[str, Any]:
    """Drain a bounded number of archive-first retention batches."""
    from config import operations as operation_config

    days = int(getattr(operation_config, "TASK_CENTER_RETENTION_DAYS", 7) or 0)
    if days <= 0:
        return {"enabled": False, "deleted_tasks": 0, "deleted_batches": 0, "batches": 0}
    totals: dict[str, Any] = {
        "enabled": True,
        "retention_days": days,
        "deleted_tasks": 0,
        "deleted_batches": 0,
        "removed_log_files": 0,
        "batches": 0,
    }
    for _ in range(_MAX_BATCHES_PER_RUN):
        result = operation_task_store.cleanup_terminal_history(
            retention_days=days,
            limit=_DELETE_BATCH_SIZE,
            archive=archive_snapshot,
        )
        totals["batches"] += 1
        totals["deleted_tasks"] += int(result.get("deleted_tasks") or 0)
        totals["deleted_batches"] += int(result.get("deleted_batches") or 0)
        native_log_files = list(result.get("native_log_files") or [])
        if native_log_files:
            totals["removed_log_files"] += remove_native_task_logs(native_log_files)
        if result.get("archive"):
            totals["last_archive"] = result["archive"]
        if not result.get("has_more"):
            break
    archive_days = int(
        getattr(operation_config, "TASK_CENTER_ARCHIVE_RETENTION_DAYS", 30) or 0
    )
    totals["removed_archives"] = remove_expired_archives(retention_days=archive_days)
    return totals


def remove_expired_archives(
    *, retention_days: int, archive_root: Path | None = None,
) -> int:
    """Remove expired managed archives one file at a time."""
    days = int(retention_days or 0)
    if days <= 0:
        return 0
    root = Path(archive_root or _ARCHIVE_ROOT)
    if not root.exists():
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for path in root.glob("task-center-*.json.gz"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            logger.warning("[TaskCenterRetention] archive removal failed: %s", path, exc_info=True)
    return removed


def remove_native_task_logs(log_files) -> int:
    """Delete only managed native ``run.jsonl`` files, one file at a time."""
    root = task_run_log._TASK_LOG_ROOT.resolve()
    removed = 0
    for raw_path in log_files or ():
        try:
            path = task_run_log.resolve_path(raw_path).resolve()
        except (OSError, ValueError):
            continue
        if path.name != "run.jsonl" or root not in path.parents:
            continue
        try:
            if path.is_file():
                path.unlink()
                removed += 1
        except OSError:
            logger.warning("[TaskCenterRetention] native log removal failed: %s", path, exc_info=True)
            continue
        for directory in (path.parent, path.parent.parent, path.parent.parent.parent):
            if directory == root or root not in directory.parents:
                break
            try:
                directory.rmdir()
            except OSError:
                break
    return removed


def scheduler_enabled() -> bool:
    from config import operations as operation_config

    return int(getattr(operation_config, "TASK_CENTER_RETENTION_DAYS", 7) or 0) > 0


def scheduler_interval_seconds() -> int:
    return _INTERVAL_SECONDS


def _scheduler_loop() -> None:
    scheduler_state.run_periodic(
        task=SCHEDULER_TASK,
        label="TaskCenterRetention",
        work=cleanup_once,
        enabled=scheduler_enabled,
        interval_seconds=scheduler_interval_seconds,
        initial_delay_seconds=_INITIAL_DELAY_SECONDS,
    )


def start_periodic_cleanup() -> bool:
    """Start the persisted daily scheduler at most once per process."""
    global _SCHEDULER_STARTED
    with _LOCK:
        if _SCHEDULER_STARTED:
            return False
        _SCHEDULER_STARTED = True
    threading.Thread(
        target=_scheduler_loop,
        name="task-center-retention",
        daemon=True,
    ).start()
    logger.info(
        "[TaskCenterRetention] scheduler started enabled=%s interval=%ss",
        scheduler_enabled(),
        _INTERVAL_SECONDS,
    )
    return True


def reset_for_tests() -> None:
    global _SCHEDULER_STARTED
    with _LOCK:
        _SCHEDULER_STARTED = False


__all__ = [
    "SCHEDULER_TASK",
    "archive_snapshot",
    "cleanup_once",
    "remove_expired_archives",
    "remove_native_task_logs",
    "scheduler_enabled",
    "scheduler_interval_seconds",
    "start_periodic_cleanup",
    "reset_for_tests",
]
