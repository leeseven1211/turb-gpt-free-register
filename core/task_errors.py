# -*- coding: utf-8 -*-
"""任务错误的统一展示分类。

这里只做稳定、无副作用的展示投影，不改写原始错误和数据库记录。注册任务、Codex/2FA
补跑及账号操作任务都可复用同一套分类口径；完整技术信息仍保留在日志中。
"""
from __future__ import annotations

import re
from typing import Any

from core.task_stages import normalize_stage


_RULES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        "configuration.missing",
        "configuration",
        "配置错误",
        "缺少配置",
        ("未配置", "配置缺失", "请填写", "api key 为空", "token 为空", "不能为空"),
    ),
    (
        "user.interrupted",
        "user",
        "用户操作",
        "任务被停止",
        ("用户手动停止", "用户取消", "已取消", "收到停止请求"),
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
            "imap", "gmail", "验证码邮件", "等待验证码超时",
        ),
    ),
    (
        "external.openai",
        "external",
        "外部错误",
        "OpenAI / Codex",
        ("openai", "chatgpt", "codex", "oauth", "authenticator", "2fa", "/api/auth/session"),
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
        "external.network",
        "external",
        "外部错误",
        "网络 / 上游服务",
        ("httperror", "connection", "timeout", "timed out", "http error 5", "网络"),
    ),
)

_SOURCE_LABELS = {
    "configuration": "配置错误",
    "user": "用户操作",
    "external": "外部错误",
    "internal": "内部错误",
    "workflow": "流程错误",
    "unknown": "未分类错误",
}

# These values are intentionally strings rather than booleans.  A retry can be
# technically possible while still being unsafe after an irreversible remote
# request, so consumers need the distinction for recovery UX.
_ERROR_METADATA: dict[str, dict[str, str]] = {
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
