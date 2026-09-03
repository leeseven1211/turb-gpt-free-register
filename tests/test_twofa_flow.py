# -*- coding: utf-8 -*-
import unittest

from config import twofa as twofa_config
from core.twofa_flow import (
    canonical_twofa_executor,
    normalize_twofa_mode,
    plan_twofa_context,
)


class TwofaFlowTests(unittest.TestCase):
    def test_protocol_direct_is_auto_protocol_fast_path(self):
        mode = normalize_twofa_mode("protocol_direct")
        plan = plan_twofa_context(mode, has_access_token=True, browser_session_required=False)

        self.assertEqual("auto", mode)
        self.assertEqual("protocol", plan.executor)
        self.assertEqual("existing_at", plan.auth_source)
        self.assertTrue(plan.direct_preferred)

    def test_protocol_without_at_prefers_protocol_reauthentication(self):
        plan = plan_twofa_context("protocol", has_access_token=False, browser_session_required=False)

        self.assertEqual("protocol", plan.executor)
        self.assertEqual("protocol_reauth", plan.auth_source)

    def test_protocol_with_password_setup_uses_browser_session_for_context(self):
        plan = plan_twofa_context("auto", has_access_token=True, browser_session_required=True)

        self.assertEqual("protocol", plan.executor)
        self.assertEqual("browser_session", plan.auth_source)
        self.assertFalse(plan.direct_preferred)

    def test_browser_mode_never_selects_protocol_executor(self):
        plan = plan_twofa_context("browser", has_access_token=True, browser_session_required=False)

        self.assertEqual("browser", plan.executor)
        self.assertEqual("browser_session", plan.auth_source)
        self.assertEqual("browser", canonical_twofa_executor("browser"))

    def test_legacy_direct_config_is_accepted_by_twofa_driver(self):
        self.assertEqual("protocol", twofa_config.get_twofa_driver("protocol_direct"))
        self.assertEqual("auto", twofa_config.get_twofa_mode("protocol_direct"))


if __name__ == "__main__":
    unittest.main()
