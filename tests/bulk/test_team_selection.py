"""Team 加入专用名单不接受其他操作、目标或修订。"""
from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from core.bulk_operations import catalog, service
from core.storage import records
from core.storage.operations import bulk, bulk_common
from tests.support_pg import PostgresTestCase


class TeamSelectionParameterTests(unittest.TestCase):
    def test_legacy_batch_catalog_only_advertises_executable_batch_operations(self):
        from flask import Flask
        from webui.routes.bulk import create_bulk_blueprint
        app = Flask(__name__)
        app.register_blueprint(create_bulk_blueprint(None))
        response = app.test_client().get("/api/bulk/catalog")
        self.assertEqual(200, response.status_code)
        result = response.get_json()["data"]
        self.assertEqual([
            "plan_check", "token_refresh", "password_setup", "twofa_setup", "codex_retry", "account_completion",
        ], [item["key"] for item in result["operations"]])
        self.assertEqual(["team_join"], [item["key"] for item in result["selection_operations"]])

    def test_team_join_catalog_has_required_exact_team_id(self):
        result = catalog.catalog()
        entry = next(item for item in result["selection_operations"] if item["key"] == "team_join")
        self.assertEqual(1, entry["version"])
        self.assertEqual("account", entry["target_kind"])
        self.assertFalse(entry["parameter_schema"]["team_id"]["optional"])
        self.assertEqual({"team_id": "9007199254740993"},
                         catalog.normalize_parameters("team_join", {"team_id": "9007199254740993"}))

    def test_selection_creation_still_accepts_team_join_without_advertising_legacy_execution(self):
        def create_selection(**values):
            self.assertEqual("team_join", values["operation_key"])
            self.assertEqual({"team_id": "7"}, values["parameters"])
            self.assertEqual({"kind": "ids", "entity": "account", "ids": [101]}, values["source"])
            return {"id": 31, "status": "preparing", "reused": False}
        store = SimpleNamespace(init=lambda: None, find_selection_request=lambda key: None,
                                create_selection=create_selection)
        with patch.object(service, "_store", return_value=store):
            accepted = service.create_selection({
                "operation": {"key": "team_join", "version": 1}, "parameters": {"team_id": "7"},
                "source": {"kind": "ids", "entity": "account", "ids": ["101"]},
            }, "team-selection-catalog-regression")
        self.assertEqual({"id": 31, "status": "preparing", "reused": False}, accepted)

    def test_team_join_rejects_missing_or_invalid_team_id(self):
        for parameters in ({}, {"team_id": 1}, {"team_id": "0"}, {"team_id": "01"},
                           {"team_id": "1", "driver": "protocol"}, {"team_id": "9223372036854775808"}):
            with self.subTest(parameters=parameters), self.assertRaises(catalog.ParameterError):
                catalog.normalize_parameters("team_join", parameters)


