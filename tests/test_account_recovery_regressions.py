import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from core import roxy_codex_oauth, roxy_registration
from core.operations import legacy_task_store
from core.storage import operation


class AccountTaskTimestampRegressionTests(unittest.TestCase):
    def test_new_legacy_task_timestamp_has_explicit_timezone(self):
        value = datetime.fromisoformat(legacy_task_store._now())
        self.assertIsNotNone(value.tzinfo)

    def test_naive_legacy_timestamp_keeps_local_wall_clock(self):
        source = datetime(2026, 8, 28, 8, 12, 44)
        normalized = operation._legacy_account_timestamp(source.isoformat())
        self.assertEqual(normalized.tzinfo, timezone.utc)
        self.assertEqual(normalized.astimezone().replace(tzinfo=None), source)

    def test_aware_legacy_timestamp_is_not_shifted_twice(self):
        normalized = operation._legacy_account_timestamp("2026-08-28T00:12:44+00:00")
        self.assertEqual(normalized, datetime(2026, 8, 28, 0, 12, 44, tzinfo=timezone.utc))


class CodexOtpRegressionTests(unittest.TestCase):
    def test_loading_alert_after_otp_is_not_treated_as_invalid_code(self):
        driver = Mock(current_url="https://auth.openai.com/email-verification")
        clock = [0.0]
        states = [
            {
                "url": "https://auth.openai.com/email-verification",
                "inputs": [{"ariaInvalid": "false"}],
                "errors": ["思考"],
                "text": "思考",
            },
            {
                "url": "https://auth.openai.com/about-you",
                "inputs": [],
                "errors": [],
                "text": "",
            },
        ]
        with (
            patch.object(roxy_codex_oauth.time, "time", side_effect=lambda: clock[0]),
            patch.object(roxy_codex_oauth.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)),
            patch.object(roxy_codex_oauth, "_read_email_otp_validate_dead_code", return_value=""),
            patch.object(roxy_codex_oauth, "_is_callback_url", return_value=False),
            patch.object(roxy_codex_oauth, "_has_strict_add_phone_form", return_value=False),
            patch.object(roxy_codex_oauth, "_is_phone_code_page", return_value=False),
            patch.object(roxy_codex_oauth, "_email_otp_page_state", side_effect=states),
            patch.object(roxy_codex_oauth, "check_cancelled"),
        ):
            self.assertEqual(roxy_codex_oauth._wait_after_email_otp_submit(driver, timeout=2), "accepted")


class ProfilePageRegressionTests(unittest.TestCase):
    def test_text_input_falls_back_when_send_keys_did_not_change_value(self):
        field = Mock(tag_name="input")
        field.get_attribute.side_effect = ["", "Haruto Sato"]
        with (
            patch.object(roxy_registration, "_find_any", return_value=field),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_set_element_value") as fallback,
        ):
            self.assertTrue(roxy_registration._select_or_type(object(), ["input[name=name]"], "Haruto Sato"))
        fallback.assert_called_once_with(unittest.mock.ANY, field, "Haruto Sato")

    def test_profile_fills_age_before_name_and_waits_for_navigation(self):
        driver = Mock()
        order = []
        profile = {"url": "https://auth.openai.com/about-you", "inputs": [{"name": "name"}, {"name": "age"}]}
        completed = {"url": "https://chatgpt.com/", "inputs": []}

        def fill_birth(_driver, _birthday, _age):
            order.append("birth")
            return "age"

        def fill_name(_driver, _selectors, _value, timeout=3):
            order.append("name")
            return True

        driver.execute_script.return_value = {"valid": True, "fields": []}
        with (
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_page_snapshot", side_effect=[profile, completed]),
            patch.object(roxy_registration, "_fill_birthday_or_age", side_effect=fill_birth),
            patch.object(roxy_registration, "_select_or_type", side_effect=fill_name),
            patch.object(roxy_registration, "_accept_profile_consents"),
            patch.object(roxy_registration, "_click_if_enabled_submit", return_value=True),
            patch.object(roxy_registration, "human_delay"),
            patch.object(roxy_registration.time, "sleep"),
        ):
            self.assertTrue(
                roxy_registration._complete_profile_page(
                    driver, "Haruto Sato", "2000-01-02", timeout=5
                )
            )

        self.assertEqual(order, ["birth", "name"])


if __name__ == "__main__":
    unittest.main()
