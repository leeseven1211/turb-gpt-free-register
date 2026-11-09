"""套餐诊断只依据当前回执，不推测历史和账号停用事实。"""
import pytest

from core.accounts.plans.errors import classify_plan_failure, country_failures_from_summary


@pytest.mark.parametrize(("detail", "code"), [
    ({"http_status": 401}, "token_http_401"),
    ({"http_status": 403}, "plan_http_forbidden"),
    ({"http_status": 429}, "plan_http_rate_limited"),
    ({"http_status": 503}, "plan_http_server_error"),
    ({"error": "token 为空"}, "token_missing"),
    ({"error": "该国库存暂缺，累计等待预算已耗尽"}, "proxy_supply_exhausted"),
    ({"error": "国家查询总期限已到"}, "country_deadline_exhausted"),
    ({"error": "该国家请求次数已耗尽"}, "country_attempts_exhausted"),
    ({"error": "请求 VN 出口，实际检测为 JP，未执行该国查询"}, "proxy_country_mismatch"),
    ({"http_status": 200, "error": "响应不是 JSON 对象"}, "response_invalid"),
    ({"error": "空响应"}, "response_missing"),
    ({"error": "ProxyError: curl: (56) Proxy CONNECT aborted"}, "proxy_connect_failed"),
    ({"error": "curl: (7) CONNECT tunnel failed"}, "proxy_tunnel_failed"),
    ({"error": "curl: (28) Operation timed out"}, "timeout"),
    ({"error": "curl: (6) Could not resolve host"}, "network_dns_failed"),
    ({"error": "curl: (35) TLS connect error"}, "network_tls_failed"),
    ({"error": "ConnectionError: connection reset"}, "network_connection_failed"),
    ({"error": "套餐查询重试配置错误: 无效配置"}, "plan_config_invalid"),
    ({"error": "自动刷新 AT 失败：MFA 未通过"}, "at_refresh_failed"),
    ({"error": "secret-value https://example.invalid"}, "detail_incomplete"),
])
def test_plan_failure_categories(detail, code):
    result = classify_plan_failure(detail)
    assert result["code"] == code
    assert "secret-value" not in str(result)
    assert "example.invalid" not in str(result)


def test_local_expiry_requires_current_local_evidence():
    detail = {"error": "AT已过期/失效，请手动查活刷新"}
    assert classify_plan_failure(detail, local_check_observed=True)["code"] == "token_expired_or_rejected"
    detail["http_status"] = None
    assert classify_plan_failure(detail, local_check_observed=True)["code"] == "token_local_expired"
    detail["http_status"] = 401
    assert classify_plan_failure(detail, local_check_observed=True)["code"] == "token_http_401"


def test_legacy_history_only_uses_latest_country_result():
    failures = country_failures_from_summary({"promotion_query_history": [
        {"country": "JP", "ok": False, "http_status": 401},
        {"country": "JP", "ok": True, "http_status": 200},
        {"country": "VN", "ok": False, "http_status": None},
    ]})
    assert [(row["country"], row["code"]) for row in failures] == [("VN", "detail_incomplete")]
