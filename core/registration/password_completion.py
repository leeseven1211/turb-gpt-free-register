"""注册续跑的密码缺项自动衔接，沿用独立账号操作的执行契约。"""
from __future__ import annotations

import logging

from core import db
from core.accounts.password_evidence import password_is_confirmed
from core.operations import task_gateway
from core.storage import registration
from core.storage.operations import registration_completion

logger = logging.getLogger(__name__)


def _remaining_error(result: dict) -> str:
    """仅移除密码缺项，保留其他后处理失败及未知警告。"""
    password_messages = {
        "原密码尚未确认生效",
        "账号已取得 Token；恢复候选尚未确认有效，需要补全密码",
    }
    remaining = []
    for part in str(result.get("error") or "").split("; "):
        text = part.strip()
        if not text or text in password_messages:
            continue
        if text.startswith(("registration_password_unconfirmed:", "registration_password_create_rejected:",
                            "密码创建请求被拒绝：HTTP ")):
            continue
        remaining.append(text)
    return "; ".join(remaining)


def after_registration(result, *, run_id: int, options: dict | None = None):
    """主体成功后提交一次持久补密码任务；调度失败仍保留账号成功事实。"""
    if (not isinstance(result, dict) or not result.get("core_persisted")
            or not result.get("registration_success") or result.get("registration_pending")
            or not (options or {}).get("password_enabled", True)):
        return result
    try:
        run = registration.get_run(int(run_id)) or {}
        if run.get("action_type") != "registration_resume":
            return result
        account = db.get_account(int(result.get("account_id") or 0)) or {}
        if (not account.get("access_token") or password_is_confirmed(account)
                or db.account_is_deactivated(account)):
            return result
        attempt = registration.get_attempt(int(run["attempt_id"])) or {}
        expected_email = str(attempt.get("email_snapshot") or "").strip().casefold()
        if not expected_email or str(account.get("email") or "").strip().casefold() != expected_email:
            return result
        from config.account import completion_settings

        settings = completion_settings()
        queued = registration_completion.enqueue(
            registration_run_id=int(run_id), account=account, settings=settings,
            remaining_error=_remaining_error(result),
        )
        task_gateway.notify_dispatch()
        return {**result, "completion_handoff": queued}
    except Exception as exc:
        logger.exception("注册续跑自动补密码入队失败：registration_run_id=%s", run_id)
        error = "registration_completion_dispatch_failed: 自动补密码未入队"
        return {
            **result, "postprocess_success": False, "partial_success": True,
            "cause_code": "registration_completion_dispatch_failed",
            "error_code": "registration_completion_dispatch_failed",
            "error": "; ".join(item for item in (result.get("error"), error) if item),
            "completion_handoff": {"accepted": False, "error_type": type(exc).__name__},
        }
