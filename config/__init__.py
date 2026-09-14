from config.env_loader import load_env
load_env(override=False)

# -*- coding: utf-8 -*-
"""
config 包的统一入口。

为保留 `from config import USER_AGENT` 这种历史用法，本文件把所有子模块的常量
重新导出到包顶层。新代码推荐按子模块直接导入：
    from config.email import EMAIL_SOURCE
    from config.proxy import pick_proxy

子模块清单：
    config.browser           浏览器指纹 / curl_cffi impersonate / HTTP 超时
    config.openai_protocol   OpenAI OAuth 固定参数 / Sentinel 版本
    config.proxy             代理池 + 随机抽取
    config.register          注册默认信息（邮箱、密码、名称、生日）
    config.email             Outlook 邮箱账号池 + OTP 轮询
    config.twofa             2FA 开关
"""

# ---------- 浏览器 / HTTP ----------
from config.browser import (
    USER_AGENT,
    CHROME_MAJOR,
    CHROME_FULL_VERSION,
    BROWSER_OS,
    NAVIGATOR_PLATFORM,
    NAVIGATOR_VENDOR,
    USER_AGENT_DATA_PLATFORM,
    SEC_CH_UA,
    SEC_CH_UA_PLATFORM,
    SEC_CH_UA_MOBILE,
    SEC_CH_UA_FULL_VERSION_LIST,
    SEC_CH_UA_PLATFORM_VERSION,
    SEC_CH_UA_ARCH,
    SEC_CH_UA_BITNESS,
    SEC_CH_UA_MODEL,
    SEND_HIGH_ENTROPY_CLIENT_HINTS,
    ACCEPT_LANGUAGE,
    BROWSER_LOCALE_PROFILE,
    BROWSER_LOCALE_PROFILES,
    AUTO_BROWSER_LOCALE_FROM_IP,
    IP_GEO_TIMEOUT,
    IP_GEO_ENDPOINTS,
    REJECT_CLOUD_PROXY,
    CLOUD_PROXY_ORG_KEYWORDS,
    COUNTRY_LOCALE_PROFILE_MAP,
    NAVIGATOR_LANGUAGE,
    NAVIGATOR_LANGUAGES,
    TIMEZONE_IANA,
    TIMEZONE_OFFSET_MINUTES,
    TIMEZONE_NAME,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    HARDWARE_CONCURRENCY,
    JS_HEAP_SIZE_LIMIT,
    DEVICE_MEMORY,
    NAVIGATOR_PROTO_SAMPLES,
    DOCUMENT_KEY_SAMPLES,
    WINDOW_KEY_SAMPLES,
    WINDOW_FEATURE_FLAGS,
    build_browser_environment,
    validate_browser_profile,
    BROWSER_PROFILE_POOL,
    pick_browser_profile,
    IMPERSONATE,
    REQUEST_TIMEOUT,
)

# ---------- OpenAI 协议 ----------
from config.openai_protocol import (
    OPENAI_PROTOCOL_VERSION,
    OPENAI_CLIENT_ID,
    OPENAI_SCOPE,
    OPENAI_AUDIENCE,
    OPENAI_REDIRECT_URI,
    SENTINEL_SV,
    OPENAI_BUILD_ID,
    OAI_CLIENT_BUILD_NUMBER,
    OAI_CLIENT_VERSION,
    STATSIG_CLIENT_KEY,
    STATSIG_SDK_VERSION,
    STATSIG_SDK_TYPE,
    AB_CLIENT_KEY,
    AB_SDK_VERSION,
    SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE,
    CHATGPT_ANON_BOOTSTRAP_ENABLED,
    CHATGPT_AUTH_BOOTSTRAP_ENABLED,
    CHATGPT_BOOTSTRAP_STRICT,
)

# ---------- 代理池 ----------
from config.proxy import (
    PROXY_POOL,
    REGISTRATION_PROXY_MODE,
    PROXY_1024_API_URL,
    PROXY_1024_REGION,
    PROXY_1024_PROTOCOL,
    PROXY_1024_SESSION_MINUTES,
    PROXY_1024_API_TIMEOUT,
    PROXY_1024_MAX_ATTEMPTS,
    PROXY_1024_VALIDATE,
    PROXY_1024_RECENT_TTL,
    PROXY_1024_ACQUIRE_INTERVAL,
    PROXY_1024_PERSIST_LEASES,
    REGISTRATION_PROXY_RETRIES,
    REGISTRATION_PROXY_RETRY_DELAY,
    PLAN_CHECK_PROXY_MODE,
    PLAN_CHECK_PROXY,
    ACCOUNT_ACTION_PROXY_MODE,
    ACCOUNT_ACTION_PROXY,
    PLAN_CHECK_TIMEOUT,
    PLAN_CHECK_MAX_ATTEMPTS,
    PLAN_CHECK_RETRY_DELAY,
    PLAN_CHECK_REGISTRATION_RECHECK_DELAY,
    PLAN_CHECK_WORKERS,
    PLAN_CHECK_QUEUE_LIMIT,
    PLAN_CHECK_MIN_INTERVAL,
    PLAN_CHECK_JITTER,
    pick_proxy,
    PROXY,
)

