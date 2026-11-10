# -*- coding: utf-8 -*-
"""C2A（ChatGPT2API）账号 AT 原位更新配置。"""
from config.env_loader import apply_env_overrides
from config.schema import schema_default

# C2A 管理 API 基址，例如 https://c2a.example.com。
C2A_API_BASE: str = schema_default("C2A_API_BASE")

# C2A 管理员 Key；请求头使用 Authorization: Bearer <key>。
C2A_API_KEY: str = schema_default("C2A_API_KEY")

# 查询远端账号与更新 AT 的单次 HTTP 超时秒数。
C2A_API_TIMEOUT: int = schema_default("C2A_API_TIMEOUT")

apply_env_overrides(globals())
