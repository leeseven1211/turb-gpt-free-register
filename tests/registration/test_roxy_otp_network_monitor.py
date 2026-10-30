"""仅本地Roxy注册开启OTP页面监控，并保留原身份与未知事实。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.browser import email_otp
from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.auth.state_machine import StageBudget
from core.registration import roxy
from tests.registration import test_registration_resume_session as resume


@pytest.mark.parametrize('enabled', [True, False])
def test_current_code_and_refresh_retry_share_explicit_monitor_and_original_budget(enabled):
    driver = SimpleNamespace(current_url='https://auth.openai.com/email-verification')
    budget = StageBudget.start(240)
    seen = []

    def wait(active_driver, **kwargs):
        seen.append(kwargs)
        if len(seen) == 1:
            record_browser_submission_fact(active_driver, 'unknown', result='unknown')
            return 'retry_previous_otp'
        return 'accepted'

    with ExitStack() as stack:
        for name in ('_clear_otp_inputs', '_type_otp', '_check_manual_stop', 'human_delay', 'log_submission_diagnostics'):
            stack.enter_context(patch.object(roxy, name))
        stack.enter_context(patch.object(roxy, '_email_otp_page_state', return_value={}))
        submit = stack.enter_context(patch.object(roxy, '_submit_email_otp_current_form', return_value={'clicked': True}))
        stack.enter_context(patch.object(roxy, '_wait_after_email_otp_submit', side_effect=wait))
        outcome, receipt = roxy._submit_registration_email_otp(driver, '123456', budget=budget,
            expected_email='unit@example.test', monitor_otp_network=enabled)
    assert outcome == 'accepted'
    assert len(seen) == submit.call_count == 2
    assert all(item['budget'] is budget for item in seen)
    assert all(bool(item.get('monitor_otp_network')) is enabled for item in seen)
    assert [item['retry_after_refresh'] for item in seen] == [True, False]
    assert driver._browser_submission_receipts[0].phase == 'superseded'
    assert receipt is driver._browser_submission_receipts[1]


@pytest.mark.parametrize('other_helpers', [False, True])
def test_retained_unknown_only_local_roxy_opts_in_without_resubmitting(other_helpers):
    flow = resume.RetainedWindowFlowTests()
    pending = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='unknown')
    helpers = SimpleNamespace(driver_name='roxy_oss', submit_email_and_wait_next=Mock(), complete_profile_page=Mock()) if other_helpers else None
    with flow.retained_context(pending=pending) as (_, mocks):
        result = flow.run_registration(_browser_helpers=helpers)
    assert result['success'], result.get('error')
    assert bool(mocks['_wait_after_email_otp_submit'].call_args.kwargs.get('monitor_otp_network')) is (not other_helpers)
    for name in ('wait_for_otp', '_type_otp', '_submit_email_otp_current_form', '_resend_email_otp_after_failure'):
        mocks[name].assert_not_called()


def test_otp_observer_pairs_current_response_and_rejects_stale_cause():
    receipt = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='ui_dispatched')
    driver = SimpleNamespace(current_window_handle='CDwindow-target', _browser_submission_receipt=receipt, _browser_submission_receipts=[receipt])
    observer = roxy._make_submission_observer(driver, monitor_otp_network=True)
    request = {'target_id': 'target', 'request_id': 'first', 'endpoint_kind': 'otp_submit', 'http_method': 'POST'}
    observer(request)
    assert receipt.request_binding == ('target', 'first')
    observer({**request, 'response': True, 'http_status': 401, 'auth_error': {'code': 'wrong_email_otp_code'}})
    assert receipt.response_binding == ('target', 'first')
    assert receipt.auth_error == {'code': 'wrong_email_otp_code', 'type': 'unknown', 'category': 'otp_rejected'}

    # 同一动作之后观察到新请求时，旧响应已不能作为当前拒绝依据。
    second = {**request, 'request_id': 'second'}
    observer(second)
    assert receipt.request_binding == ('target', 'second')
    assert receipt.response_binding is None
    assert receipt.auth_error == {}
    observer({**second, 'response': True, 'http_status': 200})
    observer({**request, 'response': True, 'http_status': 401, 'auth_error': {'code': 'wrong_email_otp_code'}})
    assert receipt.response_binding == ('target', 'second')
    assert receipt.auth_error == {}
    assert not email_otp._otp_current_remote_rejection(receipt)


def test_other_driver_observer_keeps_otp_diagnostic_binding_disabled_by_default():
    receipt = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='ui_dispatched')
    driver = SimpleNamespace(_browser_submission_receipt=receipt, _browser_submission_receipts=[receipt])
    observer = roxy._make_submission_observer(driver)
    request = {'target_id': 'target', 'request_id': 'first', 'endpoint_kind': 'otp_submit', 'http_method': 'POST'}
    observer(request)
    observer({**request, 'response': True, 'http_status': 401, 'auth_error': {'code': 'wrong_email_otp_code'}})
    assert receipt.request_binding is None
    assert receipt.response_binding is None
    assert receipt.auth_error == {}
    assert receipt.phase == 'rejected'


@pytest.mark.parametrize('unknown', [True, False])
def test_typed_otp_network_reason_preserves_exact_unknown_semantics(unknown):
    error = email_otp.EmailOtpNetworkError('ERR_TUNNEL_CONNECTION_FAILED', request_unknown=unknown)
    assert roxy._is_registration_request_unknown(error) is unknown


def test_retained_otp_network_failure_keeps_original_identity_and_auth_unknown():
    flow = resume.RetainedWindowFlowTests()
    pending = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='unknown')
    error = email_otp.EmailOtpNetworkError('ERR_TUNNEL_CONNECTION_FAILED', request_unknown=True)
    with flow.retained_context(pending=pending) as (driver, mocks):
        driver._browser_submission_receipt = pending
        mocks['_wait_after_email_otp_submit'].side_effect = error
        result = flow.run_registration()
    assert not result['success']
    assert result['error_code'] == 'otp_page_network_error'
    assert result['cause_code'] == 'otp_network_tunnel_connection_failed'
    assert result['request_unknown'] is True
    assert result['auth']['code'] == 'otp_page_network_error'
    assert result['auth']['reconcile_required'] is True
    assert result['email'] == 'resume@example.test'
    assert pending.phase == 'unknown'
    assert driver._registration_fact_context['attempt_id'] == 41
    for name in ('wait_for_otp', '_type_otp', '_submit_email_otp_current_form', '_resend_email_otp_after_failure', 'navigate', 'release'):
        mocks[name].assert_not_called()
    mocks['client'].return_value.discard_profile.assert_not_called()
    mocks['retain_failed_browser'].assert_called_once()
    mocks['browser_resume_persist'].assert_called()


@pytest.mark.parametrize('other_helpers', [False, True])
def test_normal_registration_opts_in_only_for_local_roxy(other_helpers):
    flow = resume.RetainedWindowFlowTests()
    helpers = SimpleNamespace(driver_name='roxy_oss', submit_email_and_wait_next=Mock(), complete_profile_page=Mock()) if other_helpers else None
    submitted = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='ui_dispatched')
    with flow.retained_context() as (_, mocks), patch.object(roxy, '_submit_registration_email_otp', return_value=('accepted', submitted)) as submit:
        mocks['wait_for_otp'].return_value = '123456'
        mocks['_wait_email_otp_page_ready'].return_value = 'ready'
        result = flow.run_registration(_browser_helpers=helpers)
    assert result['success'], result.get('error')
    assert bool(submit.call_args.kwargs.get('monitor_otp_network')) is (not other_helpers)


def test_old_otp_response_cannot_reject_current_inflight_request():
    receipt = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='ui_dispatched')
    driver = SimpleNamespace(current_window_handle='target', _browser_submission_receipt=receipt, _browser_submission_receipts=[receipt])
    observer = roxy._make_submission_observer(driver, monitor_otp_network=True)
    first = {'target_id': 'target', 'request_id': 'first', 'endpoint_kind': 'otp_submit', 'http_method': 'POST'}
    second = {**first, 'request_id': 'second'}
    observer(first)
    observer(second)
    observer({**first, 'response': True, 'http_status': 401, 'auth_error': {'code': 'wrong_email_otp_code'}})
    assert receipt.phase == 'request_observed'
    assert receipt.response_binding is None
    observer({**second, 'response': True, 'http_status': None})
    assert receipt.phase == 'response_observed'
    assert receipt.http_status is None
    assert receipt.auth_error == {}


@pytest.mark.parametrize('typed_error', [True, False])
def test_new_otp_reason_does_not_expand_proxy_fault_scheduling(typed_error):
    flow = resume.ResumeSessionFlowTests()
    error = (email_otp.EmailOtpNetworkError('ERR_TUNNEL_CONNECTION_FAILED', request_unknown=True)
             if typed_error else RuntimeError('net::ERR_TUNNEL_CONNECTION_FAILED'))
    with flow.run_context() as (driver, mocks):
        driver.current_url = 'https://auth.openai.com/log-in'
        mocks['navigate'].side_effect = None
        mocks['_submit_email_and_wait_next'].side_effect = error
        result = flow.run_registration()
    assert not result['success']
    assert result['current_lease_route_verified'] is True
    assert result['proxy_transport_failure'] is (not typed_error)
    assert result['resume_login_get_transport_failure'] is False


def test_otp_response_from_other_target_or_endpoint_cannot_supply_rejection():
    receipt = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='ui_dispatched')
    driver = SimpleNamespace(current_window_handle='CDwindow-current', _browser_submission_receipt=receipt, _browser_submission_receipts=[receipt])
    observer = roxy._make_submission_observer(driver, monitor_otp_network=True)
    request = {'target_id': 'current', 'request_id': 'same-id', 'endpoint_kind': 'otp_submit', 'http_method': 'POST'}
    observer(request)
    response = {**request, 'response': True, 'http_status': 401, 'auth_error': {'code': 'wrong_email_otp_code'}}
    observer({**response, 'target_id': 'other'})
    observer({**response, 'endpoint_kind': 'password_verify'})
    assert receipt.response_binding is None
    assert receipt.auth_error == {}
    assert receipt.phase == 'request_observed'
    observer(response)
    assert email_otp._otp_current_remote_rejection(receipt)


@pytest.mark.parametrize('handle,target', [
    (None, 'other'), ('', ''), ('CDwindow-', ''), (Mock(), 'other'),
    ('invalid handle', 'invalid handle'), ('CDwindow-current', 'other'),
    ('current', ''), ('current', 'worker'),
])
def test_other_or_unverified_page_cannot_bind_otp_receipt(handle, target):
    receipt = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='ui_dispatched')
    driver = SimpleNamespace(current_window_handle=handle, _browser_submission_receipt=receipt, _browser_submission_receipts=[receipt])
    observer = roxy._make_submission_observer(driver, monitor_otp_network=True)
    request = {'target_id': target, 'request_id': 'first', 'endpoint_kind': 'otp_submit', 'http_method': 'POST'}
    observer(request)
    observer({**request, 'response': True, 'http_status': 401, 'auth_error': {'code': 'wrong_email_otp_code'}})
    assert receipt.request_binding is None
    assert receipt.response_binding is None
    assert receipt.auth_error == {}
    assert receipt.phase == 'ui_dispatched'


@pytest.mark.parametrize('phase', ['rejected', 'confirmed'])
@pytest.mark.parametrize('no_http_response', [False, True])
def test_network_failure_after_new_request_preserves_unknown_without_reverting_prior_terminal_fact(phase, no_http_response):
    receipt = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase=phase,
                                       http_method='POST', http_status=401 if phase == 'rejected' else 200)
    receipt.request_binding = receipt.response_binding = ('target', 'old')
    receipt.auth_error = {'code': 'wrong_email_otp_code'} if phase == 'rejected' else {}
    driver = SimpleNamespace(current_window_handle='CDwindow-target', _browser_submission_receipt=receipt,
                             _browser_submission_receipts=[receipt])
    observer = roxy._make_submission_observer(driver, monitor_otp_network=True)
    request = {'target_id': 'target', 'request_id': 'new', 'endpoint_kind': 'otp_submit', 'http_method': 'POST'}
    observer(request)
    if no_http_response:
        observer({**request, 'response': True, 'http_status': None})
    with pytest.raises(email_otp.EmailOtpNetworkError) as raised:
        email_otp._observe_email_otp_network_error(driver, {
            'url': 'chrome-error://chromewebdata/', 'text': 'ERR_TUNNEL_CONNECTION_FAILED',
        })
    assert raised.value.request_unknown is True
    assert receipt.phase == phase
    assert not email_otp._otp_current_remote_rejection(receipt)


@pytest.mark.parametrize('other_helpers', [False, True])
@pytest.mark.parametrize('twofa_driver', ['browser', 'protocol'])
def test_mfa_monitor_only_enabled_from_local_roxy_registration(other_helpers, twofa_driver):
    flow = resume.RetainedWindowFlowTests()
    helpers = SimpleNamespace(driver_name='roxy_oss', submit_email_and_wait_next=Mock(), complete_profile_page=Mock()) if other_helpers else None
    with flow.retained_context() as (_, mocks), patch.object(roxy, 'setup_protocol_2fa_with_browser_fallback',
                                                            return_value=('unit-totp', False)) as protocol:
        mocks['twofa_driver'].return_value = twofa_driver
        result = flow.run_registration(_browser_helpers=helpers, registration_options={
            'password_enabled': True, 'twofa_enabled': True, 'codex_enabled': False, 'plan_check_enabled': False,
        })
    assert result['success'], result.get('error')
    setup = protocol if twofa_driver == 'protocol' else mocks['twofa']
    setup.assert_called_once()
    assert bool(setup.call_args.kwargs.get('monitor_mfa_enrollment')) is (not other_helpers)


def test_late_success_response_cannot_reopen_page_confirmed_network_unknown():
    receipt = BrowserSubmissionReceipt(kind='otp', stage='email_otp', endpoint_kind='otp_submit', phase='ui_dispatched')
    driver = SimpleNamespace(current_window_handle='target', _browser_submission_receipt=receipt,
                             _browser_submission_receipts=[receipt])
    observer = roxy._make_submission_observer(driver, monitor_otp_network=True)
    request = {'target_id': 'target', 'request_id': 'current', 'endpoint_kind': 'otp_submit', 'http_method': 'POST'}
    observer(request)
    with patch.object(email_otp, '_email_otp_page_state', return_value={
        'url': 'https://auth.openai.com/verified', 'emailVerified': True,
    }), patch.object(email_otp, '_is_email_verification_page', return_value=False), \
            patch.object(email_otp, 'log_submission_diagnostics'):
        assert email_otp._wait_after_email_otp_submit(driver, timeout=0, monitor_otp_network=True) == 'email_verified'
    receipt.transition('confirmed')
    observer({**request, 'response': True, 'http_status': 200})
    assert receipt._otp_network_request_unknown is False
    with pytest.raises(email_otp.EmailOtpNetworkError) as raised:
        email_otp._observe_email_otp_network_error(driver, {
            'url': 'chrome-error://chromewebdata/', 'text': 'ERR_TUNNEL_CONNECTION_FAILED',
        })
    assert raised.value.request_unknown is False
    assert receipt.phase == 'confirmed'
