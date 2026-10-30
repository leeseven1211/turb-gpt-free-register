from __future__ import annotations

from io import BytesIO
import ssl
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError, Timeout as CurlTimeout

from core.extract_link import contracts


class ExtractLinkProviderHttpErrorTests(TestCase):
    def request(self, response=None, *, error=None):
        transport = SimpleNamespace(request=Mock(return_value=response, side_effect=error))
        return contracts.request(transport, "GET", "/private-path?secret=synthetic-secret")

    def assert_safe_http_error(self, error, status):
        self.assertIsInstance(error, contracts.ProviderError)
        self.assertEqual(status, getattr(error, "http_status", None))
        self.assertIs(type(error.http_status), int)
        self.assertIn(f"HTTP {status}", str(error))
        for value in ("private-path", "synthetic-secret", "private-response", "private-error", "example.test"):
            self.assertNotIn(value, repr(error))
            self.assertNotIn(value, repr(vars(error)))

    def test_response_http_failures_keep_status_without_reading_body(self):
        for status in (301, 400, 404, 410, 429, 500, 502):
            with self.subTest(status=status):
                body = Mock(return_value={"error": "private-response synthetic-secret"})
                with self.assertRaises(contracts.ProviderError) as caught:
                    self.request(SimpleNamespace(status_code=status, json=body))
                self.assert_safe_http_error(caught.exception, status)
                body.assert_not_called()

    def test_string_http_status_is_normalized_to_plain_integer(self):
        with self.assertRaises(contracts.ProviderError) as caught:
            self.request(SimpleNamespace(status_code="404", json=Mock()))
        self.assert_safe_http_error(caught.exception, 404)

    def test_transport_urllib_http_error_preserves_status_without_retaining_response(self):
        failure = HTTPError(
            "https://example.test/private-path?secret=synthetic-secret", 404,
            "private-error", {}, BytesIO(b"private-response synthetic-secret"),
        )
        with self.assertRaises(contracts.ProviderError) as caught:
            self.request(error=failure)
        self.assert_safe_http_error(caught.exception, 404)
        self.assertIsNone(caught.exception.__context__)

    def test_transport_http_exception_uses_response_status_only(self):
        failure = RuntimeError("private-error https://example.test/?secret=synthetic-secret")
        failure.response = SimpleNamespace(status_code=503, text="private-response")
        with self.assertRaises(contracts.ProviderError) as caught:
            self.request(error=failure)
        self.assert_safe_http_error(caught.exception, 503)
        self.assertIsNone(caught.exception.__context__)

    def test_non_http_transport_failure_does_not_invent_http_status_or_leak_message(self):
        with self.assertRaises(contracts.ProviderError) as caught:
            self.request(error=TimeoutError("private-error synthetic-secret"))
        self.assertFalse(hasattr(caught.exception, "http_status"))
        self.assertNotIn("private-error", repr(caught.exception))
        self.assertNotIn("synthetic-secret", repr(caught.exception))

    def test_transport_errors_keep_safe_categories_and_exception_types(self):
        cases = (
            (TimeoutError("private-error synthetic-secret"), "请求超时", "TimeoutError"),
            (URLError(TimeoutError("private-error synthetic-secret")), "请求超时", "TimeoutError"),
            (ConnectionRefusedError("private-error synthetic-secret"), "连接失败", "ConnectionRefusedError"),
            (ssl.SSLCertVerificationError("private-error synthetic-secret"), "证书校验失败", "SSLCertVerificationError"),
            (CurlTimeout("private-error synthetic-secret", code=28), "请求超时", "Timeout"),
            (CurlConnectionError("private-error synthetic-secret", code=7), "连接失败", "ConnectionError"),
            (ValueError("private-error synthetic-secret"), "请求异常", "ValueError"),
        )
        for failure, category, exception_type in cases:
            with self.subTest(exception_type=exception_type):
                with self.assertRaises(contracts.ProviderError) as caught:
                    self.request(error=failure)
                self.assertIn(category, str(caught.exception))
                self.assertIn(exception_type, str(caught.exception))
                self.assertNotIn("private-error", repr(caught.exception))
                self.assertNotIn("synthetic-secret", repr(caught.exception))
                self.assertIsNone(caught.exception.__context__)

    def test_existing_provider_error_is_not_wrapped(self):
        failure = contracts.ProviderUnsupported()
        with self.assertRaises(contracts.ProviderUnsupported) as caught:
            self.request(error=failure)
        self.assertIs(failure, caught.exception)

    def test_success_response_and_raw_business_dict_keep_existing_contract(self):
        payload = {"status_code": 404, "status": "RUNNING", "id": "business-job"}
        self.assertEqual(payload, self.request(payload))
        for status in (200, "201", 299):
            with self.subTest(status=status):
                body = Mock(return_value=payload)
                self.assertEqual(payload, self.request(SimpleNamespace(status_code=status, json=body)))
                body.assert_called_once_with()

    def test_unsupported_tuple_or_invalid_status_remains_safe_format_failure(self):
        for response in ((404, {"error": "private-response"}), SimpleNamespace(status_code="private-error", json=Mock())):
            with self.subTest(response_type=type(response).__name__):
                with self.assertRaises(contracts.ProviderError) as caught:
                    self.request(response)
                self.assertFalse(hasattr(caught.exception, "http_status"))
                self.assertNotIn("private-response", repr(caught.exception))
                self.assertNotIn("private-error", repr(caught.exception))

    def test_invalid_response_status_has_a_specific_reason(self):
        with self.assertRaises(contracts.ProviderError) as caught:
            self.request(SimpleNamespace(status_code="private-error synthetic-secret", json=Mock()))
        self.assertIn("响应状态码无效", str(caught.exception))
        self.assertNotIn("synthetic-secret", repr(caught.exception))

    def test_response_reading_exception_keeps_type_without_message_or_context(self):
        class BrokenResponse:
            @property
            def status_code(self):
                raise ValueError("private-error synthetic-secret")

        with self.assertRaises(contracts.ProviderError) as caught:
            self.request(BrokenResponse())
        self.assertIn("响应读取异常", str(caught.exception))
        self.assertIn("ValueError", str(caught.exception))
        self.assertNotIn("synthetic-secret", repr(caught.exception))
        self.assertIsNone(caught.exception.__context__)

    def test_http_error_remains_a_provider_error_subclass(self):
        error_class = getattr(contracts, "ProviderHTTPError", None)
        self.assertIsNotNone(error_class)
        error = error_class(404)
        self.assert_safe_http_error(error, 404)
