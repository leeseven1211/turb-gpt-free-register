"""统一分发开源protocol-2 与本地 Roxy 注册。"""
from __future__ import annotations

from config import roxybrowser as _roxy_cfg
from core.auth.email_guard import serialize_email_auth
from core.registration.driver_selection import normalize_registration_driver
from core.registration.profile_utils import generate_random_birthday


@serialize_email_auth
def run_registration(
    email: str, name: str, birthday: str | None = None, proxy: str | None = None,
    otp_code: str | None = None, existing_password: str | None = None,
    existing_totp_secret: str | None = None, profile_id: str | None = None,
    registration_options: dict | None = None, email_source: str | None = None,
):
    """历史快照映射到现行链路，原始来源记录仍由存储保留。"""
    options = dict(registration_options or {})
    driver = normalize_registration_driver(
        options.get("registration_driver") or getattr(_roxy_cfg, "REGISTRATION_DRIVER", "roxy")
    )
    if driver not in {"protocol_oss_2", "roxy"}:
        raise RuntimeError(f"不支持的 REGISTRATION_DRIVER={driver!r}，当前仅支持 protocol_oss_2 / roxy")
    if registration_options is not None:
        options["registration_driver"] = driver
    if driver == "protocol_oss_2":
        from core.registration.protocol_oss_2 import run_protocol_oss_2_registration as runner
        options.update(registration_driver=driver, password_enabled=True, password_mode="password")
    else:
        from core.registration.roxy import run_roxy_registration as runner
    from core.registration.standalone import run_registration_in_context

    kwargs = dict(
        email=email, name=name, birthday=birthday or generate_random_birthday(), proxy=proxy,
        otp_code=otp_code, existing_password=existing_password, existing_totp_secret=existing_totp_secret,
        profile_id=profile_id,
    )
    if registration_options is not None or driver == "protocol_oss_2":
        kwargs["registration_options"] = options
    if email_source is not None:
        kwargs["email_source"] = email_source
    return run_registration_in_context(
        runner, kwargs, entrypoint="roxy_cli" if driver == "roxy" else "protocol_cli", driver_name=driver,
    )
