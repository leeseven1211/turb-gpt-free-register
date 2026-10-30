"""MFA新增页面原因保持固定分类、原状态及远端结果边界。"""
from copy import deepcopy

import pytest

from core.operations.errors import classify_task_error


@pytest.mark.parametrize('code,display,summary', [
    ('mfa_enrollment_page_error', 'AUTH-MFA-PAGE', 'MFA 设置页显示明确错误'),
    ('mfa_enrollment_unsupported', 'FLOW-MFA-STEP', 'MFA 当前验证步骤暂不支持'),
    ('mfa_otp_provider_not_cooperative', 'SYS-MFA-OTP', 'MFA 收码适配器不支持页面协作检查'),
    ('mfa_enrollment_step_changed', 'FLOW-MFA-CHANGED', 'MFA 设置期间页面步骤已变化，未继续激活'),
    ('mfa_activation_unconfirmed', 'AUTH-MFA-CONFIRM', 'MFA 激活结果尚未通过同邮箱远端核验'),
    ('totp_rejected', 'AUTH-MFA-TOTP-REJECTED', 'Authenticator 验证码未通过验证'),
    ('email_otp_invalid', 'MAIL-OTP-004', '邮箱验证码未通过验证'),
])
@pytest.mark.parametrize('task_type', ['registration', 'twofa_retry', 'account_completion'])
def test_fixed_mfa_causes_do_not_fall_back_to_unclassified(code, display, summary, task_type):
    original = {'cause_code': code, 'outcome': 'request_unknown', 'pending_secret_saved': True}
    before = deepcopy(original)
    projected = classify_task_error(f'RuntimeError: {code}: 原始细节', task_type=task_type,
        stage='twofa', error_code='unknown.unclassified', result_summary=original)
    assert projected['code'] == code
    assert projected['display_code'] == display
    assert projected['summary'] == summary
    assert projected['reconcile_required'] is True
    assert original == before


@pytest.mark.parametrize('error', ['ERR_TUNNEL_CONNECTION_FAILED', 'ERR_PROXY_CONNECTION_FAILED',
    'ERR_CONNECTION_RESET', 'ERR_CONNECTION_CLOSED', 'ERR_HTTP2_PING_FAILED', 'ERR_NAME_NOT_RESOLVED'])
def test_mfa_network_page_retains_exact_known_transport_cause(error):
    projected = classify_task_error(f'RuntimeError: mfa_network_error: net::{error}',
        task_type='twofa_retry', stage='twofa', error_code='unknown.unclassified')
    assert projected['code'] == 'mfa_network_error'
    assert projected['display_code'] == 'NET-MFA-PAGE'
    assert error in projected['summary']
    assert 'HTTP 500' not in projected['summary']


def test_mfa_completion_not_implied_by_activation_unconfirmed():
    projected = classify_task_error('RuntimeError: mfa_activation_unconfirmed: reason=totp_disabled',
        task_type='twofa_retry', stage='twofa')
    assert projected['code'] == 'mfa_activation_unconfirmed'
    assert projected['remote_state_impact'] == 'unknown'
    assert projected['next_action'] == 'inspect_failure'
