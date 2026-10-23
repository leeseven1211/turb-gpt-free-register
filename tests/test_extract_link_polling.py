from __future__ import annotations

import base64
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import extract_link_service as service
from core.extract_link_providers.contracts import ProviderJob, safe_payment_artifact


class ExtractPollingTests(unittest.TestCase):
    def test_safe_progress_keeps_document_fields_and_card_uses_remote_step(self):
        state = service._safe_provider_job_state(ProviderJob(extraction_state="running", summary={
            "remote_status": "AWAITING_BLIK_CODE", "percent": 66,
            "current_step": "CONFIRM", "completed_steps": 8, "total_steps": 12,
            "run_attempt": 1, "step_attempt": 2, "failure_code": "SETUP_INTENT_FAILED",
            "failure_type": "CLIENT_ERROR", "plus_verification_status": "WAITING_FOR_PAYMENT",
        }), mode="extract_only")
        self.assertEqual(8, state["summary"].get("completed_steps"))
        self.assertEqual("SETUP_INTENT_FAILED", state["summary"].get("failure_code"))
        item = service._workbench_task_item({"task_id": 1, "public_state": state, "current_stage": "extraction"})
        self.assertEqual("CONFIRM", item["progress"]["label"])

    def test_missing_or_null_sync_schedule_does_not_trigger_payment_write(self):
        self.assertFalse(service._provider_payment_sync_due({}))
        self.assertFalse(service._provider_payment_sync_due({"next_payment_state_sync_at": None}))

    def test_only_png_data_images_are_kept_with_valid_signature(self):
        png = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nsynthetic").decode()
        self.assertEqual(png, safe_payment_artifact({"qr_image_url_png": png}).get("qr_image_url_png"))
        self.assertEqual({}, safe_payment_artifact({"qr_image_url_png": "data:image/png;base64,c2NyaXB0"}))
        self.assertEqual({}, safe_payment_artifact({"qr_image_url_svg": "data:image/svg+xml;base64,PHN2Zy8+"}))

    def _monitor(self, jobs, *, budget=10, interval=2):
        clock = [0.0]
        def sleep(seconds): clock[0] += seconds
        context = SimpleNamespace(run_id=99, report=Mock(), checkpoint=Mock())
        provider = SimpleNamespace(get_status=Mock(side_effect=jobs), transport=SimpleNamespace())
        runtime = SimpleNamespace(event_timeout=budget, poll_interval=interval, timeout=30)
        initial = ProviderJob(job_id="synthetic", extraction_state="running", summary={"current_step": "CREATE"})
        state = service._safe_provider_job_state(initial, mode="extract_only")
        with patch.object(service.time, "monotonic", side_effect=lambda: clock[0]), patch.object(service.time, "sleep", side_effect=sleep), patch.object(service, "_update_provider_job"):
            result = service._monitor_provider_job(context, provider, runtime, initial, state, provider_id="lumen_flow", mode="extract_only", action="create")
        return context, provider, result, clock[0]

    def test_step_changes_and_failure_are_visible_in_persistent_events(self):
        context, provider, result, elapsed = self._monitor([
            ProviderJob(job_id="synthetic", extraction_state="running", summary={"current_step": "CONFIRM", "percent": 66, "step_attempt": 2}),
            ProviderJob(job_id="synthetic", extraction_state="failed", summary={"current_step": "CONFIRM", "failure_code": "SETUP_INTENT_FAILED"}),
        ])
        text = repr(context.report.call_args_list)
        self.assertIn("CONFIRM", text)
        self.assertIn("66", text)
        self.assertIn("SETUP_INTENT_FAILED", text)
        self.assertEqual("failed", result[1]["extraction_state"])
        self.assertEqual(2, provider.get_status.call_count)

    def test_monitor_deadline_does_not_sleep_or_query_beyond_budget(self):
        context, provider, result, elapsed = self._monitor([
            ProviderJob(job_id="synthetic", extraction_state="running"),
        ], budget=1, interval=10)
        self.assertLessEqual(elapsed, 1)
        provider.get_status.assert_not_called()
        self.assertIn("监控", repr(context.report.call_args_list))

    def test_transient_query_error_keeps_remote_job_and_retries(self):
        context, provider, result, elapsed = self._monitor([
            RuntimeError("临时网络错误"), ProviderJob(job_id="synthetic", extraction_state="succeeded"),
        ], budget=30)
        self.assertEqual(2, provider.get_status.call_count)
        self.assertEqual("succeeded", result[1]["extraction_state"])
        self.assertIn("查询", repr(context.report.call_args_list))

    def test_transport_uses_remaining_monitor_budget(self):
        transport = service._ProviderHTTPTransport(SimpleNamespace(api_base="https://example.test"))
        transport.deadline = 102.0
        with patch.object(service.time, "monotonic", return_value=100.0), patch.object(service.curl_requests, "request", return_value=object()) as request:
            transport.request("GET", "/status", timeout=30)
        self.assertEqual(2.0, request.call_args.kwargs["timeout"])

    def test_automatic_uncertain_result_stops_even_with_delayed_checkout_state(self):
        for extraction in ("succeeded", "running", "unknown"):
            with self.subTest(extraction=extraction):
                context = SimpleNamespace(run_id=99, report=Mock(), checkpoint=Mock())
                provider = SimpleNamespace(get_status=Mock(), get_automatic_payment_status=Mock(), transport=SimpleNamespace())
                job = ProviderJob(job_id="synthetic", extraction_state=extraction, payment_state="unknown",
                                  summary={"automatic_payment_terminal": True, "automatic_payment_requires_reconcile": True})
                state = service._safe_provider_job_state(job, mode="auto_payment")
                clock = [0.0]
                provider.get_status.return_value = job
                provider.get_automatic_payment_status.return_value = job
                with patch.object(service.time, "monotonic", side_effect=lambda: clock[0]), patch.object(service.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), patch.object(service, "_update_provider_job"):
                    service._monitor_provider_job(context, provider, SimpleNamespace(event_timeout=2, poll_interval=1, timeout=30),
                                                  job, state, provider_id="lumen_flow", mode="auto_payment", action="create")
                provider.get_status.assert_not_called()
                provider.get_automatic_payment_status.assert_not_called()

    def test_later_payment_check_failure_keeps_confirmed_extraction(self):
        first = ProviderJob(extraction_state="succeeded", payment_links=("https://pay.example.test/entry",))
        later = ProviderJob(extraction_state="failed", payment_state="unknown", summary={"remote_status": "ERROR"})
        merged = service._merge_provider_jobs(first, later)
        self.assertEqual("succeeded", merged.extraction_state)
        self.assertEqual("unknown", merged.payment_state)

    def test_huanguang_only_advertises_supported_type_and_modes(self):
        with patch.object(service, "_runtime_setting", return_value=True):
            self.assertFalse(service._provider_mode_enabled("huanguang", "auto_payment"))
        with self.assertRaisesRegex(ValueError, "UPI"):
            service._provider_link_type("huanguang", "pix", "upi")

    def test_sync_reference_recovers_before_old_empty_failure_without_crossing_jobs(self):
        empty = {"provider_id": "lumen_flow", "job_id": "same-job", "public_state": {"extraction_state": "pending", "preflight_status": "failed"}}
        known = {"provider_id": "lumen_flow", "job_id": "same-job", "public_state": {"extraction_state": "failed", "preflight_status": "passed"}}
        with patch("core.storage.extract_link_jobs.get_provider_job_private", side_effect=[empty, known]), patch("core.storage.operation.get_run", return_value={"data": {"workbench_action": "sync_status", "provider_job_run_id": 10}}):
            self.assertEqual(known, service._provider_job_for_sync(11))
        other = {**known, "job_id": "other-job"}
        with patch("core.storage.extract_link_jobs.get_provider_job_private", side_effect=[empty, other]), patch("core.storage.operation.get_run", return_value={"data": {"workbench_action": "sync_status", "provider_job_run_id": 10}}):
            self.assertEqual(empty, service._provider_job_for_sync(11))


if __name__ == "__main__":
    unittest.main()
