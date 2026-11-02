"""独立支付只使用官方接口，并保留可恢复的提交语义。"""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.payments import PaymentError, XXSYUNClient, select_payment_url
from core.payments import runtime


BASE = "https://upi.xxsyun.xyz/api/v1"
LINK = "https://payments.stripe.com/upi/instructions/test-material"
BODY = {"items": [{"at": "synthetic-at", "link": LINK}], "dispatch_mode": "auto"}


class Transport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, deepcopy(kwargs)))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, dict):
            return SimpleNamespace(status_code=200, headers={}, json=lambda: response)
        return response


class XXSYUNClientTests(unittest.TestCase):
    def client(self, *responses):
        transport = Transport(*responses)
        return XXSYUNClient(BASE, "synthetic-key", transport=transport), transport

    def test_created_and_duplicated_read_order_identity_and_status(self):
        for field in ("created", "duplicated"):
            with self.subTest(field=field):
                client, transport = self.client({"ok": True, field: [{"order": {"id": "order-1", "status": "pending"}}], "failed": []})
                result = client.submit(BODY, "stable-key")
                self.assertEqual(("order-1", "pending"), (result["order_id"], result["state"]))
                self.assertEqual("/orders/batch", transport.calls[0][1])
                self.assertEqual("stable-key", transport.calls[0][2]["headers"]["Idempotency-Key"])

    def test_timeout_and_replay_keep_identical_body_and_key(self):
        client, transport = self.client(TimeoutError("synthetic-key synthetic-at"), {"ok": True, "duplicated": [{"order": {"id": "original", "status": "processing"}}]})
        with self.assertRaises(PaymentError) as caught:
            client.submit(BODY, "same-key")
        self.assertEqual("REQUEST_TIMEOUT", caught.exception.code)
        self.assertTrue(caught.exception.submission_unknown)
        self.assertTrue(caught.exception.retryable)
        self.assertNotIn("synthetic", str(caught.exception))
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual("original", client.submit(BODY, "same-key")["order_id"])
        self.assertEqual(transport.calls[0][2], transport.calls[1][2])

    def test_business_error_codes_and_retry_policy(self):
        retryable = {"INSUFFICIENT_QUOTA", "EMPLOYER_SUBMISSION_COOLDOWN", "RATE_LIMITED"}
        codes = retryable | {"UNAUTHENTICATED", "EMPLOYER_PENDING", "PASSWORD_CHANGE_REQUIRED", "INVALID_AT", "LINK_INVALID", "LINK_EXPIRED", "ACCOUNT_MISMATCH", "ACCOUNT_MATCH_UNVERIFIED", "ICLOUD_EMAIL_BLOCKED", "NON_ZERO_TRIAL", "BLOCKED_EXTERNAL", "IDEMPOTENCY_CONFLICT", "ORDER_CANCEL_RESTRICTED", "NEW_UPSTREAM_CODE"}
        for code in codes:
            with self.subTest(code=code):
                client, _ = self.client({"ok": False, "error": {"code": code, "message": "synthetic-at synthetic-key https://secret.test/token", "retry_after_seconds": 27}})
                with self.assertRaises(PaymentError) as caught:
                    client.submit(BODY, "key")
                error = caught.exception
                self.assertEqual(code, error.code)
                self.assertEqual(code in retryable, error.retryable)
                self.assertFalse(error.submission_unknown)
                self.assertEqual(27, error.retry_after_seconds)
                self.assertNotIn("synthetic", str(error))
                self.assertNotIn("secret.test", str(error))

    def test_failed_row_is_not_http_success(self):
        client, _ = self.client({"ok": True, "created": [], "duplicated": [], "failed": [{"index": 0, "code": "LINK_EXPIRED", "error": "链接过期", "amount_due_minor": 0, "currency": "INR"}]})
        with self.assertRaises(PaymentError) as caught:
            client.submit(BODY, "stable-key")
        self.assertEqual("LINK_EXPIRED", caught.exception.code)

    def test_non_zero_trial_preserves_amount_currency_and_unknown_code_category(self):
        client, _ = self.client({"ok": True, "failed": [{"index": 0, "code": "NON_ZERO_TRIAL", "error": "试用不是零金额", "amount_due_minor": 499, "currency": "INR"}]})
        with self.assertRaises(PaymentError) as caught:
            client.submit(BODY, "stable-key")
        self.assertEqual(499, caught.exception.summary["amount_due_minor"])
        self.assertEqual("INR", caught.exception.summary["currency"])
        client, _ = self.client({"ok": False, "error": {"code": "NEW_REASON", "message": "新拒绝原因"}})
        with self.assertRaises(PaymentError) as caught:
            client.submit(BODY, "stable-key")
        self.assertEqual("NEW_REASON", caught.exception.code)
        self.assertEqual("UPSTREAM_BUSINESS_ERROR", caught.exception.category)

    def test_malformed_error_code_and_direct_transport_path_stay_classified(self):
        client, _ = self.client({"ok": False, "error": {"code": {"raw": "data"}}})
        with self.assertRaises(PaymentError):
            client.submit(BODY, "stable-key")
        from core.payments.xxsyun import DirectTransport
        for path in ("//other.test/path", "/../tickets", "/orders/%2e%2e/tickets", "/orders/test?token=x"):
            with self.subTest(path=path), self.assertRaises(PaymentError):
                DirectTransport(BASE).request("GET", path)

    def test_receipt_foreign_row_index_does_not_bind_to_this_submission(self):
        client, _ = self.client({"ok": True, "created": [{"index": 1, "order": {"id": "foreign", "status": "pending"}}]})
        with self.assertRaises(PaymentError) as caught:
            client.submit(BODY, "stable-key")
        self.assertTrue(caught.exception.submission_unknown)

    def test_missing_ambiguous_or_mixed_receipt_is_unknown(self):
        order = {"order": {"id": "one", "status": "pending"}}
        for payload in ({"ok": True}, {"ok": True, "created": [order, order]}, {"ok": True, "created": [order], "failed": [{"error": {"code": "LINK_INVALID"}}]}):
            with self.subTest(payload=payload):
                client, _ = self.client(payload)
                with self.assertRaises(PaymentError) as caught:
                    client.submit(BODY, "stable-key")
                self.assertTrue(caught.exception.submission_unknown)
                self.assertEqual("INCOMPLETE_RECEIPT", caught.exception.code)

    def test_http_and_json_errors_classified_without_response_leak(self):
        for status, payload, code in ((429, {}, "RATE_LIMITED"), (503, {}, "UPSTREAM_HTTP_ERROR"), (401, {}, "UNAUTHENTICATED"), (200, None, "INVALID_RESPONSE")):
            with self.subTest(status=status):
                response = SimpleNamespace(status_code=status, headers={"Retry-After": "19"}, json=lambda: payload)
                client, _ = self.client(response)
                with self.assertRaises(PaymentError) as caught:
                    client.submit(BODY, "stable-key")
                self.assertEqual(code, caught.exception.code)
                if status == 429:
                    self.assertEqual(19, caught.exception.retry_after_seconds)

    def test_http_server_error_with_business_body_keeps_original_submission_unknown(self):
        response = SimpleNamespace(status_code=500, headers={"Retry-After": "900"},
            json=lambda: {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "synthetic-at"}})
        client, _ = self.client(response)
        with self.assertRaises(PaymentError) as caught:
            client.submit(BODY, "stable-key")
        self.assertEqual("INTERNAL_ERROR", caught.exception.code)
        self.assertTrue(caught.exception.retryable)
        self.assertTrue(caught.exception.submission_unknown)
        self.assertEqual(900, caught.exception.retry_after_seconds)
        self.assertNotIn("synthetic-at", str(caught.exception))

    def test_order_query_normalizes_terminal_states_and_identity(self):
        for remote, normalized in (("completed", "succeeded"), ("failed", "failed"), ("expired", "failed"), ("cancelled", "failed"), ("awaiting_worker", "pending"), ("claimed", "pending"), ("verifying", "pending"), ("processing", "pending"), ("future-state", "unknown")):
            with self.subTest(remote=remote):
                client, _ = self.client({"ok": True, "order": {"id": "one", "status": remote, "failure_code": "LINK_EXPIRED", "failure_reason": "synthetic-key", "can_cancel": False}})
                result = client.get_order("one")
                self.assertEqual(normalized, result["state"])
                self.assertEqual(remote, result["remote_status"])
                self.assertEqual("LINK_EXPIRED", result["failure_code"])
                self.assertNotIn("synthetic-key", repr(result))
                self.assertFalse(result["can_cancel"])
        client, _ = self.client({"ok": True, "order": {"id": "different", "status": "completed"}})
        with self.assertRaises(PaymentError):
            client.get_order("one")

    def test_balance_zero_and_missing_fields_stay_distinct(self):
        client, _ = self.client({"ok": True, "summary": {"available_points": 0, "pending_points": 0, "used_points": "0", "cost_points": 10}})
        self.assertEqual({"available_points": 0, "pending_points": 0, "used_points": 0, "cost_points": 10}, client.query_balance())
        client, _ = self.client({"ok": True, "summary": {"available_points": 0}})
        self.assertIsNone(client.query_balance()["pending_points"])

    def test_balance_and_order_requests_pass_user_agent_gateway(self):
        class Gateway(BaseHTTPRequestHandler):
            def do_GET(self):
                self.reply()

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.reply()

            def reply(self):
                allowed = self.headers.get("User-Agent", "").startswith("Mozilla/5.0")
                order = {"id": "one", "status": "pending"}
                payload = ({"ok": True, "summary": {"available_points": 12},
                            "created": [{"order": order}], "order": order}
                           if allowed else {"message": "Forbidden"})
                self.send_response(200 if allowed else 403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *args):
                pass

        with HTTPServer(("127.0.0.1", 0), Gateway) as server:
            thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            thread.start()
            try:
                client = XXSYUNClient(f"http://127.0.0.1:{server.server_port}/api/v1", "synthetic-key")
                self.assertEqual(12, client.query_balance()["available_points"])
                self.assertEqual("one", client.submit(BODY, "stable-key")["order_id"])
                self.assertEqual("pending", client.get_order("one")["state"])
            finally:
                server.shutdown()
                thread.join(timeout=5)

    def test_unsupported_url_or_body_rejected_before_request(self):
        client, transport = self.client()
        for body in ({"items": []}, {"items": [{"at": "x", "link": "upi://pay"}]}, {"items": BODY["items"] * 2}):
            with self.subTest(body=body), self.assertRaises(PaymentError):
                client.submit(body, "stable-key")
        self.assertEqual([], transport.calls)
        for base in ("https://user:pass@unexpected.test/api/v1", "https://unexpected.test/api?v=1", "https://unexpected.test/api#part", "file:///tmp/api"):
            with self.subTest(base=base), self.assertRaises(PaymentError):
                XXSYUNClient(base, "synthetic-key")

    def test_configurable_api_base_remains_bound_to_transport(self):
        from core.payments.xxsyun import DirectTransport
        transport = DirectTransport("https://payment.example.test/api/v2/")
        self.assertEqual("https://payment.example.test/api/v2", transport.api_base)

    def test_direct_transport_disables_proxy_and_redirects(self):
        from core.payments.xxsyun import DirectTransport
        with patch("core.payments.xxsyun.build_opener") as opener:
            DirectTransport(BASE)
        handlers = opener.call_args.args
        from urllib.request import ProxyHandler
        self.assertEqual({}, next(handler.proxies for handler in handlers if isinstance(handler, ProxyHandler)))
        self.assertTrue(any(type(handler).__name__ == "_NoRedirect" for handler in handlers))

    def test_transport_uses_identical_bytes_after_persisted_json_reorders_keys(self):
        from core.payments.xxsyun import DirectTransport
        response = SimpleNamespace(code=200, headers={}, read=lambda: b'{"ok":true}')
        manager = unittest.mock.MagicMock()
        manager.__enter__.return_value = response
        # 传输读取原响应对象，模拟 urllib 响应上下文。
        manager.code, manager.headers, manager.read = 200, {}, response.read
        with patch("core.payments.xxsyun.build_opener") as opener:
            opener.return_value.open.return_value = manager
            transport = DirectTransport(BASE)
            transport.request("POST", "/orders/batch", json=BODY)
            original = opener.return_value.open.call_args.args[0].data
            reordered = {"dispatch_mode": "auto", "items": [{"link": LINK, "at": "synthetic-at"}]}
            transport.request("POST", "/orders/batch", json=reordered)
            replay = opener.return_value.open.call_args.args[0].data
        self.assertEqual(original, replay)


