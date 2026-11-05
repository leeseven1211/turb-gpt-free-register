"""协议补密码的真实私有检查点、执行围栏及服务编排。"""
from __future__ import annotations

import importlib
import base64
import json
import os
import uuid
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.storage import postgres as pg, records as records
from core.storage.accounts import password_recovery as store
from core.storage.operations import store as operations
from tests.support_pg import PostgresTestCase


def matching_session(email, token="fresh-token"):
    return {"accessToken": token, "user": {"email": email, "id": "fixture-user"},
            "account": {"id": "fixture-account"}, "expires": "2099-01-01"}


def identity_token(*, email=None, user_id=None, account_id=None):
    payload = {"https://api.openai.com/profile": {"email": email},
               "https://api.openai.com/auth": {"chatgpt_user_id": user_id, "chatgpt_account_id": account_id}}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"fixture.{encoded}.signature"


class PasswordSetupFixture:
    def setUp(self):
        key = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        key.start()
        self.addCleanup(key.stop)
        operations.init()
        self.email = "add-password@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email, "access_token": "old-token", "password": "mail-only-password",
            "extra_json": json.dumps({"preserved": 42}), "account_status": "active",
        })
        self.owner = self.make_owner()

    def make_owner(self, task_type="password_setup", steps=None):
        execution = uuid.uuid4().hex
        source_id = uuid.uuid4().hex
        data = {} if steps is None else {"steps": steps}
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"INSERT INTO {pg.qualified('operation_tasks')} "
                        "(task_uuid,source_system,source_id,task_type,target_type,account_id,email_snapshot,requested_action,status,data) "
                        "VALUES (%s,'webui_runtime',%s,%s,'account',%s,%s,%s,'running',%s::jsonb) RETURNING id",
                        (uuid.uuid4().hex, source_id, task_type, self.account_id, self.email, task_type, json.dumps(data)))
            task_id = cur.fetchone()[0]
            cur.execute(f"INSERT INTO {pg.qualified('operation_runs')} "
                        "(run_uuid,task_id,run_no,source_system,source_id,status,execution_id,account_id) "
                        "VALUES (%s,%s,1,'webui_runtime',%s,'running',%s,%s) RETURNING id",
                        (uuid.uuid4().hex, task_id, source_id, execution, self.account_id))
            run_id = cur.fetchone()[0]
        lease = operations.acquire_account_lease(account_id=self.account_id, run_id=run_id)
        return dict(email=self.email, account_id=self.account_id, purpose="manual", operation_run_id=run_id,
                    operation_execution_id=execution, operation_lease_token=lease,
                    attempt_id=None, registration_run_id=None, registration_execution_id=None)

    def end_owner(self):
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET status='failed' WHERE id=%s", (self.owner["operation_run_id"],))
            cur.execute(f"DELETE FROM {pg.qualified('account_operation_leases')} WHERE account_id=%s", (self.account_id,))

    def extra(self):
        return json.loads(records.get_row(records.ACCOUNTS, self.account_id)["extra_json"])

    def prepare(self):
        return store.prepare_password_recovery(**self.owner, candidate_factory=lambda: "Candidate-pass-42",
                                               intent="password_add")

    def transition(self, cp, state, confirmation=None):
        return store.transition_password_recovery(cp.recovery_id, **self.owner, expected_version=cp.version,
                                                  state=state, confirmation=confirmation)


