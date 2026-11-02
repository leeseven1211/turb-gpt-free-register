import copy
import importlib
import json
import os
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.extract_link.contracts import ExtractRequest, ProviderConfig, ProviderError, ProviderHTTPError, request
from core.storage.runtime_config import decrypt_private_text


_TASK_ID = "98dd7474-ed58-4f0a-8cce-ab83037b1bd4"
_OTHER_ID = "617042d2-e372-45f0-b17a-d5e09d5d32ca"
_BASE = "https://ytc.example/openapi/v1"
_PAYMENT_URL = "https://pay.example/instructions?secret=payment-material"


class _Response:
    def __init__(self, status, data, headers=None):
        self.status_code = status
        self.data = data
        self.headers = headers or {}

    def json(self):
        return self.data


class _Transport:
    def __init__(self, responses, *, api_base=_BASE, calls=None):
        self.responses = responses
        self.api_base = api_base
        self.calls = [] if calls is None else calls

    def for_api_base(self, api_base):
        return _Transport(self.responses, api_base=api_base, calls=self.calls)

    def request(self, method, path, *, json=None, headers=None, timeout=30):
        self.calls.append((self.api_base, method, path, copy.deepcopy(json), dict(headers or {}), timeout))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _accepted(**fields):
    return {
        "accepted": 1, "pending": 1, "rejected": 0, "unknown": 0,
        "skipped": 0, "expired": 0, "invalid": 0, "cooldown": 0, "skippedItems": [],
        "items": [{"id": _TASK_ID, "index": 0, "status": "PENDING", "autoSubmit": True,
                   "billingMode": "yitiaochong", "scan": {"status": "NONE", "canCancel": False}, **fields}],
    }


def _config(**fields):
    return ProviderConfig(**{
        "provider_id": "anguang", "api_base": _BASE, "cdk": "original-api-key",
        "capabilities": {"extract": True, "payment": True, "auto_payment": True}, "timeout": 12,
        **fields,
    })


def _request(**fields):
    return ExtractRequest(**{
        "account_id": 7, "access_token": "original-access-token", "link_type": "upi",
        "mode": "auto_payment", "idempotency_key": "extract-run-123", **fields,
    })


def _intent(private):
    return json.loads(decrypt_private_text(private["anguang_request_encrypted"]))


class AnguangProviderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        try:
            self.module = importlib.import_module("core.extract_link.anguang.client")
        except ModuleNotFoundError:
            self.fail("暗光客户端尚未实现")

    def provider(self, responses, **config):
        transport = _Transport(list(responses))
        return self.module.AnguangProvider(_config(**config), transport), transport

    def test_create_checkpoints_exact_intent_before_submitting_one_token(self):
        provider, transport = self.provider([_accepted()])
        checkpoints = []

        def checkpoint(private):
            self.assertEqual(transport.calls, [])
            checkpoints.append(copy.deepcopy(private))

        job = provider.create_job(_request(submission_checkpoint=checkpoint))

        self.assertEqual(job.job_id, _TASK_ID)
        self.assertEqual(job.extraction_state, "queued")
        self.assertEqual(job.payment_state, "pending")
        self.assertEqual(len(checkpoints), 1)
        private = checkpoints[0]
        self.assertIs(private["anguang_submission_pending"], True)
        intent = _intent(private)
        self.assertEqual(intent["api_key"], "original-api-key")
        self.assertEqual(intent["api_base"], _BASE)
        request_id = intent["request_id"]
        self.assertEqual(str(uuid.UUID(request_id)), request_id)
        self.assertEqual(transport.calls[0][0:3], (_BASE, "POST", "/tasks"))
        self.assertEqual(transport.calls[0][3], {
            "requestId": request_id, "tokens": ["original-access-token"],
            "processingMode": "STANDARD", "planName": "chatgptplusplan",
            "paymentMethodType": "UPI", "autoSubmit": True, "autoRetry": False, "maxAmountCents": 0,
        })
        self.assertEqual(intent["body"], transport.calls[0][3])
        self.assertEqual(transport.calls[0][4]["Authorization"], "Bearer original-api-key")
        self.assertEqual(transport.calls[0][4]["User-Agent"], "Mozilla/5.0")
        self.assertIs(job.private_data["anguang_submission_pending"], False)
        self.assertIs(job.summary["remote_polling"], True)
        for secret in ("original-api-key", "original-access-token"):
            self.assertNotIn(secret, repr(job))
            self.assertNotIn(secret, json.dumps(job.summary))
            self.assertNotIn(secret, json.dumps(private))
            self.assertNotIn(secret, json.dumps(job.private_data))
        self.assertNotIn(_BASE, json.dumps(private))

    def test_checkpoint_failure_prevents_submission(self):
        provider, transport = self.provider([_accepted()])

        def checkpoint(_private):
            raise RuntimeError("持久化失败")

        with self.assertRaisesRegex(RuntimeError, "持久化失败"):
            provider.create_job(_request(submission_checkpoint=checkpoint))
        self.assertEqual(transport.calls, [])

    def test_request_id_is_stable_and_options_follow_documented_contract(self):
        provider, transport = self.provider([_accepted(), _accepted()])
        for _ in range(2):
            provider.create_job(_request(options={
                "processing_mode": "STRICT", "plan_name": "chatgptgoplan", "auto_retry": True,
                "payment_method": "UPI", "autoSubmit": False, "max_amount_cents": 99,
                "untrusted": "never-forward",
            }))
        first, second = (call[3] for call in transport.calls)
        self.assertEqual(first, second)
        self.assertEqual(first["processingMode"], "STRICT")
        self.assertEqual(first["planName"], "chatgptgoplan")
        self.assertIs(first["autoRetry"], True)
        self.assertIs(first["autoSubmit"], True)
        self.assertEqual(first["maxAmountCents"], 0)
        self.assertNotIn("untrusted", first)

    def test_unsupported_modes_link_types_invalid_options_and_missing_identity_never_submit(self):
        variants = [
            {"mode": "extract_only"}, {"mode": "manual_payment"}, {"link_type": "pix"},
            {"idempotency_key": ""}, {"access_token": ""},
            {"options": {"payment_method": "PIX"}}, {"options": {"processing_mode": "NEW"}},
            {"options": {"plan_name": "unsupported"}}, {"options": {"auto_retry": "false"}},
        ]
        for fields in variants:
            with self.subTest(fields=fields):
                provider, transport = self.provider([])
                with self.assertRaises(ProviderError):
                    provider.create_job(_request(**fields))
                self.assertEqual(transport.calls, [])
        for capability in ("extract", "payment", "auto_payment"):
            capabilities = {"extract": True, "payment": True, "auto_payment": True, capability: False}
            provider, transport = self.provider([], capabilities=capabilities)
            with self.assertRaises(ProviderError):
                provider.create_job(_request())
            self.assertEqual(transport.calls, [])

    def test_timeout_replays_exact_frozen_body_and_credentials_after_configuration_change(self):
        provider, transport = self.provider([TimeoutError("original-api-key original-access-token")])
        pending = provider.create_job(_request())
        self.assertIsNone(pending.job_id)
        self.assertIs(pending.summary["submission_receipt_pending"], True)
        self.assertIs(pending.summary["remote_polling"], True)
        self.assertIs(pending.private_data["latest_query_failed"], True)
        resumed_transport = _Transport([_accepted()], api_base="https://changed.example")
        resumed_provider = self.module.AnguangProvider(
            _config(api_base="https://changed.example", cdk="changed-key"), resumed_transport,
        )

        resumed = resumed_provider.get_status("", private_data=pending.private_data)

        self.assertEqual(resumed.job_id, _TASK_ID)
        self.assertEqual(resumed_transport.calls[0][0], _BASE)
        self.assertEqual(resumed_transport.calls[0][3], transport.calls[0][3])
        self.assertEqual(resumed_transport.calls[0][4]["Authorization"], "Bearer original-api-key")
        self.assertNotIn("original-api-key", repr(pending))
        self.assertNotIn("original-access-token", repr(pending))

    def test_replay_rejection_cannot_discard_an_earlier_uncertain_submission(self):
        for response in (
            _Response(401, {}), _Response(403, {}), _Response(404, {}),
            {"accepted": 0, "unknown": 0, "items": [], "skipped": 1,
             "skippedItems": [{"index": 0, "reason": "token_has_active_task"}]},
            {"items": [{"index": 0, "status": "REJECTED", "error": "token_has_active_task"}]},
        ):
            with self.subTest(response=response):
                provider, transport = self.provider([TimeoutError("test-only-timeout"), response, _accepted()])
                pending = provider.create_job(_request())
                replay = provider.get_status("", private_data=pending.private_data)
                self.assertIsNone(replay.job_id)
                self.assertIs(replay.private_data["anguang_submission_pending"], True)
                self.assertEqual(replay.private_data["anguang_request_encrypted"], pending.private_data["anguang_request_encrypted"])
                self.assertIs(replay.summary["submission_receipt_pending"], True)
                self.assertIs(replay.summary["remote_polling"], True)
                self.assertNotEqual(replay.extraction_state, "failed")
                self.assertNotEqual(replay.summary.get("outcome"), "REJECTED")
                recovered = provider.get_status("", private_data=replay.private_data)
                self.assertEqual(recovered.job_id, _TASK_ID)
                self.assertEqual(transport.calls[0][3], transport.calls[1][3])
                self.assertEqual(transport.calls[0][3], transport.calls[2][3])

    def test_http_create_rejections_finish_but_transient_failures_keep_same_intent(self):
        for status in (400, 401, 402, 403, 404, 413, 422):
            with self.subTest(status=status):
                provider, _ = self.provider([_Response(status, {"detail": "original-access-token original-api-key"})])
                job = provider.create_job(_request())
                self.assertEqual(job.extraction_state, "failed")
                self.assertIs(job.summary["remote_polling"], False)
                self.assertIs(job.private_data["anguang_submission_pending"], False)
                self.assertNotIn("original-api-key", repr(job))
                self.assertNotIn("original-access-token", repr(job))
        for status in (409, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                provider, transport = self.provider([_Response(status, {}), _accepted()])
                pending = provider.create_job(_request())
                self.assertIs(pending.summary["remote_polling"], True)
                self.assertIs(pending.private_data["anguang_submission_pending"], True)
                self.assertEqual(pending.private_data["latest_query_http_status"], status)
                resumed = provider.get_status("", private_data=pending.private_data)
                self.assertEqual(resumed.job_id, _TASK_ID)
                self.assertEqual(transport.calls[0][3], transport.calls[1][3])

    def test_skipped_expired_invalid_and_cooldown_are_not_retried_as_new_orders(self):
        for field in ("skipped", "expired", "invalid", "cooldown", "rejected"):
            with self.subTest(field=field):
                response = {"accepted": 0, "unknown": 0, "items": [], field: 1,
                            "skippedItems": [{"index": 0, "retryAt": 1800000000}]}
                provider, transport = self.provider([response])
                job = provider.create_job(_request())
                self.assertEqual(job.extraction_state, "failed")
                self.assertIs(job.private_data["anguang_submission_pending"], False)
                self.assertIs(job.summary["remote_polling"], False)
                self.assertEqual(len(transport.calls), 1)

    def test_malformed_unknown_or_wrong_index_create_remains_recoverable(self):
        for response in ({}, {"items": [], "unknown": 1}, _accepted(index=1), _accepted(id="private-token")):
            with self.subTest(response=response):
                provider, transport = self.provider([response])
                job = provider.create_job(_request())
                self.assertIsNone(job.job_id)
                self.assertIs(job.summary["remote_polling"], True)
                self.assertIs(job.private_data["anguang_submission_pending"], True)
                self.assertEqual(len(transport.calls), 1)
                self.assertNotIn("private-token", repr(job))

    def test_existing_id_only_queries_original_order_and_credentials(self):
        provider, transport = self.provider([_accepted(), {"id": _TASK_ID, "status": "RUNNING", "scan": {"status": "NONE"}}])
        created = provider.create_job(_request())
        provider.config = _config(cdk="changed-key", api_base="https://changed.example")

        job = provider.get_status(_TASK_ID, private_data=created.private_data)

        self.assertEqual(job.job_id, _TASK_ID)
        self.assertEqual(job.extraction_state, "running")
        self.assertEqual(transport.calls[-1][0:3], (_BASE, "GET", f"/tasks/{_TASK_ID}"))
        self.assertIsNone(transport.calls[-1][3])
        self.assertEqual(transport.calls[-1][4]["Authorization"], "Bearer original-api-key")
        self.assertEqual([call[1] for call in transport.calls], ["POST", "GET"])

    def test_extraction_succeeded_does_not_confirm_scan_or_plus(self):
        provider, _ = self.provider([{
            "id": _TASK_ID, "status": "SUCCEEDED", "autoSubmit": True,
            "paymentStatus": "succeeded", "plusVerificationStatus": "CONFIRMED",
            "scan": {"status": "verifying"},
            "result": {"hostedUrl": "https://checkout.example/session", "amount": 0, "currency": "inr",
                       "paymentArtifact": {"url": _PAYMENT_URL, "data": "upi://pay?pa=merchant&secret=private",
                                           "imageUrlPng": "https://pay.example/qr.png"}},
        }])

        job = provider.get_status(_TASK_ID)

        self.assertEqual(job.extraction_state, "succeeded")
        self.assertEqual(job.payment_state, "pending")
        self.assertEqual(job.payment_links[0], _PAYMENT_URL)
        self.assertEqual(job.payment_artifact["payment_url"], _PAYMENT_URL)
        self.assertEqual(job.payment_artifact["qr_data"], "upi://pay?pa=merchant&secret=private")
        self.assertIs(job.summary["remote_polling"], True)
        self.assertNotIn("plus_status", job.summary)
        self.assertNotIn("plus_verification_status", job.summary)
        self.assertNotIn("payment-material", repr(job))

    def test_only_completed_scan_confirms_payment(self):
        for status, expected, polling in (
            ("NONE", "pending", True), ("READY", "pending", True), ("AWAITING_FUNDS", "pending", True),
            ("AWAITING_SLOT", "pending", True), ("SUBMITTING", "pending", True),
            ("awaiting_worker", "pending", True), ("claimed", "pending", True),
            ("verifying", "pending", True), ("completed", "succeeded", False),
            ("failed", "failed", False), ("expired", "failed", False), ("cancelled", "failed", False),
            ("rejected", "failed", False), ("UNKNOWN", "unknown", True), ("NEW_STATUS", "unknown", True),
        ):
            with self.subTest(status=status):
                provider, transport = self.provider([{"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": status}}])
                job = provider.get_status(_TASK_ID)
                self.assertEqual(job.payment_state, expected)
                self.assertEqual(job.summary["remote_polling"], polling)
                self.assertEqual(job.summary["automatic_payment_terminal"], not polling)
                self.assertEqual([call[1] for call in transport.calls], ["GET"])

    def test_scan_failure_preserves_previously_obtained_material(self):
        provider, _ = self.provider([
            {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "claimed"},
             "result": {"paymentArtifact": {"url": _PAYMENT_URL}}},
            {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "failed"}},
        ])
        first = provider.get_status(_TASK_ID)
        failed = provider.get_status(_TASK_ID, private_data=first.private_data)
        self.assertEqual(failed.extraction_state, "succeeded")
        self.assertEqual(failed.payment_state, "failed")
        self.assertEqual(failed.payment_links, (_PAYMENT_URL,))
        self.assertEqual(failed.payment_artifact["payment_url"], _PAYMENT_URL)

    def test_remote_retry_remains_on_same_task_and_does_not_finish_early(self):
        for status in ("QUEUED", "RUNNING", "SCANNING"):
            with self.subTest(status=status):
                provider, transport = self.provider([{
                    "id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "failed"},
                    "retry": {"status": status, "count": 1},
                }])
                job = provider.get_status(_TASK_ID)
                self.assertEqual(job.extraction_state, "succeeded")
                self.assertEqual(job.payment_state, "pending")
                self.assertIs(job.summary["remote_polling"], True)
                self.assertEqual([call[1] for call in transport.calls], ["GET"])

    def test_retry_progress_does_not_expose_a_terminal_extraction_failure(self):
        for status in ("QUEUED", "RUNNING", "SCANNING"):
            with self.subTest(status=status):
                provider, _ = self.provider([{
                    "id": _TASK_ID, "status": "FAILED", "scan": {"status": "failed"},
                    "retry": {"status": status, "count": 1},
                }])
                job = provider.get_status(_TASK_ID)
                self.assertEqual(job.extraction_state, "running")
                self.assertEqual(job.payment_state, "pending")
                self.assertIs(job.summary["remote_polling"], True)
                self.assertNotIn("remote_terminal_failure", job.summary)

    def test_uncertain_scan_is_not_finalized_by_extraction_failure(self):
        provider, transport = self.provider([{
            "id": _TASK_ID, "status": "FAILED", "scan": {"status": "UNKNOWN"},
        }])
        job = provider.get_status(_TASK_ID)
        self.assertEqual(job.payment_state, "unknown")
        self.assertIs(job.summary["remote_polling"], True)
        self.assertIs(job.summary["automatic_payment_terminal"], False)
        self.assertNotIn("remote_terminal_failure", job.summary)
        self.assertEqual([call[1] for call in transport.calls], ["GET"])

    def test_completed_scan_wins_over_stale_remote_retry_progress(self):
        provider, _ = self.provider([{
            "id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "completed"},
            "retry": {"status": "SCANNING", "count": 1},
        }])
        job = provider.get_status(_TASK_ID)
        self.assertEqual(job.payment_state, "succeeded")
        self.assertIs(job.summary["remote_polling"], False)

    def test_later_remote_failure_preserves_record_of_successful_extraction(self):
        provider, _ = self.provider([
            {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "claimed"},
             "result": {"paymentArtifact": {"url": _PAYMENT_URL}}},
            {"id": _TASK_ID, "status": "FAILED", "scan": {"status": "failed"},
             "retry": {"status": "FAILED", "count": 1}},
        ])
        first = provider.get_status(_TASK_ID)
        failed = provider.get_status(_TASK_ID, private_data=first.private_data)
        self.assertEqual(failed.extraction_state, "succeeded")
        self.assertEqual(failed.payment_state, "failed")
        self.assertEqual(failed.payment_links, (_PAYMENT_URL,))

    def test_query_failure_retains_material_and_never_submits(self):
        for error in (TimeoutError("original-api-key"), _Response(403, {}), _Response(404, {}),
                      _Response(429, {}), _Response(503, {}), {"id": _OTHER_ID, "status": "SUCCEEDED"}):
            with self.subTest(error=error):
                provider, transport = self.provider([
                    {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "claimed"},
                     "result": {"paymentArtifact": {"url": _PAYMENT_URL}}}, error,
                ])
                first = provider.get_status(_TASK_ID)
                pending = provider.get_status(_TASK_ID, private_data=first.private_data)
                self.assertEqual(pending.job_id, _TASK_ID)
                self.assertEqual(pending.payment_links, (_PAYMENT_URL,))
                self.assertIs(pending.private_data["latest_query_failed"], True)
                self.assertIs(pending.summary["remote_polling"], True)
                self.assertEqual([call[1] for call in transport.calls], ["GET", "GET"])
                self.assertNotIn("original-api-key", repr(pending))

    def test_query_failure_preserves_confirmed_payment_and_leaves_plus_independent(self):
        from core.extract_link.payment_confirmation import payment_scan_completed

        for error in (TimeoutError("test-only-timeout"), _Response(429, {"retryAfter": 120}), _Response(503, {})):
            with self.subTest(error=error):
                provider, transport = self.provider([
                    {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "completed"},
                     "plusVerificationStatus": "CONFIRMED",
                     "result": {"paymentArtifact": {"url": _PAYMENT_URL}}}, error,
                ])
                first = provider.get_status(_TASK_ID)
                restored = provider.get_status(_TASK_ID, private_data=first.private_data)
                self.assertEqual(restored.extraction_state, "succeeded")
                self.assertEqual(restored.payment_state, "succeeded")
                self.assertEqual(restored.payment_links, (_PAYMENT_URL,))
                self.assertEqual(restored.payment_artifact["payment_status"], "completed")
                self.assertIs(restored.private_data["latest_query_failed"], True)
                self.assertIs(restored.summary["remote_polling"], False)
                self.assertIs(restored.summary["automatic_payment_terminal"], True)
                self.assertIs(restored.summary["automatic_payment_requires_reconcile"], False)
                self.assertEqual(restored.summary["automatic_payment_status"], "completed")
                self.assertIs(payment_scan_completed({
                    "extraction_state": restored.extraction_state, "payment_state": restored.payment_state,
                    "summary": restored.summary,
                }, provider_id="anguang"), True)
                self.assertNotIn("plus_status", restored.summary)
                self.assertNotIn("plus_verification_status", restored.summary)
                self.assertEqual([call[1] for call in transport.calls], ["GET", "GET"])

    def test_query_failure_preserves_known_payment_failure_without_resuming_polling(self):
        provider, transport = self.provider([
            {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "failed"},
             "result": {"paymentArtifact": {"url": _PAYMENT_URL}}}, TimeoutError("test-only-timeout"),
        ])
        first = provider.get_status(_TASK_ID)
        restored = provider.get_status(_TASK_ID, private_data=first.private_data)
        self.assertEqual(restored.payment_state, "failed")
        self.assertEqual(restored.payment_links, (_PAYMENT_URL,))
        self.assertIs(restored.summary["remote_polling"], False)
        self.assertIs(restored.summary["automatic_payment_terminal"], True)
        self.assertIs(restored.summary["automatic_payment_requires_reconcile"], False)
        self.assertEqual([call[1] for call in transport.calls], ["GET", "GET"])

    def test_incomplete_successful_query_preserves_confirmed_payment_and_material(self):
        from core.extract_link.payment_confirmation import payment_scan_completed

        for fields in ({}, {"scan": {}}, {"scan": {"status": "UNKNOWN"}},
                       {"scan": {"status": "NEW_STATUS"}}, {"scan": {"status": "verifying"}}):
            with self.subTest(fields=fields):
                provider, transport = self.provider([
                    {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "completed"},
                     "result": {"paymentArtifact": {"url": _PAYMENT_URL}}},
                    {"id": _TASK_ID, "status": "SUCCEEDED", **fields},
                ])
                first = provider.get_status(_TASK_ID)
                restored = provider.get_status(_TASK_ID, private_data=first.private_data)
                self.assertEqual(restored.extraction_state, "succeeded")
                self.assertEqual(restored.payment_state, "succeeded")
                self.assertEqual(restored.payment_links, (_PAYMENT_URL,))
                self.assertEqual(restored.payment_artifact["payment_status"], "completed")
                self.assertIs(restored.summary["remote_polling"], False)
                self.assertIs(restored.summary["automatic_payment_terminal"], True)
                self.assertIs(restored.summary["automatic_payment_requires_reconcile"], False)
                self.assertIs(payment_scan_completed({
                    "extraction_state": restored.extraction_state, "payment_state": restored.payment_state,
                    "summary": restored.summary,
                }, provider_id="anguang"), True)
                self.assertNotIn("plus_status", restored.summary)
                self.assertNotIn("plus_verification_status", restored.summary)
                self.assertEqual([call[1] for call in transport.calls], ["GET", "GET"])

    def test_explicit_later_scan_failure_keeps_existing_failure_semantics(self):
        provider, transport = self.provider([
            {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "completed"},
             "result": {"paymentArtifact": {"url": _PAYMENT_URL}}},
            {"id": _TASK_ID, "status": "SUCCEEDED", "scan": {"status": "failed"}},
        ])
        first = provider.get_status(_TASK_ID)
        failed = provider.get_status(_TASK_ID, private_data=first.private_data)
        self.assertEqual(failed.payment_state, "failed")
        self.assertEqual(failed.payment_links, (_PAYMENT_URL,))
        self.assertIs(failed.summary["remote_polling"], False)
        self.assertEqual([call[1] for call in transport.calls], ["GET", "GET"])

    def test_completed_scan_proves_extraction_despite_conflicting_failure_status(self):
        from core.extract_link.payment_confirmation import payment_scan_completed

        provider, transport = self.provider([{
            "id": _TASK_ID, "status": "FAILED", "scan": {"status": "completed"},
            "result": {"paymentArtifact": {"url": _PAYMENT_URL}}, "plusVerificationStatus": "CONFIRMED",
        }])
        job = provider.get_status(_TASK_ID)
        self.assertEqual(job.extraction_state, "succeeded")
        self.assertEqual(job.payment_state, "succeeded")
        self.assertIs(job.summary["remote_polling"], False)
        self.assertNotIn("remote_terminal_failure", job.summary)
        self.assertIs(payment_scan_completed({
            "extraction_state": job.extraction_state, "payment_state": job.payment_state, "summary": job.summary,
        }, provider_id="anguang"), True)
        self.assertNotIn("plus_status", job.summary)
        self.assertNotIn("plus_verification_status", job.summary)
        self.assertEqual([call[1] for call in transport.calls], ["GET"])

    def test_unknown_status_does_not_finish_or_leak_remote_payload(self):
        provider, transport = self.provider([{
            "id": _TASK_ID, "status": "NEW_original-api-key", "scan": {"status": "UNKNOWN"},
            "failureCode": "accessToken=other-secret", "currentStep": "original-access-token",
            "error": {"message": "Bearer other-api-key https://pay.example/private account@example.test"},
        }])
        job = provider.get_status(_TASK_ID)
        self.assertEqual(job.extraction_state, "unknown")
        self.assertEqual(job.payment_state, "unknown")
        self.assertIs(job.summary["remote_polling"], True)
        self.assertEqual([call[1] for call in transport.calls], ["GET"])
        for secret in ("original-api-key", "original-access-token", "other-secret", "other-api-key", "account@example.test"):
            self.assertNotIn(secret, repr(job))

    def test_missing_recovery_intent_or_invalid_job_identity_never_submits(self):
        for job_ref, private in (("", {}), ("not-a-uuid", {}), ("", {"anguang_submission_pending": True}),
                                 ("", {"anguang_request_body": {"requestId": _TASK_ID, "tokens": []}})):
            with self.subTest(job_ref=job_ref):
                provider, transport = self.provider([])
                with self.assertRaises(ProviderError):
                    provider.get_status(job_ref, private_data=private)
                self.assertEqual(transport.calls, [])

    def test_cleared_current_config_does_not_replace_frozen_credentials(self):
        provider, transport = self.provider([_accepted(), {"id": _TASK_ID, "status": "RUNNING"}])
        created = provider.create_job(_request())
        provider.config = _config(cdk="", api_base="")
        job = provider.get_status(_TASK_ID, private_data=created.private_data)
        self.assertEqual(job.job_id, _TASK_ID)
        self.assertEqual(transport.calls[-1][0], _BASE)
        self.assertEqual(transport.calls[-1][4]["Authorization"], "Bearer original-api-key")

    def test_missing_encryption_key_or_corrupt_ciphertext_never_sends_a_request(self):
        provider, transport = self.provider([])
        checkpoints = []
        with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": ""}):
            with self.assertRaises(ProviderError):
                provider.create_job(_request(submission_checkpoint=checkpoints.append))
        self.assertEqual(checkpoints, [])
        for job_ref in ("", _TASK_ID):
            with self.subTest(job_ref=job_ref):
                with self.assertRaises(ProviderError):
                    provider.get_status(job_ref, private_data={
                        "anguang_submission_pending": True, "anguang_request_encrypted": "corrupt-original-access-token",
                    })
        self.assertEqual(transport.calls, [])

    def test_create_rate_limit_waits_for_header_or_json_delay_before_replaying(self):
        for response, delay in (
            (_Response(429, {}, {"Retry-After": "120"}), 120),
            (_Response(429, {"retryAfter": 90}), 90),
            (_Response(429, {}, {"Retry-After": "Tue, 14 Nov 2023 22:15:20 GMT"}), 120),
        ):
            with self.subTest(delay=delay):
                provider, transport = self.provider([response, _accepted()])
                with patch.object(self.module.time, "time", return_value=1700000000):
                    pending = provider.create_job(_request())
                    self.assertEqual(pending.private_data["anguang_retry_not_before"], 1700000000 + delay)
                    still_waiting = provider.get_status("", private_data=pending.private_data)
                    self.assertIs(still_waiting.summary["remote_polling"], True)
                    self.assertEqual(len(transport.calls), 1)
                with patch.object(self.module.time, "time", return_value=1700000000 + delay + 1):
                    resumed = provider.get_status("", private_data=pending.private_data)
                self.assertEqual(resumed.job_id, _TASK_ID)
                self.assertEqual(transport.calls[0][3], transport.calls[1][3])

    def test_query_rate_limit_waits_without_changing_order_or_credentials(self):
        provider, transport = self.provider([
            _Response(429, {"retryAfter": 120}), {"id": _TASK_ID, "status": "RUNNING"},
        ])
        with patch.object(self.module.time, "time", return_value=1700000000):
            pending = provider.get_status(_TASK_ID)
            self.assertEqual(pending.private_data["anguang_retry_not_before"], 1700000120)
            provider.get_status(_TASK_ID, private_data=pending.private_data)
            self.assertEqual(len(transport.calls), 1)
        with patch.object(self.module.time, "time", return_value=1700000121):
            resumed = provider.get_status(_TASK_ID, private_data=pending.private_data)
        self.assertEqual(resumed.job_id, _TASK_ID)
        self.assertEqual([call[1] for call in transport.calls], ["GET", "GET"])

    def test_malformed_remote_status_fields_are_unknown_without_leaking_or_crashing(self):
        for fields in ({"status": {}}, {"status": []}, {"scan": {"status": {}}},
                       {"scan": {"status": []}}, {"retry": {"status": {}}}):
            with self.subTest(fields=fields):
                provider, transport = self.provider([{"id": _TASK_ID, **fields}])
                job = provider.get_status(_TASK_ID)
                self.assertEqual(job.job_id, _TASK_ID)
                self.assertIs(job.summary["remote_polling"], True)
                self.assertEqual([call[1] for call in transport.calls], ["GET"])

    def test_separate_payment_start_is_unsupported(self):
        provider, transport = self.provider([])
        with self.assertRaises(ProviderError):
            provider.start_payment(_TASK_ID, {})
        self.assertEqual(transport.calls, [])

    def test_transport_ignores_environment_proxy_and_never_follows_redirects(self):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.path, self.headers.get("Authorization"), self.headers.get("User-Agent")))
                if self.path.endswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/stolen")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"safe":true}')

            def log_message(self, _format, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/openapi/v1"
            transport = self.module.AnguangHTTPTransport("https://changed.invalid").for_api_base(base)
            with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "http_proxy": "http://127.0.0.1:1", "NO_PROXY": "", "no_proxy": ""}):
                result = request(transport, "GET", "/safe", headers={"Authorization": "Bearer test-only-key"})
                self.assertEqual(result, {"safe": True})
                with self.assertRaises(ProviderHTTPError) as error:
                    request(transport, "GET", "/redirect", headers={"Authorization": "Bearer test-only-key"})
            self.assertEqual(error.exception.http_status, 302)
            self.assertEqual([call[0] for call in calls], ["/openapi/v1/safe", "/openapi/v1/redirect"])
            self.assertEqual(calls[0][1:], ("Bearer test-only-key", "Mozilla/5.0"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