class PaymentMaterialTests(unittest.TestCase):
    def test_select_only_official_https_upi_instructions_link(self):
        self.assertEqual(LINK, select_payment_url({"payment_url": LINK}))
        self.assertEqual(LINK, select_payment_url({"qr_image_url_png": "https://image.test/qr.png"}, links=("https://page.test/show",), payment_links=(LINK,)))
        for url in ("upi://pay?pa=test", "https://payments.stripe.com/checkout/test", "https://payments.stripe.com.evil.test/upi/instructions/x", "http://payments.stripe.com/upi/instructions/x", "https://user:pass@payments.stripe.com/upi/instructions/x", "https://payments.stripe.com:444/upi/instructions/x"):
            with self.subTest(url=url), self.assertRaises(PaymentError):
                select_payment_url({"payment_url": url})


class PaymentRuntimeTests(unittest.TestCase):
    def test_default_configuration_and_injected_setting_do_not_migrate_legacy_key(self):
        values = {"EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY": "legacy-key"}
        configured = runtime.configuration(settings=lambda name, default=None: values.get(name, default))
        self.assertEqual(BASE, configured.api_base)
        self.assertEqual("", configured.api_key)
        self.assertEqual((30, 10, 1), (configured.timeout, configured.poll_interval, configured.concurrency))

    def test_balance_draft_and_explicit_empty_key(self):
        configured = SimpleNamespace(api_base=BASE, api_key="saved", timeout=30, poll_interval=10, concurrency=1)
        with patch.object(runtime, "configuration", return_value=configured), patch.object(runtime, "XXSYUNClient") as client:
            client.return_value.query_balance.return_value = {"available_points": 0}
            self.assertTrue(runtime.query_xxsyun_balance()["ok"])
            self.assertEqual("saved", client.call_args.args[1])
            self.assertEqual(0, runtime.query_xxsyun_balance("draft")["balance"]["available_points"])
            self.assertEqual("draft", client.call_args.args[1])
            with self.assertRaises(PaymentError):
                runtime.query_xxsyun_balance("")