# ---------- 注册默认信息 ----------
from config.register import (
    REGISTER_EMAIL,
    REGISTRATION_AUTH_MODE,
    REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS,
    REGISTRATION_PLAN_CHECK_ENABLED,
    REGISTER_NAME,
)

# ---------- 邮箱服务 ----------
from config.email import (
    USE_EMAIL_SERVICE,
    EMAIL_SOURCE,
    OUTLOOK_ACCOUNTS_FILE,
    OUTLOOK_API_BASE,
    OTP_POLL_INTERVAL,
    OTP_MAX_WAIT,
    OTP_SETTLE_SECONDS,
    EMAIL_DOMAIN,
    QQ_IMAP_SERVER,
    QQ_IMAP_PORT,
    QQ_EMAIL,
    QQ_IMAP_PASSWORD,
    GPTMAIL_API_KEY,
    EMAIL_BUTLER_API_BASE,
    EMAIL_BUTLER_API_KEY,
    EMAIL_BUTLER_REQUEST_TIMEOUT,
    MAIL_NEST_API_KEY,
    MAIL_NEST_PROJECT_CODE,
    CLOUDFLARE_API_BASE,
    CLOUDFLARE_API_KEY,
    CLOUDFLARE_SIGNAL_API_KEY,
    CLOUDFLARE_SIGNAL_PATH,
    CLOUDFLARE_AUTH_MODE,
    CLOUDFLARE_CUSTOM_AUTH,
    CLOUDFLARE_PATH_DOMAINS,
    CLOUDFLARE_PATH_ACCOUNTS,
    CLOUDFLARE_PATH_TOKEN,
    CLOUDFLARE_PATH_MESSAGES,
    CLOUDFLARE_DEFAULT_DOMAINS,
    CLOUDFLARE_REQUEST_TIMEOUT,
    CLOUDFLARE_NAME_LENGTH,
    CLOUDMAIL_API_BASE,
    CLOUDMAIL_ADMIN_EMAIL,
    CLOUDMAIL_PASSWORD,
    CLOUDMAIL_TOKEN_PATH,
    CLOUDMAIL_AUTH_TOKEN,
    CLOUDMAIL_DOMAINS,
    CLOUDMAIL_AUTO_ADD_USER,
    CLOUDMAIL_RANDOM_LOCAL_LENGTH,
    ICLOUD_HME_API_BASE,
    ICLOUD_HME_ACCOUNT_ID,
    ICLOUD_HME_API_TOKEN,
    ICLOUD_HME_REQUEST_TIMEOUT,
    ICLOUD_HME_SYNC_TTL,
    ICLOUD_HME_AUTO_CREATE,
    ICLOUD_HME_CREATE_LABEL_PREFIX,
)

# ---------- 2FA ----------
from config.twofa import ENABLE_2FA, TWOFA_DRIVER

# ---------- 账号管理 / 补全策略 ----------
from config.account import (
    ACCOUNT_COMPLETION_PASSWORD_ENABLED,
    ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED,
    ACCOUNT_COMPLETION_2FA_ENABLED,
    ACCOUNT_COMPLETION_CODEX_ENABLED,
    ACCOUNT_COMPLETION_REFRESH_AT_ENABLED,
    ACCOUNT_PASSWORD_RESET_ENABLED,
    ACCOUNT_PASSWORD_DRIVER,
    ACCOUNT_PLAN_CHECK_DRIVER,
    ACCOUNT_2FA_DRIVER,
    ACCOUNT_PASSWORD_PROXY_MODE,
    ACCOUNT_2FA_PROXY_MODE,
    ACCOUNT_PLAN_CHECK_PROXY_MODE,
    ACCOUNT_LIVE_CHECK_PROXY_MODE,
    ACCOUNT_REFRESH_AT_PROXY_MODE,
    ACCOUNT_CODEX_PROXY_MODE,
    ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED,
    ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED,
    ACCOUNT_CODEX_DRIVER,
    ACCOUNT_LIVE_CHECK_DRIVER,
    ACCOUNT_LIVE_CHECK_BROWSER_ENABLED,
    ACCOUNT_TOKEN_REFRESH_DRIVER,
    ACCOUNT_AUTH_V2_ENABLED,
    ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK,
    ACCOUNT_AUTH_PROFILE_MODE,
    ACCOUNT_AUTH_RAW_CONTEXT_ENABLED,
    ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS,
)


