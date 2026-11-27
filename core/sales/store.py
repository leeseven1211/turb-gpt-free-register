# -*- coding: utf-8 -*-
"""账号贩卖区 PostgreSQL 仓储。

销售数据独立使用当前 PostgreSQL schema。所有公开投影都通过本模块明确列出，
避免把交付材料和指纹意外返回给 WebUI。
"""
from __future__ import annotations

import json
import re
import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from core.storage import postgres as postgres_store
from core.storage import records

from .errors import SalesError


_LOCK = threading.RLock()
_READY_KEYS: set[str] = set()
_SOURCE_ID_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
_SOURCE_FIELDS = {"id", "name", "kind", "base_url", "auth_env", "enabled"}
_SHOP_FIELDS = {
    "name", "platform", "base_url", "token_env", "external_shop_id", "enabled",
    "owner_id", "sync_interval", "last_synced_at", "error_code", "error_message",
}
_ITEM_FIELDS = {
    "status", "shop_id", "product_id", "external_inventory_id", "order_ref",
    "order_amount", "currency", "channel", "price", "sold_at", "paid_at", "note",
    "archived", "archive_pending", "sync_status", "error_code", "error_message",
    "order_status", "archive_owner_id",
}
_PUBLIC_ITEM_FIELDS = (
    "id", "source_id", "account_id", "email", "plan", "status", "shop_id",
    "product_id", "shop_name", "product_name", "external_inventory_id", "order_ref",
    "order_amount", "currency", "channel", "price", "sold_at", "paid_at", "note",
    "listed_at", "archived", "archive_pending", "sync_status", "error_code",
    "error_message", "order_status", "created_at", "updated_at",
)


def _table(name: str) -> str:
    return postgres_store.qualified(name)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _public_row(row: dict[str, Any], *, private: bool = False) -> dict[str, Any]:
    result = {field: _json_value(row.get(field)) for field in _PUBLIC_ITEM_FIELDS}
    if private:
        result["fingerprint"] = row.get("fingerprint")
        result["delivery_ciphertext"] = row.get("delivery_ciphertext")
        result["archive_owner_id"] = row.get("archive_owner_id")
        result["listing_binding"] = row.get("listing_binding") or {}
    return result


def _public_source(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(row.get(key)) for key in (
        "id", "name", "kind", "base_url", "auth_env", "enabled",
        "created_at", "updated_at",
    )}


def _public_shop(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(row.get(key)) for key in (
        "id", "name", "platform", "base_url", "token_env", "external_shop_id",
        "enabled", "owner_id", "sync_interval", "last_synced_at", "error_code",
        "error_message", "created_at", "updated_at",
    )}


def _public_product(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(row.get(key)) for key in (
        "id", "shop_id", "external_product_id", "goods_key", "name", "status", "price",
        "created_at", "updated_at",
    )}


@contextmanager
def _tx(conn=None):
    init()
    if conn is not None:
        yield conn
        return
    with records.transaction() as own:
        yield own


def _validate_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise SalesError("invalid_field", f"{name} 必须是布尔值")
    return value


def _error(code: str, message: str, status: int = 400) -> SalesError:
    error = SalesError(code, message, status)
    if not hasattr(error, "message"):
        error.message = message
    return error


def _item_sql(*, private: bool = True) -> str:
    columns = ", ".join(f"i.{field}" for field in (
        "id", "source_id", "account_id", "email", "plan", "status", "shop_id",
        "product_id", "external_inventory_id", "order_ref", "order_amount",
        "currency", "channel", "price", "sold_at", "paid_at", "note", "listed_at",
        "archived", "archive_pending", "sync_status", "error_code", "error_message",
        "created_at", "updated_at", "fingerprint", "delivery_ciphertext", "order_status",
        "archive_owner_id", "listing_binding",
    ))
    if not private:
        columns = ", ".join(
            f"i.{field}" for field in (
                "id", "source_id", "account_id", "email", "plan", "status", "shop_id",
                "product_id", "external_inventory_id", "order_ref", "order_amount",
                "currency", "channel", "price", "sold_at", "paid_at", "note", "listed_at",
                "archived", "archive_pending", "sync_status", "error_code",
                "error_message", "created_at", "updated_at", "order_status",
                "archive_owner_id", "listing_binding",
            )
        )
    return (
        f"SELECT {columns}, s.name AS shop_name, p.name AS product_name "
        f"FROM {_table('sales_items')} i "
        f"LEFT JOIN {_table('sales_shops')} s ON s.id=i.shop_id "
        f"LEFT JOIN {_table('sales_products')} p ON p.id=i.product_id "
    )


