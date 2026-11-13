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

    def test_missing_remote_account_creates_with_current_at_and_confirms_receipt(self):
        queued = self.queue()
        missing = client.C2AError("find_account", "c2a_account_missing", "未找到同邮箱账号")
        with patch.object(client, "find_unique_account", side_effect=missing), patch.object(
            client, "create_account_access_token",
            return_value={"id": "c2a-account-new", "created": True, "backend_identity": "fixture-c2a-backend"},
        ) as create, patch.object(client, "update_account_access_token") as update:
            result = self.execute(queued)

        self.assertTrue(result["ok"])
        self.assertEqual("success", result["status"])
        create.assert_called_once_with(
            "manual-c2a@example.test", self.local_token,
            expected_backend="fixture-c2a-backend",
            checkpoint=create.call_args.kwargs["checkpoint"],
            safe_mutation_policy=client.SafeMutationPolicy("fixture-c2a-backend"),
        )
        update.assert_not_called()
        run = operation.get_run(queued["run_id"])
        self.assertTrue(run["result_summary"]["created"])
        self.assertFalse(run["result_summary"]["updated"])
        self.assertEqual("c2a-account-new", run["result_summary"]["c2a_account_id"])
        self.assertEqual("confirmed", run["data"]["remote_receipt"]["receipt_state"])
        self.assertNotIn(self.local_token, str(run))

    def test_ambiguous_remote_email_never_creates_or_updates(self):
        queued = self.queue()
        ambiguous = client.C2AError("find_account", "c2a_account_ambiguous", "同邮箱存在多条账号")
        with patch.object(client, "find_unique_account", side_effect=ambiguous), patch.object(
            client, "create_account_access_token",
        ) as create, patch.object(client, "update_account_access_token") as update:
            self.assertFalse(self.execute(queued)["ok"])

        create.assert_not_called()
        update.assert_not_called()
        run = operation.get_run(queued["run_id"])
        self.assertEqual("c2a_account_ambiguous", run["result_summary"]["error_code"])
        self.assertNotIn("remote_intent", run["data"])

    def test_create_timeout_can_be_retried_as_update_when_remote_account_now_exists(self):
        queued = self.queue()
        missing = client.C2AError("find_account", "c2a_account_missing", "未找到同邮箱账号")
        timeout = client.C2AError("create_account", "c2a_timeout", "C2A 请求超时")
        with patch.object(client, "find_unique_account", side_effect=missing), patch.object(
            client, "create_account_access_token", side_effect=timeout,
        ) as create, patch.object(manual_sync.time, "sleep") as sleep:
            self.assertFalse(self.execute(queued)["ok"])

        create.assert_called_once()
        sleep.assert_not_called()
        run = operation.get_run(queued["run_id"])
        self.assertEqual("unknown", run["data"]["remote_receipt"]["receipt_state"])
        task = operation.get_task(queued["task_id"])
        retried = task_gateway.default_operation_retry(task)
        self.assertTrue(retried["accepted"])
        with patch.object(client, "find_unique_account", return_value=self.remote_account()), patch.object(
            client, "create_account_access_token",
        ) as create, patch.object(
            client, "update_account_access_token", return_value={"id": "c2a-account-17", "updated": True},
        ) as update:
            result = self.execute(retried)

        self.assertTrue(result["ok"])
        create.assert_not_called()
        update.assert_called_once()
        self.assertEqual("unknown", operation.get_run(queued["run_id"])["data"]["remote_receipt"]["receipt_state"])

    def test_lookup_failure_never_creates_an_account(self):
        queued = self.queue()
        failure = client.C2AError("find_account", "c2a_response_invalid", "账号列表格式无效")
        with patch.object(client, "find_unique_account", side_effect=failure), patch.object(
            client, "create_account_access_token",
        ) as create, patch.object(client, "update_account_access_token") as update:
            self.assertFalse(self.execute(queued)["ok"])

        create.assert_not_called()
        update.assert_not_called()
        run = operation.get_run(queued["run_id"])
        self.assertEqual("failed", run["status"])
        self.assertEqual("c2a_response_invalid", run["result_summary"]["error_code"])
        self.assertNotIn("remote_intent", run["data"])

    def test_deduplicated_import_records_separate_update_request_and_keeps_import_receipt(self):
        missing = client.C2AError("find_account", "c2a_account_missing", "未找到同邮箱账号")
        for failure_code in (None, "c2a_backend_changed", "c2a_update_rejected"):
            with self.subTest(failure_code=failure_code):
                queued = self.queue()
                failure = (
                    client.C2AError("update_account", failure_code, "后续 AT 覆盖失败")
                    if failure_code else None
                )
                with patch.object(client, "find_unique_account", side_effect=missing), patch.object(
                    client, "create_account_access_token",
                    return_value={"id": "c2a-dedup", "created": False, "updated": False},
                ), patch.object(
                    client, "update_account_access_token", side_effect=failure,
                    return_value={"id": "c2a-dedup", "updated": True},
                ) as update:
                    result = self.execute(queued)

                update.assert_called_once()
                self.assertEqual("c2a-dedup", update.call_args.args[0])
                run = operation.get_run(queued["run_id"])
                self.assertTrue(run["result_summary"]["remote_import_confirmed"])
                self.assertEqual("c2a_update_access_token", run["data"]["remote_intent"]["action"])
                self.assertEqual(f"c2a-update:{queued['run_id']}", run["data"]["remote_receipt"]["request_id"])
                events = operation.get_task(queued["task_id"])["events"]
                self.assertTrue(any(
                    event["event_type"] == "remote.receipt_received"
                    and event["detail"].get("request_id") == f"c2a-create:{queued['run_id']}"
                    for event in events
                ))
                if failure_code:
                    self.assertFalse(result["ok"])
                    self.assertEqual("failed", run["status"])
                else:
                    self.assertTrue(result["ok"])
                    self.assertTrue(run["result_summary"]["updated"])
                    self.assertFalse(run["result_summary"]["created"])

    def test_create_rejection_and_unconfirmed_receipt_keep_distinct_remote_states(self):
        missing = client.C2AError("find_account", "c2a_account_missing", "未找到同邮箱账号")
        for code, status, receipt in (
            ("c2a_create_rejected", "failed", "rejected"),
            ("c2a_create_unconfirmed", "attention_required", "unknown"),
        ):
            with self.subTest(code=code):
                queued = self.queue()
                failure = client.C2AError("create_account", code, "C2A 新建未完成")
                with patch.object(client, "find_unique_account", side_effect=missing), patch.object(
                    client, "create_account_access_token", side_effect=failure,
                ):
                    self.assertFalse(self.execute(queued)["ok"])
                run = operation.get_run(queued["run_id"])
                self.assertEqual(status, run["status"])
                self.assertEqual(receipt, run["data"]["remote_receipt"]["receipt_state"])
                self.assertEqual("create", run["result_summary"]["action"])
                self.assertEqual("c2a_update", run["result_summary"]["stage"])

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
        self.assertEqual("C2A 更新请求超时，未收到更新回执", projection["summary"])
        self.assertTrue(projection["reconcile_required"])
        self.assertEqual("unknown", projection["remote_state_impact"])
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