# ---------- 热加载支持 ----------
# WebUI 改配置后调 reload_all() 会校验并尝试让所有运行时代码看到新值，无需
# 重启进程。reload_all 的模块回滚只保证失败后恢复 writer 状态；它不把旧式
# `mod.CONSTANT` 读者变成全局无锁原子读者。旧代码若需要一致版本，应在一次
# 业务操作开始时调用 `config.non_sensitive_snapshot()`，并只使用该对象的
# values；`from config import CONSTANT` / `from config.module import CONSTANT`
# 的迁移边界仍由调用方自行处理。
import importlib as _importlib
import os as _os
import sys as _sys
import threading as _threading

_RELOADABLE_SUBMODULES = (
    "config.browser",
    "config.openai_protocol",
    "config.proxy",
    "config.register",
    "config.account",
    "config.email",
    "config.twofa",
    "config.roxybrowser",
    "config.flow_trigger",
    "config.codex",
    "config.extract_link",
    "config.sub2api",
    "config.humanize",
    "config.registration_debug",
)

_RELOAD_LOCK = _threading.RLock()


def reload_all() -> list[str]:
    """
    带候选快照发布和失败回滚的热重载，返回成功 reload 的模块名列表。

    先保存所有参与模块的 namespace、config 包顶层导出和进程环境；任一
    子模块或顶层同步失败时全部恢复。新 snapshot 读者只会看到旧版或新版；
    旧式直接读取模块常量的读者仍受逐模块 reload 迁移边界约束。
    """
    with _RELOAD_LOCK:
        # 先确保已有稳定旧版本；这样并发读者不会在本次候选 reload 期间
        # 首次初始化并发布一份可能需要回滚的环境快照。
        from config.schema import non_sensitive_snapshot

        non_sensitive_snapshot()
        package_before = dict(globals())
        environment_before = dict(_os.environ)
        environment_expected = dict(_os.environ)
        module_before = {
            name: _sys.modules.get(name)
            for name in _RELOADABLE_SUBMODULES
        }
        namespace_before = {
            name: dict(module.__dict__)
            for name, module in module_before.items()
            if module is not None
        }
        reloaded = []
        try:
            from config.env_loader import load_env
            from config.schema import build_non_sensitive_snapshot, publish_config_snapshot

            load_env(override=True)
            environment_expected = dict(_os.environ)
            # 先离线解析/严格校验整套候选配置并构建稳定快照；模块 reload
            # 失败时这个候选尚未发布。
            candidate_snapshot = build_non_sensitive_snapshot(
                environment_expected,
                strict=True,
            )
            for name in _RELOADABLE_SUBMODULES:
                mod = _sys.modules.get(name)
                if mod is None:
                    mod = _importlib.import_module(name)
                else:
                    _importlib.reload(mod)
                reloaded.append(name)
            # 同步刷新 config 包顶层的"被绑死"常量。
            _refresh_top_level_constants()
            # 仅在所有兼容模块成功后做一次 snapshot reference swap。
            publish_config_snapshot(candidate_snapshot)
            return reloaded
        except Exception:
            # 恢复模块字典和 sys.modules 中的精确对象。仅处理本次 reload
            # 清单内的模块，不触碰其他业务模块或运行时数据。
            for name, module in module_before.items():
                if module is None:
                    _sys.modules.pop(name, None)
                    continue
                _sys.modules[name] = module
                previous_namespace = namespace_before[name]
                module.__dict__.clear()
                module.__dict__.update(previous_namespace)

            from config.env_loader import restore_environment

            restore_environment(environment_before, environment_expected)

            # 恢复 config 包所有原有属性，去掉失败过程中新增的模块/常量。
            current_keys = set(globals())
            for key in current_keys - set(package_before):
                globals().pop(key, None)
            globals().update(package_before)
            raise


