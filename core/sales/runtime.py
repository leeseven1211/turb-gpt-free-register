"""销售任务 handler 与持久任务生产器。"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from core.operations import task_gateway
from core.runtime.periodic import PeriodicThread, execution_allowed
from core.storage import records
from core.storage.operations import store as operations

from . import jobs, service, store
from .errors import SalesError

logger = logging.getLogger(__name__)
_PRODUCER = PeriodicThread("sales-sync-producer")
_POLL_SECONDS = 5
_RECOVERY_BATCH_SIZE = 100
_RECOVERY_RETRY_SECONDS = 60


def _check_payload_owner(payload):
    if payload.get("shop_id") is not None:
        service.require_shop(payload["shop_id"])
    elif not (payload.get("archive_only") and payload.get("owner_id") == service.require_executor()):
        raise SalesError("shop_executor_mismatch", "当前执行端无权操作此销售任务", 403)


def _set_listing_paused(payload, *, paused, conn):
    if payload.get("action") != "list":
        return
    shop = service.require_shop(payload["shop_id"], conn=conn)
    service._same_shop(shop, conn=conn)
    before, after = ("pending", "paused") if paused else ("paused", "pending")
    event = "listing_paused" if paused else "listing_resumed"
    for item_id in sorted(jobs.item_ids(payload)):
        item = store.get_item(item_id, private=True, conn=conn, for_update=True)
        if (item and item["sync_status"] == before and item["shop_id"] == shop["id"]
                and item["product_id"] == payload["product_id"] and item["fingerprint"]):
            store.patch_item(item_id, {"sync_status": after}, event=event, conn=conn)


def _retry(task):
    payload = task.get("data") or {}
    try:
        _check_payload_owner(payload)
        if payload.get("action") != "list":
            return task_gateway.default_operation_retry(task)
        with records.transaction() as conn:
            run = operations.retry_runtime_task(task["id"], conn=conn)
            _set_listing_paused(payload, paused=False, conn=conn)
    except SalesError as error:
        return {"accepted": False, "error_code": error.code, "error": str(error)}
    except (LookupError, ValueError) as error:
        return {"accepted": False, "error_code": "sales_task_retry_failed", "error": str(error)}
    task_gateway.notify_dispatch()
    return {"accepted": True, "task_id": task["id"], "run_id": run["id"], "status": "queued"}


def _stop(task, *, force=False):
    payload = task.get("data") or {}
    try:
        _check_payload_owner(payload)
        if payload.get("action") != "list":
            action = task_gateway.default_operation_terminate if force else task_gateway.default_operation_cancel
            return action(task)
        active = next((run for run in reversed(task.get("runs") or [])
                       if run["status"] in {"queued", "running", "cancelling", "settling", "waiting"}), None)
        if active is None:
            return {"ok": True, "running": False, "state": "empty", "message": "任务没有活跃执行"}
        run_id = active["id"]
        with records.transaction() as conn:
            run = operations.request_run_cancel(
                run_id, reason="用户暂停销售上架",
                expected_status=task.get("_expected_run_status") or active["status"], conn=conn,
            )
            if run.get("cancel_skipped"):
                return {"ok": False, "state": run["status"], "message": run["message"]}
            _set_listing_paused(payload, paused=True, conn=conn)
        if force and run["status"] == "cancelling":
            run = operations.terminate_run(run_id, reason="用户终止销售上架")
    except SalesError as error:
        return {"ok": False, "error_code": error.code, "error": str(error)}
    except LookupError:
        return {"ok": False, "error_code": "sales_task_not_found", "error": "销售任务不存在"}
    task_gateway.notify_dispatch()
    state = run["status"]
    return {"ok": True, "run_id": run_id, "running": state == "cancelling", "state": state,
            "message": "已暂停上架，原目标和交付资料可供手动重跑"}


def _cancel(task):
    return _stop(task)


def _terminate(task):
    return _stop(task, force=True)


def register_actions():
    task_gateway.register_operation_actions(
        jobs.TASK_TYPE, retry_handler=_retry, cancel_handler=_cancel, terminate_handler=_terminate,
    )


def _capacity_keys(run):
    payload = run.get("data") or {}
    shop_id = payload.get("shop_id")
    return {f"shop:{shop_id}": 1} if shop_id is not None else {"manual-archive": 1}


def register_handler():
    task_gateway.register_operation_handler(
        jobs.TASK_TYPE, _execute, config_allowlist=(), retry_handler=_retry, cancel_handler=_cancel,
        terminate_handler=_terminate,
        dispatch_capacity_key=_capacity_keys, dispatch_capacity_limit=lambda _key: 1,
    )


def _execute(context):
    payload = context.run.get("data") or {}
    action = payload.get("action")
    selected = jobs.item_ids(payload)
    with jobs.execution(context):
        try:
            _check_payload_owner(payload)
            if action == "list":
                context.report(stage="sales_listing", message="回读店铺库存并核对原上架意图")
                if selected:
                    result = service.execute_listing(payload["shop_id"], payload["product_id"], selected)
                else:
                    result = service._summary([])
                preflight = jobs.unpack_result(payload.get("preflight") or {})
                rejected = [item for item in preflight.get("items", []) if item["error_code"]]
                if rejected:
                    archive_error = result.get("error_code"), result.get("error_message")
                    result = service._summary(sorted(result["items"] + rejected, key=lambda row: row["id"]),
                                              archived_count=result.get("archived_count", 0),
                                              archive_failed_count=result.get("archive_failed_count", 0))
                    if not result.get("error_code") and archive_error[0]:
                        result.update(error_code=archive_error[0], error_message=archive_error[1])
            elif action == "sync" and payload.get("archive_only"):
                context.report(stage="sales_archive", message="确认来源账号归档状态")
                result = service.process_archives(item_ids=selected)
            elif action == "sync":
                context.report(stage="sales_sync", message="读取店铺商品、库存和订单")
                result = service.execute_sync(payload["shop_id"])
            else:
                raise SalesError("sales_task_action_invalid", "销售任务操作类型无效")
        except SalesError as error:
            return task_gateway.OperationResult.failed(str(error), {
                "error_code": error.code, "cause_code": error.code, "error_message": str(error),
                "failure_stage": _stage(payload),
            })
    if result["failed_count"] or result.get("archive_failed_count"):
        result["failure_stage"] = "sales_archive" if not result["failed_count"] else _stage(payload)
        result["cause_code"] = result["error_code"]
        message = result["error_message"]
        status = "partial_success" if result["success_count"] else "failed"
        return task_gateway.OperationResult(status, jobs.pack_result(result), message, message)
    return task_gateway.OperationResult.success(jobs.pack_result(result), message="销售任务处理完成")


def _stage(payload):
    if payload.get("action") == "list":
        return "sales_listing"
    return "sales_archive" if payload.get("archive_only") else "sales_sync"


def _lock_owned_shops(shop_ids, owner_id, *, conn):
    owned = {}
    for shop_id in sorted({shop_id for shop_id in shop_ids if shop_id is not None}):
        jobs.lock(conn, f"shop:{shop_id}")
        shop = store.get_shop(shop_id, conn=conn)
        if shop and shop["owner_id"] == owner_id:
            owned[shop_id] = shop
    return owned


def enqueue_recoveries():
    owner_id = service.require_executor()
    operations.init()
    listing = store.list_listing_pending(limit=_RECOVERY_BATCH_SIZE, owner_id=owner_id)
    archives = store.list_archive_pending(limit=_RECOVERY_BATCH_SIZE, owner_id=owner_id)
    if not listing and not archives:
        return 0
    count = 0
    with records.transaction() as conn:
        jobs.lock(conn, f"producer:{owner_id}")
        owned = _lock_owned_shops([item["shop_id"] for item in listing + archives], owner_id, conn=conn)
        active = jobs.active_payloads(conn=conn)
        active_listing = {item_id for row in active if row.get("action") == "list" for item_id in jobs.item_ids(row)}
        active_archives = {item_id for row in active if row.get("archive_only") for item_id in jobs.item_ids(row)}
        listing_groups = defaultdict(list)
        archive_groups = defaultdict(list)
        for item in listing:
            if item["shop_id"] in owned and item["id"] not in active_listing:
                listing_groups[item["shop_id"], item["product_id"]].append(item)
        for item in archives:
            if ((item["shop_id"] is None or item["shop_id"] in owned)
                    and item["id"] not in active_archives and item["id"] not in active_listing):
                archive_groups[item["shop_id"]].append(item)

        for (shop_id, product_id), items in listing_groups.items():
            ready = _recoverable_items(items, conn=conn, field="sync_status", expected="pending")
            if not ready:
                continue
            jobs.submit({"action": "list", "shop_id": shop_id, "product_id": product_id,
                         "item_chunks": jobs.chunks(ready)}, trigger="sales_recovery", conn=conn)
            count += 1
        for shop_id, items in archive_groups.items():
            ready = _recoverable_items(items, conn=conn, field="archive_pending", expected=True)
            if not ready:
                continue
            jobs.submit({"action": "sync", "archive_only": True, "shop_id": shop_id,
                         "owner_id": owner_id, "item_chunks": jobs.chunks(ready)},
                        trigger="sales_recovery", conn=conn)
            count += 1
    if count:
        task_gateway.notify_dispatch()
    return count


def _recoverable_items(items, *, conn, field, expected):
    now = datetime.now(timezone.utc)
    targets = {item["id"]: (item["shop_id"], item["product_id"]) for item in items}
    ready = []
    for current in store.get_items(list(targets), conn=conn):
        if current[field] != expected or (current["shop_id"], current["product_id"]) != targets[current["id"]]:
            continue
        if current["error_code"] and (now - datetime.fromisoformat(current["updated_at"])).total_seconds() < _RECOVERY_RETRY_SECONDS:
            continue
        ready.append(current["id"])
    return ready


def _due(shop, now, last_submitted):
    synced = shop["last_synced_at"]
    last_success = datetime.fromisoformat(synced).timestamp() if synced else 0
    return (now - max(last_success, last_submitted.get(shop["id"], 0))) >= shop["sync_interval"]


def _enqueue_periodic_syncs(last_submitted):
    owner = service.require_executor()
    now = datetime.now(timezone.utc).timestamp()
    candidates = [shop["id"] for shop in store.list_shops()
                  if shop["owner_id"] == owner and shop["enabled"] and _due(shop, now, last_submitted)]
    if not candidates:
        return
    operations.init()
    with records.transaction() as conn:
        jobs.lock(conn, f"producer:{owner}")
        owned = _lock_owned_shops(candidates, owner, conn=conn)
        active = {
            payload.get("shop_id") for payload in jobs.active_payloads(conn=conn)
            if payload.get("action") == "sync" and not payload.get("archive_only")
        }
        submitted = []
        for shop_id, shop in owned.items():
            if shop_id not in active and shop["enabled"] and _due(shop, now, last_submitted):
                jobs.submit({"action": "sync", "shop_id": shop_id}, trigger="scheduled", conn=conn)
                submitted.append(shop_id)
    if submitted:
        last_submitted.update((shop_id, now) for shop_id in submitted)
        task_gateway.notify_dispatch()


def _periodic_loop():
    last_submitted = {}
    while not _PRODUCER.stop_event.is_set():
        if execution_allowed() and service.executor_id():
            _PRODUCER.work_started()
            try:
                enqueue_recoveries()
                if not _PRODUCER.stop_event.is_set() and execution_allowed():
                    _enqueue_periodic_syncs(last_submitted)
            except SalesError as error:
                _PRODUCER.record_error(error.code)
                logger.warning("销售任务调度失败，错误分类 %s", error.code)
            except Exception as error:
                _PRODUCER.record_error("sales_scheduler_storage_failed")
                logger.warning("销售任务调度无法读取或写入任务库，异常类型 %s", type(error).__name__)
            finally:
                _PRODUCER.work_finished()
        if _PRODUCER.stop_event.wait(_POLL_SECONDS):
            return


def start_periodic_sync():
    return _PRODUCER.start(_periodic_loop)


def stop_periodic_sync(timeout=2.0):
    return _PRODUCER.stop(timeout)


def periodic_sync_status():
    return _PRODUCER.status(enabled=bool(service.executor_id()))
