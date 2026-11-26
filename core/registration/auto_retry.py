# -*- coding: utf-8 -*-
"""注册失败任务的自动重试扫描。

只做“失败后按配置再试”，不改变单项重试的业务判定：
* 是否可重试由 ``registration.service.get_retry_info`` 决定；
* 身份验证等不可重试的失败会被标记为停止，避免每分钟重复尝试；
* 每个源任务记录 ``auto_retry_count``，达到上限后不再触发。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("core.registration_auto_retry")

_DEFAULT_MAX_ATTEMPTS = 2
_DEFAULT_DELAY_SECONDS = 180
_SCAN_LIMIT = 300
_ACTION_LIMIT = 10


def _settings() -> tuple[bool, int, int]:
    try:
        from config import register as register_cfg

        enabled = bool(getattr(register_cfg, "REGISTRATION_AUTO_RETRY_ENABLED", False))
        attempts = max(0, int(getattr(register_cfg, "REGISTRATION_AUTO_RETRY_MAX_ATTEMPTS", _DEFAULT_MAX_ATTEMPTS) or 0))
        delay = max(0, int(getattr(register_cfg, "REGISTRATION_AUTO_RETRY_DELAY_SECONDS", _DEFAULT_DELAY_SECONDS) or 0))
    except Exception:
        enabled, attempts, delay = False, _DEFAULT_MAX_ATTEMPTS, _DEFAULT_DELAY_SECONDS
    return enabled, attempts, delay


def _job_data(job: dict) -> dict:
    data = job.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        import json

        try:
            value = json.loads(data)
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}
    return {}


def _completed_at(job: dict) -> datetime | None:
    data = _job_data(job)
    raw = str(data.get("completed_at") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _candidates(now: datetime, delay_seconds: int, max_attempts: int) -> list[dict]:
    from psycopg.rows import dict_row

    from core.storage import postgres as postgres_store

    cutoff = now - timedelta(hours=24)
    ready_before = now - timedelta(seconds=delay_seconds)
    table = postgres_store.qualified("registration_jobs")
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT j.id, j.email, j.status, j.job_type, j.data,
                       COALESCE(j.job_retry_attempt, 0) AS retry_attempt
                FROM {table} j
                WHERE j.status = 'failed'
                  AND j.job_type IN ('registration', 'registration_resume')
                  AND NOT EXISTS (
                      SELECT 1 FROM {table} child WHERE child.parent_job_id = j.id
                  )
                  AND COALESCE(j.job_retry_attempt, 0) < %s
                ORDER BY j.id DESC
                LIMIT %s""",
            (int(max_attempts), _SCAN_LIMIT),
        )
        rows = cur.fetchall()
    selected: list[dict] = []
    for job in rows:
        completed = _completed_at(job)
        if completed is None or completed < cutoff or completed > ready_before:
            continue
        data = _job_data(job)
        if data.get("auto_retry_disabled") is True:
            continue
        selected.append(dict(job))
        if len(selected) >= _ACTION_LIMIT:
            break
    return selected


def run_once(*, now: datetime | None = None) -> dict:
    """执行一次扫描；返回本轮统计，异常由调用方记录。"""
    enabled, max_attempts, delay_seconds = _settings()
    if not enabled or max_attempts <= 0:
        return {"enabled": False, "started": 0, "stopped": 0}
    now = now or datetime.now(timezone.utc)
    from core.registration import service
    from core.storage import db_legacy as db

    started = 0
    stopped = 0
    for job in _candidates(now, delay_seconds, max_attempts):
        job_id = int(job.get("id") or 0)
        if not job_id:
            continue
        data = _job_data(job)
        count = int(data.get("auto_retry_count") or 0) + 1
        try:
            result = service.retry_job(job_id)
        except Exception as exc:  # noqa: BLE001 - 单个任务失败不能中断扫描
            logger.warning("[自动重试] job=%s 触发失败：%s", job_id, f"{type(exc).__name__}: {exc}")
            db._patch_job(job_id, {
                "auto_retry_count": count,
                "auto_retry_last_error": f"{type(exc).__name__}: {exc}"[:300],
            })
            continue
        ok = bool(isinstance(result, dict) and result.get("ok"))
        patch = {"auto_retry_count": count, "auto_retry_at": now.isoformat(timespec="seconds")}
        if ok:
            started += 1
            patch["auto_retry_last_result"] = "started"
        else:
            reason = str((result or {}).get("error") or "")[:300]
            patch["auto_retry_last_result"] = reason or "rejected"
            if count >= max_attempts or result is None:
                patch["auto_retry_disabled"] = True
                stopped += 1
        try:
            db._patch_job(job_id, patch)
        except Exception:
            logger.warning("[自动重试] job=%s 统计写入失败", job_id)
    if started or stopped:
        logger.info("[自动重试] 本轮启动=%s 停止=%s", started, stopped)
    return {"enabled": True, "started": started, "stopped": stopped}
