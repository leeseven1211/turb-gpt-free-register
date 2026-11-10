# -*- coding: utf-8 -*-
"""C2A 账号 Access Token 同步集成。"""

from core.integrations.c2a.client import (
    C2AError,
    configured_backend_identity,
    find_unique_account,
    update_account_access_token,
)

__all__ = [
    "C2AError",
    "configured_backend_identity",
    "find_unique_account",
    "update_account_access_token",
]
