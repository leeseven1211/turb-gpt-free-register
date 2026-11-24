"""账号工具栏批量提链的本地集合受理；执行复用原生 legacy handler。"""
from __future__ import annotations

import logging
import uuid

from core import db
from core.accounts.plans.promotion import is_free_trial_record
from core.operations import task_gateway
from core.storage import records
from core.storage.extract_link import account_submission as storage
from core.storage.operations import bulk_submission, store as operation

logger = logging.getLogger(__name__)


def _targets(values):
    ids, invalid, seen = [], [], set()
    for raw in values:
        try:
            if isinstance(raw, (bool, float, list, dict)):
                raise ValueError()
            value = int(raw)
            if not 0 < value < 2**63:
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            invalid.append({"id": raw, "reason": "ID 非法", "reason_code": "invalid_target"})
            continue
        if value not in seen:
            ids.append(value)
            seen.add(value)
    return ids, invalid


def submit_accounts(account_ids, *, link_type=None, cdk=None, payment_options=None, trigger="manual_bulk"):
    """固定一次集合与快照，在同一事务内占用账号并创建 Task/Run/批次。"""
    from core.extract_link import service

    if not isinstance(account_ids, list) or not account_ids or len(account_ids) > 500:
        raise ValueError("account_ids 必须是最多 500 项的非空数组")
    ids, skipped = _targets(account_ids)
    result = {"ok": True, "started": [], "busy": [], "failed": [], "skipped": skipped, "batch_id": None}
    candidates = []
    batch = None
    if ids:
        records.init()
        operation.init()
        try:
            with operation._connect() as conn:
                accounts = storage.read_accounts(ids, conn=conn)
                for account_id in ids:
                    account = accounts.get(account_id)
                    identity = {"id": account_id, "email": (account or {}).get("email") or ""}
                    if account is None:
                        reason = "账号不存在"
                    elif db.account_is_deactivated(account):
                        reason = "账号已废号"
                    elif not is_free_trial_record(account):
                        reason = "不是已确认的 Plus 免费试用账号"
                    elif not str(account.get("access_token") or "").strip():
                        reason = "缺少 access_token"
                    else:
                        candidates.append((account, identity))
                        continue
                    skipped.append({**identity, "reason": reason})
                if candidates:
                    batch = bulk_submission.create_batch(conn=conn, task_type="extract_link",
                        requested_count=len(candidates), trigger=trigger, title="批量提链")
                    result["batch_id"] = batch["id"]
                    ready = []
                    enabled_order = None
                    available = service._provider_mode_enabled("legacy", "extract_only")
                    common_error = None
                    if not available:
                        common_error = "虾扯蛋链平台或提取能力已关闭"
                    else:
                        try:
                            # CDK 仍只校验，不进入 Task、Run、批次或诊断回执。
                            service._cdk(cdk)
                            options = service._paypal_options(payment_options)
                            snapshot = service.get_config_snapshot()
                        except ValueError as exc:
                            common_error = str(exc)
                    active = storage.active_accounts([row["id"] for row, _ in candidates], conn=conn)
                    for account, identity in candidates:
                        if common_error:
                            result["failed"].append({**identity, "error": common_error})
                            continue
                        try:
                            requested = service._link_type(link_type)
                            if requested in service._failed_link_types(account) and enabled_order is None:
                                enabled_order = service._enabled_link_type_order()
                            selected, fallback = service._select_account_link_type(
                                account=account, requested=requested, enabled_type_order=enabled_order,
                            )
                        except ValueError as exc:
                            result["failed"].append({**identity, "error": str(exc)})
                            continue
                        if account["id"] in active:
                            result["busy"].append({**identity, "accepted": False, "busy": True,
                                **active[account["id"]], "error": "该账号已有排队或运行中的账号操作"})
                            continue
                        ready.append({"account_id": account["id"], "email": identity["email"],
                                      "link_type": selected, "fallback_from": fallback})
                    claimed = storage.claim_accounts(ready, trigger=trigger, conn=conn)
                    selected_targets = []
                    for target in ready:
                        if target["account_id"] not in claimed:
                            result["busy"].append({"id": target["account_id"], "email": target["email"],
                                "accepted": False, "busy": True, "error": "该账号正在提链中"})
                        else:
                            selected_targets.append(target)
                    specs = [{
                        "task_type": "extract_link", "account_id": target["account_id"], "email": target["email"],
                        "source_system": "native_operations",
                        "source_id": f"maintenance:extract_link:{target['account_id']}:{uuid.uuid4().hex}",
                        "trigger": trigger, "resource_family": "openai_interactive",
                        "batch_id": batch["id"], "batch_ordinal": ordinal,
                        "data": {"link_type": target["link_type"], "payment_options": options},
                        "config_snapshot": snapshot, "config_allowlist": service.EXTRACT_CONFIG_ALLOWLIST,
                    } for ordinal, target in enumerate(selected_targets, 1)]
                    created = bulk_submission.create_specs(specs, conn=conn)
                    for target, receipt in zip(selected_targets, created, strict=True):
                        item = service._native_response(receipt, account_id=target["account_id"],
                            email=target["email"], trigger=trigger, link_type=target["link_type"])
                        item.pop("future", None)
                        if target["fallback_from"]:
                            item["fallback_from"] = target["fallback_from"]
                        result["started"].append({"id": target["account_id"], **item})
                    storage.finish_batch(batch["id"], started_count=len(result["started"]),
                        busy_count=len(result["busy"]), failed_count=len(result["failed"]),
                        skipped_count=len(skipped), conn=conn)
        except Exception as exc:
            # 块失败必须回滚占用和任务；错误正文可能含私密内容，不进入回执。
            logger.warning("账号批量提链受理失败：count=%s error_type=%s", len(candidates), type(exc).__name__)
            classified = {item["id"] for field in ("busy", "failed", "skipped")
                          for item in result[field] if type(item.get("id")) is int}
            known = {account["id"]: identity for account, identity in candidates}
            result["failed"].extend({
                **known.get(account_id, {"id": account_id}),
                "error": "提链任务持久化失败，请重试", "reason_code": "bulk_chunk_failed",
            } for account_id in ids if account_id not in classified)
            result.update(batch_id=None, started=[])
    for field in ("started", "busy", "failed", "skipped"):
        result[field + "_count"] = len(result[field])
    if result["started"]:
        task_gateway.notify_dispatch()
    return result
