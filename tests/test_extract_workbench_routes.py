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

    def test_cancel_batch_returns_only_result_counts(self):
        with patch.object(extract_workbench.extract_link_service, "cancel_workbench_batch", create=True,
            return_value={"batch_id": 7, "cancelled": 803, "skipped": 2, "failed": 1, "private_data": "private"}) as cancel:
            response = self.client.post("/api/extract-workbench/batches/7/cancel", json={})
        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "batch_id": 7, "cancelled": 803, "skipped": 2, "failed": 1}, response.get_json())
        cancel.assert_called_once_with(7)

    def test_cancel_batch_rejects_invalid_or_extra_fields(self):
        with patch.object(extract_workbench.extract_link_service, "cancel_workbench_batch", create=True) as cancel:
            for path, body in (("/api/extract-workbench/batches/0/cancel", {}),
                ("/api/extract-workbench/batches/7/cancel", {"all": True})):
                with self.subTest(path=path, body=body):
                    self.assertEqual(400, self.client.post(path, json=body).status_code)
            self.assertEqual(400, self.client.post("/api/extract-workbench/batches/7/cancel", json=[]).status_code)
        cancel.assert_not_called()

    def test_cancel_batch_missing_returns_not_found(self):
        with patch.object(extract_workbench.extract_link_service, "cancel_workbench_batch", create=True, return_value=None):
            self.assertEqual(404, self.client.post("/api/extract-workbench/batches/7/cancel", json={}).status_code)

    def test_cancel_batch_errors_do_not_expose_internal_details(self):
        with patch.object(extract_workbench.extract_link_service, "cancel_workbench_batch", create=True,
            side_effect=RuntimeError("private-secret")):
            response = self.client.post("/api/extract-workbench/batches/7/cancel", json={})
        self.assertEqual(503, response.status_code)
        self.assertNotIn("private-secret", response.get_data(as_text=True))

    def test_cancel_batch_still_submitting_returns_conflict(self):
        with patch.object(extract_workbench.extract_link_service, "cancel_workbench_batch",
            side_effect=ValueError("private-detail")):
            response = self.client.post("/api/extract-workbench/batches/7/cancel", json={})
        self.assertEqual(409, response.status_code)
        self.assertIn("正在入队", response.get_json()["error"])
        self.assertNotIn("private-detail", response.get_data(as_text=True))

    def test_config_returns_only_public_provider_fields(self):
        config = {
            "default_provider": "lumen_flow",
            "default_mode": "extract_only",
            "batch_workers_default": 4, "batch_workers_max": 16,
            "api_key": "provider-secret",
            "providers": [{
                "id": "lumen_flow",
                "label": "流光",
                "default_type": "trial",
                "link_types": ["momo", "pix", "unsafe type"],
                "modes": ["extract_only"],
                "api_base": "https://private.example/api",
                "cdk": "private-cdk",
            }],
            "unavailable_providers": [{
                "id": "huanguang", "label": "幻光", "unavailable_reason": "缺少API地址和平台授权信息",
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
        self.assertEqual(4, payload["batch_workers_default"])
        self.assertEqual(16, payload["batch_workers_max"])
        self.assertEqual(
            [{"id": "lumen_flow", "label": "流光", "default_type": "trial", "link_types": ["momo", "pix"], "modes": ["extract_only"]}],
            payload["providers"],
        )
        self.assertEqual([{
            "id": "huanguang", "label": "幻光", "unavailable_reason": "缺少API地址和平台授权信息",
        }], payload["unavailable_providers"])
        self.assertNotIn("provider-secret", response.get_data(as_text=True))
        self.assertNotIn("private-cdk", response.get_data(as_text=True))

    def test_task_list_validates_and_projects_supported_filters(self):
        service_result = {
            "items": [{
                "task_id": 11,
                "run_id": 22,
                "account_id": 77,
                "email": "person@example.test",
                "provider_id": "lumen_flow",
                "mode": "extract_only",
                "link_type": "momo",
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
            "counts": {"all": 3, "running": 1},
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
        self.assertEqual({"all": 3, "running": 1}, payload["counts"])
        self.assertEqual(77, payload["items"][0]["account_id"])
        self.assertEqual("momo", payload["items"][0]["link_type"])
        self.assertNotIn("access_token", payload["items"][0])
        self.assertNotIn("extract_link", payload["items"][0])
        self.assertNotIn("internal", payload)

    def test_list_and_detail_preserve_safe_local_payment_confirmation_source(self):
        item = {"task_id": 11, "payment_status": "paid", "plus_status": "confirmed",
                "payment_confirmation_source": "local_plan_check", "access_token": "private-marker"}
        with (
            patch.object(extract_workbench.extract_link_service, "list_workbench_tasks", return_value={"items": [item], "total": 1}),
            patch.object(extract_workbench.extract_link_service, "extract_workbench_task_detail", return_value={"item": item, "events": [], "history": []}),
        ):
            listed = self.client.get("/api/extract-workbench/tasks")
            detail = self.client.get("/api/extract-workbench/tasks/11")
        for response, public in ((listed, listed.get_json()["items"][0]), (detail, detail.get_json()["item"])):
            with self.subTest(path=response.request.path):
                self.assertEqual(200, response.status_code)
                self.assertEqual("local_plan_check", public.get("payment_confirmation_source"))
                self.assertNotIn("private-marker", response.get_data(as_text=True))

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

    def test_task_list_filters_batch_and_keeps_batch_reference(self):
        with patch.object(
            extract_workbench.extract_link_service, "list_workbench_tasks",
            return_value={"items": [{"task_id": 11, "batch_id": 7}], "total": 1},
        ) as list_tasks:
            response = self.client.get("/api/extract-workbench/tasks?batch_id=7")
        self.assertEqual(200, response.status_code)
        self.assertEqual(7, list_tasks.call_args.kwargs["batch_id"])
        self.assertEqual(7, response.get_json()["items"][0]["batch_id"])
        for invalid in ("0", "-1", "", "foo", "1.2"):
            with self.subTest(batch_id=invalid), patch.object(
                extract_workbench.extract_link_service, "list_workbench_tasks",
            ) as invalid_list:
                result = self.client.get(f"/api/extract-workbench/tasks?batch_id={invalid}")
                self.assertEqual(400, result.status_code)
                invalid_list.assert_not_called()

    def test_candidate_preview_validates_filters_and_removes_credentials(self):
        with patch.object(
            extract_workbench.extract_link_service, "preview_workbench_candidates", create=True,
            return_value={"total": 150, "selected_count": 100, "items": [{
                "account_id": 77, "email": "candidate@example.test", "created_at": "2026-10-14",
                "email_source": "icloud_hide", "extract_link_status": "failed", "access_token": "must-not-project",
                "account_promotion_value": "other_discount",
            }]},
        ) as preview:
            response = self.client.get(
                "/api/extract-workbench/candidates?query=example&source=icloud_hide"
                "&date_from=2026-10-14&date_to=2026-10-15&extract_status=failed&promotion=other_discount&limit=100"
            )
        self.assertEqual(200, response.status_code)
        preview.assert_called_once_with(filters={
            "query": "example", "source": "icloud_hide", "date_from": "2026-10-14",
            "date_to": "2026-10-15", "extract_status": "failed", "promotion": "other_discount",
        }, limit=100)
        self.assertEqual(150, response.get_json()["total"])
        self.assertEqual(100, response.get_json()["selected_count"])
        self.assertEqual(5000, response.get_json()["max_batch_size"])
        self.assertEqual("other_discount", response.get_json()["items"][0]["account_promotion_value"])
        self.assertNotIn("must-not-project", response.get_data(as_text=True))

    def test_candidate_preview_rejects_invalid_filters_before_service(self):
        for query in (
            "date_from=2026-02-30", "date_from=20261014", "date_from=2026-10-15&date_to=2026-10-14",
            "extract_status=unknown", "promotion=unknown", "limit=0", "limit=5001", "limit=true", "access_token=must-not-return",
        ):
            with self.subTest(query=query), patch.object(
                extract_workbench.extract_link_service, "preview_workbench_candidates", create=True,
            ) as preview:
                response = self.client.get("/api/extract-workbench/candidates?" + query)
                self.assertEqual(400, response.status_code)
                self.assertNotIn("must-not-return", response.get_data(as_text=True))
                preview.assert_not_called()

    def test_create_batch_submits_filters_and_returns_batch_counts(self):
        with patch.object(
            extract_workbench.extract_link_service, "create_workbench_batch", create=True,
            return_value={"batch_id": 7, "requested": 100, "started": 98, "skipped": 1, "failed": 1, "cdk": "must-not-project"},
        ) as create_batch:
            response = self.client.post("/api/extract-workbench/batches", json={
                "title": "  14号账号提链  ", "provider_id": "lumen_flow", "mode": "extract_only",
                "filters": {"date_from": "2026-10-14", "date_to": "2026-10-14"}, "limit": 100,
                "submission_id": "44DAAB12-8F2E-49A9-AF4E-D9347A8EF770",
            })
        self.assertEqual(202, response.status_code)
        self.assertEqual({"ok": True, "batch_id": 7, "requested": 100, "started": 98, "skipped": 1, "failed": 1}, response.get_json())
        create_batch.assert_called_once_with(
            title="14号账号提链", provider_id="lumen_flow", mode="extract_only", limit=100, options={},
            filters={"query": "", "source": "", "date_from": "2026-10-14", "date_to": "2026-10-14", "extract_status": "not_succeeded", "promotion": "eligible"},
            submission_id="44daab12-8f2e-49a9-af4e-d9347a8ef770",
        )

    def test_batch_workers_requires_integer_in_range_and_passes_to_service(self):
        valid = {"provider_id": "lumen_flow", "mode": "extract_only",
                 "submission_id": "44daab12-8f2e-49a9-af4e-d9347a8ef770"}
        for workers in (1, 4, 16):
            with self.subTest(workers=workers), patch.object(
                extract_workbench.extract_link_service, "create_workbench_batch", create=True,
                return_value={"batch_id": 7, "requested": 1, "started": 1},
            ) as create_batch:
                response = self.client.post("/api/extract-workbench/batches", json={**valid, "workers": workers})
                self.assertEqual(202, response.status_code)
                self.assertEqual(workers, create_batch.call_args.kwargs["workers"])
        for workers in (None, True, False, 0, 17, 1.5, "4", [], {}):
            with self.subTest(workers=workers), patch.object(
                extract_workbench.extract_link_service, "create_workbench_batch", create=True,
            ) as create_batch:
                response = self.client.post("/api/extract-workbench/batches", json={**valid, "workers": workers})
                self.assertEqual(400, response.status_code)
                self.assertIn("并发", response.get_json()["error"])
                create_batch.assert_not_called()

    def test_old_batch_summary_keeps_unspecified_workers_null(self):
        with patch.object(extract_workbench.extract_link_service, "workbench_batch_detail", create=True,
                          return_value={"batch_id": 7, "title": "历史批次"}):
            response = self.client.get("/api/extract-workbench/batches/7")
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.get_json()["item"]["workers"])

    def test_batch_create_requires_valid_submission_uuid_before_service(self):
        valid = {"provider_id": "lumen_flow", "mode": "extract_only", "limit": 100}
        invalid_ids = (None, "", True, 7, "not-a-uuid", "44daab128f2e49a9af4ed9347a8ef770", " 44daab12-8f2e-49a9-af4e-d9347a8ef770", [])
        for submission_id in invalid_ids:
            with self.subTest(submission_id=submission_id), patch.object(
                extract_workbench.extract_link_service, "create_workbench_batch", create=True,
            ) as create_batch:
                payload = dict(valid)
                if submission_id is not None:
                    payload["submission_id"] = submission_id
                response = self.client.post("/api/extract-workbench/batches", json=payload)
                self.assertEqual(400, response.status_code)
                self.assertIn("submission_id", response.get_json()["error"])
                create_batch.assert_not_called()

    def test_batch_create_rejects_unsupported_and_private_options(self):
        valid = {"provider_id": "lumen_flow", "mode": "extract_only", "limit": 100,
                 "submission_id": "44daab12-8f2e-49a9-af4e-d9347a8ef770"}
        for changed in (
            {"limit": True}, {"limit": "100"}, {"limit": 5001}, {"title": "x" * 121},
            {"filters": {"date_from": "2026-02-30"}}, {"filters": {"archived": "1"}},
            {"options": {"job_secret": "must-not-return"}}, {"account_ids": [77]},
        ):
            with self.subTest(changed=changed), patch.object(
                extract_workbench.extract_link_service, "create_workbench_batch", create=True,
            ) as create_batch:
                response = self.client.post("/api/extract-workbench/batches", json={**valid, **changed})
                self.assertEqual(400, response.status_code)
                self.assertNotIn("must-not-return", response.get_data(as_text=True))
                create_batch.assert_not_called()

    def test_batch_service_value_error_is_safe_validation_failure(self):
        with patch.object(
            extract_workbench.extract_link_service, "create_workbench_batch", create=True,
            side_effect=ValueError("credential-value must-not-return"),
        ) as create_batch:
            response = self.client.post("/api/extract-workbench/batches", json={
                "provider_id": "lumen_flow", "mode": "extract_only",
                "submission_id": "44daab12-8f2e-49a9-af4e-d9347a8ef770",
            })
        self.assertEqual(400, response.status_code)
        self.assertNotIn("credential-value", response.get_data(as_text=True))
        create_batch.assert_called_once()

    def test_batches_list_and_detail_return_only_safe_summary(self):
        summary = {"batch_id": 7, "title": "提链批次", "provider_id": "lumen_flow", "mode": "extract_only",
                   "requested_count": 100, "started_count": 98, "skipped_count": 2, "submission_failed_count": 0, "workers": 4,
                   "status": "running", "counts": {"all": 98, "running": 3, "cdk": "must-not-project", "paid": True},
                   "private_data": {"cdk": "must-not-project"}}
        with (
            patch.object(extract_workbench.extract_link_service, "list_workbench_batches", create=True,
                         return_value={"items": [summary], "total": 1}) as list_batches,
            patch.object(extract_workbench.extract_link_service, "workbench_batch_detail", create=True,
                         return_value=summary) as detail,
        ):
            response = self.client.get("/api/extract-workbench/batches?page=2&page_size=10")
            detail_response = self.client.get("/api/extract-workbench/batches/7")
        self.assertEqual(200, response.status_code)
        list_batches.assert_called_once_with(page=2, page_size=10)
        detail.assert_called_once_with(7)
        item = response.get_json()["items"][0]
        self.assertEqual(4, item["workers"])
        self.assertEqual(98, item["counts"]["all"])
        self.assertEqual(3, item["counts"]["running"])
        self.assertNotIn("cdk", item["counts"])
        self.assertNotIn("paid", item["counts"])
        self.assertEqual(item, detail_response.get_json()["item"])
        self.assertNotIn("must-not-project", response.get_data(as_text=True))
        self.assertNotIn("must-not-project", detail_response.get_data(as_text=True))

    def test_batch_detail_not_found_and_invalid_pagination(self):
        with patch.object(
            extract_workbench.extract_link_service, "workbench_batch_detail", create=True, return_value=None,
        ):
            self.assertEqual(404, self.client.get("/api/extract-workbench/batches/7").status_code)
        with patch.object(
            extract_workbench.extract_link_service, "list_workbench_batches", create=True,
        ) as list_batches:
            self.assertEqual(400, self.client.get("/api/extract-workbench/batches?page=0").status_code)
            list_batches.assert_not_called()

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

    def test_payment_entry_is_explicitly_requested_and_returns_only_validated_fields(self):
        entry = {
            "payment_page_url": "https://checkout.example.test/page", "payment_url": "https://payments.example.test/entry",
            "qr_data": "upi://pay?pa=synthetic@example.test&tn=Token%2BExact", "amount": 0,
            "qr_image_url_png": "javascript:alert(1)", "job_secret": "must-not-project", "raw": "must-not-project",
        }
        with patch.object(extract_workbench.extract_link_service, "extract_workbench_task_payment_entry", return_value=entry) as get_entry:
            response = self.client.post("/api/extract-workbench/tasks/11/payment-entry", json={})
        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "entry": {key: entry[key] for key in ("payment_page_url", "payment_url", "qr_data", "amount")}}, response.get_json())
        get_entry.assert_called_once_with(11)
        self.assertNotIn("must-not-project", response.get_data(as_text=True))

    def test_payment_entry_rejects_unknown_body_and_missing_artifact(self):
        with patch.object(extract_workbench.extract_link_service, "extract_workbench_task_payment_entry", return_value=None) as get_entry:
            bad = self.client.post("/api/extract-workbench/tasks/11/payment-entry", json={"sync": True})
            missing = self.client.post("/api/extract-workbench/tasks/11/payment-entry", json={})
        self.assertEqual(400, bad.status_code)
        self.assertEqual(404, missing.status_code)
        get_entry.assert_called_once_with(11)

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
