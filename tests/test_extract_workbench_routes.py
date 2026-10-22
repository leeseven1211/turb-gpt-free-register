# -*- coding: utf-8 -*-
"""提链工作台路由的输入校验与安全投影。"""
from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from flask import Flask

from webui import runtime
from webui.app import create_app
from webui.routes import extract_workbench


class ExtractWorkbenchRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask("extract-workbench-routes")
        context = runtime.WebUIContext(app, logging.getLogger("extract-workbench-routes"))
        app.register_blueprint(extract_workbench.create_extract_workbench_blueprint(context))
        self.client = app.test_client()

    def test_config_returns_only_public_provider_fields(self):
        config = {
            "default_provider": "lumen_flow",
            "default_mode": "extract_only",
            "api_key": "provider-secret",
            "providers": [{
                "id": "lumen_flow",
                "label": "流光",
                "default_type": "trial",
                "modes": ["extract_only"],
                "api_base": "https://private.example/api",
                "cdk": "private-cdk",
            }],
        }
        with patch.object(
            extract_workbench.extract_link_service,
            "workbench_config",
            return_value=config,
            create=True,
        ):
            response = self.client.get("/api/extract-workbench/config")

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("lumen_flow", payload["default_provider"])
        self.assertEqual("extract_only", payload["default_mode"])
        self.assertEqual(
            [{"id": "lumen_flow", "label": "流光", "default_type": "trial", "modes": ["extract_only"]}],
            payload["providers"],
        )
        self.assertNotIn("provider-secret", response.get_data(as_text=True))
        self.assertNotIn("private-cdk", response.get_data(as_text=True))

    def test_task_list_validates_and_projects_supported_filters(self):
        service_result = {
            "items": [{
                "task_id": 11,
                "run_id": 22,
                "email": "person@example.test",
                "provider_id": "lumen_flow",
                "mode": "extract_only",
                "task_status": "running",
                "preflight_status": "passed",
                "extraction_status": "running",
                "payment_status": "not_started",
                "plus_status": "unknown",
                "run_count": 1,
                "progress": 40,
                "created_at": "2026-10-22T00:00:00Z",
                "updated_at": "2026-10-22T00:00:01Z",
                "message": "处理中",
                "error": "",
                "has_extract_link": False,
                "has_payment_link": False,
                "access_token": "must-not-project",
                "extract_link": "https://checkout.example/private",
            }],
            "total": 1,
            "page": 2,
            "page_size": 25,
            "counts": {"running": 1},
            "internal": "must-not-project",
        }
        with patch.object(
            extract_workbench.extract_link_service,
            "list_workbench_tasks",
            return_value=service_result,
            create=True,
        ) as list_tasks:
            response = self.client.get(
                "/api/extract-workbench/tasks?provider_id=lumen_flow&mode=extract_only"
                "&status=running&query=person&page=2&page_size=25"
            )

        self.assertEqual(200, response.status_code)
        list_tasks.assert_called_once_with(
            provider_id="lumen_flow",
            mode="extract_only",
            status="running",
            query="person",
            page=2,
            page_size=25,
        )
        payload = response.get_json()
        self.assertEqual(1, payload["total"])
        self.assertEqual(2, payload["page"])
        self.assertEqual({"running": 1}, payload["counts"])
        self.assertNotIn("access_token", payload["items"][0])
        self.assertNotIn("extract_link", payload["items"][0])
        self.assertNotIn("internal", payload)

    def test_task_list_rejects_invalid_pagination_without_calling_service(self):
        with patch.object(
            extract_workbench.extract_link_service,
            "list_workbench_tasks",
            create=True,
        ) as list_tasks:
            response = self.client.get("/api/extract-workbench/tasks?page=0&page_size=10000")

        self.assertEqual(400, response.status_code)
        list_tasks.assert_not_called()

    def test_task_list_treats_empty_frontend_filters_as_unset(self):
        with patch.object(
            extract_workbench.extract_link_service,
            "list_workbench_tasks",
            return_value={"items": [], "total": 0, "counts": {}},
            create=True,
        ) as list_tasks:
            response = self.client.get(
                "/api/extract-workbench/tasks?provider_id=&mode=&status=&query=&page=1&page_size=20"
            )

        self.assertEqual(200, response.status_code)
        list_tasks.assert_called_once_with(
            provider_id=None,
            mode=None,
            status=None,
            query="",
            page=1,
            page_size=20,
        )

    def test_create_rejects_credentials_and_nonpositive_account_ids(self):
        with patch.object(
            extract_workbench.extract_link_service,
            "create_workbench_tasks",
            create=True,
        ) as create_tasks:
            credential_response = self.client.post(
                "/api/extract-workbench/tasks",
                json={
                    "account_ids": [7],
                    "provider_id": "lumen_flow",
                    "mode": "extract_only",
                    "access_token": "never-accept-this",
                },
            )
            id_response = self.client.post(
                "/api/extract-workbench/tasks",
                json={"account_ids": [0], "provider_id": "lumen_flow", "mode": "extract_only"},
            )

        self.assertEqual(400, credential_response.status_code)
        self.assertEqual(400, id_response.status_code)
        self.assertNotIn("never-accept-this", credential_response.get_data(as_text=True))
        create_tasks.assert_not_called()

    def test_create_returns_durable_submission_counts(self):
        with patch.object(
            extract_workbench.extract_link_service,
            "create_workbench_tasks",
            return_value={"started": 2, "skipped": 1, "failed": 0},
            create=True,
        ) as create_tasks:
            response = self.client.post(
                "/api/extract-workbench/tasks",
                json={
                    "account_ids": ["7", "8", "9"],
                    "provider_id": "lumen_flow",
                    "mode": "extract_only",
                    "type": "trial",
                    "options": {"region": "us"},
                },
            )

        self.assertEqual(202, response.status_code)
        self.assertEqual({"ok": True, "started": 2, "skipped": 1, "failed": 0}, response.get_json())
        create_tasks.assert_called_once_with(
            account_ids=[7, 8, 9],
            provider_id="lumen_flow",
            mode="extract_only",
            type="trial",
            options={"region": "us"},
        )

    def test_detail_returns_safe_events_and_action_whitelist(self):
        detail = {
            "item": {
                "task_id": 11,
                "run_id": 22,
                "email": "person@example.test",
                "access_token": "must-not-project",
            },
            "history": [{"stage": "extraction", "status": "running", "job_secret": "must-not-project"}],
            "events": [{
                "message": "已提交",
                "cdk": "must-not-project",
                "at": "must-not-project",
                "nested": {"refresh_token": "must-not-project"},
            }],
            "private_data": {"refresh_token": "must-not-project"},
        }
        with (
            patch.object(
                extract_workbench.extract_link_service,
                "extract_workbench_task_detail",
                return_value=detail,
                create=True,
            ),
            patch.object(
                extract_workbench.extract_link_service,
                "perform_extract_workbench_action",
                return_value={"accepted": True, "task_id": 11, "run_id": 23},
                create=True,
            ) as perform_action,
        ):
            detail_response = self.client.get("/api/extract-workbench/tasks/11")
            bad_action = self.client.post("/api/extract-workbench/tasks/11/actions", json={"action": "pay_now"})
            action_response = self.client.post(
                "/api/extract-workbench/tasks/11/actions",
                json={"action": "sync_status"},
            )

        self.assertEqual(200, detail_response.status_code)
        detail_payload = detail_response.get_json()
        self.assertEqual("已提交", detail_payload["events"][0]["message"])
        for secret in ("must-not-project",):
            self.assertNotIn(secret, detail_response.get_data(as_text=True))
        self.assertEqual(400, bad_action.status_code)
        self.assertEqual(202, action_response.status_code)
        self.assertTrue(action_response.get_json()["accepted"])
        perform_action.assert_called_once_with(11, "sync_status")

    def test_link_is_retrieved_only_on_request_and_response_contains_url_only(self):
        with patch.object(
            extract_workbench.extract_link_service,
            "extract_workbench_task_link",
            return_value={"url": "https://checkout.example/pay", "job_secret": "must-not-project"},
            create=True,
        ) as get_link:
            response = self.client.post(
                "/api/extract-workbench/tasks/11/links",
                json={"kind": "payment"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "url": "https://checkout.example/pay"}, response.get_json())
        self.assertNotIn("must-not-project", response.get_data(as_text=True))
        get_link.assert_called_once_with(11, "payment")

    def test_service_exception_does_not_return_exception_text(self):
        with patch.object(
            extract_workbench.extract_link_service,
            "workbench_config",
            side_effect=RuntimeError("credential-value must-not-return"),
            create=True,
        ):
            response = self.client.get("/api/extract-workbench/config")

        self.assertEqual(503, response.status_code)
        self.assertNotIn("credential-value", response.get_data(as_text=True))

    def test_application_factory_registers_workbench_api_behind_auth(self):
        app = create_app(auth_code="workbench-route-auth")
        client = app.test_client()
        unauthorized = client.get("/api/extract-workbench/config")
        self.assertEqual(401, unauthorized.status_code)

        client.environ_base["HTTP_X_AUTH_CODE"] = "workbench-route-auth"
        with patch.object(
            extract_workbench.extract_link_service,
            "workbench_config",
            return_value={"default_provider": "legacy", "default_mode": "extract_only", "providers": []},
            create=True,
        ):
            authorized = client.get("/api/extract-workbench/config")
        self.assertEqual(200, authorized.status_code)


if __name__ == "__main__":
    unittest.main()
