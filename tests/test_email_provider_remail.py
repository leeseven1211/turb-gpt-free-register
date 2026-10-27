"""Remail 在统一邮箱链路中的来源绑定、恢复与凭据保护。"""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config import email as email_config
from core import email_provider
from tests.support_pg import PostgresTestCase


class RemailProviderTests(unittest.TestCase):
    def setUp(self):
        self.hints = patch.dict(email_provider._EMAIL_SOURCE_HINTS, {}, clear=True)
        self.hints.start()
        self.addCleanup(self.hints.stop)

    def test_source_can_be_selected_in_mixed_configuration(self):
        self.assertEqual(
            email_provider.parse_email_sources("outlook,remail,gptmail,remail"),
            ["outlook", "remail", "gptmail"],
        )

    def test_new_acquisition_rejects_retired_supplier_even_in_compatibility_mode(self):
        with patch("core.remail_client.pick_account") as pick, patch(
            "core.outlook_client.pick_account"
        ) as outlook:
            with self.assertRaisesRegex(RuntimeError, "local_inventory_source_required"):
                email_provider.acquire_email("remail", legacy_remail_compatibility=True)
            pick.assert_not_called()
            outlook.assert_not_called()

    def test_ownerless_remail_does_not_invoke_client(self):
        with patch("core.remail_client.pick_account") as pick:
            with self.assertRaisesRegex(RuntimeError, "local_inventory_source_required"):
                email_provider.acquire_email("remail")
        pick.assert_not_called()

    def test_uncertain_order_preserves_reconciliation_without_fallback(self):
        from core.remail_client import RemailOrderUncertain

        with patch('core.local_email_inventory.find_local_email', return_value=None), patch(
            'core.email_derivation.restore_address', return_value=None
        ), patch('core.storage.remail_orders.get_intent', return_value={
            'acquisition_id': 'original', 'status': 'request_unknown', 'order_no': '', 'private_json': {},
        }), patch("core.outlook_client.pick_account") as outlook, patch(
            'core.remail_order_coordinator.RemailOrderCoordinator.acquire'
        ) as purchase:
            with self.assertRaises(RemailOrderUncertain):
                email_provider.restore_email_context('one@example.test', source='remail', acquisition_id='original')
        purchase.assert_not_called()
        outlook.assert_not_called()

    def test_otp_routes_explicit_source_with_time_and_wait_options(self):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True), patch(
            "core.remail_client.fetch_latest_otp", return_value="123456"
        ) as fetch, patch.object(email_provider, "resolve_email_source") as resolve:
            self.assertEqual(email_provider.wait_for_otp(
                "one@example.test", 123.0, email_source="remail", max_wait=40,
                poll_interval=2, settle_seconds=0,
            ), "123456")
        fetch.assert_called_once_with(
            "one@example.test", after_ts=123.0, max_wait=40, poll_interval=2, settle_seconds=0,
        )
        resolve.assert_not_called()

    def test_restart_restores_original_order_without_allocating(self):
        with patch("core.remail_client.restore_account_context", return_value=SimpleNamespace(
            email="ONE@example.test"
        )) as restore, patch("core.remail_client.pick_account") as pick, patch.object(
            email_provider, "_is_configured_manual_email", return_value=False
        ):
            self.assertEqual(email_provider.restore_email_context("one@example.test", source="remail", legacy_remail_compatibility=True), "remail")
        restore.assert_called_once_with("one@example.test", compatibility=True)
        pick.assert_not_called()

    def test_restart_rejects_missing_or_mismatched_order(self):
        for context in (None, SimpleNamespace(email="other@example.test")):
            with self.subTest(context=context), patch(
                "core.remail_client.restore_account_context", return_value=context
            ), patch("core.remail_client.pick_account") as pick, patch.object(
                email_provider, "_is_configured_manual_email", return_value=False
            ):
                with self.assertRaisesRegex(RuntimeError, "不能改用其他邮箱重跑"):
                    email_provider.restore_email_context("one@example.test", source="remail", legacy_remail_compatibility=True)
                pick.assert_not_called()

    def test_failure_retains_order_and_explicit_release_uses_remail(self):
        with patch("core.remail_client.release_account") as release:
            self.assertEqual(email_provider.retain_email("one@example.test", source="remail"), "remail")
            release.assert_not_called()
            email_provider.release_email("one@example.test", status="failed", source="remail")
        release.assert_called_once_with("one@example.test", status="failed", note=None)

    def test_persistence_keeps_credentials_private_without_mutating_caller(self):
        from core.account_export import persist_account_core
        from webui.route_helpers import _compact_account_for_list

        metadata = {"source": "remail", "email": "one@example.test", "service_token": "private-test-token"}
        extra = {"account_password": "private-test-password", "user": {"name": "测试"}}
        before = copy.deepcopy(extra)
        with patch("core.remail_client.get_account_context_metadata", return_value=metadata), patch(
            "core.db.insert_account", return_value=7
        ) as insert:
            self.assertEqual(persist_account_core("one@example.test", "test-at", extra=extra, email_source="remail"), 7)
        self.assertEqual(extra, before)
        self.assertEqual(insert.call_args.kwargs["extra"]["email_service"], metadata)
        compact = _compact_account_for_list({
            "id": 7, "email": "one@example.test", "email_source": "remail",
            "extra_json": insert.call_args.kwargs["extra"],
        })
        self.assertEqual(compact["email_source"], "remail")
        self.assertNotIn("private-test-token", str(compact))
        self.assertNotIn("private-test-password", str(compact))


class RemailPersistenceTests(PostgresTestCase):
    def test_saved_account_restores_mailbox_after_restart_without_api_key(self):
        from core import remail_client
        from core.account_export import persist_account_core
        from webui.app import create_app

        with patch.dict(remail_client._CONTEXT_CACHE, {}, clear=True), patch.object(
            email_config, "REMAIL_API_KEY", ""
        ), patch("requests.sessions.Session.request", side_effect=AssertionError("本地恢复不应联网")):
            remail_client._cache_context(remail_client.RemailAccount(
                email="saved@example.test", service_token="saved-private-token",
                order_no="test-order", project_id=2, email_suffix="example.test",
            ))
            persist_account_core("saved@example.test", "fixture-access-token", email_source="remail")
            remail_client._CONTEXT_CACHE.clear()
            context = remail_client.restore_account_context("saved@example.test")
            self.assertIsNotNone(context)
            self.assertEqual(context.service_token, "saved-private-token")
            client = create_app(auth_code="test-auth").test_client()
            response = client.get("/api/accounts", headers={"X-Auth-Code": "test-auth"})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("saved-private-token", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
