"""Database-lock regressions for nested account metadata, using synthetic data."""
from __future__ import annotations

import json
import threading
import time
from unittest.mock import patch

from core import db, record_store as rs
from tests.support_pg import PostgresTestCase


class AccountMetadataConcurrencyTests(PostgresTestCase):
    def setUp(self):
        rs.init()

    def _run_behind_committed_metadata(self, update):
        email = "metadata-concurrency@example.test"
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": email,
            "totp_secret": "synthetic-old-secret",
            "extra_json": json.dumps({"totp_pending_secret": "synthetic-pending"}),
        })
        outcomes, errors = [], []

        def worker():
            try:
                outcomes.append(update(email))
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker, daemon=True)
        observed_wait = False
        try:
            with patch.object(db.compat_export, "schedule"):
                with rs.transaction() as blocker, blocker.cursor() as cur:
                    cur.execute("SELECT pg_backend_pid() AS pid")
                    blocker_pid = cur.fetchone()["pid"]
                    cur.execute(
                        f"SELECT id FROM {rs._qualified(rs.ACCOUNTS)} WHERE id=%s FOR UPDATE",
                        (account_id,),
                    )
                    thread.start()
                    # Both implementations eventually block on this row. The
                    # old implementation reads stale JSON before its UPDATE;
                    # the new one waits before reading any account metadata.
                    with rs._connect() as observer, observer.cursor() as poll:
                        deadline = time.monotonic() + 8
                        while time.monotonic() < deadline:
                            poll.execute(
                                "SELECT count(*) AS n FROM pg_stat_activity "
                                "WHERE datname=current_database() "
                                "AND %s=ANY(pg_blocking_pids(pid))",
                                (blocker_pid,),
                            )
                            if poll.fetchone()["n"]:
                                observed_wait = True
                                break
                            time.sleep(0.01)
                    # A competing transaction commits a previously unknown
                    # checkpoint while the public business updater is waiting.
                    rs.patch_row(rs.ACCOUNTS, account_id, {
                        "extra_json": json.dumps({
                            "totp_pending_secret": "synthetic-pending",
                            "concurrent_checkpoint": {"confirmed": True},
                        }),
                    }, conn=blocker)
                thread.join(timeout=10)
        finally:
            if thread.ident is not None:
                thread.join(timeout=10)
        self.assertTrue(observed_wait, "business updater never reached the locked row")
        self.assertFalse(thread.is_alive(), "business updater did not finish")
        self.assertEqual(errors, [])
        self.assertEqual(outcomes, [True])
        saved = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertEqual(
            json.loads(saved["extra_json"])["concurrent_checkpoint"],
            {"confirmed": True},
        )
        return saved

    def test_password_preserves_concurrently_committed_checkpoint(self):
        self._run_behind_committed_metadata(lambda email: db.update_account_login_password(email, "synthetic-password"))

    def test_capability_preserves_concurrently_committed_checkpoint(self):
        self._run_behind_committed_metadata(lambda email: db.update_account_password_capability(email, eligible=True))

    def test_totp_confirmation_preserves_concurrently_committed_checkpoint(self):
        self._run_behind_committed_metadata(lambda email: db.update_account_totp_secret(email, "synthetic-totp", setup_pending=False))

    def test_totp_staging_preserves_concurrently_committed_checkpoint(self):
        self._run_behind_committed_metadata(lambda email: db.stage_account_totp_secret(email, "synthetic-staged"))

    def test_totp_disable_preserves_concurrently_committed_checkpoint(self):
        self._run_behind_committed_metadata(db.mark_account_totp_disabled_for_rotation)

    def test_totp_clear_preserves_concurrently_committed_checkpoint(self):
        self._run_behind_committed_metadata(db.clear_account_totp_pending)

    def test_twofa_status_preserves_concurrently_committed_checkpoint(self):
        self._run_behind_committed_metadata(lambda email: db.update_account_twofa_status(email, "success", "confirmed"))

    def test_session_preserves_concurrently_committed_checkpoint(self):
        self._run_behind_committed_metadata(lambda email: db.update_account_session(email, "synthetic-session"))

    def test_account_insert_update_merges_explicit_extra_keys(self):
        account_id = db.insert_account(email="insert-metadata@example.test", access_token="synthetic-token", extra={"preserve": 1})
        saved_id = db.insert_account(email="insert-metadata@example.test", access_token="synthetic-token2", extra={"new": 2})
        self.assertEqual(saved_id, account_id)
        self.assertEqual(json.loads(rs.get_row(rs.ACCOUNTS, account_id)["extra_json"]), {"preserve": 1, "new": 2})

    def test_totp_pool_failure_rolls_back_account_and_metadata(self):
        email = "atomic-totp@example.test"
        account_id = rs.insert_row(rs.ACCOUNTS, {"email": email, "totp_secret": "synthetic-old"})
        pool_id = rs.insert_row(rs.OUTLOOK_POOL, {"email": email, "totp_secret": "synthetic-old"})
        original = rs.patch_row

        def fail_pool(table, *args, **kwargs):
            if table is rs.OUTLOOK_POOL:
                raise RuntimeError("synthetic pool failure")
            return original(table, *args, **kwargs)

        with patch.object(rs, "patch_row", side_effect=fail_pool), patch.object(db.compat_export, "schedule") as export:
            with self.assertRaisesRegex(RuntimeError, "synthetic pool failure"):
                db.update_account_totp_secret(email, "synthetic-new", setup_pending=True)
        export.assert_not_called()
        self.assertEqual(rs.get_row(rs.ACCOUNTS, account_id)["totp_secret"], "synthetic-old")
        self.assertNotIn("extra_json", rs.get_row(rs.ACCOUNTS, account_id))
        self.assertEqual(rs.get_row(rs.OUTLOOK_POOL, pool_id)["totp_secret"], "synthetic-old")

    def test_upsert_does_not_reset_unrelated_derived_state(self):
        email = "derived-upsert@example.test"
        account_id = rs.insert_row(rs.ACCOUNTS, {"email": email, "account_status": "deactivated"})
        self.assertEqual(rs.upsert_row_by(rs.ACCOUNTS, "email", {"email": email, "note": "new"}), account_id)
        self.assertEqual(rs.count_rows(rs.ACCOUNTS, where="deactivated"), 1)
        rs.upsert_row_by(rs.ACCOUNTS, "email", {"email": email, "account_status": "active"})
        self.assertEqual(rs.count_rows(rs.ACCOUNTS, where="deactivated"), 0)

    def test_top_level_generated_fields_are_never_persisted(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {"email": "generated-input@example.test", "account_has_password": True})
        rs.patch_row(rs.ACCOUNTS, account_id, {"account_totp_enabled": True})
        saved = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertNotIn("account_has_password", saved)
        self.assertNotIn("account_totp_enabled", saved)

    def test_sync_reads_current_account_even_when_legacy_list_is_incomplete(self):
        from core import sub2api_sync

        email = "sync-existing@example.test"
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": email,
            "account_status": "deactivated",
            "extra_json": json.dumps({"account_password": "synthetic-password", "local_checkpoint": True}),
        })
        # A capped or stale list used to misclassify an existing account as
        # new, replacing all its metadata via upsert. It is no longer a write
        # precondition; the current locked row is authoritative.
        with patch.object(sub2api_sync.db, "list_accounts", return_value=[]):
            result = sub2api_sync.sync_sub2api_records([{
                "id": 51,
                "credentials": {"email": email, "access_token": "synthetic-imported-token"},
            }], sync_codex=False)
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["accounts_created"], 0)
        self.assertEqual(result["accounts_updated"], 1)
        metadata = json.loads(rs.get_row(rs.ACCOUNTS, account_id)["extra_json"])
        self.assertEqual(metadata["account_password"], "synthetic-password")
        self.assertTrue(metadata["local_checkpoint"])
        self.assertEqual(rs.count_rows(rs.ACCOUNTS, where="deactivated"), 1)

    def test_identity_repair_never_reuses_previously_allocated_ids(self):
        first = rs.insert_row(rs.JOBS, {"job_uuid": "identity-first"})
        second = rs.insert_row(rs.JOBS, {"job_uuid": "identity-second"})
        rs.delete_rows(rs.JOBS, [second])
        self.assertEqual(rs.sync_identity(rs.JOBS), first)
        third = rs.insert_row(rs.JOBS, {"job_uuid": "identity-third"})
        self.assertGreater(third, second)

    def test_for_update_requires_a_caller_owned_transaction(self):
        with self.assertRaisesRegex(ValueError, "事务连接"):
            rs.get_row_by(rs.ACCOUNTS, "email", "synthetic@example.test", for_update=True)

    def test_token_metadata_update_rechecks_current_token_at_write(self):
        from core import chatgpt_plan

        account_id = rs.insert_row(rs.ACCOUNTS, {"email": "metadata-token@example.test", "access_token": "synthetic-old"})
        original_read = rs.get_row

        def read_then_rotate(*args, **kwargs):
            stale = original_read(*args, **kwargs)
            rs.patch_row(rs.ACCOUNTS, account_id, {"access_token": "synthetic-new", "token_expires_at": "new-expiry"})
            return stale

        with patch.object(rs, "get_row", side_effect=read_then_rotate), patch.object(
            chatgpt_plan, "token_claims", return_value={"token_expires_at": "old-expiry", "token_expired": True},
        ), patch.object(db.compat_export, "schedule") as export:
            self.assertFalse(db.update_account_token_metadata(account_id, "synthetic-old"))
        export.assert_not_called()
        saved = original_read(rs.ACCOUNTS, account_id)
        self.assertEqual(saved["access_token"], "synthetic-new")
        self.assertEqual(saved["token_expires_at"], "new-expiry")
