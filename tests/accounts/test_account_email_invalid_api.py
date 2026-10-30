# -*- coding: utf-8 -*-
"""邮箱失效标记使用独立命令，严格限定输入和公开响应。"""
from unittest import TestCase
from unittest.mock import patch

from webui.app import create_app


class AccountEmailInvalidApiTests(TestCase):
    def setUp(self):
        self.client = create_app(auth_code="email-status-test").test_client()
        self.headers = {"X-Auth-Code": "email-status-test"}
        self.url = "/api/accounts/email-invalid-bulk"
        self.result = {
            "updated_count": 1, "pool_updated_count": 0, "allocation_updated_count": 0,
            "matched_account_count": 1, "matched_pool_count": 0, "matched_allocation_count": 0,
            "account_ids": [7], "skipped": [],
        }

    def test_requires_authentication(self):
        response = self.client.post(self.url, json={"account_ids": [7], "invalid": True})
        self.assertEqual(401, response.status_code)

    def test_rejects_non_boolean_and_ambiguous_or_invalid_targets_before_storage(self):
        payloads = [
            [], {}, {"account_ids": [7]},
            *({"account_ids": [7], "invalid": value} for value in (1, 0, "false", None)),
            {"account_ids": [], "invalid": True},
            {"account_ids": [True], "invalid": True},
            {"account_ids": [0], "invalid": True},
            {"account_ids": [7.5], "invalid": True},
            {"account_ids": [2**63], "invalid": True},
            {"account_ids": list(range(1, 502)), "invalid": True},
            {"account_ids": [7], "icloud_account_id": "4", "invalid": True},
            {"ids": [7], "icloud_account_id": "4", "invalid": True},
            {"icloud_account_id": " ", "invalid": True},
            {"icloud_account_id": None, "invalid": True},
            {"account_ids": [], "icloud_account_id": "4", "invalid": True},
            {"account_ids": [7], "ids": [8], "invalid": True},
            {"account_ids": [7], "invalid": True, "reason": True},
            {"account_ids": [7], "invalid": True, "reason": "因" * 301},
            {"account_ids": [7], "invalid": True, "expected_emails": []},
            {"account_ids": [7], "invalid": True, "expected_emails": {"7": True}},
            {"account_ids": [7], "invalid": True, "expected_emails": {"bad": "a@example.test"}},
            {"account_ids": [7], "invalid": True, "expected_emails": {"²": "a@example.test"}},
            {"account_ids": [7], "invalid": True, "expected_emails": {}},
            {"account_ids": [7, 8], "invalid": True, "expected_emails": {"7": "a@example.test"}},
            {"account_ids": [7], "invalid": True, "expected_emails": {"7": "a"}},
            {"icloud_account_id": "4", "invalid": True, "expected_emails": {"7": "a@example.test"}},
        ]
        with patch("webui.routes.accounts.db.set_accounts_email_invalid", create=True) as command:
            for payload in payloads:
                with self.subTest(payload=payload):
                    response = self.client.post(self.url, json=payload, headers=self.headers)
                    self.assertEqual(400, response.status_code)
            command.assert_not_called()

    def test_explicit_ids_forward_email_snapshot_and_use_fixed_manual_source(self):
        payload = {
            "ids": [7, 7], "invalid": True, "reason": " 邮箱已失效 ",
            "expected_emails": {"7": "old@example.test"}, "source": "untrusted",
        }
        with patch("webui.routes.accounts.db.set_accounts_email_invalid", return_value={
            **self.result, "email": "private@example.test", "access_token": "private",
        }, create=True) as command:
            response = self.client.post(self.url, json=payload, headers=self.headers)
        self.assertEqual(200, response.status_code)
        command.assert_called_once_with(
            account_ids=[7], invalid=True, reason="邮箱已失效",
            expected_emails={7: "old@example.test"}, icloud_account_id=None, source="manual",
        )
        result = response.get_json()
        self.assertTrue(result["ok"])
        self.assertEqual(1, result["updated_count"])
        self.assertNotIn("email", result)
        self.assertNotIn("access_token", result)

    def test_group_has_no_500_account_limit_and_clearing_does_not_claim_mailbox_recovery(self):
        with patch("webui.routes.accounts.db.set_accounts_email_invalid", return_value={
            **self.result, "matched_account_count": 700,
        }, create=True) as command:
            response = self.client.post(self.url, json={
                "icloud_account_id": "4", "invalid": False,
            }, headers=self.headers)
        self.assertEqual(200, response.status_code)
        command.assert_called_once_with(
            account_ids=None, invalid=False, reason="", expected_emails=None,
            icloud_account_id="4", source="manual_icloud_account_group",
        )
        self.assertEqual(700, response.get_json()["matched_account_count"])
        self.assertIn("清除", response.get_json()["message"])
        self.assertNotIn("邮箱已恢复", response.get_json()["message"])

    def test_storage_validation_error_is_a_client_error(self):
        with patch("webui.routes.accounts.db.set_accounts_email_invalid", side_effect=ValueError("目标不存在"), create=True):
            response = self.client.post(self.url, json={"account_ids": [7], "invalid": True}, headers=self.headers)
        self.assertEqual(400, response.status_code)
        self.assertFalse(response.get_json()["ok"])
