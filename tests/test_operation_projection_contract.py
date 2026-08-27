from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock, patch

from core.storage import operation
from webui.routes import jobs


class OperationProjectionContractTests(TestCase):
    def test_batch_refresh_deduplicates_and_sorts_only_explicit_ids(self):
        cursor = Mock()
        with patch.object(operation, "_refresh_batch") as refresh:
            operation._refresh_batches(cursor, [7, 2, 7, None, 4])

        self.assertEqual([(cursor, 2), (cursor, 4), (cursor, 7)], [call.args for call in refresh.call_args_list])
        cursor.execute.assert_not_called()

    def test_d_event_fields_are_preserved_as_compatibility_detail(self):
        stage, event_type, detail, error, level = operation._compat_registration_event_detail({
            "checkpoint": "account_request_started",
            "event_type": "stage_timing",
            "level": "ERROR",
            "message": "远端请求结果未知",
            "detail": {
                "stage": "account_request_started",
                "state_before": "running",
                "state_after": "failed",
                "duration_ms": 842,
                "wait_reason": "driver_command",
                "error": {"code": "request_unknown", "message": "远端请求结果未知"},
            },
        })

        self.assertEqual("account_request_started", stage)
        self.assertEqual("stage_timing", event_type)
        self.assertEqual("running", detail["state_before"])
        self.assertEqual("failed", detail["state_after"])
        self.assertEqual(842, detail["duration_ms"])
        self.assertEqual("driver_command", detail["wait_reason"])
        self.assertEqual("远端请求结果未知", error)
        self.assertEqual("ERROR", level)

    def test_projection_backoff_is_bounded_and_monotonic(self):
        delays = [operation._projection_backoff(attempts) for attempts in range(1, 20)]

        self.assertEqual(5, delays[0])
        self.assertEqual(sorted(delays), delays)
        self.assertLessEqual(delays[-1], 15 * 60)

    def test_jobs_response_exposes_projection_delay_without_changing_legacy_rows(self):
        result = {"progress_batch": {"batch_id": "batch-1", "total": 1}, "progress_batches": []}
        with patch.object(jobs.operation_task_store, "list_batches", return_value=[{
            "source_system": "registration_batches",
            "source_id": "batch-1",
            "projection_status": "failed",
            "projection_delayed": True,
            "projection_lag_ms": 5000,
            "projection_queue_error": "temporary failure",
            "projection_queue_next_retry_at": "2026-08-27T01:00:05+00:00",
        }]):
            jobs._attach_projection_status(result)

        self.assertEqual("failed", result["progress_batch"]["projection_status"])
        self.assertTrue(result["progress_batch"]["projection_delayed"])
        self.assertEqual(5000, result["progress_batch"]["projection_lag_ms"])
        self.assertEqual(1, result["progress_batch"]["total"])


if __name__ == "__main__":
    import unittest

    unittest.main()
