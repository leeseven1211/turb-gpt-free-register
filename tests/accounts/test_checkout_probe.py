# -*- coding: utf-8 -*-
"""结账预检仅访问官方接口，且不会确认支付或泄露私有响应。"""
import json
import time
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from curl_cffi.requests import exceptions as curl_exceptions

from core.accounts.plans import checkout_probe as probe
from core.auth.protocol import sentinel_runner
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost


class CheckoutProbeTests(unittest.TestCase):
    def setUp(self):
        self.env = Mock()
        self.env.device_id = "device-demo"
        self.env.sentinel_sid = "sentinel-demo"
        self.env.proxy = "http://proxy.invalid:8080"
        self.env.browser_profile = {"user_agent": "Browser UA", "navigator_language": "ja-JP", "timezone_iana": "Asia/Tokyo"}
        self.env.chrome_identity = {"impersonate": "chrome136"}
        self.env.get_chatgpt_headers.return_value = {"User-Agent": "Browser UA", "Accept-Language": "ja-JP", "oai-device-id": "device-demo"}
        self.env.get_sentinel_headers.return_value = {"Origin": "https://sentinel.openai.com"}
        self.env.chatgpt_cookie_header.return_value = "oai-did=device-demo"
        self.risk = patch.object(probe, "_checkout_risk_headers", return_value={})
        self.risk_mock = self.risk.start()
        self.addCleanup(self.risk.stop)
        self.pricing = {"country_code": "JP", "currency_config": {"symbol_code": "JPY", "minor_unit_exponent": 0}}

    @staticmethod
    def response(payload, status=200):
        return Mock(status_code=status, json=Mock(return_value=payload))

    def prepare_oaics(self, state):
        self.env.get.side_effect = [self.response(self.pricing), self.response(state)]
        self.env.post.return_value = self.response({"checkout_session_id": "oaics_private_session", "processor_entity": "openai_ie"})

    def query(self, **kwargs):
        return probe.query_checkout_details("private-access-token", session=self.env, country="JP", campaign_id="plus-half-price", **kwargs)

    def test_oaics_zero_and_half_price_are_both_success_and_reuse_session(self):
        for due in (0, 1500):
            with self.subTest(due=due):
                self.env.reset_mock()
                self.prepare_oaics({"paymentMethodTypes": ["card", "LINK", "card"], "total": {"total": {"minorUnitsAmount": str(due)}, "subtotal": 3000, "taxInclusive": 0}})
                result = self.query()
                self.assertEqual(result["checkout_status"], "success")
                self.assertEqual(result["session_type"], "oaics")
                self.assertEqual(result["payment_method_types"], ["card", "link"])
                self.assertEqual(result["checkout_amount_due_minor"], due)
                self.assertEqual(result["checkout_amount_source"], "total.total")
                self.assertEqual((result["checkout_currency"], result["checkout_currency_exponent"]), ("JPY", 0))
                self.assertEqual(self.env.post.call_count, 1)
                self.assertEqual(self.env.post.call_args.kwargs["json"]["promo_campaign"]["promo_campaign_id"], "plus-half-price")
                self.assertIn("/checkout/openai_ie/oaics_private_session", self.env.get.call_args.args[0])
                self.assertFalse(self.env.close.called)
                for call in self.env.get.call_args_list + self.env.post.call_args_list:
                    self.assertFalse(call.kwargs["allow_redirects"])
                    self.assertGreater(call.kwargs["timeout"], 0)
                    self.assertLessEqual(call.kwargs["timeout"], 15)

    def test_methods_success_does_not_infer_zero_from_tax_or_discount(self):
        self.prepare_oaics({"payment_method_types": ["card"], "total": {"subtotal": 2000, "discount": 2000, "taxInclusive": 0}})
        result = self.query()
        self.assertEqual(result["checkout_status"], "success")
        self.assertIsNone(result["checkout_amount_due_minor"])
        self.assertIsNone(result["checkout_amount_source"])

    def test_nested_amount_and_custom_methods_have_controlled_field_path(self):
        self.prepare_oaics({"checkout_state": {"custom_payment_methods": [{"type": "gcash", "id": "cpmt_private"}], "invoice": {"amount_due": 22}}})
        result = self.query()
        self.assertEqual(result["payment_method_types"], ["gcash"])
        self.assertEqual(result["checkout_amount_source"], "checkout_state.invoice.amount_due")
        self.assertEqual(result["checkout_amount_due_minor"], 22)

    def test_nested_amount_currency_mismatch_never_uses_pricing_currency(self):
        cases = (
            {"invoice": {"amount_due": 1000, "currency": "usd"}},
            {"total": {"total": {"minorUnitsAmount": 0, "currency": "USD"}}},
            {"total": {"total": {"minorUnitsAmount": 0, "currency": {"symbol_code": "USD"}}}},
            {"total": {"currency": {"code": "USD"}, "total": 0}},
            {"checkout_state": {"currency": "USD", "invoice": {"amount_due": 0}}},
            {"checkout_state": {"invoice": {"currency": {"currency_code": "USD"}, "amount_due": 0}}},
        )
        for state in cases:
            with self.subTest(state=state):
                self.prepare_oaics({"payment_method_types": ["card"], **state})
                result = self.query()
                self.assertEqual(result["checkout_status"], "failed")
                self.assertEqual(result["checkout_error"], "结账币种与定价配置不一致")
                self.assertIsNone(result["checkout_amount_due_minor"])
                self.assertIsNone(result["checkout_amount_source"])

    def test_nested_amount_currency_object_and_ancestors_match_pricing(self):
        self.prepare_oaics({
            "currency": {"symbol_code": "jpy"}, "payment_method_types": ["card"],
            "checkout_state": {"currency": "JPY", "total": {
                "currency": {"code": "jpy"},
                "total": {"minorUnitsAmount": 1500, "currency": {"symbol_code": "JPY"}},
                "subtotal": {"amount": 2000, "currency": "USD"},
            }},
        })
        result = self.query()
        self.assertEqual(result["checkout_status"], "success")
        self.assertEqual(result["checkout_amount_due_minor"], 1500)
        self.assertEqual(result["checkout_currency"], "JPY")
        self.assertEqual(result["checkout_amount_source"], "checkout_state.total.total")

    def test_custom_payment_methods_use_only_controlled_name_mapping_without_type(self):
        self.prepare_oaics({"custom_payment_methods": [
            {"id": "cpmt_private_upi", "name": "UPI"},
            {"id": "cpmt_private_gcash", "display_name": "GCash"},
            {"id": "cpmt_private_card", "display": {"label": "银行卡"}},
            {"id": "cpmt_private_link", "displayName": "Link"},
            {"id": "cpmt_private_card_alias", "name": "Credit/debit card"},
            {"id": "cpmt_private_only"},
            {"id": "cpmt_private_unknown", "name": "private-access-token"},
            {"id": "cpmt_private_suffix", "display_name": "GCash private-access-token"},
        ], "total": {"total": 0}})
        result = self.query()
        self.assertEqual(result["checkout_status"], "success")
        self.assertEqual(result["payment_method_types"], ["upi", "gcash", "card", "link"])
        self.assertEqual(result["checkout_amount_due_minor"], 0)
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("cpmt_", json.dumps(result))

    def test_custom_payment_method_names_and_ids_are_not_guessed(self):
        self.prepare_oaics({"custom_payment_methods": [
            {"id": "cpmt_card_link_upi_gcash"},
            {"id": "cpmt_private", "name": "UPI private-access-token"},
            {"id": "cpmt_private", "display": "person@example.com"},
        ]})
        result = self.query()
        self.assertEqual(result["checkout_status"], "failed")
        self.assertEqual(result["payment_method_types"], [])
        self.assertNotIn("private", json.dumps(result))

    def test_stripe_init_has_no_chatgpt_credentials_and_never_confirms(self):
        self.env.get.return_value = self.response(self.pricing)
        self.env.post.return_value = self.response({"id": "cs_live_private_session", "publishable_key": "pk_live_demo123456"})
        stripe = Mock()
        stripe.post.return_value = self.response({"payment_method_types": ["card", "link", "upi"], "invoice": {"amount_due": 1000}, "currency": "jpy"})
        with patch.object(probe, "Session", return_value=stripe) as factory:
            result = self.query()
        self.assertEqual(result["checkout_status"], "success")
        self.assertEqual(result["session_type"], "cs_live")
        self.assertEqual(result["checkout_amount_due_minor"], 1000)
        self.assertEqual(result["payment_method_types"], ["card", "link", "upi"])
        factory.assert_called_once_with(impersonate="chrome136")
        self.assertEqual(stripe.proxies, {"http": self.env.proxy, "https": self.env.proxy})
        stripe.post.assert_called_once()
        call = stripe.post.call_args
        self.assertEqual(call.args[0], "https://api.stripe.com/v1/payment_pages/cs_live_private_session/init")
        self.assertFalse(call.kwargs["allow_redirects"])
        self.assertNotIn("private-access-token", json.dumps(call.kwargs))
        self.assertNotIn("cookie", {key.lower() for key in call.kwargs["headers"]})
        self.assertNotIn("authorization", {key.lower() for key in call.kwargs["headers"]})
        stripe.close.assert_called_once()
        self.assertEqual(self.env.post.call_count, 1)
        self.assertFalse(self.env.close.called)
        self.assertNotIn("private_session", json.dumps(result))
        self.assertNotIn("pk_live", json.dumps(result))

    def test_untrusted_type_entity_key_and_checkout_url_never_control_destination(self):
        cases = (
            ({"id": "cs_test_demo", "publishable_key": "pk_live_demo123456"}, "结账会话类型未知"),
            ({"id": "random_opaque_session"}, "结账会话类型未知"),
            ({"id": "oaics_demo/../secret", "processor_entity": "openai_ie"}, "结账会话类型未知"),
            ({"id": "oaics_demo", "processor_entity": "https://evil.invalid"}, "结账处理实体无效"),
            ({"id": "cs_live_demo", "publishable_key": "sk_live_secret"}, "结账公开密钥无效"),
        )
        for body, error in cases:
            with self.subTest(body=body):
                self.env.reset_mock()
                self.env.get.side_effect = None
                self.env.get.return_value = self.response(self.pricing)
                self.env.post.return_value = self.response({**body, "url": "https://evil.invalid/token=private"})
                with patch.object(probe, "Session") as stripe:
                    result = self.query()
                self.assertEqual(result["checkout_status"], "failed")
                self.assertEqual(result["checkout_error"], error)
                self.assertEqual(self.env.get.call_count, 1)
                stripe.assert_not_called()

    def test_method_identifier_and_credential_values_never_escape(self):
        self.prepare_oaics({"payment_method_types": ["card", "eyJ-secret", "pi_live_secret", "cs_live_secret", "credential", "token", "person@example.com", {"id": "card"}, {"type": "upi"}], "access_token": "private-access-token", "total": {"total": 0}})
        result = self.query()
        self.assertEqual(result["payment_method_types"], ["card", "upi"])
        output = json.dumps(result)
        for secret in ("private-access-token", "secret", "person@", "credential"):
            self.assertNotIn(secret, output)

    def test_http_and_malformed_bodies_return_only_safe_failure(self):
        for body, status in (({"error": "Bearer private-access-token person@example.com"}, 400), (["private-access-token"], 200), ({"payment_method_types": ["card"], "error": "private-access-token"}, 200)):
            with self.subTest(status=status, body=body):
                self.env.reset_mock()
                self.env.get.side_effect = None
                self.env.get.return_value = self.response(body, status)
                result = self.query()
                self.assertEqual(result["checkout_status"], "failed")
                self.assertNotIn("private-access-token", json.dumps(result))
                self.env.post.assert_not_called()

    def test_pricing_country_currency_and_exponent_are_verified_without_fallback(self):
        for currency, cc in (({"symbol_code": "JPY", "minor_unit_exponent": 0}, "US"), ({"symbol_code": "JPY"}, "JP"), ({"symbol_code": "JPY", "minor_unit_exponent": True}, "JP"), ({"symbol_code": "PRIVATE", "minor_unit_exponent": 2}, "JP")):
            with self.subTest(currency=currency, cc=cc):
                self.env.reset_mock()
                self.env.get.side_effect = None
                self.env.get.return_value = self.response({"country_code": cc, "currency_config": currency})
                result = self.query()
                self.assertEqual(result["checkout_status"], "failed")
                self.assertEqual(result["checkout_error"], "定价配置无效")
                self.env.post.assert_not_called()

    def test_expired_budget_does_not_create_checkout_or_request_anything(self):
        result = self.query(deadline_at=time.time() - 1)
        self.assertEqual(result["checkout_error"], "结账预检预算已用尽")
        self.env.get.assert_not_called()
        self.env.post.assert_not_called()
        self.risk_mock.assert_not_called()

    def test_budget_exhausted_by_risk_does_not_create_checkout(self):
        self.env.get.return_value = self.response(self.pricing)
        with patch.object(probe.time, "time", side_effect=[100, 100, 105]), patch.object(probe.logger, "warning"):
            result = self.query(deadline_at=104)
        self.assertEqual(result["checkout_error"], "结账预检预算已用尽")
        self.assertIsNone(result["checkout_http_status"])
        self.env.post.assert_not_called()

    def test_post_timeout_is_not_replayed_and_does_not_expose_exception(self):
        self.env.get.return_value = self.response(self.pricing)
        self.env.post.side_effect = RuntimeError("private-access-token https://evil.invalid person@example.com")
        result = self.query()
        self.assertEqual(result["checkout_status"], "failed")
        self.assertEqual(self.env.post.call_count, 1)
        self.assertNotIn("private-access-token", json.dumps(result))
        self.assertNotIn("evil.invalid", json.dumps(result))

    def test_sentinel_request_failure_logs_only_safe_stage_and_curl_code(self):
        self.risk.stop()
        self.env.get.return_value = self.response(self.pricing)
        error = RuntimeError("private-access-token https://secret.invalid/oaics_private person@example.com")
        error.code = 56
        self.env.post.side_effect = error
        with patch.object(probe, "generate_sentinel_token") as runner, self.assertLogs(probe.logger, level="WARNING") as logs:
            result = self.query()
        self.assertEqual(result["checkout_status"], "failed")
        self.assertIsNone(result["checkout_http_status"])
        self.assertEqual(len(logs.output), 1)
        self.assertIn("country=JP stage=sentinel_request exception=RuntimeError curl_code=56", logs.output[0])
        self.assertNotIn("sentinel_token", logs.output[0])
        self.assertNotIn("private", logs.output[0])
        self.assertNotIn("secret.invalid", logs.output[0])
        self.assertNotIn("https://", logs.output[0])
        self.assertNotIn("person@", logs.output[0])
        self.assertIsNone(logs.records[0].exc_info)
        runner.assert_not_called()
        self.assertEqual(self.env.post.call_count, 1)

    def test_sentinel_token_failure_and_timeout_are_distinct_from_request(self):
        self.risk.stop()
        self.env.get.return_value = self.response(self.pricing)
        self.env.post.return_value = self.response({"token": "private-challenge"})
        for error in (RuntimeError("private-access-token https://secret.invalid"), TimeoutError("private-access-token https://secret.invalid")):
            with self.subTest(error=type(error).__name__):
                with patch.object(probe, "generate_sentinel_token", side_effect=error), self.assertLogs(probe.logger, level="WARNING") as logs:
                    result = self.query()
                self.assertEqual(result["checkout_status"], "failed")
                self.assertIsNone(result["checkout_http_status"])
                self.assertEqual(len(logs.output), 1)
                self.assertIn("country=JP stage=sentinel_token", logs.output[0])
                self.assertNotIn("sentinel_request", logs.output[0])
                self.assertNotIn("private", logs.output[0])
                self.assertNotIn("https://", logs.output[0])
                self.assertEqual(result["checkout_error"], "结账预检预算已用尽" if isinstance(error, TimeoutError) else "结账预检失败")

    def test_other_network_and_parse_phases_have_fixed_safe_diagnostics(self):
        for stage in ("pricing", "create", "oaics_state", "stripe_init", "parse"):
            with self.subTest(stage=stage), ExitStack() as stack:
                self.env.reset_mock()
                self.env.get.side_effect = None
                self.env.post.side_effect = None
                self.env.get.return_value = self.response(self.pricing)
                error = RuntimeError("private-access-token https://secret.invalid")
                error.code = "https://secret.invalid/private-access-token"
                if stage == "pricing":
                    self.env.get.side_effect = error
                elif stage == "create":
                    self.env.post.side_effect = error
                elif stage == "oaics_state":
                    self.prepare_oaics({})
                    self.env.get.side_effect = [self.response(self.pricing), error]
                elif stage == "stripe_init":
                    self.env.post.return_value = self.response({"id": "cs_live_private_session", "publishable_key": "pk_live_demo123456"})
                    stack.enter_context(patch.object(probe, "_stripe_init", side_effect=error))
                else:
                    self.prepare_oaics({"payment_method_types": ["card"], "total": {"total": 0}})
                    stack.enter_context(patch.object(probe, "_details", side_effect=error))
                with self.assertLogs(probe.logger, level="WARNING") as logs:
                    result = self.query()
                self.assertEqual(result["checkout_status"], "failed")
                self.assertIsNone(result["checkout_http_status"])
                self.assertEqual(len(logs.output), 1)
                self.assertIn(f"country=JP stage={stage} exception=RuntimeError curl_code=None", logs.output[0])
                self.assertNotIn("private", logs.output[0])
                self.assertNotIn("https://", logs.output[0])
                self.assertLessEqual(self.env.post.call_count, 1)

    def test_real_sentinel_http_failure_retains_its_response_status(self):
        self.risk.stop()
        self.env.get.return_value = self.response(self.pricing)
        self.env.post.return_value = self.response({"error": "private-access-token https://secret.invalid"}, status=403)
        result = self.query()
        self.assertEqual(result["checkout_status"], "failed")
        self.assertEqual(result["checkout_http_status"], 403)
        self.assertEqual(result["checkout_error"], "结账风控预检失败")
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("proxy_transport_failure", result)

    def _transport_failure_query(self, stage, error):
        self.env.reset_mock(side_effect=True)
        self.env.get.return_value = self.response(self.pricing)
        with ExitStack() as stack:
            if stage == "pricing":
                self.env.get.side_effect = error
            elif stage == "sentinel_request":
                stack.enter_context(patch.object(probe, "_checkout_risk_headers", side_effect=error))
            elif stage == "create":
                self.env.post.side_effect = error
            elif stage == "oaics_state":
                self.prepare_oaics({})
                self.env.get.side_effect = [self.response(self.pricing), error]
            elif stage == "stripe_init":
                self.env.post.return_value = self.response({"id": "cs_live_private_session", "publishable_key": "pk_live_demo123456"})
                stack.enter_context(patch.object(probe, "_stripe_init", side_effect=error))
            elif stage == "sentinel_token":
                def token_failure(*args):
                    args[-1]("sentinel_token")
                    raise error
                stack.enter_context(patch.object(probe, "_checkout_risk_headers", side_effect=token_failure))
            else:
                self.prepare_oaics({"payment_method_types": ["card"], "total": {"total": 0}})
                stack.enter_context(patch.object(probe, "_details", side_effect=error))
            return self.query()

    def test_real_curl_transport_failures_mark_proxy_in_each_http_stage_without_replay(self):
        for stage in ("pricing", "sentinel_request", "create", "oaics_state", "stripe_init"):
            for exception in (curl_exceptions.ProxyError, curl_exceptions.ConnectionError,
                              curl_exceptions.SSLError, curl_exceptions.Timeout):
                with self.subTest(stage=stage, exception=exception.__name__):
                    result = self._transport_failure_query(stage, exception("private proxy failure", code=56))
                    self.assertEqual("failed", result["checkout_status"])
                    self.assertIs(result.get("proxy_transport_failure"), True)
                    self.assertNotIn("proxy_transport_failure", probe.public_checkout_details(result))
                    self.assertNotIn("private", json.dumps(result))
                    self.assertLessEqual(self.env.post.call_count, 1)

    def test_http_responses_direct_connections_and_non_http_stages_do_not_fault_proxy(self):
        for stage in ("pricing", "sentinel_request", "create", "oaics_state", "stripe_init"):
            for exception in (curl_exceptions.ConnectionError, curl_exceptions.SSLError,
                              curl_exceptions.Timeout, curl_exceptions.HTTPError):
                for status in (200, 403, 429, 502):
                    with self.subTest(stage=stage, exception=exception.__name__, http_status=status):
                        error = exception("private upstream response", code=56,
                                          response=self.response({}, status=status))
                        result = self._transport_failure_query(stage, error)
                        self.assertNotIn("proxy_transport_failure", result)
            with self.subTest(stage=stage, direct=True):
                self.env.proxy = None
                result = self._transport_failure_query(stage, curl_exceptions.Timeout("private timeout", code=28))
                self.assertNotIn("proxy_transport_failure", result)
                self.env.proxy = "http://proxy.invalid:8080"
            with self.subTest(stage=stage, unrelated_exception=True):
                result = self._transport_failure_query(stage, RuntimeError("private proxy timeout"))
                self.assertNotIn("proxy_transport_failure", result)
        for stage in ("sentinel_token", "parse"):
            with self.subTest(stage=stage):
                result = self._transport_failure_query(stage, curl_exceptions.Timeout("private timeout", code=28))
                self.assertNotIn("proxy_transport_failure", result)

    def test_proxy_tunnel_error_with_partial_http_status_still_faults_proxy(self):
        for stage in ("pricing", "sentinel_request", "create", "oaics_state", "stripe_init"):
            for status in (200, 403, 429, 502):
                with self.subTest(stage=stage, http_status=status):
                    exception = curl_exceptions.code2error(56, "CONNECT private proxy failure")
                    self.assertIs(exception, curl_exceptions.ProxyError)
                    error = exception("CONNECT private proxy failure", code=56,
                                      response=self.response({}, status=status))
                    result = self._transport_failure_query(stage, error)
                    self.assertIs(result.get("proxy_transport_failure"), True)
                    self.assertNotIn("proxy_transport_failure", probe.public_checkout_details(result))
                    self.assertNotIn("private", json.dumps(result))
                    self.assertLessEqual(self.env.post.call_count, 1)
                    self.env.proxy = None
                    self.assertNotIn("proxy_transport_failure", self._transport_failure_query(stage, error))
                    self.env.proxy = "http://proxy.invalid:8080"

    def test_completed_http_403_and_429_never_fault_proxy(self):
        for stage in ("pricing", "create"):
            for status in (403, 429):
                with self.subTest(stage=stage, http_status=status):
                    self.env.reset_mock(side_effect=True)
                    self.env.get.return_value = self.response(self.pricing)
                    response = self.response({"error": "private upstream response"}, status=status)
                    if stage == "pricing":
                        self.env.get.return_value = response
                    else:
                        self.env.post.return_value = response
                    result = self.query()
                    self.assertEqual("failed", result["checkout_status"])
                    self.assertEqual(status, result["checkout_http_status"])
                    self.assertNotIn("proxy_transport_failure", result)

    def test_missing_campaign_and_unverified_go_plan_skip_without_requests(self):
        for campaign, plan in (("", "plus"), ("go-free", "go")):
            result = probe.query_checkout_details("private-access-token", session=self.env, country="JP", campaign_id=campaign, plan=plan)
            self.assertEqual(result["checkout_status"], "skipped")
        self.env.get.assert_not_called()
        self.env.post.assert_not_called()

    def test_cancellation_and_lease_loss_are_not_converted_to_probe_failure(self):
        for exception in (OperationCancelled("cancel"), OperationLeaseLost("lost")):
            callback = Mock(side_effect=exception)
            with self.assertRaises(type(exception)):
                self.query(checkpoint=callback)
        self.env.get.assert_not_called()
        self.env.post.assert_not_called()

    def test_public_details_reject_untrusted_values_and_non_integer_amounts(self):
        self.assertEqual(probe.public_checkout_details({}), {})
        self.assertEqual(probe.public_checkout_details({"country": "JP", "plus_promo_kind": "free_trial"}), {})
        dirty = {"checkout_status": {"private": "token"}, "session_type": ["oaics"], "checkout_error": "person@example.com private-token", "payment_method_types": ["card", "cs_live_private"], "checkout_amount_due_minor": float("inf"), "checkout_currency_exponent": True, "checkout_amount_source": "private.token", "checkout_checked_at": "not-an-iso-token", "checkout_country": "https://evil.invalid", "checkout_currency": "private", "access_token": "private-token", "checkout_http_status": True}
        result = probe.public_checkout_details(dirty)
        self.assertEqual(result["checkout_status"], "failed")
        self.assertEqual(result["session_type"], "unknown")
        self.assertEqual(result["payment_method_types"], ["card"])
        self.assertIsNone(result["checkout_amount_due_minor"])
        self.assertIsNone(result["checkout_currency_exponent"])
        self.assertIsNone(result["checkout_amount_source"])
        self.assertIsNone(result["checkout_checked_at"])
        self.assertIsNone(result["checkout_http_status"])
        self.assertNotIn("private", json.dumps(result))
        for amount in (-1, True, 3.2, "1.2", 2**53, {"subtotal": 0}):
            self.assertIsNone(probe.public_checkout_details({"checkout_amount_due_minor": amount})["checkout_amount_due_minor"])

    def test_real_risk_adapter_uses_chatgpt_page_and_bounded_runner_timeout(self):
        self.risk.stop()
        self.env.post.return_value = self.response({"token": "challenge-secret"})
        raw = json.dumps({"p": "proof", "c": "challenge-secret", "id": self.env.device_id, "flow": "chatgpt_checkout", "_so": "observer-secret"})
        with patch.object(probe, "generate_sentinel_token", return_value=raw) as runner:
            result = probe._checkout_risk_headers(self.env, "actual-half-price", 15, time.time() + 4, Mock())
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["page_url"], "https://chatgpt.com/?promo_campaign=actual-half-price")
        self.assertLessEqual(kwargs["timeout_seconds"], 4)
        self.assertEqual(kwargs["cookie"], "oai-did=device-demo")
        self.assertNotIn("_so", json.loads(result["openai-sentinel-token"]))
        self.assertEqual(json.loads(result["openai-sentinel-so-token"])["so"], "observer-secret")
        call = self.env.post.call_args
        self.assertEqual(call.args[0], "https://sentinel.openai.com/backend-api/sentinel/req")
        self.assertNotIn("private-access-token", json.dumps(call.kwargs))

    def test_runner_rejects_insufficient_budget_before_launch_and_caps_timeout(self):
        for timeout in (0, -1, 0.5, float("nan")):
            with patch.object(sentinel_runner.subprocess, "run") as run:
                with self.assertRaises(TimeoutError):
                    sentinel_runner.generate_sentinel_token({}, "chatgpt_checkout", "device", timeout_seconds=timeout)
                run.assert_not_called()
        completed = Mock(returncode=0, stdout=json.dumps({"p": "p", "c": "c", "id": "device", "flow": "chatgpt_checkout"}))
        for timeout, expected in ((3, 3), (90, 60)):
            with patch.object(sentinel_runner, "_ensure_runner_environment"), patch.object(sentinel_runner.subprocess, "run", return_value=completed) as run:
                sentinel_runner.generate_sentinel_token({}, "chatgpt_checkout", "device", timeout_seconds=timeout, page_url="https://chatgpt.com/")
                self.assertEqual(run.call_args.kwargs["timeout"], expected)


if __name__ == "__main__":
    unittest.main()
