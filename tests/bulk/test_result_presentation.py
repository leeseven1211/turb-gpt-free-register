"""历史批量结果与当前结果在展示、字段筛选中的一致性。"""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from core.bulk_operations import results
from core.storage.operations import bulk_common, bulk_selections, store
from tests.support_pg import PostgresTestCase


class ResultPresentationTests(TestCase):
    def test_old_waiting_password_setup_remains_pending_without_changing_evidence(self):
        for state in ("pending_submit", "waiting_account", "queued", "running", "waiting"):
            with self.subTest(state=state):
                original = {"schema": "password_setup.v1", "state": state,
                            "result": {"confirmation": "unconfirmed", "after_state": "unconfirmed"}}
                before = deepcopy(original)
                projected = bulk_common.public_target_result(original)
                self.assertEqual(projected["state"], state)
                self.assertEqual(projected["result"]["confirmation"], "pending")
                self.assertEqual(projected["result"]["after_state"], "pending")
                self.assertNotIn("reason", projected)
                self.assertEqual(original, before)

    def test_new_password_setup_matches_historical_active_result(self):
        for state in ("pending_submit", "waiting_account", "queued", "running", "waiting"):
            with self.subTest(state=state):
                projected = results.project_one({"run": {"status": state}}, operation_key="password_setup")
                self.assertEqual(projected["result"]["confirmation"], "pending")
                self.assertEqual(projected["result"]["after_state"], "pending")
                self.assertFalse(projected["terminal"])

    def test_old_and_new_codex_failures_preserve_existing_credential(self):
        old = {"schema": "codex_retry.v1", "state": "attention_required", "source_status": "attention_required",
               "result": {"attempt_outcome": "attention_required", "credential_confirmation": "not_confirmed",
                          "asset_state_after": "valid", "existing_asset_preserved": True}}
        projected = bulk_common.public_target_result(old, summary={"existing_valid": True},
                                                     error_code="codex_credential_confirmation_missing")
        new = results.project_one({"run": {"status": "attention_required",
                                           "result_summary": {"existing_valid": True}}}, operation_key="codex_retry")
        for value in (projected, new):
            self.assertEqual(value["state"], "failed")
            self.assertEqual(value["result"]["credential_confirmation"], "failed")
            self.assertEqual(value["result"]["asset_state_after"], "valid")
            self.assertTrue(value["result"]["existing_asset_preserved"])
        self.assertEqual(old["result"]["credential_confirmation"], "not_confirmed")

    def test_old_and_new_active_codex_authorization_remain_pending(self):
        for state in ("queued", "running", "waiting"):
            with self.subTest(state=state):
                old = bulk_common.public_target_result({"schema": "codex_retry.v1", "state": state,
                    "result": {"credential_confirmation": "not_confirmed"}})
                new = results.project_one({"run": {"status": state}}, operation_key="codex_retry")
                self.assertEqual(old["result"]["credential_confirmation"], "pending")
                self.assertEqual(new["result"]["credential_confirmation"], "pending")
                self.assertFalse(new["terminal"])

    def test_explicit_partial_result_does_not_lose_independent_success(self):
        summary = {"requested_status": "partial_success", "completed_steps": ["password"],
                   "required_steps": ["password", "twofa"], "cause_code": "mfa_verify_failed"}
        old = {"schema": "account_completion.v1", "state": "attention_required",
               "source_status": "attention_required", "contribution": {"state": "attention_required"},
               "result": {"completed_steps": ["password"], "pending_steps": ["twofa"]}}
        before = deepcopy(old)
        projected = bulk_common.public_target_result(old, summary=summary)
        new = results.project_one({"run": {"status": "attention_required", "result_summary": summary}},
                                  operation_key="account_completion")
        for value in (projected, new):
            self.assertEqual(value["state"], "partial_success")
            self.assertEqual(value["source_status"], "partial_success")
            self.assertEqual(value["result"]["completed_steps"], ["password"])
        self.assertEqual(projected["contribution"]["state"], "partial_success")
        self.assertEqual(old, before)

    def test_partial_task_keeps_missing_business_confirmation_failed_like_new_projection(self):
        summary = {"requested_status": "partial_success", "cause_code": "email_otp_failed"}
        cases = (
            ("token_refresh", {"refresh_outcome": "unconfirmed", "confirmation": "unconfirmed"}),
            ("password_setup", {"confirmation": "unconfirmed", "after_state": "unconfirmed"}),
            ("codex_retry", {"attempt_outcome": "attention_required", "credential_confirmation": "not_confirmed",
                             "asset_state_after": "valid", "existing_asset_preserved": True}),
        )
        for operation, fields in cases:
            with self.subTest(operation=operation):
                facts = {**summary, "existing_valid": True}
                original = {"schema": operation + ".v1", "state": "attention_required", "result": fields}
                before = deepcopy(original)
                old = bulk_common.public_target_result(original, summary=facts)
                new = results.project_one({"run": {"status": "attention_required", "result_summary": facts}},
                                          operation_key=operation)
                self.assertEqual(old["state"], "partial_success")
                for key in fields:
                    self.assertEqual(old["result"][key], new["result"][key], key)
                self.assertEqual(original, before)

    def test_historical_unknown_query_uses_same_country_success_facts_as_new_projection(self):
        cases = (
            ("attention_required", {"ok": False}),
            ("attention_required", {"ok": True, "plan_check_countries": ["JP", "US"],
                                     "country_success_count": 1, "plan_check_partial": True}),
            ("attention_required", {"ok": True, "country_total_count": 2, "country_success_count": 2}),
            ("attention_required", {"ok": True}),
            ("attention_required", {"ok": True, "country_total_count": 2}),
            ("queued", {"ok": False}),
            ("cancelled", {}),
        )
        for state, facts in cases:
            with self.subTest(state=state, facts=facts):
                summary = {"requested_status": "partial_success", **facts}
                old = bulk_common.public_target_result({"schema": "plan_check.v1", "state": state,
                    "result": {"query_outcome": "unconfirmed"}}, summary=summary)
                new = results.project_one({"run": {"status": state, "result_summary": summary}}, operation_key="plan_check")
                self.assertEqual(old["result"]["query_outcome"], new["result"]["query_outcome"])
        known = bulk_common.public_target_result({"schema": "plan_check.v1", "state": "attention_required",
            "result": {"query_outcome": "partial_success", "country_success_count": 1}},
            summary={"requested_status": "partial_success"})
        self.assertEqual(known["result"], {"query_outcome": "partial_success", "country_success_count": 1})


