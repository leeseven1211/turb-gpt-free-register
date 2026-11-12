"""报告按账号当前轮次聚合；只在独立测试库验证 SQL 与 API。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import patch

from core.storage import records
from core.storage.operations import bulk, bulk_common as common
from core.storage.operations.bulk_report import _CACHE, _duration
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class PlanReportTests(PostgresTestCase):
    def setUp(self):
        bulk.reset_ready()
        bulk.init()
        _CACHE.clear()
        settings = patch("core.bulk_operations.catalog.capture_settings",
                         return_value={"config_revision": "report-test", "effective_settings": {}})
        settings.start()
        self.addCleanup(settings.stop)

    def batch(self, count=3, *, operation="plan_check"):
        ids = self.seed(records.ACCOUNTS, [{"email": f"report-{uuid.uuid4().hex}@example.test",
            "created_at": "2026-10-15T12:00:00", "plan_check_ok": True, "plan_check_status": "success",
            "current_plan_type": "plus", "plus_promo_kind": "free_trial"} for _ in range(count)])
        selection = bulk.create_selection(request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": ids},
            operation_key=operation, config_revision="report-test")
        bulk.freeze_selection(selection["id"])
        return bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selection["id"],
            selection_revision=1, operation_key=operation, parameters={}, config_revision="report-test")

    def rows(self, batch_id, round_id=None):
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {common.table('operation_batch_target_rounds')} WHERE batch_id=%s "
                        "AND (%s::bigint IS NULL OR round_id=%s) ORDER BY id", (batch_id, round_id, round_id))
            return [dict(row) for row in cur.fetchall()]

    def attach(self, target, *, state="success", start=0, seconds=10, relation="owned_root", generation=1, summary=None):
        base = datetime(2026, 11, 1, tzinfo=timezone.utc)
        started = base + timedelta(seconds=start) if start is not None else None
        ended = started + timedelta(seconds=seconds) if started is not None and seconds is not None else None
        uid = uuid.uuid4().hex
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {common.table('operation_tasks')}
              (task_uuid,source_system,source_id,batch_id,task_type,target_type,requested_action,status)
              VALUES (%s,'bulk_report_test',%s,%s,'plan_check','account','plan_check',%s) RETURNING id""",
                        (uid, uid, target["batch_id"], state))
            task_id = cur.fetchone()["id"]
            cur.execute(f"""INSERT INTO {common.table('operation_runs')}
              (run_uuid,task_id,run_no,source_system,source_id,batch_id,status,started_at,completed_at,result_summary)
              VALUES (%s,%s,1,'bulk_report_test',%s,%s,%s,%s,%s,%s::jsonb) RETURNING id""",
                        (uid, task_id, uid, target["batch_id"], state, started, ended, common.dumps(summary or {})))
            run_id = cur.fetchone()["id"]
            cur.execute(f"""INSERT INTO {common.table('operation_batch_run_links')}
              (target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,step_key,execution_generation,relation)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (target["id"], task_id, run_id, task_id, run_id, "plan_check", generation, relation))
            if relation != "external_blocker":
                cur.execute(f"""UPDATE {common.table('operation_batch_target_rounds')}
                  SET outcome=%s,chain_started_at=%s,chain_closed_at=%s WHERE id=%s""",
                            (state, started, ended, target["id"]))
        return run_id

    def complete(self, batch):
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common.table('operation_batch_controls')} SET state='ended',summary_revision=summary_revision+1 WHERE batch_id=%s", (batch["id"],))
            cur.execute(f"UPDATE {common.table('operation_batch_rounds')} SET state='completed',completed_at=now(),summary_revision=summary_revision+1 WHERE batch_id=%s", (batch["id"],))

    def promotion_event(self, run_id, *, country=None, ok=True, truncated=False, offer=False, event_no=1):
        rows = [{"plan": plan, "kind": "free_trial" if offer and plan == "plus" else "none",
                 "eligible": offer and plan == "plus", "stale": False} for plan in ("go", "plus")]
        detail = {"ok": ok, "phase": "initial", "account_promotions": rows, "truncated": truncated}
        if country:
            detail["country"] = country
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {common.table('operation_events')}
              (event_uuid,task_id,run_id,source_system,source_id,stage,event_type,message,detail,created_at)
              SELECT %s,task_id,id,'bulk_report_test',%s,'plan_check','promotion.query.recorded','套餐回执样例',%s::jsonb,%s
              FROM {common.table('operation_runs')} WHERE id=%s""",
                        (uuid.uuid4().hex, uuid.uuid4().hex, common.dumps(detail),
                         datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(seconds=event_no), run_id))

    def test_missing_runs_and_implicit_members_do_not_use_account_cached_promotions(self):
        batch = self.batch(5)
        bulk.materialize_targets(batch["id"], limit=2)
        report = bulk.get_plan_report(batch["id"])
        self.assertEqual(report["totals"]["accounts"], 5)
        self.assertEqual(report["totals"]["active"], 5)
        self.assertEqual(report["plans"], [{"plan": "unknown", "accounts": 5}])
        self.assertEqual(report["offers"]["with_offer_accounts"], 0)
        self.assertEqual(report["offers"]["unknown_accounts"], 5)
        self.assertIsNone(report["duration"]["avg_seconds"])
        self.assertEqual(report["duration"]["sample_count"], 0)
        report = bulk.get_plan_report(batch["id"], round_id=batch["round_id"])
        self.assertEqual(report["totals"]["accounts"], 5)

    def test_duration_uses_owned_chain_elapsed_not_sum_or_external_blocker(self):
        batch = self.batch(3)
        bulk.materialize_targets(batch["id"])
        targets = self.rows(batch["id"])
        self.attach(targets[0], start=0, seconds=10)
        self.attach(targets[0], start=5, seconds=25, relation="owned_child", generation=2)
        self.attach(targets[0], start=-500, seconds=1000, relation="external_blocker")
        self.attach(targets[1], state="failed", seconds=50)
        self.attach(targets[2], state="running", seconds=None)
        report = bulk.get_plan_report(batch["id"])
        self.assertEqual(report["duration"], {"sample_count": 2, "missing_count": 0,
            "avg_seconds": 40.0, "min_seconds": 30.0, "max_seconds": 50.0,
            "measurement": "account_execution_elapsed"})
        self.assertEqual(report["totals"], {"accounts": 3, "success": 1, "failed": 1, "partial_success": 0,
            "cancelled": 0, "not_executed": 0, "completed": 2, "active": 1})

    def test_incomplete_terminal_timestamps_are_missing_not_zero(self):
        batch = self.batch(3)
        bulk.materialize_targets(batch["id"])
        targets = self.rows(batch["id"])
        self.attach(targets[0], seconds=None)
        self.attach(targets[1], seconds=-1)
        self.attach(targets[2], state="cancelled", start=None)
        self.complete(batch)
        report = bulk.get_plan_report(batch["id"])
        self.assertEqual(report["phase"], "completed")
        self.assertEqual(report["duration"]["missing_count"], 2)
        self.assertEqual(report["duration"]["sample_count"], 0)
        self.assertIsNone(report["duration"]["min_seconds"])

    def test_current_retry_scope_replaces_one_account_and_history_remains_fixed(self):
        batch = self.batch(3)
        bulk.materialize_targets(batch["id"])
        for target in self.rows(batch["id"]):
            self.attach(target, seconds=30)
        self.complete(batch)
        roots = bulk.list_targets(batch["id"])["items"]
        retry = bulk.create_round(batch["id"], request_key=uuid.uuid4().hex, source={"view": "current"},
            selection={"kind": "targets", "target_ids": [roots[0]["id"]]})
        bulk.freeze_round(retry["id"])
        # 尚未展开的重跑成员已替换旧结果；旧首轮仍有3个成功。
        current = bulk.get_plan_report(batch["id"])
        self.assertEqual(current["totals"]["accounts"], 3)
        self.assertEqual(current["totals"]["success"], 2)
        self.assertEqual(current["totals"]["active"], 1)
        self.assertEqual(current["duration"]["sample_count"], 2)
        old = bulk.get_plan_report(batch["id"], round_id=batch["round_id"])
        self.assertEqual(old["totals"]["success"], 3)
        self.assertEqual(old["phase"], "completed")
        retry_report = bulk.get_plan_report(batch["id"], round_id=retry["id"])
        self.assertEqual(retry_report["totals"]["accounts"], 1)
        self.assertEqual(retry_report["duration"]["sample_count"], 0)

    def test_scope_rejects_other_batch_round_and_other_operation(self):
        one, other = self.batch(1), self.batch(1)
        with self.assertRaises(common.BulkError) as error:
            bulk.get_plan_report(one["id"], round_id=other["round_id"])
        self.assertEqual(error.exception.status, 404)
        unsupported = self.batch(1, operation="token_refresh")
        with self.assertRaises(common.BulkError) as error:
            bulk.get_plan_report(unsupported["id"])
        self.assertEqual(error.exception.code, "report_operation_unsupported")

    def test_offer_and_refresh_counts_deduplicate_countries_without_using_failed_snapshot(self):
        batch = self.batch(4)
        bulk.materialize_targets(batch["id"])
        targets = self.rows(batch["id"])
        summaries = [
            {"ok": True, "current_plan_type": "free", "auto_refresh_at": {"attempted": True,
             "ok": True, "status": "success", "reason": "token_local_expired"},
             "account_promotions": [{"plan": "plus", "kind": "free_trial", "eligible": True, "country": country}
                                    for country in ("JP", "US")],
             "plan_report_evidence": {"version": 1, "promotion_complete": True, "at_refresh_observed": True,
                                      "offers_by_plan": {"plus": ["free_trial", "free_trial"], "go": ["half_price"]}}},
            {"ok": True, "current_plan_type": "free", "plan_check_partial": True,
             "auto_refresh_at": {"attempted": True, "ok": False, "status": "failed", "reason": "token_missing"},
             "account_promotions": [{"plan": "plus", "kind": "free_trial", "eligible": True}]},
            {"ok": True, "current_plan_type": "plus", "plan_report_evidence": {"version": 1,
             "promotion_complete": True, "confirmed_none": True, "offers_by_plan": {}, "at_refresh_observed": True}},
            {"ok": True, "current_plan_type": "pro", "account_promotions": [
                {"plan": "plus", "kind": "free_trial", "eligible": True}]},
        ]
        for target, state, summary in zip(targets, ("success", "partial_success", "success", "failed"), summaries):
            self.attach(target, state=state, summary=summary)
        self.complete(batch)
        report = bulk.get_plan_report(batch["id"])
        self.assertEqual(report["offers"], {"with_offer_accounts": 2, "confirmed_no_offer_accounts": 1,
            "unknown_accounts": 1, "by_plan": [
                {"plan": "go", "accounts": 1, "kinds": [{"kind": "half_price", "accounts": 1}]},
                {"plan": "plus", "accounts": 2, "kinds": [{"kind": "free_trial", "accounts": 2}]}]})
        self.assertEqual(report["plans"], [{"plan": "free", "accounts": 2}, {"plan": "plus", "accounts": 1},
            {"plan": "unknown", "accounts": 1}])
        self.assertEqual(report["at_refresh"], {"expired_accounts": 1, "missing_token_accounts": 1,
            "invalid_accounts": 0, "attempted_accounts": 2, "succeeded_accounts": 1, "failed_accounts": 1,
            "pending_accounts": 0, "not_needed_accounts": 1, "unknown_accounts": 1, "not_executed_accounts": 0})

    def test_cached_reports_are_detached_and_change_after_projection_revision(self):
        batch = self.batch(1)
        report = bulk.get_plan_report(batch["id"])
        report["totals"]["accounts"] = -1
        self.assertEqual(bulk.get_plan_report(batch["id"])["totals"]["accounts"], 1)
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common.table('operation_batch_controls')} SET summary_revision=summary_revision+1 WHERE batch_id=%s", (batch["id"],))
        fresh = bulk.get_plan_report(batch["id"])
        self.assertGreater(fresh["summary_revision"], report["summary_revision"])

    def test_historical_events_restore_none_only_for_complete_last_owned_country_receipts(self):
        batch = self.batch(5)
        bulk.materialize_targets(batch["id"])
        rows = self.rows(batch["id"])
        summary = {"ok": True, "current_plan_type": "free", "plan_check_countries": ["JP", "US"],
                   "country_success_count": 2, "country_total_count": 2}
        runs = [self.attach(target, summary=summary) for target in rows]
        for run_id in runs[:4]:
            self.promotion_event(run_id, country="JP")
            self.promotion_event(run_id, country="US")
        # 完整2国明确none；后来US失败、截断、其他Run有记录分别不得伪报无优惠。
        self.promotion_event(runs[1], country="US", ok=False, event_no=2)
        self.promotion_event(runs[2], country="US", truncated=True, event_no=2)
        self.promotion_event(runs[3], country="US", offer=True, event_no=2)
        blocker = self.attach(rows[4], relation="external_blocker", summary=summary)
        self.promotion_event(blocker, country="JP")
        self.promotion_event(blocker, country="US")
        self.complete(batch)
        report = bulk.get_plan_report(batch["id"])
        self.assertEqual(report["offers"]["confirmed_no_offer_accounts"], 1)
        self.assertEqual(report["offers"]["with_offer_accounts"], 1)
        self.assertEqual(report["offers"]["unknown_accounts"], 3)
        self.assertEqual(report["offers"]["by_plan"], [{"plan": "plus", "accounts": 1,
            "kinds": [{"kind": "free_trial", "accounts": 1}]}])

    def test_historical_countryless_single_query_receipt_and_missing_events(self):
        batch = self.batch(2)
        bulk.materialize_targets(batch["id"])
        targets = self.rows(batch["id"])
        first = self.attach(targets[0], summary={"ok": True, "current_plan_type": "free"})
        self.attach(targets[1], summary={"ok": True, "current_plan_type": "free"})
        self.promotion_event(first)
        self.complete(batch)
        report = bulk.get_plan_report(batch["id"])
        self.assertEqual(report["offers"]["confirmed_no_offer_accounts"], 1)
        self.assertEqual(report["offers"]["unknown_accounts"], 1)

    def test_historical_event_restores_other_plan_after_summary_list_truncation(self):
        batch = self.batch(1)
        bulk.materialize_targets(batch["id"])
        target = self.rows(batch["id"])[0]
        run_id = self.attach(target, summary={"ok": True, "current_plan_type": "free",
            "account_promotions": [{"plan": "plus", "kind": "free_trial", "eligible": True}] * 120})
        # 根摘要刚好触及通用120项上限；已显示Plus不证明后面的Go没有优惠。
        uid = uuid.uuid4().hex
        detail = {"ok": True, "phase": "initial", "truncated": False, "account_promotions": [
            {"plan": "plus", "kind": "free_trial", "eligible": True},
            {"plan": "go", "kind": "discount", "eligible": True, "discount_percentage": 50}]}
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {common.table('operation_events')}
              (event_uuid,task_id,run_id,source_system,source_id,stage,event_type,message,detail)
              SELECT %s,task_id,id,'bulk_report_test',%s,'plan_check','promotion.query.recorded','完整套餐回执样例',%s::jsonb
              FROM {common.table('operation_runs')} WHERE id=%s""", (uid, uid, common.dumps(detail), run_id))
        self.complete(batch)
        report = bulk.get_plan_report(batch["id"])
        self.assertEqual(report["offers"]["with_offer_accounts"], 1)
        self.assertEqual(report["offers"]["by_plan"], [
            {"plan": "go", "accounts": 1, "kinds": [{"kind": "half_price", "accounts": 1}]},
            {"plan": "plus", "accounts": 1, "kinds": [{"kind": "free_trial", "accounts": 1}]}])

    def test_report_endpoint_readonly_authenticated_and_conditional(self):
        batch = self.batch(1)
        client = create_app(auth_code="report-isolated-test").test_client()
        path = f'/api/bulk/batches/{batch["id"]}/report'
        self.assertNotEqual(client.get(path).status_code, 200)
        headers = {"X-Auth-Code": "report-isolated-test"}
        first = client.get(path, headers=headers)
        self.assertEqual(first.status_code, 200, first.json)
        self.assertEqual(first.json["data"]["batch_id"], str(batch["id"]))
        self.assertEqual(first.json["data"]["view"]["kind"], "current")
        self.assertIn("ETag", first.headers)
        cached = client.get(path, headers={**headers, "If-None-Match": first.headers["ETag"]})
        self.assertEqual(cached.status_code, 304)
        bad = client.get(path + '?view=invalid', headers=headers)
        self.assertEqual(bad.status_code, 422)
        for key in ("access_token", "config_snapshot", "account_promotions", "email"):
            self.assertNotIn(key, first.data.decode())
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {common.table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_all_other_catalog_operations_share_counts_timing_and_scope_metrics(self):
        cases = {
            "token_refresh": "account.token_refresh.unconfirmed",
            "password_setup": "account.password_setup.confirmed",
            "twofa_setup": "account.twofa_setup.confirmed",
            "codex_retry": "account.codex.credential_confirmed",
            "account_completion": "step.password.confirmed",
        }
        with patch("core.storage.operations.bulk_report._load_historical_promotions",
                   side_effect=AssertionError("非套餐报告不应读取优惠事件")), \
             patch("core.bulk_operations.plan_report_evidence.normalize_plan_report_evidence",
                   side_effect=AssertionError("非套餐报告不应归一化套餐证据")):
            for operation, metric in cases.items():
                with self.subTest(operation=operation):
                    batch = self.batch(2, operation=operation)
                    bulk.materialize_targets(batch["id"])
                    targets = self.rows(batch["id"])
                    self.attach(targets[0], seconds=10)
                    self.attach(targets[1], state="failed", seconds=30)
                    self.complete(batch)
                    with common.connect() as conn, conn.cursor() as cur:
                        cur.execute(f"UPDATE {common.table('operation_batch_controls')} SET metrics=%s::jsonb WHERE batch_id=%s",
                                    (common.dumps({metric: 2}), batch["id"]))
                        cur.execute(f"UPDATE {common.table('operation_batch_rounds')} SET metrics=%s::jsonb WHERE id=%s",
                                    (common.dumps({metric: 1}), batch["round_id"]))
                    report = bulk.get_task_report(batch["id"])
                    self.assertEqual(report["operation_key"], operation)
                    self.assertEqual(report["phase"], "completed")
                    self.assertEqual(report["totals"], {"accounts": 2, "success": 1, "failed": 1,
                        "partial_success": 0, "not_executed": 0, "cancelled": 0, "completed": 2, "active": 0})
                    self.assertEqual(report["duration"]["avg_seconds"], 20)
                    public_metric = metric.replace(".unconfirmed", ".failed")
                    self.assertEqual(report["business_summary"], {public_metric: 2})
                    historical = bulk.get_task_report(batch["id"], round_id=batch["round_id"])
                    self.assertEqual(historical["business_summary"], {public_metric: 1})
                    self.assertEqual(historical["view"]["round_id"], batch["round_id"])
                    for key in ("plans", "offers", "at_refresh"):
                        self.assertNotIn(key, report)

    def test_generic_route_serves_nonplan_scope_and_rejects_unknown_operation(self):
        batch = self.batch(1, operation="password_setup")
        other = self.batch(1, operation="twofa_setup")
        client = create_app(auth_code="report-isolated-test").test_client()
        path = f'/api/bulk/batches/{batch["id"]}/report'
        headers = {"X-Auth-Code": "report-isolated-test"}
        self.assertNotEqual(client.get(path).status_code, 200)
        response = client.get(path + f'?view=round&round_id={batch["round_id"]}', headers=headers)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["data"]["operation_key"], "password_setup")
        self.assertEqual(response.json["data"]["view"]["round_id"], str(batch["round_id"]))
        wrong_scope = client.get(path + f'?view=round&round_id={other["round_id"]}', headers=headers)
        self.assertEqual(wrong_scope.status_code, 404)
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common.table('operation_batch_controls')} SET action_key='unsupported_future' WHERE batch_id=%s", (batch["id"],))
        unsupported = client.get(path, headers=headers)
        self.assertEqual(unsupported.status_code, 422)
        self.assertEqual(unsupported.json["error"]["code"], "report_operation_unsupported")


def test_elapsed_accepts_zero_and_rejects_naive_or_unfinished_intervals():
    stamp = datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert _duration([{"status": "success", "started_at": stamp, "completed_at": stamp}], "success", has_execution=True) == (0.0, False)
    assert _duration([{"status": "success", "started_at": stamp.replace(tzinfo=None), "completed_at": stamp}], "success", has_execution=True) == (None, True)
    assert _duration([{"status": "running", "started_at": stamp, "completed_at": stamp}], "success", has_execution=True) == (None, True)
