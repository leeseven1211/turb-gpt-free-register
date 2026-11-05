"""AT 回调与 Session 失败须保留具体原因和原有手动重跑语义。"""
from copy import deepcopy

import pytest

from core.operations.errors import classify_task_error


@pytest.mark.parametrize("operation,label,prefix", [
    ("oauth_callback", "OAuth 回调", "NET-CALLBACK"),
    ("session_fetch", "认证后的 Session 读取", "NET-SESSION-READ"),
])
@pytest.mark.parametrize("curl_code,suffix,display,detail", [
    (5, "proxy_dns", "005", "代理域名解析失败"),
    (6, "dns", "006", "目标域名解析失败"),
    (7, "connect", "007", "连接建立失败"),
    (18, "partial_response", "018", "响应传输截断"),
    (28, "timeout", "001", "请求超时"),
    (35, "tls", "002", " TLS 握手失败"),
    (52, "empty_response", "052", "连接关闭且未收到有效响应"),
    (55, "send", "055", "请求发送中断"),
    (56, "connection", "003", "连接中断"),
    (60, "certificate", "004", " TLS 证书校验失败"),
    (97, "proxy", "097", "代理隧道连接失败"),
])
def test_callback_and_session_network_causes_are_kept_separate(operation, label, prefix, curl_code, suffix, display, detail):
    cause_code = "oauth_callback_failed" if operation == "oauth_callback" else "session_fetch_failed"
    result = classify_task_error(
        "认证未完成", task_type="token_refresh", stage="token", error_code=cause_code,
        result_summary={"cause_code": cause_code, "auth_diagnostics": {
            "operation": operation, "failure_kind": "transport_error", "curl_error_code": curl_code,
            "exception_type": "RequestsError", "response_observed": False,
        }},
    )
    assert result["code"] == f"{operation}_transport_{suffix}"
    assert result["display_code"] == f"{prefix}-{display}"
    assert result["summary"] == label + detail
    assert result["source"] == "external"
    assert result["stage"] == "token"
    assert result["retryability"] == "conditional"


@pytest.mark.parametrize("operation,label,prefix", [
    ("oauth_callback", "OAuth 回调", "OA-CALLBACK"),
    ("session_fetch", "认证后的 Session 读取", "OA-SESSION"),
])
@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_callback_http_errors_do_not_imply_credentials_rejected_or_account_deactivated(operation, label, prefix, status):
    result = classify_task_error(
        "认证未完成", task_type="token_refresh", error_code="request_unknown", task_status="attention_required",
        result_summary={"outcome": "request_unknown", "cause_code": "oauth_callback_failed",
                        "auth_diagnostics": {"operation": operation, "failure_kind": "http_error",
                                             "http_status": status, "response_observed": True}},
    )
    assert result["code"] == f"{operation}_http_error"
    assert result["display_code"] == f"{prefix}-{status}"
    assert result["summary"] == f"{label}请求返回 HTTP {status}"
    assert result["reconcile_required"] is True
    assert result["retryability"] == "manual_only"
    assert result["next_action"] == "manual_reconcile"


@pytest.mark.parametrize("operation,kind,code,display,summary", [
    ("session_fetch", "invalid_response", "session_invalid_response", "AUTH-SESSION-002", "认证后的登录会话响应无效"),
    ("session_fetch", "missing_token", "access_token_missing", "AUTH-AT-001", "认证后的 Session 响应缺少 AT，登录态尚未建立"),
    ("session_fetch", "identity_mismatch", "session_identity_mismatch", "AUTH-IDENTITY-004", "认证后的 Session 身份与目标账号不一致"),
    ("session_fetch", "token_expired", "access_token_expired", "AUTH-SESSION-003", "认证返回的 AT 已过期，未确认为刷新成功"),
    ("oauth_callback", "redirect_invalid", "auth_redirect_invalid", "AUTH-URL-002", "认证跳转缺少有效目标地址"),
    ("oauth_callback", "redirect_limit", "auth_redirect_limit", "AUTH-URL-003", "认证跳转超出本次处理次数"),
])
def test_callback_semantic_failures_are_not_hidden_by_generic_network_cause(operation, kind, code, display, summary):
    original = {"cause_code": "oauth_callback_failed", "auth_diagnostics": {
        "operation": operation, "failure_kind": kind, "exception_type": "JSONDecodeError",
        "http_status": 200, "response_observed": True, "redirect_hop": 2, "retry_attempt": 1,
        "target_host": "chatgpt.com", "target_path": "/api/auth/session",
        "private_response": "private-user@example.test private-token private-password",
    }}
    before = deepcopy(original)
    result = classify_task_error("认证未完成", task_type="token_refresh", result_summary=original)
    assert result["code"] == code
    assert result["display_code"] == display
    assert result["summary"] == summary
    assert "private-" not in str(result)
    assert original == before


