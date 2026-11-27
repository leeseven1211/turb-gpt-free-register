"""销售条目、店铺与持久上架命令。"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from config import sales as sales_config
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import store as operations
from core.storage.runtime_config import RuntimeConfigStoreError, decrypt_private_text, encrypt_private_text

from . import jobs, matching, store
from .adapters import LiandongAdapter
from .errors import SalesError
from .sources import AccountSource

shop_adapter = LiandongAdapter
account_source = AccountSource


def executor_id():
    return str(sales_config.SALES_EXECUTOR_ID or "").strip()


def require_executor():
    current = executor_id()
    if not current:
        raise SalesError("sales_executor_disabled", "当前部署未配置销售执行端", 403)
    return current


def require_shop(shop_id, *, conn=None):
    shop = store.get_shop(jobs.positive_id(shop_id), conn=conn)
    if shop is None:
        raise SalesError("sales_shop_not_found", "店铺不存在", 404)
    if shop["owner_id"] != require_executor():
        raise SalesError("shop_executor_mismatch", "当前执行端无权操作此店铺", 403)
    return shop


def _shop_settings(shop):
    return tuple(shop[key] for key in ("platform", "base_url", "token_env", "owner_id", "external_shop_id"))


def _same_shop(shop, *, conn):
    jobs.lock(conn, f"shop:{shop['id']}")
    current = require_shop(shop["id"], conn=conn)
    if _shop_settings(current) != _shop_settings(shop):
        raise SalesError("shop_configuration_changed", "店铺配置已变更，请重新执行操作", 409)
    return current


def _product(shop_id, product_id, *, conn=None):
    product = store.get_product(jobs.positive_id(product_id), conn=conn)
    if product is None:
        raise SalesError("sales_product_not_found", "销售商品不存在", 404)
    if product["shop_id"] != shop_id:
        raise SalesError("product_shop_mismatch", "商品不属于目标店铺", 409)
    return product


def binding(shop, product):
    return {
        "external_shop_id": shop["external_shop_id"], "external_product_id": product["external_product_id"],
        "goods_key": product["goods_key"],
    }


def _same_product(shop, product, *, conn):
    current = _product(shop["id"], product["id"], conn=conn)
    if binding(shop, current) != binding(shop, product):
        raise SalesError("listing_target_changed", "店铺商品标识已变更", 409)
    return current


def _source_record(source_id, *, conn=None):
    if not isinstance(source_id, str) or not re.fullmatch(r"[a-z0-9_-]{1,40}", source_id):
        raise SalesError("sales_invalid_source_id", "来源 ID 格式不正确")
    source = store.get_source(source_id, conn=conn)
    if source is None:
        raise SalesError("sales_source_not_found", "账号来源不存在", 404)
    if not source["enabled"]:
        raise SalesError("sales_source_disabled", "账号来源已停用", 409)
    return source


def _source(source_id):
    return account_source(_source_record(source_id))


def save_source(data):
    require_executor()
    source_id = data.get("id")
    if not isinstance(source_id, str) or not re.fullmatch(r"[a-z0-9_-]{1,40}", source_id):
        raise SalesError("sales_invalid_source_id", "来源 ID 格式不正确")
    fields = ("id", "name", "kind", "base_url", "auth_env", "enabled")
    store.init()
    with records.transaction() as conn:
        jobs.lock(conn, "source-settings")
        existing = store.get_source(source_id, conn=conn)
        saved = {key: existing[key] for key in fields} if existing else {}
        saved.update(data)
        if (saved.get("kind") == "local" and source_id != "local") or (
            source_id == "local" and (saved.get("kind", "local") != "local" or saved.get("base_url"))
        ):
            raise SalesError("source_local_identity_invalid", "本地来源只能使用内置 local 标识和本机存储")
        if existing and any(saved[key] != existing[key] for key in ("kind", "base_url")):
            if store.list_items(source_id=source_id, page_size=1)["total"]:
                raise SalesError("source_identity_immutable", "此来源已有账号条目，不能改绑到另一部署", 409)
        return store.save_source(saved, conn=conn)


def save_shop(data):
    require_executor()
    shop_id = data.get("id")
    if shop_id is None:
        return store.save_shop(data)
    shop = require_shop(shop_id)
    proposed = {**shop, **data}
    sensitive_change = any(proposed[key] != shop[key] for key in ("platform", "base_url", "token_env"))
    if sensitive_change and shop["external_shop_id"]:
        _checked_adapter(proposed)
    operations.init()
    with records.transaction() as conn:
        current = _same_shop(shop, conn=conn)
        if (sensitive_change or proposed["owner_id"] != shop["owner_id"]) and any(
            job.get("shop_id") == shop_id for job in jobs.active_payloads(conn=conn)
        ):
            raise SalesError("shop_config_busy", "店铺仍有排队或执行中的任务，请在任务结束后修改接入或执行端", 409)
        return store.save_shop({
            key: data.get(key, current[key]) for key in (
                "id", "name", "platform", "base_url", "token_env", "external_shop_id", "enabled", "owner_id", "sync_interval",
            )
        }, conn=conn)


def _result(item_id, status="", error=None, **fields):
    return {
        "id": item_id,
        "status": status or ("failed" if error else "success"),
        "error_code": error.code if error else "",
        "message": str(error) if error else "",
        **fields,
    }


def _summary(results, **fields):
    errors = [row for row in results if row["error_code"]]
    summary = {
        "items": results, "total": len(results), "success_count": len(results) - len(errors),
        "failed_count": len(errors),
        "listed_count": sum(row["status"] == "listed" and not row["error_code"] for row in results),
        "sold_count": sum(row["status"] == "sold" and not row["error_code"] for row in results),
        **fields,
    }
    if errors:
        summary.update(error_code=errors[0]["error_code"], error_message=errors[0]["message"])
    return summary


def _missing_account():
    return SalesError("source_account_not_found", "来源账号不存在", 404)


def add_accounts(source_id, account_ids):
    requested = jobs.ids(account_ids)
    snapshot = _source_record(source_id)
    source = account_source(snapshot)
    by_id = {}
    results = {}
    for group in jobs.chunks(requested):
        try:
            by_id.update({account["id"]: account for account in source.accounts(group)})
        except SalesError as error:
            for account_id in group:
                results[account_id] = _result(account_id, error=error, account_id=account_id)
    with records.transaction() as conn:
        jobs.lock(conn, "source-settings")
        current = _source_record(source_id, conn=conn)
        if any(current[key] != snapshot[key] for key in ("kind", "base_url", "auth_env")):
            raise SalesError("source_configuration_changed", "来源配置已变更，请重新读取账号", 409)
        for account_id in requested:
            if account_id in results:
                continue
            account = by_id.get(account_id)
            if account is None:
                results[account_id] = _result(account_id, error=_missing_account(), account_id=account_id)
                continue
            item = store.add_item(
                source_id=source_id, account_id=account_id, email=account["email"],
                plan=account.get("plan", ""), conn=conn,
            )
            results[account_id] = _result(item["id"], item["status"], account_id=account_id)
    return _summary([results[account_id] for account_id in requested])


def _status_changes(data):
    if data.get("status") not in {"for_sale", "listed", "sold"}:
        raise SalesError("sales_invalid_status", "销售状态必须是待售、已上架或已售出")
    changes = {"status": data["status"]}
    for field, maximum in (("channel", 120), ("note", 2000), ("currency", 16)):
        if field in data:
            value = data[field]
            if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
                raise SalesError("sales_invalid_field", f"{field} 格式不正确")
            changes[field] = value.strip()
    if "price" in data:
        value = data["price"]
        if value is None:
            changes["price"] = None
        else:
            try:
                price = Decimal(str(value))
                if not price.is_finite() or not 0 <= price < 10**12:
                    raise ValueError
            except (ValueError, InvalidOperation):
                raise SalesError("sales_invalid_price", "价格必须是有限的非负金额") from None
            changes["price"] = price
    if "sold_at" in data:
        try:
            raw_time = data["sold_at"]
            sold_at = datetime.fromisoformat(raw_time) if raw_time is not None else None
            if sold_at is not None and sold_at.tzinfo is None:
                sold_at = sold_at.astimezone()
        except (TypeError, ValueError):
            raise SalesError("sales_invalid_sold_at", "sold_at 必须是日期时间") from None
        changes["sold_at"] = sold_at
    return changes


def change_status(data):
    requested = jobs.ids(data.get("item_ids"))
    changes = _status_changes(data)
    results = []
    current_owner = require_executor()
    for item_id in requested:
        try:
            with jobs.transaction() as conn:
                snapshot = store.get_item(item_id, conn=conn)
                if snapshot is None:
                    raise SalesError("item_not_found", "销售条目不存在", 404)
                if snapshot["shop_id"] is not None:
                    jobs.lock(conn, f"shop:{snapshot['shop_id']}")
                    require_shop(snapshot["shop_id"], conn=conn)
                item = store.get_item(item_id, private=True, conn=conn, for_update=True)
                if item is None:
                    raise SalesError("item_not_found", "销售条目不存在", 404)
                if item["shop_id"] != snapshot["shop_id"]:
                    raise SalesError("listing_intent_changed", "条目上架目标已变化，请重新操作", 409)
                if (changes["status"] == "for_sale" and item.get("listing_binding")
                        and item["sync_status"] in {"pending", "paused"}):
                    raise SalesError("listing_intent_active", "条目存在尚未确认的上架意图，请在任务中心处理", 409)
                update = dict(changes)
                if changes["status"] in {"listed", "sold"}:
                    update["archive_pending"] = not item["archived"]
                    if update["archive_pending"]:
                        update["archive_owner_id"] = current_owner
                elif item["archive_pending"] and not (item["external_inventory_id"] or item["order_ref"]):
                    update.update(archive_pending=False, archive_owner_id="")
                updated = store.patch_item(item_id, update, event="manual_status", conn=conn)
            results.append(_result(item_id, updated["status"]))
        except SalesError as error:
            results.append(_result(item_id, error=error))
    return _summary(results)


def _checked_adapter(shop):
    jobs.checkpoint()
    adapter = shop_adapter(shop)
    info = adapter.check()
    external_id = str(info.get("external_shop_id") or "")
    if not external_id or (shop["external_shop_id"] and shop["external_shop_id"] != external_id):
        raise SalesError("shop_identity_mismatch", "店铺返回的商户身份与已绑定商户不一致", 409)
    return adapter, info


def _refresh_products(shop, info, products):
    with jobs.transaction() as conn:
        _same_shop(shop, conn=conn)
        refreshed = store.patch_shop(shop["id"], {
            "external_shop_id": str(info["external_shop_id"]), "error_code": "", "error_message": "",
        }, conn=conn)
        store.replace_products(shop["id"], products, conn=conn)
    return refreshed


def _store_shop_error(shop, error):
    with jobs.transaction() as conn:
        _same_shop(shop, conn=conn)
        store.patch_shop(shop["id"], {"error_code": error.code, "error_message": str(error)}, conn=conn)


def check_shop(shop_id):
    shop = require_shop(shop_id)
    try:
        adapter, info = _checked_adapter(shop)
        products = adapter.products()
        updated = _refresh_products(shop, info, products)
    except SalesError as error:
        _store_shop_error(shop, error)
        raise
    return {
        "shop": updated, "external_shop_id": updated["external_shop_id"],
        "capabilities": info.get("capabilities", {}), "product_count": len(products),
    }


def _preflight(snapshot, shop_id, product_id):
    materials = {}
    errors = {}
    source_targets = defaultdict(list)
    for item in snapshot.values():
        item_id = item["id"]
        if item["fingerprint"]:
            if (item["shop_id"], item["product_id"]) != (shop_id, product_id):
                errors[item_id] = SalesError("listing_target_immutable", "已有上架目标，不能改派商品", 409)
        elif item["status"] != "for_sale" or item["order_ref"] or item["external_inventory_id"]:
            errors[item_id] = SalesError("listing_state_conflict", "条目已有销售归属，不能重新上架", 409)
        else:
            source_targets[item["source_id"]].append(item)
    for source_id, items in source_targets.items():
        try:
            source = _source(source_id)
        except SalesError as error:
            errors.update((item["id"], error) for item in items)
            continue
        for group in jobs.chunks(items):
            try:
                accounts = {a["id"]: a for a in source.accounts([item["account_id"] for item in group])}
            except SalesError as error:
                errors.update((item["id"], error) for item in group)
                continue
            for item in group:
                account = accounts.get(item["account_id"])
                try:
                    if account is None:
                        raise _missing_account()
                    line = matching.account_material(account)
                    materials[item["id"]] = (matching.fingerprint(line), _encrypt(line))
                except SalesError as error:
                    errors[item["id"]] = error
    return materials, errors


def _encrypt(line):
    try:
        return encrypt_private_text(line)
    except RuntimeConfigStoreError:
        raise SalesError("listing_encryption_unavailable", "交付材料加密失败，请检查配置主密钥", 503) from None


def _request_receipt(source_id, intent):
    with records.transaction() as conn:
        return jobs.receipt(source_id, intent, conn=conn)


def submit_listing(shop_id, product_id, item_ids, request_key):
    if request_key is None:
        raise SalesError("sales_invalid_request_key", "上架请求需要 request_key")
    requested = jobs.ids(item_ids)
    shop = require_shop(shop_id)
    product = _product(shop_id, product_id)
    source_id = jobs.request_id(request_key)
    intent = jobs.digest(["list", shop_id, product_id, requested])
    operations.init()
    prior = _request_receipt(source_id, intent)
    if prior:
        return prior
    if not shop["external_shop_id"] or not product["goods_key"]:
        raise SalesError("listing_target_unbound", "上架前请先检查店铺连接并同步商品", 409)
    snapshot = {item["id"]: item for item in store.get_items(requested, private=True)}
    materials, errors = _preflight(snapshot, shop_id, product_id)

    with records.transaction() as conn:
        jobs.lock(conn, f"request:{source_id}")
        prior = jobs.receipt(source_id, intent, conn=conn)
        if prior:
            return prior
        _same_shop(shop, conn=conn)
        current_product = _same_product(shop, product, conn=conn)
        target = binding(shop, product)
        if current_product["status"] == "unavailable":
            raise SalesError("sales_product_unavailable", "商品已从店铺商品列表中消失", 409)
        results, accepted = _freeze_batch(requested, shop_id, product_id, target, materials, errors, conn=conn)
        preflight = _summary(results)
        receipt = jobs.submit({
            "action": "list", "shop_id": shop_id, "product_id": product_id,
            "item_chunks": jobs.chunks(accepted),
            "intent_digest": intent, "preflight": jobs.pack_result(preflight),
        }, source_id=source_id, conn=conn)
    task_gateway.notify_dispatch()
    return {**receipt, **preflight}


def _freeze_batch(requested, shop_id, product_id, target, materials, errors, *, conn):
    results = []
    accepted = []
    for item_id in requested:
        try:
            with conn.transaction():
                item = store.get_item(item_id, private=True, conn=conn, for_update=True)
                if item is None:
                    raise SalesError("item_not_found", "销售条目不存在", 404)
                if item["fingerprint"]:
                    if (item["shop_id"], item["product_id"]) != (shop_id, product_id):
                        raise SalesError("listing_target_immutable", "已有上架目标，不能改派商品", 409)
                    frozen_target = item.get("listing_binding")
                    if frozen_target and frozen_target != target:
                        raise SalesError("listing_target_changed", "原上架商品或商户标识已变更", 409)
                    if not frozen_target and not (item["external_inventory_id"] or item["order_ref"]):
                        raise SalesError("listing_intent_missing", "找不到原上架意图", 409)
                    if item["sync_status"] == "paused":
                        store.patch_item(item_id, {"sync_status": "pending"}, event="listing_resumed", conn=conn)
                else:
                    if item_id in errors:
                        raise errors[item_id]
                    if item_id not in materials:
                        raise SalesError("listing_material_unavailable", "尚未取得交付资料，请重试", 409)
                    material_hash, encrypted = materials[item_id]
                    store.freeze_listing(
                        item_id, shop_id=shop_id, product_id=product_id, fingerprint=material_hash,
                        delivery_ciphertext=encrypted, binding=target, conn=conn,
                    )
                accepted.append(item_id)
        except SalesError as error:
            results.append(_result(item_id, error=error))
        else:
            results.append(_result(item_id, "queued"))
    return results, accepted


def submit_sync(shop_id, request_key=None):
    shop = require_shop(shop_id)
    operations.init()
    source_id = jobs.request_id(request_key)
    intent = jobs.digest(["sync", shop_id])
    with records.transaction() as conn:
        jobs.lock(conn, f"request:{source_id}")
        prior = jobs.receipt(source_id, intent, conn=conn)
        if prior:
            return prior
        _same_shop(shop, conn=conn)
        receipt = jobs.submit({
            "action": "sync", "shop_id": shop_id, "intent_digest": intent,
        }, source_id=source_id, conn=conn)
    task_gateway.notify_dispatch()
    return receipt


def _frozen_material(item):
    try:
        line = decrypt_private_text(item["delivery_ciphertext"])
    except RuntimeConfigStoreError:
        raise SalesError("listing_decryption_failed", "无法解密冻结的上架材料", 503) from None
    if not matching.delivery_email(line) or matching.fingerprint(line) != item["fingerprint"]:
        raise SalesError("listing_material_changed", "冻结材料校验失败", 409)
    return line


def _inventory_facts(adapter, product):
    jobs.checkpoint()
    inventory = adapter.inventory(product["external_product_id"])
    jobs.checkpoint()
    return matching.ShopFacts(product, inventory, adapter.orders())


def _confirm(item, shop, product, fact, *, archive, conn):
    inventory_id, sold, order = fact.confirmable()
    confirmed = store.confirm_inventory(
        item["id"], shop_id=shop["id"], product_id=product["id"], external_inventory_id=inventory_id,
        sold=sold, order_ref=order["order_ref"] if order else "",
        order_amount=order["amount"] if order else None, paid_at=order["paid_at"] if order else None,
        archive=archive, conn=conn,
    )
    if order:
        confirmed = _record_order(confirmed, shop, order, conn=conn)
    return confirmed


def _record_order(item, shop, order, *, conn):
    return store.patch_item(
        item["id"], {"order_status": order["status"]}, event="order_status", conn=conn,
    )


def _record_listing_error(item, shop, product, error):
    with jobs.transaction() as conn:
        _same_shop(shop, conn=conn)
        current = store.get_item(item["id"], private=True, conn=conn, for_update=True)
        if (current is not None and current["shop_id"] == shop["id"] and current["product_id"] == product["id"]
                and current["fingerprint"] == item["fingerprint"] and current["sync_status"] == "pending"):
            store.patch_item(item["id"], {"error_code": error.code, "error_message": str(error)},
                             event="listing_retry_pending", conn=conn)
    return _result(item["id"], error=error)


def _confirm_listing(items, shop, product, facts, results):
    missing = []
    for item in items:
        fact = facts.by_material.get(item["fingerprint"])
        if fact is None:
            missing.append(item)
            continue
        try:
            with jobs.transaction() as conn:
                _same_shop(shop, conn=conn)
                _same_product(shop, product, conn=conn)
                confirmed = _confirm(item, shop, product, fact, archive=True, conn=conn)
            results[item["id"]] = _result(item["id"], confirmed["status"])
        except SalesError as error:
            results[item["id"]] = _record_listing_error(item, shop, product, error)
    return missing


def execute_listing(shop_id, product_id, item_ids):
    requested = jobs.ids(item_ids)
    shop = require_shop(shop_id)
    product = _product(shop_id, product_id)
    target = binding(shop, product)
    snapshot = {item["id"]: item for item in store.get_items(requested, private=True)}
    pending = []
    results = {}
    for item_id in requested:
        item = snapshot.get(item_id)
        if item is None or (item["shop_id"], item["product_id"]) != (shop_id, product_id) or not item["fingerprint"]:
            results[item_id] = _result(item_id, error=SalesError("listing_intent_missing", "找不到原上架意图", 409))
        elif item.get("external_inventory_id") or item.get("order_ref"):
            results[item_id] = _result(item_id, item["status"])
        elif not item.get("listing_binding"):
            results[item_id] = _result(item_id, error=SalesError("listing_intent_missing", "找不到原上架意图", 409))
        elif item["listing_binding"] != target:
            error = SalesError("listing_target_changed", "原上架商品或商户标识已变更", 409)
            results[item_id] = _record_listing_error(item, shop, product, error)
        else:
            pending.append(item)
    if pending:
        _execute_pending(pending, shop, product, results)
    archives = process_archives(item_ids=requested)
    archive_issues = {row["id"]: row for row in archives["items"] if row["error_code"]}
    for item_id, issue in archive_issues.items():
        if item_id in results:
            results[item_id].update(archive_error_code=issue["error_code"], archive_message=issue["message"])
    result = _summary([results[item_id] for item_id in requested],
                      archived_count=archives["archived_count"], archive_failed_count=archives["failed_count"])
    if archive_issues and not result["failed_count"]:
        result.update(error_code=archives["error_code"], error_message=archives["error_message"])
    return result


def _execute_pending(pending, shop, product, results):
    try:
        adapter, _ = _checked_adapter(shop)
    except SalesError as error:
        _store_shop_error(shop, error)
        for item in pending:
            results[item["id"]] = _record_listing_error(item, shop, product, error)
        if error.code == "shop_identity_mismatch":
            raise
        return
    jobs.checkpoint()
    try:
        products = adapter.products()
        if not any(row["external_product_id"] == product["external_product_id"]
                   and row["goods_key"] == product["goods_key"] for row in products):
            raise SalesError("listing_target_changed", "店铺商品与冻结目标不一致", 409)
        facts = _inventory_facts(adapter, product)
    except SalesError as error:
        for item in pending:
            results[item["id"]] = _record_listing_error(item, shop, product, error)
        return
    missing = _confirm_listing(pending, shop, product, facts, results)
    for group in jobs.chunks(missing):
        _import_missing(group, shop, product, adapter, results)


def _import_missing(group, shop, product, adapter, results):
    candidates = []
    lines = []
    with jobs.transaction() as conn:
        _same_shop(shop, conn=conn)
        _same_product(shop, product, conn=conn)
        for item in group:
            current = store.get_item(item["id"], private=True, conn=conn, for_update=True)
            if (current and current["sync_status"] == "pending" and current["status"] != "sold"
                    and current.get("listing_binding") == item["listing_binding"]):
                try:
                    lines.append(_frozen_material(current))
                except SalesError as error:
                    results[item["id"]] = _result(item["id"], error=error)
                else:
                    candidates.append(current)
            elif current and (current.get("external_inventory_id") or current.get("order_ref")):
                results[item["id"]] = _result(item["id"], current["status"])
            else:
                results[item["id"]] = _result(item["id"], error=SalesError("listing_intent_changed", "原上架意图已变化", 409))
    jobs.checkpoint()
    if not candidates:
        return
    write_error = None
    try:
        adapter.import_inventory(product["external_product_id"], lines)
    except SalesError as error:
        write_error = error
    try:
        facts = _inventory_facts(adapter, product)
    except SalesError as error:
        for item in candidates:
            results[item["id"]] = _record_listing_error(item, shop, product, error)
        return
    missing = _confirm_listing(candidates, shop, product, facts, results)
    error = write_error or SalesError("listing_inventory_unconfirmed", "店铺回读尚未确认此条库存，请重试", 409)
    for item in missing:
        results[item["id"]] = _record_listing_error(item, shop, product, error)


def _archive_item(item, current_owner):
    item_id = item["id"]
    with jobs.transaction() as conn:
        shop = require_shop(item["shop_id"], conn=conn) if item["shop_id"] else None
        if shop:
            _same_shop(shop, conn=conn)
        item = store.get_item(item_id, private=True, conn=conn, for_update=True)
        if item is None or not item["archive_pending"]:
            return None
        if item["shop_id"] != (shop["id"] if shop else None):
            return None
        if not shop and item.get("archive_owner_id") != current_owner:
            return None
    try:
        source = _source(item["source_id"])
        found = next((row for row in source.accounts([item["account_id"]]) if row["id"] == item["account_id"]), None)
        if found is None:
            raise _missing_account()
        if not found["archived"]:
            jobs.checkpoint()
            if source.archive(item["account_id"]) is not True:
                raise SalesError("source_archive_unconfirmed", "来源账号归档状态尚未确认", 409)
    except SalesError as issue:
        error = issue
        changes = {"error_code": error.code, "error_message": str(error)}
        event = "archive_retry_pending"
    else:
        error = None
        changes = {"archived": True, "archive_pending": False, "archive_owner_id": "", "error_code": "", "error_message": ""}
        event = "archive_confirmed"
    with jobs.transaction() as conn:
        if shop:
            _same_shop(shop, conn=conn)
        current = store.get_item(item_id, private=True, conn=conn, for_update=True)
        if current is None or (error and not current["archive_pending"]):
            return None
        store.patch_item(item_id, changes, event=event, conn=conn)
    return _result(item_id, "archived" if error is None else "", error)


def process_archives(*, limit=100, item_ids=None):
    current_owner = require_executor()
    items = (store.list_archive_pending(limit=limit, owner_id=current_owner) if item_ids is None
             else store.get_items(item_ids))
    results = []
    for item in items:
        jobs.checkpoint()
        try:
            result = _archive_item(item, current_owner)
        except SalesError as error:
            result = _result(item["id"], error=error)
        if result is not None:
            results.append(result)
    return _summary(results, archived_count=sum(row["status"] == "archived" for row in results))


def execute_sync(shop_id):
    from .history import synchronize

    return synchronize(shop_id)


list_jobs = jobs.list_jobs
