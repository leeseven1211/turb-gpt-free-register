"""纯函数核验注册任务、根任务和 Attempt 的显式账号归属。"""
from __future__ import annotations


def registration_account_link(job: dict, root: dict | None, attempt: dict | None) -> tuple[str, int | None] | None:
    """返回同一身份的邮箱与账号 ID；显式冲突不能降级为按邮箱猜测。"""
    if not root or not attempt:
        return None
    try:
        root_id = int(job.get("root_job_id") or job["id"])
        attempt_id = int(job["attempt_id"])
        if (root_id <= 0 or attempt_id <= 0 or int(root["id"]) != root_id
                or int(root["attempt_id"]) != attempt_id or int(attempt["id"]) != attempt_id
                or int(root.get("root_job_id") or root_id) != root_id):
            return None
        roots = [int(attempt[key]) for key in ("root_job_id", "source_root_job_id") if attempt.get(key) is not None]
        if not roots or any(value != root_id for value in roots):
            return None
        account_ids = {int(item["account_id"]) for item in (job, root, attempt) if item.get("account_id") is not None}
        if len(account_ids) > 1 or any(value <= 0 for value in account_ids):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    root_email = str(root.get("email") or "").strip().casefold()
    snapshot = str(attempt.get("email_snapshot") or "").strip().casefold()
    expected = root_email or snapshot
    source_email = str(job.get("email") or "").strip().casefold()
    if not expected or snapshot != expected:
        return None
    if not root_email:
        source = str(root.get("email_source") or "").strip()
        if (not source or str(job.get("email_source") or "").strip() != source
                or (attempt.get("email_source") and str(attempt["email_source"]).strip() != source)):
            return None
        if not source_email and int(job["id"]) == root_id:
            source_email = expected
    legacy_email = str(attempt.get("email") or "").strip().casefold()
    if source_email != expected or legacy_email and legacy_email != expected:
        return None
    return expected, next(iter(account_ids), None)
