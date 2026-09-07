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
from core.account_operation_executor import executor as _ACCOUNT_EXECUTOR

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


def _run_account_setup_worker(
    email: str,
    *,
    task_id: int,
    task_trigger: str,
    steps: set[str] | tuple[str, ...] | list[str] | None = None,
) -> None:
    """Execute selected account configuration repair without starting Codex OAuth."""
    codex_retry_service.run_twofa_worker(
        email,
        task_id=task_id,
        task_trigger=task_trigger,
        steps=steps,
    )


def _run_account_completion_worker(
    email: str,
    *,
    account_id: int,
    task_id: int,
    task_trigger: str,
    planned_steps: list[str],
    settings: dict[str, object],
) -> None:
    """Execute a config-driven completion plan and record one coordinator task."""
    from core.account_completion_service import STEP_LABELS, completion_plan

    started = False
    result_summary: dict[str, Any] = {"planned_steps": list(planned_steps)}
    try:
        account_task_store.start_task(
            task_id,
            message=f"开始补全账号：{'、'.join(STEP_LABELS.get(step, step) for step in planned_steps)}",
        )
        started = True
        account_task_store.append_event(
            task_id,
            stage="plan",
            message="已按当前配置生成账号补全计划",
            detail={"steps": list(planned_steps)},
            state="success",
        )
        remaining = set(planned_steps)

        if "refresh_at" in remaining:
            account = db.get_account(int(account_id)) or {}
            # A queued completion task contains a plan snapshot, but the
            # destructive boundary is the actual refresh enqueue.  Recheck the
            # current switch and registration state immediately before it so a
            # config change cannot make an old task refresh a pending account.
            from config.account import completion_settings

            current_plan = completion_plan(account, completion_settings())
            if "refresh_at" not in current_plan["missing_steps"]:
                if current_plan.get("registration_resume"):
                    stale_message = "账号注册尚未完成，旧补全计划已取消，请重新点击补全账号继续注册"
                else:
                    stale_message = "补全时刷新 AT 已关闭，旧补全计划已失效，请重新点击补全账号"
                result_summary["stale_plan"] = True
                account_task_store.finish_task(
                    task_id,
                    status="cancelled",
                    message=stale_message,
                    result_summary=result_summary,
                    validation_method="account_completion_plan",
                )
                return
            queued = live_check_service.enqueue_account_live_check(
                account_id=int(account_id),
                email=str(account.get("email") or email),
                trigger=f"{task_trigger}_refresh_at",
                proxy=None,
                force_refresh=True,
            )
            result_summary["refresh_at"] = {
                "accepted": bool(queued.get("accepted")),
                "busy": bool(queued.get("busy")),
                "task_id": queued.get("task_id"),
                "message": queued.get("error") or "刷新 AT 已入队",
            }
            account_task_store.append_event(
                task_id,
                stage="refresh_token",
                message="补全计划中的刷新 AT 已作为独立操作入队",
                detail={"accepted": bool(queued.get("accepted")), "busy": bool(queued.get("busy"))},
                state="success" if queued.get("accepted") or queued.get("busy") else "failed",
            )
            remaining.discard("refresh_at")
            if not queued.get("accepted") and not queued.get("busy"):
                raise RuntimeError(queued.get("error") or "刷新 AT 入队失败")
            if remaining:
                result_summary["deferred_steps"] = [step for step in planned_steps if step in remaining]
                account_task_store.append_event(
                    task_id,
                    stage="plan",
                    message="等待刷新 AT 完成后再执行其余补全步骤，请在刷新完成后重新点击补全账号",
                    detail={"deferred_steps": result_summary["deferred_steps"]},
                    state="skipped",
                )
            result_summary["awaiting_steps"] = ["refresh_at"]
            account_task_store.finish_task(
                task_id,
                status="partial_success",
                message="刷新 AT 已提交，结果以独立子任务为准；成功后请重新点击补全账号",
                result_summary=result_summary,
                validation_method="account_completion_plan",
            )
            return

        setup_steps = remaining & {"password", "plan_check", "twofa"}
        if setup_steps:
            account_task_store.append_event(
                task_id,
                stage="account_setup",
                message=f"开始执行账号配置步骤：{'、'.join(STEP_LABELS[step] for step in planned_steps if step in setup_steps)}",
                detail={"steps": sorted(setup_steps)},
                state="running",
            )
            setup_result = codex_retry_service.run_twofa_worker(
                email,
                clear_log=False,
                task_id=task_id,
                task_trigger=task_trigger,
                steps=setup_steps,
                manage_task=False,
                twofa_driver_override=str(settings.get("twofa_driver") or "auto"),
                password_driver_override=str(settings.get("password_driver") or "roxy"),
                plan_driver_override=str(settings.get("plan_check_driver") or "protocol"),
            )
            result_summary["account_setup"] = {
                "ok": bool(setup_result.get("ok")),
                "status": setup_result.get("status"),
                "message": setup_result.get("message"),
                "plan_check": setup_result.get("plan_check"),
                "twofa_driver": setup_result.get("twofa_driver"),
                "auth_source": setup_result.get("auth_source"),
                "browser_opened": setup_result.get("browser_opened"),
                "account_status_persisted": setup_result.get("account_status_persisted"),
            }
            setup_status = str(setup_result.get("status") or "").lower()
            if setup_status == "deactivated":
                account_task_store.finish_task(
                    task_id,
                    status="deactivated",
                    message="账号已废号，已停止补全",
                    error=str(setup_result.get("message") or "account_deactivated"),
                    result_summary=result_summary,
                    validation_method="account_completion_plan",
                )
                return
            if setup_status == "unsupported":
                account_task_store.finish_task(
                    task_id,
                    status="unsupported",
                    message="账号配置包含当前不支持的步骤",
                    error=str(setup_result.get("message") or "账号配置步骤当前不支持"),
                    result_summary=result_summary,
                    validation_method="account_completion_plan",
                )
                return
            if not setup_result.get("ok"):
                raise RuntimeError(setup_result.get("message") or "账号配置步骤未完成")
            plan_outcome = setup_result.get("plan_check") or {}
            remaining -= setup_steps
            if "plan_check" in setup_steps and not bool(plan_outcome.get("ok")):
                # 套餐查询依赖独立的 AT/接口状态；它失败时不应把已经完成
                # 的密码或 2FA 重新标成整任务失败。保留待处理步骤，供后续
                # 单独重试套餐查询。
                result_summary["pending_steps"] = ["plan_check"]
                result_summary["plan_check_error"] = plan_outcome.get("message") or "套餐补全未完成"
                account_task_store.append_event(
                    task_id,
                    stage="plan_check",
                    message="密码/2FA 已完成，套餐查询待后续单独重试",
                    level="WARNING",
                    detail={"error": result_summary["plan_check_error"]},
                    state="skipped",
                )

        if "codex" in remaining:
            account_task_store.append_event(
                task_id,
                stage="codex",
                message="开始提交 Codex OAuth 独立操作",
                state="running",
            )
            queued = codex_operation_service.submit(
                email,
                trigger=f"{task_trigger}_codex",
                driver=str(settings.get("codex_driver") or "same_as_registration"),
            )
            result_summary["codex"] = {
                "accepted": bool(queued.get("accepted")),
                "busy": bool(queued.get("busy")),
                "task_id": queued.get("task_id"),
                "run_id": queued.get("run_id"),
                "message": queued.get("error") or "Codex OAuth 已入队",
            }
            account_task_store.append_event(
                task_id,
                stage="codex",
                message="Codex OAuth 已作为独立操作入队" if queued.get("accepted") or queued.get("busy") else "Codex OAuth 入队失败",
                detail={"accepted": bool(queued.get("accepted")), "busy": bool(queued.get("busy"))},
                state="success" if queued.get("accepted") or queued.get("busy") else "failed",
            )
            if not queued.get("accepted") and not queued.get("busy"):
                raise RuntimeError(queued.get("error") or "Codex OAuth 入队失败")
            remaining.discard("codex")

        pending_steps = set(result_summary.get("pending_steps") or [])
        result_summary["completed_steps"] = [
            step for step in planned_steps
            if step not in remaining and step not in pending_steps
        ]
        task_status = "partial_success" if result_summary.get("pending_steps") else "success"
        account_task_store.finish_task(
            task_id,
            status=task_status,
            message=(
                "密码/2FA 已完成，套餐查询待后续单独重试"
                if task_status == "partial_success"
                else "补全计划已提交，独立操作将在任务中心继续执行"
            ),
            result_summary=result_summary,
            validation_method="account_completion_plan",
        )
    except Exception as exc:
        result_summary["error"] = f"{type(exc).__name__}: {str(exc)[:220]}"
        account_task_store.finish_task(
            task_id,
            status="failed",
            message="账号补全计划执行失败",
            error=result_summary["error"],
            result_summary=result_summary,
            validation_method="account_completion_plan",
        )
        logger.exception("账号补全失败：email=%s", email)
    finally:
        # 统一释放父任务租约；账号配置子步骤在 manage_task=False 时会保留租约，
        # 直到这里完成 Codex 入队或整个补全计划结束。
        codex_retry_service.release(email)


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
        steps: set[str] | tuple[str, ...] | list[str] | None = None,
        task_type: str | None = None,
    ) -> dict:
        """Queue selected account configuration repair (legacy setup by default)."""
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

        requested_steps = {"password", "plan_check", "twofa"} if steps is None else {
            str(item or "").strip().lower() for item in steps
        }
        requested_steps &= {"password", "plan_check", "twofa"}
        if not requested_steps:
            codex_retry_service.release(email)
            return {"accepted": False, "error": "没有可执行的账号配置步骤"}
        if requested_steps == {"password"}:
            from core.account_completion_service import completion_plan
            from config.account import completion_settings

            password_plan = completion_plan(account, completion_settings())
            blocked = [
                item for item in password_plan.get("blocked") or []
                if item.get("step") == "password"
            ]
            if blocked:
                codex_retry_service.release(email)
                return {
                    "accepted": False,
                    "blocked": blocked,
                    "plan": password_plan,
                    "error": blocked[0].get("reason") or "账号密码补全当前不可用",
                }
        inferred_task_type = (
            "password_setup" if requested_steps == {"password"}
            else "twofa_setup" if requested_steps == {"twofa"}
            else "account_setup_retry"
        )
        try:
            task_id = account_task_store.create_task(
                task_type=str(task_type or inferred_task_type),
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(trigger or "manual_account_setup"),
            )
        except Exception as exc:
            codex_retry_service.release(email)
            self.logger.exception("创建账号配置补跑任务实例失败：email=%s", email)
            return {"accepted": False, "error": f"任务实例创建失败：{type(exc).__name__}: {exc}"}

        try:
            _ACCOUNT_EXECUTOR.submit(
                _run_account_setup_worker,
                email=email,
                task_id=task_id,
                task_trigger=str(trigger or "manual_account_setup"),
                steps=requested_steps,
            )
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
            "steps": sorted(requested_steps),
        }

    def enqueue_account_completion(
        self,
        account_id: int,
        *,
        trigger: str = "manual_account_completion",
    ) -> dict:
        """Generate and queue the configured missing-account completion plan."""
        from core.account_completion_service import completion_plan
        from config.account import completion_settings

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
            return {"accepted": False, "error": "账号已废号，不能补全账号"}
        # registered_accounts is created before registration is fully complete.
        # Enrich the account row with the durable Attempt state so a missing
        # Token cannot be mistaken for a refreshable, already-registered account.
        try:
            from core.storage import registration as registration_store

            attempt = registration_store.get_latest_attempt_by_account(int(account["id"]))
            if attempt:
                account = dict(account)
                account["registration_target_status"] = attempt.get("target_status")
                account["registration_remote_account_state"] = attempt.get("remote_account_state")
                account["registration_checkpoint"] = account.get("registration_checkpoint") or attempt.get("checkpoint")
        except Exception:
            logger.exception("读取账号注册 Attempt 状态失败：account_id=%s", account_id)
        settings = completion_settings()
        plan = completion_plan(account, settings)
        if "registration_resume" in plan["missing_steps"]:
            source_job = db.get_latest_registration_job_for_account(int(account["id"]))
            if not source_job:
                reason = "账号注册尚未完成，但找不到可继续的原注册任务；为避免误注册，请先从注册任务中心处理"
                return {
                    "accepted": False,
                    "blocked": [{"step": "registration_resume", "reason": reason}],
                    "plan": plan,
                    "error": reason,
                }
            try:
                from core import registration_service

                resumed = registration_service.retry_job(int(source_job["id"]))
            except Exception as exc:
                logger.exception("账号补全转注册续跑失败：account_id=%s", account_id)
                return {
                    "accepted": False,
                    "blocked": [{"step": "registration_resume", "reason": f"继续注册入队异常：{type(exc).__name__}"}],
                    "plan": plan,
                    "error": f"继续注册入队异常：{type(exc).__name__}: {exc}",
                }
            if not resumed.get("ok"):
                reason = str(resumed.get("error") or "继续注册任务未能入队")
                return {
                    "accepted": False,
                    "blocked": [{"step": "registration_resume", "reason": reason}],
                    "plan": plan,
                    "error": reason,
                }
            resume_job = resumed.get("job") or {}
            return {
                "accepted": True,
                "busy": False,
                "registration_resume": True,
                "status": "queued" if resumed.get("created") else "running",
                "job_id": resume_job.get("id"),
                "source_job_id": resumed.get("source_job_id") or int(source_job["id"]),
                "plan": plan,
                "message": resumed.get("message") or "已继续原注册任务，不执行 AT 刷新",
            }
        # 一个步骤被账号能力明确阻塞时，仍允许执行其它未完成步骤。
        # 例如密码资格为 false，但 Authenticator 2FA 仍然可以补齐。
        if plan["blocked"] and not plan["missing_steps"]:
            return {"accepted": False, "blocked": plan["blocked"], "plan": plan, "error": plan["blocked"][0]["reason"]}
        if not plan["missing_steps"]:
            return {"accepted": False, "ready": True, "plan": plan, "message": "账号已满足当前补全配置"}
        if not codex_retry_service.reserve(email):
            return {"accepted": False, "busy": True, "error": "该账号正在执行账号操作，请稍候"}
        try:
            task_id = account_task_store.create_task(
                task_type="account_completion",
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(trigger or "manual_account_completion"),
            )
        except Exception as exc:
            codex_retry_service.release(email)
            return {"accepted": False, "error": f"任务实例创建失败：{type(exc).__name__}: {exc}"}
        try:
            _ACCOUNT_EXECUTOR.submit(
                _run_account_completion_worker,
                email=email,
                account_id=int(account["id"]),
                task_id=task_id,
                task_trigger=str(trigger or "manual_account_completion"),
                planned_steps=list(plan["missing_steps"]),
                settings=settings,
            )
        except Exception as exc:
            codex_retry_service.release(email)
            error = f"账号补全启动失败：{type(exc).__name__}: {exc}"
            account_task_store.finish_task(task_id, status="failed", message="账号补全启动失败", error=error)
            return {"accepted": False, "task_id": task_id, "error": error}
        return {
            "accepted": True,
            "busy": False,
            "task_id": task_id,
            "account_id": int(account["id"]),
            "email": email,
            "status": "queued",
            "trigger": str(trigger or "manual_account_completion"),
            "plan": plan,
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
        elif task_type in {"account_setup_retry", "password_setup", "twofa_setup"}:
            step_map = {
                "account_setup_retry": None,
                "password_setup": {"password"},
                "twofa_setup": {"twofa"},
            }
            queued = self.enqueue_account_setup(
                int(account["id"]),
                trigger="manual_retry",
                steps=step_map[task_type],
                task_type=task_type,
            )
        elif task_type == "account_completion":
            queued = self.enqueue_account_completion(
                int(account["id"]),
                trigger="manual_retry_completion",
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
        repaired_compatibility_projections = operation_task_store.repair_stale_compatibility_projections()
        if repaired_compatibility_projections:
            active_logger.warning(
                "已修复 %s 个底层已结束但统一任务仍显示活动的兼容投影",
                repaired_compatibility_projections,
            )
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
        from core.account_auth_context_service import start_periodic_cleanup

        start_periodic_cleanup()
        _runtime_started = True
        return True
