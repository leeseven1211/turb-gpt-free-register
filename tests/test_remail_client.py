# -*- coding: utf-8 -*-
"""Remail 客户端契约测试：所有请求均被替换，不访问数据库或付费接口。"""
import traceback
import unittest
from unittest.mock import Mock, patch

import requests

from config import email as email_config
from core import remail_client


class RemailClientTests(unittest.TestCase):
    def setUp(self):
        remail_client._CONTEXT_CACHE.clear()
        self.addCleanup(remail_client._CONTEXT_CACHE.clear)
        defaults = {
            "REMAIL_API_BASE": "https://remail.aishop6.com/docs",
            "REMAIL_API_KEY": "rk-test-key", "REMAIL_PROJECT_ID": 1001,
            "REMAIL_EMAIL_SUFFIX": "outlook.com", "REMAIL_SERVICE_MODE": "purchase",
            "REMAIL_SUPPLY_POLICY": "public_only", "REMAIL_REQUEST_TIMEOUT": 20,
            "REMAIL_ORDER_WAIT_SECONDS": 30,
        }
        for key, value in defaults.items():
            self.start_patch(patch.object(email_config, key, value, create=True))
        self.session = Mock()
        self.session.__enter__ = Mock(return_value=self.session)
        self.session.__exit__ = Mock(return_value=False)
        self.session.trust_env = True
        self.factory = self.start_patch(patch("core.remail_client.requests.Session", return_value=self.session))
        self.request = self.session.request
        self.saved = self.start_patch(patch("core.remail_client._saved_context_metadata", return_value={}))

    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    @staticmethod
    def response(payload, status=200):
        response = Mock(status_code=status)
        response.json.return_value = payload
        return response

    @staticmethod
    def order(**overrides):
        value = {"orderNo": "R1", "status": "active", "deliveryEmail": "fresh@outlook.test", "serviceToken": "st-test-token"}
        value.update(overrides)
        return value

    def cache(self):
        account = remail_client.RemailAccount("fresh@outlook.test", "st-test-token", "R1", 1001, "outlook.com")
        remail_client._cache_context(account)
        return account

    def test_both_service_modes_use_idempotency_and_direct_connection(self):
        for mode in ("code", "purchase"):
            with self.subTest(mode=mode), patch.object(email_config, "REMAIL_SERVICE_MODE", mode):
                self.request.return_value = self.response(self.order(), 201)
                account = remail_client.pick_account()
                self.assertEqual(account.email, "fresh@outlook.test")
                self.assertIs(remail_client.get_account_context("FRESH@OUTLOOK.TEST"), account)
                args, kwargs = self.request.call_args
                self.assertEqual(args[:2], ("POST", "https://remail.aishop6.com/v1/open/orders"))
                self.assertEqual(kwargs["params"], {"serviceMode": mode, "supply": "public_only"})
                self.assertEqual(kwargs["json"], {"projectId": 1001, "emailSuffix": "outlook.com"})
                self.assertEqual(kwargs["headers"]["Authorization"], "Bearer rk-test-key")
                self.assertTrue(kwargs["headers"]["Idempotency-Key"].startswith("turb-gpt-free-register-"))
                self.assertFalse(self.session.trust_env)
                self.assertFalse(kwargs["allow_redirects"])

    def test_configuration_validation_is_local(self):
        remail_client.validate_configuration()
        self.factory.assert_not_called()
        for key, value in {"REMAIL_API_KEY": "", "REMAIL_PROJECT_ID": 0, "REMAIL_EMAIL_SUFFIX": "", "REMAIL_SERVICE_MODE": "unknown", "REMAIL_SUPPLY_POLICY": "unknown", "REMAIL_API_BASE": "https://secret@remail.test"}.items():
            with self.subTest(key=key), patch.object(email_config, key, value):
                with self.assertRaises(remail_client.RemailError):
                    remail_client.validate_configuration()
        self.factory.assert_not_called()

    def test_invalid_base_url_is_reported_as_configuration_error(self):
        for value in ("", "  ", "ftp://example.test", "https://[", "https://example.test:wrong", "https://example .test"):
            with self.subTest(value=value), patch.object(email_config, "REMAIL_API_BASE", value):
                with self.assertRaises(remail_client.RemailError):
                    remail_client.validate_configuration()
        self.factory.assert_not_called()

    def test_order_wait_queries_existing_order_only(self):
        self.request.side_effect = [self.response(self.order(deliveryEmail="", serviceToken="", status="paid"), 201), self.response(self.order())]
        account = remail_client.pick_account()
        self.assertEqual(account.email, "fresh@outlook.test")
        self.assertEqual([call.args[0] for call in self.request.call_args_list], ["POST", "GET"])
        self.assertEqual(self.request.call_args.args[1], "https://remail.aishop6.com/v1/open/orders/R1")

    def test_order_wait_is_bounded_and_never_reorders(self):
        clock = [0.0]
        self.request.return_value = self.response(self.order(deliveryEmail="", serviceToken="", status="paid"))
        with patch.object(email_config, "REMAIL_ORDER_WAIT_SECONDS", 2), patch.object(remail_client.time, "monotonic", side_effect=lambda: clock[0]), patch.object(remail_client.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
            with self.assertRaisesRegex(remail_client.RemailOrderUncertain, "超时"):
                remail_client.pick_account()
        self.assertEqual(clock[0], 2)
        self.assertEqual([call.args[0] for call in self.request.call_args_list], ["POST", "GET", "GET"])
        self.assertEqual([call.kwargs["timeout"] for call in self.request.call_args_list[1:]], [2, 1])

    def test_terminal_order_is_rejected_even_when_it_contains_credentials(self):
        for status in ("failed", "refunded", "closed"):
            with self.subTest(status=status):
                self.request.return_value = self.response(self.order(status=status, failureCode="secret"))
                with self.assertRaisesRegex(remail_client.RemailError, f"status={status}") as raised:
                    remail_client.pick_account()
                self.assertNotIn("secret", str(raised.exception))
                self.assertNotIsInstance(raised.exception, remail_client.RemailOrderUncertain)
        self.assertIsNone(remail_client.get_account_context("fresh@outlook.test"))

    def test_pickup_uses_service_token_without_api_key(self):
        self.cache()
        self.request.return_value = self.response({"items": [{"receivedAt": 1000, "verificationCode": "111111"}, {"receivedAt": 1100, "verificationCode": "654321"}]})
        with patch.object(email_config, "REMAIL_API_KEY", ""):
            code = remail_client.fetch_latest_otp("fresh@outlook.test", after_ts=1050, max_wait=1, settle_seconds=0)
        self.assertEqual(code, "654321")
        self.assertEqual(self.request.call_args.args[:2], ("GET", "https://remail.aishop6.com/v1/pickup"))
        self.assertEqual(self.request.call_args.kwargs["params"], {"email": "fresh@outlook.test", "token": "st-test-token"})
        self.assertNotIn("Authorization", self.request.call_args.kwargs["headers"])

    def test_old_and_undated_messages_cannot_satisfy_after_timestamp(self):
        self.cache()
        self.request.return_value = self.response({"items": [{"receivedAt": 99, "verificationCode": "111111"}, {"verificationCode": "222222"}]})
        with self.assertRaisesRegex(remail_client.RemailError, "验证码超时"):
            remail_client.fetch_latest_otp("fresh@outlook.test", after_ts=100, max_wait=0, settle_seconds=0)
        self.request.assert_called_once()

    def test_settle_period_accepts_a_newer_message(self):
        self.cache()
        clock = [0.0]
        self.request.side_effect = [self.response({"items": [{"receivedAt": 101, "verificationCode": "111111"}]}), self.response({"items": [{"receivedAt": 102, "verificationCode": "222222"}, {"receivedAt": 101, "verificationCode": "111111"}]}), self.response({"items": [{"receivedAt": 102, "verificationCode": "222222"}]})]
        with patch.object(remail_client.time, "monotonic", side_effect=lambda: clock[0]), patch.object(remail_client.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
            result = remail_client.fetch_latest_otp("fresh@outlook.test", after_ts=100, max_wait=5, poll_interval=1, settle_seconds=1)
        self.assertEqual(result, "222222")
        self.assertEqual(clock[0], 2)

    def test_metadata_restores_context_without_order_request(self):
        account = self.cache()
        metadata = remail_client.get_account_context_metadata(account.email)
        self.assertEqual(metadata["source"], "remail")
        self.assertEqual(metadata["service_token"], "st-test-token")
        remail_client._CONTEXT_CACHE.clear()
        self.saved.return_value = metadata
        restored = remail_client.restore_account_context("FRESH@OUTLOOK.TEST")
        self.assertEqual(restored.service_token, "st-test-token")
        self.request.assert_not_called()

    def test_saved_metadata_for_other_email_is_ignored(self):
        self.saved.return_value = {"email": "other@outlook.test", "service_token": "st-wrong", "order_no": "R-wrong"}
        self.request.return_value = self.response({"items": []})
        self.assertIsNone(remail_client.restore_account_context("fresh@outlook.test"))
        self.request.assert_called_once()
        self.assertEqual(self.request.call_args.args[1], "https://remail.aishop6.com/v1/open/orders")

    def test_order_search_exact_match_and_pagination(self):
        self.request.side_effect = [self.response({"items": [self.order(deliveryEmail="prefixfresh@outlook.test"), self.order(status="refunded")], "hasNext": True, "nextAfterId": 20}), self.response({"items": [self.order(deliveryEmail="FRESH@OUTLOOK.TEST")], "hasNext": False})]
        account = remail_client.restore_account_context("fresh@outlook.test")
        self.assertEqual(account.service_token, "st-test-token")
        self.assertEqual(self.request.call_args.kwargs["params"], {"search": "fresh@outlook.test", "limit": 100, "afterId": 20})

    def test_detail_lookup_also_rejects_wrong_email(self):
        self.request.side_effect = [self.response({"items": [self.order(serviceToken="")]}), self.response(self.order(deliveryEmail="other@outlook.test"))]
        self.assertIsNone(remail_client.restore_account_context("fresh@outlook.test"))
        self.assertEqual(self.request.call_count, 2)

    def test_restore_prefers_newest_detail_over_older_list_token(self):
        self.request.side_effect = [self.response({"items": [self.order(serviceToken="old", updatedAt=100), self.order(orderNo="R2", serviceToken="", updatedAt=200)]}), self.response(self.order(orderNo="R2", serviceToken="new"))]
        self.assertEqual(remail_client.restore_account_context("fresh@outlook.test").service_token, "new")

    def test_request_errors_never_expose_credentials_or_body(self):
        secret = "rk-secret st-secret fresh@outlook.test OTP=123456 password=test"
        scenarios = [requests.ConnectionError(secret), requests.Timeout(secret), self.response({"message": secret}, 400), self.response({"message": secret}, 500)]
        invalid_json = self.response({})
        invalid_json.json.side_effect = ValueError(secret)
        scenarios.append(invalid_json)
        for scenario in scenarios:
            with self.subTest(scenario=type(scenario).__name__):
                self.request.side_effect = scenario if isinstance(scenario, Exception) else None
                self.request.return_value = scenario
                try:
                    remail_client._request("GET", "/v1/pickup", params={"token": secret}, authenticated=False)
                except remail_client.RemailError:
                    diagnostic = traceback.format_exc()
                else:
                    self.fail("应拒绝失败响应")
                self.assertNotIn(secret, diagnostic)
                self.assertNotIn("st-secret", diagnostic)

    def test_create_network_failure_is_not_retried(self):
        self.request.side_effect = requests.Timeout("private request")
        with self.assertRaisesRegex(remail_client.RemailOrderUncertain, "结果不明"):
            remail_client.pick_account()
        self.request.assert_called_once()

    def test_uncertain_post_outcomes_are_classified_without_retry(self):
        invalid_json = self.response({})
        invalid_json.json.side_effect = ValueError("private-json")
        scenarios = [
            requests.ConnectionError("private-network"),
            self.response({"message": "private-response"}, 500),
            self.response({"message": "private-response"}, 503),
            self.response({"message": "private-response"}, 409),
            invalid_json,
            self.response([]),
            self.response({}),
            self.response({"data": {"status": "paid"}}),
        ]
        for scenario in scenarios:
            with self.subTest(scenario=type(scenario).__name__):
                self.request.reset_mock()
                self.request.side_effect = scenario if isinstance(scenario, Exception) else None
                self.request.return_value = scenario
                with self.assertRaises(remail_client.RemailOrderUncertain) as raised:
                    remail_client.pick_account()
                self.assertTrue(raised.exception.request_unknown)
                self.assertEqual(raised.exception.error_code, "remail_order_request_unknown")
                self.assertNotIn("private-", str(raised.exception))
                self.request.assert_called_once()

    def test_known_rejections_and_read_errors_remain_regular_errors(self):
        for method, status in (("POST", 400), ("POST", 401), ("POST", 403), ("POST", 422), ("GET", 409), ("GET", 503)):
            with self.subTest(method=method, status=status):
                self.request.return_value = self.response({"message": "private"}, status)
                with self.assertRaises(remail_client.RemailError) as raised:
                    remail_client._request(method, "/v1/open/orders")
                self.assertNotIsInstance(raised.exception, remail_client.RemailOrderUncertain)

    def test_logs_and_repr_do_not_expose_account_credentials(self):
        self.request.return_value = self.response(self.order())
        with self.assertLogs("core.remail_client", level="INFO") as logs:
            account = remail_client.pick_account()
            remail_client.release_account(account.email, note="password=secret", status="OTP=123456")
        text = " ".join(logs.output) + repr(account)
        for value in (account.email, account.service_token, "password=secret", "123456"):
            self.assertNotIn(value, text)
        self.assertIsNone(remail_client.get_account_context(account.email))

    def test_timestamp_formats_and_body_otp(self):
        self.assertEqual(remail_client._parse_timestamp("2026-08-29T05:00:00Z"), remail_client._parse_timestamp("2026-08-29T13:00:00+08:00"))
        self.assertEqual(remail_client._parse_timestamp(1787979600000), 1787979600)
        self.assertIsNone(remail_client._parse_timestamp(float("nan")))
        self.assertEqual(remail_client._message_code({"bodyPreview": "Your OpenAI code is 654321"}), "654321")


if __name__ == "__main__":
    unittest.main()