def _refresh_top_level_constants() -> None:
    """把刚 reload 的子模块的常量重新拷一份到 config 包顶层。"""
    import config as _self
    from config import browser, openai_protocol, proxy as _proxy, register, account, email, twofa, roxybrowser, codex, extract_link, sub2api, humanize, flow_trigger
    # 简单粗暴：枚举一遍重要常量，覆盖到 _self
    for src in (browser, openai_protocol, _proxy, register, account, email, twofa, roxybrowser, codex, extract_link, sub2api, humanize, flow_trigger):
        for k in dir(src):
            if k.isupper() or k in ("pick_proxy", "pick_browser_profile", "build_browser_environment", "validate_browser_profile"):
                setattr(_self, k, getattr(src, k))


# 新任务/服务代码的稳定入口。返回的 ConfigSnapshot 在进程内不可变，且不含
# secret 字段；不要把旧式逐项常量读取误当作 snapshot 事务。
from config.schema import (
    ConfigSnapshot,
    build_non_sensitive_snapshot,
    get_non_sensitive_snapshot,
    non_sensitive_snapshot,
)


__all__ = [
    # browser
    "USER_AGENT", "CHROME_MAJOR", "CHROME_FULL_VERSION", "BROWSER_OS",
    "NAVIGATOR_PLATFORM", "NAVIGATOR_VENDOR", "USER_AGENT_DATA_PLATFORM",
    "SEC_CH_UA", "SEC_CH_UA_PLATFORM", "SEC_CH_UA_MOBILE",
    "SEC_CH_UA_FULL_VERSION_LIST", "SEC_CH_UA_PLATFORM_VERSION",
    "SEC_CH_UA_ARCH", "SEC_CH_UA_BITNESS", "SEC_CH_UA_MODEL",
    "SEND_HIGH_ENTROPY_CLIENT_HINTS", "ACCEPT_LANGUAGE", "BROWSER_LOCALE_PROFILE", "BROWSER_LOCALE_PROFILES",
    "AUTO_BROWSER_LOCALE_FROM_IP", "IP_GEO_TIMEOUT", "IP_GEO_ENDPOINTS", "REJECT_CLOUD_PROXY", "CLOUD_PROXY_ORG_KEYWORDS", "COUNTRY_LOCALE_PROFILE_MAP",
    "NAVIGATOR_LANGUAGE", "NAVIGATOR_LANGUAGES",
    "TIMEZONE_IANA", "TIMEZONE_OFFSET_MINUTES", "TIMEZONE_NAME", "SCREEN_WIDTH", "SCREEN_HEIGHT",
    "HARDWARE_CONCURRENCY", "JS_HEAP_SIZE_LIMIT", "DEVICE_MEMORY",
    "NAVIGATOR_PROTO_SAMPLES", "DOCUMENT_KEY_SAMPLES", "WINDOW_KEY_SAMPLES", "WINDOW_FEATURE_FLAGS",
    "build_browser_environment", "validate_browser_profile",
    "BROWSER_PROFILE_POOL", "pick_browser_profile",
    "IMPERSONATE", "REQUEST_TIMEOUT",
    # openai_protocol
    "OPENAI_PROTOCOL_VERSION", "OPENAI_CLIENT_ID", "OPENAI_SCOPE", "OPENAI_AUDIENCE", "OPENAI_REDIRECT_URI",
    "SENTINEL_SV", "OPENAI_BUILD_ID", "OAI_CLIENT_BUILD_NUMBER", "OAI_CLIENT_VERSION",
    "STATSIG_CLIENT_KEY", "STATSIG_SDK_VERSION", "STATSIG_SDK_TYPE", "AB_CLIENT_KEY", "AB_SDK_VERSION",
    "SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE", "CHATGPT_ANON_BOOTSTRAP_ENABLED", "CHATGPT_AUTH_BOOTSTRAP_ENABLED", "CHATGPT_BOOTSTRAP_STRICT",
    # proxy
    "PROXY_POOL", "REGISTRATION_PROXY_MODE", "PROXY_1024_API_URL", "PROXY_1024_REGION", "PROXY_1024_PROTOCOL",
    "PROXY_1024_SESSION_MINUTES", "PROXY_1024_API_TIMEOUT", "PROXY_1024_MAX_ATTEMPTS",
    "PROXY_1024_VALIDATE", "PROXY_1024_RECENT_TTL", "PROXY_1024_ACQUIRE_INTERVAL", "PROXY_1024_PERSIST_LEASES",
    "REGISTRATION_PROXY_RETRIES", "REGISTRATION_PROXY_RETRY_DELAY",
    "PLAN_CHECK_PROXY_MODE", "PLAN_CHECK_PROXY", "ACCOUNT_ACTION_PROXY_MODE", "ACCOUNT_ACTION_PROXY",
    "PLAN_CHECK_TIMEOUT", "PLAN_CHECK_MAX_ATTEMPTS", "PLAN_CHECK_RETRY_DELAY",
    "PLAN_CHECK_REGISTRATION_RECHECK_DELAY", "PLAN_CHECK_WORKERS", "PLAN_CHECK_QUEUE_LIMIT",
    "PLAN_CHECK_MIN_INTERVAL", "PLAN_CHECK_JITTER", "pick_proxy", "PROXY",
    # register
    "REGISTER_EMAIL", "REGISTRATION_AUTH_MODE", "REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS", "REGISTRATION_PLAN_CHECK_ENABLED", "REGISTER_NAME",
    # email
    "USE_EMAIL_SERVICE", "EMAIL_SOURCE",
    "OUTLOOK_ACCOUNTS_FILE", "OUTLOOK_API_BASE",
    "OTP_POLL_INTERVAL", "OTP_MAX_WAIT", "OTP_SETTLE_SECONDS",
    "EMAIL_DOMAIN", "QQ_IMAP_SERVER", "QQ_IMAP_PORT", "QQ_EMAIL", "QQ_IMAP_PASSWORD",
    "GPTMAIL_API_KEY", "EMAIL_BUTLER_API_BASE", "EMAIL_BUTLER_API_KEY", "EMAIL_BUTLER_REQUEST_TIMEOUT",
    "MAIL_NEST_API_KEY", "MAIL_NEST_PROJECT_CODE",
    "CLOUDFLARE_API_BASE", "CLOUDFLARE_API_KEY", "CLOUDFLARE_SIGNAL_API_KEY", "CLOUDFLARE_SIGNAL_PATH", "CLOUDFLARE_AUTH_MODE", "CLOUDFLARE_CUSTOM_AUTH",
    "CLOUDFLARE_PATH_DOMAINS", "CLOUDFLARE_PATH_ACCOUNTS", "CLOUDFLARE_PATH_TOKEN",
    "CLOUDFLARE_PATH_MESSAGES", "CLOUDFLARE_DEFAULT_DOMAINS",
    "CLOUDFLARE_REQUEST_TIMEOUT", "CLOUDFLARE_NAME_LENGTH",
    "CLOUDMAIL_API_BASE", "CLOUDMAIL_ADMIN_EMAIL", "CLOUDMAIL_PASSWORD", "CLOUDMAIL_TOKEN_PATH",
    "CLOUDMAIL_AUTH_TOKEN", "CLOUDMAIL_DOMAINS",
    "CLOUDMAIL_AUTO_ADD_USER", "CLOUDMAIL_RANDOM_LOCAL_LENGTH",
    "ICLOUD_HME_API_BASE", "ICLOUD_HME_ACCOUNT_ID", "ICLOUD_HME_API_TOKEN",
    "ICLOUD_HME_REQUEST_TIMEOUT", "ICLOUD_HME_SYNC_TTL", "ICLOUD_HME_AUTO_CREATE",
    "ICLOUD_HME_CREATE_LABEL_PREFIX",
    # twofa
    "ENABLE_2FA", "TWOFA_DRIVER",
    # account completion
    "ACCOUNT_COMPLETION_PASSWORD_ENABLED", "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED",
    "ACCOUNT_COMPLETION_2FA_ENABLED", "ACCOUNT_COMPLETION_CODEX_ENABLED",
    "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED", "ACCOUNT_PASSWORD_RESET_ENABLED", "ACCOUNT_PASSWORD_DRIVER",
    "ACCOUNT_PLAN_CHECK_DRIVER", "ACCOUNT_2FA_DRIVER", "ACCOUNT_PASSWORD_PROXY_MODE",
    "ACCOUNT_2FA_PROXY_MODE", "ACCOUNT_PLAN_CHECK_PROXY_MODE", "ACCOUNT_LIVE_CHECK_PROXY_MODE",
    "ACCOUNT_REFRESH_AT_PROXY_MODE", "ACCOUNT_CODEX_PROXY_MODE", "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED",
    "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED",
    "ACCOUNT_CODEX_DRIVER", "ACCOUNT_LIVE_CHECK_DRIVER",
    "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", "ACCOUNT_TOKEN_REFRESH_DRIVER",
    "ACCOUNT_AUTH_V2_ENABLED", "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", "ACCOUNT_AUTH_PROFILE_MODE",
    "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", "ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS",
    "ConfigSnapshot", "non_sensitive_snapshot", "get_non_sensitive_snapshot",
    "build_non_sensitive_snapshot",
]
