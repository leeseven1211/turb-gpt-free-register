# -*- coding: utf-8 -*-
"""按注册任务隔离的网络抓包与失败现场保留。

大体积事件只写本地私有日志目录；PostgreSQL 任务行仅保存摘要和文件位置。
本地诊断是排障现场，按原始内容保存 URL、邮箱、页面文本、请求参数和响应正文；
``sanitize_*`` 仅作为旧调用方的兼容 API，不参与诊断产物写入。
"""
from __future__ import annotations

import base64
import contextvars
import gzip
import hashlib
import json
import logging
import queue
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from config import registration_debug as _cfg
from core.task_stages import EVENT_TYPES, normalize_stage, normalize_wait_reason

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ARTIFACT_ROOT = _PROJECT_ROOT / "注册日志" / "debug"
_CURRENT_SESSION: contextvars.ContextVar["RegistrationDebugSession | None"] = contextvars.ContextVar(
    "registration_debug_session",
    default=None,
)
_ACTIVE_LOCK = threading.RLock()
_ACTIVE: dict[int, "RegistrationDebugSession"] = {}
_BUDGET_LOCK = threading.Lock()
_BUDGET_CACHE_ROOT = ""
_BUDGET_CACHE_AT = 0.0
_BUDGET_CACHE_BYTES = 0
_SENTINEL = object()

_SECRET_KEYS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie", "password", "passwd",
    "pass", "otp", "totp", "mfa_code", "verification_code", "code_verifier", "client_secret",
    "secret", "access_token", "refresh_token", "id_token", "session_token", "csrf_token",
    "sentinel_token", "openai-sentinel-token", "openai-sentinel-so-token", "state",
}
_SECRET_KEY_PARTS = (
    "password", "passwd", "authorization", "cookie", "token", "secret", "verifier", "otp", "email",
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]{8,})?\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_JSON_SECRET_RE = re.compile(
    r'(?i)(["\'](?:password|passwd|otp|totp|verification_code|access_token|refresh_token|id_token|code_verifier|client_secret|secret|state)["\']\s*:\s*)'
    r'(["\'])(.*?)(\2)',
    re.DOTALL,
)
_FORM_SECRET_RE = re.compile(
    r"(?i)(password|passwd|otp|totp|verification_code|access_token|refresh_token|id_token|code_verifier|client_secret|secret|state)=([^&\s]+)"
)

_FAILURE_CATEGORY_LABELS = {
    "network_or_proxy": "网络或代理线路",
    "challenge_or_captcha": "验证挑战或验证码",
    "page_not_hydrated": "页面未完成渲染",
    "element_not_found": "页面元素缺失",
    "upstream_http_error": "上游 HTTP 错误",
    "unknown": "未分类",
}


def _raw_url(value: object) -> str:
    """Return the URL exactly as observed by the local diagnostic collector."""
    return str(value or "")


def _raw_headers(headers: object) -> dict[str, Any]:
    return dict(headers) if isinstance(headers, dict) else {}


def _raw_body(value: object, content_type: str = "") -> tuple[object | None, bool]:
    """Return the original body, applying only the size limit (never redaction)."""
    if value is None:
        return None, False
    max_bytes = max(1, int(getattr(_cfg, "REGISTRATION_DEBUG_BODY_MAX_KB", 1024) or 1024)) * 1024
    if isinstance(value, bytes):
        raw = value
        try:
            value = raw.decode("utf-8")
        except UnicodeDecodeError:
            if len(raw) > max_bytes:
                return {"truncated": True, "size_bytes": len(raw), "raw_bytes": raw[:max_bytes]}, True
            return raw, False
    if isinstance(value, (dict, list)):
        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        except Exception:
            encoded = str(value).encode("utf-8", errors="replace")
        if len(encoded) > max_bytes:
            return {"truncated": True, "size_bytes": len(encoded), "raw_text": encoded[:max_bytes].decode("utf-8", errors="replace")}, True
        return value, False
    text = str(value)
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) > max_bytes:
        return encoded[:max_bytes].decode("utf-8", errors="replace"), True
    return value, False


def _email_evidence_from_job(job: dict, context: dict) -> Any:
    supplied = job.get("email_evidence") if job.get("email_evidence") is not None else context.get("email_evidence")
    if not isinstance(supplied, dict):
        return supplied if supplied is not None else {
            "email": job.get("email"),
            "source": job.get("email_source"),
            "pool_record": job.get("email_pool_record"),
            "remote_alias_status": job.get("remote_alias_status"),
            "otp_received": job.get("otp_received"),
            "email_verified": job.get("email_verified"),
            "account_created": job.get("account_created"),
            "persisted": job.get("account_id") is not None,
            "release_result": job.get("email_release_result"),
        }
    defaults = {
        "email": job.get("email"),
        "source": job.get("email_source"),
        "pool_record": job.get("email_pool_record"),
        "remote_alias_status": job.get("remote_alias_status"),
        "otp_received": job.get("otp_received"),
        "email_verified": job.get("email_verified"),
        "account_created": job.get("account_created"),
        "persisted": job.get("account_id") is not None,
        "release_result": job.get("email_release_result"),
    }
    return {**defaults, **supplied}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _secret_key(value: object) -> bool:
    key = str(value or "").strip().lower().replace("_", "-")
    if key in _SECRET_KEYS:
        return True
    return any(part in key for part in _SECRET_KEY_PARTS)


def _marker(value: object) -> str:
    if value is None:
        return "<redacted>"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    else:
        text = str(value)
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"<redacted len={len(text)} sha256={digest}>"


def sanitize_url(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
        if not parsed.scheme or not parsed.netloc:
            return _redact_text(text)[:2000]
        # URL 中偶尔会出现 basic-auth；只保留主机和端口，不能把用户名/密码写进抓包。
        hostname = parsed.hostname or ""
        try:
            port = parsed.port
        except ValueError:
            port = None
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        safe_netloc = f"{hostname}:{port}" if port else hostname
        safe_query = []
        for key, raw in parse_qsl(parsed.query, keep_blank_values=True):
            # Query 经常携带 OAuth code/state 或邮箱；所有值都保留哈希而不保存原文。
            safe_query.append((key, _marker(raw)))
        return urlunsplit((parsed.scheme, safe_netloc, parsed.path, urlencode(safe_query), ""))
    except Exception:
        return _redact_text(text)[:2000]


def sanitize_headers(headers: object) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in headers.items():
        name = str(key or "")[:200]
        if not name:
            continue
        out[name] = _marker(value) if _secret_key(name) else _redact_text(value)[:4000]
    return out


def _redact_value(value: Any, *, key: str = "") -> Any:
    if key and _secret_key(key):
        return _marker(value)
    if isinstance(value, dict):
        return {str(k): _redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: object) -> str:
    text = str(value or "")
    text = _JWT_RE.sub(lambda m: _marker(m.group(0)), text)
    text = _BEARER_RE.sub(lambda m: f"Bearer {_marker(m.group(0)[7:])}", text)
    text = _JSON_SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_marker(m.group(3))}{m.group(4)}", text)
    text = _FORM_SECRET_RE.sub(lambda m: f"{m.group(1)}={_marker(m.group(2))}", text)
    text = _EMAIL_RE.sub(lambda m: _marker(m.group(0)), text)
    return text


