# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import browser


class BrowserLocaleProfileTests(unittest.TestCase):
    def test_vietnam_exit_uses_vietnamese_language_and_timezone(self):
        with patch.object(browser, "AUTO_BROWSER_LOCALE_FROM_IP", True):
            profile = browser.build_browser_environment(
                {"country": "VN", "timezone": "Asia/Ho_Chi_Minh"},
                base_profile=browser.HAR_CAPTURE_BASE_PROFILE,
            )

        self.assertEqual("vn", profile["locale_profile"])
        self.assertEqual("vi-VN", profile["navigator_language"])
        self.assertEqual(["vi-VN"], profile["navigator_languages"])
        self.assertEqual("vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7", profile["accept_language"])
        self.assertEqual("Asia/Ho_Chi_Minh", profile["timezone_iana"])
        self.assertEqual(7 * 60, profile["timezone_offset_minutes"])


if __name__ == "__main__":
    unittest.main()
