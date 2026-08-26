# -*- coding: utf-8 -*-
import logging
import unittest
from unittest.mock import patch

from webui import runtime


class WebUIRuntimeTests(unittest.TestCase):
    def setUp(self):
        runtime._runtime_started = False

    def tearDown(self):
        runtime._runtime_started = False

    def test_start_runtime_recovers_and_starts_periodic_workers_once(self):
        with (
            patch.object(runtime.db, "recover_interrupted_registration_jobs", return_value=2) as recover_jobs,
            patch.object(runtime.account_task_store, "recover_interrupted", return_value=1) as recover_accounts,
            patch.object(runtime.operation_task_store, "init") as init_operations,
            patch.object(runtime.operation_task_store, "recover_interrupted_runtime_runs", return_value=3) as recover_operations,
            patch("core.roxybrowser_client.cleanup_orphaned_profiles", return_value={"found": 0}) as cleanup_roxy,
            patch.object(runtime.sms_provider, "start_cancel_worker") as start_sms,
            patch.object(runtime.db, "recover_interrupted_plan_checks", return_value=4) as recover_plans,
            patch.object(runtime.db, "recover_interrupted_extract_links", return_value=5) as recover_links,
            patch.object(runtime.db, "recover_interrupted_live_checks", return_value=6) as recover_live,
            patch.object(runtime.db, "backfill_account_registration_proxy_context", return_value=7) as backfill_proxy,
            patch.object(runtime.codex_operation_service, "resume_queued", return_value=8) as resume_codex,
            patch("core.deactivation_mail_service.start_periodic_scanner") as start_risk_scan,
            patch("core.token_refresh_service.start_periodic_refresher") as start_at_refresh,
            patch("core.codex_token_refresh_service.start_periodic_refresher") as start_codex_refresh,
        ):
            self.assertTrue(runtime.start_runtime(logging.getLogger("test-webui-runtime")))
            self.assertFalse(runtime.start_runtime(logging.getLogger("test-webui-runtime")))

        for mock in (
            recover_jobs,
            recover_accounts,
            init_operations,
            recover_operations,
            cleanup_roxy,
            start_sms,
            recover_plans,
            recover_links,
            recover_live,
            backfill_proxy,
            resume_codex,
            start_risk_scan,
            start_at_refresh,
            start_codex_refresh,
        ):
            self.assertEqual(1, mock.call_count)


if __name__ == "__main__":
    unittest.main()
