# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import cf_temp_mail_client as client


class CFTempMailClientTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_patch = patch.object(client, "_state_file", return_value=Path(self.temp_dir.name) / "cloudflare_mailboxes.json")
        self.state_patch.start()
        self.addCleanup(self.state_patch.stop)
        client._CONTEXT_CACHE.clear()
        client._DOMAIN_COUNTER = 0

    def test_pick_account_requires_api_base(self):
        with patch.object(client._email_cfg, "CLOUDFLARE_API_BASE", "", create=True):
            with self.assertRaisesRegex(client.CFTempMailError, "请填写 CLOUDFLARE_API_BASE"):
                client.pick_account()

    @patch("core.cf_temp_mail_client.requests.request")
    def test_pick_account_anonymous_create(self, request_mock):
        response = Mock(status_code=200)
        response.json.return_value = {
            "address": "abc123@mail.example.com",
            "jwt": "jwt-token-1",
        }
        request_mock.return_value = response

        with patch.object(client._email_cfg, "CLOUDFLARE_API_BASE", "https://mail.example.com", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_AUTH_MODE", "none", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_API_KEY", "", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_PATH_ACCOUNTS", "/api/new_address", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_DEFAULT_DOMAINS", ["mail.example.com"], create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_CUSTOM_AUTH", "", create=True
        ):
            account = client.pick_account()

        self.assertEqual(account.email, "abc123@mail.example.com")
        self.assertEqual(account.jwt, "jwt-token-1")
        self.assertIs(client.get_account_context(account.email), account)
        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(args[1], "https://mail.example.com/api/new_address")
        self.assertEqual(kwargs["json"], {"domain": "mail.example.com"})

    @patch("core.cf_temp_mail_client.requests.request")
    def test_admin_create_uses_name_payload_and_header(self, request_mock):
        response = Mock(status_code=200)
        response.json.return_value = {"address": "u@mail.example.com", "jwt": "jwt-2"}
        request_mock.return_value = response

        with patch.object(client._email_cfg, "CLOUDFLARE_API_BASE", "https://mail.example.com", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_AUTH_MODE", "x-admin-auth", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_API_KEY", "admin-pass", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_PATH_ACCOUNTS", "/admin/new_address", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_DEFAULT_DOMAINS", ["mail.example.com"], create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_CUSTOM_AUTH", "global-pass", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_NAME_LENGTH", 10, create=True):
            account = client.pick_account()

        self.assertEqual(account.email, "u@mail.example.com")
        _, kwargs = request_mock.call_args
        self.assertEqual(kwargs["headers"]["x-admin-auth"], "admin-pass")
        self.assertEqual(kwargs["headers"]["x-custom-auth"], "global-pass")
        self.assertEqual(kwargs["json"]["enablePrefix"], True)
        self.assertEqual(kwargs["json"]["domain"], "mail.example.com")
        self.assertIn("name", kwargs["json"])

    @patch("core.cf_temp_mail_client.time.sleep")
    @patch("core.cf_temp_mail_client.requests.request")
    def test_fetch_latest_otp_reads_only_new_openai_email(self, request_mock, sleep):
        client._CONTEXT_CACHE["fresh@mail.example.com"] = client.CFTempMailAccount(
            email="fresh@mail.example.com",
            jwt="jwt-xyz",
            domain="mail.example.com",
        )

        inbox = Mock(status_code=200)
        inbox.json.return_value = {
            "results": [
                {
                    "id": "old",
                    "timestamp": 100,
                    "address": "fresh@mail.example.com",
                    "from": "noreply@openai.com",
                    "subject": "Code 111111",
                    "text": "Your code is 111111",
                },
                {
                    "id": "new",
                    "timestamp": 250,
                    "address": "fresh@mail.example.com",
                    "from": "noreply@openai.com",
                    "subject": "Code 654321",
                    "text": "Your code is 654321",
                },
            ]
        }
        request_mock.return_value = inbox

        with patch.object(client._email_cfg, "CLOUDFLARE_API_BASE", "https://mail.example.com", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_PATH_MESSAGES", "/api/mails", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_AUTH_MODE", "none", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_API_KEY", "", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_CUSTOM_AUTH", "", create=True):
            code = client.fetch_latest_otp(
                "fresh@mail.example.com",
                after_ts=200,
                max_wait=1,
                poll_interval=1,
                settle_seconds=0,
            )

        self.assertEqual(code, "654321")
        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], "GET")
        self.assertTrue(args[1].endswith("/api/mails"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer jwt-xyz")

    def test_release_clears_context(self):
        client._CONTEXT_CACHE["a@b.com"] = client.CFTempMailAccount(email="a@b.com", jwt="t")
        client.release_account("a@b.com", status="used")
        self.assertIsNone(client.get_account_context("a@b.com"))

    def test_admin_mode_without_key_fails(self):
        with patch.object(client._email_cfg, "CLOUDFLARE_API_BASE", "https://mail.example.com", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_AUTH_MODE", "x-admin-auth", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_API_KEY", "", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_PATH_ACCOUNTS", "/admin/new_address", create=True
        ):
            with self.assertRaisesRegex(client.CFTempMailError, "CLOUDFLARE_API_KEY"):
                client.pick_account()

    def test_persisted_mailbox_survives_release_and_process_cache_clear(self):
        account = client.CFTempMailAccount(
            email="persist@mail.example.com", jwt="mailbox-jwt", domain="mail.example.com", created_at=123,
        )
        client._persist_account(account)
        client._CONTEXT_CACHE[account.email] = account
        client.release_account(account.email, status="used")
        restored = client.get_account_context(account.email)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.jwt, "mailbox-jwt")
        self.assertEqual((Path(self.temp_dir.name) / "cloudflare_mailboxes.json").stat().st_mode & 0o777, 0o600)

    def test_scan_openai_deactivation_matches_notice(self):
        client._persist_account(client.CFTempMailAccount(email="user@mail.example.com", jwt="mailbox-jwt"))
        message = {
            "id": "m-1",
            "address": "user@mail.example.com",
            "from": "OpenAI <noreply@openai.com>",
            "subject": "Notice regarding your OpenAI account",
            "created_at": "2026-08-06 09:00:00",
            "text": "As a result of these violations, we are deactivating your access to our services immediately. Initiate an appeal.",
        }
        with patch.object(client._email_cfg, "CLOUDFLARE_SIGNAL_API_KEY", "", create=True), patch.object(
            client, "list_messages", side_effect=[[message], []]
        ):
            result = client.scan_openai_deactivation("user@mail.example.com", lookback_days=120)
        self.assertTrue(result["detected"])
        self.assertEqual(result["sender"], "noreply@openai.com")
        self.assertNotIn("text", result)

    @patch("core.cf_temp_mail_client.requests.post")
    def test_scan_openai_deactivation_uses_dedicated_signal_endpoint(self, post_mock):
        response = Mock(status_code=200)
        response.json.return_value = {
            "ok": True,
            "detected": True,
            "confidence": "high",
            "checked_at": "2026-08-06T10:00:00Z",
            "received_at": "2026-08-05 09:00:00",
            "subject": "Notice regarding your OpenAI account",
            "sender": "noreply@openai.com",
            "message_id": "mail-1",
        }
        post_mock.return_value = response
        with patch.object(client._email_cfg, "CLOUDFLARE_API_BASE", "https://mail.example.com/compat/temp-mail/v1", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_SIGNAL_API_KEY", "signal-key", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_SIGNAL_PATH", "/signals/scan", create=True):
            result = client.scan_openai_deactivation("old@mail.example.com", lookback_days=120)

        self.assertTrue(result["detected"])
        args, kwargs = post_mock.call_args
        self.assertEqual(args[0], "https://mail.example.com/compat/temp-mail/v1/signals/scan")
        self.assertEqual(kwargs["headers"]["x-admin-auth"], "signal-key")
        self.assertEqual(kwargs["json"], {"email": "old@mail.example.com", "lookback_days": 120})


    @patch("core.cf_temp_mail_client.requests.request")
    def test_list_messages_sends_limit_offset(self, request_mock):
        response = Mock(status_code=200)
        response.json.return_value = {"results": []}
        request_mock.return_value = response

        with patch.object(client._email_cfg, "CLOUDFLARE_API_BASE", "https://mail.example.com", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_PATH_MESSAGES", "/api/mails", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_AUTH_MODE", "none", create=True), patch.object(
            client._email_cfg, "CLOUDFLARE_API_KEY", "", create=True
        ), patch.object(client._email_cfg, "CLOUDFLARE_CUSTOM_AUTH", "", create=True):
            client.list_messages("jwt-xyz")

        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], "GET")
        self.assertTrue(args[1].endswith("/api/mails"))
        self.assertEqual(kwargs["params"]["limit"], 20)
        self.assertEqual(kwargs["params"]["offset"], 0)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer jwt-xyz")


    def test_created_at_without_tz_is_utc(self):
        from datetime import datetime, timezone
        ts = client._message_timestamp({"created_at": "2026-07-19 12:57:38"})
        expected = datetime(2026, 7, 19, 12, 57, 38, tzinfo=timezone.utc).timestamp()
        self.assertAlmostEqual(ts, expected, places=0)

    def test_otp_from_cloudflare_raw_openai_mail(self):
        raw = (
            "From: ChatGPT <noreply@tm.openai.com>\r\n"
            "Subject: ChatGPT code\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            "\r\n"
            "<html><body><p>Your code</p>\n449759\n</body></html>\r\n"
        )
        item = {
            "id": 77,
            "source": "bounces+x@em7877.tm.openai.com",
            "address": "user@beliefcode.online",
            "raw": raw,
            "created_at": "2026-07-19 12:57:38",
        }
        otp_item = client._otp_item(item)
        from core.otp_utils import looks_like_openai_email, extract_otp
        self.assertTrue(looks_like_openai_email(otp_item))
        self.assertEqual(extract_otp(otp_item), "449759")


if __name__ == "__main__":
    unittest.main()
