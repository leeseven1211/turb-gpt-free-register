# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from config import codex as codex_config
from core import sms_provider


class _Http:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class GrizzlySmsProviderTests(unittest.TestCase):
    def setUp(self):
        sms_provider._ACQUIRED_AT.clear()
        sms_provider._ACTIVATION_META.clear()
        sms_provider._GRIZZLY_COUNTRY_CURSOR = 0

    def test_parse_get_number_v2_includes_activation_time(self):
        raw = json.dumps({
            "activationId": 12345,
            "phoneNumber": "56912345678",
            "activationCost": 0.06,
            "countryCode": "151",
            "activationTime": "2026-08-11 10:38:03",
        })

        activation_id, phone, meta = sms_provider._parse_grizzly_number_response(raw)

        self.assertEqual(activation_id, "12345")
        self.assertEqual(phone, "56912345678")
        self.assertEqual(meta["activation_time"], "2026-08-11 10:38:03")
        self.assertEqual(meta["activation_cost"], 0.06)

    def test_acquire_grizzly_uses_v2_and_records_planned_cancel(self):
        http = _Http()
        raw = json.dumps({
            "activationId": 12345,
            "phoneNumber": "56912345678",
            "activationTime": "2026-08-11 10:38:03",
        })
        captured = {}

        def fake_request(_http, params):
            captured.update(params)
            return raw

        with tempfile.TemporaryDirectory() as td:
            queue_path = Path(td) / "sms_cancel_queue.json"
            with (
                patch.object(codex_config, "SMS_PROVIDER", "grizzly"),
                patch.object(codex_config, "SMS_SERVICE", "dr"),
                patch.object(codex_config, "SMS_COUNTRY", "151"),
                patch.object(codex_config, "SMS_MAX_PRICE", "0.06"),
                patch.object(sms_provider, "_CANCEL_QUEUE_PATH", queue_path),
                patch.object(sms_provider, "start_cancel_worker") as start_worker,
                patch.object(sms_provider, "_request_grizzly", side_effect=fake_request),
                patch.object(sms_provider.time, "time", return_value=1000.0),
            ):
                activation_id, phone = sms_provider.acquire_number(http=http)

            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["items"][0]["activation_id"], "12345")
            self.assertEqual(payload["items"][0]["next_attempt_at"], 1320.0)
            start_worker.assert_called_once_with()

        self.assertEqual((activation_id, phone), ("12345", "56912345678"))
        self.assertEqual(captured["action"], "getNumberV2")
        self.assertEqual(captured["maxPrice"], "0.06")
        self.assertEqual(sms_provider._ACTIVATION_META["12345"]["cancel_at"], 1305.0)

    def test_acquire_grizzly_falls_back_to_next_country_and_rotates(self):
        http = _Http()
        calls = []

        def fake_request(_http, params):
            calls.append(params["country"])
            if params["country"] == "117":
                raise sms_provider.SmsNoNumbersError("NO_NUMBERS")
            return json.dumps({
                "activationId": 999,
                "phoneNumber": "77011234567",
                "countryCode": params["country"],
            })

        with tempfile.TemporaryDirectory() as td:
            with (
                patch.object(codex_config, "SMS_PROVIDER", "grizzly"),
                patch.object(codex_config, "SMS_SERVICE", "dr"),
                patch.object(codex_config, "SMS_COUNTRY", "117,2,148"),
                patch.object(codex_config, "SMS_MAX_PRICE", "0.06"),
                patch.object(sms_provider, "_CANCEL_QUEUE_PATH", Path(td) / "queue.json"),
                patch.object(sms_provider, "start_cancel_worker"),
                patch.object(sms_provider, "_request_grizzly", side_effect=fake_request),
            ):
                activation_id, phone = sms_provider.acquire_number(http=http)

        self.assertEqual((activation_id, phone), ("999", "77011234567"))
        self.assertEqual(calls, ["117", "2"])
        self.assertEqual(sms_provider._GRIZZLY_COUNTRY_CURSOR, 2)
        self.assertEqual(sms_provider._ACTIVATION_META["999"]["requested_country"], "2")

    def test_complete_removes_crash_recovery_cancel_job(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path = Path(td) / "sms_cancel_queue.json"
            sms_provider._ACTIVATION_META["12345"] = {"acquired_at": 1000.0, "cancel_at": 1305.0}
            with (
                patch.object(codex_config, "SMS_PROVIDER", "grizzly"),
                patch.object(sms_provider, "_CANCEL_QUEUE_PATH", queue_path),
                patch.object(sms_provider, "set_status", return_value="ACCESS_ACTIVATION"),
            ):
                sms_provider._enqueue_grizzly_cancel("12345")
                sms_provider.complete("12345")

            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["items"], [])

    def test_wrong_max_price_is_a_non_retryable_typed_error(self):
        http = MagicMock()
        http.get.return_value.status_code = 200
        http.get.return_value.text = "WRONG_MAX_PRICE:6.50"

        with patch.object(codex_config, "SMS_API_KEY", "test-key"):
            with self.assertRaisesRegex(sms_provider.SmsPriceLimitError, "SMS_MAX_PRICE"):
                sms_provider._request_grizzly(http, {"action": "getNumberV2"})

    def test_early_cancel_is_persisted_with_backoff_then_success_is_removed(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path = Path(td) / "sms_cancel_queue.json"
            sms_provider._ACTIVATION_META["12345"] = {
                "activation_time": "2026-08-11 10:38:03",
                "acquired_at": 1000.0,
                "cancel_at": 1305.0,
            }
            with (
                patch.object(sms_provider, "_CANCEL_QUEUE_PATH", queue_path),
                patch.object(sms_provider.time, "time", return_value=1100.0),
            ):
                sms_provider._enqueue_grizzly_cancel("12345")

            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["items"][0]["activation_time"], "2026-08-11 10:38:03")
            self.assertEqual(payload["items"][0]["next_attempt_at"], 1305.0)

            with (
                patch.object(sms_provider, "_CANCEL_QUEUE_PATH", queue_path),
                patch.object(sms_provider.time, "time", return_value=1400.0),
            ):
                done = sms_provider._update_cancel_job_after_attempt(
                    "12345", "early", "EARLY_CANCEL_DENIED"
                )
            self.assertFalse(done)
            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["items"][0]["next_attempt_at"], 1460.0)
            self.assertEqual(payload["items"][0]["early_denied_count"], 1)

            with (
                patch.object(sms_provider, "_CANCEL_QUEUE_PATH", queue_path),
                patch.object(sms_provider.time, "time", return_value=1460.0),
            ):
                done = sms_provider._update_cancel_job_after_attempt(
                    "12345", "cancelled", "ACCESS_CANCEL"
                )
            self.assertTrue(done)
            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["items"], [])

    def test_early_cancel_response_is_not_reported_as_success(self):
        http = _Http()
        with (
            patch.object(sms_provider, "_http", return_value=http),
            patch.object(sms_provider, "_request_grizzly", return_value="EARLY_CANCEL_DENIED"),
        ):
            outcome, raw = sms_provider._cancel_grizzly_once("12345")

        self.assertEqual(outcome, "early")
        self.assertEqual(raw, "EARLY_CANCEL_DENIED")
        self.assertTrue(http.closed)

    def test_uses_cancel_time_when_api_returns_one(self):
        meta = {"cancel_at_hint": 1700000300}

        self.assertEqual(sms_provider._planned_cancel_at(meta, 1700000000), 1700000305)

    def test_uses_retry_after_from_early_cancel_response(self):
        retry_at = sms_provider._retry_at_from_cancel_response(
            "EARLY_CANCEL_DENIED:90", 1700000000
        )

        self.assertEqual(retry_at, 1700000090)

    def test_default_sms_wait_extends_to_cancel_boundary(self):
        sms_provider._ACTIVATION_META["12345"] = {"cancel_at": 1305.0}
        with (
            patch.object(codex_config, "SMS_PROVIDER", "grizzly"),
            patch.object(codex_config, "SMS_CODE_WAIT", 120),
            patch.object(sms_provider.time, "time", return_value=1020.0),
        ):
            configured, effective = sms_provider._sms_code_wait_window("12345")

        self.assertEqual(configured, 120)
        self.assertEqual(effective, 285)

    def test_explicit_test_wait_is_not_extended(self):
        sms_provider._ACTIVATION_META["12345"] = {"cancel_at": 1305.0}
        with (
            patch.object(codex_config, "SMS_PROVIDER", "grizzly"),
            patch.object(sms_provider.time, "time", return_value=1020.0),
        ):
            configured, effective = sms_provider._sms_code_wait_window("12345", max_wait=10)

        self.assertEqual((configured, effective), (10, 10))

    def test_natural_terminal_order_is_removed_from_cancel_queue(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path = Path(td) / "sms_cancel_queue.json"
            sms_provider._ACTIVATION_META["12345"] = {
                "acquired_at": 1000.0,
                "cancel_at": 1305.0,
            }
            with (
                patch.object(sms_provider, "_CANCEL_QUEUE_PATH", queue_path),
                patch.object(sms_provider.time, "time", return_value=1305.0),
            ):
                sms_provider._enqueue_grizzly_cancel("12345")
                done = sms_provider._update_cancel_job_after_attempt(
                    "12345", "gone", "SmsProviderError: NO_ACTIVATION"
                )

            self.assertTrue(done)
            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["items"], [])


if __name__ == "__main__":
    unittest.main()
