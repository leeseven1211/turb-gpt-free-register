"""巡检使用隔离 PostgreSQL 与模拟认证，不调用真实账号接口。"""
from __future__ import annotations

import base64
import json
import time
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from core.storage import records as record_store
from core.operations import run_log as task_run_log
from core.accounts.inspection import service as service
from core.storage.accounts import inspections as store
from core.storage.operations import store as operation
from core.operations import task_gateway
from tests.support_pg import PostgresTestCase


def token(exp):
    payload=base64.urlsafe_b64encode(json.dumps({"exp":exp}).encode()).decode().rstrip("=")
    return "header."+payload+".signature"


class InspectionTokenTests(TestCase):
    def test_exp_boundaries_and_invalid_shapes(self):
        self.assertFalse(service.token_needs_refresh(token(101),now=100))
        for value in (None,"","broken",token(100),token(99),token(True),token("101"),token(float("inf"))):
            with self.subTest(value_type=type(value).__name__):
                self.assertTrue(service.token_needs_refresh(value,now=100))

    def test_protocol_callback_runs_before_original_session_closes(self):
        from core.accounts.liveness.protocol import v2 as v2
        from tests.accounts.test_protocol_v2_liveness import _Session
        session=_Session()
        seen=[]
        def authenticated(result,current):
            self.assertIs(session,current)
            session.session.close.assert_not_called()
            seen.append(result["access_token"])
            result["plan_result"]={"ok":False,"error":"模拟套餐失败"}
            return result
        with patch.object(v2,"get_account_login_credentials",return_value=("fixture-password","")), \
             patch.object(v2,"_network_preflight_with_retry",return_value=(session,"authorize")), \
             patch.object(v2,"follow_authorize",return_value="https://auth.openai.com/log-in/password"), \
             patch.object(v2,"_password_verify",return_value={"continue_url":"https://auth.openai.com/authorize/continue?code=fixture"}), \
             patch.object(v2,"_follow_and_fetch",return_value={"accessToken":"fixture-fresh","account":{"planType":"free"}}):
            result=v2.refresh_access_token("fixture@example.test",proxy="",on_authenticated=authenticated)
        self.assertEqual(["fixture-fresh"],seen)
        self.assertTrue(result["ok"])
        self.assertFalse(result["plan_result"]["ok"])
        session.session.close.assert_called_once()