class PasswordSetupStoreTests(PasswordSetupFixture, PostgresTestCase):
    def existing_password(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Existing-pass-42", "preserved": 42}),
            "totp_secret": "fixture-totp-secret",
        })

    def test_verified_original_password_and_new_session_are_saved_atomically(self):
        self.existing_password()
        cp = self.prepare()
        confirmed = store.save_password_recovery_session(cp.recovery_id, **self.owner,
            access_token="fresh-token", session_info=matching_session(self.email),
            verified_password="Existing-pass-42", auth_method="password_mfa_totp", password_auth_status="verified")
        self.assertEqual("confirmed", confirmed.state)
        self.assertEqual("Existing-pass-42", confirmed.password)
        self.assertNotEqual(cp.password, confirmed.password)
        self.assertIsNone(store.resume_password_recovery(**self.owner))
        account = records.get_row(records.ACCOUNTS, self.account_id)
        self.assertEqual("fresh-token", account["access_token"])
        self.assertEqual("fixture-totp-secret", account["totp_secret"])
        self.assertEqual("Existing-pass-42", self.extra()["account_password"])
        self.assertEqual("confirmed", self.extra()["account_password_state"])
        self.assertEqual("verified", account["last_password_auth_status"])
        self.assertEqual(42, self.extra()["preserved"])
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT confirmation FROM {pg.qualified('account_password_recoveries')} WHERE id=%s", (cp.recovery_id,))
            self.assertEqual("existing_password_login", cur.fetchone()[0])

    def test_unsubmitted_candidate_is_not_mistaken_for_verified_original_password(self):
        self.existing_password()
        cp = self.prepare()
        with self.assertRaisesRegex(store.PasswordRecoveryError, "password_login_confirmation_mismatch"):
            store.save_password_recovery_session(cp.recovery_id, **self.owner,
                access_token="fresh-token", session_info=matching_session(self.email),
                verified_password=cp.password, password_auth_status="verified")
        self.assertEqual("old-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])
        self.assertEqual(cp.password, store.resume_password_recovery(**self.owner).password)

    def test_dispatched_candidate_is_preserved_when_original_password_is_verified(self):
        self.existing_password()
        cp = self.transition(self.prepare(), "started")
        cp = self.transition(cp, "unknown")
        with self.assertRaisesRegex(store.PasswordRecoveryError, "password_login_confirmation_not_prepared"):
            store.save_password_recovery_session(cp.recovery_id, **self.owner,
                access_token="fresh-token", session_info=matching_session(self.email),
                verified_password="Existing-pass-42", password_auth_status="verified")
        pending = store.resume_password_recovery(**self.owner)
        self.assertEqual("unknown", pending.state)
        self.assertEqual(cp.password, pending.password)

    def test_session_failure_rolls_back_original_password_confirmation(self):
        self.existing_password()
        cp = self.prepare()
        original_patch = records.patch_row
        def fail_session(collection, row_id, values, **kwargs):
            if "access_token" in values:
                raise RuntimeError("fixture session persistence failed")
            return original_patch(collection, row_id, values, **kwargs)
        with patch.object(records, "patch_row", side_effect=fail_session):
            with self.assertRaisesRegex(RuntimeError, "fixture session persistence failed"):
                store.save_password_recovery_session(cp.recovery_id, **self.owner,
                    access_token="fresh-token", session_info=matching_session(self.email),
                    verified_password="Existing-pass-42", password_auth_status="verified")
        account = records.get_row(records.ACCOUNTS, self.account_id)
        self.assertEqual("old-token", account["access_token"])
        self.assertNotEqual("verified", account.get("last_password_auth_status"))
        self.assertEqual("prepared", store.resume_password_recovery(**self.owner).state)
        self.assertEqual(cp.password, store.resume_password_recovery(**self.owner).password)

    def test_original_password_confirmation_requires_matching_session_and_token(self):
        self.existing_password()
        cp = self.prepare()
        invalid_sessions = (
            {},
            {"accessToken": "fresh-token"},
            {"accessToken": "fresh-token", "user": {}},
            matching_session("other@example.test"),
            matching_session(self.email, "different-token"),
            {"user": {"email": self.email}},
        )
        for info in invalid_sessions:
            with self.subTest(kind=tuple(info)):
                with self.assertRaisesRegex(store.PasswordRecoveryError, "session_context_invalid"):
                    store.save_password_recovery_session(cp.recovery_id, **self.owner,
                        access_token="fresh-token", session_info=info, verified_password="Existing-pass-42",
                        password_auth_status="verified")
                account = records.get_row(records.ACCOUNTS, self.account_id)
                self.assertEqual("old-token", account["access_token"])
                self.assertNotEqual("verified", account.get("last_password_auth_status"))
                self.assertNotEqual("confirmed", self.extra().get("account_password_state"))
                self.assertEqual(cp.password, store.resume_password_recovery(**self.owner).password)
                self.assertEqual("prepared", store.resume_password_recovery(**self.owner).state)

    def test_token_identity_claim_conflicts_cannot_confirm_original_password(self):
        self.existing_password()
        cp = self.prepare()
        for claims in ({"email": "other@example.test"}, {"user_id": "different-user"},
                       {"account_id": "different-account"}):
            with self.subTest(field=next(iter(claims))):
                token = identity_token(**claims)
                with self.assertRaisesRegex(store.PasswordRecoveryError, "session_context_invalid"):
                    store.save_password_recovery_session(cp.recovery_id, **self.owner,
                        access_token=token, session_info=matching_session(self.email, token),
                        verified_password="Existing-pass-42", password_auth_status="verified")
                self.assertEqual("old-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])
                self.assertEqual("prepared", store.resume_password_recovery(**self.owner).state)

    def test_original_password_confirmation_requires_current_password_verification(self):
        self.existing_password()
        cp = self.prepare()
        for status in ("", "skipped", "accepted", "rejected", "unknown"):
            with self.subTest(status=status):
                with self.assertRaisesRegex(store.PasswordRecoveryError, "password_login_confirmation_unverified"):
                    store.save_password_recovery_session(cp.recovery_id, **self.owner,
                        access_token="fresh-token", session_info=matching_session(self.email),
                        verified_password="Existing-pass-42", password_auth_status=status)
                self.assertEqual("prepared", store.resume_password_recovery(**self.owner).state)
                self.assertNotEqual("confirmed", self.extra().get("account_password_state"))

    def test_optional_token_identity_claims_do_not_block_a_matching_session(self):
        self.existing_password()
        cp = self.prepare()
        token = identity_token()
        confirmed = store.save_password_recovery_session(cp.recovery_id, **self.owner,
            access_token=token, session_info=matching_session(self.email.upper(), token),
            verified_password="Existing-pass-42", password_auth_status="verified")
        self.assertEqual("confirmed", confirmed.state)
        self.assertEqual("confirmed", self.extra()["account_password_state"])

    def test_setup_candidate_is_private_until_explicit_add_confirmation(self):
        cp = self.prepare()
        self.assertEqual("", cp.old_password)
        self.assertNotIn("account_password", self.extra())
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT credential_ciphertext FROM {pg.qualified('account_password_recoveries')}")
            self.assertNotIn("Candidate-pass-42", cur.fetchone()[0])
        cp = self.transition(cp, "started")
        self.transition(cp, "confirmed", "password_add_response")
        self.assertEqual({"account_password": "Candidate-pass-42", "account_password_state": "confirmed",
                          "preserved": 42}, self.extra())

    def test_combined_setup_requires_password_step(self):
        self.end_owner()
        self.owner = self.make_owner("account_setup_retry", ["password", "twofa"])
        self.assertEqual("prepared", self.prepare().state)

    def test_twofa_and_completion_coordinator_cannot_own_password_candidate(self):
        for task_type, steps in [("twofa_setup", None), ("account_completion", ["password"]),
                                 ("account_setup_retry", ["twofa"])]:
            with self.subTest(task_type=task_type):
                self.end_owner()
                self.owner = self.make_owner(task_type, steps)
                with self.assertRaisesRegex(store.PasswordRecoveryError, "manual_operation_mismatch"):
                    self.prepare()

    def test_add_confirmation_can_replace_an_unverified_local_password(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {"extra_json": json.dumps({"account_password": "Already-set-1"})})
        cp = self.transition(self.prepare(), "started")
        self.assertEqual("Already-set-1", self.extra()["account_password"])
        self.transition(cp, "confirmed", "password_add_response")
        self.assertEqual("Candidate-pass-42", self.extra()["account_password"])
        self.assertEqual("confirmed", self.extra()["account_password_state"])

    def test_add_response_does_not_confirm_a_password_change_candidate(self):
        cp = store.prepare_password_recovery(**self.owner, candidate_factory=lambda: "Candidate-pass-42")
        cp = self.transition(cp, "started")
        with self.assertRaisesRegex(store.PasswordRecoveryError, "password_add_context_invalid"):
            self.transition(cp, "confirmed", "password_add_response")

    def test_add_does_not_take_over_a_pending_password_change(self):
        store.prepare_password_recovery(**self.owner, candidate_factory=lambda: "Change-pass-42")
        with self.assertRaisesRegex(store.PasswordRecoveryError, "recovery_intent_conflict"):
            self.prepare()

    def test_password_change_cannot_resume_or_confirm_an_add_candidate(self):
        cp = self.transition(self.prepare(), "started")
        with self.assertRaisesRegex(store.PasswordRecoveryError, "recovery_intent_conflict"):
            store.resume_password_recovery(**self.owner, intent="password_change")
        with self.assertRaisesRegex(store.PasswordRecoveryError, "recovery_intent_conflict"):
            self.transition(cp, "confirmed", "password_change_response")

    def test_legacy_add_candidate_resumes_without_changing_its_password(self):
        cp = store.prepare_password_recovery(**self.owner, candidate_factory=lambda: "Legacy-add-42")
        # 旧版补密码检查点没有 intent；模拟该旧格式，恢复仍复用原私有候选。
        cipher, _ = store._cipher()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT credential_ciphertext FROM {pg.qualified('account_password_recoveries')} WHERE id=%s",
                        (cp.recovery_id,))
            payload = json.loads(cipher.decrypt(cur.fetchone()[0].encode()))
            payload.pop("intent")
            cur.execute(f"UPDATE {pg.qualified('account_password_recoveries')} SET credential_ciphertext=%s WHERE id=%s",
                        (cipher.encrypt(json.dumps(payload).encode()).decode(), cp.recovery_id))
        with self.assertRaisesRegex(store.PasswordRecoveryError, "recovery_intent_conflict"):
            store.resume_password_recovery(**self.owner, intent="password_change")
        resumed = self.prepare()
        self.assertEqual("Legacy-add-42", resumed.password)
        self.assertEqual("password_add", resumed.intent)

    def test_session_write_checks_current_execution_and_preserves_candidate(self):
        cp = self.prepare()
        save_session = getattr(store, "save_password_recovery_session", None)
        self.assertTrue(callable(save_session), "协议会话应在执行围栏事务内保存")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET execution_id='replacement' WHERE id=%s",
                        (self.owner["operation_run_id"],))
        with self.assertRaisesRegex(store.PasswordRecoveryError, "operation_execution_mismatch"):
            save_session(cp.recovery_id, **self.owner, access_token="stale-token",
                         session_info=matching_session(self.email, "stale-token"))
        self.assertEqual("old-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])

    def test_session_write_keeps_unrelated_fields_without_confirming_password(self):
        cp = self.prepare()
        save_session = getattr(store, "save_password_recovery_session", None)
        self.assertTrue(callable(save_session), "协议会话应在执行围栏事务内保存")
        save_session(cp.recovery_id, **self.owner, access_token="fresh-token", session_info=matching_session(self.email))
        account = records.get_row(records.ACCOUNTS, self.account_id)
        self.assertEqual("fresh-token", account["access_token"])
        self.assertEqual("mail-only-password", account["password"])
        self.assertEqual(42, self.extra()["preserved"])
        self.assertNotIn("account_password", self.extra())
        self.assertEqual("prepared", store.resume_password_recovery(**self.owner).state)


class PasswordSetupServiceTests(PasswordSetupFixture, PostgresTestCase):
    def setUp(self):
        super().setUp()
        try:
            self.service = importlib.import_module("core.accounts.password_setup.service")
        except ModuleNotFoundError:
            self.fail("尚未实现纯协议补密码服务")

    def run_service(self, add, *, login=None, checkpoint=None, report=None):
        def authenticated(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                "session": matching_session(email)}, object())
        with patch.object(self.service, "refresh_access_token", side_effect=login or authenticated), \
                patch.object(self.service, "add_password", side_effect=add):
            return self.service.run_protocol_password_setup(self.email, proxy=None, checkpoint=checkpoint, report=report,
                execution_fence={"run_id": self.owner["operation_run_id"],
                    "execution_id": self.owner["operation_execution_id"], "lease_token": self.owner["operation_lease_token"]})

    def test_service_persists_before_dispatch_and_only_confirms_after_response(self):
        def add(session, email, password, **kwargs):
            cp = store.resume_password_recovery(**self.owner)
            self.assertEqual(password, cp.password)
            self.assertEqual("prepared", cp.state)
            self.assertNotIn("account_password", self.extra())
            kwargs["on_dispatched"]()
            self.assertEqual("started", store.resume_password_recovery(**self.owner).state)
            kwargs["on_confirmed"]()
            return {"ok": True}
        result = self.run_service(add)
        self.assertTrue(result["ok"])
        self.assertEqual("confirmed", result["remote_receipt_state"])
        self.assertTrue(self.extra()["account_password"])
        self.assertEqual("fresh-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])
        self.assertEqual("accepted", records.get_row(records.ACCOUNTS, self.account_id)["last_password_auth_status"])
        self.assertNotIn(self.extra()["account_password"], json.dumps(result))
        self.assertNotIn("fresh-token", json.dumps(result))

    def test_verified_password_finishes_success_without_adding_or_replacing_it(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Existing-pass-42", "preserved": 42}),
            "totp_secret": "fixture-totp-secret",
        })
        def login(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                "password_auth_status": "verified", "auth_method": "password_mfa_totp",
                "session": matching_session(email)}, object())
        def forbidden(*args, **kwargs):
            self.fail("已验证原密码不应再调用添加密码")
        events = []
        result = self.run_service(forbidden, login=login, report=lambda **event: events.append(event))
        self.assertTrue(result["ok"])
        self.assertEqual("success", result["status"])
        self.assertEqual("原密码有效", result["message"])
        self.assertTrue(result["password_verified"])
        self.assertFalse(result["password_added"])
        self.assertFalse(result["mutation_submitted"])
        self.assertEqual("confirmed", result["remote_receipt_state"])
        account = records.get_row(records.ACCOUNTS, self.account_id)
        self.assertEqual("verified", account["last_password_auth_status"])
        self.assertEqual("Existing-pass-42", self.extra()["account_password"])
        self.assertEqual("fixture-totp-secret", account["totp_secret"])
        self.assertIn(("set_password", "success", "原密码有效，已验证"),
            [(e["stage"], e["state"], e["message"]) for e in events])
        self.assertNotIn("Existing-pass-42", json.dumps(result))
        self.assertNotIn("fresh-token", json.dumps(result))

    def test_password_method_or_saved_value_without_verified_result_does_not_shortcut(self):
        for status in (None, "skipped", "rejected", "unknown"):
            with self.subTest(status=status):
                records.patch_row(records.ACCOUNTS, self.account_id, {
                    "extra_json": json.dumps({"account_password": "Existing-pass-42"}),
                })
                called = []
                def login(email, **kwargs):
                    return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                        "password_auth_status": status, "auth_method": "password_mfa_totp",
                        "session": matching_session(email)}, object())
                def add(_session, _email, _password, **kwargs):
                    called.append(True)
                    kwargs["on_dispatched"]()
                    kwargs["on_confirmed"]()
                result = self.run_service(add, login=login)
                self.assertTrue(result["ok"])
                self.assertEqual([True], called)
                self.assertFalse(result["password_verified"])

    def test_verified_password_without_token_does_not_confirm_or_add(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Existing-pass-42"}),
        })
        def login(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": True,
                "password_auth_status": "verified", "session": {}}, object())
        result = self.run_service(lambda *a, **k: self.fail("未取得会话不得添加密码"), login=login)
        self.assertFalse(result["ok"])
        self.assertEqual("password_setup_session_missing", result["error_code"])
        self.assertNotEqual("confirmed", self.extra().get("account_password_state"))

    def test_verified_password_with_unbound_or_wrong_identity_never_confirms_or_adds(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Existing-pass-42", "account_password_state": "candidate"}),
        })
        pending = self.prepare()
        invalid_sessions = ({}, matching_session("other@example.test"),
                            matching_session(self.email, "different-token"),
                            {"accessToken": "fresh-token", "user": {}},
                            {"user": {"email": self.email}})
        for info in invalid_sessions:
            with self.subTest(kind=tuple(info)):
                def login(email, **kwargs):
                    return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                        "password_auth_status": "verified", "session": info}, object())
                result = self.run_service(lambda *a, **k: self.fail("身份不匹配不得添加密码"), login=login)
                self.assertFalse(result["ok"])
                self.assertFalse(result["password_verified"])
                self.assertFalse(result["password_added"])
                self.assertEqual("password_recovery_session_context_invalid", result["error_code"])
                self.assertEqual("candidate", self.extra()["account_password_state"])
                self.assertEqual("old-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])
                self.assertEqual(pending.password, store.resume_password_recovery(**self.owner).password)
                self.assertEqual("prepared", store.resume_password_recovery(**self.owner).state)

    def test_email_only_session_with_wrong_identity_does_not_submit_add_password(self):
        def login(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                "password_auth_status": "skipped", "session": matching_session("other@example.test")}, object())
        result = self.run_service(lambda *a, **k: self.fail("异账号会话不可添加密码"), login=login)
        self.assertFalse(result["ok"])
        self.assertFalse(result["password_added"])
        self.assertEqual("old-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])

    def test_authentication_callback_without_success_does_not_confirm_or_add(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Existing-pass-42"}),
        })
        def login(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": False, "access_token": "fresh-token",
                "password_auth_status": "verified", "session": matching_session(email)}, object())
        result = self.run_service(lambda *a, **k: self.fail("认证未完成不可添加密码"), login=login)
        self.assertFalse(result["ok"])
        self.assertFalse(result["password_verified"])
        self.assertEqual("old-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])

    def test_unmatched_session_preserves_an_earlier_unknown_password_submission(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Existing-pass-42", "account_password_state": "candidate"}),
        })
        pending = self.transition(self.transition(self.prepare(), "started"), "unknown")
        def login(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                "password_auth_status": "verified", "session": {}}, object())
        result = self.run_service(lambda *a, **k: self.fail("会话未对应不得重复添加密码"), login=login)
        self.assertFalse(result["ok"])
        self.assertFalse(result["password_verified"])
        self.assertEqual("unknown", result["remote_receipt_state"])
        self.assertEqual("password_recovery_session_context_invalid", result["error_code"])
        resumed = store.resume_password_recovery(**self.owner)
        self.assertEqual((pending.password, "unknown"), (resumed.password, resumed.state))
        self.assertEqual("old-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])

    def test_verified_password_is_exposed_to_account_list_without_secrets(self):
        from webui.app import create_app
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Existing-pass-42"}),
        })
        def login(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                "password_auth_status": "verified", "auth_method": "password_mfa_totp",
                "session": matching_session(email)}, object())
        self.assertTrue(self.run_service(lambda *a, **k: self.fail("不得添加已有密码"), login=login)["ok"])
        client = create_app(auth_code="fixture-auth").test_client()
        response = client.get("/api/accounts?paged=1", headers={"X-Auth-Code": "fixture-auth"})
        self.assertEqual(200, response.status_code)
        account = next(r for r in response.get_json()["items"] if r["id"] == self.account_id)
        self.assertEqual("verified", account["last_password_auth_status"])
        self.assertTrue(account["has_account_password"])
        self.assertNotIn("Existing-pass-42", response.get_data(as_text=True))
        self.assertNotIn("fresh-token", response.get_data(as_text=True))

    def test_verified_original_password_does_not_resolve_unknown_candidate(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Existing-pass-42"}),
        })
        cp = self.transition(self.transition(self.prepare(), "started"), "unknown")
        def login(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                "password_auth_status": "verified", "session": matching_session(email)}, object())
        result = self.run_service(lambda *a, **k: self.fail("不得重复添加未决密码"), login=login)
        self.assertEqual("unknown", result["remote_receipt_state"])
        self.assertEqual(cp.password, store.resume_password_recovery(**self.owner).password)
        self.assertEqual("unknown", store.resume_password_recovery(**self.owner).state)
        self.assertEqual("fresh-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])

    def test_authentication_failure_keeps_specific_safe_reason(self):
        for code, label in (("oauth_callback_failed", "登录回调未完成"), ("email_otp_failed", "登录邮箱验证码"),
                            ("mfa_rejected", "登录 2FA 验证未通过")):
            with self.subTest(code=code):
                result = self.run_service(lambda *a, **k: self.fail("认证失败不可提交密码"),
                    login=lambda *a, **k: {"ok": False, "error": code})
                self.assertIn(label, result["message"])
                self.assertEqual("password_setup_" + code, result["error_code"])
        result = self.run_service(lambda *a, **k: self.fail("需重置密码不可提交"), login=lambda *a, **k: {
            "ok": False, "error": "password_result_unknown", "auth_diagnostics": {
                "auth_error": {"code": "password_reset_required", "message": "cookie=PRIVATE"}},
        })
        self.assertEqual("password_setup_password_reset_required", result["error_code"])
        self.assertIn("远端要求重置密码", result["message"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_existing_totp_secret_is_passed_to_password_reauthentication(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {"totp_secret": "fixture-totp-secret"})
        def add(_session, _email, _password, **kwargs):
            self.assertEqual(kwargs["totp_secret"], "fixture-totp-secret")
            kwargs["on_dispatched"]()
            kwargs["on_confirmed"]()
        result = self.run_service(add)
        self.assertTrue(result["ok"])
        self.assertNotIn("fixture-totp-secret", json.dumps(result))

    def test_unknown_dispatch_keeps_same_candidate_after_execution_restart(self):
        candidates = []
        def unknown(session, email, password, **kwargs):
            candidates.append(password)
            kwargs["on_dispatched"]()
            raise self.service.ProtocolPasswordSetupError("password_setup_transport", "请求无回执", request_unknown=True)
        first = self.run_service(unknown)
        self.assertEqual("unknown", first["remote_receipt_state"])
        self.assertNotIn("account_password", self.extra())
        self.assertEqual("unknown", store.resume_password_recovery(**self.owner).state)
        self.end_owner()
        self.owner = self.make_owner()
        def confirmed(session, email, password, **kwargs):
            candidates.append(password)
            kwargs["on_dispatched"]()
            kwargs["on_confirmed"]()
            return {"ok": True}
        self.assertTrue(self.run_service(confirmed)["ok"])
        self.assertEqual(candidates[0], candidates[1])
        self.assertEqual(candidates[0], self.extra()["account_password"])

    def test_explicit_remote_rejection_keeps_candidate_and_refreshed_token(self):
        def rejected(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            raise self.service.ProtocolPasswordSetupError("password_setup_already_set", "远端已有密码")
        result = self.run_service(rejected)
        self.assertFalse(result["ok"])
        self.assertEqual("rejected", result["remote_receipt_state"])
        self.assertNotIn("account_password", self.extra())
        self.assertEqual("fresh-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])

    def test_existing_local_password_still_checks_remote_and_can_be_added(self):
        for state in (None, "candidate", "confirmed"):
            with self.subTest(state=state):
                extra = {"account_password": "Already-set-1"}
                if state:
                    extra["account_password_state"] = state
                records.patch_row(records.ACCOUNTS, self.account_id, {"extra_json": json.dumps(extra)})

                def add(session, email, password, **kwargs):
                    self.assertEqual("Already-set-1", self.extra()["account_password"])
                    kwargs["on_dispatched"]()
                    kwargs["on_confirmed"]()

                result = self.run_service(add)
                self.assertEqual("success", result["status"])
                self.assertNotEqual("Already-set-1", self.extra()["account_password"])
                self.assertEqual("confirmed", self.extra()["account_password_state"])

    def test_remote_rejection_preserves_existing_local_candidate(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "extra_json": json.dumps({"account_password": "Candidate-only", "account_password_state": "candidate"})})

        def rejected(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            raise self.service.ProtocolPasswordSetupError("password_setup_already_set", "远端已有密码")

        result = self.run_service(rejected)
        self.assertEqual("password_setup_already_set", result["error_code"])
        self.assertEqual("Candidate-only", self.extra()["account_password"])
        self.assertEqual("candidate", self.extra()["account_password_state"])

    def test_lost_execution_cannot_submit_or_confirm_password(self):
        def stale(session, email, password, **kwargs):
            with pg.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET execution_id='replacement' WHERE id=%s",
                            (self.owner["operation_run_id"],))
            kwargs["on_dispatched"]()
            self.fail("失去执行身份应在提交前阻断")
        result = self.run_service(stale)
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation_submitted"])
        self.assertNotIn("account_password", self.extra())

    def test_cancellation_from_callback_survives_auth_adapter(self):
        from core.operations.runtime import OperationCancelled
        def cancelled(session, email, password, **kwargs):
            raise OperationCancelled("stop")
        with self.assertRaises(OperationCancelled):
            self.run_service(cancelled)

    def test_auth_failure_does_not_dispatch_and_raw_error_is_not_returned(self):
        def forbidden(*args, **kwargs):
            self.fail("登录失败不可补密码")
        result = self.run_service(forbidden, login=lambda *a, **k: {"ok": False, "error": "raw-cookie=SECRET"})
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation_submitted"])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_auth_deactivation_is_preserved_without_submitting_password(self):
        def forbidden(*args, **kwargs):
            self.fail("已停用账号不可补密码")
        result = self.run_service(forbidden, login=lambda *a, **k: {
            "ok": False, "status": "deactivated", "error": "account_deactivated",
        })
        self.assertEqual("deactivated", result["status"])
        self.assertEqual("account_deactivated", result["error_code"])
        self.assertFalse(result["mutation_submitted"])

    def test_confirmed_password_closes_authentication_and_password_progress(self):
        from core.operations.progress import build_progress_snapshot
        events = []
        def confirmed(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            kwargs["on_confirmed"]()
            return {"ok": True}
        result = self.run_service(confirmed, report=lambda **event: events.append(event))
        persisted = [{**event, "id": index, "event_type": "stage." + event["state"]}
                     for index, event in enumerate(events, 1)]
        progress = build_progress_snapshot(1, 2, "password_setup", {
            "status": "success", "data": {"config_snapshot": {"password_driver": "protocol"}},
            "result_summary": result,
        }, persisted)
        states = {step["id"]: step["state"] for step in progress["main_steps"]}
        self.assertEqual("success", states["authenticate"])
        self.assertEqual("success", states["set_password"])

    def test_rejected_password_closes_failed_progress_without_hiding_authenticated_success(self):
        events = []
        def rejected(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            raise self.service.ProtocolPasswordSetupError("password_setup_already_set", "远端已有密码")
        self.run_service(rejected, report=lambda **event: events.append(event))
        terminal = [(event["stage"], event["state"]) for event in events if event["state"] != "running"]
        self.assertEqual([("login", "success"), ("set_password", "failed")], terminal)

    def test_cancellation_after_confirmation_keeps_success_receipt_and_stops_followup(self):
        from core.operations.runtime import OperationCancelled
        def confirmed(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            kwargs["on_confirmed"]()
            raise OperationCancelled("确认后取消")
        result = self.run_service(confirmed)
        self.assertTrue(result["ok"])
        self.assertTrue(result["stop_requested"])
        self.assertEqual("confirmed", result["remote_receipt_state"])
        self.assertTrue(self.extra()["account_password"])
