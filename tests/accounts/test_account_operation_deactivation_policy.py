# -*- coding: utf-8 -*-
"""账户操作对已确认废号的统一阻断回归。"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core.extract_link import service as extract_link_service
from core.accounts.plans import service as plan_check_service
from core.storage import db_legacy
from webui.app import create_app


_DEACTIVATED_ACCOUNT = {
    "id": 7,
    "email": "deactivated@example.test",
    "access_token": "synthetic-token",
    "current_plan_type": "free",
    "plus_trial_eligible": True,
    "codex_credential_state": "deactivated",
}


class AccountOperationDeactivationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def test_all_durable_deactivation_projections_are_confirmed(self):
        for key in ("account_status", "codex_status", "codex_credential_state"):
            with self.subTest(key=key):
                self.assertTrue(db_legacy.account_is_deactivated({key: "deactivated"}))
        self.assertFalse(db_legacy.account_is_deactivated({"account_status": "active", "codex_status": "failed"}))

    def test_plan_service_rejects_deactivated_account_before_claim_or_submit(self):
        with (
            patch.object(plan_check_service.db, "get_account", return_value=_DEACTIVATED_ACCOUNT),
            patch.object(plan_check_service.db, "claim_account_plan_check") as claim,
            patch.object(plan_check_service, "_submit_native_plan") as submit,
        ):
            result = plan_check_service.enqueue_account_plan_check(
                account_id=7,
                email="deactivated@example.test",
                access_token="synthetic-token",
                trigger="manual",
            )

        self.assertFalse(result["accepted"])
        self.assertTrue(result["deactivated"])
        claim.assert_not_called()
        submit.assert_not_called()

    def test_extract_service_rejects_deactivated_account_before_claim_or_submit(self):
        with (
            patch.object(extract_link_service.db, "get_account", return_value=_DEACTIVATED_ACCOUNT),
            patch.object(extract_link_service.db, "claim_account_extract") as claim,
            patch.object(extract_link_service, "_submit_native_extract") as submit,
        ):
            result = extract_link_service.enqueue_account_extract(
                account_id=7,
                email="deactivated@example.test",
                access_token="synthetic-token",
            )

        self.assertFalse(result["accepted"])
        self.assertTrue(result["deactivated"])
        claim.assert_not_called()
        submit.assert_not_called()

    def test_single_plan_and_extract_routes_reject_deactivated_account(self):
        with (
            patch("webui.routes.accounts._feature_unavailable", return_value=None),
            patch("webui.routes.accounts.db.get_account", return_value=_DEACTIVATED_ACCOUNT),
            patch("webui.routes.accounts.plan_check_service.enqueue_account_plan_check") as enqueue_plan,
            patch("webui.routes.accounts.extract_link_service.enqueue_account_extract") as enqueue_extract,
        ):
            plan_response = self.client.post(
                "/api/accounts/check-plan",
                json={"account_id": 7},
                headers=self.headers,
            )
            extract_response = self.client.post(
                "/api/accounts/extract-link",
                json={"account_id": 7},
                headers=self.headers,
            )

        self.assertEqual(409, plan_response.status_code)
        self.assertTrue(plan_response.get_json()["deactivated"])
        self.assertEqual(409, extract_response.status_code)
        self.assertTrue(extract_response.get_json()["deactivated"])
        enqueue_plan.assert_not_called()
        enqueue_extract.assert_not_called()

    def test_bulk_plan_and_extract_routes_skip_deactivated_account(self):
        with (
            patch("webui.routes.accounts._feature_unavailable", return_value=None),
            patch("webui.routes.accounts.db.get_account", return_value=_DEACTIVATED_ACCOUNT),
            patch("webui.routes.accounts.account_task_store.create_batch") as create_batch,
            patch("webui.routes.accounts.plan_check_service.enqueue_account_plan_check") as enqueue_plan,
            patch("webui.routes.accounts.extract_link_service.enqueue_account_extract") as enqueue_extract,
        ):
            plan_response = self.client.post(
                "/api/accounts/check-plan-bulk",
                json={"account_ids": [7]},
                headers=self.headers,
            )
            extract_response = self.client.post(
                "/api/accounts/extract-link-bulk",
                json={"account_ids": [7]},
                headers=self.headers,
            )

        self.assertEqual(202, plan_response.status_code)
        self.assertEqual(1, plan_response.get_json()["skipped_count"])
        self.assertEqual(202, extract_response.status_code)
        self.assertEqual(1, extract_response.get_json()["skipped_count"])
        create_batch.assert_not_called()
        enqueue_plan.assert_not_called()
        enqueue_extract.assert_not_called()
