"""完整交付资料与外部库存、订单的精确匹配。"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

from .errors import SalesError


def email_key(value):
    return str(value or "").strip().casefold()


def delivery_email(line):
    parts = line.split("----") if isinstance(line, str) else []
    if len(parts) != 3 or any(not part.strip() for part in parts):
        return ""
    if any(char in line for char in ("\r", "\n", "\x00", "\u0085", "\u2028", "\u2029")):
        return ""
    email = email_key(parts[0])
    return email if "@" in email else ""


def account_material(account):
    line = account.get("delivery_line")
    email = delivery_email(line)
    if not email:
        raise SalesError("listing_material_incomplete", "交付资料须包含单行邮箱、密码和 2FA 密钥")
    if email != email_key(account.get("email")):
        raise SalesError("listing_material_email_mismatch", "交付邮箱与来源账号邮箱不一致", 409)
    return line


def fingerprint(line):
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


@dataclass
class InventoryFact:
    inventory_rows: dict = field(default_factory=dict)
    orders: dict = field(default_factory=dict)

    def confirmable(self):
        if len(self.inventory_rows) > 1:
            raise SalesError("listing_inventory_conflict", "同一交付资料在本商品下有多条库存", 409)
        if len(self.orders) > 1:
            raise SalesError("listing_order_conflict", "同一交付资料对应多笔已交付订单", 409)
        inventory_id, status = next(iter(self.inventory_rows.items()), ("", ""))
        order = next(iter(self.orders.values()), None)
        return inventory_id, status == "sold" or order is not None, order


class ShopFacts:
    def __init__(self, product, inventory, orders):
        self.by_material = defaultdict(InventoryFact)
        self.lines = {}
        self.invalid_inventory_ids = []
        self.by_inventory_id = {}
        for row in inventory:
            inventory_id = row["external_inventory_id"]
            self.by_inventory_id[inventory_id] = row["content"]
            self._inventory(row)
        for order in orders:
            if order["goods_key"] == product["goods_key"] and order["status"] in {"paid", "refunded"}:
                for line in order["cards"]:
                    if delivery_email(line):
                        key = fingerprint(line)
                        self.lines[key] = line
                        self.by_material[key].orders[order["order_ref"]] = order

    def _inventory(self, row):
        line = row["content"]
        if not delivery_email(line):
            self.invalid_inventory_ids.append(row["external_inventory_id"])
            return
        key = fingerprint(line)
        self.lines[key] = line
        self.by_material[key].inventory_rows[row["external_inventory_id"]] = row["status"]
