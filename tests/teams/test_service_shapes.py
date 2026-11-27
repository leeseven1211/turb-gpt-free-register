"""真实 Team 服务与 HTTP 的非空响应契约；仅使用隔离合成数据。"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from flask import Flask

from core.storage import records
from core.teams import execution
from tests.support_pg import PostgresTestCase
from tests.teams import test_service as service_support
from tests.teams.test_http_routes import _assert_response_contract
from webui.routes.teams import create_teams_blueprint


class TeamServiceShapeTests(PostgresTestCase):
    """借用服务夹具，不继承并重新执行其已有测试。"""

    bind = service_support.TeamServiceTests.bind

    def setUp(self):
        service_support.TeamServiceTests.setUp(self)
        self.enterContext(patch(
            "core.teams.remote.TeamRemoteAdapter._request",
            side_effect=AssertionError("响应契约测试不得请求远端"),
        ))
        self.enterContext(patch(
            "core.teams.auth.TeamAuthenticator.open",
            side_effect=AssertionError("响应契约测试不得恢复远端认证"),
        ))
        app = Flask(__name__)
        app.register_blueprint(create_teams_blueprint(None))
        self.client = app.test_client()

    def request_data(self, method, path, payload=None, *, status=200, key=None):
        response = getattr(self.client, method)(
            path, json=payload,
            headers={"Idempotency-Key": key} if key else {},
        )
        self.assertEqual(status, response.status_code, response.get_json())
        _assert_response_contract(response, method, path.split("?", 1)[0])
        return response.get_json()["data"]

    def assert_local_id(self, value):
        self.assertIsInstance(value, str)
        self.assertRegex(value, r"^[1-9][0-9]*$")

    def snapshot(self, team_id, *, members, invitations, seats=None, **references):
        team = self.repository.get_team(team_id)
        return self.repository.apply_sync_snapshot(
            team_id, workspace_id=team["workspace_id"],
            manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"],
            members=members, invitations=invitations, purchased_seats=seats,
            members_complete=True, invitations_complete=True, **references,
        )

    def pending_invitations(self):
        team = self.bind()["team"]
        ids = self.seed(records.ACCOUNTS, [
            {"email": f"shape-member-{index}@example.test", "password": "test-only-password"}
            for index in range(2)
        ])
        members = [{
            "remote_user_id": "shape-manager", "email": "manager@example.test",
            "account_id": self.account_id, "role": "owner",
        }]
        invitations = [{
            "remote_invitation_id": f"shape-invitation-{index}",
            "email": f"shape-member-{index}@example.test", "invitation_state": "pending",
        } for index in range(2)]
        self.snapshot(team["id"], members=members, invitations=invitations)
        rows = self.repository.list_invitations(team["id"])["items"]
        by_account = {row["account_id"]: row for row in rows}
        return team, members, invitations, [by_account[value] for value in ids]

    def test_probe_receipt_and_nonempty_success_and_failure_details_match_openapi(self):
        receipt = self.request_data(
            "post", "/api/teams/binding-probes",
            {"manager_account_id": str(self.account_id)}, status=202,
            key="team-shapes-probe-request-0001",
        )
        for field in ("probe_id", "task_id", "run_id"):
            self.assert_local_id(receipt[field])
        path = f"/api/teams/binding-probes/{receipt['probe_id']}"
        queued = self.request_data("get", path)
        self.assertEqual("queued", queued["status"])
        self.assertEqual(receipt["task_id"], queued["task_id"])
        self.assertEqual(receipt["run_id"], queued["run_id"])
        self.assertTrue(queued["manager_account"]["archived"])
        workspace = {
            "workspace_id": "shape-workspace", "workspace_type": "team", "name": "契约测试团队",
            "role": "owner", "can_manage": True, "purchased_seats": 0,
            "capabilities": {
                "read_members": True, "read_invitations": True, "invite_members": None,
            },
        }
        self.repository.update_probe(
            receipt["probe_id"], status="success", stage="complete", workspaces=[workspace],
        )
        succeeded = self.request_data("get", path)
        self.assertEqual([workspace], succeeded["workspaces"])
        self.assertEqual("shape-workspace", succeeded["suggested_workspace_id"])
        for field in ("completed_at", "expires_at"):
            self.assertIsNotNone(datetime.fromisoformat(succeeded[field]).utcoffset())
        self.assertGreater(
            datetime.fromisoformat(succeeded["expires_at"]),
            datetime.fromisoformat(succeeded["completed_at"]),
        )
        error = {
            "code": "team_permission_denied", "message": "测试管理权限已被拒绝",
            "stage": "permission_check", "retryable": True,
        }
        self.repository.update_probe(
            receipt["probe_id"], status="failed", stage="permission_check", error_info=error,
        )
        failed = self.request_data("get", path)
        self.assertEqual(error, failed["error_info"])
        self.assertIsNone(failed["expires_at"])

    def test_nonempty_members_expose_nullable_and_valid_task_references(self):
        bound = self.bind()
        team = bound["team"]
        member_id = self.seed(records.ACCOUNTS, [{
            "email": "shape-joined@example.test", "password": "test-only-password",
        }])[0]
        self.snapshot(team["id"], members=[{
            "remote_user_id": "shape-external", "email": "external@example.test", "role": "member",
        }], invitations=[])
        current = self.repository.get_team(team["id"])
        self.repository.apply_sync_snapshot(
            team["id"], workspace_id=current["workspace_id"],
            manager_account_id=current["manager_account_id"],
            manager_revision=current["manager_revision"],
            members=[{
                "remote_user_id": "shape-joined", "email": "shape-joined@example.test",
                "account_id": member_id, "role": "member", "execution_status": "queued",
            }], members_complete=False, invitations_complete=False,
            task_id=int(bound["sync"]["task_id"]), run_id=int(bound["sync"]["run_id"]),
        )
        data = self.request_data("get", f"/api/teams/{team['id']}/members?include_facets=1")
        self.assertEqual(2, data["total"])
        by_remote = {row["remote_user_id"]: row for row in data["items"]}
        linked = by_remote["shape-joined"]
        external = by_remote["shape-external"]
        self.assert_local_id(linked["id"])
        self.assertEqual(str(member_id), linked["account"]["id"])
        self.assertEqual({
            "task_id": bound["sync"]["task_id"], "run_id": bound["sync"]["run_id"], "status": "queued",
        }, linked["latest_task"])
        self.assertIsNone(external["account"])
        self.assertIsNone(external["latest_task"])

    def test_nonempty_invitation_list_and_details_keep_execution_shapes(self):
        team, _, _, rows = self.pending_invitations()
        pending, failed = rows
        submitted = execution.enqueue_operation(None, "team_join", {
            "team_id": int(team["id"]), "invitation_id": failed["id"],
            "account_id": failed["account_id"], "request_key": "team-shapes-invitation-task",
        })
        self.repository.update_invitation(team["id"], failed["id"], changes={
            "last_task_id": submitted["task_id"], "last_run_id": submitted["run_id"],
            "execution_status": "failed", "stage": "persist", "active": False,
            "reason_code": "team_save_failed", "error_message": "测试本地上下文保存失败",
        })
        path = f"/api/teams/{team['id']}/invitations"
        listed = self.request_data("get", path + "?include_facets=1")
        self.assertEqual(2, listed["total"])
        for row in listed["items"]:
            self.assert_local_id(row["id"])
            self.assert_local_id(row["account"]["id"])
            detail = self.request_data("get", path + f"/{row['id']}")["invitation"]
            self.assertEqual(row, detail)
        by_id = {row["id"]: row for row in listed["items"]}
        fresh = by_id[str(pending["id"])]["latest_execution"]
        self.assertEqual("none", fresh["status"])
        self.assertIsNone(fresh["task_id"])
        self.assertIsNone(fresh["run_id"])
        last = by_id[str(failed["id"])]
        self.assertEqual(str(submitted["task_id"]), last["latest_execution"]["task_id"])
        self.assertEqual(str(submitted["run_id"]), last["latest_execution"]["run_id"])
        self.assertEqual({
            "code": "team_save_failed", "message": "测试本地上下文保存失败",
            "stage": "persist", "retryable": True,
        }, last["latest_execution"]["error_info"])
        self.assertTrue(last["actions"]["continue"]["enabled"])
        self.assertTrue(last["actions"]["retry"]["enabled"])
        self.assertTrue(last["actions"]["view_task"]["enabled"])

    def test_single_and_bulk_continue_retry_receipts_keep_capacity_and_fixed_items(self):
        team, members, invitations, rows = self.pending_invitations()
        invitation_ids = [str(row["id"]) for row in rows]
        cases = [
            ("continue", False), ("retry", False), ("continue", True), ("retry", True),
        ]
        for ordinal, (action, bulk) in enumerate(cases):
            with self.subTest(action=action, bulk=bulk):
                if bulk:
                    self.snapshot(team["id"], members=members, invitations=invitations, seats=0)
                path = f"/api/teams/{team['id']}/invitations/"
                path += f"{action}-bulk" if bulk else f"{invitation_ids[0]}/{action}"
                payload = {"invitation_ids": [*invitation_ids, invitation_ids[0]]} if bulk else {}
                key = f"team-shapes-{action}-request-{ordinal:04d}"
                receipt = self.request_data("post", path, payload, status=202, key=key)
                replay = self.request_data("post", path, payload, status=202, key=key)
                self.assertEqual(receipt, replay)
                for field in ("id", "team_id", "batch_id", "task_id", "run_id"):
                    self.assert_local_id(receipt[field])
                self.assertEqual(action, receipt["operation"])
                counts = receipt["counts"]
                self.assertEqual(3 if bulk else 1, counts["requested_count"])
                self.assertEqual(2 if bulk else 1, counts["unique_count"])
                self.assertEqual(1 if bulk else 0, counts["duplicate_count"])
                self.assertEqual(counts["unique_count"], counts["pending_count"])
                self.assertEqual(
                    counts["unique_count"],
                    sum(counts[field] for field in (
                        "pending_count", "accepted_count", "skipped_count", "failed_count",
                    )),
                )
                capacity = receipt["capacity"]
                self.assertEqual(3, capacity["occupied_count"])
                self.assertEqual("purchased_seats" if bulk else "unavailable", capacity["basis"])
                self.assertEqual(0 if bulk else None, capacity["effective_limit"])
                self.assertEqual(0 if bulk else None, capacity["available_count"])
                self.assertEqual(bulk, capacity["can_submit"])
                self.assertEqual(None if bulk else "team_limit_required", capacity["blocking_reason_code"])
                items = self.request_data("get", receipt["items_url"])
                self.assertEqual(receipt, items["request"])
                self.assertEqual(counts["unique_count"], items["total"])
                self.assertTrue(items["items"])
                for item in items["items"]:
                    self.assert_local_id(item["account_id"])
                    self.assertEqual("pending", item["acceptance_status"])
                    self.assertEqual("none", item["execution_status"])
                    self.assertIsNone(item["task_id"])
                    self.assertIsNone(item["run_id"])
