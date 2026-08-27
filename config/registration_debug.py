# -*- coding: utf-8 -*-
"""注册调试与失败现场诊断的运行时限制。"""
from config.env_loader import apply_env_overrides

# 失败浏览器现场的默认保留时间。只影响本次显式开启调试的注册任务。
REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS: int = 1800

# 普通模式失败时保存轻量现场；不会拦截全量网络请求，也不会暂停浏览器。
REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED: bool = True

# 普通模式失败现场最多保留的资源时序条数，避免异常页面返回过大的性能条目。
REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT: int = 80

# 普通模式失败现场的页面可见文本最大大小（KB）。
REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB: int = 32

# 同时暂停并保留的失败现场数量；超过上限时仍保存抓包，但不继续占用浏览器。
REGISTRATION_DEBUG_MAX_HELD_SESSIONS: int = 16

# 单个文本/JSON 请求或响应正文的最大保存大小。
REGISTRATION_DEBUG_BODY_MAX_KB: int = 1024

# 单任务允许保存的正文总量。达到上限后继续记录请求元数据。
REGISTRATION_DEBUG_BODY_BUDGET_MB: int = 128

# 所有调试产物的软上限；超过后新任务自动降级为只记录元数据。
REGISTRATION_DEBUG_GLOBAL_BUDGET_MB: int = 5120

# 调试产物默认保留天数。
REGISTRATION_DEBUG_RETENTION_DAYS: int = 7

# 每个任务的异步写入队列长度。
REGISTRATION_DEBUG_QUEUE_SIZE: int = 20000

apply_env_overrides(globals(), {
    "REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS": "int",
    "REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED": "bool",
    "REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT": "int",
    "REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB": "int",
    "REGISTRATION_DEBUG_MAX_HELD_SESSIONS": "int",
    "REGISTRATION_DEBUG_BODY_MAX_KB": "int",
    "REGISTRATION_DEBUG_BODY_BUDGET_MB": "int",
    "REGISTRATION_DEBUG_GLOBAL_BUDGET_MB": "int",
    "REGISTRATION_DEBUG_RETENTION_DAYS": "int",
    "REGISTRATION_DEBUG_QUEUE_SIZE": "int",
})
