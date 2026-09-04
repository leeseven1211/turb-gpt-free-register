# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core import email_butler_client as client


class EmailButlerClientTests(unittest.TestCase):
    def test_scan_maps_only_safe_signal_fields(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 200,
            "checked_at": "2026-08-10T00:00:00Z",
            "signal": {
                "detected": True,
                "received_at": "2026-08-09T00:00:00Z",
                "subject": "OpenAI Account Deactivated",
                "from": "noreply@openai.com",
                "message_id": "m-1",
                "confidence": "high",
                "body": "must not be returned",
            },
        }
        with patch.object(client.requests, "request", return_value=response), patch.object(
            client._email_cfg, "EMAIL_BUTLER_API_BASE", "http://127.0.0.1:8788/v1"
        ), patch.object(client._email_cfg, "EMAIL_BUTLER_API_KEY", "secret"):
            result = client.scan_openai_deactivation("a@example.com")
        self.assertTrue(result["detected"])
        self.assertNotIn("body", result)
        self.assertEqual(result["confidence"], "high")

    def test_scan_retries_one_transient_connection_error(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 200,
            "checked_at": "2026-08-10T00:00:00Z",
            "signal": {"detected": False},
        }
        with patch.object(
            client.requests,
            "request",
            side_effect=[client.requests.ConnectionError("TLS closed"), response],
        ) as request_mock, patch.object(client.time, "sleep") as sleep_mock:
            result = client.scan_openai_deactivation("a@example.com")

        self.assertFalse(result["detected"])
        self.assertEqual(request_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.5)

    def test_connection_requires_signal_capability(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 200,
            "capabilities": ["mailboxes.create", "mailboxes.messages", "mailboxes.release"],
        }
        with patch.object(client.requests, "request", return_value=response):
            with self.assertRaises(client.EmailButlerClientError):
                client.test_connection(api_base="http://example.test/v1", api_key="secret")

    def test_restore_context_requests_exact_email(self):
        with patch.object(client, "_request", return_value={
            "mailbox": {
                "id": "mb-1",
                "email": "restore@example.com",
                "lease_id": "lease-1",
            }
        }) as request_mock:
            account = client.restore_account_context("restore@example.com")
        self.assertEqual(account.mailbox_id, "mb-1")
        request_mock.assert_called_once_with(
            "POST",
            "/mailboxes",
            json={"requested_email": "restore@example.com", "purpose": "live-check"},
        )

    def test_fetch_inbound_otp_uses_single_pg_wait_request_without_lease(self):
        with patch.object(
            client,
            "_request",
            return_value={"code": 200, "verification_code": "654321"},
        ) as request_mock:
            otp = client.fetch_inbound_otp(
                "alias@icloud.com",
                after_ts=100.0,
                max_wait=15,
                poll_interval=1,
                settle_seconds=0,
            )

        self.assertEqual(otp, "654321")
        args, kwargs = request_mock.call_args
        self.assertEqual(args, ("POST", "/inbound/code"))
        self.assertEqual(kwargs["json"]["email"], "alias@icloud.com")
        self.assertEqual(kwargs["json"]["timeout_seconds"], 15)
        self.assertEqual(kwargs["timeout"], 25)
        self.assertTrue(kwargs["retry_connection_error"])
        self.assertIsNone(client.get_account_context("alias@icloud.com"))

    def test_inbound_wait_retries_one_transient_connection_error(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": 200, "verification_code": "123456"}
        # fetch_inbound_otp 不接受 api_base，只能从配置读；显式给出，避免这个用例
        # 依赖开发机 .env 里恰好配了 EMAIL_BUTLER_API_BASE。
        with patch.object(
            client._email_cfg, "EMAIL_BUTLER_API_BASE", "http://example.test/v1", create=True
        ), patch.object(
            client._email_cfg, "EMAIL_BUTLER_API_KEY", "test-key", create=True
        ), patch.object(
            client.requests,
            "request",
            side_effect=[client.requests.ConnectionError("TLS closed"), response],
        ) as request_mock, patch.object(client.time, "sleep") as sleep_mock:
            otp = client.fetch_inbound_otp(
                "alias@icloud.com",
                after_ts=100.0,
                max_wait=15,
            )

        self.assertEqual(otp, "123456")
        self.assertEqual(request_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.5)

    def test_inbound_wait_continues_after_gateway_524(self):
        with patch.object(
            client,
            "_request",
            side_effect=[
                client.EmailButlerClientError(
                    "Email Butler 请求失败 (/inbound/code): HTTP 524; None"
                ),
                {"code": 200, "verification_code": "246810"},
            ],
        ) as request_mock, patch.object(client.time, "sleep"):
            otp = client.fetch_inbound_otp(
                "alias@icloud.com",
                after_ts=100.0,
                max_wait=160,
                poll_interval=1,
            )

        self.assertEqual(otp, "246810")
        self.assertEqual(request_mock.call_count, 2)
        for request_call in request_mock.call_args_list:
            self.assertLessEqual(
                request_call.kwargs["json"]["timeout_seconds"],
                client._INBOUND_WAIT_CHUNK_SECONDS,
            )
            self.assertLessEqual(
                request_call.kwargs["timeout"],
                client._INBOUND_WAIT_CHUNK_SECONDS + 10,
            )

    def test_inbound_wait_does_not_retry_auth_error(self):
        with patch.object(
            client,
            "_request",
            side_effect=client.EmailButlerClientError(
                "Email Butler API Key 非法、已停用或已轮换"
            ),
        ) as request_mock:
            with self.assertRaises(client.EmailButlerClientError):
                client.fetch_inbound_otp(
                    "alias@icloud.com",
                    after_ts=100.0,
                    max_wait=160,
                )

        request_mock.assert_called_once()

    def test_inbound_wait_uses_local_probe_after_remote_miss(self):
        with patch.object(client, "_request", return_value={"code": 200}) as request_mock:
            otp = client.fetch_inbound_otp(
                "alias@icloud.com",
                after_ts=100.0,
                max_wait=160,
                local_probe=lambda: "135790",
            )

        self.assertEqual(otp, "135790")
        request_mock.assert_called_once()

    def test_non_idempotent_request_does_not_retry_connection_error(self):
        with patch.object(
            client.requests,
            "request",
            side_effect=client.requests.ConnectionError("TLS closed"),
        ) as request_mock:
            with self.assertRaises(client.EmailButlerClientError):
                client._request(
                    "POST",
                    "/mailboxes",
                    json={"purpose": "registration"},
                    api_base="http://example.test/v1",
                    api_key="secret",
                )

        request_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
