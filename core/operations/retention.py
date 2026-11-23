# -*- coding: utf-8 -*-
"""Daily, archive-first retention for unified task-center history."""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
import stat
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.errors import DeadlockDetected, LockNotAvailable, QueryCanceled, SerializationFailure

from core import operation_task_store
from core.runtime import scheduler_state
from core.runtime.periodic import PeriodicThread
from core.runtime.paths import task_log_root
from core.operations import run_log as task_run_log


_ARCHIVE_ROOT = task_log_root() / "task-center-archives"
_ARCHIVE_METADATA_KEYS = ("version", "created_at", "cutoff", "retention_days")
_ARCHIVE_CHUNK_SIZE = 256 * 1024
_ARCHIVE_NAME = re.compile(r"task-center-\d{8}T\d{6}Z-(?:[0-9a-f]{8}|[0-9a-f]{32})\.json\.gz")
_DELETE_BATCH_SIZE = 500
_MAX_BATCHES_PER_RUN = 20
_RETRYABLE_ROLLBACKS = (DeadlockDetected, LockNotAvailable, SerializationFailure, QueryCanceled)
SCHEDULER_TASK = "task_center_retention"
_INTERVAL_SECONDS = 24 * 60 * 60
_INITIAL_DELAY_SECONDS = 60
logger = logging.getLogger('core.task_center_retention')
_SCHEDULER = PeriodicThread("task-center-retention")
# A busy prefix can span more than one wake-up. Never reuse its cursor for another database.
_scan = threading.local()


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


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _prepare_archive_directory(root: Path) -> None:
    if not root.is_dir():
        _prepare_archive_directory(root.parent)
        root.mkdir(exist_ok=True)
        _sync_directory(root.parent)


def _new_archive_path(root: Path) -> Path:
    _prepare_archive_directory(root)
    created = datetime.now(timezone.utc)
    return root / f"task-center-{created.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex}.json.gz"


def _identity(info: os.stat_result) -> tuple[int, int, int]:
    return info.st_dev, info.st_ino, info.st_ctime_ns


def _unlink_if_unchanged(path: Path, expected: tuple[int, int, int]) -> bool:
    try:
        if _identity(path.lstat()) == expected:
            path.unlink()
            return True
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("[TaskCenterRetention] archive removal failed: %s", path, exc_info=True)
    return False


def _publish_archive(tmp: Path, path: Path, hold: Callable[[Path, int], None] | None = None) -> None:
    import fcntl

    with tmp.open("rb") as handle:
        fd = handle.fileno()
        fcntl.flock(fd, fcntl.LOCK_SH)
        os.fsync(fd)
        # Hard linking a file in the same directory publishes it without overwriting any archive.
        os.link(tmp, path)
        try:
            tmp.unlink()
            _sync_directory(path.parent)
            if hold is not None:
                hold(path, fd)
        except BaseException:
            _unlink_if_unchanged(path, _identity(os.fstat(fd)))
            raise


def archive_snapshot(snapshot: dict[str, Any], *, archive_root: Path | None = None) -> dict[str, Any]:
    """Write, reread, and verify one redacted gzip archive atomically."""
    root = Path(archive_root or _ARCHIVE_ROOT)
    final_path = _new_archive_path(root)
    safe_payload = _archive_scrub(snapshot)
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
        _publish_archive(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)
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


def _read_archive_digest(handle, check_cancel: Callable[[], None]) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while True:
        check_cancel()
        block = handle.read(_ARCHIVE_CHUNK_SIZE)
        if not block:
            return size, digest.hexdigest()
        digest.update(block)
        size += len(block)


