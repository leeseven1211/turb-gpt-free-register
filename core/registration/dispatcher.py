"""统一注册驱动分发。

这里只负责选择驱动和保持公共调用签名；具体注册流程由各驱动模块实现。
"""
from __future__ import annotations

from config import roxybrowser as _roxy_cfg
from core.profile_utils import generate_random_birthday


def run_registration(
    email: str,
    name: str,
    birthday: str | None = None,
    proxy: str | None = None,
    otp_code: str | None = None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
    profile_id: str | None = None,
    registration_options: dict | None = None,
    email_source: str | None = None,
):
    """按 `REGISTRATION_DRIVER` 分发一次注册任务。"""
    snapshot_driver = ""
    if isinstance(registration_options, dict):
        snapshot_driver = str(registration_options.get("registration_driver") or "").strip()
    driver_mode = str(
        snapshot_driver or getattr(_roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol"
    ).strip().lower()

    # Roxy 是唯一的浏览器注册驱动；旧别名保留用于兼容历史任务配置。
    if driver_mode in ("roxy", "roxybrowser", "fingerprint", "browser"):
        from core.registration.roxy import run_roxy_registration
        from core.registration.standalone import run_registration_in_context

        kwargs = dict(
            email=email,
            name=name,
            birthday=birthday or generate_random_birthday(),
            proxy=proxy,
            otp_code=otp_code,
            existing_password=existing_password,
            existing_totp_secret=existing_totp_secret,
        )
        if registration_options is not None:
            kwargs["registration_options"] = registration_options
        if email_source is not None:
            kwargs["email_source"] = email_source
        kwargs["profile_id"] = profile_id
        return run_registration_in_context(
            run_roxy_registration,
            kwargs,
            entrypoint="roxy_cli",
            driver_name="roxy",
        )

    if existing_password and driver_mode not in ("protocol", "api", "http"):
        raise RuntimeError(
            "待邮箱验证账号续跑当前仅支持 Roxy 或 Protocol 注册驱动"
        )

    if driver_mode not in ("protocol", "api", "http"):
        raise RuntimeError(
            f"不支持的 REGISTRATION_DRIVER={driver_mode!r}，当前仅支持 protocol / roxy"
        )

    from core.registration.protocol import run_protocol_registration
    from core.registration.standalone import run_protocol_in_context

    kwargs = dict(
        email=email,
        name=name,
        birthday=birthday,
        proxy=proxy,
        otp_code=otp_code,
    )
    if registration_options is not None:
        kwargs["registration_options"] = registration_options
    if email_source is not None:
        kwargs["email_source"] = email_source
    if existing_password is not None:
        kwargs["existing_password"] = existing_password
    if existing_totp_secret is not None:
        kwargs["existing_totp_secret"] = existing_totp_secret
    return run_protocol_in_context(run_protocol_registration, kwargs)
