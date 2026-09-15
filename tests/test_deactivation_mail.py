# -*- coding: utf-8 -*-
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import account_task_store as legacy_account_task_store
from core import db, deactivation_mail_service
from core.operations import task_gateway as account_task_store
from core.record_store import ACCOUNTS
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class DeactivationMailTests(PostgresTestCase):
    def test_detected_mail_is_durable_and_empty_rescan_does_not_clear_it(self):
        self.seed(ACCOUNTS, [
            {"id": 1, "email": "a@test.com", "email_source": "email_butler"},
        ])
        db.update_account_deactivation_mail(1, {
            "status": "success",
            "detected": True,
            "subject": "Deactivated",
            "sender": "noreply@openai.com",
            "received_at": "2026-08-06T09:00:00Z",
        })
        db.update_account_deactivation_mail(1, {"status": "success", "detected": False})
        row = db.get_account(1)
        self.assertTrue(row["deactivation_mail_detected"])
        self.assertEqual(row["deactivation_mail_subject"], "Deactivated")

    def test_manual_endpoint_queues_without_access_token(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        # 显式声明特性可用：否则这个用例只在"开发机 .env 恰好配了 Email Butler"
        # 时才通过，换台机器或 CI 上会因 503 失败。
        with patch("core.feature_availability.require_feature", return_value=(True, "")), \
             patch.object(
            deactivation_mail_service,
            "enqueue",
            return_value={"accepted": True, "account_id": 7},
        ), patch.object(
            deactivation_mail_service,
            "queue_settings",
            return_value={"enabled": True},
        ):
            response = client.post("/api/accounts/7/check-deactivation-mail")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.get_json()["ok"])

    def test_bulk_endpoint_uses_one_grouped_enqueue_call(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with (
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch.object(
                legacy_account_task_store,
                "create_batch",
                return_value="batch-1",
            ),
            patch.object(
                deactivation_mail_service,
                "enqueue_bulk",
                return_value={
                    "started": [{"id": 1, "task_id": 11}],
                    "busy": [],
                    "skipped": [],
                },
            ) as enqueue_bulk,
            patch.object(
                deactivation_mail_service,
                "queue_settings",
                return_value={"enabled": True},
            ),
        ):
            response = client.post(
                "/api/accounts/check-deactivation-mail-bulk",
                json={"account_ids": [1, 2]},
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["started_count"], 1)
        enqueue_bulk.assert_called_once_with(
            [1, 2],
            trigger="manual_bulk",
            batch_id="batch-1",
        )

    def test_account_management_ui_has_mail_scan_controls(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        html = client.get("/", headers={"X-Auth-Code": "test-auth"}).get_data(as_text=True)
        response = client.get("/static/js/modern/accounts.js")
        try:
            self.assertEqual(response.status_code, 200)
            html += "\n" + response.get_data(as_text=True)
        finally:
            response.close()
        self.assertIn('class="col-risk-mail column-filter-header"', html)
        self.assertIn('data-column-filter="accountRiskFilterV2"', html)
        self.assertIn("data-deactivation-mail-check", html)
        self.assertIn("btnCheckSelectedDeactivationMailV2", html)
        self.assertIn("'icloud_hide'", html)

    def test_icloud_hide_is_supported_by_mail_scanner(self):
        self.assertIn("icloud_hide", deactivation_mail_service._SUPPORTED_SOURCES)

    def test_email_butler_missing_account_is_marked_unsupported(self):
        self.seed(ACCOUNTS, [
            {"id": 3, "email": "missing@test.com", "email_source": "email_butler"},
        ])
        with (
            patch.object(
                deactivation_mail_service,
                "scan_openai_deactivation",
                side_effect=deactivation_mail_service.EmailButlerClientError(
                    "Email Butler 请求失败 (/signals/scan): HTTP 404; email account not found"
                ),
            ),
            patch.object(deactivation_mail_service.account_task_store, "start_task"),
            patch.object(deactivation_mail_service.account_task_store, "append_event"),
            patch.object(deactivation_mail_service.account_task_store, "finish_task") as finish,
        ):
            deactivation_mail_service._scan(3, "manual", task_id=999991)

        self.assertEqual("unsupported", db.get_account(3)["deactivation_mail_scan_status"])
        finish.assert_called_once()
        self.assertEqual("unsupported", finish.call_args.kwargs["status"])

    def test_email_butler_non_permanent_error_remains_failed(self):
        self.seed(ACCOUNTS, [
            {"id": 4, "email": "timeout@test.com", "email_source": "email_butler"},
        ])
        with (
            patch.object(
                deactivation_mail_service,
                "scan_openai_deactivation",
                side_effect=deactivation_mail_service.EmailButlerClientError(
                    "Email Butler 请求失败 (/signals/scan): HTTP 503; service unavailable"
                ),
            ),
            patch.object(deactivation_mail_service.account_task_store, "start_task"),
            patch.object(deactivation_mail_service.account_task_store, "append_event"),
            patch.object(deactivation_mail_service.account_task_store, "finish_task") as finish,
        ):
            deactivation_mail_service._scan(4, "manual", task_id=999992)

        self.assertEqual("failed", db.get_account(4)["deactivation_mail_scan_status"])
        finish.assert_called_once()
        self.assertEqual("failed", finish.call_args.kwargs["status"])

    def test_bulk_enqueue_uses_dedicated_icloud_coordinator(self):
        accounts = {
            1: {"id": 1, "email": "first@icloud.com", "email_source": "icloud_hide"},
            2: {"id": 2, "email": "second@icloud.com", "email_source": "icloud_hide"},
        }
        with (
            patch.object(deactivation_mail_service.db, "get_account", side_effect=accounts.get),
            patch.object(deactivation_mail_service.db, "update_account_deactivation_mail"),
            patch.object(
                deactivation_mail_service.db,
                "list_accounts",
                return_value=[],
            ),
            patch.object(
                deactivation_mail_service,
                "_submit_native_hme_group",
                return_value={
                    "accepted": True,
                    "busy": False,
                    "reused": False,
                    "task_id": 101,
                    "run_id": 201,
                    "status": "queued",
                },
            ) as submit_group,
        ):
            result = deactivation_mail_service.enqueue_bulk([1, 2], trigger="manual_bulk")

        self.assertEqual(len(result["started"]), 2)
        self.assertEqual({item["task_id"] for item in result["started"]}, {101})
        self.assertEqual({item["run_id"] for item in result["started"]}, {201})
        self.assertTrue(all(item["shared_scan"] for item in result["started"]))
        submit_group.assert_called_once()
        self.assertEqual(
            submit_group.call_args.kwargs["entries"],
            [
                {"account_id": 1, "email": "first@icloud.com"},
                {"account_id": 2, "email": "second@icloud.com"},
            ],
        )

    def test_grouped_scan_fans_out_terminal_results_to_each_account(self):
        entries = [
            {"account_id": 1, "task_id": 101, "email": "first@icloud.com"},
            {"account_id": 2, "task_id": 102, "email": "second@icloud.com"},
        ]
        result = {
            "ok": True,
            "detected": False,
            "checked_at": "2026-08-10T00:00:00Z",
            "confidence": "none",
        }
        with (
            patch.object(deactivation_mail_service.db, "update_account_deactivation_mail") as update,
            patch.object(
                deactivation_mail_service,
                "scan_hme_deactivation_bulk",
                return_value={"first@icloud.com": result, "second@icloud.com": result},
            ) as scan,
        ):
            context = Mock()
            context.is_cancel_requested.return_value = False
            deactivation_mail_service._scan_hme_group(context, entries, "manual_bulk")

        scan.assert_called_once_with(
            ["first@icloud.com", "second@icloud.com"],
            lookback_days=deactivation_mail_service._LOOKBACK_DAYS,
        )
        success_updates = [
            call for call in update.call_args_list if call.args[1].get("status") == "success"
        ]
        self.assertEqual({call.args[0] for call in success_updates}, {1, 2})
        context.finish.assert_called_once()
        self.assertEqual("success", context.finish.call_args.kwargs["status"])


if __name__ == "__main__":
    unittest.main()
