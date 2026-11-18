# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from core.runtime.periodic import PeriodicThread
from tests.runtime.test_periodic_lifecycle import FakeThread


class AccountAuthContextServiceTests(unittest.TestCase):
    def setUp(self):
        from core.accounts import auth_context_cleanup as service
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(service, "_SCHEDULER", PeriodicThread("test-auth-cleanup")))
        self.stack.enter_context(patch("core.runtime.process.get_runtime_context", return_value=None))

    def tearDown(self):
        # Every thread is a controlled fake scoped to this test's owner.
        self.stack.close()

    def test_disabled_raw_context_starts_only_a_dormant_scheduler(self):
        from core.accounts import auth_context_cleanup as account_auth_context_service

        with patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", False), \
             patch.object(account_auth_context_service, "cleanup_once") as cleanup, \
             patch.object(account_auth_context_service.threading, "Thread", side_effect=FakeThread) as thread:
            self.assertTrue(account_auth_context_service.start_periodic_cleanup())
            self.assertFalse(account_auth_context_service.start_periodic_cleanup())

        cleanup.assert_not_called()
        thread.assert_called_once()
        self.assertTrue(account_auth_context_service.scheduler_status()["alive"])

    def test_enabled_raw_context_runs_startup_cleanup_and_starts_one_worker(self):
        from core.accounts import auth_context_cleanup as account_auth_context_service

        with patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", True), \
             patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", 30), \
             patch.object(account_auth_context_service, "cleanup_once", return_value=2) as cleanup, \
             patch.object(account_auth_context_service.threading, "Thread", side_effect=FakeThread) as thread:
            self.assertTrue(account_auth_context_service.start_periodic_cleanup())
            self.assertFalse(account_auth_context_service.start_periodic_cleanup())

        cleanup.assert_called_once_with()
        thread.assert_called_once()
        self.assertTrue(account_auth_context_service.scheduler_status()["alive"])

    def test_disabled_or_zero_retention_does_not_touch_private_contexts(self):
        from core.accounts import auth_context_cleanup as account_auth_context_service

        for enabled, days in ((False, 30), (True, 0)):
            with self.subTest(enabled=enabled, days=days), \
                 patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", enabled), \
                 patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", days), \
                 patch("core.storage.accounts.auth.cleanup_expired_auth_contexts") as cleanup:
                self.assertEqual(account_auth_context_service.cleanup_once(), 0)
                cleanup.assert_not_called()

    def test_startup_cleanup_failure_keeps_periodic_retry_available(self):
        from core.accounts import auth_context_cleanup as service

        with patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", True), \
             patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", 30), \
             patch.object(service, "cleanup_once", side_effect=RuntimeError("临时数据库错误")), \
             patch.object(service.threading, "Thread", side_effect=FakeThread) as thread, \
             patch.object(service.logger, "exception"):
            self.assertTrue(service.start_periodic_cleanup())
            self.assertFalse(service.start_periodic_cleanup())
            self.assertTrue(service.scheduler_status()["alive"])


if __name__ == "__main__":
    unittest.main()
