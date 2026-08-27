import unittest
from pathlib import Path
from unittest.mock import patch

from core.registration import dispatcher


class RegistrationDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.args = {
            "email": "test@example.com",
            "name": "Test User",
            "birthday": "1990-01-01",
            "proxy": "http://proxy.example:8080",
            "otp_code": "123456",
            "batch_dir": Path("batch"),
        }

    def test_protocol_driver_forwards_common_contract(self):
        expected = {"success": True, "email": self.args["email"]}
        with (
            patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "protocol"),
            patch(
                "core.registration.protocol.run_protocol_registration",
                return_value=expected,
            ) as run_protocol,
        ):
            result = dispatcher.run_registration(**self.args)

        self.assertIs(expected, result)
        run_protocol.assert_called_once_with(**self.args)

    def test_main_keeps_compatibility_facade(self):
        import main

        expected = {"success": True}
        with patch.object(main, "_run_registration", return_value=expected) as run_registration:
            result = main.run_registration(**self.args)

        self.assertIs(expected, result)
        run_registration.assert_called_once_with(
            **self.args,
            existing_password=None,
            existing_totp_secret=None,
        )

    def test_protocol_aliases_are_supported(self):
        for driver in ("api", "http"):
            with self.subTest(driver=driver), patch.object(
                dispatcher._roxy_cfg, "REGISTRATION_DRIVER", driver
            ), patch(
                "core.registration.protocol.run_protocol_registration",
                return_value={"success": True},
            ) as run_protocol:
                dispatcher.run_registration(**self.args)

            run_protocol.assert_called_once_with(**self.args)

    def test_roxy_driver_forwards_resume_arguments(self):
        expected = {"success": True}
        with (
            patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "roxybrowser"),
            patch.object(dispatcher, "generate_random_birthday", return_value="1990-01-01"),
            patch("core.registration.roxy.run_roxy_registration", return_value=expected) as run_roxy,
        ):
            result = dispatcher.run_registration(
                **{
                    **self.args,
                    "birthday": None,
                    "existing_password": "saved-password",
                    "existing_totp_secret": "saved-totp",
                }
            )

        self.assertIs(expected, result)
        run_roxy.assert_called_once_with(
            email=self.args["email"],
            name=self.args["name"],
            birthday="1990-01-01",
            proxy=self.args["proxy"],
            otp_code=self.args["otp_code"],
            batch_dir=self.args["batch_dir"],
            existing_password="saved-password",
            existing_totp_secret="saved-totp",
        )

    def test_removed_browser_drivers_are_rejected(self):
        for driver in ("cloak", "browser_use", "skyvern"):
            with self.subTest(driver=driver), patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", driver):
                with self.assertRaisesRegex(RuntimeError, "仅支持 protocol / roxy"):
                    dispatcher.run_registration(**self.args)

    def test_non_roxy_resume_is_rejected_before_driver_import(self):
        with patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "cloak"):
            with self.assertRaisesRegex(RuntimeError, "仅支持 Roxy"):
                dispatcher.run_registration(**self.args, existing_password="saved-password")

    def test_unknown_driver_fails_with_available_driver_names(self):
        with patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "unknown"):
            with self.assertRaisesRegex(RuntimeError, "仅支持 protocol / roxy"):
                dispatcher.run_registration(**self.args)


if __name__ == "__main__":
    unittest.main()
