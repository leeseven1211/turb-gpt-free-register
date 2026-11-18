"""Regression coverage for the task-center read-only query plan."""

from unittest.mock import patch

from core import account_task_store, operation_task_store
from core.storage.operations import common as operation_common
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

    def test_current_page_still_prefers_older_active_run_over_newer_terminal(self):
        task = operation_task_store.create_runtime_task(
            task_type="read-active-priority", account_id=None, email="active-priority@example.test")
        active_id = task["run"]["id"]
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {operation_task_store._table('operation_runs')}
                (run_uuid,task_id,run_no,source_system,source_id,status)
                VALUES ('read-newer-terminal',%s,2,'native_operations','read-newer-terminal','failed') RETURNING id""", (task["id"],))
            newer_id = cur.fetchone()["id"]
            cur.execute(f"UPDATE {operation_task_store._table('operation_tasks')} SET last_run_id=%s WHERE id=%s", (newer_id,task["id"]))
        listed = operation_task_store.list_tasks(page_size=10, include_facets=False)
        item = next(value for value in listed["items"] if value["id"] == task["id"])
        self.assertEqual(active_id, item["last_run_id"])
        self.assertEqual("queued", item["status"])
        self.assertEqual(2, item["run_count"])

    def test_source_identity_gate_preserves_collisions_missing_rows_and_nulls(self):
        # Both legacy sources may have the same numeric ID. A missing row in
        # the requested source must never borrow fields from the other source.
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {operation_task_store._table('account_action_tasks')}
                    (id,task_uuid,task_type,trigger,status,queued_at,error)
                    VALUES (77,'read-source-77','read-source','test','failed',
                            '2026-10-01T01:00:00Z','account-error'),
                           (88,'read-source-88','read-source','test','success',
                            '2026-10-01T01:00:00Z','wrong-source-error')"""
            )
            cur.execute(
                f"""INSERT INTO {operation_task_store._table('registration_jobs')}
                    (id,job_uuid,created_at,updated_at,status,data)
                    VALUES (77,'read-job-77','2026-10-01T00:00:00Z',
                            '2026-10-01T00:00:00Z','pending',
                            '{{"error_message":"registration-error"}}'::jsonb),
                           (99,'read-job-99','','2026-10-01T00:00:00Z',NULL,'{{}}')"""
            )
            run_rows = """FROM (VALUES
                (1,'registration_jobs','77','success','probe','raw-registration'),
                (2,'account_action_tasks','77','running','probe','raw-account'),
                (3,'native_operations','77','waiting','probe','raw-native'),
                (4,'registration_jobs','88','waiting','probe','raw-missing'),
                (5,'registration_jobs','99','running','probe','raw-null-status'),
                (6,NULL,'77','waiting','probe','raw-null-source'),
                (7,'registration_jobs',NULL,'failed','probe','raw-null-id')
            ) value(id,source_system,source_id,status,progress_stage,error_message)
            CROSS JOIN LATERAL (
                SELECT value.*,NULL::timestamptz AS started_at,NULL::timestamptz AS completed_at
            ) rr"""
            fields = (
                "effective_status", "effective_progress_stage", "effective_error_message",
                "effective_created_at_sort",
            )
            rows_by_shape = []
            for selected in (None, fields):
                cur.execute(
                    f"SELECT rr.id,{operation_common._compatibility_run_projection_sql(fields=selected)} "
                    f"{run_rows} {operation_common._compatibility_run_joins_sql()} ORDER BY rr.id"
                )
                rows_by_shape.append([dict(row) for row in cur.fetchall()])
        full, narrow = rows_by_shape
        self.assertEqual(
            [{key: row[key] for key in ("id", *fields)} for row in full], narrow,
        )
        self.assertEqual(
            ["queued", "failed", "waiting", "waiting", None, "waiting", "failed"],
            [row["effective_status"] for row in narrow],
        )
        self.assertEqual(
            ["queued", "complete", "probe", "probe", "probe", "probe", "complete"],
            [row["effective_progress_stage"] for row in narrow],
        )
        self.assertEqual(
            ["registration-error", "account-error", "raw-native", "raw-missing", None,
             "raw-null-source", "raw-null-id"],
            [row["effective_error_message"] for row in narrow],
        )
        self.assertTrue(narrow[0]["effective_created_at_sort"])
        self.assertTrue(narrow[1]["effective_created_at_sort"])
        self.assertTrue(all(row["effective_created_at_sort"] is None for row in narrow[2:]))

    def test_filters_and_facets_match_baseline_sql_for_mixed_terminal_and_active_tasks(self):
        for index in range(8):
            task = operation_task_store.create_runtime_task(task_type="plan_check" if index % 2 else "live_check",
                account_id=None, email=f"read-mixed-{index}@example.test", trigger="read-fixture")
            if index % 3:
                operation_task_store.finish_run(task["run"]["id"], status="success" if index % 2 else "failed",
                                                result_summary={"marker": f"fixture-{index}"})
            if index % 4 == 0:
                operation_task_store.finish_run(task["run"]["id"], status="failed")
                operation_task_store.retry_runtime_task(task["id"])
        for filters in ({}, {"status": "queued"}, {"status": "success"}, {"stage": "complete"},
                        {"task_type": "plan_check", "status": "success"}, {"run_count": "2"},
                        {"q": "read-mixed"}, {"result": "fixture"}, {"target": "mixed-2"},
                        {"created_from": "2020-01-01", "created_to": "2099-01-01"}):
            with self.subTest(filters=filters):
                expected = self._reference_list(filters)
                actual = operation_task_store.list_tasks(page_size=3, **filters)
                self.assertEqual(expected["total"], actual["total"])
                self.assertEqual(expected["facets"], actual["facets"])
                keys = ("id", "last_run_id", "status", "run_count", "current_stage")
                self.assertEqual([[item.get(key) for key in keys] for item in expected["items"]],
                                 [[item.get(key) for key in keys] for item in actual["items"]])

    def _reference_list(self, filters):
        """独立按旧全集合SQL计算预期，测试不依赖Git历史或当前页快捷分支。"""
        query = operation_task_store._operation_task_query_base(include_current_run=True, include_run_count=True)
        count_expression = "COALESCE(run_counts.run_count,0)"
        where, params = operation_task_store._operation_task_where(**filters, run_count_expression=count_expression)
        clause = " WHERE " + " AND ".join(where)
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n {query}{clause}", params)
            total = cur.fetchone()["n"]
            cur.execute(f"SELECT t.id,r.id AS last_run_id,COALESCE(r.effective_status,t.status) AS status,"
                        f"{count_expression} AS run_count,COALESCE(r.effective_progress_stage,t.current_stage) AS current_stage "
                        f"{query}{clause} ORDER BY COALESCE(r.effective_created_at_sort,t.created_at) DESC,t.id DESC LIMIT 3", params)
            items = [dict(row) for row in cur.fetchall()]
            facets = {}
            for name, expression in (("task_type", "t.task_type"), ("status", "COALESCE(r.effective_status,t.status)"),
                ("target_status", "t.target_status"), ("stage", "LOWER(COALESCE(r.effective_progress_stage,CASE WHEN r.effective_status='queued' THEN 'queued' ELSE t.current_stage END,''))"),
                ("run_count", f"CASE WHEN {count_expression}>=4 THEN '4+' ELSE CAST({count_expression} AS TEXT) END")):
                predicates, values = operation_task_store._operation_task_where(**filters, exclude=name, run_count_expression=count_expression)
                predicates.append(f"NULLIF({expression},'') IS NOT NULL")
                cur.execute(f"SELECT {expression} AS value,COUNT(*) AS count {query} WHERE {' AND '.join(predicates)} GROUP BY 1 ORDER BY 1", values)
                facets[name] = [{"value": str(row["value"]), "count": int(row["count"]),
                                 **({"label": operation_task_store.stage_label(row["value"])} if name == "stage" else {})} for row in cur.fetchall()]
        return {"total": total, "items": items, "facets": facets}
