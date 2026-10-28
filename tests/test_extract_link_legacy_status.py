"""虾扯蛋链真实状态查询与 UPI 结果字段契约，不访问真实账号或远端。"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import unittest

from core.extract_link_providers.contracts import ExtractRequest, ProviderConfig, ProviderError, ProviderHTTPError
from core.extract_link_providers.legacy import LegacyProvider


class _Transport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, path, *, json=None, headers=None, timeout=None):
        self.calls.append((method, path, json, timeout))
        return self.response


def _provider(response):
    transport = _Transport(response)
    return LegacyProvider(ProviderConfig(
        "legacy", "https://provider.example.test", "synthetic-cdk",
        {"extract": True}, timeout=7,
    ), transport), transport


class LegacyStatusTests(unittest.TestCase):
    def test_upi_creation_only_extracts_and_never_submits_payment(self):
        provider, transport = _provider({"ok": True, "job_id": "created-job", "queue_position": 2})
        result = provider.create_job(ExtractRequest(1, "synthetic-token", "upi", "extract_only"))
        self.assertEqual("queued", result.extraction_state)
        self.assertEqual(("POST", "/api/extract", {
            "link_type": "upi", "cdk": "synthetic-cdk", "token": "synthetic-token",
        }, 7), transport.calls[0])

    def test_status_uses_bounded_json_read_and_encoded_job_reference(self):
        provider, transport = _provider({
            "ok": True, "done": True, "job_id": "job/ref", "status": "success",
            "result": {"long_url": "https://payment.example.test/upi"},
        })
        result = provider.get_status("job/ref")
        self.assertEqual("succeeded", result.extraction_state)
        self.assertEqual(("https://payment.example.test/upi",), result.links)
        method, path, body, timeout = transport.calls[0]
        self.assertEqual("GET", method)
        self.assertEqual("/api/jobs/job%2Fref", urlsplit(path).path)
        self.assertEqual({"cdk": ["synthetic-cdk"]}, parse_qs(urlsplit(path).query))
        self.assertIsNone(body)
        self.assertEqual(7, timeout)

    def test_native_upi_fields_keep_exact_copy_code_and_all_payment_material(self):
        copy_code = "upi://pay?pa=synthetic@example.test&am=0&tn=Exact%2BToken"
        result = LegacyProvider._job({"status": "success", "result": {
            "long_url": "https://payment.example.test/upi",
            "copy_paste": copy_code,
            "image_url_png": "https://qr.example.test/upi.png",
            "image_url_svg": "https://qr.example.test/upi.svg",
            "amount": 0, "currency": "INR",
            "expires_at": "2026-10-28T13:00:00Z",
        }}, "upi-job")
        self.assertEqual("succeeded", result.extraction_state)
        self.assertEqual(("https://payment.example.test/upi",), result.links)
        self.assertEqual(result.links, result.payment_links)
        self.assertEqual({
            "payment_page_url": "https://payment.example.test/upi", "qr_data": copy_code,
            "qr_image_url_png": "https://qr.example.test/upi.png",
            "qr_image_url_svg": "https://qr.example.test/upi.svg",
            "amount": 0, "currency": "INR", "expires_at": "2026-10-28T13:00:00Z",
        }, result.payment_artifact)
        self.assertNotIn(copy_code, repr(result))

    def test_created_and_submitted_are_pending_instead_of_unknown(self):
        for status in ("created", "submitted"):
            with self.subTest(status=status):
                result = LegacyProvider._job({"ok": True, "done": False, "status": status}, "pending-job")
                self.assertEqual("queued", result.extraction_state)

    def test_done_with_result_is_success_even_without_redundant_status(self):
        result = LegacyProvider._job({"ok": True, "done": True, "result": {
            "long_url": "https://payment.example.test/upi",
        }}, "done-job")
        self.assertEqual("succeeded", result.extraction_state)

    def test_done_with_metadata_or_error_payload_does_not_claim_extraction_success(self):
        for payload in ({"cdk_remaining": 0}, {"error": "UPI failed"}, {"long_url": "javascript:invalid"}):
            with self.subTest(payload=payload):
                result = LegacyProvider._job({"ok": True, "done": True, "result": payload}, "empty-job")
                self.assertEqual("unknown", result.extraction_state)
                self.assertEqual("missing_payment_material", result.summary["failure_code"])
                self.assertEqual("missing_payment_material", result.summary["failure_type"])
                self.assertIn("未返回可用支付材料", result.summary["failure_message"])

    def test_done_with_real_qr_material_can_succeed_without_web_link(self):
        result = LegacyProvider._job({"ok": True, "done": True, "result": {
            "copy_paste": "upi://pay?pa=synthetic@example.test&am=0",
        }}, "qr-only-job")
        self.assertEqual("succeeded", result.extraction_state)
        self.assertEqual("upi://pay?pa=synthetic@example.test&am=0", result.payment_artifact["qr_data"])

    def test_http_success_with_query_rejection_raises_without_failing_original_job(self):
        provider, _ = _provider({"ok": False, "code": "cdk_invalid", "error": {
            "message": "查询 CDK 无效 synthetic-cdk https://private.example.test/path",
        }})
        with self.assertRaises(ProviderError) as error:
            provider.get_status("original-job")
        self.assertEqual("extract_status_query_rejected", error.exception.code)
        self.assertEqual("cdk_invalid", error.exception.failure_code)
        self.assertIn("状态查询被拒绝", str(error.exception))
        self.assertIn("查询 CDK 无效", str(error.exception))
        self.assertNotIn("synthetic-cdk", str(error.exception))
        self.assertNotIn("https://private.example.test/path", str(error.exception))

    def test_remote_failure_keeps_classified_reason_and_removes_credentials(self):
        provider, _ = _provider({"ok": True, "done": True, "status": "failed", "error": {
            "code": "UPI_TIMEOUT", "message": "上游 UPI 超时 synthetic-cdk token=synthetic-token person@example.test https://private.example.test/order",
        }})
        result = provider.get_status("failed-job")
        self.assertEqual("failed", result.extraction_state)
        self.assertEqual("UPI_TIMEOUT", result.summary["failure_code"])
        self.assertEqual("upstream_timeout", result.summary["failure_type"])
        self.assertIn("上游 UPI 超时", result.summary["failure_message"])
        for private in ("synthetic-cdk", "synthetic-token", "person@example.test", "https://private.example.test/order"):
            self.assertNotIn(private, result.summary["failure_message"])
        self.assertTrue(result.summary["remote_terminal_failure"])

    def test_string_failure_is_classified_without_remote_code(self):
        result = LegacyProvider._job({"status": "failed", "error": "UPI 上游请求超时"}, "failed-job")
        self.assertEqual("upstream_timeout", result.summary["failure_code"])
        self.assertEqual("UPI 上游请求超时", result.summary["failure_message"])

    def test_explicit_creation_rejection_is_failed_not_unknown(self):
        provider, _ = _provider({"ok": False, "code": "token_task_in_progress", "error": "该 token 已有未完成任务"})
        result = provider.create_job(ExtractRequest(1, "synthetic-token", "upi", "extract_only"))
        self.assertEqual("failed", result.extraction_state)
        self.assertEqual("REJECTED", result.summary["outcome"])
        self.assertEqual("token_task_in_progress", result.summary["failure_code"])
        self.assertEqual("task_in_progress", result.summary["failure_type"])

    def test_http_rejection_preserves_remote_reason_but_server_failure_stays_unknown(self):
        provider, _ = _provider(SimpleNamespace(status_code=409, json=lambda: {
            "code": "token_task_in_progress", "error": "该 token 已有未完成任务",
        }))
        result = provider.create_job(ExtractRequest(1, "synthetic-token", "upi", "extract_only"))
        self.assertEqual("REJECTED", result.summary["outcome"])
        self.assertIn("未完成任务", result.summary["failure_message"])
        provider, _ = _provider(SimpleNamespace(status_code=500, json=lambda: {"error": "synthetic-private-server-error"}))
        with self.assertRaises(ProviderHTTPError) as error:
            provider.create_job(ExtractRequest(1, "synthetic-token", "upi", "extract_only"))
        self.assertNotIn("synthetic-private-server-error", str(error.exception))


class LegacyAutomaticPaymentTests(unittest.TestCase):
    def provider(self, response):
        provider, transport = _provider(response)
        provider.config = replace(provider.config,
            capabilities={"extract": True, "payment": True, "auto_payment": True},
            payment_cdk="synthetic-payment-cdk")
        return provider, transport

    def test_upi_automatic_payment_creation_sends_separate_cdk_and_keeps_mode(self):
        provider, transport = self.provider({"ok": True, "job_id": "auto-job"})
        result = provider.create_job(ExtractRequest(1, "synthetic-token", "upi", "auto_payment"))
        self.assertEqual({
            "link_type": "upi", "cdk": "synthetic-cdk", "token": "synthetic-token",
            "payment_platform": {"enabled": True, "platform_id": "xiachedan_plus", "cdk": "synthetic-payment-cdk"},
        }, transport.calls[0][2])
        self.assertEqual("queued", result.extraction_state)
        self.assertEqual("pending", result.payment_state)
        self.assertEqual("auto_payment", result.private_data["mode"])
        self.assertNotIn("synthetic-payment-cdk", repr(result))

    def test_other_modes_do_not_submit_payment_even_when_payment_cdk_is_configured(self):
        for mode in ("extract_only", "manual_payment"):
            with self.subTest(mode=mode):
                provider, transport = self.provider({"ok": True, "job_id": "plain-job"})
                result = provider.create_job(ExtractRequest(1, "synthetic-token", "upi", mode))
                self.assertNotIn("payment_platform", transport.calls[0][2])
                self.assertNotIn("synthetic-payment-cdk", repr(transport.calls[0][2]))
                self.assertEqual("not_started", result.payment_state)
                self.assertEqual(mode, result.private_data["mode"])

    def test_unsupported_type_or_missing_payment_permission_never_submits(self):
        cases = (
            ({"extract": True, "payment": True, "auto_payment": True}, "synthetic-payment-cdk", "pix"),
            ({"extract": True, "payment": True, "auto_payment": False}, "synthetic-payment-cdk", "upi"),
            ({"extract": True, "payment": False, "auto_payment": True}, "synthetic-payment-cdk", "upi"),
            ({"extract": True, "payment": True, "auto_payment": True}, "", "upi"),
        )
        for capabilities, cdk, link_type in cases:
            with self.subTest(capabilities=capabilities, cdk=bool(cdk), link_type=link_type):
                provider, transport = self.provider({"ok": True, "job_id": "never-created"})
                provider.config = replace(provider.config, capabilities=capabilities, payment_cdk=cdk)
                with self.assertRaises(ProviderError):
                    provider.create_job(ExtractRequest(1, "synthetic-token", link_type, "auto_payment"))
                self.assertFalse(transport.calls)

    def test_payment_sync_reads_existing_order_and_only_submitted_remains_pending(self):
        provider, transport = self.provider({"ok": True, "result": {
            "long_url": "https://payment.example.test/upi",
        }, "payment_platform": {"status": "submitted", "order_id": "synthetic-order", "order_status_label": "等待扫码"}})
        transport.response["status"] = "success"
        provider.get_status("original-job", private_data={"mode": "auto_payment"})
        result = provider.get_automatic_payment_status("original-job")
        self.assertEqual(("POST", "/api/payment-status", {
            "job_id": "original-job", "cdk": "synthetic-cdk", "payment_cdk": "synthetic-payment-cdk",
        }, 7), transport.calls[-1])
        self.assertEqual("pending", result.payment_state)
        self.assertEqual(("https://payment.example.test/upi",), result.links)
        self.assertEqual("auto_payment", result.private_data["mode"])

    def test_job_status_preserves_pending_failed_and_unknown_payment_facts(self):
        for remote, wanted in (("waiting", "pending"), ("submitting", "pending"),
                               ("submitted", "pending"), ("failed", "failed"), ("unknown", "unknown")):
            with self.subTest(remote=remote):
                result = LegacyProvider._job({"status": "success", "result": {
                    "long_url": "https://payment.example.test/upi",
                    "payment_platform": {"status": remote, "order_status_label": "支付成功"},
                }}, "existing-job")
                self.assertEqual("succeeded", result.extraction_state)
                self.assertEqual(wanted, result.payment_state)

    def test_get_status_retains_private_recovery_mode_and_extract_only_never_queries_payment(self):
        provider, transport = self.provider({"ok": True, "status": "success", "result": {
            "long_url": "https://payment.example.test/upi",
        }})
        result = provider.get_status("extract-job", private_data={"mode": "extract_only", "existing_reference": "keep"})
        self.assertEqual({"mode": "extract_only", "existing_reference": "keep"}, result.private_data)
        with self.assertRaises(ProviderError):
            provider.get_automatic_payment_status("extract-job")
        self.assertEqual(1, len(transport.calls))

    def test_payment_query_rejection_keeps_original_task_and_redacts_both_cdks(self):
        provider, transport = self.provider({"ok": True, "status": "success", "result": {
            "long_url": "https://payment.example.test/upi", "payment_platform": {"status": "submitted"},
        }})
        provider.get_status("original-job", private_data={"mode": "auto_payment"})
        transport.response = {"ok": False, "code": "payment_cdk_invalid", "error":
            "支付查询失败 synthetic-cdk synthetic-payment-cdk"}
        with self.assertRaises(ProviderError) as error:
            provider.get_automatic_payment_status("original-job")
        self.assertEqual("extract_status_query_rejected", error.exception.code)
        self.assertEqual("payment_cdk_invalid", error.exception.failure_code)
        self.assertNotIn("synthetic-cdk", str(error.exception))
        self.assertNotIn("synthetic-payment-cdk", str(error.exception))

    def test_new_queued_job_does_not_query_payment_before_link_exists(self):
        provider, transport = self.provider({"ok": True, "job_id": "queued-job"})
        provider.create_job(ExtractRequest(1, "synthetic-token", "upi", "auto_payment"))
        result = provider.get_automatic_payment_status("queued-job")
        self.assertEqual("queued", result.extraction_state)
        self.assertEqual("pending", result.payment_state)
        self.assertEqual([("POST", "/api/extract")], [(call[0], call[1]) for call in transport.calls])

    def test_missing_mode_is_rejected_before_payment_query(self):
        provider, transport = self.provider({"ok": True, "result": {}})
        with self.assertRaises(ProviderError):
            provider.get_automatic_payment_status("unknown-job")
        self.assertFalse(transport.calls)

    def test_waiting_without_an_order_does_not_trigger_payment_sync(self):
        provider, transport = self.provider({"ok": True, "status": "success", "result": {
            "long_url": "https://payment.example.test/upi", "payment_platform": {"status": "waiting"},
        }})
        provider.get_status("waiting-job", private_data={"mode": "auto_payment"})
        result = provider.get_automatic_payment_status("waiting-job")
        self.assertEqual("pending", result.payment_state)
        self.assertEqual(1, len(transport.calls))

    def test_payment_only_response_keeps_material_and_completed_status_survives_missing_payment_fields(self):
        provider, transport = self.provider({"ok": True, "status": "success", "result": {
            "long_url": "https://payment.example.test/upi",
            "copy_paste": "upi://pay?pa=synthetic@example.test",
            "payment_platform": {"status": "submitted", "order_id": "keep-order"},
        }})
        provider.get_status("complete-job", private_data={"mode": "auto_payment", "existing_reference": "keep"})
        transport.response = {"ok": True, "payment_platform": {"status": "submitted", "order_status": "COMPLETED"}}
        result = provider.get_automatic_payment_status("complete-job")
        self.assertEqual("succeeded", result.extraction_state)
        self.assertEqual("succeeded", result.payment_state)
        self.assertEqual("keep-order", result.private_data["legacy_payment_order_id"])
        self.assertEqual("keep", result.private_data["existing_reference"])
        self.assertEqual(("https://payment.example.test/upi",), result.links)
        self.assertIn("qr_data", result.payment_artifact)
        transport.response = {"ok": True, "status": "success"}
        result = provider.get_status("complete-job")
        self.assertEqual("succeeded", result.payment_state)
        self.assertTrue(result.summary["automatic_payment_terminal"])
        self.assertEqual("COMPLETED", result.summary["automatic_payment_status"])

    def test_failed_payment_has_explicit_classification_and_both_cdks_are_redacted(self):
        result = LegacyProvider._job({"status": "success", "result": {
            "long_url": "https://payment.example.test/upi", "payment_platform": {
                "status": "submitted", "order_status": "NEED_REUPLOAD",
                "message": "订单需重传 synthetic-cdk synthetic-payment-cdk",
            },
        }}, "failed-payment", secrets=("synthetic-cdk", "synthetic-payment-cdk"))
        self.assertEqual("payment_order_need_reupload", result.summary["failure_code"])
        self.assertEqual("payment_order_failed", result.summary["failure_type"])
        self.assertNotIn("synthetic-cdk", result.summary["failure_message"])
        self.assertNotIn("synthetic-payment-cdk", result.summary["failure_message"])
        self.assertTrue(result.summary["automatic_payment_terminal"])

    def test_old_submitted_snapshot_does_not_regress_existing_terminal_order_or_query_again(self):
        for terminal, wanted in (("COMPLETED", "succeeded"), ("FAILED", "failed")):
            with self.subTest(terminal=terminal):
                provider, transport = self.provider({"ok": True, "status": "success", "result": {
                    "long_url": "https://payment.example.test/upi", "payment_platform": {
                        "status": "submitted", "order_id": "same-order", "order_status": terminal,
                    },
                }})
                provider.get_status("terminal-job", private_data={"mode": "auto_payment"})
                transport.response["result"]["payment_platform"] = {"status": "submitted", "order_id": "same-order"}
                result = provider.get_status("terminal-job")
                self.assertEqual(wanted, result.payment_state)
                self.assertEqual(terminal, result.summary["automatic_payment_status"])
                self.assertTrue(result.summary["automatic_payment_terminal"])
                result = provider.get_automatic_payment_status("terminal-job")
                self.assertEqual(wanted, result.payment_state)
                self.assertEqual(["GET", "GET"], [call[0] for call in transport.calls])

    def test_new_order_reference_can_change_terminal_state_without_old_payment_failure(self):
        provider, transport = self.provider({"ok": True, "status": "success", "result": {
            "long_url": "https://payment.example.test/upi", "payment_platform": {
                "status": "submitted", "order_id": "old-order", "order_status": "FAILED",
            },
        }})
        provider.get_status("recovered-job", private_data={"mode": "auto_payment"})
        transport.response["result"]["payment_platform"] = {"status": "submitted", "order_id": "new-order"}
        result = provider.get_status("recovered-job")
        self.assertEqual("pending", result.payment_state)
        self.assertFalse(result.summary["automatic_payment_terminal"])
        self.assertNotIn("failure_code", result.summary)
        self.assertEqual("new-order", result.private_data["legacy_payment_order_id"])

    def test_restart_restores_same_order_terminal_state_without_payment_query(self):
        for terminal, wanted in (("COMPLETED", "succeeded"), ("FAILED", "failed")):
            with self.subTest(terminal=terminal):
                provider, _ = self.provider({"ok": True, "status": "success", "result": {
                    "long_url": "https://payment.example.test/upi", "payment_platform": {
                        "status": "submitted", "order_id": "persisted-order", "order_status": terminal,
                    },
                }})
                saved = provider.get_status("restart-job", private_data={"mode": "auto_payment"})
                restarted, transport = self.provider({"ok": True, "status": "success", "result": {
                    "long_url": "https://payment.example.test/upi",
                    "payment_platform": {"status": "submitted", "order_id": "persisted-order"},
                }})
                restored = restarted.get_status("restart-job", private_data=saved.private_data)
                self.assertEqual(wanted, restored.payment_state)
                self.assertEqual(terminal, restored.summary["automatic_payment_status"])
                self.assertTrue(restored.summary["automatic_payment_terminal"])
                restarted.get_automatic_payment_status("restart-job")
                self.assertEqual(["GET"], [call[0] for call in transport.calls])
                transport.response["result"]["payment_platform"] = {"status": "submitted", "order_id": "new-order"}
                changed = restarted.get_status("restart-job")
                self.assertEqual("pending", changed.payment_state)
                self.assertFalse(changed.summary["automatic_payment_terminal"])

    def test_payment_order_states_use_official_terminal_meaning(self):
        for remote, wanted in (("PENDING", "pending"), ("ASSIGNED", "pending"), ("CHECKING", "pending"),
                               ("COMPLETED", "succeeded"), ("FAILED", "failed"), ("CANCELLED", "failed"),
                               ("EXPIRED", "failed"), ("NEED_REUPLOAD", "failed"), ("mystery", "unknown")):
            with self.subTest(remote=remote):
                result = LegacyProvider._job({"status": "success", "result": {
                    "long_url": "https://payment.example.test/upi",
                    "payment_platform": {"status": "submitted", "order_status": remote},
                }}, "existing-job")
                self.assertEqual(wanted, result.payment_state)
                self.assertNotIn("platform_plus_status", result.summary)

    def test_nested_order_status_precedes_human_label_and_exact_completed_label_is_supported(self):
        for payment, wanted in (({"status": "submitted", "order": {"status": "FAILED"}, "order_status_label": "已完成"}, "failed"),
                                ({"status": "submitted", "order_status_label": "已完成"}, "succeeded"),
                                ({"status": "submitted", "order_status_label": "支付已完成，请核实"}, "pending")):
            with self.subTest(payment=payment):
                result = LegacyProvider._job({"status": "success", "result": {
                    "long_url": "https://payment.example.test/upi", "payment_platform": payment,
                }}, "existing-job")
                self.assertEqual(wanted, result.payment_state)
