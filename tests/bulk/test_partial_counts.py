"""历史部分成功计数的真实 PostgreSQL 读取与固定 SQL 次数契约。"""

from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
import uuid

import psycopg
from psycopg.types.json import Jsonb

from core.storage import records
from core.storage.operations import bulk, bulk_common as common, store
from tests.support_pg import PostgresTestCase


class PartialCountsSqlTests(TestCase):
    """固定 generic plan 的范围形状，不启动 PostgreSQL。"""

    def query(self, rows, *, by_round=False, partials=()):
        statements = []

        class Cursor:
            def execute(self, query, params):
                statements.append((" ".join(query.split()), params))

            def fetchall(self):
                return list(partials)

        with patch.object(common, "table", lambda name: '"test_partial"."' + name + '"'):
            result = common.preserve_partial_counts_many(Cursor(), rows, by_round=by_round)
        self.assertEqual(1, len(statements), "范围修正必须仍是单条集合查询")
        return result, *statements[0]

    def test_single_distinct_scope_uses_scalar_even_with_duplicate_rows(self):
        rows = [{"id": 7, "counts": {"attention_required": 2}},
                {"id": 7, "counts": {"attention_required": 2}},
                {"id": 8, "counts": {"success": 1}}]
        original = deepcopy(rows)
        for by_round in (False, True):
            with self.subTest(by_round=by_round):
                result, query, params = self.query(rows, by_round=by_round, partials=[{"scope_id": 7, "n": 1}])
                column = "tr.round_id" if by_round else "tr.batch_id"
                self.assertIn(column + "=%s::bigint", query)
                self.assertNotIn("ANY(", query)
                self.assertEqual((7,), params)
                self.assertEqual([{"attention_required": 1, "partial_success": 1}] * 2 + [{"success": 1}],
                                 [row["counts"] for row in result])
                self.assertEqual(original, rows)

    def test_many_historical_rounds_keep_array_scope_without_parent_scans(self):
        rows = [{"id": n, "counts": {"attention_required": 1}} for n in (7, 9, 7)]
        result, query, params = self.query(rows, by_round=True, partials=[{"scope_id": 9, "n": 1}])
        self.assertIn("tr.round_id=ANY(%s::bigint[])", query)
        self.assertEqual(1, query.count("%s"))
        self.assertEqual({7, 9}, set(params[0]))
        self.assertIn("partial_candidates AS MATERIALIZED", query)
        self.assertNotIn("operation_selection_targets", query)
        self.assertNotIn("operation_batch_controls", query)
        self.assertEqual([{"attention_required": 1}, {"attention_required": 0, "partial_success": 1},
                          {"attention_required": 1}], [row["counts"] for row in result])

    def test_current_batch_scope_keeps_latest_or_initial_membership(self):
        rows = [{"batch_id": n, "counts": {"attention_required": 1}} for n in (7, 9)]
        result, query, params = self.query(rows)
        self.assertIn("tr.batch_id=ANY(%s::bigint[])", query)
        self.assertEqual({7, 9}, set(params[0]))
        self.assertIn('JOIN "test_partial"."operation_selection_targets" root ON root.id=tr.canonical_target_id', query)
        self.assertIn('JOIN "test_partial"."operation_batch_controls" c ON c.batch_id=tr.batch_id', query)
        self.assertIn("tr.round_id=COALESCE(root.latest_requested_round_id,c.initial_round_id)", query)
        self.assertEqual(rows, result)


