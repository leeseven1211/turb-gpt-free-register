from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from core.operations.contracts import BulkItemResult
from core.storage import postgres, records as rs
from core.storage.accounts import bulk_mutations as mutations
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountBulkMutationTests(PostgresTestCase):
    def setUp(self):
        self.seed(rs.ACCOUNTS, [
            {"id": 1, "email": "first@example.test", "access_token": "synthetic"},
            {"id": 2, "email": "second@example.test", "account_status": "deactivated"},
            {"id": 3, "email": "untouched@example.test"},
        ])
        with rs.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE TABLE IF NOT EXISTS {postgres.qualified('mutation_statements')} (kind TEXT)")
            cur.execute(
                f"CREATE OR REPLACE FUNCTION {postgres.qualified('count_account_mutation')}() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN INSERT INTO "
                f"{postgres.qualified('mutation_statements')} VALUES (TG_OP); RETURN NULL; END $$"
            )
            cur.execute(
                f"CREATE OR REPLACE TRIGGER account_mutation AFTER UPDATE OR DELETE ON {postgres.qualified(rs.ACCOUNTS.name)} "
                f"FOR EACH STATEMENT EXECUTE FUNCTION {postgres.qualified('count_account_mutation')}()"
            )
            cur.execute(f"TRUNCATE {postgres.qualified('mutation_statements')}")

    def statement_count(self, kind):
        with rs.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {postgres.qualified('mutation_statements')} WHERE kind=%s", (kind,))
            return cur.fetchone()["n"]

    def test_archive_uses_one_set_update_and_preserves_input_order(self):
        items = mutations.archive_many([2, 1, 2, 99], True)
        self.assertEqual([(x.key, x.status) for x in items], [(2, "updated"), (1, "updated"), (99, "skipped")])
        self.assertEqual(items[-1].reason_code, "account_not_found")
        self.assertEqual(items[-1].reason, "账号不存在")
        self.assertEqual(self.statement_count("UPDATE"), 1)
        self.assertTrue(rs.get_row(rs.ACCOUNTS, 1)["archived"])
        self.assertTrue(rs.get_row(rs.ACCOUNTS, 2)["archived"])
        self.assertFalse(rs.get_row(rs.ACCOUNTS, 3)["archived"])

    def test_note_updates_selected_rows_once_and_preserves_other_facts(self):
        items = mutations.update_note_many([1, 2, 1, 99], "reviewed")
        self.assertEqual([x.key for x in items if x.status == "updated"], [1, 2])
        self.assertEqual(self.statement_count("UPDATE"), 1)
        self.assertEqual(rs.get_row(rs.ACCOUNTS, 1)["note"], "reviewed")
        self.assertEqual(rs.get_row(rs.ACCOUNTS, 1)["access_token"], "synthetic")
        self.assertEqual(rs.get_row(rs.ACCOUNTS, 2)["account_status"], "deactivated")
        self.assertNotEqual(rs.get_row(rs.ACCOUNTS, 3).get("note"), "reviewed")

    def test_delete_removes_each_selected_account_once(self):
        items = mutations.delete_many([2, 1, 2, 99])
        self.assertEqual([(x.key, x.status) for x in items], [(2, "updated"), (1, "updated"), (99, "skipped")])
        self.assertEqual(self.statement_count("DELETE"), 1)
        self.assertIsNone(rs.get_row(rs.ACCOUNTS, 1))
        self.assertIsNone(rs.get_row(rs.ACCOUNTS, 2))
        self.assertIsNotNone(rs.get_row(rs.ACCOUNTS, 3))

    def test_malformed_numeric_targets_skip_without_failing_valid_members(self):
        items = mutations.archive_many([1, "01", "1.0", "9" * 5000], True)
        self.assertEqual([item.status for item in items], ["updated", "skipped", "skipped", "skipped"])
        self.assertEqual([item.reason_code for item in items[1:]], ["invalid_target"] * 3)
        self.assertEqual(self.statement_count("UPDATE"), 1)

    def test_caller_transaction_rolls_back_the_whole_chunk(self):
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with rs.transaction() as conn:
                mutations.update_note_many([1, 2], "not committed", conn=conn)
                mutations.archive_many([1, 2], True, conn=conn)
                raise RuntimeError("rollback")
        self.assertFalse(rs.get_row(rs.ACCOUNTS, 1)["archived"])
        self.assertNotEqual(rs.get_row(rs.ACCOUNTS, 2).get("note"), "not committed")
        self.assertEqual(self.statement_count("UPDATE"), 0)

    def test_email_invalid_skips_stale_identity_and_updates_linked_resources(self):
        parent_id = rs.insert_row(rs.OUTLOOK_POOL, {"email": "first@example.test", "status": "used"})
        items = mutations.set_email_invalid_many(
            [1, 2, 1, 99], invalid=True, reason="manual evidence",
            expected_emails={1: "first@example.test", 2: "old@example.test", 99: "missing@example.test"},
        )
        self.assertEqual([(x.key, x.status) for x in items], [(1, "updated"), (2, "skipped"), (99, "skipped")])
        self.assertEqual(items[1].reason_code, "account_email_changed")
        self.assertEqual(items[1].reason, "账号邮箱已变更")
        self.assertEqual(self.statement_count("UPDATE"), 1)
        self.assertTrue(rs.get_row(rs.ACCOUNTS, 1)["email_invalid"])
        self.assertTrue(rs.get_row(rs.OUTLOOK_POOL, parent_id)["email_invalid"])
        self.assertEqual(rs.get_row(rs.OUTLOOK_POOL, parent_id)["status"], "used")
        self.assertFalse(rs.get_row(rs.ACCOUNTS, 2)["email_invalid"])
        self.assertEqual(rs.get_row(rs.ACCOUNTS, 2)["account_status"], "deactivated")

    def test_group_clear_preserves_broader_parent_scope(self):
        parent = rs.insert_row(rs.ICLOUD_HIDE_POOL, {
            "email": "parent@example.test", "account_id": "group-4", "status": "used",
        })
        child = rs.insert_row(rs.ACCOUNTS, {"id": 4, "email": "parent+child@example.test", "email_source": "icloud_hide"})
        allocation = rs.insert_row(rs.EMAIL_ADDRESS_ALLOCATIONS, {
            "address": "parent+child@example.test", "address_norm": "parent+child@example.test",
            "source": "icloud_hide", "parent_kind": rs.ICLOUD_HIDE_POOL.name, "parent_id": parent,
            "parent_address": "parent@example.test", "inbox_profile_id": 1, "strategy": "plus_tag",
            "tag": "child", "acquisition_id": "synthetic", "owner_kind": "registration_root",
            "owner_id": "synthetic", "state": "used", "account_id": child,
        })
        mutations.set_email_invalid_many(None, invalid=True, icloud_account_id="group-4")
        mutations.set_email_invalid_many([child], invalid=False)
        self.assertFalse(rs.get_row(rs.ACCOUNTS, child)["email_invalid"])
        self.assertTrue(rs.get_row(rs.ICLOUD_HIDE_POOL, parent)["email_invalid"])
        self.assertTrue(rs.get_row(rs.EMAIL_ADDRESS_ALLOCATIONS, allocation)["email_invalid"])
        self.assertEqual(rs.get_row(rs.EMAIL_ADDRESS_ALLOCATIONS, allocation)["state"], "used")

    def test_group_without_accounts_still_reports_changed_pool_resources(self):
        parent = rs.insert_row(rs.ICLOUD_HIDE_POOL, {
            "email": "unused@example.test", "account_id": "unused-group", "status": "available",
        })
        items = mutations.set_email_invalid_many(None, invalid=True, icloud_account_id="unused-group")
        self.assertEqual([(item.key, item.status) for item in items], [("unused-group", "updated")])
        self.assertEqual(items[0].data["updated_count"], 0)
        self.assertEqual(items[0].data["pool_updated_count"], 1)
        self.assertEqual(items[0].data["account_ids"], [])
        self.assertTrue(rs.get_row(rs.ICLOUD_HIDE_POOL, parent)["email_invalid"])
        self.assertEqual(rs.get_row(rs.ICLOUD_HIDE_POOL, parent)["status"], "available")

    def test_email_invalid_uses_caller_connection_for_all_related_tables(self):
        parent = rs.insert_row(rs.OUTLOOK_POOL, {"email": "first@example.test", "status": "used"})
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with rs.transaction() as conn:
                mutations.set_email_invalid_many([1], invalid=True, conn=conn)
                self.assertTrue(rs.get_row(rs.ACCOUNTS, 1, conn=conn)["email_invalid"])
                self.assertTrue(rs.get_row(rs.OUTLOOK_POOL, parent, conn=conn)["email_invalid"])
                raise RuntimeError("rollback")
        self.assertFalse(rs.get_row(rs.ACCOUNTS, 1)["email_invalid"])
        self.assertFalse(rs.get_row(rs.OUTLOOK_POOL, parent).get("email_invalid", False))

    def test_email_invalid_route_command_executes_with_email_snapshot(self):
        from core import account_task_store
        from core.operations import bulk_mutation_worker, task_gateway
        from core.storage.operations import bulk_mutations as commands, store as operation

        with patch.object(account_task_store, "_SCHEMA", self.schema), \
                patch.object(account_task_store, "_READY_KEY", ""), \
                patch.object(task_gateway, "notify_dispatch"):
            operation.reset_ready()
            mutations.register_handlers()
            client = create_app(auth_code="synthetic-auth").test_client()
            response = client.post("/api/accounts/email-invalid-bulk", json={
                "account_ids": [1, "1", 2, "bad", None, {}], "invalid": True, "reason": "manual evidence",
                "expected_emails": {"1": "first@example.test", "2": "stale@example.test"},
            }, headers={"X-Auth-Code": "synthetic-auth", "X-Account-Request-Key": "abcdef1234567890abcdef1234567890"})
            self.assertEqual(response.status_code, 202)
            submitted = response.get_json()
            command = commands.get_command(submitted["command_id"])
            self.assertEqual(command["parameters"]["expected_emails"], {
                "1": "first@example.test", "2": "stale@example.test",
            })
            run = operation.claim_run(submitted["run_id"], execution_id="synthetic-worker", worker_pid=123)
            result = bulk_mutation_worker._handle_claimed_bulk_mutation(
                task_gateway.OperationHandlerContext(run, execution_id="synthetic-worker"),
            )
            self.assertEqual(result.summary["updated_count"], 1)
            self.assertEqual(result.summary["skipped_count"], 4)
            persisted = commands.get_command_result(submitted["command_id"])
            self.assertEqual(persisted["requested_count"], 6)
            self.assertEqual(persisted["duplicate_count"], 1)
            self.assertEqual(persisted["skipped_count"], 4)
            self.assertEqual(persisted["items"][1]["reason_code"], "account_email_changed")
        self.assertTrue(rs.get_row(rs.ACCOUNTS, 1)["email_invalid"])
        self.assertFalse(rs.get_row(rs.ACCOUNTS, 2)["email_invalid"])

    def test_archive_command_keeps_duplicate_invalid_and_missing_receipts_and_conflicts(self):
        from core import account_task_store
        from core.operations import bulk_mutation_worker, task_gateway
        from core.storage.operations import bulk_mutations as commands, store as operation

        with patch.object(account_task_store, "_SCHEMA", self.schema), \
                patch.object(account_task_store, "_READY_KEY", ""), patch.object(task_gateway, "notify_dispatch"):
            operation.reset_ready()
            mutations.register_handlers()
            client = create_app(auth_code="synthetic-auth").test_client()
            headers = {"X-Auth-Code": "synthetic-auth", "X-Account-Request-Key": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}
            targets = [1, "1", "bad", True, None, {}, [], 99]
            response = client.post("/api/accounts/archive-bulk", json={"account_ids": targets}, headers=headers)
            self.assertEqual(response.status_code, 202)
            submitted = response.get_json()
            self.assertIsInstance(submitted["command_id"], str)
            self.assertIsInstance(submitted["task_id"], str)
            self.assertIsInstance(submitted["run_id"], str)
            command = commands.get_command(submitted["command_id"])
            self.assertEqual(command["input_targets"], [1, 1, "bad", True, None, {}, [], 99])
            with rs.transaction() as conn, conn.cursor() as cur:
                cur.execute(f"TRUNCATE {postgres.qualified('mutation_statements')}")
            run = operation.claim_run(int(submitted["run_id"]), execution_id="synthetic-worker", worker_pid=123)
            bulk_mutation_worker._handle_claimed_bulk_mutation(
                task_gateway.OperationHandlerContext(run, execution_id="synthetic-worker"),
            )
            result = commands.get_command_result(submitted["command_id"])
            self.assertEqual(result["requested_count"], 8)
            self.assertEqual(result["duplicate_count"], 1)
            self.assertEqual(result["updated_count"], 1)
            self.assertEqual(result["skipped_count"], 6)
            self.assertEqual(result["failed_count"], 0)
            self.assertEqual([item["reason_code"] for item in result["items"]], [
                None, "invalid_target", "invalid_target", "invalid_target", "invalid_target", "invalid_target", "account_not_found",
            ])
            self.assertEqual(self.statement_count("UPDATE"), 1)
            same = client.post("/api/accounts/archive-bulk", json={"account_ids": targets}, headers=headers)
            self.assertEqual(same.status_code, 202)
            self.assertEqual(same.get_json()["command_id"], submitted["command_id"])
            conflict = client.post("/api/accounts/archive-bulk", json={"account_ids": [2]}, headers=headers)
            self.assertEqual(conflict.status_code, 409)


