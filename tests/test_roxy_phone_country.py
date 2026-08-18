import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.codex_retry_service import CodexRetryStopped
from core.roxy_codex_oauth import (
    _account_login_credentials,
    _body_indicates_whatsapp_only,
    _classify_phone_page_failure,
    _complete_login_challenge_after_email,
    _do_phone_verification_if_present,
    _finish_consent_workspace,
    _is_codex_retry_stopped_exception,
    _is_totp_login_page,
    _phone_error_allows_number_rotation,
    _phone_error_counts_country_failure,
    _phone_channel_selection,
    _prepare_phone_form_for_submit,
    _run_roxy_codex_oauth_once,
    _select_phone_country_by_calling_code,
    _submit_saved_login_password,
    _verify_sms_channel_selected,
    _wait_after_phone_send,
    _wait_for_fresh_email_otp,
)
from core import sms_provider


class _Element:
    def __init__(self, driver, kind):
        self.driver = driver
        self.kind = kind

    def click(self):
        self.driver.clicked.append(self.kind)

    def send_keys(self, *keys):
        self.driver.keys.append((self.kind, keys))


class _SwitchTo:
    def __init__(self, driver):
        self.active_element = _Element(driver, "active")


class _CountryDriver:
    def __init__(self, *, current_code="1"):
        self.current_code = current_code
        self.clicked = []
        self.keys = []
        self.scan_count = 0
        self.switch_to = _SwitchTo(self)
        self.button = _Element(self, "button")
        self.option = _Element(self, "option-cl")

    def execute_script(self, script, *args):
        if "return {hasButton:" in script:
            text = "Chile (+56)" if self.current_code == "56" else "United States (+1)"
            return {"hasButton": True, "text": text, "dialCode": self.current_code, "expanded": "false"}
        if "return form?.querySelector('button[aria-haspopup=" in script:
            return self.button
        if "const candidates =" in script:
            self.scan_count += 1
            if self.scan_count == 1:
                return {"ready": True, "found": False, "before": 0, "after": 240, "max": 9000}
            return {
                "ready": True,
                "found": True,
                "option": self.option,
                "text": "Chile (+56)",
                "code": "56",
                "key": "CL",
            }
        if "const hiddenSelect" in script:
            return {"text": "Chile (+56)", "dialCode": "56", "countryKey": "CL", "expanded": "false"}
        return None


