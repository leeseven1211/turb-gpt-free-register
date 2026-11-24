"""Codex 凭证的集合状态写入；不读取或清理兼容文件。"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime
import json

from psycopg.rows import dict_row

from core.operations.bulk_mutations import BulkItemResult, BulkMutationResult, execute_chunked_bulk
from core.storage import postgres as postgres_store, records as record_store


def _valid_filename(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("codex-")
        and value.endswith(".json")
        and not any(part in value for part in ("/", "\\", ".."))
    )


def _mutate_many(filenames, operation: str, *, archived: bool = True, conn=None) -> BulkMutationResult:
    names = tuple(filenames)
    timestamp = datetime.now().isoformat(timespec="seconds")
    visited = set()
    changed = {}

    def apply_chunk(chunk):
        valid = list(dict.fromkeys(name.strip() for name in chunk
                                   if isinstance(name, str) and _valid_filename(name.strip())
                                   and name.strip() not in visited))
        if valid:
            if conn is None:
                record_store.init()
            table = postgres_store.qualified(record_store.CODEX_CREDENTIALS.name)
            # 排序后取得同一批凭证的行锁，让重叠批次保持一致锁序。
            locked = (
                f"WITH targets AS MATERIALIZED (SELECT filename FROM {table} "
                "WHERE filename=ANY(%s) ORDER BY filename FOR UPDATE) "
            )
            if operation == "codex_delete":
                sql = locked + f"DELETE FROM {table} AS credential USING targets " \
                    "WHERE credential.filename=targets.filename RETURNING credential.filename"
                parameters = (valid,)
            else:
                if operation == "codex_archive":
                    changes = {"archived_at": timestamp if archived else None}
                    updates = "archived=%s, data=credential.data || %s::jsonb, updated_at=%s"
                    parameters = (valid, bool(archived), json.dumps(changes), timestamp)
                elif operation == "codex_reset_export":
                    changes = {"exported_at": None}
                    updates = "exported_count=0, data=credential.data || %s::jsonb, updated_at=%s"
                    parameters = (valid, json.dumps(changes), timestamp)
                else:
                    changes = {"exported_at": timestamp}
                    updates = "exported_count=credential.exported_count+1, " \
                        "data=credential.data || %s::jsonb, updated_at=%s"
                    parameters = (valid, json.dumps(changes), timestamp)
                sql = locked + f"UPDATE {table} AS credential SET {updates} FROM targets " \
                    "WHERE credential.filename=targets.filename RETURNING credential.filename, " \
                    "credential.archived, credential.exported_count, " \
                    "credential.data->>'archived_at' AS archived_at, " \
                    "credential.data->>'exported_at' AS exported_at"
            with (nullcontext(conn) if conn is not None else postgres_store.connect()) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, parameters)
                    changed.update({row["filename"]: dict(row) for row in cursor.fetchall()})
                    visited.update(valid)
        results = []
        for key in chunk:
            name = key.strip() if isinstance(key, str) else key
            if not _valid_filename(name):
                results.append(BulkItemResult(key=key, status="skipped", reason_code="invalid_filename",
                                              reason=f"非法文件名: {key}"))
            elif name not in changed:
                results.append(BulkItemResult(key=key, status="skipped", reason_code="not_found",
                                              reason="凭证不存在"))
            else:
                row = changed[name]
                if operation == "codex_archive":
                    data = {"archived": row["archived"], "archived_at": row["archived_at"]}
                elif operation == "codex_delete":
                    data = None
                else:
                    data = {"exported_count": row["exported_count"], "exported_at": row["exported_at"]}
                results.append(BulkItemResult(key=key, status="updated", data=data))
        return results

    result = execute_chunked_bulk(operation, names, apply_chunk)
    return replace(result, items=tuple(
        replace(item, reason_code="invalid_filename", reason=f"非法文件名: {item.key}")
        if item.reason_code == "invalid_target" else item
        for item in result.items
    ))


def archive_many(filenames, archived: bool = True, *, conn=None) -> BulkMutationResult:
    return _mutate_many(filenames, "codex_archive", archived=archived, conn=conn)


def delete_many(filenames, *, conn=None) -> BulkMutationResult:
    return _mutate_many(filenames, "codex_delete", conn=conn)


def reset_exported_many(filenames, *, conn=None) -> BulkMutationResult:
    return _mutate_many(filenames, "codex_reset_export", conn=conn)


def mark_exported_many(filenames, *, conn=None) -> BulkMutationResult:
    return _mutate_many(filenames, "codex_mark_exported", conn=conn)


def register_handlers(register=None) -> None:
    """由 runtime assembly 显式安装，无模块导入注册副作用。"""
    if register is None:
        from core.operations.bulk_mutation_worker import register_bulk_mutation_handler as register

    register(
        "codex_archive", lambda chunk, parameters, *, conn: archive_many(
            chunk, bool(parameters.get("archived", True)), conn=conn,
        ),
        parameter_allowlist=("archived",),
    )
    register("codex_delete", lambda chunk, parameters, *, conn: delete_many(chunk, conn=conn))
    register(
        "codex_reset_export", lambda chunk, parameters, *, conn: reset_exported_many(chunk, conn=conn),
    )
    register(
        "codex_mark_exported", lambda chunk, parameters, *, conn: mark_exported_many(chunk, conn=conn),
    )


__all__ = ["archive_many", "delete_many", "reset_exported_many", "mark_exported_many", "register_handlers"]
