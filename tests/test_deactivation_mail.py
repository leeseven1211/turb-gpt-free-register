# -*- coding: utf-8 -*-
import tempfile
import unittest
from unittest.mock import patch

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

    def test_bulk_enqueue_uses_dedicated_icloud_coordinator(self):
        accounts = {
            1: {"id": 1, "email": "first@icloud.com", "email_source": "icloud_hide"},
            2: {"id": 2, "email": "second@icloud.com", "email_source": "icloud_hide"},
        }
        queued = []
        task_ids = iter([101, 102])
        with (
            patch.object(deactivation_mail_service.db, "get_account", side_effect=accounts.get),
            patch.object(
                deactivation_mail_service.account_task_store,
                "create_task",
                side_effect=lambda **_kwargs: next(task_ids),
            ),
            patch.object(deactivation_mail_service.db, "update_account_deactivation_mail"),
            patch.object(deactivation_mail_service.account_task_store, "finish_task"),
            patch.object(
                deactivation_mail_service._HME_QUEUE,
                "put",
                side_effect=lambda item: queued.append(item),
            ),
            patch.object(deactivation_mail_service, "_ensure_hme_coordinator") as ensure,
            patch.object(deactivation_mail_service._EXECUTOR, "submit") as submit,
        ):
            deactivation_mail_service._IN_FLIGHT.clear()
            result = deactivation_mail_service.enqueue_bulk([1, 2], trigger="manual_bulk")
            deactivation_mail_service._IN_FLIGHT.clear()

        self.assertEqual(len(result["started"]), 2)
        self.assertEqual(len(queued), 1)
        self.assertEqual(len(queued[0][0]), 2)
        self.assertEqual(queued[0][1], "manual_bulk")
        ensure.assert_called_once_with()
        submit.assert_not_called()

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
            patch.object(deactivation_mail_service.account_task_store, "start_task"),
            patch.object(deactivation_mail_service.account_task_store, "append_event"),
            patch.object(deactivation_mail_service.account_task_store, "finish_task") as finish,
            patch.object(
                deactivation_mail_service,
                "scan_hme_deactivation_bulk",
                return_value={"first@icloud.com": result, "second@icloud.com": result},
            ) as scan,
        ):
            deactivation_mail_service._IN_FLIGHT.update({1, 2})
            deactivation_mail_service._scan_group(entries, "manual_bulk")

        scan.assert_called_once_with(
            ["first@icloud.com", "second@icloud.com"],
            lookback_days=deactivation_mail_service._LOOKBACK_DAYS,
        )
        success_updates = [
            call for call in update.call_args_list if call.args[1].get("status") == "success"
        ]
        self.assertEqual({call.args[0] for call in success_updates}, {1, 2})
        self.assertEqual(2, finish.call_count)
        self.assertTrue(all(call.kwargs["status"] == "success" for call in finish.call_args_list))
        self.assertFalse(deactivation_mail_service._IN_FLIGHT.intersection({1, 2}))


if __name__ == "__main__":
    unittest.main()
