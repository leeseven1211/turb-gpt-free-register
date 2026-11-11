# -*- coding: utf-8 -*-
"""提链工作台的只读查询与展示投影。

依赖现有 db 与存储查询入口；不调用服务层或任务执行入口。
"""
from __future__ import annotations

import re

from core import db
from core.operations import run_log as task_run_log

HUANGUANG_QUOTA_STAGES = {
    "quota_extraction_exhausted": "提链 CDK 次数已用完，等待补充额度",
    "quota_payment_exhausted": "支付扫码 CDK 次数已用完，等待补充额度",
    "quota_extraction_disabled": "提链 CDK 已停用，等待更新配置",
    "quota_payment_disabled": "支付扫码 CDK 已停用，等待更新配置",
    "quota_unavailable": "CDK 额度暂无法确认，等待重新查询",
    "quota_local_reserved": "CDK 可用次数已分配给正在提交的任务，等待额度释放",
}


def provider_status_label(status: str) -> str:
    return {
        "succeeded": "success",
        "success": "success",
        "queued": "queued",
        "running": "running",
        "failed": "failed",
        "pending": "pending",
        "unknown": "unknown",
        "not_started": "not_started",
    }.get(str(status or "").lower(), "unknown")


def generic_workbench_failure(value: str) -> bool:
    text = value.strip().rstrip("。.!！:： ").lower()
    if text.startswith("平台提链失败：") or text.startswith("平台提链失败:"):
        text = text[7:].strip()
    return text in {
        "", "任务处理失败", "任务失败", "处理失败", "提链失败", "平台提链失败", "请求失败",
        "error", "failed", "task failed", "task processing failed", "unknown error",
    }


