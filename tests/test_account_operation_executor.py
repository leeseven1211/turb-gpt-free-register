# -*- coding: utf-8 -*-
import unittest
import threading
import time
from unittest.mock import MagicMock, call, patch


class AccountOperationExecutorTests(unittest.TestCase):
    def test_account_operation_services_share_the_common_executor(self):
        from core import (
            account_operation_executor,
            codex_operation_service,
            codex_token_refresh_service,
            deactivation_mail_service,
            extract_link_service,
            live_check_service,
            plan_check_service,
        )
        from webui import runtime

        common = account_operation_executor.executor
        self.assertIs(live_check_service._EXECUTOR, common)
        self.assertIs(plan_check_service._ACCOUNT_EXECUTOR, common)
        self.assertIs(codex_operation_service._EXECUTOR, common)
        self.assertFalse(
            hasattr(codex_token_refresh_service, "_EXECUTOR"),
            "Codex token refresh must dispatch through the durable gateway, not a local executor",
        )
        self.assertIs(deactivation_mail_service._EXECUTOR, common)
        self.assertIs(extract_link_service._EXECUTOR, common)
        self.assertIs(runtime._ACCOUNT_EXECUTOR, common)
        self.assertIsNot(plan_check_service._EXECUTOR, common)

    def test_common_executor_reads_account_batch_workers(self):
        from core import account_operation_executor

        with patch("config.codex.ACCOUNT_BATCH_WORKERS", 7):
            self.assertEqual(7, account_operation_executor.configured_workers())

    def test_common_executor_rebuilds_for_a_new_configured_worker_count(self):
        from core.account_operation_executor import AccountOperationExecutor

        first_pool = MagicMock()
        second_pool = MagicMock()
        with (
            patch("core.account_operation_executor.ThreadPoolExecutor", side_effect=[first_pool, second_pool]) as pool,
            patch("config.codex.ACCOUNT_BATCH_WORKERS", 2),
        ):
            operation_executor = AccountOperationExecutor()
            operation_executor.submit(lambda: None)
            with patch("config.codex.ACCOUNT_BATCH_WORKERS", 5):
                operation_executor.submit(lambda: None)
            operation_executor.shutdown()

        self.assertEqual([2, 5], [call.kwargs["max_workers"] for call in pool.call_args_list])
        self.assertEqual(
            [
                call(wait=False, cancel_futures=False),
                call(wait=True, cancel_futures=False),
            ],
            first_pool.shutdown.call_args_list,
        )
        second_pool.shutdown.assert_called_once_with(wait=True, cancel_futures=False)

    def test_two_pool_generations_share_one_concurrency_budget(self):
        from core.account_operation_executor import AccountOperationExecutor

        entered = threading.Event()
        release = threading.Event()
        lock = threading.Lock()
        active = 0
        maximum = 0

        def work():
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
                if active >= 2:
                    entered.set()
            release.wait(2)
            with lock:
                active -= 1

        operation_executor = AccountOperationExecutor()
        try:
            with patch("config.codex.ACCOUNT_BATCH_WORKERS", 2):
                first = [operation_executor.submit(work) for _ in range(2)]
                self.assertTrue(entered.wait(1))
            with patch("config.codex.ACCOUNT_BATCH_WORKERS", 4):
                second = [operation_executor.submit(work) for _ in range(4)]
                time.sleep(0.1)
                self.assertLessEqual(operation_executor.status()["active"], 4)
            release.set()
            for future in first + second:
                future.result(timeout=3)
            self.assertLessEqual(maximum, 4)
        finally:
            release.set()
            operation_executor.shutdown()

    def test_try_submit_is_non_blocking_when_global_budget_is_full(self):
        from core.account_operation_executor import AccountOperationExecutor

        entered = threading.Event()
        release = threading.Event()
        operation_executor = AccountOperationExecutor()

        def work():
            entered.set()
            release.wait(2)

        try:
            with patch("config.codex.ACCOUNT_BATCH_WORKERS", 1):
                first = operation_executor.try_submit(work)
                self.assertIsNotNone(first)
                self.assertTrue(entered.wait(1))
                self.assertIsNone(operation_executor.try_submit(work))
            release.set()
            first.result(timeout=3)
        finally:
            release.set()
            operation_executor.shutdown()

    def test_codex_bulk_dispatch_submits_each_run_to_common_pool(self):
        from core import codex_operation_service

        with patch.object(codex_operation_service._EXECUTOR, "submit") as submit:
            codex_operation_service._dispatch_bulk([11, 12, 13], workers=99)

        self.assertEqual(3, submit.call_count)
        self.assertEqual([11, 12, 13], [call.args[1] for call in submit.call_args_list])

    def test_plan_check_keeps_registration_trigger_on_the_registration_pool(self):
        from core import plan_check_service

        with (
            patch.object(plan_check_service._QUEUE_SLOTS, "acquire", return_value=True),
            patch.object(plan_check_service._QUEUE_SLOTS, "release"),
            patch.object(plan_check_service.db, "claim_account_plan_check", return_value=True),
            patch.object(plan_check_service.account_task_store, "create_task", return_value=901),
            patch.object(plan_check_service._EXECUTOR, "submit") as registration_submit,
            patch.object(plan_check_service._ACCOUNT_EXECUTOR, "submit") as account_submit,
        ):
            plan_check_service.enqueue_account_plan_check(
                account_id=1,
                email="account@example.com",
                access_token="access-token",
                trigger="registration_auto",
            )
            plan_check_service.enqueue_account_plan_check(
                account_id=2,
                email="account-2@example.com",
                access_token="access-token",
                trigger="manual_bulk",
            )

        self.assertEqual(1, registration_submit.call_count)
        self.assertEqual(1, account_submit.call_count)


if __name__ == "__main__":
    unittest.main()