class AccountBulkRoutesTests(TestCase):
    def setUp(self):
        self.client = create_app(auth_code="synthetic-auth").test_client()
        self.headers = {"X-Auth-Code": "synthetic-auth", "X-Account-Request-Key": "1234567890abcdef1234567890abcdef"}

    def test_single_and_bulk_routes_share_the_same_storage_method(self):
        for action, payload, method, parameters in (
            ("archive", {"archived": False}, "archive_many", {"archived": False}),
            ("note", {"note": "reviewed"}, "update_note_many", {"note": "reviewed"}),
            ("delete", {}, "delete_many", {}),
        ):
            with self.subTest(action=action):
                calls = []

                def apply(ids, **kwargs):
                    calls.append((list(ids), kwargs))
                    return [BulkItemResult(key=1, status="updated", data={"id": 1, "email": "first@example.test"})]

                with patch.object(mutations, method, side_effect=apply):
                    single = self.client.post(f"/api/accounts/1/{action}", json=payload, headers=self.headers)
                    mutations.register_handlers()
                    with patch("core.operations.task_gateway.submit_bulk_mutation") as submit:
                        submit.return_value = {"accepted": True, "task_id": 10, "run_id": 20, "status": "queued"}
                        bulk = self.client.post(f"/api/accounts/{action}-bulk",
                                                json={"account_ids": [1, 1], **payload}, headers=self.headers)
                    from core.operations import bulk_mutation_worker
                    handler = bulk_mutation_worker._HANDLERS[f"account_{action}"]
                    handler.callback((1,), parameters, conn=None)
                self.assertEqual(single.status_code, 200)
                self.assertEqual(bulk.status_code, 202)
                self.assertEqual(len(calls), 2)
                self.assertEqual(calls[0][0], calls[1][0])
                self.assertEqual(bulk.get_json()["task_id"], "10")
                self.assertEqual(submit.call_args.args[0:2], (f"account_{action}", [1, 1]))

    def test_invalid_ids_are_preserved_in_the_submitted_command(self):
        with patch("core.operations.task_gateway.submit_bulk_mutation", return_value={
            "accepted": True, "command_id": 30, "task_id": 10, "run_id": 20,
        }) as submit:
            response = self.client.post("/api/accounts/archive-bulk",
                                        json={"account_ids": [True, 0, 1.5, "bad"]}, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["updated_count"], 0)
        self.assertEqual(submit.call_args.args[1], [True, 0, 1.5, "bad"])
        self.assertEqual(response.get_json()["requested_count"], 4)

    def test_email_invalid_submits_one_command_without_reading_accounts(self):
        with patch("core.operations.task_gateway.submit_bulk_mutation", return_value={
            "accepted": True, "task_id": 11, "run_id": 21, "status": "queued",
        }) as submit, patch("webui.routes.accounts.db.get_account", side_effect=AssertionError("per-account read")):
            response = self.client.post("/api/accounts/email-invalid-bulk", json={
                "account_ids": [1, 1, 2], "invalid": True,
                "expected_emails": {"1": "first@example.test", "2": "second@example.test"},
            }, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(submit.call_args.args[:2], ("account_email_invalid", [1, 1, 2]))
        self.assertEqual(submit.call_args.kwargs["idempotency_key"], "1234567890abcdef1234567890abcdef")
        self.assertEqual(response.get_json()["updated_count"], 0)

    def test_invalid_request_key_returns_client_error_before_submission(self):
        with patch("core.operations.task_gateway.submit_bulk_mutation") as submit:
            response = self.client.post("/api/accounts/note-bulk", json={"account_ids": [1], "note": "reviewed"},
                                        headers={**self.headers, "X-Account-Request-Key": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        submit.assert_not_called()
