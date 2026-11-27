"""Team 任务精确归属与原生重跑幂等接缝回归。"""
from __future__ import annotations

import json
import logging
import threading
import unittest
from unittest.mock import patch

from flask import Flask

from core import account_task_store, operation_task_store
from core.operations import action_service, query_service, task_gateway
from core.operations.contracts import OperationQuery
from tests.support_pg import PostgresTestCase
from webui.routes.operations import create_operations_blueprint
from webui.runtime import WebUIContext


def _client():
    app = Flask(__name__)
    app.register_blueprint(create_operations_blueprint(WebUIContext(app, logging.getLogger(__name__))))
    return app.test_client()


class TeamOperationHttpTests(unittest.TestCase):
    def test_new_team_column_preserves_old_public_task_shape_and_exact_new_ids(self):
        legacy = query_service.public_operation_record({"id": 41, "status": "success", "team_id": None})
        team = query_service.public_operation_record({
            "id": 42, "status": "success", "team_id": 9007199254740993,
        })
        self.assertEqual({"id": 41, "status": "success"}, legacy)
        self.assertEqual("9007199254740993", team["team_id"])

    def test_team_filter_rejects_invalid_or_repeated_ids_before_storage_read(self):
        client = _client()
        with patch.object(query_service, "list_operations", return_value={"ok": True, "items": [], "total": 0}) as read:
            for value in ("", "0", "-1", "+1", "1.0", "1,2", "12x", "１２", "9223372036854775808"):
                with self.subTest(value=value):
                    response = client.get("/api/operations", query_string={"team_id": value})
                    self.assertEqual(422, response.status_code)
                    self.assertEqual("parameter_invalid", response.get_json()["error_code"])
            self.assertEqual(422, client.get("/api/operations?team_id=12&team_id=13").status_code)
        read.assert_not_called()

    def test_team_filter_keeps_large_id_exact_and_old_query_defaults(self):
        with patch.object(query_service, "list_operations", return_value={"ok": True, "items": [], "total": 0}) as read:
            response = _client().get("/api/operations?team_id=9007199254740993&q=Team&include_batches=0")
        self.assertEqual(200, response.status_code)
        query = read.call_args.args[0]
        self.assertEqual(9007199254740993, query.team_id)
        self.assertEqual(("Team", 1, 50), (query.q, query.page, query.page_size))
        self.assertFalse(query.include_batches)


