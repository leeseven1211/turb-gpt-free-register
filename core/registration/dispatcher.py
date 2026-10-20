"""统一注册驱动分发。

这里只负责选择驱动和保持公共调用签名；具体注册流程由各驱动模块实现。
"""
from __future__ import annotations

from config import roxybrowser as _roxy_cfg
from core.email_auth_guard import serialize_email_auth
from core.profile_utils import generate_random_birthday


@serialize_email_auth
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

    # 开源 Roxy 使用独立页面辅助；旧别名仍指向本地 Roxy。
    if driver_mode in ("roxy", "roxy_oss", "roxybrowser", "fingerprint", "browser"):
        if driver_mode == "roxy_oss":
            from core.registration.roxy_oss import run_roxy_oss_registration as run_browser_registration
        else:
            from core.registration.roxy import run_roxy_registration as run_browser_registration
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
            run_browser_registration,
            kwargs,
            entrypoint="roxy_cli",
            driver_name="roxy_oss" if driver_mode == "roxy_oss" else "roxy",
        )

    if existing_password and driver_mode not in ("protocol", "protocol_oss", "protocol_oss_2", "api", "http"):
        raise RuntimeError(
            "待邮箱验证账号续跑当前仅支持 Roxy 或 Protocol 注册驱动"
        )

    if driver_mode in {"protocol_oss", "protocol_oss_2"}:
        from core.registration.standalone import run_registration_in_context

        if driver_mode == "protocol_oss_2":
            from core.registration.protocol_oss_2 import run_protocol_oss_2_registration as run_open_source
        else:
            from core.registration.protocol_oss import run_protocol_oss_registration as run_open_source

        kwargs = dict(
            email=email,
            name=name,
            birthday=birthday,
            proxy=proxy,
            otp_code=otp_code,
            profile_id=profile_id,
        )
        if registration_options is not None:
            kwargs["registration_options"] = registration_options
        if email_source is not None:
            kwargs["email_source"] = email_source
        if existing_password is not None:
            kwargs["existing_password"] = existing_password
        if existing_totp_secret is not None:
            kwargs["existing_totp_secret"] = existing_totp_secret
        return run_registration_in_context(
            run_open_source, kwargs, entrypoint="protocol_cli", driver_name=driver_mode,
        )

    if driver_mode not in ("protocol", "api", "http"):
        raise RuntimeError(
            f"不支持的 REGISTRATION_DRIVER={driver_mode!r}，当前仅支持 protocol / protocol_oss / protocol_oss_2 / roxy / roxy_oss"
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
