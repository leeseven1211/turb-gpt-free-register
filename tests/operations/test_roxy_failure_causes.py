"""Roxy 已证实失败的纯诊断投影，不改变未知结果与原任务。"""
from copy import deepcopy
import json
import unittest

from core.operations.errors import classify_task_error


_PROFILE_PREFIX = (
    "RuntimeError: request_unknown: account_create_http_400: "
    "资料创建接口明确返回 HTTP 400；上游错误枚举="
)
_PROFILE_SUFFIX = "；已保留原身份与密码，需沿原任务链恢复"
_CONFLICT = "ValueError: 当前 Run 仍有未决浏览器提交，拒绝重复派发请求"


class RoxyFailureCauseTests(unittest.TestCase):
    def test_local_submission_conflict_is_specific_and_retains_unknown_impact(self):
        for task_type, stage, raw in (
            ("registration", "email_otp", _CONFLICT),
            ("registration_resume", "profile", "registration_failed: " + _CONFLICT),
        ):
            with self.subTest(task_type=task_type):
                summary = {"request_unknown": True, "retry_action": "registration_resume", "attempt_id": 8}
                original = deepcopy(summary)
                info = classify_task_error(
                    raw, task_type=task_type, stage=stage,
                    error_code="request_unknown", result_summary=summary, task_status="failed",
                )
                self.assertEqual("local_browser_submission_conflict", info["code"])
                self.assertEqual("SYS-SUBMISSION-001", info["display_code"])
                self.assertEqual("internal", info["source"])
                self.assertEqual("unknown", info["remote_state_impact"])
                self.assertTrue(info["reconcile_required"])
                self.assertEqual("request_unknown", info["original_error_code"])
                self.assertEqual(original, summary)

    def test_submission_conflict_requires_exact_generated_exception_and_registration(self):
        for raw, task_type in (
            (_CONFLICT, "extract_link"),
            (_CONFLICT, "twofa_retry"),
            (_CONFLICT.replace("ValueError", "RuntimeError"), "registration"),
            ("ValueError: 当前 Run 仍有未决浏览器提交", "registration"),
        ):
            with self.subTest(raw=raw, task_type=task_type):
                info = classify_task_error(raw, task_type=task_type)
                self.assertNotEqual("local_browser_submission_conflict", (info or {}).get("code"))

    def test_profile_registration_disallowed_is_preserved_for_saved_roxy_error(self):
        error = {"code": "registration_disallowed", "type": "invalid_request_error", "category": "signup_rejected"}
        for task_type in ("registration", "registration_resume"):
            with self.subTest(task_type=task_type):
                info = classify_task_error(
                    _PROFILE_PREFIX + json.dumps(error, separators=(",", ":")) + _PROFILE_SUFFIX,
                    task_type=task_type, stage="profile", error_code="request_unknown", task_status="failed",
                )
                self.assertEqual("account_create_registration_disallowed", info["code"])
                self.assertEqual("OA-REG-DISALLOWED-001", info["display_code"])
                self.assertTrue(info["reconcile_required"])
                self.assertEqual("unknown", info["remote_state_impact"])

    def test_profile_rejection_uses_current_structured_action_and_preserves_input(self):
        summary = {"request_unknown": True, "registration_diagnostics": {
            "operation": "profile_submit", "failure_kind": "http_error", "http_status": 400,
            "auth_error": {"code": "registration_disallowed", "type": "invalid_request_error"},
        }}
        original = deepcopy(summary)
        info = classify_task_error("资料创建失败", task_type="registration", stage="profile", result_summary=summary)
        self.assertEqual("account_create_registration_disallowed", info["code"])
        self.assertTrue(info["reconcile_required"])
        self.assertEqual(original, summary)
        for changed in (
            {"operation": "otp_submit"}, {"http_status": 401}, {"failure_kind": "transport_error"},
        ):
            invalid = deepcopy(summary)
            invalid["registration_diagnostics"].update(changed)
            info = classify_task_error("失败", task_type="registration", result_summary=invalid)
            self.assertNotEqual("account_create_registration_disallowed", (info or {}).get("code"))

    def test_profile_raw_error_rejects_unbound_or_malformed_evidence(self):
        errors = (
            '{"code":"registration_disallowed","code":"invalid_state"}',
            '{"code":"registration_disallowed","message":"private-secret"}',
            '{"code":"registration_disallowed","other":{"code":"registration_disallowed"}}',
            '{"code":"registration_disallowed_typo"}',
            '{"code":"' + "x" * 1000 + '"}',
        )
        for raw in [
            "registration_disallowed", "HTTP 400 registration_disallowed",
            *(_PROFILE_PREFIX + error + _PROFILE_SUFFIX for error in errors),
        ]:
            with self.subTest(raw=raw[:100]):
                info = classify_task_error(raw, task_type="registration")
                self.assertNotEqual("account_create_registration_disallowed", (info or {}).get("code"))
        info = classify_task_error(
            _PROFILE_PREFIX + '{"code":"registration_disallowed"}' + _PROFILE_SUFFIX, task_type="extract_link",
        )
        self.assertNotEqual("account_create_registration_disallowed", (info or {}).get("code"))