class AccountInspectionTests(PostgresTestCase):
    def setUp(self):
        operation.reset_ready()
        operation.init()
        self.dispatch=patch.object(task_gateway,"notify_dispatch")
        self.dispatch.start()
        self.addCleanup(self.dispatch.stop)
        service.register_operation_handlers()

    def account(self,n=1,**extra):
        data={"email":f"inspection-{n}@example.test","access_token":token(time.time()+3600),
              "account_status":"active","created_at":"2026-10-19T10:00:00","updated_at":"2026-10-19T10:00:00"}
        data.update(extra)
        return record_store.insert_row(record_store.ACCOUNTS,data)

    def start(self,**kwargs):
        parent_id,created=store.create_inspection(**kwargs)
        self.assertTrue(created)
        return parent_id

    def run_all(self,parent_id):
        results=[]
        for run_id,status in store.child_runs(parent_id):
            if status == "queued":
                results.append(task_gateway._execute_operation_handler(store.ITEM_TYPE,run_id))
        return results

    def summary(self):
        return store.list_inspections()["items"][0]

    def test_valid_token_only_local_and_shared_handler(self):
        self.account()
        parent=self.start(workers=1)
        with patch.object(service.live_check_service,"run_account_live_check_inline") as live:
            self.run_all(parent)
        live.assert_not_called()
        summary=self.summary()
        self.assertIn('T', summary['created_at'])
        self.assertIn('+00:00', summary['created_at'])
        self.assertEqual((1,0,"completed"),(summary["checked_count"],summary["invalid_count"],summary["status"]))

    def test_scope_snapshot_skips_deactivated_and_excludes_new_accounts(self):
        self.account(1,account_status="deactivated")
        self.account(2,archived=True)
        parent=self.start(archived="0")
        self.account(3)
        summary=self.summary()
        self.assertEqual((1,1,1),(summary["total_count"],summary["skipped_count"],summary["deactivated_skipped_count"]))
        details=store.failures(parent)
        self.assertEqual("deactivated_skipped",details["items"][0]["status"])

    def test_second_start_reuses_active_task(self):
        self.account()
        parent=self.start()
        self.assertEqual((parent,False),store.create_inspection(workers=2,archived="only"))
        self.assertEqual(1,store.list_inspections()["total"])

    def test_empty_and_idempotent_submissions(self):
        parent=self.start(idempotency_key="same")
        self.assertEqual("completed",self.summary()["status"])
        self.assertEqual((parent,False),store.create_inspection(idempotency_key="same"))

    def test_default_inspection_keeps_its_limit_when_shared_budget_is_twenty(self):
        self.account()
        with patch.object(service.account_operation_executor, "configured_workers", return_value=20):
            service.start_inspection()
        self.assertEqual(16, self.summary()["workers"])

    def test_expired_refresh_and_plan_use_original_session_and_save_at_first(self):
        account_id=self.account(access_token=token(1))
        parent=self.start()
        fresh=token(time.time()+7200)
        session=SimpleNamespace(proxy=None)
        def inline(**kwargs):
            result={"ok":True,"status":"live","access_token":fresh,"session":{"accessToken":fresh,"user":{"id":"fixture-user"}}}
            result=kwargs["on_authenticated"](result,session)
            return {"accepted":True,"result":result}
        def query(**kwargs):
            self.assertIs(session,kwargs["session"])
            self.assertEqual(fresh,record_store.get_row(record_store.ACCOUNTS,account_id)["access_token"])
            return {"ok":True,"current_plan_type":"free","http_status":200}
        with patch.object(service.live_check_service,"run_account_live_check_inline",side_effect=inline),patch.object(service.plan_check_service,"_query_account_plan",side_effect=query):
            self.run_all(parent)
        summary=self.summary()
        self.assertEqual((1,1,1),(summary["invalid_count"],summary["live_success_count"],summary["plan_success_count"]))
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT jsonb_typeof(chatgpt_session) AS kind,chatgpt_session FROM {record_store._qualified(record_store.ACCOUNTS)} WHERE id=%s",(account_id,))
            saved=cur.fetchone()
        self.assertEqual("object",saved["kind"])
        self.assertEqual(fresh,saved["chatgpt_session"]["accessToken"])

    def test_plan_failure_keeps_refresh_success_and_not_live_failure_details(self):
        account_id=self.account(access_token=token(1))
        parent=self.start()
        fresh=token(time.time()+1000)
        def inline(**kwargs):
            result=kwargs["on_authenticated"]({"ok":True,"status":"live","access_token":fresh,"session":{"accessToken":fresh}},SimpleNamespace(proxy=None))
            return {"accepted":True,"result":result}
        with patch.object(service.live_check_service,"run_account_live_check_inline",side_effect=inline),patch.object(service.plan_check_service,"_query_account_plan",side_effect=RuntimeError("模拟套餐失败")):
            self.run_all(parent)
        self.assertEqual(1,self.summary()["live_success_count"])
        self.assertEqual(1,self.summary()["plan_failed_count"])
        self.assertEqual([],store.failures(parent)["items"])
        saved=record_store.get_row(record_store.ACCOUNTS,account_id)
        self.assertEqual(fresh,saved["access_token"])
        self.assertEqual(fresh,saved["chatgpt_session"]["accessToken"])
        self.assertEqual("failed",saved["plan_check_status"])

    def test_plan_write_failure_keeps_confirmed_token_and_session(self):
        account_id=self.account(access_token=token(1))
        parent=self.start()
        fresh=token(time.time()+1000)
        def inline(**kwargs):
            result=kwargs["on_authenticated"]({"ok":True,"status":"live","access_token":fresh,"session":{"accessToken":fresh}},SimpleNamespace(proxy=None))
            return {"accepted":True,"result":result}
        with patch.object(service.live_check_service,"run_account_live_check_inline",side_effect=inline), \
             patch.object(service.plan_check_service,"_query_account_plan",return_value={"ok":True}), \
             patch.object(store,"save_plan",side_effect=RuntimeError("模拟套餐存储故障")):
            self.run_all(parent)
        summary=self.summary()
        self.assertEqual((1,0,1),(summary["live_success_count"],summary["live_failed_count"],summary["plan_failed_count"]))
        saved=record_store.get_row(record_store.ACCOUNTS,account_id)
        self.assertTrue(saved["live_check_ok"])
        self.assertEqual(fresh,saved["access_token"])
        self.assertEqual(fresh,saved["chatgpt_session"]["accessToken"])
        original=operation.get_run(store.child_runs(parent)[0][0])
        self.assertIn("套餐结果保存失败",original["result_summary"]["plan_error"])

    def test_unconfirmed_token_write_never_queries_plan_or_reports_success(self):
        original_token=token(1)
        account_id=self.account(access_token=original_token)
        parent=self.start()
        def inline(**kwargs):
            result=kwargs["on_authenticated"]({"ok":True,"status":"live","access_token":token(time.time()+1000)},SimpleNamespace(proxy=None))
            return {"accepted":True,"result":result}
        with patch.object(service.live_check_service,"run_account_live_check_inline",side_effect=inline), \
             patch.object(store,"save_liveness",return_value=False), \
             patch.object(service.plan_check_service,"_query_account_plan") as plan:
            self.run_all(parent)
        plan.assert_not_called()
        self.assertEqual(0,self.summary()["live_success_count"])
        self.assertEqual("attention_required",operation.get_run(store.child_runs(parent)[0][0])["status"])
        self.assertEqual(original_token,record_store.get_row(record_store.ACCOUNTS,account_id)["access_token"])

    def test_failure_snapshot_survives_delete_and_task_retry(self):
        account_id=self.account(access_token=token(1))
        parent=self.start()
        with patch.object(service.live_check_service,"run_account_live_check_inline",return_value={"accepted":True,"result":{"ok":False,"status":"failed","error":"本轮认证失败"}}):
            self.run_all(parent)
        original=store.failures(parent)["items"][0]
        operation.retry_runtime_task(original["task_id"])
        record_store.delete_rows_where_returning(record_store.ACCOUNTS,where="id=%s",params=(account_id,))
        later=store.failures(parent)["items"][0]
        self.assertEqual(original,later)
        self.assertEqual("本轮认证失败",later["error"])

    def test_delete_deactivated_respects_scope_and_keeps_history(self):
        self.account(1,account_status="deactivated")
        self.account(2,account_status="deactivated",archived=True)
        healthy=self.account(3)
        parent=self.start()
        self.assertEqual(1,store.delete_deactivated("0"))
        self.assertIsNotNone(record_store.get_row(record_store.ACCOUNTS,healthy))
        self.assertEqual(1,store.failures(parent)["total"])
        self.assertEqual(1,store.delete_deactivated("only"))
        self.assertEqual(0,store.delete_deactivated("all"))

    def test_deleted_before_execution_skips(self):
        account_id=self.account()
        parent=self.start()
        record_store.delete_rows_where_returning(record_store.ACCOUNTS,where="id=%s",params=(account_id,))
        self.run_all(parent)
        self.assertEqual(1,self.summary()["skipped_count"])

    def test_cancel_queued_children_uses_existing_runtime(self):
        self.account(1)
        self.account(2)
        parent=self.start()
        service.cancel_inspection(parent)
        self.assertTrue(all(status == "cancelled" for _,status in store.child_runs(parent)))

    def test_parent_cancel_targets_retried_run_and_keeps_original_failure(self):
        self.account(access_token=token(1))
        parent=self.start()
        with patch.object(service.live_check_service,"run_account_live_check_inline",return_value={"accepted":True,"result":{"ok":False,"status":"failed","error":"原始巡检失败"}}):
            self.run_all(parent)
        original=store.failures(parent)["items"][0]
        retry=operation.retry_runtime_task(original["task_id"])
        self.assertEqual([(retry["id"],"queued")],store.active_child_runs(parent))
        service.cancel_inspection(parent)
        self.assertEqual("cancelled",operation.get_run(retry["id"])["status"])
        self.assertEqual([],store.active_child_runs(parent))
        self.assertEqual(original,store.failures(parent)["items"][0])

    def test_individual_queued_child_cancel_reconciles_waiting_parent(self):
        self.account()
        parent=self.start()
        run_id=store.child_runs(parent)[0][0]
        run=operation.get_run(run_id)
        task={"id":run["task_id"],"parent_task_id":parent,"runs":[run]}
        action=task_gateway.operation_action(store.ITEM_TYPE,"cancel",source_system="native_operations")
        self.assertTrue(action(task)["ok"])
        self.assertEqual("cancelled",operation.get_run(run_id)["status"])
        self.assertIsNone(store.list_inspections()["active"])

    def test_pipeline_limit_uses_parent_lock_and_requeues(self):
        self.account(1)
        self.account(2)
        parent=self.start(workers=1)
        runs=store.child_runs(parent)
        first=operation.claim_run(runs[0][0],execution_id="first",worker_pid=1)
        self.assertTrue(store.reserve_pipeline(task_gateway.OperationHandlerContext(first,execution_id="first")))
        second=task_gateway._execute_operation_handler(store.ITEM_TYPE,runs[1][0])
        self.assertEqual("deferred",second["status"])

    def test_rejects_stale_account_and_execution_fences(self):
        account_id=self.account(access_token=token(1))
        parent=self.start()
        run_id=store.child_runs(parent)[0][0]
        claimed=operation.claim_run(run_id,execution_id="current",worker_pid=1)
        context=task_gateway.OperationHandlerContext(claimed,execution_id="current")
        with context.lease():
            record_store.patch_row(record_store.ACCOUNTS,account_id,{"access_token":"changed"})
            with self.assertRaises(task_gateway.OperationLeaseLost):
                store.save_liveness(account_id,{"ok":True,"access_token":"stale"},fence=context.execution_fence,
                    expected_email="inspection-1@example.test",expected_token=token(1))

    def test_busy_account_has_rejection_snapshot_without_new_account_lease(self):
        account_id=self.account()
        active=operation.create_runtime_task(task_type="live_check",account_id=account_id,email="inspection-1@example.test")
        parent=self.start()
        failure=store.failures(parent)["items"][0]
        self.assertEqual("rejected",failure["status"])
        self.assertEqual(1,self.summary()["live_failed_count"])
        operation.finish_run(active["run"]["id"],status="success")
        retry=operation.retry_runtime_task(failure["task_id"])
        self.assertEqual(account_id,retry["account_id"])
        self.assertEqual("success",task_gateway._execute_operation_handler(store.ITEM_TYPE,retry["id"])["status"])
        self.assertEqual("rejected",store.failures(parent)["items"][0]["status"])

    def test_parameters_are_bounded(self):
        for scope in (None,True,"bad"):
            with self.assertRaises(ValueError):
                store.create_inspection(archived=scope)
        for workers in (0,17,True,"3"):
            with self.assertRaises(ValueError):
                service.start_inspection(workers=workers)

    def test_failure_pagination_only_returns_requested_slice(self):
        for n in range(25):
            self.account(n,account_status="deactivated")
        parent=self.start()
        self.assertEqual(20,len(store.failures(parent)["items"]))
        page=store.failures(parent,limit=20,offset=20)
        self.assertEqual(25,page["total"])
        self.assertEqual(5,len(page["items"]))
        self.assertEqual(25,self.summary()["deactivated_skipped_count"])
        with operation._connect() as conn,conn.cursor() as cur:
            cur.execute(f"SELECT result_summary FROM {operation._table('operation_runs')} WHERE task_id=%s ORDER BY run_no LIMIT 1",(parent,))
            summary=cur.fetchone()["result_summary"]
        self.assertEqual(25,summary["child_count"])
        self.assertNotIn("children",summary)
        self.assertNotIn("child_tasks",summary)
        self.assertLess(len(json.dumps(summary)),500)

    def test_concurrent_start_creates_one_snapshot(self):
        self.account()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:store.create_inspection(),range(2)))
        self.assertEqual(1,sum(created for _,created in results))
        self.assertEqual(1,len({task_id for task_id,_ in results}))

    def test_start_rolls_back_if_child_creation_fails(self):
        self.account()
        original=store._task
        def failing(cur,**kwargs):
            if kwargs["kind"] == store.ITEM_TYPE:
                raise RuntimeError("模拟快照写入失败")
            return original(cur,**kwargs)
        with patch.object(store,"_task",side_effect=failing),self.assertRaises(RuntimeError):
            store.create_inspection()
        self.assertEqual(0,store.list_inspections()["total"])

    def test_http_auth_parameter_validation_and_history(self):
        from webui.app import create_app
        app=create_app(auth_code="test-inspection")
        client=app.test_client()
        headers={"X-Auth-Code":"test-inspection"}
        self.assertEqual(401,client.get("/api/accounts/inspections").status_code)
        self.assertEqual(400,client.get("/api/accounts/inspections?page=0",headers=headers).status_code)
        self.assertEqual(400,client.post("/api/accounts/inspections",headers=headers,json=[]).status_code)
        self.assertEqual(400,client.post("/api/accounts/delete-deactivated",headers=headers,json={}).status_code)
        self.assertEqual(404,client.get("/api/accounts/inspections/999999/failures",headers=headers).status_code)
        self.account(account_status="deactivated")
        with patch("webui.routes.accounts._feature_unavailable",return_value=None):
            result=client.post("/api/accounts/inspections",headers=headers,json={"workers":2,"archived":"0"})
        self.assertEqual(202,result.status_code)
        self.assertTrue(result.get_json()["created"])
        self.assertEqual(1,client.get("/api/accounts/inspections",headers=headers).get_json()["total"])
        self.assertEqual(1,client.post("/api/accounts/delete-deactivated",headers=headers,json={"archived":"0"}).get_json()["deleted_count"])
