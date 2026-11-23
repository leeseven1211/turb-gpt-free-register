# -*- coding: utf-8 -*-
"""邮箱库存资格查询所需的 v2 表达式索引。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.storage import postgres as postgres_store


class InventoryIndexError(RuntimeError):
    """索引对象无法复用或最终校验失败。"""

    def __init__(self, code: str, index_name: str):
        self.code = code
        self.index_name = index_name
        super().__init__(
            f"{code}: 索引 {postgres_store.qualified(index_name)} 的定义或状态不符合预期"
        )


_BUTLER_PREDICATE = "(status <> ALL (ARRAY['prepared'::text, 'rejected'::text]))"
_BUTLER_EXPRESSION = (
    "lower(COALESCE(address_norm, ((data -> 'mailbox'::text) "
    "->> 'email'::text), ''::text))"
)


@dataclass(frozen=True)
class IndexSpec:
    """一个必须精确匹配的非唯一单表达式 Btree 索引。"""

    name: str
    table: str
    expression: str
    predicate: str | None = None
    collation_column: str = "email"


INDEX_SPECS: tuple[IndexSpec, ...] = (
    IndexSpec("idx_registered_accounts_email_lower", "registered_accounts", "lower(email)"),
    IndexSpec("idx_local_email_claims_address_norm_lower", "local_email_claims", "lower(address_norm)", collation_column="address_norm"),
    IndexSpec("idx_email_address_allocations_address_norm_lower", "email_address_allocations", "lower(address_norm)", collation_column="address_norm"),
    IndexSpec("idx_email_pool_outlook_email_lower", "email_pool_outlook", "lower(email)"),
    IndexSpec("idx_email_pool_generic_api_email_lower", "email_pool_generic_api", "lower(email)"),
    IndexSpec("idx_email_pool_domain_email_lower", "email_pool_domain", "lower(email)"),
    IndexSpec("idx_email_pool_icloud_hide_email_lower", "email_pool_icloud_hide", "lower(email)"),
    IndexSpec("idx_email_pool_butler_email_lower", "email_pool_butler", "lower(email)"),
    IndexSpec(
        "idx_email_butler_claim_intents_address_lower",
        "email_butler_claim_intents",
        _BUTLER_EXPRESSION,
        _BUTLER_PREDICATE,
        "address_norm",
    ),
)


def _row_value(row: Any, key: str, position: int):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    return row[position]


def _inspect_one(cur, spec: IndexSpec) -> dict:
    qualified_table = postgres_store.qualified(spec.table)
    cur.execute(
        """
        SELECT c.relkind, am.amname, i.indisunique, i.indisexclusion,
               i.indisvalid, i.indisready, i.indislive, i.indnkeyatts,
               i.indnatts, i.indkey::text, i.indoption::text,
               i.indpred IS NULL AS unfiltered,
               i.indrelid = to_regclass(%s) AS correct_table,
               CASE WHEN i.indexrelid IS NOT NULL
                    THEN pg_get_indexdef(c.oid, 1, false) END AS expression,
               CASE WHEN i.indexrelid IS NOT NULL
                    THEN pg_get_expr(i.indpred, i.indrelid, false) END AS predicate,
               CASE WHEN i.indexrelid IS NOT NULL
                    THEN i.indclass[0] = (SELECT op.oid FROM pg_opclass op
                      WHERE op.opcmethod = am.oid
                        AND op.opcnamespace = 'pg_catalog'::regnamespace
                        AND op.opcname = 'text_ops'
                        AND op.opcintype = 'text'::regtype
                        AND op.opcdefault)
                    ELSE NULL END AS default_text_ops,
               CASE WHEN i.indexrelid IS NOT NULL
                    THEN i.indcollation[0] = (SELECT a.attcollation
                      FROM pg_attribute a
                      WHERE a.attrelid = i.indrelid
                        AND a.attname = %s
                        AND a.attnum > 0
                        AND NOT a.attisdropped)
                    ELSE NULL END AS source_collation
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          LEFT JOIN pg_index i ON i.indexrelid = c.oid
          LEFT JOIN pg_am am ON am.oid = c.relam
         WHERE n.nspname = %s AND c.relname = %s
        """,
        (qualified_table, spec.collation_column, postgres_store.schema_name(), spec.name),
    )
    row = cur.fetchone()
    if row is None:
        return {
            "name": spec.name,
            "table": spec.table,
            "exists": False,
            "expression": None,
            "predicate": None,
        }
    return {
        "name": spec.name,
        "table": spec.table,
        "exists": True,
        "relkind": _row_value(row, "relkind", 0),
        "amname": _row_value(row, "amname", 1),
        "indisunique": _row_value(row, "indisunique", 2),
        "indisexclusion": _row_value(row, "indisexclusion", 3),
        "indisvalid": _row_value(row, "indisvalid", 4),
        "indisready": _row_value(row, "indisready", 5),
        "indislive": _row_value(row, "indislive", 6),
        "indnkeyatts": _row_value(row, "indnkeyatts", 7),
        "indnatts": _row_value(row, "indnatts", 8),
        "indkey": _row_value(row, "indkey", 9),
        "indoption": _row_value(row, "indoption", 10),
        "unfiltered": _row_value(row, "unfiltered", 11),
        "correct_table": _row_value(row, "correct_table", 12),
        "expression": _row_value(row, "expression", 13),
        "predicate": _row_value(row, "predicate", 14),
        "default_text_ops": _row_value(row, "default_text_ops", 15),
        "source_collation": _row_value(row, "source_collation", 16),
    }


def inspect_indexes(conn) -> list[dict]:
    """返回九个目标对象的状态，不创建或修改任何对象。"""
    with conn.cursor() as cur:
        return [_inspect_one(cur, spec) for spec in INDEX_SPECS]


def _is_exact(observed: dict, spec: IndexSpec) -> bool:
    return (
        observed.get("exists")
        and observed.get("relkind") == "i"
        and observed.get("amname") == "btree"
        and observed.get("indisunique") is False
        and observed.get("indisexclusion") is False
        and observed.get("indisvalid") is True
        and observed.get("indisready") is True
        and observed.get("indislive") is True
        and observed.get("indnkeyatts") == 1
        and observed.get("indnatts") == 1
        and observed.get("indkey") == "0"
        and observed.get("indoption") == "0"
        and observed.get("correct_table") is True
        and observed.get("default_text_ops") is True
        and observed.get("source_collation") is True
        and observed.get("expression") == spec.expression
        and observed.get("predicate") == spec.predicate
    )


def _error(spec: IndexSpec) -> RuntimeError:
    return InventoryIndexError("index_definition_invalid", spec.name)


def _create_index(conn, spec: IndexSpec, *, concurrent: bool = False) -> None:
    concurrently = " CONCURRENTLY" if concurrent else ""
    predicate = f" WHERE {spec.predicate}" if spec.predicate else ""
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE INDEX{concurrently} {postgres_store.quote_identifier(spec.name)} "
            f"ON {postgres_store.qualified(spec.table)} USING btree ({spec.expression}){predicate}"
        )


def ensure_indexes(conn, *, concurrent: bool = False, analyze: bool = True) -> dict:
    """检查并补齐 v2 索引；在线模式必须使用自动提交连接。"""
    if concurrent and not conn.autocommit:
        raise RuntimeError("CONCURRENTLY 建索引必须使用自动提交连接")

    created: list[str] = []
    reused: list[str] = []
    for spec in INDEX_SPECS:
        with conn.cursor() as cur:
            observed = _inspect_one(cur, spec)
        if observed["exists"]:
            if not _is_exact(observed, spec):
                raise _error(spec)
            reused.append(spec.name)
            continue
        _create_index(conn, spec, concurrent=concurrent)
        created.append(spec.name)

    if analyze:
        with conn.cursor() as cur:
            # v2 首次部署、部分成功重试和在线预建都需要刷新表达式统计。
            for table in sorted({spec.table for spec in INDEX_SPECS}):
                cur.execute(f"ANALYZE {postgres_store.qualified(table)}")

    final = inspect_indexes(conn)
    invalid = [
        spec.name for spec, observed in zip(INDEX_SPECS, final)
        if not _is_exact(observed, spec)
    ]
    if invalid:
        raise InventoryIndexError("index_validation_invalid", invalid[0])
    return {"created": created, "reused": reused, "indexes": final}


def summarize_indexes(conn) -> dict:
    """生成只读检查结果，供维护工具输出。"""
    observed = inspect_indexes(conn)
    invalid = [
        spec.name for spec, item in zip(INDEX_SPECS, observed)
        if not _is_exact(item, spec)
    ]
    return {
        "schema": postgres_store.schema_name(),
        "expected": len(INDEX_SPECS),
        "ready": len(INDEX_SPECS) - len(invalid),
        "ok": not invalid,
        "invalid": invalid,
        "indexes": observed,
    }
