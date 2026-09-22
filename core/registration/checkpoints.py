"""注册过程中可恢复检查点的共享持久化入口。"""
from __future__ import annotations

from core import db
from core.email_provider import resolve_email_source


class RegistrationCheckpointConflict(RuntimeError):
    """远端账号已完成认证，拒绝降级覆盖为待验证状态。"""


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
