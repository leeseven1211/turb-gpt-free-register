"""幻光公开文档中的任务、二维码及到账证据契约。"""

import unittest
import time
from copy import deepcopy
from types import SimpleNamespace

from core.extract_link_providers.contracts import ExtractRequest, ProviderConfig, ProviderError
from core.extract_link_providers.huanguang import HuanguangProvider


_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6kuUAAAAASUVORK5CYII="


class HuanguangDocumentContractTests(unittest.TestCase):
    def test_per_task_retry_limit_reaches_platform_without_sending_arbitrary_options(self):
        transport = _Transport([{"job_id": "synthetic-job", "job_secret": "synthetic-private-secret"}])
        provider = HuanguangProvider(_config(), transport)
        provider.create_job(ExtractRequest(
            1, "synthetic-token", "upi", "extract_only", options={"retry_count": 3, "chongyun_auto_submit": True},
            entry_proxy="http://entry", exit_proxy="http://exit",
        ))
        self.assertEqual(3, transport.calls[0][2].get("retry_count"))
        self.assertNotIn("chongyun_auto_submit", transport.calls[0][2])

    def test_invalid_retry_limit_cannot_be_sent_directly_to_provider(self):
        for count in (True, 0, -1, 11, 3.0, "3", None):
            with self.subTest(count=count):
                transport = _Transport([])
                provider = HuanguangProvider(_config(), transport)
                with self.assertRaises(ProviderError):
                    provider.create_job(ExtractRequest(
                        1, "synthetic-token", "upi", options={"retry_count": count},
                        entry_proxy="http://entry", exit_proxy="http://exit",
                    ))
                self.assertEqual([], transport.calls)

    def test_link_ready_is_extracted_while_remote_detection_is_still_running(self):
        job = self._job({
            "status": "running", "percent": 98,
            "result": {"provider_redirect_url": "https://pay.example.test/page", "payment_check_status": "running"},
        })
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual("RUNNING", job.summary.get("remote_status"))
        self.assertTrue(job.summary.get("remote_polling"))

    def test_done_without_payment_material_cannot_report_extraction_success(self):
        job = self._job({"status": "done", "result": None})
        self.assertEqual("failed", job.extraction_state)
        self.assertIn("支付材料", job.summary.get("failure_message"))
        self.assertFalse(job.summary.get("remote_polling"))

    def test_existing_link_survives_later_detection_error(self):
        job = self._job({
            "status": "error", "text": "到账检测异常",
            "result": {"checkout_url": "https://pay.example.test/page", "payment_status": "payment_check_error"},
        })
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual("unknown", job.payment_state)
        self.assertEqual("ERROR", job.summary.get("remote_status"))

    def test_native_png_and_svg_urls_are_preserved(self):
        job = self._job({"status": "done", "result": {
            "qr_image_png": "https://qr.example.test/code.png",
            "qr_image_svg": "https://qr.example.test/code.svg",
        }})
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual("https://qr.example.test/code.png", job.payment_artifact.get("qr_image_url_png"))
        self.assertEqual("https://qr.example.test/code.svg", job.payment_artifact.get("qr_image_url_svg"))

    def test_native_png_data_url_is_an_image_and_never_replaces_qr_payload(self):
        job = self._job({"status": "running", "result": {"qr_image_png": _PNG}})
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual(_PNG, job.payment_artifact.get("qr_image_url_png"))
        self.assertNotIn("qr_data", job.payment_artifact)

    def test_svg_data_url_is_rejected_while_exact_qr_payload_is_retained(self):
        payload = "upi://pay?pa=synthetic%40bank&tn=Token%2BExact"
        job = self._job({"status": "done", "result": {
            "qr_image_svg": "data:image/svg+xml,<svg onload='alert(1)'/>", "qr_data": payload,
        }})
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual(payload, job.payment_artifact.get("qr_data"))
        self.assertNotIn("qr_image_url_svg", job.payment_artifact)

    def test_invalid_material_cannot_turn_a_terminal_job_into_success(self):
        for result in (
            {"checkout_url": "javascript:alert(1)"},
            {"provider_redirect_url": "https://user:password@pay.example.test/"},
            {"qr_data": "  "}, {"qr_data": "upi://pay\x00"},
            {"qr_image_png": "data:image/png;base64,aW52YWxpZA=="},
            {"qr_image_svg": "data:image/svg+xml,<svg/>"},
            {"amount": 0, "payment_status": "completed"},
        ):
            with self.subTest(result=result):
                job = self._job({"status": "done", "percent": 100, "result": result})
                self.assertEqual("failed", job.extraction_state)

    def test_valid_legacy_image_is_kept_when_native_image_is_invalid(self):
        job = self._job({"status": "running", "result": {
            "qr_image_png": "data:image/png;base64,broken",
            "image_url_png": "https://qr.example.test/code.png",
        }})
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual("https://qr.example.test/code.png", job.payment_artifact.get("qr_image_url_png"))

    def test_documented_direct_verification_is_required_for_payment_success(self):
        job = self._job({"status": "done", "result": {
            "checkout_url": "https://pay.example.test/page", "payment_status": "completed",
            "entitlement_active": True, "plan_type": "plus", "has_active_subscription": True,
            "entitlement_inferred": False,
        }})
        self.assertEqual("succeeded", job.payment_state)
        self.assertEqual("verified", job.summary.get("platform_plus_status"))
        self.assertEqual("verified", job.payment_artifact.get("platform_plus_status"))

    def test_inferred_entitlement_remains_unconfirmed(self):
        job = self._job({"status": "done", "result": {
            "payment_status": "completed", "entitlement_active": True, "plan_type": "plus",
            "has_active_subscription": True, "entitlement_inferred": True,
        }})
        self.assertEqual("unknown", job.payment_state)
        self.assertEqual("inferred", job.summary.get("platform_plus_status"))
        self.assertTrue(job.summary.get("entitlement_inferred"))

    def test_completed_without_full_verification_cannot_report_payment_success(self):
        for missing in ("entitlement_active", "plan_type", "has_active_subscription"):
            result = {
                "payment_status": "completed", "entitlement_active": True,
                "plan_type": "plus", "has_active_subscription": True,
            }
            result.pop(missing)
            with self.subTest(missing=missing):
                self.assertEqual("unknown", self._job({"status": "done", "result": result}).payment_state)

    def test_verification_requires_documented_boolean_evidence(self):
        for field, invalid in (
            ("entitlement_active", False), ("entitlement_active", 1),
            ("entitlement_active", "true"), ("has_active_subscription", False),
            ("has_active_subscription", 1), ("has_active_subscription", "true"),
            ("plan_type", "free"), ("entitlement_inferred", "true"),
        ):
            result = {
                "payment_status": "completed", "entitlement_active": True,
                "plan_type": "plus", "has_active_subscription": True,
                "entitlement_inferred": False,
            }
            result[field] = invalid
            with self.subTest(field=field, invalid=invalid):
                self.assertEqual("unknown", self._job({"status": "done", "result": result}).payment_state)

    def test_document_allows_missing_inference_flag_for_direct_verification(self):
        job = self._job({"status": "done", "result": {
            "payment_status": "completed", "entitlement_active": True,
            "plan_type": "plus", "has_active_subscription": True,
        }})
        self.assertEqual("succeeded", job.payment_state)

    def test_payment_states_distinguish_waiting_failure_and_uncertainty(self):
        for source, expected in (
            ("awaiting_payment", "pending"), ("activation_pending", "pending"),
            ("failed", "failed"), ("expired", "failed"), ("payment_timeout", "unknown"),
            ("payment_check_error", "unknown"), ("verification_unavailable", "unknown"),
        ):
            with self.subTest(source=source):
                job = self._job({"status": "done", "result": {"payment_status": source}})
                self.assertEqual(expected, job.payment_state)

    def test_platform_scan_completion_alone_is_not_payment_success(self):
        job = self._job({"status": "done", "result": {"chongyun_order_status": "COMPLETED"}})
        self.assertNotEqual("succeeded", job.payment_state)

    def test_scan_refund_and_rejection_are_payment_failures(self):
        for result in (
            {"chongyun_status": "refunded"}, {"chongyun_status": "rejected"},
            {"chongyun_order_status": "FAILED_REFUNDED"},
        ):
            with self.subTest(result=result):
                job = self._job({"status": "done", "result": {
                    "checkout_url": "https://pay.example.test/page",
                    "payment_status": "awaiting_payment", **result,
                }})
                self.assertEqual("succeeded", job.extraction_state)
                self.assertEqual("failed", job.payment_state)
                self.assertTrue(job.summary.get("automatic_payment_terminal"))
                self.assertFalse(job.summary.get("automatic_payment_requires_reconcile"))

    def test_stopped_scan_without_entitlement_remains_uncertain(self):
        for result in (
            {"chongyun_status": "completed", "chongyun_order_status": "COMPLETED"},
            {"chongyun_status": "unknown"}, {"chongyun_status": "manual_review"},
            {"chongyun_order_status": "UNKNOWN"},
            {"chongyun_status": "active", "chongyun_order_status": "WAITING_SCAN"},
        ):
            with self.subTest(result=result):
                job = self._job({"status": "done", "result": {
                    "checkout_url": "https://pay.example.test/page",
                    "payment_status": "awaiting_payment", "chongyun_polling": False,
                    **result,
                }})
                self.assertEqual("unknown", job.payment_state)
                self.assertTrue(job.summary.get("automatic_payment_terminal"))
                self.assertTrue(job.summary.get("automatic_payment_requires_reconcile"))

    def test_uncertain_scan_keeps_monitoring_while_any_background_work_runs(self):
        for remote_status, background in (
            ("done", {"chongyun_polling": True}),
            ("done", {"payment_check_status": "running"}),
            ("running", {}),
        ):
            for scan_status in ("unknown", "manual_review", "completed"):
                with self.subTest(remote_status=remote_status, background=background, scan_status=scan_status):
                    job = self._job({"status": remote_status, "result": {
                        "checkout_url": "https://pay.example.test/page",
                        "payment_status": "payment_timeout", "chongyun_status": scan_status,
                        **background,
                    }})
                    self.assertEqual("unknown", job.payment_state)
                    self.assertTrue(job.summary.get("remote_polling"))
                    self.assertIs(False, job.summary.get("automatic_payment_terminal"))
                    self.assertIs(False, job.summary.get("automatic_payment_requires_reconcile"))

    def test_active_scan_without_payment_status_is_pending(self):
        job = self._job({"status": "done", "result": {
            "checkout_url": "https://pay.example.test/page", "chongyun_status": "active",
            "chongyun_order_status": "WAITING_SCAN", "chongyun_polling": True,
        }})
        self.assertEqual("pending", job.payment_state)
        self.assertEqual("WAITING_SCAN", job.summary.get("automatic_payment_status"))

    def test_scan_completion_or_uncertainty_cannot_override_explicit_payment_failure(self):
        for payment_status in ("failed", "expired"):
            for scan in (
                {"chongyun_status": "completed"}, {"chongyun_status": "manual_review"},
                {"chongyun_status": "unknown"}, {"chongyun_order_status": "COMPLETED"},
                {"chongyun_order_status": "UNKNOWN"},
            ):
                with self.subTest(payment_status=payment_status, scan=scan):
                    job = self._job({"status": "done", "result": {
                        "checkout_url": "https://pay.example.test/page",
                        "payment_status": payment_status, "chongyun_polling": False, **scan,
                    }})
                    self.assertEqual("failed", job.payment_state)
                    self.assertFalse(job.summary.get("automatic_payment_requires_reconcile"))

    def test_inferred_entitlement_cannot_hide_explicit_payment_failure(self):
        for payment_status in ("failed", "expired"):
            for scan_status in ("completed", "manual_review", "unknown"):
                with self.subTest(payment_status=payment_status, scan_status=scan_status):
                    job = self._job({"status": "done", "result": {
                        "payment_status": payment_status, "chongyun_status": scan_status,
                        "entitlement_inferred": True, "entitlement_active": True,
                        "plan_type": "plus", "has_active_subscription": True,
                    }})
                    self.assertEqual("failed", job.payment_state)
                    self.assertEqual("inferred", job.summary["platform_plus_status"])

    def test_progress_retains_stage_queue_and_attempt_counts(self):
        job = self._job({
            "status": "running", "percent": 34, "attempt": 2, "max_attempts": 3,
            "queue_position": 4, "text": "正在创建支付请求", "cdk_state": "reserved",
        })
        self.assertEqual("正在创建支付请求", job.summary.get("current_step"))
        self.assertEqual(34, job.summary.get("percent"))
        self.assertEqual(2, job.summary.get("step_attempt"))
        self.assertEqual(3, job.summary.get("max_attempts"))
        self.assertEqual(4, job.summary.get("queue_position"))
        self.assertEqual("reserved", job.summary.get("cdk_state"))

    def test_untrusted_progress_values_are_not_projected(self):
        job = self._job({
            "status": "synthetic-private-secret", "percent": True, "attempt": -1,
            "max_attempts": "3", "queue_position": False, "text": {"token": "private"},
            "cdk_state": "https://private.example.test/?token=private",
            "result": {"payment_check_status": "token=private", "entitlement_active": "true"},
        })
        self.assertEqual("unknown", job.extraction_state)
        for field in ("percent", "step_attempt", "max_attempts", "queue_position", "current_step", "cdk_state", "payment_check_status", "entitlement_active"):
            self.assertNotIn(field, job.summary)
        self.assertNotIn("synthetic-private-secret", repr(job.summary))

    def test_failure_and_stage_messages_are_redacted_before_projection(self):
        job = self._job({
            "status": "error",
            "error": "提链失败 token=synthetic-token cdk=CDK-ABCD-1234-ABCD-1234 user@example.test https://pay.example.test/?secret=synthetic-secret synthetic-private-secret",
            "text": "重试 token=synthetic-token user@example.test https://proxy-user:proxy-password@proxy.example.test:8080",
        })
        self.assertEqual("failed", job.extraction_state)
        self.assertTrue(job.summary.get("remote_terminal_failure"))
        for name in ("failure_message", "current_step"):
            message = job.summary[name]
            self.assertLessEqual(len(message), 300)
            for secret in ("synthetic-token", "CDK-ABCD-1234-ABCD-1234", "user@example.test", "pay.example.test", "proxy-password", "synthetic-private-secret"):
                self.assertNotIn(secret, message)

    def test_terminal_cdk_error_text_is_not_hidden_by_generic_failure(self):
        for status in ("error", "failed", "cancelled", "canceled"):
            with self.subTest(status=status):
                job = self._job({
                    "status": status, "error": "任务处理失败",
                    "text": "提链 CDK 次数已用完，任务未执行",
                })
                self.assertEqual("failed", job.extraction_state)
                self.assertEqual("提链 CDK 次数已用完，任务未执行", job.summary.get("failure_message"))

    def test_specific_result_error_is_not_hidden_by_generic_outer_error(self):
        job = self._job({
            "status": "error", "error": "任务处理失败", "text": "正在创建支付请求",
            "result": {"error": "代理隧道连接失败，HTTP 403"},
        })
        self.assertEqual("代理隧道连接失败，HTTP 403", job.summary.get("failure_message"))

    def test_specific_result_error_is_not_hidden_by_outer_running_message(self):
        job = self._job({
            "status": "error", "message": "正在创建支付请求",
            "result": {"error": "代理隧道连接失败，HTTP 403"},
        })
        self.assertEqual("代理隧道连接失败，HTTP 403", job.summary.get("failure_message"))

    def test_explicit_error_keeps_priority_even_when_it_describes_running_stage(self):
        job = self._job({
            "status": "error", "error": "正在创建支付请求时代理认证失败",
            "result": {"error": "代理隧道连接失败，HTTP 403"},
        })
        self.assertEqual("正在创建支付请求时代理认证失败", job.summary.get("failure_message"))

    def test_specific_error_is_preserved_instead_of_previous_progress(self):
        for error in ("代理隧道连接失败，HTTP 403", "任务处理失败"):
            with self.subTest(error=error):
                job = self._job({
                    "status": "error", "error": error, "text": "正在创建支付请求",
                })
                self.assertEqual(error, job.summary.get("failure_message"))

    def test_done_without_material_keeps_synthetic_failure_contract(self):
        job = self._job({
            "status": "done", "error": "任务处理失败",
            "text": "提链 CDK 次数已用完，任务未执行",
        })
        self.assertEqual("任务处理失败", job.summary.get("failure_message"))
        empty = self._job({"status": "done", "result": {}})
        self.assertEqual("幻光任务已结束，但未返回有效支付材料", empty.summary.get("failure_message"))

    def test_selected_terminal_error_text_remains_redacted_and_bounded(self):
        job = self._job({
            "status": "error", "error": "任务处理失败",
            "text": "提链失败 cdk=CDK-ABCD-1234-ABCD-1234 secret=synthetic-private-secret user@example.test https://proxy-user:proxy-password@proxy.example.test:8080 " + "错误" * 200,
        })
        message = job.summary["failure_message"]
        self.assertTrue(message.startswith("提链失败"))
        self.assertLessEqual(len(message), 300)
        for secret in ("CDK-ABCD-1234-ABCD-1234", "synthetic-private-secret", "user@example.test", "proxy-password", "proxy.example.test"):
            self.assertNotIn(secret, message)

    def test_done_still_requests_monitoring_while_payment_checker_runs(self):
        for result in ({"payment_check_status": "running"}, {"chongyun_polling": True}, {"xxsyun_polling": True}, {"seashore_polling": True}):
            with self.subTest(result=result):
                self.assertTrue(self._job({"status": "done", "result": result}).summary.get("remote_polling"))

    def test_cancelled_job_only_keeps_platform_order_polling(self):
        for result, expected in (
            ({"payment_check_status": "running"}, False),
            ({"payment_check_status": "running", "chongyun_polling": True}, True),
            ({"xxsyun_polling": "true"}, False),
        ):
            with self.subTest(result=result):
                job = self._job({"status": "cancelled", "result": result})
                self.assertEqual(expected, job.summary.get("remote_polling"))

    def test_progress_keeps_separate_detection_and_entitlement_evidence(self):
        job = self._job({"status": "running", "result": {
            "payment_status": "awaiting_payment", "payment_check_status": "running",
            "entitlement_active": False, "entitlement_inferred": False,
        }})
        self.assertEqual("awaiting_payment", job.summary.get("payment_status"))
        self.assertEqual("running", job.summary.get("payment_check_status"))
        self.assertIs(False, job.summary.get("entitlement_active"))
        self.assertIs(False, job.summary.get("entitlement_inferred"))

    def test_unsupported_link_type_is_rejected_before_sending_credentials(self):
        transport = _Transport([])
        provider = HuanguangProvider(_config(), transport)
        with self.assertRaises(ProviderError):
            provider.create_job(ExtractRequest(1, "synthetic-token", "pix", entry_proxy="http://entry", exit_proxy="http://exit"))
        self.assertEqual([], transport.calls)

    def test_upi_submission_uses_documented_fields_and_keeps_query_secret_private(self):
        transport = _Transport([{"ok": True, "job_id": "synthetic-job", "job_secret": "synthetic-private-secret", "queue_position": 2}])
        provider = HuanguangProvider(_config(), transport)
        created = provider.create_job(ExtractRequest(1, "synthetic-token", "upi", entry_proxy="http://entry", exit_proxy="http://exit"))
        self.assertEqual("queued", created.extraction_state)
        self.assertEqual(2, created.summary.get("queue_position"))
        self.assertNotIn("synthetic-private-secret", repr(created))
        self.assertEqual("upi", transport.calls[0][2]["link_type"])
        self.assertNotIn("chongyun_auto_submit", transport.calls[0][2])

    def test_multiple_proxy_candidates_are_submitted_in_full_and_hidden_from_repr(self):
        entries = ("http://fixture-user:fixture-password@entry-one.example.test:8080", "socks5h://entry-two.example.test:1080")
        exits = ("http://exit-one.example.test:8080", "http://exit-two.example.test:8080")
        transport = _Transport([{"job_id": "synthetic-job", "job_secret": "synthetic-secret"}])
        provider = HuanguangProvider(_config(), transport)
        request = ExtractRequest(1, "synthetic-token", "upi", entry_proxies=entries, exit_proxies=exits)

        provider.create_job(request)

        self.assertEqual(list(entries), transport.calls[0][2]["entry_proxies"])
        self.assertEqual(list(exits), transport.calls[0][2]["exit_proxies"])
        for address in (*entries, *exits):
            self.assertNotIn(address, repr(request))
        self.assertNotIn("fixture-password", repr(request))

    def test_socks_proxy_echo_is_redacted_from_remote_progress_and_failure(self):
        address = "socks5h://fixture-user:fixture-password@proxy.example.test:1080"
        job = self._job({"status": "error", "text": f"代理失败 {address}", "error": f"连接失败 {address}"})
        self.assertNotIn(address, repr(job))
        self.assertNotIn("fixture-password", repr(job.summary))
        self.assertNotIn("fixture-user", repr(job.summary))
        self.assertIn("代理失败", job.summary["current_step"])

    def test_known_cdk_and_job_secret_are_redacted_when_polling(self):
        transport = _Transport([{
            "status": "error", "error": "失败 synthetic-cdk synthetic-private-secret",
        }])
        job = HuanguangProvider(_config(), transport).get_status(
            "synthetic-job", private_data={"job_secret": "synthetic-private-secret"},
        )
        self.assertIsInstance(job.summary.get("failure_message"), str)
        self.assertNotIn("synthetic-cdk", job.summary.get("failure_message"))
        self.assertNotIn("synthetic-private-secret", repr(job))
        self.assertNotIn("synthetic-private-secret", transport.calls[0][1])

    def test_auto_payment_is_rejected_before_sending_credentials(self):
        transport = _Transport([])
        provider = HuanguangProvider(_config(), transport)
        with self.assertRaises(ProviderError) as error:
            provider.create_job(ExtractRequest(
                1, "synthetic-token", "upi", "auto_payment",
                entry_proxy="http://entry", exit_proxy="http://exit",
            ))
        self.assertEqual("unsupported", error.exception.code)
        self.assertEqual([], transport.calls)

    def test_auto_payment_submits_separate_payment_cdk_only_when_explicitly_enabled(self):
        transport = _Transport([{"job_id": "synthetic-job", "job_secret": "synthetic-private-secret"}])
        provider = HuanguangProvider(_config(payment_cdk="synthetic-payment-secret", auto_payment=True), transport)
        created = provider.create_job(ExtractRequest(
            1, "synthetic-token", "upi", "auto_payment",
            entry_proxy="http://entry", exit_proxy="http://exit",
        ))
        body = transport.calls[0][2]
        self.assertEqual("synthetic-cdk", body["cdk"])
        self.assertEqual("chongyun", body.get("scan_provider"))
        self.assertIs(True, body["chongyun_auto_submit"])
        self.assertEqual("synthetic-payment-secret", body["chongyun_cdk"])
        self.assertEqual({"job_secret": "synthetic-private-secret"}, created.private_data)
        self.assertNotIn("synthetic-payment-secret", repr(created))

    def test_auto_payment_requires_both_capabilities_and_payment_cdk(self):
        for capabilities, payment_cdk in (
            ({"extract": True, "payment": True, "auto_payment": False}, "synthetic-payment-secret"),
            ({"extract": True, "payment": False, "auto_payment": True}, "synthetic-payment-secret"),
            ({"extract": True, "payment": True, "auto_payment": True}, ""),
        ):
            with self.subTest(capabilities=capabilities, payment_cdk=bool(payment_cdk)):
                transport = _Transport([])
                provider = HuanguangProvider(_config(payment_cdk=payment_cdk, capabilities=capabilities), transport)
                with self.assertRaises(ProviderError):
                    provider.create_job(ExtractRequest(
                        1, "synthetic-token", "upi", "auto_payment",
                        entry_proxy="http://entry", exit_proxy="http://exit",
                    ))
                self.assertEqual([], transport.calls)

    def test_non_auto_modes_never_submit_scan_despite_config_or_options(self):
        for mode in ("extract_only", "manual_payment"):
            with self.subTest(mode=mode):
                transport = _Transport([{"job_id": "synthetic-job", "job_secret": "synthetic-private-secret"}])
                provider = HuanguangProvider(_config(payment_cdk="synthetic-payment-secret", auto_payment=True), transport)
                provider.create_job(ExtractRequest(
                    1, "synthetic-token", "upi", mode,
                    options={"chongyun_auto_submit": True, "chongyun_cdk": "injected-secret"},
                    entry_proxy="http://entry", exit_proxy="http://exit",
                ))
                self.assertNotIn("chongyun_auto_submit", transport.calls[0][2])
                self.assertNotIn("chongyun_cdk", transport.calls[0][2])
                self.assertNotIn("scan_provider", transport.calls[0][2])

    def test_payment_cdk_is_redacted_and_never_resent_during_query(self):
        transport = _Transport([
            {"job_id": "synthetic-job", "job_secret": "synthetic-private-secret",
             "text": "已受理 synthetic-payment-secret"},
            {"status": "error", "text": "失败 synthetic-payment-secret",
             "error": "连接失败 synthetic-payment-secret"},
        ])
        config = _config(payment_cdk="synthetic-payment-secret", auto_payment=True)
        provider = HuanguangProvider(config, transport)
        created = provider.create_job(ExtractRequest(
            1, "synthetic-token", "upi", "auto_payment",
            entry_proxy="http://entry", exit_proxy="http://exit",
        ))
        job = provider.get_status(created.job_id, private_data=created.private_data)
        self.assertNotIn("synthetic-payment-secret", repr(config))
        self.assertNotIn("synthetic-payment-secret", repr(created))
        self.assertNotIn("synthetic-payment-secret", repr(job))
        self.assertEqual("GET", transport.calls[1][0])
        self.assertIsNone(transport.calls[1][2])
        self.assertNotIn("synthetic-payment-secret", repr(transport.calls[1]))
        with self.assertRaises(ProviderError):
            provider.start_payment(created.job_id, {"chongyun_cdk": "synthetic-payment-secret"})
        self.assertEqual(2, len(transport.calls))

    def test_enabled_fallback_is_created_with_platform_fields_and_key_stays_private(self):
        key = "synthetic-xxsyun-api-key"
        transport = _Transport([{
            "job_id": "synthetic-job", "job_secret": "synthetic-private-secret",
            "text": f"已受理 {key}",
        }])
        config = _config(payment_cdk="synthetic-payment-secret", auto_payment=True,
                         xxsyun_api_key=key, scan_fallback_enabled=True)
        created = HuanguangProvider(config, transport).create_job(ExtractRequest(
            1, "synthetic-token", "upi", "auto_payment",
            entry_proxy="http://entry", exit_proxy="http://exit",
        ))
        self.assertIs(True, transport.calls[0][2].get("scan_fallback_enabled"))
        self.assertEqual(key, transport.calls[0][2].get("fallback_xxsyun_api_key"))
        self.assertEqual({"Content-Type": "application/json"}, transport.calls[0][3])
        self.assertNotIn("xxsyun_auto_submit", transport.calls[0][2])
        self.assertNotIn("xxsyun_api_key", transport.calls[0][2])
        self.assertEqual({"job_secret": "synthetic-private-secret"}, created.private_data)
        self.assertNotIn(key, repr(config))
        self.assertNotIn(key, repr(created))
        self.assertNotIn(key, repr(created.summary))
        self.assertNotIn(key, repr(created.private_data))

    def test_missing_or_disabled_fallback_never_blocks_primary_auto_payment(self):
        for enabled, key in ((False, "synthetic-xxsyun-api-key"), (True, ""), (True, "  ")):
            with self.subTest(enabled=enabled, key=bool(key.strip())):
                transport = _Transport([{"job_id": "synthetic-job", "job_secret": "synthetic-private-secret"}])
                provider = HuanguangProvider(_config(
                    payment_cdk="synthetic-payment-secret", auto_payment=True,
                    xxsyun_api_key=key, scan_fallback_enabled=enabled,
                ), transport)
                created = provider.create_job(ExtractRequest(
                    1, "synthetic-token", "upi", "auto_payment",
                    entry_proxy="http://entry", exit_proxy="http://exit",
                ))
                self.assertEqual("queued", created.extraction_state)
                self.assertIs(True, transport.calls[0][2]["chongyun_auto_submit"])
                self.assertNotIn("scan_fallback_enabled", transport.calls[0][2])
                self.assertNotIn("fallback_xxsyun_api_key", transport.calls[0][2])

    def test_non_auto_modes_never_submit_fallback_even_with_enabled_config_and_options(self):
        for mode in ("extract_only", "manual_payment"):
            with self.subTest(mode=mode):
                transport = _Transport([{"job_id": "synthetic-job", "job_secret": "synthetic-private-secret"}])
                provider = HuanguangProvider(_config(
                    payment_cdk="synthetic-payment-secret", auto_payment=True,
                    xxsyun_api_key="synthetic-xxsyun-api-key", scan_fallback_enabled=True,
                ), transport)
                provider.create_job(ExtractRequest(
                    1, "synthetic-token", "upi", mode,
                    options={"scan_fallback_enabled": True, "fallback_xxsyun_api_key": "injected-key"},
                    entry_proxy="http://entry", exit_proxy="http://exit",
                ))
                self.assertNotIn("scan_fallback_enabled", transport.calls[0][2])
                self.assertNotIn("fallback_xxsyun_api_key", transport.calls[0][2])

    def test_fallback_activity_overrides_old_primary_refund_and_continues_polling(self):
        for result, expected in (
            ({"scan_fallback_status": "checking", "scan_fallback_polling": True}, "pending"),
            ({"scan_fallback_status": "submitting", "scan_fallback_polling": True}, "pending"),
            ({"scan_fallback_status": "submitted", "scan_fallback_provider": "xxsyun",
              "xxsyun_status": "awaiting_worker", "xxsyun_polling": True}, "pending"),
            ({"xxsyun_status": "claimed", "xxsyun_polling": True}, "pending"),
            ({"xxsyun_status": "verifying", "xxsyun_polling": True}, "pending"),
        ):
            with self.subTest(result=result):
                job = self._job({"status": "done", "result": {
                    "checkout_url": "https://pay.example.test/page",
                    "chongyun_status": "refunded", "chongyun_order_status": "FAILED_REFUNDED",
                    "payment_status": "awaiting_payment", **result,
                }})
                self.assertEqual(expected, job.payment_state)
                self.assertTrue(job.summary["remote_polling"])
                self.assertIs(False, job.summary["automatic_payment_terminal"])
                for field in ("scan_fallback_status", "scan_fallback_provider", "scan_fallback_polling", "xxsyun_status", "xxsyun_polling"):
                    if field in result:
                        self.assertEqual(result[field], job.summary.get(field))

    def test_fallback_platform_completion_remains_unknown_without_plus_evidence(self):
        job = self._job({"status": "done", "result": {
            "checkout_url": "https://pay.example.test/page", "payment_status": "awaiting_payment",
            "chongyun_status": "refunded", "chongyun_order_status": "FAILED_REFUNDED",
            "scan_fallback_status": "submitted", "scan_fallback_provider": "xxsyun",
            "xxsyun_status": "completed", "xxsyun_polling": False,
        }})
        self.assertEqual("unknown", job.payment_state)
        self.assertEqual("XXSYUN_COMPLETED", job.summary.get("automatic_payment_status"))
        self.assertTrue(job.summary["automatic_payment_requires_reconcile"])

    def test_fallback_plus_verification_takes_priority_over_both_platform_failures(self):
        job = self._job({"status": "done", "result": {
            "payment_status": "completed", "entitlement_active": True, "plan_type": "plus",
            "has_active_subscription": True, "entitlement_inferred": False,
            "chongyun_status": "refunded", "xxsyun_status": "failed",
            "scan_fallback_status": "submitted", "scan_fallback_provider": "xxsyun",
        }})
        self.assertEqual("succeeded", job.payment_state)
        self.assertEqual("verified", job.summary.get("platform_plus_status"))
        self.assertEqual("failed", job.summary.get("xxsyun_status"))

    def test_xxsyun_failure_and_uncertainty_states_are_not_primary_refund(self):
        for phase, expected in (
            ("failed", "failed"), ("expired", "failed"), ("cancelled", "failed"),
            ("rejected", "failed"), ("manual_review", "unknown"),
            ("credentials_required", "unknown"), ("submitting", "unknown"),
        ):
            with self.subTest(phase=phase):
                job = self._job({"status": "done", "result": {
                    "chongyun_status": "refunded", "xxsyun_status": phase,
                    "xxsyun_polling": False,
                }})
                self.assertEqual(expected, job.payment_state)
                self.assertEqual(phase, job.summary.get("xxsyun_status"))

    def test_explicit_payment_failure_is_not_hidden_by_pending_fallback(self):
        for payment_status in ("failed", "expired"):
            with self.subTest(payment_status=payment_status):
                job = self._job({"status": "done", "result": {
                    "payment_status": payment_status, "xxsyun_status": "claimed",
                    "xxsyun_polling": True, "scan_fallback_status": "submitted",
                }})
                self.assertEqual("failed", job.payment_state)

    def test_unknown_fallback_fields_cannot_leak_into_summary(self):
        job = self._job({"status": "done", "result": {
            "xxsyun_status": "api_key=synthetic-key", "xxsyun_polling": "true",
            "scan_fallback_status": "api_key=synthetic-key", "scan_fallback_provider": "private-platform",
            "scan_fallback_polling": 1, "scan_fallback_message": "api_key=synthetic-key",
        }})
        for field in ("xxsyun_status", "xxsyun_polling", "scan_fallback_status", "scan_fallback_provider", "scan_fallback_polling", "scan_fallback_message"):
            self.assertNotIn(field, job.summary)
        self.assertNotIn("synthetic-key", repr(job))

    def test_xxsyun_key_is_redacted_from_query_messages_without_resending_it(self):
        key = "synthetic-xxsyun-api-key"
        transport = _Transport([{"status": "error", "text": f"失败 {key}", "error": f"失败 {key}"}])
        job = HuanguangProvider(_config(xxsyun_api_key=key), transport).get_status(
            "synthetic-job", private_data={"job_secret": "synthetic-private-secret"},
        )
        self.assertNotIn(key, repr(job))
        self.assertNotIn(key, repr(job.private_data))
        self.assertNotIn(key, repr(transport.calls))
        self.assertEqual("GET", transport.calls[0][0])
        self.assertIsNone(transport.calls[0][2])

    def test_labeled_api_keys_are_redacted_even_when_not_in_current_config(self):
        job = self._job({
            "status": "error", "text": "检查 api_key=synthetic-foreign-key",
            "error": "失败 fallback_xxsyun_api_key=synthetic-fallback-key xxsyun_api_key=synthetic-primary-key",
        })
        for key in ("synthetic-foreign-key", "synthetic-fallback-key", "synthetic-primary-key"):
            self.assertNotIn(key, repr(job))

    def test_credentials_required_resumes_only_original_order_then_fetches_full_snapshot(self):
        key = "synthetic-xxsyun-api-key"
        transport = _Transport([
            {"status": "done", "result": {"xxsyun_status": "credentials_required"}},
            {"xxsyun_status": "claimed", "xxsyun_polling": True},
            {"status": "done", "result": {"xxsyun_status": "claimed", "xxsyun_polling": True,
             "checkout_url": "https://pay.example.test/page"}},
        ])
        job = HuanguangProvider(_config(xxsyun_api_key=key), transport).get_status(
            "synthetic-job", private_data={"job_secret": "synthetic-private-secret"},
        )
        self.assertEqual("pending", job.payment_state)
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual(["GET", "POST", "GET"], [call[0] for call in transport.calls])
        self.assertEqual("/api/xxsyun-resume", transport.calls[1][1])
        self.assertEqual({"job_id": "synthetic-job", "api_key": key}, transport.calls[1][2])
        self.assertEqual({
            "X-Pay153-Job-Secret": "synthetic-private-secret", "Content-Type": "application/json",
        }, transport.calls[1][3])
        self.assertEqual(transport.calls[0][1], transport.calls[2][1])
        self.assertNotIn(key, repr(job))
        self.assertNotIn(key, repr(job.private_data))

    def test_resume_is_bounded_when_server_still_requires_credentials(self):
        snapshot = {"status": "done", "result": {"xxsyun_status": "credentials_required"}}
        transport = _Transport([snapshot, {"xxsyun_status": "credentials_required"}, snapshot])
        job = HuanguangProvider(_config(xxsyun_api_key="synthetic-xxsyun-api-key"), transport).get_status(
            "synthetic-job", private_data={"job_secret": "synthetic-private-secret"},
        )
        self.assertEqual("unknown", job.payment_state)
        self.assertEqual("credentials_required", job.summary.get("xxsyun_status"))
        self.assertEqual(["GET", "POST", "GET"], [call[0] for call in transport.calls])

    def test_missing_key_does_not_attempt_to_resume_original_order(self):
        transport = _Transport([{"status": "done", "result": {"xxsyun_status": "credentials_required"}}])
        job = HuanguangProvider(_config(), transport).get_status(
            "synthetic-job", private_data={"job_secret": "synthetic-private-secret"},
        )
        self.assertEqual("unknown", job.payment_state)
        self.assertEqual(["GET"], [call[0] for call in transport.calls])

    def test_resume_failure_keeps_original_order_as_unknown_without_new_checkout(self):
        transport = _Transport([
            {"status": "done", "result": {"xxsyun_status": "credentials_required",
             "checkout_url": "https://pay.example.test/page"}},
            ProviderError("Provider 请求失败"),
        ])
        job = HuanguangProvider(_config(xxsyun_api_key="synthetic-xxsyun-api-key"), transport).get_status(
            "synthetic-job", private_data={"job_secret": "synthetic-private-secret"},
        )
        self.assertEqual("unknown", job.payment_state)
        self.assertEqual("credentials_required", job.summary.get("xxsyun_status"))
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual(["GET", "POST"], [call[0] for call in transport.calls])

    def test_post_resume_query_failure_preserves_original_material_and_resumed_progress(self):
        transport = _Transport([
            {"status": "done", "result": {"xxsyun_status": "credentials_required",
             "checkout_url": "https://pay.example.test/page"}},
            {"xxsyun_status": "claimed", "xxsyun_polling": True},
            ProviderError("Provider 请求失败"),
        ])
        job = HuanguangProvider(_config(xxsyun_api_key="synthetic-xxsyun-api-key"), transport).get_status(
            "synthetic-job", private_data={"job_secret": "synthetic-private-secret"},
        )
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual("pending", job.payment_state)
        self.assertEqual("claimed", job.summary.get("xxsyun_status"))
        self.assertTrue(job.summary["remote_polling"])
        self.assertEqual(["GET", "POST", "GET"], [call[0] for call in transport.calls])

    @staticmethod
    def _job(data):
        return HuanguangProvider._job(data, "synthetic-job", "synthetic-private-secret")