def workbench_failure_detail(summary: dict) -> str:
    # 旧记录的通用错误仅用已保存的明确失败原因补全，不触发远端查询或业务重跑。
    for key in ("failure_message", "current_step"):
        detail = summary.get(key)
        if not isinstance(detail, str) or generic_workbench_failure(detail):
            continue
        detail = detail.strip()
        if detail.startswith(("正在", "等待", "排队", "准备")):
            continue
        if key == "current_step" and not re.search(
            r"失败|错误|异常|无效|不足|已用完|用尽|耗尽|未执行|取消|拒绝|超时|不可用|无法|"
            r"\b(?:error|failed|invalid|exhausted|insufficient|timeout|denied|cancelled|canceled)\b",
            detail, re.IGNORECASE,
        ):
            continue
        detail = task_run_log.redact_text(detail, len(detail))
        detail = re.sub(r"(?i)\b(?:https?|socks5h?)://[^\s<>]+", "[REDACTED_URL]", detail)
        detail = re.sub(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", detail)
        return " ".join(detail.split())[:300]
    return ""


_RECONCILE_HALT_LABELS = {
    "remote_not_found": "原单连续查询不到，已停止自动续查",
    "query_failures": "连续查询失败达到上限，已停止自动续查",
    "timeout": "自动续查超过总时限，已停止",
    "no_progress": "长时间没有有效进展，已停止自动续查",
}

_PAYMENT_PROCESSING_HINTS = (
    "submitting", "awaiting_worker", "claimed", "verifying", "activation_pending",
    "processing", "checking", "提交扫码", "核验中", "待接单", "扫码中",
)

_PLUS_CONFIRMED_RAW = {"verified", "confirmed"}
_PLUS_NOT_CONFIRMED_RAW = {"inferred", "not_confirmed"}
_PLUS_UNAVAILABLE_RAW = {"check_failed", "not_available", "verification_unavailable"}
_PLUS_CHECKING_RAW = {"checking", "waiting_for_payment"}


def _payment_phase(payment: str, *, mode: str, extraction: str, summary: dict,
                   has_payment_entry: bool) -> str:
    """把平台各自的支付说法收敛成 7 个阶段，不再把待支付和结果未知混成一堆。"""
    if mode == "extract_only" or payment == "unpaid":
        return "not_started"
    if payment == "paid":
        return "paid"
    raw = " ".join(str(summary.get(key) or "") for key in (
        "payment_check_status", "automatic_payment_status", "xxsyun_status",
        "payment_status", "current_step",
    )).lower()
    if payment == "failed":
        return "expired" if ("expired" in raw or "过期" in raw) else "failed"
    if payment == "request_unknown":
        return "unknown"
    if extraction != "success" and not has_payment_entry:
        return "not_started"
    if any(token in raw for token in _PAYMENT_PROCESSING_HINTS) or summary.get("payment_order_id") or summary.get("payment_submitted_at"):
        return "processing"
    return "awaiting_payment"


def _plus_state(plus: str, summary: dict, *, payment_phase: str) -> str:
    """三家平台的 Plus 说法统一成 5 态，推断值不算确认。"""
    raw = str(summary.get("platform_plus_status") or summary.get("plus_verification_status") or "").strip().lower()
    if plus == "confirmed" or raw in _PLUS_CONFIRMED_RAW:
        return "confirmed"
    if plus in {"failed", "not_confirmed"} or raw in _PLUS_NOT_CONFIRMED_RAW:
        return "not_confirmed"
    if raw in _PLUS_UNAVAILABLE_RAW:
        return "unavailable"
    if raw in _PLUS_CHECKING_RAW or plus in {"pending", "queued"}:
        return "checking"
    if payment_phase == "paid":
        return "checking"
    return "unknown"


def _remote_raw(summary: dict) -> dict:
    """保留平台原话，界面只读不改，排查时才有证据。"""
    raw = {}
    for key, label in (
        ("remote_status", "提链状态"),
        ("xxsyun_status", "扫码台"),
        ("automatic_payment_status", "自动支付"),
        ("payment_check_status", "支付检查"),
        ("platform_plus_status", "Plus（幻光）"),
        ("plus_verification_status", "Plus（流光）"),
    ):
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            raw[label] = value.strip()[:60]
    return raw


def workbench_task_item(row: dict, *, account: dict | None = None) -> dict:
    data = row.get("task_data") if isinstance(row.get("task_data"), dict) else {}
    state = row.get("public_state") if isinstance(row.get("public_state"), dict) else {}
    summary = state.get("summary") if isinstance(state.get("summary"), dict) else {}
    run_summary = row.get("result_summary") if isinstance(row.get("result_summary"), dict) else {}
    provider_id = str(data.get("provider_id") or row.get("job_provider_id") or "legacy")
    mode = str(data.get("mode") or "extract_only")
    payment_source = "xxsyun" if data.get("payment_source") == "xxsyun" else "native"
    task_status = str(row.get("run_status") or row.get("task_status") or "queued").lower()
    if task_status == "attention_required":
        task_status = "request_unknown"
    extraction_value = state.get("extraction_state") or run_summary.get("extraction_status")
    if provider_id == "huanguang" and summary.get("extraction_ever_succeeded") is True:
        extraction_value = "succeeded"
    if not extraction_value and provider_id == "legacy":
        if task_status == "success" and (run_summary.get("has_link") or run_summary.get("remote_job_id")):
            extraction_value = "success"
        elif task_status in {"failed", "request_unknown", "attention_required", "cancelled", "stopped"}:
            extraction_value = "failed"
    extraction = str(extraction_value or "pending").lower()
    extraction = provider_status_label(extraction)
    payment = str(state.get("payment_state") or run_summary.get("payment_status") or "not_started").lower()
    if mode == "extract_only":
        payment = "not_started"
    payment = {
        "succeeded": "paid", "success": "paid", "paid": "paid",
        "not_started": "unpaid", "failed": "failed",
        "pending": "pending_payment", "unknown": "request_unknown",
    }.get(payment, "pending_payment")
    preflight = str(state.get("preflight_status") or run_summary.get("preflight_status") or "pending").lower()
    plus = str(state.get("plus_status") or run_summary.get("plus_status") or "unknown").lower()
    if mode in {"auto_payment", "manual_payment"} and extraction == "success":
        from core.storage.extract_link.jobs import independent_plus_is_confirmed
        anchor = summary.get("payment_submitted_at") if payment_source == "xxsyun" else row.get("task_created_at")
        if independent_plus_is_confirmed(account, task_created_at=anchor):
            plus = "confirmed"
    progress = {
        "label": str(summary.get("current_step") or row.get("progress_stage") or row.get("current_stage") or ""),
        "percent": summary.get("percent"),
    }
    error = str(row.get("error_message") or "")
    legacy_projection_matches = bool(
        provider_id == "legacy"
        and run_summary.get("remote_job_id")
        and account
        and str(account.get("extract_link_job_id") or "") == str(run_summary.get("remote_job_id") or "")
    )
    legacy_has_link = bool(legacy_projection_matches and account.get("extract_link_long_url"))
    from core.extract_link.contracts import safe_payment_artifact
    artifact = safe_payment_artifact(state.get("payment_artifact"))
    has_payment_entry = bool(
        state.get("payment_links") or state.get("links") or legacy_has_link
        or any(artifact.get(key) for key in (
            "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
        ))
    )
    message = str(state.get("message") or run_summary.get("message") or error or "")
    quota_stage = str(row.get("progress_stage") or row.get("current_stage") or "")
    if provider_id == "huanguang" and task_status == "queued" and quota_stage in HUANGUANG_QUOTA_STAGES:
        message = HUANGUANG_QUOTA_STAGES[quota_stage]
        progress["label"] = message
        progress["percent"] = None
        error = ""
    elif provider_id == "huanguang" and extraction == "failed" and generic_workbench_failure(error):
        detail = workbench_failure_detail(summary) if generic_workbench_failure(message) else (
            workbench_failure_detail({"current_step": message})
        )
        if detail:
            error = detail if detail.startswith("平台提链失败") else f"平台提链失败：{detail}"
            if generic_workbench_failure(message):
                message = error
    payment_phase = _payment_phase(
        payment, mode=mode, extraction=extraction, summary=summary,
        has_payment_entry=has_payment_entry,
    )
    plus_state = _plus_state(plus, summary, payment_phase=payment_phase)
    halt_reason = str(summary.get("local_reconcile_reason") or "")
    halted = summary.get("local_reconcile_halted") is True
    reconcile_halt = {
        "halted": halted,
        "reason": halt_reason[:60],
        "label": _RECONCILE_HALT_LABELS.get(halt_reason, "已停止自动续查，待核对") if halted else "",
    }
    prepare_state = {"passed": "done", "success": "done", "failed": "failed", "skipped": "skipped"}.get(preflight, "pending")
    run_state = {"success": "done", "failed": "failed", "running": "running", "queued": "queued"}.get(extraction, "pending")
    verify_state = {"confirmed": "done", "not_confirmed": "failed", "unavailable": "warning", "checking": "running"}.get(plus_state, "pending")
    stages = {
        "prepare": {"state": prepare_state, "status": preflight},
        "run": {"state": run_state, "status": extraction, "step": progress.get("label") or "", "percent": progress.get("percent")},
        "verify": {"state": verify_state, "status": plus_state},
    }
    created_at = row.get("run_created_at") or row.get("task_created_at")
    updated_at = row.get("job_updated_at") or row.get("task_updated_at") or row.get("run_completed_at") or created_at
    return {
        "task_id": int(row.get("task_id") or 0),
        "run_id": int(row.get("run_id") or 0) or None,
        "account_id": int(row.get("account_id") or 0) or None,
        "batch_id": int(row.get("batch_id") or 0) or None,
        "email": str(row.get("email") or ""),
        "provider_id": provider_id,
        "mode": mode,
        "payment_source": payment_source,
        "payment_source_label": "XXSYUN" if payment_source == "xxsyun" else "平台自带",
        "payment_order": ({"id": summary.get("payment_order_id"), "remote_order_id": summary.get("payment_remote_order_id") or "",
                           "submission_state": summary.get("payment_submission_state") or "reserved",
                           "payment_state": state.get("payment_state") or "pending", "submitted_at": summary.get("payment_submitted_at") or None}
                          if payment_source == "xxsyun" and summary.get("payment_order_id") else None),
        "link_type": str(data.get("link_type") or "")[:80],
        "task_status": task_status,
        "preflight_status": preflight,
        "extraction_status": extraction,
        "payment_status": payment,
        "payment_confirmation_source": summary.get("payment_confirmation_source") if (
            payment == "paid" and summary.get("payment_confirmation_source") in {"local_plan_check", "platform_order_check"}
        ) else "",
        "plus_status": plus,
        "payment_phase": payment_phase,
        "plus_state": plus_state,
        "remote_raw": _remote_raw(summary),
        "reconcile_halt": reconcile_halt,
        "stages": stages,
        "run_count": int(row.get("run_count") or 0),
        "progress": progress,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
        "message": message[:500],
        "error": error[:500],
        "has_extract_link": bool(state.get("links") or artifact.get("payment_page_url") or state.get("payment_links") or legacy_has_link),
        "has_payment_link": bool(artifact.get("payment_url") or artifact.get("payment_page_url") or state.get("payment_links") or state.get("links") or legacy_has_link),
        "has_payment_entry": has_payment_entry,
        "has_qr": bool(artifact.get("qr_data") or artifact.get("qr_image_url_png") or artifact.get("qr_image_url_svg")),
        "local_reconcile_halted": provider_id in {"huanguang", "legacy"} and summary.get("local_reconcile_halted") is True,
    }


def workbench_status_matches(item: dict, status: str) -> bool:
    if not status:
        return True
    task_status = str(item.get("task_status") or "")
    extraction = str(item.get("extraction_status") or "")
    payment = str(item.get("payment_status") or "")
    plus = str(item.get("plus_status") or "")
    if item.get("local_reconcile_halted") is True and status in {"processing", "running", "needs_attention"}:
        return status == "needs_attention"
    if status == "processing":
        return (
            task_status in {"queued", "running", "waiting", "cancelling", "settling", "stopping"}
            or (item.get("mode") == "auto_payment" and payment == "pending_payment"
                and task_status not in {"attention_required", "request_unknown", "failed", "cancelled", "stopped", "interrupted"})
            or (payment == "paid" and plus in {"unknown", "pending", "queued"})
        )
    if status == "running":
        return task_status in {"running", "cancelling", "settling", "stopping"}
    if status == "extraction_succeeded":
        return extraction == "success"
    if status == "payment_succeeded":
        return payment == "paid"
    if status == "plus_confirmed":
        return plus == "confirmed"
    if status == "needs_attention":
        return (
            task_status in {"failed", "request_unknown", "cancelled", "attention_required", "partial_success", "stopped", "interrupted"}
            or extraction in {"unknown", "failed"} or payment in {"request_unknown", "failed"}
            or plus in {"failed", "not_confirmed"} or (payment == "paid" and plus == "unknown")
        )
    return False


def list_workbench_tasks(
    *, provider_id: str | None = None, mode: str | None = None,
    status: str = "", query: str = "", page: int = 1, page_size: int = 20,
    batch_id: int | None = None,
) -> dict:
    """按现有筛选和分页规则读取工作台任务并投影当前页。"""
    from core.storage.extract_link import jobs as extract_link_jobs

    result = extract_link_jobs.list_workbench_page(
        provider_id=provider_id, mode=mode, query=query, status=status,
        page=page, page_size=page_size,
        **({"batch_id": int(batch_id)} if batch_id is not None else {}),
    )
    return {**result, "items": workbench_project_rows(result["items"])}


def workbench_project_rows(rows: list[dict]) -> list[dict]:
    account_rows = db.get_accounts_for_jobs([
        {
            "id": int(row.get("task_id") or 0),
            "account_id": row.get("account_id"),
            "email": row.get("email"),
        }
        for row in rows
    ])
    return [
        workbench_task_item(row, account=account_rows.get(int(row.get("task_id") or 0)))
        for row in rows
    ]


def workbench_counts(items: list[dict]) -> dict:
    return {
        "all": len(items),
        "processing": sum(workbench_status_matches(item, "processing") for item in items),
        "running": sum(workbench_status_matches(item, "running") for item in items),
        "extraction_succeeded": sum(workbench_status_matches(item, "extraction_succeeded") for item in items),
        "payment_succeeded": sum(workbench_status_matches(item, "payment_succeeded") for item in items),
        "plus_confirmed": sum(workbench_status_matches(item, "plus_confirmed") for item in items),
        "needs_attention": sum(workbench_status_matches(item, "needs_attention") for item in items),
    }


def preview_workbench_candidates(*, filters: dict | None = None, limit: int = 100) -> dict:
    """读取批次候选预览及选中数量。"""
    from core.storage.extract_link import batches as extract_link_batches

    result = extract_link_batches.candidate_accounts(filters=filters, limit=limit)
    items = result.get("items") or []
    return {
        "total": int(result.get("total") or 0),
        "selected_count": len(items),
        "limit": int(result["limit"]),
        "max_batch_size": extract_link_batches.MAX_BATCH_SIZE,
        "items": items[:20],
    }


def workbench_batch_summary(batch: dict, aggregate: dict) -> dict:
    data = batch.get("data") if isinstance(batch.get("data"), dict) else {}
    counts = {key: int(aggregate.get(key) or 0) for key in (
        "all", "processing", "running", "extraction_succeeded", "payment_succeeded", "plus_confirmed", "needs_attention",
    )}
    requested = int(batch.get("requested_count") or 0)
    skipped = int(data.get("submission_skipped") or 0)
    failed = int(data.get("submission_failed") or 0)
    incomplete = not data.get("submission_complete") or requested != counts["all"] + skipped + failed
    if counts["running"]:
        status = "running"
    elif counts["processing"]:
        status = "queued" if aggregate.get("task_queued") else "waiting"
    elif incomplete or skipped or failed or counts["needs_attention"]:
        status = "partial_success" if aggregate.get("task_succeeded") or counts["extraction_succeeded"] or counts["payment_succeeded"] else "failed"
    else:
        status = "success" if counts["all"] else "failed"
    created_at = batch.get("created_at")
    workers = data.get("workers")
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 50:
        workers = None
    return {
        "batch_id": int(batch["id"]), "title": str(batch.get("title") or "提链批次")[:240],
        "workers": workers,
        "provider_id": str(data.get("provider_id") or "legacy"), "mode": str(data.get("mode") or "extract_only"),
        "payment_source": "xxsyun" if data.get("payment_source") == "xxsyun" else "native",
        "payment_source_label": "XXSYUN" if data.get("payment_source") == "xxsyun" else "平台自带",
        "status": status, "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "requested_count": requested, "started_count": counts["all"], "skipped_count": skipped,
        "submission_failed_count": failed, "submission_incomplete": bool(incomplete), "counts": counts,
    }


def list_workbench_batches(*, page: int = 1, page_size: int = 20) -> dict:
    """读取批次分页与存储层汇总统计。"""
    from core.storage.extract_link import batches as extract_link_batches

    result = extract_link_batches.batch_rows(page=page, page_size=page_size)
    batches = result.get("items") or []
    grouped = extract_link_batches.batch_task_counts([int(batch["id"]) for batch in batches])
    return {**result, "items": [workbench_batch_summary(batch, grouped.get(int(batch["id"]), {})) for batch in batches]}


def workbench_batch_detail(batch_id: int) -> dict | None:
    """读取单个批次及对应汇总。"""
    from core.storage.extract_link import batches as extract_link_batches

    batches = extract_link_batches.batch_rows(batch_id=int(batch_id)).get("items") or []
    if not batches:
        return None
    counts = extract_link_batches.batch_task_counts([int(batch_id)])
    return workbench_batch_summary(batches[0], counts.get(int(batch_id), {}))


def extract_workbench_task_detail(task_id: int) -> dict | None:
    """读取任务详情、执行历史与事件展示字段。"""
    from core.storage.extract_link import jobs as extract_link_jobs

    detail = extract_link_jobs.get_workbench_detail_rows(int(task_id))
    if detail is None:
        return None
    item = workbench_project_rows([detail["item"]])[0]
    history = []
    for run in detail["history"]:
        history.append({
            "run_id": run["run_id"],
            "run_no": run.get("run_no"),
            "status": run.get("status"),
            "provider_id": run["provider_id"],
            "extraction_status": run["extraction_status"],
            "payment_status": run["payment_status"],
            "created_at": run.get("created_at"),
            "completed_at": run.get("completed_at"),
            "message": task_run_log.redact_text(str(run.get("error_message") or ""), 500),
        })
    events = []
    for event in detail["events"]:
        message = task_run_log.redact_text(str(event.get("message") or ""), 500)
        events.append({
            "id": event.get("id"),
            "run_id": event.get("run_id"),
            "stage": str(event.get("stage") or "")[:80],
            "status": str(event.get("status") or "")[:80],
            "label": str(event.get("label") or event.get("stage") or "事件")[:100],
            "message": message,
            "created_at": event.get("created_at"),
        })
    return {"item": item, "history": history, "events": events}