class RoxyPhoneCountryTests(unittest.TestCase):
    def test_saved_login_credentials_are_loaded_without_changing_values(self):
        account = {
            "extra_json": '{"registration_password":"StoredPassword!123"}',
            "totp_secret": "JBSWY3DPEHPK3PXP",
        }
        with patch("core.db.get_account_by_email", return_value=account):
            password, secret = _account_login_credentials("a@example.com")

        self.assertEqual(password, "StoredPassword!123")
        self.assertEqual(secret, "JBSWY3DPEHPK3PXP")

    def test_login_challenge_uses_saved_password_then_totp_without_email_otp(self):
        driver = MagicMock()
        driver.step = "password"
        order = []

        def state(_driver):
            return {"url": f"https://auth.openai.com/{driver.step}", "inputs": [], "errors": []}

        def submit_password(_driver, _email, _password):
            order.append("password")
            driver.step = "totp"

        def submit_totp(_driver, _email, _secret):
            order.append("totp")
            driver.step = "advanced"

        with (
            patch("core.roxy_codex_oauth._login_challenge_state", side_effect=state),
            patch("core.roxy_codex_oauth._is_login_password_page", side_effect=lambda _driver: driver.step == "password"),
            patch("core.roxy_codex_oauth._is_totp_login_page", side_effect=lambda _driver, _state=None: driver.step == "totp"),
            patch("core.roxy_codex_oauth._is_email_verification_page", return_value=False),
            patch("core.roxy_codex_oauth._is_login_advanced", side_effect=lambda _driver, _state=None: driver.step == "advanced"),
            patch("core.roxy_codex_oauth._submit_saved_login_password", side_effect=submit_password),
            patch("core.roxy_codex_oauth._submit_saved_login_totp", side_effect=submit_totp),
            patch("core.roxy_codex_oauth.human_delay"),
        ):
            result = _complete_login_challenge_after_email(
                driver,
                "a@example.com",
                "StoredPassword!123",
                "JBSWY3DPEHPK3PXP",
                timeout=2,
            )

        self.assertEqual(result, "advanced")
        self.assertEqual(order, ["password", "totp"])

    def test_totp_form_wins_over_stale_password_url(self):
        state = {
            "url": "https://auth.openai.com/log-in/password",
            "inputs": [{"type": "text", "name": "totp", "autocomplete": "one-time-code"}],
            "text": "Enter the code from your authenticator app",
        }

        self.assertTrue(_is_totp_login_page(MagicMock(), state))

    def test_saved_password_submits_form_without_clicking_reveal_button(self):
        driver = MagicMock()
        password_input = MagicMock()
        submitter = MagicMock()
        driver.execute_script.side_effect = [
            {"ok": True, "input": password_input, "submitter": submitter},
            True,
        ]

        with patch("core.roxy_codex_oauth._human_type_text") as type_text, patch(
            "core.roxy_codex_oauth._human_click"
        ) as click, patch("core.roxy_codex_oauth.human_delay"):
            _submit_saved_login_password(driver, "a@example.com", "StoredPassword!123")

        type_text.assert_called_once_with(driver, password_input, "StoredPassword!123", clear=True)
        click.assert_not_called()
        password_input.send_keys.assert_not_called()
        self.assertIn("requestSubmit", driver.execute_script.call_args_list[1].args[0])
        self.assertIs(driver.execute_script.call_args_list[1].args[2], submitter)

    def test_login_password_page_without_saved_password_fails_before_phone(self):
        driver = MagicMock()
        with (
            patch(
                "core.roxy_codex_oauth._login_challenge_state",
                return_value={"url": "https://auth.openai.com/log-in/password", "inputs": [], "errors": []},
            ),
            patch("core.roxy_codex_oauth._is_login_password_page", return_value=True),
            patch("core.roxy_codex_oauth._click_passwordless_signup_if_present", return_value={"ok": False}),
        ):
            with self.assertRaisesRegex(RuntimeError, "本地无注册密码"):
                _complete_login_challenge_after_email(driver, "a@example.com", "", "", timeout=1)

    def test_email_otp_provider_receives_codex_wait_budget(self):
        calls = []

        def provider(email, *, after_ts, max_wait=None):
            calls.append((email, after_ts, max_wait))
            return "123456"

        result = _wait_for_fresh_email_otp(
            provider,
            "a@example.com",
            after_ts=100.0,
            timeout=90,
        )

        self.assertEqual(result, "123456")
        self.assertEqual(calls[0][:2], ("a@example.com", 100.0))
        self.assertGreaterEqual(calls[0][2], 89)
        self.assertLessEqual(calls[0][2], 90)

    def test_missing_twofa_establishes_chatgpt_session_before_oauth(self):
        order = []
        driver = MagicMock()
        opened = SimpleNamespace(profile_id="profile-1", raw={})

        def fill(_driver, _email, _otp_provider, url):
            order.append("chatgpt_login" if url == "https://chatgpt.com/auth/login" else "oauth_login")

        def setup(_driver):
            order.append("twofa")
            return True

        with (
            patch("core.codex_oauth._codex_auth_url_source", return_value="cpa"),
            patch(
                "core.codex_oauth._request_cpa_authorize_url",
                return_value={"state": "state-1", "auth_url": "https://auth.openai.com/oauth/authorize?state=state-1"},
            ),
            patch("core.codex_oauth._extract_code", return_value="code-1"),
            patch("core.codex_oauth._submit_cpa_callback", return_value={"message": "ok"}),
            patch("core.codex_oauth._save_cpa_local_record", return_value=None),
            patch("core.roxy_codex_oauth._detect_browser_kind", return_value="roxy"),
            patch("core.roxy_codex_oauth._fill_email_and_otp", side_effect=fill),
            patch(
                "core.roxy_registration._fetch_chatgpt_session",
                side_effect=lambda *_args, **_kwargs: order.append("chatgpt_session") or {"accessToken": "token"},
            ),
            patch(
                "core.roxy_codex_oauth._do_phone_verification_if_present",
                side_effect=lambda _driver: order.append("phone"),
            ),
            patch(
                "core.roxy_codex_oauth._finish_consent_workspace",
                side_effect=lambda _driver, email="": order.append("callback") or "http://localhost/callback?code=code-1&state=state-1",
            ),
            patch("core.roxy_codex_oauth.human_delay"),
        ):
            result = _run_roxy_codex_oauth_once(
                "a@example.com",
                otp_provider=object(),
                force=True,
                existing_driver=driver,
                existing_opened=opened,
                reuse_existing_profile=True,
                clear_existing_state=False,
                before_oauth_setup=setup,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            order,
            ["chatgpt_login", "chatgpt_session", "twofa", "oauth_login", "phone", "callback"],
        )

    def test_selects_virtualized_react_aria_country_with_enter(self):
        driver = _CountryDriver(current_code="1")

        result = _select_phone_country_by_calling_code(driver, "+56977760779", timeout=2)

        self.assertTrue(result["selected"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["dialCode"], "56")
        self.assertEqual(result["countryKey"], "CL")
        self.assertEqual(driver.clicked, ["button"])
        self.assertIn(("option-cl", ("\ue007",)), driver.keys)

    def test_keeps_country_when_calling_code_already_matches(self):
        driver = _CountryDriver(current_code="56")

        result = _select_phone_country_by_calling_code(driver, "+56977760779", timeout=2)

        self.assertTrue(result["selected"])
        self.assertFalse(result["changed"])
        self.assertEqual(result["dialCode"], "56")
        self.assertEqual(driver.clicked, [])

    def test_unselected_whatsapp_text_does_not_fail_sms_submission(self):
        state = {
            "url": "https://auth.openai.com/add-phone",
            "radios": [
                {"value": "sms", "checked": True},
                {"value": "whatsapp", "checked": False},
            ],
            "bodyText": "SMS\nWhatsApp",
        }

        self.assertEqual(_classify_phone_page_failure(state), "")

    def test_checked_whatsapp_radio_is_rejected(self):
        state = {
            "url": "https://auth.openai.com/add-phone",
            "radios": [{"value": "whatsapp", "checked": True}],
            "bodyText": "WhatsApp",
        }

        self.assertEqual(_classify_phone_page_failure(state), "whatsapp_channel")

    def test_checked_whatsapp_with_sms_available_is_a_same_number_reset(self):
        state = {
            "url": "https://auth.openai.com/add-phone",
            "radios": [
                {"value": "sms", "checked": False},
                {"value": "whatsapp", "checked": True},
            ],
            "controls": [],
            "bodyText": "SMS WhatsApp",
        }

        self.assertEqual(_classify_phone_page_failure(state), "sms_channel_reset")

    def test_whatsapp_only_body_without_radio_is_rejected(self):
        state = {
            "url": "https://auth.openai.com/add-phone",
            "radios": [],
            "controls": [],
            "bodyText": "確認のため、WhatsApp を通じてワンタイムコードを送ります。",
        }

        self.assertTrue(_body_indicates_whatsapp_only(state))
        self.assertEqual(_classify_phone_page_failure(state), "whatsapp_channel")

    def test_body_with_both_sms_and_whatsapp_is_not_whatsapp_only(self):
        state = {
            "url": "https://auth.openai.com/add-phone",
            "radios": [],
            "controls": [],
            "bodyText": "Choose SMS or WhatsApp",
        }

        self.assertFalse(_body_indicates_whatsapp_only(state))
        self.assertEqual(_classify_phone_page_failure(state), "")

    def test_codex_retry_stop_exception_is_not_a_regular_phone_error(self):
        self.assertTrue(_is_codex_retry_stopped_exception(CodexRetryStopped("stop")))
        self.assertFalse(_is_codex_retry_stopped_exception(RuntimeError("phone failed")))

    def test_channel_selection_reads_hidden_native_radio(self):
        state = {
            "radios": [
                {"value": "sms", "checked": True, "visible": False},
                {"value": "whatsapp", "checked": False, "visible": False},
            ],
            "controls": [],
        }

        selected = _phone_channel_selection(state)

        self.assertTrue(selected["has_sms"])
        self.assertTrue(selected["selected_sms"])
        self.assertFalse(selected["selected_whatsapp"])

    def test_verify_sms_rejects_react_state_that_remains_whatsapp(self):
        class Driver:
            current_url = "https://auth.openai.com/add-phone"

            def execute_script(self, _script):
                return {
                    "url": self.current_url,
                    "radios": [
                        {"value": "sms", "checked": False},
                        {"value": "whatsapp", "checked": True},
                    ],
                    "controls": [],
                    "inputs": [],
                    "forms": [{"action": "/add-phone"}],
                    "bodyText": "SMS WhatsApp",
                }

        with self.assertRaisesRegex(RuntimeError, "whatsapp_channel"):
            _verify_sms_channel_selected(Driver(), timeout=0.2)

    def test_sms_channel_rerender_refills_the_same_number_before_submit(self):
        phone_fill = {
            "e164": "+542325597108",
            "actualVisible": "2325597108",
            "hiddenValue": "+542325597108",
            "dialCode": "54",
            "selectedText": "Argentina (+54)",
        }
        verified = {"visibleValue": "2325597108", "hiddenValue": "+542325597108"}
        with (
            patch("core.roxy_codex_oauth._ensure_add_phone_input"),
            patch("core.roxy_codex_oauth._set_phone_value", return_value=phone_fill) as fill,
            patch("core.roxy_codex_oauth._blur_active_input_and_wait"),
            patch(
                "core.roxy_codex_oauth._verify_add_phone_value_before_submit",
                side_effect=[verified, RuntimeError("phone cleared"), verified, verified],
            ),
            patch("core.roxy_codex_oauth._select_sms_channel_or_raise"),
            patch("core.roxy_codex_oauth._verify_sms_channel_selected", return_value={"selected_sms": True}),
        ):
            result = _prepare_phone_form_for_submit(object(), "+542325597108", attempts=2)

        self.assertEqual(fill.call_count, 2)
        self.assertTrue(all(call.args[1] == "+542325597108" for call in fill.call_args_list))
        self.assertEqual(result["phone_verify"], verified)

    def test_required_field_transient_does_not_rotate_number(self):
        state = {
            "url": "https://auth.openai.com/add-phone",
            "inputs": [{"ariaInvalid": "true", "value": ""}],
            "forms": [{"action": "/add-phone"}],
            "radios": [],
            "controls": [],
            "bodyText": "電話番号が必要です",
        }
        clock = {"value": 0.0}

        def now():
            clock["value"] += 0.4
            return clock["value"]

        with (
            patch("core.roxy_codex_oauth.time.time", side_effect=now),
            patch("core.roxy_codex_oauth.time.sleep"),
            patch("core.roxy_codex_oauth._phone_page_state", return_value=state),
            patch("core.roxy_codex_oauth._is_add_phone_page", return_value=True),
            patch("core.roxy_codex_oauth._is_phone_code_page", return_value=False),
            patch("core.roxy_codex_oauth._force_submit_add_phone_form", return_value={"ok": True}),
        ):
            outcome = _wait_after_phone_send(object(), timeout=1)

        self.assertEqual(outcome, "submission_uncertain")
        self.assertFalse(_phone_error_allows_number_rotation(RuntimeError("phone_form_unstable")))

    def test_explicit_number_failure_still_allows_immediate_rotation(self):
        error = RuntimeError("invalid_phone: phone number is not valid")

        self.assertTrue(_phone_error_allows_number_rotation(error))
        self.assertTrue(_phone_error_counts_country_failure(error))
        self.assertTrue(_phone_error_allows_number_rotation(sms_provider.SmsCodeTimeout("timeout")))
        self.assertFalse(_phone_error_counts_country_failure(RuntimeError("send_limited: rate limit")))

    def test_whatsapp_channel_never_rotates_or_penalizes_country(self):
        error = RuntimeError("whatsapp_channel: page only supports WhatsApp")

        self.assertFalse(_phone_error_allows_number_rotation(error))
        self.assertFalse(_phone_error_counts_country_failure(error))

    def test_whatsapp_only_page_stops_before_acquiring_number(self):
        http = MagicMock()
        state = {
            "url": "https://auth.openai.com/add-phone",
            "radios": [],
            "controls": [],
            "bodyText": "確認のため、WhatsApp を通じてワンタイムコードを送ります。",
        }
        with (
            patch("core.roxy_codex_oauth._has_strict_add_phone_form", return_value=True),
            patch("core.roxy_codex_oauth._is_phone_code_page", return_value=False),
            patch("core.roxy_codex_oauth._phone_page_state", return_value=state),
            patch.object(sms_provider, "_http", return_value=http),
            patch.object(sms_provider, "acquire_number") as acquire,
        ):
            with self.assertRaisesRegex(RuntimeError, "取号前停止"):
                _do_phone_verification_if_present(object())

        acquire.assert_not_called()
        http.close.assert_called_once()

    def test_whatsapp_error_after_purchase_stops_after_one_number(self):
        http = MagicMock()
        state = {
            "url": "https://auth.openai.com/add-phone",
            "radios": [{"value": "sms", "checked": False}, {"value": "whatsapp", "checked": False}],
            "controls": [],
            "bodyText": "SMS WhatsApp",
        }
        with (
            patch("core.roxy_codex_oauth._has_strict_add_phone_form", return_value=True),
            patch("core.roxy_codex_oauth._is_phone_code_page", return_value=False),
            patch("core.roxy_codex_oauth._phone_page_state", return_value=state),
            patch.object(sms_provider, "_http", return_value=http),
            patch.object(sms_provider, "acquire_number", return_value=("a1", "56954364095")) as acquire,
            patch(
                "core.roxy_codex_oauth._prepare_phone_form_for_submit",
                side_effect=RuntimeError("whatsapp_channel: page rejected SMS"),
            ),
            patch.object(sms_provider, "cancel") as cancel,
            patch.object(sms_provider, "report_activation_failure") as report_failure,
        ):
            with self.assertRaisesRegex(RuntimeError, "不接受 SMS"):
                _do_phone_verification_if_present(object())

        acquire.assert_called_once()
        cancel.assert_called_once_with("a1", http, background=True)
        report_failure.assert_not_called()

    def test_sms_channel_reset_reuses_same_number_once(self):
        http = MagicMock()
        driver = object()
        state = {
            "url": "https://auth.openai.com/add-phone",
            "radios": [{"value": "sms", "checked": False}, {"value": "whatsapp", "checked": False}],
            "controls": [],
            "bodyText": "SMS WhatsApp",
        }
        with (
            patch("core.roxy_codex_oauth._has_strict_add_phone_form", return_value=True),
            patch("core.roxy_codex_oauth._is_phone_code_page", return_value=False),
            patch("core.roxy_codex_oauth._phone_page_state", return_value=state),
            patch.object(sms_provider, "_http", return_value=http),
            patch.object(sms_provider, "acquire_number", return_value=("a1", "56954364095")) as acquire,
            patch("core.roxy_codex_oauth._prepare_phone_form_for_submit", return_value={}) as prepare,
            patch("core.roxy_codex_oauth._click_add_phone_continue_button", return_value={"ok": True}),
            patch(
                "core.roxy_codex_oauth._wait_after_phone_send",
                side_effect=[RuntimeError("sms_channel_reset: React reset"), "code_page"],
            ),
            patch("core.roxy_codex_oauth._force_submit_add_phone_form", return_value={"ok": True}) as force_submit,
            patch("core.roxy_codex_oauth._wait_page_settle_after_submit"),
            patch.object(sms_provider, "set_status"),
            patch.object(sms_provider, "wait_for_sms_code", return_value="123456"),
            patch("core.roxy_codex_oauth._ensure_phone_code_page_after_sms"),
            patch("core.roxy_codex_oauth._type_otp"),
            patch("core.roxy_codex_oauth.human_delay"),
            patch("core.roxy_codex_oauth._click_if_present", return_value=True),
            patch("core.roxy_codex_oauth._wait_after_phone_otp_submit", return_value="left_phone_flow"),
            patch.object(sms_provider, "complete") as complete,
            patch.object(sms_provider, "cancel") as cancel,
        ):
            _do_phone_verification_if_present(driver)

        acquire.assert_called_once()
        self.assertEqual(prepare.call_count, 2)
        self.assertTrue(all(call.args[1] == "+56954364095" for call in prepare.call_args_list))
        force_submit.assert_called_once_with(driver)
        complete.assert_called_once_with("a1", http)
        cancel.assert_not_called()

    def test_callback_loop_handles_late_add_phone_page(self):
        driver = type("Driver", (), {"current_url": "https://auth.openai.com/add-phone"})()
        callback = "http://localhost:1455/auth/callback?code=test&state=test"
        with (
            patch(
                "core.roxy_codex_oauth._extract_callback_url_from_any_window",
                side_effect=["", callback],
            ),
            patch("core.roxy_codex_oauth._has_strict_add_phone_form", return_value=True),
            patch("core.roxy_codex_oauth._is_phone_code_page", return_value=False),
            patch("core.roxy_codex_oauth._do_phone_verification_if_present") as phone_flow,
        ):
            result = _finish_consent_workspace(driver, email="test@example.com")

        self.assertEqual(result, callback)
        phone_flow.assert_called_once_with(driver)

    def test_local_phone_form_error_stops_without_buying_second_number(self):
        http = MagicMock()
        with (
            patch("core.roxy_codex_oauth._has_strict_add_phone_form", return_value=True),
            patch("core.roxy_codex_oauth._is_phone_code_page", return_value=False),
            patch.object(sms_provider, "_http", return_value=http),
            patch.object(sms_provider, "acquire_number", return_value=("a1", "542325597108")) as acquire,
            patch(
                "core.roxy_codex_oauth._prepare_phone_form_for_submit",
                side_effect=RuntimeError("phone_form_unstable: react state lost"),
            ),
            patch.object(sms_provider, "cancel") as cancel,
            patch.object(sms_provider, "report_activation_failure") as report_failure,
        ):
            with self.assertRaisesRegex(RuntimeError, "已停止继续买号"):
                _do_phone_verification_if_present(object())

        acquire.assert_called_once()
        cancel.assert_called_once_with("a1", http, background=True)
        report_failure.assert_not_called()

    def test_sms_received_then_browser_failure_never_buys_second_number(self):
        http = MagicMock()
        with (
            patch("core.roxy_codex_oauth._has_strict_add_phone_form", return_value=True),
            patch("core.roxy_codex_oauth._is_phone_code_page", return_value=False),
            patch.object(sms_provider, "_http", return_value=http),
            patch.object(sms_provider, "acquire_number", return_value=("a1", "542325597108")) as acquire,
            patch("core.roxy_codex_oauth._prepare_phone_form_for_submit", return_value={}),
            patch("core.roxy_codex_oauth._click_add_phone_continue_button", return_value={"ok": True}),
            patch("core.roxy_codex_oauth._wait_after_phone_send", return_value="submission_uncertain"),
            patch.object(sms_provider, "set_status"),
            patch.object(sms_provider, "wait_for_sms_code", return_value="123456"),
            patch(
                "core.roxy_codex_oauth._ensure_phone_code_page_after_sms",
                side_effect=RuntimeError("sms_received_but_phone_code_page_missing"),
            ),
            patch.object(sms_provider, "complete") as complete,
            patch.object(sms_provider, "cancel") as cancel,
            patch.object(sms_provider, "report_activation_failure") as report_failure,
        ):
            with self.assertRaisesRegex(RuntimeError, "已停止继续买号"):
                _do_phone_verification_if_present(object())

        acquire.assert_called_once()
        complete.assert_called_once_with("a1", http)
        cancel.assert_not_called()
        report_failure.assert_not_called()

    def test_explicit_invalid_phone_rotates_and_second_number_can_succeed(self):
        http = MagicMock()
        driver = object()
        with (
            patch("core.roxy_codex_oauth._has_strict_add_phone_form", return_value=True),
            patch("core.roxy_codex_oauth._is_phone_code_page", return_value=False),
            patch.object(sms_provider, "_http", return_value=http),
            patch.object(
                sms_provider,
                "acquire_number",
                side_effect=[("a1", "542325597108"), ("a2", "27644073175")],
            ) as acquire,
            patch(
                "core.roxy_codex_oauth._prepare_phone_form_for_submit",
                side_effect=[RuntimeError("invalid_phone: phone number is not valid"), {}],
            ),
            patch("core.roxy_codex_oauth._find_any", return_value=object()),
            patch("core.roxy_codex_oauth._refresh_add_phone_for_retry"),
            patch("core.roxy_codex_oauth._sleep_before_phone_retry"),
            patch("core.roxy_codex_oauth._click_add_phone_continue_button", return_value={"ok": True}),
            patch("core.roxy_codex_oauth._wait_after_phone_send", return_value="code_page"),
            patch.object(sms_provider, "set_status"),
            patch.object(sms_provider, "wait_for_sms_code", return_value="123456"),
            patch("core.roxy_codex_oauth._ensure_phone_code_page_after_sms"),
            patch("core.roxy_codex_oauth._type_otp"),
            patch("core.roxy_codex_oauth.human_delay"),
            patch("core.roxy_codex_oauth._click_if_present", return_value=True),
            patch("core.roxy_codex_oauth._wait_after_phone_otp_submit", return_value="left_phone_flow"),
            patch.object(sms_provider, "complete") as complete,
            patch.object(sms_provider, "cancel") as cancel,
            patch.object(sms_provider, "report_activation_failure") as report_failure,
        ):
            _do_phone_verification_if_present(driver)

        self.assertEqual(acquire.call_count, 2)
        cancel.assert_called_once_with("a1", http, background=True)
        report_failure.assert_called_once_with("a1", "invalid_phone: phone number is not valid")
        complete.assert_called_once_with("a2", http)


if __name__ == "__main__":
    unittest.main()
