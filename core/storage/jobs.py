"""注册任务仓储公开入口。"""
from __future__ import annotations

from typing import Any, Callable

_NAMES = {
    "create_job", "create_retry_job", "update_job", "transition_job_status", "claim_job_for_execution",
    "cancel_pending_jobs", "update_job_progress", "finish_job_progress", "recover_interrupted_registration_jobs",
    "list_jobs", "get_job", "count_registration_jobs_by_batch_email", "claim_registration_batch_email",
    "get_successful_retry_for_job", "get_successful_retries_for_jobs",
    "get_accounts_for_jobs", "delete_job", "delete_jobs", "migrate_legacy_files",
}
_REGISTRATION_NAMES = {
    "create_attempt", "ensure_attempt_for_job", "get_attempt", "get_attempt_by_job", "list_attempts",
    "advance_checkpoint", "mark_request_unknown", "mark_manual_reconcile", "start_run", "retry_run",
    "list_runs", "get_run", "finish_run", "persist_core_account", "events", "backfill", "verify",
    "recover_interrupted_runs", "list_events", "mark_checkpoint", "record_checkpoint", "persist_account_core",
}


def _legacy(name: str) -> Callable[..., Any]:
    from core.storage import db_legacy

    return getattr(db_legacy, name)


def __getattr__(name: str) -> Any:
    if name in _REGISTRATION_NAMES:
        from core.storage import registration

        return getattr(registration, name)
    if name not in _NAMES:
        raise AttributeError(name)
    return _legacy(name)


__all__ = sorted(_NAMES | _REGISTRATION_NAMES)
