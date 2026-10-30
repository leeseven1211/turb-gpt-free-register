"""在隔离浏览器执行生产DOM脚本；不接触远端或用户浏览器。"""
from pathlib import Path
from unittest.mock import patch

import pytest

from core.auth.browser import mfa_auth


class _Element:
    def __init__(self, handle):
        self.handle = handle

    def get_attribute(self, key):
        return self.handle.evaluate("(el, key) => key === 'textContent' ? el.textContent : el.getAttribute(key)", key)

    def is_displayed(self):
        return self.handle.is_visible()

    def is_enabled(self):
        return self.handle.is_enabled()


class _Driver:
    def __init__(self, page):
        self.page = page

    @property
    def current_url(self):
        return self.page.url

    def find_elements(self, by, value):
        selector = '#' + value if by == 'id' else value
        return [_Element(handle) for handle in self.page.query_selector_all(selector)]

    def execute_script(self, script, *args):
        values = [arg.handle if isinstance(arg, _Element) else arg for arg in args]
        handle = self.page.evaluate_handle("args => (function(){" + script + "}).apply(null, args)", values)

        def convert(value):
            element = value.as_element()
            if element is not None:
                return _Element(element)
            kind = value.evaluate("v => v === null ? 'primitive' : Array.isArray(v) ? 'array' : typeof v")
            if kind in {'array', 'object'}:
                props = value.get_properties()
                if kind == 'array':
                    return [convert(props[key]) for key in sorted((key for key in props if key.isdigit()), key=int)]
                return {key: convert(item) for key, item in props.items()}
            return value.json_value()

        return convert(handle)


@pytest.fixture
def page():
    api = pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip('本机未安装隔离 Chromium 测试运行时')
        browser = runtime.chromium.launch(headless=True)
        context = browser.new_context()
        fixture = Path(__file__).parents[1] / 'fixtures/mfa-authenticator-modern.html'
        context.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html', body=fixture.read_text()))
        current = context.new_page()
        current.goto('https://chatgpt.com/settings/security')
        try:
            yield current
        finally:
            context.close()
            browser.close()


def test_actual_hindi_dialog_manual_rerender_submit_and_success_toast(page):
    driver = _Driver(page)
    events = []
    first, field = mfa_auth._detect_mfa_enrollment_step(driver, monitor_mfa_enrollment=True)
    assert first == 'totp'
    assert field.get_attribute('name') == 'verification-code'
    assert mfa_auth._button_after_input(driver, field) is None
    toggle = mfa_auth._find_authenticator_toggle(driver)

    with patch.object(mfa_auth, '_open_chatgpt_security_settings', return_value=toggle), \
            patch.object(mfa_auth, '_human_click', side_effect=lambda _driver, element, **kwargs: element.handle.click()), \
            patch.object(mfa_auth, '_human_type_text', side_effect=lambda _driver, element, value, **kwargs: element.handle.fill(value)), \
            patch.object(mfa_auth, '_probe_existing_roxy_totp', side_effect=lambda _driver, email, **kwargs:
                (events.append(('核验', email)), {'confirmed': True, 'reason': 'totp_enabled'})[1]), \
            patch.object(mfa_auth.time, 'time', return_value=100):
        secret = mfa_auth.setup_roxy_2fa(driver, 'fixture@example.test', monitor_mfa_enrollment=True,
            on_secret=lambda _secret: events.append(('pending', page.locator('[role="switch"]').get_attribute('aria-checked'))))
    assert secret == 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'
    assert events == [('pending', 'false'), ('核验', 'fixture@example.test')]
    assert mfa_auth._detect_mfa_enrollment_step(driver, monitor_mfa_enrollment=True) == ('complete', None)


def test_real_hidden_and_sms_fields_never_replace_authenticator_semantics(page):
    driver = _Driver(page)
    page.locator('input').evaluate("el => el.hidden = true")
    assert mfa_auth._detect_mfa_enrollment_step(driver, monitor_mfa_enrollment=True) == ('transition', None)
    page.locator('[role="dialog"]').evaluate("el => { el.innerHTML = '<h2>SMS verification</h2><input name=verification-code autocomplete=one-time-code>'; }")
    with pytest.raises(RuntimeError, match='mfa_enrollment_unsupported'):
        mfa_auth._detect_mfa_enrollment_step(driver, monitor_mfa_enrollment=True)


def test_default_manual_key_read_keeps_existing_role_dialog(page):
    page.set_content('<section role="dialog"><form><input name="totp_otp"></form>'
        '<code>JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP</code></section>')
    driver = _Driver(page)
    field = driver.find_elements('css selector', 'input')[0]
    assert mfa_auth._read_totp_secret_from_dialog(driver, field) == 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'


def test_hindi_manual_entry_is_available_only_with_explicit_monitor(page):
    driver = _Driver(page)
    field = driver.find_elements('css selector', 'input')[0]
    with pytest.raises(RuntimeError, match='未提供安全可点击的手动密钥入口'):
        mfa_auth._manual_totp_secret(driver, field)
    with patch.object(mfa_auth, '_human_click', side_effect=lambda _driver, element, **_kwargs: element.handle.click()):
        assert mfa_auth._manual_totp_secret(driver, field, monitor_mfa_enrollment=True) == (
            'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'
        )
