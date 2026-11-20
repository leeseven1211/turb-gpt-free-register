"""在 HTTP 线程中累计少量耗时数据，供慢请求日志使用。"""
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(slots=True)
class RequestTiming:
    queue_seconds: float
    route: str = ""
    handler_seconds: float = 0.
    handler_finished: float | None = None
    json_seconds: float = 0.
    pool_seconds: float = 0.


current_request_timing = ContextVar[RequestTiming | None]("current_request_timing", default=None)
