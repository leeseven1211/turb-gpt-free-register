"""真实隔离 PostgreSQL 下的协议改密与失败重跑闭环。"""
import json
from contextlib import ExitStack
from unittest.mock import patch

from core.accounts.password_setup import reset, reset_completion
from core.storage import records
from core.storage.accounts import password_recovery, protocol_sessions
from tests.accounts import test_password_change_completion_store as store_fixtures
from tests.accounts.test_password_change_completion_store import (
    matching_session,
    protocol_session,
)
from tests.accounts.test_password_reset_protocol import _ResetSession, _Response
from tests.support_pg import PostgresTestCase


def _object(value):
    return value if isinstance(value, dict) else json.loads(value)


class PasswordResetP1IntegrationTests(PostgresTestCase):
    # 复用账号、Run、租约夹具，不继承或重复执行存储层的独立用例。
    setUp = store_fixtures.PasswordChangeCompletionStoreTests.setUp
    make_owner = store_fixtures.PasswordChangeCompletionStoreTests.make_owner
    end_owner = store_fixtures.PasswordChangeCompletionStoreTests.end_owner

    def run_reset(self, *, business_ok=True):
        response_session = _ResetSession([_Response(200, {"page": {"type": "new_password"}}), _Response(200)])
        auth = {
            "ok": True, "password_auth_status": "verified", "auth_method": "password_mfa",
            "access_token": "fresh-token", "session": matching_session(self.email),
            "_protocol_session": protocol_session(),
        }
        observed_tokens = []

        def business(token, **_kwargs):
            observed_tokens.append(token)
            stored = records.get_row(records.ACCOUNTS, self.account_id)
            self.assertEqual(token, stored["access_token"])
            self.assertEqual(token, _object(stored["chatgpt_session"])["accessToken"])
            return {
                "ok": True, "account_id": "fixture-account",
                "response_account_id": "fixture-account",
            } if business_ok else {
                "ok": False, "error": "token_revoked", "http_status": 401,
            }

        with ExitStack() as stack:
            stack.enter_context(patch.object(reset, "_session_stale", return_value=False))
            stack.enter_context(patch.object(reset, "_check_reset_mailbox"))
            send = stack.enter_context(patch.object(reset, "_send_reset_otp"))
            stack.enter_context(patch.object(reset, "_wait_reset_otp", return_value="123456"))
            stack.enter_context(patch.object(reset, "request_sentinel_token", return_value="fixture-sentinel"))
            stack.enter_context(patch.object(reset, "build_sentinel_header", return_value=("fixture", "")))
            stack.enter_context(patch.object(reset, "_network_preflight_with_retry", return_value=(
                response_session, "https://auth.openai.com/authorize",
            )))
            stack.enter_context(patch.object(reset, "_run_password_verification", return_value=auth))
            stack.enter_context(patch.object(reset_completion, "check_account_plan", side_effect=business))
            result = reset.run_protocol_password_reset(
                self.email, refresh_before_reset=False,
                execution_fence={
                    "run_id": self.owner["operation_run_id"],
                    "execution_id": self.owner["operation_execution_id"],
                    "lease_token": self.owner["operation_lease_token"],
                },
            )
        return result, send.call_count, observed_tokens

    def test_single_operation_saves_password_token_session_and_private_cookies(self):
        result, reset_count, observed = self.run_reset()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["credentials_saved"])
        self.assertTrue(result["business_verified"])
        self.assertEqual(1, reset_count)
        self.assertEqual(["fresh-token"], observed)
        account = records.get_row(records.ACCOUNTS, self.account_id)
        self.assertNotEqual("old-password", _object(account["extra_json"])["account_password"])
        self.assertEqual("fresh-token", account["access_token"])
        self.assertEqual(protocol_session(), protocol_sessions.load_session(self.account_id, self.email))
        self.assertFalse(password_recovery.resume_manual_password_change(**self.owner).completion_pending)

    def test_business_failure_then_new_run_only_completes_existing_password(self):
        result, reset_count, _ = self.run_reset(business_ok=False)
        self.assertFalse(result["ok"])
        self.assertTrue(result["password_confirmed"])
        self.assertTrue(result["completion_pending"])
        self.assertEqual("token_revoked", result["cause_code"])
        self.assertEqual(1, reset_count)
        before = records.get_row(records.ACCOUNTS, self.account_id)
        stored_password = _object(before["extra_json"])["account_password"]
        self.end_owner()
        self.owner = self.make_owner()
        result, reset_count, observed = self.run_reset()
        self.assertTrue(result["ok"], result)
        self.assertEqual(0, reset_count)
        self.assertEqual(["fresh-token"], observed)
        after = records.get_row(records.ACCOUNTS, self.account_id)
        self.assertEqual(stored_password, _object(after["extra_json"])["account_password"])
        self.assertFalse(password_recovery.resume_manual_password_change(**self.owner).completion_pending)
