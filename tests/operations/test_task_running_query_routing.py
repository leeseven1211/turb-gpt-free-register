"""Offline routing checks for the narrow public running-list optimization."""
from __future__ import annotations

from contextlib import ExitStack
import unittest
from unittest.mock import patch

from core.storage import postgres
from core.storage.operations import store


class TaskRunningQueryRoutingTests(unittest.TestCase):
    def _capture(self, **overrides):
        statements = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query, params=()):
                statements.append((" ".join(str(query).split()), tuple(params)))

            def fetchone(self):
                return {"n": 0}

            def fetchall(self):
                return []

        class Connection(Cursor):
            def cursor(self, **_):
                return Cursor()

        kwargs = {
            "status": "running", "public_status": True, "include_facets": False,
            "page": 1, "page_size": 50,
        }
        kwargs.update(overrides)
        with ExitStack() as stack:
            stack.enter_context(patch.object(
                postgres, "connect", side_effect=AssertionError("offline database checkout forbidden"),
            ))
            stack.enter_context(patch.object(
                postgres, "connect_dedicated", side_effect=AssertionError("offline owner session forbidden"),
            ))
            stack.enter_context(patch.object(
                postgres, "database_url", side_effect=AssertionError("offline database configuration forbidden"),
            ))
            stack.enter_context(patch.object(store._schema, "init_operation_schema"))
            stack.enter_context(patch.object(store._common, "_connect", return_value=Connection()))
            stack.enter_context(patch.object(
                store._common, "_table", side_effect=lambda name: f'"offline"."{name}"',
            ))
            stack.enter_context(patch.object(
                store._common.postgres_store, "qualified",
                side_effect=lambda name: f'"offline"."{name}"',
            ))
            stack.enter_context(patch.object(store, "_attach_plan_failure_summaries"))
            stack.enter_context(patch.object(store._common, "_attach_admission_wait"))
            stack.enter_context(patch.object(store.bulk_execution, "attach_context"))
            response = store.list_tasks(**kwargs)
        self.assertEqual([], response["items"])
        self.assertEqual(0, response["total"])
        return statements

    def test_only_canonical_public_running_count_and_page_use_candidates(self):
        for page, size in ((1, 50), (40, 50), (3, 1)):
            with self.subTest(page=page, size=size):
                statements = self._capture(page=page, page_size=size)
                self.assertEqual(2, len(statements))
                for sql, _ in statements:
                    self.assertIn("running_task_candidates AS MATERIALIZED", sql)
                    self.assertEqual(1, sql.count("running_task_candidates AS MATERIALIZED"))
                self.assertEqual(("running",), statements[0][1])
                self.assertEqual(("running", size, (page - 1) * size), statements[1][1])
                # Paging still carries the exact winning Run identity into
                # the unchanged display reload, never a last-run pointer.
                self.assertIn("r.id AS current_run_id", statements[1][0])
                self.assertIn("WHERE rr.id=selected.current_run_id LIMIT 1", statements[1][0])

    def test_extra_filters_keep_the_existing_query_path(self):
        filters = (
            {"task_type": "live_check"},
            {"source": "native_operations"},
            {"q": "search"},
            {"q": " "},
            {"batch_id": 1},
            {"batch_id": 0},
            {"task_id": "7"},
            {"target": "target"},
            {"target_status": "success"},
            {"batch": "batch"},
            {"run_count": "0"},
            {"stage": "preflight"},
            {"created_from": "2026-01-01"},
            {"created_to": "2026-12-31"},
            {"result": "marker"},
        )
        for override in filters:
            with self.subTest(override=override):
                for sql, _ in self._capture(**override):
                    self.assertNotIn("running_task_candidates", sql)

    def test_internal_facets_and_other_statuses_keep_the_existing_query_path(self):
        boundaries = (
            {"public_status": False},
            {"include_facets": True},
            {"status": ""},
            {"status": "queued"},
            {"status": "waiting"},
            {"status": "stopping"},
            {"status": "RUNNING"},
            {"status": " running "},
        )
        for override in boundaries:
            with self.subTest(override=override):
                for sql, _ in self._capture(**override):
                    self.assertNotIn("running_task_candidates", sql)


if __name__ == "__main__":
    unittest.main()
