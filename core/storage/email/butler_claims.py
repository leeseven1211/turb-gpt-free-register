"""Durable consumer claims; remote inventory remains exclusively Butler-owned."""
from __future__ import annotations

import uuid

from core.storage import records as record_store

_TABLE = record_store.EMAIL_BUTLER_CLAIM_INTENTS
_MAILBOX_FIELDS = ('id', 'email', 'lease_id', 'leased_until', 'provider', 'mailbox_email',
                   'recipient_mode', 'strict_family', 'identity_type', 'parent_email', 'identity_id')


def get_intent(acquisition_id: str) -> dict | None:
    return record_store.get_row_by(_TABLE, 'acquisition_id', str(acquisition_id))


def prepare(*, acquisition_id: str, owner_kind: str, owner_id, api_base: str, credential_ref: str) -> dict:
    if not str(acquisition_id or '').strip() or not str(owner_kind or '').strip() or owner_id is None:
        raise ValueError('email_derivation_identity_conflict: Butler 领取缺少稳定业务意图')
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'butler-consumer-claim:' + acquisition_id)
        previous = record_store.get_row_by(_TABLE, 'acquisition_id', acquisition_id, conn=conn)
        if previous:
            if (previous['owner_kind'],previous['owner_id']) != (str(owner_kind),str(owner_id)):
                raise ValueError('email_derivation_identity_conflict: Butler 领取意图已归属于其他业务')
            return previous
        row_id = record_store.insert_row(_TABLE, {
            'acquisition_id':acquisition_id, 'owner_kind':str(owner_kind), 'owner_id':str(owner_id),
            'status':'prepared', 'api_base':api_base, 'credential_ref':credential_ref,
        }, conn=conn)
        return record_store.get_row(_TABLE,row_id,conn=conn)


def mark_submitting(acquisition_id: str, *, recovery_capable: bool = False) -> tuple[bool, dict]:
    """Commit one first submitter; other callers must use remote recovery."""
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'butler-consumer-claim:' + acquisition_id)
        row = record_store.get_row_by(_TABLE, 'acquisition_id', acquisition_id, conn=conn)
        if row is None:
            raise ValueError('Butler 领取意图不存在')
        if row['status'] not in {'prepared', 'rejected'}:
            return False, row
        record_store.patch_row(_TABLE, row['id'], {
            'status': 'submitting', 'submission_execution': uuid.uuid4().hex,
            'acquisition_capable': bool(recovery_capable),
        }, conn=conn)
        return True, record_store.get_row(_TABLE, row['id'], conn=conn)


def record_result(acquisition_id: str, *, mailbox: dict | None = None, unknown: bool = False, rejected: bool = False, execution: str | None = None) -> dict:
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn,'butler-consumer-claim:' + acquisition_id)
        previous = record_store.get_row_by(_TABLE,'acquisition_id',acquisition_id,conn=conn)
        if not previous:
            raise ValueError('Butler 领取意图不存在')
        # A delayed timeout cannot undo a successfully recovered claim.
        if previous['status'] == 'claimed':
            if mailbox and str(mailbox.get('email') or '').strip().lower() != previous['address_norm']:
                raise ValueError('email_derivation_identity_conflict: Butler 同一意图返回不同完整地址')
            return previous
        if rejected and (previous['status'] == 'request_unknown' or
                previous['status'] == 'submitting' and previous.get('submission_execution') != execution):
            return previous
        changes = {'status':'request_unknown' if unknown else 'rejected' if rejected else 'claimed'}
        if mailbox is not None:
            changes.update(mailbox={key:mailbox[key] for key in _MAILBOX_FIELDS if key in mailbox},
                           address_norm=str(mailbox.get('email') or '').strip().lower())
        record_store.patch_row(_TABLE,previous['id'],changes,conn=conn)
        return record_store.get_row(_TABLE,previous['id'],conn=conn)
