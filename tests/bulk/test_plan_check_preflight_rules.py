"""套餐预检资格的独立规则期望，不连接数据库。"""
import unittest

from core.bulk_operations import preflight_policy
from core.bulk_operations.preflight_policy import plan_check_result


class PlanCheckRuleTests(unittest.TestCase):
    def test_effective_snapshot_matches_legacy_one_level_resolution(self):
        cases = [
            ({"auto_refresh_at_enabled": False}, {"auto_refresh_at_enabled": False}),
            ({"auto_refresh_at_enabled": True, "config_snapshot": {"auto_refresh_at_enabled": False}}, {"auto_refresh_at_enabled": False}),
            ({"config_snapshot": None}, {}),
            ({"config_snapshot": "false"}, {}),
            ({"config_snapshot": {"config_snapshot": {"auto_refresh_at_enabled": False}}}, {"config_snapshot": {"auto_refresh_at_enabled": False}}),
        ]
        for settings, expected in cases:
            with self.subTest(settings=settings):
                self.assertEqual(expected, preflight_policy.effective_settings(settings))

    def test_priority_and_saved_config_truthiness(self):
        ready = {"id": 7, "email": " a@example.test ", "access_token": "present"}
        cases = [
            (None, 8, True, {}, ("not_executable", "account_missing", None)),
            ({**ready, "account_status": "\u2003DEACTIVATED\t"}, 8, True, {}, ("not_executable", "account_deactivated", None)),
            ({**ready, "email": "\u2003\t"}, 8, True, {}, ("not_executable", "account_email_missing", None)),
            (ready, 8, True, {}, ("waiting_account", "account_busy", 8)),
            (ready, None, True, {}, ("waiting_account", "registration_in_progress", None)),
            ({**ready, "access_token": ""}, None, False, {"auto_refresh_at_enabled": False}, ("not_executable", "access_token_missing", None)),
            ({**ready, "access_token": ""}, None, False, {}, ("ready", None, None)),
            ({**ready, "access_token": ""}, None, False, {"auto_refresh_at_enabled": "false"}, ("ready", None, None)),
        ]
        for account, blocker, registration, settings, expected in cases:
            with self.subTest(expected=expected, account=account):
                result = plan_check_result(account, blocker_run_id=blocker, registration_busy=registration, settings=settings)
                self.assertEqual(expected, (result["disposition"], result["reason_code"], result["blocker_run_id"]))


if __name__ == "__main__":
    unittest.main()
