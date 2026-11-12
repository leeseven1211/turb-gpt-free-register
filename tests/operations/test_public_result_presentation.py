"""公开失败状态、历史结果筛选与内部执行事实隔离的回归。"""

import logging
from unittest import TestCase
from unittest.mock import patch

from flask import Flask

from core import account_task_store
from core.operations.presentation import public_progress_snapshot, public_result_status, public_result_status_sql
from core.storage.operations import store
from tests.support_pg import PostgresTestCase
from webui import runtime
from webui.routes import operations


def _client():
    app = Flask("public-result-tests")
    context = runtime.WebUIContext(app, logging.getLogger("public-result-tests"))
    app.register_blueprint(operations.create_operations_blueprint(context))
    return app.test_client()


class PublicResultRoutesTests(TestCase):
    def test_progress_projection_converts_nested_results_and_preserves_source(self):
        raw = {'outcome': {'status': 'attention_required', 'state': 'pending'},
               'routes': [{'status': 'request_unknown'}],
               'main_steps': [{'state': 'pending', 'display_status': 'unconfirmed'}]}
        result = public_progress_snapshot(raw)
        self.assertEqual('failed', result['outcome']['status'])
        self.assertEqual('failed', result['outcome']['state'])
        self.assertEqual('failed', result['routes'][0]['status'])
        self.assertEqual('failed', result['main_steps'][0]['display_status'])
        self.assertEqual('failed', result['main_steps'][0]['state'])
        self.assertEqual('attention_required', raw['outcome']['status'])
        self.assertEqual('pending', raw['main_steps'][0]['state'])

    def test_progress_projection_keeps_remote_evidence_and_http_status(self):
        raw = {'status': 'request_unknown', 'result_summary': {'auth': {'status': 'unknown'},
               'outcome': 'request_unknown', 'reconcile_required': True},
               'remote_intent': {'state': 'unknown', 'receipt_state': 'unknown'},
               'diagnostics': {'status': 502, 'evidence': 'unconfirmed'}}
        result = public_progress_snapshot(raw)
        self.assertEqual('failed', result['status'])
        self.assertEqual(raw['result_summary'], result['result_summary'])
        self.assertEqual(raw['remote_intent'], result['remote_intent'])
        self.assertEqual(502, result['diagnostics']['status'])
        self.assertEqual('unconfirmed', result['diagnostics']['evidence'])

    def test_detail_exposes_failure_without_mutating_retry_facts(self):
        raw = {"id": 41, "task_type": "registration", "source_system": "registration_chains",
               "status": "request_unknown", "target_status": "attention_required",
               "result_summary": {"cause_code": "email_otp_failed"},
               "runs": [{"id": 51, "status": "attention_required", "result_summary": {
                   "cause_code": "email_otp_failed", "requested_status": "partial_success"}}]}
        with patch.object(operations.operation_task_store, "get_task", return_value=raw), \
                patch.object(operations.svc, "attach_registration_resume_retry_info") as retry_info:
            response = _client().get("/api/operations/41?include_events=0")
        self.assertEqual(200, response.status_code)
        task = response.get_json()["task"]
        self.assertEqual("failed", task["status"])
        self.assertEqual("failed", task["target_status"])
        self.assertEqual("request_unknown", task["internal_status"])
        self.assertEqual("partial_success", task["runs"][0]["status"])
        self.assertEqual("request_unknown", raw["status"])
        self.assertEqual("attention_required", raw["runs"][0]["status"])
        retry_info.assert_called_once_with([raw])

    def test_list_requests_public_sql_and_checks_registration_actions_with_raw_state(self):
        row = {"id": 41, "task_type": "registration", "source_system": "registration_chains",
               "status": "failed", "internal_status": "attention_required",
               "target_status": "failed", "internal_target_status": "request_unknown"}
        observed = []

        def attach(tasks):
            observed.append((tasks[0]["status"], tasks[0]["target_status"]))

        with patch.object(operations.operation_task_store, "list_tasks", return_value={
                "ok": True, "items": [row], "total": 1}) as listing, \
                patch.object(operations.svc, "attach_registration_resume_retry_info", side_effect=attach):
            response = _client().get("/api/operations?status=failed&include_batches=0&include_facets=0")
        self.assertEqual(200, response.status_code)
        self.assertTrue(listing.call_args.kwargs["public_status"])
        self.assertEqual([("attention_required", "request_unknown")], observed)
        self.assertEqual("failed", response.get_json()["items"][0]["status"])