class TeamSelectionStorageTests(PostgresTestCase):
    def setUp(self):
        bulk.reset_ready()
        bulk.init()
        self.ids = self.seed(records.ACCOUNTS, [
            {"email": "team-one@example.test", "password": "synthetic"},
            {"email": "team-two@example.test", "access_token": "synthetic"},
        ])

    def selection(self, *, operation="team_join", team_id="7"):
        selected = bulk.create_selection(
            request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": self.ids},
            operation_key=operation, operation_version=1,
            parameters={"team_id": team_id} if operation == "team_join" else {},
            config_revision="team_join.v1",
        )
        return bulk.freeze_selection(selected["id"])

    def test_frozen_emails_survive_account_changes_and_preview_is_readonly(self):
        from core.teams.selection import read_team_selection
        selected = self.selection()
        records.patch_row(records.ACCOUNTS, self.ids[0], {"email": "changed@example.test"})
        frozen = read_team_selection(str(selected["id"]), 1, "7")
        self.assertEqual([str(value) for value in self.ids], frozen["account_ids"])
        self.assertEqual("team-one@example.test", frozen["expected_emails"][str(self.ids[0])])
        self.assertEqual("ready", bulk.get_selection(selected["id"])["status"])

    def test_operation_team_revision_and_expiration_have_distinct_errors(self):
        from core.teams.errors import TeamError
        from core.teams.selection import read_team_selection
        selected = self.selection()
        other = self.selection(operation="plan_check")
        for selected_id, revision, team_id, code in (
            (other["id"], 1, "7", "selection_operation_mismatch"),
            (selected["id"], 1, "8", "selection_team_mismatch"),
            (selected["id"], 2, "7", "selection_revision_mismatch"),
        ):
            with self.subTest(code=code), self.assertRaises(TeamError) as error:
                read_team_selection(str(selected_id), revision, team_id)
            self.assertEqual(code, error.exception.code)
        with bulk_common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {bulk_common.table('operation_selections')} SET expires_at=now()-interval '1 second' WHERE id=%s",
                        (selected["id"],))
        with self.assertRaises(TeamError) as expired:
            read_team_selection(str(selected["id"]), 1, "7")
        self.assertEqual("selection_expired", expired.exception.code)
        self.assertEqual(410, expired.exception.status)

    def test_for_consumption_requires_callers_transaction(self):
        from core.teams.errors import TeamError
        from core.teams.selection import read_team_selection
        selected = self.selection()
        with self.assertRaises(TeamError) as error:
            read_team_selection(str(selected["id"]), 1, "7", for_consumption=True)
        self.assertEqual("selection_transaction_required", error.exception.code)

    def test_preparing_selection_reports_not_ready_before_revision_check(self):
        from core.teams.errors import TeamError
        from core.teams.selection import read_team_selection
        selected = bulk.create_selection(
            request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": self.ids},
            operation_key="team_join", parameters={"team_id": "7"}, config_revision="team_join.v1")
        with self.assertRaises(TeamError) as error:
            read_team_selection(str(selected["id"]), 1, "7")
        self.assertEqual("selection_not_ready", error.exception.code)

    def test_old_query_selection_replay_accepts_missing_default_team_scope(self):
        payload = {"operation": {"key": "team_join", "version": 1}, "parameters": {"team_id": "7"},
                   "source": {"kind": "query", "query": {"archived": "all"}}}
        request_key = uuid.uuid4().hex
        selected = service.create_selection(payload, request_key)
        with bulk_common.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""UPDATE {bulk_common.table('operation_selections')}
                    SET query_spec=query_spec #- '{{source,query,team_scope}}'
                    WHERE id=%s""", (selected["id"],))
        replay = service.create_selection(payload, request_key)
        self.assertEqual(selected["id"], replay["id"])

    def test_async_http_selection_keeps_snapshot_and_cannot_enter_legacy_batch(self):
        from core.teams.selection import read_team_selection
        from webui.app import create_app
        client = create_app(auth_code="team-selection").test_client()
        headers = {"X-Auth-Code": "team-selection", "Idempotency-Key": uuid.uuid4().hex}
        payload = {"operation": {"key": "team_join", "version": 1}, "parameters": {"team_id": "7"},
                   "source": {"kind": "ids", "entity": "account", "ids": [str(value) for value in self.ids]}}
        accepted = client.post("/api/bulk/selections", json=payload, headers=headers)
        self.assertEqual(202, accepted.status_code, accepted.get_json())
        selection_id = accepted.get_json()["data"]["id"]
        self.assertEqual("preparing", accepted.get_json()["data"]["state"])
        with patch("core.bulk_operations.adapters.preflight_many", side_effect=AssertionError("不得借其他领域预检")):
            service.run_once("selection")
        selected = client.get(f"/api/bulk/selections/{selection_id}", headers=headers)
        self.assertEqual(200, selected.status_code)
        self.assertEqual("ready", selected.get_json()["data"]["state"])
        frozen = read_team_selection(selection_id, 1, "7")
        self.assertEqual([str(value) for value in self.ids], frozen["account_ids"])
        records.patch_row(records.ACCOUNTS, self.ids[0], {"email": "new-identity@example.test"})
        replay = client.post("/api/bulk/selections", json=payload, headers=headers)
        self.assertEqual(selection_id, replay.get_json()["data"]["id"])
        self.assertEqual("team-one@example.test", read_team_selection(selection_id, 1, "7")["expected_emails"][str(self.ids[0])])
        denied = client.post("/api/bulk/batches", json={
            "operation": {"key": "team_join", "version": 1}, "parameters": {"team_id": "7"},
            "selection_id": selection_id, "selection_revision": 1,
        }, headers={**headers, "Idempotency-Key": uuid.uuid4().hex})
        self.assertEqual(422, denied.status_code)
        self.assertEqual("team_join_endpoint_required", denied.get_json()["error"]["code"])

    def test_join_request_consumption_is_visible_to_preview_and_later_join(self):
        from core.storage.teams import schema
        from core.teams.errors import TeamError
        from core.teams.selection import read_team_selection
        schema.init()
        selected = self.selection()
        with bulk_common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {bulk_common.table('team_workspaces')}
                (id,workspace_id,manager_account_id) VALUES (7,'consumed-workspace',%s)""", (self.ids[0],))
            read_team_selection(str(selected["id"]), 1, "7", for_consumption=True, conn=conn)
            cur.execute(f"""INSERT INTO {bulk_common.table('team_join_requests')}
                (team_id,selection_id,selection_revision,requested_count,unique_count)
                VALUES (7,%s,1,2,2) RETURNING id""", (selected["id"],))
            request_id = cur.fetchone()["id"]
        for consumption in (False, True):
            with self.subTest(consumption=consumption), self.assertRaises(TeamError) as error:
                with bulk_common.connect() as conn:
                    read_team_selection(str(selected["id"]), 1, "7", for_consumption=consumption, conn=conn)
            self.assertEqual("selection_consumed", error.exception.code)
            self.assertEqual(str(request_id), error.exception.details["existing_join_request_id"])
