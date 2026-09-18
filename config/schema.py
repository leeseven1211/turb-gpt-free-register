# -*- coding: utf-8 -*-
"""统一配置 schema、环境解析、校验和非敏感快照。

这里是 WebUI 可编辑配置的运行时契约。完整字段定义（文件归属、类型、
分组、文案、默认值、范围、选项、别名、敏感性和生效策略）全部由本模块
拥有；WebUI 只能消费这里生成的 metadata，CLI/config 模块不依赖 WebUI。

配置模块通过 :func:`schema_default` 取得默认值，环境覆盖通过
``config.env_loader.apply_env_overrides`` 走本 registry。请求处理不再读取
``config/*.py`` 源码；源码 AST 解析仅保留在旧兼容 helper 中。
"""
from __future__ import annotations

import copy
import math
import os
import re
import threading
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class ConfigValidationError(ValueError):
    """候选配置不符合 schema 时抛出的稳定异常。"""

    def __init__(self, errors: Mapping[str, str] | str):
        if isinstance(errors, str):
            normalized = {"__config__": errors}
        else:
            normalized = {str(key): str(value) for key, value in errors.items()}
        self.errors = MappingProxyType(dict(normalized))
        message = "; ".join(f"{key}: {value}" for key, value in normalized.items())
        super().__init__(message or "配置校验失败")


@dataclass(frozen=True)
class ConfigOption:
    value: str
    label: str


@dataclass(frozen=True)
class ConfigField:
    """一个可配置字段的完整 schema。"""

    key: str
    file: str | None
    type: str
    default: Any
    group: str
    label: str
    help: str
    storage: str = "env"
    options: tuple[ConfigOption, ...] = ()
    min_value: int | float | None = None
    max_value: int | float | None = None
    secret: bool = False
    aliases: Mapping[str, str] = dataclass_field(default_factory=lambda: MappingProxyType({}))
    restart: bool = False
    hot_edit: str = "safe"
    allow_prefix: str | None = None
    csv_options: tuple[str, ...] = ()
    editable: bool = True

    @property
    def module(self) -> str | None:
        if not self.file:
            return None
        return f"config.{Path(self.file).stem}"

    @property
    def range(self) -> dict[str, int | float]:
        out: dict[str, int | float] = {}
        if self.min_value is not None:
            out["min"] = self.min_value
        if self.max_value is not None:
            out["max"] = self.max_value
        return out

    def clone_default(self) -> Any:
        return copy.deepcopy(self.default)

    def public_value(self, value: Any) -> Any:
        """规范化只用于展示/API 的值，不改变兼容模块中的旧别名。"""
        if self.type != "str" or not isinstance(value, str):
            return copy.deepcopy(value)
        return self.aliases.get(value.strip(), value.strip())

    def metadata(self) -> dict[str, Any]:
        """转换为前端可直接消费的字段元数据。"""
        out: dict[str, Any] = {
            "key": self.key,
            "file": self.file,
            "module": self.module,
            "type": self.type,
            "default": self.clone_default(),
            "group": self.group,
            "label": self.label,
            "help": self.help,
            "storage": self.storage,
            "secret": self.secret,
            "aliases": dict(self.aliases),
            "restart": self.restart,
            "requires_restart": self.restart,
            "hot_edit": self.hot_edit,
            "editable": self.editable,
        }
        if self.options:
            out["options"] = [
                {"value": option.value, "label": option.label}
                for option in self.options
            ]
        if self.range:
            out["range"] = self.range
            if "min" in self.range:
                out["min"] = self.range["min"]
            if "max" in self.range:
                out["max"] = self.range["max"]
        if self.allow_prefix:
            out["allow_prefix"] = self.allow_prefix
        if self.csv_options:
            out["csv_options"] = list(self.csv_options)
        return out


@dataclass(frozen=True)
class ConfigResolution:
    value: Any
    source: str
    source_key: str | None = None
    configured: bool = False
    invalid: bool = False


def _option(value: str, label: str | None = None) -> ConfigOption:
    return ConfigOption(value, label or value)


def _options(*items: tuple[str, str] | str) -> tuple[ConfigOption, ...]:
    return tuple(
        _option(item[0], item[1]) if isinstance(item, tuple) else _option(item)
        for item in items
    )


# 默认值集中在这里。配置模块只保留兼容常量名，并通过 schema_default() 取值。
_DEFAULTS: dict[str, Any] = {
    "ACCOUNT_BATCH_WORKERS": 3,
    "EMAIL_BUTLER_RISK_SCAN_ENABLED": True,
    "EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS": 21600,
    "AT_AUTO_REFRESH_ENABLED": True,
    "AT_REFRESH_SCAN_INTERVAL_SECONDS": 3600,
    "CODEX_TOKEN_AUTO_REFRESH_ENABLED": True,
    "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS": 86400,
    "WEBUI_AUTH_CODE": "",
    "WEBUI_SESSION_SECRET": "",
    "ENABLE_CODEX_AUTO": False,
    "OPENAI_PROTOCOL_VERSION": "v1",
    "REGISTRATION_DRIVER": "roxy",
    "REGISTRATION_AUTH_MODE": "otp",
    "REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS": 60,
    "REGISTRATION_PLAN_CHECK_ENABLED": True,
    "ACCOUNT_COMPLETION_PASSWORD_ENABLED": True,
    "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED": True,
    "ACCOUNT_COMPLETION_2FA_ENABLED": True,
    "ACCOUNT_COMPLETION_CODEX_ENABLED": True,
    "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED": False,
    "ACCOUNT_PASSWORD_RESET_ENABLED": False,
    "ACCOUNT_PASSWORD_DRIVER": "roxy",
    "ACCOUNT_PLAN_CHECK_DRIVER": "protocol",
    "ACCOUNT_PASSWORD_PROXY_MODE": "registration",
    "ACCOUNT_2FA_PROXY_MODE": "registration",
    "ACCOUNT_PLAN_CHECK_PROXY_MODE": "direct",
    "ACCOUNT_LIVE_CHECK_PROXY_MODE": "direct",
    "ACCOUNT_REFRESH_AT_PROXY_MODE": "registration",
    "ACCOUNT_CODEX_PROXY_MODE": "registration",
    "ACCOUNT_EMAIL_CHANGE_ENABLED": True,
    "ACCOUNT_EMAIL_CHANGE_PROXY_MODE": "registration",
    "ACCOUNT_LIVE_CHECK_DRIVER": "protocol_current",
    "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED": False,
    "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK": False,
    "ACCOUNT_AUTH_PROFILE_MODE": "current",
    "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED": False,
    "ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS": 30,
    "LIVE_CHECK_ROXY_FALLBACK_ENABLED": True,
    "ACCOUNT_2FA_DRIVER": "auto",
    "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED": True,
    "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED": True,
    "ACCOUNT_CODEX_DRIVER": "same_as_registration",
    "REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS": 1800,
    "REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED": True,
    "REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT": 80,
    "REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB": 32,
    "REGISTRATION_DEBUG_MAX_HELD_SESSIONS": 16,
    "REGISTRATION_DEBUG_BODY_MAX_KB": 1024,
    "REGISTRATION_DEBUG_BODY_BUDGET_MB": 128,
    "REGISTRATION_DEBUG_GLOBAL_BUDGET_MB": 5120,
    "REGISTRATION_DEBUG_RETENTION_DAYS": 7,
    "REGISTRATION_DEBUG_QUEUE_SIZE": 20000,
    "ROXY_API_BASE": "http://127.0.0.1:50100",
    "ROXY_API_TOKEN": "",
    "ROXY_PROFILE_ID": "",
    "ROXY_WORKSPACE_ID": "90143",
    "ROXY_PROJECT_ID": "97471",
    "ROXY_WORKSPACE_LIST_PATH": "/browser/workspace",
    "ROXY_OPEN_PATH": "/browser/open",
    "ROXY_OPEN_HEADLESS": False,
    "ROXY_CODEX_OPEN_HEADLESS": False,
    "ROXY_CLOSE_PATH": "/browser/close",
    "ROXY_KEEP_BROWSER_OPEN": False,
    "ROXY_WINDOW_WAIT_TIMEOUT": 900,
    "ROXY_WINDOW_WAIT_INTERVAL": 10,
    "ROXY_ONE_PROFILE_PER_ACCOUNT": True,
    "ROXY_REUSE_ACCOUNT_PROFILE": True,
    "ROXY_DELETE_PROFILE_AFTER_RUN": False,
    "ROXY_RANDOM_OS_ON_CREATE": True,
    "ROXY_RANDOM_OS_CHOICES": "Windows,macOS",
    "ROXY_RANDOM_PROFILE_NAME_ON_CREATE": True,
    "ROXY_PROFILE_NAME_PREFIX": "rb",
    "ROXY_CREATE_USE_PROXY_POOL": False,
    "ROXY_PROXY_CHECK_CHANNEL": "IPRust.io",
    "ROXY_DELETE_PATH": "/browser/delete",
    "CODEX_OAUTH_DRIVER": "roxy",
    "CODEX_TOKEN_REFRESH_BEFORE_HOURS": 24,
    "CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS": 120,
    "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE": 20,
    "CODEX_TOKEN_AUTO_SYNC_SUB2API": True,
    "ROXY_CODEX_CALLBACK_TIMEOUT": 180,
    "ENABLE_2FA": False,
    "TWOFA_DRIVER": "auto",
    "ENABLE_FLOW_TRIGGER": False,
    "ENABLE_HUMANIZE_DELAY": True,
    "HUMANIZE_DELAY_FACTOR": 1.0,
    "ENABLE_HUMANIZE_BROWSER_ACTIONS": True,
    "USE_EMAIL_SERVICE": False,
    "REGISTER_EMAIL": "",
    "REGISTER_NAME": "",
    "OTP_MAX_WAIT": 240,
    "OTP_POLL_INTERVAL": 3,
    "EMAIL_SOURCE": "outlook,generic_api,mailnest",
    "EMAIL_BUTLER_API_BASE": "",
    "EMAIL_BUTLER_API_KEY": "",
    "EMAIL_BUTLER_REQUEST_TIMEOUT": 20,
    "GPTMAIL_API_KEY": "",
    "CLOUDFLARE_API_BASE": "",
    "CLOUDFLARE_API_KEY": "",
    "CLOUDFLARE_SIGNAL_API_KEY": "",
    "CLOUDFLARE_SIGNAL_PATH": "/signals/scan",
    "CLOUDFLARE_AUTH_MODE": "none",
    "CLOUDFLARE_CUSTOM_AUTH": "",
    "CLOUDFLARE_PATH_ACCOUNTS": "/api/new_address",
    "CLOUDFLARE_PATH_MESSAGES": "/api/mails",
    "CLOUDFLARE_PATH_DOMAINS": "/api/domains",
    "CLOUDFLARE_PATH_TOKEN": "/api/token",
    "CLOUDFLARE_DEFAULT_DOMAINS": [],
    "CLOUDFLARE_REQUEST_TIMEOUT": 20,
    "CLOUDFLARE_NAME_LENGTH": 10,
    "OUTLOOK_FETCH_MODE": "auto",
    "EMAIL_DOMAIN": "",
    "QQ_EMAIL": "",
    "QQ_IMAP_PASSWORD": "",
    "MAIL_NEST_API_KEY": "",
    "MAIL_NEST_PROJECT_CODE": "chatgpt001",
    "CLOUDMAIL_API_BASE": "",
    "CLOUDMAIL_ADMIN_EMAIL": "",
    "CLOUDMAIL_PASSWORD": "",
    "CLOUDMAIL_TOKEN_PATH": "/api/public/genToken",
    "CLOUDMAIL_AUTH_TOKEN": "",
    "CLOUDMAIL_DOMAINS": [],
    "CLOUDMAIL_AUTO_ADD_USER": True,
    "CLOUDMAIL_RANDOM_LOCAL_LENGTH": 12,
    "ICLOUD_HME_API_BASE": "http://127.0.0.1:8081",
    "ICLOUD_HME_ACCOUNT_ID": "",
    "ICLOUD_HME_API_TOKEN": "",
    "ICLOUD_HME_REQUEST_TIMEOUT": 35,
    "ICLOUD_HME_SYNC_TTL": 300,
    "ICLOUD_HME_INBOX_MODE": "sidecar",
    "ICLOUD_HME_FORWARD_IMAP_SERVER": "imap.gmail.com",
    "ICLOUD_HME_FORWARD_IMAP_PORT": 993,
    "ICLOUD_HME_FORWARD_IMAP_EMAIL": "",
    "ICLOUD_HME_FORWARD_IMAP_PASSWORD": "",
    "ICLOUD_HME_AUTO_CREATE": False,
    "ICLOUD_HME_CREATE_LABEL_PREFIX": "turb",
    "BROWSER_LOCALE_PROFILE": "jp",
    "AUTO_BROWSER_LOCALE_FROM_IP": True,
    "IP_GEO_TIMEOUT": 6.0,
    "BROWSER_DATA_SAVER_MODE": False,
    "BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES": ["image", "media"],
    "BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS": [
        "**://auth.openai.com/awe/api/v2/rum**",
        "**://chatgpt.com/ces/statsc/flush**",
        "**://connect.facebook.net/**",
        "**://analytics.tiktok.com/**",
        "**://snap.licdn.com/**",
        "**://bat.bing.com/**",
        "**://accounts.google.com/gsi/client**",
        "**://*/favicon.ico**",
        "**://chatgpt.com/ces/v1/rgstr**",
        "**://chatgpt.com/cdn/assets/*.js**",
    ],
    "REGISTRATION_PROXY_MODE": "pool",
    "PROXY_1024_API_URL": "",
    "PROXY_1024_REGION": "",
    "PROXY_1024_PROTOCOL": "http",
    "PROXY_1024_SESSION_MINUTES": 30,
    "PROXY_1024_ROTATE_SESSION_TIME": True,
    "PROXY_1024_API_TIMEOUT": 12.0,
    "PROXY_1024_MAX_ATTEMPTS": 5,
    "PROXY_1024_ACQUIRE_TIMEOUT": 60.0,
    "REGISTRATION_PROXY_RETRIES": 2,
    "REGISTRATION_PROXY_RETRY_DELAY": 1.0,
    "ACCOUNT_ACTION_PROXY_RETRIES": 2,
    "ACCOUNT_ACTION_PROXY_RETRY_DELAY": 1.0,
    "PROXY_1024_VALIDATE": True,
    "PROXY_1024_VALIDATE_ATTEMPTS": 2,
    "PROXY_1024_RECENT_TTL": 1800,
    "PROXY_1024_ACQUIRE_INTERVAL": 0.6,
    "PROXY_POOL": ["socks5://127.0.0.1:7897"],
    "PLAN_CHECK_PROXY_MODE": "auto",
    "PLAN_CHECK_PROXY": "",
    "ACCOUNT_ACTION_PROXY_MODE": "registration",
    "ACCOUNT_ACTION_PROXY": "",
    "PLAN_CHECK_TIMEOUT": 15.0,
    "PLAN_CHECK_MAX_ATTEMPTS": 2,
    "PLAN_CHECK_RETRY_DELAY": 1.5,
    "PLAN_CHECK_REGISTRATION_RECHECK_DELAY": 2.0,
    "PLAN_CHECK_WORKERS": 3,
    "PLAN_CHECK_QUEUE_LIMIT": 500,
    "PLAN_CHECK_MIN_INTERVAL": 0.4,
    "PLAN_CHECK_JITTER": 0.3,
    "EXTRACT_LINK_API_BASE": "https://ple.bzb.qzz.io",
    "EXTRACT_LINK_CDK": "",
    "EXTRACT_LINK_TYPE": "pix",
    "SUB2API_API_BASE": "",
    "SUB2API_API_KEY": "",
    "SUB2API_API_TIMEOUT": 20,
    "CODEX_AUTH_URL_SOURCE": "cpa",
    "CPA_MANAGEMENT_URL": "http://127.0.0.1:8317/management.html",
    "CPA_MANAGEMENT_KEY": "",
    "CPA_REQUEST_TIMEOUT": 30,
    "CPA_CREDENTIAL_CONFIRM_TIMEOUT": 12,
    "CPA_SAVE_CALLBACK_RECEIPT": True,
    "SMS_PROVIDER": "l",
    "SMS_COUNTRY": "10",
    "SMS_SERVICE": "openai",
    "SMS_MAX_PRICE": "",
    "SMS_AUTO_SELECT_COUNTRY": True,
    "SMS_AUTO_COUNTRY_MIN_RATIO": 25,
    "SMS_MAX_RETRIES": 10,
    "SMS_CODE_WAIT": 120,
    "CODEX_PHONE_TOTAL_TIMEOUT": 300,
    "SMS_API_KEY": "",
    "H_API_BASE": "http://localhost:8788",
    "H_ADMIN_AUTH_CODE": "",
    "H_PHONE_PREFIX": "",
    "H_PHONE_ACQUIRE_MODE": "reusable",
    "L_API_BASE": "http://localhost:8788",
    "L_ADMIN_AUTH_CODE": "",
    "L_PHONE_PREFIX": "",
}


