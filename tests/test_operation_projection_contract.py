from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock, patch

from core.storage import operation
from webui.routes import jobs


class OperationProjectionContractTests(TestCase):
    def test_explicit_progress_event_time_is_not_replaced_by_stage_start(self):
        event = operation._normalize_compatibility_event({
            "source_system": "registration_progress_events",
            "created_at": "2026-10-13T09:24:53+00:00",
            "detail": {"started_at": "2026-10-13T09:24:23+00:00", "occurred_at": "2026-10-13T09:24:53+00:00"},
        })
        self.assertEqual("2026-10-13T09:24:53+00:00", event["created_at"])

    def test_legacy_running_preserves_independent_row_time(self):
        event = operation._normalize_compatibility_event({
            "source_system": "registration_progress_events", "event_type": "stage.running",
            "created_at": "2026-10-13T09:24:53+00:00",
            "detail": {"started_at": "2026-10-13T09:24:23+00:00"},
        })
        self.assertEqual("2026-10-13T09:24:53+00:00", event["created_at"])
        self.assertTrue(event["event_time_known"])

    def test_legacy_running_synthetic_time_is_unknown_without_losing_sort_order(self):
        event = operation._normalize_compatibility_event({
            "id": 9, "source_system": "registration_progress_events", "event_type": "stage.running",
            "created_at": "2026-10-13T09:24:23+00:00",
            "detail": {"started_at": "2026-10-13T09:24:23+00:00"},
        })
        self.assertIsNone(event["created_at"])
        self.assertFalse(event["event_time_known"])
        self.assertEqual("2026-10-13T09:24:23+00:00", operation._event_time_sort_key(event)[0].isoformat())

    def test_terminal_time_takes_precedence_over_inherited_running_time(self):
        event = operation._normalize_compatibility_event({
            "source_system": "registration_progress_events", "event_type": "stage.failed",
            "created_at": "2026-10-13T09:24:23+00:00",
            "detail": {
                "occurred_at": "2026-10-13T09:24:23+00:00",
                "started_at": "2026-10-13T09:24:23+00:00",
                "completed_at": "2026-10-13T09:25:03+00:00",
            },
        })
        self.assertEqual("2026-10-13T09:25:03+00:00", event["created_at"])
        self.assertTrue(event["event_time_known"])

    def test_legacy_naive_stage_time_misstored_as_utc_is_not_independent_evidence(self):
        event = operation._normalize_compatibility_event({
            "source_system": "registration_progress_events", "event_type": "stage.running",
            "created_at": "2026-10-13T17:24:23+00:00",
            "detail": {"started_at": "2026-10-13T17:24:23"},
        })
        self.assertIsNone(event["created_at"])
        self.assertFalse(event["event_time_known"])

    def test_legacy_mutable_stage_row_time_cannot_confirm_new_running_event(self):
        event = operation._normalize_compatibility_event({
            "source_system": "registration_progress", "event_type": "stage.running",
            "created_at": "2026-10-13T09:24:53+00:00",
            "detail": {"started_at": "2026-10-13T09:25:23+00:00"},
        })
        self.assertIsNone(event["created_at"])
        self.assertFalse(event["event_time_known"])

    def test_old_unconfirmed_closeout_does_not_reuse_inherited_running_time(self):
        detail = {
            "state": "pending", "evidence": "unconfirmed",
            "started_at": "2026-10-13T09:24:23+00:00", "occurred_at": "2026-10-13T09:24:53+00:00",
        }
        for confirmed in (False, True):
            event = operation._normalize_compatibility_event({
                "source_system": "registration_progress_events", "event_type": "stage.pending",
                "created_at": "2026-10-13T09:24:53+00:00",
                "detail": {**detail, **({"event_time_known": True} if confirmed else {})},
            })
            self.assertEqual("2026-10-13T09:24:53+00:00" if confirmed else None, event["created_at"])
            self.assertEqual(confirmed, event["event_time_known"])

    def test_registration_unknown_never_offers_full_retry_or_postprocess(self):
        pending_account = {
            "id": 7,
            "email": "pending@example.test",
            "access_token": "",
            "extra_json": '{"registration_checkpoint":"email_verification_pending"}',
        }
        self.assertEqual([], operation._next_registration_actions(
            {"id": 9, "status": "failed"}, None, "request_unknown",
            remote_identity_state="confirmed", remote_account_state="request_unknown",
        ))
        self.assertEqual([], operation._next_registration_actions(
            {"id": 9, "status": "failed"}, pending_account, "request_unknown",
            remote_identity_state="confirmed", remote_account_state="request_unknown",
        ))
        self.assertEqual([], operation._next_registration_actions(
            {"id": 9, "status": "failed"}, None, "not_created",
            remote_identity_state="confirmed",
        ))

    def test_deactivated_account_projection_has_no_registration_follow_up(self):
        account = {
            "id": 7,
            "email": "deactivated@example.test",
            "access_token": "token",
            "account_status": "deactivated",
            "codex_status": "deactivated",
        }

        state = operation._account_state(account)
        actions = operation._next_registration_actions(
            {"id": 9, "status": "failed"},
            account,
            state["target_status"],
        )

        self.assertEqual("failed", state["checkpoint"])
        self.assertEqual("confirmed", state["remote_identity_state"])
        self.assertEqual("confirmed", state["remote_account_state"])
        self.assertEqual("persisted", state["local_account_state"])
        self.assertEqual("deactivated", state["target_status"])
        self.assertEqual([], actions)

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
