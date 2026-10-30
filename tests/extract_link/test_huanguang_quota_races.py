"""幻光额度查询并发返回和提交预算释放的回归验证。"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from core.extract_link import service as service


def _quota(remaining: int) -> dict:
    return {
        "ok": True,
        "extraction": {"required": True, "remaining": remaining, "reserved": 0, "active": True},
        "payment": {"required": False, "remaining": None, "reserved": None, "active": None},
    }


class HuanguangQuotaRaceTests(TestCase):
    def setUp(self):
        service._HUANGUANG_QUOTA_BLOCKS.clear()
        service._HUANGUANG_QUOTA_INFLIGHT.clear()
        service._HUANGUANG_QUOTA_ADMITTED.clear()
        self.runtime = SimpleNamespace(config=SimpleNamespace(
            api_base="https://platform.example.test", cdk="synthetic-race-cdk", payment_cdk="",
        ))

    def gate(self, context):
        return service._huanguang_create_quota(
            context, self.runtime, provider_id="huanguang", mode="extract_only", action="create",
        )

    def test_stale_positive_response_cannot_reuse_released_last_use(self):
        query_started = threading.Event()
        return_old_response = threading.Event()
        outcomes = []
        failures = []
        stale_context = SimpleNamespace(defer=Mock())

        def query(**_kwargs):
            if threading.current_thread().name == "huanguang-old-quota-response":
                # 模拟上游已经读到最后一次，但响应晚于另一个任务提交返回。
                snapshot = _quota(1)
                query_started.set()
                if not return_old_response.wait(5):
                    raise AssertionError("未收到旧额度响应的放行信号")
                return snapshot
            return _quota(1)

        def delayed_worker():
            try:
                with self.gate(stale_context) as allowed:
                    outcomes.append(bool(allowed))
            except Exception as exc:
                failures.append(exc)

        worker = threading.Thread(target=delayed_worker, name="huanguang-old-quota-response", daemon=True)
        with patch.object(service, "query_huanguang_cdk_quota", side_effect=query):
            worker.start()
            try:
                self.assertTrue(query_started.wait(5), "旧额度查询未开始")
                with self.gate(SimpleNamespace(defer=Mock())) as release_submission:
                    self.assertTrue(release_submission)
                    # 创建请求已返回，后续监控仍可继续；已使用的最后一次不能被旧响应复用。
                    release_submission()
                    self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)
                    return_old_response.set()
                    worker.join(5)
                    self.assertFalse(worker.is_alive(), "旧额度查询未结束")
            finally:
                return_old_response.set()
                worker.join(5)
        self.assertEqual([], failures)
        self.assertEqual([False], outcomes)
        stale_context.defer.assert_called_once_with(
            delay_seconds=60, stage="quota_local_reserved",
            reason=service._HUANGUANG_QUOTA_STAGES["quota_local_reserved"],
        )
        self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)

    def test_submission_release_is_idempotent_and_does_not_wait_for_monitoring(self):
        first_context = SimpleNamespace(defer=Mock())
        second_context = SimpleNamespace(defer=Mock())
        with patch.object(service, "query_huanguang_cdk_quota", side_effect=[_quota(2), _quota(1)]):
            with self.gate(first_context) as release_first:
                release_first()
                release_first()
                self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)
                # 第一个任务尚未退出监控上下文，新查询的剩余一次仍可用于第二次提交。
                with self.gate(second_context) as release_second:
                    self.assertTrue(release_second)
                    release_second()
                    release_second()
                    self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)
        first_context.defer.assert_not_called()
        second_context.defer.assert_not_called()
        self.assertEqual({}, service._HUANGUANG_QUOTA_INFLIGHT)
