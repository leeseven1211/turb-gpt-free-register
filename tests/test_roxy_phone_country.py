import unittest

from core.codex_retry_service import CodexRetryStopped
from core.roxy_codex_oauth import (
    _body_indicates_whatsapp_only,
    _classify_phone_page_failure,
    _is_codex_retry_stopped_exception,
    _select_phone_country_by_calling_code,
)


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


if __name__ == "__main__":
    unittest.main()
