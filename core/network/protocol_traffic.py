"""协议 HTTP 的会话聚合计量，只保存数值和任务归属。

request_count 按 BrowserSession 的一次后端调用计数；业务重试分别计数，
后端自动跟随重定向只计入 redirect_count。upload/download 仅使用后端观测的
传输正文计数（压缩响应为解压前），不含 HTTP 头、TLS、隧道或代理商账单。
响应解压正文长度单独记录，不能回填为传输字节。预检出口探测、Node 请求及
绕过 BrowserSession.get/post 的请求不在此范围内。
"""
from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Mapping

logger = logging.getLogger('core.protocol_traffic')
_CORRELATION = ContextVar("protocol_traffic_correlation", default=None)
_INT_FIELDS = (
    "account_id", "operation_task_id", "operation_run_id", "registration_job_id",
    "route_attempt_no", "registration_attempt_id", "registration_run_id",
)
_STATUS_FAMILIES = ("1xx", "2xx", "3xx", "4xx", "5xx", "unknown")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _correlation(values: Mapping) -> dict:
    """业务归属使用白名单，URL、邮箱与私有字段没有存储入口。"""
    out = {}
    for field in _INT_FIELDS:
        value = values.get(field)
        if value is not None:
            try:
                out[field] = int(value)
            except (TypeError, ValueError, OverflowError):
                # 归属异常只使该字段不可观测，不能阻止注册执行。
                continue
    for field, limit in (("proxy_lease_id", 160), ("purpose", 80)):
        if values.get(field):
            out[field] = str(values[field])[:limit]
    return out


@contextmanager
def correlation_context(*, inherit: bool = True, **values):
    """关联默认继承外层；独立业务入口可禁用继承，退出后恢复原关联。"""
    outer = (_CORRELATION.get() or {}) if inherit else {}
    token = _CORRELATION.set({**outer, **_correlation(values)})
    try:
        yield
    finally:
        _CORRELATION.reset(token)


def current_correlation() -> dict:
    """向同一任务的浏览器观察器提供已验证的归属，返回副本。"""
    return dict(_CORRELATION.get() or {})


def _counter(response, field: str) -> int | None:
    value = getattr(response, field, None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return int(value)


class ProtocolTrafficCapture:
    """一个 HTTP 会话一个幂等汇总；数值内存聚合，短节流写入现有流量表。"""

    def __init__(self, correlation: Mapping, *, clock=time.monotonic, flush_interval=5.0):
        self.correlation = _correlation(correlation)
        self.clock = clock
        self.flush_interval = flush_interval
        self.summary_key = f"protocol-http:{uuid.uuid4().hex}"
        self._lock = threading.RLock()
        self._last_flush = None
        self._dirty = False
        self._summary = {
            "source": "protocol_http", "method": "http_backend", "availability": "available",
            "started_at": _now(), "ended_at": _now(),
            "upload_bytes": 0, "download_bytes": 0,
            "request_count": 0, "failed_count": 0, "unfinished_count": 0, "unknown_count": 0,
            "duration_ms": 0, "redirect_count": 0, "decoded_response_bytes": 0,
            "upload_observed_count": 0, "download_observed_count": 0,
            "byte_unknown_count": 0,
            "status_families": {family: 0 for family in _STATUS_FAMILIES},
            "byte_semantics": "http_transfer_body_without_headers_tls",
        }

    @classmethod
    def for_current_context(cls):
        from core.operations.run_log import current_context
        current = current_context()
        correlation = dict(_CORRELATION.get() or {})
        if current.get("task_id") is not None:
            correlation.setdefault("operation_task_id", current["task_id"])
        if current.get("run_id") is not None:
            correlation.setdefault("operation_run_id", current["run_id"])
        if not correlation:
            return None
        return cls(correlation)

    def bind(self, **correlation) -> None:
        with self._lock:
            self.correlation.update(_correlation(correlation))
            self._dirty = self._summary["request_count"] > 0

    def record(self, *, started_at: float, response=None, error=None) -> None:
        """读取后端已有计数，不序列化请求、响应头或内容。"""
        with self._lock:
            summary = self._summary
            summary["request_count"] += 1
            summary["ended_at"] = _now()
            summary["duration_ms"] += max(0, int((time.perf_counter() - started_at) * 1000))
            self._dirty = True
            if error is not None:
                summary["failed_count"] += 1
                summary["unfinished_count"] += 1
            # curl 超时异常可携带已观测的部分响应；不猜测未收到响应的字节。
            family_recorded = False
            try:
                if response is None and error is not None:
                    response = getattr(error, "response", None)
                status = _counter(response, "status_code") or 0
                family = f"{status // 100}xx" if 100 <= status < 600 else "unknown"
                summary["status_families"][family] += 1
                family_recorded = True
                if error is None and status >= 400:
                    summary["failed_count"] += 1
                if family == "unknown":
                    summary["unknown_count"] += 1
                upload = _counter(response, "upload_size")
                download = _counter(response, "download_size")
                if upload is not None:
                    summary["upload_bytes"] += upload
                    summary["upload_observed_count"] += 1
                if download is not None:
                    summary["download_bytes"] += download
                    summary["download_observed_count"] += 1
                if upload is None or download is None:
                    summary["byte_unknown_count"] += 1
                summary["redirect_count"] += _counter(response, "redirect_count") or 0
                content = getattr(response, "content", None)
                if isinstance(content, (bytes, bytearray, memoryview)):
                    summary["decoded_response_bytes"] += len(content)
            except Exception:
                # 计量异常不能替换 HTTP 的成功/失败结果，也不能记录异常私有文本。
                summary["unknown_count"] += 1
                summary["byte_unknown_count"] += 1
                if not family_recorded:
                    summary["status_families"]["unknown"] += 1
            due = self._last_flush is None or self.clock() - self._last_flush >= self.flush_interval
            if due:
                self.flush()

    def snapshot(self) -> dict:
        with self._lock:
            return {**self._summary, "status_families": dict(self._summary["status_families"])}

    def flush(self) -> None:
        """写入失败保留 dirty 状态供收口重试，不抛出业务异常。"""
        from core.browser import traffic as browser_traffic
        with self._lock:
            if not self._dirty:
                return
            self._last_flush = self.clock()
            try:
                promoted = {key: value for key, value in self.correlation.items()
                            if key not in {"registration_attempt_id", "registration_run_id"}}
                browser_traffic.persist_summary(
                    summary_key=self.summary_key,
                    summary={**self.snapshot(), **{key: self.correlation.get(key)
                             for key in ("registration_attempt_id", "registration_run_id")}},
                    **promoted,
                )
            except Exception:
                logger.debug("[流量] 协议汇总写入失败；业务继续")
                return
            self._dirty = False
