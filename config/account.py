# -*- coding: utf-8 -*-
"""账号管理和“补全账号”策略配置。

注册链路使用 ``config.register`` / ``config.twofa`` / ``config.codex``；本模块
只决定账号管理里的“补全账号”要包含哪些缺失能力，避免把两条链路重新耦合。
"""
from config.env_loader import apply_env_overrides


# 补全账号默认只处理缺失项。刷新 AT 仍是独立的“操作”，默认不由补全隐式触发。
ACCOUNT_COMPLETION_PASSWORD_ENABLED = True
ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED = True
ACCOUNT_COMPLETION_2FA_ENABLED = True
ACCOUNT_COMPLETION_CODEX_ENABLED = True
ACCOUNT_COMPLETION_REFRESH_AT_ENABLED = False

# 账号级执行器。same_as_registration 只对 Codex 有意义，其它驱动值由对应
# 服务校验；先保留为配置项，便于后续增加新的协议/浏览器实现。
ACCOUNT_PASSWORD_DRIVER = "roxy"
ACCOUNT_PLAN_CHECK_DRIVER = "protocol"
ACCOUNT_2FA_DRIVER = "protocol"
ACCOUNT_CODEX_DRIVER = "same_as_registration"

# 普通“查活”单独维护驱动选择，不复用 ACCOUNT_PLAN_CHECK_DRIVER。
# 阶段 1 默认解析为当前协议型旧 AT probe，保持现有行为；后续通过真实契约
# 测试后再开放 browser_roxy / protocol_v2。
ACCOUNT_LIVE_CHECK_DRIVER = "protocol_current"
# 阶段 2 的 Roxy 旧 AT probe 默认关闭；真实契约测试通过后才允许开启。
ACCOUNT_LIVE_CHECK_BROWSER_ENABLED = False

# 显式“刷新 AT”仍保持原有协议邮箱 OTP → Roxy 兜底顺序。只有用户同时选择
# protocol_v2 并打开总开关时，才会尝试保存的 OpenAI 密码 / TOTP；普通查活不受影响。
ACCOUNT_TOKEN_REFRESH_DRIVER = "legacy"
ACCOUNT_AUTH_V2_ENABLED = False
# 密码明确错误后是否允许另起认证会话发送一次邮箱 OTP。默认关闭，避免把
# 过期/录错密码静默掩盖；开启后任务结果仍保留 password_rejected。
ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK = False


apply_env_overrides(globals(), {
    "ACCOUNT_COMPLETION_PASSWORD_ENABLED": "bool",
    "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED": "bool",
    "ACCOUNT_COMPLETION_2FA_ENABLED": "bool",
    "ACCOUNT_COMPLETION_CODEX_ENABLED": "bool",
    "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED": "bool",
    "ACCOUNT_PASSWORD_DRIVER": "str",
    "ACCOUNT_PLAN_CHECK_DRIVER": "str",
    "ACCOUNT_2FA_DRIVER": "str",
    "ACCOUNT_CODEX_DRIVER": "str",
    "ACCOUNT_LIVE_CHECK_DRIVER": "str",
    "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED": "bool",
    "ACCOUNT_TOKEN_REFRESH_DRIVER": "str",
    "ACCOUNT_AUTH_V2_ENABLED": "bool",
    "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK": "bool",
})


def completion_settings() -> dict[str, object]:
    """Return a small, non-sensitive snapshot used by planning and task data."""
    return {
        "password_enabled": bool(ACCOUNT_COMPLETION_PASSWORD_ENABLED),
        "plan_check_enabled": bool(ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED),
        "twofa_enabled": bool(ACCOUNT_COMPLETION_2FA_ENABLED),
        "codex_enabled": bool(ACCOUNT_COMPLETION_CODEX_ENABLED),
        "refresh_at_enabled": bool(ACCOUNT_COMPLETION_REFRESH_AT_ENABLED),
        "password_driver": str(ACCOUNT_PASSWORD_DRIVER or "roxy").strip().lower() or "roxy",
        "plan_check_driver": str(ACCOUNT_PLAN_CHECK_DRIVER or "protocol").strip().lower() or "protocol",
        "token_refresh_driver": str(ACCOUNT_TOKEN_REFRESH_DRIVER or "legacy").strip().lower() or "legacy",
        "auth_v2_enabled": bool(ACCOUNT_AUTH_V2_ENABLED),
        "auth_password_email_fallback": bool(ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK),
        "twofa_driver": str(ACCOUNT_2FA_DRIVER or "protocol").strip().lower() or "protocol",
        "codex_driver": str(ACCOUNT_CODEX_DRIVER or "same_as_registration").strip().lower() or "same_as_registration",
    }
