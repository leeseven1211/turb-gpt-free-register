"""C2A 本地 AT 重新导入必须走持久任务且保留远端回执边界。"""
import base64
import json
import time
from unittest.mock import patch

from core import db
from core.integrations.c2a import client, manual_sync
from core.operations import concurrency, task_gateway
from core.storage import records
from core.storage.operations import legacy_task_store
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


def fixture_token(payload):
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJ0ZXN0In0.{encoded}.fixture-signature"


class C2AManualSyncTests(PostgresTestCase):
    def setUp(self):
        operation.reset_ready()
        operation.init()
        legacy_schema = patch.object(legacy_task_store, "_SCHEMA", self.schema)
        legacy_schema.start()
        self.addCleanup(legacy_schema.stop)
        task_gateway.init()
        self.local_token = fixture_token({
            "exp": int(time.time()) + 3600,
            "https://api.openai.com/profile": {"email": "manual-c2a@example.test"},
        })
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": "manual-c2a@example.test",
            "access_token": self.local_token,
            "created_at": "2026-11-10",
            "updated_at": "2026-11-10",
        })
        identity = patch.object(client, "configured_backend_identity", return_value="fixture-c2a-backend")
        policy = patch.object(
            client,
            "verify_safe_mutation_policy",
            return_value=client.SafeMutationPolicy("fixture-c2a-backend"),
        )
        dispatcher = patch.object(task_gateway, "notify_dispatch")
        identity.start()
        policy.start()
        dispatcher.start()
        self.addCleanup(identity.stop)
        self.addCleanup(policy.stop)
        self.addCleanup(dispatcher.stop)
        self.addCleanup(task_gateway.unregister_operation_handler, manual_sync.TASK_TYPE)

    def queue(self):
        account = db.get_account(self.account_id)
        self.assertIsNotNone(account)
        return manual_sync.queue_account(account)

    def execute(self, queued):
        return task_gateway._execute_operation_handler(manual_sync.TASK_TYPE, queued["run_id"])

    @staticmethod
    def remote_account():
        return {
            "id": "c2a-account-17",
            "email": "manual-c2a@example.test",
            "backend_identity": "fixture-c2a-backend",
        }

    def test_queue_saves_only_account_reference_and_backend_summary(self):
        queued = self.queue()

        self.assertTrue(queued["accepted"])
        self.assertEqual("queued", queued["status"])
        run = operation.get_run(queued["run_id"])
        self.assertEqual(manual_sync.TASK_TYPE, run["task_type"])
        self.assertEqual("c2a_sync", concurrency.resolve_admission_class(run).key)
        self.assertEqual({"backend_identity": "fixture-c2a-backend"}, run["data"])
        self.assertNotIn(self.local_token, str(run["data"]))

    def test_unique_remote_account_updates_current_at_and_confirms_receipt(self):
        queued = self.queue()
        with patch.object(client, "find_unique_account", return_value=self.remote_account()) as find, patch.object(
            client, "update_account_access_token",
            return_value={"id": "c2a-account-17", "updated": True, "backend_identity": "fixture-c2a-backend"},
        ) as update:
            result = self.execute(queued)

        self.assertTrue(result["ok"])
        self.assertEqual("success", result["status"])
        find.assert_called_once_with(
            "manual-c2a@example.test",
            expected_backend="fixture-c2a-backend",
            checkpoint=find.call_args.kwargs["checkpoint"],
        )
        update.assert_called_once()
        self.assertEqual("c2a-account-17", update.call_args.args[0])
        self.assertEqual(self.local_token, update.call_args.args[1])
        self.assertEqual("fixture-c2a-backend", update.call_args.kwargs["expected_backend"])
        self.assertTrue(callable(update.call_args.kwargs["checkpoint"]))
        self.assertEqual(
            client.SafeMutationPolicy("fixture-c2a-backend"),
            update.call_args.kwargs["safe_mutation_policy"],
        )
        run = operation.get_run(queued["run_id"])
        self.assertEqual("success", run["status"])
        self.assertEqual("confirmed", run["data"]["remote_receipt"]["receipt_state"])
        self.assertTrue(run["data"]["remote_receipt"]["detail"]["remote_result_confirmed"])
        self.assertNotIn(self.local_token, str(run))

    def test_expired_or_missing_local_at_never_calls_c2a(self):
        cases = (
            ("expired", {"token_expired": True}, None, "c2a_local_at_expired"),
            ("missing", None, "", "c2a_local_at_missing"),
        )
        for name, claims, replacement, code in cases:
            with self.subTest(name=name):
                queued = self.queue()
                account = db.get_account(self.account_id)
                if replacement is not None:
                    account = {**account, "access_token": replacement}
                with patch.object(manual_sync.db, "get_account", return_value=account), patch.object(
                    manual_sync, "token_claims", return_value=claims or {}
                ), patch.object(client, "find_unique_account") as find, patch.object(
                    client, "update_account_access_token"
                ) as update:
                    self.assertFalse(self.execute(queued)["ok"])
                find.assert_not_called()
                update.assert_not_called()
                run = operation.get_run(queued["run_id"])
                self.assertEqual("failed", run["status"])
                self.assertEqual(code, run["result_summary"]["error_code"])

    def test_unverified_or_mismatched_local_at_never_calls_c2a(self):
        cases = (
            ("malformed", "not-a-jwt", "c2a_local_at_unverified"),
            ("malformed_payload", "eyJhbGciOiJ0ZXN0In0.W10.signature", "c2a_local_at_unverified"),
            ("no_exp", fixture_token({"https://api.openai.com/profile": {"email": "manual-c2a@example.test"}}), "c2a_local_at_unverified"),
            ("no_email", fixture_token({"exp": int(time.time()) + 3600}), "c2a_local_at_unverified"),
            ("bad_exp", fixture_token({"exp": 10 ** 100, "https://api.openai.com/profile": {"email": "manual-c2a@example.test"}}), "c2a_local_at_unverified"),
            ("wrong_email", fixture_token({"exp": int(time.time()) + 3600, "https://api.openai.com/profile": {"email": "other@example.test"}}), "c2a_local_at_identity_mismatch"),
        )
        for name, token, code in cases:
            with self.subTest(name=name):
                queued = self.queue()
                account = {**db.get_account(self.account_id), "access_token": token}
                with patch.object(manual_sync.db, "get_account", return_value=account), patch.object(
                    client, "find_unique_account"
                ) as find, patch.object(client, "update_account_access_token") as update:
                    self.assertFalse(self.execute(queued)["ok"])
                find.assert_not_called()
                update.assert_not_called()
                run = operation.get_run(queued["run_id"])
                self.assertEqual(code, run["result_summary"]["error_code"])

    def test_update_timeout_is_not_replayed_and_requires_manual_reconciliation(self):
        queued = self.queue()
        timeout = client.C2AError("update_account", "c2a_timeout", "C2A 请求超时")
        with patch.object(client, "find_unique_account", return_value=self.remote_account()), patch.object(
            client, "update_account_access_token", side_effect=timeout
        ) as update, patch.object(manual_sync.time, "sleep") as sleep:
            self.assertFalse(self.execute(queued)["ok"])

        update.assert_called_once()
        sleep.assert_not_called()
        task = operation.get_task(queued["task_id"])
        self.assertEqual("attention_required", task["status"])
        self.assertEqual("c2a_timeout", task["result_summary"]["error_code"])
        run = operation.get_run(queued["run_id"])
        self.assertEqual("c2a_update", run["result_summary"]["stage"])
        self.assertEqual("unknown", run["data"]["remote_receipt"]["receipt_state"])
        self.assertTrue(run["result_summary"]["reconcile_required"])
        from core.operations.errors import classify_task_error
        projection = classify_task_error(
            task.get("error") or "C2A 请求超时", task_type=manual_sync.TASK_TYPE,
            result_summary=run["result_summary"], task_status=task["status"],
        )
        self.assertIn("远端结果待确认", projection["summary"])
        self.assertNotIn("未更新远端账号", projection["summary"])
        retried = task_gateway.default_operation_retry(task)
        self.assertTrue(retried["accepted"])
        self.assertNotEqual(queued["run_id"], retried["run_id"])

    def test_explicit_remote_rejection_records_rejected_receipt_and_fails(self):
        queued = self.queue()
        rejected = client.C2AError("update_account", "c2a_update_rejected", "C2A 拒绝更新")
        with patch.object(client, "find_unique_account", return_value=self.remote_account()), patch.object(
            client, "update_account_access_token", side_effect=rejected
        ) as update:
            self.assertFalse(self.execute(queued)["ok"])

        update.assert_called_once()
        run = operation.get_run(queued["run_id"])
        self.assertEqual("failed", run["status"])
        self.assertEqual("c2a_update_rejected", run["result_summary"]["error_code"])
        self.assertEqual("rejected", run["data"]["remote_receipt"]["receipt_state"])

    def test_unsafe_c2a_policy_blocks_update_before_remote_intent(self):
        queued = self.queue()
        blocked = client.C2AError(
            "c2a_safety",
            "c2a_remote_auto_removal_enabled",
            "C2A 自动移除异常或限流账号已开启，未更新远端账号",
        )
        with patch.object(client, "verify_safe_mutation_policy", side_effect=blocked), patch.object(
            client, "find_unique_account"
        ) as find, patch.object(client, "update_account_access_token") as update:
            self.assertFalse(self.execute(queued)["ok"])

        find.assert_called_once()
        update.assert_not_called()
        run = operation.get_run(queued["run_id"])
        self.assertEqual("failed", run["status"])
        self.assertEqual("c2a_remote_auto_removal_enabled", run["result_summary"]["error_code"])
        self.assertNotIn("remote_intent", run["data"])

    def test_backend_change_does_not_lookup_or_update_remote_account(self):
        queued = self.queue()
        with patch.object(client, "configured_backend_identity", return_value="changed-c2a-backend"), patch.object(
            client, "find_unique_account"
        ) as find, patch.object(client, "update_account_access_token") as update:
            self.assertFalse(self.execute(queued)["ok"])

        find.assert_not_called()
        update.assert_not_called()
        run = operation.get_run(queued["run_id"])
        self.assertEqual("failed", run["status"])
        self.assertEqual("c2a_backend_changed", run["result_summary"]["error_code"])
