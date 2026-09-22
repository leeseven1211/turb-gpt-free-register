# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import roxybrowser as roxy_config
from core import roxybrowser_client


class RoxyCreateIntervalTests(unittest.TestCase):
    def test_create_slots_are_separated_by_configured_interval(self):
        with patch.object(roxybrowser_client, "_NEXT_CREATE_SLOT", 0.0), patch.object(
            roxy_config, "ROXY_CREATE_INTERVAL", 1.5
        ), patch.object(
            roxybrowser_client.time, "monotonic", side_effect=[100.0, 100.1]
        ), patch.object(roxybrowser_client.time, "sleep") as wait:
            roxybrowser_client._wait_for_create_slot()
            roxybrowser_client._wait_for_create_slot()

        wait.assert_called_once()
        self.assertAlmostEqual(1.4, wait.call_args.args[0], places=6)

    def test_zero_interval_disables_create_slot_wait(self):
        with patch.object(roxybrowser_client, "_NEXT_CREATE_SLOT", 0.0), patch.object(
            roxy_config, "ROXY_CREATE_INTERVAL", 0
        ), patch.object(roxybrowser_client.time, "sleep") as wait:
            roxybrowser_client._wait_for_create_slot()

        wait.assert_not_called()


if __name__ == "__main__":
    unittest.main()