@pytest.mark.parametrize("exception_type,suffix", [
    ("ProxyError", "proxy"), ("ReadTimeout", "timeout"), ("SSLError", "tls"),
    ("ConnectionResetError", "connection"), ("IncompleteRead", "partial_response"),
])
def test_callback_exception_type_can_supply_a_network_cause_without_curl_code(exception_type, suffix):
    result = classify_task_error("", result_summary={"cause_code": "oauth_callback_failed", "auth_diagnostics": {
        "operation": "oauth_callback", "failure_kind": "transport_error", "exception_type": exception_type,
    }})
    assert result["code"] == f"oauth_callback_transport_{suffix}"


def test_session_failure_does_not_borrow_transport_details_from_another_request():
    result = classify_task_error("认证未完成", result_summary={
        "cause_code": "session_fetch_failed",
        "auth_diagnostics": {"operation": "session_fetch", "failure_kind": "transport_error"},
        "cause_diagnostics": {"operation": "password_sentinel", "curl_error_code": 35},
    })
    assert result["code"] == "session_fetch_transport_error"
    assert result["summary"] == "认证后的 Session 读取网络请求失败"


@pytest.mark.parametrize("auth_code", [
    "OAuthCallback", "OAuthSignin", "Configuration", "AccessDenied", "invalid_state", "invalid_grant",
])
def test_callback_error_redirect_shows_only_its_observed_error_code(auth_code):
    result = classify_task_error(
        "认证未完成", task_type="token_refresh", task_status="attention_required", error_code="request_unknown",
        result_summary={"outcome": "request_unknown", "cause_code": "oauth_callback_rejected",
                        "auth_diagnostics": {"operation": "oauth_callback", "failure_kind": "rejected",
                                             "http_status": 302, "response_observed": True,
                                             "auth_error": {"code": auth_code}}},
    )
    assert result["code"] == "oauth_callback_rejected"
    assert result["display_code"] == "AUTH-CALLBACK-002"
    assert result["summary"] == f"OAuth 回调返回认证错误，未建立有效会话（回调错误码：{auth_code}）"
    assert result["source"] == "external"
    assert result["retryability"] == "manual_only"
    assert "密码" not in result["summary"]
    assert "code 已消费" not in result["summary"]
    assert "停用" not in result["summary"]


@pytest.mark.parametrize("auth_code", ["private-token@example.test", "account_deactivated", ["OAuthCallback"], None])
def test_unrecognized_callback_error_codes_do_not_escape_the_projection(auth_code):
    original = {"cause_code": "oauth_callback_rejected", "auth_diagnostics": {
        "operation": "oauth_callback", "failure_kind": "rejected", "auth_error": {"code": auth_code},
    }}
    before = deepcopy(original)
    result = classify_task_error("认证未完成", task_type="token_refresh", result_summary=original)
    assert result["code"] == "oauth_callback_rejected"
    assert result["summary"] == "OAuth 回调返回认证错误，未建立有效会话"
    assert original == before


@pytest.mark.parametrize("code", [
    "oauth_callback_failed", "oauth_callback_rejected", "session_fetch_failed", "session_invalid_response", "access_token_missing",
    "session_identity_mismatch", "access_token_expired", "auth_redirect_invalid", "auth_redirect_limit",
])
def test_fixed_callback_causes_are_classified_without_legacy_message_text(code):
    result = classify_task_error("认证未完成", task_type="token_refresh", error_code=code)
    assert result["code"] == code
    assert result["source"] != "unknown"
    assert result["display_code"] != "UNK-000"