class HuanguangSubmissionReceiptTests(unittest.TestCase):
    def test_checkpoint_callable_is_hidden_from_request_repr(self):
        class PrivateCheckpoint:
            def __call__(self, private):
                return None

            def __repr__(self):
                return "synthetic-callback-secret"

        self.assertNotIn("synthetic-callback-secret", repr(self._request(PrivateCheckpoint())))

    def test_checkpoint_precedes_single_account_batch_post_and_keeps_retry_count(self):
        transport = _Transport([{"batch_receipts": True}, self._accepted()])
        saved = []

        def checkpoint(private):
            self.assertEqual([("GET", "/api/config")], [call[:2] for call in transport.calls])
            saved.append(deepcopy(private))

        job = HuanguangProvider(_config(), transport).create_job(self._request(checkpoint))

        self.assertEqual("0123456789abcdef", job.job_id)
        self.assertEqual(1, len(saved))
        secret = saved[0]["batch_receipt_secret"]
        self.assertRegex(secret, r"^[a-f0-9]{64}$")
        self.assertIs(True, saved[0]["batch_receipt_pending"])
        method, path, body, headers, _ = transport.calls[1]
        self.assertEqual(("POST", "/api/checkout-batch"), (method, path))
        self.assertEqual(["synthetic-token"], body.get("sessions"))
        self.assertNotIn("token", body)
        self.assertEqual(3, body.get("retry_count"))
        self.assertEqual(secret, headers.get("X-Pay153-Batch-Secret"))
        self.assertEqual(secret, job.private_data.get("batch_receipt_secret"))
        self.assertIs(False, job.private_data.get("batch_receipt_pending"))
        self.assertNotIn(secret, repr(job))

    def test_checkpoint_failure_prevents_remote_post(self):
        transport = _Transport([{"batch_receipts": True}])

        def checkpoint(_private):
            raise RuntimeError("私有回执保存失败")

        with self.assertRaisesRegex(RuntimeError, "私有回执保存失败"):
            HuanguangProvider(_config(), transport).create_job(self._request(checkpoint))
        self.assertEqual([("GET", "/api/config")], [call[:2] for call in transport.calls])

    def test_unsupported_or_unavailable_capability_retains_legacy_endpoint(self):
        for config in ({"batch_receipts": False}, {"batch_receipts": "true"}, ProviderError("暂不可用")):
            with self.subTest(config=config):
                transport = _Transport([config, {"job_id": "synthetic-job", "job_secret": "synthetic-secret"}])
                saved = []
                job = HuanguangProvider(_config(), transport).create_job(self._request(saved.append))
                self.assertEqual("synthetic-job", job.job_id)
                self.assertEqual([], saved)
                self.assertEqual(("POST", "/api/checkout"), transport.calls[1][:2])

    def test_lost_post_response_recovers_original_receipt_without_another_post(self):
        transport = _Transport([
            {"batch_receipts": True}, TimeoutError("synthetic response lost"),
            {"state": "complete", "status": 200, "body": self._accepted()},
        ])
        saved = []
        job = HuanguangProvider(_config(), transport).create_job(self._request(saved.append))
        self.assertEqual("0123456789abcdef", job.job_id)
        self.assertEqual(["GET", "POST", "GET"], [call[0] for call in transport.calls])
        self.assertEqual("/api/checkout-batch-receipt", transport.calls[2][1])
        self.assertEqual(saved[0]["batch_receipt_secret"], transport.calls[2][3].get("X-Pay153-Batch-Secret"))

    def test_pending_receipt_survives_lost_response_and_recovers_after_restart(self):
        transport = _Transport([{"batch_receipts": True}, TimeoutError(), {"state": "unknown"}])
        job = HuanguangProvider(_config(), transport).create_job(self._request(lambda _private: None))
        self.assertIsNone(job.job_id)
        self.assertIs(True, job.summary.get("submission_receipt_pending"))
        self.assertIs(True, job.summary.get("remote_polling"))
        self.assertIs(True, job.private_data.get("batch_receipt_pending"))
        resumed_transport = _Transport([{"state": "complete", "status": 200, "body": self._accepted()}])
        resumed = HuanguangProvider(_config(), resumed_transport).get_status("", private_data=job.private_data)
        self.assertEqual("0123456789abcdef", resumed.job_id)
        self.assertEqual([("GET", "/api/checkout-batch-receipt")], [call[:2] for call in resumed_transport.calls])
        self.assertIs(False, resumed.private_data.get("batch_receipt_pending"))

    def test_receipt_query_failure_retains_private_recovery_fields(self):
        private = {"batch_receipt_secret": "synthetic-batch-secret", "batch_receipt_pending": True}
        for response in (TimeoutError(), {"state": "processing"}, {"state": "unknown"},
                         SimpleNamespace(status_code=404, json=lambda: {"error": "任务不存在"})):
            with self.subTest(response=response):
                transport = _Transport([response])
                job = HuanguangProvider(_config(), transport).get_status("", private_data=private)
                self.assertEqual(private, {key: job.private_data.get(key) for key in private})
                self.assertIsNone(job.job_id)
                self.assertIs(True, job.summary.get("submission_receipt_pending"))
                self.assertEqual(["GET"], [call[0] for call in transport.calls])

    def test_malformed_single_row_receipts_remain_unknown(self):
        accepted = self._accepted()["jobs"][0]
        malformed = (
            {}, {"jobs": [], "rejected": []}, {"jobs": [accepted, accepted], "rejected": []},
            {"jobs": [{**accepted, "row": True}], "rejected": []},
            {"jobs": [{**accepted, "row": 2}], "rejected": []},
            {"jobs": [{"row": 1, "job_id": accepted["job_id"]}], "rejected": []},
            {"jobs": [accepted], "rejected": [{"row": 1, "error": "拒绝"}]},
            {"jobs": "invalid", "rejected": []},
        )
        for receipt in malformed:
            with self.subTest(receipt=receipt):
                transport = _Transport([{"state": "complete", "status": 200, "body": receipt}])
                job = HuanguangProvider(_config(), transport).get_status("", private_data={
                    "batch_receipt_secret": "synthetic-batch-secret", "batch_receipt_pending": True,
                })
                self.assertIsNone(job.job_id)
                self.assertIs(True, job.private_data.get("batch_receipt_pending"))

    def test_explicit_single_row_rejection_is_safe_and_does_not_remain_pending(self):
        for response in (
            {"state": "complete", "status": 200, "body": {"jobs": [], "rejected": [{
                "row": 1, "error": "CDK=synthetic-cdk token=synthetic-token",
            }]}},
            {"state": "complete", "status": 403, "body": {"error": "secret=synthetic-batch-secret"}},
        ):
            with self.subTest(response=response):
                transport = _Transport([response])
                job = HuanguangProvider(_config(), transport).get_status("", private_data={
                    "batch_receipt_secret": "synthetic-batch-secret", "batch_receipt_pending": True,
                })
                self.assertEqual("REJECTED", job.summary.get("outcome"))
                self.assertIs(False, job.private_data.get("batch_receipt_pending"))
                self.assertIs(False, job.summary.get("remote_polling"))
                self.assertNotIn("synthetic-cdk", repr(job))
                self.assertNotIn("synthetic-token", repr(job))
                self.assertNotIn("synthetic-batch-secret", repr(job))

    def test_ambiguous_http_and_invalid_json_recover_receipt_but_rejection_does_not(self):
        def invalid_json():
            raise ValueError("secret=synthetic-json-secret")

        for response in (
            SimpleNamespace(status_code=502, json=lambda: {"error": "暂不可用"}),
            SimpleNamespace(status_code=200, json=invalid_json),
        ):
            with self.subTest(response=response):
                transport = _Transport([{"batch_receipts": True}, response, {
                    "state": "complete", "status": 200, "body": self._accepted(),
                }])
                job = HuanguangProvider(_config(), transport).create_job(self._request(lambda _private: None))
                self.assertEqual("0123456789abcdef", job.job_id)
                self.assertEqual(["GET", "POST", "GET"], [call[0] for call in transport.calls])
        transport = _Transport([{"batch_receipts": True}, SimpleNamespace(status_code=403, json=lambda: {"error": "拒绝"})])
        rejected = HuanguangProvider(_config(), transport).create_job(self._request(lambda _private: None))
        self.assertEqual("REJECTED", rejected.summary.get("outcome"))
        self.assertEqual(["GET", "POST"], [call[0] for call in transport.calls])

    @staticmethod
    def _request(checkpoint):
        return ExtractRequest(
            account_id=1, access_token="synthetic-token", link_type="upi", mode="extract_only",
            options={"retry_count": 3}, entry_proxy="http://entry", exit_proxy="http://exit",
            entry_proxies=(), exit_proxies=(), submission_checkpoint=checkpoint,
        )

    @staticmethod
    def _accepted():
        return {"jobs": [{"row": 1, "job_id": "0123456789abcdef", "job_secret": "synthetic-job-secret"}], "rejected": []}


