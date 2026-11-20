"""账号页原始受理回执的来源标识。"""
from __future__ import annotations

import re


def normalize_request_key(raw: str) -> str:
    if not re.fullmatch(r"(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", raw):
        raise ValueError("账号操作请求编号格式无效")
    return raw.replace("-", "")


def source_prefix(request_key: str) -> str:
    return f"webui-account-request:{request_key}"


def source_prefix_end(request_key: str) -> str:
    # 使用等长十六进制前缀的后继，允许查询复用来源唯一索引。
    digits = "0123456789abcdefg"
    return source_prefix(request_key[:-1] + digits[digits.index(request_key[-1]) + 1])