class TeamRetryRequestTests(unittest.TestCase):
    def setUp(self):
        self.client = _client()
        self.task = {
            "id": 41, "task_type": "team_join", "source_system": "native_operations",
            "team_id": 12, "status": "failed", "target_status": "unknown", "runs": [],
        }
        self.read = patch.object(action_service.operation_task_store, "get_task", return_value=self.task)
        self.read.start()
        self.managed = patch("core.bulk_operations.service.retry_managed_task", return_value=None)
        self.managed.start()
        self.addCleanup(self.read.stop)
        self.addCleanup(self.managed.stop)

    def _retry(self, handler, *, headers=None, body=None):
        with patch.object(task_gateway, "operation_action", return_value=handler):
            return self.client.post("/api/operations/41/retry", headers=headers or {}, json=body)

    def test_http_key_reaches_new_handler_and_replayed_active_task(self):
        calls = []
        receipts = {}

        def retry(task, *, request_key=None):
            calls.append(request_key)
            if request_key not in receipts:
                receipts[request_key] = {"accepted": True, "task_id": task["id"], "run_id": 51}
                task["status"] = "running"
            return receipts[request_key]

        key = "team-retry-request-001"
        first = self._retry(retry, headers={"Idempotency-Key": key})
        second = self._retry(retry, headers={"Idempotency-Key": key})
        self.assertEqual((202, 202), (first.status_code, second.status_code))
        self.assertEqual(first.get_json(), second.get_json())
        self.assertEqual([key, key], calls)
        self.assertEqual(1, len(receipts))

    def test_unbound_team_probe_replays_through_coordinator_while_active(self):
        self.task.pop("team_id")
        self.task.update(task_type="team_probe", source_system="team_management", status="running")
        seen = []

        def retry(_task, *, request_key=None):
            seen.append(request_key)
            return {"accepted": True, "reused": True, "task_id": "41", "run_id": "51"}

        response = self._retry(retry, headers={"Idempotency-Key": "team-probe-retry-request-001"})
        self.assertEqual(202, response.status_code)
        self.assertTrue(response.get_json()["reused"])
        self.assertEqual(["team-probe-retry-request-001"], seen)

    def test_body_key_is_forwarded_and_mismatched_keys_are_rejected(self):
        seen = []

        def retry(_task, *, request_key=None):
            seen.append(request_key)
            return {"accepted": True, "run_id": 51}

        response = self._retry(retry, body={"idempotency_key": "team-body-request-001"})
        self.assertEqual(202, response.status_code)
        self.assertEqual(["team-body-request-001"], seen)
        conflict = self._retry(
            retry, headers={"Idempotency-Key": "team-header-request-001"},
            body={"idempotency_key": "team-body-request-001"},
        )
        self.assertEqual(422, conflict.status_code)
        self.assertEqual("idempotency_key_mismatch", conflict.get_json()["error_code"])
        self.assertEqual(1, len(seen))

    def test_old_single_argument_handler_keeps_its_call_contract(self):
        self.task.pop("team_id")
        observed = []

        def retry(task):
            observed.append(task["id"])
            return {"accepted": True, "run_id": 51}

        response = self._retry(retry, headers={"Idempotency-Key": "legacy-retry-request-001"})
        self.assertEqual(202, response.status_code)
        self.assertEqual([41], observed)

    def test_handler_type_error_is_not_retried_as_legacy_signature(self):
        attempts = []

        def retry(_task, *, request_key=None):
            attempts.append(request_key)
            raise TypeError("团队处理器内部类型错误")

        response = self._retry(retry, headers={"Idempotency-Key": "team-error-request-001"})
        self.assertEqual(503, response.status_code)
        self.assertIn("团队处理器内部类型错误", response.get_json()["error"])
        self.assertEqual(["team-error-request-001"], attempts)

    def test_team_retry_requires_valid_key_and_preserves_classified_domain_status(self):
        from core.teams.errors import TeamError

        attempts = []

        def retry(_task, *, request_key=None):
            attempts.append(request_key)
            raise TeamError("idempotency_conflict", "请求键已用于其他目标。", status=409,
                            details={"team_id": "12"})

        for headers in ({}, {"Idempotency-Key": "short"}, {"Idempotency-Key": "x" * 129}):
            with self.subTest(headers_present=bool(headers)):
                response = self._retry(retry, headers=headers)
                self.assertEqual(422, response.status_code)
                self.assertIn(response.get_json()["error_code"], {
                    "idempotency_key_required", "idempotency_key_invalid",
                })
        self.assertEqual([], attempts)
        response = self._retry(retry, headers={"Idempotency-Key": " team-conflict-request-001 "})
        self.assertEqual(409, response.status_code)
        self.assertEqual("idempotency_conflict", response.get_json()["error_code"])
        self.assertEqual({"team_id": "12"}, response.get_json()["details"])
        self.assertEqual(["team-conflict-request-001"], attempts)

