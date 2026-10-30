# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import account as account_config
from config import openai_protocol
from core.accounts.liveness.service import _resolve_refresh_driver
from core.auth.twofa import plan_twofa_context


class ProtocolRefreshSelectionTests(unittest.TestCase):
    def test_invalid_email_freezes_password_capable_driver_even_with_v1_default(self):
        from core.accounts.liveness import service as service

        account = {"id": 7, "email": "fixture@example.test", "access_token": "fixture-at", "email_invalid": True}
        with (
            patch.object(openai_protocol, "OPENAI_PROTOCOL_VERSION", "v1"),
            patch.object(service.db, "get_account", return_value=account),
            patch.object(service.db, "account_is_deactivated", return_value=False),
            patch.object(service.db, "claim_account_live_check", return_value=True),
            patch.object(service, "_append_log"),
            patch.object(service.account_task_store, "submit_durable_operation", return_value={
                "accepted": True, "task_id": 101, "run_id": 1001, "status": "queued",
            }) as submit,
        ):
            result = service.enqueue_account_live_check(
                account_id=7, email=account["email"], trigger="token_refresh_manual", force_refresh=True,
            )

        self.assertTrue(result["accepted"])
        self.assertEqual("protocol_v2", result["token_refresh_driver"])
        self.assertEqual("v2", submit.call_args.kwargs["data"]["refresh_driver"])

    def test_twofa_protocol_reauth_is_context_source_not_refresh_driver(self):
        plan = plan_twofa_context(
            "auto",
            has_access_token=False,
            browser_session_required=False,
        )

        self.assertEqual("protocol", plan.executor)
        self.assertEqual("protocol_reauth", plan.auth_source)
        self.assertEqual("legacy", _resolve_refresh_driver("protocol"))

    def test_explicit_refresh_driver_contract_stays_independent(self):
        self.assertEqual("legacy", _resolve_refresh_driver("protocol_current"))
        with patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", False):
            self.assertEqual("legacy", _resolve_refresh_driver("protocol_v2"))
        with patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", True):
            self.assertEqual("protocol_v2", _resolve_refresh_driver("protocol_v2"))

    def test_shared_protocol_version_v2_selects_v2_for_refresh_at(self):
        with patch.object(openai_protocol, "OPENAI_PROTOCOL_VERSION", "v2", create=True), patch.object(
            account_config, "ACCOUNT_TOKEN_REFRESH_DRIVER", "legacy"
        ), patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", True):
            self.assertEqual("protocol_v2", _resolve_refresh_driver())

    def test_shared_protocol_version_v2_does_not_depend_on_legacy_kill_switch(self):
        with patch.object(openai_protocol, "OPENAI_PROTOCOL_VERSION", "v2", create=True), patch.object(
            account_config, "ACCOUNT_TOKEN_REFRESH_DRIVER", "legacy"
        ), patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", False):
            self.assertEqual("protocol_v2", _resolve_refresh_driver())

    def test_shared_protocol_version_v1_selects_legacy_for_refresh_at(self):
        with patch.object(openai_protocol, "OPENAI_PROTOCOL_VERSION", "v1", create=True), patch.object(
            account_config, "ACCOUNT_TOKEN_REFRESH_DRIVER", "protocol_v2"
        ), patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", True):
            self.assertEqual("legacy", _resolve_refresh_driver())


if __name__ == "__main__":
    unittest.main()
