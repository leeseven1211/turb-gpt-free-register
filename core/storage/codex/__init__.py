"""Codex 凭证和独立 callback 回执仓储公开入口。"""
from __future__ import annotations

from typing import Any, Callable

from core.storage import records as record_store

_NAMES = {
    "get_account_by_email",
    "save_codex_credential_record", "write_codex_credential", "list_codex_accounts", "archive_codex",
    "read_codex_credential", "mark_codex_exported", "mark_codex_sub2_uploaded", "mark_codex_sub2_sync_error",
    "mark_codex_oauth_refresh", "reset_codex_exported", "delete_codex_credential", "codex_accounts_summary",
    "mark_codex_account_deactivated", "update_account_codex_operation_state",
    "account_is_deactivated",
}


def _legacy(name: str) -> Callable[..., Any]:
    from core.storage import db_legacy

    return getattr(db_legacy, name)


def __getattr__(name: str) -> Any:
    if name not in _NAMES:
        raise AttributeError(name)
    return _legacy(name)


def _callback_filename(filename: str) -> str:
    name = str(filename or "").strip()
    if (
        not name.startswith("codex-")
        or not name.endswith(".json")
        or "/" in name
        or "\\" in name
        or ".." in name
    ):
        raise ValueError("非法 Codex callback 回执文件名")
    return name


def save_codex_callback_receipt(filename: str, content: dict, *, source: str) -> int:
    """幂等保存远端 callback 回执，不将其视为可用 OAuth 凭证。"""
    name = _callback_filename(filename)
    if source not in {"cpa", "sub2"}:
        raise ValueError(f"不支持的 Codex callback 来源: {source}")
    if not isinstance(content, dict):
        raise ValueError("Codex callback 回执必须是 JSON 对象")
    return record_store.upsert_row_by(
        record_store.CODEX_CALLBACK_RECEIPTS,
        "filename",
        {"filename": name, "email": str(content.get("email") or ""), "source": source, "content": content},
    )


def read_codex_callback_receipt(filename: str) -> dict | None:
    """只从 PostgreSQL 读取回执行，不扫描或回退到本地 JSON。"""
    return record_store.get_row_by(
        record_store.CODEX_CALLBACK_RECEIPTS, "filename", _callback_filename(filename)
    )


__all__ = sorted(_NAMES | {"save_codex_callback_receipt", "read_codex_callback_receipt"})