class TeamBulkRetryRequestTests(PostgresTestCase):
    def setUp(self):
        self.client = _client()
        self.task = {
            "id": 41, "task_type": "team_join", "source_system": "team_management",
            "team_id": 12, "status": "failed", "target_status": "unknown", "runs": [],
        }
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.schema_patch.start()
        self.addCleanup(self.schema_patch.stop)
        account_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()

    def test_bulk_team_retries_use_distinct_stable_keys_for_each_fixed_task(self):
        observed = []
        receipts = {}

        def retry(task, *, request_key=None):
            observed.append((task["id"], request_key))
            receipts.setdefault(request_key, {"accepted": True, "run_id": 100 + task["id"]})
            return receipts[request_key]

        tasks = {
            41: {**self.task, "id": 41},
            42: {**self.task, "id": 42, "status": "running"},
        }
        with (
            patch.object(action_service.operation_task_store, "get_action_tasks_many", return_value=tasks),
            patch.object(task_gateway, "operation_action", return_value=retry),
        ):
            for _ in range(2):
                response = self.client.post(
                    "/api/operations/bulk", json={"action": "retry", "task_ids": [41, 42]},
                    headers={"Idempotency-Key": "team-bulk-retry-request-001"},
                )
                self.assertEqual(200, response.status_code)
                self.assertEqual(2, response.get_json()["accepted_count"])
        self.assertEqual(2, len(observed))
        self.assertNotEqual(observed[0][1], observed[1][1])
        self.assertTrue(all(16 <= len(key) <= 128 for _, key in observed))
        self.assertEqual(2, len(receipts))

    def test_bulk_key_binds_fixed_tasks_and_replays_before_task_state_checks(self):
        calls = []

        def retry(task, *, request_key=None):
            calls.append(task["id"])
            return {"accepted": True, "run_id": 100 + task["id"]}

        with (
            patch.object(action_service.operation_task_store, "get_action_tasks_many", return_value={
                41: {**self.task, "id": 41}, 42: {**self.task, "id": 42},
            }) as read,
            patch.object(task_gateway, "operation_action", return_value=retry),
        ):
            headers = {"Idempotency-Key": "team-bulk-fixed-request-001"}
            first = self.client.post("/api/operations/bulk",
                                     json={"action": "retry", "task_ids": [41, 42]}, headers=headers)
            read.return_value = {}
            replay = self.client.post("/api/operations/bulk",
                                      json={"action": "retry", "task_ids": [41, 42]}, headers=headers)
            changed = self.client.post("/api/operations/bulk",
                                       json={"action": "retry", "task_ids": [41]}, headers=headers)
            changed_action = self.client.post("/api/operations/bulk",
                                              json={"action": "cancel", "task_ids": [41, 42]}, headers=headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual(first.get_json(), replay.get_json())
        self.assertEqual([41, 42], calls)
        self.assertEqual(409, changed.status_code)
        self.assertEqual(409, changed_action.status_code)
        self.assertEqual("idempotency_conflict", changed.get_json()["error_code"])
        read.assert_called_once()

    def test_bulk_replay_resumes_only_items_without_committed_receipts(self):
        attempts = []
        interrupted = False

        def retry(task, *, request_key=None):
            nonlocal interrupted
            attempts.append(task["id"])
            if task["id"] == 42 and not interrupted:
                interrupted = True
                raise SystemExit("模拟 HTTP 处理进程中断")
            return {"accepted": True, "run_id": 100 + task["id"]}

        with (
            patch.object(action_service.operation_task_store, "get_action_tasks_many", return_value={
                41: {**self.task, "id": 41}, 42: {**self.task, "id": 42},
            }),
            patch.object(task_gateway, "operation_action", return_value=retry),
        ):
            headers = {"Idempotency-Key": "team-bulk-resume-request-001"}
            with self.assertRaises(SystemExit):
                self.client.post("/api/operations/bulk",
                                 json={"action": "retry", "task_ids": [41, 42]}, headers=headers)
            resumed = self.client.post("/api/operations/bulk",
                                       json={"action": "retry", "task_ids": [41, 42]}, headers=headers)
        self.assertEqual(200, resumed.status_code)
        self.assertEqual(2, resumed.get_json()["accepted_count"])
        self.assertEqual([41, 42, 42], attempts)

    def test_concurrent_bulk_request_preserves_one_item_executor(self):
        attempts = []
        entered = threading.Event()
        release = threading.Event()
        responses = []

        def retry(task, *, request_key=None):
            attempts.append(task["id"])
            entered.set()
            self.assertTrue(release.wait(10))
            return {"accepted": True, "run_id": 141}

        def submit():
            responses.append(_client().post(
                "/api/operations/bulk", json={"action": "retry", "task_ids": [41]},
                headers={"Idempotency-Key": "team-bulk-concurrent-001"},
            ))

        with (
            patch.object(action_service.operation_task_store, "get_action_tasks_many",
                         return_value={41: self.task}),
            patch.object(task_gateway, "operation_action", return_value=retry),
        ):
            first = threading.Thread(target=submit)
            first.start()
            self.assertTrue(entered.wait(10))
            second = threading.Thread(target=submit)
            second.start()
            second.join(5)
            release.set()
            first.join(10)
            second.join(10)
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
        self.assertEqual([41], attempts)
        self.assertEqual([200, 503], sorted(response.status_code for response in responses))
        busy = next(response for response in responses if response.status_code == 503)
        self.assertTrue(busy.get_json()["retryable"])


class TeamOperationStorageTests(PostgresTestCase):
    def setUp(self):
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.schema_patch.start()
        self.addCleanup(self.schema_patch.stop)
        account_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()

    def _task(self, source, *, team_id=None, status="success", parent_id=None, task_type="team_sync", text=""):
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {operation_task_store._table('operation_tasks')}
                    (task_uuid,source_system,source_id,task_type,target_type,requested_action,
                     status,target_status,current_stage,team_id,parent_task_id,email_snapshot,data)
                    VALUES (%s,'native_operations',%s,%s,'team','sync',%s,'unknown','complete',
                            %s,%s,%s,%s::jsonb) RETURNING id""",
                (source, source, task_type, status, team_id, parent_id, text, json.dumps({"team_id": "12"})),
            )
            return int(cur.fetchone()["id"])

    def test_team_filter_scopes_parents_children_total_facets_and_pages_exactly(self):
        parent = self._task("team-parent", team_id=12, status="success")
        child = self._task("team-child", team_id=12, status="failed", parent_id=parent, task_type="team_join")
        self._task("team-other", team_id=112, task_type="other-team", text="Team12@example.test")
        self._task("team-json-only", task_type="json-only", text="12")
        query = dict(team_id=12, include_batches=False, page_size=1)
        first = query_service.list_operations(OperationQuery(**query))
        second = query_service.list_operations(OperationQuery(page=2, **query))
        beyond = query_service.list_operations(OperationQuery(page=3, **query))
        self.assertEqual([2, 2, 2], [row["total"] for row in (first, second, beyond)])
        self.assertEqual([child, parent], [first["items"][0]["id"], second["items"][0]["id"]])
        self.assertEqual([], beyond["items"])
        self.assertEqual(
            [("team_join", 1), ("team_sync", 1)],
            [(item["value"], item["count"]) for item in first["facets"]["task_type"]],
        )
        self.assertEqual(
            [("failed", 1), ("success", 1)],
            [(item["value"], item["count"]) for item in first["facets"]["status"]],
        )
        combined = query_service.list_operations(OperationQuery(
            team_id=12, status="failed", include_batches=False,
        ))
        self.assertEqual(1, combined["total"])
        self.assertEqual([child], [item["id"] for item in combined["items"]])
        self.assertEqual(first["facets"]["status"], combined["facets"]["status"])
        empty = query_service.list_operations(OperationQuery(team_id=2, include_batches=False))
        self.assertEqual((0, []), (empty["total"], empty["items"]))
        self.assertTrue(all(not values for values in empty["facets"].values()))
        running = query_service.list_operations(OperationQuery(
            team_id=12, status="running", include_facets=False, include_batches=False,
        ))
        self.assertEqual((0, []), (running["total"], running["items"]))

    def test_gateway_persists_team_id_for_parent_and_child_tasks(self):
        parent = task_gateway.submit_durable_operation(
            task_type="team_sync", account_id=None, email="", team_id=12,
            source_id="team-submit-parent", dispatch=False,
        )
        child = task_gateway.submit_durable_operation(
            task_type="team_join", account_id=None, email="", team_id=12,
            source_id="team-submit-child", parent_task_id=parent["task_id"], dispatch=False,
        )
        found = operation_task_store.list_tasks(team_id=12, include_facets=False)
        self.assertEqual(2, found["total"])
        self.assertEqual({parent["task_id"], child["task_id"]}, {row["id"] for row in found["items"]})
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT team_id FROM {operation_task_store._table('operation_tasks')} ORDER BY id")
            self.assertEqual([12, 12], [row["team_id"] for row in cur.fetchall()])

    def test_team_batch_and_tasks_use_the_callers_transaction(self):
        with operation_task_store._connect() as conn:
            with self.assertRaisesRegex(RuntimeError, "回滚受理"):
                with conn.transaction():
                    batch = operation_task_store.create_runtime_batch(
                        batch_type="team_sync", title="Team 同步", requested_count=1, conn=conn,
                    )
                    task_gateway.submit_durable_operation(
                        task_type="team_sync", account_id=None, email="", team_id=12,
                        batch_id=batch["id"], source_id="team-rollback", conn=conn, dispatch=False,
                    )
                    raise RuntimeError("回滚受理")
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS n FROM {operation_task_store._table('operation_batches')}")
                self.assertEqual(0, cur.fetchone()["n"])
                cur.execute(f"SELECT COUNT(*) AS n FROM {operation_task_store._table('operation_tasks')}")
                self.assertEqual(0, cur.fetchone()["n"])

    def test_team_batch_navigation_only_contains_batches_with_matching_visible_tasks(self):
        team_batch = operation_task_store.create_runtime_batch(
            batch_type="team_sync", title="目标 Team", requested_count=1,
        )
        other_batch = operation_task_store.create_runtime_batch(
            batch_type="team_sync", title="其他 Team", requested_count=1,
        )
        for team_id, batch in ((12, team_batch), (112, other_batch)):
            task_gateway.submit_durable_operation(
                task_type="team_sync", account_id=None, email="", team_id=team_id,
                batch_id=batch["id"], source_id=f"team-batch-{team_id}", dispatch=False,
            )
        result = query_service.list_operations(OperationQuery(team_id=12))
        self.assertEqual([team_batch["id"]], [batch["id"] for batch in result["batches"]])
        self.assertEqual(1, result["total"])

    def test_reused_task_keeps_original_batch_and_matches_each_exact_batch_reference(self):
        old_batch, new_batch, other_batch = [
            operation_task_store.create_runtime_batch(
                batch_type="team_sync", title=title, requested_count=1,
            )
            for title in ("原同步批次", "复用同步批次", "其他团队批次")
        ]
        reused = task_gateway.submit_durable_operation(
            task_type="team_sync", account_id=None, email="", team_id=12,
            batch_id=old_batch["id"], source_id="team-multi-batch-reused", dispatch=False,
        )
        other = task_gateway.submit_durable_operation(
            task_type="team_sync", account_id=None, email="", team_id=112,
            batch_id=other_batch["id"], source_id="team-multi-batch-other", dispatch=False,
        )
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {operation_task_store._table('operation_batch_items')}
                    (batch_id,task_id,run_id,ordinal) VALUES (%s,%s,%s,1),(%s,%s,%s,2)""",
                (new_batch["id"], reused["task_id"], reused["run_id"],
                 new_batch["id"], other["task_id"], other["run_id"]),
            )
        reused_query = query_service.list_operations(OperationQuery(
            team_id=12, batch_id=new_batch["id"], include_batches=False,
        ))
        self.assertEqual(1, reused_query["total"])
        self.assertEqual([reused["task_id"]], [item["id"] for item in reused_query["items"]])
        self.assertEqual(old_batch["id"], reused_query["items"][0]["batch_id"])
        navigation = query_service.list_operations(OperationQuery(team_id=12))
        self.assertEqual(
            [new_batch["id"], old_batch["id"]], [batch["id"] for batch in navigation["batches"]],
        )
        local = task_gateway.submit_durable_operation(
            task_type="team_reverify", account_id=None, email="", team_id=12,
            batch_id=new_batch["id"], source_id="team-multi-batch-local", dispatch=False,
        )
        with operation_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {operation_task_store._table('operation_tasks')} SET status='success' WHERE id=%s",
                (local["task_id"],),
            )
            cur.execute(
                f"UPDATE {operation_task_store._table('operation_runs')} SET status='success' WHERE id=%s",
                (local["run_id"],),
            )
        filtered = query_service.list_operations(OperationQuery(
            team_id=12, batch_id=new_batch["id"], status="success",
            page_size=1, include_batches=False,
        ))
        self.assertEqual(1, filtered["total"])
        self.assertEqual([local["task_id"]], [item["id"] for item in filtered["items"]])
        self.assertEqual(
            [("queued", 1), ("success", 1)],
            [(item["value"], item["count"]) for item in filtered["facets"]["status"]],
        )
        old = query_service.list_operations(OperationQuery(
            team_id=12, batch_id=old_batch["id"], include_batches=False,
        ))
        self.assertEqual([reused["task_id"]], [item["id"] for item in old["items"]])
        beyond = query_service.list_operations(OperationQuery(
            team_id=12, batch_id=new_batch["id"], page=3, page_size=1, include_batches=False,
        ))
        self.assertEqual((2, []), (beyond["total"], beyond["items"]))
        self.assertEqual(
            [("team_reverify", 1), ("team_sync", 1)],
            [(item["value"], item["count"]) for item in beyond["facets"]["task_type"]],
        )

    def test_team_coordinators_keep_control_after_child_creation_and_completion(self):
        from core.storage.operations import runtime

        for task_type in ("team_join", "team_join_request", "team_probe", "team_sync", "team_reverify"):
            with self.subTest(task_type=task_type):
                parent = task_gateway.submit_durable_operation(
                    task_type=task_type, account_id=None, email="", team_id=12,
                    source_system="team_management", source_id=f"{task_type}-parent", dispatch=False,
                )
                child = task_gateway.submit_durable_operation(
                    task_type="team_invite", account_id=None, email="", team_id=12,
                    source_system="team_management", source_id=f"{task_type}-child",
                    parent_task_id=parent["task_id"], dispatch=False,
                )
                with operation_task_store._connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"SELECT status FROM {operation_task_store._table('operation_runs')} WHERE id=%s",
                        (parent["run_id"],),
                    )
                    self.assertEqual("queued", cur.fetchone()["status"])
                    cur.execute(
                        f"UPDATE {operation_task_store._table('operation_runs')} SET status='success' WHERE id=%s",
                        (child["run_id"],),
                    )
                    cur.execute(
                        f"UPDATE {operation_task_store._table('operation_tasks')} SET status='success' WHERE id=%s",
                        (child["task_id"],),
                    )
                    runtime._reconcile_parent_task_cur(cur, parent["task_id"], child_task_id=child["task_id"])
                    cur.execute(
                        f"SELECT status FROM {operation_task_store._table('operation_runs')} WHERE id=%s",
                        (parent["run_id"],),
                    )
                    self.assertEqual("queued", cur.fetchone()["status"])
