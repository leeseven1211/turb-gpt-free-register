# -*- coding: utf-8 -*-
"""地址账本、固定路由版本和认证执行 fence 的 PostgreSQL 隔离回归。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import os
import threading

from core.storage import postgres as postgres_store, records as record_store
from core.storage.email import address_allocations as allocations
from tests.support_pg import PostgresTestCase


class EmailAddressAllocationTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.profile = allocations.create_inbox_profile(
            inbox_key="test-inbox", connector="forward_imap", credential_ref="env:TEST_PROFILE_PASSWORD",
            inbox_locator={"host": "imap.example.test", "username": "inbox@example.test"},
        )
        self.parent_id = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "parent@icloud.test", "status": "used", "account_id": "apple-test", "remote_active": True,
        })

    def allocate(self, intent="root-1", **kwargs):
        arguments = dict(source="icloud_hide", acquisition_id=intent, owner_kind="registration_root", owner_id=intent,
                         inbox_profile_id=self.profile["id"])
        arguments.update(kwargs)
        return allocations.allocate_address(**arguments)

    def test_defaults_issue_three_unique_addresses_then_can_increase_limit(self):
        issued = [self.allocate(f"root-{number}") for number in range(3)]
        self.assertEqual(len({row["address"] for row in issued}), 3)
        for row in issued:
            self.assertRegex(row["address"], r"^parent\+[a-z0-9]{6}@icloud\.test$")
        self.assertIsNone(self.allocate("fourth"))
        additional = self.allocate("fourth", max_children=4)
        self.assertIsNotNone(additional)
        self.assertEqual(allocations.allocation_summary()["total"], 4)
        self.assertEqual(record_store.get_row(record_store.ICLOUD_HIDE_POOL, self.parent_id)["status"], "used")

    def test_parent_override_and_terminal_addresses_keep_cumulative_quota(self):
        allocations.configure_parent("icloud_hide", self.parent_id, max_children=2)
        first = self.allocate("first")
        second = self.allocate("second")
        allocations.mark_allocation_state(first["id"], "replaced", data={"remote_result_unknown": True})
        allocations.mark_allocation_state(second["id"], "retired")
        self.assertIsNone(self.allocate("third", max_children=20))
        allocations.configure_parent("icloud_hide", self.parent_id, max_children=3)
        self.assertIsNotNone(self.allocate("third"))
        self.assertEqual(self.allocate("first")["id"], first["id"])

    def test_same_acquisition_cross_thread_and_restart_return_same_binding(self):
        with ThreadPoolExecutor(max_workers=6) as executor:
            rows = list(executor.map(lambda _: self.allocate("same-root"), range(6)))
        self.assertEqual(len({row["id"] for row in rows}), 1)
        record_store.reset_ready()
        self.assertEqual(self.allocate("same-root")["id"], rows[0]["id"])
        self.assertEqual(allocations.allocation_summary()["total"], 1)

    def test_distinct_acquisitions_do_not_overrun_parent_cap(self):
        with ThreadPoolExecutor(max_workers=6) as executor:
            rows = list(executor.map(lambda number: self.allocate(f"parallel-{number}"), range(6)))
        issued = [row for row in rows if row]
        self.assertEqual(len(issued), 3)
        self.assertEqual(len({row["address"] for row in issued}), 3)

    def test_email_invalid_parent_blocks_new_addresses_but_keeps_original_identity(self):
        original = self.allocate("original-identity")
        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, self.parent_id, {
            "email_invalid": True, "email_invalid_reason": "已确认无法收件",
        })

        self.assertIsNone(self.allocate("new-identity"))
        resumed = self.allocate("original-identity")
        self.assertEqual(resumed["id"], original["id"])
        self.assertEqual(resumed["state"], "reserved")
        self.assertEqual(record_store.get_row(record_store.ICLOUD_HIDE_POOL, self.parent_id)["status"], "used")

        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, self.parent_id, {"email_invalid": False})
        self.assertIsNotNone(self.allocate("new-identity"))

    def test_first_parent_is_filled_before_next_and_filters_are_respected(self):
        other = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "second@icloud.test", "status": "replaced", "account_id": "second-apple",
        })
        rows = [self.allocate(str(number)) for number in range(4)]
        self.assertEqual([row["parent_id"] for row in rows], [self.parent_id] * 3 + [other])
        selected = self.allocate("filtered", account_ids=["second-apple"])
        self.assertEqual(selected["parent_id"], other)
        self.assertIsNone(self.allocate("empty-selection", parent_ids=[]))

    def test_unhealthy_or_explicit_disabled_parent_is_not_reactivated(self):
        for values in ({"status": "disabled"}, {"status": "failed"}, {"remote_active": False},
                       {"archived": True}, {"disabled_reason": "remote_inactive"}):
            with self.subTest(values=values):
                parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
                    "email": f"disabled-{record_store.count_rows(record_store.ICLOUD_HIDE_POOL)}@icloud.test",
                    "status": "available", **values,
                })
                self.assertIsNone(self.allocate(f"unhealthy-{parent}", parent_id=parent))
        allocations.configure_parent("icloud_hide", self.parent_id, enabled=False)
        self.assertIsNone(self.allocate("disabled-policy"))

    def test_address_collision_in_archived_account_and_pool_is_not_reused(self):
        record_store.insert_row(record_store.ACCOUNTS, {"email": "parent+aaaaaa@icloud.test", "archived": True})
        record_store.insert_row(record_store.OUTLOOK_POOL, {"email": "parent+bbbbbb@icloud.test", "status": "used"})
        with patch.object(allocations, "_new_address", side_effect=[
            ("parent+aaaaaa@icloud.test", "aaaaaa"), ("parent+bbbbbb@icloud.test", "bbbbbb"),
            ("parent+cccccc@icloud.test", "cccccc"),
        ]):
            row = self.allocate("collision")
        self.assertEqual(row["address"], "parent+cccccc@icloud.test")
        self.assertTrue(allocations.address_is_taken("PARENT+CCCCCC@ICLOUD.TEST"))

    def test_transaction_binding_rolls_back_job_and_allocation_together(self):
        job_id = record_store.insert_row(record_store.JOBS, {"job_uuid": "test-job", "batch_id": "test-batch", "status": "queued"})
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with record_store.transaction() as conn:
                row = self.allocate("rollback-root", job_id=job_id, conn=conn)
                self.assertEqual(record_store.get_row(record_store.JOBS, job_id, conn=conn)["email_address_id"], row["id"])
                raise RuntimeError("rollback")
        self.assertIsNone(allocations.find_allocation(acquisition_id="rollback-root"))
        self.assertIsNone(record_store.get_row(record_store.JOBS, job_id).get("email"))
        row = self.allocate("rollback-root", job_id=job_id)
        claims = record_store.list_rows(record_store.REGISTRATION_BATCH_EMAIL_CLAIMS)
        self.assertEqual(claims[0]["email"], row["address"])
        from core import db
        self.assertTrue(db.claim_registration_batch_email("test-batch", row["address"], job_id=job_id))
        other_job = record_store.insert_row(record_store.JOBS, {"job_uuid": "other-job", "batch_id": "test-batch", "status": "queued"})
        self.assertFalse(db.claim_registration_batch_email("test-batch", row["address"], job_id=other_job))

    def test_attempt_binding_uses_same_connection(self):
        from core.storage import registration
        registration.init()
        job_id = record_store.insert_row(record_store.JOBS, {"job_uuid": "attempt-job", "status": "queued"})
        attempt = registration.ensure_attempt_for_job(job_id)
        row = self.allocate("attempt-root", job_id=job_id, attempt_id=attempt["id"])
        saved = registration.get_attempt(attempt["id"])
        self.assertEqual(saved["email"], row["address"])
        self.assertEqual(saved["data"]["email_address_id"], row["id"])
        self.assertEqual(saved["email_snapshot"], row["address"])

    def test_binding_keeps_original_profile_when_new_revision_appears(self):
        original = self.allocate("versioned")
        newer = allocations.create_inbox_profile(inbox_key="test-inbox", connector="forward_imap",
            credential_ref="env:TEST_PROFILE_PASSWORD_V2", inbox_locator={"host": "imap.example.test", "username": "inbox@example.test"})
        self.assertEqual(newer["revision"], 2)
        self.assertEqual(self.allocate("versioned", inbox_profile_id=newer["id"])["inbox_profile_id"], original["inbox_profile_id"])
        self.assertEqual(allocations.get_inbox_profile(original["inbox_profile_id"])["credential_ref"], "env:TEST_PROFILE_PASSWORD")
        allocations.configure_parent("icloud_hide", self.parent_id, inbox_profile_id=newer["id"])
        allocations.retire_inbox_profile(newer["id"])
        self.assertIsNone(self.allocate("retired-profile", inbox_profile_id=newer["id"]))
        self.assertEqual(allocations.find_allocation(address=original["address"].upper())["id"], original["id"])

    def test_profile_factory_is_lazy_and_uses_locked_parent(self):
        outlook_id = record_store.insert_row(record_store.OUTLOOK_POOL, {"email": "outlook@example.test", "status": "used", "client_id": "test-client", "refresh_token": "test-refresh"})
        invoked = []
        def factory(parent, conn):
            invoked.append(parent["id"])
            return allocations.create_inbox_profile(inbox_key=f"outlook:{parent['id']}", connector="outlook",
                credential_ref=f"pool:outlook:{parent['id']}", inbox_locator={"parent_id": parent["id"]}, conn=conn)
        row = allocations.allocate_address(source="outlook", acquisition_id="outlook-root", owner_kind="registration_root",
            owner_id="outlook-root", profile_factory=factory)
        self.assertEqual(invoked, [outlook_id])
        self.assertEqual(allocations.get_inbox_profile(row["inbox_profile_id"])["credential_ref"], f"pool:outlook:{outlook_id}")

    def test_new_sibling_and_mother_keep_first_profile_after_global_inbox_changes(self):
        original = self.allocate("first-profile")
        newer = allocations.create_inbox_profile(inbox_key="other-inbox", connector="forward_imap",
            credential_ref="env:TEST_PROFILE_PASSWORD_NEW", inbox_locator={"host": "imap.example.test", "username": "other@example.test"})
        sibling = self.allocate("second-profile", inbox_profile_id=newer["id"])
        self.assertEqual(sibling["inbox_profile_id"], original["inbox_profile_id"])
        self.assertEqual(allocations.get_parent("icloud_hide", self.parent_id)["derivation_policy"]["inbox_profile_id"], self.profile["id"])
        from core.email import derivation as email_derivation
        with patch.dict(os.environ, {"env:TEST_PROFILE_PASSWORD": "test-old-password", "env:TEST_PROFILE_PASSWORD_NEW": "test-new-password"}):
            mother_route = email_derivation.inbox_profile_for_address("parent@icloud.test")
        self.assertEqual(mother_route["id"], self.profile["id"])
        self.assertEqual(mother_route["username"], "inbox@example.test")
        self.assertTrue(mother_route["strict_family"])

    def test_deletion_and_first_derivation_cannot_leave_orphaned_child(self):
        from core import db
        before_delete, release_delete, allocation_done = threading.Event(), threading.Event(), threading.Event()
        original_delete = record_store.delete_rows_where_returning
        def paused_delete(*args, **kwargs):
            before_delete.set()
            if not release_delete.wait(5):
                raise RuntimeError("测试删除等待超时")
            return original_delete(*args, **kwargs)
        def allocate_while_deleting():
            try:
                return self.allocate("racing-delete")
            finally:
                allocation_done.set()
        with patch.object(record_store, "delete_rows_where_returning", side_effect=paused_delete), ThreadPoolExecutor(max_workers=2) as executor:
            deleting = executor.submit(db.delete_icloud_hide_email, "parent@icloud.test")
            self.assertTrue(before_delete.wait(5))
            allocating = executor.submit(allocate_while_deleting)
            try:
                self.assertFalse(allocation_done.wait(.2), "删除检查完成后必须继续持有母记录锁")
            finally:
                release_delete.set()
            self.assertTrue(deleting.result(timeout=5))
            self.assertIsNone(allocating.result(timeout=5))
        self.assertIsNone(allocations.get_parent("icloud_hide", self.parent_id))
        self.assertEqual(allocations.allocation_summary()["total"], 0)

    def test_deleting_case_duplicate_parents_preserves_only_referenced_recovery(self):
        from core import db
        duplicate_id = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "PARENT@icloud.test", "status": "used", "account_id": "test-apple",
        })
        child = self.allocate("case-duplicate", parent_id=duplicate_id)
        self.assertTrue(db.delete_icloud_hide_email("parent@icloud.test"))
        self.assertIsNone(allocations.get_parent("icloud_hide", self.parent_id))
        preserved = allocations.get_parent("icloud_hide", duplicate_id)
        self.assertTrue(preserved["archived"])
        self.assertEqual(allocations.get_allocation(child["id"])["parent_id"], duplicate_id)

    def test_profiles_reject_secret_copies_and_remain_idempotent(self):
        same = allocations.create_inbox_profile(inbox_key="test-inbox", connector="forward_imap",
            credential_ref="env:TEST_PROFILE_PASSWORD", inbox_locator={"host": "imap.example.test", "username": "inbox@example.test"})
        self.assertEqual(same["id"], self.profile["id"])
        with self.assertRaises(ValueError):
            allocations.create_inbox_profile(inbox_key="bad", connector="imap", credential_ref="env:TEST",
                inbox_locator={"password": "should-not-be-stored"})
        self.allocate("first-owner", acquisition_id="id-1", owner_id="owner-1")
        with self.assertRaises(ValueError):
            self.allocate("other-owner", acquisition_id="id-1", owner_id="owner-2")


class EmailOtpRequestTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.address = "parent+abcdef@icloud.test"

    def acquire(self, owner="root-1", **kwargs):
        arguments = dict(address=self.address, owner_kind="registration_root", owner_id=owner)
        arguments.update(kwargs)
        return allocations.acquire_otp_request(**arguments)

    def expire(self, request):
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(timespec="microseconds")
        record_store.patch_row(record_store.EMAIL_OTP_REQUESTS, request["id"], {"lease_expires_at": past})

    @staticmethod
    def credentials(request):
        return {"execution_token": request["execution_token"], "fence": request["fence"]}

    def test_complete_address_isolation_and_cross_process_style_contention(self):
        original = self.acquire()
        with self.assertRaises(allocations.OtpLeaseBusy):
            self.acquire("other-root")
        other = self.acquire("other-root", address="parent+ghijkl@icloud.test")
        self.assertNotEqual(original["id"], other["id"])
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.acquire, f"parallel-{number}", address="parallel@example.test") for number in range(2)]
        results, busy = [], 0
        for future in futures:
            try:
                results.append(future.result())
            except allocations.OtpLeaseBusy:
                busy += 1
        self.assertEqual((len(results), busy), (1, 1))

    def test_unknown_submission_survives_restart_and_reacquire_without_resend(self):
        original = self.acquire(challenge_id="original-session")
        credentials = self.credentials(original)
        allocations.update_otp_send(original["id"], send_state="request_unknown", **credentials)
        allocations.record_otp_candidate(original["id"], message_key="inbox:uidvalidity:123", evidence={"recipient_exact": True}, **credentials)
        allocations.record_otp_submission(original["id"], submission_state="result_unknown", **credentials)
        self.expire(original)
        record_store.reset_ready()
        restored = self.acquire(challenge_id="original-session", new_generation=False)
        self.assertEqual(restored["id"], original["id"])
        self.assertGreater(restored["fence"], original["fence"])
        self.assertEqual(restored["candidate_message_key"], "inbox:uidvalidity:123")
        self.assertEqual(restored["submission_state"], "result_unknown")
        self.assertEqual(restored["send_generation"], 1)
        with self.assertRaises(allocations.StaleOtpFence):
            allocations.record_otp_submission(original["id"], submission_state="confirmed", **credentials)

    def test_resend_advances_generation_and_preserves_previous_facts(self):
        original = self.acquire(challenge_id="session-1")
        allocations.record_otp_candidate(original["id"], message_key="mail:one", **self.credentials(original))
        resent = self.acquire(challenge_id="session-2", execution_token=original["execution_token"])
        self.assertEqual(resent["send_generation"], 2)
        self.assertEqual(allocations.get_otp_request(original["id"])["state"], "superseded")
        self.assertEqual(allocations.get_otp_request(original["id"])["candidate_message_key"], "mail:one")
        self.assertIsNone(resent.get("candidate_message_key"))
        with self.assertRaises(allocations.StaleOtpFence):
            allocations.record_otp_candidate(original["id"], message_key="late", **self.credentials(original))

    def test_candidate_read_is_not_consumption_and_confirmation_releases_lease(self):
        request = self.acquire()
        credentials = self.credentials(request)
        offered = allocations.record_otp_candidate(request["id"], message_key="mail:one", **credentials)
        self.assertEqual(offered["submission_state"], "not_started")
        allocations.record_otp_submission(request["id"], submission_state="offered", **credentials)
        self.assertEqual(allocations.find_active_otp_request(self.address)["id"], request["id"])
        allocations.record_otp_submission(request["id"], submission_state="confirmed", **credentials)
        self.assertIsNone(allocations.find_active_otp_request(self.address))
        next_request = self.acquire("new-intent")
        self.assertGreater(next_request["fence"], request["fence"])

    def test_expired_owner_does_not_block_other_owner_or_accept_late_writes(self):
        original = self.acquire()
        self.expire(original)
        with self.assertRaises(allocations.StaleOtpFence):
            allocations.renew_otp_lease(original["id"], **self.credentials(original))
        replacement = self.acquire("replacement-owner")
        self.assertGreater(replacement["fence"], original["fence"])
        self.assertEqual(allocations.get_otp_request(original["id"])["state"], "superseded")

    def test_otp_facts_do_not_store_plain_code_or_mail_body(self):
        request = self.acquire()
        for evidence in ({"code": "123456"}, {"raw_message": "private message"}, {"nested": {"password": "private"}}):
            with self.assertRaises(ValueError):
                allocations.record_otp_candidate(request["id"], message_key="mail:one", evidence=evidence, **self.credentials(request))
