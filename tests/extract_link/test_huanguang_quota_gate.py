from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from core.extract_link import service as service
from tests.extract_link import test_extract_link_provider_flow as provider_flow


def quotas(extraction=100, payment=100):
    return {"ok": True, **{name: {"required": True, "remaining": remaining, "reserved": 0, "active": True}
                           for name, remaining in (("extraction", extraction), ("payment", payment))}}


class HuanguangQuotaGateTests(TestCase):
    def setUp(self):
        service._HUANGUANG_QUOTA_BLOCKS.clear()
        service._HUANGUANG_QUOTA_INFLIGHT.clear()
        service._HUANGUANG_QUOTA_ADMITTED.clear()
        self.context = SimpleNamespace(defer=Mock())
        self.runtime = SimpleNamespace(config=SimpleNamespace(
            api_base="https://platform.example.test", cdk="synthetic-extract-cdk", payment_cdk="synthetic-scan-cdk",
        ))

    def gate(self, *, mode="auto_payment", action="create", provider="huanguang", context=None):
        return service._huanguang_create_quota(
            context or self.context, self.runtime, provider_id=provider, mode=mode, action=action,
        )

    def test_each_cdk_exhaustion_or_disabled_status_defers_same_run(self):
        for kind in ("extraction", "payment"):
            for condition in ("exhausted", "disabled"):
                with self.subTest(kind=kind, condition=condition):
                    self.setUp()
                    quota = quotas()
                    quota[kind]["remaining" if condition == "exhausted" else "active"] = 0 if condition == "exhausted" else False
                    with patch.object(service, "query_huanguang_cdk_quota", return_value=quota):
                        with self.gate() as allowed:
                            self.assertFalse(allowed)
                    self.context.defer.assert_called_once_with(
                        delay_seconds=60, stage=f"quota_{kind}_{condition}",
                        reason=service._HUANGUANG_QUOTA_STAGES[f"quota_{kind}_{condition}"],
                    )
                    self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)

    def test_query_failure_or_unknown_active_waits_without_inventing_zero(self):
        for value in (RuntimeError("private-provider-response"), quotas()):
            with self.subTest(value=type(value).__name__):
                self.setUp()
                if isinstance(value, dict):
                    value["payment"]["active"] = None
                with patch.object(service, "query_huanguang_cdk_quota", **(
                    {"side_effect": value} if isinstance(value, Exception) else {"return_value": value}
                )):
                    with self.gate() as allowed:
                        self.assertFalse(allowed)
                self.assertEqual("quota_unavailable", self.context.defer.call_args.kwargs["stage"])
                self.assertNotIn("private", repr(self.context.defer.call_args))

    def test_positive_quota_is_queried_again_and_reservation_released(self):
        with patch.object(service, "query_huanguang_cdk_quota", return_value=quotas()) as query:
            for _ in range(2):
                with self.gate() as allowed:
                    self.assertTrue(allowed)
                    self.assertTrue(service._HUANGUANG_QUOTA_INFLIGHT)
                self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)
        self.assertEqual(2, query.call_count)
        self.context.defer.assert_not_called()

    def test_last_available_use_is_not_assigned_to_two_local_submissions(self):
        with patch.object(service, "query_huanguang_cdk_quota", return_value=quotas(extraction=1)):
            with self.gate() as first:
                self.assertTrue(first)
                with self.gate(context=SimpleNamespace(defer=Mock())) as second:
                    self.assertFalse(second)
        self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)

    def test_reserved_remote_uses_are_not_subtracted_twice_and_extraction_can_be_unmetered(self):
        quota = quotas(extraction=1)
        quota["extraction"]["reserved"] = 20
        for unmetered in (False, True):
            with self.subTest(unmetered=unmetered):
                if unmetered:
                    quota["extraction"] = {"required": False, "remaining": None, "reserved": None, "active": True}
                with patch.object(service, "query_huanguang_cdk_quota", return_value=quota):
                    with self.gate() as allowed:
                        self.assertTrue(allowed)

    def test_extract_only_does_not_require_payment_quota(self):
        with patch.object(service, "query_huanguang_cdk_quota", return_value=quotas(payment=0)) as query:
            with self.gate(mode="extract_only") as allowed:
                self.assertTrue(allowed)
        self.assertIs(False, query.call_args.kwargs["include_payment"])

    def test_original_job_queries_and_other_providers_bypass_quota_gate(self):
        with patch.object(service, "query_huanguang_cdk_quota") as query:
            for action in ("sync_status", "manual_payment", "auto_payment"):
                with self.gate(action=action) as allowed:
                    self.assertTrue(allowed)
            with self.gate(provider="lumen_flow") as allowed:
                self.assertTrue(allowed)
        query.assert_not_called()

    def test_blocked_cache_is_invalidated_when_cdk_changes(self):
        with patch.object(service, "query_huanguang_cdk_quota", side_effect=[quotas(0), quotas()]) as query:
            with self.gate() as allowed:
                self.assertFalse(allowed)
            with self.gate() as allowed:
                self.assertFalse(allowed)
            self.runtime.config.cdk = "updated-synthetic-cdk"
            with self.gate() as allowed:
                self.assertTrue(allowed)
        self.assertEqual(2, query.call_count)

    def test_cache_hits_do_not_extend_block_after_quota_refill(self):
        clock = {"now": 0}
        with (
            patch.object(service.time, "monotonic", side_effect=lambda: clock["now"]),
            patch.object(service, "query_huanguang_cdk_quota", side_effect=[quotas(0), quotas()]) as query,
        ):
            with self.gate() as allowed:
                self.assertFalse(allowed)
            clock["now"] = 10
            with self.gate() as allowed:
                self.assertFalse(allowed)
            clock["now"] = 16
            with self.gate() as allowed:
                self.assertTrue(allowed)
        self.assertEqual(2, query.call_count)

    def test_local_budget_is_released_when_execution_raises(self):
        with patch.object(service, "query_huanguang_cdk_quota", return_value=quotas()):
            with self.assertRaises(RuntimeError):
                with self.gate():
                    raise RuntimeError("本机预检失败")
        self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)

    def test_handler_defers_before_at_preflight_proxy_or_remote_creation(self):
        fixture = provider_flow.ExtractLinkPreflightConfigurationTests()
        with fixture._scenario(provider_id="huanguang", preflight_enabled=True,
                               refresh_at_enabled=True, inline_results=[]) as scenario:
            scenario.context.defer = Mock()
            with (
                patch.object(service, "query_huanguang_cdk_quota", return_value=quotas(0)),
                patch.object(service, "_ensure_extract_token") as token,
                patch.object(service, "_prepare_huanguang_proxies") as proxies,
                patch.object(service.db, "mark_account_extract_running") as mark,
            ):
                service._handle_provider_operation(scenario.context)
            scenario.context.defer.assert_called_once()
            scenario.context.finish.assert_not_called()
            scenario.provider.create_job.assert_not_called()
            scenario.save_job.assert_not_called()
            token.assert_not_called()
            proxies.assert_not_called()
            mark.assert_not_called()

    def test_quota_waiting_projection_preserves_old_facts_and_shows_current_reason(self):
        item = service._workbench_task_item({
            "task_id": 1, "run_id": 2, "run_count": 3, "run_status": "queued",
            "task_data": {"provider_id": "huanguang", "mode": "auto_payment"},
            "progress_stage": "quota_payment_exhausted",
            "public_state": {"extraction_state": "succeeded", "payment_state": "unknown",
                             "message": "旧网络错误", "summary": {"current_step": "旧进度"},
                             "links": ["https://checkout.example.test/saved"]},
        })
        self.assertEqual("支付扫码 CDK 次数已用完，等待补充额度", item["message"])
        self.assertEqual(item["message"], item["progress"]["label"])
        self.assertEqual("", item["error"])
        self.assertEqual((2, 3, "queued", "success"), (
            item["run_id"], item["run_count"], item["task_status"], item["extraction_status"],
        ))
        self.assertTrue(item["has_payment_entry"])

    def test_read_only_quota_query_does_not_receive_account_or_token(self):
        provider = SimpleNamespace(query_cdk_quota=Mock(side_effect=[quotas()["extraction"], quotas()["payment"]]))
        with patch.object(service, "_provider", return_value=provider):
            result = service.query_huanguang_cdk_quota(runtime=self.runtime)
        self.assertEqual(100, result["payment"]["remaining"])
        self.assertEqual(2, provider.query_cdk_quota.call_count)
        self.assertNotIn("synthetic", repr(result))
