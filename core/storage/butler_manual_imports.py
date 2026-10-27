"""Persistence helpers for explicit manual imports, separate from registration claims."""
from core import record_store
from core.local_email_inventory import TABLES


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
