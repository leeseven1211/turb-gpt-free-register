"""统一 wave 可在跨领域账号裁决前只规划注册补跑。"""
from unittest import TestCase
from unittest.mock import patch

from core.registration import retry_wave, service
from core.storage.registration.bulk_retry import RetryAdmission
from tests.support_pg import PostgresTestCase
from tests.registration.test_registration_resume_retry_chain import facts
from tests.registration import test_registration_retry_followups_service as followup_tests


class RetryWaveServiceTests(PostgresTestCase):
    setUp = followup_tests.RegistrationRetryFollowupsServiceTests.setUp
    source = followup_tests.RegistrationRetryFollowupsServiceTests.source
    def test_prepare_does_not_admit_or_wake_worker(self):
        sources = [self.source(index, action=action)
                   for index, action in enumerate(("plan_check", "codex", "twofa"), 1)]
        mapping = {index + 41: source["id"] for index, source in enumerate(sources)}
        from core.codex import operation_service as codex

        with (
            patch("core.storage.registration.retry_followups.admit", side_effect=AssertionError("unexpected write")),
            patch("core.storage.registration.bulk_retry.admit", side_effect=AssertionError("unexpected write")),
            patch("core.operations.task_gateway.notify_dispatch", side_effect=AssertionError("unexpected wake")),
            patch.object(codex, "_config_snapshot", return_value={"oauth_driver": "protocol"}),
            patch.object(codex, "_deployment_unavailable", return_value=None),
            patch.object(codex, "_feature_ready", return_value=(True, "")),
            patch("core.runtime.capabilities.account_setup_unavailable", return_value=None),
        ):
            wave = retry_wave.prepare(mapping)
        self.assertEqual(mapping, wave.sources)
        self.assertEqual([], wave.admissions)
        self.assertEqual(["plan_check", "codex", "twofa"], [spec.action for spec in wave.followups])
        self.assertEqual({}, wave.results)


class RetryWavePureTests(TestCase):
    def test_result_mapping_preserves_duplicate_source_order_without_mutating_receipt(self):
        wave = retry_wave.RetryWave({43: 22, 41: 21, 42: 21}, [], [], {})
        result = {21: {"ok": True, "status": 202}, 22: {"ok": False, "error": "blocked", "status": 409}}
        replies = retry_wave.task_replies(wave, result)
        self.assertEqual([43, 41, 42], list(replies))
        self.assertEqual((409, 202, 202), tuple(reply[1] for reply in replies.values()))
        self.assertEqual(202, result[21]["status"])

    def test_registration_admission_only_wakes_after_commit(self):
        root, _, _, attempt = facts()
        plan = RetryAdmission(
            source=root, root=root, attempt=attempt, action="registration", email=root["email"],
            email_source="icloud_hide", account=None, batch_id=None, batch_index=1, batch_size=1, workers=3,
            config_snapshot={"registration_driver": "protocol_oss_2"}, debug_enabled=False,
        )
        wave = retry_wave.RetryWave({41: root["id"]}, [plan], [], {})
        with (
            patch.object(service, "is_job_worker_active", return_value=False),
            patch("core.storage.registration.bulk_retry.admit", return_value={root["id"]: ({"id": 55}, True)}),
            patch.object(service, "configure_submission_workers"),
            patch.object(service, "notify_dispatch") as notify,
            patch.object(service, "start_dispatcher", side_effect=AssertionError("API starts worker")),
        ):
            result = retry_wave.admit_registration(wave)
        self.assertTrue(result[root["id"]]["created"])
        notify.assert_called_once()

    def test_busy_queue_state_is_not_treated_as_an_http_status(self):
        wave = retry_wave.RetryWave({41: 21}, [], [], {})
        payload, status = retry_wave.task_replies(wave, {
            21: {"ok": False, "busy": True, "status": "queued", "task_id": 50, "run_id": 60},
        })[41]
        self.assertEqual(409, status)
        self.assertEqual((50, 60), (payload["task_id"], payload["run_id"]))
