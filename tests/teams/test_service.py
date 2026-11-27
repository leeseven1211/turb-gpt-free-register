"""Team 服务的持久受理、预检及窄响应。"""
from tests.support_pg import PostgresTestCase


class TeamServiceTests(PostgresTestCase):
    def setUp(self):
        from core.storage.teams import repository
        from core.storage import records
        repository.init()
        self.repository = repository
        self.account_id = self.seed(records.ACCOUNTS, [{
            "email": "manager@example.test", "password": "test-only-password",
            "access_token": "test-only-token", "archived": True,
        }])[0]

    def bind(self, key="team-bind-key-0001"):
        from core.teams import service
        probe = self.repository.create_probe(manager_account_id=self.account_id)
        probe = self.repository.update_probe(probe["id"], status="success", stage="complete",
                                             workspaces=[{
                                                 "workspace_id": "workspace-test",
                                                 "workspace_type": "team", "name": "测试团队",
                                                 "role": "owner", "can_manage": True,
                                                 "capabilities": {"read_members": True,
                                                                  "read_invitations": True,
                                                                  "invite_members": True},
                                                 "purchased_seats": None,
                                             }])
        return service.create_team({
            "manager_account_id": str(self.account_id), "workspace_id": "workspace-test",
            "probe_id": str(probe["id"]), "probe_revision": probe["revision"],
        }, key)

    def test_bind_receipt_survives_probe_expiry_and_hides_private_fields(self):
        from core.teams import service
        result = self.bind()
        team = result["team"]
        self.assertEqual(str(self.account_id), team["manager_account"]["id"])
        self.assertTrue(team["manager_account"]["archived"])
        self.assertNotIn("password", repr(result))
        self.assertNotIn("test-only-token", repr(result))
        self.assertIsNone(team["confirmed_member_count"])
        probe = self.repository.get_probe(1)
        payload = {
            "manager_account_id": str(self.account_id), "workspace_id": "workspace-test",
            "probe_id": str(probe["id"]), "probe_revision": probe["revision"],
        }
        self.repository.update_probe(probe["id"], status="failed", stage="complete")
        self.assertEqual(result, service.create_team(payload, "team-bind-key-0001"))

    def test_same_key_on_other_path_is_conflict_before_revision_check(self):
        from core.teams import service
        from core.teams.errors import TeamError
        team = self.bind()["team"]
        with self.assertRaises(TeamError) as raised:
            service.update_team(team["id"], {"expected_revision": 999, "display_name": "新名"},
                                "team-bind-key-0001")
        self.assertEqual("idempotency_conflict", raised.exception.code)

    def test_preview_has_no_database_writes_and_join_requires_limit(self):
        from core.teams import service
        from core.teams.errors import TeamError
        from core.storage import postgres, records
        team = self.bind()["team"]
        self.assertEqual(
            {"enabled": False, "reason_code": "team_limit_required"},
            service.get_team(team["id"])["actions"]["join"],
        )
        member_id = self.seed(records.ACCOUNTS, [{
            "email": "member@example.test", "password": "test-only-password",
        }])[0]
        payload = {"account_ids": [str(member_id), str(member_id)]}
        with postgres.connect() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            # preview 必须能在数据库只读事务内完成。
            result = service._preview_join(team["id"], payload, conn=conn)
        self.assertFalse(result["capacity"]["can_submit"])
        self.assertEqual(1, result["counts"]["duplicate_count"])
        with self.assertRaises(TeamError) as raised:
            service.submit_join(team["id"], payload, "team-join-key-0001")
        self.assertEqual("team_limit_required", raised.exception.code)

    def test_join_fixed_targets_return_pending_and_durable_task(self):
        from core.teams import service
        from core.storage import records
        team = self.bind()["team"]
        service.update_team(team["id"], {"expected_revision": team["revision"],
                                        "planned_member_limit": 4}, "team-patch-key-0001")
        member_id = self.seed(records.ACCOUNTS, [{
            "email": "member@example.test", "password": "test-only-password",
        }])[0]
        result = service.submit_join(team["id"], {
            "account_ids": [str(member_id), str(member_id)],
        }, "team-join-key-0001")
        self.assertTrue(result["accepted"])
        self.assertIsNotNone(result["task_id"])
        self.assertEqual(1, result["counts"]["pending_count"])
        self.assertEqual(1, result["counts"]["duplicate_count"])
        receipt = service.get_join_request(team["id"], result["id"], {"page": 1, "page_size": 20})
        self.assertEqual(1, receipt["total"])
        self.assertEqual(str(member_id), receipt["items"][0]["account_id"])

    def test_real_http_receipts_conform_to_openapi_without_mocking_service(self):
        from flask import Flask
        from webui.routes.teams import create_teams_blueprint
        from tests.teams.test_http_routes import _assert_response_contract
        from core.storage import records
        from core.teams import service

        team = self.bind()["team"]
        service.update_team(team["id"], {"expected_revision": team["revision"],
                                        "planned_member_limit": 4}, "team-patch-key-http")
        member_id = self.seed(records.ACCOUNTS, [{
            "email": "http-member@example.test", "password": "test-only-password",
        }])[0]
        app = Flask(__name__)
        app.register_blueprint(create_teams_blueprint(None))
        client = app.test_client()
        requests = [
            ("get", "/api/teams", None),
            ("get", f"/api/teams/{team['id']}", None),
            ("post", f"/api/teams/{team['id']}/join-preview", {"account_ids": [str(member_id)]}),
            ("post", f"/api/teams/{team['id']}/join", {"account_ids": [str(member_id)]}),
            ("post", "/api/teams/sync-bulk", {"team_ids": [team["id"], team["id"], "999999"]}),
        ]
        for ordinal, (method, path, payload) in enumerate(requests):
            with self.subTest(path=path):
                response = getattr(client, method)(path, json=payload, headers={
                    "Idempotency-Key": f"team-http-integration-{ordinal:04d}",
                })
                self.assertLess(response.status_code, 300, response.get_json())
                _assert_response_contract(response, method, path)
