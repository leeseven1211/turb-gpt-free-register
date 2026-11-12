"""通过真实Flask和隔离PostgreSQL验证批次受理与固定范围。"""
from __future__ import annotations

import uuid
from unittest.mock import patch

from core.bulk_operations import service
from core.storage import records
from core.storage.operations import bulk
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class BulkApiTests(PostgresTestCase):
    def setUp(self):
        from core.storage.operations import legacy_task_store
        self.legacy_schema = patch.object(legacy_task_store, "_SCHEMA", self.schema)
        self.legacy_ready = patch.object(legacy_task_store, "_READY_KEY", "")
        self.legacy_schema.start()
        self.legacy_ready.start()
        self.addCleanup(self.legacy_schema.stop)
        self.addCleanup(self.legacy_ready.stop)
        legacy_task_store.init()
        bulk.reset_ready()
        bulk.init()
        self.client = create_app(auth_code="bulk-isolated-test").test_client()
        self.headers = {"X-Auth-Code": "bulk-isolated-test"}
        self.ids = self.seed(records.ACCOUNTS, [{"email": f"bulk-api-{n}@example.test", "created_at": "2026-10-15T12:00:00",
            "updated_at": "2026-10-15T12:00:00", "plan_check_status": "success", "plan_check_ok": True,
            "plus_promo_kind": "none", "current_plan_type": "free"} for n in range(5)])

    def post(self, path, body, key=None):
        return self.client.post("/api/bulk" + path, json=body,
            headers={**self.headers, "Idempotency-Key": key or uuid.uuid4().hex})

    def get(self, path):
        response = self.client.get("/api/bulk" + path, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json["data"]

    def create(self, source=None, execution=None):
        settings = self.get("/catalog")["operations"][0]
        revision = str(settings["effective_settings"]["config_revision"])
        selection_response = self.post("/selections", {"operation": {"key": "plan_check", "version": 1},
            "source": source or {"kind": "query", "query": {"date_from": "2026-10-01", "date_to": "2026-10-31", "filters": {"promotion": ["none"]}}},
            "parameters": {}, "expected_config_revision": revision})
        self.assertEqual(selection_response.status_code, 202, selection_response.json)
        selection_id = selection_response.json["data"]["id"]
        service.run_once("selection")
        selection = self.get(f"/selections/{selection_id}")
        self.assertEqual(selection["state"], "ready", selection)
        body = {"operation": {"key": "plan_check", "version": 1}, "selection_id": selection_id,
                "selection_revision": selection["selection_revision"], "parameters": {}, "expected_config_revision": revision,
                "execution": execution or {"max_concurrency": 3}}
        key = uuid.uuid4().hex
        response = self.post("/batches", body, key)
        self.assertEqual(response.status_code, 202, response.json)
        replay = self.post("/batches", body, key)
        self.assertEqual(replay.status_code, 202, replay.json)
        self.assertEqual(response.json["data"]["id"], replay.json["data"]["id"])
        return response.json["data"]

    def test_create_paused_and_control_require_batch_scope(self):
        batch = self.create(execution={"max_concurrency": 3, "start_paused": True})
        self.assertTrue(batch["control"]["paused"])
        detail = self.get(f'/batches/{batch["id"]}')
        self.assertTrue(detail["control"]["paused"])
        self.assertEqual(5, detail["summary"]["pending_submit"])
        invalid = self.post(f'/batches/{batch["id"]}/control', {"action": "pause",
            "expected_control_revision": 1, "scope": {"kind": "round", "round_id": batch["round_id"]}})
        self.assertEqual(422, invalid.status_code)
        self.assertEqual("parameter_invalid", invalid.json["error"]["code"])
        for revision, action in enumerate(("resume", "pause"), 1):
            body = {"action": action, "expected_control_revision": revision, "scope": {"kind": "batch"}}
            key = uuid.uuid4().hex
            response = self.post(f'/batches/{batch["id"]}/control', body, key)
            replay = self.post(f'/batches/{batch["id"]}/control', body, key)
            self.assertEqual(202, response.status_code, response.json)
            self.assertEqual(response.json["data"]["id"], replay.json["data"]["id"])
            self.assertEqual("completed", response.json["data"]["state"])
            self.assertEqual(action == "pause", self.get(f'/batches/{batch["id"]}')["control"]["paused"])

    def test_start_paused_rejects_non_boolean(self):
        for value in (1, "true", None):
            response = self.post("/batches", {"operation": {"key": "plan_check", "version": 1},
                "selection_revision": 1, "execution": {"start_paused": value}})
            self.assertEqual(422, response.status_code)
            self.assertEqual("parameter_invalid", response.json["error"]["code"])

    def test_create_read_and_cancel_fixed_targets(self):
        batch = self.create()
        self.assertIsInstance(batch["id"], str)
        detail = self.get(f'/batches/{batch["id"]}')
        self.assertEqual(detail["target_count"], 5)
        self.assertEqual(detail["summary"]["pending_submit"], 5)
        targets = self.get(f'/batches/{batch["id"]}/targets?page_size=2')
        self.assertEqual(len(targets["items"]), 2)
        self.assertTrue(targets["page"]["next_cursor"])
        body = {"action": "cancel_not_started", "expected_control_revision": detail["control"]["revision"], "scope": {"kind": "batch"}}
        response = self.post(f'/batches/{batch["id"]}/control', body)
        self.assertEqual(response.status_code, 202, response.json)
        service.run_once("selection")
        detail = self.get(f'/batches/{batch["id"]}')
        self.assertEqual(detail["summary"]["cancelled"], 5)

    def test_invalid_result_filter_is_rejected_before_round_acceptance(self):
        batch = self.create()
        cases = [{"result_filters": {"access_token": "value"}},
                 {"reason_codes": ["x"] * 31}, {"reason_codes": ["x" * 121]}]
        for invalid in cases:
            with self.subTest(invalid=invalid):
                response = self.post(f'/batches/{batch["id"]}/rounds', {
                    "source": {"view": "current"},
                    "selection": {"kind": "result_filter", "states": ["failed"], **invalid}})
                self.assertEqual(response.status_code, 422, response.json)
                self.assertEqual(response.json["error"]["code"], "invalid_result_filter")
        rounds = self.get(f'/batches/{batch["id"]}/rounds')
        self.assertEqual(len(rounds["items"]), 1)

    def test_shared_query_limit_and_missing_ids(self):
        batch = self.create({"kind": "query", "query": {"limit": 2}})
        self.assertEqual(batch["target_count"], 2)
        batch2 = self.create({"kind": "ids", "ids": [str(self.ids[0]), "999999"]})
        self.assertEqual(batch2["target_count"], 2)

    def test_cursor_is_bound_to_resource_and_filters(self):
        batch = self.create()
        path = f'/batches/{batch["id"]}/targets?page_size=2'
        first = self.get(path)
        cursor = first["page"]["next_cursor"]
        second = self.get(path + "&cursor=" + cursor)
        self.assertFalse({x["target_id"] for x in first["items"]} & {x["target_id"] for x in second["items"]})
        response = self.client.get("/api/bulk" + path + "&state[]=failed&cursor=" + cursor, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["error"]["code"], "cursor_scope_mismatch")

    def test_request_validation_and_auth(self):
        self.assertEqual(self.client.get("/api/bulk/catalog").status_code, 401)
        response = self.post("/selections", {"sql": "select *"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["error"]["code"], "field_not_supported")
        response = self.client.post("/api/bulk/selections", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 422)

    def test_get_does_not_start_workers_or_execute_external_operations(self):
        with patch("core.bulk_operations.service.start_workers") as start, patch("core.bulk_operations.adapters.submit_chunk") as submit:
            self.get("/catalog")
            self.get("/batches")
        start.assert_not_called()
        submit.assert_not_called()

    def test_selection_replay_survives_configuration_change(self):
        settings = self.get("/catalog")["operations"][0]
        body = {"operation": {"key": "plan_check", "version": 1}, "parameters": {},
                "expected_config_revision": str(settings["effective_settings"]["config_revision"]),
                "source": {"kind": "ids", "ids": [str(self.ids[0])]}}
        key = uuid.uuid4().hex
        first = self.post("/selections", body, key)
        self.assertEqual(first.status_code, 202, first.json)
        with patch("core.bulk_operations.catalog.capture_settings", side_effect=AssertionError("原回执不得读取新配置")):
            again = self.post("/selections", body, key)
        self.assertEqual(again.status_code, 202, again.json)
        self.assertEqual(first.json["data"]["id"], again.json["data"]["id"])

    def test_old_task_retry_header_keeps_one_round(self):
        from core.bulk_operations import adapters
        batch = self.create()
        bulk.process_batch(int(batch["id"]), adapters.submit_chunk)
        task_id = bulk.list_targets(int(batch["id"]))["items"][0]["task_id"]
        headers = {**self.headers, "Idempotency-Key": uuid.uuid4().hex}
        path = f"/api/operations/{task_id}/retry"
        first = self.client.post(path, headers=headers)
        second = self.client.post(path, headers=headers)
        self.assertEqual(first.status_code, 202, first.json)
        self.assertEqual(second.status_code, 202, second.json)
        self.assertEqual(first.json["round_id"], second.json["round_id"])
        rounds = bulk.list_rounds(int(batch["id"]))["items"]
        self.assertEqual(len(rounds), 2)

    def test_history_round_pagination_and_old_round_view(self):
        batch = self.create()
        batch_id = int(batch["id"])
        for _ in range(42):
            rnd = bulk.create_round(batch_id, request_key=uuid.uuid4().hex, source={"view": "current"},
                                    selection={"kind": "result_filter", "states": ["failed"]})
            bulk.freeze_round(rnd["id"])
        detail = self.get(f"/batches/{batch_id}")
        cursor = detail["rounds_next_cursor"]
        seen = {x["id"] for x in detail["rounds_head"]}
        pages = 1
        while cursor:
            data = self.get(f"/batches/{batch_id}/rounds?cursor={cursor}")
            page_ids = {x["id"] for x in data["items"]}
            self.assertFalse(seen & page_ids)
            seen.update(page_ids)
            cursor = data["page"]["next_cursor"]
            pages += 1
        self.assertEqual(len(seen), 43)
        self.assertEqual(pages, 3)
        old = self.get(f'/batches/{batch_id}?view=round&round_id={batch["round_id"]}')
        self.assertEqual(old["selected_round"]["id"], batch["round_id"])

    def test_invalid_revision_is_422(self):
        for revision in (None, True, "1", 0):
            response = self.post("/batches", {"operation": {"key": "plan_check", "version": 1},
                "selection_id": "1", "selection_revision": revision})
            self.assertEqual(response.status_code, 422, response.json)
