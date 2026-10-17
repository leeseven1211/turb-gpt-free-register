# -*- coding: utf-8 -*-
"""统一任务阶段定义和 D 窗口诊断事件契约。

任务执行器仍可使用自己的内部函数，但写事件和展示时必须映射到这里的稳定阶段。
这样注册、继续注册、Codex 补跑和账号配置补跑复用同一套术语，前端不再从日志文本猜步骤。
"""
from __future__ import annotations

from typing import Any


FLOW_VERSION = 2

# 注册页面、邮箱、凭证准备、密码和验证码是同一认证主步骤中的独立阶段。
REGISTRATION_AUTH_STAGES = (
    "page", "submit_email", "auth_redirect", "login", "credential_prepare", "login_password", "email_otp",
)


STEP_STATES = frozenset({"pending", "running", "success", "skipped", "failed"})

# 等待原因使用有限枚举，便于聚合时长而无需解析驱动日志文本。
# ``unknown`` 表示明确未知，区别于缺失原因和已测量的非等待阶段。
WAIT_REASONS = frozenset({
    "resource_wait", "driver_command", "page_transition", "email_wait",
    "human_delay", "db_write", "projection", "cleanup", "unknown",
})

# 任务中心投影消费的公开事件契约（窗口 E）。每个诊断事件都带关联字段和
# ``event_type``；阶段转移还带 state_before/state_after 与时间信息。
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
    "authenticate": {"label": "登录与身份验证", "group": "identity"},
    "set_password": {"label": "设置账号密码", "group": "security"},
    "set_twofa": {"label": "配置 Authenticator 2FA", "group": "security"},
    "phone_verify": {"label": "手机验证", "group": "identity"},
    "credential": {"label": "保存与确认凭证", "group": "codex"},
    "refresh_dispatch": {"label": "提交 Token 刷新任务", "group": "account"},
    "codex_dispatch": {"label": "提交 Codex 授权任务", "group": "codex"},
    "result": {"label": "结果", "group": "system"},
    "queued": {"label": "进入队列", "group": "system"},
    "preflight": {"label": "配置预检", "group": "system"},
    "email": {"label": "准备邮箱", "group": "resource"},
    "network": {"label": "分配网络", "group": "resource"},
    "browser": {"label": "启动浏览器", "group": "browser"},
    "page": {"label": "打开页面", "group": "browser"},
    "submit_email": {"label": "提交邮箱", "group": "identity"},
    "auth_redirect": {"label": "进入认证", "group": "identity"},
    "credential_prepare": {"label": "准备注册凭证", "group": "identity"},
    "login_password": {"label": "账号密码", "group": "identity"},
    "mfa_challenge": {"label": "TOTP MFA", "group": "identity"},
    "email_otp": {"label": "邮箱验证", "group": "identity"},
    "profile": {"label": "账号资料", "group": "identity"},
    "token": {"label": "获取 Token", "group": "account"},
    "oauth": {"label": "Codex 授权", "group": "codex"},
    "auth_url": {"label": "获取授权地址", "group": "codex"},
    "workspace": {"label": "工作区", "group": "codex"},
    "login": {"label": "登录 OpenAI", "group": "identity"},
    "login_mfa": {"label": "登录 MFA", "group": "identity"},
    "phone_check": {"label": "检查手机验证", "group": "codex"},
    "phone_acquire": {"label": "申请接码号码", "group": "resource"},
    "phone_otp": {"label": "短信验证", "group": "identity"},
    "consent": {"label": "确认授权", "group": "codex"},
    "callback": {"label": "接收 OAuth 回调", "group": "codex"},
    "credential_confirm": {"label": "确认远端凭证", "group": "codex"},
    "credential_persist": {"label": "保存凭证", "group": "codex"},
    "cancelling": {"label": "正在停止", "group": "system"},
    "codex": {"label": "Codex 授权", "group": "codex"},
    "plan": {"label": "生成补全计划", "group": "account"},
    "twofa": {"label": "Authenticator 2FA", "group": "security"},
    "plan_check": {"label": "查询套餐", "group": "account"},
    "access_token": {"label": "校验 Token", "group": "account"},
    "refresh_token": {"label": "刷新 Token", "group": "account"},
    "account_setup_dispatch": {"label": "提交账号配置任务", "group": "account"},
    "account_setup": {"label": "执行账号配置", "group": "account"},
    "account_status": {"label": "确认账号状态", "group": "account"},
    "dispatch": {"label": "提交独立子任务", "group": "system"},
    "password_checkpoint": {"label": "保存密码检查点", "group": "security"},
    "password_reset": {"label": "重置账号密码", "group": "security"},
    "password_reset_otp": {"label": "验证密码重置邮件", "group": "identity"},
    "change_email": {"label": "换绑邮箱", "group": "identity"},
    "change_email_begin": {"label": "发起邮箱换绑", "group": "identity"},
    "change_email_verify": {"label": "确认新邮箱", "group": "identity"},
    "new_email_otp": {"label": "验证新邮箱验证码", "group": "identity"},
    "recent_login": {"label": "登录重认证", "group": "identity"},
    "writeback": {"label": "保存换绑结果", "group": "account"},
    "extract_link": {"label": "提炼", "group": "account"},
    "mailbox_scan": {"label": "扫描邮件", "group": "account"},
    "complete": {"label": "完成", "group": "system"},
    "interrupted": {"label": "执行中断", "group": "system"},
}