_FIELD_DEFINITIONS = [
    # ---- 通用配置 ----
    {
        "key": "ACCOUNT_BATCH_WORKERS", "file": "codex.py", "type": "int", "group": "通用配置",
        "label": "账号操作并发数", "help": "账号补全、补密码、补 2FA、查套餐、查活、刷新 AT、查封号邮件、Codex 和提链共用的并发数，范围 1-16；注册线程数另行设置",
    },
    # ---- 定时任务 ----
    {
        "key": "EMAIL_BUTLER_RISK_SCAN_ENABLED", "file": "email.py", "type": "bool", "group": "定时任务",
        "label": "自动查封号邮件", "help": "周期扫描支持的邮箱来源，识别 OpenAI 封号通知；关闭后仍可在账号页手动触发",
    },
    {
        "key": "EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS", "file": "email.py", "type": "int", "group": "定时任务",
        "label": "查封号邮件间隔（秒）", "help": "两轮扫描之间的最短间隔，范围 900-604800；默认 21600（6 小时）",
    },
    {
        "key": "AT_AUTO_REFRESH_ENABLED", "file": "codex.py", "type": "bool", "group": "定时任务",
        "label": "自动刷新账号 AT", "help": "临近过期时自动刷新 ChatGPT accessToken；关闭后仍可在账号页手动刷新",
    },
    {
        "key": "AT_REFRESH_SCAN_INTERVAL_SECONDS", "file": "codex.py", "type": "int", "group": "定时任务",
        "label": "刷新账号 AT 间隔（秒）", "help": "两轮扫描之间的最短间隔，范围 300-86400；默认 3600（1 小时）",
    },
    # ---- WebUI 授权 ----
    {
        "key": "WEBUI_AUTH_CODE", "file": "codex.py", "type": "str", "group": "WebUI 授权",
        "label": "WebUI 授权码", "help": "仅保存在 .env（WEBUI_AUTH_CODE），避免出现在进程命令行中；保存后重启 WebUI 生效",
        "storage": "env", "secret": True,
    },
    {
        "key": "WEBUI_SESSION_SECRET", "file": "codex.py", "type": "str", "group": "WebUI 授权",
        "label": "Session 签名密钥", "help": "可选，保存在 .env（WEBUI_SESSION_SECRET）；不填则从固定授权码派生，修改授权码会使已有登录失效",
        "storage": "env", "secret": True,
    },
    # ---- 注册主链路 ----
    {
        "key": "ENABLE_CODEX_AUTO", "file": "codex.py", "type": "bool", "group": "注册主链路",
        "label": "启用 Codex OAuth", "help": "注册成功后自动跑 Codex 授权（全新session+接码），落盘 codex-邮箱.json",
    },
    {
        "key": "OPENAI_PROTOCOL_VERSION", "file": "openai_protocol.py", "type": "str", "group": "账号补全",
        "label": "刷新 AT 协议版本", "help": "仅用于账号补全中的刷新 AT；v1/v2 选择对应协议实现，注册、2FA、套餐、普通查活等步骤不读取此配置。",
    },
    {
        "key": "REGISTRATION_DRIVER", "file": "roxybrowser.py", "type": "str", "group": "注册主链路",
        "label": "注册主流程驱动", "help": "选择注册所用的自动化方式：roxy=浏览器主流程，protocol=协议辅助/回退；默认推荐 roxy",
    },
    {
        "key": "REGISTRATION_AUTH_MODE", "file": "register.py", "type": "str", "group": "注册主链路",
        "label": "注册认证方式", "help": "otp=只用邮箱一次性验证码；password=设置并保存账号密码。选择 password 才会执行密码注册，但仍可能需要邮箱验证码",
    },
    {
        "key": "REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS", "file": "register.py", "type": "int", "group": "注册主链路",
        "label": "密码提交跳转等待(秒)", "help": "从点击创建密码页的继续按钮后独立计时；默认 60 秒，避免慢代理下页面迟到进入邮箱验证码页却被提前判失败",
    },
    {
        "key": "REGISTRATION_PLAN_CHECK_ENABLED", "file": "register.py", "type": "bool", "group": "注册主链路",
        "label": "注册后自动查套餐", "help": "注册核心保存后独立查询套餐；关闭后不影响账号落库，之后可在账号管理中手动查询或补全",
    },
    # ---- 账号补全策略 ----
    {
        "key": "ACCOUNT_COMPLETION_PASSWORD_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全账号密码", "help": "“补全账号”发现账号缺少登录密码时补充；关闭后不会处理密码",
    },
    {
        "key": "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全套餐状态", "help": "“补全账号”发现套餐未成功确认时补查；关闭后不会处理套餐",
    },
    {
        "key": "ACCOUNT_COMPLETION_2FA_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全 Authenticator 2FA", "help": "“补全账号”发现账号缺少 Authenticator 2FA 时启用；关闭后不会处理 2FA",
    },
    {
        "key": "ACCOUNT_COMPLETION_CODEX_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全 Codex", "help": "“补全账号”发现 Codex 未完成时提交 Codex OAuth；关闭后不会处理 Codex",
    },
    {
        "key": "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全时允许刷新 AT", "help": "默认关闭。开启后仅对已完成注册但缺少/无法使用 AT 的账号允许刷新；注册尚未完成的账号会优先继续原注册任务，不会刷新 AT",
    },
    {
        "key": "ACCOUNT_PASSWORD_RESET_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "允许邮箱重置账号密码", "help": "默认关闭。开启后，账号补全登录时若本地没有 OpenAI 密码，会点击忘记密码、读取邮箱验证码并设置新密码；只影响账号补全，不影响注册、查活和刷新 AT",
    },
    {
        "key": "ACCOUNT_PASSWORD_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "密码补全驱动", "help": "当前唯一实现为 RoxyBrowser，暂不可切换",
    },
    {
        "key": "ACCOUNT_EMAIL_CHANGE_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "启用协议邮箱换绑", "help": "只通过 BrowserSession HTTP 协议执行邮箱换绑；远端结果不确定时不会自动打开浏览器兜底",
    },
    {
        "key": "ACCOUNT_PLAN_CHECK_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "套餐补全驱动", "help": "当前唯一实现为纯协议，暂不可切换",
    },
    {
        "key": "ACCOUNT_PASSWORD_PROXY_MODE", "file": "account.py", "type": "str", "group": "代理与网络",
        "label": "补密码代理来源", "help": "registration=跟随注册线路；direct=直连；pool=静态代理池；provider:<id>=指定代理提供商。密码认证默认跟随注册线路。",
    },
    {
        "key": "ACCOUNT_2FA_PROXY_MODE", "file": "account.py", "type": "str", "group": "代理与网络",
        "label": "补 2FA 代理来源", "help": "registration=跟随注册线路；direct=直连；pool=静态代理池；provider:<id>=指定代理提供商。",
    },
    {
        "key": "ACCOUNT_PLAN_CHECK_PROXY_MODE", "file": "account.py", "type": "str", "group": "代理与网络",
        "label": "查套餐代理来源", "help": "默认 direct。查套餐只读现有 Token，可按需选择 registration、pool 或 provider:<id>。",
    },
    {
        "key": "ACCOUNT_LIVE_CHECK_PROXY_MODE", "file": "account.py", "type": "str", "group": "代理与网络",
        "label": "查活代理来源", "help": "默认 direct。普通查活只验证现有 Token，不登录、不发 OTP、不刷新 AT。",
    },
    {
        "key": "ACCOUNT_REFRESH_AT_PROXY_MODE", "file": "account.py", "type": "str", "group": "代理与网络",
        "label": "刷新 AT 代理来源", "help": "默认 registration。刷新 AT 会重新认证并可能读取邮箱验证码，建议使用注册同类线路。",
    },
    {
        "key": "ACCOUNT_CODEX_PROXY_MODE", "file": "account.py", "type": "str", "group": "代理与网络",
        "label": "Codex OAuth 代理来源", "help": "默认 registration。可选 direct、pool 或 provider:<id>。",
    },
    {
        "key": "ACCOUNT_EMAIL_CHANGE_PROXY_MODE", "file": "account.py", "type": "str", "group": "代理与网络",
        "label": "邮箱换绑代理来源", "help": "默认 registration。邮箱换绑使用独立用途线路，可选 direct、pool 或 provider:<id>。",
    },
    {
        "key": "ACCOUNT_LIVE_CHECK_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "普通查活驱动", "help": "可选 protocol_current 或 browser_roxy；browser_roxy 只验证已有 AT，不登录、不发 OTP、不刷新 AT；全局协议版本设置不影响普通查活",
    },
    {
        "key": "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "开放 Roxy 普通查活", "help": "灰度开关，默认关闭；开启后才允许将普通查活驱动设为 browser_roxy，且仍只验证已有 AT",
    },
    {
        "key": "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "密码错误后邮箱兜底", "help": "默认关闭；开启后仅在新认证会话由远端明确进入邮箱验证码 challenge 时继续，不从密码页盲发 OTP；结果仍保留 password_rejected，不重试密码",
    },
    {
        "key": "ACCOUNT_AUTH_PROFILE_MODE", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "Protocol 设备画像", "help": "current 保持现状、每次会话随机设备画像；account_stable 仅在实际使用 v2 协议刷新时按账号懒创建稳定画像，不影响注册 device_id、普通查活和 v1 刷新链路",
    },
    {
        "key": "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "保存认证原始上下文", "help": "默认关闭；开启后仅为 v2 协议实际认证 run 按白名单保存设备 ID、session 标识和代理上下文到受限私有表，不进入普通 API/导出；不会复用过期代理",
    },
    {
        "key": "ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", "file": "account.py", "type": "int", "group": "账号补全",
        "label": "认证上下文保留天数", "help": "原始认证上下文的自动清理周期，默认 30 天；设置为 0 表示不自动清理，仍可手工逐行清理",
    },
    {
        "key": "LIVE_CHECK_ROXY_FALLBACK_ENABLED", "file": "proxy.py", "type": "bool", "group": "账号补全",
        "label": "刷新 Roxy 兜底", "help": "仅控制 v1 协议刷新 AT 失败后的既有 Roxy 登录兜底；不影响普通查活，也不允许普通查活登录或发送 OTP",
    },
    {
        "key": "ACCOUNT_2FA_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "2FA 补全驱动", "help": "auto=自动选择（优先复用有效 AT，需要时协议重认证；组合补密码时复用浏览器会话拿新 AT）；protocol=协议开通并按配置回退浏览器；browser=直接浏览器",
    },
    {
        "key": "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "2FA 协议失败后浏览器兜底", "help": "仅用于账号补全；auto/protocol 失败后是否允许打开 Roxy 安全设置页面，默认开启",
    },
    {
        "key": "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "2FA 需要时协议重认证", "help": "仅用于 auto/protocol；没有可复用 AT 或旧 AT 被 MFA 接口要求近期认证时，先走协议邮箱 OTP 换新 AT，再继续开通；默认开启",
    },
    {
        "key": "ACCOUNT_CODEX_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "Codex 补全驱动", "help": "可选纯协议、RoxyBrowser 或跟随注册主流程；三种路由都由 Codex OAuth 执行器处理",
    },
    # ---- 注册调试 ----
    {
        "key": "REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "失败现场保留（秒）", "help": "调试任务最终失败后保留浏览器和代理的最长时间；默认 1800（30 分钟）",
    },
    {
        "key": "REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED", "file": "registration_debug.py", "type": "bool", "group": "注册调试",
        "label": "普通模式失败诊断", "help": "普通注册失败时保存脱敏页面现场、失败请求元数据和浏览器错误；不会抓取成功请求或暂停浏览器",
    },
    {
        "key": "REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "失败资源记录上限", "help": "普通模式失败现场最多保存的资源时序条数；默认 80",
    },
    {
        "key": "REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "失败页面文本上限（KB）", "help": "普通模式失败现场最多保存的页面可见文本大小；默认 32",
    },
    {
        "key": "REGISTRATION_DEBUG_MAX_HELD_SESSIONS", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "最大保留现场数", "help": "允许同时暂停保留的失败浏览器数量；超出后仍保存抓包但自动关闭现场",
    },
    {
        "key": "REGISTRATION_DEBUG_BODY_MAX_KB", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "单正文上限（KB）", "help": "单个文本、HTML 或 JSON 请求/响应正文的最大保存大小",
    },
    {
        "key": "REGISTRATION_DEBUG_BODY_BUDGET_MB", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "单任务正文预算（MB）", "help": "达到预算后继续记录全部请求元数据，但不再保存正文",
    },
    {
        "key": "REGISTRATION_DEBUG_GLOBAL_BUDGET_MB", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "抓包总预算（MB）", "help": "调试目录超过软上限后，新任务自动降级为只记录请求元数据",
    },
    {
        "key": "REGISTRATION_DEBUG_RETENTION_DAYS", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "抓包保留天数", "help": "WebUI 启动时逐文件清理超过此天数的调试产物",
    },
    {
        "key": "REGISTRATION_DEBUG_QUEUE_SIZE", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "单任务事件队列", "help": "默认 20000；队列满时丢弃后续抓包事件并计数，不阻塞注册线程",
    },

    {
        "key": "ROXY_API_BASE", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy API 地址", "help": "默认 http://127.0.0.1:50000；需在 Roxy 应用 API 配置中开启",
    },
    {
        "key": "ROXY_API_TOKEN", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy API Key", "help": "保存在 .env（ROXY_API_TOKEN），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "ROXY_PROFILE_ID", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy 环境ID", "help": "指定要打开的 Roxy 浏览器环境/Profile ID；留空则尝试创建临时环境",
    },
    {
        "key": "ROXY_WORKSPACE_ID", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy 工作区ID", "help": "创建一号一环境时必填，会作为 workspaceId 提交给 Roxy 创建 Profile 接口",
    },
    {
        "key": "ROXY_PROJECT_ID", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy 项目ID", "help": "从 /browser/workspace 的 project_details.projectId 获取；创建 Profile 时会作为 projectId 提交",
    },
    {
        "key": "ROXY_WORKSPACE_LIST_PATH", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "获取团队接口", "help": "默认 /browser/workspace；点击获取团队/项目时会先试此路径，再自动尝试常见兼容路径",
    },
    {
        "key": "ROXY_OPEN_PATH", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "打开接口路径", "help": "默认 /browser/open；如 Roxy 版本不同可在此调整",
    },
    {
        "key": "ROXY_OPEN_HEADLESS", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "无头启动窗口", "help": "打开 Roxy 环境时向 /browser/open 传 headless；False=显示窗口，True=无头启动",
    },
    {
        "key": "ROXY_CODEX_OPEN_HEADLESS", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "Codex OAuth 无头启动", "help": "Codex OAuth 单独控制窗口渲染；默认 False=显示窗口，避免授权确认页在无头模式下无法完成",
    },
    {
        "key": "ROXY_CLOSE_PATH", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "关闭接口路径", "help": "默认 /browser/close",
    },
    {
        "key": "ROXY_KEEP_BROWSER_OPEN", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "保留浏览器", "help": "调试时可开启，任务结束后不自动关闭 Roxy 环境",
    },
    {
        "key": "ROXY_WINDOW_WAIT_TIMEOUT", "file": "roxybrowser.py", "type": "int", "group": "RoxyBrowser",
        "label": "窗口满等待上限(秒)", "help": "Roxy 返回窗口额度不足时保持当前任务等待的最长时间；默认 900 秒，避免快速失败并启动全部排队任务",
    },
    {
        "key": "ROXY_WINDOW_WAIT_INTERVAL", "file": "roxybrowser.py", "type": "int", "group": "RoxyBrowser",
        "label": "窗口满重试间隔(秒)", "help": "等待 Roxy 空闲窗口时重新尝试创建环境的间隔；默认 10 秒",
    },
    {
        "key": "ROXY_ONE_PROFILE_PER_ACCOUNT", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "一号一环境", "help": "每个账号最多绑定一个 Roxy Profile；没有绑定时才创建新环境",
    },
    {
        "key": "ROXY_REUSE_ACCOUNT_PROFILE", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "复用账号环境", "help": "注册续跑和账号级浏览器操作优先打开账号已绑定的 Roxy Profile",
    },
    {
        "key": "ROXY_DELETE_PROFILE_AFTER_RUN", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "结束后删除环境", "help": "高风险开关；默认关闭。开启后删除本轮新建的 Roxy Profile，即使已绑定账号",
    },
    {
        "key": "ROXY_RANDOM_OS_ON_CREATE", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "创建环境随机OS", "help": "创建 Roxy 环境时每次在 Windows / macOS 中随机，不固定 macOS",
    },
    {
        "key": "ROXY_RANDOM_OS_CHOICES", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "随机OS范围", "help": "逗号分隔，默认 Windows,macOS；Roxy 支持 Windows / macOS / Linux / IOS / Android",
    },
    {
        "key": "ROXY_RANDOM_PROFILE_NAME_ON_CREATE", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "创建环境随机名称", "help": "创建 Roxy 环境时自动生成不同名称，避免固定 gpt-free-register",
    },
    {
        "key": "ROXY_PROFILE_NAME_PREFIX", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "随机名称前缀", "help": "默认 rb；实际名称格式类似 rb-时间戳-随机码",
    },
    {
        "key": "ROXY_CREATE_USE_PROXY_POOL", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "创建环境使用代理池", "help": "仅用于静态「代理池」模式；选择 1024Proxy 时会自动把每个任务的独立家宽租约写入 Roxy proxyInfo，且优先于此开关",
    },
    {
        "key": "ROXY_PROXY_CHECK_CHANNEL", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "代理检测通道", "help": "写入 Roxy proxyInfo.checkChannel；留空则不传，默认 IPRust.io",
    },
    {
        "key": "ROXY_DELETE_PATH", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "删除接口路径", "help": "默认 /browser/delete；如 Roxy 版本不同可调整",
    },
    {
        "key": "CODEX_OAUTH_DRIVER", "file": "codex.py", "type": "str", "group": "注册主链路",
        "label": "Codex 授权驱动", "help": "选择 Codex OAuth 所用的自动化方式：protocol=纯协议，roxy=浏览器，same_as_registration=跟随注册主流程驱动",
    },
    {
        "key": "CODEX_TOKEN_AUTO_REFRESH_ENABLED", "file": "codex.py", "type": "bool", "group": "Codex",
        "label": "自动刷新 OAuth Token", "help": "进入到期窗口后使用 refresh_token 换新 access token；不重新登录，不收邮箱或短信验证码",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_BEFORE_HOURS", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "提前刷新(小时)", "help": "Codex access token 距离过期多少小时开始自动刷新，默认 24",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "刷新巡检间隔(秒)", "help": "后台检查 Codex OAuth 到期状态的间隔，默认 86400 秒（每天一次），最小按 300 秒执行",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "启动后首次巡检(秒)", "help": "WebUI 启动后等待多久执行第一次 Codex OAuth 到期巡检",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "单轮最多刷新", "help": "每轮自动巡检最多加入队列的 Codex 凭证数量",
    },
    {
        "key": "CODEX_TOKEN_AUTO_SYNC_SUB2API", "file": "codex.py", "type": "bool", "group": "Codex",
        "label": "刷新后同步 sub2api", "help": "仅对曾由当前页面成功上传过 sub2api 的凭证自动更新，避免 refresh_token 轮换后 sub2api 仍使用旧值",
    },
    {
        "key": "ROXY_CODEX_CALLBACK_TIMEOUT", "file": "roxybrowser.py", "type": "int", "group": "RoxyBrowser",
        "label": "Codex回调超时", "help": "Roxy Codex OAuth 等待 localhost:1455 callback 的最长秒数",
    },
    {
        "key": "ENABLE_2FA", "file": "twofa.py", "type": "bool", "group": "注册主链路",
        "label": "启用 2FA(TOTP)", "help": "注册完成后自动设置动态口令（会多收一封 OTP 邮件）",
    },
    {
        "key": "TWOFA_DRIVER", "file": "twofa.py", "type": "str", "group": "注册主链路",
        "label": "2FA 开通方式", "help": "auto=自动选择（协议优先）；protocol=协议开通并按现有流程回退；browser=直接用 RoxyBrowser 安全设置页面",
    },
    {
        "key": "ENABLE_FLOW_TRIGGER", "file": "flow_trigger.py", "type": "bool", "group": "注册主链路",
        "label": "启用 Flow 触发", "help": "注册成功后自动调用内部 Flow 接口（不影响注册结果）",
    },
    {
        "key": "ENABLE_HUMANIZE_DELAY", "file": "humanize.py", "type": "bool", "group": "人工节奏",
        "label": "启用随机停顿", "help": "在注册、OTP、授权等步骤之间加入随机等待，更接近人工操作节奏",
    },
    {
        "key": "HUMANIZE_DELAY_FACTOR", "file": "humanize.py", "type": "float", "group": "人工节奏",
        "label": "停顿倍率", "help": "随机停顿整体倍率；1.0=默认，0.5=减半，2.0=加倍",
    },
    {
        "key": "ENABLE_HUMANIZE_BROWSER_ACTIONS", "file": "humanize.py", "type": "bool", "group": "人工节奏",
        "label": "浏览器动作随机化", "help": "Roxy 点击、输入、页面观察使用随机鼠标落点和逐字输入，降低机械操作痕迹",
    },
    # ---- 邮箱 / OTP ----
    {
        "key": "USE_EMAIL_SERVICE", "file": "email.py", "type": "bool", "group": "邮箱 / OTP",
        "label": "自动取邮箱+收码", "help": "True=从邮箱池自动领邮箱并自动收 OTP；False=手动模式：用 REGISTER_EMAIL，OTP 在任务页手填",
    },
    {
        "key": "REGISTER_EMAIL", "file": "register.py", "type": "str", "group": "邮箱 / OTP",
        "label": "手动注册邮箱", "help": "USE_EMAIL_SERVICE=False 时必填。例如你的 outlook.com 地址；OTP 去网页邮箱看，再回任务页提交",
    },
    {
        "key": "REGISTER_NAME", "file": "register.py", "type": "str", "group": "邮箱 / OTP",
        "label": "显示名称", "help": "留空则自动生成英文名",
    },
    {
        "key": "OTP_MAX_WAIT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "OTP 最长等待(秒)", "help": "单轮等待验证码邮件的最长秒数；Email Butler/iCloud 转发建议 240，避免过早重发制造多枚验证码",
    },
    {
        "key": "OTP_POLL_INTERVAL", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "OTP 轮询间隔(秒)", "help": "每隔多少秒查一次新邮件",
    },
    {
        "key": "EMAIL_SOURCE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "邮箱来源", "help": "WebUI 可选来源列表，可填单个或多个并用逗号分隔；开始注册时必须明确选择一个，任务不会跨平台兜底：outlook,generic_api,cloudflare_domain,cloudflare,email_butler,gptmail,mailnest,cloudmail,icloud_hide",
    },
    {
        "key": "EMAIL_BUTLER_API_BASE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Email Butler API 地址", "help": "通用 /v1 根地址，例如 http://127.0.0.1:8788/v1",
        "storage": "env",
    },
    {
        "key": "EMAIL_BUTLER_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Email Butler API Key", "help": "专用客户端 Key；策略在 Butler 端绑定，保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "EMAIL_BUTLER_REQUEST_TIMEOUT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "Email Butler 请求超时(秒)", "help": "单次 HTTP 请求超时，默认 20 秒",
    },
    {
        "key": "GPTMAIL_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "GPTMail API Key", "help": "选择 gptmail 邮箱来源时必填；保存在 .env，不会写入 config 源码",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDFLARE_API_BASE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare API 地址", "help": "Worker 临时邮箱 API 根地址，如 https://mail.example.com；选择 cloudflare 时必填",
        "storage": "env",
    },
    {
        "key": "CLOUDFLARE_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare API Key", "help": "匿名可空；admin 模式填 ADMIN_PASSWORD；保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDFLARE_SIGNAL_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 封号信号 Key", "help": "仅用于查询封号邮件信号，不返回邮件正文；建议使用独立 Key",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDFLARE_SIGNAL_PATH", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 封号信号路径", "help": "默认 /signals/scan",
    },
    {
        "key": "CLOUDFLARE_AUTH_MODE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 鉴权模式", "help": "none / bearer / x-api-key / x-admin-auth / query-key",
    },
    {
        "key": "CLOUDFLARE_CUSTOM_AUTH", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 全局密码", "help": "Worker PASSWORDS，注入 x-custom-auth；保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDFLARE_PATH_ACCOUNTS", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 创建路径", "help": "默认 /api/new_address；admin 常用 /admin/new_address",
    },
    {
        "key": "CLOUDFLARE_PATH_MESSAGES", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 邮件路径", "help": "默认 /api/mails",
    },
    {
        "key": "CLOUDFLARE_PATH_DOMAINS", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 域名路径", "help": "默认 /api/domains（预留）",
    },
    {
        "key": "CLOUDFLARE_PATH_TOKEN", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare Token路径", "help": "默认 /api/token（fallback 预留）",
    },
    {
        "key": "CLOUDFLARE_DEFAULT_DOMAINS", "file": "email.py", "type": "list_str_multiline", "group": "邮箱 / OTP",
        "label": "Cloudflare 默认域名", "help": "收信域名，每行一个或逗号分隔；创建时轮询使用，可留空",
    },
    {
        "key": "CLOUDFLARE_REQUEST_TIMEOUT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "Cloudflare 请求超时(秒)", "help": "HTTP 请求超时，默认 20",
    },
    {
        "key": "CLOUDFLARE_NAME_LENGTH", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "Cloudflare 随机名前缀长度", "help": "admin 创建时 local-part 长度，默认 10",
    },
    {
        "key": "OUTLOOK_FETCH_MODE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Outlook取件模式", "help": "auto=远端优先，远端 402/DEPLOYMENT_DISABLED 自动切 Graph 直连；direct=只用 Microsoft Graph 直连；remote=只用远端服务",
    },
    {
        "key": "EMAIL_DOMAIN", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "转发域名(cloudflare_domain)", "help": "仅 cloudflare_domain 使用：Email Routing 的域名，如 mydomain.com；与 EMAIL_SOURCE=cloudflare 无关",
    },
    {
        "key": "QQ_EMAIL", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "QQ 邮箱地址", "help": "仅 cloudflare_domain：接收 Email Routing 转发的 QQ 邮箱，如 123456@qq.com",
    },
    {
        "key": "QQ_IMAP_PASSWORD", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "QQ 邮箱 IMAP 授权码", "help": "仅 cloudflare_domain：QQ IMAP 授权码，保存在 .env，不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "MAIL_NEST_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "MailNest API Key", "help": "选择 mailnest 邮箱来源时必填；保存在 .env，不会写入 config 源码",
        "storage": "env", "secret": True,
    },
    {
        "key": "MAIL_NEST_PROJECT_CODE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "MailNest 项目代码", "help": "项目代码 默认 chatgpt001 获取页面 mailnest.top/buy-email",
    },
    {
        "key": "CLOUDMAIL_API_BASE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail API 地址", "help": "Cloud Mail Worker/API 地址，例如 https://mail.example.com",
    },
    {
        "key": "CLOUDMAIL_ADMIN_EMAIL", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail管理员邮箱", "help": "用于生成 Token；域名被平台隐藏时也会用它登录读取域名",
        "storage": "env",
    },
    {
        "key": "CLOUDMAIL_PASSWORD", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail 密码", "help": "用于自动获取 Token；保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDMAIL_TOKEN_PATH", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail Token路径", "help": "固定使用 /api/public/genToken；如部署版本不同可修改",
    },
    {
        "key": "CLOUDMAIL_AUTH_TOKEN", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail Token", "help": "CloudMail/Cloud Mail API Authorization Token；保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDMAIL_DOMAINS", "file": "email.py", "type": "list_str_multiline", "group": "邮箱 / OTP",
        "label": "CloudMail 域名列表", "help": "可留空；运行时会自动从平台获取。也可点“获取 CloudMail 域名”缓存到这里",
    },
    {
        "key": "CLOUDMAIL_AUTO_ADD_USER", "file": "email.py", "type": "bool", "group": "邮箱 / OTP",
        "label": "CloudMail自动创建用户", "help": "生成随机邮箱后调用 /api/public/addUser 创建用户",
    },
    {
        "key": "CLOUDMAIL_RANDOM_LOCAL_LENGTH", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "CloudMail随机名前缀长度", "help": "生成邮箱 local-part 的长度，建议 10-16",
    },
    {
        "key": "ICLOUD_HME_API_BASE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "iCloud HME 服务地址", "help": "本机 icloud-hme sidecar 地址，默认 http://127.0.0.1:8081",
        "storage": "env",
    },
    {
        "key": "ICLOUD_HME_ACCOUNT_ID", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "iCloud 固定账号 ID", "help": "sidecar 中的固定账号 ID；留空自动发现并同步全部 active 账号",
        "storage": "env",
    },
    {
        "key": "ICLOUD_HME_API_TOKEN", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "iCloud HME API Token", "help": "本地服务启用鉴权时填写；仅监听 127.0.0.1 时可留空",
        "storage": "env", "secret": True,
    },
    {
        "key": "ICLOUD_HME_REQUEST_TIMEOUT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "iCloud 请求超时(秒)", "help": "同步别名和 IMAP 拉信的单次请求超时，默认 35",
    },
    {
        "key": "ICLOUD_HME_SYNC_TTL", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "iCloud 同步缓存(秒)", "help": "别名池自动同步的缓存时长，默认 300；连接测试会强制同步",
    },
    {
        "key": "ICLOUD_HME_INBOX_MODE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "隐藏邮箱收件模式", "help": "sidecar=iCloud IMAP；forward_imap=本机直接读取 Gmail；forward_butler=Oracle 接收 Gmail 并从 Email Butler PG 缓存取码",
    },
    {
        "key": "ICLOUD_HME_FORWARD_IMAP_SERVER", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "转发 IMAP 服务器", "help": "Gmail 填 imap.gmail.com",
    },
    {
        "key": "ICLOUD_HME_FORWARD_IMAP_PORT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "转发 IMAP 端口", "help": "SSL IMAP 默认 993",
    },
    {
        "key": "ICLOUD_HME_FORWARD_IMAP_EMAIL", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "隐藏邮箱转发到", "help": "Apple HME 的 forwardToEmail；必须与实际 Gmail 地址完全一致",
        "storage": "env",
    },
    {
        "key": "ICLOUD_HME_FORWARD_IMAP_PASSWORD", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Gmail IMAP 应用密码", "help": "forward_imap 模式用于本机直接读取 Gmail；请填写 Gmail 应用专用密码",
        "storage": "env", "secret": True,
    },
    {
        "key": "ICLOUD_HME_AUTO_CREATE", "file": "email.py", "type": "bool", "group": "邮箱 / OTP",
        "label": "库存为空自动创建", "help": "关闭时仅使用已同步别名；开启后池为空会向 Apple 申请一个新隐藏邮箱",
    },
    {
        "key": "ICLOUD_HME_CREATE_LABEL_PREFIX", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "新别名标签前缀", "help": "自动创建新隐藏邮箱时使用的标签前缀，默认 turb",
    },
    # ---- 浏览器地区画像 ----
    {
        "key": "BROWSER_LOCALE_PROFILE", "file": "browser.py", "type": "str", "group": "浏览器画像",
        "label": "地区画像", "help": "应与代理出口地区一致；可选 jp/cn/us/sg。当前本地代理实测为日本东京，推荐 jp",
    },

    {
        "key": "AUTO_BROWSER_LOCALE_FROM_IP", "file": "browser.py", "type": "bool", "group": "浏览器画像",
        "label": "按出口IP自动画像", "help": "开启后每个 BrowserSession 会用当前代理出口 IP 自动选择语言/时区；失败时回退到地区画像",
    },
    {
        "key": "IP_GEO_TIMEOUT", "file": "browser.py", "type": "float", "group": "浏览器画像",
        "label": "IP定位超时(秒)", "help": "出口 IP 地理信息接口的单次请求超时；接口失败会自动回退，不影响注册",
    },
    {
        "key": "BROWSER_DATA_SAVER_MODE", "file": "browser.py", "type": "bool", "group": "浏览器画像",
        "label": "本地浏览器省流量模式", "help": "仅 Roxy/Cloak 本地浏览器生效；拦截图片、媒体、注册不需要的 ChatGPT SPA 脚本和明确配置的遥测/广告 URL，不拦截认证接口和 WebSocket",
    },
    {
        "key": "BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", "file": "browser.py", "type": "list_str_multiline", "group": "浏览器画像",
        "label": "省流量拦截类型", "help": "每行一种，默认 image、media；font/stylesheet 等类型需单独验证页面稳定性；填 [] 可关闭类型拦截",
    },
    {
        "key": "BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS", "file": "browser.py", "type": "list_str_multiline", "group": "浏览器画像",
        "label": "省流量 URL 规则", "help": "每行一个 URL glob；内置规则含遥测/广告和注册不需要的 ChatGPT SPA JS；不要加入 auth-cdn、session、sentinel 或注册接口；填 [] 可关闭 URL 规则",
    },

    # ---- 代理与网络 ----
    {
        "key": "REGISTRATION_PROXY_MODE", "file": "proxy.py", "type": "str", "group": "代理与网络",
        "label": "注册代理来源", "help": "pool=现有静态代理池；1024=每个注册任务从 1024Proxy 提取独立 IP；none=直连",
    },
    {
        "key": "PROXY_1024_API_URL", "file": "proxy.py", "type": "str", "group": "代理与网络",
        "label": "1024Proxy 提取 API", "help": "粘贴白名单 API 完整 URL；单任务使用 num=1，注册批次会按待执行任务数批量提取，并用下方粘性时长覆盖 URL 的 time 参数；仅保存到 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "PROXY_1024_REGION", "file": "proxy.py", "type": "str", "group": "代理与网络",
        "label": "家宽国家 / 地区", "help": "选择或输入 ISO 两位地区代码；例如 US=美国、JP=日本、GB=英国；Rand=随机。留空沿用提取 API 链接中的 region",
    },
    {
        "key": "PROXY_1024_PROTOCOL", "file": "proxy.py", "type": "str", "group": "代理与网络",
        "label": "返回代理协议", "help": "通常填 http；也支持 https、socks5、socks5h，必须与 1024Proxy 生成接口时选择的协议一致",
    },
    {
        "key": "PROXY_1024_SESSION_MINUTES", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "粘性时长(分钟)", "help": "默认 30，允许 1~120；延长时间本身不增加按 GB 套餐流量，只增加同一 IP 可使用的窗口",
    },
    {
        "key": "PROXY_1024_ROTATE_SESSION_TIME", "file": "proxy.py", "type": "bool", "group": "代理与网络",
        "label": "每任务轮换远端会话", "help": "推荐开启；按任务在基础时长至 120 分钟间轮换 time 参数，避免白名单 API 在粘性窗口内重复返回同一 IP",
    },
    {
        "key": "PROXY_1024_API_TIMEOUT", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "API/检测超时(秒)", "help": "提取 API 和出口 IP 检测的单次超时，建议 10~20 秒",
    },
    {
        "key": "PROXY_1024_MAX_ATTEMPTS", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "最大有效失败次数", "help": "空响应、不可用代理或地区不符的最大次数；重复粘性 IP 另有快速重取额度，不消耗该次数",
    },
    {
        "key": "PROXY_1024_ACQUIRE_TIMEOUT", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "代理获取总预算(秒)", "help": "包含重复 IP 重取和出口检测的整段硬上限；建议 60 秒",
    },
    {
        "key": "REGISTRATION_PROXY_RETRIES", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "注册代理换线重试次数", "help": "只对隧道、连接重置和认证跳转超时等明确代理瞬时错误换线重试；不改变并发数，也不重试密码入口缺失",
    },
    {
        "key": "REGISTRATION_PROXY_RETRY_DELAY", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "注册换线重试间隔(秒)", "help": "换线前的短暂间隔，避免连续请求同一代理平台窗口",
    },
    {
        "key": "ACCOUNT_ACTION_PROXY_RETRIES", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "查活/刷新 AT 换线次数", "help": "查活或刷新 AT 在申请代理阶段遇到重复租约时的额外换线次数；不重跑已提交的认证步骤",
    },
    {
        "key": "ACCOUNT_ACTION_PROXY_RETRY_DELAY", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "查活/刷新 AT 换线间隔(秒)", "help": "查活或刷新 AT 申请新代理前等待的秒数，避免连续命中同一粘性代理窗口",
    },
    {
        "key": "PROXY_1024_VALIDATE", "file": "proxy.py", "type": "bool", "group": "代理与网络",
        "label": "使用前检测出口", "help": "领取邮箱前先通过该代理访问 IPInfo，确认代理可用并记录出口地区",
    },
    {
        "key": "PROXY_1024_VALIDATE_ATTEMPTS", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "同端点检测次数", "help": "出口检测遇到超时、连接或 SSL 瞬时错误时，先重试同一代理；建议 2",
    },
    {
        "key": "PROXY_1024_RECENT_TTL", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "最近 IP 隔离(秒)", "help": "任务释放后多久内拒绝重复分配同一 IP；默认 1800，与 30 分钟粘性时间一致",
    },
    {
        "key": "PROXY_1024_ACQUIRE_INTERVAL", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "提取最小间隔(秒)", "help": "并发任务调用提取 API 的最小间隔，默认 0.6 秒，避免瞬间突发",
    },
    {
        "key": "PROXY_POOL", "file": "proxy.py", "type": "list_str_multiline", "group": "代理与网络",
        "label": "代理池(每行一个)", "help": "每行一个代理 URL，留空行会被忽略；为空则不使用代理",
        "storage": "env", "secret": True,
    },
    {
        "key": "PLAN_CHECK_PROXY_MODE", "file": "proxy.py", "type": "str", "group": "代理与网络",
        "label": "旧版套餐网络模式", "help": "仅兼容 CLI/旧接口；WebUI 查套餐、查活、Agent、Codex OAuth 使用“账号功能代理来源”",
    },
    {
        "key": "PLAN_CHECK_PROXY", "file": "proxy.py", "type": "str", "group": "代理与网络",
        "label": "旧版套餐专用代理", "help": "仅兼容 CLI/旧接口；留空时从代理池选择。可能包含认证信息，仅保存到 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "ACCOUNT_ACTION_PROXY_MODE", "file": "proxy.py", "type": "str", "group": "代理与网络",
        "label": "账号功能代理来源", "help": "registration=跟随注册代理来源（推荐）；1024=每个账号功能申请新租约；pool=使用静态代理池；direct=直连。适用于查套餐、查活和 Codex OAuth",
    },
    {
        "key": "ACCOUNT_ACTION_PROXY", "file": "proxy.py", "type": "str", "group": "代理与网络",
        "label": "账号功能固定代理", "help": "仅账号功能代理来源为 pool 时优先使用；留空则从代理池抽取。可能包含认证信息，仅保存到 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "PLAN_CHECK_TIMEOUT", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "套餐查询超时(秒)", "help": "查套餐的单次请求超时，建议 10-20 秒；独立于注册请求超时",
    },
    {
        "key": "PLAN_CHECK_MAX_ATTEMPTS", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "套餐查询最大尝试次数", "help": "查套餐遇到网络错误、429、5xx 等临时错误时的重试次数，建议 2 次",
    },
    {
        "key": "PLAN_CHECK_RETRY_DELAY", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "套餐查询重试间隔(秒)", "help": "查套餐的重试间隔，按尝试次数递增；服务端 Retry-After 优先",
    },
    {
        "key": "PLAN_CHECK_REGISTRATION_RECHECK_DELAY", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "新账号资格复查延迟(秒)", "help": "新注册 free 账号未发现试用资格或首次查询失败时复查一次；0 表示关闭",
    },
    {
        "key": "PLAN_CHECK_WORKERS", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "注册流程套餐查询并发数", "help": "仅用于注册链路中没有复用注册代理时的异步套餐查询；账号页套餐查询统一使用通用配置 ACCOUNT_BATCH_WORKERS",
    },
    {
        "key": "PLAN_CHECK_QUEUE_LIMIT", "file": "proxy.py", "type": "int", "group": "代理与网络",
        "label": "套餐查询队列上限", "help": "防止异常批量操作无限堆积，建议 100-1000",
    },
    {
        "key": "PLAN_CHECK_MIN_INTERVAL", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "套餐请求最小间隔(秒)", "help": "限制查套餐请求的启动频率，降低 429 风险",
    },
    {
        "key": "PLAN_CHECK_JITTER", "file": "proxy.py", "type": "float", "group": "代理与网络",
        "label": "套餐请求随机抖动(秒)", "help": "在查套餐请求的最小间隔上增加随机延迟，避免请求过于规律",
    },
    # ---- 提链 ----
    {
        "key": "EXTRACT_LINK_API_BASE", "file": "extract_link.py", "type": "str", "group": "提链",
        "label": "提链服务地址", "help": "填写提链服务 API 地址",
    },
    {
        "key": "EXTRACT_LINK_CDK", "file": "extract_link.py", "type": "str", "group": "提链",
        "label": "提链 CDK", "help": "创建提链任务和监听任务事件使用；成功提链扣 1 次",
        "storage": "env", "secret": True,
    },
    {
        "key": "EXTRACT_LINK_TYPE", "file": "extract_link.py", "type": "str", "group": "提链",
        "label": "提链类型", "help": "从提链网站读取当前启用类型；接口不可用时保留备用选项，默认 PIX",
    },
    # ---- Codex 配置 ----
    {
        "key": "SUB2API_API_BASE", "file": "sub2api.py", "type": "str", "group": "Codex",
        "label": "sub2 API基址", "help": "sub2api 服务地址；用于 Codex OAuth 授权和凭证上传，例如 http://127.0.0.1:8080",
    },
    {
        "key": "SUB2API_API_KEY", "file": "sub2api.py", "type": "str", "group": "Codex",
        "label": "sub2 API Key", "help": "sub2api 管理接口 API Key；请求头使用 x-api-key；为空则不带鉴权头", "storage": "env", "secret": True,
    },
    {
        "key": "SUB2API_API_TIMEOUT", "file": "sub2api.py", "type": "int", "group": "Codex",
        "label": "sub2 超时", "help": "sub2api 请求超时秒数",
    },
    # ---- 接码平台 ----
    # ---- Codex：基础 / CPA / sub2api 配置 ----
    {
        "key": "CODEX_AUTH_URL_SOURCE", "file": "codex.py", "type": "str", "group": "Codex",
        "label": "授权地址来源", "help": "cpa=CPA生成并上传CPA；sub2=sub2生成并上传sub2；local=本地PKCE",
    },
    {
        "key": "CPA_MANAGEMENT_URL", "file": "codex.py", "type": "str", "group": "Codex",
        "label": "CPA 管理地址", "help": "例如 http://localhost:8317/admin/oauth；程序会取 origin 调用 /v0/management/*",
    },
    {
        "key": "CPA_MANAGEMENT_KEY", "file": "codex.py", "type": "str", "group": "Codex",
        "label": "管理密钥", "help": "保存在 .env（CPA_MANAGEMENT_KEY），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "CPA_REQUEST_TIMEOUT", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "CPA 超时(秒)", "help": "请求 CPA 管理接口的超时时间",
    },
    {
        "key": "CPA_CREDENTIAL_CONFIRM_TIMEOUT", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "CPA 凭证确认等待(秒)", "help": "Callback 接收后等待 CPA 生成真实 auth JSON 的最长时间；超时则标记待确认。",
    },
    {
        "key": "CPA_SAVE_CALLBACK_RECEIPT", "file": "codex.py", "type": "bool", "group": "Codex",
        "label": "保存CPA回执", "help": "CPA 未返回完整授权文件时，本地仍保存一份回调提交记录",
    },

    {
        "key": "SMS_PROVIDER", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "接码通道", "help": "grizzly / l / h；l 使用 L_API.md，h 使用 H_API.md 定义的本地取号服务",
    },
    {
        "key": "SMS_COUNTRY", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "国家代码", "help": "传给接码平台的 country；GrizzlySMS 可用逗号填写有序备用列表（如 117,2,148），无号/超价时自动切换；H/L 通道填写单个国家",
    },
    {
        "key": "SMS_SERVICE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "服务/项目代码", "help": "GrizzlySMS/L 作为 service；H 通道作为 H_API.md 的 projectId",
    },
    {
        "key": "SMS_MAX_PRICE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "最高价格上限", "help": "这是允许购买的单号价格上限，不是固定成交价；留空表示不限，实际价格以平台返回为准",
    },
    {
        "key": "SMS_AUTO_SELECT_COUNTRY", "file": "codex.py", "type": "bool", "group": "接码平台",
        "label": "按成功率选国家", "help": "GrizzlySMS 每批次首次接码前，在价格上限内按短信成功率自动选国；同批次后续任务优先沿用",
    },
    {
        "key": "SMS_AUTO_COUNTRY_MIN_RATIO", "file": "codex.py", "type": "int", "group": "接码平台",
        "label": "成功率最低统计量", "help": "过滤成功率看似很高但统计量太少的国家；建议保持 25 或更高",
    },
    {
        "key": "SMS_MAX_RETRIES", "file": "codex.py", "type": "int", "group": "接码平台",
        "label": "换号重试次数", "help": "一个号收不到短信/被OpenAI拒时换下一个号，最多重试几次",
    },
    {
        "key": "SMS_CODE_WAIT", "file": "codex.py", "type": "int", "group": "接码平台",
        "label": "单号等短信上限(秒)", "help": "单个号码等待短信的硬上限；超时后后台取消，不再阻塞注册线程",
    },
    {
        "key": "CODEX_PHONE_TOTAL_TIMEOUT", "file": "codex.py", "type": "int", "group": "接码平台",
        "label": "手机验证总预算(秒)", "help": "整段手机验证的硬上限，包含取号、页面操作、等待短信和换号；建议 300",
    },
    {
        "key": "SMS_API_KEY", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "GrizzlySMS API密钥", "help": "GrizzlySMS 平台 API Key，保存在 .env（SMS_API_KEY），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "H_API_BASE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "H API 地址", "help": "H 取号服务基础地址，例如 http://localhost:8788",
    },
    {
        "key": "H_ADMIN_AUTH_CODE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "H 授权码", "help": "保存在 .env（H_ADMIN_AUTH_CODE），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "H_PHONE_PREFIX", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "H 号码前缀", "help": "H 返回号码不含国家码时填写，例如美国 10 位本地号填 1；留空则不补",
    },
    {
        "key": "H_PHONE_ACQUIRE_MODE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "H 取号方式", "help": "reusable=优先复用历史可用号码；new=每次都取一个新号码",
    },
    {
        "key": "L_API_BASE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "L API 地址", "help": "L 取号服务基础地址，例如 http://localhost:8788",
    },
    {
        "key": "L_ADMIN_AUTH_CODE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "L 授权码", "help": "保存在 .env（L_ADMIN_AUTH_CODE），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "L_PHONE_PREFIX", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "L 号码前缀", "help": "L 返回号码不含国家码时填写，例如美国 10 位本地号填 1；留空则不补",
    },
]