def sanitize_body(value: object, content_type: str = "") -> tuple[object | None, bool]:
    """返回（脱敏正文，是否截断）。"""
    if value is None:
        return None, False
    max_bytes = max(1, int(getattr(_cfg, "REGISTRATION_DEBUG_BODY_MAX_KB", 1024) or 1024)) * 1024
    if isinstance(value, (dict, list)):
        safe_value = _redact_value(value)
        try:
            safe_raw = json.dumps(safe_value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        except Exception:
            safe_raw = str(safe_value).encode("utf-8", errors="replace")
        if len(safe_raw) > max_bytes:
            return {
                "truncated": True,
                "size_bytes": len(safe_raw),
                "sha256": hashlib.sha256(safe_raw).hexdigest(),
            }, True
        return safe_value, False
    if isinstance(value, bytes):
        raw = value
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {"binary_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}, False
    else:
        text = str(value)
    raw = text.encode("utf-8", errors="replace")
    lowered = str(content_type or "").lower()
    if "json" in lowered or text.lstrip().startswith(("{", "[")):
        try:
            safe_value = _redact_value(json.loads(text))
            safe_raw = json.dumps(safe_value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
            if len(safe_raw) > max_bytes:
                return {
                    "truncated": True,
                    "size_bytes": len(safe_raw),
                    "sha256": hashlib.sha256(safe_raw).hexdigest(),
                }, True
            return safe_value, False
        except (TypeError, ValueError):
            pass
    safe_text = _redact_text(text)
    safe_raw = safe_text.encode("utf-8", errors="replace")
    if len(safe_raw) > max_bytes:
        return safe_raw[:max_bytes].decode("utf-8", errors="replace"), True
    return safe_text, False


def _safe_artifact_dir(job: dict) -> Path:
    job_uuid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(job.get("job_uuid") or f"job-{job.get('id') or 'unknown'}"))
    return _ARTIFACT_ROOT / job_uuid


def _dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _cached_artifact_size() -> int:
    """短时缓存全局目录大小，避免多并发启动时重复遍历数 GB 的历史抓包。"""
    global _BUDGET_CACHE_ROOT, _BUDGET_CACHE_AT, _BUDGET_CACHE_BYTES
    root = str(_ARTIFACT_ROOT.resolve())
    now = time.monotonic()
    with _BUDGET_LOCK:
        if root == _BUDGET_CACHE_ROOT and now - _BUDGET_CACHE_AT < 5.0:
            return _BUDGET_CACHE_BYTES
        size = _dir_size(_ARTIFACT_ROOT)
        _BUDGET_CACHE_ROOT = root
        _BUDGET_CACHE_AT = now
        _BUDGET_CACHE_BYTES = size
        return size


class RegistrationDebugSession:
    """按任务隔离的采集会话。

    ``full`` 用于显式调试：从任务启动就旁路采集网络并支持失败暂停。
    ``failure_only`` 用于普通模式：只在最终失败时创建文件并保存现场，成功任务
    不启动写入线程，也不连接 Roxy CDP，避免改变正常注册路径的时序。
    """

    def __init__(self, job: dict, *, capture_mode: str = "full"):
        self.job = dict(job or {})
        self.job_id = int(job["id"])
        self.job_uuid = str(job.get("job_uuid") or f"job-{self.job_id}")
        self.batch_id = str(job.get("batch_id") or "")
        context = job.get("diagnostic_context") if isinstance(job.get("diagnostic_context"), dict) else {}
        self.attempt_id = job.get("attempt_id") or job.get("registration_attempt_id") or context.get("attempt_id")
        self.run_id = job.get("run_id") or job.get("registration_run_id") or job.get("active_run_id") or job.get("last_run_id") or context.get("run_id")
        self.execution_id = job.get("execution_id") or context.get("execution_id")
        self.trigger_stage = normalize_stage(job.get("trigger_stage") or context.get("trigger_stage") or job.get("progress_stage") or "browser")
        self.last_confirmed_state = str(job.get("last_confirmed_state") or context.get("last_confirmed_state") or job.get("remote_state") or "")
        self.failure_stage = normalize_stage(job.get("failure_stage") or context.get("failure_stage") or self.trigger_stage)
        self.email_evidence: Any = _email_evidence_from_job(job, context)
        self.error_info: dict[str, Any] | None = None
        self.artifact_dir = _safe_artifact_dir(job)
        self.events_path = self.artifact_dir / "network.jsonl.gz"
        self.manifest_path = self.artifact_dir / "manifest.json"
        self.snapshot_path = self.artifact_dir / "last-page.png"
        self.page_state_path = self.artifact_dir / "last-page.json"
        self.capture_mode = "failure_only" if capture_mode == "failure_only" else "full"
        self.capture_started = False
        self.failure_captured = False
        self.failure_category = ""
        self.current_stage = normalize_stage(job.get("progress_stage") or "browser")
        self.started_at = _now_iso()
        self.debug_state = "recording"
        self.hold_until = ""
        self.pause_reason = ""
        self.release_action = ""
        self._release_event = threading.Event()
        self._closed = threading.Event()
        self._queue: queue.Queue = queue.Queue(maxsize=max(1000, int(getattr(_cfg, "REGISTRATION_DEBUG_QUEUE_SIZE", 20000) or 20000)))
        self._writer: threading.Thread | None = None
        self._collectors: list[Any] = []
        self._pending_network: deque[dict] = deque(maxlen=100)
        self._pending_events: deque[dict] = deque(maxlen=200)
        self._failure_network_seen: deque[dict] = deque(maxlen=100)
        self._stage_started_at: dict[str, float] = {}
        self._stage_timings: list[dict[str, Any]] = []
        self._stage_state: dict[str, str] = {}
        self._stage_initial_state: dict[str, str] = {}
        self._stage_wait_reason: dict[str, str] = {}
        self._lock = threading.RLock()
        self.request_count = 0
        self.failed_count = 0
        self.http_error_count = 0
        self.websocket_frame_count = 0
        self.dropped_event_count = 0
        self.body_bytes_saved = 0
        self.network_error_observed = False
        if self.capture_mode == "failure_only":
            # Failure-only capture is lazy, but failed request bodies remain
            # raw and are still bounded by the per-body limit.
            self.body_budget_bytes = 0
            self.body_capture_enabled = True
        else:
            self.body_budget_bytes = max(0, int(getattr(_cfg, "REGISTRATION_DEBUG_BODY_BUDGET_MB", 128) or 128)) * 1024 * 1024
            global_budget = max(0, int(getattr(_cfg, "REGISTRATION_DEBUG_GLOBAL_BUDGET_MB", 5120) or 5120)) * 1024 * 1024
            self.body_capture_enabled = not global_budget or _cached_artifact_size() < global_budget
        if self.capture_mode == "full":
            self._start_capture()

    def _start_capture(self) -> None:
        """初始化产物目录和异步写入器；普通模式只在失败路径调用。"""
        if self.capture_started:
            return
        self.capture_started = True
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._writer = threading.Thread(target=self._writer_loop, name=f"debug-writer-{self.job_id}", daemon=True)
        self._writer.start()
        self.record({
            "kind": "capture_started",
            "job_id": self.job_id,
            "batch_id": self.batch_id,
            "capture_mode": self.capture_mode,
            "body_capture_enabled": self.body_capture_enabled,
        })
        if self.capture_mode == "full":
            self._patch_job(
                debug_state="recording",
                debug_artifact_dir=str(self.artifact_dir),
                debug_capture_started_at=self.started_at,
                debug_capture_summary=self.summary(),
            )
        else:
            self._patch_job(
                failure_diagnostics_state="recording",
                failure_diagnostics_artifact_dir=str(self.artifact_dir),
                failure_diagnostics_capture_started_at=self.started_at,
                failure_diagnostics_summary=self.summary(),
            )
        for item in list(self._pending_network):
            self.record(item)
        self._pending_network.clear()
        for item in list(self._pending_events):
            self.record(item)
        self._pending_events.clear()

    def _context_fields(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "attempt_id": self.attempt_id,
            "run_id": self.run_id,
            "execution_id": self.execution_id,
            "trigger_stage": self.trigger_stage,
            "last_confirmed_state": self.last_confirmed_state,
            "failure_stage": self.failure_stage,
            "email_evidence": self.email_evidence,
        }

    @staticmethod
    def _event_type(kind: Any) -> str:
        value = str(kind or "diagnostic")
        return value if value in EVENT_TYPES else "diagnostic"

    def update_context(
        self,
        *,
        attempt_id: Any = None,
        run_id: Any = None,
        execution_id: Any = None,
        trigger_stage: Any = None,
        last_confirmed_state: Any = None,
        failure_stage: Any = None,
        email_evidence: Any = None,
    ) -> None:
        """Update correlation fields without changing registration behavior."""
        if attempt_id is not None:
            self.attempt_id = attempt_id
        if run_id is not None:
            self.run_id = run_id
        if execution_id is not None:
            self.execution_id = execution_id
        if trigger_stage is not None:
            self.trigger_stage = normalize_stage(trigger_stage)
        if last_confirmed_state is not None:
            self.last_confirmed_state = str(last_confirmed_state)
        if failure_stage is not None:
            self.failure_stage = normalize_stage(failure_stage)
        if email_evidence is not None:
            self.email_evidence = email_evidence

    def _classify_failure(self, reason: Any) -> dict[str, Any] | None:
        try:
            from core.task_errors import classify_task_error

            self.error_info = classify_task_error(
                reason,
                stage=self.failure_stage or self.current_stage,
                task_type=str(self.job.get("job_type") or "registration"),
                error_code=str(self.job.get("error_code") or ""),
            )
        except Exception:
            self.error_info = None
        return self.error_info

    def _error_payload(self, message: Any, *, stage: str | None = None, status: int = 0) -> dict[str, Any]:
        info = self._classify_failure(message) if message else None
        payload = dict(info or {})
        payload["message"] = str(message or "")[:1000]
        if stage:
            payload["stage"] = normalize_stage(stage)
        if status:
            payload["http_status"] = int(status)
        return payload

    def _refresh_terminal_context(self) -> None:
        """Pick up attempt/run/evidence fields written while the run was active."""
        try:
            from core import db

            latest = db.get_job(self.job_id) or {}
        except Exception:
            return
        if not isinstance(latest, dict):
            return
        self.job.update(latest)
        context = latest.get("diagnostic_context") if isinstance(latest.get("diagnostic_context"), dict) else {}
        attempt_id = latest.get("attempt_id") or latest.get("registration_attempt_id") or context.get("attempt_id") or self.attempt_id
        run_id = latest.get("run_id") or latest.get("registration_run_id") or latest.get("active_run_id") or latest.get("last_run_id") or context.get("run_id") or self.run_id
        execution_id = latest.get("execution_id") or context.get("execution_id") or self.execution_id
        # B creates the Run after the legacy job row and intentionally keeps
        # ``registration_jobs`` as a compatibility table.  Resolve the Run by
        # its durable Attempt/job link only when IDs are absent; failures are
        # ignored so diagnostics remain independent of database availability.
        if attempt_id and not run_id:
            try:
                from core.storage import registration

                runs = registration.list_runs(int(attempt_id), limit=100)
                matching = [
                    row for row in runs
                    if int(row.get("job_id") or 0) == self.job_id
                    or (execution_id and str(row.get("execution_id") or "") == str(execution_id))
                ]
                candidate = (matching or runs or [None])[0]
                if candidate:
                    run_id = candidate.get("id") or candidate.get("run_id")
            except Exception:
                logger.debug("[Job %s][Debug] 解析 RegistrationRun 失败，继续使用已有诊断上下文", self.job_id, exc_info=True)
        self.update_context(
            attempt_id=attempt_id,
            run_id=run_id,
            execution_id=execution_id,
            last_confirmed_state=latest.get("last_confirmed_state") or context.get("last_confirmed_state") or self.last_confirmed_state,
            email_evidence=_email_evidence_from_job(latest, context),
        )

    def record_email_evidence(self, evidence: Any) -> None:
        self.email_evidence = evidence if evidence is not None else {}
        event = {"kind": "email_evidence", **self._context_fields()}
        if self.capture_started:
            self.record(event)
        else:
            self._pending_events.append(event)

    def _patch_job(self, **changes: Any) -> None:
        try:
            patch_job(self.job_id, **changes)
        except Exception:
            logger.exception("[Job %s][Debug] 更新任务调试状态失败", self.job_id)

    def _writer_loop(self) -> None:
        try:
            with gzip.open(self.events_path, "at", encoding="utf-8", compresslevel=5) as stream:
                pending_flush = 0
                last_flush = time.monotonic()
                while True:
                    item = self._queue.get()
                    if item is _SENTINEL:
                        self._queue.task_done()
                        break
                    try:
                        stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":"), default=str))
                        stream.write("\n")
                        pending_flush += 1
                        if pending_flush >= 10 or time.monotonic() - last_flush >= 0.5:
                            stream.flush()
                            pending_flush = 0
                            last_flush = time.monotonic()
                    finally:
                        self._queue.task_done()
                stream.flush()
        except Exception:
            logger.exception("[Job %s][Debug] 写入抓包文件失败", self.job_id)

    def record(self, event: dict) -> None:
        if self._closed.is_set() or not self.capture_started:
            return
        item = dict(event or {})
        item.setdefault("captured_at", _now_iso())
        item.setdefault("event_type", self._event_type(item.get("event_type") or item.get("kind")))
        # ``kind`` remains for compatibility with existing readers; E should
        # use event_type as the frozen contract field.
        for key, value in self._context_fields().items():
            item.setdefault(key, value)
        item.setdefault("stage", self.current_stage)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            # 先丢正文再尝试一次非阻塞元数据写入；诊断绝不能把注册线程
            # 卡在有界队列上。
            for body_key in ("request_body", "response_body"):
                if body_key in item:
                    item[body_key], truncated = _raw_body(item.get(body_key))
                    if truncated:
                        item[f"{body_key}_truncated"] = True
            item["capture_degraded"] = "queue_full"
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                self.dropped_event_count += 1

    def _finish_stage(self, stage: str, *, state: str = "running", ended: float | None = None) -> None:
        started = self._stage_started_at.pop(stage, None)
        if started is None:
            return
        ended = time.monotonic() if ended is None else ended
        timing = {
            "stage": stage,
            "state": str(state or "running"),
            "state_before": self._stage_initial_state.get(stage, "pending"),
            "state_after": str(state or "running"),
            "started_monotonic": started,
            "ended_monotonic": ended,
            "duration_ms": round(max(0.0, ended - started) * 1000, 2),
            "wait_reason": self._stage_wait_reason.get(stage, "unknown"),
        }
        self._stage_timings.append(timing)
        event = {"kind": "stage_timing", **timing}
        if self.capture_started:
            self.record(event)
        else:
            self._pending_events.append(event)

    def update_stage(
        self,
        stage: str,
        state: str = "running",
        detail: str | None = None,
        wait_reason: str | None = None,
    ) -> None:
        next_stage = normalize_stage(stage) if stage else self.current_stage
        now = time.monotonic()
        if next_stage != self.current_stage:
            self._finish_stage(self.current_stage, state=self._stage_state.get(self.current_stage, "success"), ended=now)
            self.current_stage = next_stage
            self.trigger_stage = self.trigger_stage or next_stage
        self.failure_stage = next_stage
        if str(state or "").lower() == "failed":
            self.trigger_stage = next_stage
        state_after = str(state or "running")
        state_before = self._stage_state.get(next_stage, "pending")
        self._stage_initial_state.setdefault(next_stage, state_before)
        self._stage_wait_reason[next_stage] = normalize_wait_reason(wait_reason)
        self._stage_state[next_stage] = state_after
        self._stage_started_at.setdefault(next_stage, now)
        event = {
            "kind": "stage",
            "stage": self.current_stage,
            "state": state_after,
            "state_before": state_before,
            "state_after": state_after,
            "detail": str(detail or "")[:1000],
            "started_monotonic": self._stage_started_at[next_stage],
            "duration_ms": round(max(0.0, now - self._stage_started_at[next_stage]) * 1000, 2),
            "wait_reason": self._stage_wait_reason[next_stage],
        }
        if self.capture_started:
            self.record(event)
        else:
            self._pending_events.append(event)

    def reserve_body(self, body: object) -> bool:
        if not self.body_capture_enabled or body is None:
            return False
        try:
            size = len(json.dumps(body, ensure_ascii=False, default=str).encode("utf-8"))
        except Exception:
            size = len(str(body).encode("utf-8", errors="replace"))
        with self._lock:
            if self.body_budget_bytes and self.body_bytes_saved + size > self.body_budget_bytes:
                self.body_capture_enabled = False
                self.record({"kind": "capture_degraded", "reason": "body_budget_exhausted"})
                return False
            self.body_bytes_saved += size
            return True

    def record_network(self, record: dict) -> None:
        item = dict(record or {})
        item["kind"] = "network_request"
        status = int(item.get("status") or 0)
        if item.get("failure") or status >= 400:
            item.setdefault(
                "error",
                self._error_payload(
                    item.get("failure") or f"HTTP {status}",
                    stage=str(item.get("stage") or self.current_stage),
                    status=status,
                ),
            )
        if self.capture_mode == "failure_only":
            # 普通模式只在失败现场落盘失败请求元数据；成功请求不进入队列，
            # 避免把正常流程变成隐式抓包。失败请求正文按原始内容保存，
            # 仅受单条正文大小限制。
            if not item.get("failure") and status < 400:
                return
            item.pop("request_body", None)
            item.pop("response_body", None)
            item["capture_mode"] = self.capture_mode
            with self._lock:
                self.request_count += 1
                self.failed_count += 1 if item.get("failure") else 0
                self.http_error_count += 1 if status >= 400 else 0
                self.network_error_observed = self.network_error_observed or bool(item.get("failure"))
                for body_key in ("request_body", "response_body"):
                    if item.get(body_key) is not None:
                        try:
                            self.body_bytes_saved += len(json.dumps(item[body_key], ensure_ascii=False, default=str).encode("utf-8"))
                        except Exception:
                            self.body_bytes_saved += len(str(item[body_key]).encode("utf-8", errors="replace"))
                self._failure_network_seen.append(dict(item))
                if not self.capture_started:
                    self._pending_network.append(item)
                    return
            self.record(item)
            return
        request_body = item.get("request_body")
        response_body = item.get("response_body")
        if request_body is not None and not self.reserve_body(request_body):
            item.pop("request_body", None)
            item["request_body_omitted"] = "body_budget"
        if response_body is not None and not self.reserve_body(response_body):
            item.pop("response_body", None)
            item["response_body_omitted"] = "body_budget"
        with self._lock:
            self.request_count += 1
            if item.get("failure"):
                self.failed_count += 1
                self.network_error_observed = True
            if status >= 400:
                self.http_error_count += 1
        self.record(item)

    def attach_roxy(self, debugger_address: str | None) -> None:
        if self.capture_mode == "failure_only":
            return
        if not debugger_address:
            self.record({"kind": "capture_warning", "reason": "roxy_debugger_address_missing"})
            return
        collector = RoxyCDPCollector(self, debugger_address)
        self._collectors.append(collector)
        collector.start()

    @staticmethod
    def _failure_category(reason: str, state: dict, network: list[dict] | None = None) -> str:
        """把失败现场归到稳定的排查分类，原始异常仍保留在任务日志中。"""
        text = str(reason or "").lower()
        url = str(state.get("url") or "").lower()
        dom = state.get("dom") if isinstance(state.get("dom"), dict) else {}
        if any(item.get("failure") for item in (network or [])) or any(
            marker in text for marker in ("proxy", "tunnel", "connection", "timed out", "timeout", "chrome-error")
        ):
            return "network_or_proxy"
        if "cloudflare" in text or "challenge" in text or "captcha" in text:
            return "challenge_or_captcha"
        if "chatgpt.com/auth" in url and not int(dom.get("input_count") or 0) and not int(dom.get("action_count") or 0):
            return "page_not_hydrated"
        if "找不到" in str(reason or "") or "not found" in text or "missing" in text:
            return "element_not_found"
        if any(int(item.get("status") or 0) >= 400 for item in (network or [])):
            return "upstream_http_error"
        return "unknown"

    @staticmethod
    def _failure_category_label(category: str) -> str:
        return _FAILURE_CATEGORY_LABELS.get(str(category or ""), _FAILURE_CATEGORY_LABELS["unknown"])

    @staticmethod
    def _browser_logs(driver: Any) -> list[dict]:
        if driver is None or not hasattr(driver, "get_log"):
            return []
        try:
            rows = driver.get_log("browser") or []
        except Exception:
            return []
        out = []
        for row in rows[:100]:
            if isinstance(row, dict):
                out.append({
                    "level": str(row.get("level") or "")[:40],
                    "message": str(row.get("message") or "")[:2000],
                    "timestamp": row.get("timestamp"),
                })
            else:
                out.append({"message": str(row)[:2000]})
        return out

    def capture_page_snapshot(self, driver: Any, reason: str) -> None:
        if driver is None:
            return
        self._start_capture()
        try:
            driver.save_screenshot(str(self.snapshot_path))
        except Exception as exc:
            self.record({"kind": "snapshot_error", "operation": "screenshot", "error": f"{type(exc).__name__}: {exc}"})
        try:
            raw = driver.execute_script(
                """return (function() {
                  const visible = el => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                      rect.width > 0 && rect.height > 0;
                  };
                  const text = el => String(el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 240);
                  const describe = el => {
                    const type = el.getAttribute('type') || '';
                    const autocomplete = String(el.getAttribute('autocomplete') || '').toLowerCase();
                    const secretInput = type.toLowerCase() === 'password' || autocomplete.includes('password');
                    return ({
                    tag: el.tagName || '',
                    type,
                    name: el.getAttribute('name') || '',
                    id: el.id || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    aria: el.getAttribute('aria-label') || '',
                    text: secretInput ? '<redacted:password>' : text(el),
                    disabled: !!el.disabled,
                  });};
                  const inputs = Array.from(document.querySelectorAll('input,textarea,select')).filter(visible);
                  const actions = Array.from(document.querySelectorAll('button,a,[role="button"],input[type="submit"]')).filter(visible);
                  const resources = (performance.getEntriesByType('resource') || []).map(entry => ({
                    name: entry.name || '',
                    initiatorType: entry.initiatorType || '',
                    duration: entry.duration || 0,
                    transferSize: entry.transferSize || 0,
                    encodedBodySize: entry.encodedBodySize || 0,
                    decodedBodySize: entry.decodedBodySize || 0,
                    responseStatus: entry.responseStatus || 0,
                  }));
                  const navigation = performance.getEntriesByType('navigation')[0] || {};
                  return {
                    url: location.href,
                    title: document.title || '',
                    readyState: document.readyState || '',
                    bodyText: (document.body && document.body.innerText || '').slice(0, 50000),
                    htmlLength: (document.documentElement && document.documentElement.outerHTML || '').length,
                    dom: {
                      input_count: inputs.length,
                      inputs: inputs.slice(0, 50).map(describe),
                      action_count: actions.length,
                      actions: actions.slice(0, 80).map(describe),
                    },
                    resources: resources,
                    navigation: {
                      domContentLoaded: navigation.domContentLoadedEventEnd || 0,
                      loadEventEnd: navigation.loadEventEnd || 0,
                      responseEnd: navigation.responseEnd || 0,
                      transferSize: navigation.transferSize || 0,
                    },
                  };
                })();"""
            ) or {}
            raw_dom = raw.get("dom") if isinstance(raw.get("dom"), dict) else {}
            inputs = []
            for item in (raw_dom.get("inputs") or [])[:50]:
                if not isinstance(item, dict):
                    continue
                sanitized = dict(item)
                input_type = str(sanitized.get("type") or "").lower()
                autocomplete = str(sanitized.get("autocomplete") or "").lower()
                if input_type == "password" or "password" in autocomplete:
                    sanitized["text"] = "<redacted:password>"
                    sanitized.pop("value", None)
                inputs.append(sanitized)
            dom = {
                "input_count": int(raw_dom.get("input_count") or 0),
                "inputs": inputs,
                "action_count": int(raw_dom.get("action_count") or 0),
                "actions": list((raw_dom.get("actions") or [])[:80]),
            }
            resource_limit = max(1, int(getattr(_cfg, "REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT", 80) or 80))
            resources = []
            for item in (raw.get("resources") or [])[-resource_limit:]:
                if not isinstance(item, dict):
                    continue
                resources.append({
                    "url": _raw_url(item.get("name")),
                    "initiator_type": str(item.get("initiatorType") or "")[:60],
                    "duration_ms": round(float(item.get("duration") or 0), 2),
                    "transfer_size": int(item.get("transferSize") or 0),
                    "encoded_body_size": int(item.get("encodedBodySize") or 0),
                    "decoded_body_size": int(item.get("decodedBodySize") or 0),
                    "response_status": int(item.get("responseStatus") or 0),
                })
            text_limit = max(1, int(getattr(_cfg, "REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB", 32) or 32)) * 1024
            error_info = self._classify_failure(reason)
            state = {
                "captured_at": _now_iso(),
                "reason": str(reason or "")[:1000],
                "url": _raw_url(raw.get("url")),
                "title": str(raw.get("title") or "")[:500],
                "ready_state": raw.get("readyState"),
                "body_text": str(raw.get("bodyText") or "")[:text_limit],
                "html_length": raw.get("htmlLength"),
                "dom": dom,
                "resources": resources,
                "navigation": dict(raw.get("navigation") or {}) if isinstance(raw.get("navigation"), dict) else {},
                "browser_logs": self._browser_logs(driver),
                **self._context_fields(),
                "stage_timings": list(self._stage_timings),
                "network_error_observed": bool(self.network_error_observed),
                "error_info": error_info or {},
                "error": error_info or {"message": str(reason or "")[:1000]},
            }
            self.failure_category = self._failure_category(reason, state, list(self._failure_network_seen))
            state["failure_category"] = self.failure_category
            state["failure_category_label"] = self._failure_category_label(self.failure_category)
            self.page_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            self.record({"kind": "page_snapshot", **state})
        except Exception as exc:
            self.record({"kind": "snapshot_error", "operation": "page_state", "error": f"{type(exc).__name__}: {exc}"})

    def pause_failure(self, driver: Any, reason: str) -> str:
        """在 Roxy 最终失败、进入 finally 清理之前保留现场。"""
        self.trigger_stage = normalize_stage(self.current_stage)
        self.failure_stage = normalize_stage(self.current_stage)
        self._refresh_terminal_context()
        if self.capture_mode == "failure_only":
            self.failure_captured = True
            error_info = self._classify_failure(reason)
            if driver is not None:
                self.capture_page_snapshot(driver, reason)
            else:
                # 协议驱动或浏览器尚未启动时仍落盘失败请求元数据和错误原因。
                self._start_capture()
                category = self._failure_category(reason, {}, list(self._failure_network_seen))
                self.failure_category = category
                self.record({
                    "kind": "failure_diagnostics",
                    "reason": str(reason or "")[:1000],
                    "failure_category": category,
                    "failure_category_label": self._failure_category_label(category),
                    "page_snapshot": False,
                    "network_error_observed": bool(self.network_error_observed),
                    "error_info": error_info or {},
                    "error": error_info or {"message": str(reason or "")[:1000]},
                    **self._context_fields(),
                })
            self.debug_state = "captured"
            self._patch_job(
                failure_diagnostics_state="captured",
                failure_diagnostics_failure_reason=str(reason or "")[:1000],
                failure_diagnostics_category=self.failure_category or "unknown",
                failure_diagnostics_category_label=self._failure_category_label(self.failure_category),
                failure_diagnostics_summary=self.summary(),
            )
            logger.info(
                "[Job %s][FailureDiagnostics] 已保存失败现场：category=%s artifact=%s",
                self.job_id,
                self.failure_category or "unknown",
                self.artifact_dir,
            )
            return self.debug_state
        self.capture_page_snapshot(driver, reason)
        if driver is None and not self._collectors:
            self.debug_state = "hold_skipped"
            self.record({"kind": "debug_hold_skipped", "reason": "no_browser_or_cdp_target"})
            self._patch_job(debug_state=self.debug_state, debug_pause_reason="失败时没有可保留的浏览器现场")
            return self.debug_state
        max_held = max(0, int(getattr(_cfg, "REGISTRATION_DEBUG_MAX_HELD_SESSIONS", 16) or 16))
        timeout = max(1, int(getattr(_cfg, "REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS", 1800) or 1800))
        deadline = datetime.now().astimezone() + timedelta(seconds=timeout)
        with _ACTIVE_LOCK:
            held = sum(1 for session in _ACTIVE.values() if session.debug_state == "paused")
            if max_held and held >= max_held:
                self.debug_state = "hold_skipped"
            else:
                # 在同一把锁内完成计数和占位，避免多并发任务同时越过现场上限。
                self.debug_state = "paused"
        if self.debug_state == "hold_skipped":
            self.record({"kind": "debug_hold_skipped", "reason": "held_session_limit", "limit": max_held})
            self._patch_job(debug_state=self.debug_state, debug_pause_reason="保留现场数量已达上限")
            return self.debug_state
        self.pause_reason = str(reason or "")[:1000]
        self.hold_until = deadline.isoformat(timespec="seconds")
        self.record({"kind": "debug_paused", "reason": self.pause_reason, "hold_until": self.hold_until})
        self._patch_job(
            debug_state="paused",
            debug_pause_reason=self.pause_reason,
            debug_hold_until=self.hold_until,
            debug_capture_summary=self.summary(),
        )
        logger.warning(
            "[Job %s][Debug] 注册失败现场已暂停保留，最晚到 %s；可在 WebUI 结束调试或停止任务",
            self.job_id,
            self.hold_until,
        )

        while datetime.now().astimezone() < deadline:
            if self._release_event.wait(timeout=1.0):
                break
            try:
                from core.registration_service import is_stop_requested
                if is_stop_requested(self.job_id):
                    self.release_action = "stop"
                    break
            except Exception:
                pass

        if self.release_action == "stop":
            state = "stopped"
        elif self._release_event.is_set():
            state = "released"
        else:
            state = "expired"
        self.debug_state = state
        self.record({"kind": "debug_released", "action": self.release_action or state})
        self._patch_job(debug_state=state, debug_released_at=_now_iso(), debug_capture_summary=self.summary())
        return state

    def release(self, action: str = "finish") -> dict:
        if self.debug_state != "paused":
            return {"ok": False, "error": "任务当前没有暂停中的调试现场", "state": self.debug_state}
        self.release_action = str(action or "finish")[:40]
        self._release_event.set()
        return {"ok": True, "job_id": self.job_id, "state": "releasing", "action": self.release_action}

    def summary(self) -> dict:
        return {
            "state": self.debug_state,
            "capture_mode": self.capture_mode,
            "captured": bool(self.capture_started),
            "request_count": int(self.request_count),
            "failed_count": int(self.failed_count),
            "http_error_count": int(self.http_error_count),
            "websocket_frame_count": int(self.websocket_frame_count),
            "dropped_event_count": int(self.dropped_event_count),
            "body_bytes_saved": int(self.body_bytes_saved),
            "body_capture_enabled": bool(self.body_capture_enabled),
            "hold_until": self.hold_until,
            "artifact_dir": str(self.artifact_dir),
            "job_id": self.job_id,
            "attempt_id": self.attempt_id,
            "run_id": self.run_id,
            "trigger_stage": self.trigger_stage,
            "last_confirmed_state": self.last_confirmed_state,
            "failure_stage": self.failure_stage,
            "network_error_observed": bool(self.network_error_observed),
            "email_evidence": self.email_evidence,
            "stage_timings": list(self._stage_timings),
            "error_info": self.error_info or {},
        }

    def finalize(self, status: str = "") -> None:
        if self._closed.is_set():
            return
        terminal_status = str(status or "").strip().lower()
        unknown_state = str(self.last_confirmed_state or self.job.get("last_confirmed_state") or "").upper() == "UNKNOWN"
        should_capture = terminal_status in {"failed", "partial_success", "unknown"} or unknown_state
        if should_capture:
            self._refresh_terminal_context()
        if self.capture_mode == "failure_only" and should_capture and not self.capture_started:
            # Core failure normally calls capture_current_failure first.  This
            # fallback covers partial_success, post-processing failure and an
            # UNKNOWN remote state that exits without an exception callback.
            self.failure_captured = True
            self.trigger_stage = normalize_stage(self.current_stage)
            self.failure_stage = normalize_stage(self.current_stage or self.job.get("progress_stage"))
            reason = self.job.get("error") or self.job.get("error_message") or terminal_status or "unknown"
            error_info = self._classify_failure(reason)
            self.failure_category = self._failure_category(str(reason), {}, list(self._failure_network_seen))
            self._start_capture()
            self.record({
                "kind": "failure_diagnostics",
                "reason": str(reason)[:1000],
                "failure_category": self.failure_category,
                "failure_category_label": self._failure_category_label(self.failure_category),
                "trigger": "terminal_status",
                "status": terminal_status,
                "network_error_observed": bool(self.network_error_observed),
                "error_info": error_info or {},
                "error": error_info or {"message": str(reason)[:1000]},
                **self._context_fields(),
            })
        if not self.capture_started:
            self._closed.set()
            with _ACTIVE_LOCK:
                _ACTIVE.pop(self.job_id, None)
            return
        for collector in self._collectors:
            try:
                collector.stop()
            except Exception:
                logger.exception("[Job %s][Debug] 停止抓包采集器失败", self.job_id)
        self._finish_stage(self.current_stage, state=getattr(self, "_stage_state", {}).get(self.current_stage, terminal_status or "success"))
        self.debug_state = "completed" if self.debug_state not in {"expired", "stopped"} else self.debug_state
        self.record({"kind": "capture_finished", "status": status, "summary": self.summary()})
        try:
            if self._writer is not None:
                self._queue.put(_SENTINEL, timeout=2)
                self._writer.join(timeout=10)
        except Exception:
            logger.exception("[Job %s][Debug] 等待抓包写入完成失败", self.job_id)
        self._closed.set()
        summary = self.summary()
        manifest = {
            "job_id": self.job_id,
            "job_uuid": self.job_uuid,
            "batch_id": self.batch_id,
            "capture_mode": self.capture_mode,
            "started_at": self.started_at,
            "finished_at": _now_iso(),
            "status": status,
            "failure_category": self.failure_category,
            **self._context_fields(),
            "summary": summary,
            "files": {
                "network": self.events_path.name if self.events_path.exists() else "",
                "screenshot": self.snapshot_path.name if self.snapshot_path.exists() else "",
                "page_state": self.page_state_path.name if self.page_state_path.exists() else "",
            },
        }
        try:
            self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("[Job %s][Debug] 写入 manifest 失败", self.job_id)
        self._patch_job(
            **(
                {
                    "debug_state": self.debug_state,
                    "debug_capture_completed_at": _now_iso(),
                    "debug_capture_summary": summary,
                }
                if self.capture_mode == "full"
                else {
                    "failure_diagnostics_state": self.debug_state,
                    "failure_diagnostics_capture_completed_at": _now_iso(),
                    "failure_diagnostics_summary": summary,
                }
            ),
        )
        with _ACTIVE_LOCK:
            _ACTIVE.pop(self.job_id, None)


