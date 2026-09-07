# -*- coding: utf-8 -*-
"""账号管理和“补全账号”策略配置。

注册链路使用 ``config.register`` / ``config.twofa`` / ``config.codex``；本模块
只决定账号管理里的“补全账号”要包含哪些缺失能力，避免把两条链路重新耦合。
"""
from config.env_loader import apply_env_overrides
from core.twofa_flow import normalize_twofa_mode


# 补全账号默认只处理缺失项。刷新 AT 仍是独立的“操作”，默认不由补全隐式触发。
ACCOUNT_COMPLETION_PASSWORD_ENABLED = True
ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED = True
ACCOUNT_COMPLETION_2FA_ENABLED = True
ACCOUNT_COMPLETION_CODEX_ENABLED = True
ACCOUNT_COMPLETION_REFRESH_AT_ENABLED = False
# Password recovery changes the remote OpenAI password. Keep it opt-in so a
# normal account-completion run cannot trigger reset emails unexpectedly.
ACCOUNT_PASSWORD_RESET_ENABLED = False

# 账号级执行器。same_as_registration 只对 Codex 有意义，其它驱动值由对应
# 服务校验；先保留为配置项，便于后续增加新的协议/浏览器实现。
ACCOUNT_PASSWORD_DRIVER = "roxy"
ACCOUNT_PLAN_CHECK_DRIVER = "protocol"
ACCOUNT_2FA_DRIVER = "auto"
# 账号补全 2FA 默认自动选择：优先协议并按认证上下文获取 AT，协议明确失败
# 且此开关开启时，才继续沿用现有浏览器安全设置流程。
ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED = True
# Protocol 2FA 遇到 MFA 401 时，是否先用协议完成邮箱重认证并换取新 AT。
# 默认开启；关闭后保持“旧 AT 直开失败即按兜底开关处理”的行为。
ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED = True
ACCOUNT_CODEX_DRIVER = "same_as_registration"

# 普通“查活”单独维护驱动选择，不复用 ACCOUNT_PLAN_CHECK_DRIVER。
# 阶段 1 默认解析为当前协议型旧 AT probe，保持现有行为；browser_roxy 已完成
# 契约接入但仍由独立 gate 控制；protocol_v2 不作为普通查活驱动。
ACCOUNT_LIVE_CHECK_DRIVER = "protocol_current"
# Roxy 旧 AT probe 默认关闭；本地明确开启 gate 后才允许使用。
ACCOUNT_LIVE_CHECK_BROWSER_ENABLED = False

# 旧刷新配置仅为历史 .env 兼容保留；新的协议版本统一配置位于
# config.openai_protocol.OPENAI_PROTOCOL_VERSION。只有刷新 AT 同时支持 v1/v2，
# 才会按该配置选择；其他步骤会忽略它并使用自己的唯一实现。
ACCOUNT_TOKEN_REFRESH_DRIVER = "legacy"
# 旧配置的 v2 安全开关仅对历史 ACCOUNT_TOKEN_REFRESH_DRIVER=protocol_v2 生效。
# 新的 OPENAI_PROTOCOL_VERSION=v2 是显式选择，不再依赖此兼容字段。
ACCOUNT_AUTH_V2_ENABLED = False
# 密码明确错误后是否允许另起认证会话发送一次邮箱 OTP。默认关闭，避免把
# 过期/录错密码静默掩盖；开启后任务结果仍保留 password_rejected。
ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK = False
# v2 协议的设备画像默认继续沿用现有“每个 BrowserSession 随机画像”。只有
# 明确选择 account_stable，且实际进入 v2 刷新时，才按账号懒创建私有身份。
ACCOUNT_AUTH_PROFILE_MODE = "current"
# 原始认证上下文（设备 ID、session 标识、完整代理）默认不保存；只有本地明确开启
# 才创建受限 run context。0 表示关闭自动清理，不表示关闭手工逐行清理。
ACCOUNT_AUTH_RAW_CONTEXT_ENABLED = False
ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS = 30


apply_env_overrides(globals(), {
    "ACCOUNT_COMPLETION_PASSWORD_ENABLED": "bool",
    "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED": "bool",
    "ACCOUNT_COMPLETION_2FA_ENABLED": "bool",
    "ACCOUNT_COMPLETION_CODEX_ENABLED": "bool",
    "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED": "bool",
    "ACCOUNT_PASSWORD_RESET_ENABLED": "bool",
    "ACCOUNT_PASSWORD_DRIVER": "str",
    "ACCOUNT_PLAN_CHECK_DRIVER": "str",
    "ACCOUNT_2FA_DRIVER": "str",
    "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED": "bool",
    "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED": "bool",
    "ACCOUNT_CODEX_DRIVER": "str",
    "ACCOUNT_LIVE_CHECK_DRIVER": "str",
    "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED": "bool",
    "ACCOUNT_TOKEN_REFRESH_DRIVER": "str",
    "ACCOUNT_AUTH_V2_ENABLED": "bool",
    "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK": "bool",
    "ACCOUNT_AUTH_PROFILE_MODE": "str",
    "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED": "bool",
    "ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS": "int",
})


def completion_settings() -> dict[str, object]:
    """Return a small, non-sensitive snapshot used by planning and task data."""
    from core.protocol_version import configured_protocol_version

    return {
        "password_enabled": bool(ACCOUNT_COMPLETION_PASSWORD_ENABLED),
        "plan_check_enabled": bool(ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED),
        "twofa_enabled": bool(ACCOUNT_COMPLETION_2FA_ENABLED),
        "codex_enabled": bool(ACCOUNT_COMPLETION_CODEX_ENABLED),
        "refresh_at_enabled": bool(ACCOUNT_COMPLETION_REFRESH_AT_ENABLED),
        "password_reset_enabled": bool(ACCOUNT_PASSWORD_RESET_ENABLED),
        "password_driver": str(ACCOUNT_PASSWORD_DRIVER or "roxy").strip().lower() or "roxy",
        "plan_check_driver": str(ACCOUNT_PLAN_CHECK_DRIVER or "protocol").strip().lower() or "protocol",
        "protocol_version": configured_protocol_version(),
        # Compatibility projection for old callers; new code should consume
        # protocol_version instead of this legacy driver name.
        "token_refresh_driver": str(ACCOUNT_TOKEN_REFRESH_DRIVER or "legacy").strip().lower() or "legacy",
        "auth_v2_enabled": bool(ACCOUNT_AUTH_V2_ENABLED),
        "auth_password_email_fallback": bool(ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK),
        "auth_profile_mode": str(ACCOUNT_AUTH_PROFILE_MODE or "current").strip().lower() or "current",
        "auth_raw_context_enabled": bool(ACCOUNT_AUTH_RAW_CONTEXT_ENABLED),
        "auth_raw_context_retention_days": int(ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS or 0),
        "twofa_driver": normalize_twofa_mode(ACCOUNT_2FA_DRIVER),
        "twofa_browser_fallback_enabled": bool(ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED),
        "twofa_protocol_reauth_enabled": bool(ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED),
        "codex_driver": str(ACCOUNT_CODEX_DRIVER or "same_as_registration").strip().lower() or "same_as_registration",
    }
