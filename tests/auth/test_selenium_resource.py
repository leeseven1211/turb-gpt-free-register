# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from selenium.common.exceptions import WebDriverException


class SeleniumResourceTests(unittest.TestCase):
    def test_transient_tunnel_error_can_settle_to_visible_target_form_without_another_get(self):
        from core.auth.browser import selenium_resource as resource

        now = [0.0]
        clock = SimpleNamespace(monotonic=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
        driver = SimpleNamespace(
            set_page_load_timeout=Mock(), set_script_timeout=Mock(),
            get=Mock(side_effect=WebDriverException("net::ERR_TUNNEL_CONNECTION_FAILED")),
            execute_script=Mock(side_effect=lambda *_a: {"url": "chrome-error://chromewebdata/", "usable": False}
                                if now[0] < 2 else {"url": "https://chatgpt.com/auth/login", "usable": True}),
        )
        with patch.object(resource, "time", clock), patch.object(resource, "_checkpoint"):
            resource._safe_get(driver, "https://chatgpt.com/auth/login", attempts=1)
        driver.get.assert_called_once()
        self.assertLessEqual(now[0], 10)
        self.assertEqual(driver.set_script_timeout.call_args.args, (8,))

    def test_navigation_error_grace_rejects_foreign_origin_and_never_replays_get(self):
        from core.auth.browser import selenium_resource as resource

        for target in ("https://chatgpt.com.evil.test/auth/login", "chrome-error://chromewebdata/",
                       "https://chatgpt.com:8443/auth/login"):
            now = [0.0]
            clock = SimpleNamespace(monotonic=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
            driver = SimpleNamespace(
                set_page_load_timeout=Mock(), set_script_timeout=Mock(),
                get=Mock(side_effect=WebDriverException("net::ERR_TUNNEL_CONNECTION_FAILED")),
                execute_script=Mock(return_value={"url": target, "usable": True}),
            )
            with self.subTest(target=target), patch.object(resource, "time", clock), patch.object(resource, "_checkpoint"):
                with self.assertRaises(WebDriverException):
                    resource._safe_get(driver, "https://chatgpt.com/auth/login", attempts=1)
            driver.get.assert_called_once()
            self.assertLessEqual(now[0], 10)

    def test_quit_driver_stops_driver_service_when_quit_raises(self):
        from core.auth.browser.selenium_resource import quit_driver

        process = Mock()
        process.poll.return_value = None
        service = SimpleNamespace(process=process, stop=Mock())
        driver = SimpleNamespace(service=service, quit=Mock(side_effect=RuntimeError("session lost")))

        with patch("core.auth.browser.selenium_resource.logger.warning") as warning:
            self.assertFalse(quit_driver(driver))

        service.stop.assert_called_once_with()
        warning.assert_called_once()

    def test_quit_driver_stops_live_driver_service_after_normal_quit(self):
        from core.auth.browser.selenium_resource import quit_driver

        process = Mock()
        process.poll.return_value = None
        service = SimpleNamespace(process=process, stop=Mock())
        driver = SimpleNamespace(service=service, quit=Mock())

        self.assertTrue(quit_driver(driver))

        service.stop.assert_called_once_with()
