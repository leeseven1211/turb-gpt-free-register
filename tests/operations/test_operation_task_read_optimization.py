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

    def test_facets_scan_the_task_relation_once(self):
        # Identify the actual facet query by its result columns, so this checks
        # the PostgreSQL plan used by list_tasks regardless of SQL formatting.
        import psycopg

        plans = []
        execute = psycopg.Cursor.execute

        def trace(cursor, statement, params=None, **kwargs):
            result = execute(cursor, statement, params, **kwargs)
            if [column.name for column in cursor.description or ()] == ["facet", "value", "count"]:
                with cursor.connection.cursor() as probe:
                    execute(probe, "EXPLAIN (FORMAT JSON) " + statement, params)
                    plans.append(probe.fetchone()["QUERY PLAN"][0]["Plan"])
            return result

        with patch.object(psycopg.Cursor, "execute", trace):
            operation_task_store.list_tasks(public_status=True)
        self.assertEqual(1, len(plans))
        scans = 0
        while plans:
            node = plans.pop()
            scans += node.get("Relation Name") == "operation_tasks"
            plans.extend(node.get("Plans", ()))
        self.assertEqual(1, scans)

    def test_public_facets_follow_the_winning_historical_run(self):
        table = operation_task_store._table
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            # The two independent historical sources deliberately share ID 77.
            cur.execute(f"""INSERT INTO {table('account_action_tasks')}
                (id,task_uuid,task_type,trigger,status,queued_at)
                VALUES (77,'account-77','imported','test','pending','2026-10-01T01:00:00Z')""")
            cur.execute(f"""INSERT INTO {table('registration_jobs')}
                (id,job_uuid,status,created_at,updated_at,data) VALUES
                (77,'job-77','success','2026-10-01T00:00:00Z','2026-10-01T00:00:00Z','{{}}')""")
            cur.execute(f"""INSERT INTO {table('operation_tasks')}
                (id,task_uuid,source_system,source_id,task_type,target_type,requested_action,
                 status,target_status,created_at,data) VALUES
                (1,'account','account_action_tasks','77','imported','none','read','failed','ready','2020-01-01Z','{{}}'),
                (2,'job','registration_chains','77','imported','none','read','failed','attention_required','2020-01-01Z','{{}}'),
                (3,'empty','native_operations','3','native','none','read','running','','2030-01-01Z','{{}}'),
                (4,'hidden','native_operations','4','hidden','none','read','stopped','ready',
                 '2030-01-01Z','{{"deleted_by_user":true}}')""")
            cur.execute(f"""INSERT INTO {table('operation_runs')}
                (id,run_uuid,task_id,run_no,source_system,source_id,status,data,result_summary) VALUES
                (11,'account-old',1,1,'account_action_tasks','77','failed','{{}}',NULL),
                (12,'account-new',1,2,'native_operations','12','failed','{{}}',NULL),
                (21,'job-overlay',2,1,'registration_jobs','77','attention_required',
                 '{{"completion_handoff":true}}','{{"completion_handoff":true,"requested_status":"partial_success"}}')""")
            cur.execute(f"UPDATE {table('operation_tasks')} SET last_run_id=12 WHERE id=1")

        response = operation_task_store.list_tasks(public_status=True, task_type="imported", status="queued")
        self.assertEqual(1, response["total"])
        self.assertEqual([(1, 11)], [(row["id"], row["last_run_id"]) for row in response["items"]])
        self.assertEqual([{"value": "partial_success", "count": 1}, {"value": "queued", "count": 1}],
                         response["facets"]["status"])
        self.assertEqual([{"value": "2", "count": 1}], response["facets"]["run_count"])
        self.assertEqual([{"value": "ready", "count": 1}], response["facets"]["target_status"])

        all_rows = operation_task_store.list_tasks(public_status=True, page_size=1, page=2)
        self.assertEqual(3, all_rows["total"])
        self.assertEqual([1], [row["id"] for row in all_rows["items"]])
        self.assertEqual([{"value": value, "count": 1} for value in ("0", "1", "2")],
                         all_rows["facets"]["run_count"])
        self.assertEqual([{"value": "partial_success", "count": 1}, {"value": "ready", "count": 1}],
                         all_rows["facets"]["target_status"])

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