def archive_snapshot_stream(
    metadata: Mapping[str, Any],
    sections: Mapping[str, Iterable[dict[str, Any]]],
    *,
    archive_root: Path | None = None,
    check_cancel: Callable[[], None] | None = None,
    _hold: Callable[[Path, int], None] | None = None,
) -> dict[str, Any]:
    """Write, reread, and verify the version-1 archive without collecting its rows."""
    def checkpoint() -> None:
        if check_cancel is not None:
            check_cancel()

    if set(metadata) != set(_ARCHIVE_METADATA_KEYS) or type(metadata["version"]) is not int or metadata["version"] != 1:
        raise ValueError("invalid version-1 archive metadata")
    for name in sections:
        # Match the old envelope's key handling and prevent duplicate metadata keys.
        if (not isinstance(name, str) or name in metadata
                or next(iter(_archive_scrub({name: None})), None) != name):
            raise ValueError("invalid archive section name")

    checkpoint()
    root = Path(archive_root or _ARCHIVE_ROOT)
    final_path = _new_archive_path(root)
    encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"))
    counts: dict[str, int] = {}
    content_digest = hashlib.sha256()
    content_size = 0
    buffer = bytearray()
    with tempfile.NamedTemporaryFile(
        prefix=".task-center-", suffix=".json.gz.tmp", dir=root, delete=False,
    ) as tmp_handle:
        tmp_path = Path(tmp_handle.name)
    try:
        with gzip.open(tmp_path, "wb") as handle:
            def flush() -> None:
                nonlocal content_size
                checkpoint()
                handle.write(buffer)
                content_digest.update(buffer)
                content_size += len(buffer)
                buffer.clear()

            def emit(text: str) -> None:
                buffer.extend(text.encode("utf-8"))
                if len(buffer) >= _ARCHIVE_CHUNK_SIZE:
                    flush()

            def encode_value(value: Any) -> str:
                text = encoder.encode(value)
                # v1 accepts infinities. Preserve the old readback comparison
                # for NaN, whose equality can differ after decoding.
                if "NaN" in text and json.loads(text) != value:
                    raise RuntimeError("任务中心清理归档回读校验不一致")
                return text

            emit(encode_value(_archive_scrub({key: metadata[key] for key in _ARCHIVE_METADATA_KEYS}))[:-1])
            for name, rows in sections.items():
                checkpoint()
                emit("," + encoder.encode(name) + ":[")
                count = 0
                for row in rows:
                    checkpoint()
                    if count:
                        emit(",")
                    emit(encode_value(_archive_scrub(row, depth=2)))
                    count += 1
                counts[name] = count
                emit("]")
            emit("}")
            if buffer:
                flush()
        checkpoint()
        with gzip.open(tmp_path, "rb") as handle:
            # Reading to EOF also checks the gzip footer and CRC.
            verified = _read_archive_digest(handle, checkpoint)
        if verified != (content_size, content_digest.hexdigest()):
            raise RuntimeError("任务中心清理归档回读校验不一致")
        checkpoint()
        with tmp_path.open("rb") as handle:
            size, sha256 = _read_archive_digest(handle, checkpoint)
        checkpoint()
        _publish_archive(tmp_path, final_path, _hold)
    finally:
        tmp_path.unlink(missing_ok=True)
    return {"path": str(final_path), "size": size, "sha256": sha256, "counts": counts}


def _cleanup_batch(days: int, check_cancel: Callable[[], None], after=None) -> dict[str, Any]:
    check_cancel()
    with ExitStack() as locks:
        published = []

        def hold(path: Path, fd: int) -> None:
            # Keep the publication's shared flock and inode alive until the store finishes committing.
            locks.callback(os.close, os.dup(fd))
            published.append((path, _identity(os.fstat(fd))))

        def archive_for_attempt(metadata, sections, *, check_cancel=None):
            return archive_snapshot_stream(metadata, sections, check_cancel=check_cancel, _hold=hold)

        try:
            result = operation_task_store.cleanup_terminal_history(
                retention_days=days,
                limit=_DELETE_BATCH_SIZE,
                archive_stream=archive_for_attempt,
                check_cancel=check_cancel,
                after=after,
            )
        except _RETRYABLE_ROLLBACKS as error:
            # The final database transaction rolled back. Unknown commit outcomes keep their archives.
            for path, identity in published:
                _unlink_if_unchanged(path, identity)
            check_cancel()
            raise scheduler_state.PeriodicCycleRetry() from error
        if result.get("retry") and not result.get("archive") and not any(
            result.get(key) for key in ("deleted_tasks", "deleted_batches", "deleted_events")
        ):
            # Final validation declined the snapshot and committed no deletes.
            for path, identity in published:
                _unlink_if_unchanged(path, identity)
        return result


