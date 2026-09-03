# -*- coding: utf-8 -*-
"""
2FA（TOTP）配置

是否在注册成功后自动设置 2FA：
    True:  注册完成 → 按 TWOFA_DRIVER 开通 TOTP → 把 secret 写入 DB
    False: 跳过整个 2FA 流程，只保存 邮箱 + accessToken

TWOFA_DRIVER:
    auto:      优先使用协议；根据认证上下文自动复用/获取新鲜 AT，失败按配置回退浏览器
    protocol:  使用协议调用 enroll/activate；需要时自动通过协议重认证或浏览器登录获取 AT
    browser:   使用 RoxyBrowser 的安全设置页面开通，兼容页面交互流程

关掉 2FA 不会影响账号可用性，仅意味着账号没有动态口令保护，且少收一封 OTP 邮件。
"""
from config.env_loader import apply_env_overrides
from core.twofa_flow import canonical_twofa_executor, normalize_twofa_mode

ENABLE_2FA = False
TWOFA_DRIVER = "auto"


def get_twofa_driver(value=None) -> str:
    """Return a concrete executor while accepting automatic/legacy modes."""
    return canonical_twofa_executor(TWOFA_DRIVER if value is None else value)


def get_twofa_driver_for_options(options=None) -> str:
    """Resolve the executor from a submitted registration snapshot.

    Registration jobs must keep using the mode selected when they were
    submitted.  The live module setting remains the fallback for legacy
    callers that do not carry a snapshot.
    """
    if isinstance(options, dict) and "twofa_driver" in options:
        return get_twofa_driver(options.get("twofa_driver"))
    return get_twofa_driver()


def get_twofa_mode(value=None) -> str:
    """Return the public normalized mode, including legacy alias migration."""
    return normalize_twofa_mode(TWOFA_DRIVER if value is None else value)

# ---- .env overrides for WebUI editable fields ----
apply_env_overrides(globals(), {'ENABLE_2FA': 'bool', 'TWOFA_DRIVER': 'str'})
