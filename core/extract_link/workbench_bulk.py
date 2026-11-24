"""提链工作台集合用例；外部平台执行仍由原有提链 Worker 负责。"""
from __future__ import annotations

from core.operations.contracts import BulkItemResult
from core.storage.extract_link import workbench_bulk as storage


def normalize_ids(values, *, maximum=5000):
    if not isinstance(values, (list, tuple)) or not values or len(values) > maximum:
        raise ValueError(f"task_ids 必须包含 1 至 {maximum} 个有效任务 ID")
    result = []
    for value in values:
        if type(value) is int and 0 < value < 2**63:
            result.append(str(value))
        elif isinstance(value, str) and value.isascii() and value.isdecimal() and 0 < int(value) < 2**63:
            result.append(str(int(value)))
        else:
            raise ValueError("task_ids 必须是有效正整数")
    return result


def _entry(row):
    from core.extract_link.contracts import safe_links, safe_payment_artifact
    if row.get("task_type") != "extract_link":
        return {}
    job = row.get("provider_job") or {}
    state = job.get("public_state") or {}
    entry = safe_payment_artifact(state.get("payment_artifact"))
    links = safe_links(*(state.get("links") or []))
    payment_links = safe_links(*(state.get("payment_links") or []))
    if not entry.get("payment_page_url") and links:
        entry["payment_page_url"] = links[0]
    elif not entry.get("payment_page_url") and not entry.get("payment_url") and payment_links:
        entry["payment_page_url"] = payment_links[0]
    fields = ("payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg")
    if any(entry.get(key) for key in fields):
        return entry
    # 原单公开链接回退顺序与单条 payment-entry 相同。
    candidates = safe_links(entry.get("payment_url"), entry.get("payment_page_url"),
                            *payment_links, *links)
    if candidates:
        return {"payment_page_url": candidates[0]}
    data = row.get("data") or {}
    summary = (row.get("latest_run") or {}).get("result_summary") or {}
    remote_job = str(summary.get("remote_job_id") or "").strip()
    if str(data.get("provider_id") or "legacy") == "legacy" and summary.get("has_link") \
            and remote_job and str(row.get("legacy_job_id") or "") == remote_job:
        legacy = safe_links(row.get("legacy_link"))
        if legacy:
            return {"payment_page_url": legacy[0]}
    return {}


def payment_entries(task_ids):
    raw = normalize_ids(task_ids)
    ids = list(dict.fromkeys(raw))
    rows = storage.read_snapshots(ids, use_latest=False)
    items = []
    for task_id in ids:
        row = rows.get(int(task_id))
        entry = _entry(row) if row else {}
        if entry:
            items.append({"task_id": task_id, "status": "updated", "entry": entry,
                          "reason_code": "", "reason": ""})
        else:
            items.append({"task_id": task_id, "status": "skipped",
                          "reason_code": "payment_entry_missing" if row else "task_not_found",
                          "reason": "当前任务没有已保存的支付入口" if row else "任务不存在"})
    return {"ok": True, "items": items, "requested_count": len(raw), "unique_count": len(ids),
            "duplicate_count": len(raw) - len(ids)}


