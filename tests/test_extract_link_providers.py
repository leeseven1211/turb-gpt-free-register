import unittest


class ExtractLinkProviderTests(unittest.TestCase):
    def test_registry_is_explicit_and_rejects_unknown_or_disabled_capability(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ProviderConfig, ProviderError

        config = ProviderConfig(
            provider_id="lumen_flow",
            api_base="https://lumen.example",
            cdk="private-cdk",
            capabilities={"extract": True, "payment": False},
        )
        provider = get_provider("lumen_flow", config=config, transport=object())
        self.assertEqual(provider.provider_id, "lumen_flow")
        with self.assertRaises(ProviderError):
            get_provider("missing", config=config, transport=object())
        with self.assertRaises(ProviderError) as error:
            provider.start_payment("job", {})
        self.assertEqual(error.exception.code, "unsupported")

    def test_lumen_extract_only_never_starts_payment(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ExtractRequest, ProviderConfig

        transport = _Transport([
            {"results": [{"outcome": "ACCEPTED", "task": {"taskId": "task-1", "status": "RUNNING"}}]},
            {"taskId": "task-1", "status": "SUCCEEDED", "result": {
                "paymentUrl": "https://legacy.example/keep",
                "hostedUrl": "https://pay.example/hosted?secret=private-url-token",
                "paymentArtifact": {"url": "https://pay.example/artifact", "processorUrl": "https://processor.example/pay"},
                "ordinaryUrl": "https://example.test/info",
            }},
        ])
        provider = get_provider("lumen_flow", config=_config("lumen_flow", capabilities={"extract": True, "payment": True}), transport=transport)
        request = ExtractRequest(7, "private-token", "pix", "extract_only", "idem-1", options={})

        result = provider.create_job(request)
        status = provider.get_status(result.job_id)

        self.assertEqual(result.extraction_state, "running")
        self.assertEqual(status.extraction_state, "succeeded")
        self.assertEqual(status.payment_links, (
            "https://pay.example/hosted?secret=private-url-token",
            "https://pay.example/artifact",
            "https://processor.example/pay",
        ))
        self.assertEqual(status.links, ("https://legacy.example/keep",))
        self.assertNotIn("private-url-token", repr(status))
        self.assertEqual(transport.calls[0][0:2], ("POST", "/public/api/checkout/flow/submit-batch"))
        self.assertNotIn("automaticMomoPayment", transport.calls[0][2]["requests"][0])
        self.assertEqual(transport.calls[1][0:2], ("GET", "/public/api/checkout/flow/task-1"))
        self.assertEqual(len(transport.calls), 2)

    def test_lumen_uses_configured_link_type_without_enabling_automatic_payment(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ExtractRequest

        transport = _Transport([{
            "results": [{"outcome": "ACCEPTED", "task": {"taskId": "task-7", "status": "QUEUED"}}],
        }])
        provider = get_provider("lumen_flow", config=_config("lumen_flow"), transport=transport)
        provider.create_job(ExtractRequest(7, "private-token", link_type="momo"))

        item = transport.calls[0][2]["requests"][0]
        self.assertEqual("MOMO", item["paymentMethodType"])
        self.assertNotIn("automaticMomoPayment", item)

    def test_lumen_unknown_status_is_conservative_and_error_hides_secrets(self):
        from core.extract_link_providers import get_provider

        transport = _Transport([{"taskId": "job", "status": "SOMETHING_NEW", "accessToken": "private-token"}])
        provider = get_provider("lumen_flow", config=_config("lumen_flow"), transport=transport)
        status = provider.get_status("job")
        self.assertEqual(status.extraction_state, "unknown")
        self.assertNotIn("private-token", repr(status))

    def test_lumen_terminal_failure_preserves_safe_reason_and_explicit_status(self):
        from core.extract_link_providers import get_provider

        for remote_status in ("FAILED", "CANCELED"):
            with self.subTest(remote_status=remote_status):
                provider = get_provider(
                    "lumen_flow", config=_config("lumen_flow"),
                    transport=_Transport([{
                        "taskId": "task-failed", "status": remote_status,
                        "error": {"message": "结账链接生成失败", "accessToken": "private-token"},
                    }]),
                )

                status = provider.get_status("task-failed")

                self.assertEqual(status.job_id, "task-failed")
                self.assertEqual(status.extraction_state, "failed")
                self.assertEqual(status.summary["remote_status"], remote_status)
                self.assertIs(status.summary["remote_terminal_failure"], True)
                self.assertEqual(status.summary["failure_message"], "结账链接生成失败")
                self.assertNotIn("private-token", repr(status))

    def test_lumen_status_requires_matching_remote_task_identity(self):
        from core.extract_link_providers import get_provider

        for identity in (
            {"taskId": "task-expected"},
            {"checkoutTaskId": "task-expected"},
            {"taskId": "task-expected", "checkoutTaskId": "task-expected"},
            {},
            {"taskId": None, "checkoutTaskId": ""},
        ):
            with self.subTest(identity=identity):
                provider = get_provider(
                    "lumen_flow", config=_config("lumen_flow"),
                    transport=_Transport([dict(identity, status="FAILED")]),
                )

                status = provider.get_status("task-expected")

                self.assertEqual(status.job_id, "task-expected")
                self.assertEqual(status.extraction_state, "failed")
                self.assertIs(status.summary["remote_terminal_failure"], True)

    def test_lumen_status_rejects_mismatched_or_invalid_remote_identity_safely(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ProviderError

        for identity in (
            {"taskId": "other-task-private-token"},
            {"checkoutTaskId": "other-task-private-token"},
            {"taskId": "task-expected", "checkoutTaskId": "other-task-private-token"},
            {"taskId": {"accessToken": "private-token"}},
        ):
            with self.subTest(identity=identity):
                provider = get_provider(
                    "lumen_flow", config=_config("lumen_flow"),
                    transport=_Transport([dict(identity, status="FAILED")]),
                )

                with self.assertRaises(ProviderError) as error:
                    provider.get_status("task-expected")

                self.assertIn("任务编号", str(error.exception))
                self.assertNotIn("private-token", str(error.exception))
                self.assertNotIn("task-expected", str(error.exception))

    def test_lumen_failure_reason_supports_message_fields_without_copying_raw_response(self):
        from core.extract_link_providers import get_provider

        for reason_field in ("error", "errorMessage", "failureReason", "message", "reason", "detail"):
            with self.subTest(reason_field=reason_field):
                provider = get_provider(
                    "lumen_flow", config=_config("lumen_flow"),
                    transport=_Transport([{
                        "taskId": "task-failed", "status": "FAILED",
                        "result": {reason_field: "平台暂时不可用", "accessToken": "private-token"},
                        "raw": {"cdk": "private-cdk"},
                    }]),
                )

                status = provider.get_status("task-failed")

                self.assertEqual(status.summary["failure_message"], "平台暂时不可用")
                self.assertNotIn("private-token", repr(status))
                self.assertNotIn("private-cdk", repr(status))

    def test_lumen_failure_reason_redacts_credentials_urls_and_email(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ExtractRequest

        reason = (
            "提链失败 private-token private-cdk，"
            '"accessToken": "other-token-value", CDK=other-cdk-value; '
            "https://checkout.example/pay?secret=private-url-token "
            "account@example.test"
        )
        provider = get_provider(
            "lumen_flow", config=_config("lumen_flow"),
            transport=_Transport([{"results": [{
                "outcome": "ACCEPTED",
                "task": {"taskId": "task-failed", "status": "FAILED", "errorMessage": reason},
            }]}]),
        )

        status = provider.create_job(ExtractRequest(7, "private-token"))

        self.assertIn("提链失败", status.summary["failure_message"])
        for private_value in (
            "private-token", "private-cdk", "other-token-value", "other-cdk-value",
            "private-url-token", "checkout.example", "account@example.test",
        ):
            self.assertNotIn(private_value, repr(status))

    def test_lumen_rejected_submission_keeps_safe_failure_reason(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ExtractRequest

        provider = get_provider(
            "lumen_flow", config=_config("lumen_flow"),
            transport=_Transport([{"results": [{
                "outcome": "REJECTED", "errorMessage": "当前提链类型不可用 private-cdk",
            }]}]),
        )

        status = provider.create_job(ExtractRequest(7, "private-token"))

        self.assertEqual(status.extraction_state, "failed")
        self.assertEqual(status.summary["outcome"], "REJECTED")
        self.assertIn("当前提链类型不可用", status.summary["failure_message"])
        self.assertNotIn("private-cdk", repr(status))
        self.assertNotIn("remote_terminal_failure", status.summary)

    def test_lumen_failure_reason_redacts_short_bearer_cookie_and_other_cdk(self):
        from core.extract_link_providers import get_provider

        reason = (
            '平台返回错误，Authorization: Bearer abc; "Cookie": "sid=hidden; session=private-cookie"; '
            "Bearer xyz AAM-0123456789ABCDEF0123456789ABCDEF"
        )
        provider = get_provider(
            "lumen_flow", config=_config("lumen_flow"),
            transport=_Transport([{"taskId": "task-failed", "status": "FAILED", "error": reason}]),
        )

        status = provider.get_status("task-failed")

        self.assertIn("平台返回错误", status.summary["failure_message"])
        for private_value in ("abc", "xyz", "hidden", "private-cookie", "AAM-0123456789ABCDEF0123456789ABCDEF"):
            self.assertNotIn(private_value, repr(status))

    def test_lumen_unknown_or_running_status_does_not_claim_terminal_failure(self):
        from core.extract_link_providers import get_provider

        for remote_status in ("RUNNING", "PRIVATE_NEW_STATUS_private-token"):
            with self.subTest(remote_status=remote_status):
                provider = get_provider(
                    "lumen_flow", config=_config("lumen_flow"),
                    transport=_Transport([{
                        "taskId": "task-running", "status": remote_status,
                        "errorMessage": "暂时失败，平台仍在重试 private-token",
                    }]),
                )

                status = provider.get_status("task-running")

                self.assertNotIn("remote_terminal_failure", status.summary)
                self.assertNotIn("failure_message", status.summary)
                self.assertNotIn("private-token", repr(status))

    def test_lumen_checkout_success_does_not_imply_payment_success(self):
        from core.extract_link_providers import get_provider

        provider = get_provider(
            "lumen_flow",
            config=_config("lumen_flow"),
            transport=_Transport([{"taskId": "task-6", "status": "SUCCEEDED", "result": {}}]),
        )

        status = provider.get_status("task-6")

        self.assertEqual(status.extraction_state, "succeeded")
        self.assertEqual(status.payment_state, "unknown")

    def test_lumen_payment_sync_is_explicit_and_does_not_start_payment(self):
        from core.extract_link_providers import get_provider

        transport = _Transport([{
            "taskId": "task-2",
            "status": "SUCCEEDED",
            "result": {"paymentStatus": "requires_action"},
            "nextPaymentStateSyncAt": "2026-10-22T12:00:00Z",
        }])
        provider = get_provider("lumen_flow", config=_config("lumen_flow"), transport=transport)

        result = provider.sync_payment_state("task-2")

        self.assertEqual(result.extraction_state, "succeeded")
        self.assertEqual(result.payment_state, "pending")
        self.assertEqual(
            result.private_data["next_payment_state_sync_at"],
            "2026-10-22T12:00:00Z",
        )
        self.assertEqual(transport.calls[0][0:2], (
            "POST", "/public/api/checkout/flow/task-2/sync-payment-state",
        ))
        self.assertEqual(transport.calls[0][2], {})

    def test_lumen_auto_momo_uses_its_own_read_only_status_endpoint(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ExtractRequest

        transport = _Transport([
            {"results": [{"outcome": "ACCEPTED", "task": {"taskId": "task-3", "status": "RUNNING"}}]},
            {"checkoutTaskId": "task-3", "status": "PAYMENT_UNCERTAIN"},
        ])
        provider = get_provider("lumen_flow", config=_config("lumen_flow"), transport=transport)
        provider.create_job(ExtractRequest(
            7, "private-token", mode="auto_payment", options={"payment_method": "MOMO"},
        ))

        payment = provider.get_automatic_payment_status("task-3")

        self.assertEqual(payment.payment_state, "unknown")
        self.assertEqual(transport.calls[0][2]["requests"][0]["automaticMomoPayment"], True)
        self.assertEqual(transport.calls[1][0:2], (
            "GET", "/public/api/checkout/flow/task-3/momo-payment",
        ))

    def test_lumen_auto_momo_success_is_payment_success_not_checkout_success(self):
        from core.extract_link_providers import get_provider

        provider = get_provider(
            "lumen_flow",
            config=_config("lumen_flow"),
            transport=_Transport([{"checkoutTaskId": "task-7", "status": "PAYMENT_SUCCEEDED"}]),
        )

        payment = provider.get_automatic_payment_status("task-7")

        self.assertEqual(payment.extraction_state, "unknown")
        self.assertEqual(payment.payment_state, "succeeded")

    def test_lumen_plus_verification_sync_requires_and_sends_original_token(self):
        from core.extract_link_providers import get_provider

        transport = _Transport([{
            "taskId": "task-4", "status": "SUCCEEDED", "plusVerificationStatus": "CHECKING",
        }])
        provider = get_provider("lumen_flow", config=_config("lumen_flow"), transport=transport)

        result = provider.sync_plus_verification("task-4", "private-token")

        self.assertEqual(result.summary["plus_verification_status"], "CHECKING")
        self.assertEqual(transport.calls[0][0:2], (
            "POST", "/public/api/checkout/flow/task-4/sync-plus-verification",
        ))
        self.assertEqual(transport.calls[0][2], {"accessToken": "private-token"})
        self.assertNotIn("private-token", repr(result))

    def test_lumen_start_payment_is_explicitly_unsupported_without_a_request(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ProviderError

        transport = _Transport([])
        provider = get_provider("lumen_flow", config=_config("lumen_flow"), transport=transport)

        with self.assertRaises(ProviderError) as error:
            provider.start_payment("task-5", {})

        self.assertEqual(error.exception.code, "unsupported")
        self.assertEqual(transport.calls, [])

    def test_huanguang_requires_preassigned_routes_and_keeps_job_secret_private(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ExtractRequest, ProviderConfig

        transport = _Transport([
            {"ok": True, "job_id": "hg-1", "job_secret": "private-secret"},
            {"job_id": "hg-1", "status": "running", "percent": 50,
             "result": {"short_link": "https://pay.example/short", "provider_redirect_url": "https://provider.example/pay", "checkout_url": "https://checkout.example/pay", "qr_data": "upi://pay/example"}},
        ])
        provider = get_provider("huanguang", config=_config("huanguang"), transport=transport)
        request = ExtractRequest(8, "private-token", "upi", "extract_only", "idem-2", options={}, entry_proxy="http://entry", exit_proxy="http://exit")
        created = provider.create_job(request)
        status = provider.get_status(created.job_id)

        self.assertEqual(status.extraction_state, "running")
        self.assertEqual(status.payment_links, (
            "https://pay.example/short",
            "https://provider.example/pay",
            "https://checkout.example/pay",
        ))
        self.assertNotIn("private-secret", repr(created))
        self.assertEqual(transport.calls[0][1], "/api/checkout")
        self.assertEqual(transport.calls[0][2]["entry_proxies"], ["http://entry"])
        self.assertEqual(transport.calls[0][2]["exit_proxies"], ["http://exit"])
        self.assertEqual(transport.calls[1][3]["headers"]["X-Pay153-Job-Secret"], "private-secret")

    def test_huanguang_restores_job_secret_after_provider_restart(self):
        from core.extract_link_providers import get_provider

        transport = _Transport([{"id": "hg-1", "status": "done"}])
        provider = get_provider("huanguang", config=_config("huanguang"), transport=transport)
        self.assertEqual(
            provider.get_status("hg-1", private_data={"job_secret": "private-secret"}).extraction_state,
            "succeeded",
        )

    def test_huanguang_rejects_unsupported_second_payment_explicitly(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ProviderError

        provider = get_provider("huanguang", config=_config("huanguang"), transport=_Transport([]))
        with self.assertRaises(ProviderError) as error:
            provider.start_payment("job", {})
        self.assertEqual(error.exception.code, "unsupported")

    def test_legacy_adapter_preserves_existing_create_and_status_protocol(self):
        from core.extract_link_providers import get_provider
        from core.extract_link_providers.contracts import ExtractRequest

        transport = _Transport([
            {"ok": True, "job_id": "legacy-1"},
            {"job": {"status": "done", "result": {
                "short_link": "https://pay.example/legacy?secret=private-url-token",
                "checkout_url": "https://checkout.example/pay",
                "ordinary_url": "https://example.test/help",
            }}},
        ])
        provider = get_provider("legacy", config=_config("legacy"), transport=transport)
        created = provider.create_job(ExtractRequest(9, "private-token", "pix", "extract_only", "idem-3", options={}))
        status = provider.get_status(created.job_id)
        self.assertEqual(created.job_id, "legacy-1")
        self.assertEqual(status.extraction_state, "succeeded")
        self.assertEqual(status.links, (
            "https://pay.example/legacy?secret=private-url-token",
            "https://checkout.example/pay",
        ))
        self.assertEqual(status.payment_links, (
            "https://pay.example/legacy?secret=private-url-token",
            "https://checkout.example/pay",
        ))
        self.assertNotIn("private-url-token", repr(status))
        self.assertEqual(transport.calls[0][1], "/api/extract")
        self.assertTrue(transport.calls[1][1].startswith("/api/jobs/legacy-1/events?cdk="))

    def test_secret_values_are_omitted_from_object_representations(self):
        from core.extract_link_providers.contracts import ExtractRequest, ProviderJob

        config = _config("legacy")
        request = ExtractRequest(1, "private-token", options={"cdk": "private-cdk"})
        result = ProviderJob(private_data={"job_secret": "private-secret"})
        for value in (config, request, result):
            self.assertNotIn("private-cdk", repr(value))
            self.assertNotIn("private-token", repr(value))
            self.assertNotIn("private-secret", repr(value))


class PaymentArtifactProviderTests(unittest.TestCase):
    def test_lumen_keeps_checkout_page_payment_entry_and_original_qr_separately(self):
        from core.extract_link_providers import get_provider

        qr_data = "upi://pay?pa=synthetic@example.test&am=0&tn=Token%2BExact"
        provider = get_provider("lumen_flow", config=_config("lumen_flow"), transport=_Transport([{
            "taskId": "artifact-task", "status": "SUCCEEDED", "plusVerificationStatus": "ACTIVE",
            "result": {
                "hostedUrl": "https://checkout.example.test/page", "paymentStatus": "requires_action",
                "amount": 0, "currency": "BRL", "paymentArtifact": {
                    "data": qr_data, "imageUrlPng": "https://qr.example.test/code.png",
                    "imageUrlSvg": "https://qr.example.test/code.svg",
                    "hostedInstructionsUrl": "https://payments.example.test/instructions",
                    "expiresAt": 1792800000, "accessToken": "must-not-project",
                },
            },
        }]))
        job = provider.get_status("artifact-task")
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual("pending", job.payment_state)
        self.assertEqual({
            "payment_page_url": "https://checkout.example.test/page",
            "payment_url": "https://payments.example.test/instructions",
            "qr_data": qr_data, "qr_image_url_png": "https://qr.example.test/code.png",
            "qr_image_url_svg": "https://qr.example.test/code.svg", "amount": 0, "currency": "BRL",
            "expires_at": "2026-10-24T00:00:00Z", "payment_status": "requires_action",
            "platform_plus_status": "ACTIVE",
        }, job.payment_artifact)
        self.assertNotIn(qr_data, repr(job))
        self.assertNotIn("must-not-project", repr(job))

    def test_payment_artifact_rejects_invalid_urls_without_truncating_payment_data(self):
        from core.extract_link_providers.contracts import safe_payment_artifact

        long_url = "https://checkout.example.test/" + "x" * 3000
        self.assertEqual({"payment_page_url": long_url}, safe_payment_artifact({"payment_page_url": long_url}))
        for url in ("javascript:alert(1)", "https://user:pass@example.test/code", "https://[", "https://example.test/\ncode", "https://example.test/" + "x" * 17000):
            with self.subTest(url=url[:30]):
                self.assertEqual({}, safe_payment_artifact({"payment_url": url}))
        self.assertEqual({}, safe_payment_artifact({"qr_data": "x" * 65537, "amount": True, "extra": "private"}))
        self.assertEqual({"qr_data": "  exact payload\n", "amount": 0}, safe_payment_artifact({"qr_data": "  exact payload\n", "amount": 0}))
        for amount in (float("inf"), float("nan"), -1, 10 ** 999):
            self.assertEqual({}, safe_payment_artifact({"amount": amount}))

    def test_payment_expiration_normalizes_seconds_and_rejects_invalid_values(self):
        from core.extract_link_providers.contracts import safe_payment_artifact

        for expires in (1792800000, 1792800000.0, "2026-10-24T08:00:00+08:00"):
            self.assertEqual({"expires_at": "2026-10-24T00:00:00Z"}, safe_payment_artifact({"expires_at": expires}))
        for expires in (True, -1, 10 ** 999, float("inf"), "not-a-date", "2026-10-24T00:00:00", "9999-12-31T23:59:59-23:00"):
            self.assertEqual({}, safe_payment_artifact({"expires_at": expires}))

    def test_other_providers_preserve_native_qr_artifacts(self):
        from core.extract_link_providers.huanguang import HuanguangProvider
        from core.extract_link_providers.legacy import LegacyProvider

        result = {"checkout_url": "https://checkout.example.test/page", "qr_data": "upi://pay?pa=synthetic&tn=Token%2BExact", "image_url_png": "https://qr.example.test/code.png", "image_url_svg": "https://qr.example.test/code.svg", "amount": 0}
        for job in (HuanguangProvider._job({"status": "done", "result": result}, "hg-job", "private-secret"), LegacyProvider._job({"status": "done", "result": result}, "legacy-job")):
            self.assertEqual("succeeded", job.extraction_state)
            self.assertEqual({"payment_page_url": result["checkout_url"], "qr_data": result["qr_data"], "qr_image_url_png": result["image_url_png"], "qr_image_url_svg": result["image_url_svg"], "amount": 0}, job.payment_artifact)


class _Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, *, json=None, headers=None, timeout=None):
        self.calls.append((method, path, json or {}, {"headers": headers or {}, "timeout": timeout}))
        response = self.responses.pop(0)
        return response

    def events(self, path, *, timeout=None):
        self.calls.append(("SSE", path, {}, {"timeout": timeout}))
        return [("progress", self.responses.pop(0))]


def _config(provider_id, capabilities=None):
    from core.extract_link_providers.contracts import ProviderConfig

    return ProviderConfig(provider_id, "https://provider.example", "private-cdk", capabilities or {"extract": True, "payment": True})
