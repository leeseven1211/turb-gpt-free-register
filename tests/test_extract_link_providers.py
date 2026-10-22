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