_OPTIONS: dict[str, tuple[ConfigOption, ...]] = {
    "OPENAI_PROTOCOL_VERSION": _options(
        ("v1", "协议 v1（现有稳定实现）"),
        ("v2", "协议 v2（已支持的步骤）"),
    ),
    "REGISTRATION_DRIVER": _options(("protocol", "纯协议注册"), ("roxy", "RoxyBrowser")),
    "REGISTRATION_AUTH_MODE": _options(
        ("otp", "不设置密码（邮箱验证码）"), ("password", "设置账号密码")
    ),
    "ACCOUNT_PASSWORD_DRIVER": _options(("roxy", "RoxyBrowser（当前唯一实现）")),
    "ACCOUNT_PLAN_CHECK_DRIVER": _options(("protocol", "纯协议（当前唯一实现）")),
    "ACCOUNT_LIVE_CHECK_DRIVER": _options(
        ("protocol_current", "现有协议（保持现状）"),
        ("browser_roxy", "Roxy 浏览器（旧 AT probe）"),
    ),
    "ACCOUNT_AUTH_PROFILE_MODE": _options(
        ("current", "当前会话画像（保持现状）"),
        ("account_stable", "账号稳定 Protocol 画像（懒创建）"),
    ),
    "ACCOUNT_EMAIL_CHANGE_PROXY_MODE": _options(
        ("registration", "跟随注册线路"),
        ("direct", "直连"),
        ("pool", "静态代理池"),
        ("provider:1024proxy", "1024Proxy 独立租约"),
    ),
    "TWOFA_DRIVER": _options(
        ("auto", "自动选择（协议优先）"),
        ("protocol", "协议开通"),
        ("browser", "浏览器页面（RoxyBrowser）"),
    ),
    "ACCOUNT_2FA_DRIVER": _options(
        ("auto", "自动选择（协议优先）"),
        ("protocol", "协议开通"),
        ("browser", "浏览器页面（RoxyBrowser）"),
    ),
    "ACCOUNT_CODEX_DRIVER": _options(
        ("protocol", "纯协议授权"),
        ("roxy", "RoxyBrowser"),
        ("same_as_registration", "跟随注册驱动"),
    ),
    "CODEX_OAUTH_DRIVER": _options(
        ("protocol", "纯协议授权"),
        ("roxy", "RoxyBrowser"),
        ("same_as_registration", "跟随注册驱动"),
    ),
    "CLOUDFLARE_AUTH_MODE": _options(
        "none", "bearer", "x-api-key", "x-admin-auth", "query-key"
    ),
    "OUTLOOK_FETCH_MODE": _options(
        ("auto", "远端优先，失败切 Graph"),
        ("remote", "只用远端服务"),
        ("direct", "只用 Microsoft Graph"),
    ),
    "ICLOUD_HME_INBOX_MODE": _options(
        ("sidecar", "sidecar 读取 iCloud IMAP"),
        ("forward_imap", "本机读取 Gmail"),
        ("forward_butler", "Email Butler PG 收件"),
    ),
    "REGISTRATION_PROXY_MODE": _options(
        ("pool", "静态代理池"), ("1024", "1024Proxy 平台 API"), ("none", "直连")
    ),
    "PROXY_1024_PROTOCOL": _options("http", "https", "socks5", "socks5h"),
    "PLAN_CHECK_PROXY_MODE": _options("auto", "proxy", "direct"),
    "ACCOUNT_ACTION_PROXY_MODE": _options(
        ("registration", "跟随注册线路"),
        ("1024", "1024Proxy 独立租约"),
        ("pool", "静态代理池"),
        ("direct", "直连"),
    ),
    "CODEX_AUTH_URL_SOURCE": _options(
        ("cpa", "CPA"), ("sub2", "sub2api"), ("local", "本地 PKCE")
    ),
    "SMS_PROVIDER": _options("grizzly", "l", "h"),
    "H_PHONE_ACQUIRE_MODE": _options(
        ("reusable", "优先复用历史号码"), ("new", "每次取新号码")
    ),
    "BROWSER_LOCALE_PROFILE": _options(
        ("jp", "日本"), ("cn", "中国"), ("us", "美国"), ("sg", "新加坡")
    ),
    "PROXY_1024_REGION": _options(
        ("", "沿用 API URL"),
        ("US", "美国"), ("JP", "日本"), ("GB", "英国"), ("CA", "加拿大"),
        ("AU", "澳大利亚"), ("DE", "德国"), ("FR", "法国"), ("NL", "荷兰"),
        ("SG", "新加坡"), ("KR", "韩国"), ("HK", "中国香港"), ("TW", "中国台湾"),
        ("ES", "西班牙"), ("IT", "意大利"), ("CH", "瑞士"), ("SE", "瑞典"),
        ("NO", "挪威"), ("PL", "波兰"), ("BR", "巴西"), ("MX", "墨西哥"),
        ("IN", "印度"), ("ID", "印度尼西亚"), ("TH", "泰国"), ("VN", "越南"),
        ("PH", "菲律宾"), ("MY", "马来西亚"), ("AE", "阿联酋"), ("TR", "土耳其"),
        ("Rand", "随机地区"),
    ),
    "EXTRACT_LINK_TYPE": _options(
        ("pix", "PIX"), ("gopay", "GoPay"), ("upi", "UPI"),
        ("ideal", "iDEAL"), ("ideal_short", "iDEAL Short"),
        ("kakao_pay", "Kakao Pay"), ("momo", "MoMo"), ("gcash", "GCash"),
        ("paypal", "PayPal"), ("ph_short", "菲律宾短链"),
    ),
    "EMAIL_SOURCE": _options(
        ("outlook", "Outlook"), ("generic_api", "通用 API"),
        ("cloudflare_domain", "Cloudflare 域名邮箱"), ("cloudflare", "Cloudflare Worker"),
        ("email_butler", "Email Butler"), ("gptmail", "GPTMail"),
        ("mailnest", "MailNest"), ("cloudmail", "CloudMail"),
        ("icloud_hide", "iCloud Hide My Email"),
    ),
}


