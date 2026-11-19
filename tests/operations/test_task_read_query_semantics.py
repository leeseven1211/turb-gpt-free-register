"""PG regressions for filtered pages and shared facet queries.

It has no artifact paths or dynamic baseline-source dependency. The oracle is
literal fixture intent: one near-match per self-excluded facet, known page
order and known persisted facts. It never calls the query's SQL builders to
calculate expected IDs/counts/statuses. Large-scale complete-response equality
against saved-before code remains a separate benchmark responsibility.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from core import account_task_store, operation_task_store
from core.operations import query_service
from core.operations.contracts import OperationQuery
from tests.support_pg import PostgresTestCase


class TaskReadQuerySemanticsTests(PostgresTestCase):
    def setUp(self):
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.schema_patch.start()
        account_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()

    def tearDown(self):
        self.schema_patch.stop()

    def _seed_task(
        self, label, *, task_type="read-facet-alpha", status="waiting",
        target_status="success", stage="probe", runs=1, summary=None,
        task_error=None, hidden=False, created_second=0,
    ):
        """Insert inert facts directly; do not invoke workers or mutate status.

        When there are two Runs, the newest is success while the older remains
        active. The task's last_run_id deliberately points at that terminal Run.
        """
        stamp = f"2026-10-15T00:00:{created_second:02d}+00:00"
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {operation_task_store._table('operation_tasks')}
                    (task_uuid,source_system,source_id,task_type,target_type,
                     requested_action,status,target_status,current_stage,
                     email_snapshot,error_message,created_at,updated_at,data)
                    VALUES (%s,'native_operations',%s,%s,'account','read_test',
                            %s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING id""",
                (f"read-candidate-{label}", label, task_type, status, target_status,
                 stage, f"{label}@example.test", task_error, stamp, stamp,
                 json.dumps({"deleted_by_user": hidden, "synthetic": True})),
            )
            task_id = int(cur.fetchone()["id"])
            run_ids = []
            for run_no in range(1, runs + 1):
                run_status = status if run_no == 1 else "success"
                run_summary = summary if run_no == 1 else {"marker": "newest-terminal-only"}
                cur.execute(
                    f"""INSERT INTO {operation_task_store._table('operation_runs')}
                        (run_uuid,task_id,run_no,source_system,source_id,status,
                         progress_stage,result_summary,next_attempt_at,created_at)
                        VALUES (%s,%s,%s,'native_operations',%s,%s,%s,%s::jsonb,
                                '2099-01-01T00:00:00Z',%s) RETURNING id""",
                    (f"read-candidate-{label}-{run_no}", task_id, run_no,
                     f"{label}:{run_no}", run_status, stage,
                     json.dumps(run_summary) if run_summary is not None else None, stamp),
                )
                run_ids.append(int(cur.fetchone()["id"]))
            if run_ids:
                cur.execute(
                    f"UPDATE {operation_task_store._table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
                    (run_ids[-1], task_id),
                )
        return task_id, run_ids

    def _facets(self, response):
        # Stage labels are a separate presentation contract. Here the literal
        # oracle checks only facet values/counts, including missing/empty lists.
        return {
            name: [(row["value"], row["count"]) for row in rows]
            for name, rows in response["facets"].items()
        }

    def _facts(self):
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {operation_task_store._table('operation_tasks')} ORDER BY id")
            tasks = [dict(row) for row in cur.fetchall()]
            cur.execute(f"SELECT * FROM {operation_task_store._table('operation_runs')} ORDER BY id")
            runs = [dict(row) for row in cur.fetchall()]
        return tasks, runs

    def test_tasks_without_runs_keep_filtered_pages_public_status_and_zero_count(self):
        ids = [self._seed_task(
            f"norun-match-{n}", task_type="read-no-run", status="unknown",
            target_status="unknown", stage=None, runs=0,
            task_error="norun-result", created_second=n,
        )[0] for n in (1, 2, 3)]
        self._seed_task(
            "norun-match-hidden", task_type="read-no-run", status="unknown",
            target_status="unknown", stage=None, runs=0,
            task_error="norun-result", hidden=True, created_second=4,
        )
        before = self._facts()
        kwargs = dict(
            task_type="read-no-run", status="failed", target_status="failed",
            q="norun-match", result="norun-result", run_count="0", page_size=1,
            include_facets=True, include_batches=False,
        )
        response = query_service.list_operations(OperationQuery(page=2, **kwargs))
        self.assertEqual(3, response["total"])
        self.assertEqual([ids[1]], [row["id"] for row in response["items"]])
        row = response["items"][0]
        self.assertEqual("failed", row["status"])
        self.assertEqual("unknown", row["internal_status"])
        self.assertEqual("failed", row["target_status"])
        self.assertEqual("unknown", row["internal_target_status"])
        self.assertIsNone(row["last_run_id"])
        self.assertIsNone(row["result_summary"])
        self.assertEqual(0, row["run_count"])
        expected_facets = {
            "task_type": [("read-no-run", 3)], "status": [("failed", 3)],
            "target_status": [("failed", 3)], "stage": [], "run_count": [("0", 3)],
        }
        self.assertEqual(expected_facets, self._facets(response))
        beyond = query_service.list_operations(OperationQuery(page=4, **kwargs))
        self.assertEqual(3, beyond["total"])
        self.assertEqual([], beyond["items"])
        self.assertEqual(expected_facets, self._facets(beyond))
        self.assertEqual(before, self._facts())

    def test_public_target_and_result_search_use_current_run_summary(self):
        partial_id, partial_runs = self._seed_task(
            "summary-partial", task_type="read-public-target", status="attention_required",
            target_status="unknown", stage="complete",
            summary={"marker": "summary-probe", "requested_status": " PARTIAL_SUCCESS "},
        )
        failed_id, _ = self._seed_task(
            "summary-failed", task_type="read-public-target", status="attention_required",
            target_status="unknown", stage="complete", summary={"marker": "summary-probe"},
        )
        before = self._facts()
        common = dict(q="summary-probe", result="summary-probe", include_batches=False)
        partial = query_service.list_operations(OperationQuery(
            status="partial_success", target_status="partial_success", **common,
        ))
        self.assertEqual(1, partial["total"])
        self.assertEqual([partial_id], [row["id"] for row in partial["items"]])
        self.assertEqual(partial_runs[0], partial["items"][0]["last_run_id"])
        self.assertEqual("partial_success", partial["items"][0]["status"])
        self.assertEqual("partial_success", partial["items"][0]["target_status"])
        self.assertEqual({
            "task_type": [("read-public-target", 1)], "status": [("partial_success", 1)],
            "target_status": [("partial_success", 1)], "stage": [("complete", 1)],
            "run_count": [("1", 1)],
        }, self._facets(partial))
        failed = query_service.list_operations(OperationQuery(status="failed", target_status="failed", **common))
        self.assertEqual(1, failed["total"])
        self.assertEqual([failed_id], [row["id"] for row in failed["items"]])
        empty = query_service.list_operations(OperationQuery(result="marker-does-not-exist", include_batches=False))
        self.assertEqual(0, empty["total"])
        self.assertEqual([], empty["items"])
        self.assertEqual({name: [] for name in ("task_type", "status", "target_status", "stage", "run_count")},
                         self._facets(empty))
        self.assertEqual(before, self._facts())

    def test_each_facet_excludes_only_its_dimension_under_simultaneous_filters(self):
        summary = {"marker": "facet-probe"}
        base_id, base_runs = self._seed_task("facet-base", summary=summary)
        self._seed_task("facet-type", task_type="read-facet-beta", summary=summary)
        self._seed_task("facet-status", status="running", summary=summary)
        self._seed_task("facet-target", target_status="failed", summary=summary)
        self._seed_task("facet-stage", stage="other", summary=summary)
        multi_id, multi_runs = self._seed_task("facet-count", runs=2, summary=summary)
        self._seed_task("facet-hidden", summary=summary, hidden=True)
        before = self._facts()
        kwargs = dict(
            task_type="read-facet-alpha", status="waiting", target_status="success",
            stage="probe", q="facet-probe", result="facet-probe", include_batches=False,
        )
        response = query_service.list_operations(OperationQuery(run_count="1", **kwargs))
        self.assertEqual(1, response["total"])
        self.assertEqual([base_id], [row["id"] for row in response["items"]])
        self.assertEqual(base_runs[0], response["items"][0]["last_run_id"])
        self.assertEqual({
            "task_type": [("read-facet-alpha", 1), ("read-facet-beta", 1)],
            "status": [("running", 1), ("waiting", 1)],
            "target_status": [("failed", 1), ("success", 1)],
            "stage": [("other", 1), ("probe", 1)],
            "run_count": [("1", 1), ("2", 1)],
        }, self._facets(response))
        multi = query_service.list_operations(OperationQuery(run_count="2", **kwargs))
        self.assertEqual(1, multi["total"])
        self.assertEqual([multi_id], [row["id"] for row in multi["items"]])
        row = multi["items"][0]
        self.assertEqual(multi_runs[0], row["last_run_id"])
        self.assertEqual("waiting", row["status"])
        self.assertEqual(summary, row["result_summary"])
        self.assertEqual(2, row["run_count"])
        self.assertEqual(before, self._facts())

    def test_public_running_fast_path_keeps_winner_and_no_run_fallback(self):
        excluded_id, excluded_runs = self._seed_task(
            "running-newer-queued", status="running", runs=2, created_second=1,
        )
        active_id, active_runs = self._seed_task(
            "running-older-active", status="running", runs=2, created_second=2,
        )
        no_run_id, _ = self._seed_task(
            "running-no-run", status="running", runs=0, created_second=3,
        )
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            # Both active Runs participate in winner selection. Newer queued
            # must exclude the older running Run from the running list.
            cur.execute(
                f"UPDATE {operation_task_store._table('operation_runs')} "
                "SET status='queued' WHERE id=%s", (excluded_runs[1],),
            )
            # Task status and last_run_id may point at a newer terminal Run;
            # the older active Run remains the authoritative winning Run.
            cur.execute(
                f"UPDATE {operation_task_store._table('operation_tasks')} "
                "SET status='failed' WHERE id=%s", (active_id,),
            )
        before = self._facts()
        expected = [(no_run_id, None, 0), (active_id, active_runs[0], 2)]
        first = operation_task_store.list_tasks(
            status="running", public_status=True, include_facets=False,
            page=1, page_size=50,
        )
        self.assertEqual(2, first["total"])
        self.assertNotIn(excluded_id, [item["id"] for item in first["items"]])
        self.assertEqual(
            expected,
            [(item["id"], item["last_run_id"], item["run_count"])
             for item in first["items"]],
        )
        self.assertEqual(["running", "running"], [item["status"] for item in first["items"]])
        for page, rows in ((1, expected[:1]), (2, expected[1:]), (3, [])):
            with self.subTest(page=page):
                result = operation_task_store.list_tasks(
                    status="running", public_status=True, include_facets=False,
                    page=page, page_size=1,
                )
                self.assertEqual(2, result["total"])
                self.assertEqual(
                    rows,
                    [(item["id"], item["last_run_id"], item["run_count"])
                     for item in result["items"]],
                )
        self.assertEqual(before, self._facts())
