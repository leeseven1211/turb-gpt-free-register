# -*- coding: utf-8 -*-
"""Skyvern 云端浏览器注册入口。"""
from __future__ import annotations

from core.registration.legacy.browser_use.flow import run_browser_use_registration


def run_skyvern_registration(
    email: str,
    name: str,
    birthday: str,
    proxy: str | None = None,
    otp_code: str | None = None,
    registration_options: dict | None = None,
    email_source: str | None = None,
) -> dict:
    registration_kwargs = {
        "email": email,
        "name": name,
        "birthday": birthday,
        "proxy": proxy,
        "otp_code": otp_code,
        "cloud_provider": "skyvern",
        "registration_options": registration_options,
    }
    if email_source is not None:
        registration_kwargs["email_source"] = email_source
    return run_browser_use_registration(**registration_kwargs)