class _RoxyTargetCollector:
    def __init__(self, owner: "RoxyCDPCollector", target_id: str, ws_url: str, target_type: str):
        self.owner = owner
        self.session = owner.session
        self.target_id = target_id
        self.ws_url = ws_url
        self.target_type = target_type
        self._thread = threading.Thread(target=self._run, name=f"debug-cdp-{self.session.job_id}-{target_id[:6]}", daemon=True)
        self._stop = threading.Event()
        self._ws = None
        self._send_lock = threading.Lock()
        self._command_id = 0
        self._pending: dict[int, dict] = {}
        self._requests: dict[str, dict] = {}
        self._redirect_seq: defaultdict[str, int] = defaultdict(int)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        self._thread.join(timeout=3)

    def _send(self, method: str, params: dict | None = None, pending: dict | None = None) -> None:
        if self._ws is None:
            return
        with self._send_lock:
            self._command_id += 1
            command_id = self._command_id
            if pending:
                self._pending[command_id] = pending
            self._ws.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))

    def _run(self) -> None:
        try:
            import websocket
            self._ws = websocket.create_connection(self.ws_url, timeout=2, suppress_origin=True)
            self._ws.settimeout(1)
            self._send("Network.enable", {
                "maxTotalBufferSize": 100 * 1024 * 1024,
                "maxResourceBufferSize": 4 * 1024 * 1024,
                "maxPostDataSize": 1024 * 1024,
            })
            self._send("Runtime.enable")
            self._send("Log.enable")
            while not self._stop.is_set():
                try:
                    raw = self._ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not raw:
                    break
                try:
                    self._handle(json.loads(raw))
                except Exception as exc:
                    self.session.record({"kind": "capture_warning", "target_id": self.target_id, "error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:
            if not self._stop.is_set():
                self.session.record({
                    "kind": "capture_warning",
                    "reason": "roxy_cdp_target_failed",
                    "target_id": self.target_id,
                    "target_type": self.target_type,
                    "error": f"{type(exc).__name__}: {exc}",
                })
        finally:
            for request_id in list(self._requests):
                self._finish_request(request_id, failure="target_closed", body_unavailable="target_closed")

    def _request_key(self, request_id: str) -> str:
        return f"{self.target_id}:{request_id}:{self._redirect_seq[request_id]}"

    def _handle(self, message: dict) -> None:
        if "id" in message:
            pending = self._pending.pop(int(message.get("id") or 0), None)
            if not pending:
                return
            request_id = str(pending.get("request_id") or "")
            result = message.get("result") or {}
            error = message.get("error")
            if error:
                self._finish_request(request_id, body_unavailable=str(error.get("message") or "cdp_error")[:300])
                return
            body = result.get("body")
            if result.get("base64Encoded") and body:
                try:
                    body = base64.b64decode(body)
                except Exception:
                    body = b""
            record = self._requests.get(request_id)
            if record is not None:
                safe_body, truncated = _raw_body(body, str(record.get("mime_type") or ""))
                record["response_body"] = safe_body
                if truncated:
                    record["response_body_truncated"] = True
            self._finish_request(request_id)
            return

        method = str(message.get("method") or "")
        params = message.get("params") or {}
        if method == "Network.requestWillBeSent":
            request_id = str(params.get("requestId") or "")
            if params.get("redirectResponse") and request_id in self._requests:
                redirect = params.get("redirectResponse") or {}
                current = self._requests[request_id]
                current.update({
                    "status": redirect.get("status"),
                    "response_headers": _raw_headers(redirect.get("headers") or {}),
                    "redirect": True,
                })
                self._finish_request(request_id, body_unavailable="redirect")
                self._redirect_seq[request_id] += 1
            request = params.get("request") or {}
            post_body, post_truncated = _raw_body(request.get("postData"), str((request.get("headers") or {}).get("content-type") or ""))
            self._requests[request_id] = {
                "capture_request_id": self._request_key(request_id),
                "target_id": self.target_id,
                "target_type": self.target_type,
                "stage": self.session.current_stage,
                "started_at": _now_iso(),
                "started_monotonic": params.get("timestamp"),
                "method": request.get("method"),
                "url": _raw_url(request.get("url")),
                "resource_type": params.get("type"),
                "request_headers": _raw_headers(request.get("headers") or {}),
                "request_body": post_body,
                "request_body_truncated": post_truncated,
                "initiator": params.get("initiator") or {},
                "document_url": _raw_url(params.get("documentURL")),
            }
        elif method == "Network.requestWillBeSentExtraInfo":
            request_id = str(params.get("requestId") or "")
            if request_id in self._requests:
                self._requests[request_id]["request_headers"] = _raw_headers(params.get("headers") or {})
        elif method == "Network.responseReceived":
            request_id = str(params.get("requestId") or "")
            record = self._requests.get(request_id)
            if record is None:
                return
            response = params.get("response") or {}
            record.update({
                "status": response.get("status"),
                "status_text": response.get("statusText"),
                "mime_type": response.get("mimeType"),
                "response_headers": _raw_headers(response.get("headers") or {}),
                "protocol": response.get("protocol"),
                "remote_ip": response.get("remoteIPAddress"),
                "remote_port": response.get("remotePort"),
                "from_disk_cache": bool(response.get("fromDiskCache")),
                "from_service_worker": bool(response.get("fromServiceWorker")),
                "timing": response.get("timing") or {},
            })
        elif method == "Network.responseReceivedExtraInfo":
            request_id = str(params.get("requestId") or "")
            if request_id in self._requests:
                self._requests[request_id]["response_headers"] = _raw_headers(params.get("headers") or {})
        elif method == "Network.loadingFinished":
            request_id = str(params.get("requestId") or "")
            record = self._requests.get(request_id)
            if record is None:
                return
            record["encoded_data_length"] = params.get("encodedDataLength")
            started = record.get("started_monotonic")
            if started is not None and params.get("timestamp") is not None:
                record["duration_ms"] = round(max(0.0, float(params["timestamp"]) - float(started)) * 1000, 2)
            mime = str(record.get("mime_type") or "").lower()
            capture_body = any(marker in mime for marker in ("json", "text/", "html", "xml", "javascript", "x-www-form-urlencoded"))
            if capture_body and self.session.body_capture_enabled:
                self._send("Network.getResponseBody", {"requestId": request_id}, {"request_id": request_id})
            else:
                self._finish_request(request_id, body_unavailable="binary_or_disabled")
        elif method == "Network.loadingFailed":
            request_id = str(params.get("requestId") or "")
            self._finish_request(
                request_id,
                failure=str(params.get("errorText") or "network_failed")[:500],
                body_unavailable="loading_failed",
            )
        elif method == "Network.webSocketCreated":
            self.session.record({"kind": "websocket_open", "target_id": self.target_id, "url": _raw_url(params.get("url"))})
        elif method in {"Network.webSocketFrameSent", "Network.webSocketFrameReceived"}:
            response = params.get("response") or {}
            payload, truncated = _raw_body(response.get("payloadData"), "text/plain")
            self.session.websocket_frame_count += 1
            self.session.record({
                "kind": "websocket_frame",
                "target_id": self.target_id,
                "direction": "sent" if method.endswith("Sent") else "received",
                "opcode": response.get("opcode"),
                "payload": payload,
                "truncated": truncated,
            })
        elif method == "Network.webSocketClosed":
            self.session.record({"kind": "websocket_close", "target_id": self.target_id})
        elif method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails") or {}
            self.session.record({
                "kind": "page_error",
                "target_id": self.target_id,
                "text": str(details.get("text") or "")[:2000],
                "url": _raw_url(details.get("url")),
                "line": details.get("lineNumber"),
                "column": details.get("columnNumber"),
            })
        elif method == "Log.entryAdded":
            entry = params.get("entry") or {}
            if str(entry.get("level") or "").lower() in {"error", "warning"}:
                self.session.record({
                    "kind": "console",
                    "target_id": self.target_id,
                    "level": entry.get("level"),
                    "source": entry.get("source"),
                    "url": _raw_url(entry.get("url")),
                    "text": str(entry.get("text") or "")[:4000],
                })

    def _finish_request(self, request_id: str, *, failure: str = "", body_unavailable: str = "") -> None:
        record = self._requests.pop(str(request_id or ""), None)
        if not record:
            return
        record.pop("started_monotonic", None)
        if failure:
            record["failure"] = str(failure)[:500]
        if body_unavailable and "response_body" not in record:
            record["response_body_omitted"] = body_unavailable
        self.session.record_network(record)


class RoxyCDPCollector:
    """通过 Roxy debuggerAddress 旁路监听所有页面/worker Target。"""

    def __init__(self, session: RegistrationDebugSession, debugger_address: str):
        self.session = session
        address = str(debugger_address or "").strip().rstrip("/")
        self.http_base = address if address.startswith(("http://", "https://")) else f"http://{address}"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll_targets, name=f"debug-cdp-discovery-{session.job_id}", daemon=True)
        self._targets: dict[str, _RoxyTargetCollector] = {}
        self._lock = threading.RLock()

    def start(self) -> None:
        self.session.record({"kind": "collector_started", "collector": "roxy_cdp", "endpoint": _raw_url(self.http_base)})
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        with self._lock:
            targets = list(self._targets.values())
            self._targets.clear()
        for target in targets:
            target.stop()

    def _load_targets(self) -> list[dict]:
        req = Request(f"{self.http_base}/json/list", headers={"Accept": "application/json"})
        with urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data if isinstance(data, list) else []

    def _poll_targets(self) -> None:
        while not self._stop.is_set():
            try:
                items = self._load_targets()
                live_ids: set[str] = set()
                for item in items:
                    target_type = str(item.get("type") or "")
                    if target_type not in {"page", "iframe", "service_worker", "shared_worker", "worker"}:
                        continue
                    target_id = str(item.get("id") or "")
                    ws_url = str(item.get("webSocketDebuggerUrl") or "")
                    if not target_id or not ws_url:
                        continue
                    live_ids.add(target_id)
                    with self._lock:
                        if target_id not in self._targets:
                            collector = _RoxyTargetCollector(self, target_id, ws_url, target_type)
                            self._targets[target_id] = collector
                            collector.start()
                with self._lock:
                    stale = [key for key in self._targets if key not in live_ids]
                    stale_collectors = [self._targets.pop(key) for key in stale]
                for collector in stale_collectors:
                    collector.stop()
            except Exception as exc:
                if not self._stop.is_set():
                    self.session.record({"kind": "capture_warning", "reason": "roxy_target_discovery_failed", "error": f"{type(exc).__name__}: {exc}"})
            self._stop.wait(0.5)


def activate_for_job(job: dict) -> contextvars.Token | None:
    # ThreadPoolExecutor 会复用工作线程。若上一个任务在异常/中断路径
    # 没有成功 reset ContextVar，当前任务不能继承那个任务的调试会话；否则
    # 即使本任务关闭了诊断，Roxy 启动逻辑仍会把它误判为调试任务。
    stale_session = _CURRENT_SESSION.get()
    if stale_session is not None:
        try:
            stale_session.finalize(status="interrupted")
        except Exception:
            logger.exception("清理遗留注册调试会话失败：job_id=%s", getattr(stale_session, "job_id", "-"))
        finally:
            _CURRENT_SESSION.set(None)

    debug_enabled = bool(job.get("debug_enabled", False))
    failure_diagnostics_enabled = bool(getattr(_cfg, "REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED", True))
    if not debug_enabled and not failure_diagnostics_enabled:
        return None
    session = RegistrationDebugSession(
        job,
        capture_mode="full" if debug_enabled else "failure_only",
    )
    with _ACTIVE_LOCK:
        _ACTIVE[session.job_id] = session
    return _CURRENT_SESSION.set(session)


def patch_job(job_id: int, **changes: Any) -> bool:
    """用 registration_jobs 的 JSONB 扩展字段保存调试元数据。

    调试字段不是任务状态机的提升列，直接走行级 patch 可避免全量快照覆盖
    其它线程正在写入的状态，同时不需要为每个新调试字段做数据库迁移。
    """
    from core import record_store

    return bool(record_store.patch_row(record_store.JOBS, int(job_id), dict(changes)))


def deactivate_for_job(token: contextvars.Token | None, status: str = "") -> None:
    session = _CURRENT_SESSION.get()
    try:
        if session is not None:
            session.finalize(status=status)
    finally:
        # 没有 token 时表示本任务没有创建调试会话；也要清空当前线程可能
        # 遗留的 ContextVar，不能让线程池把旧会话带给下一个任务。
        if token is not None:
            try:
                _CURRENT_SESSION.reset(token)
            except Exception:
                _CURRENT_SESSION.set(None)
        else:
            _CURRENT_SESSION.set(None)


def current_session() -> RegistrationDebugSession | None:
    return _CURRENT_SESSION.get()


def update_current_stage(
    stage: str,
    state: str = "running",
    detail: str | None = None,
    wait_reason: str | None = None,
) -> None:
    session = current_session()
    if session is not None:
        session.update_stage(stage, state=state, detail=detail, wait_reason=wait_reason)


def update_current_stage_timing(
    stage: str,
    *,
    state: str = "running",
    detail: str | None = None,
    wait_reason: str | None = None,
) -> None:
    """Stage progress entry point that carries the optional wait reason."""
    session = current_session()
    if session is not None:
        session.update_stage(stage, state=state, detail=detail, wait_reason=wait_reason)


def update_current_context(**kwargs: Any) -> None:
    session = current_session()
    if session is not None:
        session.update_context(**kwargs)


def record_email_evidence(evidence: Any) -> None:
    session = current_session()
    if session is not None:
        session.record_email_evidence(evidence)


def attach_current_roxy(debugger_address: str | None) -> None:
    session = current_session()
    if session is not None:
        session.attach_roxy(debugger_address)


def pause_current_failure(driver: Any, reason: str) -> str:
    session = current_session()
    if session is None:
        return "disabled"
    return session.pause_failure(driver, reason)


def capture_current_failure(reason: str, driver: Any = None) -> str:
    """普通模式失败收口入口；调试模式由原有暂停逻辑负责，不重复保留现场。"""
    session = current_session()
    if session is None or session.capture_mode != "failure_only" or session.failure_captured:
        return "disabled"
    return session.pause_failure(driver, reason)


def release_job(job_id: int, action: str = "finish") -> dict:
    with _ACTIVE_LOCK:
        session = _ACTIVE.get(int(job_id))
    if session is None:
        return {"ok": False, "error": "调试会话不在当前进程或已经结束", "status": 409}
    return session.release(action=action)


def active_summary(job_id: int) -> dict | None:
    with _ACTIVE_LOCK:
        session = _ACTIVE.get(int(job_id))
    return session.summary() if session is not None else None


def record_protocol_exchange(
    *,
    method: str,
    url: str,
    started_at: float,
    request_headers: dict | None = None,
    request_body: object = None,
    response: Any = None,
    error: BaseException | None = None,
) -> None:
    session = current_session()
    if session is None:
        return
    elapsed_ms = round(max(0.0, time.perf_counter() - started_at) * 1000, 2)
    response_status = int(getattr(response, "status_code", 0) or 0) if response is not None else 0
    if session.capture_mode == "failure_only" and not error and response_status < 400:
        # 普通模式不读取成功响应正文，也不把成功请求放进内存；失败收口时
        # 只保留 HTTP 错误或传输异常的元数据。
        return
    content_type = ""
    response_headers: dict = {}
    response_body = None
    status = 0
    final_url = url
    if response is not None:
        status = response_status
        response_headers = dict(getattr(response, "headers", {}) or {})
        content_type = str(response_headers.get("content-type") or "")
        final_url = str(getattr(response, "url", "") or url)
        try:
            response_body, response_truncated = _raw_body(getattr(response, "text", ""), content_type)
        except Exception:
            response_truncated = False
    else:
        response_truncated = False
    safe_request_body, request_truncated = _raw_body(request_body, str((request_headers or {}).get("content-type") or ""))
    session.record_network({
        "segment": "registration_protocol",
        "stage": session.current_stage,
        "started_at": _now_iso(),
        "method": str(method or "GET").upper(),
        "url": _raw_url(final_url),
        "request_headers": _raw_headers(request_headers or {}),
        "request_body": safe_request_body,
        "request_body_truncated": request_truncated,
        "status": status,
        "response_headers": _raw_headers(response_headers),
        "response_body": response_body,
        "response_body_truncated": response_truncated,
        "duration_ms": elapsed_ms,
        "failure": f"{type(error).__name__}: {error}"[:500] if error else "",
    })
    # curl_cffi 的 redirect history 也作为独立请求事件保存，便于还原协议跳转链。
    if response is not None:
        for index, history in enumerate(list(getattr(response, "history", []) or [])):
            session.record_network({
                "segment": "registration_protocol",
                "stage": session.current_stage,
                "started_at": _now_iso(),
                "method": str(getattr(getattr(history, "request", None), "method", "GET") or "GET"),
                "url": _raw_url(getattr(history, "url", "")),
                "status": int(getattr(history, "status_code", 0) or 0),
                "response_headers": dict(getattr(history, "headers", {}) or {}),
                "redirect": True,
                "redirect_index": index,
            })


def _artifact_dir_for_job(job: dict) -> Path:
    configured = str(
        job.get("debug_artifact_dir")
        or job.get("failure_diagnostics_artifact_dir")
        or ""
    ).strip()
    path = Path(configured) if configured else _safe_artifact_dir(job)
    resolved_root = _ARTIFACT_ROOT.resolve()
    resolved = path.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError("调试产物路径不在允许目录")
    return resolved


def read_events(job: dict, *, limit: int = 300, errors_only: bool = False) -> list[dict]:
    path = _artifact_dir_for_job(job) / "network.jsonl.gz"
    if not path.exists():
        return []
    selected: deque[dict] = deque(maxlen=max(1, min(5000, int(limit or 300))))
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if item.get("kind") != "network_request":
                    continue
                if errors_only and not (item.get("failure") or int(item.get("status") or 0) >= 400):
                    continue
                selected.append(item)
    except EOFError:
        # writer 仍在追加 gzip 数据时，读端可能暂时看不到完整 trailer；返回已读事件即可。
        logger.debug("[Job %s][Debug] 抓包文件仍在写入，暂时读取到文件尾", job.get("id"))
    except OSError:
        logger.warning("[Job %s][Debug] 读取抓包文件失败", job.get("id"), exc_info=True)
    return list(selected)


def read_timeline(job: dict, *, limit: int = 500) -> list[dict]:
    """Read all structured diagnostic events, including stage and evidence events."""
    path = _artifact_dir_for_job(job) / "network.jsonl.gz"
    if not path.exists():
        return []
    selected: deque[dict] = deque(maxlen=max(1, min(5000, int(limit or 500))))
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if isinstance(item, dict):
                    selected.append(item)
    except (EOFError, OSError):
        logger.debug("[Job %s][Debug] 诊断时间线读取到当前文件尾", job.get("id"), exc_info=True)
    return list(selected)


def read_page_state(job: dict) -> dict:
    """读取本地原始页面现场；不存在时返回空对象。"""
    path = _artifact_dir_for_job(job) / "last-page.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def screenshot_path(job: dict) -> Path | None:
    """返回经过产物目录校验的失败截图路径。"""
    path = _artifact_dir_for_job(job) / "last-page.png"
    return path if path.is_file() else None


def build_har(job: dict) -> dict:
    entries = []
    for item in read_events(job, limit=5000):
        request_headers = [{"name": str(k), "value": str(v)} for k, v in (item.get("request_headers") or {}).items()]
        response_headers = [{"name": str(k), "value": str(v)} for k, v in (item.get("response_headers") or {}).items()]
        post_data = item.get("request_body")
        response_body = item.get("response_body")
        entries.append({
            "startedDateTime": item.get("started_at") or item.get("captured_at") or _now_iso(),
            "time": float(item.get("duration_ms") or 0),
            "request": {
                "method": item.get("method") or "GET",
                "url": item.get("url") or "",
                "httpVersion": "HTTP/1.1",
                "headers": request_headers,
                "queryString": [],
                "cookies": [],
                "headersSize": -1,
                "bodySize": -1,
                **({"postData": {"mimeType": "application/json", "text": json.dumps(post_data, ensure_ascii=False, default=str)}} if post_data is not None else {}),
            },
            "response": {
                "status": int(item.get("status") or 0),
                "statusText": item.get("status_text") or "",
                "httpVersion": item.get("protocol") or "",
                "headers": response_headers,
                "cookies": [],
                "content": {
                    "size": int(item.get("encoded_data_length") or 0),
                    "mimeType": item.get("mime_type") or "",
                    **({"text": json.dumps(response_body, ensure_ascii=False, default=str)} if response_body is not None else {}),
                },
                "redirectURL": "",
                "headersSize": -1,
                "bodySize": int(item.get("encoded_data_length") or -1),
            },
            "cache": {},
            "timings": {"send": 0, "wait": float(item.get("duration_ms") or 0), "receive": 0},
            "comment": json.dumps({
                "job_id": job.get("id"),
                "stage": item.get("stage"),
                "failure": item.get("failure"),
                "from_service_worker": item.get("from_service_worker"),
            }, ensure_ascii=False),
        })
    return {"log": {"version": "1.2", "creator": {"name": "turb-registration-debug", "version": "1"}, "entries": entries}}


def compare_jobs(target_job: dict, baseline_job: dict) -> dict:
    def keyed(rows: list[dict]) -> dict[tuple, dict]:
        counts: defaultdict[tuple, int] = defaultdict(int)
        out: dict[tuple, dict] = {}
        for item in rows:
            try:
                parsed = urlsplit(str(item.get("url") or ""))
                base = (str(item.get("stage") or ""), str(item.get("method") or ""), parsed.netloc, parsed.path)
            except Exception:
                base = (str(item.get("stage") or ""), str(item.get("method") or ""), "", str(item.get("url") or ""))
            counts[base] += 1
            out[base + (counts[base],)] = item
        return out

    target = keyed(read_events(target_job, limit=5000))
    baseline = keyed(read_events(baseline_job, limit=5000))
    differences = []
    for key in list(dict.fromkeys([*baseline.keys(), *target.keys()])):
        left = baseline.get(key)
        right = target.get(key)
        if left is None:
            kind = "target_only"
        elif right is None:
            kind = "baseline_only"
        elif (
            int(left.get("status") or 0), bool(left.get("failure")), left.get("response_body")
        ) == (
            int(right.get("status") or 0), bool(right.get("failure")), right.get("response_body")
        ):
            continue
        else:
            kind = "changed"
        differences.append({
            "kind": kind,
            "stage": key[0],
            "method": key[1],
            "host": key[2],
            "path": key[3],
            "ordinal": key[4],
            "baseline": _comparison_item(left),
            "target": _comparison_item(right),
        })
        if len(differences) >= 500:
            break
    return {
        "baseline_job_id": baseline_job.get("id"),
        "target_job_id": target_job.get("id"),
        "difference_count": len(differences),
        "differences": differences,
    }


def _comparison_item(item: dict | None) -> dict | None:
    if item is None:
        return None
    return {
        "status": item.get("status"),
        "duration_ms": item.get("duration_ms"),
        "failure": item.get("failure"),
        "response_body": item.get("response_body"),
        "from_service_worker": item.get("from_service_worker"),
        "remote_ip": item.get("remote_ip"),
    }


def delete_job_artifacts(job: dict) -> None:
    try:
        path = _artifact_dir_for_job(job)
    except ValueError:
        return
    if not path.exists():
        return
    # 安全约束：逐文件删除，不做递归目录删除命令。
    for item in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        try:
            if item.is_file() or item.is_symlink():
                item.unlink(missing_ok=True)
            elif item.is_dir():
                item.rmdir()
        except OSError:
            logger.warning("[Job %s][Debug] 删除调试产物失败：%s", job.get("id"), item)
    try:
        path.rmdir()
    except OSError:
        pass


def cleanup_expired_artifacts() -> dict:
    days = max(1, int(getattr(_cfg, "REGISTRATION_DEBUG_RETENTION_DAYS", 7) or 7))
    cutoff = time.time() - days * 86400
    removed_files = 0
    removed_dirs = 0
    if not _ARTIFACT_ROOT.exists():
        return {"removed_files": 0, "removed_dirs": 0}
    with _ACTIVE_LOCK:
        active_dirs = {session.artifact_dir.resolve() for session in _ACTIVE.values()}
    for directory in list(_ARTIFACT_ROOT.iterdir()):
        try:
            if not directory.is_dir() or directory.resolve() in active_dirs or directory.stat().st_mtime >= cutoff:
                continue
        except OSError:
            continue
        for item in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                    removed_files += 1
                elif item.is_dir():
                    item.rmdir()
                    removed_dirs += 1
            except OSError:
                continue
        try:
            directory.rmdir()
            removed_dirs += 1
        except OSError:
            pass
    return {"removed_files": removed_files, "removed_dirs": removed_dirs}
