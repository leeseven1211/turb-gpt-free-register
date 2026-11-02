# -*- coding: utf-8 -*-
"""独立支付编排；提链事实、支付订单和套餐到账分别持久化。"""
from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timedelta, timezone

from core import db
from core.operations.runtime import OperationCancelled
from core.operations import run_log
from core.payments import PaymentError, XXSYUNClient, select_payment_url
from core.payments.runtime import configuration
from core.storage.extract_link import jobs, payments

logger = logging.getLogger(__name__)
_CANCELLED_RECOVERY_LOCK = threading.Lock()


def frozen_source(data: dict | None) -> str:
    """缺少来源的历史任务始终使用平台自带支付。"""
    return "xxsyun" if isinstance(data, dict) and data.get("payment_source") == "xxsyun" else "native"


def configured_source(provider_id: str, settings) -> str:
    value = str(settings(f"EXTRACT_LINK_{provider_id.upper()}_AUTO_PAYMENT_SOURCE", "native") or "native").strip().lower()
    if value not in {"native", "xxsyun"}:
        raise ValueError("自动支付来源无效")
    return value


class ExtractionContext:
    """仅捕获提链终态，原 Run 的终态由独立支付阶段决定。"""
    def __init__(self, context):
        self._context = context
        self.result = None
        self.run = {**context.run, "data": {**context.run.get("data", {}), "mode": "extract_only", "payment_source": "native"}}

    def __getattr__(self, name):
        return getattr(self._context, name)

    @property
    def finished(self):
        return self.result is not None

    def finish(self, **kwargs):
        self.result = kwargs

    def report(self, **kwargs):
        # 外层仍是自动支付任务，提链阶段不发布“支付已跳过”的终态。
        if kwargs.get("stage") != "payment":
            return self._context.report(**kwargs)


def _saved_extraction(context, order=None):
    data = context.run.get("data") or {}
    for run_id in dict.fromkeys((context.run_id, data.get("provider_job_run_id"), (order or {}).get("origin_run_id"))):
        if run_id:
            job = jobs.get_provider_job_private(int(run_id))
            if job:
                return job
    return {}


def _effective_order(order, *, include_private=False):
    related_id = (order.get("summary") or {}).get("related_payment_order_id")
    if related_id:
        related = payments.get_payment_order(int(related_id), include_private=include_private)
        if (not related or any(related.get(key) != order.get(key)
                for key in ("account_id", "material_fingerprint", "api_base", "payment_provider"))):
            raise ValueError("关联支付订单的账号或材料身份不匹配")
        return related
    return order


def _save_state(context, service, extraction, state, order=None):
    state["payment_source"] = "xxsyun"
    summary = dict(state.get("summary") or {})
    if order:
        effective = _effective_order(order)
        summary.update(payment_order_id=order["id"], payment_provider="xxsyun",
                       payment_submitted_at=_timestamp(order.get("submitted_at")),
                       payment_remote_order_id=effective.get("remote_order_id") or "",
                       payment_submission_state=order.get("submission_state") or "reserved")
    state["summary"] = summary
    service._update_provider_job(context, str(context.run["data"].get("provider_id") or "legacy"),
                                 extraction.get("job_id") or (order or {}).get("extract_job_id"), state,
                                 extraction.get("private_data") or {})
    return state


