"""Captured business reads use initialized tables despite an unrelated ready cache."""
from contextlib import nullcontext
import os
from unittest import TestCase
from unittest.mock import MagicMock, patch
import uuid

import psycopg

from core.operations.settlement_contracts import SettlementDomain
from core.storage import postgres, records
from core.storage.operations import common, legacy_task_store, registration_completion, runtime, store
from tests.support_pg import PostgresTestCase


def account_row():
    return {
        "id": 7, "email": "captured@example.test", "deactivated": False,
        "data": {
            "access_token": "fixture-token",
            "extra_json": {"account_password": "fixture-confirmed", "account_password_state": "confirmed"},
        },
    }


def parent_row():
    return {
        "id": 22, "task_id": 11, "last_run_id": 22, "source_id": "10",
        "task_type": "registration_resume", "resolved_account_id": 7,
        "resolved_batch_id": None, "status": "waiting", "error_message": None,
        "data": {"completion_handoff": {"task_id": 33}}, "result_summary": {},
    }


class CapturedRecordReadUnitTests(TestCase):
    domain = SettlementDomain("postgresql://unit.invalid/not-contacted",
                              "test_captured_operation", "test_captured_business", "offline-domain")

    def test_lease_acquisition_uses_its_borrowed_cursor_without_record_initialization(self):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [
            {"status": "running", "account_id": 7, "resource_family": "registration_completion",
             "data": {"registration_completion": True, "steps": ["password"]}},
            account_row(), {"lease_token": "fixture-lease"},
        ]
        with common.settlement_scope(self.domain), patch.object(
            common, "_connect", return_value=nullcontext(conn),
        ) as connect, patch.object(records, "_READY_KEY", "another-domain"), patch.object(
            records, "init", side_effect=AssertionError("captured read attempted record migration"),
        ) as initialize:
            token = runtime.acquire_account_lease(7, 33)
        self.assertEqual("fixture-lease", token)
        initialize.assert_not_called()
        self.assertEqual(1, connect.call_count)
        self.assertEqual(1, conn.cursor.call_count)
        queries = [str(call.args[0]) for call in cur.execute.call_args_list]
        self.assertTrue(any('"test_captured_business"."registered_accounts"' in query for query in queries))
        self.assertFalse(any(query.lstrip().upper().startswith(("CREATE", "ALTER")) for query in queries))

    def test_registration_reconcile_never_initializes_or_borrows_another_connection(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            parent_row(), {"id": 10, "status": "success", "data": {}}, {"last_run_id": 22},
            {"id": 33, "run_id": 34, "task_type": "password_setup", "status": "success",
             "completed_at": None, "error_message": None},
            account_row(),
        ]
        with common.settlement_scope(self.domain), patch.object(records, "_READY_KEY", "another-domain"), patch.object(
            records, "init", side_effect=AssertionError("captured read attempted record migration"),
        ) as initialize, patch.object(common, "_connect") as connect, patch.object(postgres, "connect") as borrow:
            result = registration_completion.reconcile(cur, 22)
        self.assertEqual({"parent_task_id": 11, "status": "success"}, result)
        initialize.assert_not_called()
        connect.assert_not_called()
        borrow.assert_not_called()
        queries = [str(call.args[0]) for call in cur.execute.call_args_list]
        for name in ("registration_jobs", "registered_accounts"):
            self.assertTrue(any(f'"test_captured_business"."{name}"' in query for query in queries))

    def test_ordinary_registration_reconcile_keeps_the_record_owner_read_path(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            parent_row(), {"last_run_id": 22},
            {"id": 33, "run_id": 34, "task_type": "password_setup", "status": "success",
             "completed_at": None, "error_message": None},
        ]
        with patch.object(records, "get_row", side_effect=[
            {"id": 10, "status": "success"}, records.merge_row(records.ACCOUNTS, account_row()),
        ]) as read:
            result = registration_completion.reconcile(cur, 22)
        self.assertEqual("success", result["status"])
        self.assertEqual([records.JOBS, records.ACCOUNTS], [call.args[0] for call in read.call_args_list])
        self.assertTrue(all(call.kwargs["conn"] is cur.connection for call in read.call_args_list))


class CapturedRecordReadPostgresTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        store.reset_ready()
        store.init()

    def test_locked_account_and_registration_reconcile_survive_ready_cache_and_ambient_drift(self):
        account_id = records.insert_row(records.ACCOUNTS, {
            **account_row(), "email": f"captured-{uuid.uuid4().hex}@example.test",
        })
        job_id = records.insert_row(records.JOBS, {"job_type": "registration_resume", "status": "success"})
        child = store.create_runtime_task(
            task_type="password_setup", account_id=account_id, email="captured@example.test",
            trigger="test", source_system="webui_runtime", resource_family="registration_completion",
            data={"registration_completion": True, "steps": ["password"]},
        )
        with store._connect() as conn, conn.cursor() as cur:
            unique = uuid.uuid4().hex
            cur.execute(f"""INSERT INTO {store._table('operation_tasks')}
                (task_uuid,source_system,source_id,task_type,target_type,requested_action,status,account_id)
                VALUES (%s,'registration_chains',%s,'registration_resume','account','registration_resume','waiting',%s)
                RETURNING id""", (unique, unique, account_id))
            parent_id = cur.fetchone()["id"]
            cur.execute(f"""INSERT INTO {store._table('operation_runs')}
                (run_uuid,task_id,run_no,source_system,source_id,status,data)
                VALUES (%s,%s,1,'registration_jobs',%s,'waiting',%s::jsonb) RETURNING id""",
                (unique, parent_id, str(job_id), common._json({"completion_handoff": {"task_id": child["id"]}})))
            parent_run_id = cur.fetchone()["id"]
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
                        (parent_run_id, parent_id))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='running' WHERE id=%s",
                        (child["run"]["id"],))
        domain = SettlementDomain(postgres.database_url(), self.schema, self.schema, "test-captured")
        queries = []
        execute = psycopg.Cursor.execute

        def traced(cursor, query, *args, **kwargs):
            queries.append(str(query))
            return execute(cursor, query, *args, **kwargs)

        with patch.dict(os.environ, {"TURB_DB_SCHEMA": "test_unrelated_domain",
                                    "OPERATION_TASK_DB_SCHEMA": "test_unrelated_domain"}), \
             patch.object(records, "_READY_KEY", "another-domain"), \
             patch.object(records, "init", side_effect=AssertionError("captured read attempted record migration")), \
             patch.object(psycopg.Cursor, "execute", traced), common.settlement_scope(domain):
            token = runtime.acquire_account_lease(account_id, child["run"]["id"])
            self.assertTrue(token)
            with store._connect() as conn, conn.cursor() as cur:
                # Match settlement's already-held business/account lock.
                cur.execute(f"SELECT id FROM {postgres.qualified(records.ACCOUNTS.name)} WHERE id=%s FOR UPDATE",
                            (account_id,))
                cur.fetchone()
                result = runtime.finish_run(
                    child["run"]["id"], status="success", lease_token=token, _settlement_conn=conn,
                )
                self.assertEqual("success", result["status"])
                cur.execute(f"SELECT status FROM {store._table('operation_tasks')} WHERE id=%s", (parent_id,))
                self.assertEqual("success", cur.fetchone()["status"])
                cur.execute(f"SELECT count(*) AS n FROM {store._table('account_operation_leases')} WHERE run_id=%s",
                            (child["run"]["id"],))
                self.assertEqual(0, cur.fetchone()["n"])
        self.assertFalse(any(query.lstrip().upper().startswith(("CREATE", "ALTER")) for query in queries))
        self.assertTrue(all("test_unrelated_domain" not in query for query in queries))