_ALIASES: dict[str, Mapping[str, str]] = {
    # 旧配置名仍可读取/运行，但公共 API 展示统一为 auto。
    "ACCOUNT_2FA_DRIVER": {"protocol_direct": "auto"},
    "TWOFA_DRIVER": {"protocol_direct": "auto"},
}


_RANGES: dict[str, tuple[int | float | None, int | float | None]] = {
    "ACCOUNT_BATCH_WORKERS": (1, 16),
    "EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS": (900, 604800),
    "AT_REFRESH_SCAN_INTERVAL_SECONDS": (300, 86400),
    "CODEX_TOKEN_REFRESH_BEFORE_HOURS": (0, 720),
    "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS": (300, 604800),
    "CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS": (0, 86400),
    "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE": (1, 10000),
    "REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS": (1, 3600),
    "REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS": (0, 86400),
    "REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT": (0, 100000),
    "REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB": (1, 10240),
    "REGISTRATION_DEBUG_MAX_HELD_SESSIONS": (0, 10000),
    "REGISTRATION_DEBUG_BODY_MAX_KB": (0, 102400),
    "REGISTRATION_DEBUG_BODY_BUDGET_MB": (0, 102400),
    "REGISTRATION_DEBUG_GLOBAL_BUDGET_MB": (0, 1048576),
    "REGISTRATION_DEBUG_RETENTION_DAYS": (0, 3650),
    "REGISTRATION_DEBUG_QUEUE_SIZE": (1, 1000000),
    "ROXY_WINDOW_WAIT_TIMEOUT": (0, 86400),
    "ROXY_WINDOW_WAIT_INTERVAL": (1, 3600),
    "ROXY_CODEX_CALLBACK_TIMEOUT": (1, 86400),
    "OTP_MAX_WAIT": (1, 86400),
    "OTP_POLL_INTERVAL": (1, 3600),
    "EMAIL_BUTLER_REQUEST_TIMEOUT": (1, 3600),
    "CLOUDFLARE_REQUEST_TIMEOUT": (1, 3600),
    "CLOUDFLARE_NAME_LENGTH": (1, 128),
    "CLOUDMAIL_RANDOM_LOCAL_LENGTH": (1, 128),
    "ICLOUD_HME_REQUEST_TIMEOUT": (1, 3600),
    "ICLOUD_HME_SYNC_TTL": (0, 604800),
    "ICLOUD_HME_FORWARD_IMAP_PORT": (1, 65535),
    "IP_GEO_TIMEOUT": (0.1, 300.0),
    "PROXY_1024_SESSION_MINUTES": (1, 120),
    "PROXY_1024_API_TIMEOUT": (0.1, 300.0),
    "PROXY_1024_MAX_ATTEMPTS": (1, 100),
    "PROXY_1024_ACQUIRE_TIMEOUT": (0.1, 3600.0),
    "REGISTRATION_PROXY_RETRIES": (0, 100),
    "REGISTRATION_PROXY_RETRY_DELAY": (0, 300.0),
    "ACCOUNT_ACTION_PROXY_RETRIES": (0, 100),
    "ACCOUNT_ACTION_PROXY_RETRY_DELAY": (0, 300.0),
    "PROXY_1024_VALIDATE_ATTEMPTS": (1, 100),
    "PROXY_1024_RECENT_TTL": (0, 604800),
    "PROXY_1024_ACQUIRE_INTERVAL": (0, 300.0),
    "PLAN_CHECK_TIMEOUT": (0.1, 300.0),
    "PLAN_CHECK_MAX_ATTEMPTS": (1, 100),
    "PLAN_CHECK_RETRY_DELAY": (0, 300.0),
    "PLAN_CHECK_REGISTRATION_RECHECK_DELAY": (0, 604800.0),
    "PLAN_CHECK_WORKERS": (1, 64),
    "PLAN_CHECK_QUEUE_LIMIT": (1, 1000000),
    "PLAN_CHECK_MIN_INTERVAL": (0, 300.0),
    "PLAN_CHECK_JITTER": (0, 300.0),
    "SUB2API_API_TIMEOUT": (1, 3600),
    "CPA_REQUEST_TIMEOUT": (1, 3600),
    "CPA_CREDENTIAL_CONFIRM_TIMEOUT": (0, 86400),
    "CPA_CALLBACK_SUBMIT_RETRIES": (0, 100),
    "CPA_CALLBACK_SUBMIT_RETRY_DELAY": (0, 300),
    "SMS_AUTO_COUNTRY_MIN_RATIO": (0, 100),
    "SMS_MAX_RETRIES": (0, 100),
    "SMS_CODE_WAIT": (1, 86400),
    "CODEX_PHONE_TOTAL_TIMEOUT": (1, 86400),
    "H_PHONE_ACQUIRE_MODE": (None, None),
}


