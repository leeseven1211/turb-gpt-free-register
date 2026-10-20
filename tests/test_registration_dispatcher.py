import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.registration import dispatcher


class RegistrationDispatcherTests(unittest.TestCase):
    def setUp(self):
        # 此类只验证分发契约；独立入口的持久生命周期由专门 PG 测试覆盖。
        context = patch("core.registration_service.registration_fact_context", return_value={
            "attempt_id": 1, "run_id": 2, "execution_id": "dispatcher-fixture", "job_id": 3,
        })
        context.start()
        self.addCleanup(context.stop)
        self.args = {
            "email": "test@example.com",
            "name": "Test User",
            "birthday": "1990-01-01",
            "proxy": "http://proxy.example:8080",
            "otp_code": "123456",
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

    def test_open_source_protocol_driver_uses_own_flow_and_attempt_name(self):
        expected = {"success": True, "email": self.args["email"]}
        snapshot = {"registration_driver": "protocol_oss"}
        kwargs = {**self.args, "profile_id": None, "registration_options": snapshot}
        with (
            patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "protocol"),
            patch(
                "core.registration.protocol_oss.run_protocol_oss_registration",
                return_value=expected,
                create=True,
            ) as run_protocol_oss,
            patch("core.registration.protocol.run_protocol_registration") as run_protocol,
            patch(
                "core.registration.standalone.run_registration_in_context",
                return_value=expected,
            ) as run_in_context,
        ):
            result = dispatcher.run_registration(
                **self.args,
                registration_options=snapshot,
            )

        self.assertIs(expected, result)
        run_in_context.assert_called_once_with(
            run_protocol_oss,
            kwargs,
            entrypoint="protocol_cli",
            driver_name="protocol_oss",
        )
        run_protocol.assert_not_called()

    def test_open_source_roxy_driver_preserves_resume_contract_and_independent_attempt(self):
        expected = {"success": True, "email": self.args["email"]}
        snapshot = {"registration_driver": "roxy_oss", "password_enabled": True}
        kwargs = {
            **self.args,
            "existing_password": "unit-original-password",
            "existing_totp_secret": "unit-original-totp",
            "profile_id": "unit-original-profile",
            "registration_options": snapshot,
            "email_source": "icloud_hide",
        }
        with (
            patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "protocol"),
            patch("core.registration.roxy_oss.run_roxy_oss_registration", return_value=expected) as run_oss,
            patch("core.registration.roxy.run_roxy_registration") as run_roxy,
            patch("core.registration.standalone.run_registration_in_context", return_value=expected) as run_in_context,
        ):
            result = dispatcher.run_registration(**kwargs)

        self.assertIs(expected, result)
        run_in_context.assert_called_once_with(
            run_oss, kwargs, entrypoint="roxy_cli", driver_name="roxy_oss",
        )
        run_roxy.assert_not_called()

    def test_protocol_driver_forwards_selected_email_source(self):
        expected = {"success": True, "email": self.args["email"]}
        with (
            patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "protocol"),
            patch(
                "core.registration.protocol.run_protocol_registration",
                return_value=expected,
            ) as run_protocol,
        ):
            result = dispatcher.run_registration(**self.args, email_source="icloud_hide")

        self.assertIs(expected, result)
        run_protocol.assert_called_once_with(**self.args, email_source="icloud_hide")

    def test_snapshot_protocol_driver_overrides_later_live_roxy_config(self):
        expected = {"success": True, "email": self.args["email"]}
        snapshot = {"registration_driver": "protocol"}
        with (
            patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "roxy"),
            patch(
                "core.registration.protocol.run_protocol_registration",
                return_value=expected,
            ) as run_protocol,
            patch("core.registration.roxy.run_roxy_registration") as run_roxy,
        ):
            result = dispatcher.run_registration(
                **self.args,
                registration_options=snapshot,
            )

        self.assertIs(expected, result)
        run_protocol.assert_called_once_with(**self.args, registration_options=snapshot)
        run_roxy.assert_not_called()

    def test_protocol_driver_forwards_saved_password_for_resume(self):
        expected = {"success": True, "email": self.args["email"]}
        with (
            patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "protocol"),
            patch(
                "core.registration.protocol.run_protocol_registration",
                return_value=expected,
            ) as run_protocol,
        ):
            result = dispatcher.run_registration(
                **self.args,
                existing_password="saved-password",
                existing_totp_secret="saved-totp",
            )

        self.assertIs(expected, result)
        run_protocol.assert_called_once_with(
            **self.args,
            existing_password="saved-password",
            existing_totp_secret="saved-totp",
        )

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

    def test_main_forwards_selected_email_source(self):
        import main

        expected = {"success": True}
        with patch.object(main, "_run_registration", return_value=expected) as run_registration:
            result = main.run_registration(**self.args, email_source="icloud_hide")

        self.assertIs(expected, result)
        run_registration.assert_called_once_with(
            **self.args,
            existing_password=None,
            existing_totp_secret=None,
            email_source="icloud_hide",
        )

    def test_cli_batch_does_not_create_file_archive(self):
        import main
        from core import account_export

        with TemporaryDirectory() as temporary_dir:
            archive_dir = Path(temporary_dir) / "accounts"
            with (
                patch.object(account_export, "_ACCOUNTS_DIR", archive_dir, create=True),
                patch("core.postgres_store.require_ready"),
                patch.object(main, "run_serial_batch", return_value=[{"success": True}]),
                patch("sys.argv", ["main.py", "--count", "1"]),
            ):
                with self.assertRaisesRegex(SystemExit, "0"):
                    main.main()

            self.assertFalse(archive_dir.exists())

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
                    "email_source": "icloud_hide",
                }
            )

        self.assertIs(expected, result)
        run_roxy.assert_called_once_with(
            email=self.args["email"],
            name=self.args["name"],
            birthday="1990-01-01",
            proxy=self.args["proxy"],
            otp_code=self.args["otp_code"],
            existing_password="saved-password",
            existing_totp_secret="saved-totp",
            profile_id=None,
            email_source="icloud_hide",
        )

    def test_removed_browser_drivers_are_rejected(self):
        for driver in ("cloak", "browser_use", "skyvern"):
            with self.subTest(driver=driver), patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", driver):
                with self.assertRaisesRegex(RuntimeError, "仅支持 protocol / protocol_oss / protocol_oss_2 / roxy"):
                    dispatcher.run_registration(**self.args)

    def test_non_roxy_resume_is_rejected_before_driver_import(self):
        with patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "cloak"):
            with self.assertRaisesRegex(RuntimeError, "仅支持 Roxy"):
                dispatcher.run_registration(**self.args, existing_password="saved-password")

    def test_unknown_driver_fails_with_available_driver_names(self):
        with patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "unknown"):
            with self.assertRaisesRegex(RuntimeError, "仅支持 protocol / protocol_oss / protocol_oss_2 / roxy"):
                dispatcher.run_registration(**self.args)


if __name__ == "__main__":
    unittest.main()