ALIASES = {
    "running": "queued",
    "network_route": "network",
    "driver": "browser",
    "reauth": "login_password",
    "roxy_fallback": "browser",
    "plan_request": "plan_check",
}

_FLOW = dict[str, tuple[dict[str, Any], ...]]


def _step(step_id: str, label: str, group: str, *raw_stages: str, depends_on: tuple[str, ...] = ()) -> dict[str, Any]:
    """构建一个规范业务步骤。

    模板保留 ``raw_stages``，因为一个业务步骤可能对应多个 raw stage，
    后续投影仍需显示实际发生的具体阶段。
    """
    raw_values = list(raw_stages or (step_id,))
    return {
        "id": step_id,
        "step_id": step_id,
        "key": "complete" if step_id == "result" else raw_values[0],  # 兼容旧版 flow_for() 返回值
        "label": label,
        "group": group,
        "raw_stages": raw_values,
        "depends_on": tuple(depends_on),
    }


def _result() -> dict[str, Any]:
    return _step("result", "结果", "system", "complete", "interrupted", "cancelling")


def _flow(*steps: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return (*steps, _result())


def _s(step_id: str, *raw: str, depends_on: tuple[str, ...] = ()) -> dict[str, Any]:
    info = STAGES.get(step_id, {})
    return _step(step_id, info.get("label", step_id), info.get("group", "other"), *(raw or (step_id,)), depends_on=depends_on)


# 这里是唯一模板源。即使执行器新增 raw stage，也保持业务 ID 稳定；
# 列表覆盖 operation 层当前发出的全部任务类型，包括此前缺失的两个 change 变体。
TASK_TEMPLATES: _FLOW = {
    "registration": _flow(
        _s("network"), _s("email"), _s("browser"), _s("authenticate", *REGISTRATION_AUTH_STAGES),
        _s("profile"), _s("token"), _s("codex", "codex", "oauth"), _s("set_twofa", "twofa", "twofa_result"), _s("plan_check"),
    ),
    "registration_resume": _flow(
        _s("network"), _step("email", "复用账号邮箱", "resource", "email"), _s("browser"), _s("authenticate", *REGISTRATION_AUTH_STAGES), _s("profile"), _s("token"),
        _s("codex", "codex", "oauth"), _s("set_twofa", "twofa", "twofa_result"), _s("plan_check"),
    ),
    "codex_retry": _flow(
        _s("preflight"), _s("network"), _s("browser"), _s("auth_url"),
        _s("authenticate", "login", "login_password", "login_mfa", "email_otp", "mfa_challenge"),
        _s("workspace"), _s("phone_verify", "phone_check", "phone_acquire", "phone_otp"),
        _s("consent"), _s("callback"), _s("credential", "credential_confirm", "credential_persist"),
    ),
    "twofa_retry": _flow(_s("network"), _s("browser"), _s("authenticate", "login", "login_password", "email_otp", "mfa_challenge"), _s("set_twofa", "twofa", "twofa_result"), _s("plan_check")),
    "account_setup_retry": _flow(_s("network"), _s("plan_check"), _s("browser"), _s("authenticate", "login", "email_otp", "mfa_challenge"), _s("set_password", "login_password", "password_reset", "password_reset_otp", "password_checkpoint"), _s("set_twofa", "twofa", "twofa_result")),
    "password_setup": _flow(_s("network"), _s("browser"), _s("authenticate", "login", "email_otp", "mfa_challenge"), _s("set_password", "login_password", "password_reset", "password_reset_otp", "password_checkpoint")),
    "password_change": _flow(_s("network"), _s("browser"), _s("authenticate", "login", "email_otp", "mfa_challenge"), _s("set_password", "login_password", "password_reset", "password_reset_otp", "password_checkpoint")),
    "twofa_setup": _flow(_s("network"), _s("set_twofa", "twofa", "twofa_result")),
    "twofa_change": _flow(_s("network"), _s("browser"), _s("authenticate", "login", "email_otp", "mfa_challenge"), _s("set_twofa", "twofa", "twofa_result")),
    "account_completion": _flow(
        _s("plan"), _s("refresh_dispatch", "refresh_token", "dispatch"), _s("account_setup_dispatch", "account_setup"), _s("network"), _s("plan_check"), _s("browser"),
        _s("authenticate", "login", "login_password", "email_otp", "mfa_challenge"), _s("set_password", "password_reset", "password_checkpoint"),
        _s("set_twofa", "twofa", "twofa_result"), _s("codex_dispatch", "codex", "oauth", "dispatch"),
    ),
    # 依赖只说明明确失败后哪些本地步骤无法进入，不强制按模板顺序运行。
    # 注册、补全和配置分支含条件或独立子任务，保持无依赖推断。
    "live_check": _flow(_s("preflight"), _s("network", depends_on=("preflight",)), _s("access_token", depends_on=("network",))),
    "token_refresh": _flow(_s("preflight"), _s("network", depends_on=("preflight",)), _s("authenticate", "login", "login_password", "login_mfa", "email_otp", "mfa_challenge", depends_on=("network",)), _s("refresh_token", depends_on=("authenticate",)), _s("token", depends_on=("refresh_token",))),
    "codex_token_refresh": _flow(_s("preflight"), _s("refresh_token", depends_on=("preflight",)), _s("credential", "credential_confirm", "credential_persist", depends_on=("refresh_token",))),
    "plan_check": _flow(_s("preflight"), _s("network", depends_on=("preflight",)), _s("plan_check", depends_on=("network",))),
    "deactivation_mail": _flow(_s("preflight"), _s("mailbox_scan")),
    "extract_link": _flow(_s("preflight"), _s("access_token"), _s("refresh_token"), _s("extract_link")),
    "email_change": _flow(_s("email"), _s("network"), _s("login_password", "login_password", "reauth", "recent_login"), _s("email_otp", "email_otp", "new_email_otp"), _s("submit_email", "submit_email", "change_email", "change_email_begin", "change_email_verify", "writeback")),
}

# 公开兼容视图仍保留 raw stage 元组，供只需要旧诊断词汇的调用方使用；
# 新投影统一读取模板。
TASK_FLOWS: dict[str, tuple[str, ...]] = {
    task_type: tuple(raw for step in flow for raw in step["raw_stages"])
    for task_type, flow in TASK_TEMPLATES.items()
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


def flow_for(task_type: Any, run: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """返回任务的规范 v2 业务模板。

    只有 run summary 明确提供计划子集时才过滤计划项；实际观测到的 raw
    stage 不在这里丢弃，投影层会追加动态节点，避免执行器更新抹掉证据。
    """
    task_key = str(task_type or "").strip().lower()
    flow = TASK_TEMPLATES.get(task_key, _flow())
    summary_value = (run or {}).get("result_summary")
    result_summary = summary_value if isinstance(summary_value, dict) else {}
    planned_value = result_summary.get("planned_steps")
    planned_steps = planned_value if isinstance(planned_value, (list, tuple)) else []
    planned = {str(value).strip().lower() for value in planned_steps if str(value).strip()}
    if not planned or task_key not in {"password_setup", "password_change", "twofa_setup", "twofa_change", "twofa_retry", "account_setup_retry", "account_completion"}:
        return [dict(item, raw_stages=list(item["raw_stages"])) for item in flow]
    allowed = set()
    # planned_steps 使用 operation 层名称而非 UI ID；在此做兼容翻译，
    # 保证模板和投影共用一套定义，明确收窄的计划不会重新展示全部分支。
    if task_key in {"password_setup", "password_change"}:
        allowed = {"network", "browser", "authenticate", "set_password"}
    elif task_key in {"twofa_setup", "twofa_change", "twofa_retry", "account_setup_retry"}:
        allowed = {"network"}
        if "plan_check" in planned:
            allowed.add("plan_check")
        if "password" in planned:
            allowed |= {"browser", "authenticate", "set_password"}
        if "twofa" in planned:
            allowed |= {"browser", "authenticate", "set_twofa"}
        # 没有计划详情时使用规范形状；有计划详情时，省略项表示明确跳过。
    elif task_key == "account_completion":
        allowed = {"plan"}
        if "refresh_at" in planned:
            allowed.add("refresh_dispatch")
        if "account_setup" in planned:
            allowed.add("account_setup_dispatch")
        if "plan_check" in planned:
            allowed |= {"network", "plan_check"}
        if "password" in planned:
            allowed |= {"browser", "authenticate", "set_password"}
        if "twofa" in planned:
            allowed |= {"set_twofa"}
        if "codex" in planned:
            allowed.add("codex_dispatch")
    return [dict(item, raw_stages=list(item["raw_stages"])) for item in flow if item["id"] in allowed or item["id"] == "result"]


def step_for_raw_stage(task_type: Any, raw_stage: Any, run: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """将执行器阶段解析为共享业务步骤描述。

    函数无副作用，operation 写入方和日志补全可与进度投影使用同一映射。
    未知阶段返回 ``None``，由投影层创建动态节点，不会静默归入邻近阶段。
    """
    raw = normalize_stage(raw_stage)
    for item in flow_for(task_type, run):
        if raw in {normalize_stage(value) for value in item.get("raw_stages", [])}:
            return item
    return None


def business_step_id(task_type: Any, raw_stage: Any, run: dict[str, Any] | None = None) -> str | None:
    """返回已知 raw stage 对应的稳定业务 ID。"""
    item = step_for_raw_stage(task_type, raw_stage, run)
    return item.get("id") if item else None


_ACCOUNT_SETUP_TASK_TYPES = {
    "account_setup_retry", "password_setup", "password_change",
    "twofa_setup", "twofa_change", "twofa_retry",
}


def is_task_lifecycle_stage(task_type: Any, stage: Any) -> bool:
    """账号配置执行器的外层起止记录不代表某个业务步骤已经开始。"""
    task_key = str(task_type or "").strip().lower()
    return normalize_stage(stage) == "account_setup" and task_key in _ACCOUNT_SETUP_TASK_TYPES


def resolve_step(task_type: Any, stage: Any, detail: dict[str, Any] | None = None, run: dict[str, Any] | None = None) -> str | None:
    """将 raw event 解析为稳定的顶层业务步骤 ID。

    worker 已发出稳定 ID 时优先使用 ``detail.step_id``；其余兼容别名与
    读侧投影一致。未知阶段返回 ``None``，调用方可保留为动态节点。
    """
    detail_value = detail if isinstance(detail, dict) else {}
    task_key = str(task_type or "").strip().lower()
    if is_task_lifecycle_stage(task_key, stage):
        return None
    explicit = str(detail_value.get("main_step_id") or detail_value.get("step_id") or "").strip()
    known = {item["id"] for item in flow_for(task_key, run)}
    if explicit in known:
        return explicit
    raw = normalize_stage(stage)
    if raw == "account_status" and task_key in _ACCOUNT_SETUP_TASK_TYPES:
        return "result"
    if raw in known:
        return raw
    item = step_for_raw_stage(task_key, raw, run)
    if item:
        return item["id"]
    aliases = {
        "page": "authenticate", "submit_email": "authenticate", "auth_redirect": "authenticate",
        "oauth": "codex", "phone_check": "phone_verify", "phone_acquire": "phone_verify",
        "phone_otp": "phone_verify", "credential_confirm": "credential", "credential_persist": "credential",
        "change_email": "submit_email", "change_email_begin": "submit_email", "change_email_verify": "submit_email",
        "writeback": "submit_email", "reauth": "login_password", "proxy": "network",
        "mailbox": "email", "email_prepare": "email", "dispatch": "refresh_dispatch",
    }
    mapped = aliases.get(raw)
    if mapped in known:
        return mapped
    if raw == "account_setup":
        if "account_setup_dispatch" in known:
            return "account_setup_dispatch"
        if "set_twofa" in known:
            return "set_twofa"
    if raw in {"login", "login_password", "login_mfa", "email_otp", "mfa_challenge", "password_reset", "password_reset_otp", "token"}:
        for candidate in ("authenticate", "login_password", "set_password"):
            if candidate in known:
                return candidate
    if raw == "browser" and "set_twofa" in known and "browser" not in known:
        return "set_twofa"
    if raw in {"complete", "interrupted", "cancelling"} and "result" in known:
        return "result"
    return None
