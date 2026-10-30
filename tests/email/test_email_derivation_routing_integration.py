# -*- coding: utf-8 -*-
"""派生服务到实际收件适配器的 PostgreSQL 隔离集成回归。"""
import os
from email.message import EmailMessage
from unittest.mock import Mock, patch

from core.email import derivation as derivation
from core.email import provider as email_provider
from core.email import forward_imap as forward
from core.email.icloud_hide import client as hme
from core.email.outlook import client as outlook
from core.email.cloudflare_domain import client as qq
from core.storage import records as record_store
from core.storage.email import address_allocations as allocations
from tests.support_pg import PostgresTestCase


class EmailDerivationRoutingIntegrationTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.parent_address = "parent@icloud.com"
        self.profile = allocations.create_inbox_profile(
            inbox_key="imap:historical-inbox", connector="forward_imap",
            credential_ref="TEST_DERIVATION_HISTORY_SECRET",
            inbox_locator={"server": "imap.history.test", "port": 1993, "email": "historical@example.test", "folder": "INBOX"},
        )
        self.parent_id = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": self.parent_address, "status": "used", "account_id": "apple-parent", "remote_active": True,
        })
        self.child = allocations.allocate_address(
            source="icloud_hide", acquisition_id="routing-intent", owner_kind="registration_root", owner_id="routing-intent",
            inbox_profile_id=self.profile["id"], parent_id=self.parent_id,
        )

    def test_provider_resolves_child_once_and_pins_historical_profile(self):
        seen = []

        def probe(target, after_ts, **kwargs):
            seen.append((target, after_ts, forward._settings()))
            return "123456"

        with patch.dict(os.environ, {"TEST_DERIVATION_HISTORY_SECRET": "old-password"}), patch.object(
            forward._email_cfg, "ICLOUD_HME_INBOX_MODE", "sidecar"
        ), patch.object(forward._email_cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "new@example.test"), patch.object(
            forward._email_cfg, "ICLOUD_HME_FORWARD_IMAP_PASSWORD", "new-password"
        ), patch.object(forward, "_fetch_latest_otp_local", side_effect=probe), patch.object(hme, "fetch_latest_otp") as old_adapter:
            code = email_provider.wait_for_otp(self.child["address"], after_ts=10, email_source="icloud_hide", force_service=True)
        self.assertEqual(code, "123456")
        self.assertEqual(seen, [(self.child["address"], 10, ("imap.history.test", 1993, "historical@example.test", "old-password"))])
        old_adapter.assert_not_called()

    def test_direct_hme_child_adapter_does_not_reenter_itself(self):
        with patch.dict(os.environ, {"TEST_DERIVATION_HISTORY_SECRET": "old-password"}), patch.object(
            forward, "_fetch_latest_otp_local", return_value="123456"
        ) as local:
            code = hme.fetch_latest_otp(self.child["address"], after_ts=10, max_wait=5)
        self.assertEqual(code, "123456")
        self.assertEqual(local.call_count, 1)
        self.assertEqual(local.call_args.args[0], self.child["address"])

    def test_mother_with_children_keeps_profile_after_global_mode_changes(self):
        with patch.dict(os.environ, {"TEST_DERIVATION_HISTORY_SECRET": "old-password"}), patch.object(
            forward._email_cfg, "ICLOUD_HME_INBOX_MODE", "sidecar"
        ), patch.object(forward, "_fetch_latest_otp_local", return_value="123456") as local, patch.object(
            hme, "_request", side_effect=AssertionError("有固定收件路由的母账号不应读取当前 sidecar")
        ):
            result = hme.fetch_latest_otp(self.parent_address, after_ts=10, max_wait=5)
        self.assertEqual(result, "123456")
        local.assert_called_once()
        self.assertEqual(local.call_args.args[0], self.parent_address)

    def test_non_plus_old_source_does_not_query_allocation_table(self):
        with patch.object(allocations, "find_allocation", side_effect=AssertionError("旧地址不应新增账本查询")), patch(
            "core.email.gptmail.client.fetch_latest_otp", return_value="123456"
        ) as fetch:
            code = email_provider.wait_for_otp("old@example.test", after_ts=10, email_source="gptmail", force_service=True)
        self.assertEqual(code, "123456")
        fetch.assert_called_once_with("old@example.test", after_ts=10)

    def test_unbound_historical_plus_keeps_generic_api_source(self):
        with patch("core.email.generic_api.client.fetch_latest_otp", return_value="123456") as fetch:
            code = email_provider.wait_for_otp("old+existing@example.test", after_ts=10, email_source="generic_api", force_service=True)
        self.assertEqual(code, "123456")
        fetch.assert_called_once_with("old+existing@example.test", after_ts=10)

    def test_bound_outlook_parent_credentials_filter_child_across_both_protocols(self):
        parent = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "parent@outlook.com", "password": "parent-password", "client_id": "parent-client", "refresh_token": "parent-refresh", "status": "used",
        })
        profile = allocations.create_inbox_profile(
            inbox_key="outlook:parent", connector="outlook", credential_ref=f"parent:outlook:{parent}", inbox_locator={"parent_id": parent},
        )
        child = allocations.allocate_address(
            source="outlook", acquisition_id="outlook-intent", owner_kind="registration_root", owner_id="outlook-intent",
            inbox_profile_id=profile["id"], parent_id=parent,
        )
        seen = []

        def fetch(_http, protocol, account):
            seen.append((protocol, account.email, account.client_id, account.refresh_token))
            if protocol == "imap":
                return []
            return [
                {"id": "sibling-message", "to": "parent+another@outlook.com", "from": "noreply@openai.com", "subject": "Your code is 222222", "date": "2026-10-20T00:00:02Z"},
                {"id": "child-message", "to": child["address"], "from": "noreply@openai.com", "subject": "Your code is 111111", "date": "2026-10-20T00:00:01Z"},
            ]

        with patch.object(outlook, "_http_session", return_value=Mock()), patch.object(outlook, "_fetch_via", side_effect=fetch):
            code = email_provider.wait_for_otp(child["address"], after_ts=10, email_source="outlook", force_service=True, settle_seconds=0)
        self.assertEqual(code, "111111")
        self.assertEqual(seen, [("graph", "parent@outlook.com", "parent-client", "parent-refresh"), ("imap", "parent@outlook.com", "parent-client", "parent-refresh")])

    def test_post_creation_failure_keeps_same_child_recoverable(self):
        email_provider.release_email(
            self.child["address"], status="failed", source="icloud_hide",
            note="创建接口已通过但后续失败，已废弃: 获取会话超时",
        )
        self.assertEqual(email_provider.restore_email_context(self.child["address"], source="icloud_hide"), "icloud_hide")
        self.assertEqual(derivation.restore_address(self.child["address"])["binding"]["id"], self.child["id"])

    def test_mother_with_children_does_not_eat_rewritten_ambiguous_child(self):
        msg = EmailMessage()
        msg["To"] = self.parent_address
        msg["X-ICLOUD-HME"] = self.parent_address
        msg["From"] = "OpenAI <noreply@openai.com>"
        msg["Subject"] = "Your code is 123456"
        msg["Date"] = "Tue, 20 Oct 2026 00:00:01 +0000"
        msg.set_content("Your code is 123456")
        item = qq._msg_to_dict(msg)
        mail = Mock()

        def probe(target, after_ts, **kwargs):
            return forward._latest_forwarded_otp(mail, target, after_ts) or "pending"

        with patch.dict(os.environ, {"TEST_DERIVATION_HISTORY_SECRET": "old-password"}), patch.object(
            forward._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_imap"
        ), patch.object(forward, "_fetch_latest_otp_local", side_effect=probe
        ), patch.object(forward, "_iter_messages_for_recipient", return_value=[(item, self.parent_address, "10")]):
            result = email_provider.wait_for_otp(self.parent_address, after_ts=10, email_source="icloud_hide", force_service=True)
        self.assertEqual(result, "pending")

    def test_deactivation_scan_uses_same_historical_inbox_as_child_otp(self):
        seen = []

        def connect():
            seen.append(forward._settings())
            return Mock()

        with patch.dict(os.environ, {"TEST_DERIVATION_HISTORY_SECRET": "old-password"}), patch.multiple(
            forward._email_cfg, ICLOUD_HME_FORWARD_IMAP_SERVER="imap.current.test", ICLOUD_HME_FORWARD_IMAP_PORT=993,
            ICLOUD_HME_FORWARD_IMAP_EMAIL="current@example.test", ICLOUD_HME_FORWARD_IMAP_PASSWORD="current-password",
        ), patch.object(forward, "_connect", side_effect=connect), patch.object(
            forward, "_messages_for_recipients", return_value={self.child["address"]: []}
        ):
            results = forward.scan_openai_deactivation_bulk([self.child["address"]])
        self.assertFalse(results[self.child["address"]]["detected"])
        self.assertEqual(seen, [("imap.history.test", 1993, "historical@example.test", "old-password")])

    def test_profile_route_version_metadata_reaches_candidate_observer(self):
        with patch.dict(os.environ, {"TEST_DERIVATION_HISTORY_SECRET": "old-password"}):
            resolved = derivation._profile_credentials(self.profile)
        self.assertEqual(resolved.get("id"), self.profile["id"])
        self.assertEqual(resolved.get("inbox_key"), "imap:historical-inbox")
        self.assertEqual(resolved.get("revision"), self.profile["revision"])