# 当前仍需兼容的、但不是 WebUI editable 的环境覆盖。默认值取模块当前
# namespace，避免把运行配置再次复制到这里。
LEGACY_ENV_OVERRIDE_TYPES: Mapping[str, str] = MappingProxyType({
    "REJECT_CLOUD_PROXY": "bool",
    "BROWSER_USE_API_KEY": "str",
    "BROWSER_USE_PROXY_COUNTRY_CODE": "str",
    "BROWSER_USE_USE_PROXY": "bool",
    "BROWSER_USE_PROFILE_ID": "str",
    "BROWSER_USE_CDP_BASE": "str",
    "BROWSER_USE_TIMEOUT": "int",
    "BROWSER_USE_SESSION_TIMEOUT": "int",
    "BROWSER_USE_FAST_MODE": "bool",
    "BROWSER_USE_LOG_TIMING": "bool",
    "BROWSER_USE_KEEP_BROWSER_OPEN": "bool",
    "BROWSER_USE_START_URL": "str",
    "CLOAK_HEADLESS": "bool",
    "CLOAK_HUMANIZE": "bool",
    "CLOAK_HUMAN_PRESET": "str",
    "CLOAK_GEOIP": "bool",
    "CLOAK_LOCALE": "str",
    "CLOAK_TIMEZONE": "str",
    "CLOAK_USE_PROXY": "bool",
    "CLOAK_LICENSE_KEY": "str",
    "CLOAK_FINGERPRINT_SEED": "str",
    "CLOAK_USER_DATA_DIR": "str",
    "CLOAK_SELENIUM_TIMEOUT": "int",
    "CLOAK_KEEP_BROWSER_OPEN": "bool",
    "SKYVERN_API_KEY": "str",
    "SKYVERN_API_BASE": "str",
    "SKYVERN_BROWSER_SESSION_TIMEOUT": "int",
    "SKYVERN_BROWSER_PROFILE_ID": "str",
    "SKYVERN_PROXY_LOCATION": "str",
    "SKYVERN_GENERATE_BROWSER_PROFILE": "bool",
    "SKYVERN_AD_BLOCKER": "bool",
    "SKYVERN_BROWSER_TYPE": "str",
    "SKYVERN_KEEP_BROWSER_OPEN": "bool",
    "SKYVERN_START_URL": "str",
    "CPA_CALLBACK_SUBMIT_RETRIES": "int",
    "CPA_CALLBACK_SUBMIT_RETRY_DELAY": "int",
    "QQ_IMAP_SERVER": "str",
    "QQ_IMAP_PORT": "int",
    "OUTLOOK_API_BASE": "str",
    "EMAIL_BUTLER_RISK_SCAN_INITIAL_DELAY_SECONDS": "int",
    "EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS": "int",
    "EXTRACT_LINK_QUEUE_LIMIT": "int",
    "EXTRACT_LINK_REQUEST_TIMEOUT": "int",
    "EXTRACT_LINK_EVENT_TIMEOUT": "int",
    "PROXY_1024_PERSIST_LEASES": "bool",
    "ACCOUNT_TOKEN_REFRESH_DRIVER": "str",
    "ACCOUNT_AUTH_V2_ENABLED": "bool",
    "SUB2API_API_URL": "str",
    "SUB2API_API_AUTH_HEADER": "str",
    "SUB2API_API_AUTH_PREFIX": "str",
    "SUB2_CODEX_API_BASE": "str",
    "SUB2_CODEX_AUTH_URL_PATH": "str",
    "SUB2_CODEX_CALLBACK_PATH": "str",
    "SUB2_CODEX_API_TOKEN": "str",
    "SUB2_CODEX_AUTH_HEADER": "str",
    "SUB2_CODEX_AUTH_PREFIX": "str",
    "SUB2_CODEX_CALLBACK_PAYLOAD_MODE": "str",
})


