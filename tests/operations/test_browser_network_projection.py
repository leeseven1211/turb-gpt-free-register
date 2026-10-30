"""单条浏览器网络错误保留准确分类，不外推整个任务或代理状态。"""
import pytest

from core.operations.errors import classify_task_error


@pytest.mark.parametrize("raw", ["net::ERR_HTTP2_PING_FAILED", "ERR_HTTP2_PING_FAILED"])
def test_exact_http2_ping_failure_has_transport_display(raw):
    info = classify_task_error(raw, stage="submit_email", task_type="registration")
    assert info["code"] == "browser_http2_ping_failed"
    assert info["display_code"] == "NET-HTTP2-001"
    assert info["summary"] == "HTTP/2连接保活失败"
    assert info["stage"] == "submit_email"
    assert "代理" not in info["summary"]


@pytest.mark.parametrize("raw", [
    "RuntimeError: net::ERR_HTTP2_PING_FAILED", "net::ERR_HTTP2_PING_FAILED_EXTRA",
    "ERR_HTTP2_PING_FAIL", "其他失败 net::ERR_HTTP2_PING_FAILED",
    "RuntimeError: 邮箱提交后未进入密码页/验证码页，最后状态={}",
])
def test_other_errors_are_not_promoted_to_http2_ping_failure(raw):
    assert classify_task_error(raw, task_type="registration")["code"] != "browser_http2_ping_failed"
