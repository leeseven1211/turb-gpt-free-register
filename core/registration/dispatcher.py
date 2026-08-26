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
    batch_dir=None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
):
    """按 `REGISTRATION_DRIVER` 分发一次注册任务。"""
    driver_mode = str(getattr(_roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()

    if driver_mode in ("roxy", "roxybrowser", "fingerprint", "browser"):
        from core.registration.roxy import run_roxy_registration

        return run_roxy_registration(
            email=email,
            name=name,
            birthday=birthday or generate_random_birthday(),
            proxy=proxy,
            otp_code=otp_code,
            batch_dir=batch_dir,
            existing_password=existing_password,
            existing_totp_secret=existing_totp_secret,
        )

    if existing_password:
        raise RuntimeError(
            f"待邮箱验证账号续跑当前仅支持 Roxy 注册驱动，当前 REGISTRATION_DRIVER={driver_mode!r}"
        )

    if driver_mode in ("cloak", "cloakbrowser"):
        from core.cloakbrowser_registration import run_cloak_registration

        return run_cloak_registration(
            email=email,
            name=name,
            birthday=birthday or generate_random_birthday(),
            proxy=proxy,
            otp_code=otp_code,
            batch_dir=batch_dir,
        )

    if driver_mode in ("browser_use", "browseruse", "browser-use", "bu"):
        from core.registration.browser_use import run_browser_use_registration

        return run_browser_use_registration(
            email=email,
            name=name,
            birthday=birthday or generate_random_birthday(),
            proxy=proxy,
            otp_code=otp_code,
            batch_dir=batch_dir,
        )

    if driver_mode in ("skyvern", "sv"):
        from core.skyvern_registration import run_skyvern_registration

        return run_skyvern_registration(
            email=email,
            name=name,
            birthday=birthday or generate_random_birthday(),
            proxy=proxy,
            otp_code=otp_code,
            batch_dir=batch_dir,
        )

    if driver_mode not in ("protocol", "api", "http"):
        raise RuntimeError(
            f"不支持的 REGISTRATION_DRIVER={driver_mode!r}，可选 protocol / roxy / cloak / browser_use / skyvern"
        )

    from core.registration.protocol import run_protocol_registration

    return run_protocol_registration(
        email=email,
        name=name,
        birthday=birthday,
        proxy=proxy,
        otp_code=otp_code,
        batch_dir=batch_dir,
    )