def init() -> None:
    """在当前数据库/schema 中幂等创建销售表，并确保内置 local 来源存在。"""
    url = postgres_store.database_url()
    if not url:
        raise RuntimeError("sales_store 需要配置可用的 DATABASE_URL")
    postgres_store._guard_production_database(url)
    key = f"{url}::{postgres_store.schema_name()}"
    with _LOCK:
        if key in _READY_KEYS:
            return
        with records.transaction() as conn:
            schema = postgres_store.quote_identifier(postgres_store.schema_name())
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"sales-schema:{postgres_store.schema_name()}",),
                )
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {_table('sales_sources')} (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        kind TEXT NOT NULL CHECK (kind IN ('local', 'remote')),
                        base_url TEXT NOT NULL DEFAULT '',
                        auth_env TEXT NOT NULL DEFAULT '',
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {_table('sales_shops')} (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        platform TEXT NOT NULL DEFAULT 'liandong',
                        base_url TEXT NOT NULL DEFAULT 'https://wzyp.cn',
                        token_env TEXT NOT NULL DEFAULT '',
                        external_shop_id TEXT NOT NULL DEFAULT '',
                        enabled BOOLEAN NOT NULL DEFAULT FALSE,
                        owner_id TEXT NOT NULL DEFAULT 'local',
                        sync_interval INTEGER NOT NULL DEFAULT 60 CHECK (sync_interval > 0),
                        last_synced_at TIMESTAMPTZ,
                        error_code TEXT NOT NULL DEFAULT '',
                        error_message TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {_table('sales_products')} (
                        id BIGSERIAL PRIMARY KEY,
                        shop_id BIGINT NOT NULL REFERENCES {_table('sales_shops')}(id) ON DELETE CASCADE,
                        external_product_id TEXT NOT NULL,
                        goods_key TEXT NOT NULL DEFAULT '',
                        name TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'active',
                        price NUMERIC,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        UNIQUE (shop_id, external_product_id)
                    )
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {_table('sales_items')} (
                        id BIGSERIAL PRIMARY KEY,
                        source_id TEXT NOT NULL REFERENCES {_table('sales_sources')}(id),
                        account_id BIGINT NOT NULL,
                        email TEXT NOT NULL DEFAULT '',
                        plan TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'for_sale'
                            CHECK (status IN ('for_sale', 'listed', 'sold')),
                        shop_id BIGINT REFERENCES {_table('sales_shops')}(id),
                        product_id BIGINT REFERENCES {_table('sales_products')}(id),
                        external_inventory_id TEXT NOT NULL DEFAULT '',
                        order_ref TEXT NOT NULL DEFAULT '',
                        order_amount NUMERIC,
                        currency TEXT NOT NULL DEFAULT 'CNY',
                        channel TEXT NOT NULL DEFAULT '',
                        price NUMERIC,
                        sold_at TIMESTAMPTZ,
                        paid_at TIMESTAMPTZ,
                        note TEXT NOT NULL DEFAULT '',
                        listed_at TIMESTAMPTZ,
                        archived BOOLEAN NOT NULL DEFAULT FALSE,
                        archive_pending BOOLEAN NOT NULL DEFAULT FALSE,
                        sync_status TEXT NOT NULL DEFAULT 'idle',
                        error_code TEXT NOT NULL DEFAULT '',
                        error_message TEXT NOT NULL DEFAULT '',
                        order_status TEXT NOT NULL DEFAULT '',
                        archive_owner_id TEXT NOT NULL DEFAULT '',
                        listing_binding JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        fingerprint TEXT,
                        delivery_ciphertext TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        UNIQUE (source_id, account_id)
                    )
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {_table('sales_item_events')} (
                        id BIGSERIAL PRIMARY KEY,
                        item_id BIGINT NOT NULL REFERENCES {_table('sales_items')}(id) ON DELETE CASCADE,
                        event TEXT NOT NULL,
                        changes JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute(f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS sales_items_fingerprint_uq
                    ON {_table('sales_items')} (fingerprint)
                    WHERE fingerprint IS NOT NULL AND fingerprint <> ''
                """)
                cur.execute(f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS sales_items_inventory_uq
                    ON {_table('sales_items')} (shop_id, external_inventory_id)
                    WHERE shop_id IS NOT NULL AND external_inventory_id <> ''
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS sales_items_status_idx
                    ON {_table('sales_items')} (status, id)
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS sales_items_archive_pending_idx
                    ON {_table('sales_items')} (archive_pending, id)
                """)
                cur.execute(f"""
                    INSERT INTO {_table('sales_sources')}
                        (id, name, kind, base_url, auth_env, enabled)
                    VALUES ('local', '本地账号', 'local', '', '', TRUE)
                    ON CONFLICT (id) DO NOTHING
                """)
        _READY_KEYS.add(key)


def reset_ready() -> None:
    """清除初始化缓存，供切换测试 schema 后重新建表。"""
    with _LOCK:
        _READY_KEYS.clear()


def list_sources() -> list[dict]:
    init()
    with records.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table('sales_sources')} ORDER BY id")
        return [_public_source(row) for row in cur.fetchall()]


def save_source(data: dict, *, conn=None) -> dict:
    if not isinstance(data, dict):
        raise _error("invalid_field", "来源数据必须是对象")
    source_id = str(data.get("id") or "").strip().lower()
    if not _SOURCE_ID_RE.fullmatch(source_id):
        raise _error("invalid_source_id", "来源 id 只能包含小写字母、数字、下划线和短横线")
    kind = str(data.get("kind") or ("local" if source_id == "local" else "remote"))
    if kind not in {"local", "remote"}:
        raise _error("invalid_field", "来源 kind 必须是 local 或 remote")
    unknown = set(data) - _SOURCE_FIELDS
    if unknown:
        raise _error("invalid_field", f"不支持的来源字段: {sorted(unknown)[0]}")
    enabled = data.get("enabled", True)
    _validate_bool("enabled", enabled)
    with _tx(conn) as tx, tx.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {_table('sales_sources')}
                (id, name, kind, base_url, auth_env, enabled, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET
                name=EXCLUDED.name, kind=EXCLUDED.kind, base_url=EXCLUDED.base_url,
                auth_env=EXCLUDED.auth_env, enabled=EXCLUDED.enabled, updated_at=now()
            RETURNING *
            """,
            (
                source_id, str(data.get("name") or source_id), kind,
                str(data.get("base_url") or ""), str(data.get("auth_env") or ""), enabled,
            ),
        )
        return _public_source(cur.fetchone())


def get_source(source_id: str, *, conn=None) -> dict | None:
    with _tx(conn) as tx, tx.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table('sales_sources')} WHERE id=%s", (source_id,))
        row = cur.fetchone()
        return _public_source(row) if row else None


def list_shops() -> list[dict]:
    init()
    with records.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table('sales_shops')} ORDER BY id")
        return [_public_shop(row) for row in cur.fetchall()]


def save_shop(data: dict, *, conn=None) -> dict:
    if not isinstance(data, dict):
        raise _error("invalid_field", "店铺数据必须是对象")
    enabled = data.get("enabled", False)
    _validate_bool("enabled", enabled)
    values = {
        "name": str(data.get("name") or ""),
        "platform": str(data.get("platform") or "liandong"),
        "base_url": str(data.get("base_url") or "https://wzyp.cn"),
        "token_env": str(data.get("token_env") or ""),
        "external_shop_id": str(data.get("external_shop_id") or ""),
        "enabled": enabled,
        "owner_id": str(data.get("owner_id") or "local"),
        "sync_interval": int(data.get("sync_interval", 60)),
    }
    if not values["name"]:
        raise _error("invalid_field", "店铺 name 不能为空")
    if values["sync_interval"] <= 0:
        raise _error("invalid_field", "sync_interval 必须大于 0")
    unknown = set(data) - (_SHOP_FIELDS | {"id"})
    if unknown:
        raise _error("invalid_field", f"不支持的店铺字段: {sorted(unknown)[0]}")
    with _tx(conn) as tx, tx.cursor() as cur:
        shop_id = data.get("id")
        if shop_id is None:
            cur.execute(
                f"""
                INSERT INTO {_table('sales_shops')}
                    (name, platform, base_url, token_env, external_shop_id, enabled,
                     owner_id, sync_interval)
                VALUES (%(name)s, %(platform)s, %(base_url)s, %(token_env)s, %(external_shop_id)s,
                        %(enabled)s, %(owner_id)s, %(sync_interval)s)
                RETURNING *
                """,
                values,
            )
        else:
            cur.execute(
                f"""
                UPDATE {_table('sales_shops')}
                SET name=%(name)s, platform=%(platform)s, base_url=%(base_url)s,
                    token_env=%(token_env)s, external_shop_id=%(external_shop_id)s,
                    enabled=%(enabled)s, owner_id=%(owner_id)s,
                    sync_interval=%(sync_interval)s, updated_at=now()
                WHERE id=%(id)s
                RETURNING *
                """,
                {**values, "id": int(shop_id)},
            )
        row = cur.fetchone()
        if not row:
            raise _error("shop_not_found", f"店铺不存在: {shop_id}")
        return _public_shop(row)


def get_shop(shop_id: int, *, conn=None) -> dict | None:
    with _tx(conn) as tx, tx.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table('sales_shops')} WHERE id=%s", (shop_id,))
        row = cur.fetchone()
        return _public_shop(row) if row else None


def patch_shop(shop_id: int, changes: dict, *, conn=None) -> dict:
    if not isinstance(changes, dict):
        raise _error("invalid_field", "店铺变更必须是对象")
    unknown = set(changes) - _SHOP_FIELDS
    if unknown:
        raise _error("invalid_field", f"不支持的店铺字段: {sorted(unknown)[0]}")
    if "enabled" in changes:
        _validate_bool("enabled", changes["enabled"])
    if not changes:
        row = get_shop(shop_id)
        if row is None:
            raise _error("shop_not_found", f"店铺不存在: {shop_id}", 404)
        return row
    with _tx(conn) as tx, tx.cursor() as cur:
        sets = []
        params: list[Any] = []
        for field, value in changes.items():
            if field == "sync_interval":
                value = int(value)
                if value <= 0:
                    raise _error("invalid_field", "sync_interval 必须大于 0")
            sets.append(f"{field}=%s")
            params.append(value)
        sets.append("updated_at=now()")
        params.append(shop_id)
        cur.execute(
            f"UPDATE {_table('sales_shops')} SET {', '.join(sets)} WHERE id=%s RETURNING *",
            params,
        )
        row = cur.fetchone()
        if not row:
            raise _error("shop_not_found", f"店铺不存在: {shop_id}", 404)
        return _public_shop(row)


def replace_products(shop_id: int, products: list[dict], *, conn=None) -> list[dict]:
    if not isinstance(products, list):
        raise _error("invalid_field", "商品必须是列表")
    with _tx(conn) as tx, tx.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {_table('sales_shops')} WHERE id=%s", (shop_id,))
        if cur.fetchone() is None:
            raise _error("shop_not_found", f"店铺不存在: {shop_id}", 404)
        external_ids = []
        for data in products:
            external_id = str(data.get("external_product_id") or "").strip()
            if not external_id:
                raise _error("invalid_field", "商品 external_product_id 不能为空")
            external_ids.append(external_id)
            cur.execute(
                f"""
                INSERT INTO {_table('sales_products')}
                    (shop_id, external_product_id, goods_key, name, status, price, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (shop_id, external_product_id) DO UPDATE SET
                    goods_key=EXCLUDED.goods_key, name=EXCLUDED.name, status=EXCLUDED.status,
                    price=EXCLUDED.price, updated_at=now()
                """,
                (
                    shop_id, external_id, str(data.get("goods_key") or ""),
                    str(data.get("name") or ""), str(data.get("status") or "active"),
                    data.get("price"),
                ),
            )
        if external_ids:
            cur.execute(
                f"""
                UPDATE {_table('sales_products')}
                SET status='unavailable', updated_at=now()
                WHERE shop_id=%s AND external_product_id <> ALL(%s)
                """,
                (shop_id, external_ids),
            )
        else:
            cur.execute(
                f"UPDATE {_table('sales_products')} SET status='unavailable', updated_at=now() WHERE shop_id=%s",
                (shop_id,),
            )
        cur.execute(f"SELECT * FROM {_table('sales_products')} WHERE shop_id=%s ORDER BY id", (shop_id,))
        return [_public_product(row) for row in cur.fetchall()]


def list_products(shop_id: int, *, conn=None) -> list[dict]:
    with _tx(conn) as tx, tx.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table('sales_products')} WHERE shop_id=%s ORDER BY id", (shop_id,))
        return [_public_product(row) for row in cur.fetchall()]


def get_product(product_id: int, *, conn=None) -> dict | None:
    with _tx(conn) as tx, tx.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table('sales_products')} WHERE id=%s", (product_id,))
        row = cur.fetchone()
        return _public_product(row) if row else None


def add_item(*, source_id: str, account_id: int, email: str, plan: str = "",
             note: str = "", conn=None) -> dict:
    with _tx(conn) as tx, tx.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {_table('sales_sources')} WHERE id=%s", (source_id,))
        if cur.fetchone() is None:
            raise _error("source_not_found", f"来源不存在: {source_id}", 404)
        records.advisory_xact_lock(tx, f"sales-item-identity:{source_id}:{int(account_id)}")
        cur.execute(
            f"""
            INSERT INTO {_table('sales_items')}
                (source_id, account_id, email, plan, note, updated_at)
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (source_id, account_id) DO NOTHING
            RETURNING id
            """,
            (source_id, int(account_id), str(email), str(plan), str(note)),
        )
        inserted = cur.fetchone()
        if inserted:
            item_id = inserted["id"]
        else:
            cur.execute(
                f"""
                SELECT id, status, shop_id, product_id, fingerprint, delivery_ciphertext
                FROM {_table('sales_items')}
                WHERE source_id=%s AND account_id=%s
                FOR UPDATE
                """,
                (source_id, int(account_id)),
            )
            existing = cur.fetchone()
            item_id = existing["id"]
            if (
                existing["status"] == "for_sale"
                and not existing["shop_id"]
                and not existing["product_id"]
                and not existing["fingerprint"]
                and not existing["delivery_ciphertext"]
            ):
                cur.execute(
                    f"""
                    UPDATE {_table('sales_items')}
                    SET email=%s, plan=%s, note=%s, updated_at=now()
                    WHERE id=%s
                    """,
                    (str(email), str(plan), str(note), item_id),
                )
        return _get_item_with_cursor(cur, item_id, private=False)


def _get_item_with_cursor(cur, item_id: int, *, private: bool = False, for_update: bool = False):
    sql = _item_sql(private=private) + "WHERE i.id=%s"
    if for_update:
        sql += " FOR UPDATE OF i"
    cur.execute(sql, (item_id,))
    row = cur.fetchone()
    return _public_row(row, private=private) if row else None


def get_item(
    item_id: int,
    *,
    private: bool = False,
    conn=None,
    for_update: bool = False,
) -> dict | None:
    with _tx(conn) as tx, tx.cursor() as cur:
        return _get_item_with_cursor(cur, item_id, private=private, for_update=for_update)


def get_items(item_ids: list[int], *, private: bool = False, conn=None) -> list[dict]:
    if not item_ids:
        return []
    with _tx(conn) as tx, tx.cursor() as cur:
        sql = _item_sql(private=private) + "WHERE i.id = ANY(%s) ORDER BY i.id"
        cur.execute(sql, (item_ids,))
        return [_public_row(row, private=private) for row in cur.fetchall()]


def list_items(*, page: int = 1, page_size: int = 20, status: str = "",
               shop_id: int | None = None, source_id: str = "", q: str = "") -> dict:
    init()
    page = max(1, int(page))
    page_size = min(200, max(1, int(page_size)))
    clauses = ["TRUE"]
    params: list[Any] = []
    count_clauses = ["TRUE"]
    count_params: list[Any] = []
    if status:
        if status not in {"for_sale", "listed", "sold"}:
            raise _error("invalid_status", f"未知销售状态: {status}")
        clauses.append("i.status=%s")
        params.append(status)
    if shop_id is not None:
        clauses.append("i.shop_id=%s")
        params.append(int(shop_id))
        count_clauses.append("i.shop_id=%s")
        count_params.append(int(shop_id))
    if source_id:
        clauses.append("i.source_id=%s")
        params.append(source_id)
        count_clauses.append("i.source_id=%s")
        count_params.append(source_id)
    if q:
        clauses.append("(i.email ILIKE %s OR i.source_id ILIKE %s OR i.order_ref ILIKE %s OR COALESCE(s.name,'') ILIKE %s OR COALESCE(p.name,'') ILIKE %s)")
        pattern = f"%{q}%"
        params.extend([pattern] * 5)
        count_clauses.append(clauses[-1])
        count_params.extend([pattern] * 5)
    where = " AND ".join(clauses)
    count_where = " AND ".join(count_clauses)
    with records.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS n FROM {_table('sales_items')} i LEFT JOIN {_table('sales_shops')} s ON s.id=i.shop_id LEFT JOIN {_table('sales_products')} p ON p.id=i.product_id WHERE {where}", params)
        total = int(cur.fetchone()["n"])
        cur.execute(
            f"SELECT i.status, count(*) AS n FROM {_table('sales_items')} i LEFT JOIN {_table('sales_shops')} s ON s.id=i.shop_id LEFT JOIN {_table('sales_products')} p ON p.id=i.product_id WHERE {count_where} GROUP BY i.status",
            count_params,
        )
        counts = {"all": 0, "for_sale": 0, "listed": 0, "sold": 0}
        for row in cur.fetchall():
            counts[row["status"]] = int(row["n"])
            counts["all"] += int(row["n"])
        offset = (page - 1) * page_size
        cur.execute(
            _item_sql(private=False) + f"WHERE {where} ORDER BY i.id DESC LIMIT %s OFFSET %s",
            [*params, page_size, offset],
        )
        items = [_public_row(row) for row in cur.fetchall()]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "counts": counts}


def _insert_event(cur, item_id: int, event: str, changes: dict) -> None:
    cur.execute(
        f"INSERT INTO {_table('sales_item_events')} (item_id, event, changes) VALUES (%s, %s, %s::jsonb)",
        (item_id, event or "patch", json.dumps(changes, default=_json_value, ensure_ascii=False)),
    )


def patch_item(item_id: int, changes: dict, *, event: str = "", conn=None) -> dict:
    if not isinstance(changes, dict):
        raise _error("invalid_field", "条目变更必须是对象")
    unknown = set(changes) - _ITEM_FIELDS
    if unknown:
        raise _error("invalid_field", f"不支持的条目字段: {sorted(unknown)[0]}")
    with _tx(conn) as tx, tx.cursor() as cur:
        current = _get_item_with_cursor(cur, item_id, private=True, for_update=True)
        if current is None:
            raise _error("item_not_found", f"条目不存在: {item_id}", 404)
        if current["status"] == "sold" and changes.get("status") not in (None, "sold"):
            has_external_evidence = any(
                current.get(field)
                for field in ("external_inventory_id", "order_ref", "order_amount", "paid_at", "order_status")
            )
            if has_external_evidence:
                raise _error("sold_status_immutable", "已有外部销售事实的条目不能降级")
            changes = {**changes, "sold_at": None}
        if current.get("fingerprint"):
            if "shop_id" in changes and changes["shop_id"] != current["shop_id"]:
                raise _error("listing_target_immutable", "已冻结条目不能改派店铺")
            if "product_id" in changes and changes["product_id"] != current["product_id"]:
                raise _error("listing_target_immutable", "已冻结条目不能改派商品")
            if (
                "external_inventory_id" in changes
                and changes["external_inventory_id"] != current["external_inventory_id"]
            ):
                raise _error("external_inventory_immutable", "已有外部库存映射不能改写")
        if "status" in changes and changes["status"] not in {"for_sale", "listed", "sold"}:
            raise _error("invalid_status", f"未知销售状态: {changes['status']}")
        if "archived" in changes:
            _validate_bool("archived", changes["archived"])
        if "archive_pending" in changes:
            _validate_bool("archive_pending", changes["archive_pending"])
        if "status" in changes and changes["status"] in {"listed", "sold"} and "archive_pending" not in changes:
            changes = {**changes, "archive_pending": True}
        if not changes:
            return _public_row(current)
        sets = [f"{key}=%s" for key in changes]
        params = list(changes.values())
        sets.append("updated_at=now()")
        params.append(item_id)
        cur.execute(f"UPDATE {_table('sales_items')} SET {', '.join(sets)} WHERE id=%s", params)
        _insert_event(cur, item_id, event, changes)
        return _get_item_with_cursor(cur, item_id, private=False)


def freeze_listing(
    item_id: int,
    *,
    shop_id: int,
    product_id: int,
    fingerprint: str,
    delivery_ciphertext: str,
    binding: dict | None = None,
    historical: bool = False,
    conn=None,
) -> dict:
    fingerprint = str(fingerprint or "").strip()
    if not fingerprint:
        raise _error("invalid_field", "fingerprint 不能为空")
    if binding is not None:
        if not isinstance(binding, dict):
            raise _error("invalid_field", "listing binding 必须是对象")
        allowed_binding = {"external_shop_id", "external_product_id", "goods_key"}
        if set(binding) - allowed_binding:
            raise _error("invalid_field", "listing binding 包含不支持的字段")
        binding = {
            key: str(binding.get(key) or "")
            for key in allowed_binding
        }
        if not all(binding.values()):
            raise _error("invalid_field", "listing binding 字段必须完整")
    if historical and binding is not None:
        raise _error("invalid_field", "历史接管不能提供 listing binding")
    with _tx(conn) as tx, tx.cursor() as cur:
        row = _get_item_with_cursor(cur, item_id, private=True, for_update=True)
        if row is None:
            raise _error("item_not_found", f"条目不存在: {item_id}", 404)
        cur.execute(
            f"SELECT id FROM {_table('sales_products')} WHERE id=%s AND shop_id=%s",
            (product_id, shop_id),
        )
        if cur.fetchone() is None:
            raise _error("product_shop_mismatch", "商品不属于目标店铺")
        if row["status"] == "sold" and not historical:
            raise _error("sold_listing_immutable", "已售出条目不能再次上架")
        if historical:
            if any(row.get(field) for field in (
                "shop_id", "product_id", "external_inventory_id", "order_ref",
                "fingerprint", "delivery_ciphertext",
            )):
                raise _error("historical_listing_already_bound", "历史条目已有销售归属")
        if row.get("listing_binding") and binding and row["listing_binding"] != binding:
            raise _error("listing_binding_immutable", "已有商品绑定不能改写")
        same_target = row["shop_id"] == shop_id and row["product_id"] == product_id
        if row["status"] == "listed" and not same_target and not historical:
            raise _error("listing_target_immutable", "已上架条目不能改派店铺或商品")
        has_frozen_material = bool(row.get("fingerprint") or row.get("delivery_ciphertext"))
        if has_frozen_material and row["shop_id"] is not None and not same_target:
            raise _error("listing_target_immutable", "已有上架意图不能改派店铺或商品")
        if row.get("fingerprint") and row["fingerprint"] != fingerprint:
            raise _error("listing_material_immutable", "重跑不能替换原交付材料")
        effective_fingerprint = row.get("fingerprint") or fingerprint
        effective_ciphertext = (
            row.get("delivery_ciphertext")
            if row.get("delivery_ciphertext") is not None
            else delivery_ciphertext
        )
        records.advisory_xact_lock(tx, f"sales-fingerprint:{fingerprint}")
        cur.execute(
            f"SELECT id FROM {_table('sales_items')} WHERE fingerprint=%s AND id<>%s FOR UPDATE",
            (fingerprint, item_id),
        )
        if cur.fetchone() is not None:
            raise _error("listing_fingerprint_conflict", "交付材料指纹已被其他条目占用")
        cur.execute(
            f"""
            UPDATE {_table('sales_items')}
            SET shop_id=%s, product_id=%s, fingerprint=%s, delivery_ciphertext=%s,
                listing_binding=CASE WHEN listing_binding='{{}}'::jsonb THEN %s::jsonb ELSE listing_binding END,
                sync_status='pending', error_code='', error_message='', updated_at=now()
            WHERE id=%s
            """,
            (
                shop_id, product_id, effective_fingerprint, effective_ciphertext,
                json.dumps(binding or {}, ensure_ascii=False), item_id,
            ),
        )
        _insert_event(cur, item_id, "freeze_listing", {"shop_id": shop_id, "product_id": product_id})
        return _get_item_with_cursor(cur, item_id, private=False)


def confirm_inventory(item_id: int, *, shop_id: int, product_id: int,
                      external_inventory_id: str, sold: bool = False, order_ref: str = "",
                      order_amount: Any = None, currency: str = "CNY",
                      paid_at: Any = None, archive: bool = True, conn=None) -> dict:
    _validate_bool("sold", sold)
    _validate_bool("archive", archive)
    external_inventory_id = str(external_inventory_id or "").strip()
    # 订单回执可能只带订单号和卡片材料，库存接口没有逐行 ID 时允许空值；
    # 非空值仍受店铺范围唯一约束。
    with _tx(conn) as tx, tx.cursor() as cur:
        row = _get_item_with_cursor(cur, item_id, private=True, for_update=True)
        if row is None:
            raise _error("item_not_found", f"条目不存在: {item_id}", 404)
        if row["shop_id"] != shop_id or row["product_id"] != product_id:
            raise _error("listing_target_immutable", "确认目标与冻结目标不一致")
        if row["status"] == "sold" and not sold:
            sold = True
        current_inventory_id = str(row.get("external_inventory_id") or "")
        if current_inventory_id and external_inventory_id and current_inventory_id != external_inventory_id:
            raise _error("external_inventory_conflict", "条目已有不同的外部库存映射")
        effective_inventory_id = external_inventory_id or current_inventory_id
        current_order_ref = str(row.get("order_ref") or "")
        if current_order_ref and order_ref and current_order_ref != str(order_ref):
            raise _error("order_ref_conflict", "条目已有不同的订单号")
        effective_order_ref = current_order_ref or str(order_ref or "")
        effective_order_amount = (
            row.get("order_amount") if row.get("order_amount") is not None else order_amount
        )
        effective_paid_at = row.get("paid_at") or paid_at
        effective_currency = str(row.get("currency") or currency or "CNY")
        if effective_inventory_id:
            records.advisory_xact_lock(
                tx, f"sales-inventory:{shop_id}:{effective_inventory_id}"
            )
        cur.execute(
            f"""
            SELECT id FROM {_table('sales_items')}
            WHERE shop_id=%s AND external_inventory_id=%s AND external_inventory_id <> '' AND id<>%s
            FOR UPDATE
            """,
            (shop_id, effective_inventory_id, item_id),
        )
        if cur.fetchone() is not None:
            raise _error("external_inventory_conflict", "外部库存已映射到其他条目")
        now = _now()
        new_status = "sold" if sold else ("sold" if row["status"] == "sold" else "listed")
        sold_at = row["sold_at"] or (now if sold else None)
        listed_at = row["listed_at"] or now
        archive_pending = True if archive else bool(row["archive_pending"])
        cur.execute(
            f"""
            UPDATE {_table('sales_items')}
            SET status=%s, external_inventory_id=%s, order_ref=%s, order_amount=%s,
                currency=%s, paid_at=COALESCE(%s, paid_at),
                sold_at=%s, listed_at=%s, archive_pending=%s, sync_status='idle',
                error_code='', error_message='', updated_at=now()
            WHERE id=%s
            """,
            (
                new_status, effective_inventory_id, effective_order_ref, effective_order_amount,
                effective_currency, effective_paid_at, sold_at, listed_at, archive_pending, item_id,
            ),
        )
        _insert_event(cur, item_id, "confirm_inventory", {
            "external_inventory_id": external_inventory_id, "sold": sold, "archive": archive,
        })
        return _get_item_with_cursor(cur, item_id, private=False)


def list_archive_pending(*, limit: int = 100, owner_id: str | None = None) -> list[dict]:
    init()
    limit = max(1, min(1000, int(limit)))
    with records.transaction() as conn, conn.cursor() as cur:
        owner_clause = ""
        params: list[Any] = [limit]
        if owner_id:
            owner_clause = (
                " AND ((i.shop_id IS NULL AND i.archive_owner_id=%s)"
                " OR (i.shop_id IS NOT NULL AND s.owner_id=%s))"
            )
            params[0:0] = [owner_id, owner_id]
        cur.execute(
            _item_sql(private=False)
            + f"WHERE i.archive_pending=TRUE AND i.archived=FALSE{owner_clause} "
              "ORDER BY i.updated_at, i.id LIMIT %s",
            params,
        )
        return [_public_row(row) for row in cur.fetchall()]


def list_listing_pending(*, limit: int = 100, owner_id: str | None = None) -> list[dict]:
    init()
    limit = max(1, min(1000, int(limit)))
    with records.transaction() as conn, conn.cursor() as cur:
        owner_clause = ""
        params: list[Any] = [limit]
        if owner_id:
            owner_clause = "AND s.owner_id=%s"
            params.insert(0, owner_id)
        cur.execute(
            _item_sql(private=True)
            + f"""
            WHERE i.sync_status='pending'
              AND i.shop_id IS NOT NULL AND i.product_id IS NOT NULL
              AND NULLIF(i.fingerprint, '') IS NOT NULL
              AND NULLIF(i.delivery_ciphertext, '') IS NOT NULL
              AND i.status <> 'sold'
              {owner_clause if owner_clause else 'AND TRUE'}
            ORDER BY i.updated_at, i.id LIMIT %s
            """,
            params,
        )
        return [_public_row(row, private=True) for row in cur.fetchall()]


def list_events(item_id: int) -> list[dict]:
    init()
    with records.transaction() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT id, item_id, event, changes, created_at FROM {_table('sales_item_events')} WHERE item_id=%s ORDER BY id",
            (item_id,),
        )
        return [
            {
                "id": row["id"], "item_id": row["item_id"], "event": row["event"],
                "changes": row["changes"], "created_at": _iso(row["created_at"]),
            }
            for row in cur.fetchall()
        ]


def find_inventory_items(
    shop_id: int,
    *,
    inventory_ids: list[str] | None = None,
    fingerprints: list[str] | None = None,
    order_refs: list[str] | None = None,
    conn=None,
) -> list[dict]:
    """按外部回读材料批量查找条目，结果包含内部匹配所需私有字段。"""
    inventory_ids = [str(value) for value in (inventory_ids or []) if str(value)]
    fingerprints = [str(value) for value in (fingerprints or []) if str(value)]
    order_refs = [str(value) for value in (order_refs or []) if str(value)]
    if not inventory_ids and not fingerprints and not order_refs:
        return []
    with _tx(conn) as tx, tx.cursor() as cur:
        clauses: list[str] = []
        params: list[Any] = []
        if inventory_ids:
            clauses.append("(i.shop_id=%s AND i.external_inventory_id = ANY(%s))")
            params.extend([shop_id, inventory_ids])
        if order_refs:
            clauses.append("(i.shop_id=%s AND i.order_ref = ANY(%s))")
            params.extend([shop_id, order_refs])
        if fingerprints:
            clauses.append("i.fingerprint = ANY(%s)")
            params.append(fingerprints)
        cur.execute(
            _item_sql(private=True) + "WHERE " + " OR ".join(clauses) + " ORDER BY i.id",
            params,
        )
        return [_public_row(row, private=True) for row in cur.fetchall()]