def _timestamp(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _update(context, order, **changes):
    context.checkpoint()
    return payments.update_payment_order(order["id"], run_id=context.run_id,
                                         execution_fence=getattr(context, "execution_fence", None), **changes)


def _defer(context, state, *, reason, delay=10, wait_material=False):
    context.report(stage="payment", state="pending", message=reason)
    context.defer(delay_seconds=max(1, delay), reason=reason, data={
        "payment_source": "xxsyun", "mode": "auto_payment", "workbench_action": "sync_status",
        "provider_job_run_id": context.run_id,
        "independent_payment_new_attempt": (context.run.get("data") or {}).get("independent_payment_new_attempt") is True,
        "extract_poll_continuation": False, "independent_payment_wait_material": wait_material,
        "payment_order_id": (state.get("summary") or {}).get("payment_order_id"),
    }, stage="payment")


def _pending_payment_intent(context, order):
    intent = (context.run.get("data") or {}).get("remote_intent") or {}
    return (intent.get("action") == "independent_payment_submit"
        and intent.get("request_id") == order["idempotency_key"]
        and (intent.get("receipt_state") or intent.get("state")) not in {"confirmed", "rejected", "not_submitted"})


def _confirm_order_receipt(context, order):
    if callable(getattr(context, "remote_request_receipt", None)):
        context.remote_request_receipt(action="independent_payment_submit", request_id=order["idempotency_key"], outcome="confirmed",
            detail={"payment_order_id": order["id"], "remote_result_confirmed": True,
                    "local_business_writeback_confirmed": True, "local_readback_confirmed": True, "response_observed": True})


def _finish(context, state, *, failed=False):
    summary = state.get("summary") or {}
    context.finish(status="partial_success" if failed else "success", message=state["message"],
                   error=state["message"] if failed else None, result_summary={
                       "provider_id": context.run["data"].get("provider_id"), "mode": "auto_payment",
                       "payment_source": "xxsyun", "extraction_status": state.get("extraction_state"),
                       "payment_status": state.get("payment_state"), "plus_status": state.get("plus_status"),
                       "payment_order_id": summary.get("payment_order_id"),
                       "failure_code": summary.get("failure_code"),
                       "payment_submitted_at": summary.get("payment_submitted_at"),
                   })


def _verify_plus(context, service, extraction, state, order, runtime):
    summary = dict(order.get("summary") or {})
    if not service._bool_setting("EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED", False):
        summary["plus_verification_status"] = "not_applicable"
        order = {**order, **_update(context, order, summary=summary)}
        state.update(plus_status="not_applicable", message="独立支付已完成，套餐核验按配置关闭")
        state = _save_state(context, service, extraction, state, order)
        _finish(context, state)
        return
    anchor = order.get("submitted_at")
    current = db.get_account(int(context.account_id)) or {}
    confirmed = jobs.independent_plus_is_confirmed(current, task_created_at=anchor)
    if not confirmed:
        state.update(plus_status="pending", message="独立支付已完成，正在核验 Plus 套餐")
        _save_state(context, service, extraction, state, order)
        from core.accounts.plans import service as plan_service
        try:
            plan_service.run_account_plan_check_inline(
                account_id=int(context.account_id), email=context.email,
                access_token=str(current.get("access_token") or ""),
                trigger="extract_post_payment", operation_context=context,
            )
        except (OperationCancelled, service.account_task_store.OperationLeaseLost):
            raise
        except Exception as exc:
            summary.update(plus_failure_code="PLAN_CHECK_ERROR", plus_failure_message=run_log.redact_text(str(exc), 300))
        context.checkpoint()
        current = db.get_account(int(context.account_id)) or {}
        confirmed = jobs.independent_plus_is_confirmed(current, task_created_at=anchor)
    summary["plus_verification_status"] = "confirmed" if confirmed else "pending"
    order = _update(context, order, summary=summary)
    if confirmed:
        state.update(plus_status="confirmed", message="独立支付完成，独立套餐查询已确认 Plus 到账")
        state.setdefault("summary", {}).update(payment_confirmation_source="local_plan_check",
            payment_confirmed_plan_checked_at=_timestamp(current.get("plan_checked_at") or current.get("plan_last_success_at")))
        state = _save_state(context, service, extraction, state, order)
        _finish(context, state)
    else:
        state.update(plus_status="pending", message="独立支付已完成，独立套餐查询尚未确认 Plus 到账")
        state = _save_state(context, service, extraction, state, order)
        _defer(context, state, reason=state["message"], delay=max(60, runtime.poll_interval))


def handle(context, service):
    """已有独立订单优先恢复；尚未建单时只执行现有提链。"""
    data = context.run.get("data") or {}
    order = payments.get_task_payment_order(context.task_id, include_private=True)
    new_attempt = bool(order and order.get("payment_state") == "failed" and data.get("independent_payment_new_attempt") is True)
    extraction = _saved_extraction(context, order)
    if not order or new_attempt:
        expires = ((extraction.get("public_state") or {}).get("payment_artifact") or {}).get("expires_at")
        expired = jobs._workbench_timestamp(expires)
        material_expired = expired is not None and expired <= datetime.now(timezone.utc)
        if material_expired:
            data = {**data, "workbench_action": "create", "provider_job_run_id": None, "extract_poll_continuation": False}
            context.run = {**context.run, "data": data}
            db.claim_account_extract(int(context.account_id), trigger="independent_payment_expired_material", link_type="upi")
        if not extraction or data.get("workbench_action") == "create" or data.get("independent_payment_wait_material") is True or data.get("independent_payment_refresh_material") is True:
            proxy = ExtractionContext(context)
            service._handle_provider_operation(proxy)
            if proxy.result is None:
                return
            if proxy.result.get("status") != "success":
                context.finish(**{**proxy.result, "result_summary": {**(proxy.result.get("result_summary") or {}), "payment_source": "xxsyun"}})
                return
            extraction = _saved_extraction(context)
            context.run = {**context.run, "data": {**context.run.get("data", {}), "independent_payment_refresh_material": False}}
    with context.lease(resource_family="openai_interactive"):
        return _execute_payment(context, service, order, new_attempt, extraction)


def _execute_payment(context, service, order, new_attempt, extraction):
    data = context.run.get("data") or {}
    if not order or new_attempt:
        state = dict(extraction.get("public_state") or {})
        try:
            payment_url = select_payment_url(state.get("payment_artifact") or {},
                links=state.get("links") or (), payment_links=state.get("payment_links") or ())
        except PaymentError as exc:
            state.setdefault("summary", {}).update(failure_code=exc.code, failure_message=str(exc))
            state.update(payment_state="not_started", plus_status="not_applicable", message="提链已取得材料，等待官方 UPI instructions HTTPS 链接")
            _save_state(context, service, extraction, state)
            if state.get("extraction_state") in {"pending", "queued", "running", "unknown"} or state["summary"].get("remote_polling") is True:
                _defer(context, state, reason=state["message"], delay=10, wait_material=True)
            else:
                state["message"] = f"提链成功，{exc}；可重跑重新提链或同步原单"
                _save_state(context, service, extraction, state)
                _finish(context, state, failed=True)
            return
        runtime = configuration(service._runtime_setting)
        account = db.get_account(int(context.account_id)) or {}
        token = str(account.get("access_token") or "").strip()
        if not token:
            state.update(payment_state="failed", message="账号 AT 不可用，未提交独立支付")
            state.setdefault("summary", {}).update(failure_code="INVALID_AT")
            _save_state(context, service, extraction, state)
            _finish(context, state, failed=True)
            return
        private = extraction.get("private_data") or {}
        try:
            order = payments.reserve_payment_order(
                task_id=context.task_id, run_id=context.run_id, account_id=context.account_id,
                extract_provider_id=data.get("provider_id") or "legacy", extract_job_id=extraction.get("job_id") or "",
                material_job_id=private.get("material_job_id") or extraction.get("job_id") or "",
                payment_provider="xxsyun", material_fingerprint=hashlib.sha256(payment_url.encode()).hexdigest(),
                api_base=runtime.api_base, api_key=runtime.api_key,
                request_body={"items": [{"at": token, "link": payment_url}], "dispatch_mode": "auto"},
                concurrency=runtime.concurrency, new_attempt=new_attempt,
                execution_fence=getattr(context, "execution_fence", None),
            )
        except payments.PaymentCapacityUnavailable:
            state.update(payment_state="pending", message="独立支付共享并发已满，等待订单名额")
            _save_state(context, service, extraction, state)
            _defer(context, state, reason=state["message"], delay=runtime.poll_interval)
            return
        # 预约接口的公开结果不要求包含私有数据，发送前再读取持久请求。
        order = payments.get_payment_order(order["id"], include_private=True)
        context.run = {**context.run, "data": {**data, "independent_payment_new_attempt": False}}
    runtime = configuration()
    state = dict(extraction.get("public_state") or {})
    state.setdefault("extraction_state", "succeeded")
    state.setdefault("summary", {})
    state.update(payment_state=order["payment_state"], plus_status=state.get("plus_status") or "not_applicable")
    effective = _effective_order(order, include_private=True)
    client = XXSYUNClient(effective["api_base"], effective["private"]["api_key"], timeout=runtime.timeout)
    if order["payment_state"] == "succeeded":
        if effective.get("remote_order_id") and _pending_payment_intent(context, order):
            _confirm_order_receipt(context, order)
        _verify_plus(context, service, extraction, state, order, runtime)
        return
    if order["payment_state"] == "failed":
        state.update(message=str((order.get("summary") or {}).get("failure_message") or "独立支付订单明确失败，可重跑创建新尝试"))
        state["summary"].update({k: v for k, v in (order.get("summary") or {}).items() if k in {"failure_code", "failure_message"}})
        _save_state(context, service, extraction, state, order)
        _finish(context, state, failed=True)
        return
    next_poll = jobs._workbench_timestamp(order.get("next_poll_at"))
    if next_poll is not None and next_poll > datetime.now(timezone.utc):
        state.update(message="支付平台要求等待，尚未到原单继续请求时间")
        _save_state(context, service, extraction, state, order)
        _defer(context, state, reason=state["message"], delay=(next_poll-datetime.now(timezone.utc)).total_seconds())
        return
    submitted_request = not bool(effective.get("remote_order_id"))
    try:
        context.checkpoint()
        if effective.get("remote_order_id"):
            result = client.get_order(effective["remote_order_id"])
        else:
            if not order.get("submitted_at"):
                updated = _update(context, order, submitted_at=datetime.now(timezone.utc), submission_state="submitting")
                order = {**order, **updated}
            request_id = order["idempotency_key"]
            if not _pending_payment_intent(context, order) and callable(getattr(context, "remote_request_started", None)):
                context.remote_request_started("independent_payment_submit", request_id=request_id,
                    detail={"payment_order_id": order["id"], "payment_provider": "xxsyun"})
            result = client.submit(order["private"]["body"], request_id)
        context.checkpoint()
        summary = {**(order.get("summary") or {}), **(result.get("summary") or {})}
        summary.update(remote_status=result.get("remote_status") or "", can_cancel=result.get("can_cancel") is True,
                       failure_code=result.get("failure_code") or "", failure_message=result.get("failure_message") or "")
        changes = {"submission_state": "submitted", "payment_state": result["state"], "summary": summary,
                   "next_poll_at": datetime.now(timezone.utc) + timedelta(seconds=runtime.poll_interval)}
        if not (order.get("summary") or {}).get("related_payment_order_id"):
            changes["remote_order_id"] = result.get("order_id") or order.get("remote_order_id")
        try:
            updated = _update(context, order, **changes)
        except payments.PaymentOrderIdentityConflict as exc:
            canonical = exc.existing_order
            matched = canonical and order.get("account_id") is not None and all(canonical.get(key) == order.get(key)
                for key in ("account_id", "material_fingerprint", "api_base", "payment_provider"))
            if matched:
                summary["related_payment_order_id"] = canonical["id"]
                updated = _update(context, order, **{key: value for key, value in changes.items() if key != "remote_order_id"})
            else:
                summary.update(failure_code="LOCAL_PAYMENT_IDENTITY_CONFLICT", error_category="LOCAL_PAYMENT_IDENTITY_CONFLICT",
                    failure_message="本地支付订单身份冲突：平台原单已属于其他账号或材料，付款结果未改写；可重跑重新提链")
                updated = _update(context, order, submission_state="rejected", payment_state="failed", summary=summary)
        order = {**order, **updated}
        summary = dict(order.get("summary") or {})
        if result.get("order_id") and (submitted_request or _pending_payment_intent(context, order)):
            _confirm_order_receipt(context, order)
    except PaymentError as exc:
        summary = {**(order.get("summary") or {}), **getattr(exc, "summary", {}), "failure_code": exc.code, "failure_message": run_log.redact_text(str(exc), 300)}
        # 原单查询失败不能抹掉已有订单身份，更不能重新提交另一单。
        awaiting = bool(effective.get("remote_order_id") or exc.retryable or exc.submission_unknown)
        updated = _update(context, order, summary=summary,
            submission_state=order.get("submission_state") if effective.get("remote_order_id") else "unknown" if exc.submission_unknown else "reserved" if exc.retryable else "rejected",
            payment_state="unknown" if exc.submission_unknown else "pending" if awaiting else "failed",
            next_poll_at=datetime.now(timezone.utc) + timedelta(seconds=max(runtime.poll_interval, exc.retry_after_seconds)))
        order = {**order, **updated}
        summary = dict(order.get("summary") or {})
        if submitted_request and not exc.submission_unknown and callable(getattr(context, "remote_request_receipt", None)):
            context.remote_request_receipt(action="independent_payment_submit", request_id=order["idempotency_key"],
                outcome="rejected", detail={"response_observed": True, "remote_result_confirmed": False})
        state["summary"].update(failure_code=exc.code, failure_message=summary["failure_message"])
        state.update(payment_state=order["payment_state"], message=f"独立支付 {exc.code}：{summary['failure_message']}")
        _save_state(context, service, extraction, state, order)
        if awaiting:
            _defer(context, state, reason=state["message"], delay=max(runtime.poll_interval, exc.retry_after_seconds))
        else:
            _finish(context, state, failed=True)
        return
    state.update(payment_state=order["payment_state"])
    if order["payment_state"] == "succeeded":
        _verify_plus(context, service, extraction, state, order, runtime)
    elif order["payment_state"] == "failed":
        state["summary"].update(failure_code=summary.get("failure_code"), failure_message=summary.get("failure_message"))
        state.update(message=summary.get("failure_message") or "独立支付订单明确失败，可重跑创建新尝试")
        _save_state(context, service, extraction, state, order)
        _finish(context, state, failed=True)
    else:
        state.update(message="独立支付订单已保存，等待原单支付结果")
        _save_state(context, service, extraction, state, order)
        _defer(context, state, reason=state["message"], delay=runtime.poll_interval)



def perform_action(task, *, action, latest_run_id, prior_job, service):
    """整批重跑由保存的阶段决定续查、新尝试或重新提链。"""
    from core.storage.operations import store as operation

    if action not in {"retry", "sync_status", "auto_payment"}:
        return {"accepted": False}
    data = task.get("data") or {}
    order = payments.get_task_payment_order(int(task["id"]))
    state = (prior_job or {}).get("public_state") or {}
    failed_order = bool(order and order.get("payment_state") == "failed")
    failure_code = str(((order or {}).get("summary") or {}).get("failure_code") or "").upper()
    reextract = action == "retry" and (
        (failed_order and failure_code in {"LINK_EXPIRED", "LINK_INVALID", "LOCAL_PAYMENT_IDENTITY_CONFLICT"})
        or (not order and (not service._provider_has_reference(prior_job) or state.get("extraction_state") == "failed"
            or (state.get("summary") or {}).get("failure_code") in {"MATERIAL_UNSUPPORTED", "MATERIAL_MISSING"}))
    )
    if not order and not prior_job and not reextract:
        return {"accepted": False}
    if reextract and not service._provider_mode_enabled(data.get("provider_id"), "auto_payment", "xxsyun"):
        return {"accepted": False}
    run_data = {"provider_id": data.get("provider_id"), "mode": "auto_payment", "payment_source": "xxsyun",
        "link_type": data.get("link_type") or "upi", "options": data.get("options") or {},
        "workbench_action": "create" if reextract else "sync_status",
        "provider_job_run_id": None if reextract else latest_run_id,
        "independent_payment_new_attempt": failed_order and action == "retry",
        "independent_payment_refresh_material": not order and not reextract and action == "sync_status",
        "extract_poll_continuation": False,
        "allow_no_promotion": data.get("allow_no_promotion") is True}
    claimed = False
    if reextract:
        claimed = db.claim_account_extract(int(task.get("account_id") or 0),
            trigger="extract_workbench_retry", link_type=run_data["link_type"])
        if not claimed:
            return {"accepted": False}
    try:
        submitted = operation.retry_runtime_task(int(task["id"]), trigger=f"extract_workbench_{action}", data=run_data)
    except Exception:
        if claimed:
            db.update_account_extract(int(task["account_id"]), {"status": "failed", "ok": False,
                "message": "提链重跑未能入队", "error": "提链重跑未能入队"})
        raise
    run = (submitted.get("run") or submitted) if isinstance(submitted, dict) else {}
    if not run.get("id"):
        return {"accepted": False}
    service.account_task_store.notify_dispatch()
    return {"accepted": True, "task_id": int(task["id"]), "run_id": int(run["id"])}


def resume_orders(service):
    """按独立订单恢复，覆盖所有提链来源，并尊重本地取消。"""
    from core.storage.operations import store as operation

    resumed = 0
    cancelled_orders = []
    for order in payments.list_recoverable_payment_orders():
        cancelled = (order.get("task_status") in {"cancelled", "stopped", "paused"}
            or order.get("latest_run_status") in {"cancelled", "stopped"}
            or order.get("batch_status") in {"cancelled", "stopped", "paused"}
            or order.get("cancel_requested_at") is not None)
        if cancelled:
            cancelled_orders.append(order)
            continue
        if order.get("latest_run_status") not in {"attention_required", "interrupted", "partial_success", "success"}:
            continue
        task = operation.get_task(int(order["task_id"]), include_events=False)
        if not task or task.get("status") in {"cancelled", "stopped", "paused"}:
            continue
        source_data = task.get("data") or {}
        if frozen_source(source_data) != "xxsyun":
            continue
        try:
            queued = operation.retry_runtime_task(int(order["task_id"]), trigger="independent_payment_restart_sync", data={
                "provider_id": order["extract_provider_id"], "mode": "auto_payment", "payment_source": "xxsyun",
                "workbench_action": "sync_status", "provider_job_run_id": int(order["origin_run_id"]),
                "extract_poll_continuation": False, "independent_payment_new_attempt": False,
            })
        except Exception:
            continue
        resumed += bool(queued)
    _schedule_cancelled_recovery(cancelled_orders)
    return resumed



def _reconcile_cancelled_order(order):
    """本地取消不发送支付请求；仅回收已知原单的终态名额。"""
    if order.get("payment_state") in {"succeeded", "failed"}:
        return
    next_poll = jobs._workbench_timestamp(order.get("next_poll_at"))
    if next_poll is not None and next_poll > datetime.now(timezone.utc):
        return
    summary = dict(order.get("summary") or {})
    changes = {}
    effective = _effective_order(order)
    if not effective.get("remote_order_id"):
        if order.get("submission_state") == "reserved" and not order.get("submitted_at"):
            summary.update(failure_code="LOCAL_CANCELLED_BEFORE_SUBMIT", failure_message="本地已取消，独立支付尚未提交")
            changes.update(submission_state="rejected", payment_state="failed")
        else:
            summary.update(failure_code="SUBMISSION_UNKNOWN", failure_message="提交结果未知，重跑将按原幂等意图恢复")
            changes.update(submission_state="unknown", payment_state="unknown")
    else:
        saved = payments.get_payment_order(effective["id"], include_private=True)
        runtime = configuration()
        try:
            result = XXSYUNClient(saved["api_base"], saved["private"]["api_key"], timeout=runtime.timeout).get_order(saved["remote_order_id"])
        except PaymentError as exc:
            summary.update({**getattr(exc, "summary", {}), "failure_code": exc.code,
                            "failure_message": str(exc), "retry_after_seconds": exc.retry_after_seconds})
            changes.update(next_poll_at=datetime.now(timezone.utc) + timedelta(seconds=max(runtime.poll_interval, exc.retry_after_seconds)))
        else:
            summary.update({**(result.get("summary") or {}), "remote_status": result.get("remote_status") or "",
                            "can_cancel": result.get("can_cancel") is True,
                            "failure_code": result.get("failure_code") or "", "failure_message": result.get("failure_message") or ""})
            changes.update(payment_state=result["state"],
                           next_poll_at=datetime.now(timezone.utc) + timedelta(seconds=runtime.poll_interval))
    payments.update_payment_order(order["id"], run_id=order["latest_run_id"], summary=summary, **changes)


def _schedule_cancelled_recovery(orders):
    if not orders or not _CANCELLED_RECOVERY_LOCK.acquire(blocking=False):
        return

    def recover():
        try:
            for order in orders:
                try:
                    _reconcile_cancelled_order(order)
                except Exception as exc:
                    logger.warning("[独立支付] 本地已取消订单的原单查询未完成：payment_order_id=%s error_type=%s",
                                   order["id"], type(exc).__name__)
        finally:
            _CANCELLED_RECOVERY_LOCK.release()

    threading.Thread(target=recover, name="independent-payment-cancelled-recovery", daemon=True).start()
