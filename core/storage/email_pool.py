"""邮箱池仓储公开入口。"""
from __future__ import annotations

from typing import Any, Callable

_NAMES = {
    "email_pool_secret", "import_outlook_accounts", "import_registered_email_accounts", "claim_next_outlook",
    "release_outlook", "release_unconsumed_outlook", "delete_outlook", "list_outlook_pool", "outlook_pool_summary",
    "get_outlook_by_email", "import_generic_api_emails", "claim_next_generic_api_email", "release_generic_api_email",
    "release_unconsumed_generic_api_email", "delete_generic_api_email", "list_generic_api_email_pool",
    "generic_api_email_pool_summary", "get_generic_api_email_by_email", "claim_next_domain_email", "release_domain_email",
    "release_unconsumed_domain_email", "get_domain_email_by_email", "list_domain_email_pool", "domain_email_pool_summary",
    "delete_domain_email", "sync_icloud_hide_aliases", "claim_next_icloud_hide_email", "release_icloud_hide_email",
    "release_unconsumed_icloud_hide_email", "get_icloud_hide_email_by_email", "list_icloud_hide_email_pool",
    "icloud_hide_email_pool_summary", "delete_icloud_hide_email",
}


def _legacy(name: str) -> Callable[..., Any]:
    from core.storage import db_legacy

    return getattr(db_legacy, name)


def __getattr__(name: str) -> Any:
    if name not in _NAMES:
        raise AttributeError(name)
    return _legacy(name)


__all__ = sorted(_NAMES)
