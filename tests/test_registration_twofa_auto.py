# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from core.registration_service import registration_config_snapshot


class RegistrationTwofaAutoTests(unittest.TestCase):
    def test_registration_snapshot_uses_normalized_twofa_mode(self):
        with patch("config.twofa.get_twofa_mode", return_value="auto"):
            snapshot = registration_config_snapshot()

        self.assertEqual("auto", snapshot["twofa_driver"])


if __name__ == "__main__":
    unittest.main()
