# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from core import cloakbrowser_driver
from core import roxy_registration


class CloakLocaleTests(unittest.TestCase):
    @patch.object(cloakbrowser_driver._cfg, "CLOAK_TIMEZONE", "")
    @patch.object(cloakbrowser_driver._cfg, "CLOAK_LOCALE", "")
    @patch.object(cloakbrowser_driver._cfg, "CLOAK_GEOIP", True)
    def test_unknown_country_uses_generic_english_instead_of_japanese(self):
        geo = {"country": "NZ", "timezone": "Pacific/Auckland"}
        with patch.object(cloakbrowser_driver, "_detect_cloak_exit_geo", return_value=geo):
            options = cloakbrowser_driver._build_cloak_locale_options("http://proxy.test:8080")
        self.assertEqual(options["timezone"], "Pacific/Auckland")
        self.assertEqual(options["locale"], "en-US")
        self.assertEqual(options["accept_language"], "en-US,en;q=0.9")

    @patch.object(cloakbrowser_driver._cfg, "CLOAK_TIMEZONE", "")
    @patch.object(cloakbrowser_driver._cfg, "CLOAK_LOCALE", "")
    @patch.object(cloakbrowser_driver._cfg, "CLOAK_GEOIP", True)
    def test_known_country_uses_matching_locale(self):
        geo = {"country": "US", "timezone": "America/New_York"}
        with patch.object(cloakbrowser_driver, "_detect_cloak_exit_geo", return_value=geo):
            options = cloakbrowser_driver._build_cloak_locale_options("http://proxy.test:8080")
        self.assertEqual(options["locale"], "en-US")
        self.assertEqual(options["timezone"], "America/New_York")
        self.assertIn("en-US", options["accept_language"])


class _FakeKeyboard:
    def __init__(self):
        self.pressed = []

    def press(self, key):
        self.pressed.append(key)

    def type(self, text, delay=0):
        raise AssertionError("不应回退到 page.keyboard.type")


class _FakePage:
    def __init__(self):
        self.keyboard = _FakeKeyboard()


class _FakeLocator:
    def __init__(self):
        self.typed = []

    def click(self, timeout=0):
        return None

    def press_sequentially(self, text, delay=0, timeout=0):
        self.typed.append(text)


class CloakSendKeysTests(unittest.TestCase):
    def test_regular_text_is_appended_instead_of_filled(self):
        page = _FakePage()
        locator = _FakeLocator()
        element = cloakbrowser_driver.CloakElement(page, locator=locator)
        element.send_keys("ab")
        element.send_keys("c")
        self.assertEqual(locator.typed, ["ab", "c"])

    def test_selenium_backspace_maps_to_playwright_key(self):
        page = _FakePage()
        element = cloakbrowser_driver.CloakElement(page, locator=_FakeLocator())
        element.send_keys("\ue003")
        self.assertEqual(page.keyboard.pressed, ["Backspace"])

    def test_text_property_uses_locator_inner_text(self):
        class Locator:
            def inner_text(self, **kwargs):
                return "  Resend email  "

        element = cloakbrowser_driver.CloakElement(page=object(), locator=Locator())
        self.assertEqual(element.text, "Resend email")


class _FakeJsHandle:
    def __init__(self, kind, value=None, properties=None):
        self.kind = kind
        self.value = value
        self.properties = properties or {}
        self.disposed = False

    def as_element(self):
        return self if self.kind == "element" else None

    def evaluate(self, expression):
        if "Object.keys" in expression:
            return list(self.properties)
        return self.kind

    def get_properties(self):
        return self.properties

    def json_value(self):
        return self.value

    def dispose(self):
        self.disposed = True


class CloakJsResultTests(unittest.TestCase):
    def test_nested_dom_handle_is_preserved_as_cloak_element(self):
        button = _FakeJsHandle("element")
        label = _FakeJsHandle("string", "Continue")
        row = _FakeJsHandle("object", properties={"button": button, "label": label})
        root = _FakeJsHandle("array", properties={"0": row})
        page = object()

        result = cloakbrowser_driver.CloakSeleniumDriver._unwrap_js_result(page, root)

        self.assertEqual(result[0]["label"], "Continue")
        self.assertIsInstance(result[0]["button"], cloakbrowser_driver.CloakElement)
        self.assertIs(result[0]["button"].handle, button)
        self.assertTrue(root.disposed)
        self.assertTrue(row.disposed)
        self.assertTrue(label.disposed)
        self.assertFalse(button.disposed)


class CloakRegistrationTypingTests(unittest.TestCase):
    def test_cloak_human_type_uses_one_complete_send_keys_call(self):
        class Element:
            def __init__(self):
                self.cleared = 0
                self.sent = []

            def clear(self):
                self.cleared += 1

            def send_keys(self, value):
                self.sent.append(value)

        class Driver:
            _registration_log_prefix = "[Cloak注册]"

            def execute_script(self, *args):
                return None

        el = Element()
        with (
            patch.object(roxy_registration, "_human_scroll_to"),
            patch.object(roxy_registration, "_human_click"),
            patch.object(roxy_registration.time, "sleep"),
        ):
            roxy_registration._human_type_text(Driver(), el, "full@example.test", clear=True)

        self.assertEqual(el.cleared, 1)
        self.assertEqual(el.sent, ["full@example.test"])


if __name__ == "__main__":
    unittest.main()
