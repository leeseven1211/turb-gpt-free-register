"""账号巡检：本地 JWT 检查、按需刷新及同会话套餐查询。"""
from __future__ import annotations

import math
import time
from config.schema import get_config_snapshot
from core import account_operation_executor, live_check_service, plan_check_service, task_run_log
from core.storage import accounts, account_inspections as store
from core.operations import task_gateway
from core.chatgpt_plan import normalize_token, decode_jwt_payload_unverified
from core.operation_runtime import OperationCancelled

CONFIG_ALLOWLIST={**live_check_service.LIVE_CONFIG_ALLOWLIST,**plan_check_service.PLAN_CONFIG_ALLOWLIST}


def token_needs_refresh(token, now=None):
    """只读 JWT exp；格式错误、缺失、过期均需要刷新。"""
    if not isinstance(token,str):
        return True
    parts=normalize_token(token).split('.')
    if len(parts) != 3 or not all(parts):
        return True
    payload=decode_jwt_payload_unverified(normalize_token(token))
    exp=payload.get('exp') if isinstance(payload,dict) else None
    return isinstance(exp,bool) or not isinstance(exp,(int,float)) or not math.isfinite(exp) or exp <= (time.time() if now is None else now)


def _handle(context):
    if not store.reserve_pipeline(context):
        raise task_gateway.OperationLeaseUnavailable("本轮巡检并发已满，稍后继续")
    context.checkpoint()
    account=accounts.get_account(context.account_id)
    if account is None:
        return task_gateway.OperationResult.success({"inspection_outcome":"deleted_skipped","checked":False},message="账号已删除，本次跳过")
    if accounts.account_is_deactivated(account) or str(account.get("live_check_status") or "").strip().lower() == "deactivated":
        return task_gateway.OperationResult.success({"inspection_outcome":"deactivated_skipped","checked":False,"error":"账号已标记为已废，本次跳过"},message="已废账号跳过")
    invalid=token_needs_refresh(account.get("access_token"))
    if not invalid:
        return task_gateway.OperationResult.success({"inspection_outcome":"valid","checked":True,"invalid":False},message="AT 本地有效，无需网络请求")
    summary={"checked":True,"invalid":True}
    with context.lease(resource_family=context.resource_family):
        snapshot={"email":account["email"],"token":str(account.get("access_token") or "")}

        def write_result(result):
            saved=store.save_liveness(context.account_id,result,fence=context.execution_fence,
                expected_email=snapshot["email"],expected_token=snapshot["token"])
            if not saved:
                raise task_gateway.OperationLeaseLost("新 AT 未确认持久化，停止后续套餐查询")
            if saved and result.get("ok") and result.get("access_token"):
                snapshot["token"]=str(result["access_token"])
            return saved

        def authenticated(result,session):
            context.checkpoint()
            write_result(result)
            try:
                context.report(stage="plan_check",state="running",message="复用本次登录会话查询套餐")
                plan=plan_check_service._query_account_plan(email=snapshot["email"],access_token=snapshot["token"],
                    trigger="inspection",proxy=getattr(session,"proxy",None),timezone_offset_min="-",session=session,
                    config_snapshot=context.config_snapshot)
                context.checkpoint()
            except (task_gateway.OperationLeaseLost,OperationCancelled):
                raise
            except Exception as exc:
                plan={"ok":False,"error":task_run_log.redact_text(str(exc),500)}
            try:
                if not store.save_plan(context.account_id,plan,fence=context.execution_fence,
                    expected_email=snapshot["email"],expected_token=snapshot["token"]):
                    plan={"ok":False,"error":"账号套餐结果未能保存"}
            except (task_gateway.OperationLeaseLost,OperationCancelled):
                raise
            except Exception as exc:
                # AT 已确认落库；套餐存储故障不能改写成认证失败。
                plan={"ok":False,"error":"套餐结果保存失败："+task_run_log.redact_text(str(exc),500)}
            result["plan_result"]={"ok":bool(plan.get("ok")),"error":task_run_log.redact_text(plan.get("error") or "",500)}
            return result

        queued=live_check_service.run_account_live_check_inline(account_id=context.account_id,email=account["email"],
            trigger="inspection",force_refresh=True,operation_context=context,config_snapshot=context.config_snapshot,
            on_authenticated=authenticated,result_writer=write_result,allow_missing_token=True)
        result=queued.get("result") or {"ok":False,"status":"rejected","error":queued.get("error") or "查活未能入队"}
        summary.update(live_ok=bool(result.get("ok")),inspection_outcome="refreshed" if result.get("ok") else result.get("status") or "failed")
        if result.get("ok"):
            plan=result.get("plan_result") or {"ok":False,"error":"当前登录驱动未提供可复用的协议会话"}
            summary["plan_ok"]=bool(plan.get("ok"))
            if not plan.get("ok"):
                summary["plan_error"]=task_run_log.redact_text(plan.get("error") or "套餐查询失败",1000)
        else:
            summary["error"]=task_run_log.redact_text(result.get("error") or "查活失败",2000)
        if result.get("reconcile_required"):
            return task_gateway.OperationResult.request_unknown(summary["error"],summary)
        if result.get("cancelled"):
            return task_gateway.OperationResult("cancelled",summary,"巡检已取消",summary.get("error"))
        return task_gateway.OperationResult("success" if result.get("ok") else "failed",summary,
            "AT 刷新完成" if result.get("ok") else "AT 刷新失败",summary.get("error"))


def cancel_inspection(inspection_id):
    for run_id,status in store.active_child_runs(int(inspection_id)):
        if status in store.ACTIVE:
            task_gateway._operation().request_run_cancel(run_id,reason="用户停止本次账号巡检")
    task_gateway._operation().reconcile_parent_task(int(inspection_id))
    task_gateway.notify_dispatch()
    return {"ok":True,"task_id":int(inspection_id)}


def _cancel_item(task):
    result=task_gateway.default_operation_cancel(task)
    if result.get("ok") and task.get("parent_task_id"):
        task_gateway._operation().reconcile_parent_task(int(task["parent_task_id"]))
    return result


def _retry_parent(task):
    data=task.get("data") or {}
    return start_inspection(workers=int(data.get("workers",3)),archived=data.get("archived","0"))


def register_operation_handlers():
    task_gateway.register_operation_handler(store.ITEM_TYPE,_handle,config_allowlist=CONFIG_ALLOWLIST,
        cancel_handler=_cancel_item)
    task_gateway.register_operation_actions(store.PARENT_TYPE,retry_handler=_retry_parent,
        cancel_handler=lambda task:cancel_inspection(task["id"]),terminate_handler=lambda task:cancel_inspection(task["id"]))
    return True


def start_inspection(*,workers=None,archived="0",idempotency_key=None):
    workers=account_operation_executor.configured_workers() if workers is None else workers
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("巡检并发必须为 1–16 的整数，实际并发同时受账号操作共享预算限制")
    store.validate_scope(archived)
    register_operation_handlers()
    config=task_gateway.normalize_config_snapshot(get_config_snapshot(),allowlist=CONFIG_ALLOWLIST)
    task_id,created=store.create_inspection(archived=archived,workers=workers,config_snapshot=config,idempotency_key=idempotency_key)
    if created:
        task_gateway.notify_dispatch()
    return {"id":task_id,"task_id":task_id,"created":created}


register_operation_handlers()
