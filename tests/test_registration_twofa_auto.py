# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import twofa as twofa_config
from core.registration_service import registration_config_snapshot


class RegistrationTwofaAutoTests(unittest.TestCase):
    def test_registration_snapshot_uses_normalized_twofa_mode(self):
        with patch.object(twofa_config, "TWOFA_DRIVER", "protocol_direct"), patch.object(
            twofa_config, "get_twofa_mode", wraps=twofa_config.get_twofa_mode
        ) as get_mode:
            snapshot = registration_config_snapshot()

        self.assertEqual("auto", snapshot["twofa_driver"])
        get_mode.assert_called_once_with()

    def test_registration_snapshot_mode_overrides_runtime_twofa_config(self):
        with patch.object(twofa_config, "TWOFA_DRIVER", "protocol"):
            self.assertEqual(
                "browser",
                twofa_config.get_twofa_driver_for_options({"twofa_driver": "browser"}),
            )


if __name__ == "__main__":
    unittest.main()
