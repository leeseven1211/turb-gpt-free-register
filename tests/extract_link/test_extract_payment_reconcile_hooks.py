"""套餐结果写回和启动恢复只补齐已有支付事实。"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.extract_link import service as extract_link_service
from core.accounts.plans import service as plan_check_service
from core.storage.extract_link import jobs as extract_link_jobs
from core.storage.accounts import plan_countries


class ExtractPaymentReconcileHookTests(unittest.TestCase):
    def run_single_plan(self, result, reconcile, *, trigger="manual", written=True):
        context = SimpleNamespace(task_id=101, run_id=102, checkpoint=Mock(),
            report=Mock(return_value={}), finish=Mock())
        route = SimpleNamespace(proxy_url="", public_dict=lambda: {"network_route": "direct"}, release=Mock())
        with (
            patch.object(plan_check_service.db, "mark_account_plan_check_running", return_value=True),
            patch.object(plan_check_service.db, "update_account_plan_check", return_value=written) as save,
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch.object(plan_check_service, "_query_account_plan", return_value=result),
            patch.object(plan_check_service, "_record_promotion_queries"),
            patch.object(plan_check_service, "_log_plan_result"),
            patch.object(extract_link_jobs, "reconcile_completed_payments", create=True, side_effect=reconcile) as sync,
        ):
            self._last_save = save
            returned = plan_check_service._run_plan_check(
                account_id=77, email="reconcile@example.test", access_token="fixture-at",
                trigger=trigger, proxy=None, timezone_offset_min="-", operation_context=context,
            )
        return returned, save, sync

    def test_successful_plus_check_reconciles_only_after_account_writeback(self):
        calls = []
        def reconcile(**kwargs):
            self._last_save.assert_called_once()
            calls.append(kwargs)
            return {"confirmed": 1, "skipped": 0, "failed": 0}
        result, save, sync = self.run_single_plan({"ok": True, "current_plan_type": "plus"}, reconcile)
        self.assertTrue(result["ok"])
        save.assert_called_once()
        sync.assert_called_once_with(account_id=77)
        self.assertEqual([{"account_id": 77}], calls)

    def test_failed_free_registration_or_unwritten_result_does_not_reconcile(self):
        for result, trigger, written in (
            ({"ok": False}, "manual", True),
            ({"ok": True, "current_plan_type": "free"}, "manual", True),
            ({"ok": True, "current_plan_type": "plus"}, "registration_auto", True),
            ({"ok": True, "current_plan_type": "plus"}, "manual", False),
        ):
            with self.subTest(result=result, trigger=trigger, written=written):
                returned, _, sync = self.run_single_plan(result, lambda **kwargs: {}, trigger=trigger, written=written)
                self.assertEqual(result["ok"], returned["ok"])
                sync.assert_not_called()

    def test_reconcile_failure_keeps_successful_plan_result(self):
        def fail(**kwargs):
            raise RuntimeError("fixture-private-detail")
        result, _, sync = self.run_single_plan({"ok": True, "current_plan_type": "pro"}, fail)
        self.assertTrue(result["ok"])
        sync.assert_called_once_with(account_id=77)

    def test_country_summary_reconciles_after_final_account_writeback(self):
        result = {"ok": True, "current_plan_type": "plus", "country_success_count": 1,
            "failed_countries": [], "plan_check_partial": False}
        with (
            patch.object(plan_countries, "initialize_country_checks", return_value=([], {
                "countries": {"JP": {"pending": False, "history": []}}, "max_attempts": 1,
            })),
            patch("core.accounts.plans.countries.aggregate_country_results", return_value=result),
            patch.object(plan_countries, "save_country_summary", return_value=True) as save,
            patch.object(extract_link_jobs, "reconcile_completed_payments", create=True,
                return_value={"confirmed": 1, "skipped": 0, "failed": 0}) as sync,
        ):
            returned = plan_check_service._run_country_plan_checks(
                account_id=77, email="reconcile@example.test", access_token="fixture-at", trigger="manual",
                proxy=None, timezone_offset_min="-", countries=["JP"], reporter=Mock(),
                operation_context=None, config_snapshot={}, proxy_source=None,
            )
        self.assertTrue(returned["ok"])
        save.assert_called_once()
        sync.assert_called_once_with(account_id=77)

    def test_startup_reconciles_completed_local_facts_even_if_provider_is_disabled(self):
        with (
            patch.object(extract_link_service, "_bool_setting", return_value=False),
            patch.object(extract_link_jobs, "reconcile_completed_payments", create=True,
                return_value={"confirmed": 1, "skipped": 0, "failed": 0}) as sync,
            patch.object(extract_link_jobs, "list_recoverable_workbench_jobs") as recover,
        ):
            self.assertEqual(0, extract_link_service.resume_known_remote_jobs())
        sync.assert_called_once_with()
        recover.assert_not_called()

    def test_periodic_recovery_retries_saved_payment_evidence_writeback(self):
        with (
            patch.object(extract_link_service, "_bool_setting", return_value=True),
            patch.object(extract_link_jobs, "reconcile_completed_payments", create=True,
                return_value={"confirmed": 0, "skipped": 0, "failed": 0}) as sync,
            patch.object(extract_link_jobs, "list_recoverable_workbench_jobs", return_value=[]),
        ):
            self.assertEqual(0, extract_link_service.resume_known_remote_jobs(continuous_only=True))
        sync.assert_called_once_with()

    def test_local_reconcile_error_does_not_block_existing_remote_recovery(self):
        with (
            patch.object(extract_link_service, "_bool_setting", return_value=True),
            patch.object(extract_link_jobs, "reconcile_completed_payments", create=True,
                side_effect=RuntimeError("fixture-private-detail")),
            patch.object(extract_link_jobs, "list_recoverable_workbench_jobs", return_value=[]) as recover,
        ):
            self.assertEqual(0, extract_link_service.resume_known_remote_jobs())
        recover.assert_called_once()
