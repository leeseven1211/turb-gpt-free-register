"""提链工作台的集合账号准入、占用与 Task/Run 创建。"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
import uuid

from core.accounts.plans import promotion as plus_promotion
from core import db
from core.storage import postgres as postgres_store, records as record_store
from core.storage.operations import bulk_submission, common, store as operation

_MAX_CHUNK = 500


class _ChunkFailure(RuntimeError):
    def __init__(self, failed_count: int, skipped_count: int, cause: Exception):
        super().__init__(str(cause))
        self.failed_count = int(failed_count)
        self.skipped_count = int(skipped_count)
        self.__cause__ = cause


def _normalize_ids(account_ids: Iterable[int]) -> tuple[list[int], int]:
    values: list[int] = []
    duplicates = 0
    seen: set[int] = set()
    for raw in account_ids if isinstance(account_ids, Iterable) and not isinstance(account_ids, (str, bytes, Mapping)) else ():
        try:
            value = int(raw)
        except (TypeError, ValueError, OverflowError):
            duplicates += 1
            continue
        if value <= 0 or value >= 2**63:
            duplicates += 1
            continue
        if value in seen:
            duplicates += 1
            continue
        seen.add(value)
        values.append(value)
    return values, duplicates


def _chunk_create(
    ids: list[int], *, data: Mapping[str, object], config_snapshot: object,
    batch_id: int | None, first_ordinal: int, allow_no_promotion: bool,
) -> tuple[int, int, int]:
    if not ids:
        return 0, 0, 0
    operation.init()
    from core.extract_link.service import EXTRACT_CONFIG_ALLOWLIST
    source_data = dict(data)
    source_data.pop("config_snapshot", None)
    source_data["workbench_action"] = "create"
    now = db._now()
    table = postgres_store.qualified(record_store.ACCOUNTS.name)
    active_statuses = sorted(common._ACTIVE_RUN_STATUSES)
    with operation._connect() as conn, conn.cursor() as cur:
        # 锁序固定为账号→活动 Run；同一块内只读一次目标集合。
        cur.execute(f"SELECT * FROM {table} WHERE id=ANY(%s) ORDER BY id FOR UPDATE", (ids,))
        accounts = {int(row["id"]): record_store._merge(record_store.ACCOUNTS, row) for row in cur.fetchall()}
        cur.execute(
            f"SELECT account_id FROM {operation._table('operation_runs')} "
            "WHERE account_id=ANY(%s) AND resource_family=%s AND status=ANY(%s) "
            "ORDER BY account_id",
            (ids, "openai_interactive", active_statuses),
        )
        busy = {int(row["account_id"]) for row in cur.fetchall() if row.get("account_id") is not None}
        eligible: list[int] = []
        skipped = 0
        for account_id in ids:
            account = accounts.get(account_id)
            if account is None or account.get("archived") or db.account_is_deactivated(account):
                skipped += 1; continue
            try:
                allowed = plus_promotion.is_extract_link_eligible(
                    account, allow_no_promotion=allow_no_promotion,
                )
            except Exception:
                allowed = False
            if not allowed or not str(account.get("access_token") or "").strip() or account_id in busy:
                skipped += 1; continue
            eligible.append(account_id)
        if not eligible:
            return 0, skipped, 0
        guard, guard_params = db._stage_claim_guard("extract_link")
        changes = {
            "extract_link_status": "queued", "extract_link_ok": False,
            "extract_link_trigger": "extract_workbench", "extract_link_type": str(data.get("link_type") or "upi").lower(), "extract_link_queued_at": now,
            "extract_link_started_at": None, "extract_link_completed_at": None,
            "extract_link_error": None, "extract_link_message": "已入队",
            "updated_at": now,
        }
        claimed = record_store.patch_rows_where_returning(
            record_store.ACCOUNTS, changes=changes,
            where=f"id=ANY(%s) AND ({guard})",
            params=[eligible, *guard_params], conn=conn, id_only=True,
        )
        claimed_ids = {int(row["id"]) for row in claimed}
        skipped += len(eligible) - len(claimed_ids)
        if not claimed_ids:
            return 0, skipped, 0
        specs = []
        for ordinal, account_id in enumerate((value for value in ids if value in claimed_ids), first_ordinal):
            account = accounts[account_id]
            payload = dict(source_data)
            payload["provider_id"] = str(payload.get("provider_id") or "legacy")
            payload["mode"] = str(payload.get("mode") or "extract_only")
            payload["payment_source"] = str(payload.get("payment_source") or "native")
            payload["link_type"] = str(payload.get("link_type") or "upi")
            if allow_no_promotion:
                payload["allow_no_promotion"] = True
            specs.append({
                "task_type": "extract_link", "account_id": account_id,
                "email": str(account.get("email") or "").strip(),
                "trigger": "extract_workbench", "source_system": "native_operations",
                "source_id": f"extract-workbench:{account_id}:{uuid.uuid4().hex}",
                "resource_family": "openai_interactive", "data": payload,
                "config_snapshot": config_snapshot, "config_allowlist": EXTRACT_CONFIG_ALLOWLIST,
                "batch_id": batch_id, "batch_ordinal": ordinal,
            })
        try:
            created = bulk_submission.create_specs(specs, conn=conn)
        except Exception as exc:
            # 让连接上下文看到异常并回滚本块的 claim；不能留下无 Task 的 queued 账号。
            raise _ChunkFailure(len(claimed_ids), skipped, exc) from exc
        started = sum(1 for row in created if row.get("accepted"))
        failed = len(created) - started
        return started, skipped, failed


def create_tasks(
    account_ids: Iterable[int], *, data: Mapping[str, object], config_snapshot: object,
    batch_id: int | None = None, first_ordinal: int = 1,
    allow_no_promotion: bool = False,
) -> dict[str, int]:
    """在每个最多 500 目标的事务块内完成准入、占用和普通任务集合创建。"""
    ids, invalid_or_duplicate = _normalize_ids(account_ids)
    if not ids:
        return {"started": 0, "skipped": invalid_or_duplicate, "failed": 0}
    started = skipped = failed = 0
    for offset in range(0, len(ids), _MAX_CHUNK):
        block = ids[offset:offset + _MAX_CHUNK]
        try:
            block_started, block_skipped, block_failed = _chunk_create(
                block, data=data, config_snapshot=config_snapshot, batch_id=batch_id,
                first_ordinal=int(first_ordinal) + started, allow_no_promotion=allow_no_promotion,
            )
        except _ChunkFailure as exc:
            skipped += exc.skipped_count
            failed += exc.failed_count
            continue
        started += block_started; skipped += block_skipped; failed += block_failed
    return {"started": started, "skipped": skipped + invalid_or_duplicate, "failed": failed}


__all__ = ["create_tasks"]
