"""账号页到原注册任务的适配；注册决策与执行仍由 registration.service 负责。"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping

from psycopg.rows import dict_row

from core import db
from core.registration import service as registration_service
from core.storage import postgres, records, registration

logger = logging.getLogger(__name__)
_ACTIVE = ("pending", "queued", "running", "stopping", "cancelling", "settling", "waiting", "debug_paused")
_REGISTRATION_TYPES = ("registration", "registration_resume")
_POSTPROCESS_TYPES = ("twofa_retry", "codex_retry")


def _id(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) or isinstance(value, str) and value.isascii() and value.isdigit():
        parsed = int(value)
        if 0 < parsed < 2**63:
            return parsed
    return None


def validate_account_ids(values) -> list[int]:
    if not isinstance(values, list) or not values:
        raise ValueError("account_ids 必须是非空数组")
    if len(values) > 500:
        raise ValueError("单次最多重跑 500 个账号")
    ids = [_id(value) for value in values]
    if any(value is None for value in ids):
        raise ValueError("account_ids 必须包含有效正整数")
    return list(dict.fromkeys(ids))


def _email(value) -> str:
    return str(value or "").strip().casefold()


def unavailable(reason="未找到可核验的原注册任务，请在任务记录中查看") -> dict:
    return {"available": False, "source_job_id": None, "action": None,
            "label": "重跑注册", "reason": reason, "active": False}


def _sources(account_ids: list[int]) -> tuple[dict, dict, dict]:
    """固定次数读取账号、显式关联 Attempt 和任务链；不按邮箱认领历史失败。"""
    accounts = records.list_rows(records.ACCOUNTS, where="id = ANY(%s)", params=(account_ids,),
                                 exclude_columns=("chatgpt_session",))
    by_account = {int(row["id"]): row for row in accounts}
    if not by_account:
        return {}, {}, {}
    registration.init()
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT a.id, a.account_id, a.root_job_id, a.source_root_job_id, a.email_snapshot, a.email "
            f"FROM {postgres.qualified('registration_attempts')} a "
            "WHERE a.account_id = ANY(%s) OR EXISTS ("
            f"SELECT 1 FROM {postgres.qualified(records.JOBS.name)} j "
            "WHERE j.attempt_id=a.id AND j.account_id = ANY(%s)) ORDER BY a.id DESC",
            (account_ids, account_ids),
        )
        attempts = list(cur.fetchall())
    roots = sorted({root for row in attempts for value in (row.get("root_job_id"), row.get("source_root_job_id"))
                    if (root := _id(value)) is not None})
    attempt_ids = [int(row["id"]) for row in attempts]
    emails = sorted({_email(row.get("email")) for row in accounts if _email(row.get("email"))})
    jobs = records.list_rows(
        records.JOBS,
        where=("(COALESCE(NULLIF(job_type, ''), 'registration') = ANY(%s) AND "
               "(attempt_id = ANY(%s) OR id = ANY(%s) OR root_job_id = ANY(%s) OR account_id = ANY(%s) "
               "OR (status = ANY(%s) AND LOWER(BTRIM(email)) = ANY(%s)))) "
               "OR (job_type = ANY(%s) AND root_job_id = ANY(%s))"),
        params=(list(_REGISTRATION_TYPES), attempt_ids, roots, roots, account_ids, list(_ACTIVE), emails,
                list(_POSTPROCESS_TYPES), roots),
        order_by="id DESC",
    )
    by_job = {int(row["id"]): row for row in jobs}
    linked = defaultdict(list)
    for attempt in attempts:
        owners = {_id(attempt.get("account_id"))}
        owners.update(_id(job.get("account_id")) for job in jobs if job.get("attempt_id") == attempt["id"])
        for owner in owners & by_account.keys():
            linked[owner].append(attempt)
    return by_account, linked, by_job


def project_accounts(accounts: list[Mapping]) -> dict[int, dict]:
    """批量返回白名单能力投影；调用者决定读取失败时如何展示。"""
    ids = list(dict.fromkeys(ident for row in accounts if (ident := _id(row.get("id"))) is not None))
    if not ids:
        return {}
    actual, attempts_by_account, jobs = _sources(ids)
    projections = {ident: unavailable("账号不存在" if ident not in actual else
                                     "未找到可核验的原注册任务，请在任务记录中查看") for ident in ids}
    selected = {}
    for ident, account in actual.items():
        if db.account_is_deactivated(account):
            projections[ident] = unavailable("账号已废号，不能重跑注册")
            continue
        address = _email(account.get("email"))
        attempts = attempts_by_account.get(ident) or []
        linked_attempt_ids = {int(attempt["id"]) for attempt in attempts}
        linked_roots = {_id(attempt.get(key)) for attempt in attempts
                        for key in ("root_job_id", "source_root_job_id") if _id(attempt.get(key)) is not None}
        active = next((job for job in jobs.values() if job.get("status") in _ACTIVE and (
            ((job.get("job_type") or "registration") in _REGISTRATION_TYPES and (
                job.get("account_id") == ident or job.get("attempt_id") in linked_attempt_ids
                or address and _email(job.get("email")) == address
            )) or (
                job.get("job_type") in _POSTPROCESS_TYPES and job.get("root_job_id") in linked_roots
                and job.get("attempt_id") in linked_attempt_ids and job.get("account_id") in (None, ident)
                and _email(job.get("email")) in ("", address)
            )
        )), None)
        if active:
            projections[ident].update(source_job_id=int(active["id"]), action=active.get("job_type") or "registration",
                                      label="注册进行中", reason="该账号已有注册任务正在执行", active=True)
            continue
        if len(attempts) > 1:
            projections[ident] = unavailable("关联多个注册 Attempt，请在任务记录中选择原任务")
            continue
        if not attempts:
            continue
        attempt = attempts[0]
        roots = {_id(attempt.get(key)) for key in ("root_job_id", "source_root_job_id") if attempt.get(key) is not None}
        if (not address or _email(attempt.get("email_snapshot")) != address
                or attempt.get("email") and _email(attempt["email"]) != address
                or attempt.get("account_id") not in (None, ident) or len(roots) != 1 or None in roots):
            projections[ident] = unavailable("原注册 Attempt 与当前账号身份不一致")
            continue
        root_id = next(iter(roots))
        root = jobs.get(root_id)
        chain = [job for job in jobs.values() if int(job.get("root_job_id") or job["id"]) == root_id
                 and (job.get("job_type") or "registration") in _REGISTRATION_TYPES]
        source = chain[0] if chain else None
        if (not root or not source or (root.get("job_type") or "registration") not in _REGISTRATION_TYPES or any(
            job.get("attempt_id") != attempt["id"] or job.get("account_id") not in (None, ident)
            or _email(job.get("email")) not in ("", address) for job in (root, source)
        )):
            projections[ident] = unavailable("原注册任务链缺失或身份不一致，请在任务记录中查看")
            continue
        selected[ident] = source
    infos = registration_service.get_retry_info_bulk(list({int(row["id"]): row for row in selected.values()}.values()))
    for ident, job in selected.items():
        info = infos.get(int(job["id"])) or {}
        projections[ident].update(
            available=bool(info.get("retryable")), source_job_id=int(job["id"]),
            action=info.get("retry_action"), label=info.get("retry_label") or "重跑注册",
            reason=info.get("retry_reason") or ("" if info.get("retryable") else "原注册任务当前不可重跑"),
        )
    return projections


def attach_projection(accounts: list[dict]) -> None:
    try:
        projections = project_accounts(accounts)
    except Exception:
        logger.exception("读取账号原注册重跑能力失败")
        projections = {}
    for account in accounts:
        account["registration_retry"] = projections.get(_id(account.get("id"))) or unavailable("原注册任务状态暂不可用，请刷新后重试")


def _result_item(account_id: int, source: dict, result: Mapping) -> dict:
    job = result.get("job")
    item = {
        "account_id": account_id,
        "job_id": _id(job.get("id")) if isinstance(job, Mapping) else _id(result.get("job_id")),
        "source_job_id": source["source_job_id"],
        "retry_action": result.get("retry_action") or source.get("action"),
        "message": str(result.get("message") or (result.get("error") if result.get("busy") else None)
                       or "原注册任务已入队"),
    }
    item["job_id"] = item["job_id"] or source["source_job_id"]
    for field in ("task_id", "operation_task_id", "run_id"):
        value = _id(result.get(field))
        if value is not None:
            item[field] = value
    return item


def retry_accounts(account_ids: list[int]) -> dict:
    """每次点击重新核验来源，再交原重跑入口复验并派发。"""
    ids = validate_account_ids(account_ids)
    try:
        projections = project_accounts([{"id": ident} for ident in ids])
    except Exception:
        logger.exception("读取原注册任务来源失败，未派发注册重跑")
        projections = {ident: unavailable("原注册任务状态暂不可用，请刷新后重试") for ident in ids}
    started, reused, skipped = [], [], []
    for ident in ids:
        source = projections[ident]
        if source["active"]:
            reused.append(_result_item(ident, source, {"message": source["reason"]}))
            continue
        if not source["available"]:
            skipped.append({"account_id": ident, "reason": source["reason"]})
            continue
        try:
            result = registration_service.retry_job(source["source_job_id"])
        except Exception:
            logger.exception("账号原注册重跑入队失败：account_id=%s", ident)
            skipped.append({"account_id": ident, "reason": "原注册任务入队失败，请刷新任务状态后重试"})
            continue
        if result.get("reused") or result.get("busy"):
            reused.append(_result_item(ident, source, result))
        elif result.get("ok"):
            started.append(_result_item(ident, source, result))
        else:
            skipped.append({"account_id": ident, "reason": result.get("error") or "原注册任务当前不可重跑"})
    return {"ok": True, "started_count": len(started), "started": started,
            "reused_count": len(reused), "reused": reused, "skipped_count": len(skipped), "skipped": skipped}


__all__ = ["attach_projection", "project_accounts", "retry_accounts", "unavailable", "validate_account_ids"]