class PublicResultStoreTests(PostgresTestCase):
    def setUp(self):
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.schema_patch.start()
        account_task_store.init()
        store.reset_ready()
        store.init()

    def tearDown(self):
        self.schema_patch.stop()

    def _task(self, *, partial=False, task_type="token_refresh"):
        task = store.create_runtime_task(task_type=task_type, account_id=None,
                                         email="public-result@example.test", trigger="test")
        summary = {"cause_code": "email_otp_failed", "outcome": "request_unknown"}
        if partial:
            summary["requested_status"] = "partial_success"
        store.finish_run(task["run"]["id"], status="attention_required",
                         result_summary=summary, error="邮箱取码超时")
        return task

    def test_filter_facets_detail_and_progress_share_public_result_and_keep_raw_storage(self):
        failure = self._task(task_type="registration")
        partial = self._task(partial=True)
        listed = store.list_tasks(public_status=True, status="failed", target_status="failed", page_size=1)
        self.assertEqual(1, listed["total"])
        self.assertEqual(failure["id"], listed["items"][0]["id"])
        self.assertEqual("failed", listed["items"][0]["status"])
        self.assertEqual("attention_required", listed["items"][0]["internal_status"])
        self.assertEqual([{"value": "failed", "count": 1}], listed["facets"]["status"])
        partial_list = store.list_tasks(public_status=True, status="partial_success")
        self.assertEqual([partial["id"]], [row["id"] for row in partial_list["items"]])
        self.assertEqual({"failed", "partial_success"},
                         {item["value"] for item in store.list_tasks(public_status=True)["facets"]["status"]})
        self.assertEqual(2, store.list_tasks(status="attention_required")["total"])
        self.assertEqual("attention_required", store.get_task(failure["id"])["status"])
        self.assertEqual("attention_required", store.get_run(failure["run"]["id"])["status"])
        progress = store.get_run_progress(failure["id"], failure["run"]["id"], public_status=True)
        self.assertEqual("failed", progress["outcome"]["status"])
        self.assertEqual("failed", progress["outcome"]["state"])
        self.assertEqual("attention_required", progress["outcome"]["internal_status"])
        self.assertEqual("attention_required", store.get_run_progress(
            failure["id"], failure["run"]["id"])["outcome"]["status"])

    def test_active_retry_stays_active_in_failed_filters(self):
        task = self._task()
        store.retry_runtime_task(task["id"])
        self.assertEqual(0, store.list_tasks(public_status=True, status="failed")["total"])
        self.assertEqual("queued", store.list_tasks(public_status=True)["items"][0]["status"])

    def test_legacy_account_api_filters_public_failure_without_rewriting_legacy_task(self):
        task_id = account_task_store.create_task(task_type='live_check', account_id=None,
                                                 email='legacy-public@example.test', trigger='test')
        with account_task_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {account_task_store._table('account_action_tasks')} SET status='request_unknown', "
                        "result_summary=%s::jsonb,error='邮箱取码超时' WHERE id=%s",
                        (store._json({'cause_code': 'email_otp_failed'}), task_id))
        result = account_task_store.list_tasks(status='failed', public_status=True)
        self.assertEqual(1, result['total'])
        self.assertEqual('failed', result['items'][0]['status'])
        self.assertEqual('request_unknown', account_task_store.get_task(task_id)['status'])
        with patch('core.accounts.token_refresh.settings', return_value={}), \
                patch.object(operations.codex_token_refresh_service, 'settings', return_value={}):
            response = _client().get('/api/account-tasks?status=failed')
            detail = _client().get(f'/api/account-tasks/{task_id}')
        self.assertEqual('failed', response.get_json()['items'][0]['status'])
        self.assertEqual('failed', detail.get_json()['task']['status'])
        self.assertEqual('request_unknown', account_task_store.get_task(task_id)['status'])

    def test_sql_projection_matches_python_for_legacy_terminal_values(self):
        values = ["attention_required", "request_unknown", "manual_reconcile", "unknown", "unconfirmed",
                  "password_confirmation_pending", "credential_pending_confirmation", "failed", "success", "queued"]
        with store._connect() as conn, conn.cursor() as cur:
            for partial in (False, True):
                summary = {"requested_status": "partial_success"} if partial else {}
                for value in values:
                    cur.execute(f"SELECT {public_result_status_sql('%s', '%s::jsonb')} AS status",
                                (value, store._json(summary), value))
                    self.assertEqual(public_result_status(value, summary), cur.fetchone()["status"])
