"""原单续查的进展识别和停止边界。"""

from datetime import datetime, timedelta, timezone
import json
import unittest

from core.extract_link_reconcile_policy import halt_reason, record_reconcile


class ExtractLinkReconcilePolicyTests(unittest.TestCase):
    now = datetime(2026, 10, 25, 4, 0, tzinfo=timezone.utc)
    started = "2026-10-25T03:00:00+00:00"

    def state(self, **summary):
        return {
            "extraction_state": "running", "payment_state": "pending",
            "summary": {"remote_status": "RUNNING", "current_step": "到账检测39", **summary},
        }

    def reason(self, metadata, **overrides):
        options = {"total_timeout": 7200, "no_progress_timeout": 1800, "max_query_failures": 12}
        return halt_reason(metadata, now=self.now, **{**options, **overrides})

    def test_initialization_uses_original_run_age_and_only_returns_safe_metadata(self):
        metadata = record_reconcile(
            {"secret": "synthetic-private-token"}, self.state(), now=self.now, started_at=self.started,
        )
        self.assertEqual(self.started, metadata["started_at"])
        self.assertEqual(self.started, metadata["last_progress_at"])
        self.assertEqual(0, metadata["consecutive_failures"])
        self.assertEqual(0, metadata["consecutive_not_found"])
        self.assertEqual({
            "started_at", "last_progress_at", "progress_fingerprint", "consecutive_failures",
            "consecutive_not_found", "last_http_status", "halted_reason", "halted_at",
        }, set(metadata))
        self.assertRegex(metadata["progress_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertNotIn("synthetic-private-token", json.dumps(metadata))
        self.assertEqual("no_progress", self.reason(metadata))

    def test_initial_success_does_not_erase_original_run_age(self):
        metadata = record_reconcile(
            None, self.state(), now=self.now, started_at=self.started, query_succeeded=True,
        )
        self.assertEqual(self.started, metadata["last_progress_at"])
        self.assertEqual("timeout", self.reason(metadata, total_timeout=3600))

    def test_initialization_does_not_clear_previous_query_failures_or_change_progress(self):
        previous = record_reconcile(None, self.state(), now=self.now, started_at=self.started)
        previous = record_reconcile(previous, self.state(), now=self.now, query_succeeded=False, http_status=404)
        metadata = record_reconcile(previous, self.state(percent=90), now=self.now, started_at=self.now)
        self.assertEqual(previous, metadata)

    def test_success_clears_failures_without_refreshing_unchanged_progress(self):
        previous = record_reconcile(None, self.state(), now=self.now, started_at=self.started)
        previous = record_reconcile(previous, self.state(), now=self.now, query_succeeded=False, http_status=404)
        metadata = record_reconcile(previous, self.state(), now=self.now, query_succeeded=True, http_status=200)
        self.assertEqual(self.started, metadata["started_at"])
        self.assertEqual(self.started, metadata["last_progress_at"])
        self.assertEqual(0, metadata["consecutive_failures"])
        self.assertEqual(0, metadata["consecutive_not_found"])
        self.assertEqual(200, metadata["last_http_status"])

    def test_volatile_text_and_polling_counters_do_not_create_progress(self):
        previous = record_reconcile(None, self.state(), now=self.now, started_at=self.started)
        state = self.state(current_step="到账检测40", elapsed=600, poll_count=99, message="下一次查询")
        state["message"] = "检测次数已变化"
        metadata = record_reconcile(previous, state, now=self.now, query_succeeded=True)
        self.assertEqual(previous["progress_fingerprint"], metadata["progress_fingerprint"])
        self.assertEqual(self.started, metadata["last_progress_at"])

    def test_each_business_change_refreshes_progress_without_restarting_total_age(self):
        changes = (
            ("remote_status", "DONE"), ("percent", 60), ("queue_position", 2),
            ("step_attempt", 2), ("auto_relink_attempt", 1), ("automatic_payment_status", "claimed"),
            ("xxsyun_status", "verifying"), ("payment_check_status", "completed"),
            ("entitlement_active", True), ("entitlement_inferred", True), ("remote_chain_length", 2),
            ("submission_receipt_pending", True), ("current_step", "扫码付款"),
        )
        previous = record_reconcile(None, self.state(), now=self.now, started_at=self.started)
        for key, value in changes:
            with self.subTest(field=key):
                metadata = record_reconcile(previous, self.state(**{key: value}), now=self.now, query_succeeded=True)
                self.assertNotEqual(previous["progress_fingerprint"], metadata["progress_fingerprint"])
                self.assertEqual(self.now.isoformat(), metadata["last_progress_at"])
                self.assertEqual(self.started, metadata["started_at"])
        for key, value in (("extraction_state", "succeeded"), ("payment_state", "succeeded")):
            with self.subTest(field=key):
                state = {**self.state(), key: value}
                metadata = record_reconcile(previous, state, now=self.now, query_succeeded=True)
                self.assertNotEqual(previous["progress_fingerprint"], metadata["progress_fingerprint"])
                self.assertEqual(self.now.isoformat(), metadata["last_progress_at"])

    def test_failed_queries_do_not_create_progress_and_non_404_resets_not_found_streak(self):
        previous = record_reconcile(None, self.state(), now=self.now, started_at=self.started)
        metadata = previous
        for status, failures, missing in ((404, 1, 1), (404, 2, 2), (503, 3, 0), (404, 4, 1), (None, 5, 0)):
            metadata = record_reconcile(
                metadata, self.state(percent=80), now=self.now, query_succeeded=False, http_status=status,
            )
            self.assertEqual(failures, metadata["consecutive_failures"])
            self.assertEqual(missing, metadata["consecutive_not_found"])
            self.assertEqual(status, metadata["last_http_status"])
            self.assertEqual(previous["progress_fingerprint"], metadata["progress_fingerprint"])
            self.assertEqual(self.started, metadata["last_progress_at"])

    def test_new_run_and_progress_do_not_reset_original_start(self):
        previous = record_reconcile(None, self.state(), now=self.now, started_at=self.started)
        metadata = record_reconcile(
            previous, self.state(percent=80), now=self.now, started_at=self.now, query_succeeded=True,
        )
        self.assertEqual(self.started, metadata["started_at"])
        self.assertEqual("timeout", self.reason(metadata, total_timeout=3600))

    def test_dates_are_timezone_aware_and_invalid_dates_fall_back_to_now(self):
        for bad_date in ("无效日期", "2026-10-25T03:00:00", 123, object()):
            with self.subTest(value=type(bad_date).__name__):
                metadata = record_reconcile(
                    {"started_at": bad_date, "last_progress_at": bad_date}, self.state(), now=self.now,
                )
                self.assertEqual(self.now.isoformat(), metadata["started_at"])
                self.assertEqual(self.now.isoformat(), metadata["last_progress_at"])
                self.assertEqual("", self.reason(metadata))
        metadata = record_reconcile(
            None, self.state(), now=self.now, started_at="2026-10-25T11:00:00+08:00",
        )
        self.assertEqual("timeout", self.reason(metadata, total_timeout=3600))
        naive_now = self.now.replace(tzinfo=None)
        metadata = record_reconcile(None, self.state(), now=naive_now)
        self.assertIsNotNone(datetime.fromisoformat(metadata["started_at"]).tzinfo)

    def test_bad_metadata_does_not_leak_or_break_the_policy(self):
        metadata = record_reconcile({
            "consecutive_failures": -3, "consecutive_not_found": "synthetic-private-token",
            "last_http_status": True, "progress_fingerprint": "synthetic-private-token",
            "halted_reason": "synthetic-private-token", "halted_at": "synthetic-private-token",
        }, {"summary": None}, now=self.now, query_succeeded=False, http_status=True)
        self.assertEqual(1, metadata["consecutive_failures"])
        self.assertEqual(0, metadata["consecutive_not_found"])
        self.assertIsNone(metadata["last_http_status"])
        self.assertEqual("", metadata["halted_reason"])
        self.assertNotIn("synthetic-private-token", json.dumps(metadata))
        self.assertEqual("", self.reason(None))

    def test_existing_halt_reason_has_priority_and_survives_success(self):
        previous = record_reconcile(None, self.state(), now=self.now, started_at=self.started)
        previous.update(halted_reason="no_progress", halted_at=self.started, consecutive_not_found=3)
        metadata = record_reconcile(previous, self.state(percent=100), now=self.now, query_succeeded=True)
        self.assertEqual("no_progress", self.reason(metadata, total_timeout=1))
        self.assertEqual(self.started, metadata["halted_at"])

    def test_halt_priority_is_not_found_then_failures_then_total_then_progress(self):
        metadata = {"started_at": self.started, "last_progress_at": self.started,
                    "consecutive_failures": 12, "consecutive_not_found": 3}
        self.assertEqual("remote_not_found", self.reason(metadata, total_timeout=1))
        metadata["consecutive_not_found"] = 2
        self.assertEqual("query_failures", self.reason(metadata, total_timeout=1))
        metadata["consecutive_failures"] = 11
        self.assertEqual("timeout", self.reason(metadata, total_timeout=3600))
        self.assertEqual("no_progress", self.reason(metadata, no_progress_timeout=3600))

    def test_timeouts_and_failure_limit_apply_at_the_exact_boundary(self):
        metadata = {"started_at": (self.now - timedelta(seconds=59)).isoformat(),
                    "last_progress_at": (self.now - timedelta(seconds=29)).isoformat(),
                    "consecutive_failures": 2, "consecutive_not_found": 2}
        self.assertEqual("", self.reason(metadata, total_timeout=60, no_progress_timeout=30, max_query_failures=3))
        self.assertEqual("timeout", self.reason(metadata, total_timeout=59))
        self.assertEqual("no_progress", self.reason(metadata, no_progress_timeout=29))
        self.assertEqual("query_failures", self.reason(metadata, max_query_failures=2))


if __name__ == "__main__":
    unittest.main()
