# -*- coding: utf-8 -*-
"""Rust sentinel-rs 内核的运行参数（只影响 rust / sentinel_rs 注册）。"""
from config.env_loader import apply_env_overrides
from config.schema import schema_default

# 原生二进制路径；留空时按项目内 native/sentinel-rs 构建产物和 PATH 查找。
SENTINEL_RS_BIN = schema_default("SENTINEL_RS_BIN")

# 单次原生注册进程的总时限（秒），包含取码等待和回调阶段。
SENTINEL_RS_TIMEOUT_SECONDS = schema_default("SENTINEL_RS_TIMEOUT_SECONDS")

# 原生进程日志级别：Turb 只收脱敏尾部诊断，不转发正文。
SENTINEL_RS_LOG_LEVEL = schema_default("SENTINEL_RS_LOG_LEVEL")

apply_env_overrides(globals())
