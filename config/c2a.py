# -*- coding: utf-8 -*-
"""C2A（ChatGPT2API）账号 AT 原位更新与异常巡检配置。"""
from config.env_loader import apply_env_overrides
from config.schema import schema_default

# C2A 管理 API 基址，例如 https://c2a.example.com。
C2A_API_BASE: str = schema_default("C2A_API_BASE")

# C2A 管理员 Key；请求头使用 Authorization: Bearer <key>。
C2A_API_KEY: str = schema_default("C2A_API_KEY")

# 查询远端账号与更新 AT 的单次 HTTP 超时秒数。
C2A_API_TIMEOUT: int = schema_default("C2A_API_TIMEOUT")

# 异常巡检按保存后的配置运行。关闭时继续推进已受理的修复。
C2A_MONITOR_ENABLED: bool = schema_default("C2A_MONITOR_ENABLED")
C2A_MONITOR_INTERVAL_SECONDS: int = schema_default("C2A_MONITOR_INTERVAL_SECONDS")
C2A_MONITOR_COOLDOWN_SECONDS: int = schema_default("C2A_MONITOR_COOLDOWN_SECONDS")
C2A_MONITOR_MAX_PER_CYCLE: int = schema_default("C2A_MONITOR_MAX_PER_CYCLE")

apply_env_overrides(globals())
