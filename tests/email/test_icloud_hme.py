# -*- coding: utf-8 -*-
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from unittest.mock import patch

from core import db
from core.storage import records as rs
from core.email.icloud_hide import client as client
from core.email import provider as email_provider
from tests.support_pg import PostgresTestCase


class ICloudHidePoolTests(PostgresTestCase):
    def setUp(self):
        from tests.support_email_service_facts import confirmed_service_facts
        self.facts = confirmed_service_facts()
        self.acknowledge = self.facts.__enter__()
        self.addCleanup(self.facts.__exit__, None, None, None)

    def sync_aliases(self, *args, **kwargs):
        result = db.sync_icloud_hide_aliases(*args, **kwargs)
        self.acknowledge()
        return result

    def tearDown(self):
        pass

    def test_sync_claim_and_release_unconsumed(self):
        result = self.sync_aliases([
            {
                "email": "one@example.com",
                "anonymousId": "anon-1",
                "label": "One",
                "forwardToEmail": "owner@gmail.com",
                "active": True,
            },
            {"email": "off@example.com", "anonymousId": "anon-2", "label": "Off", "active": False},
        ], "acc-1")
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(db.icloud_hide_email_pool_summary()["available"], 1)
        self.assertEqual(db.icloud_hide_email_pool_summary()["disabled"], 1)

        claimed = db.claim_next_icloud_hide_email("acc-1")
        self.assertEqual(claimed["email"], "one@example.com")
        self.assertEqual(claimed["status"], "used")
        self.assertEqual(claimed["forward_to_email"], "owner@gmail.com")
        self.assertTrue(db.release_unconsumed_icloud_hide_email("one@example.com", note="task stopped"))
        self.assertEqual(db.get_icloud_hide_email_by_email("one@example.com")["status"], "available")

    def test_claim_can_restrict_to_multiple_accounts(self):
        self.sync_aliases([{"email": "a@example.com", "active": True}], "acc-a")
        self.sync_aliases([{"email": "b@example.com", "active": True}], "acc-b")

        claimed = db.claim_next_icloud_hide_email(account_ids=["acc-b"])

        self.assertEqual(claimed["email"], "b@example.com")
        self.assertEqual(db.get_icloud_hide_email_by_email("a@example.com")["status"], "available")

    def test_claim_excludes_alias_already_seen_in_same_registration_batch(self):
        self.sync_aliases([
            {"email": "old@example.com", "active": True},
            {"email": "fresh@example.com", "active": True},
        ], "acc-a")
        self.assertTrue(db.claim_registration_batch_email(
            "batch-a", "old@example.com", job_id=1, email_source="icloud_hide"
        ))

        claimed = db.claim_next_icloud_hide_email(
            account_ids=["acc-a"],
            batch_id="batch-a",
        )

        self.assertEqual(claimed["email"], "fresh@example.com")
        self.assertEqual(db.get_icloud_hide_email_by_email("old@example.com")["status"], "available")

    def test_atomic_claim_excludes_pre_claim_table_registration_job(self):
        self.sync_aliases([
            {"email": "old@example.com", "active": True},
            {"email": "fresh@example.com", "active": True},
        ], "acc-a")
        old_job = db.create_job("icloud_hide", batch_id="batch-a")
        db.update_job(old_job["id"], email="old@example.com")

        claimed = db.claim_next_icloud_hide_email(
            account_ids=["acc-a"],
            batch_id="batch-a",
            job_id=old_job["id"] + 1,
            email_source="icloud_hide",
        )

        self.assertEqual(claimed["email"], "fresh@example.com")
        self.assertEqual(
            db.get_icloud_hide_email_by_email("old@example.com")["status"],
            "available",
        )

    def test_batch_claim_is_durable_in_same_transaction_as_pool_claim(self):
        self.sync_aliases([
            {"email": "one@example.com", "active": True},
        ], "acc-a")

        claimed = db.claim_next_icloud_hide_email(
            account_ids=["acc-a"],
            batch_id="batch-a",
            job_id=17,
            email_source="icloud_hide",
        )

        self.assertEqual(claimed["email"], "one@example.com")
        row = rs.get_row_by(
            rs.REGISTRATION_BATCH_EMAIL_CLAIMS,
            "claim_key",
            "batch-a\x1fone@example.com",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["job_id"], 17)
        self.assertTrue(db.claim_registration_batch_email(
            "batch-a", "one@example.com", job_id=17, email_source="icloud_hide"
        ))

    def test_batch_claim_failure_rolls_back_pool_claim(self):
        self.sync_aliases([
            {"email": "one@example.com", "active": True},
        ], "acc-a")

        with patch.object(rs, "insert_row_if_absent", side_effect=RuntimeError("claim write failed")):
            with self.assertRaisesRegex(RuntimeError, "claim write failed"):
                db.claim_next_icloud_hide_email(
                    account_ids=["acc-a"],
                    batch_id="batch-a",
                    job_id=17,
                    email_source="icloud_hide",
                )

        self.assertEqual(
            db.get_icloud_hide_email_by_email("one@example.com")["status"],
            "available",
        )

    def test_batch_claim_retries_postgres_deadlock(self):
        from psycopg.errors import DeadlockDetected

        self.sync_aliases([
            {"email": "one@example.com", "active": True},
        ], "acc-a")

        with patch.object(
            rs,
            "claim_next_row",
            side_effect=[DeadlockDetected("deadlock"), {"email": "one@example.com", "status": "used"}],
        ), patch.object(rs, "insert_row_if_absent", return_value=17), patch(
            "core.storage.db_legacy.time.sleep"
        ) as sleep:
            claimed = db.claim_next_icloud_hide_email(
                account_ids=["acc-a"],
                batch_id="batch-a",
                job_id=17,
                email_source="icloud_hide",
            )

        self.assertEqual(claimed["email"], "one@example.com")
        sleep.assert_called_once_with(0.05)

    def test_concurrent_batch_claims_receive_distinct_aliases(self):
        self.sync_aliases([
            {"email": "one@example.com", "active": True},
            {"email": "two@example.com", "active": True},
        ], "acc-a")

        def claim(job_id):
            return db.claim_next_icloud_hide_email(
                account_ids=["acc-a"],
                batch_id="batch-a",
                job_id=job_id,
                email_source="icloud_hide",
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            rows = list(executor.map(claim, (17, 18)))

        self.assertEqual(
            {row["email"] for row in rows},
            {"one@example.com", "two@example.com"},
        )
        claims = rs.list_rows(
            rs.REGISTRATION_BATCH_EMAIL_CLAIMS,
            where='"batch_id" = %s',
            params=("batch-a",),
        )
        self.assertEqual({row["job_id"] for row in claims}, {17, 18})

    def test_summary_is_grouped_by_account(self):
        self.sync_aliases([
            {"email": "a1@example.com", "active": True},
            {"email": "a2@example.com", "active": True},
        ], "acc-a")
        self.sync_aliases([{"email": "b1@example.com", "active": False}], "acc-b")
        db.claim_next_icloud_hide_email("acc-a")

        grouped = {row["account_id"]: row for row in db.icloud_hide_email_pool_summary_by_account()}

        self.assertEqual(grouped["acc-a"]["available"], 1)
        self.assertEqual(grouped["acc-a"]["used"], 1)
        self.assertEqual(grouped["acc-b"]["disabled"], 1)

    def test_registered_alias_is_not_released(self):
        rs.insert_row(rs.ACCOUNTS, {"email": "bound@example.com"})
        self.sync_aliases([{"email": "bound@example.com", "active": True}], "acc-1")
        self.assertEqual(db.get_icloud_hide_email_by_email("bound@example.com")["status"], "used")
        self.assertFalse(db.release_unconsumed_icloud_hide_email("bound@example.com"))

    def test_full_sync_disables_missing_alias_but_partial_sync_does_not(self):
        self.sync_aliases([
            {"email": "keep@example.com", "active": True},
            {"email": "missing@example.com", "active": True},
        ], "acc-1")
        self.sync_aliases([{"email": "new@example.com", "active": True}], "acc-1", full_snapshot=False)
        self.assertEqual(db.get_icloud_hide_email_by_email("missing@example.com")["status"], "available")

        self.sync_aliases([
            {"email": "keep@example.com", "active": True},
            {"email": "new@example.com", "active": True},
        ], "acc-1")
        missing = db.get_icloud_hide_email_by_email("missing@example.com")
        self.assertEqual(missing["status"], "disabled")
        self.assertEqual(missing["disabled_reason"], "remote_missing")

    def test_active_sync_reactivates_legacy_route_disabled_alias(self):
        rs.insert_row(rs.ICLOUD_HIDE_POOL, {
            "email": "relay@example.com",
            "status": "disabled",
            "account_id": "acc-1",
            "remote_active": True,
        })
        self.sync_aliases([{"email": "relay@example.com", "active": True}], "acc-1")

        saved_row = db.get_icloud_hide_email_by_email("relay@example.com")
        self.assertEqual(saved_row["status"], "available")
        self.assertNotIn("disabled_reason", saved_row)


class ICloudHMEClientTests(unittest.TestCase):
    def assert_management_retired(self, operation, **kwargs):
        # Exercise the real retired entry; guard only effects it must never reach.
        with ExitStack() as stack:
            effects = [stack.enter_context(patch(target)) for target in (
                "core.email.icloud_hide.client._request",
                "core.db.sync_icloud_hide_aliases",
                "core.db.icloud_hide_email_pool_summary",
                "core.db.icloud_hide_email_pool_summary_by_account",
                "core.email.inventory.claim",
                "core.email.forward_imap.test_local_connection",
                "core.email.forward_imap.test_connection",
            )]
            with self.assertRaisesRegex(client.ICloudHMEError, "^email_management_retired:"):
                operation(**kwargs)
            for effect in effects:
                effect.assert_not_called()

    def test_non_icloud_forward_target_is_disabled_for_imap_pool(self):
        prepared, routing = client._prepare_imap_aliases([
            {"email": "bad@icloud.com", "forwardToEmail": "owner@gmail.com", "active": True},
            {"email": "good@icloud.com", "forwardToEmail": "owner@icloud.com", "active": True},
        ])
        self.assertFalse(prepared[0]["active"])
        self.assertTrue(prepared[1]["active"])
        self.assertEqual(routing["forward_domains"], ["gmail.com", "icloud.com"])
        self.assertEqual(routing["forward_incompatible"], 1)
        self.assertEqual(routing["remote_usable"], 1)

    def test_gmail_forward_target_is_enabled_for_matching_forward_imap(self):
        prepared, routing = client._prepare_imap_aliases(
            [{"email": "alias@icloud.com", "forwardToEmail": "owner@gmail.com", "active": True}],
            inbox_mode="forward_imap",
            forward_imap_email="owner@gmail.com",
        )
        self.assertTrue(prepared[0]["active"])
        self.assertEqual(routing["remote_usable"], 1)
        self.assertEqual(routing["forward_incompatible"], 0)

    def test_forward_imap_keeps_intermediate_gmail_target_usable(self):
        prepared, routing = client._prepare_imap_aliases(
            [{"email": "alias@icloud.com", "forwardToEmail": "relay@gmail.com", "active": True}],
            inbox_mode="forward_imap",
            forward_imap_email="owner@gmail.com",
        )
        self.assertTrue(prepared[0]["active"])
        self.assertEqual(routing["remote_usable"], 1)
        self.assertEqual(routing["forward_incompatible"], 0)

    @patch("core.email.forward_imap.fetch_latest_otp", return_value="123456")
    def test_forward_butler_relay_target_does_not_block_polling(self, fetch):
        with patch.object(client, "_inbox_mode", return_value="forward_butler"), patch.object(
            client._email_cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "owner@gmail.com"
        ), patch.object(
            client, "get_account_context", return_value=client.ICloudHMEAccount(
                email="alias@icloud.com", account_id="acc-1", forward_to_email="other@gmail.com"
            )
        ):
            self.assertEqual(client.fetch_latest_otp("alias@icloud.com", max_wait=1), "123456")
        fetch.assert_called_once()

    @patch("core.email.forward_imap.fetch_latest_otp", return_value="123456")
    @patch.object(client, "get_account_context", return_value=client.ICloudHMEAccount(
        email="alias@icloud.com", account_id="acc-1", forward_to_email="relay@gmail.com"
    ))
    @patch.object(client, "_inbox_mode", return_value="forward_imap")
    def test_forward_imap_uses_final_inbox_for_relay_route(self, _mode, _context, fetch):
        result = client.fetch_latest_otp("alias@icloud.com", after_ts=123.0, max_wait=10)

        self.assertEqual(result, "123456")
        fetch.assert_called_once()

    def test_dynamic_forced_sync_is_retired_before_remote_or_local_mutation(self):
        with patch.object(client._email_cfg, "ICLOUD_HME_ACCOUNT_ID", ""):
            self.assert_management_retired(client.sync_aliases, force=True)

    def test_explicit_account_sync_is_retired_without_partial_remote_work(self):
        with patch.object(client._email_cfg, "ICLOUD_HME_ACCOUNT_ID", "configured-account"):
            self.assert_management_retired(
                client.sync_aliases, force=False, account_id="explicit-account",
                api_base="http://127.0.0.1:8081", timeout=7,
            )

    def test_pick_account_uses_local_inventory_without_remote_sync(self):
        row = {
            "email": "b@example.com", "account_id": "acc-b", "anonymous_id": "anon-b",
            "label": "local alias", "forward_to_email": "owner@gmail.com",
        }
        with patch("core.email.inventory.claim", return_value=row) as claim, patch.object(
            client, "sync_aliases"
        ) as sync, patch.object(client, "_request") as request, patch.object(client, "create_address") as create:
            account = client.pick_account()

        self.assertEqual(account, client.ICloudHMEAccount(
            email="b@example.com", account_id="acc-b", anonymous_id="anon-b",
            label="local alias", forward_to_email="owner@gmail.com",
        ))
        claim.assert_called_once_with(
            "icloud_hide", owner_kind=None, owner_id=None, acquisition_id=None,
            batch_id=None, job_id=None,
        )
        sync.assert_not_called()
        request.assert_not_called()
        create.assert_not_called()

    def test_pick_account_forwards_stable_identity_and_registration_batch(self):
        with patch("core.email.inventory.claim", return_value={
            "email": "b@example.com", "account_id": "acc-b",
        }) as claim, patch.object(client, "sync_aliases") as sync, patch.object(
            client, "_request"
        ) as request, patch.object(client, "create_address") as create:
            account = client.pick_account(
                owner_kind="registration_job", owner_id=17, acquisition_id="local-job:17",
                batch_id="batch-a", job_id=17,
            )

        self.assertEqual(account, client.ICloudHMEAccount(email="b@example.com", account_id="acc-b"))
        claim.assert_called_once_with(
            "icloud_hide", owner_kind="registration_job", owner_id=17, acquisition_id="local-job:17",
            batch_id="batch-a", job_id=17,
        )
        sync.assert_not_called()
        request.assert_not_called()
        create.assert_not_called()

    def test_pick_account_empty_local_inventory_has_no_remote_fallback(self):
        with patch("core.email.inventory.claim", return_value=None) as claim, patch.object(
            client, "sync_aliases"
        ) as sync, patch.object(client, "_request") as request, patch.object(client, "create_address") as create:
            with self.assertRaisesRegex(client.ICloudHMEError, "^local_email_inventory_empty:"):
                client.pick_account(
                    owner_kind="registration_job", owner_id=17, acquisition_id="local-job:17",
                    batch_id="batch-a", job_id=17,
                )

        claim.assert_called_once_with(
            "icloud_hide", owner_kind="registration_job", owner_id=17, acquisition_id="local-job:17",
            batch_id="batch-a", job_id=17,
        )
        sync.assert_not_called()
        request.assert_not_called()
        create.assert_not_called()

    def test_dynamic_connection_check_is_retired_before_account_enumeration(self):
        with patch.object(client._email_cfg, "ICLOUD_HME_ACCOUNT_ID", ""):
            self.assert_management_retired(client.test_connection, api_base="http://127.0.0.1:8081")

    @patch("core.email.forward_imap.fetch_latest_otp", return_value="123456")
    @patch.object(client, "_validate_forward_route")
    @patch.object(client, "_inbox_mode", return_value="forward_butler")
    def test_fetch_latest_otp_delegates_to_forward_cache(self, _mode, validate_route, fetch):
        result = client.fetch_latest_otp("alias@icloud.com", after_ts=123.0, max_wait=10)
        self.assertEqual(result, "123456")
        validate_route.assert_called_once_with("alias@icloud.com")
        fetch.assert_called_once()

    def setUp(self):
        client._LAST_SYNC_AT = 0.0
        client._LAST_SYNC_KEY = ""
        client._LAST_ACCOUNT_ID = ""
        client._LAST_SYNC_RESULT = {}
        self.inbox_mode_patch = patch.object(client, "_inbox_mode", return_value="sidecar")
        self.inbox_mode_patch.start()

    def tearDown(self):
        self.inbox_mode_patch.stop()

    def test_explicit_connection_check_is_retired_before_sync_or_imap(self):
        self.assert_management_retired(
            client.test_connection, api_base="http://127.0.0.1:8081", account_id="acc-1", timeout=7,
        )

    def test_connection_retirement_precedes_forward_route_checks(self):
        for mode in ("sidecar", "forward_imap", "forward_butler"):
            with self.subTest(mode=mode), patch.object(client, "_inbox_mode", return_value=mode), patch.object(
                client._email_cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "owner@gmail.com"
            ):
                self.assert_management_retired(
                    client.test_connection, api_base="http://127.0.0.1:8081", account_id="acc-1",
                )

    def test_cached_sync_cannot_bypass_retired_management(self):
        cached = {"account_id": "auto-selected", "account_ids": ["auto-selected"], "cached": True}
        with patch.object(client, "_LAST_SYNC_AT", time.time()), patch.object(
            client, "_LAST_SYNC_KEY", "cached-sidecar"
        ), patch.object(client, "_LAST_ACCOUNT_ID", "auto-selected"), patch.object(
            client, "_LAST_SYNC_RESULT", cached
        ), patch.object(client._email_cfg, "ICLOUD_HME_ACCOUNT_ID", ""):
            for force in (False, True):
                with self.subTest(force=force):
                    self.assert_management_retired(client.sync_aliases, force=force)
            self.assertEqual(client._LAST_SYNC_RESULT, cached)

    @patch("core.email.icloud_hide.client.get_account_context", return_value=client.ICloudHMEAccount(
        email="alias@icloud.com", account_id="acc-1"
    ))
    @patch("core.email.icloud_hide.client._request")
    def test_fetch_latest_otp_reads_new_openai_message(self, request_mock, _context):
        request_mock.return_value = {
            "method": "imap",
            "messages": [{
                "id": "101",
                "from": "OpenAI <noreply@tm.openai.com>",
                "to": "alias@icloud.com",
                "subject": "Your ChatGPT code is 654321",
                "date": "2026-08-10T12:00:01Z",
                "preview": "Your verification code is 654321",
            }],
        }
        otp = client.fetch_latest_otp(
            "alias@icloud.com",
            after_ts=time.mktime((2026, 8, 10, 11, 59, 0, 0, 0, -1)),
            max_wait=2,
            poll_interval=1,
            settle_seconds=0,
        )
        self.assertEqual(otp, "654321")


class ICloudEmailProviderTests(unittest.TestCase):
    def test_source_is_parsed_and_acquired(self):
        self.assertEqual(email_provider.parse_email_sources("icloud_hide,outlook"), ["icloud_hide", "outlook"])
        with patch("core.email.icloud_hide.client.pick_account", return_value=client.ICloudHMEAccount(
            email="alias@icloud.com", account_id="acc-1"
        )) as pick, patch("core.email.derivation.store.find_allocation", return_value=None) as allocation, patch(
            "core.email.derivation.acquire_address"
        ) as restore:
            self.assertEqual(
                email_provider._pick_from_source(
                    "icloud_hide",
                    batch_id="batch-a",
                    job_id=17,
                    owner_kind="registration_job",
                    owner_id=17,
                    acquisition_id="local-job:17",
                ),
                "alias@icloud.com",
            )

        allocation.assert_called_once_with(acquisition_id="local-job:17")
        restore.assert_not_called()
        pick.assert_called_once_with(
            batch_id="batch-a", job_id=17, owner_kind="registration_job", owner_id=17,
            acquisition_id="local-job:17",
        )

    @patch("core.db.get_icloud_hide_email_by_email", return_value={"email": "alias@icloud.com", "account_id": "acc-1"})
    def test_resolve_and_release_unconsumed_use_icloud_pool(self, _context):
        with patch("core.db.release_unconsumed_icloud_hide_email", return_value=True) as release:
            self.assertEqual(email_provider.resolve_email_source("alias@icloud.com"), "icloud_hide")
            self.assertTrue(email_provider.release_email_if_unconsumed("alias@icloud.com", note="stopped"))
            release.assert_called_once_with("alias@icloud.com", note="stopped")


if __name__ == "__main__":
    unittest.main()
