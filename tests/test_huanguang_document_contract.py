"""幻光公开文档中的任务、二维码及到账证据契约。"""

import unittest

from core.extract_link_providers.contracts import ExtractRequest, ProviderConfig, ProviderError
from core.extract_link_providers.huanguang import HuanguangProvider


_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6kuUAAAAASUVORK5CYII="


class HuanguangDocumentContractTests(unittest.TestCase):
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

    @staticmethod
    def _job(data):
        return HuanguangProvider._job(data, "synthetic-job", "synthetic-private-secret")


class _Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, *, json=None, headers=None, timeout=None):
        self.calls.append((method, path, json, headers, timeout))
        return self.responses.pop(0)


def _config():
    return ProviderConfig("huanguang", "https://provider.example.test", "synthetic-cdk", {"extract": True, "payment": True})
