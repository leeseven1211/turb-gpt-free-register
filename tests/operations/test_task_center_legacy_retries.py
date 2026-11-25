"""历史账号任务的任务中心重跑集合读取原来源，并集合创建新原生任务。"""
from contextlib import ExitStack
import json
import uuid
from unittest.mock import patch

from psycopg import Cursor

from core.operations import action_service, task_gateway
from core.storage import records
from core.storage.operations import legacy_task_store, store
from tests.support_pg import PostgresTestCase


class TaskCenterLegacyRetryTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"legacy-center-{index}@example.test", "access_token": "isolated-value",
             "status": "success"} for index in range(1, 111)
        ])
        self.notify = self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.stack.enter_context(patch("core.runtime.capabilities.account_setup_unavailable", return_value=None))
        self.stack.enter_context(patch("core.accounts.operation_settings.completion_deployment_unavailable", return_value=None))
        self.stack.enter_context(patch.object(action_service.live_check_service, "deployment_unavailable", return_value=None))

    def sources(self, kind="plan_check", count=100, account_offset=0):
        with store._connect() as conn, conn.cursor() as cur:
            targets = []
            for index in range(1, count + 1):
                account_id = index + account_offset
                key = uuid.uuid4().hex
                cur.execute(f"""INSERT INTO {legacy_task_store._table('account_action_tasks')}
                    (task_uuid,task_type,account_id,email_snapshot,trigger,status,queued_at,result_summary)
                    VALUES (%s,%s,%s,%s,'manual','failed',now()::text,'{{}}') RETURNING id""",
                    (key, kind, account_id, f"legacy-center-{account_id}@example.test"))
                legacy_id = cur.fetchone()["id"]
                operation = store.create_runtime_task(task_type=kind, account_id=account_id,
                    email=f"legacy-center-{account_id}@example.test", source_system="account_action_tasks",
                    source_id=str(legacy_id), conn=conn)
                cur.execute(f"""UPDATE {store._table('operation_runs')}
                    SET status='failed',source_id=%s WHERE id=%s""",
                    (str(legacy_id), operation["run"]["id"]))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                    (operation["id"],))
                targets.append({"id": operation["id"], "legacy_id": legacy_id, "account_id": account_id})
        return targets

    def test_hundred_plan_sources_do_not_call_single_enqueue_and_have_bounded_sql(self):
        targets = self.sources()
        execute = Cursor.execute
        statements = []

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", measured), \
                patch.object(action_service.plan_check_service, "enqueue_account_plan_check",
                    side_effect=AssertionError("不能逐行调用计划查询受理")):
            reply = action_service.accept_bulk_operation_action("retry", [target["id"] for target in targets])
        print(f"任务中心 100 个历史套餐来源重跑 SQL：{len(statements)}")
        self.assertEqual(reply["accepted_count"], 100)
        self.assertEqual(reply["skipped_count"], 0)
        self.assertLessEqual(len(statements), 25, f"实际 SQL {len(statements)}")
        self.notify.assert_called_once()
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT trigger,data FROM {store._table('operation_tasks')} WHERE source_system='native_operations'")
            created = list(cur.fetchall())
        self.assertEqual(len(created), 100)
        self.assertEqual({row["trigger"] for row in created}, {"manual_retry"})

    def test_setup_preserves_requested_task_type_and_force_options(self):
        password = self.sources("password_change", count=1)
        twofa = self.sources("twofa_change", count=1, account_offset=1)
        with patch.object(action_service.account_task_store, "get_task",
                side_effect=AssertionError("不能逐项读取历史来源")):
            reply = action_service.accept_bulk_operation_action("retry", [password[0]["id"], twofa[0]["id"]])
        self.assertEqual(reply["accepted_count"], 2)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT task_type,data FROM {store._table('operation_tasks')}
                WHERE source_system='webui_runtime' ORDER BY account_id""")
            rows = list(cur.fetchall())
        self.assertEqual([row["task_type"] for row in rows], ["password_change", "twofa_change"])
        # 原持久层脱敏该布尔键；worker 仍依据 password_change 类型选择强制重置。
        self.assertEqual(rows[0]["data"]["steps"], ["password"])
        self.assertTrue(rows[1]["data"]["force_twofa_change"])

    def test_token_refresh_keeps_manual_retry_trigger_and_email_invalid_driver(self):
        target = self.sources("token_refresh", count=1)[0]
        records.patch_row(records.ACCOUNTS, 1, changes={"email_invalid": True})
        with patch.object(action_service.live_check_service, "_resolve_refresh_driver", return_value="protocol_v1"):
            reply = action_service.accept_bulk_operation_action("retry", [target["id"]])
        self.assertEqual(reply["accepted_count"], 1)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT trigger,data FROM {store._table('operation_tasks')} WHERE source_system='native_operations'")
            created = dict(cur.fetchone())
        self.assertEqual(created["trigger"], "token_refresh_manual_retry")
        self.assertTrue(created["data"]["force_refresh"])
        self.assertEqual(created["data"]["refresh_driver"], "v2")

    def test_rejected_stage_and_deactivated_target_do_not_block_other_sources(self):
        targets = self.sources(count=3)
        records.patch_row(records.ACCOUNTS, 1, changes={"plan_check_status": "running",
            "plan_check_started_at": "2099-01-01T00:00:00"})
        records.patch_row(records.ACCOUNTS, 2, changes={"account_status": "deactivated"})
        ids = [targets[2]["id"], targets[0]["id"], targets[1]["id"]]
        reply = action_service.accept_bulk_operation_action("retry", ids)
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [targets[2]["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [targets[0]["id"], targets[1]["id"]])

    def test_legacy_codex_does_not_add_waiting_or_stopping_guard(self):
        targets = self.sources("codex_retry", count=2)
        for target, status in zip(targets, ("waiting", "stopping"), strict=True):
            active = store.create_runtime_task(task_type="unrelated", account_id=target["account_id"],
                email=f"legacy-center-{target['account_id']}@example.test")
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {store._table('operation_runs')} SET status=%s WHERE id=%s",
                    (status, active["run"]["id"]))
        with patch.object(action_service.codex_operation_service, "_deployment_unavailable", return_value=None), \
                patch.object(action_service.codex_operation_service, "_feature_ready", return_value=(True, "")), \
                patch.object(action_service.codex_operation_service, "start_dispatcher",
                    side_effect=AssertionError("API 不能启动执行器")), \
                patch.object(action_service.codex_operation_service, "register_handler",
                    side_effect=AssertionError("API 不能注册执行 handler")):
            reply = action_service.accept_bulk_operation_action("retry", [target["id"] for target in targets])
        self.assertEqual(reply["accepted_count"], 2)

    def test_extract_retry_keeps_recorded_link_type_without_new_promotion_guard(self):
        target = self.sources("extract_link", count=1)[0]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {legacy_task_store._table('account_action_tasks')} SET result_summary=%s::jsonb WHERE id=%s",
                ('{"link_type":"card"}', target["legacy_id"]))
        service = action_service.extract_link_service
        with patch.object(service, "_provider_mode_enabled", return_value=True), \
                patch.object(service, "_cdk", return_value="isolated"), \
                patch.object(service, "_select_account_link_type", return_value=("card", None)) as selected, \
                patch.object(service, "_paypal_options", return_value={}):
            reply = action_service.accept_bulk_operation_action("retry", [target["id"]])
        self.assertEqual(reply["accepted_count"], 1)
        self.assertEqual(selected.call_args.kwargs["requested"], "card")
        self.assertNotIn("plus", selected.call_args.kwargs["account"])

    def test_duplicate_legacy_source_creates_only_first_account_task(self):
        target = self.sources("plan_check", count=1)[0]
        reply = action_service.accept_bulk_operation_action("retry", [target["id"], target["id"]])
        # 路由会先去重；应用层即使重复调用，也不能创建第二个同账号活动 Run。
        self.assertEqual(reply["accepted_count"], 2)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_tasks')} WHERE source_system='native_operations'")
            self.assertEqual(cur.fetchone()["n"], 1)

    def test_event_failure_rolls_back_stage_and_all_created_tasks(self):
        targets = self.sources("token_refresh", count=2)
        execute = Cursor.execute

        def broken(cursor, query, params=None, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                raise RuntimeError("isolated event failure")
            return execute(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", broken):
            reply = action_service.accept_bulk_operation_action("retry", [target["id"] for target in targets])
        self.assertEqual(reply["accepted_count"], 0)
        for number in (1, 2):
            self.assertNotEqual(records.get_row(records.ACCOUNTS, number).get("live_check_status"), "queued")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_tasks')} WHERE source_system='native_operations'")
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_stage_rejected_first_task_does_not_reserve_account_for_second_kind(self):
        first = self.sources("plan_check", count=1)[0]
        second = self.sources("password_change", count=1)[0]
        records.patch_row(records.ACCOUNTS, 1, changes={
            "plan_check_status": "running", "plan_check_started_at": "2099-01-01T00:00:00"})
        reply = action_service.accept_bulk_operation_action("retry", [first["id"], second["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [second["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [first["id"]])

    def native_source(self, *, account_id=1, family="openai_interactive", status="failed"):
        task_gateway.register_operation_actions("center_mixed_retry",
            retry_handler=task_gateway.default_operation_retry, source_systems=("native_operations",))
        with store._connect() as conn, conn.cursor() as cur:
            task = store.create_runtime_task(task_type="center_mixed_retry", account_id=account_id,
                email=f"legacy-center-{account_id}@example.test", source_system="native_operations",
                source_id=uuid.uuid4().hex, resource_family=family, conn=conn)
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status=%s WHERE id=%s",
                (status, task["run"]["id"]))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                (task["id"],))
        return {"id": task["id"], "run_id": task["run"]["id"]}

    def test_legacy_then_native_same_family_uses_selection_order(self):
        native = self.native_source()
        legacy = self.sources("password_change", count=1)[0]
        reply = action_service.accept_bulk_operation_action("retry", [legacy["id"], native["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [legacy["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [native["id"]])
        self.assertEqual(store.get_task(native["id"], include_events=False)["last_run_id"], native["run_id"])

    def test_native_then_legacy_same_family_uses_selection_order(self):
        legacy = self.sources("password_change", count=1)[0]
        native = self.native_source()
        reply = action_service.accept_bulk_operation_action("retry", [native["id"], legacy["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [native["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [legacy["id"]])
        self.assertNotEqual(store.get_task(native["id"], include_events=False)["last_run_id"], native["run_id"])

    def test_stage_rejected_legacy_first_allows_native_same_family(self):
        native = self.native_source()
        legacy = self.sources("plan_check", count=1)[0]
        records.patch_row(records.ACCOUNTS, 1, changes={
            "plan_check_status": "running", "plan_check_started_at": "2099-01-01T00:00:00"})
        reply = action_service.accept_bulk_operation_action("retry", [legacy["id"], native["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [native["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [legacy["id"]])

    def test_native_and_legacy_different_families_both_accept(self):
        native = self.native_source(family="independent_family")
        legacy = self.sources("password_change", count=1)[0]
        reply = action_service.accept_bulk_operation_action("retry", [legacy["id"], native["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [legacy["id"], native["id"]])
        self.assertEqual(reply["skipped_count"], 0)

    def refresh_source(self, *, origin_account_id=1, credential_account_id=1, refreshable=True):
        target = self.sources("codex_token_refresh", count=1, account_offset=origin_account_id - 1)[0]
        name = f"codex-mixed-center-{credential_account_id}-free.json"
        email = f"legacy-center-{credential_account_id}@example.test"
        content = {"email": email, "access_token": "isolated-access",
            **({"refresh_token": "isolated-refresh"} if refreshable else {})}
        records.insert_row(records.CODEX_CREDENTIALS, {"filename": name, "email": email, "content": content})
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {legacy_task_store._table('account_action_tasks')} SET result_summary=%s::jsonb WHERE id=%s",
                ('{"filename":"' + name + '"}', target["legacy_id"]))
        return target

    def test_refresh_then_regular_reserves_actual_credential_account_in_selection_order(self):
        regular = self.sources("password_change", count=1, account_offset=1)[0]
        refresh = self.refresh_source(origin_account_id=1, credential_account_id=2)
        reply = action_service.accept_bulk_operation_action("retry", [refresh["id"], regular["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [refresh["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [regular["id"]])
        self.assertEqual(records.get_row(records.ACCOUNTS, 2)["codex_execution_status"], "queued")

    def test_regular_then_refresh_returns_busy_reference_to_this_wave_winner(self):
        refresh = self.refresh_source(origin_account_id=1, credential_account_id=2)
        regular = self.sources("password_change", count=1, account_offset=1)[0]
        reply = action_service.accept_bulk_operation_action("retry", [regular["id"], refresh["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [regular["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [refresh["id"]])
        self.assertIn("durable refresh", reply["skipped"][0]["error"])

    def test_invalid_refresh_does_not_reserve_actual_account_for_native(self):
        native = self.native_source(account_id=2)
        refresh = self.refresh_source(origin_account_id=1, credential_account_id=2, refreshable=False)
        reply = action_service.accept_bulk_operation_action("retry", [refresh["id"], native["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [native["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [refresh["id"]])

    def test_mixed_domain_event_failure_rolls_back_native_and_legacy_facts_together(self):
        native = self.native_source(account_id=1)
        legacy = self.sources("token_refresh", count=1, account_offset=1)[0]
        execute = Cursor.execute
        events = []

        def fail_second_event(cursor, query, params=None, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                events.append(str(query))
                if len(events) == 2:
                    raise RuntimeError("isolated second domain event failure")
            return execute(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", fail_second_event):
            reply = action_service.accept_bulk_operation_action("retry", [native["id"], legacy["id"]])
        self.assertEqual(reply["accepted_count"], 0)
        self.assertEqual(len(events), 2)
        self.assertEqual(store.get_task(native["id"], include_events=False)["last_run_id"], native["run_id"])
        self.assertNotEqual(records.get_row(records.ACCOUNTS, 2).get("live_check_status"), "queued")
        self.notify.assert_not_called()

    def test_post_commit_mail_failure_does_not_erase_committed_direct_reply(self):
        native = self.native_source(account_id=1)
        mail = self.sources("deactivation_mail", count=1, account_offset=1)[0]
        with patch.object(action_service.deactivation_mail_service, "enqueue_bulk",
                side_effect=RuntimeError("isolated mail acceptance failure")):
            reply = action_service.accept_bulk_operation_action("retry", [native["id"], mail["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [native["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [mail["id"]])
        self.assertNotEqual(store.get_task(native["id"], include_events=False)["last_run_id"], native["run_id"])

    def large_regular_specs(self, count=501):
        from core.operations import task_center_legacy_retry as legacy

        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"legacy-center-{index}@example.test", "access_token": "isolated-value"}
            for index in range(111, count + 1)])
        accounts = {row["id"]: row for row in records.list_rows(records.ACCOUNTS)}
        specs = {index: {"task_type": "plan_check", "account_id": index,
            "email": accounts[index]["email"], "source_system": "native_operations",
            "source_id": f"large-test:{index}", "resource_family": "openai_interactive",
            "trigger": "manual_retry", "data": {}, "config_snapshot": {}, "config_allowlist": ()}
            for index in range(1, count + 1)}
        return legacy, specs, accounts

    def test_501_regular_targets_bound_each_json_write_to_500_rows(self):
        legacy, specs, accounts = self.large_regular_specs()
        execute, payload_sizes = Cursor.execute, []

        def measured(cursor, query, params=None, **kwargs):
            if "jsonb_to_recordset" in str(query):
                for value in params or ():
                    if isinstance(value, str) and value.startswith("["):
                        payload_sizes.append(len(json.loads(value)))
            return execute(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", measured), store._connect() as conn:
            created, _ = legacy.commit_regular(conn, specs, accounts)
        self.assertEqual(len(created), 501)
        self.assertTrue(payload_sizes)
        self.assertLessEqual(max(payload_sizes), 500, payload_sizes)

    def test_second_chunk_failure_rolls_back_all_501_regular_targets(self):
        legacy, specs, accounts = self.large_regular_specs()
        execute, event_calls = Cursor.execute, []

        def fail_second_events(cursor, query, params=None, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                event_calls.append(str(query))
                if len(event_calls) == 2:
                    raise RuntimeError("isolated second chunk failure")
            return execute(cursor, query, params, **kwargs)

        with self.assertRaises(RuntimeError), patch.object(Cursor, "execute", fail_second_events), store._connect() as conn:
            legacy.commit_regular(conn, specs, accounts)
        self.assertEqual(len(event_calls), 2)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_tasks')}")
            self.assertEqual(cur.fetchone()["n"], 0)
        self.assertNotEqual(records.get_row(records.ACCOUNTS, 1).get("plan_check_status"), "queued")
        self.assertNotEqual(records.get_row(records.ACCOUNTS, 501).get("plan_check_status"), "queued")

    def managed_and_direct(self):
        native = self.native_source(account_id=1)
        managed = self.native_source(account_id=2)
        tasks = store.get_action_tasks_many([native["id"], managed["id"]])
        tasks[managed["id"]]["_managed_target_round_id"] = 7001
        return native, managed, tasks

    def test_deferred_managed_lookup_failure_preserves_committed_direct_receipt(self):
        native, managed, tasks = self.managed_and_direct()
        with patch.object(action_service.operation_task_store, "get_action_tasks_many", return_value=tasks), \
                patch.object(action_service.operation_task_store, "get_managed_retry_targets",
                    side_effect=RuntimeError("isolated managed lookup failure")):
            reply = action_service.accept_bulk_operation_action("retry", [native["id"], managed["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [native["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [managed["id"]])
        self.assertNotEqual(store.get_task(native["id"], include_events=False)["last_run_id"], native["run_id"])
        self.assertEqual(store.get_task(managed["id"], include_events=False)["last_run_id"], managed["run_id"])
        self.notify.assert_called_once()

    def test_deferred_managed_batch_failure_preserves_other_batch_and_direct_receipt(self):
        from core.bulk_operations import service

        native, managed, tasks = self.managed_and_direct()
        other = self.native_source(account_id=3)
        tasks.update(store.get_action_tasks_many([other["id"]]))
        tasks[other["id"]]["_managed_target_round_id"] = 7002
        targets = {7001: {"batch_id": 8001, "canonical_target_id": 9001},
            7002: {"batch_id": 8002, "canonical_target_id": 9002}}
        with patch.object(action_service.operation_task_store, "get_action_tasks_many", return_value=tasks), \
                patch.object(action_service.operation_task_store, "get_managed_retry_targets", return_value=targets), \
                patch.object(service, "create_round", side_effect=[
                    RuntimeError("isolated managed batch failure"), {"state": "preparing"}]) as create:
            reply = action_service.accept_bulk_operation_action("retry",
                [native["id"], managed["id"], other["id"]])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [native["id"], other["id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [managed["id"]])
        self.assertEqual(create.call_count, 2)
        self.assertNotEqual(store.get_task(native["id"], include_events=False)["last_run_id"], native["run_id"])
        self.assertEqual(store.get_task(managed["id"], include_events=False)["last_run_id"], managed["run_id"])