def cleanup_once(*, stop: threading.Event | None = None) -> dict[str, Any]:
    """Drain a bounded number of archive-first retention batches."""
    from config import operations as operation_config

    days = int(getattr(operation_config, "TASK_CENTER_RETENTION_DAYS", 7) or 0)
    if days <= 0:
        return {"enabled": False, "deleted_tasks": 0, "deleted_batches": 0, "deleted_events": 0, "batches": 0}

    def check_cancel() -> None:
        if stop is None:
            return
        from core.runtime.periodic import execution_allowed

        if stop.is_set() or not execution_allowed():
            raise scheduler_state.PeriodicCycleCancelled()

    started = time.monotonic()
    totals: dict[str, Any] = {
        "enabled": True,
        "retention_days": days,
        "deleted_tasks": 0,
        "deleted_batches": 0,
        "deleted_events": 0,
        "removed_log_files": 0,
        "raw_bytes": 0,
        "busy_candidates": 0,
        "invalidated_pieces": 0,
        "inconsistent_candidates": 0,
        "batches": 0,
    }
    pg = operation_task_store.postgres_store
    domain = hash((pg.database_url(), pg.schema_name(), operation_task_store._schema_name(), days))
    same_domain = getattr(_scan, "domain", None) == domain
    after = _scan.after if same_domain else None
    revisit = getattr(_scan, "revisit", False) if same_domain else False
    deferred = False
    for _ in range(_MAX_BATCHES_PER_RUN):
        result = _cleanup_batch(days, check_cancel, after)
        totals["batches"] += 1
        totals["deleted_tasks"] += int(result.get("deleted_tasks") or 0)
        totals["deleted_batches"] += int(result.get("deleted_batches") or 0)
        totals["deleted_events"] += int(result.get("deleted_events") or 0)
        totals["raw_bytes"] += int(result.get("raw_bytes") or 0)
        totals["busy_candidates"] += int(result.get("busy_tasks") or 0)
        totals["invalidated_pieces"] += int(bool(result.get("retry")))
        totals["inconsistent_candidates"] += int(result.get("inconsistent_tasks") or 0)
        native_log_files = list(result.get("native_log_files") or [])
        if native_log_files:
            totals["removed_log_files"] += remove_native_task_logs(native_log_files)
        if result.get("archive"):
            totals["last_archive"] = result["archive"]
        busy = bool(result.get("locked") or result.get("retry") or result.get("busy_tasks"))
        if busy and "next_cursor" not in result:
            # No page was read before its deadline. Retry at the same position.
            deferred = True
            break
        revisit |= busy or (after is not None and bool(result.get("deleted_tasks")))
        if result.get("has_more") and not busy and not result.get("inconsistent_tasks"):
            continue  # Drain the current page, including the remaining events of a large task.
        after = result.get("next_cursor")
        if after is None:
            # Busy rows, or earlier parents freed by a later deletion, need another pass.
            deferred, revisit = revisit, False
            break
    else:
        deferred = True
    _scan.domain, _scan.after, _scan.revisit = domain, after, revisit
    check_cancel()
    archive_days = int(
        getattr(operation_config, "TASK_CENTER_ARCHIVE_RETENTION_DAYS", 30) or 0
    )
    totals["removed_archives"] = remove_expired_archives(retention_days=archive_days)
    totals["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    if deferred:
        logger.info(
            "[TaskCenterRetention] 本轮完成，等待续扫 tasks=%d events=%d batches=%d "
            "raw_bytes=%d busy_candidates=%d invalidated_pieces=%d inconsistent_candidates=%d elapsed_ms=%d",
            totals["deleted_tasks"], totals["deleted_events"], totals["deleted_batches"], totals["raw_bytes"],
            totals["busy_candidates"], totals["invalidated_pieces"], totals["inconsistent_candidates"], totals["elapsed_ms"],
        )
        raise scheduler_state.PeriodicCycleRetry()
    return totals


def remove_expired_archives(
    *, retention_days: int, archive_root: Path | None = None,
) -> int:
    """Remove expired managed archives one file at a time."""
    import fcntl

    days = int(retention_days or 0)
    if days <= 0:
        return 0
    root = Path(archive_root or _ARCHIVE_ROOT)
    if not root.exists():
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for path in root.glob("task-center-*.json.gz"):
        if not _ARCHIVE_NAME.fullmatch(path.name):
            continue
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_mtime >= cutoff:
                continue
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = os.fstat(fd)
                if _identity(locked) == _identity(info):
                    removed += _unlink_if_unchanged(path, _identity(locked))
            finally:
                os.close(fd)
        except (BlockingIOError, FileNotFoundError):
            continue
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
        work=lambda: cleanup_once(stop=_SCHEDULER.stop_event),
        enabled=scheduler_enabled,
        interval_seconds=scheduler_interval_seconds,
        initial_delay_seconds=_INITIAL_DELAY_SECONDS,
        stop=_SCHEDULER.stop_event,
        lifecycle=_SCHEDULER,
    )


def start_periodic_cleanup() -> bool:
    """Start one observable producer; work remains behind runtime admission."""
    try:
        started = _SCHEDULER.start(_scheduler_loop)
    except Exception:
        logger.exception("Periodic scheduler start failed; it may be retried")
        return False

    return started


def stop_periodic_cleanup(timeout: float = 2.0) -> bool:
    return _SCHEDULER.stop(timeout)


def scheduler_status() -> dict:
    return _SCHEDULER.status(enabled=scheduler_enabled())


def reset_for_tests() -> None:
    if not stop_periodic_cleanup(timeout=2.0):
        raise RuntimeError("periodic_scheduler_still_running")


__all__ = [
    "SCHEDULER_TASK",
    "archive_snapshot",
    "archive_snapshot_stream",
    "cleanup_once",
    "remove_expired_archives",
    "remove_native_task_logs",
    "scheduler_enabled",
    "scheduler_interval_seconds",
    "start_periodic_cleanup",
    "stop_periodic_cleanup",
    "scheduler_status",
    "reset_for_tests",
]
