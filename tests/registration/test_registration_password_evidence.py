"""候选密码跨失败续跑与账号补全的证据边界。"""
from __future__ import annotations

import json

from core.accounts.completion import completion_plan
from core.accounts.password_evidence import password_is_confirmed, registration_password_extra
from core.registration.postprocess import summarize_postprocess
from core.storage import records, registration
from tests.support_pg import PostgresTestCase


class RegistrationPasswordEvidenceTests(PostgresTestCase):
    def test_accepted_password_and_profile_before_token_remain_candidates(self):
        for checkpoint in ("otp_confirmed", "account_request_started", "account_confirmed"):
            with self.subTest(checkpoint=checkpoint):
                email = f"{checkpoint}@fixture.test"
                attempt = registration.create_attempt(email)
                aid = int(attempt["id"])
                run = registration.start_run(aid, execution_id=email, initial_status="running")
                saved = registration.save_password_checkpoint(
                    aid, email=email, password="Candidate-original", state="confirmed",
                    run_id=int(run["id"]), execution_id=email, account={"email_source": "generic_api"})
                registration.advance_checkpoint(aid, checkpoint)
                account = records.get_row(records.ACCOUNTS, int(saved["account_id"]))
                self.assertEqual("", account["access_token"])
                self.assertEqual("candidate", json.loads(account["extra_json"])["account_password_state"])
                self.assertFalse(password_is_confirmed(account))

    def test_otp_only_resume_keeps_original_candidate_and_requests_password_completion(self):
        email = "otp-only@fixture.test"
        aid = int(registration.create_attempt(email)["id"])
        first = registration.start_run(aid, execution_id="first", initial_status="running")
        registration.save_password_checkpoint(
            aid, email=email, password="Candidate-original", state="confirmed",
            run_id=int(first["id"]), execution_id="first", account={"email_source": "generic_api"})
        registration.finish_run(int(first["id"]), status="failed", error_code="email_otp_no_mail")
        second = registration.start_run(aid, action_type="registration_resume", execution_id="second", initial_status="running")
        result = registration.persist_core_account(
            aid, access_token="fixture-at", run_id=int(second["id"]), execution_id="second",
            account={"extra_json": json.dumps({"registration_checkpoint": "core_persisted"})})
        account = records.get_row(records.ACCOUNTS, int(result["account_id"]))
        self.assertEqual("Candidate-original", json.loads(account["extra_json"])["account_password"])
        self.assertFalse(password_is_confirmed(account))
        plan = completion_plan(account, {"password_enabled": True, "plan_check_enabled": False,
                                         "twofa_enabled": False, "codex_enabled": False})
        self.assertEqual(["password"], plan["missing_steps"])

    def test_token_with_explicit_password_confirmation_is_ready(self):
        aid = int(registration.create_attempt("confirmed@fixture.test")["id"])
        saved = registration.persist_core_account(aid, access_token="fixture-at", account={
            "extra_json": json.dumps(registration_password_extra("Confirmed-original", confirmed=True))})
        self.assertTrue(password_is_confirmed(saved["account"]))


def test_historical_password_alone_is_not_confirmation():
    assert not password_is_confirmed({"access_token": "fixture-at", "extra_json": {"account_password": "Historical"}})
    summary = summarize_postprocess(core_success=True, password_present=False, password_required=True,
                                    twofa_required=False, plan_check_required=False, codex_enabled=False)
    assert summary.account_readiness == "incomplete"
    assert [item.action for item in summary.next_actions] == ["account_setup_retry"]
