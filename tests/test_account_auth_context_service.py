# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch


class AccountAuthContextServiceTests(unittest.TestCase):
    def setUp(self):
        from core import account_auth_context_service

        account_auth_context_service.reset_for_tests()

    def tearDown(self):
        from core import account_auth_context_service

        account_auth_context_service.reset_for_tests()

    def test_disabled_raw_context_does_not_cleanup_or_start_worker(self):
        from core import account_auth_context_service

        with patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", False), \
             patch.object(account_auth_context_service, "cleanup_once") as cleanup, \
             patch.object(account_auth_context_service.threading, "Thread") as thread:
            self.assertFalse(account_auth_context_service.start_periodic_cleanup())

        cleanup.assert_not_called()
        thread.assert_not_called()

    def test_enabled_raw_context_runs_startup_cleanup_and_starts_one_worker(self):
        from core import account_auth_context_service

        with patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", True), \
             patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", 30), \
             patch.object(account_auth_context_service, "cleanup_once", return_value=2) as cleanup, \
             patch.object(account_auth_context_service.threading, "Thread") as thread:
            self.assertTrue(account_auth_context_service.start_periodic_cleanup())
            self.assertFalse(account_auth_context_service.start_periodic_cleanup())

        cleanup.assert_called_once_with()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
