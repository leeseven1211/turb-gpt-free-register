# -*- coding: utf-8 -*-
"""统一任务阶段定义和 D 窗口诊断事件契约。

任务执行器仍可使用自己的内部函数，但写事件和展示时必须映射到这里的稳定阶段。
这样注册、继续注册、Codex 补跑和账号配置补跑复用同一套术语，前端不再从日志文本猜步骤。
"""
from __future__ import annotations

from typing import Any


STEP_STATES = frozenset({"pending", "running", "success", "skipped", "failed"})

# Wait reasons are deliberately finite so duration reports can be aggregated
# without parsing driver log prose.  ``unknown`` is explicit rather than an
# omitted field: a missing reason and a measured non-waiting stage are distinct.
WAIT_REASONS = frozenset({
    "resource_wait", "driver_command", "page_transition", "email_wait",
    "human_delay", "db_write", "projection", "cleanup", "unknown",
})

# Public event contract consumed by the task-center projection (window E).
# Every diagnostic event carries the correlation fields and ``event_type``;
# stage transitions additionally carry state_before/state_after and timing.
EVENT_TYPES = frozenset({
    "diagnostic",
    "capture_started", "capture_finished", "stage", "stage_timing",
    "network_request", "email_evidence", "failure_diagnostics",
    "page_snapshot", "page_error", "console", "websocket_open",
    "websocket_frame", "websocket_close", "capture_warning",
    "capture_degraded", "snapshot_error", "collector_started", "debug_paused",
    "debug_released", "debug_hold_skipped",
})
DIAGNOSTIC_TRIGGER_STATUSES = frozenset({"failed", "partial_success", "unknown"})
DIAGNOSTIC_CONTEXT_FIELDS = frozenset({
    "job_id", "attempt_id", "run_id", "execution_id", "trigger_stage", "last_confirmed_state",
    "failure_stage", "email_evidence",
})
ERROR_FIELDS = frozenset({
    "error_code", "source", "stage", "retryability", "remote_state_impact", "next_action",
})
EVENT_BASE_FIELDS = frozenset({
    "event_type", "kind", "captured_at", "job_id", "attempt_id", "run_id", "execution_id",
    "trigger_stage", "last_confirmed_state", "failure_stage", "stage", "error",
})
STAGE_EVENT_FIELDS = frozenset({
    "state_before", "state_after", "duration_ms", "wait_reason",
})


STAGES: dict[str, dict[str, str]] = {
    "queued": {"label": "进入队列", "group": "system"},
    "preflight": {"label": "配置预检", "group": "system"},
    "email": {"label": "准备邮箱", "group": "resource"},
    "network": {"label": "分配网络", "group": "resource"},
    "browser": {"label": "启动浏览器", "group": "browser"},
    "page": {"label": "打开页面", "group": "browser"},
    "submit_email": {"label": "提交邮箱", "group": "identity"},
    "auth_redirect": {"label": "进入认证", "group": "identity"},
    "login_password": {"label": "账号密码", "group": "identity"},
    "email_otp": {"label": "邮箱验证", "group": "identity"},
    "profile": {"label": "账号资料", "group": "identity"},
    "token": {"label": "获取 Token", "group": "account"},
    "oauth": {"label": "Codex 授权", "group": "codex"},
    "auth_url": {"label": "获取授权地址", "group": "codex"},
    "login": {"label": "登录 OpenAI", "group": "identity"},
    "phone_check": {"label": "检查手机验证", "group": "codex"},
    "phone_acquire": {"label": "申请接码号码", "group": "resource"},
    "phone_otp": {"label": "短信验证", "group": "identity"},
    "consent": {"label": "确认授权", "group": "codex"},
    "callback": {"label": "接收 OAuth 回调", "group": "codex"},
    "credential_confirm": {"label": "确认远端凭证", "group": "codex"},
    "credential_persist": {"label": "保存凭证", "group": "codex"},
    "cancelling": {"label": "正在停止", "group": "system"},
    "codex": {"label": "Codex 授权", "group": "codex"},
    "twofa": {"label": "Authenticator 2FA", "group": "security"},
    "plan_check": {"label": "查询套餐", "group": "account"},
    "access_token": {"label": "校验 Token", "group": "account"},
    "refresh_token": {"label": "刷新 Token", "group": "account"},
    "mailbox_scan": {"label": "扫描邮件", "group": "account"},
    "complete": {"label": "完成", "group": "system"},
    "interrupted": {"label": "执行中断", "group": "system"},
}

ALIASES = {
    "running": "queued",
    "network_route": "network",
    "driver": "browser",
    "account_setup": "twofa",
    "reauth": "login_password",
    "roxy_fallback": "browser",
    "plan_request": "plan_check",
}

TASK_FLOWS: dict[str, tuple[str, ...]] = {
    "registration": (
        "network", "email", "browser", "page", "submit_email", "auth_redirect",
        "login_password", "email_otp", "profile", "token", "codex", "twofa",
        "plan_check", "complete",
    ),
    "registration_resume": (
        "network", "browser", "login_password", "email_otp", "profile", "token",
        "codex", "twofa", "plan_check", "complete",
    ),
    "codex_retry": (
        "preflight", "network", "browser", "auth_url", "login", "email_otp",
        "phone_check", "phone_acquire", "phone_otp", "consent", "callback",
        "credential_confirm", "credential_persist", "complete",
    ),
    "twofa_retry": ("network", "browser", "login_password", "twofa", "plan_check", "complete"),
    "account_setup_retry": ("network", "browser", "login_password", "twofa", "plan_check", "complete"),
    "live_check": ("network", "access_token", "complete"),
    "token_refresh": ("network", "login_password", "email_otp", "token", "complete"),
    "codex_token_refresh": ("refresh_token", "complete"),
    "plan_check": ("network", "plan_check", "complete"),
    "deactivation_mail": ("mailbox_scan", "complete"),
}


def normalize_stage(stage: Any) -> str:
    value = str(stage or "event").strip().lower().removesuffix("_result")
    return ALIASES.get(value, value)


def normalize_step_state(state: Any) -> str | None:
    """返回任务步骤协议允许的五态；无效值不进入事件投影。"""
    value = str(state or "").strip().lower()
    return value if value in STEP_STATES else None


def normalize_wait_reason(reason: Any) -> str:
    value = str(reason or "").strip().lower()
    return value if value in WAIT_REASONS else "unknown"


def stage_label(stage: Any) -> str:
    key = normalize_stage(stage)
    return STAGES.get(key, {}).get("label") or key


def flow_for(task_type: Any) -> list[dict[str, str]]:
    keys = TASK_FLOWS.get(str(task_type or "").strip().lower(), ("queued", "complete"))
    return [
        {
            "key": key,
            "label": stage_label(key),
            "group": STAGES.get(key, {}).get("group", "other"),
        }
        for key in keys
    ]
