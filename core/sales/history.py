"""店铺历史库存和订单同步。"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from . import jobs, matching, service, store
from .errors import SalesError


def _read_sources(emails):
    """每个邮箱需要所有启用来源完成查询才可判为全局唯一。"""
    candidates = defaultdict(dict)
    unavailable = set()
    if not emails:
        return candidates, unavailable
    sources = [row for row in store.list_sources() if row["enabled"]]
    if not sources:
        return candidates, set(emails)
    for source in sources:
        try:
            client = service.account_source(source)
        except SalesError:
            unavailable.update(emails)
            continue
        for group in jobs.chunks(sorted(emails)):
            jobs.checkpoint()
            try:
                accounts = client.find_accounts(group)
            except SalesError:
                unavailable.update(group)
                continue
            for account in accounts:
                email = matching.email_key(account.get("email"))
                if email not in emails:
                    continue
                try:
                    line = matching.account_material(account)
                except SalesError:
                    continue
                candidates[matching.fingerprint(line)][(source["id"], account["id"])] = account
    return candidates, unavailable


def _add_historical_item(key, email, candidates, unavailable, shop, product, line, *, conn):
    if email in unavailable:
        raise SalesError("source_match_unavailable", "部分启用来源未完成查询，无法确认唯一账号", 409)
    matches = candidates.get(key, {})
    if not matches:
        raise SalesError("source_match_not_found", "启用来源中没有完全匹配的账号", 404)
    if len(matches) > 1:
        raise SalesError("source_match_ambiguous", "完整资料对应多个来源账号", 409)
    (source_id, account_id), account = next(iter(matches.items()))
    jobs.lock(conn, "source-settings")
    service._source_record(source_id, conn=conn)
    item = store.add_item(
        source_id=source_id, account_id=account_id, email=account["email"], plan=account.get("plan", ""), conn=conn,
    )
    existing = store.get_item(item["id"], private=True, conn=conn, for_update=True)
    if existing["fingerprint"]:
        if existing["fingerprint"] != key:
            raise SalesError("listing_material_changed", "历史库存材料与账号已有销售归属冲突", 409)
        if (existing["shop_id"], existing["product_id"]) != (shop["id"], product["id"]):
            raise SalesError("listing_target_immutable", "历史库存与账号已有上架目标冲突", 409)
        return existing
    store.freeze_listing(
        item["id"], shop_id=shop["id"], product_id=product["id"], fingerprint=key,
        delivery_ciphertext=service._encrypt(line), historical=True, conn=conn,
    )
    return store.get_item(item["id"], private=True, conn=conn)


def _existing_mapping(shop, product, key, inventory_id, known_by_fingerprint, known_by_inventory):
    by_inventory = known_by_inventory.get(inventory_id)
    by_material = known_by_fingerprint.get(key)
    if by_inventory and (by_inventory.get("fingerprint") != key or by_inventory["product_id"] != product["id"]):
        raise SalesError("listing_inventory_conflict", "库存编号与已有交付资料或商品冲突", 409)
    if by_material and (by_material["shop_id"], by_material["product_id"]) != (shop["id"], product["id"]):
        raise SalesError("listing_fingerprint_conflict", "相同交付资料已有另一处店铺或商品归属", 409)
    return by_inventory or by_material


def _confirm_history(shop, product, facts, by_fingerprint, by_inventory, candidates, unavailable, repeated):
    results = []
    for inventory_id in facts.invalid_inventory_ids:
        error = SalesError("listing_material_incomplete", "库存没有完整单行交付资料", 409)
        results.append(service._result(None, error=error, product_id=product["id"], external_inventory_id=inventory_id))
    for key, fact in facts.by_material.items():
        inventory_id = next(iter(fact.inventory_rows), "")
        item = None
        try:
            if key in repeated:
                raise SalesError("listing_fingerprint_conflict", "相同交付资料同时出现在多个商品", 409)
            fact.confirmable()
            line = facts.lines[key]
            with jobs.transaction() as conn:
                service._same_shop(shop, conn=conn)
                service._same_product(shop, product, conn=conn)
                item = _existing_mapping(shop, product, key, inventory_id, by_fingerprint, by_inventory)
                if item is None:
                    item = _add_historical_item(
                        key, matching.delivery_email(line), candidates, unavailable, shop, product, line, conn=conn,
                    )
                # 明确提交的新上架意图即使先由周期同步发现，也须保留归档义务。
                frozen_target = item.get("listing_binding")
                if frozen_target and frozen_target != service.binding(shop, product):
                    raise SalesError("listing_target_changed", "库存所属商品与原上架商品标识不一致", 409)
                archive = bool(frozen_target) and item["sync_status"] in {"pending", "paused"}
                confirmed = service._confirm(item, shop, product, fact, archive=archive, conn=conn)
        except SalesError as error:
            results.append(service._result(item["id"] if item else None, error=error,
                                           product_id=product["id"], external_inventory_id=inventory_id))
        else:
            results.append(service._result(confirmed["id"], confirmed["status"], product_id=product["id"],
                                           external_inventory_id=inventory_id))
    return results


def _order_changes(shop, orders, products, matches):
    """已关联订单可独立观察退款等状态，保留原交付事实。"""
    by_order = {row["order_ref"]: row for row in orders}
    product_keys = {product["id"]: product["goods_key"] for product in products}
    for item in matches:
        order = by_order.get(item["order_ref"])
        if not order or order["goods_key"] != product_keys.get(item["product_id"]):
            continue
        with jobs.transaction() as conn:
            service._same_shop(shop, conn=conn)
            service._record_order(item, shop, order, conn=conn)


def _reconcile(shop, products, observations, orders):
    inventory_ids = {inventory_id for facts in observations.values() for inventory_id in facts.by_inventory_id}
    by_product = defaultdict(set)
    for product_id, facts in observations.items():
        for key in facts.by_material:
            by_product[key].add(product_id)
    known = store.find_inventory_items(
        shop["id"], inventory_ids=list(inventory_ids), fingerprints=list(by_product),
        order_refs=[order["order_ref"] for order in orders],
    )
    by_inventory = {row["external_inventory_id"]: row for row in known
                    if row["shop_id"] == shop["id"] and row.get("external_inventory_id")}
    by_fingerprint = {row["fingerprint"]: row for row in known if row.get("fingerprint")}
    emails = {
        matching.delivery_email(line) for facts in observations.values() for key, line in facts.lines.items()
        if key not in by_fingerprint and len(by_product[key]) == 1
    }
    candidates, unavailable = _read_sources(emails)
    repeated = {key for key, product_ids in by_product.items() if len(product_ids) > 1}
    results = []
    for product in products:
        product_id = product["id"]
        if product_id not in observations:
            continue
        results.extend(_confirm_history(
            shop, product, observations[product_id], by_fingerprint, by_inventory, candidates, unavailable, repeated,
        ))
    _order_changes(shop, orders, products, known)
    return results


def synchronize(shop_id):
    shop = service.require_shop(shop_id)
    try:
        adapter, info = service._checked_adapter(shop)
        products = adapter.products()
        jobs.checkpoint()
        orders = adapter.orders()
        shop = service._refresh_products(shop, info, products)
    except SalesError as error:
        service._store_shop_error(shop, error)
        raise

    observed_ids = {product["external_product_id"] for product in products}
    products = [product for product in store.list_products(shop_id) if product["external_product_id"] in observed_ids]
    observations = {}
    errors = []
    for product in products:
        jobs.checkpoint()
        try:
            inventory = adapter.inventory(product["external_product_id"])
        except SalesError as error:
            errors.append(service._result(None, error=error, product_id=product["id"]))
        else:
            observations[product["id"]] = matching.ShopFacts(product, inventory, orders)
    results = errors + _reconcile(shop, products, observations, orders)
    with jobs.transaction() as conn:
        service._same_shop(shop, conn=conn)
        updates = {"error_code": "", "error_message": ""}
        if errors:
            updates.update(error_code=errors[0]["error_code"], error_message=errors[0]["message"])
        else:
            updates["last_synced_at"] = datetime.now(timezone.utc)
        store.patch_shop(shop_id, updates, conn=conn)
    return service._summary(results, product_count=len(products), order_count=len({order["order_ref"] for order in orders}))
