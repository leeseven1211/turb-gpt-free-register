# -*- coding: utf-8 -*-
"""按注册任务隔离的网络抓包与失败现场保留。

大体积事件只写本地私有日志目录；PostgreSQL 任务行仅保存摘要和文件位置。
抓包写入前统一脱敏，普通模式不会落盘 Cookie、Authorization、密码、OTP 或 Token。
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
    def __init__(self, job: dict):
        self.job_id = int(job["id"])
        self.job_uuid = str(job.get("job_uuid") or f"job-{self.job_id}")
        self.batch_id = str(job.get("batch_id") or "")
        self.artifact_dir = _safe_artifact_dir(job)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.artifact_dir / "network.jsonl.gz"
        self.manifest_path = self.artifact_dir / "manifest.json"
        self.snapshot_path = self.artifact_dir / "last-page.png"
        self.page_state_path = self.artifact_dir / "last-page.json"
        self.current_stage = str(job.get("progress_stage") or "browser")
        self.started_at = _now_iso()
        self.debug_state = "recording"
        self.hold_until = ""
        self.pause_reason = ""
        self.release_action = ""
        self._release_event = threading.Event()
        self._closed = threading.Event()
        self._queue: queue.Queue = queue.Queue(maxsize=max(1000, int(getattr(_cfg, "REGISTRATION_DEBUG_QUEUE_SIZE", 20000) or 20000)))
        self._writer = threading.Thread(target=self._writer_loop, name=f"debug-writer-{self.job_id}", daemon=True)
        self._collectors: list[Any] = []
        self._lock = threading.RLock()
        self.request_count = 0
        self.failed_count = 0
        self.http_error_count = 0
        self.websocket_frame_count = 0
        self.dropped_event_count = 0
        self.body_bytes_saved = 0
        self.body_budget_bytes = max(0, int(getattr(_cfg, "REGISTRATION_DEBUG_BODY_BUDGET_MB", 128) or 128)) * 1024 * 1024
        global_budget = max(0, int(getattr(_cfg, "REGISTRATION_DEBUG_GLOBAL_BUDGET_MB", 5120) or 5120)) * 1024 * 1024
        self.body_capture_enabled = not global_budget or _cached_artifact_size() < global_budget
        self._writer.start()
        self.record({
            "kind": "capture_started",
            "job_id": self.job_id,
            "batch_id": self.batch_id,
            "body_capture_enabled": self.body_capture_enabled,
        })
        self._patch_job(
            debug_state="recording",
            debug_artifact_dir=str(self.artifact_dir),
            debug_capture_started_at=self.started_at,
            debug_capture_summary=self.summary(),
        )

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
        if self._closed.is_set():
            return
        item = dict(event or {})
        item.setdefault("captured_at", _now_iso())
        item.setdefault("job_id", self.job_id)
        item.setdefault("stage", self.current_stage)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            # 先丢正文再尝试短暂等待，尽量保证每个请求至少留下元数据。
            item.pop("request_body", None)
            item.pop("response_body", None)
            item["capture_degraded"] = "queue_full"
            try:
                self._queue.put(item, timeout=0.2)
            except queue.Full:
                self.dropped_event_count += 1

    def update_stage(self, stage: str, state: str = "running", detail: str | None = None) -> None:
        if stage:
            self.current_stage = str(stage)
        self.record({
            "kind": "stage",
            "stage": self.current_stage,
            "state": str(state or "running"),
            "detail": _redact_text(detail)[:1000] if detail else "",
        })

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
        request_body = item.get("request_body")
        response_body = item.get("response_body")
        if request_body is not None and not self.reserve_body(request_body):
            item.pop("request_body", None)
            item["request_body_omitted"] = "body_budget"
        if response_body is not None and not self.reserve_body(response_body):
            item.pop("response_body", None)
            item["response_body_omitted"] = "body_budget"
        status = int(item.get("status") or 0)
        with self._lock:
            self.request_count += 1
            if item.get("failure"):
                self.failed_count += 1
            if status >= 400:
                self.http_error_count += 1
        self.record(item)

    def attach_roxy(self, debugger_address: str | None) -> None:
        if not debugger_address:
            self.record({"kind": "capture_warning", "reason": "roxy_debugger_address_missing"})
            return
        collector = RoxyCDPCollector(self, debugger_address)
        self._collectors.append(collector)
        collector.start()

    def capture_page_snapshot(self, driver: Any, reason: str) -> None:
        if driver is None:
            return
        try:
            driver.save_screenshot(str(self.snapshot_path))
        except Exception as exc:
            self.record({"kind": "snapshot_error", "operation": "screenshot", "error": f"{type(exc).__name__}: {exc}"})
        try:
            raw = driver.execute_script(
                """return {
                  url: location.href,
                  title: document.title || '',
                  readyState: document.readyState || '',
                  bodyText: (document.body && document.body.innerText || '').slice(0, 20000),
                  htmlLength: (document.documentElement && document.documentElement.outerHTML || '').length
                };"""
            ) or {}
            state = {
                "captured_at": _now_iso(),
                "reason": _redact_text(reason)[:1000],
                "url": sanitize_url(raw.get("url")),
                "title": _redact_text(raw.get("title"))[:500],
                "ready_state": raw.get("readyState"),
                "body_text": _redact_text(raw.get("bodyText"))[:20000],
                "html_length": raw.get("htmlLength"),
            }
            self.page_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            self.record({"kind": "page_snapshot", **state})
        except Exception as exc:
            self.record({"kind": "snapshot_error", "operation": "page_state", "error": f"{type(exc).__name__}: {exc}"})

    def pause_failure(self, driver: Any, reason: str) -> str:
        """在 Roxy 最终失败、进入 finally 清理之前保留现场。"""
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
        self.pause_reason = _redact_text(reason)[:1000]
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
            "request_count": int(self.request_count),
            "failed_count": int(self.failed_count),
            "http_error_count": int(self.http_error_count),
            "websocket_frame_count": int(self.websocket_frame_count),
            "dropped_event_count": int(self.dropped_event_count),
            "body_bytes_saved": int(self.body_bytes_saved),
            "body_capture_enabled": bool(self.body_capture_enabled),
            "hold_until": self.hold_until,
            "artifact_dir": str(self.artifact_dir),
        }

    def finalize(self, status: str = "") -> None:
        if self._closed.is_set():
            return
        for collector in self._collectors:
            try:
                collector.stop()
            except Exception:
                logger.exception("[Job %s][Debug] 停止抓包采集器失败", self.job_id)
        self.debug_state = "completed" if self.debug_state not in {"expired", "stopped"} else self.debug_state
        self.record({"kind": "capture_finished", "status": status, "summary": self.summary()})
        try:
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
            "started_at": self.started_at,
            "finished_at": _now_iso(),
            "status": status,
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
            debug_state=self.debug_state,
            debug_capture_completed_at=_now_iso(),
            debug_capture_summary=summary,
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
                safe_body, truncated = sanitize_body(body, str(record.get("mime_type") or ""))
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
                    "response_headers": sanitize_headers(redirect.get("headers") or {}),
                    "redirect": True,
                })
                self._finish_request(request_id, body_unavailable="redirect")
                self._redirect_seq[request_id] += 1
            request = params.get("request") or {}
            post_body, post_truncated = sanitize_body(request.get("postData"), str((request.get("headers") or {}).get("content-type") or ""))
            self._requests[request_id] = {
                "capture_request_id": self._request_key(request_id),
                "target_id": self.target_id,
                "target_type": self.target_type,
                "stage": self.session.current_stage,
                "started_at": _now_iso(),
                "started_monotonic": params.get("timestamp"),
                "method": request.get("method"),
                "url": sanitize_url(request.get("url")),
                "resource_type": params.get("type"),
                "request_headers": sanitize_headers(request.get("headers") or {}),
                "request_body": post_body,
                "request_body_truncated": post_truncated,
                "initiator": _redact_value(params.get("initiator") or {}),
                "document_url": sanitize_url(params.get("documentURL")),
            }
        elif method == "Network.requestWillBeSentExtraInfo":
            request_id = str(params.get("requestId") or "")
            if request_id in self._requests:
                self._requests[request_id]["request_headers"] = sanitize_headers(params.get("headers") or {})
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
                "response_headers": sanitize_headers(response.get("headers") or {}),
                "protocol": response.get("protocol"),
                "remote_ip": response.get("remoteIPAddress"),
                "remote_port": response.get("remotePort"),
                "from_disk_cache": bool(response.get("fromDiskCache")),
                "from_service_worker": bool(response.get("fromServiceWorker")),
                "timing": _redact_value(response.get("timing") or {}),
            })
        elif method == "Network.responseReceivedExtraInfo":
            request_id = str(params.get("requestId") or "")
            if request_id in self._requests:
                self._requests[request_id]["response_headers"] = sanitize_headers(params.get("headers") or {})
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
            self.session.record({"kind": "websocket_open", "target_id": self.target_id, "url": sanitize_url(params.get("url"))})
        elif method in {"Network.webSocketFrameSent", "Network.webSocketFrameReceived"}:
            response = params.get("response") or {}
            payload, truncated = sanitize_body(response.get("payloadData"), "text/plain")
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
                "text": _redact_text(details.get("text"))[:2000],
                "url": sanitize_url(details.get("url")),
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
                    "url": sanitize_url(entry.get("url")),
                    "text": _redact_text(entry.get("text"))[:4000],
                })

    def _finish_request(self, request_id: str, *, failure: str = "", body_unavailable: str = "") -> None:
        record = self._requests.pop(str(request_id or ""), None)
        if not record:
            return
        record.pop("started_monotonic", None)
        if failure:
            record["failure"] = _redact_text(failure)[:500]
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
        self.session.record({"kind": "collector_started", "collector": "roxy_cdp", "endpoint": sanitize_url(self.http_base)})
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
    if not bool(job.get("debug_enabled", False)):
        return None
    session = RegistrationDebugSession(job)
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
    if session is not None:
        session.finalize(status=status)
    if token is not None:
        try:
            _CURRENT_SESSION.reset(token)
        except Exception:
            _CURRENT_SESSION.set(None)


def current_session() -> RegistrationDebugSession | None:
    return _CURRENT_SESSION.get()


def update_current_stage(stage: str, state: str = "running", detail: str | None = None) -> None:
    session = current_session()
    if session is not None:
        session.update_stage(stage, state=state, detail=detail)


def attach_current_roxy(debugger_address: str | None) -> None:
    session = current_session()
    if session is not None:
        session.attach_roxy(debugger_address)


def pause_current_failure(driver: Any, reason: str) -> str:
    session = current_session()
    if session is None:
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
    content_type = ""
    response_headers: dict = {}
    response_body = None
    status = 0
    final_url = url
    if response is not None:
        status = int(getattr(response, "status_code", 0) or 0)
        response_headers = dict(getattr(response, "headers", {}) or {})
        content_type = str(response_headers.get("content-type") or "")
        final_url = str(getattr(response, "url", "") or url)
        lowered = content_type.lower()
        if any(marker in lowered for marker in ("json", "text/", "html", "xml", "x-www-form-urlencoded")):
            try:
                response_body, response_truncated = sanitize_body(getattr(response, "text", ""), content_type)
            except Exception:
                response_body, response_truncated = None, False
        else:
            response_truncated = False
    else:
        response_truncated = False
    safe_request_body, request_truncated = sanitize_body(request_body, str((request_headers or {}).get("content-type") or ""))
    session.record_network({
        "segment": "registration_protocol",
        "stage": session.current_stage,
        "started_at": _now_iso(),
        "method": str(method or "GET").upper(),
        "url": sanitize_url(final_url),
        "request_headers": sanitize_headers(request_headers or {}),
        "request_body": safe_request_body,
        "request_body_truncated": request_truncated,
        "status": status,
        "response_headers": sanitize_headers(response_headers),
        "response_body": response_body,
        "response_body_truncated": response_truncated,
        "duration_ms": elapsed_ms,
        "failure": f"{type(error).__name__}: {_redact_text(error)}"[:500] if error else "",
    })
    # curl_cffi 的 redirect history 也作为独立请求事件保存，便于还原协议跳转链。
    if response is not None:
        for index, history in enumerate(list(getattr(response, "history", []) or [])):
            session.record_network({
                "segment": "registration_protocol",
                "stage": session.current_stage,
                "started_at": _now_iso(),
                "method": str(getattr(getattr(history, "request", None), "method", "GET") or "GET"),
                "url": sanitize_url(getattr(history, "url", "")),
                "status": int(getattr(history, "status_code", 0) or 0),
                "response_headers": sanitize_headers(dict(getattr(history, "headers", {}) or {})),
                "redirect": True,
                "redirect_index": index,
            })


def _artifact_dir_for_job(job: dict) -> Path:
    configured = str(job.get("debug_artifact_dir") or "").strip()
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