class ResultFilterSqlTests(PostgresTestCase):
    def matches(self, state, fields, key, wanted, summary=None, schema=None):
        from psycopg.types.json import Jsonb

        # 直接在隔离 schema 中执行生产筛选表达式；同次 Run 摘要由合成目标行提供。
        with patch.object(bulk_common, "source_summary_sql", side_effect=lambda alias="tr": f"{alias}.source_summary"), \
                patch.object(bulk_selections, "source_summary_sql", side_effect=lambda alias="tr": f"{alias}.source_summary"):
            predicate, args = bulk_selections.result_predicate({"result_filters": {key: wanted}})
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""WITH tr AS (SELECT 1::bigint AS id,%s::text AS outcome,
                %s::jsonb AS result,%s::jsonb AS source_summary)
                SELECT ({predicate}) AS matches FROM tr""",
                (state, Jsonb({"result": fields, "schema": schema}), Jsonb(summary or {}), *args))
            return cur.fetchone()["matches"]

    def test_old_waiting_setup_confirmation_matches_pending_not_failed(self):
        for state in ("queued", "running", "waiting"):
            with self.subTest(state=state):
                fields = {"confirmation": "unconfirmed"}
                self.assertTrue(self.matches(state, fields, "confirmation", "pending"))
                self.assertFalse(self.matches(state, fields, "confirmation", "failed"))

    def test_old_codex_credential_filter_matches_public_state(self):
        for state, expected in (("queued", "pending"), ("running", "pending"),
                                ("failed", "failed"), ("attention_required", "failed")):
            with self.subTest(state=state):
                self.assertTrue(self.matches(state, {"credential_confirmation": "not_confirmed"},
                                             "credential_confirmation", expected))

    def test_explicit_partial_summary_matches_target_and_result_field(self):
        summary = {"requested_status": "partial_success"}
        for key in ("confirmation", "credential_confirmation", "attempt_outcome"):
            with self.subTest(key=key):
                fields = {key: "unconfirmed"}
                expected = "partial_success" if key == "attempt_outcome" else "failed"
                other = "failed" if expected == "partial_success" else "partial_success"
                self.assertTrue(self.matches("attention_required", fields, key, expected, summary))
                self.assertFalse(self.matches("attention_required", fields, key, other, summary))

    def test_query_filter_matches_python_and_new_country_projection(self):
        facts = (
            {"ok": False},
            {"ok": True},
            {"ok": True, "country_total_count": 2},
            {"ok": True, "country_total_count": 2, "country_success_count": 2},
            {"ok": True, "country_total_count": 2, "country_success_count": 1, "plan_check_partial": True},
            {"ok": True, "country_total_count": 0, "plan_check_countries": ["JP", "US"], "country_success_count": 1},
        )
        for state in ("attention_required", "queued", "cancelled"):
            for values in facts:
                with self.subTest(state=state, facts=values):
                    summary = {"requested_status": "partial_success", **values}
                    fields = {"query_outcome": "unconfirmed"}
                    old = bulk_common.public_target_result({"schema": "plan_check.v1", "state": state,
                        "result": fields}, summary=summary)
                    new = results.project_one({"run": {"status": state, "result_summary": summary}}, operation_key="plan_check")
                    expected = new["result"]["query_outcome"]
                    self.assertEqual(old["result"]["query_outcome"], expected)
                    self.assertTrue(self.matches(state, fields, "query_outcome", expected, summary))
        self.assertTrue(self.matches("attention_required", {"query_outcome": "partial_success"},
                                     "query_outcome", "partial_success"))

    def test_business_confirmation_sql_matches_new_projection_for_partial_and_cancelled(self):
        summary = {"requested_status": "partial_success"}
        for operation, keys in (("token_refresh", ("refresh_outcome", "confirmation")),
                                ("password_setup", ("confirmation",)),
                                ("codex_retry", ("attempt_outcome", "credential_confirmation"))):
            for state in ("attention_required", "cancelled", "not_executed"):
                new = results.project_one({"run": {"status": state, "result_summary": summary}}, operation_key=operation)
                for key in keys:
                    with self.subTest(operation=operation, state=state, key=key):
                        # schema 是业务确认字段解释的一部分。
                        self.assertTrue(self.matches(state, {key: "unconfirmed"}, key,
                                                     new["result"][key], summary, schema=operation + ".v1"))
