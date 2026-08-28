import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import browser_use_registration
from core import roxy_registration


class _RoxyDriver:
    def __init__(self):
        self.state = "otp"

    @property
    def current_url(self):
        if self.state == "otp":
            return "https://auth.openai.com/email-verification"
        return "https://auth.openai.com/create-account/password"

    def execute_script(self, _script):
        return {"ok": True, "input": object(), "button": object()}


class _RefreshableOtpDriver(_RoxyDriver):
    def __init__(self):
        super().__init__()
        self.refresh_count = 0
        self.scan_count = 0

    def refresh(self):
        self.refresh_count += 1

    def execute_script(self, _script):
        self.scan_count += 1
        if self.refresh_count:
            return {
                "ok": True,
                "reason": "create_account_password_target",
                "target": object(),
            }
        return {
            "ok": False,
            "reason": "missing_create_account_password_target",
            "candidates": [{"text": "Resend email", "href": "", "name": "intent", "value": "resend", "aria": ""}],
        }


class _BrowserUsePage:
    def __init__(self):
        self.state = "email_verification"


class RegistrationFailureClassificationTests(unittest.TestCase):
    def test_pre_account_shell_failures_are_disposable_but_checkpointed_failures_are_not(self):
        disposable_errors = (
            "Roxy registration stage timeout exhausted",
            "email OTP input budget exhausted",
            "page_not_hydrated: blank shell",
        )
        for error in disposable_errors:
            with self.subTest(error=error):
                self.assertTrue(
                    roxy_registration._is_disposable_pre_account_failure(
                        error,
                        create_acknowledged=False,
                        account_id=None,
                    )
                )

        self.assertTrue(
            roxy_registration._is_disposable_pre_account_failure(
                '找不到邮箱输入框/邮箱入口，state={"actions": [], "inputs": [], '
                '"title": "開始する | ChatGPT", "url": "https://chatgpt.com/auth/login"}',
                create_acknowledged=False,
                account_id=None,
            )
        )

        self.assertFalse(
            roxy_registration._is_disposable_pre_account_failure(
                "Roxy registration stage timeout exhausted",
                create_acknowledged=True,
                account_id=None,
            )
        )
        self.assertFalse(
            roxy_registration._is_disposable_pre_account_failure(
                "Roxy registration stage timeout exhausted",
                create_acknowledged=False,
                account_id=501,
            )
        )


