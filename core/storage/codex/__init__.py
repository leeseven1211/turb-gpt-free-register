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


def get_codex_account(filename: str) -> dict | None:
    """按唯一文件名读取一份列表元数据，不扫描全部凭证。"""
    name = _legacy("_validate_codex_filename")(filename)
    row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", name)
    return _legacy("_codex_public_row")(row) if row else None


def get_codex_accounts_by_filenames(filenames: list[str]) -> dict[str, dict]:
    """一次集合查询定位显式文件名，避免批量入口逐项全量列表。"""
    names = list(dict.fromkeys(_legacy("_validate_codex_filename")(value) for value in filenames))
    if not names:
        return {}
    return {row["filename"]: _legacy("_codex_public_row")(row)
            for row in record_store.list_rows(record_store.CODEX_CREDENTIALS,
                where="filename=ANY(%s)", params=(names,))}


def get_codex_account_by_email(email: str) -> dict | None:
    """沿用旧列表的时间/ID排序，只读取规范邮箱匹配的首份凭证。"""
    normalized = str(email or "").strip().casefold()
    if not normalized:
        return None
    rows = record_store.list_rows(record_store.CODEX_CREDENTIALS,
        where="LOWER(BTRIM(email))=%s", params=(normalized,),
        order_by="COALESCE(mtime,updated_at) DESC,id DESC", limit=1)
    return _legacy("_codex_public_row")(rows[0]) if rows else None


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


__all__ = sorted(_NAMES | {"save_codex_callback_receipt", "read_codex_callback_receipt",
                         "get_codex_account", "get_codex_accounts_by_filenames", "get_codex_account_by_email"})