def _prepare_sync(row):
    from core.extract_link import service
    from core.extract_link.independent_payment import frozen_source
    active = {"queued", "running", "waiting", "cancelling", "settling", "stopping"}
    if row.get("task_type") != "extract_link" or row.get("source_system") != "native_operations":
        return None, "task_not_supported", "该任务不支持原单同步"
    if row.get("has_active_run") or str(row.get("status") or "").lower() in active:
        return None, "task_active", "任务仍在执行"
    if row.get("account_busy"):
        return None, "account_busy", "该账号已有排队或运行中的账号操作"
    latest = row.get("latest_run") or {}
    summary = latest.get("result_summary") or {}
    if row.get("account_deactivated") or row.get("status") == "deactivated" \
            or row.get("target_status") in {"deactivated", "account_deactivated"} \
            or any(summary.get(key) == "deactivated" for key in ("status", "requested_status")):
        return None, "account_deactivated", "账号已废号，禁止重跑"
    data = row.get("data") or {}
    provider = str(data.get("provider_id") or "legacy").strip().lower()
    mode = str(data.get("mode") or "extract_only").strip().lower()
    job = row.get("provider_job") or {}
    if provider not in service._PROVIDER_SETTINGS:
        return None, "provider_not_supported", "当前平台不支持原单同步"
    if provider != "anguang" and frozen_source(data) == "xxsyun":
        order = row.get("payment_order")
        if not order and not job:
            return None, "provider_reference_missing", "未保存可同步的原单"
        run_data = {"provider_id": provider, "mode": "auto_payment", "payment_source": "xxsyun",
            "link_type": data.get("link_type") or "upi", "options": data.get("options") or {},
            "workbench_action": "sync_status", "provider_job_run_id": latest.get("id"),
            "independent_payment_new_attempt": False,
            "independent_payment_refresh_material": not order,
            "extract_poll_continuation": False, "allow_no_promotion": data.get("allow_no_promotion") is True}
    else:
        saved = provider in {"legacy", "anguang"} and service._provider_has_reference(job)
        if not saved and (not service._bool_setting("EXTRACT_LINK_ENABLED", True)
                          or not service._provider_enabled(provider)):
            return None, "provider_disabled", "当前配置未启用该平台"
        if not job or not service._provider_has_reference(job):
            return None, "provider_reference_missing", "未保存可同步的原单"
        run_data = {"provider_id": provider, "mode": mode, "workbench_action": "sync_status",
                    "provider_job_run_id": latest.get("id")}
        if provider in {"huanguang", "anguang"}:
            run_data["extract_poll_continuation"] = False
    merged = dict(latest.get("data") or {})
    merged.update(data)
    merged.update(run_data)
    merged["retry_trigger"] = "extract_workbench_sync_status"
    merged.pop("remote_intent", None)
    merged.pop("remote_receipt", None)
    return {"task_id": int(row["id"]), "task_uuid": row["task_uuid"],
            "run_no": int(latest.get("run_no") or 0) + 1,
            "account_id": row.get("account_id"), "parent_task_id": row.get("parent_task_id"),
            "batch_id": latest.get("batch_id"), "source_run_id": latest.get("id"),
            "provider_id": provider, "resource_family": latest.get("resource_family") or "openai_interactive",
            "data": merged}, "", ""


def sync_status_many(chunk, parameters, *, conn):
    ids = [str(value) for value in chunk]
    snapshots = storage.read_snapshots(ids, conn=conn, lock=True)
    prepared, skipped = [], {}
    selected_accounts = set()
    for task_id in ids:
        row = snapshots.get(int(task_id))
        if not row:
            skipped[task_id] = ("task_not_found", "任务不存在")
            continue
        item, code, reason = _prepare_sync(row)
        if item is None:
            skipped[task_id] = (code, reason)
        elif item.get("account_id") and item["account_id"] in selected_accounts:
            skipped[task_id] = ("account_busy", "该账号已有排队或运行中的账号操作")
        else:
            prepared.append(item)
            if item.get("account_id"):
                selected_accounts.add(item["account_id"])
    runs = storage.retry_sync_many(prepared, conn=conn)
    return tuple(BulkItemResult(task_id, "skipped", *skipped[task_id]) if task_id in skipped
                 else BulkItemResult(task_id, "updated", data={"task_id": int(task_id),
                                                             "run_id": runs[int(task_id)]})
                 for task_id in ids)


def _after_sync(chunk, parameters, items):
    from core import account_task_store
    account_task_store.notify_dispatch()


def register_handlers(register=None):
    if register is None:
        from core.operations.bulk_mutation_worker import register_bulk_mutation_handler as register
    register("extract_sync_status", sync_status_many, after_commit=_after_sync)
