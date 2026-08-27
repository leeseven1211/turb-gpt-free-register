# -*- coding: utf-8 -*-
"""WebUI request context and explicit process lifecycle."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from flask import Flask

from core import (
    account_task_store,
    codex_operation_service,
    codex_retry_service,
    codex_token_refresh_service,
    db,
    deactivation_mail_service,
    live_check_service,
    operation_task_store,
    plan_check_service,
    sms_provider,
)

logger = logging.getLogger(__name__)


def _run_codex_retry_worker(
    email: str,
    *,
    batch_label: str | None = None,
    clear_log: bool = True,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> None:
    """Execute one Codex retry; callers must reserve the account first."""
    codex_retry_service.run_worker(
        email,
        batch_label=batch_label,
        clear_log=clear_log,
        task_id=task_id,
        task_trigger=task_trigger,
    )


def _run_account_setup_worker(email: str, *, task_id: int, task_trigger: str) -> None:
    """Execute account configuration repair without starting Codex OAuth."""
    codex_retry_service.run_twofa_worker(
        email,
        task_id=task_id,
        task_trigger=task_trigger,
    )


@dataclass
class WebUIContext:
    """Explicit dependencies shared by route groups."""

    app: Flask
    logger: logging.Logger
    prepared_downloads: dict[str, dict[str, Any]] = field(default_factory=dict)

    def put_prepared_download(
        self,
        content: bytes,
        filename: str,
        mimetype: str = "application/zip",
    ) -> str:
        now = time.time()
        # Prune short-lived downloads before adding the next one.
        for key, value in list(self.prepared_downloads.items()):
            if now - float(value.get("created_at") or 0) > 600:
                self.prepared_downloads.pop(key, None)
        download_id = uuid.uuid4().hex
        self.prepared_downloads[download_id] = {
            "content": bytes(content),
            "filename": filename,
            "mimetype": mimetype,
            "created_at": now,
        }
        return download_id

    def enqueue_codex_retry(self, email: str, *, trigger: str = "manual") -> dict:
        """Compatibility name for the unified Codex operation coordinator."""
        return codex_operation_service.submit(email, trigger=trigger)

    def enqueue_account_setup(
        self,
        account_id: int,
        *,
        trigger: str = "manual_account_setup",
    ) -> dict:
        """Queue account password, plan and authenticator repair."""
        try:
            account = db.get_account(int(account_id))
        except (TypeError, ValueError):
            account = None
        if account is None:
            return {"accepted": False, "error": "账号不存在"}
        email = str(account.get("email") or "").strip()
        if not email:
            return {"accepted": False, "error": "账号邮箱为空"}
        if str(account.get("account_status") or "").lower() == "deactivated":
            return {"accepted": False, "error": "账号已废号，不能补齐配置"}
        if not codex_retry_service.reserve(email):
            return {"accepted": False, "busy": True, "error": "该账号正在执行账号操作，请稍候"}

        try:
            task_id = account_task_store.create_task(
                task_type="account_setup_retry",
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(trigger or "manual_account_setup"),
            )
        except Exception as exc:
            codex_retry_service.release(email)
            self.logger.exception("创建账号配置补跑任务实例失败：email=%s", email)
            return {"accepted": False, "error": f"任务实例创建失败：{type(exc).__name__}: {exc}"}

        worker = threading.Thread(
            target=_run_account_setup_worker,
            kwargs={
                "email": email,
                "task_id": task_id,
                "task_trigger": str(trigger or "manual_account_setup"),
            },
            name=f"account-setup-{email}",
            daemon=True,
        )
        try:
            worker.start()
        except Exception as exc:
            codex_retry_service.release(email)
            error = f"账号配置补跑启动失败：{type(exc).__name__}: {exc}"
            account_task_store.finish_task(
                task_id,
                status="failed",
                message="账号配置补跑启动失败",
                error=error,
            )
            return {"accepted": False, "task_id": task_id, "error": error}
        return {
            "accepted": True,
            "busy": False,
            "task_id": task_id,
            "account_id": int(account.get("id") or 0) or None,
            "email": email,
            "status": "queued",
            "trigger": str(trigger or "manual_account_setup"),
        }

    def retry_account_task_result(self, task_id: int) -> tuple[dict, int]:
        """Resolve a historical account task to its current retry service."""
        task = account_task_store.get_task(task_id)
        if not task:
            return {"ok": False, "error": "任务实例不存在"}, 404
        if task.get("status") in {"queued", "running"}:
            return {"ok": False, "error": "任务仍在执行"}, 409
        account = db.get_account(int(task.get("account_id") or 0))
        if not account:
            return {"ok": False, "error": "关联账号不存在"}, 404
        task_type = str(task.get("task_type") or "")
        if task_type in {"live_check", "token_refresh"}:
            queued = live_check_service.enqueue_account_live_check(
                account_id=int(account["id"]),
                email=str(account.get("email") or ""),
                trigger="token_refresh_manual_retry" if task_type == "token_refresh" else "manual_retry",
                proxy=None,
                force_refresh=task_type == "token_refresh",
            )
        elif task_type == "plan_check":
            queued = plan_check_service.enqueue_account_plan_check(
                account_id=int(account["id"]),
                email=str(account.get("email") or ""),
                access_token=str(account.get("access_token") or ""),
                trigger="manual_retry",
                proxy=None,
            )
        elif task_type == "deactivation_mail":
            queued = deactivation_mail_service.enqueue(int(account["id"]), trigger="manual_retry")
        elif task_type == "codex_retry":
            queued = self.enqueue_codex_retry(
                email=str(account.get("email") or ""),
                trigger="manual_retry",
            )
        elif task_type == "account_setup_retry":
            queued = self.enqueue_account_setup(
                int(account["id"]),
                trigger="manual_retry",
            )
        elif task_type == "codex_token_refresh":
            filename = str((task.get("result_summary") or {}).get("filename") or "")
            queued = codex_token_refresh_service.enqueue_refresh(filename, trigger="manual_retry")
        else:
            return {"ok": False, "error": "该任务类型暂不支持重跑"}, 400
        if queued.get("busy"):
            return {"ok": False, **queued}, 409
        if not queued.get("accepted"):
            return {"ok": False, **queued}, 400
        return {"ok": True, **queued}, 202


_runtime_lock = threading.Lock()
_runtime_started = False


def start_runtime(runtime_logger: logging.Logger | None = None) -> bool:
    """Start WebUI recovery and periodic workers once per process."""
    global _runtime_started
    active_logger = runtime_logger or logger
    with _runtime_lock:
        if _runtime_started:
            return False

        recovered_jobs = db.recover_interrupted_registration_jobs()
        if recovered_jobs:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的注册/Codex 任务", recovered_jobs)
        recovered_account_tasks = account_task_store.recover_interrupted()
        if recovered_account_tasks:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的账号任务实例", recovered_account_tasks)
        operation_task_store.init()
        recovered_operation_runs = operation_task_store.recover_interrupted_runtime_runs()
        if recovered_operation_runs:
            active_logger.warning("已收口 %s 个因 WebUI 重启中断的原生账号操作", recovered_operation_runs)
        operation_task_store.start_projection_worker()
        try:
            from core.roxybrowser_client import cleanup_orphaned_profiles

            orphan_result = cleanup_orphaned_profiles()
            if orphan_result.get("found"):
                active_logger.warning(
                    "Roxy 孤儿环境恢复完成：found=%s cleaned=%s failed=%s",
                    orphan_result.get("found"),
                    orphan_result.get("cleaned"),
                    orphan_result.get("failed"),
                )
        except Exception:
            active_logger.exception("Roxy 孤儿环境启动恢复失败；登记会保留到下次启动继续重试")

        try:
            from core.registration_debug import cleanup_expired_artifacts

            debug_cleanup = cleanup_expired_artifacts()
            if debug_cleanup.get("removed_files") or debug_cleanup.get("removed_dirs"):
                active_logger.info(
                    "注册调试产物过期清理完成：files=%s dirs=%s",
                    debug_cleanup.get("removed_files", 0),
                    debug_cleanup.get("removed_dirs", 0),
                )
        except Exception:
            active_logger.exception("注册调试产物过期清理失败；不影响 WebUI 启动")

        sms_provider.start_cancel_worker()
        recovered_plan_checks = db.recover_interrupted_plan_checks()
        if recovered_plan_checks:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的套餐查询状态", recovered_plan_checks)
        recovered_extract_links = db.recover_interrupted_extract_links()
        if recovered_extract_links:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的提链状态", recovered_extract_links)
        recovered_live_checks = db.recover_interrupted_live_checks()
        if recovered_live_checks:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的查活状态", recovered_live_checks)
        backfilled_proxy_context = db.backfill_account_registration_proxy_context()
        if backfilled_proxy_context:
            active_logger.info("已为 %s 个历史账号补齐注册代理来源/国家", backfilled_proxy_context)

        resumed_codex_runs = codex_operation_service.resume_queued()
        if resumed_codex_runs:
            active_logger.info("已恢复调度 %s 个数据库队列中的 Codex attempt", resumed_codex_runs)
        from core.deactivation_mail_service import start_periodic_scanner
        from core.token_refresh_service import start_periodic_refresher
        from core.codex_token_refresh_service import start_periodic_refresher as start_codex_token_refresher

        start_periodic_scanner()
        start_periodic_refresher()
        start_codex_token_refresher()
        _runtime_started = True
        return True
