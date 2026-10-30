"""OTP 页面网络细因不会被回执状态或其他请求诊断覆盖。"""
from copy import deepcopy

import pytest

from core.operations.errors import classify_task_error
from core.registration.service import _registration_request_unknown_facts


OTP_NETWORK_CASES = [
    (
        'otp_network_tunnel_connection_failed', 'net::ERR_TUNNEL_CONNECTION_FAILED',
        'NET-OTP-TUNNEL', 'OTP 页面代理隧道连接失败（ERR_TUNNEL_CONNECTION_FAILED）',
    ),
    (
        'otp_network_proxy_connection_failed', 'net::ERR_PROXY_CONNECTION_FAILED',
        'NET-OTP-PROXY', 'OTP 页面代理连接失败（ERR_PROXY_CONNECTION_FAILED）',
    ),
    (
        'otp_network_connection_reset', 'net::ERR_CONNECTION_RESET',
        'NET-OTP-RESET', 'OTP 页面连接被重置（ERR_CONNECTION_RESET）',
    ),
    (
        'otp_network_connection_closed', 'net::ERR_CONNECTION_CLOSED',
        'NET-OTP-CLOSED', 'OTP 页面连接被关闭（ERR_CONNECTION_CLOSED）',
    ),
    (
        'otp_network_http2_ping_failed', 'net::ERR_HTTP2_PING_FAILED',
        'NET-OTP-HTTP2', 'OTP 页面 HTTP/2 连接探测失败（ERR_HTTP2_PING_FAILED）',
    ),
    (
        'otp_network_name_not_resolved', 'net::ERR_NAME_NOT_RESOLVED',
        'NET-OTP-DNS', 'OTP 页面域名解析失败（ERR_NAME_NOT_RESOLVED）',
    ),
    (
        'otp_network_failed_to_fetch', 'Failed to fetch',
        'NET-OTP-FETCH', 'OTP 页面请求读取失败（Failed to fetch）',
    ),
]


@pytest.mark.parametrize('code,network_error,display,summary', OTP_NETWORK_CASES)
@pytest.mark.parametrize('task_type', ['registration', 'registration_resume'])
def test_structured_otp_network_cause_keeps_unknown_receipt_and_input(
    code, network_error, display, summary, task_type,
):
    original = {
        'cause_code': code, 'outcome': 'request_unknown', 'request_unknown': True,
        'register_response_confirmed': True, 'attempt_id': 11,
        'retry_action': 'registration_resume',
        'otp_submit_receipt': {'state': 'request_unknown', 'dispatch_id': 'unit-otp'},
        'registration_diagnostics': {
            'operation': 'otp_validate', 'failure_kind': 'transport_error',
            'failure_stage': 'email_otp', 'last_confirmed_stage': 'password',
            'otp_received': True,
        },
    }
    before = deepcopy(original)

    projected = classify_task_error(
        '验证码页面传输失败', task_type=task_type, stage='email_otp',
        error_code='otp_page_network_error', result_summary=original,
    )

    assert projected['code'] == code
    assert projected['error_code'] == code
    assert projected['original_error_code'] == 'otp_page_network_error'
    assert projected['display_code'] == display
    assert projected['summary'] == summary
    assert projected['source'] == 'external'
    assert projected['source_label'] == '网络 / 上游服务'
    assert projected['reconcile_required'] is True
    assert projected['retryability'] == 'manual_only'
    assert projected['remote_state_impact'] == 'unknown'
    assert projected['next_action'] == 'manual_reconcile'
    assert original == before


@pytest.mark.parametrize('code,network_error,display,summary', OTP_NETWORK_CASES)
@pytest.mark.parametrize('task_type', ['registration', 'registration_resume'])
def test_fixed_otp_exception_text_retains_network_detail_without_summary(
    code, network_error, display, summary, task_type,
):
    projected = classify_task_error(
        f'EmailOtpNetworkError: otp_page_network_error: {code}: {network_error}；'
        '验证码页面传输失败，已保留原提交及同一账号上下文',
        task_type=task_type, stage='email_otp', error_code='otp_page_network_error',
    )

    assert projected['code'] == code
    assert projected['display_code'] == display
    assert projected['summary'] == summary
    assert projected['remote_state_impact'] == 'unknown'
    assert projected['next_action'] == 'inspect_failure'


@pytest.mark.parametrize('code,network_error,display,summary', OTP_NETWORK_CASES)
def test_registration_unknown_facts_keeps_fixed_otp_network_cause(
    code, network_error, display, summary,
):
    original = {
        'cause_code': code, 'register_response_confirmed': True,
        'raw_response': '不可透传的远端正文',
    }
    before = deepcopy(original)

    facts = _registration_request_unknown_facts(original)

    assert facts == {
        'outcome': 'request_unknown', 'cause_code': code,
        'register_response_confirmed': True,
    }
    assert original == before


@pytest.mark.parametrize('code', [
    'otp_page_network_error',
    'otp_network_failed_to_fetch_untrusted',
    'otp_network_untrusted_remote_body',
])
def test_registration_unknown_facts_does_not_expand_otp_cause_allowlist(code):
    assert _registration_request_unknown_facts({'cause_code': code}) == {
        'outcome': 'request_unknown',
    }


def test_failed_fetch_does_not_imply_proxy_http_or_invalid_otp():
    projected = classify_task_error(
        '验证码页面传输失败', task_type='registration', error_code='otp_page_network_error',
        result_summary={
            'cause_code': 'otp_network_failed_to_fetch',
            'auth_diagnostics': {
                'operation': 'password_verify', 'failure_kind': 'http_error',
                'http_status': 403,
            },
        },
    )

    assert projected['code'] == 'otp_network_failed_to_fetch'
    assert projected['summary'] == 'OTP 页面请求读取失败（Failed to fetch）'
    assert '代理' not in projected['summary']
    assert 'HTTP' not in projected['summary']
    assert '验证码未通过' not in projected['summary']
    assert '过期' not in projected['summary']
    assert 'http_status' not in projected
