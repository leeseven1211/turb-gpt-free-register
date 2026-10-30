"""Regression coverage for the task-center read-only query plan."""

from unittest.mock import patch

from core import account_task_store, operation_task_store
from tests.support_pg import PostgresTestCase


class OperationTaskReadOptimizationTests(PostgresTestCase):
    def setUp(self):
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.schema_patch.start()
        account_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()

    def tearDown(self):
        self.schema_patch.stop()

    def test_run_count_facets_and_active_run_selection_keep_their_semantics(self):
        task = operation_task_store.create_runtime_task(
            task_type="read-optimization",
            account_id=901,
            email="read-optimization@example.test",
            trigger="test",
        )
        current_run = task["run"]
        for attempt in range(3):
            operation_task_store.finish_run(
                int(current_run["id"]),
                status="failed",
                error=f"synthetic failure {attempt}",
            )
            current_run = operation_task_store.retry_runtime_task(
                int(task["id"]), trigger=f"retry-{attempt + 1}",
            )

        listed = operation_task_store.list_tasks(page_size=10, task_id=str(task["id"]))

        self.assertEqual(1, listed["total"])
        item = listed["items"][0]
        self.assertEqual(4, item["run_count"])
        self.assertEqual("queued", item["status"])
        self.assertEqual(int(current_run["id"]), int(item["last_run_id"]))
        self.assertEqual(
            [{"value": "4+", "count": 1}],
            listed["facets"]["run_count"],
        )

    def test_each_dependent_filter_builds_all_facets_without_missing_aliases(self):
        task = operation_task_store.create_runtime_task(
            task_type="read-filter-optimization",
            account_id=902,
            email="read-filter-optimization@example.test",
            trigger="test",
        )
        current_run = task["run"]
        for attempt in range(3):
            operation_task_store.finish_run(
                int(current_run["id"]),
                status="failed",
                error=f"synthetic result marker {attempt}",
            )
            current_run = operation_task_store.retry_runtime_task(
                int(task["id"]), trigger=f"retry-{attempt + 1}",
            )
        operation_task_store.finish_run(
            int(current_run["id"]),
            status="failed",
            error="synthetic result marker final",
        )

        filter_cases = (
            ("q", {"q": "read-filter-optimization@example.test"}),
            ("result", {"result": "synthetic result marker final"}),
            ("status", {"status": "failed"}),
            ("stage", {"stage": "complete"}),
            ("run_count", {"run_count": "4+"}),
        )
        for name, filters in filter_cases:
            with self.subTest(filter=name):
                listed = operation_task_store.list_tasks(page_size=10, **filters)
                self.assertEqual(1, listed["total"])
                self.assertEqual(1, len(listed["items"]))
                self.assertEqual(
                    {"task_type", "status", "target_status", "stage", "run_count"},
                    set(listed["facets"]),
                )
