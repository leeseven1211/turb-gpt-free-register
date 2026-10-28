# -*- coding: utf-8 -*-
"""任务错误的统一展示分类。

这里只做稳定、无副作用的展示投影，不改写原始错误和数据库记录。注册任务、Codex/2FA
补跑及账号操作任务都可复用同一套分类口径；完整技术信息仍保留在日志中。
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any

from core.task_stages import STAGES, normalize_stage


class TaskErrorCode(str, Enum):
    """任务层共享的稳定错误码，不携带远端原文或敏感上下文。"""

    CONFIGURATION = "configuration.missing"
    USER_INTERRUPTED = "user.interrupted"
    SERVICE_INTERRUPTED = "service.interrupted"
    EXTERNAL_PROXY = "external.proxy"
    EXTERNAL_ROXY_CAPACITY = "external.roxy_capacity"
    EXTERNAL_ROXY = "external.roxy"
    EXTERNAL_EMAIL = "external.email"
    EXTERNAL_EMAIL_EMAIL_BUTLER_PREPARE = "external.email.email_butler_prepare"
    EXTERNAL_EMAIL_SERVICE_UNAVAILABLE = "external.email.service_unavailable"
    EXTERNAL_EMAIL_ACCOUNT_MISSING = "external.email.account_missing"
    EXTERNAL_EXTRACT_REJECTED = "external.extract_link.rejected"
    EXTERNAL_OPENAI = "external.openai"
    EXTERNAL_OPENAI_ACCOUNT_CREATION_REJECTED = "external.openai.account_creation_rejected"
    EXTERNAL_OPENAI_REGISTRATION_REJECTED = "external.openai.registration_rejected"
    EXTERNAL_OPENAI_CREDENTIAL_EXPIRED = "external.openai.credential_expired"
    EXTERNAL_OPENAI_AUTH_REAUTH_REQUIRED = "external.openai.auth_reauth_required"
    EXTERNAL_OPENAI_AUTH_ROUTE_REJECTED = "external.openai.auth_route_rejected"
    EXTERNAL_OPENAI_PLAN_FORBIDDEN = "external.openai.plan_forbidden"
    EXTERNAL_OPENAI_EMAIL_CHANGE_ACCOUNT_TOO_NEW = "external.openai.email_change_account_too_new"
    EXTERNAL_OPENAI_EMAIL_CHANGE_FORBIDDEN = "external.openai.email_change_forbidden"
    EXTERNAL_OPENAI_EMAIL_CHANGE_RECENT_LOGIN = "external.openai.email_change_recent_login"
    EXTERNAL_OPENAI_EMAIL_CHANGE_REJECTED = "external.openai.email_change_rejected"
    EXTERNAL_OPENAI_EMAIL_CHANGE_INCOMPLETE = "external.openai.email_change_incomplete"
    EXTERNAL_OPENAI_EMAIL_CHANGE_FAILED = "external.openai.email_change_failed"
    EXTERNAL_OPENAI_EMAIL_DOMAIN_REJECTED = "external.openai.email_domain_rejected"
    EXTERNAL_NETWORK_MFA_TRANSPORT = "external.network.mfa_transport"
    EXTERNAL_NETWORK_REGISTRATION_TIMEOUT = "external.network.registration_timeout"
    EXTERNAL_NETWORK = "external.network"
    ACCOUNT_DEACTIVATED = "account.deactivated"
    ACCOUNT_TARGET_UNAVAILABLE = "account.target_unavailable"
    ACCOUNT_EMAIL_ALREADY_USED = "account.email_already_used"
    ACCOUNT_EMAIL_MATCHES_CURRENT = "account.email_matches_current"
    INTERNAL_STORAGE = "internal.storage"
    INTERNAL_CODE = "internal.code"
    INTERNAL_BROWSER = "internal.browser"
    INTERNAL_REQUEST_PREPARE = "internal.request_prepare"
    WORKFLOW_VERIFICATION = "workflow.verification"
    WORKFLOW_PAGE_STATE = "workflow.page_state"
    WORKFLOW_PASSWORD_ENTRY_NOT_HYDRATED = "workflow.password_entry_not_hydrated"
    WORKFLOW_PASSWORD_ENTRY_NOT_OFFERED = "workflow.password_entry_not_offered"
    WORKFLOW_PASSWORD_ENTRY_RECOVERY_EXHAUSTED = "workflow.password_entry_recovery_exhausted"
    WORKFLOW_PASSWORD_SETTINGS_ENTRY_UNAVAILABLE = "workflow.password_settings_entry_unavailable"
    WORKFLOW_RETRY_BLOCKED = "workflow.retry_blocked"
    WORKFLOW_UNSUPPORTED = "workflow.unsupported"
    TASK_PENDING = "task.pending"
    REQUEST_UNKNOWN = "request_unknown"
    UNKNOWN = "unknown.unclassified"


# Some callers use the shorter domain name; keep one enum rather than creating
# a second set of values that could drift from the task projection rules.
ErrorCode = TaskErrorCode


def stable_error_code(value: Any, *, default: str = TaskErrorCode.UNKNOWN.value) -> str:
    """从异常、mapping 或结构化步骤结果读取安全错误码。"""
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, dict):
        value = value.get("error_code") or value.get("code") or value.get("error")
    code = str(value or "").strip()
    if not code:
        return default
    return code[:120]


def is_request_unknown(value: Any) -> bool:
    """兼容读取远端回执状态；只决定恢复约束，不作为展示的主错误码。"""
    if isinstance(value, dict) and (
        value.get("request_unknown") is True
        or value.get("reconcile_required") is True
        or str(value.get("outcome") or "").strip().lower() == "request_unknown"
    ):
        return True
    return stable_error_code(value, default="").lower() in {
        "request_unknown",
        "password_result_unknown",
    }


_RULES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        "account.deactivated",
        "account",
        "账号状态",
        "账号已停用",
        ("account_deactivated", "账号已废", "账号已停用"),
    ),
    (
        "account.target_unavailable",
        "account",
        "账号状态",
        "操作目标已不可用",
        ("账号已删除或提链状态已被重置",),
    ),
    (
        "external.network.mfa_transport",
        "external",
        "网络 / 上游服务",
        "2FA 通道网络错误",
        ("twofaprotocoltransporterror", "transport failed after retry", "enroll transport failed", "activate transport failed"),
    ),
    (
        "task.pending",
        "system",
        "任务状态",
        "套餐查询等待执行",
        ("套餐查询待处理", "套餐查询待重试", "套餐查询已入队"),
    ),
    (
        "workflow.password_entry_not_hydrated",
        "workflow",
        "流程错误",
        "密码入口页面未加载",
        ("password_entry_page_not_hydrated",),
    ),
    (
        "workflow.password_entry_not_offered",
        "workflow",
        "流程错误",
        "当前流程未提供密码入口",
        ("password_entry_not_offered",),
    ),
    (
        "workflow.password_entry_recovery_exhausted",
        "workflow",
        "流程错误",
        "密码入口页面恢复已用尽",
        ("password_entry_recovery_exhausted",),
    ),
    (
        "workflow.password_settings_entry_unavailable",
        "workflow",
        "流程错误",
        "账号设置页没有添加密码入口",
        ("未找到“add password/设置密码”入口", "只提供当前密码输入框"),
    ),
    (
        "configuration.missing",
        "configuration",
        "配置错误",
        "缺少配置",
        ("未配置", "配置缺失", "请填写", "api key 为空", "token 为空", "不能为空", "cloudflare 邮箱凭据缺失"),
    ),
    (
        "service.interrupted",
        "system",
        "系统事件",
        "服务重启中断",
        (
            "webui 进程重启导致任务中断",
            "webui 重启导致任务中断，请重新执行",
            "执行进程中断，等待同一 attempt 恢复",
            "worker_interrupted",
            "run.interrupted",
        ),
    ),
    (
        "user.interrupted",
        "user",
        "用户操作",
        "任务被停止",
        ("用户手动停止", "用户手动取消", "用户取消", "已取消", "收到停止请求", "收到取消请求", "取消请求"),
    ),
    (
        "external.openai.credential_expired",
        "external",
        "OpenAI / ChatGPT",
        "授权已失效",
        (
            "at已过期", "at已失效", "accesstoken 已过期", "access token 已过期",
            "access_token 已过期", "现有 accesstoken 已过期", "token expired", "token invalid",
        ),
    ),
    (
        "external.openai.auth_reauth_required",
        "external",
        "OpenAI / ChatGPT",
        "授权已失效",
        ("reauth_required", "refresh_token_reused", "invalid_refresh_token", "refresh_token_invalidated"),
    ),
    (
        "external.email.account_missing",
        "external",
        "邮箱 / 验证码服务",
        "邮箱服务账号不存在",
        ("email is not registered for openai", "email account not found", "account not found"),
    ),
    (
        "external.email.service_unavailable",
        "external",
        "邮箱 / 验证码服务",
        "邮箱服务暂时不可用",
        (
            "email butler 请求失败", "email butler request failed", "signals/scan",
            "passwordless/send-otp", "email butler", "邮箱服务暂时不可用",
        ),
    ),
    (
        "external.openai.auth_route_rejected",
        "external",
        "OpenAI / ChatGPT",
        "授权路由被拒绝",
        ("auth_route_rejected", "auth authorize 路由被拒绝"),
    ),
    (
        "internal.code",
        "internal",
        "内部错误",
        "本地代码错误",
        ("syntaxerror", "cannot schedule new futures after interpreter shutdown", "账号配置重试未返回结果"),
    ),
    (
        "workflow.retry_blocked",
        "workflow",
        "流程错误",
        "原邮箱不可用，不能安全重试",
        ("原注册邮箱不再处于保留状态", "不能改用其他邮箱重跑"),
    ),
    (
        "workflow.page_state",
        "workflow",
        "流程错误",
        "页面未进入下一步",
        ("资料页点击提交后", "仍未离开", "页面未继续", "提交本地 totp 后页面 20 秒未继续"),
    ),
    (
        "external.roxy_capacity",
        "external",
        "外部错误",
        "Roxy 窗口容量",
        (
            "窗口额度不足", "窗口数量已达上限", "窗口数已达上限", "窗口达到上限",
            "窗口单日创建次数已经超出", "window quota", "window limit",
            "maximum number of windows", "too many windows",
        ),
    ),
    (
        "external.roxy",
        "external",
        "外部错误",
        "Roxy 浏览器服务",
        (
            "roxy api", "roxybrowser", "roxy 创建环境", "/browser/create",
            "/browser/open", "selenium/调试地址",
        ),
    ),
    (
        "external.proxy",
        "external",
        "外部错误",
        "代理服务",
        ("proxy", "代理", "duplicateproxy", "提取 ip", "出口 ip"),
    ),
    (
        "external.email",
        "external",
        "外部错误",
        "邮箱 / 验证码服务",
        (
            "邮箱池", "邮箱服务", "收码", "otp service", "邮件服务", "验证码接口",
            "imap", "gmail", "验证码邮件", "等待验证码超时", "otp_request_unconfirmed",
            "otp_reused_after_resend", "otp_invalid_or_expired", "otp_delivery_missing",
            "验证码重发", "icloud hme 批量扫描缺少有效账号",
        ),
    ),
    (
        "external.openai.account_creation_rejected",
        "external",
        "OpenAI / ChatGPT",
        "账号创建被上游拒绝",
        (
            "account_create_rejected",
            "利用規約のため、お客様のアカウントを作成できません",
            "アカウントを作成できません",
            "can't create your account",
            "cannot create your account",
            "account cannot be created",
            "无法创建账号",
            "无法创建您的账号",
        ),
    ),
    (
        "external.openai",
        "external",
        "外部错误",
        "OpenAI / Codex",
        (
            "openai", "chatgpt", "codex", "oauth", "authenticator", "2fa", "/api/auth/session",
            "otp_page_navigation_failed",
            "/accounts/change_email/",
        ),
    ),
    (
        "internal.storage",
        "internal",
        "内部错误",
        "数据存储",
        ("postgres", "database", "数据库", "数据写入", "持久化", "undefinedcolumn", "deadlock detected"),
    ),
    (
        "internal.browser",
        "internal",
        "内部错误",
        "浏览器自动化",
        (
            "playwright", "浏览器启动", "roxybrowser", "browsercontext", "page crashed",
            "staleelementreferenceexception", "invalidsessionidexception", "javascriptexception",
        ),
    ),
    (
        "workflow.verification",
        "workflow",
        "流程错误",
        "验证流程",
        ("验证码超时", "邮箱验证码", "验证失败", "verification"),
    ),
    (
        "workflow.page_state",
        "workflow",
        "流程错误",
        "页面状态不符合预期",
        ("未识别到", "无法切换", "未进入", "页面状态", "当前页面", "state="),
    ),
    (
        "workflow.unsupported",
        "workflow",
        "流程错误",
        "当前功能不支持",
        ("不支持", "unsupported", "not supported"),
    ),
    (
        "external.network.registration_timeout",
        "external",
        "网络 / 上游服务",
        "注册认证跳转超时",
        (
            "roxy registration stage timeout exhausted",
            "邮箱提交/认证跳转超过总预算",
        ),
    ),
    (
        "external.network",
        "external",
        "外部错误",
        "网络 / 上游服务",
        (
            "httperror", "connection", "timeout", "timed out", "http error 5", "网络",
            "password_result_unknown", "ssl_error", "err_ssl_", "socket hang up",
            "connection reset", "client network socket", "tls connect", "read timeout",
        ),
    ),
)

_SOURCE_LABELS = {
    "configuration": "配置错误",
    "user": "用户操作",
    "external": "外部错误",
    "internal": "内部错误",
    "workflow": "流程错误",
    "unknown": "诊断证据不足",
    "system": "系统事件",
}

_COARSE_PROJECTED_ERROR_CODES = {
    TaskErrorCode.EXTERNAL_EMAIL.value,
    TaskErrorCode.EXTERNAL_OPENAI.value,
    TaskErrorCode.UNKNOWN.value,
    TaskErrorCode.REQUEST_UNKNOWN.value,
}

_EMAIL_CHANGE_RULES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        TaskErrorCode.ACCOUNT_EMAIL_ALREADY_USED.value,
        "账号状态",
        "目标邮箱已被使用",
        "目标邮箱已被本地账号使用，换绑尚未提交；请更换邮箱后重试",
        ("目标邮箱已被本地账号占用",),
    ),
    (
        TaskErrorCode.ACCOUNT_EMAIL_MATCHES_CURRENT.value,
        "邮箱准备",
        "目标邮箱与当前邮箱相同",
        "领取到的邮箱与当前邮箱相同，换绑尚未提交；请重新领取邮箱后重试",
        ("领取到的邮箱与当前邮箱相同",),
    ),
    (
        TaskErrorCode.EXTERNAL_OPENAI_EMAIL_DOMAIN_REJECTED.value,
        "OpenAI / ChatGPT",
        "目标邮箱域名被拒绝",
        "OpenAI 拒绝该目标邮箱域名，请更换域名后再试",
        ("email_domain_rejected",),
    ),
    (
        TaskErrorCode.EXTERNAL_OPENAI_EMAIL_CHANGE_ACCOUNT_TOO_NEW.value,
        "OpenAI / ChatGPT",
        "账号注册时间不足",
        "账号注册时间不足，暂不允许换绑邮箱",
        ("email_change_account_too_new",),
    ),
    (
        TaskErrorCode.EXTERNAL_OPENAI_EMAIL_CHANGE_RECENT_LOGIN.value,
        "OpenAI / ChatGPT",
        "Recent Login 认证失败",
        "Recent Login 认证失败，尚未提交目标邮箱",
        ("recent login",),
    ),
    (
        TaskErrorCode.EXTERNAL_EMAIL_EMAIL_BUTLER_PREPARE.value,
        "EmailButler",
        "EmailButler 邮箱准备失败",
        "EmailButler 未能准备目标邮箱（HTTP {http_status}）",
        ("邮箱准备失败", "email butler"),
    ),
)

# These values are intentionally strings rather than booleans.  A retry can be
# technically possible while still being unsafe after an irreversible remote
# request, so consumers need the distinction for recovery UX.
_ERROR_METADATA: dict[str, dict[str, str]] = {
    "account.deactivated": {
        "retryability": "not_retryable",
        "remote_state_impact": "remote_confirmed",
        "next_action": "none",
    },
    "account.email_already_used": {
        "retryability": "retryable",
        "remote_state_impact": "not_started",
        "next_action": "retry_email_prepare",
    },
    "account.email_matches_current": {
        "retryability": "retryable",
        "remote_state_impact": "not_started",
        "next_action": "retry_email_prepare",
    },
    "account.target_unavailable": {
        "retryability": "not_retryable",
        "remote_state_impact": "not_started",
        "next_action": "inspect_account_state",
    },
    "task.pending": {
        "retryability": "conditional",
        "remote_state_impact": "unknown",
        "next_action": "wait_for_task",
    },
    "service.interrupted": {
        "retryability": "retryable",
        "remote_state_impact": "unknown",
        "next_action": "resume_or_reconcile",
    },
    "configuration.missing": {
        "retryability": "not_retryable",
        "remote_state_impact": "not_started",
        "next_action": "fix_configuration",
    },
    "user.interrupted": {
        "retryability": "manual_only",
        "remote_state_impact": "unknown",
        "next_action": "resume_or_reconcile",
    },
    "external.proxy": {
        "retryability": "retryable",
        "remote_state_impact": "not_started_or_unknown",
        "next_action": "retry_with_new_proxy",
    },
    "external.roxy_capacity": {
        "retryability": "retryable",
        "remote_state_impact": "not_started",
        "next_action": "retry_when_capacity_available",
    },
    "external.roxy": {
        "retryability": "conditional",
        "remote_state_impact": "not_started_or_unknown",
        "next_action": "reconcile_roxy_profile",
    },
    "external.email": {
        "retryability": "retryable",
        "remote_state_impact": "unchanged_or_unknown",
        "next_action": "retry_email_wait",
    },
    "external.email.email_butler_prepare": {
        "retryability": "retryable",
        "remote_state_impact": "not_started",
        "next_action": "retry_email_prepare",
    },
    "external.email.service_unavailable": {
        "retryability": "retryable",
        "remote_state_impact": "unknown",
        "next_action": "retry_email_service",
    },
    "external.email.account_missing": {
        "retryability": "conditional",
        "remote_state_impact": "unknown",
        "next_action": "check_email_service",
    },
    "external.openai": {
        "retryability": "conditional",
        "remote_state_impact": "unknown",
        "next_action": "reconcile_session",
    },
    "external.openai.registration_rejected": {
        "retryability": "conditional",
        "remote_state_impact": "remote_rejected",
        "next_action": "inspect_remote_rejection",
    },
    "external.openai.credential_expired": {
        "retryability": "conditional",
        "remote_state_impact": "unknown",
        "next_action": "refresh_credential",
    },
    "external.openai.auth_reauth_required": {
        "retryability": "manual_only",
        "remote_state_impact": "unknown",
        "next_action": "reauthenticate_before_retry",
    },
    "external.openai.auth_route_rejected": {
        "retryability": "conditional",
        "remote_state_impact": "remote_rejected",
        "next_action": "inspect_remote_rejection",
    },
    "external.openai.plan_forbidden": {
        "retryability": "conditional",
        "remote_state_impact": "remote_unchanged",
        "next_action": "inspect_plan_auth_route",
    },
    "external.openai.email_domain_rejected": {
        "retryability": "not_retryable",
        "remote_state_impact": "remote_rejected",
        "next_action": "change_email_domain",
    },
    "external.openai.email_change_account_too_new": {
        "retryability": "conditional",
        "remote_state_impact": "remote_rejected",
        "next_action": "wait_for_account_age",
    },
    "external.openai.email_change_forbidden": {
        "retryability": "conditional",
        "remote_state_impact": "remote_rejected",
        "next_action": "reauthenticate_before_retry",
    },
    "external.openai.email_change_recent_login": {
        "retryability": "retryable",
        "remote_state_impact": "not_started",
        "next_action": "reauthenticate_before_retry",
    },
    "external.openai.email_change_rejected": {
        "retryability": "manual_only",
        "remote_state_impact": "remote_rejected",
        "next_action": "inspect_remote_rejection",
    },
    "external.openai.email_change_incomplete": {
        "retryability": "manual_only",
        "remote_state_impact": "unknown",
        "next_action": "inspect_remote_state",
    },
    "external.openai.email_change_failed": {
        "retryability": "manual_only",
        "remote_state_impact": "unknown",
        "next_action": "inspect_remote_state",
    },
    "external.openai.account_creation_rejected": {
        "retryability": "retryable",
        "remote_state_impact": "remote_rejected_or_pending",
        "next_action": "registration_resume",
    },
    "external.network.mfa_transport": {
        "retryability": "retryable",
        "remote_state_impact": "account_core_confirmed",
        "next_action": "retry_twofa_with_fresh_transport",
    },
    "external.network.registration_timeout": {
        "retryability": "retryable",
        "remote_state_impact": "not_started_or_unknown",
        "next_action": "retry_with_new_proxy",
    },
    "internal.storage": {
        "retryability": "retryable",
        "remote_state_impact": "remote_unchanged",
        "next_action": "retry_persistence",
    },
    "internal.code": {
        "retryability": "not_retryable",
        "remote_state_impact": "unknown",
        "next_action": "fix_local_code",
    },
    "internal.browser": {
        "retryability": "retryable",
        "remote_state_impact": "unknown",
        "next_action": "resume_or_reconcile",
    },
    "workflow.verification": {
        "retryability": "conditional",
        "remote_state_impact": "remote_may_be_confirmed",
        "next_action": "resume_email_verification",
    },
    "workflow.page_state": {
        "retryability": "conditional",
        "remote_state_impact": "unknown",
        "next_action": "reconcile_session",
    },
    "workflow.password_entry_not_hydrated": {
        "retryability": "retryable",
        "remote_state_impact": "remote_may_be_pending",
        "next_action": "retry_registration",
    },
    "workflow.password_entry_not_offered": {
        "retryability": "conditional",
        "remote_state_impact": "remote_may_be_pending",
        "next_action": "retry_registration",
    },
    "workflow.password_entry_recovery_exhausted": {
        "retryability": "retryable",
        "remote_state_impact": "remote_may_be_pending",
        "next_action": "retry_registration",
    },
    "workflow.password_settings_entry_unavailable": {
        "retryability": "conditional",
        "remote_state_impact": "remote_unchanged",
        "next_action": "inspect_account_settings",
    },
    "workflow.retry_blocked": {
        "retryability": "not_retryable",
        "remote_state_impact": "unknown",
        "next_action": "restore_email_lease",
    },
    "workflow.unsupported": {
        "retryability": "not_retryable",
        "remote_state_impact": "remote_rejected",
        "next_action": "none",
    },
    "external.network": {
        "retryability": "retryable",
        "remote_state_impact": "unknown",
        "next_action": "retry_request_or_reconcile",
    },
    "unknown.unclassified": {
        "retryability": "manual_only",
        "remote_state_impact": "unknown",
        "next_action": "manual_reconcile",
    },
}

_DISPLAY_CODES = {
    "configuration.missing": "CFG-001",
    "user.interrupted": "USR-001",
    "service.interrupted": "SYS-002",
    "account.deactivated": "ACCT-001",
    "account.target_unavailable": "ACCT-002",
    "account.email_already_used": "ACCT-003",
    "account.email_matches_current": "ACCT-004",
    "task.pending": "STATE-001",
    "external.proxy": "PROXY-001",
    "external.roxy_capacity": "ROXY-002",
    "external.roxy": "ROXY-001",
    "external.email": "MAIL-001",
    "external.email.email_butler_prepare": "MAIL-004",
    "external.email.service_unavailable": "MAIL-002",
    "external.email.account_missing": "MAIL-003",
    "external.extract_link.rejected": "LINK-HTTP-000",
    "external.openai": "OA-000",
    "external.openai.account_creation_rejected": "OA-REG-001",
    "external.openai.registration_rejected": "OA-REG-000",
    "external.openai.credential_expired": "AUTH-001",
    "external.openai.auth_reauth_required": "AUTH-002",
    "external.openai.auth_route_rejected": "OA-AUTH-000",
    "external.openai.plan_forbidden": "OA-PLAN-403",
    "external.openai.email_change_account_too_new": "OA-EMAIL-002",
    "external.openai.email_change_forbidden": "OA-EMAIL-003",
    "external.openai.email_change_recent_login": "OA-EMAIL-004",
    "external.openai.email_change_rejected": "OA-EMAIL-005",
    "external.openai.email_change_incomplete": "OA-EMAIL-001",
    "external.openai.email_change_failed": "OA-EMAIL-000",
    "external.openai.email_domain_rejected": "OA-EMAIL-006",
    "external.network.mfa_transport": "NET-002",
    "external.network.registration_timeout": "NET-003",
    "external.network": "NET-001",
    "internal.storage": "SYS-DB-001",
    "internal.code": "SYS-CODE-001",
    "internal.browser": "SYS-BROWSER-001",
    "internal.request_prepare": "SYS-REQ-001",
    "workflow.verification": "FLOW-VERIFY-001",
    "workflow.page_state": "FLOW-PAGE-001",
    "workflow.password_entry_not_hydrated": "FLOW-PWD-001",
    "workflow.password_entry_not_offered": "FLOW-PWD-002",
    "workflow.password_entry_recovery_exhausted": "FLOW-PWD-003",
    "workflow.password_settings_entry_unavailable": "FLOW-PWD-004",
    "workflow.retry_blocked": "FLOW-RETRY-001",
    "workflow.unsupported": "FLOW-UNSUPPORTED-001",
    "unknown.unclassified": "UNK-000",
}

_DISPLAY_SUMMARIES = {
    "configuration.missing": "配置缺失",
    "user.interrupted": "任务已取消",
    "service.interrupted": "服务重启导致任务中断",
    "account.deactivated": "账号已停用",
    "account.target_unavailable": "账号已删除或提链状态已重置",
    "account.email_already_used": "目标邮箱已被使用",
    "account.email_matches_current": "目标邮箱与当前邮箱相同",
    "task.pending": "套餐查询等待执行",
    "external.proxy": "代理获取失败",
    "external.roxy_capacity": "Roxy 窗口额度不足",
    "external.roxy": "Roxy 浏览器服务异常",
    "external.email": "邮箱 / 验证码服务异常",
    "external.email.email_butler_prepare": "邮箱准备失败",
    "external.email.service_unavailable": "邮箱服务暂时不可用",
    "external.email.account_missing": "邮箱服务账号不存在",
    "external.extract_link.rejected": "提链创建请求被远端拒绝",
    "external.openai": "OpenAI / Codex 服务异常",
    "external.openai.account_creation_rejected": "账号创建被上游拒绝",
    "external.openai.credential_expired": "授权已失效，请刷新 AT",
    "external.openai.auth_reauth_required": "授权已失效，请重新登录",
    "external.openai.auth_route_rejected": "授权路由被拒绝",
    "external.openai.plan_forbidden": "套餐查询接口返回 HTTP 403",
    "external.openai.email_change_account_too_new": "账号注册时间不足，暂不允许换绑",
    "external.openai.email_change_forbidden": "当前会话不允许换绑邮箱",
    "external.openai.email_change_recent_login": "Recent Login 认证失败",
    "external.openai.email_change_rejected": "邮箱换绑请求被拒绝",
    "external.openai.email_change_incomplete": "邮箱换绑未完成",
    "external.openai.email_change_failed": "邮箱换绑失败",
    "external.openai.email_domain_rejected": "目标邮箱域名被拒绝",
    "external.network.mfa_transport": "2FA 通道网络异常",
    "external.network.registration_timeout": "注册认证跳转超时",
    "external.network": "网络 / 上游服务异常",
    "internal.storage": "数据存储异常",
    "internal.code": "本地代码错误",
    "internal.browser": "浏览器自动化异常",
    "internal.request_prepare": "请求在本地准备阶段失败",
    "workflow.verification": "验证流程失败",
    "workflow.page_state": "页面未进入下一步",
    "workflow.password_entry_not_hydrated": "密码入口页面未加载",
    "workflow.password_entry_not_offered": "当前流程未提供密码入口",
    "workflow.password_entry_recovery_exhausted": "密码入口页面恢复失败",
    "workflow.password_settings_entry_unavailable": "账号设置页没有添加密码入口",
    "workflow.retry_blocked": "原邮箱不可用，不能安全重试",
    "workflow.unsupported": "当前功能不支持",
    "unknown.unclassified": "诊断证据不足，无法确认具体原因",
}


def _summary(message: str, limit: int = 160) -> str:
    value = re.sub(r"\s+", " ", str(message or "")).strip()
    value = re.sub(r"^(?:[A-Za-z_][\w.]*Error|Exception):\s*", "", value)
    return value[:limit] + ("…" if len(value) > limit else "")


def _error_projection(
    code: str,
    source: str,
    source_label: str,
    kind_label: str,
    *,
    stage: str,
    error_code: str,
    raw: str,
    summary: str | None = None,
    display_code: str | None = None,
) -> dict[str, Any]:
    resolved_display_code = display_code or _DISPLAY_CODES.get(code, "UNK-000")
    if code == TaskErrorCode.EXTERNAL_OPENAI_AUTH_ROUTE_REJECTED.value:
        status_match = re.search(r"\bHTTP(?:\s+Error)?\s*:?\s*(\d{3})\b", raw, flags=re.IGNORECASE)
        if status_match:
            resolved_display_code = f"OA-AUTH-{status_match.group(1)}"
            summary = f"授权路由被拒绝（HTTP {status_match.group(1)}）"
    result = {
        "code": code,
        "error_code": code,
        "display_code": resolved_display_code,
        "source": source,
        "source_label": source_label,
        "kind_label": kind_label,
        "title": f"{source_label} · {kind_label}",
        "summary": summary or _DISPLAY_SUMMARIES.get(code) or _summary(raw),
        "is_error": code != TaskErrorCode.TASK_PENDING.value,
    }
    result.update(_ERROR_METADATA.get(code, {}))
    supplied_error_code = str(error_code or "").strip()
    result["error_code"] = (
        code if supplied_error_code in _COARSE_PROJECTED_ERROR_CODES else supplied_error_code or code
    )
    result["stage"] = normalize_stage(stage) if stage else "unknown"
    if supplied_error_code:
        result["original_error_code"] = supplied_error_code
    return result


def _email_change_error_projection(
    raw: str,
    haystack: str,
    *,
    stage: str,
    error_code: str,
) -> dict[str, Any] | None:
    if "undefinedcolumn" in haystack:
        return None
    for code, source_label, kind_label, summary, needles in _EMAIL_CHANGE_RULES:
        if not all(needle in haystack for needle in needles):
            continue
        if code == TaskErrorCode.EXTERNAL_EMAIL_EMAIL_BUTLER_PREPARE.value:
            status_match = re.search(r"\bHTTP\s+(\d{3})\b", raw, flags=re.IGNORECASE)
            if not status_match:
                continue
            summary = summary.format(http_status=status_match.group(1))
            source = "external"
        else:
            source = "external"
        return _error_projection(
            code,
            source,
            source_label,
            kind_label,
            stage=stage,
            error_code=error_code,
            raw=raw,
            summary=summary,
        )

    if "邮箱换绑未完成" in haystack or "email_change_incomplete" in haystack:
        return _error_projection(
            TaskErrorCode.EXTERNAL_OPENAI_EMAIL_CHANGE_INCOMPLETE.value,
            "external",
            "OpenAI / ChatGPT",
            "邮箱换绑未完成",
            stage=stage,
            error_code=error_code,
            raw=raw,
            summary="邮箱换绑未完成",
        )

    if "远端拒绝邮箱换绑请求" in haystack:
        return _error_projection(
            TaskErrorCode.EXTERNAL_OPENAI_EMAIL_CHANGE_REJECTED.value,
            "external",
            "OpenAI / ChatGPT",
            "邮箱换绑请求被拒绝",
            stage=stage,
            error_code=error_code,
            raw=raw,
            summary="邮箱换绑请求被拒绝",
        )

    if "邮箱换绑失败" in haystack or "email_change_failed" in haystack:
        return _error_projection(
            TaskErrorCode.EXTERNAL_OPENAI_EMAIL_CHANGE_FAILED.value,
            "external",
            "OpenAI / ChatGPT",
            "邮箱换绑失败",
            stage=stage,
            error_code=error_code,
            raw=raw,
            summary="邮箱换绑失败",
        )

    if "/backend-api/accounts/change_email/" not in haystack:
        return None
    status_match = re.search(r"\b返回\s*(\d{3})\b", raw)
    status = status_match.group(1) if status_match else ""
    if status == "403":
        return _error_projection(
            TaskErrorCode.EXTERNAL_OPENAI_EMAIL_CHANGE_FORBIDDEN.value,
            "external",
            "OpenAI / ChatGPT",
            "邮箱换绑请求被拒绝",
            stage=stage,
            error_code=error_code,
            raw=raw,
            summary="OpenAI 拒绝当前会话的邮箱换绑请求（HTTP 403）",
        )
    suffix = f"（HTTP {status}，未返回可识别细码）" if status else "（未返回可识别细码）"
    return _error_projection(
        TaskErrorCode.EXTERNAL_OPENAI_EMAIL_CHANGE_REJECTED.value,
        "external",
        "OpenAI / ChatGPT",
        "邮箱换绑请求被拒绝",
        stage=stage,
        error_code=error_code,
        raw=raw,
        summary=f"OpenAI 拒绝邮箱换绑请求{suffix}",
    )


def _registration_error_projection(
    raw: str,
    *,
    haystack: str,
    stage: str,
    task_type: str,
    error_code: str,
) -> dict[str, Any] | None:
    if str(task_type or "").strip().lower() not in {"registration", "registration_resume"}:
        return None
    if "http error" not in haystack and "registration_failed" not in haystack:
        return None
    status_match = re.search(r"(?:HTTP\s+Error|HTTP)\s*:?[\s(]*(\d{3})", raw, flags=re.IGNORECASE)
    if not status_match:
        return None
    status = status_match.group(1)
    return _error_projection(
        TaskErrorCode.EXTERNAL_OPENAI_REGISTRATION_REJECTED.value,
        "external",
        "OpenAI / ChatGPT",
        "注册请求被拒绝",
        stage=stage,
        error_code=error_code,
        raw=raw,
        summary=f"注册请求被拒绝（HTTP {status}）",
        display_code=f"OA-REG-{status}",
    )


_BUTLER_RECIPIENT_CAUSES: dict[str, tuple[str, str]] = {
    "email_scan_connector_unsupported": ("MAIL-SCAN-001", "固定收件连接器尚不支持封号邮件扫描"),
    "source_untrusted": ("MAIL-SOURCE-001", "验证码邮件缺少可信 OpenAI 来源证据"),
    "source_authentication_failed": ("MAIL-SOURCE-002", "验证码邮件的 OpenAI 来源认证失败或矛盾"),
    "recipient_contract_unsupported": ("MAIL-RECIPIENT-001", "Email Butler 尚未支持严格收件契约"),
    "recipient_evidence_missing": ("MAIL-RECIPIENT-002", "验证码邮件缺少完整收件证据"),
    "recipient_ambiguous": ("MAIL-RECIPIENT-003", "验证码邮件存在同母地址收件歧义"),
    "recipient_mismatch": ("MAIL-RECIPIENT-004", "验证码邮件的完整收件地址不匹配"),
    "mailbox_mismatch": ("MAIL-RECIPIENT-005", "验证码邮件的最终收件箱不匹配或未配置"),
    "inbound_code_timeout": ("MAIL-RECIPIENT-006", "等待窗口内未收到符合条件的入站验证码"),
}


_CAUSE_DETAILS: dict[str, tuple[str, str]] = {
    **_BUTLER_RECIPIENT_CAUSES,
    "email_resource_expired": ("MAIL-RESOURCE-001", "原邮箱已超过有效期，请保留原身份并检查邮箱资源"),
    "email_resource_expiry_invalid": ("MAIL-RESOURCE-002", "邮箱有效期格式无效，需要明确带时区的绝对时间"),
    "email_resource_read_failed": ("MAIL-RESOURCE-003", "原邮箱取码接口不可用，请检查其状态及有效期"),
    "email_cutover_target_invalid": ("MAIL-ROUTE-001", "Butler 迁移目标配置或回执无效"),
    "email_cutover_route_changed": ("MAIL-ROUTE-002", "收件路由已变化，请重新预览后重跑"),
    "icloud_result_conflict": ("MAIL-REPORT-001", "相同操作的 HME 上报结果发生冲突"),
    "icloud_identity_not_found": ("MAIL-REPORT-002", "Butler 未找到原完整 HME 身份"),
    "email_derivation_inventory_empty": ("MAIL-STOCK-001", "可领取子地址库存不足，请先生成补充"),
    "email_derivation_identity_conflict": ("MAIL-STOCK-002", "子地址领取身份与原业务归属不一致"),
    "email_derivation_source_unsupported": ("MAIL-STOCK-003", "邮箱来源不支持子地址库存"),
    "email_derivation_profile_unavailable": ("MAIL-STOCK-004", "子地址固定收件配置不可用"),
    "email_derivation_capacity_exhausted": ("MAIL-STOCK-005", "母邮箱子地址生成额度不足"),
    "email_derivation_request_conflict": ("MAIL-STOCK-006", "子地址生成请求身份与原参数不一致"),
    "email_derivation_source_disabled": ("MAIL-STOCK-007", "该邮箱来源未启用子地址库存领取"),
    "email_derivation_parent_unavailable": ("MAIL-STOCK-008", "子地址母邮箱当前不可用"),
    "email_derivation_address_invalid": ("MAIL-STOCK-009", "母邮箱地址格式无法生成子地址"),
    "email_derivation_address_collision": ("MAIL-STOCK-010", "子地址生成遇到重复地址，请重新生成"),
    "worker_interrupted": ("SYS-WORKER-001", "执行进程中断"),
    "access_token_missing": ("AUTH-AT-001", "账号缺少可用 AT"),
    "auth_page_unknown": ("AUTH-PAGE-001", "认证页面状态未识别"),
    "auth_route_rejected": ("OA-AUTH-000", "授权路由被拒绝"),
    "auth_cloudflare_challenge": ("OA-AUTH-CF-CHALLENGE", "认证请求被 Cloudflare 挑战阻断"),
    "codex_consent_unverifiable": (
        "OA-CODEX-CONSENT-001", "Codex 授权确认页无法继续，需浏览器驱动",
    ),
    "email_otp_failed": ("MAIL-OTP-001", "邮箱验证码验证未完成"),
    "email_otp_send_failed": ("MAIL-SEND-001", "验证码发送请求失败"),
    "email_otp_send_rejected": ("MAIL-SEND-002", "验证码发送请求被拒绝"),
    "email_otp_send_unconfirmed": ("MAIL-SEND-003", "验证码发送结果未获确认"),
    "email_otp_send_no_response": ("MAIL-SEND-004", "验证码发送请求未收到响应"),
    "email_otp_send_unknown": ("MAIL-SEND-005", "验证码发送结果未确认"),
    "email_otp_no_mail": ("MAIL-OTP-005", "等待窗口内未收到验证码邮件"),
    "email_submit_unconfirmed": ("FLOW-EMAIL-001", "邮箱提交后未确认下一步"),
    "email_transition_timeout": ("FLOW-EMAIL-002", "邮箱提交或认证跳转预算耗尽"),
    "email_entry_not_ready": ("FLOW-EMAIL-003", "邮箱输入框或邮箱入口尚未就绪"),
    "browser_stage_timeout": ("FLOW-STAGE-001", "浏览器阶段等待预算耗尽，具体原因证据不足"),
    "email_change_verify_prepare_failed": (
        "OA-EMAIL-VERIFY-001", "新邮箱验证请求在本地准备阶段失败",
    ),
    "extract_create_invalid_json": ("OA-EXTRACT-001", "提链创建响应无法解析"),
    "extract_create_missing_job_id": ("OA-EXTRACT-002", "提链创建响应缺少任务 ID"),
    "extract_create_http_unknown": ("OA-EXTRACT-HTTP", "提链创建请求返回 HTTP 错误"),
    "extract_create_transport_error": ("NET-EXTRACT-001", "提链创建网络请求中断"),
    "extract_provider_failed": ("LINK-FAILED", "平台提链失败"),
    "mfa_code_missing": ("AUTH-MFA-001", "MFA 验证码不可用"),
    "mfa_factor_missing": ("AUTH-MFA-002", "MFA 验证方式不可用"),
    "mfa_issue_challenge_failed": ("AUTH-MFA-003", "MFA 挑战发起失败"),
    "mfa_issue_challenge_invalid_response": ("AUTH-MFA-004", "MFA 挑战响应无效"),
    "mfa_rejected": ("AUTH-MFA-005", "MFA 验证被拒绝"),
    "mfa_secret_invalid": ("AUTH-MFA-006", "本地 MFA 密钥格式无效"),
    "mfa_secret_missing": ("AUTH-MFA-007", "本地缺少 MFA 密钥"),
    "mfa_verify_failed": ("AUTH-MFA-008", "MFA 验证请求未完成"),
    "mfa_verify_invalid_response": ("AUTH-MFA-009", "MFA 验证响应无效"),
    "network_preflight_failed": ("NET-ROUTE-001", "认证线路预检失败"),
    "oauth_callback_failed": ("AUTH-CALLBACK-001", "OAuth 回调未完成"),
    "password_missing": ("AUTH-PWD-001", "本地缺少账号密码"),
    "password_rejected": ("AUTH-PWD-002", "账号密码被拒绝"),
    "password_rejected_email_fallback_failed": ("AUTH-PWD-003", "密码被拒且邮箱兜底未完成"),
    "password_result_unknown": ("AUTH-PWD-004", "密码提交结果未确认"),
    "password_sentinel_failed": ("AUTH-PWD-005", "密码认证前置检查失败"),
    "password_verify_failed": ("AUTH-PWD-006", "密码验证请求未完成"),
    "password_verify_invalid_response": ("AUTH-PWD-007", "密码验证响应无效"),
    "passwordless_fallback_unavailable": ("AUTH-PWD-008", "邮箱免密兜底不可用"),
    "password_login_unavailable": ("AUTH-PWD-009", "邮箱已失效，服务端未提供可用的密码登录流程"),
    "email_verification_required": ("AUTH-PWD-010", "邮箱已失效，密码登录后仍需邮箱验证"),
    "password_entry_navigation_timeout": ("FLOW-PWD-005", "创建密码页跳转超时"),
    "profile_session_read_failed": ("FLOW-PROFILE-001", "资料提交后的会话读取未完成"),
    "profile_session_unconfirmed": ("FLOW-PROFILE-002", "资料提交后的登录态未确认"),
    "profile_auth_error": ("FLOW-PROFILE-003", "资料阶段进入认证错误页"),
    "account_create_invalid_state": ("OA-REG-SESSION-001", "资料提交时认证会话已失效"),
    "post_register_failure": ("OA-REG-POST-001", "注册请求之后流程失败（细项未记录）"),
    "protocol_network_error": ("NET-AUTH-001", "协议认证网络请求失败"),
    "protocol_v2_unknown_error": ("AUTH-PROTOCOL-001", "协议认证异常（细项未记录）"),
    "refresh_driver_exception": ("SYS-REFRESH-001", "AT 刷新执行异常"),
    "roxy_not_configured": ("ROXY-REFRESH-000", "Roxy 连接配置不完整"),
    "roxy_profile_open_failed": ("ROXY-REFRESH-001", "Roxy 环境创建或启动失败"),
    "roxy_driver_attach_failed": ("ROXY-REFRESH-002", "连接 Roxy 浏览器调试端口失败"),
    "roxy_navigation_failed": ("ROXY-REFRESH-003", "Roxy 登录页面加载失败"),
    "roxy_login_failed": ("ROXY-REFRESH-004", "Roxy 登录挑战未完成"),
    "roxy_session_fetch_failed": ("ROXY-REFRESH-005", "Roxy 登录后读取会话失败"),
    "roxy_authenticated_callback_failed": ("ROXY-REFRESH-006", "Roxy 登录成功后的账号处理失败"),
    "roxy_proxy_tunnel_failed": ("NET-ROXY-001", "Roxy 代理隧道连接失败"),
    "refresh_result_invalid": ("SYS-REFRESH-RESULT", "AT 刷新驱动返回结果无效"),
    "refresh_cancelled": ("USR-REFRESH-001", "AT 刷新已取消"),
    "refresh_local_commit_failed": ("SYS-REFRESH-WRITEBACK", "AT 刷新本地写回或读回未完成"),
    "account_setup_local_commit_failed": ("SYS-SETUP-WRITEBACK", "账号配置本地写回或读回未完成"),
    "remote_response_missing": ("REQ-RESPONSE-001", "远端响应缺失"),
    "registration_checkpoint_failed": ("OA-REG-CHECKPOINT-001", "注册检查点本地写入失败"),
    "user_register_continue_url_missing": ("OA-REG-RESPONSE-001", "账号创建响应缺少后续验证地址"),
    "user_register_result_unknown": ("OA-REG-REQUEST-001", "账号创建请求结果未确认，未保留失败细项"),
    "account_create_user_already_exists": ("OA-REG-EXISTS-001", "远端提示账号已存在，完整登录态尚未确认"),
    "protocol_preauth_transport_failed": ("NET-REG-PREAUTH", "协议认证前置请求发生传输错误"),
    "protocol_post_otp_transport_failed": ("NET-REG-OTP", "已取得邮箱验证码，后续认证请求发生传输错误"),
    "protocol_auth_transport_failed": ("NET-REG-AUTH", "协议认证请求发生传输错误"),
    "protocol_auth_rejected_before_password": ("OA-REG-AUTH-PWD", "密码尚未确认时认证请求被拒绝"),
    "protocol_auth_http_failed": ("OA-REG-AUTH-HTTP", "协议认证请求返回 HTTP 错误"),
    "protocol_session_incomplete": ("FLOW-REG-SESSION", "注册资料已确认，后续登录态尚未取得"),
    "protocol_failure_evidence_missing": ("FLOW-REG-EVIDENCE", "协议失败未保留足够请求证据，无法确认具体原因"),
    "local_config_schema_mismatch": ("SYS-CONFIG-SCHEMA", "配置 schema 不匹配，请重启后重跑"),
}


# 注册驱动可以写入 Run 的固定原因码；拒绝从异常正文推断或透传任意字符串。
REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES = frozenset({
    "account_create_invalid_state",
    "account_create_user_already_exists",
    "user_register_result_unknown",
    "registration_checkpoint_failed",
    "user_register_continue_url_missing",
    "email_otp_send_rejected",
    "email_otp_send_failed",
    "email_otp_send_unconfirmed",
    "email_otp_send_no_response",
    "email_otp_send_unknown",
    "email_otp_no_mail",
    "post_register_failure",
    "protocol_preauth_transport_failed",
    "protocol_post_otp_transport_failed",
    "protocol_auth_transport_failed",
    "protocol_auth_rejected_before_password",
    "protocol_auth_http_failed",
    "protocol_session_incomplete",
    "protocol_failure_evidence_missing",
})


_REGISTRATION_DIAGNOSTIC_OPERATIONS = frozenset({
    "preauth", "email_submit", "password_submit", "otp_send", "otp_validate", "profile_submit",
    "callback", "session", "auth_session", "other",
})
_REGISTRATION_DIAGNOSTIC_STAGES = frozenset({
    "browser", "submit_email", "auth_redirect", "password", "login_password", "email_otp", "profile", "token",
})
_REGISTRATION_DIAGNOSTIC_FAILURE_KINDS = frozenset({
    "transport_error", "http_error", "invalid_response", "missing_session", "unknown",
})
_REGISTRATION_EXCEPTION_TYPES = frozenset({
    "Exception", "RuntimeError", "ValueError", "TypeError", "KeyError", "AttributeError", "JSONDecodeError",
    "TimeoutError", "Timeout", "ReadTimeout", "ConnectTimeout", "RequestTimeout", "TimeoutException",
    "ConnectionError", "ConnectionResetError", "ConnectionAbortedError", "BrokenPipeError", "OSError",
    "SSLError", "SSLCertVerificationError", "CertificateError", "TlsError", "ProxyConnectionError", "ProxyError",
    "HTTPError", "HTTPStatusError", "RequestException", "RequestError", "TransportError", "ProtocolError",
    "ConnectError", "ReadError", "WriteError", "ConnectTimeoutError", "ReadTimeoutError", "ProtocolOssRequestUnknown",
})


def safe_registration_diagnostics(value: object) -> dict[str, Any]:
    """只保留固定请求与进度事实，不信任异常正文或任意属性字符串。"""
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, allowed in (
        ("operation", _REGISTRATION_DIAGNOSTIC_OPERATIONS),
        ("failure_kind", _REGISTRATION_DIAGNOSTIC_FAILURE_KINDS),
        ("failure_stage", _REGISTRATION_DIAGNOSTIC_STAGES),
        ("last_confirmed_stage", _REGISTRATION_DIAGNOSTIC_STAGES | {""}),
    ):
        item = value.get(key)
        if isinstance(item, str) and item in allowed:
            result[key] = item
    status = value.get("http_status")
    if type(status) is int and 100 <= status <= 599:
        result["http_status"] = status
    if isinstance(value.get("auth_error"), dict):
        from core.http_response_diagnostics import safe_auth_error

        auth_error = safe_auth_error(value["auth_error"])
        if auth_error:
            result["auth_error"] = auth_error
    for key in ("otp_received", "profile_confirmed"):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    exception_type = value.get("exception_type")
    if isinstance(exception_type, str):
        result["exception_type"] = exception_type if exception_type in _REGISTRATION_EXCEPTION_TYPES else "Exception"
    chain = value.get("exception_chain")
    if isinstance(chain, (list, tuple)):
        result["exception_chain"] = [
            item if isinstance(item, str) and item in _REGISTRATION_EXCEPTION_TYPES else "Exception"
            for item in chain[:8]
        ]
    return result


def registration_diagnostic_cause_code(value: object) -> str:
    """同一次失败请求的受控证据决定原因，较早响应不参与推断。"""
    diagnostics = safe_registration_diagnostics(value)
    if not diagnostics:
        return ""
    operation = diagnostics.get("operation")
    kind = diagnostics.get("failure_kind")
    status = diagnostics.get("http_status")
    if kind == "http_error" and operation == "profile_submit":
        code = diagnostics.get("auth_error", {}).get("code")
        if status == 409 and code == "invalid_state":
            return "account_create_invalid_state"
        if status == 400 and code == "user_already_exists":
            return "account_create_user_already_exists"
    if diagnostics.get("profile_confirmed") is True:
        return "protocol_session_incomplete"
    if kind == "transport_error" and operation not in {None, "other"}:
        if diagnostics.get("otp_received") is True:
            return "protocol_post_otp_transport_failed"
        if operation == "preauth":
            return "protocol_preauth_transport_failed"
        return "protocol_auth_transport_failed"
    if kind == "http_error" and isinstance(status, int) and 400 <= status <= 599:
        if (status < 500 and operation in {"email_submit", "password_submit", "auth_session"}
                and diagnostics.get("last_confirmed_stage") in {"", "browser", "submit_email", "auth_redirect"}
                and diagnostics.get("failure_stage") in {"submit_email", "auth_redirect", "password", "login_password"}):
            return "protocol_auth_rejected_before_password"
        return "protocol_auth_http_failed"
    return "protocol_failure_evidence_missing"


def _auth_request_diagnostic_cause(diagnostics: dict[str, Any], *, code: str) -> dict[str, str] | None:
    """同一诊断来源内的请求操作和网络细项一起解析，避免跨请求拼接根因。"""
    operation = str(diagnostics.get("cause_operation") or diagnostics.get("operation") or "").strip()
    failure_kind = str(diagnostics.get("cause_failure_kind") or diagnostics.get("failure_kind") or "").strip()
    exception_type = str(diagnostics.get("exception_type") or "").strip()
    if not operation and code == "password_sentinel_failed":
        operation = "password_sentinel"
    request_template = {
        "password_sentinel": ("密码认证前置检查", "NET-SENTINEL", "OA-SENTINEL"),
        "password_verify": ("密码验证", "NET-PWD", "OA-PWD"),
        "mfa_verify": ("MFA 验证", "NET-MFA", "OA-MFA"),
    }.get(operation)
    if request_template is None or code in {"password_rejected", "mfa_rejected"}:
        return None
    label, network_prefix, http_prefix = request_template
    curl_code = diagnostics.get("curl_error_code")
    curl_code = curl_code if isinstance(curl_code, int) and not isinstance(curl_code, bool) else None
    transport_detail = {
        28: ("timeout", "001", "请求超时"),
        35: ("tls", "002", " TLS 握手失败"),
        56: ("connection", "003", "连接中断"),
        60: ("certificate", "004", " TLS 证书校验失败"),
    }.get(curl_code)
    if transport_detail is None:
        if exception_type in {"Timeout", "ReadTimeout", "ConnectTimeout", "TimeoutError"}:
            transport_detail = ("timeout", "001", "请求超时")
        elif exception_type == "SSLCertVerificationError":
            transport_detail = ("certificate", "004", " TLS 证书校验失败")
        elif exception_type == "SSLError":
            transport_detail = ("tls", "002", " TLS 握手失败")
        elif exception_type in {"ConnectionError", "ConnectionResetError", "ConnectionAbortedError"}:
            transport_detail = ("connection", "003", "连接中断")
    if transport_detail is not None:
        return {
            "cause_code": f"{operation}_transport_{transport_detail[0]}",
            "cause_display_code": f"{network_prefix}-{transport_detail[1]}",
            "cause_summary": f"{label}{transport_detail[2]}",
        }
    status = diagnostics.get("http_status")
    if isinstance(status, int) and not isinstance(status, bool) and 400 <= status <= 599:
        if operation == "password_sentinel" and status < 500:
            code_suffix, message = "http_rejected", f"{label}被拒绝（HTTP {status}）"
        else:
            code_suffix, message = "http_error", f"{label}请求返回 HTTP {status}"
        return {
            "cause_code": f"{operation}_{code_suffix}",
            "cause_display_code": f"{http_prefix}-{status}", "cause_summary": message,
        }
    if failure_kind == "transport_error":
        return {
            "cause_code": f"{operation}_transport_error", "cause_display_code": f"{network_prefix}-000",
            "cause_summary": f"{label}网络请求失败",
        }
    return None


def _specific_error_cause(summary: dict[str, Any]) -> dict[str, str] | None:
    """从固定原因码和安全诊断选出主错误，不让远端回执状态盖住失败原因。"""
    diagnostic_sources = [value for key in ("auth_diagnostics", "cause_diagnostics")
                          if isinstance(value := summary.get(key), dict)]
    diagnostics = diagnostic_sources[0] if diagnostic_sources else {}
    code = str(summary.get("cause_code") or "").strip()
    registration_cause = registration_diagnostic_cause_code(summary.get("registration_diagnostics"))
    if registration_cause and code in ({"", "registration_failed", "user_register_result_unknown"} | {
        item for item in REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES if item.startswith("protocol_")
    }):
        code = registration_cause
    if code == "password_rejected_email_fallback_failed":
        inner_code = str(diagnostics.get("cause_code") or "").strip()
        if inner_code in _CAUSE_DETAILS:
            code = inner_code
    for diagnostic_source in diagnostic_sources:
        cause = _auth_request_diagnostic_cause(diagnostic_source, code=code)
        if cause is not None:
            return cause
    failure_kind = str(diagnostics.get("cause_failure_kind") or diagnostics.get("failure_kind") or "").strip()
    if code == "email_otp_failed":
        detail = {
            "no_mail": ("MAIL-OTP-002", "未收到新的验证码邮件"),
            "imap_error": ("MAIL-IMAP-001", "转发邮箱读取失败"),
            "manual_timeout": ("MAIL-OTP-003", "等待手动验证码超时"),
            "invalid_code": ("MAIL-OTP-004", "邮箱验证码被拒绝"),
        }.get(failure_kind)
        if detail:
            return {"cause_code": code, "cause_display_code": detail[0], "cause_summary": detail[1]}
    if code == "extract_create_http_unknown":
        cause_diagnostics = summary.get("cause_diagnostics")
        cause_diagnostics = cause_diagnostics if isinstance(cause_diagnostics, dict) else {}
        status = cause_diagnostics.get("http_status")
        if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
            return {"cause_code": code, "cause_display_code": "OA-EXTRACT-HTTP", "cause_summary": f"提链创建请求返回 HTTP {status}"}
    if code == "email_change_verify_prepare_failed" and summary.get("remote_begin_accepted") is True:
        return {
            "cause_code": code,
            "cause_display_code": "OA-EMAIL-VERIFY-001",
            "cause_summary": "新邮箱验证请求在本地准备阶段失败；begin 已接受，待核验",
        }
    if code in _CAUSE_DETAILS:
        display_code, cause_summary = _CAUSE_DETAILS[code]
        return {"cause_code": code, "cause_display_code": display_code, "cause_summary": cause_summary}
    return None


def _registration_browser_error_cause(raw: str, *, task_type: str) -> dict[str, str] | None:
    """识别浏览器已记录的阶段症状，不把类名里的 Timeout 当作网络证据。"""
    task_key = str(task_type or "").strip().lower()
    registration_task_types = {"", "registration", "registration_resume"}
    account_login_task_types = {"twofa_retry", "account_setup_retry", "password_setup", "account_completion"}
    if task_key not in registration_task_types | account_login_task_types:
        return None
    markers = (
        ("ERR_TUNNEL_CONNECTION_FAILED", "roxy_proxy_tunnel_failed"),
        ("ERR_PROXY_CONNECTION_FAILED", "roxy_proxy_tunnel_failed"),
        ("_EmailSubmissionUnknown", "email_submit_unconfirmed"),
        ("_PasswordTransitionTimeout", "password_result_unknown"),
        ("找不到邮箱输入框/邮箱入口", "email_entry_not_ready"),
    )
    if task_key in registration_task_types:
        markers += (
            ("资料提交后的会话读取未完成", "profile_session_read_failed"),
            ("资料提交后的会话尚未确认登录态", "profile_session_unconfirmed"),
            ("资料提交后进入认证错误页", "profile_auth_error"),
            ("资料阶段进入认证错误页", "profile_auth_error"),
        )
    markers += (("邮箱提交/认证跳转超过总预算", "email_transition_timeout"),)
    if task_key in registration_task_types:
        markers += (("create_account_password_navigation_timeout", "password_entry_navigation_timeout"),)
    for marker, code in markers:
        if marker in raw:
            return _specific_error_cause({"cause_code": code})
    if re.search(r"(?<![\w])StageTimeout(?=[:：\s]|$)", raw):
        return _specific_error_cause({"cause_code": "browser_stage_timeout"})
    return None


def _classify_raw_task_error(
    message: Any,
    *,
    stage: str = "",
    task_type: str = "",
    error_code: str = "",
) -> dict[str, Any] | None:
    """把原始错误投影成前端可读的稳定分类；空错误返回 ``None``。"""
    raw = str(message or "").strip()
    if not raw:
        return None
    if str(task_type or "").strip().lower() == "plan_check" and raw.upper() == "HTTP 403":
        return _error_projection(
            TaskErrorCode.EXTERNAL_OPENAI_PLAN_FORBIDDEN.value,
            "external", "OpenAI / ChatGPT", "套餐查询接口被拒绝",
            stage=stage, error_code=error_code, raw=raw,
        )
    if str(task_type or "").strip().lower() == "extract_link":
        rejected = re.fullmatch(
            r"(?:ExtractCreateRejected:\s*)?提链创建请求被远端拒绝（HTTP ([1-5]\d{2})）",
            raw,
        )
        if rejected:
            status = rejected.group(1)
            return _error_projection(
                TaskErrorCode.EXTERNAL_EXTRACT_REJECTED.value,
                "external", "提链服务", "创建请求被拒绝",
                stage=stage, error_code=error_code, raw=raw,
                summary=f"提链创建请求被远端拒绝（HTTP {status}）",
                display_code=f"LINK-HTTP-{status}",
            )
    if str(task_type or "").strip().lower() == "email_change" and raw in {
        "邮箱准备失败: begin 请求本地准备失败",
        "邮箱换绑失败: begin 请求本地准备失败",
    }:
        return _error_projection(
            TaskErrorCode.INTERNAL_REQUEST_PREPARE.value,
            "internal", "本地流程", "请求准备失败",
            stage=stage, error_code=error_code, raw=raw,
            summary="邮箱换绑 begin 请求在本地准备阶段失败",
        )
    # 只匹配实际错误；Codex 等阶段名只定位发生位置，不能证明上游服务失败。
    haystack = raw.lower()
    if "remail 库存不足" in haystack:
        return _error_projection(
            TaskErrorCode.EXTERNAL_EMAIL.value,
            "external", "邮箱服务", "库存不足",
            stage=stage, error_code=error_code, raw=raw,
            summary="库存不足",
        )
    if str(task_type or "").strip().lower() == "email_change":
        projection = _email_change_error_projection(
            raw,
            haystack,
            stage=stage,
            error_code=error_code,
        )
        if projection is not None:
            return projection
    registration_projection = _registration_error_projection(
        raw,
        haystack=haystack,
        stage=stage,
        task_type=task_type,
        error_code=error_code,
    )
    if registration_projection is not None:
        return registration_projection
    for code, source, source_label, kind_label, needles in _RULES:
        if any(needle in haystack for needle in needles):
            summary = None
            if code == "external.proxy" and "proxypooltimeout" in haystack:
                summary = (
                    "IP 查询次数已用尽，等待换线超时"
                    if "查询次数上限" in raw else "等待可用线路超时"
                )
            return _error_projection(
                code,
                source,
                source_label,
                kind_label,
                stage=stage,
                error_code=error_code,
                raw=raw,
                summary=summary,
            )
    return _error_projection(
        TaskErrorCode.UNKNOWN.value,
        "unknown",
        _SOURCE_LABELS["unknown"],
        "具体原因未确认",
        stage=stage,
        error_code=error_code,
        raw=raw,
    )


_RECEIPT_TASK_LABELS = {
    "registration": ("OA-REG-RECEIPT", "注册"),
    "registration_resume": ("OA-REG-RESUME-RECEIPT", "继续注册"),
    "token_refresh": ("AUTH-REFRESH-RECEIPT", "AT 刷新"),
    "live_check": ("AUTH-LIVE-RECEIPT", "账号查活"),
    "codex_retry": ("AUTH-CODEX-RECEIPT", "Codex 授权"),
    "codex_token_refresh": ("AUTH-CODEX-REFRESH-RECEIPT", "Codex Token 刷新"),
    "twofa_retry": ("AUTH-MFA-RECEIPT", "2FA 补跑"),
    "twofa_setup": ("AUTH-MFA-SETUP-RECEIPT", "2FA 设置"),
    "twofa_change": ("AUTH-MFA-CHANGE-RECEIPT", "2FA 修改"),
    "password_setup": ("AUTH-PWD-SETUP-RECEIPT", "密码设置"),
    "password_change": ("AUTH-PWD-CHANGE-RECEIPT", "密码修改"),
    "account_completion": ("ACCT-COMPLETE-RECEIPT", "账号补全"),
    "account_setup_retry": ("ACCT-SETUP-RECEIPT", "账号配置补跑"),
    "email_change": ("OA-EMAIL-RECEIPT", "邮箱换绑"),
    "extract_link": ("LINK-RECEIPT", "提链"),
    "plan_check": ("OA-PLAN-RECEIPT", "套餐查询"),
    "deactivation_mail": ("MAIL-SCAN-RECEIPT", "停用邮件检查"),
}


def _receipt_missing_cause(
    *, stage: str, task_type: str, summary: dict[str, Any],
) -> dict[str, str]:
    """历史记录没有细项时只说已知任务或阶段，不从待核验状态猜测根因。"""
    stage_key = normalize_stage(stage) if stage else ""
    if stage_key in STAGES and stage_key not in {"result", "complete", "queued", "interrupted"}:
        display_code, label = {
            "login_password": ("AUTH-PWD-RECEIPT", "密码验证"),
            "email_otp": ("MAIL-OTP-RECEIPT", "邮箱验证"),
            "mfa_challenge": ("AUTH-MFA-RECEIPT", "MFA 验证"),
            "login_mfa": ("AUTH-MFA-RECEIPT", "MFA 验证"),
        }.get(stage_key, (f"STAGE-{stage_key.upper().replace('_', '-')}-RECEIPT", STAGES[stage_key]["label"]))
        return {
            "cause_code": f"{stage_key}_receipt_missing", "cause_display_code": display_code,
            "cause_summary": f"{label}阶段未保留回执或失败细项",
        }
    category = str(summary.get("error_category") or "").strip()
    if category in {"auth", "email"}:
        display_code, label = {
            "auth": ("AUTH-RECEIPT", "登录认证"),
            "email": ("MAIL-RECEIPT", "邮箱验证"),
        }[category]
        return {
            "cause_code": f"{category}_receipt_missing", "cause_display_code": display_code,
            "cause_summary": f"{label}阶段未保留回执或失败细项",
        }
    task_key = str(task_type or "").strip().lower()
    if task_key in _RECEIPT_TASK_LABELS:
        display_code, label = _RECEIPT_TASK_LABELS[task_key]
        return {
            "cause_code": f"{task_key}_receipt_missing", "cause_display_code": display_code,
            "cause_summary": f"{label}任务未保留回执或失败细项",
        }
    return {
        "cause_code": "task_receipt_missing", "cause_display_code": "TASK-RECEIPT-000",
        "cause_summary": "任务未保留回执或失败细项",
    }


def _cause_error_projection(
    cause: dict[str, str], *, stage: str, error_code: str, raw: str,
) -> dict[str, Any]:
    display_code = cause["cause_display_code"]
    source, source_label = (
        ("user", "用户操作") if display_code.startswith("USR-")
        else ("internal", "内部错误") if display_code.startswith("SYS-")
        else ("external", "网络 / 上游服务") if display_code.startswith("NET-")
        else ("external", "邮箱 / 验证码服务") if display_code.startswith("MAIL-")
        else ("workflow", "流程错误") if display_code.startswith("FLOW-") or cause["cause_code"].endswith("_receipt_missing")
        else ("external", "远端服务")
    )
    projection = _error_projection(
        cause["cause_code"], source, source_label, cause["cause_summary"],
        stage=stage, error_code="", raw=raw,
        summary=cause["cause_summary"], display_code=display_code,
    )
    projection.update(cause)
    projection.update({
        "retryability": "conditional", "remote_state_impact": "unknown",
        "next_action": "inspect_failure",
    })
    if cause["cause_code"].startswith("email_derivation_"):
        projection.update(source="internal", source_label="邮箱库存", remote_state_impact="not_started")
        projection["title"] = f"邮箱库存 · {cause['cause_summary']}"
        if cause["cause_code"] == "email_derivation_inventory_empty":
            projection.update(retryability="retryable", next_action="generate_email_inventory")
    if cause['cause_code'].startswith('email_resource_'):
        projection.update(source='external', source_label='邮箱资源', next_action='inspect_email_resource')
        if cause['cause_code'] in {'email_resource_expired', 'email_resource_expiry_invalid'}:
            projection['retryability'] = 'not_retryable'
    if cause["cause_code"] == "local_config_schema_mismatch":
        projection.update(source="internal", source_label="本地配置", remote_state_impact="unknown",
                          next_action="restart_and_retry")
    if error_code:
        projection["original_error_code"] = error_code
    return projection


def classify_task_error(
    message: Any,
    *,
    stage: str = "",
    task_type: str = "",
    error_code: str = "",
    result_summary: dict[str, Any] | None = None,
    task_status: str = "",
) -> dict[str, Any] | None:
    """具体原因优先展示；回执缺失只约束后续操作，不充当通用主错误。"""
    raw = str(message or "").strip()
    summary_data = result_summary if isinstance(result_summary, dict) else {}
    reconcile_required = (
        str(task_status or "").strip().lower() == "request_unknown"
        or str(error_code or "").strip().lower() == "request_unknown"
        or is_request_unknown(summary_data)
        or any(marker in raw.lower() for marker in (
            "request_unknown", "password_result_unknown", "远端请求结果待确认", "需人工对账",
            "结果待确认", "结果未知", "远端写请求尚未完成整条任务核验", "远端账号状态待核验",
            "禁止直接重试", "远端结果待确认", "结果待核验",
        ))
    )
    cause = _specific_error_cause(summary_data)
    if cause is None and re.search(r"\bKeyError\s*:\s*['\"]?schema 未定义字段:\s*[A-Z][A-Z0-9_]*", raw):
        cause = _specific_error_cause({"cause_code": "local_config_schema_mismatch"})
    if cause is None and (str(error_code).startswith(("roxy_", "email_derivation_", "email_resource_"))
                          or str(error_code) in _BUTLER_RECIPIENT_CAUSES):
        cause = _specific_error_cause({"cause_code": error_code})
    if cause is None and str(task_type or "").strip().lower() == "extract_link" and (
        str(error_code or "").strip() == "extract_provider_failed" or raw == "平台提链失败"
    ):
        # 历史记录的明确平台失败仍可展示；恢复约束继续由已保存的回执状态决定。
        cause = _specific_error_cause({"cause_code": "extract_provider_failed"})
    if cause is None:
        # 旧记录可能只把固定原因码写在正文中；只识别整词，不输出任意诊断原文。
        for candidate in sorted(_CAUSE_DETAILS, key=len, reverse=True):
            if candidate == "auth_cloudflare_challenge":
                # 挑战原因只接受抓包保存的结构化证据，不由正文中的原因码推断。
                continue
            if candidate == "auth_route_rejected":
                # 历史原文的 HTTP 状态继续交给已有授权路由分类读取。
                continue
            if re.search(rf"(?<![\w]){re.escape(candidate)}(?![\w])", raw):
                cause = _specific_error_cause({"cause_code": candidate})
                break
    if cause is None:
        cause = _registration_browser_error_cause(raw, task_type=task_type)
    raw_projection = None
    if cause is not None and cause["cause_code"] in {
        "refresh_driver_exception", "protocol_v2_unknown_error", "post_register_failure",
    }:
        raw_projection = _classify_raw_task_error(raw, stage=stage, task_type=task_type, error_code=error_code)
        # 驱动兜底异常只定位失败范围；明确的代理、数据库等原始错误仍应作为主原因。
        if raw_projection is not None and raw_projection["code"] != TaskErrorCode.UNKNOWN.value:
            cause = None
    if cause is not None:
        projection = _cause_error_projection(cause, stage=stage, error_code=error_code, raw=raw)
    else:
        projection = raw_projection or _classify_raw_task_error(raw, stage=stage, task_type=task_type, error_code=error_code)
        if reconcile_required and (projection is None or projection["code"] == TaskErrorCode.UNKNOWN.value):
            cause = _receipt_missing_cause(stage=stage, task_type=task_type, summary=summary_data)
            projection = _cause_error_projection(cause, stage=stage, error_code=error_code, raw=raw)
    if projection is not None and reconcile_required:
        # 保留防重复执行的恢复语义，但主错误仍是已证实的具体失败原因。
        projection.update({
            "reconcile_required": True, "retryability": "manual_only",
            "remote_state_impact": "unknown", "next_action": "manual_reconcile",
        })
    return projection


__all__ = [
    "ErrorCode",
    "REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES",
    "TaskErrorCode",
    "classify_task_error",
    "is_request_unknown",
    "stable_error_code",
    "safe_registration_diagnostics",
    "registration_diagnostic_cause_code",
]