_RESTART_KEYS = frozenset({
    "WEBUI_AUTH_CODE",
    "WEBUI_SESSION_SECRET",
    "PLAN_CHECK_WORKERS",
    "PLAN_CHECK_QUEUE_LIMIT",
})

_SECRET_KEYS = frozenset({
    "WEBUI_AUTH_CODE", "WEBUI_SESSION_SECRET", "ROXY_API_TOKEN",
    "EMAIL_BUTLER_API_KEY", "GPTMAIL_API_KEY", "CLOUDFLARE_API_KEY",
    "CLOUDFLARE_SIGNAL_API_KEY", "CLOUDFLARE_CUSTOM_AUTH", "QQ_IMAP_PASSWORD",
    "MAIL_NEST_API_KEY", "CLOUDMAIL_PASSWORD", "CLOUDMAIL_AUTH_TOKEN",
    "ICLOUD_HME_API_TOKEN", "ICLOUD_HME_FORWARD_IMAP_PASSWORD",
    "PROXY_1024_API_URL", "PLAN_CHECK_PROXY", "ACCOUNT_ACTION_PROXY",
    "EXTRACT_LINK_CDK", "SUB2API_API_KEY", "CPA_MANAGEMENT_KEY", "SMS_API_KEY",
    "H_ADMIN_AUTH_CODE", "L_ADMIN_AUTH_CODE", "PROXY_POOL",
})

