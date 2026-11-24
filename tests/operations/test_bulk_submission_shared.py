from __future__ import annotations

from core.storage import postgres
from core.storage.operations import bulk_submission, schema
from core.storage.operations import common
from tests.support_pg import PostgresTestCase
from psycopg.rows import dict_row
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch


class SharedBulkSubmissionTests(PostgresTestCase):
    def test_create_specs_is_collection_idempotent_and_preserves_order(self):
        schema.reset_operation_ready()
        schema.init_operation_schema()
        with postgres.connect() as conn:
            first = bulk_submission.create_specs([
                {
                    "task_type": "plan_check", "account_id": 7, "email": "a@example.test",
                    "source_id": "bulk-test:7", "trigger": "manual_bulk",
                    "resource_family": "openai_interactive", "data": {"timezone_offset_min": "-"},
                },
                {
                    "task_type": "live_check", "account_id": 8, "email": "b@example.test",
                    "source_id": "bulk-test:8", "trigger": "manual_bulk",
                    "resource_family": "openai_interactive", "data": {},
                },
            ], conn=conn)
        self.assertEqual([row["account_id"] for row in first], [7, 8])
        self.assertTrue(all(row["accepted"] and not row["reused"] for row in first))
        with postgres.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_tasks')} WHERE source_id LIKE 'bulk-test:%'")
            self.assertEqual(cur.fetchone()["n"], 2)
            cur.execute(f"""SELECT count(*) AS n FROM {common._table('operation_events')}
                WHERE task_id IN (SELECT id FROM {common._table('operation_tasks')} WHERE source_id LIKE 'bulk-test:%')""")
            self.assertEqual(cur.fetchone()["n"], 2)
            second = bulk_submission.create_specs([
                {
                    "task_type": "plan_check", "account_id": 7, "email": "a@example.test",
                    "source_id": "bulk-test:7", "trigger": "manual_bulk",
                    "resource_family": "openai_interactive", "data": {"timezone_offset_min": "-"},
                },
                {
                    "task_type": "live_check", "account_id": 8, "email": "b@example.test",
                    "source_id": "bulk-test:8", "trigger": "manual_bulk",
                    "resource_family": "openai_interactive", "data": {},
                },
            ], conn=conn)
        self.assertEqual([row["task_id"] for row in second], [row["task_id"] for row in first])
        self.assertTrue(all(row["reused"] for row in second))

    def test_conflicting_identity_duplicate_specs_and_concurrent_source_are_explicit(self):
        schema.reset_operation_ready()
        schema.init_operation_schema()
        spec = {"task_type": "plan_check", "account_id": 7, "email": "a@example.test",
                "source_id": "idempotent-shared", "data": {"mode": "a"}}
        with common._connect() as conn:
            result = bulk_submission.create_specs([spec, spec], conn=conn)
        self.assertEqual(result[0]["task_id"], result[1]["task_id"])
        for changed in (
            {"account_id": 8}, {"task_type": "live_check"}, {"data": {"mode": "b"}},
            {"resource_family": "completion_coordinator"}, {"email": "changed@example.test"},
        ):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "idempotency_key_conflict"):
                with common._connect() as conn:
                    bulk_submission.create_specs([{**spec, **changed}], conn=conn)
        concurrent = {**spec, "source_id": "concurrent-shared", "account_id": None}
        def create():
            with common._connect() as conn:
                return bulk_submission.create_specs([concurrent], conn=conn)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(lambda _: create(), range(2)))
        self.assertEqual(values[0]["task_id"], values[1]["task_id"])
        self.assertEqual(sorted(item["reused"] for item in values), [False, True])

    def test_worker_runtime_data_does_not_change_submission_fingerprint(self):
        schema.reset_operation_ready()
        schema.init_operation_schema()
        spec = {"task_type": "plan_check", "account_id": 7, "email": "a@example.test",
                "source_id": "immutable-submission", "data": {"mode": "a"}}
        with common._connect() as conn:
            first = bulk_submission.create_specs([spec], conn=conn)[0]
            with conn.cursor() as cur:
                cur.execute(f"""UPDATE {common._table('operation_runs')}
                    SET data=data || '{{"remote_intent":{{"synthetic":true}},"failure_context":"synthetic"}}'::jsonb
                    WHERE id=%s""", (first["run_id"],))
                cur.execute(f"""UPDATE {common._table('operation_tasks')}
                    SET data=data || '{{"failure_context":"synthetic"}}'::jsonb WHERE id=%s""", (first["task_id"],))
        with common._connect() as conn:
            replay = bulk_submission.create_specs([spec], conn=conn)[0]
        self.assertTrue(replay["reused"])
        self.assertEqual(replay["task_id"], first["task_id"])
        self.assertEqual(replay["email"], "a@example.test")

    def test_configuration_requires_explicit_allowlist_and_rollback_is_shared(self):
        schema.reset_operation_ready()
        schema.init_operation_schema()
        spec = {"task_type": "live_check", "account_id": None, "source_id": "allowlist"}
        with self.assertRaisesRegex(ValueError, "requires_allowlist"):
            with common._connect() as conn:
                bulk_submission.create_specs([{**spec, "data": {"config_snapshot": {"unlisted": 1}}}], conn=conn)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with common._connect() as conn:
                bulk_submission.create_specs([{
                    **spec, "config_snapshot": {"allowed": 1, "unlisted": 2}, "config_allowlist": ("allowed",),
                }], conn=conn)
                raise RuntimeError("rollback")
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_tasks')} WHERE source_id='allowlist'")
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_shared_primitive_does_not_initialize_schema_inside_locked_transaction(self):
        schema.reset_operation_ready()
        schema.init_operation_schema()
        with patch.object(schema, "init_operation_schema", side_effect=AssertionError("nested initialization")):
            with common._connect() as conn:
                result = bulk_submission.create_specs([{
                    "task_type": "live_check", "account_id": None, "source_id": "no-cold-init",
                }], conn=conn)
        self.assertTrue(result[0]["accepted"])
