"""注册失败原因和安全展示；不包含注册执行步骤。"""
from __future__ import annotations

import json
import re

from core.email.forward_imap import ForwardIMAPNoMailTimeout


def _protocol_registration_cause_code(
    exc: BaseException,
    error_text: str,
    *,
    register_accepted: bool,
    checkpoint_account_id: int | None,
    otp_send_in_flight: bool,
) -> str:
    """只用固定原因码描述失败，不把服务端正文或凭据写入任务结果。"""
    if not register_accepted:
        return (
            "user_register_result_unknown"
            if error_text.startswith("user/register 请求结果未知")
            else "registration_failed"
        )
    if checkpoint_account_id is None:
        return "registration_checkpoint_failed"
    if error_text.startswith("user/register 响应缺少 continue_url"):
        return "user_register_continue_url_missing"
    for marker in (
        "email_otp_send_rejected",
        "email_otp_send_failed",
        "email_otp_send_unconfirmed",
    ):
        if error_text.startswith(marker):
            return marker
    if otp_send_in_flight:
        return "email_otp_send_no_response" if isinstance(exc, TimeoutError) else "email_otp_send_unknown"
    if isinstance(exc, ForwardIMAPNoMailTimeout):
        return "email_otp_no_mail"
    return "post_register_failure"


def _safe_protocol_registration_error(exc: BaseException, cause_code: str) -> str:
    """仅保留固定阶段、异常类型和 HTTP 状态，不复制远端正文。"""
    from core.operations.errors import safe_registration_diagnostics

    diagnostics = safe_registration_diagnostics(getattr(exc, "registration_diagnostics", None))
    descriptions = {
        "account_create_invalid_state": "资料提交时认证会话已失效",
        "account_create_user_already_exists": "远端提示账号已存在，完整登录态尚未确认",
        "user_register_result_unknown": "账号创建请求结果待确认，未保留失败细项",
        "registration_checkpoint_failed": "注册执行检查点读取或保存失败",
        "user_register_continue_url_missing": "账号创建响应缺少后续验证地址",
        "email_otp_send_rejected": "验证码发送请求被拒绝",
        "email_otp_send_failed": "验证码发送请求失败",
        "email_otp_send_unconfirmed": "验证码发送结果未确认",
        "email_otp_send_no_response": "验证码发送请求未收到响应",
        "email_otp_send_unknown": "验证码发送结果待确认",
        "email_otp_no_mail": "等待窗口内未收到验证码邮件",
        "post_register_failure": "注册请求之后流程失败",
        "registration_failed": "注册流程失败",
        "password_entry_navigation_failed": "密码入口导航失败",
        "password_entry_navigation_timeout": "密码入口导航超时",
        "password_entry_not_offered": "当前认证页未提供可用密码入口",
        "registration_password_entry_unavailable": "强制密码步骤未能进入创建或验证页面",
        "registration_password_create_rejected": "远端拒绝了本轮强制密码创建请求",
        "registration_password_unconfirmed": "注册认证已完成，强制密码尚未确认",
        "registration_auth_state_unrecognized": "注册认证返回未支持的页面状态",
        "registration_session_invalid_response": "注册认证未返回可核验的完整会话",
        "identity_mismatch": "登录会话邮箱缺失或与原注册邮箱不匹配",
        "protocol_preauth_transport_failed": "协议认证前置请求发生传输错误",
        "protocol_post_otp_transport_failed": "已取得邮箱验证码，后续认证请求发生传输错误",
        "protocol_auth_transport_failed": "协议认证请求发生传输错误",
        "protocol_auth_rejected_before_password": "密码尚未确认时认证请求被拒绝",
        "protocol_auth_http_failed": "协议认证请求返回 HTTP 错误",
        "protocol_session_incomplete": "注册资料已确认，后续登录态尚未取得",
        "protocol_failure_evidence_missing": "协议失败未保留足够请求证据，无法确认具体原因",
    }
    type_name = diagnostics.get("exception_type", "Exception") if diagnostics else type(exc).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", type_name):
        type_name = "Exception"
    response = getattr(exc, "response", None)
    status = diagnostics.get("http_status")
    for value in (
        getattr(response, "status_code", None),
        getattr(exc, "status_code", None),
        getattr(exc, "http_status", None),
    ):
        if diagnostics:
            break
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            continue
        if 100 <= candidate <= 599:
            status = candidate
            break
    if status is None and not diagnostics and not cause_code.startswith("protocol_") and cause_code != "user_register_result_unknown":
        match = re.search(r"\b(?:HTTP(?:\s+Error)?\s*:?|status\s*[=:])\s*(\d{3})\b", str(exc), re.IGNORECASE)
        if match:
            candidate = int(match.group(1))
            if 100 <= candidate <= 599:
                status = candidate
    suffix = f" HTTP {status}" if status is not None else ""
    if diagnostics:
        suffix += " 诊断=" + json.dumps(diagnostics, ensure_ascii=False, separators=(",", ":"))
    if diagnostics.get("operation") == "mailbox_wait":
        from core.operations.errors import classify_task_error

        info = classify_task_error("", task_type="registration", result_summary={"cause_code": cause_code})
        if info is not None:
            return f"{cause_code}: {info['summary']}：{type_name}{suffix}"
    if cause_code in {"account_create_invalid_state", "account_create_user_already_exists"} or (
        cause_code.startswith("protocol_") and cause_code in descriptions
    ) or (
        cause_code.startswith("registration_") and cause_code in descriptions
    ):
        return f"{cause_code}: {descriptions[cause_code]}：{type_name}{suffix}"
    return f"{descriptions.get(cause_code, '注册流程失败')}：{type_name}{suffix}"
