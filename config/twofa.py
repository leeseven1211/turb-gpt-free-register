# -*- coding: utf-8 -*-
"""
2FA（TOTP）配置

是否在注册成功后自动设置 2FA：
    True:  注册完成 → 按 TWOFA_DRIVER 开通 TOTP → 把 secret 写入 DB
    False: 跳过整个 2FA 流程，只保存 邮箱 + accessToken

TWOFA_DRIVER:
    protocol: 使用当前新鲜 accessToken 直接调用 enroll/activate，速度更快
    browser:   使用 RoxyBrowser 的安全设置页面开通，兼容页面交互流程

关掉 2FA 不会影响账号可用性，仅意味着账号没有动态口令保护，且少收一封 OTP 邮件。
"""
from config.env_loader import apply_env_overrides

ENABLE_2FA = False
TWOFA_DRIVER = "protocol"


def get_twofa_driver(value=None) -> str:
    """返回规范化的 2FA 开通方式，兼容旧配置中的常见别名。"""
    raw = TWOFA_DRIVER if value is None else value
    normalized = str(raw or "").strip().lower()
    aliases = {
        "api": "protocol",
        "http": "protocol",
        "roxy": "browser",
        "roxybrowser": "browser",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"protocol", "browser"}:
        raise ValueError("TWOFA_DRIVER 只支持 protocol 或 browser")
    return normalized

# ---- .env overrides for WebUI editable fields ----
apply_env_overrides(globals(), {'ENABLE_2FA': 'bool', 'TWOFA_DRIVER': 'str'})
