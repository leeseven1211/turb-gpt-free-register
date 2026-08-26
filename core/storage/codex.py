"""Codex 凭证仓储公开入口。"""
from __future__ import annotations

from typing import Any, Callable

_NAMES = {
    "get_account_by_email",
    "save_codex_credential_record", "write_codex_credential", "list_codex_accounts", "archive_codex",
    "read_codex_credential", "mark_codex_exported", "mark_codex_sub2_uploaded", "mark_codex_sub2_sync_error",
    "mark_codex_oauth_refresh", "reset_codex_exported", "delete_codex_credential", "codex_accounts_summary",
}


def _legacy(name: str) -> Callable[..., Any]:
    from core.storage import db_legacy

    return getattr(db_legacy, name)


def __getattr__(name: str) -> Any:
    if name not in _NAMES:
        raise AttributeError(name)
    return _legacy(name)


__all__ = sorted(_NAMES)
