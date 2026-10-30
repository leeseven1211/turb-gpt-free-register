"""用户指定的开源protocol-2 注册驱动。"""
from __future__ import annotations


def run_protocol_oss_2_registration(
    email: str, name: str, birthday: str | None = None, proxy: str | None = None,
    otp_code: str | None = None, existing_password: str | None = None,
    existing_totp_secret: str | None = None, profile_id: str | None = None,
    registration_options: dict | None = None, email_source: str | None = None,
) -> dict:
    """复用本地生命周期，认证主流程使用独立的上游引擎。"""
    from core.registration.protocol_oss import run_protocol_oss_registration
    from core.registration.protocol_oss_2.runtime import run_upstream_protocol
    from core.auth.protocol.session import BrowserSession

    options = dict(registration_options or {})
    options.update(registration_driver="protocol_oss_2", password_enabled=True, password_mode="password")
    return run_protocol_oss_registration(
        email=email, name=name, birthday=birthday, proxy=proxy, otp_code=otp_code,
        existing_password=existing_password, existing_totp_secret=existing_totp_secret,
        profile_id=profile_id, registration_options=options, email_source=email_source,
        _flow_runner=run_upstream_protocol, _driver_name="protocol_oss_2", _label="开源protocol-2",
        _session_factory=lambda **kwargs: BrowserSession(**kwargs, detect_exit_geo=False),
    )
