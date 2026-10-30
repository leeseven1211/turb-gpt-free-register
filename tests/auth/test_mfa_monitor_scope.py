"""共享 MFA 默认使用旧流程，注册监控只能由调用方显式启用。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.browser import mfa_auth
from core.email.mailbox_wait import current_budget


SECRET = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'


def test_default_detector_keeps_legacy_css_without_reading_whole_document():
    field = Mock()
    field.is_displayed.return_value = True
    driver = SimpleNamespace(
        execute_script=Mock(side_effect=AssertionError('默认入口不读取新的整页识别脚本')),
        find_elements=lambda _by, selector: [field] if selector == 'input[name="totp_otp"]' else [],
    )
    assert mfa_auth._detect_mfa_enrollment_step(driver) == ('totp', field)


def test_default_detector_keeps_generic_email_classification_for_modern_name():
    field = Mock()
    field.is_displayed.return_value = True
    driver = SimpleNamespace(
        execute_script=Mock(side_effect=AssertionError('默认入口不启用新版语义识别')),
        find_elements=lambda _by, selector: [field] if 'one-time-code' in selector else [],
    )
    assert mfa_auth._detect_mfa_enrollment_step(driver) == ('email', field)


def test_default_setup_keeps_opaque_otp_provider_and_original_field_without_monitor():
    email_field, totp_field, button = object(), object(), object()
    enabled = [False]
    toggle = Mock()
    toggle.get_attribute.side_effect = lambda key: 'true' if key == 'aria-checked' and enabled[0] else 'false'
    calls = []

    def provider(email, *, after_ts):
        calls.append((email, after_ts, current_budget()))
        return '123456'

    def click(_driver, _element, *, label):
        if label == 'totp_verify':
            enabled[0] = True

    with ExitStack() as stack:
        for name, result in (
            ('_open_chatgpt_security_settings', toggle),
            ('_wait_mfa_enrollment_step', ('email', email_field)),
            ('_wait_after_mfa_email_submit', totp_field),
            ('_manual_totp_secret', SECRET), ('_button_after_input', button),
            ('_find_authenticator_toggle', toggle), ('_first_visible_css', None),
        ):
            stack.enter_context(patch.object(mfa_auth, name, return_value=result))
        stack.enter_context(patch.object(mfa_auth, '_human_click', side_effect=click))
        typed = stack.enter_context(patch.object(mfa_auth, '_human_type_text'))
        detect = stack.enter_context(patch.object(mfa_auth, '_detect_mfa_enrollment_step',
            side_effect=AssertionError('默认激活不执行新步骤监控')))
        probe = stack.enter_context(patch.object(mfa_auth, '_probe_existing_roxy_totp',
            side_effect=AssertionError('默认激活不增加完成后的接口核验')))
        stack.enter_context(patch.object(mfa_auth.time, 'time', return_value=100))
        assert mfa_auth.setup_roxy_2fa(object(), 'unit@example.test', otp_provider=provider) == SECRET

    assert calls == [('unit@example.test', 100, None)]
    assert [call.args[1] for call in typed.call_args_list] == [email_field, totp_field]
    detect.assert_not_called()
    probe.assert_not_called()


def test_default_enabled_toggle_keeps_existing_secret_without_extra_final_probe():
    toggle = Mock()
    toggle.get_attribute.return_value = 'true'
    with patch.object(mfa_auth, '_open_chatgpt_security_settings', return_value=toggle), \
            patch.object(mfa_auth, '_probe_existing_roxy_totp', return_value={
                'confirmed': False, 'reason': 'read_failed',
            }) as probe, \
            patch.object(mfa_auth, '_detect_mfa_enrollment_step',
                side_effect=AssertionError('默认已启用开关不新增弹窗识别')):
        assert mfa_auth.setup_roxy_2fa(object(), 'unit@example.test', existing_secret=SECRET) == SECRET
    probe.assert_called_once()


@pytest.mark.parametrize('enabled', [False, True])
def test_protocol_browser_fallback_only_forwards_explicit_monitor(enabled):
    with patch.object(mfa_auth, 'setup_2fa_protocol', side_effect=RuntimeError('协议失败')), \
            patch.object(mfa_auth, 'setup_roxy_2fa', return_value=SECRET) as browser:
        kwargs = {'monitor_mfa_enrollment': True} if enabled else {}
        assert mfa_auth.setup_protocol_2fa_with_browser_fallback(
            object(), 'unit@example.test', object(), 'unit-access-token', **kwargs,
        ) == (SECRET, True)
    assert bool(browser.call_args.kwargs.get('monitor_mfa_enrollment')) is enabled
    if not enabled:
        assert 'monitor_mfa_enrollment' not in browser.call_args.kwargs
