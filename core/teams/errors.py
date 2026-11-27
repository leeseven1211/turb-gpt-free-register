"""Team HTTP 与领域层共用的可分类异常。"""
from __future__ import annotations


class TeamError(Exception):
    """保存公开的窄错误字段，不携带账号或远端认证材料。"""

    def __init__(self, code: str, message: str | None = None, *, status: int = 409,
                 field: str | None = None, retryable: bool = False,
                 details: dict | None = None) -> None:
        self.code = code
        self.message = message or code
        self.status = status
        self.field = field
        self.retryable = retryable
        self.details = details or {}
        super().__init__(self.message)
