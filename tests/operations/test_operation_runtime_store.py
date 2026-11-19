"""Runtime storage keeps lease and cancellation fences after repository extraction."""
from __future__ import annotations

from contextlib import nullcontext
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.storage.operations import common, runtime, schema


class OperationRuntimeStoreBoundaryTests(TestCase):
    def setUp(self):
        self.cursor = MagicMock()
        self.cursor.rowcount = 1
        self.connection = MagicMock()
        self.connection.cursor.return_value = nullcontext(self.cursor)
        for replacement in (
            patch.object(schema, "init_operation_schema"),
            patch.object(common, "_connect", return_value=nullcontext(self.connection)),
            patch.object(common, "_schema_name", return_value="test_runtime_boundary"),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_positional_acquire_rejects_a_run_owned_by_another_account(self):
        self.cursor.fetchone.return_value = {
            "status": "running", "account_id": 999, "resource_family": "openai_interactive",
        }
        with patch.object(runtime.record_store, "get_row") as read_account:
            lease = runtime.acquire_account_lease(307, 46100, resource_family="openai_interactive", ttl_seconds=600)

        self.assertIsNone(lease)
        read_account.assert_not_called()
        self.assertEqual(1, len(self.cursor.execute.call_args_list))
        self.assertIn("FOR UPDATE", self.cursor.execute.call_args.args[0])

    def test_positional_release_remains_fenced_by_the_given_lease_token(self):
        self.assertTrue(runtime.release_account_lease(46100, "lease-token"))

        query, params = self.cursor.execute.call_args.args
        self.assertIn("WHERE run_id=%s AND lease_token=%s", query)
        self.assertEqual((46100, "lease-token"), params)

    def test_missing_cancel_token_generation_is_treated_as_cancelled(self):
        self.cursor.fetchone.return_value = None
        self.assertTrue(runtime.is_run_cancel_requested(46101, "old-generation"))

        query, params = self.cursor.execute.call_args.args
        self.assertIn("cancellation_token=%s", query)
        self.assertEqual([46101, "old-generation"], params)

    def test_rejected_heartbeat_does_not_extend_the_lease(self):
        self.cursor.rowcount = 0
        with patch.object(runtime.bulk_execution, "fact_update", return_value=nullcontext(None)):
            self.assertFalse(runtime.heartbeat_run(46101, "expired-lease"))

        self.assertEqual(1, len(self.cursor.execute.call_args_list))
        query, params = self.cursor.execute.call_args.args
        self.assertIn("lease.expires_at > now()", query)
        self.assertEqual((46101, "expired-lease"), params)


if __name__ == "__main__":
    import unittest

    unittest.main()
