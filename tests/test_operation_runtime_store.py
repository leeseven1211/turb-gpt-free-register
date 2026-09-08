"""Tests for the unified operation runtime storage boundary."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from core.storage import operation_runtime_store


class OperationRuntimeStoreBoundaryTests(TestCase):
    def test_acquire_forwards_keyword_arguments_to_implementation(self):
        implementation = SimpleNamespace(acquire_account_lease=lambda **kwargs: kwargs)
        with patch.object(operation_runtime_store, "_operation", return_value=implementation):
            result = operation_runtime_store.acquire_account_lease(
                307,
                46100,
                resource_family="openai_interactive",
                ttl_seconds=600,
            )

        self.assertEqual(
            {
                "account_id": 307,
                "run_id": 46100,
                "resource_family": "openai_interactive",
                "ttl_seconds": 600,
            },
            result,
        )

    def test_release_accepts_run_and_lease_token_and_forwards_keywords(self):
        implementation = SimpleNamespace(release_account_lease=lambda **kwargs: kwargs)
        with patch.object(operation_runtime_store, "_operation", return_value=implementation):
            result = operation_runtime_store.release_account_lease(46100, "lease-token")

        self.assertEqual(
            {"run_id": 46100, "lease_token": "lease-token"},
            result,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
