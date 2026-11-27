"""已确认密码变更的私有收尾检查点与协议会话事务测试。"""
from __future__ import annotations

import json
import os
import uuid
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.storage import postgres as pg, records
from core.storage.accounts import password_recovery as store
from core.storage.accounts import protocol_sessions
from core.storage.operations import store as operations
from tests.support_pg import PostgresTestCase


def matching_session(email: str, token: str = "fresh-token") -> dict:
    return {
        "accessToken": token,
        "user": {"email": email, "id": "fixture-user"},
        "account": {"id": "fixture-account"},
        "expires": "2099-01-01",
    }


def protocol_session() -> dict:
    return {
        "cookies": [{
            "name": "__Secure-next-auth.session-token",
            "value": "fixture-cookie",
            "domain": "chatgpt.com",
            "path": "/",
            "secure": True,
            "expires": None,
        }],
        "device_id": "fixture-device",
        "browser_profile": {
            "screen_width": 1920,
            "screen_height": 1080,
            "device_pixel_ratio": 1,
            "hardware_concurrency": 8,
            "device_memory": 8,
            "js_heap_size_limit": 4096000000,
        },
        "user_id": "fixture-user",
        "chatgpt_account_id": "fixture-account",
    }


class PasswordChangeCompletionStoreTests(PostgresTestCase):
    def setUp(self):
        key = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        key.start()
        self.addCleanup(key.stop)
        operations.init()
        self.email = "change@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email,
            "access_token": "old-token",
            "password": "old-password",
            "extra_json": json.dumps({"account_password": "old-password", "preserved": 42}),
            "account_status": "active",
        })
        self.owner = self.make_owner()

    def make_owner(self, resource_family="openai_interactive", task_id=None):
        execution_id = uuid.uuid4().hex
        source_id = uuid.uuid4().hex
        with pg.connect() as conn, conn.cursor() as cur:
            if task_id is None:
                cur.execute(
                    f"INSERT INTO {pg.qualified('operation_tasks')} "
                    "(task_uuid,source_system,source_id,task_type,target_type,account_id,email_snapshot,"
                    "requested_action,status,data) VALUES (%s,'webui_runtime',%s,'password_change',"
                    "'account',%s,%s,'password_change','running',%s::jsonb) RETURNING id",
                    (uuid.uuid4().hex, source_id, self.account_id, self.email, "{}"),
                )
                task_id = cur.fetchone()[0]
            cur.execute(
                f"SELECT COALESCE(MAX(run_no), 0) + 1 FROM {pg.qualified('operation_runs')} WHERE task_id=%s",
                (task_id,),
            )
            run_no = cur.fetchone()[0]
            cur.execute(
                f"INSERT INTO {pg.qualified('operation_runs')} "
                "(run_uuid,task_id,run_no,source_system,source_id,status,execution_id,account_id,resource_family) "
                "VALUES (%s,%s,%s,'webui_runtime',%s,'running',%s,%s,%s) RETURNING id",
                (uuid.uuid4().hex, task_id, run_no, source_id, execution_id, self.account_id, resource_family),
            )
            run_id = cur.fetchone()[0]
        lease = operations.acquire_account_lease(
            account_id=self.account_id,
            run_id=run_id,
            resource_family=resource_family,
        )
        return {
            "email": self.email,
            "account_id": self.account_id,
            "purpose": "manual",
            "operation_run_id": run_id,
            "operation_execution_id": execution_id,
            "operation_lease_token": lease,
            "attempt_id": None,
            "registration_run_id": None,
            "registration_execution_id": None,
        }

    def end_owner(self):
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {pg.qualified('operation_runs')} SET status='failed' WHERE id=%s",
                (self.owner["operation_run_id"],),
            )
            cur.execute(
                f"DELETE FROM {pg.qualified('account_operation_leases')} WHERE run_id=%s",
                (self.owner["operation_run_id"],),
            )

    def prepare_confirmed_pending(self):
        checkpoint = store.prepare_password_recovery(
            **self.owner,
            candidate_factory=lambda: "new-password",
        )
        checkpoint = store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="started",
        )
        return store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="confirmed",
            confirmation="password_change_response",
            completion_pending=True,
        )

    def test_confirmed_pending_can_be_taken_over_but_pending_resume_stays_pending_only(self):
        checkpoint = self.prepare_confirmed_pending()
        self.assertTrue(checkpoint.completion_pending)
        self.assertIsNone(store.resume_password_recovery(**self.owner))

        self.end_owner()
        self.owner = self.make_owner()
        resumed = store.resume_manual_password_change(**self.owner)

        self.assertEqual(checkpoint.recovery_id, resumed.recovery_id)
        self.assertEqual("new-password", resumed.password)
        self.assertTrue(resumed.completion_pending)
        self.assertNotEqual(checkpoint.version, resumed.version)

    def test_manual_resume_does_not_select_password_add_or_non_pending_recovery(self):
        checkpoint = store.prepare_password_recovery(
            **self.owner,
            candidate_factory=lambda: "new-password",
            intent="password_add",
        )
        checkpoint = store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="started",
        )
        store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="confirmed",
            confirmation="password_add_response",
        )
        self.end_owner()
        self.owner = self.make_owner()

        self.assertIsNone(store.resume_manual_password_change(**self.owner))

    def test_legacy_confirmed_recovery_without_p1_marker_is_not_completed_resume(self):
        checkpoint = store.prepare_password_recovery(
            **self.owner,
            candidate_factory=lambda: "new-password",
        )
        checkpoint = store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="started",
        )
        store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="confirmed",
            confirmation="password_change_response",
        )
        self.end_owner()
        self.owner = self.make_owner()
        self.assertIsNone(store.resume_manual_password_change(**self.owner))

    def test_manual_resume_rejects_active_old_run_and_current_password_conflict(self):
        self.prepare_confirmed_pending()
        replacement = self.make_owner("password_change_recovery")
        with self.assertRaisesRegex(store.PasswordRecoveryError, "owner_active"):
            store.resume_manual_password_change(**replacement)

        self.end_owner()
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "other-password"}),
            "password": "other-password",
        })
        self.owner = replacement
        with self.assertRaisesRegex(store.PasswordRecoveryError, "password_conflict"):
            store.resume_manual_password_change(**self.owner)

    def test_save_and_complete_manual_password_change_are_atomic_and_clear_pending_marker(self):
        self.prepare_confirmed_pending()
        self.end_owner()
        self.owner = self.make_owner()
        resumed = store.resume_manual_password_change(**self.owner)

        store.save_manual_password_change_session(
            resumed.recovery_id,
            **self.owner,
            access_token="fresh-token",
            session_info=matching_session(self.email),
            protocol_session=protocol_session(),
            auth_method="session_cookie",
        )
        account = records.get_row(records.ACCOUNTS, self.account_id)
        self.assertEqual("fresh-token", account["access_token"])
        self.assertEqual(protocol_session(), protocol_sessions.load_session(self.account_id, self.email))

        completed = store.complete_manual_password_change(
            resumed.recovery_id,
            **self.owner,
            expected_version=resumed.version,
            access_token="fresh-token",
        )
        self.assertFalse(completed.completion_pending)
        self.assertEqual(resumed.version + 1, completed.version)
        resumed_after_completion = store.resume_manual_password_change(**self.owner)
        self.assertEqual(completed.recovery_id, resumed_after_completion.recovery_id)
        self.assertFalse(resumed_after_completion.completion_pending)

    def test_manual_session_save_preserves_registration_progress(self):
        extra = {
            "account_password": "old-password",
            "registration_checkpoint": "session_pending",
            "registration_pending_reason": "fixture-pending",
            "preserved": 42,
        }
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps(extra),
        })
        checkpoint = self.prepare_confirmed_pending()
        before = records.get_row(records.ACCOUNTS, self.account_id)["extra_json"]

        store.save_manual_password_change_session(
            checkpoint.recovery_id,
            **self.owner,
            access_token="fresh-token",
            session_info=matching_session(self.email),
            protocol_session=protocol_session(),
        )

        after = records.get_row(records.ACCOUNTS, self.account_id)["extra_json"]
        self.assertEqual(before, after)

    def test_same_durable_task_resumes_completed_checkpoint_but_new_task_does_not(self):
        checkpoint = self.prepare_confirmed_pending()
        task_id_a = self.operation_task_id(self.owner["operation_run_id"])
        self.end_owner()
        self.owner = self.make_owner()
        resumed_b = store.resume_manual_password_change(**self.owner)
        self.assertTrue(resumed_b.completion_pending)
        store.save_manual_password_change_session(
            resumed_b.recovery_id,
            **self.owner,
            access_token="fresh-token",
            session_info=matching_session(self.email),
            protocol_session=protocol_session(),
        )
        completed_b = store.complete_manual_password_change(
            resumed_b.recovery_id,
            **self.owner,
            expected_version=resumed_b.version,
            access_token="fresh-token",
        )
        self.assertFalse(completed_b.completion_pending)

        self.end_owner()
        self.owner = self.make_owner(task_id=task_id_a)
        resumed_a = store.resume_manual_password_change(**self.owner)
        self.assertIsNotNone(resumed_a)
        self.assertFalse(resumed_a.completion_pending)
        self.assertEqual("confirmed", resumed_a.state)

        self.end_owner()
        self.owner = self.make_owner()
        self.assertIsNone(store.resume_manual_password_change(**self.owner))

    def test_unknown_candidate_keeps_original_task_for_a_retry_after_b_completes(self):
        checkpoint = store.prepare_password_recovery(
            **self.owner,
            candidate_factory=lambda: "new-password",
        )
        checkpoint = store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="started",
        )
        checkpoint = store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="unknown",
        )
        task_id_a = self.operation_task_id(self.owner["operation_run_id"])

        self.end_owner()
        self.owner = self.make_owner()
        resumed_b = store.resume_password_recovery(**self.owner, intent="password_change")
        self.assertEqual(checkpoint.recovery_id, resumed_b.recovery_id)
        self.assertIn(task_id_a, self.completion_task_ids(checkpoint.recovery_id))
        confirmed_b = store.transition_password_recovery(
            resumed_b.recovery_id,
            **self.owner,
            expected_version=resumed_b.version,
            state="confirmed",
            confirmation="password_change_response",
            completion_pending=True,
        )
        store.save_manual_password_change_session(
            confirmed_b.recovery_id,
            **self.owner,
            access_token="fresh-token",
            session_info=matching_session(self.email),
            protocol_session=protocol_session(),
        )
        completed_b = store.complete_manual_password_change(
            confirmed_b.recovery_id,
            **self.owner,
            expected_version=confirmed_b.version,
            access_token="fresh-token",
        )
        self.assertFalse(completed_b.completion_pending)

        self.end_owner()
        self.owner = self.make_owner(task_id=task_id_a)
        resumed_a = store.resume_manual_password_change(**self.owner)
        self.assertEqual(completed_b.recovery_id, resumed_a.recovery_id)
        self.assertFalse(resumed_a.completion_pending)

    def test_confirmed_retry_cannot_change_pending_marker_or_bypass_version(self):
        checkpoint = self.prepare_confirmed_pending()
        unchanged = store.transition_password_recovery(
            checkpoint.recovery_id,
            **self.owner,
            expected_version=checkpoint.version,
            state="confirmed",
            confirmation="password_change_response",
            completion_pending=False,
        )
        self.assertTrue(unchanged.completion_pending)
        with self.assertRaisesRegex(store.PasswordRecoveryError, "version_conflict"):
            store.transition_password_recovery(
                checkpoint.recovery_id,
                **self.owner,
                expected_version=checkpoint.version - 1,
                state="confirmed",
                confirmation="password_change_response",
                completion_pending=True,
            )
        self.assertTrue(store.get_password_recovery(checkpoint.recovery_id, **self.owner).completion_pending)

    def test_legacy_unknown_takeover_preserves_original_task_without_metadata(self):
        checkpoint = store.prepare_password_recovery(
            **self.owner, candidate_factory=lambda: "new-password",
        )
        checkpoint = store.transition_password_recovery(
            checkpoint.recovery_id, **self.owner, expected_version=checkpoint.version, state="started",
        )
        checkpoint = store.transition_password_recovery(
            checkpoint.recovery_id, **self.owner, expected_version=checkpoint.version, state="unknown",
        )
        task_a = self.operation_task_id(self.owner["operation_run_id"])
        cipher, _ = store._cipher()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT credential_ciphertext FROM {pg.qualified('account_password_recoveries')} WHERE id=%s",
                (checkpoint.recovery_id,),
            )
            payload = json.loads(cipher.decrypt(cur.fetchone()[0].encode()))
            payload.pop("completion_task_ids", None)
            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()
            cur.execute(
                f"UPDATE {pg.qualified('account_password_recoveries')} SET credential_ciphertext=%s WHERE id=%s",
                (encrypted, checkpoint.recovery_id),
            )
        self.end_owner()
        self.owner = self.make_owner()
        resumed = store.resume_password_recovery(**self.owner, intent="password_change")
        self.assertEqual(
            {task_a, self.operation_task_id(self.owner["operation_run_id"])},
            set(self.completion_task_ids(checkpoint.recovery_id)),
        )
        confirmed = store.transition_password_recovery(
            resumed.recovery_id, **self.owner, expected_version=resumed.version,
            state="confirmed", confirmation="password_change_response", completion_pending=True,
        )
        self.complete_checkpoint(confirmed)
        self.end_owner()
        self.owner = self.make_owner(task_id=task_a)
        recovered = store.resume_manual_password_change(**self.owner)
        self.assertEqual(checkpoint.recovery_id, recovered.recovery_id)
        self.assertFalse(recovered.completion_pending)

    def test_old_completed_task_does_not_take_over_later_candidate_or_pending_completion(self):
        first = self.prepare_confirmed_pending()
        task_a = self.operation_task_id(self.owner["operation_run_id"])
        self.complete_checkpoint(first)
        self.end_owner()
        self.owner = self.make_owner()
        task_b = self.operation_task_id(self.owner["operation_run_id"])
        second = store.prepare_password_recovery(
            **self.owner, candidate_factory=lambda: "later-password",
        )
        second = store.transition_password_recovery(
            second.recovery_id, **self.owner, expected_version=second.version, state="started",
        )
        second = store.transition_password_recovery(
            second.recovery_id, **self.owner, expected_version=second.version, state="unknown",
        )
        self.end_owner()
        self.owner = self.make_owner(task_id=task_a)
        recovered_a = store.resume_manual_password_change(**self.owner)
        self.assertEqual(first.recovery_id, recovered_a.recovery_id)
        self.assertFalse(recovered_a.completion_pending)
        self.end_owner()
        self.owner = self.make_owner(task_id=task_b)
        recovered_b = store.resume_password_recovery(**self.owner, intent="password_change")
        store.transition_password_recovery(
            recovered_b.recovery_id, **self.owner, expected_version=recovered_b.version,
            state="confirmed", confirmation="password_change_response", completion_pending=True,
        )
        self.end_owner()
        self.owner = self.make_owner(task_id=task_a)
        with self.assertRaisesRegex(store.PasswordRecoveryError, "password_conflict"):
            store.resume_manual_password_change(**self.owner)

    def complete_checkpoint(self, checkpoint):
        store.save_manual_password_change_session(
            checkpoint.recovery_id, **self.owner, access_token="fresh-token",
            session_info=matching_session(self.email), protocol_session=protocol_session(),
        )
        return store.complete_manual_password_change(
            checkpoint.recovery_id, **self.owner,
            expected_version=checkpoint.version, access_token="fresh-token",
        )

    def test_manual_session_requires_chatgpt_session_token_cookie(self):
        checkpoint = self.prepare_confirmed_pending()
        self.end_owner()
        self.owner = self.make_owner()
        resumed = store.resume_manual_password_change(**self.owner)
        invalid = protocol_session()
        invalid["cookies"] = [{
            "name": "oai-did",
            "value": "fixture-device",
            "domain": "chatgpt.com",
            "path": "/",
        }]
        with self.assertRaisesRegex(store.PasswordRecoveryError, "protocol_session_invalid"):
            store.save_manual_password_change_session(
                resumed.recovery_id,
                **self.owner,
                access_token="fresh-token",
                session_info=matching_session(self.email),
                protocol_session=invalid,
            )
        self.assertTrue(store.get_password_recovery(resumed.recovery_id, **self.owner).completion_pending)

    def test_replaced_private_protocol_cache_keeps_completion_pending(self):
        checkpoint = self.prepare_confirmed_pending()
        self.end_owner()
        self.owner = self.make_owner()
        resumed = store.resume_manual_password_change(**self.owner)
        store.save_manual_password_change_session(
            resumed.recovery_id,
            **self.owner,
            access_token="fresh-token",
            session_info=matching_session(self.email),
            protocol_session=protocol_session(),
        )
        replaced = protocol_session()
        replaced["cookies"][0]["value"] = "replacement-cookie"
        protocol_sessions.save_session(self.account_id, self.email, replaced)
        with self.assertRaisesRegex(store.PasswordRecoveryError, "protocol_session_digest_mismatch"):
            store.complete_manual_password_change(
                resumed.recovery_id,
                **self.owner,
                expected_version=resumed.version,
                access_token="fresh-token",
            )
        self.assertTrue(store.get_password_recovery(resumed.recovery_id, **self.owner).completion_pending)

    def test_complete_rejects_version_or_token_conflict_without_clearing_pending(self):
        self.prepare_confirmed_pending()
        self.end_owner()
        self.owner = self.make_owner()
        resumed = store.resume_manual_password_change(**self.owner)
        store.save_manual_password_change_session(
            resumed.recovery_id,
            **self.owner,
            access_token="fresh-token",
            session_info=matching_session(self.email),
            protocol_session=protocol_session(),
        )

        for kwargs, code in (
            ({"expected_version": resumed.version - 1, "access_token": "fresh-token"}, "version_conflict"),
            ({"expected_version": resumed.version, "access_token": "stale-token"}, "session_token_conflict"),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(store.PasswordRecoveryError, code):
                store.complete_manual_password_change(resumed.recovery_id, **self.owner, **kwargs)
            self.assertTrue(store.get_password_recovery(resumed.recovery_id, **self.owner).completion_pending)

    def test_protocol_session_can_join_recovery_transaction_and_roll_back_with_it(self):
        protocol_sessions.init()
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with pg.connect() as conn:
                protocol_sessions.save_session(
                    self.account_id,
                    self.email,
                    protocol_session(),
                    conn=conn,
                )
                raise RuntimeError("rollback")
        self.assertIsNone(protocol_sessions.load_session(self.account_id, self.email))

    def operation_task_id(self, run_id):
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT task_id FROM {pg.qualified('operation_runs')} WHERE id=%s",
                (run_id,),
            )
            return cur.fetchone()[0]

    def completion_task_ids(self, recovery_id):
        cipher, _ = store._cipher()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT credential_ciphertext FROM {pg.qualified('account_password_recoveries')} WHERE id=%s",
                (recovery_id,),
            )
            payload = json.loads(cipher.decrypt(cur.fetchone()[0].encode()))
        return payload["completion_task_ids"]
