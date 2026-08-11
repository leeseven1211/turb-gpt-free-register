# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import account_export
from core import plan_check_service


class RegistrationPlanCheckTests(unittest.TestCase):
    def test_manual_plan_check_acquires_and_releases_account_proxy(self):
        route = SimpleNamespace(
            proxy_url="http://fresh-jp.example:8080",
            public_dict=lambda: {
                "proxy_mode": "1024",
                "network_route": "proxy",
                "proxy_provider": "1024proxy",
                "proxy_used": "http://1.2.*.*:8080",
                "proxy_region": "JP",
            },
            release=Mock(),
        )
        expected = {"ok": True, "current_plan_type": "free", "plus_trial_eligible": True}
        with (
            patch.object(plan_check_service.db, "mark_account_plan_check_running", return_value=True),
            patch.object(plan_check_service.db, "update_account_plan_check", return_value=True),
            patch.object(plan_check_service, "_query_account_plan", return_value=expected) as query,
            patch("core.account_proxy.acquire_account_proxy", return_value=route) as acquire,
            patch.object(plan_check_service, "_QUEUE_SLOTS"),
        ):
            result = plan_check_service._run_plan_check(
                account_id=9,
                email="old@example.com",
                access_token="token",
                trigger="manual",
                proxy=None,
                timezone_offset_min="-",
            )
        acquire.assert_called_once_with(
            account_id=9,
            email="old@example.com",
            purpose="plan-check",
            explicit_proxy=None,
        )
        self.assertEqual(query.call_args.kwargs["proxy"], "http://fresh-jp.example:8080")
        route.release.assert_called_once_with(reason="plan-check-9")
        self.assertEqual(result["proxy_region"], "JP")

    def test_sync_registration_check_uses_explicit_proxy_and_persists_before_return(self):
        expected = {
            "ok": True,
            "current_plan_type": "free",
            "plus_trial_eligible": True,
        }
        with (
            patch.object(plan_check_service.db, "claim_account_plan_check", return_value=True) as claim,
            patch.object(plan_check_service.db, "mark_account_plan_check_running", return_value=True) as mark,
            patch.object(plan_check_service.db, "update_account_plan_check", return_value=True) as update,
            patch.object(plan_check_service, "_query_account_plan", return_value=expected) as query,
        ):
            result = plan_check_service.check_registration_account_plan(
                account_id=7,
                email="new@example.com",
                access_token="token",
                proxy="http://proxy.example:8080",
            )

        self.assertEqual(result, expected)
        claim.assert_called_once_with(acc_id=7, trigger="registration_auto")
        mark.assert_called_once_with(7)
        query.assert_called_once_with(
            email="new@example.com",
            access_token="token",
            trigger="registration_auto",
            proxy="http://proxy.example:8080",
            timezone_offset_min="-",
        )
        update.assert_called_once_with(acc_id=7, result=expected)

    def test_save_account_uses_sync_check_when_registration_proxy_is_available(self):
        with (
            patch("core.db.insert_account", return_value=12),
            patch.object(account_export, "_append_batch_archive", return_value="batch"),
            patch.object(plan_check_service, "check_registration_account_plan", return_value={"ok": True}) as sync_check,
            patch.object(plan_check_service, "enqueue_account_plan_check") as enqueue,
        ):
            row_id = account_export.save_account_data(
                email="new@example.com",
                access_token="token",
                proxy_used="http://proxy.example:8080",
                plan_check_proxy="http://proxy.example:8080",
            )

        self.assertEqual(row_id, 12)
        sync_check.assert_called_once_with(
            account_id=12,
            email="new@example.com",
            access_token="token",
            proxy="http://proxy.example:8080",
        )
        enqueue.assert_not_called()

    def test_save_account_keeps_async_check_without_registration_proxy(self):
        with (
            patch("core.db.insert_account", return_value=13),
            patch.object(account_export, "_append_batch_archive", return_value="batch"),
            patch.object(plan_check_service, "check_registration_account_plan") as sync_check,
            patch.object(
                plan_check_service,
                "enqueue_account_plan_check",
                return_value={"accepted": True},
            ) as enqueue,
        ):
            row_id = account_export.save_account_data(
                email="direct@example.com",
                access_token="token",
            )

        self.assertEqual(row_id, 13)
        sync_check.assert_not_called()
        enqueue.assert_called_once_with(
            account_id=13,
            email="direct@example.com",
            access_token="token",
            trigger="registration_auto",
        )


if __name__ == "__main__":
    unittest.main()
