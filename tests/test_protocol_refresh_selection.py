# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import account as account_config
from core.live_check_service import _resolve_refresh_driver
from core.twofa_flow import plan_twofa_context


class ProtocolRefreshSelectionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
