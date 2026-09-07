# -*- coding: utf-8 -*-
import unittest

from core.account_completion_service import completion_plan


class AccountCompletionPlanTests(unittest.TestCase):
    def test_only_missing_enabled_steps_are_planned(self):
        plan = completion_plan(
            {
                "access_token": "at",
                "token_expired": False,
                "plan_check_status": "success",
                "totp_secret": "totp",
                "extra_json": '{"account_password":"pw"}',
                "codex_status": "missing",
            },
            {
                "password_enabled": True,
                "plan_check_enabled": True,
                "twofa_enabled": True,
                "codex_enabled": True,
                "refresh_at_enabled": False,
            },
        )

        self.assertEqual(["codex"], plan["missing_steps"])
        self.assertEqual(["Codex"], plan["missing_labels"])
        self.assertFalse(plan["blocked"])

    def test_refresh_at_is_blocked_by_default_and_is_explicit_when_enabled(self):
        account = {"access_token": "", "codex_status": "success"}
        base = {
            "password_enabled": False,
            "plan_check_enabled": False,
            "twofa_enabled": False,
            "codex_enabled": False,
        }
        disabled = completion_plan(account, {**base, "refresh_at_enabled": False})
        self.assertEqual([], disabled["missing_steps"])
        self.assertEqual("refresh_at", disabled["blocked"][0]["step"])

        enabled = completion_plan(account, {**base, "refresh_at_enabled": True})
        self.assertEqual(["refresh_at"], enabled["missing_steps"])
        self.assertFalse(enabled["blocked"])

    def test_twofa_pending_checkpoint_is_not_treated_as_ready(self):
        plan = completion_plan(
            {
                "access_token": "at",
                "plan_check_status": "success",
                "totp_secret": "totp",
                "extra_json": '{"totp_setup_pending":true,"account_password":"pw"}',
                "codex_status": "success",
            },
            {
                "password_enabled": True,
                "plan_check_enabled": True,
                "twofa_enabled": True,
                "codex_enabled": True,
                "refresh_at_enabled": False,
            },
        )
        self.assertEqual(["twofa"], plan["missing_steps"])

    def test_remote_password_ineligibility_does_not_block_password_step(self):
        plan = completion_plan(
            {
                "access_token": "at",
                "plan_check_status": "success",
                "totp_secret": "totp",
                "extra_json": '{"account_password_capability":{"eligible":false,"reason":"remote_not_eligible"}}',
                "codex_status": "success",
            },
            {
                "password_enabled": True,
                "plan_check_enabled": True,
                "twofa_enabled": True,
                "codex_enabled": True,
                "refresh_at_enabled": False,
            },
        )

        self.assertIn("password", plan["missing_steps"])
        self.assertFalse(plan["blocked"])

    def test_password_reset_opt_in_allows_ineligible_account_into_reset_flow(self):
        plan = completion_plan(
            {
                "access_token": "at",
                "plan_check_status": "success",
                "totp_secret": "totp",
                "extra_json": '{"account_password_capability":{"eligible":false,"reason":"remote_not_eligible"}}',
                "codex_status": "success",
            },
            {
                "password_enabled": True,
                "password_reset_enabled": True,
                "plan_check_enabled": True,
                "twofa_enabled": True,
                "codex_enabled": True,
                "refresh_at_enabled": False,
            },
        )

        self.assertIn("password", plan["missing_steps"])
        self.assertFalse(plan["blocked"])

    def test_confirmed_missing_password_entry_blocks_repeat_completion(self):
        plan = completion_plan(
            {
                "access_token": "at",
                "totp_secret": "totp",
                "extra_json": '{"account_password_capability":{"eligible":false,"reason":"password_settings_entry_unavailable"}}',
                "codex_status": "success",
            },
            {
                "password_enabled": True,
                "plan_check_enabled": False,
                "twofa_enabled": True,
                "codex_enabled": True,
                "refresh_at_enabled": False,
            },
        )

        self.assertNotIn("password", plan["missing_steps"])
        self.assertEqual("password", plan["blocked"][0]["step"])

    def test_pending_registration_never_plans_at_refresh(self):
        account = {
            "access_token": "",
            "registration_target_status": "email_verification_pending",
            "extra_json": '{"account_password":"Password!123"}',
            "codex_status": "missing",
        }
        plan = completion_plan(account, {
            "password_enabled": True,
            "plan_check_enabled": True,
            "twofa_enabled": True,
            "codex_enabled": True,
            "refresh_at_enabled": True,
        })

        self.assertEqual(["registration_resume"], plan["missing_steps"])
        self.assertTrue(plan["registration_resume"])
        self.assertFalse(plan["blocked"])

    def test_normalized_pending_registration_state_is_used_without_legacy_checkpoint(self):
        plan = completion_plan(
            {
                "access_token": "",
                "registration_target_status": "email_verification_pending",
                "extra_json": '{"account_password":"Password!123"}',
            },
            {
                "password_enabled": True,
                "plan_check_enabled": True,
                "twofa_enabled": True,
                "codex_enabled": True,
                "refresh_at_enabled": True,
            },
        )

        self.assertEqual(["registration_resume"], plan["missing_steps"])


if __name__ == "__main__":
    unittest.main()
