# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from core.registration import checkpoints


class RegistrationCheckpointTests(unittest.TestCase):
    def test_new_account_saves_pending_password_without_profile_assumption(self):
        with (
            patch.object(checkpoints.db, "get_account_by_email", return_value=None),
            patch.object(checkpoints.db, "insert_account", return_value=17) as insert,
        ):
            account_id = checkpoints.save_email_verification_checkpoint(
                email="new@example.com",
                password="Password!123",
                proxy="http://proxy.example",
                email_source="generic_api",
            )

        self.assertEqual(account_id, 17)
        self.assertEqual(insert.call_args.kwargs["access_token"], "")
        self.assertEqual(insert.call_args.kwargs["extra"], {
            "account_password": "Password!123",
            "registration_checkpoint": "email_verification_pending",
            "registration_pending_reason": "email_otp_pending",
        })

    def test_pending_account_updates_checkpoint_without_replacing_account_row(self):
        existing = {"id": 23, "access_token": ""}
        with (
            patch.object(checkpoints.db, "get_account_by_email", return_value=existing),
            patch.object(checkpoints.db, "update_account_email_verification_checkpoint", return_value=True) as update,
            patch.object(checkpoints.db, "insert_account") as insert,
        ):
            account_id = checkpoints.save_email_verification_checkpoint(
                email="pending@example.com",
                password="Password!123",
                proxy="http://proxy.example",
                email_source="icloud_hide",
                profile_metadata={"profile_id": "profile-1", "retained": True},
            )

        self.assertEqual(account_id, 23)
        update.assert_called_once_with(
            "pending@example.com",
            "Password!123",
            profile_metadata={"profile_id": "profile-1", "retained": True},
        )
        insert.assert_not_called()

    def test_completed_account_rejects_pending_checkpoint_overwrite(self):
        existing = {"id": 29, "access_token": "existing-token"}
        with (
            patch.object(checkpoints.db, "get_account_by_email", return_value=existing),
            patch.object(checkpoints.db, "update_account_email_verification_checkpoint") as update,
            patch.object(checkpoints.db, "insert_account") as insert,
        ):
            with self.assertRaisesRegex(checkpoints.RegistrationCheckpointConflict, "已有 access token"):
                checkpoints.save_email_verification_checkpoint(
                    email="completed@example.com",
                    password="Password!123",
                    proxy="http://proxy.example",
                )

        update.assert_not_called()
        insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
