# -*- coding: utf-8 -*-
"""任务错误的统一展示分类。

这里只做稳定、无副作用的展示投影，不改写原始错误和数据库记录。注册任务、Codex/2FA
补跑及账号操作任务都可复用同一套分类口径；完整技术信息仍保留在日志中。
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any

from core.task_stages import normalize_stage


class TaskErrorCode(str, Enum):
    """任务层共享的稳定错误码，不携带远端原文或敏感上下文。"""

    CONFIGURATION = "configuration.missing"
    USER_INTERRUPTED = "user.interrupted"
    SERVICE_INTERRUPTED = "service.interrupted"
    EXTERNAL_PROXY = "external.proxy"
    EXTERNAL_ROXY_CAPACITY = "external.roxy_capacity"
    EXTERNAL_ROXY = "external.roxy"
    EXTERNAL_EMAIL = "external.email"
    EXTERNAL_OPENAI = "external.openai"
    EXTERNAL_OPENAI_ACCOUNT_CREATION_REJECTED = "external.openai.account_creation_rejected"
    EXTERNAL_NETWORK_MFA_TRANSPORT = "external.network.mfa_transport"
    EXTERNAL_NETWORK_REGISTRATION_TIMEOUT = "external.network.registration_timeout"
    EXTERNAL_NETWORK = "external.network"
    INTERNAL_STORAGE = "internal.storage"
    INTERNAL_BROWSER = "internal.browser"
    WORKFLOW_VERIFICATION = "workflow.verification"
    WORKFLOW_PAGE_STATE = "workflow.page_state"
    WORKFLOW_PASSWORD_ENTRY_NOT_HYDRATED = "workflow.password_entry_not_hydrated"
    WORKFLOW_PASSWORD_ENTRY_NOT_OFFERED = "workflow.password_entry_not_offered"
    WORKFLOW_PASSWORD_ENTRY_RECOVERY_EXHAUSTED = "workflow.password_entry_recovery_exhausted"
    WORKFLOW_UNSUPPORTED = "workflow.unsupported"
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
    """未知远端结果是一等状态，不能被任务层当成普通可重试错误。"""
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
        "request_unknown",
        "external",
        "远端待核验",
        "远端请求结果待确认",
        ("request_unknown", "远端请求结果待确认", "需人工对账", "结果待确认"),
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
        "configuration.missing",
        "configuration",
        "配置错误",
        "缺少配置",
        ("未配置", "配置缺失", "请填写", "api key 为空", "token 为空", "不能为空"),
    ),
    (
        "service.interrupted",
        "system",
        "系统事件",
        "服务重启中断",
        (
            "webui 进程重启导致任务中断",
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
        ("用户手动停止", "用户取消", "已取消", "收到停止请求"),
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
            "验证码重发",
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
        "external.network.mfa_transport",
        "external",
        "网络 / 上游服务",
        "2FA 通道网络错误",
        (
            "twofaprotocoltransporterror",
            "transport failed after retry",
            "enroll transport failed",
            "activate transport failed",
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
        ("postgres", "database", "数据库", "数据写入", "持久化"),
    ),
    (
        "internal.browser",
        "internal",
        "内部错误",
        "浏览器自动化",
        ("playwright", "浏览器启动", "roxybrowser", "browsercontext", "page crashed"),
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
    "unknown": "未分类错误",
    "system": "系统事件",
}

# These values are intentionally strings rather than booleans.  A retry can be
# technically possible while still being unsafe after an irreversible remote
# request, so consumers need the distinction for recovery UX.
_ERROR_METADATA: dict[str, dict[str, str]] = {
    "request_unknown": {
        "retryability": "manual_only",
        "remote_state_impact": "unknown",
        "next_action": "manual_reconcile",
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
    "external.openai": {
        "retryability": "conditional",
        "remote_state_impact": "unknown",
        "next_action": "reconcile_session",
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


def _summary(message: str, limit: int = 160) -> str:
    value = re.sub(r"\s+", " ", str(message or "")).strip()
    value = re.sub(r"^(?:[A-Za-z_][\w.]*Error|Exception):\s*", "", value)
    return value[:limit] + ("…" if len(value) > limit else "")


def classify_task_error(
    message: Any,
    *,
    stage: str = "",
    task_type: str = "",
    error_code: str = "",
) -> dict[str, str] | None:
    """把原始错误投影成前端可读的稳定分类；空错误返回 ``None``。"""
    raw = str(message or "").strip()
    if not raw:
        return None
    # 以实际错误和失败阶段为准；不能因为任务类型是 codex_retry，就把其中的代理、
    # 数据库或页面状态错误统统误归为 OpenAI 上游错误。
    haystack = f"{stage} {raw}".lower()
    for code, source, source_label, kind_label, needles in _RULES:
        if any(needle in haystack for needle in needles):
            result = {
                "code": code,
                "error_code": code,
                "source": source,
                "source_label": source_label,
                "kind_label": kind_label,
                "title": f"{source_label} · {kind_label}",
                "summary": _summary(raw),
            }
            result.update(_ERROR_METADATA.get(code, {}))
            result["error_code"] = str(error_code or code)
            result["stage"] = normalize_stage(stage) if stage else "unknown"
            if error_code:
                result["original_error_code"] = str(error_code)
            return result
    result = {
        "code": "unknown.unclassified",
        "error_code": "unknown.unclassified",
        "source": "unknown",
        "source_label": _SOURCE_LABELS["unknown"],
        "kind_label": "待归类",
        "title": "未分类错误 · 待归类",
        "summary": _summary(raw),
    }
    result.update(_ERROR_METADATA["unknown.unclassified"])
    result["stage"] = normalize_stage(stage) if stage else "unknown"
    if error_code:
        result["original_error_code"] = str(error_code)
    return result


__all__ = [
    "ErrorCode",
    "TaskErrorCode",
    "classify_task_error",
    "is_request_unknown",
    "stable_error_code",
]
