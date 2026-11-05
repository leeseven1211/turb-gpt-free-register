"""配置维护页的 Sentinel 候选检查，持久排队并受共享维护额度控制。"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from core.auth.protocol.sentinel_assets import AssetCheck, AssetError, SentinelAssetManager
from core.operations import task_gateway


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# urllib's socket timeout does not bound DNS resolution. The default daemon
# supervises a killable CLI process: 15s cache lock + 15s download + startup.
_PROCESS_TIMEOUT_SECONDS = 35
_STATUSES = {"never", "refreshed", "failed", "cached", "stale", "missing", "corrupt"}
_ERROR_CODES = {
    "invalid_resource_url", "empty_script", "invalid_script_encoding", "invalid_script_content",
    "ambiguous_loader", "sdk_url_not_found", "sdk_marker_missing", "cache_lock_unsupported",
    "cache_lock_timeout", "corrupt_cache", "download_timeout", "unexpected_transport_redirect",
    "too_many_redirects", "invalid_redirect", "unexpected_http_status", "invalid_content_type",
    "unsupported_content_encoding", "invalid_content_length", "response_too_large",
    "content_length_mismatch", "fetch_or_cache_failed", "cache_io_failed", "check_failed",
    "worker_start_failed",
    "scheduler_store_unavailable", "maintenance_cancelled",
}
_TASK_TYPE = "sentinel_maintenance_check"
_SERVICE_INSTANCES = {}


def _cache_key(service):
    return hashlib.sha256(str(service.manager.cache_dir.resolve()).encode()).hexdigest()


def register_handler():
    """恢复维护队列的处理器；注册和状态读取都不发起下载。"""
    task_gateway.register_operation_handler(_TASK_TYPE, _handle_check, config_allowlist=(), cancel_handler=_cancel_check)


def _cancel_check(task):
    result = task_gateway.default_operation_cancel(task)
    for service in _SERVICE_INSTANCES.values():
        with service._mutex:
            if service._queued_task_id == int(task["id"]) and service._pending_lease is not None:
                service._pending_lease.close()
                service._pending_lease = None
                service._running = False
    return result


def _handle_check(context):
    key = str((context.run.get("data") or {}).get("cache_key") or "")
    service = _SERVICE_INSTANCES.get(key) or get_service()
    if _cache_key(service) != key:
        return task_gateway.OperationResult.failed("维护缓存配置已变化，请重新发起检查", {"error_code": "maintenance_cache_changed"})
    context.checkpoint()
    with service._mutex:
        lease, service._pending_lease = service._pending_lease, None
        if lease is None:
            lease = service._lease(create=True)
        if lease is None:
            return context.defer(delay_seconds=1, reason="maintenance_cache_busy")
        service._running = True
        service._queued_run_id = context.run_id
        service._queued_task_id = context.task_id
    result = service._run_check(lease)
    summary = service.status()
    if result.status == "failed":
        return task_gateway.OperationResult.failed("Sentinel 候选检查未完成", summary)
    return task_gateway.OperationResult.success(summary, message="Sentinel 候选检查完成")


def _safe_error(reason):
    return reason if isinstance(reason, str) and reason in _ERROR_CODES else "check_failed"


def _start_daemon(callback):
    threading.Thread(target=callback, name="sentinel-maintenance", daemon=True).start()


class SentinelMaintenanceService:
    """One explicit refresh per cache; status reads never wait for its flock."""

    def __init__(self, *, manager=None, builtin_path=None, builtin_version=None, clock=None, executor=None):
        self._use_subprocess = manager is None
        self.manager = manager if manager is not None else SentinelAssetManager(_PROJECT_ROOT / "run" / "sentinel-candidates")
        self.builtin_path = Path(builtin_path) if builtin_path is not None else _PROJECT_ROOT / "sentinel" / "sdk.js"
        if builtin_version is None:
            from config.openai_protocol import SENTINEL_SV
            builtin_version = SENTINEL_SV
        self.builtin_version = builtin_version
        self.clock = clock if clock is not None else time.time
        self.executor = executor if executor is not None else _start_daemon
        self._mutex = threading.RLock()
        self._running = False
        self._last_checked_at = None
        self._last_status = "never"
        self._error_code = None
        self._candidate = None
        self._pending_lease = None
        self._queued_run_id = None
        self._queued_task_id = None
        self._worker_threads: list[threading.Thread] = []

    def _lease(self, *, create):
        """Return an acquired check lease, None if busy; GET never creates it."""
        import fcntl

        if create:
            self.manager.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            handle = self.manager._path(".maintenance.lock").open("a+b" if create else "rb")
        except FileNotFoundError:
            return False
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return None
        except BaseException:
            handle.close()
            raise
        return handle

    def _external_running(self):
        try:
            lease = self._lease(create=False)
            if lease is None:
                return True
            if lease is not False:
                lease.close()
        except (ImportError, OSError, AssetError):
            pass
        return False

    @staticmethod
    def _candidate_summary(artifact):
        if artifact is None:
            return None
        return {
            "version": artifact.version, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at,
            "generic_status": artifact.compatibility.generic_status,
            "proto2_status": artifact.compatibility.proto2_status, "runtime_verified": False,
        }

    def _load_local(self):
        """Reuse the manager's full integrity check under a nonblocking lock.

        Calling check(refresh=False) here would wait up to the download timeout
        on another process. The manager's private local helpers share its exact
        validation and file limits while this adapter owns only the read lease.
        """
        import fcntl

        try:
            lock_path = self.manager._path(".lock")
            if not lock_path.exists():
                if self.manager._path("index.json").exists():
                    raise AssetError("corrupt_cache")
                return
            with lock_path.open("rb") as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return
                artifact, index = self.manager._load()
                self._candidate = self._candidate_summary(artifact)
                try:
                    record = self.manager._read_json("last_check.json", limit=4096)
                except FileNotFoundError:
                    if artifact is not None:
                        self._last_status = "stale" if self.clock() - index["checked_at"] >= self.manager.ttl_seconds else "cached"
                    return
                checked_at = record["checked_at"]
                status, reason = record["status"], record.get("reason")
                if (
                    status not in _STATUSES or isinstance(checked_at, bool)
                    or not isinstance(checked_at, (int, float)) or not math.isfinite(checked_at)
                    or not 0 <= checked_at <= self.clock() + 60
                    or (reason is not None and reason not in _ERROR_CODES)
                ):
                    raise AssetError("corrupt_cache")
                self._last_checked_at, self._last_status, self._error_code = checked_at, status, reason
        except (AssetError, KeyError, TypeError, ValueError):
            self._last_status, self._error_code = "corrupt", "corrupt_cache"
        except (ImportError, OSError):
            self._last_status, self._error_code = "failed", "cache_io_failed"

    def _summary(self, *, running):
        try:
            digest = hashlib.sha256(self.builtin_path.read_bytes()).hexdigest()
        except OSError:
            digest = ""
        builtin = {"version": self.builtin_version, "sha256": digest}
        if self._candidate is None:
            comparison = "not_checked" if self._last_status == "never" else "unknown"
        elif not digest or not self.builtin_version:
            comparison = "unknown"
        elif self._candidate["version"] != self.builtin_version:
            comparison = "version_changed"
        elif self._candidate["sha256"] != digest:
            comparison = "content_changed"
        else:
            comparison = "same"
        return {
            "ok": True, "running": running, "last_checked_at": self._last_checked_at,
            "last_status": self._last_status, "error_code": self._error_code, "builtin": builtin,
            "candidate": dict(self._candidate) if self._candidate is not None else None,
            "comparison": comparison,
        }

    def status(self):
        with self._mutex:
            task_active = False
            if self._queued_run_id is not None:
                from core.storage.operations import runtime

                run = runtime.get_run(self._queued_run_id)
                task_active = bool(run and run.get("status") in {"queued", "running", "cancelling", "settling", "waiting"})
                if run and run.get("status") in {"cancelled", "failed", "interrupted"}:
                    if self._pending_lease is not None:
                        self._pending_lease.close()
                        self._pending_lease = None
                    self._running = False
            if not self._running and not task_active:
                self._load_local()
            return self._summary(running=self._running or task_active or self._external_running())

    def _persist_check(self, result, checked_at, *, blocking=True):
        # Reuse the manager's atomic file and its lock rather than maintaining a
        # second result database. This also records worker/start failures safely.
        record = {"status": result.status, "reason": result.reason, "checked_at": checked_at}
        if blocking:
            with self.manager._lock():
                self.manager._write_json("last_check.json", record)
            return
        # A failed thread launch is still on the request thread. It must never
        # wait behind a CLI download merely to persist its diagnostic summary.
        import fcntl

        with self.manager._path(".lock").open("a+b") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            self.manager._write_json("last_check.json", record)

    def _finish(self, result, *, blocking=True):
        checked_at = self.clock()
        try:
            self._persist_check(result, checked_at, blocking=blocking)
        except (AssetError, OSError):
            result = AssetCheck("failed", "cache_io_failed", result.artifact)
        with self._mutex:
            if result.artifact is not None:
                self._candidate = self._candidate_summary(result.artifact)
            self._last_checked_at, self._last_status = checked_at, result.status
            self._error_code = result.reason
            self._running = False

    def _refresh_subprocess(self):
        command = [
            sys.executable, str(_PROJECT_ROOT / "tools" / "diagnostics" / "check_sentinel_assets.py"),
            "--cache-dir", str(self.manager.cache_dir), "--refresh", "--json",
            "--timeout", str(self.manager.timeout_seconds),
        ]
        # No shell, credentials, stdin or SDK execution. The process can only
        # invoke the existing credential-free maintenance CLI. Keeping this
        # inside the daemon also keeps process launch off the request thread.
        with subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, close_fds=True,
        ) as process:
            try:
                output, _ = process.communicate(timeout=_PROCESS_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()  # Reap it before releasing the check lease.
                return AssetCheck("failed", "download_timeout")
            finally:
                # An output-pipe error must not make Popen.__exit__ wait for a
                # still-hung resolver, or leave a child alive after lease release.
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        if process.returncode not in {0, 1} or len(output) > 65536:
            return AssetCheck("failed", "check_failed")
        try:
            payload = json.loads(output)
            if not isinstance(payload, dict):
                raise ValueError
            status, reason = payload.get("status"), payload.get("reason")
            if status == "failed":
                return AssetCheck("failed", _safe_error(reason))
            if status != "refreshed" or reason is not None or process.returncode != 0:
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            return AssetCheck("failed", "check_failed")
        # Never trust paths/artifact fields from stdout. Re-read the manager's
        # validated on-disk record and content under its bounded local lock.
        try:
            with self.manager._lock():
                artifact, _ = self.manager._load()
            if artifact is None:
                return AssetCheck("failed", "corrupt_cache")
        except AssetError as error:
            return AssetCheck("failed", _safe_error(error.reason))
        except OSError:
            return AssetCheck("failed", "cache_io_failed")
        return AssetCheck("refreshed", artifact=artifact)

    def _run_check(self, lease):
        try:
            try:
                # Injected managers retain their offline opener/executor
                # contract. The production default always gets a killable
                # process, including its DNS lookup and response reads.
                result = self._refresh_subprocess() if self._use_subprocess else self.manager.check(refresh=True)
                result = AssetCheck(
                    result.status if result.status in _STATUSES else "failed",
                    _safe_error(result.reason) if result.reason is not None else None,
                    result.artifact,
                )
            except Exception:
                result = AssetCheck("failed", "check_failed")
            self._finish(result)
            return result
        finally:
            lease.close()
            with self._mutex:
                self._running = False

    def start_check(self):
        with self._mutex:
            if self._running:
                return {**self._summary(running=True), "started": False}
            self._load_local()
            try:
                lease = self._lease(create=True)
            except (ImportError, OSError, AssetError):
                self._last_status, self._error_code = "failed", "cache_io_failed"
                return {**self._summary(running=False), "started": False}
            if lease is None:
                return {**self._summary(running=True), "started": False}
            self._running = True
            self._pending_lease = lease
        try:
            register_handler()
            key = _cache_key(self)
            _SERVICE_INSTANCES[key] = self
            queued = task_gateway.submit_durable_operation(
                task_type=_TASK_TYPE, account_id=None, email="", trigger="manual",
                resource_family="maintenance_check", source_id=f"sentinel-check:{uuid.uuid4().hex}",
                data={"cache_key": key}, dispatch=False,
            )
            if not queued.get("accepted"):
                raise RuntimeError("维护检查入队未确认")
            self._queued_run_id = queued["run_id"]
            self._queued_task_id = queued["task_id"]
        except Exception:
            try:
                self._finish(AssetCheck("failed", "scheduler_store_unavailable"), blocking=False)
            finally:
                self._pending_lease = None
                lease.close()
            return {**self.status(), "started": False}
        def dispatch():
            try:
                task_gateway._execute_operation_handler(_TASK_TYPE, queued["run_id"])
            except Exception:
                # 持久队列与缓存租约仍保留，数据库恢复后由共享扫描继续派发。
                pass

        try:
            if self.executor is _start_daemon:
                thread = threading.Thread(target=dispatch, name="sentinel-maintenance", daemon=True)
                self._worker_threads.append(thread)
                thread.start()
            else:
                self.executor(dispatch)
        except Exception:
            # 调度承载失败保留持久排队记录，下一次共享扫描可继续派发。
            with self._mutex:
                if self._pending_lease is not None:
                    self._pending_lease.close()
                    self._pending_lease = None
            queued["blocked_by"] = ["executor_submit_failed"]
        task_gateway.notify_dispatch()
        with self._mutex:
            return {**self._summary(running=self._running), "started": True, "accepted": True,
                    "task_id": queued["task_id"], "run_id": queued["run_id"], "status": "queued",
                    **({"blocked_by": queued["blocked_by"]} if queued.get("blocked_by") else {})}


_SERVICE = None
_SERVICE_LOCK = threading.Lock()


def get_service():
    """Lazily construct the process adapter; construction performs no checks."""
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = SentinelMaintenanceService()
        return _SERVICE
