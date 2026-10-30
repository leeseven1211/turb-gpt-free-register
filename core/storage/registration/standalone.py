"""为无 WebUI 的 Protocol/Roxy CLI 入口保留稳定的注册意图。"""
from __future__ import annotations

import uuid
import errno
import os
import socket

from core.storage import records as record_store
from core.storage import registration


def _local_pid_exited(pid) -> bool:
    """仅 ESRCH 能证明本机旧进程已退出；权限不足或 PID 缺失不抢占。"""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.ESRCH
    return False


def _recover_exited_cli_run(cur, raw_attempt, *, entrypoint: str = "protocol_cli") -> None:
    """持有原 Attempt 锁，只收口具有本机归属且 PID 已退出的 CLI Run。"""
    cur.execute(
        f"SELECT * FROM {registration._table('registration_runs')} "
        "WHERE attempt_id=%s AND status='running' FOR UPDATE",
        (int(raw_attempt["id"]),),
    )
    for run in cur.fetchall():
        data = dict(registration._decode(run.get("data")) or {})
        if (run.get("job_id") is not None or data.get("entrypoint") != entrypoint
                or data.get("worker_host") != socket.gethostname()
                or not _local_pid_exited(run.get("worker_pid"))):
            continue
        private = dict(registration._decode(raw_attempt.get("private_context")) or {})
        unknown = private.get("password_state") in {"started", "confirmed"} or raw_attempt.get("remote_account_state") in {"request_unknown", "confirmed"}
        core_saved = raw_attempt.get("account_id") and raw_attempt.get("local_account_state") == "persisted"
        status = "partial_success" if core_saved else "request_unknown" if unknown else "interrupted"
        completed = registration._now()
        cur.execute(
            f"UPDATE {registration._table('registration_runs')} "
            "SET status=%s, completed_at=%s, heartbeat_at=NULL, "
            "result_summary=COALESCE(result_summary,'{}'::jsonb) || %s::jsonb, "
            "error_code='cli_worker_exited', error_message='本机旧 CLI 进程已退出，保留原意图继续执行' "
            "WHERE id=%s AND status='running'",
            (status, completed, registration._json({"entrypoint": entrypoint, "registration_success": bool(core_saved),
                "postprocess_success": False, "core_persisted": bool(core_saved), "worker_recovered": True}), int(run["id"])),
        )
        cur.execute(
            f"UPDATE {registration._table('registration_attempts')} "
            "SET active_execution_id=CASE WHEN active_execution_id=%s THEN NULL ELSE active_execution_id END, "
            "remote_account_state=CASE WHEN %s AND remote_account_state<>'confirmed' THEN 'request_unknown' ELSE remote_account_state END, "
            "target_status=CASE WHEN %s THEN 'request_unknown' ELSE target_status END, "
            "updated_at=%s WHERE id=%s",
            (run.get("execution_id"), unknown and not core_saved, unknown and not core_saved, completed, int(raw_attempt["id"])),
        )
        registration._insert_event(
            cur, attempt_id=int(raw_attempt["id"]), run_id=int(run["id"]), job_id=None,
            checkpoint=raw_attempt.get("checkpoint") or "created", event_type="cli_run_interrupted",
            level="WARNING", message="本机旧 CLI 进程已退出，保留原凭据等待同一意图恢复",
            detail={"run_id": int(run["id"]), "status": status}, execution_id=run.get("execution_id"),
            event_uuid=None,
        )


def prepare_attempt(
    email: str,
    *,
    email_source: str | None = None,
    entrypoint: str = "protocol_cli",
    driver: str = "protocol",
) -> dict:
    """同邮箱 CLI 重跑复用原意图，已有其他任务链时停止而不猜测归属。"""
    address = str(email or "").strip()
    if not address:
        raise ValueError("CLI 注册缺少邮箱")
    source = str(entrypoint or "protocol_cli").strip() or "protocol_cli"
    driver_name = str(driver or "protocol").strip() or "protocol"
    identifier_namespace = "protocol-cli" if source == "protocol_cli" else source
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"turb:{identifier_namespace}:" + address.casefold()))
    registration.init()
    blocked_reason = None
    with registration._connect() as conn, conn.cursor() as cur:
        record_store.advisory_xact_lock(conn, "protocol-cli:" + address.casefold())
        cur.execute(
            f"SELECT * FROM {registration._table('registration_attempts')} "
            "WHERE lower(email_snapshot)=lower(%s) ORDER BY id DESC FOR UPDATE",
            (address,),
        )
        candidates = cur.fetchall()
        if any(row["attempt_uuid"] != identifier for row in candidates):
            raise RuntimeError("此邮箱已有注册任务链，请从原任务继续执行")
        if candidates:
            existing = candidates[0]
            existing_source = str(existing.get("email_source") or "").strip().lower()
            requested_source = str(email_source or "").strip().lower()
            if existing_source and requested_source and existing_source != requested_source:
                raise RuntimeError("原注册 Attempt 的邮箱来源不一致，拒绝切换来源")
            existing_driver = str(existing.get("driver") or "").strip().lower()
            requested_driver = driver_name.lower()
            if existing_driver and requested_driver and existing_driver != requested_driver:
                raise RuntimeError("原注册 Attempt 的驱动不一致，拒绝切换驱动")
            _recover_exited_cli_run(cur, candidates[0], entrypoint=source)
            attempt = registration._row(candidates[0])
            if attempt.get("account_id") and attempt.get("local_account_state") == "persisted":
                blocked_reason = "此邮箱的核心账号已保存，请使用账号后处理入口"
            elif attempt.get("target_status") in {"deactivated", "completed"}:
                blocked_reason = "此邮箱注册意图已结束，拒绝重复注册"
            else:
                return attempt
        else:
            cur.execute(
                f"SELECT id FROM {registration._table(record_store.ACCOUNTS.name)} "
                "WHERE lower(email)=lower(%s) LIMIT 1",
                (address,),
            )
            if cur.fetchone():
                raise RuntimeError("此邮箱已有账号记录，请使用原账号恢复入口")
            cur.execute(
                f"INSERT INTO {registration._table('registration_attempts')} "
                "(attempt_uuid,email_snapshot,email,email_source,driver,data) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb) RETURNING *",
                (identifier, address, address, email_source, driver_name,
                 registration._json({"entrypoint": source, "driver": driver_name})),
            )
            return registration._row(cur.fetchone())
    # 恢复收口先提交，再拒绝重复注册；在事务内抛错会回滚旧 Run 的收口。
    raise RuntimeError(blocked_reason)
