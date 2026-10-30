# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import email as email_config
from core.email import provider as email_provider


class GPTMailProviderTests(unittest.TestCase):
    def setUp(self):
        email_provider._EMAIL_SOURCE_HINTS.clear()

    def test_parse_sources_keeps_gptmail_in_order(self):
        self.assertEqual(
            email_provider.parse_email_sources("outlook,gptmail,generic_api,mailnest,cloudmail"),
            ["outlook", "gptmail", "generic_api", "mailnest", "cloudmail"],
        )

    @patch("core.email.gptmail.client.pick_account")
    def test_acquire_email_uses_gptmail_client(self, pick_account):
        pick_account.return_value.email = "fresh@gptmail.test"

        with patch("core.email.provider.parse_email_sources", return_value=["gptmail"]):
            self.assertEqual(email_provider.acquire_email(), "fresh@gptmail.test")

    @patch("core.email.gptmail.client.get_account_context", return_value=object())
    def test_resolve_email_source_recognizes_cached_gptmail_address(self, get_context):
        self.assertEqual(email_provider.resolve_email_source("fresh@gptmail.test"), "gptmail")
        get_context.assert_called_once_with("fresh@gptmail.test")

    @patch("core.email.gptmail.client.release_account")
    @patch("core.email.provider.resolve_email_source", return_value="gptmail")
    def test_release_email_clears_gptmail_context(self, resolve, release):
        self.assertEqual(email_provider.release_email("fresh@gptmail.test", status="failed"), "gptmail")
        release.assert_called_once_with("fresh@gptmail.test", status="failed", note=None)

    def test_retain_email_does_not_release_provider_lease(self):
        with patch("core.email.gptmail.client.release_account") as release:
            source = email_provider.retain_email(
                "held@gptmail.test",
                source="gptmail",
                note="中途失败",
            )

        self.assertEqual(source, "gptmail")
        release.assert_not_called()
        self.assertEqual(email_provider.resolve_email_source("held@gptmail.test"), "gptmail")

    def test_release_email_uses_explicit_source_without_reresolving(self):
        with patch(
            "core.email.provider.resolve_email_source",
            side_effect=AssertionError("不应按当前配置重新解析来源"),
        ), patch("core.email.icloud_hide.client.release_account") as release_account:
            source = email_provider.release_email(
                "held@icloud.com",
                status="failed",
                note="上游确认永久失效",
                source="icloud_hide",
            )

        self.assertEqual(source, "icloud_hide")
        release_account.assert_called_once_with(
            "held@icloud.com",
            status="failed",
            note="上游确认永久失效",
        )

    def test_mark_permanently_unusable_passes_verified_source_to_release(self):
        with patch.object(email_provider, "release_email", return_value="icloud_hide") as release_email:
            source = email_provider.mark_email_permanently_unusable(
                "held@icloud.com",
                source="icloud_hide",
                note="上游确认永久失效",
            )

        self.assertEqual(source, "icloud_hide")
        release_email.assert_called_once_with(
            "held@icloud.com",
            status="failed",
            note="上游确认永久失效",
            source="icloud_hide",
        )

    def test_mark_permanently_unusable_rejects_unknown_source(self):
        with patch.object(email_provider, "resolve_email_source", return_value=None) as resolve_source, patch.object(
            email_provider, "release_email"
        ) as release_email:
            with self.assertRaisesRegex(RuntimeError, "邮箱来源无法确认"):
                email_provider.mark_email_permanently_unusable(
                    "unknown@example.test",
                    note="上游确认永久失效",
                )

        resolve_source.assert_called_once_with("unknown@example.test", fallback=False)
        release_email.assert_not_called()

    @patch("core.email.gptmail.client.pick_account")
    def test_acquire_email_remembers_explicit_source(self, pick_account):
        pick_account.return_value.email = "fresh@gptmail.test"

        self.assertEqual(email_provider.acquire_email("gptmail"), "fresh@gptmail.test")
        self.assertEqual(email_provider.resolve_email_source("fresh@gptmail.test", fallback=False), "gptmail")

    @patch("core.email.gptmail.client.get_account_context", return_value=None)
    def test_restore_retry_context_rejects_lost_gptmail_lease(self, get_context):
        with self.assertRaisesRegex(RuntimeError, "不能改用其他邮箱重跑"):
            email_provider.restore_email_context(
                "held@gptmail.test",
                source="gptmail",
            )

        get_context.assert_called_once_with("held@gptmail.test")

    @patch("core.db.get_domain_email_by_email", return_value={"status": "available"})
    def test_restore_domain_retry_rejects_released_email(self, get_domain_email):
        with patch.object(email_provider, "_is_configured_manual_email", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "不能改用其他邮箱重跑"):
                email_provider.restore_email_context(
                    "held@domain.test",
                    source="cloudflare_domain",
                )

        get_domain_email.assert_called_once_with("held@domain.test")

    @patch("core.email.gptmail.client.fetch_latest_otp", return_value="654321")
    @patch("core.email.provider.resolve_email_source", return_value="gptmail")
    def test_wait_for_otp_uses_gptmail_client(self, resolve, fetch_latest_otp):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True):
            self.assertEqual(email_provider.wait_for_otp("fresh@gptmail.test", after_ts=123.0), "654321")
        fetch_latest_otp.assert_called_once_with("fresh@gptmail.test", after_ts=123.0)

    def test_wait_for_otp_uses_explicit_source_without_reresolving(self):
        with patch(
            "core.email.provider.resolve_email_source",
            side_effect=AssertionError("重跑任务不应按已有账号或当前配置改判邮箱来源"),
        ), patch("core.email.icloud_hide.client.fetch_latest_otp", return_value="654321") as fetch_latest_otp, patch.object(
            email_config, "USE_EMAIL_SERVICE", True
        ):
            otp = email_provider.wait_for_otp(
                "held@example.test",
                after_ts=123.0,
                email_source="icloud_hide",
            )

        self.assertEqual(otp, "654321")
        fetch_latest_otp.assert_called_once_with("held@example.test", after_ts=123.0)

    @patch("core.email.mailnest.client.pick_account")
    def test_acquire_email_uses_mailnest_client(self, pick_account):
        pick_account.return_value.email = "fresh@mailnest.test"

        with patch("core.email.provider.parse_email_sources", return_value=["mailnest"]):
            self.assertEqual(email_provider.acquire_email(), "fresh@mailnest.test")

    @patch("core.email.mailnest.client.fetch_latest_otp", return_value="112233")
    @patch("core.email.provider.resolve_email_source", return_value="mailnest")
    def test_wait_for_otp_uses_mailnest_client(self, resolve, fetch_latest_otp):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True):
            self.assertEqual(email_provider.wait_for_otp("fresh@mailnest.test", after_ts=123.0), "112233")
        fetch_latest_otp.assert_called_once_with("fresh@mailnest.test", after_ts=123.0)

    @patch("core.email.cloudmail.client.pick_account")
    def test_acquire_email_uses_cloudmail_client(self, pick_account):
        pick_account.return_value.email = "fresh@cloudmail.test"

        with patch("core.email.provider.parse_email_sources", return_value=["cloudmail"]):
            self.assertEqual(email_provider.acquire_email(), "fresh@cloudmail.test")

    @patch("core.email.cloudmail.client.fetch_latest_otp", return_value="445566")
    @patch("core.email.provider.resolve_email_source", return_value="cloudmail")
    def test_wait_for_otp_uses_cloudmail_client(self, resolve, fetch_latest_otp):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True):
            self.assertEqual(email_provider.wait_for_otp("fresh@cloudmail.test", after_ts=123.0), "445566")
        fetch_latest_otp.assert_called_once_with("fresh@cloudmail.test", after_ts=123.0)
