"""原生刷新诊断的运行隔离、生命周期及受保护下载入口。"""
from pathlib import Path
from tempfile import mkdtemp
from types import SimpleNamespace
import logging
import unittest
from unittest.mock import patch

from flask import Flask

from core import operation_debug, registration_debug
from webui import runtime
from webui.routes import operations


class OperationDebugTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(mkdtemp(prefix="turb-operation-debug-"))
        self.patch_root = patch.object(registration_debug, "_ARTIFACT_ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.task = {"id": 41, "task_uuid": "task-fixture", "task_type": "token_refresh",
                     "source_system": "native_operations", "runs": [
                         {"id": 51, "run_uuid": "run-first", "status": "failed"},
                         {"id": 52, "run_uuid": "run-second", "status": "success"},
                     ]}

    def test_native_capture_does_not_read_or_write_registration_jobs_or_remove_their_session(self):
        context = SimpleNamespace(task_id=41, run_id=51)
        sentinel = object()
        registration_debug._ACTIVE[51] = sentinel
        self.addCleanup(registration_debug._ACTIVE.pop, 51, None)
        with (
            patch.object(operations.operation_task_store, "get_task", return_value=self.task),
            patch.object(registration_debug, "patch_job", side_effect=AssertionError("写入了注册任务")),
            patch("core.db.get_job", side_effect=AssertionError("读取了注册任务")),
        ):
            activation = operation_debug.activate(context)
            self.assertIsNotNone(activation)
            self.assertLess(activation.session.job_id, 0)
            registration_debug.capture_current_failure("密码页请求返回 HTTP 401")
            activation.session.record({"kind": "network_request", "url": "https://auth.openai.com/log-in/password",
                                       "method": "GET", "status": 401})
            operation_debug.deactivate(activation, "failed")

        self.assertIsNone(registration_debug.current_session())
        self.assertIs(sentinel, registration_debug._ACTIVE[51])
        first = operation_debug.describe(self.task, self.task["runs"][0])
        second = operation_debug.describe(self.task, self.task["runs"][1])
        self.assertTrue(first["available"])
        self.assertFalse(second["available"])
        job = operation_debug.artifact_job(self.task, self.task["runs"][0])
        self.assertEqual(401, registration_debug.build_har(job)["log"]["entries"][0]["response"]["status"])

    def _client(self):
        app = Flask("operation-debug-test")
        context = runtime.WebUIContext(app, logging.getLogger("operation-debug-test"))
        app.register_blueprint(operations.create_operations_blueprint(context))
        return app.test_client()

    def test_imap_deadline_is_classified_as_mail_service_instead_of_unknown_or_browser_network(self):
        session = operation_debug.OperationDebugSession(
            operation_debug.artifact_job(self.task, self.task["runs"][0]), capture_mode="full",
        )
        category = session._failure_category(
            "Roxy ForwardIMAPError: 本机 Gmail IMAP 等待验证码超时（>240s）；读取阶段耗尽总预算",
            {"url": "https://auth.openai.com/email-verification", "dom": {"input_count": 1}},
        )
        self.assertEqual("mail_service", category)
        self.assertEqual("邮箱收码服务", session._failure_category_label(category))

    def test_unconfirmed_email_submission_preserves_auth_diagnostic_category(self):
        category = operation_debug.OperationDebugSession._failure_category(
            "email_submit_unconfirmed: 验证码提交结果未确认，state=stuck", {},
        )
        self.assertEqual("auth_submission_unconfirmed", category)
        self.assertEqual("认证提交未确认", operation_debug.OperationDebugSession._failure_category_label(category))

    def test_download_rejects_run_from_another_task_and_unrelated_task_type(self):
        client = self._client()
        with patch.object(operations.operation_task_store, "get_task", return_value=self.task):
            response = client.get("/api/operations/41/runs/999/debug/har")
            self.assertEqual(404, response.status_code)
        for kind, source in (("plan_check", "native_operations"), ("token_refresh", "account_action_tasks")):
            task = {**self.task, "task_type": kind, "source_system": source}
            with patch.object(operations.operation_task_store, "get_task", return_value=task):
                self.assertEqual(404, client.get("/api/operations/41/runs/51/debug/har").status_code)

    def test_debug_har_download_uses_matching_run_and_returns_attachment(self):
        session = operation_debug.OperationDebugSession(
            operation_debug.artifact_job(self.task, self.task["runs"][0]), capture_mode="full",
        )
        session.record({"kind": "network_request", "url": "https://auth.openai.com/log-in/password",
                        "method": "GET", "status": 401})
        session.finalize("failed")
        with patch.object(operations.operation_task_store, "get_task", return_value=self.task):
            response = self._client().get("/api/operations/41/runs/51/debug/har")
        self.assertEqual(200, response.status_code)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(401, response.get_json()["log"]["entries"][0]["response"]["status"])

    def test_inline_refresh_debug_is_accessible_from_its_own_parent_run(self):
        task = {**self.task, "task_type": "extract_link"}
        session = operation_debug.OperationDebugSession(operation_debug.artifact_job(task, task["runs"][0]), capture_mode="full")
        session.finalize("failed")
        with patch.object(operations.operation_task_store, "get_task", return_value=task):
            self.assertEqual(200, self._client().get("/api/operations/41/runs/51/debug/har").status_code)


if __name__ == "__main__":
    unittest.main()
