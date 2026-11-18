"""Persistence helpers for explicit manual imports, separate from registration claims."""
from contextlib import nullcontext
from datetime import datetime, timezone
from core.storage import records as record_store
from core.email.inventory import TABLES


def conflicts(addresses, *, conn, exclude_item_id=None):
    addresses = list(addresses)
    if not addresses:
        return set()
    occupied = set()
    for spec, field in [*((spec, 'email') for spec in TABLES.values()),
                        (record_store.ACCOUNTS, 'email'),
                        (record_store.EMAIL_ADDRESS_ALLOCATIONS, 'address_norm'),
                        (record_store.LOCAL_EMAIL_CLAIMS, 'address_norm')]:
        rows = record_store.list_rows(spec, where=f'lower({field}) = ANY(%s)', params=(addresses,), conn=conn)
        occupied.update(str(row[field]).lower() for row in rows)
    legacy = record_store.list_rows(record_store.EMAIL_BUTLER_CLAIM_INTENTS,
        where="lower(COALESCE(address_norm, data->'mailbox'->>'email', '')) = ANY(%s) AND status NOT IN ('prepared','rejected')",
        params=(addresses,), conn=conn)
    occupied.update(str(row.get('address_norm') or (row.get('mailbox') or {}).get('email') or '').lower() for row in legacy)
    rows = record_store.list_rows(record_store.EMAIL_BUTLER_IMPORT_ITEMS,
        where="address_norm = ANY(%s) AND status <> 'skipped'" + (' AND id <> %s' if exclude_item_id else ''),
        params=(addresses, exclude_item_id) if exclude_item_id else (addresses,), conn=conn)
    occupied.update(row['address_norm'] for row in rows)
    return occupied


def batch(batch_id, *, conn=None):
    row = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'batch_id', batch_id, conn=conn)
    if not row:
        raise LookupError('import_batch_not_found')
    return row


def items(batch_id, *, conn=None):
    return record_store.list_rows(record_store.EMAIL_BUTLER_IMPORT_ITEMS, where='batch_id = %s',
                                 params=(batch_id,), order_by='position ASC', conn=conn)


def request_execution(batch_id, *, conn=None):
    """Persist a wakeable request in the same transaction as creation or retry."""
    with (nullcontext(conn) if conn is not None else record_store.transaction()) as active:
        record_store.advisory_xact_lock(active, 'butler-manual-import:' + batch_id)
        current = batch(batch_id, conn=active)
        if current['status'] in {'completed', 'cancelled'} or current.get('dispatch_requested') is True:
            return False
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, current['id'], {
            'dispatch_requested': True,
            'dispatch_requested_at': datetime.now(timezone.utc).isoformat(),
        }, conn=active)
        return True


def pending_batches(*, limit=20):
    """Read durable requests only; interrupted attempts are never auto-retried."""
    return record_store.list_rows(
        record_store.EMAIL_BUTLER_IMPORT_BATCHES,
        where="status NOT IN ('completed','cancelled') AND data->>'dispatch_requested' = 'true'",
        order_by='id ASC', limit=max(1, min(100, int(limit))),
    )
