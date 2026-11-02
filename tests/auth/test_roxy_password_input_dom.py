"""在隔离 Chromium 中验证 Roxy 密码读回与原提交校验。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.auth.browser import password_auth
from tests.auth import test_mfa_page_dom as mfa_dom


chromium_page = mfa_dom.page


_PASSWORD = "FixturePass123!"
_FORM = """
<form id="login">
  <input name="username" type="email" value="fixture@example.test" readonly>
  <input id="password" type="password" required minlength="8" value="attribute-only">
  <button type="submit">Continue</button>
</form>
<script>
const field = document.querySelector('#password');
const form = document.querySelector('form');
const native = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
native.set.call(field, '');
window.fixture = {setterCalls:0, inputEvents:0, changeEvents:0, clicks:0, submissions:0,
  submitted:false, rejectSetter:false, replaceOnInput:false};
Object.defineProperty(HTMLInputElement.prototype, 'value', {
  configurable:true, get:native.get,
  set(value) {
    window.fixture.setterCalls += 1;
    if (!window.fixture.rejectSetter) native.set.call(this, value);
  },
});
field.addEventListener('input', () => {
  window.fixture.inputEvents += 1;
  if (window.fixture.replaceOnInput) field.replaceWith(field.cloneNode());
});
field.addEventListener('change', () => window.fixture.changeEvents += 1);
document.querySelector('button').addEventListener('click', () => window.fixture.clicks += 1);
form.onsubmit = event => {
  event.preventDefault();
  window.fixture.submissions += 1;
  window.fixture.submitted = true;
};
</script>
"""


class _PasswordDriver(mfa_dom._Driver):
    def __init__(self, page, clock):
        super().__init__(page)
        self.clock = clock
        self.queue_attempts = 0

    def execute_script(self, script, *args):
        result = super().execute_script(script, *args)
        if args and args[0] == "queue":
            self.queue_attempts += 1
            if result.get("ok"):
                self.page.wait_for_function("window.fixture.submitted")
            else:
                # 首轮拒绝后耗尽既有准备预算，避免测试重复驱动同一失败表单。
                self.clock.now = 10.0
        return result


@pytest.fixture
def password_form(chromium_page):
    chromium_page.goto('https://auth.openai.com/log-in/password')
    chromium_page.set_content(_FORM)
    return chromium_page


def _fill(page, *, typing="normal", reject_setter=False, replace_input=False, log_prefix=None):
    clock = SimpleNamespace(now=0.0)
    driver = _PasswordDriver(page, clock)
    if log_prefix is not None:
        driver._registration_log_prefix = log_prefix
    page.evaluate("value => window.fixture.rejectSetter = value", reject_setter)
    page.evaluate("value => window.fixture.replaceOnInput = value", replace_input)

    def type_password(_driver, element, value, *, clear):
        assert _driver is driver and clear is True
        if typing == "normal":
            element.handle.type(value)
        elif typing == "partial":
            element.handle.type(value[:3])
        elif typing == "raises":
            raise RuntimeError("输入桥接失败")
        # empty 模拟 send_keys 正常返回，但页面没有接受任何字符。

    def state(_driver):
        submitted = page.evaluate("window.fixture.submitted")
        return {
            "url": "https://auth.openai.com/" + ("email-verification" if submitted else "log-in/password"),
            "inputs": [{"type": "text", "name": "code"}] if submitted else [{"type": "password"}],
        }

    with ExitStack() as stack:
        for name, replacement in (
            ("_human_type_text", type_password),
            ("_password_page_state", state),
            ("_is_email_verification_page", lambda _driver: page.evaluate("window.fixture.submitted")),
            ("_is_login_password_page", lambda _driver: True),
            ("_is_signup_password_page", lambda _driver: False),
            ("_has_access_token", lambda _driver: False),
            ("_registration_auth_mode", lambda: "password"),
        ):
            stack.enter_context(patch.object(password_auth, name, side_effect=replacement))
        stack.enter_context(patch.object(password_auth, "human_delay"))
        stack.enter_context(patch.object(password_auth, "log_submission_diagnostics"))
        stack.enter_context(patch.object(password_auth, "time", SimpleNamespace(time=lambda: clock.now, sleep=lambda _: None)))
        result = password_auth._fill_password_page_if_present(
            driver, "fixture@example.test", timeout=1, existing_password=_PASSWORD,
        )
    return result, driver


def test_matching_roxy_password_uses_the_dom_property_without_native_setter(password_form):
    result, driver = _fill(password_form)
    facts = password_form.evaluate("window.fixture")
    assert result == _PASSWORD
    assert password_form.locator('#password').get_attribute('value') == 'attribute-only'
    assert facts['setterCalls'] == 0
    assert facts['clicks'] == facts['submissions'] == driver.queue_attempts == 1


@pytest.mark.parametrize("typing, input_events, change_events", [("empty", 1, 1), ("partial", 4, 2)])
def test_roxy_silent_input_loss_uses_one_native_setter_then_the_original_queue(
    password_form, typing, input_events, change_events,
):
    result, driver = _fill(password_form, typing=typing)
    facts = password_form.evaluate("window.fixture")
    assert result == _PASSWORD
    assert password_form.locator('#password').input_value() == _PASSWORD
    assert facts['setterCalls'] == 1
    assert facts['inputEvents'] == input_events
    # 部分键入还会在原 setter 的 blur 时触发浏览器自身的 change。
    assert facts['changeEvents'] == change_events
    assert facts['clicks'] == facts['submissions'] == driver.queue_attempts == 1


def test_rejected_native_setter_still_cannot_queue_or_click_a_password_submit(password_form):
    with pytest.raises(RuntimeError, match='password_form_not_ready.*password_value_changed'):
        _fill(password_form, typing="empty", reject_setter=True)
    facts = password_form.evaluate("window.fixture")
    assert facts['setterCalls'] == facts['inputEvents'] == facts['changeEvents'] == 1
    assert facts['clicks'] == facts['submissions'] == 0
    assert password_form.evaluate("window.__turbPasswordSubmissionReceipt === undefined")


def test_cloak_keeps_its_existing_password_input_behavior(password_form):
    with pytest.raises(RuntimeError, match='password_form_not_ready.*password_value_changed'):
        _fill(password_form, typing="empty", log_prefix="[Cloak注册]")
    facts = password_form.evaluate("window.fixture")
    assert facts['setterCalls'] == facts['clicks'] == facts['submissions'] == 0


def test_setter_rerender_cannot_submit_a_replacement_node_even_with_the_same_password(password_form):
    with pytest.raises(RuntimeError, match='password_form_not_ready.*password_input_replaced'):
        _fill(password_form, typing="empty", replace_input=True)
    facts = password_form.evaluate("window.fixture")
    assert password_form.locator('#password').input_value() == _PASSWORD
    assert facts['setterCalls'] == 1
    assert facts['clicks'] == facts['submissions'] == 0
    assert password_form.evaluate("window.__turbPasswordSubmissionReceipt === undefined")


def test_typing_exception_does_not_run_the_added_password_setter(password_form):
    with pytest.raises(RuntimeError, match='输入桥接失败'):
        _fill(password_form, typing="raises")
    facts = password_form.evaluate("window.fixture")
    assert facts['setterCalls'] == facts['clicks'] == facts['submissions'] == 0
