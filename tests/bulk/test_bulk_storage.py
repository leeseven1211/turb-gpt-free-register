"""真实PostgreSQL验证批量冻结、幂等、恢复与计数边界。"""

from __future__ import annotations

import uuid
from unittest.mock import patch
from tests.support_pg import PostgresTestCase
from core.storage import records
from core.storage.operations import bulk, bulk_common as common, store


class BulkStorageTests(PostgresTestCase):
    def setUp(self):
        bulk.reset_ready()
        bulk.init()
        self.settings = patch(
            "core.bulk_operations.catalog.capture_settings",
            return_value={"config_revision": "test-v1", "effective_settings": {}},
        )
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def accounts(self, count=3):
        return self.seed(
            records.ACCOUNTS,
            [
                {
                    "email": f"isolated-{uuid.uuid4().hex}-{i}@example.test",
                    "created_at": "2026-10-15T10:00:00",
                    "updated_at": "2026-10-15T10:00:00",
                }
                for i in range(count)
            ],
        )

    def selection(self, ids=None, **kwargs):
        source = {"kind": "ids", "ids": ids} if ids is not None else {"kind": "query", "query": {}}
        source.update(kwargs)
        result = bulk.create_selection(
            request_key=uuid.uuid4().hex,
            source=source,
            operation_key="plan_check",
            parameters={},
            config_revision="test-v1",
        )
        return bulk.freeze_selection(result["id"])

    def batch(self, count=3):
        selection = self.selection(self.accounts(count))
        return self.consume(selection)

    def consume(self, selection, key=None):
        return bulk.create_batch(
            request_key=key or uuid.uuid4().hex,
            selection_id=selection["id"],
            selection_revision=1,
            operation_key="plan_check",
            parameters={},
            config_revision="test-v1",
            max_concurrency=16,
        )

    def submitter(self, conn, targets, context):
        output = []
        with conn.cursor() as cur:
            for target in targets:
                unique = uuid.uuid4().hex
                cur.execute(
                    f"""INSERT INTO {common.table("operation_tasks")}
                  (task_uuid,source_system,source_id,batch_id,task_type,target_type,target_id,account_id,requested_action)
                  VALUES (%s,'bulk_test',%s,%s,'plan_check','account',%s,%s,'plan_check') RETURNING id""",
                    (unique, unique, context["batch_id"], target["account_id"], target["account_id"]),
                )
                task_id = cur.fetchone()["id"]
                cur.execute(
                    f"""INSERT INTO {common.table("operation_runs")}
                  (run_uuid,task_id,run_no,source_system,source_id,batch_id,account_id)
                  VALUES (%s,%s,1,'bulk_test',%s,%s,%s) RETURNING id""",
                    (unique, task_id, unique, context["batch_id"], target["account_id"]),
                )
                run_id = cur.fetchone()["id"]
                cur.execute(
                    f"UPDATE {common.table('operation_tasks')} SET last_run_id=%s WHERE id=%s", (run_id, task_id)
                )
                output.append(
                    {
                        "target_round_id": target["id"],
                        "disposition": "created",
                        "task_id": task_id,
                        "run_id": run_id,
                        "step_key": "plan_check",
                        "relation": "owned_root",
                    }
                )
        return output

    def test_snapshot_idempotency_and_missing_identity(self):
        ids = self.accounts(2)
        key = uuid.uuid4().hex
        args = dict(
            request_key=key,
            source={"kind": "ids", "ids": [ids[0], ids[0], 999999]},
            operation_key="plan_check",
            config_revision="test-v1",
        )
        first = bulk.create_selection(**args)
        again = bulk.create_selection(**args)
        self.assertEqual(first["id"], again["id"])
        frozen = bulk.freeze_selection(first["id"])
        self.assertEqual(2, frozen["target_count"])
        targets = bulk.get_selection(first["id"])["targets"]
        self.assertEqual("account_missing", targets[1]["match_evidence"]["reason_code"])
        batch = self.consume(frozen, key="batch-fixed")
        self.assertEqual(batch["id"], self.consume(frozen, key="batch-fixed")["id"])
        with self.assertRaises(common.BulkError):
            self.consume(frozen)
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS count FROM {common.table('operation_batch_target_rounds')}")
            self.assertEqual(0, cur.fetchone()["count"])

    def test_query_limit_and_immutable_members(self):
        self.accounts(5)
        selected = self.selection(query={"limit": 2})
        self.assertEqual(2, selected["target_count"])
        self.accounts(1)
        self.assertEqual(2, bulk.freeze_selection(selected["id"])["target_count"])

    def test_projection_is_idempotent_and_round_retry_resets_current(self):
        batch = self.batch(2)
        bulk.process_batch(batch["id"], self.submitter)
        bulk.project_pending()
        self.assertEqual(2, bulk.get_batch(batch["id"])["counts"]["queued"])
        self.assertEqual(0, bulk.project_pending())
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {common.table('operation_batch_target_rounds')} ORDER BY id")
            targets = [x["id"] for x in cur.fetchall()]
            cur.execute(f"UPDATE {common.table('operation_runs')} SET status='failed',error_code='test_network_failed'")
            for target in targets:
                bulk.record_managed_change(conn, target)
        bulk.project_pending()
        self.assertEqual(2, bulk.get_batch(batch["id"])["counts"]["failed"])
        retry = bulk.create_round(
            batch["id"],
            request_key=uuid.uuid4().hex,
            source={"view": "current"},
            selection={"kind": "result_filter", "outcomes": ["failed"]},
        )
        bulk.freeze_round(retry["id"])
        self.assertEqual(2, bulk.get_batch(batch["id"])["counts"]["pending_submit"])
        self.assertEqual(2, bulk.get_round(batch["id"], batch["round_id"])["counts"]["failed"])

    def test_cancel_unmaterialized_is_constant_execution_cost(self):
        batch = self.batch(5)
        command = bulk.request_control(
            batch["id"], request_key="cancel-1", action="cancel_not_started", expected_control_revision=1
        )
        replay = bulk.request_control(
            batch["id"], request_key="cancel-1", action="cancel_not_started", expected_control_revision=1
        )
        self.assertEqual(command["id"], replay["id"])
        bulk.settle_control(command["id"])
        bulk.settle_control(command["id"])
        self.assertEqual(5, bulk.get_batch(batch["id"])["counts"]["cancelled"])
        self.assertEqual(["cancelled"] * 5, [x["outcome"] for x in bulk.list_targets(batch["id"])["items"]])
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS count FROM {common.table('operation_runs')}")
            self.assertEqual(0, cur.fetchone()["count"])

    def test_preparing_cancel_and_round_publish_order(self):
        batch = self.batch(1)
        one = bulk.create_round(
            batch["id"], request_key="round-one", source={"view": "current"}, selection={"kind": "all"}
        )
        two = bulk.create_round(
            batch["id"], request_key="round-two", source={"view": "current"}, selection={"kind": "all"}
        )
        self.assertTrue(bulk.freeze_round(two["id"])["deferred"])
        command = bulk.request_control(
            batch["id"],
            request_key="cancel-round",
            action="cancel_not_started",
            expected_control_revision=3,
            round_id=one["id"],
        )
        bulk.settle_control(command["id"])
        cancelled = bulk.get_round(batch["id"], one["id"])
        self.assertEqual("cancelled_before_freeze", cancelled["completion_reason"])
        self.assertIsNone(cancelled["target_count"])
        self.assertEqual("active", bulk.freeze_round(two["id"])["state"])

    def test_expired_lease_fences_stale_worker(self):
        self.accounts(1)
        selection = bulk.create_selection(
            request_key="lease-test",
            source={"kind": "query", "query": {}},
            operation_key="plan_check",
            config_revision="test-v1",
        )
        claimed = bulk.claim_work("selection", "one")[0]
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {common.table('operation_selections')} SET lease_until=now()-interval '1 second' WHERE id=%s",
                (selection["id"],),
            )
        second = bulk.claim_work("selection", "two")[0]
        self.assertGreater(second["fence"], claimed["fence"])
        with self.assertRaises(common.BulkError):
            bulk.freeze_selection(selection["id"], owner_id="one", fence=claimed["fence"])
        self.assertEqual(
            "ready", bulk.freeze_selection(selection["id"], owner_id="two", fence=second["fence"])["state"]
        )

    def test_real_adapter_normal_block_uses_bounded_sql(self):
        import psycopg
        from core.bulk_operations.adapters import submit_chunk

        selected = self.selection(self.accounts(100))
        batch = bulk.create_batch(
            request_key=uuid.uuid4().hex,
            selection_id=selected["id"],
            selection_revision=1,
            operation_key="plan_check",
            parameters={},
            config_revision="test-v1",
            max_concurrency=64,
        )
        statements = []
        execute = psycopg.Cursor.execute

        def measured(cursor, query, *args, **kwargs):
            statements.append(str(query).split(None, 1)[0])
            return execute(cursor, query, *args, **kwargs)

        with patch.object(psycopg.Cursor, "execute", measured):
            result = bulk.process_batch(batch["id"], submit_chunk, limit=100)
        self.assertEqual(100, result["submitted"])
        self.assertLessEqual(len(statements), 30, f"100账号正常块SQL次数={len(statements)}: {statements}")
        bulk.project_pending()
        self.assertEqual(100, bulk.get_batch(batch["id"])["counts"]["queued"])

    def test_concurrent_same_batch_request_returns_one_batch(self):
        from concurrent.futures import ThreadPoolExecutor

        selected = self.selection(self.accounts(3))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.consume(selected, key="concurrent-batch"), range(2)))
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(1, sum(not item.get("reused") for item in results))

    def test_cancel_queued_and_preserve_owned_history(self):
        batch = self.batch(2)
        bulk.process_batch(batch["id"], self.submitter)
        bulk.project_pending()
        command = bulk.request_control(
            batch["id"], request_key="cancel-queued", action="cancel_not_started", expected_control_revision=1
        )
        bulk.settle_control(command["id"])
        bulk.project_pending()
        self.assertEqual(2, bulk.get_batch(batch["id"])["counts"]["cancelled"])
        import psycopg

        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with common.connect() as conn, conn.cursor() as cur:
                cur.execute(f"DELETE FROM {common.table('operation_runs')}")

    def test_replay_survives_config_change_and_parameters_are_bound(self):
        selected = self.selection(self.accounts(1))
        batch = self.consume(selected, key="config-replay")
        with patch(
            "core.bulk_operations.catalog.capture_settings",
            return_value={"config_revision": "new-version", "effective_settings": {}},
        ):
            self.assertEqual(batch["id"], self.consume(selected, key="config-replay")["id"])
        another = self.selection([1])
        with self.assertRaises(common.BulkError) as error:
            bulk.create_batch(
                request_key="different-params",
                selection_id=another["id"],
                selection_revision=1,
                operation_key="plan_check",
                parameters={"timezone_offset_min": 0},
                config_revision="test-v1",
            )
        self.assertEqual("selection_parameters_changed", error.exception.code)

    def test_large_preflight_is_bounded_without_one_hundred_account_query_loops(self):
        ids = self.accounts(1100)
        selected = bulk.create_selection(request_key="preflight-bounded-page", source={"kind": "ids", "ids": ids},
            operation_key="plan_check", parameters={}, config_revision="test-v1")
        sizes = []
        def check(targets, conn):
            sizes.append(len(targets))
            return [{"target_id": item["id"], "status": "ready"} for item in targets]
        frozen = bulk.freeze_selection(selected["id"], preflight=check)
        self.assertEqual(1100, frozen["target_count"])
        self.assertEqual([1100], sizes)
        self.assertEqual(1100, frozen["preflight_summary"]["ready"])

    def test_preflight_and_same_members_new_batch(self):
        ids = self.accounts(3)
        selected = bulk.create_selection(
            request_key="preflight",
            source={"kind": "ids", "ids": ids},
            operation_key="plan_check",
            config_revision="test-v1",
        )

        def preflight(targets, conn):
            return [{"target_id": item["id"], "status": "ready", "reason_code": None} for item in targets]

        frozen = bulk.freeze_selection(selected["id"], preflight=preflight)
        self.assertEqual(3, frozen["preflight_summary"]["ready"])
        first = self.consume(frozen)
        new = bulk.create_selection(
            request_key="new-batch-from-old",
            source={"kind": "batch_targets", "batch_id": first["id"], "selection": {"kind": "all"}},
            operation_key="plan_check",
            config_revision="test-v1",
        )
        second = self.consume(bulk.freeze_selection(new["id"]))
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(3, second["target_count"])
        self.assertNotEqual(
            bulk.list_targets(first["id"])["items"][0]["id"], bulk.list_targets(second["id"])["items"][0]["id"]
        )

    def test_manual_retry_keeps_root_task_and_owns_new_run(self):
        from core.bulk_operations.adapters import submit_chunk

        batch = self.batch(1)
        bulk.process_batch(batch["id"], submit_chunk)
        old = bulk.list_targets(batch["id"])["items"][0]
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {common.table('operation_runs')} SET status='failed',error_code='test_timeout' WHERE id=%s",
                (old["run_id"],),
            )
            cur.execute(f"UPDATE {common.table('operation_tasks')} SET status='failed' WHERE id=%s", (old["task_id"],))
            records.patch_row(records.ACCOUNTS, old["account_id"], changes={"plan_check_status": "failed"}, conn=conn)
            bulk.record_managed_change(conn, old["target_round_id"])
        bulk.project_pending()
        new = bulk.create_round(
            batch["id"],
            request_key="manual-root-retry",
            source={"view": "current"},
            selection={"kind": "result_filter", "states": ["failed"]},
        )
        bulk.freeze_round(new["id"])
        bulk.process_batch(batch["id"], submit_chunk)
        current = bulk.list_targets(batch["id"])["items"][0]
        self.assertEqual(old["task_id"], current["task_id"])
        self.assertNotEqual(old["run_id"], current["run_id"])
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS total FROM {common.table('operation_tasks')}")
            self.assertEqual(1, cur.fetchone()["total"])
            cur.execute(f"SELECT count(*) AS total FROM {common.table('operation_runs')}")
            self.assertEqual(2, cur.fetchone()["total"])

    def test_late_old_result_does_not_overwrite_current_round_or_metrics(self):
        from core.bulk_operations.adapters import submit_chunk

        batch = self.batch(1)
        bulk.process_batch(batch["id"], submit_chunk)
        old = bulk.list_targets(batch["id"])["items"][0]
        summary = {
            "ok": True,
            "country_total_count": 1,
            "country_success_count": 1,
            "plan_check_countries": ["JP"],
            "current_plan_type": "free",
            "plus_promo_kind": "none",
        }
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {common.table('operation_runs')} SET status='success',result_summary=%s::jsonb WHERE id=%s",
                (common.dumps(summary), old["run_id"]),
            )
            cur.execute(f"UPDATE {common.table('operation_tasks')} SET status='success' WHERE id=%s", (old["task_id"],))
            bulk.record_managed_change(conn, old["target_round_id"])
        bulk.project_pending()
        self.assertEqual(1, bulk.get_batch(batch["id"])["metrics"]["account.confirmed_no_offer"])
        new = bulk.create_round(
            batch["id"],
            request_key="explicit-requery",
            source={"view": "current"},
            selection={"kind": "targets", "target_ids": [old["id"]]},
        )
        bulk.freeze_round(new["id"])
        self.assertEqual(0, bulk.get_batch(batch["id"])["metrics"]["account.confirmed_no_offer"])
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {common.table('operation_runs')} SET status='failed',result_summary='{{}}',error_code='late_correction' WHERE id=%s",
                (old["run_id"],),
            )
            bulk.record_managed_change(conn, old["target_round_id"])
        bulk.project_pending()
        detail = bulk.get_batch(batch["id"])
        self.assertEqual(1, detail["counts"]["pending_submit"])
        self.assertEqual(0, detail["metrics"]["account.confirmed_no_offer"])
        self.assertEqual(1, bulk.get_round(batch["id"], batch["round_id"])["counts"]["failed"])
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT count(*) AS total FROM {common.table('operation_events')} WHERE event_type='bulk.result_revised'"
            )
            self.assertEqual(1, cur.fetchone()["total"])

    def test_control_lease_fences_old_worker_and_claim_checks_cancel(self):
        from core.bulk_operations.adapters import submit_chunk

        batch = self.batch(1)
        bulk.process_batch(batch["id"], submit_chunk)
        owned = bulk.list_targets(batch["id"])["items"][0]
        command = bulk.request_control(
            batch["id"], request_key="leased-cancel", action="cancel_not_started", expected_control_revision=1
        )
        one = bulk.claim_work("control", "old-worker")[0]
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {common.table('operation_batch_control_commands')} SET lease_until=now()-interval '1 second' WHERE id=%s",
                (command["id"],),
            )
        two = bulk.claim_work("control", "new-worker")[0]
        with self.assertRaises(common.BulkError) as stale:
            bulk.settle_control(command["id"], owner_id="old-worker", fence=one["fence"])
        self.assertEqual("lease_lost", stale.exception.code)
        with self.assertRaises(common.BulkError) as cancelled:
            store.claim_run(owned["run_id"], execution_id="test-no-network", worker_pid=0)
        self.assertEqual("bulk_claim_cancelled", cancelled.exception.code)
        bulk.settle_control(command["id"], owner_id="new-worker", fence=two["fence"])
        bulk.project_pending()
        self.assertEqual(1, bulk.get_batch(batch["id"])["counts"]["cancelled"])

    def test_empty_and_failed_retry_preparation_leave_no_permanent_active_batch(self):
        batch = self.batch(1)
        command = bulk.request_control(
            batch["id"], request_key="end-before-empty", action="cancel_not_started", expected_control_revision=1
        )
        bulk.settle_control(command["id"])
        retry = bulk.create_round(
            batch["id"],
            request_key="empty-failures",
            source={"view": "current"},
            selection={"kind": "result_filter", "states": ["failed"]},
        )
        frozen = bulk.freeze_round(retry["id"])
        self.assertEqual(0, frozen["target_count"])
        self.assertEqual("ended", bulk.get_batch(batch["id"])["state"])
        failed = bulk.create_round(
            batch["id"], request_key="bad-preparation", source={"view": "current"}, selection={"kind": "all"}
        )
        self.assertTrue(bulk.fail_round(failed["id"], error_code="target_outside_batch"))
        self.assertEqual("failed", bulk.get_round(batch["id"], failed["id"])["state"])
        self.assertEqual("ended", bulk.get_batch(batch["id"])["state"])

    def test_expand_fairness_rotates_even_when_earlier_batch_has_no_room(self):
        first = self.batch(1)
        second = self.batch(1)
        self.assertEqual(first["id"], bulk.list_active_batches(limit=1)[0]["batch_id"])
        bulk.process_batch(first["id"], self.submitter)
        self.assertEqual(second["id"], bulk.list_active_batches(limit=1)[0]["batch_id"])

    def test_get_does_not_initialize_or_migrate_schema(self):
        batch = self.batch(1)
        bulk.reset_ready()
        with patch("core.storage.operations.bulk_schema.init", side_effect=AssertionError("GET不能迁移")):
            self.assertEqual(batch["id"], bulk.get_batch(batch["id"])["id"])
            self.assertEqual(1, len(bulk.list_targets(batch["id"])["items"]))
            self.assertEqual(1, len(bulk.list_rounds(batch["id"])["items"]))
            self.assertEqual(batch["selection_id"], bulk.get_selection(batch["selection_id"])["id"])

    def test_frozen_members_reject_identity_mutation_and_relationship_mixup(self):
        import psycopg

        first = self.batch(1)
        second = self.batch(1)
        one = bulk.list_targets(first["id"])["items"][0]
        two = bulk.list_targets(second["id"])["items"][0]
        with self.assertRaises(psycopg.errors.CheckViolation):
            with common.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {common.table('operation_selection_targets')} SET target_id=9999 WHERE id=%s", (one["id"],)
                )
        bulk.materialize_targets(first["id"])
        with self.assertRaises(psycopg.errors.CheckViolation):
            with common.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {common.table('operation_batch_target_rounds')} SET canonical_target_id=%s WHERE batch_id=%s",
                    (two["id"], first["id"]),
                )

    def test_statement_guard_replaces_legacy_row_guard_and_rolls_back_all_changed_members(self):
        import psycopg

        selected = self.selection(self.accounts(2))
        targets = bulk.get_selection(selected["id"])["targets"]
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"DROP TRIGGER bulk_frozen_target ON {common.table('operation_selection_targets')}")
            cur.execute(f"""CREATE FUNCTION {common.table('bulk_legacy_guard_fixture')}()
              RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$""")
            cur.execute(f"""CREATE TRIGGER bulk_frozen_target BEFORE UPDATE
              ON {common.table('operation_selection_targets')} FOR EACH ROW
              EXECUTE FUNCTION {common.table('bulk_legacy_guard_fixture')}()""")
        for _ in range(2):
            bulk.reset_ready()
            bulk.init()
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT tgtype,tgoldtable,tgnewtable FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='bulk_frozen_target'",
                        (common.table('operation_selection_targets'),))
            trigger = cur.fetchone()
        self.assertEqual(16, trigger["tgtype"])
        self.assertEqual("bulk_old_targets", trigger["tgoldtable"])
        self.assertEqual("bulk_new_targets", trigger["tgnewtable"])
        with self.assertRaises(psycopg.errors.CheckViolation):
            with common.connect() as conn, conn.cursor() as cur:
                cur.execute(f"""UPDATE {common.table('operation_selection_targets')}
                  SET baseline=jsonb_build_object('changed',true) WHERE selection_id=%s""", (selected["id"],))
        self.assertEqual([target["baseline"] for target in targets],
                         [target["baseline"] for target in bulk.get_selection(selected["id"])["targets"]])
        with self.assertRaises(psycopg.errors.CheckViolation):
            with common.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {common.table('operation_selection_targets')} SET id=DEFAULT WHERE id=%s",
                            (targets[0]["id"],))
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common.table('operation_selection_targets')} SET current_projection_revision=1 WHERE selection_id=%s",
                        (selected["id"],))

    def test_handoff_partial_does_not_close_before_dependency_registration(self):
        batch = self.batch(1)
        bulk.process_batch(batch["id"], self.submitter)
        row = bulk.list_targets(batch["id"])["items"][0]
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {common.table('operation_runs')} SET status='partial_success',result_summary=%s::jsonb WHERE id=%s",
                (common.dumps({"awaiting_steps": ["account_setup"]}), row["run_id"]),
            )
            bulk.record_managed_change(conn, row["target_round_id"])
            cur.execute(
                f"SELECT chain_state FROM {common.table('operation_batch_target_rounds')} WHERE id=%s",
                (row["target_round_id"],),
            )
            self.assertNotEqual("closed", cur.fetchone()["chain_state"])

    def test_new_retry_uses_root_task_when_last_owned_run_is_a_child(self):
        batch = self.batch(1)
        bulk.process_batch(batch["id"], self.submitter)
        parent = bulk.list_targets(batch["id"])["items"][0]
        unique = uuid.uuid4().hex
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {common.table("operation_tasks")}
              (task_uuid,source_system,source_id,batch_id,task_type,target_type,account_id,requested_action)
              VALUES (%s,'bulk_test',%s,%s,'twofa_setup','account',%s,'twofa_setup') RETURNING id""",
                (unique, unique, batch["id"], parent["account_id"]),
            )
            child_task = cur.fetchone()["id"]
            cur.execute(
                f"""INSERT INTO {common.table("operation_runs")}
              (run_uuid,task_id,run_no,source_system,source_id,status,batch_id,account_id)
              VALUES (%s,%s,1,'bulk_test',%s,'failed',%s,%s) RETURNING id""",
                (unique, child_task, unique, batch["id"], parent["account_id"]),
            )
            child_run = cur.fetchone()["id"]
            bulk.inherit_managed_run(
                conn,
                child_run,
                source_run_id=parent["run_id"],
                parent_task_id=parent["task_id"],
                step_key="twofa_setup",
            )
            cur.execute(
                f"UPDATE {common.table('operation_runs')} SET status='failed',error_code='test_fail' WHERE id=%s",
                (parent["run_id"],),
            )
            bulk.record_managed_change(conn, parent["target_round_id"])
        bulk.project_pending()
        retry = bulk.create_round(
            batch["id"],
            request_key="root-not-child",
            source={"view": "current"},
            selection={"kind": "targets", "target_ids": [parent["id"]]},
        )
        bulk.freeze_round(retry["id"])
        bulk.materialize_targets(batch["id"])
        targets = bulk.prepare_targets(batch["id"])
        self.assertEqual(parent["task_id"], targets[0]["source_task_id"])
        self.assertNotEqual(child_task, targets[0]["source_task_id"])

    def test_unchanged_waiting_backoff_does_not_emit_projection_storm(self):
        batch = self.batch(1)

        def waiting(conn, targets, context):
            return [
                {
                    "target_round_id": item["id"],
                    "disposition": "waiting_account",
                    "reason_code": "account_busy",
                    "blocker_run_id": 1234,
                }
                for item in targets
            ]

        bulk.process_batch(batch["id"], waiting)
        bulk.project_pending()
        target = bulk.list_targets(batch["id"])["items"][0]
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT source_revision FROM {common.table('operation_batch_target_rounds')} WHERE id=%s",
                (target["target_round_id"],),
            )
            revision = cur.fetchone()["source_revision"]
            cur.execute(
                f"UPDATE {common.table('operation_batch_target_rounds')} SET next_prepare_at=now() WHERE id=%s",
                (target["target_round_id"],),
            )
        bulk.process_batch(batch["id"], waiting)
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""SELECT source_revision,prepare_attempts,next_prepare_at>=now()+interval '4 seconds' AS backed_off
              FROM {common.table("operation_batch_target_rounds")} WHERE id=%s""",
                (target["target_round_id"],),
            )
            row = cur.fetchone()
            self.assertEqual(revision, row["source_revision"])
            self.assertEqual(2, row["prepare_attempts"])
            self.assertTrue(row["backed_off"])
            cur.execute(
                f"SELECT count(*) AS total FROM {common.table('operation_projection_outbox')} WHERE processed_at IS NULL"
            )
            self.assertEqual(0, cur.fetchone()["total"])

    def test_projection_error_isolated_and_keeps_original_results_for_retry(self):
        first = self.batch(1)
        second = self.batch(1)
        bulk.process_batch(first["id"], self.submitter)
        bulk.process_batch(second["id"], self.submitter)
        from core.bulk_operations.results import project_many as real_project

        def projected(evidence, **kwargs):
            if any(item["batch_id"] == first["id"] for item in evidence):
                raise common.BulkError("adapter_contract_violation", "测试适配契约错误", 500)
            return real_project(evidence, **kwargs)

        with patch("core.bulk_operations.results.project_many", side_effect=projected):
            bulk.project_pending()
        self.assertEqual(1, bulk.get_batch(second["id"])["counts"]["queued"])
        broken = bulk.get_batch(first["id"])
        self.assertEqual("failed", broken["projection"]["state"])
        self.assertEqual("adapter_contract_violation", broken["projection"]["error_code"])
        self.assertEqual(1, broken["counts"]["pending_submit"])
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""UPDATE {common.table("operation_projection_outbox")} event SET available_at=now()
              FROM {common.table("operation_batch_target_rounds")} target WHERE event.target_round_id=target.id AND target.batch_id=%s""",
                (first["id"],),
            )
        bulk.project_pending()
        self.assertEqual(1, bulk.get_batch(first["id"])["counts"]["queued"])
        self.assertEqual("current", bulk.get_batch(first["id"])["projection"]["state"])

    def test_round_source_all_and_explicit_targets_respect_frozen_round_members(self):
        batch = self.batch(5)
        roots = bulk.list_targets(batch["id"])["items"]
        members = [item["id"] for item in roots[:2]]
        retry = bulk.create_round(
            batch["id"],
            request_key="two-source-members",
            source={"view": "current"},
            selection={"kind": "targets", "target_ids": members},
        )
        bulk.freeze_round(retry["id"])
        copied = bulk.create_selection(
            request_key="copy-two-source-round",
            source={
                "kind": "batch_targets",
                "batch_id": batch["id"],
                "view": "round",
                "round_id": retry["id"],
                "selection": {"kind": "all"},
            },
            operation_key="plan_check",
            config_revision="test-v1",
        )
        frozen = bulk.freeze_selection(copied["id"])
        self.assertEqual(2, frozen["target_count"])
        copied_ids = {item["target_id"] for item in bulk.get_selection(copied["id"])["items"]}
        self.assertEqual({item["account_id"] for item in roots[:2]}, copied_ids)
        invalid = bulk.create_selection(
            request_key="copy-outside-source-round",
            source={
                "kind": "batch_targets",
                "batch_id": batch["id"],
                "view": "round",
                "round_id": retry["id"],
                "selection": {"kind": "targets", "target_ids": [roots[2]["id"]]},
            },
            operation_key="plan_check",
            config_revision="test-v1",
        )
        with self.assertRaises(common.BulkError) as error:
            bulk.freeze_selection(invalid["id"])
        self.assertEqual("target_outside_round", error.exception.code)
        next_round = bulk.create_round(
            batch["id"],
            request_key="retry-outside-source-round",
            source={"view": "round", "round_id": retry["id"]},
            selection={"kind": "targets", "target_ids": [roots[2]["id"]]},
        )
        with self.assertRaises(common.BulkError) as error:
            bulk.freeze_round(next_round["id"])
        self.assertEqual("target_outside_round", error.exception.code)
