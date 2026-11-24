from __future__ import annotations

from core.storage import postgres
from core.storage.operations import bulk_submission, schema
from core.storage.operations import common
from tests.support_pg import PostgresTestCase
from psycopg.rows import dict_row


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
