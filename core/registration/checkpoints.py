"""注册过程中可恢复检查点的共享持久化入口。"""
from __future__ import annotations

from core import db
from core.email.provider import resolve_email_source


class RegistrationCheckpointConflict(RuntimeError):
    """远端账号已完成认证，拒绝降级覆盖为待验证状态。"""


def save_protocol_password_checkpoint(*, email: str, password: str, state: str,
                                      proxy: str | None = None, email_source: str | None = None) -> dict:
    """保存原 Attempt 的私有密码；缺少持久化任务上下文时拒绝发送新密码。"""
    from core.registration.service import registration_fact_context
    from core.storage import registration

    context = registration_fact_context()
    if context.get("attempt_id") is None:
        raise RuntimeError("新密码提交缺少可持久化的原 Attempt，已停止")
    return registration.save_password_checkpoint(
        int(context["attempt_id"]), email=email, password=password, state=state,
        run_id=context.get("run_id"), execution_id=context.get("execution_id"), job_id=context.get("job_id"),
        account={"proxy_used": proxy, "email_source": email_source or resolve_email_source(email)}
        if state == "confirmed" else None,
    )


def save_email_verification_checkpoint(
    *,
    email: str,
    password: str,
    proxy: str | None,
    email_source: str | None = None,
    profile_metadata: dict | None = None,
) -> int:
    """保存密码提交后的邮箱验证中间态，并对已完成账号 fail-closed。"""
    normalized_email = str(email or "").strip()
    normalized_password = str(password or "").strip()
    if not normalized_email:
        raise ValueError("待验证账号邮箱不能为空")
    if not normalized_password:
        raise ValueError("待验证账号密码不能为空")

    existing = db.get_account_by_email(normalized_email)
    if existing:
        if str(existing.get("access_token") or "").strip():
            raise RegistrationCheckpointConflict(
                "同邮箱账号已有 access token，拒绝覆盖为待邮箱验证状态"
            )
        updated = db.update_account_email_verification_checkpoint(
            normalized_email,
            normalized_password,
            profile_metadata=dict(profile_metadata or {}) or None,
        )
        if not updated:
            raise RuntimeError("待邮箱验证 checkpoint 更新失败，拒绝继续注册")
        return int(existing["id"])

    extra = {
        "account_password": normalized_password,
        "registration_checkpoint": "email_verification_pending",
        "registration_pending_reason": "email_otp_pending",
    }
    if profile_metadata:
        extra["roxybrowser"] = dict(profile_metadata)
    return db.insert_account(
        email=normalized_email,
        access_token="",
        proxy_used=proxy or None,
        email_source=email_source or resolve_email_source(normalized_email),
        extra=extra,
    )


def save_protocol_totp_checkpoint(*, email: str, secret: str, confirmed: bool) -> None:
    """将注册 2FA 的待确认和已启用状态分别持久化。"""
    from core.registration.service import registration_fact_context
    from core.storage import registration

    context = registration_fact_context()
    if context.get("attempt_id") is not None:
        registration.save_totp_checkpoint(int(context["attempt_id"]), email=email, secret=secret,
                                         confirmed=confirmed, run_id=context.get("run_id"),
                                         execution_id=context.get("execution_id"))
    elif confirmed:
        if not db.update_account_totp_secret(email, secret, setup_pending=False):
            raise RuntimeError("已启用 2FA 密钥保存失败")
    else:
        if not db.stage_account_totp_secret(email, secret):
            raise RuntimeError("待确认 2FA 密钥保存失败，拒绝激活")