_PROVIDER_PROXY_KEYS = {
    "ACCOUNT_PASSWORD_PROXY_MODE", "ACCOUNT_2FA_PROXY_MODE",
    "ACCOUNT_PLAN_CHECK_PROXY_MODE", "ACCOUNT_LIVE_CHECK_PROXY_MODE",
    "ACCOUNT_REFRESH_AT_PROXY_MODE", "ACCOUNT_CODEX_PROXY_MODE",
    "ACCOUNT_EMAIL_CHANGE_PROXY_MODE",
}

_DYNAMIC_PATTERNS = {
    "PROXY_1024_REGION": re.compile(r"^(?:[A-Za-z]{2}|Rand)?$"),
    "ROXY_RANDOM_OS_CHOICES": re.compile(r"^[^\r\n]+(?:,[^\r\n]+)*$"),
}

# 旧版 WebUI 曾在“定时任务”和“Codex”两个位置展示这两个 Codex
# refresh 字段。canonical registry 只保留一份定义，editor_metadata() 在
# schema 内部按旧顺序生成展示投影，不再复制第二份静态字段元数据。
_LEGACY_SCHEDULED_DISPLAY_KEYS = (
    "CODEX_TOKEN_AUTO_REFRESH_ENABLED",
    "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS",
)

_PLACEHOLDER_EMPTY = {
    "", "-", "—", "无", "空", "none", "null", "n/a", "na", "未设置", "未配置",
}


def _legacy_fields() -> list[dict[str, Any]]:
    """返回兼容旧字段表形状的 schema-owned 定义副本。

    函数名保留是为了减少内部/外部旧调用方的迁移成本；它不再导入
    ``webui.config_editor``。
    """
    return [copy.deepcopy(field) for field in _FIELD_DEFINITIONS]


def _editor_field_definitions() -> list[dict[str, Any]]:
    """构造兼容旧 UI 顺序的展示投影；canonical 定义仍只有一份。"""
    definitions = _legacy_fields()
    by_key = {definition["key"]: definition for definition in definitions}
    scheduled = [
        dict(by_key[key], group="定时任务")
        for key in _LEGACY_SCHEDULED_DISPLAY_KEYS
    ]
    projected: list[dict[str, Any]] = []
    inserted = False
    for definition in definitions:
        if not inserted and definition.get("key") == "WEBUI_AUTH_CODE":
            projected.extend(scheduled)
            inserted = True
        projected.append(definition)
    return projected


