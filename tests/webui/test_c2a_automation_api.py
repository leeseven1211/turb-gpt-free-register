"""C2A 巡检入口使用已保存配置，并返回可跟踪的任务回执。"""
import hashlib
from unittest.mock import patch

from config import c2a as c2a_config
from core import operation_task_store
from core.integrations.c2a import client, monitor
from core.operations import task_gateway
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class C2AAutomationApiTests(PostgresTestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def test_status_requires_login_and_returns_monitor_summary(self):
        self.assertEqual(401, self.client.get("/api/c2a/automation").status_code)
        status = {"enabled": False, "max_per_cycle": 500, "repair_stages": {"refresh_wait": 2}}
        with patch.object(monitor, "status", return_value=status):
            response = self.client.get("/api/c2a/automation", headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "monitor": status}, response.json)

    def test_manual_check_queues_a_scan_without_starting_execution(self):
        self.assertEqual(401, self.client.post("/api/c2a/automation/check", json={}).status_code)
        base = "https://fixture-c2a.example.test"
        key = "fixture-c2a-key"
        forbidden = AssertionError("Web 不能注册执行处理器或请求远端")
        with (
            patch.multiple(c2a_config, C2A_API_BASE=base, C2A_API_KEY=key, C2A_MONITOR_ENABLED=False),
            patch.object(task_gateway, "register_operation_handler", side_effect=forbidden),
            patch.object(client, "list_configured_accounts", side_effect=forbidden),
        ):
            response = self.client.post("/api/c2a/automation/check", headers=self.headers, json={})
        self.assertEqual(202, response.status_code, response.json)
        self.assertEqual({"ok", "accepted", "task_id", "run_id", "status", "message"}, set(response.json))
        self.assertTrue(response.json["ok"])
        self.assertTrue(response.json["accepted"])
        self.assertEqual("queued", response.json["status"])
        run = operation_task_store.get_run(response.json["run_id"])
        self.assertEqual(response.json["task_id"], run["task_id"])
        self.assertEqual("c2a_scan", run["task_type"])
        self.assertEqual(hashlib.sha256(base.encode()).hexdigest(), run["data"]["backend_identity"])
        self.assertIs(run["data"]["force"], True)
        self.assertNotIn(key, str(run["data"]))

    def test_manual_check_rejects_query_and_every_body_except_empty_json_object(self):
        inputs = [
            ("?api_base=https://draft.test", {"json": {}}),
            ("", {"json": {"api_key": "draft"}}),
            ("", {"data": "{", "content_type": "application/json"}),
            ("", {"data": "", "content_type": "application/json"}),
            ("", {"data": "null", "content_type": "application/json"}),
            ("", {"json": []}),
            ("", {"json": False}),
            ("", {"data": "{}", "content_type": "text/plain"}),
        ]
        with patch.object(monitor, "run_once") as run_once:
            for query, options in inputs:
                with self.subTest(query=query, options=options):
                    response = self.client.post(f"/api/c2a/automation/check{query}", headers=self.headers, **options)
                    self.assertEqual(400, response.status_code)
                    self.assertEqual("config_invalid", response.json["error_code"])
                    self.assertNotIn("draft", response.get_data(as_text=True))
        run_once.assert_not_called()

    def test_manual_check_returns_a_fixed_reason_when_configuration_is_invalid(self):
        rejection = {"accepted": False, "error_code": "c2a_config_invalid", "error": "upstream request body"}
        with patch.object(monitor, "run_once", return_value=rejection):
            response = self.client.post("/api/c2a/automation/check", headers=self.headers, json={})
        self.assertEqual(503, response.status_code)
        self.assertEqual("c2a_config_invalid", response.json["error_code"])
        self.assertNotIn(rejection["error"], response.get_data(as_text=True))
