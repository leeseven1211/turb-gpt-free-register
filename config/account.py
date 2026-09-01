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
        "twofa_driver": str(ACCOUNT_2FA_DRIVER or "protocol").strip().lower() or "protocol",
        "codex_driver": str(ACCOUNT_CODEX_DRIVER or "same_as_registration").strip().lower() or "same_as_registration",
    }
