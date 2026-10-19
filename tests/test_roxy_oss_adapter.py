"""开源页面辅助实际执行、本地提交契约与并发恢复。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.registration import auth_capabilities, email_otp, password_auth, roxy
from core.registration.auth_context import current_override
from core.registration.roxy_oss import RoxyOssBrowserHelpers, run_roxy_oss_registration
from core.registration.roxy_oss.upstream import browser_helpers as upstream


def test_entrypoint_preserves_profile_credentials_email_source_and_snapshot():
    options = {"registration_driver": "roxy_oss", "password_enabled": True}
    kwargs = {
        "email": "fixture@example.test", "name": "测试用户", "birthday": "1990-01-02",
        "proxy": "http://pool.example:8080", "otp_code": "unit-otp",
        "existing_password": "unit-saved-password", "existing_totp_secret": "unit-saved-totp",
        "profile_id": "unit-profile", "registration_options": options, "email_source": "icloud_hide",
    }
    expected = {"success": True}
    with patch.object(roxy, "run_roxy_registration", return_value=expected) as runner:
        assert run_roxy_oss_registration(**kwargs) is expected
    forwarded = dict(runner.call_args.kwargs)
    helpers = forwarded.pop("_browser_helpers")
    assert forwarded == kwargs
    assert isinstance(helpers, RoxyOssBrowserHelpers)
    assert helpers.driver_name == "roxy_oss"


def test_email_stage_executes_upstream_dom_with_local_submission_and_callbacks():
    driver = SimpleNamespace(execute_script=Mock(return_value=object()))
    submitted = Mock()
    progress = Mock()
    with (
        patch("core.registration_service.is_stop_requested", return_value=False),
        patch.object(upstream, "_find_visible_email_input_js", wraps=upstream._find_visible_email_input_js) as find,
        patch.object(email_otp, "_email_submit_advanced_state", return_value=None),
        patch.object(email_otp, "_human_type_text") as type_email,
        patch.object(email_otp, "_email_input_value_state", return_value={"inputs": [{"value": "fixture@example.test"}]}),
        patch.object(email_otp, "human_delay"),
        patch.object(email_otp, "_submit_email_step") as submit,
        patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"),
    ):
        result = RoxyOssBrowserHelpers().submit_email_and_wait_next(
            driver, "fixture@example.test", on_submitted=submitted, on_progress=progress,
        )
    assert result == "otp"
    find.assert_called_once_with(driver)
    driver.execute_script.assert_called_once()
    type_email.assert_called_once()
    submit.assert_called_once_with(driver, "fixture@example.test")
    submitted.assert_called_once_with()
    assert any(call.args[0] == "pending" for call in progress.call_args_list)
    assert current_override("_find_visible_email_input_js") is None


def test_profile_executes_upstream_filling_before_local_submission_and_identity_confirmation():
    order = []

    def script(source, *args):
        if "const birthday = String(arguments[0])" in source:
            order.append("birthday")
            return {"ok": True, "mode": "age"}
        if "allCheckboxes" in source:
            order.append("consent")
            return {"count": 1}
        if "valid:form.checkValidity()" in source:
            return {"valid": True}
        raise AssertionError("出现非预期页面脚本")

    driver = SimpleNamespace(execute_script=Mock(side_effect=script))
    profile = {"url": "https://auth.openai.com/about-you", "inputs": [{"name": "name"}]}
    homepage = {"url": "https://chatgpt.com/"}
    element = SimpleNamespace(tag_name="input")
    with (
        patch("core.registration_service.is_stop_requested", return_value=False),
        patch.object(password_auth, "_page_snapshot", side_effect=[profile, homepage]),
        patch.object(password_auth, "human_delay"),
        patch.object(upstream, "_find_any", return_value=element),
        patch.object(upstream, "_human_type_text", side_effect=lambda *_args, **_kwargs: order.append("name")),
        patch.object(upstream, "_fill_birthday_or_age", wraps=upstream._fill_birthday_or_age) as birthday,
        patch.object(password_auth, "_click_if_enabled_submit", side_effect=lambda *_args: order.append("submit") or True),
        patch.object(password_auth, "log_submission_diagnostics"),
        patch.object(password_auth, "_read_profile_session_once", return_value={"accessToken": "unit-token"}) as confirm,
    ):
        assert RoxyOssBrowserHelpers().complete_profile_page(
            driver, "测试用户", "1990-01-02", expected_email="fixture@example.test", timeout=10,
        ) is True
    birthday.assert_called_once()
    assert order == ["birthday", "name", "consent", "submit"]
    assert confirm.call_args.kwargs["expected_email"] == "fixture@example.test"
    assert current_override("_fill_birthday_or_age") is None


@pytest.mark.parametrize("upstream_fails", [False, True])
def test_upstream_and_local_roxy_remain_isolated_concurrently_and_after_errors(upstream_fails):
    barrier = Barrier(2)
    observed = {}

    def target(driver, _email, **_kwargs):
        observed[driver.name] = current_override("_find_visible_email_input_js")
        barrier.wait(timeout=5)
        if driver.name == "upstream" and upstream_fails:
            raise RuntimeError("模拟上游页面辅助失败")
        return email_otp._find_visible_email_input_js(driver)

    def invoke(name):
        driver = SimpleNamespace(name=name, execute_script=Mock(return_value=name))
        try:
            if name == "upstream":
                return RoxyOssBrowserHelpers().submit_email_and_wait_next(driver, "fixture@example.test")
            return roxy._call_shared_capability("_submit_email_and_wait_next", driver, "fixture@example.test")
        finally:
            assert current_override("_find_visible_email_input_js") is None

    with (
        patch("core.registration_service.is_stop_requested", return_value=False),
        patch.object(auth_capabilities, "_submit_email_and_wait_next", side_effect=target),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        opened = pool.submit(invoke, "upstream")
        local = pool.submit(invoke, "local")
        if upstream_fails:
            with pytest.raises(RuntimeError, match="模拟上游页面辅助失败"):
                opened.result(timeout=5)
        else:
            assert opened.result(timeout=5) == "upstream"
        assert local.result(timeout=5) == "local"
    assert observed["upstream"] is upstream._find_visible_email_input_js
    assert observed["local"] is None


def test_driver_identity_and_saved_credentials_survive_local_resume_and_checkpoints():
    from tests import test_registration_resume_session as fixtures

    harness = fixtures.ResumeSessionFlowTests()
    with harness.run_context() as (_, mocks):
        result = run_roxy_oss_registration(
            fixtures.EMAIL, "测试用户", "1990-01-02", proxy="http://pool.example:8080",
            existing_password="unit-original-password", existing_totp_secret="unit-original-totp",
            profile_id="unit-profile", email_source="icloud_hide",
            registration_options={"registration_driver": "roxy_oss", "password_enabled": True,
                                  "twofa_enabled": False, "codex_enabled": False, "plan_check_enabled": False},
        )
    assert result["success"] is True, result.get("error")
    assert result["auth"]["auth_method"] == "roxy_oss"
    assert mocks["persist"].call_args.kwargs["extra"]["registration_driver"] == "roxy_oss"
    assert mocks["persist"].call_args.kwargs["extra"]["account_password"] == "unit-original-password"
    for call in mocks["checkpoint"].call_args_list:
        assert call.kwargs["registration_driver"] == "roxy_oss"
        assert call.kwargs["openai_password"] == "unit-original-password"
    mocks["_fill_password_page_if_present"].assert_not_called()
    mocks["wait_for_otp"].assert_not_called()
    mocks["release"].assert_not_called()


def test_failure_keeps_independent_auth_method_and_original_local_cleanup():
    from tests import test_registration_resume_session as fixtures

    harness = fixtures.ResumeSessionFlowTests()
    with harness.run_context(action="register") as (_, mocks):
        result = run_roxy_oss_registration(
            fixtures.EMAIL, "测试用户", "1990-01-02", proxy="http://pool.example:8080",
            registration_options={"password_enabled": True, "twofa_enabled": False,
                                  "codex_enabled": False, "plan_check_enabled": False},
        )
    assert result["success"] is False
    assert result["auth"]["auth_method"] == "roxy_oss"
    mocks["persist"].assert_not_called()
    assert mocks["retain"].called or mocks["release"].called
