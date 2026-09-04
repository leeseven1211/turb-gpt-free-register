"""账号仓储公开入口。

实现仍集中在兼容迁移模块中，入口函数通过懒解析保持热更新和旧测试 patch 兼容。
后续按查询/命令继续下沉到本模块。
"""
from __future__ import annotations

from typing import Any, Callable

_NAMES = {
    "insert_account", "get_account", "get_account_by_email", "list_accounts", "list_accounts_page",
    "update_account_codex_status", "update_account_codex_operation_state", "update_account_login_password",
    "update_account_password_capability",
    "update_account_totp_secret", "update_account_twofa_status", "update_account_token_metadata",
    "update_account_session", "sync_account_token_metadata", "update_account_note", "update_account_registration_proxy",
    "backfill_account_registration_proxy_context", "update_account_deactivation_mail", "update_account_liveness",
    "mark_account_deactivated",
    "account_is_deactivated", "claim_account_live_check", "recover_interrupted_live_checks",
    "mark_account_live_check_running", "update_accounts_note", "archive_account", "archive_accounts",
    "count_accounts", "delete_account", "delete_accounts", "claim_account_plan_check",
    "mark_account_plan_check_running", "recover_interrupted_plan_checks", "update_account_plan_check",
    "claim_account_extract", "mark_account_extract_running", "recover_interrupted_extract_links", "update_account_extract",
}


def _legacy(name: str) -> Callable[..., Any]:
    from core.storage import db_legacy

    return getattr(db_legacy, name)


def __getattr__(name: str) -> Any:
    if name not in _NAMES:
        raise AttributeError(name)
    return _legacy(name)


__all__ = sorted(_NAMES)
