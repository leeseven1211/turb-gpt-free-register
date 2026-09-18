# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class SeleniumResourceTests(unittest.TestCase):
    def test_quit_driver_stops_driver_service_when_quit_raises(self):
        from core.registration.selenium_resource import quit_driver

        process = Mock()
        process.poll.return_value = None
        service = SimpleNamespace(process=process, stop=Mock())
        driver = SimpleNamespace(service=service, quit=Mock(side_effect=RuntimeError("session lost")))

        with patch("core.registration.selenium_resource.logger.warning") as warning:
            self.assertFalse(quit_driver(driver))

        service.stop.assert_called_once_with()
        warning.assert_called_once()

    def test_quit_driver_stops_live_driver_service_after_normal_quit(self):
        from core.registration.selenium_resource import quit_driver

        process = Mock()
        process.poll.return_value = None
        service = SimpleNamespace(process=process, stop=Mock())
        driver = SimpleNamespace(service=service, quit=Mock())

        self.assertTrue(quit_driver(driver))

        service.stop.assert_called_once_with()