class RegistrationPasswordFlowTests(unittest.TestCase):
    def test_roxy_waits_for_delayed_create_password_target(self):
        driver = _RoxyDriver()
        target = object()
        calls = 0

        def delayed_target(_script):
            nonlocal calls
            calls += 1
            if calls < 3:
                return {"ok": False, "reason": "missing_create_account_password_target"}
            return {"ok": True, "reason": "create_account_password_target", "target": target}

        def click_target(_driver, element, label=""):
            self.assertIs(element, target)
            self.assertEqual(label, "signup_use_password")
            driver.state = "password"

        driver.execute_script = delayed_target
        with (
            patch.object(roxy_registration, "_human_click", side_effect=click_target),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration.time, "sleep"),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=2)

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "entered_create_account_password")
        self.assertEqual(calls, 3)

    def test_roxy_password_target_supports_japanese_text_only_link(self):
        driver = _RoxyDriver()
        target = object()

        def text_only_target(script):
            self.assertIn("パスワードで続行", script)
            self.assertIn("conflictingLoginPath", script)
            return {
                "ok": True,
                "reason": "create_account_password_target",
                "target": target,
                "href": "",
                "text": "パスワードで続行",
            }

        def click_target(_driver, element, label=""):
            self.assertIs(element, target)
            self.assertEqual(label, "signup_use_password")
            driver.state = "password"

        driver.execute_script = text_only_target
        with (
            patch.object(roxy_registration, "_human_click", side_effect=click_target),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=1)

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "entered_create_account_password")

    def test_roxy_missing_password_target_preserves_candidate_diagnostics(self):
        driver = _RoxyDriver()
        candidate = {
            "tag": "A",
            "text": "Resend email",
            "href": "",
            "name": "",
            "value": "",
            "aria": "",
        }
        driver.execute_script = lambda _script: {
            "ok": False,
            "reason": "missing_create_account_password_target",
            "candidates": [candidate],
        }
        with (
            patch.object(roxy_registration, "_is_signup_password_page", return_value=False),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration.time, "sleep"),
            patch.object(roxy_registration.time, "time", side_effect=[0, 0, 2]),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "missing_create_account_password_target_after_wait")
        self.assertEqual(result["candidates"], [candidate])

    def test_roxy_password_target_refreshes_once_before_classifying_otp_only_flow(self):
        driver = _RefreshableOtpDriver()
        target = object()
        driver.execute_script = lambda _script: (
            {"ok": True, "reason": "create_account_password_target", "target": target}
            if driver.refresh_count
            else {"ok": False, "reason": "missing_create_account_password_target", "candidates": [
                {"text": "Resend email", "href": "", "name": "intent", "value": "resend", "aria": ""}
            ]}
        )

        def click_target(_driver, element, label=""):
            self.assertIs(element, target)
            self.assertEqual(label, "signup_use_password")
            driver.state = "password"

        with (
            patch.object(roxy_registration, "_human_click", side_effect=click_target),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=Mock(side_effect=[0, 0, 10] + [0] * 30), sleep=Mock()),
            ),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=2)

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "entered_create_account_password")
        self.assertEqual(driver.refresh_count, 1)

    def test_roxy_password_submit_does_not_advance_while_password_page_is_stuck(self):
        driver = _RoxyDriver()
        password = "ValidPass123!"
        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", return_value=False),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(roxy_registration, "_is_signup_password_page", return_value=True),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_password_transition_timeout_seconds", return_value=20),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_human_click"),
            patch.object(roxy_registration, "human_delay"),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=Mock(side_effect=[0, 0, 0, 31]), sleep=Mock()),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "仍停留在密码页"):
                roxy_registration._fill_password_page_if_present(driver, "new@example.com", timeout=2)

    def test_roxy_password_submit_uses_independent_transition_budget(self):
        driver = _RoxyDriver()
        driver.state = "password"
        password = "ValidPass123!"
        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", side_effect=[False, True]),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(roxy_registration, "_is_signup_password_page", return_value=True),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_password_transition_timeout_seconds", return_value=60),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_human_click"),
            patch.object(roxy_registration, "_check_manual_stop"),
            patch.object(roxy_registration, "human_delay"),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=Mock(side_effect=[0, 0, 0, 30]), sleep=Mock()),
            ),
        ):
            result = roxy_registration._fill_password_page_if_present(
                driver,
                "new@example.com",
                timeout=2,
            )

        self.assertEqual(result, password)

    def test_roxy_password_is_checkpointed_immediately_after_submit_click(self):
        driver = _RoxyDriver()
        driver.state = "password"
        password = "ValidPass123!"
        order = []

        def submit_password(_driver, _element, label=""):
            self.assertEqual(label, "password_submit")
            order.append("click")
            driver.state = "otp"

        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", side_effect=lambda _driver: driver.state == "otp"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_human_click", side_effect=submit_password),
            patch.object(roxy_registration, "human_delay"),
        ):
            result = roxy_registration._fill_password_page_if_present(
                driver,
                "new@example.com",
                timeout=2,
                on_password_submitted=lambda value: order.append(("checkpoint", value)),
            )

        self.assertEqual(result, password)
        self.assertEqual(order, ["click", ("checkpoint", password)])

    def test_roxy_password_mode_switches_from_otp_before_filling_password(self):
        driver = _RoxyDriver()
        password = "ValidPass123!"

        def switch_to_password(_driver, timeout=15):
            driver.state = "password"
            return {"ok": True, "reason": "entered_create_account_password"}

        def submit_password(_driver, _element, label=""):
            if label == "password_submit":
                driver.state = "otp"

        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", side_effect=lambda _driver: driver.state == "otp"),
            patch.object(roxy_registration, "_click_signup_password_from_otp_if_present", side_effect=switch_to_password) as switch,
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_human_click", side_effect=submit_password),
            patch.object(roxy_registration, "human_delay"),
        ):
            result = roxy_registration._fill_password_page_if_present(driver, "new@example.com", timeout=2)

        self.assertEqual(result, password)
        switch.assert_called_once()

    def test_roxy_otp_mode_keeps_passwordless_registration(self):
        driver = _RoxyDriver()
        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="otp"),
            patch.object(roxy_registration, "_is_email_verification_page", return_value=True),
            patch.object(roxy_registration, "_click_signup_password_from_otp_if_present") as switch,
        ):
            result = roxy_registration._fill_password_page_if_present(driver, "new@example.com", timeout=1)

        self.assertIsNone(result)
        switch.assert_not_called()

    def test_browser_use_password_mode_switches_from_otp_before_filling_password(self):
        page = _BrowserUsePage()
        password = "ValidPass123!"

        def state(_page):
            return {"state": page.state, "url": "https://auth.openai.com/" + page.state}

        def switch_to_password(_page, timeout=15):
            page.state = "password"
            return True

        def click_submit(_page, _selectors, timeout_ms=1500):
            page.state = "email_verification"
            return True

        with (
            patch.object(browser_use_registration, "_registration_auth_mode", return_value="password"),
            patch.object(browser_use_registration, "_browser_use_heartbeat", return_value=page),
            patch.object(browser_use_registration, "_quick_auth_state", side_effect=state),
            patch.object(browser_use_registration, "_click_signup_password_from_otp_if_present", side_effect=switch_to_password) as switch,
            patch.object(browser_use_registration, "_registration_password", return_value=password),
            patch.object(browser_use_registration, "_fill_first", return_value=True),
            patch.object(browser_use_registration, "_click_first", side_effect=click_submit),
            patch.object(browser_use_registration, "_bu_delay"),
        ):
            result = browser_use_registration._fill_password_if_present(
                page,
                "new@example.com",
                timeout=2,
                context=None,
            )

        self.assertEqual(result, password)
        switch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
