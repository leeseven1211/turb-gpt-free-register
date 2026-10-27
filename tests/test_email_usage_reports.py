"""HME result outbox uses only isolated PostgreSQL and fixture connections."""
import importlib
import importlib.util
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core import email_butler_client as butler, postgres_store, record_store
from core import icloud_hme_client as hme
from tests.support_pg import PostgresTestCase


ADDRESS = "usage-fixture@icloud.com"


class EmailUsageReportsTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.env = patch.dict(os.environ, {"USAGE_FIXTURE_KEY": "fixture-only"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.profile_id = record_store.insert_row(record_store.EMAIL_INBOX_PROFILES, {
            "inbox_key": butler._hme_profile_key(ADDRESS), "revision": 1, "state": "active",
            "connector": "forward_butler", "credential_ref": "USAGE_FIXTURE_KEY",
            "inbox_locator": {"api_base": "https://fixed.example/v1", "mailbox_email": "final@example.test"},
            "butler_identity": {"email": ADDRESS, "provider": "icloud_hme", "acquisition_id": "original-acquisition"},
        })
        self.row = {"email": ADDRESS, "local_inbox_profile_id": self.profile_id,
            "local_owner_kind": "registration_root", "local_owner_id": "task-owner",
            "butler_handoff": {"acquisition_id": "handoff-acquisition", "owner_kind": "local_inventory",
                "owner_id": "remote-owner", "identity_id": "remote-identity"}}

    def reports(self):
        self.assertIsNotNone(importlib.util.find_spec("core.email_usage_reports"), "durable HME outbox is missing")
        return importlib.import_module("core.email_usage_reports")

    def rows(self):
        return record_store.list_rows(record_store.EMAIL_USAGE_REPORTS, order_by="id")

    def enqueue(self, status="used"):
        return self.reports().enqueue(ADDRESS, status=status, source="icloud_hide", row=self.row)

    def test_enqueue_rolls_back_with_the_local_transaction(self):
        reports = self.reports()
        with self.assertRaisesRegex(RuntimeError, "rollback fixture"):
            with record_store.transaction() as conn, conn.cursor() as cursor:
                reports.enqueue(ADDRESS, status="used", source="icloud_hide", row=self.row, cursor=cursor)
                raise RuntimeError("rollback fixture")
        self.assertEqual(self.rows(), [])

    def test_duplicate_success_is_durable_and_preserves_remote_ownership(self):
        first = self.enqueue()
        second = self.enqueue()
        self.assertEqual(first["id"], second["id"])
        event = self.rows()[0]
        self.assertEqual(event["payload"]["owner_kind"], "local_inventory")
        self.assertEqual(event["payload"]["owner_id"], "remote-owner")
        self.assertEqual(event["payload"]["acquisition_id"], "handoff-acquisition")
        self.assertNotIn("task-owner", str(event))
        self.assertTrue(self.reports().has_success(ADDRESS))

    def test_unknown_and_available_enqueue_nothing(self):
        for status in ("request_unknown", "unknown", "running", "reserved", "available"):
            self.assertIsNone(self.enqueue(status))
        self.assertEqual(self.rows(), [])

    def test_shared_parent_profile_does_not_share_child_operation_ids(self):
        reports = self.reports()
        route = {"inbox_profile_id": self.profile_id}
        first = reports.enqueue("usage-fixture+first@icloud.com", source="icloud_hide", status="used", row=route)
        second = reports.enqueue("usage-fixture+second@icloud.com", source="icloud_hide", status="used", row=route)
        self.assertNotEqual(first["operation_id"], second["operation_id"])
        self.assertEqual(len(self.rows()), 2)

    def test_success_supersedes_pending_failure_and_ignores_late_failure(self):
        self.enqueue("failed")
        self.enqueue("used")
        self.assertIsNone(self.enqueue("retired"))
        self.assertEqual([(r["result"], r["state"]) for r in self.rows()],
            [("provider_error", "superseded"), ("ok", "pending")])

    def test_retry_survives_connection_change_and_uses_same_operation(self):
        self.enqueue()
        with patch.object(butler, "_request", side_effect=butler.EmailButlerClientError("https://secret@bad.test otp=123456")):
            self.assertTrue(self.reports().dispatch_once())
        failed = self.rows()[0]
        self.assertEqual(failed["state"], "pending")
        self.assertNotIn("123456", str(failed))
        record_store.patch_row(record_store.EMAIL_USAGE_REPORTS, failed["id"], {"next_attempt_at": None})
        with patch.object(butler, "_request", return_value={"code": 200}) as request:
            self.assertTrue(self.reports().dispatch_once())
        self.assertEqual(request.call_args.kwargs["api_base"], "https://fixed.example/v1")
        self.assertEqual(request.call_args.kwargs["api_key"], "fixture-only")
        self.assertEqual(request.call_args.kwargs["json"]["operation_id"], failed["operation_id"])
        self.assertEqual(self.rows()[0]["state"], "delivered")

    def test_worker_cannot_send_same_event_concurrently(self):
        self.enqueue()
        started, finish = threading.Event(), threading.Event()
        def send(*args, **kwargs):
            started.set()
            self.assertTrue(finish.wait(10))
            return {"code": 200}
        with patch.object(butler, "_request", side_effect=send) as request, ThreadPoolExecutor(2) as pool:
            first = pool.submit(self.reports().dispatch_once)
            self.assertTrue(started.wait(10))
            second = pool.submit(self.reports().dispatch_once)
            try:
                self.assertFalse(second.result(timeout=10))
            finally:
                finish.set()
            self.assertTrue(first.result(timeout=10))
        self.assertEqual(request.call_count, 1)

    def test_expired_lease_is_recovered_and_stale_completion_is_fenced(self):
        reports = self.reports()
        self.enqueue()
        original = reports._claim_next()
        with record_store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres_store.qualified(record_store.EMAIL_USAGE_REPORTS.name)} SET lease_until = NOW() - INTERVAL '1 second'")
        takeover = reports._claim_next()
        self.assertEqual(original["operation_id"], takeover["operation_id"])
        self.assertNotEqual(original["lease_owner"], takeover["lease_owner"])
        reports._finish(original, delivered=True)
        self.assertEqual(self.rows()[0]["state"], "sending")
        reports._finish(takeover, delivered=True)
        self.assertEqual(self.rows()[0]["state"], "delivered")

    def test_definite_auth_failure_blocks_without_leaking_details(self):
        self.enqueue()
        error = butler.EmailButlerClientError("secret-key https://bad.test otp=123456")
        error.status_code = 401
        with patch.object(butler, "_request", side_effect=error):
            self.reports().dispatch_once()
        self.assertEqual(self.rows()[0]["state"], "blocked")
        status = self.reports().worker_status()
        self.assertEqual(status["counts"]["blocked"], 1)
        for private in (ADDRESS, "fixed.example", "secret-key", "123456", "USAGE_FIXTURE_KEY"):
            self.assertNotIn(private, str(status))

    def test_historical_hme_release_enqueues_without_http(self):
        self.reports()
        with patch.dict(butler._CONTEXT_CACHE, {}, clear=True), patch.object(butler, "_request") as request:
            butler.release_account(ADDRESS, status="used", note="otp=123456")
        request.assert_not_called()
        self.assertEqual(self.rows()[0]["result"], "ok")
        self.assertNotIn("123456", str(self.rows()))

    def test_legacy_allocation_and_report_share_transaction_and_success_is_final(self):
        reports = self.reports()
        allocation_id = record_store.insert_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, {
            "address": ADDRESS, "address_norm": ADDRESS, "parent_address": "parent@icloud.com",
            "source": "icloud_hide", "parent_id": 1, "parent_kind": "icloud_hme", "inbox_profile_id": self.profile_id,
            "state": "reserved", "strategy": "plus_tag", "tag": "fixture",
            "acquisition_id": "legacy-acquisition", "owner_kind": "registration_root", "owner_id": "legacy-owner"})
        with patch.object(reports, "enqueue", side_effect=RuntimeError("queue unavailable")):
            with self.assertRaisesRegex(RuntimeError, "queue unavailable"):
                reports.record_legacy_result(ADDRESS, status="used", source="icloud_hide")
        self.assertEqual(record_store.get_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, allocation_id)["state"], "reserved")
        self.assertTrue(reports.record_legacy_result(ADDRESS, status="used", source="icloud_hide"))
        self.assertTrue(reports.record_legacy_result(ADDRESS, status="retired", source="icloud_hide"))
        self.assertEqual(record_store.get_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, allocation_id)["state"], "used")
        self.assertEqual(len(self.rows()), 1)

    def test_legacy_ordinary_lease_remains_one_shot_without_outbox(self):
        self.reports()
        account = butler.EmailButlerAccount("legacy@example.test", "legacy-id", provider="outlook",
            api_base="https://fixed.example/v1", api_key="fixture-only")
        with patch.dict(butler._CONTEXT_CACHE, {account.email: account}, clear=True), patch.object(
                butler, "_request", side_effect=butler.EmailButlerClientError("offline")) as request:
            with self.assertRaises(butler.EmailButlerClientError):
                butler.release_account(account.email, status="failed")
        request.assert_called_once()
        self.assertEqual(self.rows(), [])

    def test_management_helpers_fail_closed_without_network(self):
        with patch.object(hme, "_request") as request:
            for action in (hme.sync_aliases, hme.create_address):
                with self.assertRaisesRegex(hme.ICloudHMEError, "email_management_retired"):
                    action()
        request.assert_not_called()

    def test_local_result_rolls_back_if_enqueue_fails_and_late_failure_is_ignored(self):
        from core.local_email_inventory import record_outcome
        reports = self.reports()
        pool_id = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {**self.row, "status": "reserved"})
        with patch.object(reports, "enqueue", side_effect=RuntimeError("queue unavailable")):
            with self.assertRaisesRegex(RuntimeError, "queue unavailable"):
                record_outcome(ADDRESS, source="icloud_hide", status="used")
        self.assertEqual(record_store.get_row(record_store.ICLOUD_HIDE_POOL, pool_id)["status"], "reserved")
        for status in ("request_unknown", "unknown", "available"):
            self.assertTrue(record_outcome(ADDRESS, source="icloud_hide", status=status))
        self.assertEqual(self.rows(), [])
        self.assertTrue(record_outcome(ADDRESS, source="icloud_hide", status="used"))
        self.assertTrue(record_outcome(ADDRESS, source="icloud_hide", status="used"))
        self.assertTrue(record_outcome(ADDRESS, source="icloud_hide", status="failed"))
        self.assertEqual(record_store.get_row(record_store.ICLOUD_HIDE_POOL, pool_id)["status"], "used")
        self.assertEqual(len(self.rows()), 1)

    def test_persisted_profile_without_current_secret_still_enqueues_local_success(self):
        self.reports()
        os.environ.pop("USAGE_FIXTURE_KEY")
        with patch.dict(butler._CONTEXT_CACHE, {}, clear=True), patch.object(butler, "_request") as request:
            butler.release_account(ADDRESS, status="used")
        request.assert_not_called()
        self.assertEqual(self.rows()[0]["state"], "pending")

    def test_inflight_success_prevents_concurrent_local_failure_downgrade(self):
        from core.local_email_inventory import record_outcome
        reports = self.reports()
        pool_id = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {**self.row, "status": "used"})
        success_ready, commit_success, checked = threading.Event(), threading.Event(), threading.Event()
        def success():
            with record_store.transaction() as conn, conn.cursor() as cur:
                reports.enqueue(ADDRESS, source="icloud_hide", status="used", row=self.row, cursor=cur)
                success_ready.set()
                self.assertTrue(commit_success.wait(10))
        original = reports.has_success
        def checked_success(*args, **kwargs):
            result = original(*args, **kwargs)
            checked.set()
            return result
        with ThreadPoolExecutor(2) as pool:
            pending_success = pool.submit(success)
            self.assertTrue(success_ready.wait(10))
            with patch.object(reports, "has_success", side_effect=checked_success):
                pending_failure = pool.submit(record_outcome, ADDRESS, source="icloud_hide", status="failed")
                # A correct success guard waits for the in-flight transaction.
                # An unlocked read returns False, after which enqueue waits.
                checked.wait(.2)
                commit_success.set()
                pending_success.result(timeout=10)
                self.assertTrue(pending_failure.result(timeout=10))
        self.assertEqual(record_store.get_row(record_store.ICLOUD_HIDE_POOL, pool_id)["status"], "used")