class PartialCountsTests(PostgresTestCase):
    def setUp(self):
        bulk.reset_ready()
        bulk.init()
        settings = patch("core.bulk_operations.catalog.capture_settings",
                         return_value={"config_revision": "test-v1", "effective_settings": {}})
        settings.start()
        self.addCleanup(settings.stop)

    @contextmanager
    def measured_sql(self):
        statements = []
        execute = psycopg.Cursor.execute

        def measured(cursor, query, *args, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, *args, **kwargs)

        with patch.object(psycopg.Cursor, "execute", measured):
            yield statements

    def make_batch(self, outcomes, *, name="selected", operation="plan_check", paused=False):
        ids = self.seed(records.ACCOUNTS, [
            {"email": f"partial-{uuid.uuid4().hex}@example.test"} for _ in outcomes
        ])
        selected = bulk.create_selection(request_key=uuid.uuid4().hex,
            source={"kind": "ids", "ids": ids}, operation_key="plan_check", parameters={}, config_revision="test-v1")
        bulk.freeze_selection(selected["id"])
        batch = bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selected["id"], selection_revision=1,
            operation_key="plan_check", parameters={}, config_revision="test-v1", name=name)
        bulk.materialize_targets(batch["id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {common.table('operation_batch_target_rounds')} WHERE batch_id=%s ORDER BY ordinal",
                        (batch["id"],))
            targets = [dict(row) for row in cur.fetchall()]
            for target, outcome in zip(targets, outcomes):
                self.set_target(cur, target, outcome)
            values = dict(Counter(outcomes))
            cur.execute(f"UPDATE {common.table('operation_batch_rounds')} SET counts=%s,state='completed' WHERE id=%s",
                        (Jsonb(values), batch["round_id"]))
            cur.execute(f"UPDATE {common.table('operation_batch_controls')} SET counts=%s,state=%s,is_paused=%s,action_key=%s WHERE batch_id=%s",
                        (Jsonb(values), "active" if paused else "ended", paused, operation, batch["id"]))
        return batch, targets

    def set_target(self, cur, target, outcome):
        contribution = Jsonb({outcome: 1})
        cur.execute(f"""UPDATE {common.table('operation_batch_target_rounds')}
          SET outcome=%s,admission_state='submitted',chain_state='closed',applied_contribution=%s WHERE id=%s""",
                    (outcome, contribution, target["id"]))
        cur.execute(f"UPDATE {common.table('operation_selection_targets')} SET current_contribution=%s WHERE id=%s",
                    (contribution, target["canonical_target_id"]))

    def add_source(self, target, summary, *, generation=1, relation="owned_root", detached=False):
        unique = uuid.uuid4().hex
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {common.table('operation_tasks')}
              (task_uuid,source_system,source_id,batch_id,task_type,target_type,requested_action)
              VALUES (%s,'partial_counts_test',%s,%s,'plan_check','account','plan_check') RETURNING id""",
                        (unique, unique, target["batch_id"]))
            task_id = cur.fetchone()["id"]
            cur.execute(f"""INSERT INTO {common.table('operation_runs')}
              (run_uuid,task_id,run_no,source_system,source_id,batch_id,status,result_summary)
              VALUES (%s,%s,1,'partial_counts_test',%s,%s,'attention_required',%s) RETURNING id""",
                        (unique, task_id, unique, target["batch_id"], Jsonb(summary)))
            run_id = cur.fetchone()["id"]
            cur.execute(f"""INSERT INTO {common.table('operation_batch_run_links')}
              (target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,step_key,execution_generation,relation)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (target["id"], None if detached else task_id, None if detached else run_id,
                         task_id, run_id, unique, generation, relation))
        return run_id

    def legacy_batch(self, **kwargs):
        batch, targets = self.make_batch(["attention_required", "attention_required"], **kwargs)
        self.add_source(targets[0], {"requested_status": "partial_success"})
        self.add_source(targets[1], {"requested_status": "failed"})
        return batch, targets

    def stored_facts(self):
        with store._connect() as conn, conn.cursor() as cur:
            result = {}
            for name in ("operation_batch_controls", "operation_batch_rounds", "operation_selection_targets",
                         "operation_batch_target_rounds", "operation_batch_run_links", "operation_runs"):
                order = "batch_id" if name == "operation_batch_controls" else "id"
                cur.execute(f"SELECT * FROM {common.table(name)} ORDER BY {order}")
                result[name] = cur.fetchall()
            return result

    def test_modern_list_keeps_three_queries_and_original_counts(self):
        batch, _ = self.make_batch(["success", "partial_success", "failed", "cancelled"])
        with self.measured_sql() as queries:
            result = bulk.list_batches()
        self.assertEqual(3, len(queries))
        self.assertEqual({"success": 1, "partial_success": 1, "failed": 1, "cancelled": 1}, result["items"][0]["counts"])
        self.assertEqual(batch["id"], result["items"][0]["id"])
        self.assertEqual({"total_batches": 1, "active_batches": 0, "paused_batches": 0,
                          "ended_batches": 1, "failed_targets": 1}, result["summary"])

    def test_source_evidence_runs_only_for_filtered_candidates(self):
        self.make_batch(["success"], name="modern-only")
        self.legacy_batch(name="history-only")
        for _ in range(6):
            self.legacy_batch(name="unrelated-history")

        def nodes(plan):
            yield plan
            for child in plan.get("Plans", []):
                yield from nodes(child)

        execute = psycopg.Cursor.execute
        for name, expected, limit in (("modern-only", 0, 3), ("history-only", 2, 4)):
            queries = []

            def measured(cursor, query, params=None, *args, **kwargs):
                queries.append((str(query), params))
                return execute(cursor, query, params, *args, **kwargs)

            with patch.object(psycopg.Cursor, "execute", measured):
                result = bulk.list_batches(q=name)
            self.assertEqual(1, result["summary"]["total_batches"])
            self.assertEqual(limit, len(queries))
            probes = []
            with store._connect() as conn, conn.cursor() as cur:
                for query, params in queries:
                    if "operation_runs" not in query:
                        continue
                    cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + query, params)
                    plan = next(iter(cur.fetchone().values()))[0]["Plan"]
                    probes.extend(node["Actual Loops"] for node in nodes(plan)
                                  if node.get("Subplan Name", "").startswith("SubPlan") and
                                  any(child.get("Relation Name") == "operation_runs" for child in nodes(node)))
            self.assertTrue(probes, "必须观测真实 Run 证据子计划")
            with self.subTest(scope=name):
                self.assertEqual([expected] * len(probes), probes,
                                 "范围外的历史目标不应执行 Run 证据查询")

    def test_mixed_history_list_has_constant_queries_and_full_filtered_summary(self):
        selected = [self.legacy_batch()[0] for _ in range(6)]
        modern, _ = self.make_batch(["failed", "failed"])
        self.legacy_batch(name="excluded")
        self.legacy_batch(operation="token_refresh")
        self.legacy_batch(paused=True)
        before = self.stored_facts()
        with self.measured_sql() as mixed_queries:
            mixed = bulk.list_batches(q="selected", operation_key="plan_check", control_state="ended", limit=50)
        self.assertEqual([modern["id"], *[batch["id"] for batch in reversed(selected)]],
                         [row["id"] for row in mixed["items"]])
        self.assertEqual({"failed": 2}, mixed["items"][0]["counts"])
        self.assertTrue(all(row["counts"] == {"failed": 1, "partial_success": 1} for row in mixed["items"][1:]))
        self.assertEqual(8, mixed["summary"]["failed_targets"])
        self.assertLessEqual(len(mixed_queries), 5)
        for limit in (1, 3, 50):
            with self.subTest(limit=limit):
                with self.measured_sql() as queries:
                    result = bulk.list_batches(limit=limit, after_id=selected[-1]["id"],
                        q="selected", operation_key="plan_check", control_state="ended",
                        created_from="2000-01-01", created_to="2100-01-01")
                expected_ids = [batch["id"] for batch in reversed(selected[:-1])]
                self.assertEqual(expected_ids[:limit], [row["id"] for row in result["items"]])
                self.assertTrue(all(row["counts"] == {"failed": 1, "partial_success": 1} for row in result["items"]))
                self.assertEqual({"total_batches": 7, "active_batches": 0, "paused_batches": 0,
                                  "ended_batches": 7, "failed_targets": 8}, result["summary"])
                self.assertEqual({"has_more": limit < 5,
                                  "next_cursor": expected_ids[limit - 1] if limit < 5 else None}, result["page"])
                self.assertLessEqual(len(queries), 5, f"历史列表 SQL 次数应为常数，实际 {len(queries)}")
        self.assertEqual(before, self.stored_facts())
        self.assertGreater(modern["id"], selected[-1]["id"])

    def test_latest_owned_snapshot_run_is_the_only_partial_success_evidence(self):
        batch, targets = self.make_batch(["attention_required"] * 5 + ["failed", "partial_success"])
        partial = {"requested_status": "partial_success"}
        self.add_source(targets[0], partial)
        self.add_source(targets[0], {"requested_status": "failed"}, generation=2, relation="owned_continuation")
        self.add_source(targets[0], partial, generation=1)  # 较大 link.id 不能击败较高世代。
        self.add_source(targets[1], {"requested_status": "failed"}, generation=2)
        self.add_source(targets[1], partial, generation=2, relation="owned_continuation", detached=True)
        self.add_source(targets[1], {"requested_status": "failed"}, generation=3, relation="owned_child")
        self.add_source(targets[1], {"requested_status": "failed"}, generation=4, relation="external_blocker")
        self.add_source(targets[2], partial, relation="owned_child")
        self.add_source(targets[2], partial, generation=2, relation="external_blocker")
        self.add_source(targets[3], {"status": "partial_success", "ok": True})
        # targets[4] 没有 Run；非 attention 状态也不应受到明确 partial 证据的修正。
        self.add_source(targets[5], partial)
        self.add_source(targets[6], partial)
        before = self.stored_facts()
        self.assertEqual({"failed": 5, "partial_success": 2}, bulk.get_batch(batch["id"])["counts"])
        self.assertEqual({"failed": 5, "partial_success": 2}, bulk.get_round(batch["id"], batch["round_id"])["counts"])
        self.assertEqual(5, bulk.list_batches()["summary"]["failed_targets"])
        self.assertEqual(before, self.stored_facts())

    def test_rounds_and_current_targets_keep_distinct_evidence_with_constant_queries(self):
        batch, original = self.legacy_batch()
        round_ids = [batch["round_id"]]
        # 只重试第一个目标：第二个目标必须继续从 initial_round_id 读取。
        for index in range(5):
            retry = bulk.create_round(batch["id"], request_key=uuid.uuid4().hex, source={"view": "current"},
                                     selection={"kind": "targets", "target_ids": [original[0]["canonical_target_id"]]})
            bulk.freeze_round(retry["id"])
            bulk.materialize_targets(batch["id"])
            round_ids.append(retry["id"])
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {common.table('operation_batch_target_rounds')} WHERE round_id=%s", (retry["id"],))
                target = dict(cur.fetchone())
                self.set_target(cur, target, "attention_required")
                cur.execute(f"UPDATE {common.table('operation_batch_rounds')} SET counts=%s,state='completed' WHERE id=%s",
                            (Jsonb({"attention_required": 1}), retry["id"]))
                cur.execute(f"UPDATE {common.table('operation_batch_controls')} SET counts=%s,state='ended' WHERE batch_id=%s",
                            (Jsonb({"attention_required": 2}), batch["id"]))
            self.add_source(target, {"requested_status": "failed" if index == 4 else "partial_success"})
        before = self.stored_facts()
        with self.measured_sql() as detail_queries:
            detail = bulk.get_batch(batch["id"])
        self.assertEqual({"failed": 2}, detail["counts"])
        self.assertEqual([{"failed": 1}] + [{"failed": 0, "partial_success": 1}] * 4 +
                         [{"failed": 1, "partial_success": 1}], [row["counts"] for row in detail["rounds"]])
        self.assertIn("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", detail_queries)
        with self.subTest(surface="detail"):
            self.assertLessEqual(len(detail_queries), 6)
        with self.measured_sql() as round_queries:
            page = bulk.list_rounds(batch["id"], limit=3, after_round_no=6)
        self.assertEqual(list(reversed(round_ids[1:5]))[:3], [row["id"] for row in page["items"]])
        self.assertEqual({"has_more": True, "next_cursor": 3}, page["page"])
        self.assertLessEqual(len(round_queries), 3)
        self.assertEqual({"failed": 1, "partial_success": 1}, bulk.get_round(batch["id"], round_ids[0])["counts"])
        self.assertEqual(2, bulk.list_batches()["summary"]["failed_targets"])
        self.assertEqual(before, self.stored_facts())

    def test_missing_newer_snapshot_keeps_latest_existing_owned_run_evidence(self):
        batch, targets = self.make_batch(["attention_required"] * 3)
        self.add_source(targets[0], {"requested_status": "partial_success"})
        self.add_source(targets[1], {"requested_status": "failed"})
        missing = [self.add_source(target, {"requested_status": status}, generation=2,
                                   relation="owned_continuation", detached=True)
                   for target, status in zip(targets, ("failed", "partial_success", "partial_success"))]
        # 归档后 live FK 可以为空，snapshot 也可以指向已不存在的 Run。
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {common.table('operation_runs')} WHERE id=ANY(%s)", (missing,))
        before = self.stored_facts()
        expected = {"failed": 2, "partial_success": 1}
        self.assertEqual(expected, bulk.get_round(batch["id"], batch["round_id"])["counts"])
        self.assertEqual(expected, bulk.list_rounds(batch["id"])["items"][0]["counts"])
        self.assertEqual(expected, bulk.get_batch(batch["id"])["counts"])
        self.assertEqual(before, self.stored_facts())

    def test_historical_targets_cannot_lose_parents_omitted_from_round_query(self):
        batch, targets = self.legacy_batch()
        with store._connect() as conn, conn.cursor() as cur:
            for name, key, value in (("operation_selection_targets", "id", targets[0]["canonical_target_id"]),
                                     ("operation_batch_controls", "batch_id", batch["id"])):
                with self.subTest(parent=name), self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    with conn.transaction():
                        cur.execute(f"DELETE FROM {common.table(name)} WHERE {key}=%s", (value,))
        self.assertEqual({"failed": 1, "partial_success": 1},
                         bulk.get_round(batch["id"], batch["round_id"])["counts"])

    def test_compatible_single_row_helper_never_mutates_input_counts(self):
        batch, _ = self.legacy_batch()
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {common.table('operation_batch_controls')} WHERE batch_id=%s", (batch["id"],))
            row = dict(cur.fetchone())
            original = deepcopy(row)
            first = common.preserve_partial_counts(cur, row)
            second = common.preserve_partial_counts(cur, row)
            round_input = {"id": -99, "batch_id": batch["id"], "counts": {"attention_required": 2}}
            round_original = deepcopy(round_input)
            explicit_round = common.preserve_partial_counts(cur, round_input, round_id=batch["round_id"])
        self.assertEqual(original, row)
        self.assertEqual(first, second)
        self.assertEqual({"attention_required": 1, "partial_success": 1}, first["counts"])
        self.assertEqual(round_original, round_input)
        self.assertEqual(-99, explicit_round["id"])
        self.assertEqual({"attention_required": 1, "partial_success": 1}, explicit_round["counts"])

    def test_compatible_helper_empty_counts_return_original_without_queries(self):
        with store._connect() as conn, conn.cursor() as cur:
            for row in ({}, {"counts": None}, {"counts": {}}, {"counts": {"attention_required": 0}},
                        {"counts": {"success": 1, "partial_success": 2}}):
                for round_id in (None, 123):
                    with self.subTest(row=row, round_id=round_id), self.measured_sql() as queries:
                        self.assertIs(row, common.preserve_partial_counts(cur, row, round_id=round_id))
                    self.assertEqual([], queries)