class HuanguangAutoRelinkTests(unittest.TestCase):
    root_id = "0123456789abcdef"
    child_id = "fedcba9876543210"
    grandchild_id = "1111111111111111"

    def test_auto_relink_starting_keeps_terminal_parent_polling(self):
        for status in ("checking_payment", "starting"):
            with self.subTest(status=status):
                job = HuanguangProvider._job({"status": "done", "result": {
                    "auto_relink_status": status, "auto_relink_attempt": 1,
                }}, self.root_id, "synthetic-job-secret")
                self.assertIs(True, job.summary.get("remote_polling"))
                self.assertIs(False, job.summary.get("automatic_payment_terminal"))
                self.assertEqual(status, job.summary.get("auto_relink_status"))

    def test_child_uses_original_secret_and_root_reference_survives_restart(self):
        first_transport = _Transport([self._parent()])
        parent = HuanguangProvider(_config(), first_transport).get_status(
            self.root_id, private_data={"job_secret": "synthetic-job-secret"},
        )
        self.assertEqual(self.root_id, parent.job_id)
        self.assertEqual(self.child_id, parent.private_data.get("active_job_id"))
        self.assertEqual(self.child_id, parent.private_data.get("material_job_id"))
        self.assertEqual(2, parent.summary.get("remote_chain_length"))
        self.assertIs(True, parent.summary.get("remote_polling"))
        self.assertEqual("pending", parent.payment_state)
        second_transport = _Transport([{"id": self.child_id, "status": "done", "result": {
            "checkout_url": "https://pay.example.test/child", "payment_status": "completed",
            "entitlement_active": True, "plan_type": "plus", "has_active_subscription": True,
            "entitlement_inferred": False,
        }}])
        child = HuanguangProvider(_config(), second_transport).get_status(self.root_id, private_data=parent.private_data)
        self.assertEqual(self.root_id, child.job_id)
        self.assertEqual("succeeded", child.payment_state)
        self.assertEqual(self.child_id, child.private_data.get("material_job_id"))
        self.assertIs(False, child.summary.get("remote_polling"))
        self.assertEqual("/api/checkout-progress?job_id=" + self.child_id, second_transport.calls[0][1])
        self.assertEqual("synthetic-job-secret", second_transport.calls[0][3].get("X-Pay153-Job-Secret"))
        self.assertEqual(2, len(child.private_data["job_chain"]))
        for private in (self.root_id, self.child_id, "synthetic-job-secret"):
            self.assertNotIn(private, repr(child.summary))

    def test_parent_unknown_is_not_erased_by_child_failure(self):
        transport = _Transport([self._parent(payment_status="payment_timeout")])
        parent = HuanguangProvider(_config(), transport).get_status(self.root_id, private_data={"job_secret": "synthetic-job-secret"})
        child = HuanguangProvider(_config(), _Transport([{"status": "error", "result": {
            "payment_status": "failed",
        }}])).get_status(self.root_id, private_data=parent.private_data)
        self.assertEqual("unknown", child.payment_state)
        self.assertIs(True, child.summary.get("automatic_payment_requires_reconcile"))

    def test_all_chain_failures_are_terminal_without_inheriting_parent_payment_into_child(self):
        parent = HuanguangProvider(_config(), _Transport([self._parent()])).get_status(
            self.root_id, private_data={"job_secret": "synthetic-job-secret"},
        )
        child = HuanguangProvider(_config(), _Transport([{"status": "error", "result": {"payment_status": "failed"}}])).get_status(
            self.root_id, private_data=parent.private_data,
        )
        self.assertEqual("failed", child.payment_state)
        self.assertIs(False, child.summary.get("remote_polling"))
        self.assertEqual("failed", child.private_data["job_chain"][0]["state"]["payment_state"])
        self.assertEqual("failed", child.private_data["job_chain"][1]["state"]["payment_state"])

    def test_parent_and_child_cannot_combine_incomplete_plus_evidence(self):
        parent_data = self._parent(payment_status="completed")
        parent_data["result"].update({"entitlement_active": True, "entitlement_inferred": False})
        parent = HuanguangProvider(_config(), _Transport([parent_data])).get_status(
            self.root_id, private_data={"job_secret": "synthetic-job-secret"},
        )
        child = HuanguangProvider(_config(), _Transport([{"status": "done", "result": {
            "payment_status": "completed", "plan_type": "plus", "has_active_subscription": True,
        }}])).get_status(self.root_id, private_data=parent.private_data)
        self.assertEqual("unknown", child.payment_state)
        self.assertNotEqual("verified", child.summary.get("platform_plus_status"))

    def test_each_query_discovers_at_most_one_child(self):
        parent = HuanguangProvider(_config(), _Transport([self._parent()])).get_status(
            self.root_id, private_data={"job_secret": "synthetic-job-secret"},
        )
        transport = _Transport([self._parent(child_id=self.grandchild_id)])
        child = HuanguangProvider(_config(), transport).get_status(self.root_id, private_data=parent.private_data)
        self.assertEqual(3, child.summary.get("remote_chain_length"))
        self.assertEqual(1, len(transport.calls))
        self.assertEqual(self.grandchild_id, child.private_data.get("active_job_id"))

    def test_known_parent_child_reference_is_not_mistaken_for_cycle(self):
        data = self._parent()
        data["result"]["auto_relink_status"] = "starting"
        parent = HuanguangProvider(_config(), _Transport([data])).get_status(
            self.root_id, private_data={"job_secret": "synthetic-job-secret"},
        )
        transport = _Transport([{"status": "running", "result": {}}, data])
        child = HuanguangProvider(_config(), transport).get_status(self.root_id, private_data=parent.private_data)
        self.assertEqual(2, child.summary.get("remote_chain_length"))
        self.assertNotIn("remote_chain_error", child.summary)
        self.assertIs(True, child.summary.get("remote_polling"))

    def test_bad_child_ids_self_links_and_cycles_stop_without_new_submissions(self):
        for child_id, expected in (("bad/child", "invalid_child_id"), (self.root_id, "cycle")):
            with self.subTest(child_id=child_id):
                transport = _Transport([self._parent(child_id=child_id)])
                job = HuanguangProvider(_config(), transport).get_status(self.root_id, private_data={"job_secret": "synthetic-job-secret"})
                self.assertEqual(expected, job.summary.get("remote_chain_error"))
                self.assertEqual("unknown", job.payment_state)
                self.assertIs(False, job.summary.get("remote_polling"))
                self.assertEqual(["GET"], [call[0] for call in transport.calls])
        parent = HuanguangProvider(_config(), _Transport([self._parent()])).get_status(
            self.root_id, private_data={"job_secret": "synthetic-job-secret"},
        )
        transport = _Transport([self._parent(child_id=self.root_id)])
        cycle = HuanguangProvider(_config(), transport).get_status(self.root_id, private_data=parent.private_data)
        self.assertEqual("cycle", cycle.summary.get("remote_chain_error"))
        self.assertEqual(2, len(cycle.private_data["job_chain"]))

    def test_chain_limit_preserves_twenty_existing_nodes(self):
        ids = [f"{index:016x}" for index in range(1, 21)]
        private = {
            "job_secret": "synthetic-job-secret", "root_job_id": ids[0], "active_job_id": ids[-1],
            "job_chain": [{"job_id": job_id, "parent_job_id": ids[index - 1] if index else None, "state": {
                "extraction_state": "failed", "payment_state": "failed", "summary": {"remote_polling": False},
            }} for index, job_id in enumerate(ids)],
        }
        transport = _Transport([self._parent(child_id="0000000000000015")])
        job = HuanguangProvider(_config(), transport).get_status(ids[0], private_data=private)
        self.assertEqual("chain_limit", job.summary.get("remote_chain_error"))
        self.assertEqual(20, len(job.private_data["job_chain"]))
        self.assertEqual("unknown", job.payment_state)
        self.assertEqual(["GET"], [call[0] for call in transport.calls])

    def test_child_network_failure_keeps_discovered_reference_and_private_receipt(self):
        parent = HuanguangProvider(_config(), _Transport([self._parent()])).get_status(self.root_id, private_data={
            "job_secret": "synthetic-job-secret", "batch_receipt_secret": "synthetic-batch-secret", "batch_receipt_pending": False,
        })
        transport = _Transport([TimeoutError()])
        job = HuanguangProvider(_config(), transport).get_status(self.root_id, private_data=parent.private_data)
        self.assertEqual(self.child_id, job.private_data.get("active_job_id"))
        self.assertEqual("synthetic-batch-secret", job.private_data.get("batch_receipt_secret"))
        self.assertIs(True, job.summary.get("remote_polling"))
        self.assertEqual("pending", job.payment_state)

    def test_same_node_keeps_payment_material_during_partial_progress(self):
        transport = _Transport([{"status": "running", "result": {
            "checkout_url": "https://pay.example.test/child", "qr_data": "upi://pay?pa=synthetic",
        }}, {"status": "running", "result": {"currency": "INR"}}])
        provider = HuanguangProvider(_config(), transport)
        first = provider.get_status(self.root_id, private_data={"job_secret": "synthetic-job-secret"})
        second = provider.get_status(self.root_id, private_data=first.private_data)
        self.assertEqual("succeeded", second.extraction_state)
        self.assertEqual(("https://pay.example.test/child",), second.links)
        self.assertEqual("upi://pay?pa=synthetic", second.payment_artifact.get("qr_data"))
        self.assertEqual("INR", second.payment_artifact.get("currency"))

    def test_legacy_root_seed_keeps_existing_link_when_first_progress_omits_material(self):
        transport = _Transport([{"status": "done", "result": {"payment_status": "payment_check_error"}}])
        job = HuanguangProvider(_config(), transport).get_status(self.root_id, private_data={
            "job_secret": "synthetic-job-secret", "previous_public_state": {
                "extraction_state": "succeeded", "payment_state": "unknown",
                "links": ["https://pay.example.test/existing"],
                "payment_artifact": {"payment_page_url": "https://pay.example.test/existing", "qr_data": "upi://pay?pa=synthetic"},
            },
        })
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual(("https://pay.example.test/existing",), job.links)
        self.assertEqual("upi://pay?pa=synthetic", job.payment_artifact.get("qr_data"))
        self.assertEqual("unknown", job.payment_state)
        self.assertIs(True, job.summary.get("extraction_ever_succeeded"))
        self.assertNotIn("remote_terminal_failure", job.summary)
        self.assertNotIn("failure_message", job.summary)
        self.assertNotIn("previous_public_state", job.private_data)

    def test_legacy_root_seed_keeps_explicit_remote_failure_with_existing_material(self):
        for status, payment_status, error, expected_payment in (
            ("error", "payment_check_error", "平台明确失败", "unknown"),
            ("cancelled", "payment_check_error", "平台明确失败", "unknown"),
            ("canceled", "payment_check_error", "平台明确失败", "unknown"),
            ("done", "payment_check_error", "平台明确失败", "unknown"),
            ("done", "failed", "", "failed"),
        ):
            with self.subTest(status=status, payment_status=payment_status):
                job = HuanguangProvider(_config(), _Transport([{
                    "status": status, "error": error,
                    "result": {"payment_status": payment_status},
                }])).get_status(self.root_id, private_data={
                    "job_secret": "synthetic-job-secret", "previous_public_state": {
                        "extraction_state": "succeeded", "payment_state": "unknown",
                        "links": ["https://pay.example.test/existing"],
                    },
                })
                self.assertEqual("succeeded", job.extraction_state)
                self.assertEqual(expected_payment, job.payment_state)
                self.assertIs(True, job.summary.get("remote_terminal_failure"))
                self.assertEqual(error or "幻光任务已结束，但未返回有效支付材料", job.summary.get("failure_message"))

    def test_legacy_root_seed_keeps_only_validated_snapshot_fields(self):
        job = HuanguangProvider(_config(), _Transport([TimeoutError()])).get_status(self.root_id, private_data={
            "job_secret": "synthetic-job-secret", "previous_public_state": {
                "extraction_state": "succeeded", "payment_state": "unknown",
                "links": ["javascript:alert(1)", "https://pay.example.test/existing"],
                "payment_links": ["https://pay.example.test/existing", {"raw": "synthetic-raw"}],
                "payment_artifact": {"payment_page_url": "https://pay.example.test/existing", "raw": "synthetic-raw"},
                "summary": {"remote_status": "RUNNING", "remote_polling": True, "raw": "synthetic-raw",
                            "extraction_ever_succeeded": True},
                "private_data": {"access_token": "synthetic-raw"}, "raw": "synthetic-raw",
            },
        })
        state = job.private_data["job_chain"][0]["state"]
        self.assertEqual(["https://pay.example.test/existing"], state["links"])
        self.assertEqual(["https://pay.example.test/existing"], state["payment_links"])
        self.assertIs(True, job.summary.get("remote_polling"))
        self.assertNotIn("synthetic-raw", repr(job.private_data))
        self.assertNotIn("previous_public_state", job.private_data)

    def test_existing_chain_does_not_accept_root_seed_as_child_material(self):
        root = HuanguangProvider(_config(), _Transport([self._parent()])).get_status(
            self.root_id, private_data={"job_secret": "synthetic-job-secret"},
        )
        private = {**root.private_data, "previous_public_state": {
            "extraction_state": "succeeded", "links": ["https://pay.example.test/root-only"],
        }}
        child = HuanguangProvider(_config(), _Transport([{"status": "running"}])).get_status(self.root_id, private_data=private)
        self.assertEqual("running", child.extraction_state)
        self.assertEqual((), child.links)
        self.assertIs(False, child.summary.get("extraction_ever_succeeded"))
        self.assertNotIn("previous_public_state", child.private_data)

    def test_extraction_fact_requires_material_and_ignores_untrusted_seed_summary(self):
        job = HuanguangProvider(_config(), _Transport([{"status": "done"}])).get_status(self.root_id, private_data={
            "job_secret": "synthetic-job-secret", "previous_public_state": {
                "extraction_state": "succeeded", "links": ["javascript:alert(1)"],
                "summary": {"extraction_ever_succeeded": True},
            },
        })
        self.assertEqual("failed", job.extraction_state)
        self.assertIs(False, job.summary.get("extraction_ever_succeeded"))

    def test_new_child_never_inherits_parent_material(self):
        data = self._parent()
        data["result"]["checkout_url"] = "https://pay.example.test/expired-parent"
        parent = HuanguangProvider(_config(), _Transport([data])).get_status(self.root_id, private_data={"job_secret": "synthetic-job-secret"})
        self.assertEqual((), parent.links)
        self.assertNotIn("payment_page_url", parent.payment_artifact)
        self.assertEqual("queued", parent.extraction_state)
        self.assertEqual(["https://pay.example.test/expired-parent"], parent.private_data["job_chain"][0]["state"]["links"])
        self.assertIs(True, parent.summary.get("extraction_ever_succeeded"))

    def test_pending_parent_queries_rotate_and_never_exceed_two_progress_gets(self):
        ids = [f"{index:016x}" for index in range(1, 21)]
        private = {"job_secret": "synthetic-job-secret", "job_chain": [
            {"job_id": job_id, "parent_job_id": ids[index - 1] if index else None, "state": {
                "extraction_state": "running", "payment_state": "pending", "summary": {"remote_polling": True},
            }} for index, job_id in enumerate(ids)
        ]}
        for parent_id in ids[:2]:
            transport = _Transport([{"status": "running"}, {"status": "running"}])
            job = HuanguangProvider(_config(), transport).get_status(ids[0], private_data=private)
            self.assertEqual([
                "/api/checkout-progress?job_id=" + ids[-1], "/api/checkout-progress?job_id=" + parent_id,
            ], [call[1] for call in transport.calls])
            private = job.private_data

    def test_status_call_has_one_total_deadline_and_restores_transport_deadline(self):
        observed = []

        class DeadlineTransport(_Transport):
            def request(self, *args, **kwargs):
                observed.append(self.deadline)
                return super().request(*args, **kwargs)

        transport = DeadlineTransport([{"status": "running"}])
        original = time.monotonic() + 100
        transport.deadline = original
        HuanguangProvider(_config(timeout=2), transport).get_status(self.root_id, private_data={"job_secret": "synthetic-job-secret"})
        self.assertEqual(original, transport.deadline)
        self.assertLess(observed[0], original)
        self.assertLessEqual(observed[0] - time.monotonic(), 2)

    def test_relink_metadata_and_private_ids_are_safe_when_remote_text_echoes_them(self):
        data = self._parent()
        data["text"] = "自动重提 " + self.child_id + " 原任务 " + self.root_id
        job = HuanguangProvider(_config(), _Transport([data])).get_status(self.root_id, private_data={"job_secret": "synthetic-job-secret"})
        self.assertEqual(1, job.summary.get("auto_relink_attempt"))
        for node in job.private_data["job_chain"]:
            self.assertNotIn(self.root_id, repr(node["state"]["summary"]))
            self.assertNotIn(self.child_id, repr(node["state"]["summary"]))

    def test_malformed_relink_status_is_ignored_without_stopping_progress(self):
        for value in ({"status": "starting"}, ["starting"], True):
            with self.subTest(value=value):
                job = HuanguangProvider._job({"status": "running", "result": {"auto_relink_status": value}}, self.root_id, "synthetic-job-secret")
                self.assertIs(True, job.summary.get("remote_polling"))
                self.assertNotIn("auto_relink_status", job.summary)

    def test_late_parent_verification_switches_material_owner_without_switching_active_child(self):
        data = self._parent(payment_status="pending")
        data["result"]["auto_relink_status"] = "starting"
        parent = HuanguangProvider(_config(), _Transport([data])).get_status(
            self.root_id, private_data={"job_secret": "synthetic-job-secret"})
        result = HuanguangProvider(_config(), _Transport([
            {"status": "running", "result": {"qr_data": "child-qr"}},
            {"status": "done", "result": {"payment_status": "completed", "entitlement_active": True,
                "entitlement_inferred": False, "plan_type": "plus", "has_active_subscription": True,
                "checkout_url": "https://pay.example.test/parent"}},
        ])).get_status(self.root_id, private_data=parent.private_data)
        self.assertEqual(self.child_id, result.private_data["active_job_id"])
        self.assertEqual(self.root_id, result.private_data["material_job_id"])
        self.assertEqual(("https://pay.example.test/parent",), result.links)
        self.assertNotIn("qr_data", result.payment_artifact)

    def _parent(self, *, payment_status="failed", child_id=None):
        return {"status": "done", "result": {
            "payment_status": payment_status, "auto_relink_job_id": child_id or self.child_id,
            "auto_relink_attempt": 1,
        }}


class _Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, *, json=None, headers=None, timeout=None):
        self.calls.append((method, path, json, headers, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _config(*, payment_cdk=None, auto_payment=False, capabilities=None, **provider_fields):
    kwargs = {"payment_cdk": payment_cdk} if payment_cdk is not None else {}
    return ProviderConfig(
        "huanguang", "https://provider.example.test", "synthetic-cdk",
        capabilities if capabilities is not None else {"extract": True, "payment": True, "auto_payment": auto_payment},
        **kwargs, **provider_fields,
    )