def _build_fields(legacy_fields: Iterable[Mapping[str, Any]]) -> tuple[ConfigField, ...]:
    fields: list[ConfigField] = []
    seen: set[str] = set()
    for legacy in legacy_fields:
        key = str(legacy.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        if key not in _DEFAULTS:
            raise RuntimeError(f"schema 缺少默认值: {key}")
        min_value, max_value = _RANGES.get(key, (None, None))
        options = _OPTIONS.get(key, ())
        aliases = MappingProxyType(dict(_ALIASES.get(key, {})))
        hot_edit = "restart" if key in _RESTART_KEYS else "safe"
        fields.append(ConfigField(
            key=key,
            file=legacy.get("file"),
            type=str(legacy.get("type") or "str"),
            default=copy.deepcopy(_DEFAULTS[key]),
            group=str(legacy.get("group") or "其他"),
            label=str(legacy.get("label") or key),
            help=str(legacy.get("help") or ""),
            storage=str(legacy.get("storage") or "env"),
            options=options,
            min_value=min_value,
            max_value=max_value,
            secret=key in _SECRET_KEYS or bool(legacy.get("secret")),
            aliases=aliases,
            restart=key in _RESTART_KEYS,
            hot_edit=hot_edit,
            allow_prefix="provider:" if key in _PROVIDER_PROXY_KEYS else None,
            csv_options=tuple(option.value for option in _OPTIONS.get(key, ()) if key == "EMAIL_SOURCE"),
        ))
    return tuple(fields)


class ConfigSchema:
    """延迟构建、映射兼容的配置 schema registry。"""

    def __init__(self) -> None:
        self._fields: tuple[ConfigField, ...] | None = None
        self._by_key: dict[str, ConfigField] = {}
        self._lock = threading.RLock()

    def _ensure_loaded(self) -> None:
        if self._fields is not None:
            return
        with self._lock:
            if self._fields is None:
                fields = _build_fields(_legacy_fields())
                self._fields = fields
                self._by_key = {field.key: field for field in fields}

    @property
    def fields(self) -> tuple[ConfigField, ...]:
        self._ensure_loaded()
        assert self._fields is not None
        return self._fields

    @property
    def editable_fields(self) -> tuple[ConfigField, ...]:
        return tuple(field for field in self.fields if field.editable)

    def get(self, key: str, default: ConfigField | None = None) -> ConfigField | None:
        self._ensure_loaded()
        return self._by_key.get(key, default)

    def __getitem__(self, key: str) -> ConfigField:
        self._ensure_loaded()
        return self._by_key[key]

    def __contains__(self, key: object) -> bool:
        self._ensure_loaded()
        return key in self._by_key

    def __iter__(self):
        return iter(self.fields)

    def __len__(self) -> int:
        return len(self.fields)

    def keys(self):
        self._ensure_loaded()
        return self._by_key.keys()

    def values(self):
        self._ensure_loaded()
        return self._by_key.values()

    def items(self):
        self._ensure_loaded()
        return self._by_key.items()

    def metadata(self) -> list[dict[str, Any]]:
        return [field.metadata() for field in self.editable_fields]

    def restart_keys(self) -> frozenset[str]:
        return frozenset(field.key for field in self.editable_fields if field.restart)

    def fields_for_module(self, module: str | None, namespace: Mapping[str, Any]) -> list[ConfigField]:
        """返回当前模块应处理的 schema 字段和兼容 env 字段。"""
        fields = [
            field for field in self.fields
            if field.module == module and field.key in namespace
        ]
        known = {field.key for field in fields}
        for key in LEGACY_ENV_OVERRIDE_TYPES:
            if key in namespace and key not in known:
                fields.append(ConfigField(
                    key=key,
                    file=None,
                    type=LEGACY_ENV_OVERRIDE_TYPES[key],
                    default=copy.deepcopy(namespace[key]),
                    group="其他",
                    label=key,
                    help="兼容环境变量",
                    editable=False,
                ))
        return fields

    def editor_metadata(self, legacy_fields: Iterable[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
        # 参数仅保留给旧测试/调用方；WebUI 默认直接消费本 schema。旧版 UI
        # 曾在“定时任务”和“Codex”两个位置展示同一组 Codex refresh 字段，
        # 因而这里保留展示顺序/重复展示；CONFIG_SCHEMA.fields 和
        # _FIELD_DEFINITIONS 本身均按 key 唯一，校验、解析和 snapshot 使用唯一字段。
        definitions = list(
            legacy_fields if legacy_fields is not None else _editor_field_definitions()
        )
        fields = [field for definition in definitions for field in _build_fields([definition])]
        return [field.metadata() for field in fields if field.editable]


CONFIG_SCHEMA = ConfigSchema()
SCHEMA = CONFIG_SCHEMA
CONFIG_FIELDS = CONFIG_SCHEMA
DEFAULTS = MappingProxyType(_DEFAULTS)


def schema_default(key: str) -> Any:
    """取得字段默认值的深拷贝，供 config 子模块声明兼容常量。"""
    try:
        return copy.deepcopy(_DEFAULTS[key])
    except KeyError as exc:
        raise KeyError(f"schema 未定义字段: {key}") from exc


def _normalize_string(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text.lower() in {item.lower() for item in _PLACEHOLDER_EMPTY}:
        return ""
    return text


def _coerce(value: Any, field: ConfigField, *, strict: bool) -> Any:
    if field.type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on", "y"}:
                return True
            if normalized in {"false", "0", "no", "off", "n"}:
                return False
        if strict:
            raise ValueError("必须是布尔值")
        raise ValueError("布尔值无法解析")

    if field.type == "int":
        if isinstance(value, bool):
            raise ValueError("必须是整数")
        if isinstance(value, int):
            return value
        text = str(value).strip()
        if not re.fullmatch(r"[+-]?\d+", text):
            raise ValueError("必须是整数")
        return int(text)

    if field.type == "float":
        if isinstance(value, bool):
            raise ValueError("必须是数字")
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("必须是数字") from exc
        if not math.isfinite(result):
            raise ValueError("必须是有限数字")
        return result

    if field.type == "list_str_multiline":
        if isinstance(value, str):
            try:
                import ast
                parsed = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, (list, tuple)):
                values = parsed
            else:
                values = value.splitlines()
        elif isinstance(value, (list, tuple)):
            values = value
        else:
            raise ValueError("必须是字符串列表")
        return [item for item in (_normalize_string(item) for item in values) if item]

    if field.type != "str":
        raise ValueError(f"不支持的类型: {field.type}")
    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError("必须是字符串")
    text = "" if value is None else str(value).strip()
    # ``none`` 是通用空占位，但也是 CLOUDFLARE_AUTH_MODE 的合法
    # canonical option；选项值必须先于通用空值语义保留。
    option_values = {option.value.casefold() for option in field.options}
    if text.casefold() in {item.casefold() for item in _PLACEHOLDER_EMPTY}:
        if text.casefold() not in option_values:
            return ""
    return text


def _validate_value(field: ConfigField, value: Any, *, strict: bool) -> Any:
    result = _coerce(value, field, strict=strict)
    if field.type in {"int", "float"}:
        if field.min_value is not None and result < field.min_value:
            raise ValueError(f"不得小于 {field.min_value}")
        if field.max_value is not None and result > field.max_value:
            raise ValueError(f"不得大于 {field.max_value}")

    if field.type == "str":
        if field.key == "EMAIL_SOURCE":
            values = [part.strip().casefold() for part in result.split(",") if part.strip()]
            allowed = {option.value for option in field.options}
            invalid = [part for part in values if part not in allowed]
            if invalid and strict:
                raise ValueError("包含未支持的邮箱来源")
            result = ",".join(values)
        elif field.options:
            option_values = {option.value.casefold(): option.value for option in field.options}
            lowered = result.casefold()
            if lowered in option_values:
                result = option_values[lowered]
            elif result in field.aliases:
                # 保存 API 采用 canonical 值；运行时覆盖会保留旧 alias。
                result = result
            elif field.allow_prefix and result.startswith(field.allow_prefix) and result[len(field.allow_prefix):].strip():
                result = result
            elif field.key == "PROXY_1024_REGION" and _DYNAMIC_PATTERNS[field.key].fullmatch(result):
                result = result.upper() if result not in {"", "Rand"} else result
            elif strict:
                raise ValueError("不在允许选项中")
        elif field.key in _DYNAMIC_PATTERNS and result and not _DYNAMIC_PATTERNS[field.key].fullmatch(result):
            if strict:
                raise ValueError("格式不合法")

    if field.key == "PROXY_1024_REGION" and result and not _DYNAMIC_PATTERNS[field.key].fullmatch(result):
        if strict:
            raise ValueError("必须是两位地区代码或 Rand")
    return result


def validate_value(key: str, value: Any) -> Any:
    """按 schema 校验并返回用于保存的规范化值。"""
    field = CONFIG_SCHEMA.get(key)
    if field is None:
        raise ConfigValidationError({key: "未定义配置字段"})
    try:
        return _validate_value(field, value, strict=True)
    except ValueError as exc:
        raise ConfigValidationError({key: str(exc)}) from exc


def _cross_field_errors(values: Mapping[str, Any]) -> dict[str, str]:
    """返回依赖多个字段的候选配置错误。"""
    errors: dict[str, str] = {}
    if (
        values.get("ACCOUNT_LIVE_CHECK_DRIVER") == "browser_roxy"
        and not values.get("ACCOUNT_LIVE_CHECK_BROWSER_ENABLED")
    ):
        errors["ACCOUNT_LIVE_CHECK_DRIVER"] = (
            "选择 browser_roxy 前必须开启 ACCOUNT_LIVE_CHECK_BROWSER_ENABLED"
        )
    return errors


def validate_config_updates(updates: Mapping[str, Any]) -> dict[str, Any]:
    """一次性校验候选配置；任何字段失败都不返回部分结果。"""
    if not isinstance(updates, Mapping) or not updates:
        raise ConfigValidationError("无更新内容")
    errors: dict[str, str] = {}
    normalized: dict[str, Any] = {}
    for raw_key, value in updates.items():
        key = str(raw_key)
        field = CONFIG_SCHEMA.get(key)
        if field is None or not field.editable:
            errors[key] = "未定义或不可编辑的配置字段"
            continue
        try:
            normalized[key] = _validate_value(field, value, strict=True)
        except ValueError as exc:
            errors[key] = str(exc)

    # 跨字段约束必须针对合并后的候选值判断，支持同一请求同时打开 gate。
    if not errors:
        current = {key: resolution.value for key, resolution in resolve_config().items()}
        current.update(normalized)
        errors.update(_cross_field_errors(current))

    if errors:
        raise ConfigValidationError(errors)
    return normalized


def _environment_values() -> dict[str, str]:
    from config.env_loader import dotenv_loading_disabled, read_env_file

    values = {str(key): str(value) for key, value in os.environ.items()}
    # 项目 .env 是 WebUI 的持久化来源，与 load_env(override=True) 保持一致。
    if not dotenv_loading_disabled():
        values.update({str(key): str(value) for key, value in read_env_file().items()})
    return values


def _raw_for_field(field: ConfigField, values: Mapping[str, str]) -> tuple[str | None, str | None]:
    if field.key in values:
        return values[field.key], field.key
    for alias in field.aliases:
        if alias in values:
            return values[alias], alias
    return None, None


def resolve_field(field: ConfigField, values: Mapping[str, str], *, strict: bool = False) -> ConfigResolution:
    raw, source_key = _raw_for_field(field, values)
    if raw is None:
        return ConfigResolution(field.clone_default(), "default", configured=False)
    text = str(raw).strip()
    explicit_empty_list = field.type == "list_str_multiline" and field.key == "PROXY_POOL" and text == ""
    if not text and not explicit_empty_list:
        return ConfigResolution(field.clone_default(), "default", source_key=source_key, configured=False)
    try:
        value = _validate_value(field, raw, strict=True)
    except (TypeError, ValueError):
        if strict:
            raise
        return ConfigResolution(
            field.clone_default(), "default", source_key=source_key, configured=False, invalid=True
        )
    return ConfigResolution(value, "env", source_key=source_key, configured=bool(text))


def resolve_config(
    env_values: Mapping[str, str] | None = None,
    *,
    strict: bool = False,
) -> dict[str, ConfigResolution]:
    """解析所有字段；``strict`` 用于 reload 前的离线候选校验。"""
    values = dict(env_values) if env_values is not None else _environment_values()
    if not strict:
        return {
            field.key: resolve_field(field, values)
            for field in CONFIG_SCHEMA.editable_fields
        }

    resolutions: dict[str, ConfigResolution] = {}
    errors: dict[str, str] = {}
    for field in CONFIG_SCHEMA.editable_fields:
        try:
            resolutions[field.key] = resolve_field(field, values, strict=True)
        except (TypeError, ValueError) as exc:
            errors[field.key] = str(exc)
    if not errors:
        errors.update(
            _cross_field_errors({key: resolution.value for key, resolution in resolutions.items()})
        )
    if errors:
        raise ConfigValidationError(errors)
    return resolutions


def effective_config() -> dict[str, Any]:
    return {key: resolution.value for key, resolution in resolve_config().items()}


get_effective_config = effective_config


def effective_config_metadata() -> list[dict[str, Any]]:
    """返回 API 字段列表并区分已发布值与尚未 reload 的当前配置。"""
    resolutions = resolve_config()
    published = non_sensitive_snapshot()
    # ``value/source/config_revision`` 是已发布快照；当前环境只放到
    # ``configured_*``。这样外部环境在未 reload 时会显式显示 pending，不能把
    # 尚未生效的值伪装成当前 effective value。
    revision = published.revision
    out: list[dict[str, Any]] = []
    # 保留旧 WebUI 的展示分组/顺序投影（其中两项 Codex refresh 字段在
    # “定时任务”和“Codex”各显示一次），但每个 key 的解析和 snapshot 仍只
    # 使用 CONFIG_SCHEMA 中的一份 canonical 定义。
    for item in CONFIG_SCHEMA.editor_metadata():
        field = CONFIG_SCHEMA.get(item["key"])
        if field is None:
            continue
        resolution = resolutions[field.key]
        configured_value = "" if field.secret else field.public_value(resolution.value)
        published_value = "" if field.secret else published.get(
            field.key,
            field.public_value(field.clone_default()),
        )
        published_source = published.sources.get(field.key, "default")
        published_source_key = field.key if published_source == "env" else None
        pending_reload = (
            resolution.invalid
            or resolution.source != published_source
            or (not field.secret and configured_value != published_value)
        )
        item.update({
            # Backward-compatible names now have an explicit published meaning.
            "value": published_value,
            "source": published_source,
            "published_effective_value": published_value,
            "published_effective_source": published_source,
            "published_source_key": published_source_key,
            "published_revision": revision,
            "configured_value": configured_value,
            "configured_source": resolution.source,
            "configured_source_key": resolution.source_key,
            "pending_reload": pending_reload,
            "pending": pending_reload,
            "source_key": published_source_key,
            "configured": bool(resolution.configured),
            "invalid_env": bool(resolution.invalid),
            "config_revision": revision,
        })
        # 不让 secret 的默认/别名/错误信息意外进入响应。
        if field.secret:
            item.pop("default", None)
        out.append(item)
    return out


class ConfigSnapshot:
    """不可变、无敏感字段的任务配置快照。"""

    __slots__ = ("revision", "values", "sources")

    def __init__(self, values: Mapping[str, Any], sources: Mapping[str, str], revision: int):
        object.__setattr__(self, "revision", int(revision))
        object.__setattr__(self, "values", MappingProxyType({
            key: _freeze(value) for key, value in values.items()
        }))
        object.__setattr__(self, "sources", MappingProxyType(dict(sources)))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ConfigSnapshot 是不可变对象")

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return {key: _thaw(value) for key, value in self.values.items()}

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __iter__(self):
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return copy.deepcopy(value)


_SNAPSHOT_LOCK = threading.Lock()
_PUBLISHED_SNAPSHOT: ConfigSnapshot | None = None


def build_non_sensitive_snapshot(
    env_values: Mapping[str, str] | None = None,
    *,
    strict: bool = True,
) -> ConfigSnapshot:
    """离线解析并构建候选快照，不发布到全局引用。"""
    resolutions = resolve_config(env_values, strict=strict)
    values = {
        field.key: field.public_value(resolutions[field.key].value)
        for field in CONFIG_SCHEMA.editable_fields
        if not field.secret
    }
    sources = {
        field.key: resolutions[field.key].source
        for field in CONFIG_SCHEMA.editable_fields
    }
    return ConfigSnapshot(values, sources, revision=0)


def publish_config_snapshot(candidate: ConfigSnapshot) -> ConfigSnapshot:
    """将已构建候选以一次 reference swap 发布，并绑定 revision。"""
    if not isinstance(candidate, ConfigSnapshot):
        raise TypeError("candidate 必须是 ConfigSnapshot")
    global _PUBLISHED_SNAPSHOT
    with _SNAPSHOT_LOCK:
        previous = _PUBLISHED_SNAPSHOT
        revision = previous.revision + 1 if previous is not None else 0
        # 构建完整不可变对象后只执行一次全局引用替换；读者拿到的对象中
        # values/sources/revision 永远属于同一版本。
        published = ConfigSnapshot(candidate.values, candidate.sources, revision)
        _PUBLISHED_SNAPSHOT = published
        return published


def _published_snapshot() -> ConfigSnapshot:
    global _PUBLISHED_SNAPSHOT
    snapshot = _PUBLISHED_SNAPSHOT
    if snapshot is not None:
        return snapshot
    # 首次读取兼容坏环境变量的历史回退语义；严格校验留给 reload/save。
    candidate = build_non_sensitive_snapshot(strict=False)
    with _SNAPSHOT_LOCK:
        if _PUBLISHED_SNAPSHOT is None:
            _PUBLISHED_SNAPSHOT = ConfigSnapshot(candidate.values, candidate.sources, 0)
        return _PUBLISHED_SNAPSHOT


def config_revision() -> int:
    return _published_snapshot().revision


def mark_config_revision(candidate: ConfigSnapshot | None = None) -> int:
    """兼容旧调用方；新 reload 应显式传入已预构建候选。"""
    prepared = candidate if candidate is not None else build_non_sensitive_snapshot(strict=True)
    return publish_config_snapshot(prepared).revision


def non_sensitive_snapshot() -> ConfigSnapshot:
    """返回当前已发布的稳定快照；不重新读取环境或逐项拼装。"""
    return _published_snapshot()


get_non_sensitive_snapshot = non_sensitive_snapshot
snapshot_non_sensitive = non_sensitive_snapshot
get_config_snapshot = non_sensitive_snapshot


def render_env_example_section() -> str:
    """从 schema 生成 WebUI editable 配置段，供 .env.example/工具复用。"""
    lines = [
        "# ---- WebUI editable config (generated from config.schema) ----",
        "# 修改配置请使用 WebUI 或复制到 .env；secret 字段保持为空。",
    ]
    current_group = None
    for field in CONFIG_SCHEMA.editable_fields:
        if field.group != current_group:
            current_group = field.group
            lines.extend(["", f"# [{current_group}]"])
        if field.help:
            lines.append(f"# {field.help}")
        if field.options:
            labels = ", ".join(option.value for option in field.options if option.value)
            if labels:
                lines.append(f"# options: {labels}")
        if field.secret or field.default in (None, ""):
            rendered = ""
        elif field.type == "bool":
            rendered = "True" if field.default else "False"
        elif field.type == "list_str_multiline":
            rendered = "\n".join(str(item) for item in field.default)
        else:
            rendered = str(field.default)
        lines.append(f"{field.key}={rendered}")
    lines.extend(["", "# ---- end generated config ----"])
    return "\n".join(lines) + "\n"


def render_env_example() -> str:
    """稳定的 `.env.example` 可编辑配置段生成入口。"""
    return render_env_example_section()


def apply_env_namespace(namespace: dict[str, Any], explicit_schema: Mapping[str, str] | None = None) -> None:
    """供 env_loader 调用的中央环境覆盖实现。"""
    from config.env_loader import ensure_loaded

    ensure_loaded()
    module = namespace.get("__name__")
    if explicit_schema is not None:
        fields = [
            ConfigField(
                key=key,
                file=None,
                type=value_type,
                default=copy.deepcopy(namespace.get(key)),
                group="其他",
                label=key,
                help="兼容环境变量",
                editable=False,
            )
            for key, value_type in explicit_schema.items()
            if key in namespace
        ]
    else:
        fields = CONFIG_SCHEMA.fields_for_module(module, namespace)

    for field in fields:
        if os.getenv(field.key) is None:
            continue
        raw = os.getenv(field.key, "")
        if not str(raw).strip() and not (field.type == "list_str_multiline" and field.key == "PROXY_POOL"):
            continue
        try:
            # 兼容旧模块的 protocol_direct 等别名：模块常量保留旧值，API 再公共化。
            namespace[field.key] = _validate_value(field, raw, strict=True)
            if field.type == "str" and raw.strip() in field.aliases:
                namespace[field.key] = raw.strip()
        except (TypeError, ValueError):
            # 与历史 env_value 行为一致：坏环境变量不让进程启动时被单字段击穿，
            # 但 WebUI 保存路径会严格拒绝同样的候选值。
            namespace[field.key] = copy.deepcopy(field.default)


__all__ = [
    "CONFIG_SCHEMA", "SCHEMA", "CONFIG_FIELDS", "DEFAULTS", "ConfigField",
    "ConfigOption", "ConfigResolution", "ConfigSnapshot", "ConfigSchema",
    "ConfigValidationError", "LEGACY_ENV_OVERRIDE_TYPES", "schema_default",
    "validate_value", "validate_config_updates", "resolve_config", "resolve_field",
    "effective_config", "get_effective_config", "effective_config_metadata",
    "non_sensitive_snapshot", "get_non_sensitive_snapshot", "snapshot_non_sensitive",
    "get_config_snapshot", "config_revision", "mark_config_revision",
    "build_non_sensitive_snapshot", "publish_config_snapshot",
    "render_env_example_section", "render_env_example", "apply_env_namespace",
]
