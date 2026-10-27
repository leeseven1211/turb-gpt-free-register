"""Explicit local email imports; importing never asks an upstream for stock."""
from __future__ import annotations

from datetime import datetime
import hashlib
import re
from urllib.parse import urlsplit

from core import record_store

_ADDRESS = re.compile(r'[^\s<>@,;]+@[^\s<>@,;]+\Z')


def butler_forward_address(value) -> str:
    address = str(value or '').strip().lower()
    if (not _ADDRESS.fullmatch(address) or address.rpartition('@')[2] != 'icloud.com'
            or len(address) > 254 or len(address.partition('@')[0]) > 64):
        raise ValueError('Email Butler 单列导入仅支持完整 iCloud HME 转发地址；其他邮箱请使用 Outlook 或通用 API 导入')
    return address


def _fixed_butler_profile(conn) -> dict:
    from config import email as config
    from core.email_derivation import _save_profile_secret
    from core.storage.email_address_allocations import create_inbox_profile

    base = str(getattr(config, 'EMAIL_BUTLER_API_BASE', '') or '').strip().rstrip('/')
    key = str(getattr(config, 'EMAIL_BUTLER_API_KEY', '') or '').strip()
    mailbox = str(getattr(config, 'ICLOUD_HME_FORWARD_IMAP_EMAIL', '') or '').strip().lower()
    try:
        parsed = urlsplit(base)
        valid = (parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username
                 and not parsed.password and not parsed.query and not parsed.fragment
                 and parsed.path.rstrip('/').endswith('/v1'))
    except ValueError:
        valid = False
    if not valid or not key or not _ADDRESS.fullmatch(mailbox):
        raise ValueError('导入前请完整配置 Email Butler /v1 地址、API Key 和固定最终转发收件箱')
    identity = hashlib.sha256(f'butler-local:{base}:{mailbox}'.encode()).hexdigest()
    version = hashlib.sha256(f'{identity}:{key}'.encode()).hexdigest()
    reference = 'EMAIL_DERIVATION_BUTLER_SECRET_' + version[:20].upper()
    _save_profile_secret(reference, key)
    return create_inbox_profile(inbox_key='butler-local:' + identity, connector='forward_butler',
        credential_ref=reference, inbox_locator={'api_base': base, 'mailbox_email': mailbox},
        data={'require_recipient_evidence': True}, conn=conn)


def import_resources(records: list[dict], *, source: str) -> tuple[int, int]:
    """Insert only never-seen full addresses, with one cross-source lock per address."""
    from core.local_email_inventory import TABLES, import_conflict

    if source not in {'outlook', 'generic_api', 'email_butler'}:
        raise ValueError('不支持的手动邮箱导入来源')
    inserted = skipped = 0
    profile = None
    with record_store.transaction() as conn:
        # 同一批事务会持有所有地址锁；各来源使用相同顺序，避免相反输入批次互等。
        for raw in sorted(records, key=lambda item: str(item.get('email') or '').strip().lower()):
            email = str(raw.get('email') or '').strip().lower()
            if not _ADDRESS.fullmatch(email):
                skipped += 1
                continue
            if source == 'email_butler':
                email = butler_forward_address(email)
            code_url = str(raw.get('code_url') or raw.get('url') or '').strip()
            if source == 'generic_api' and not code_url:
                skipped += 1
                continue
            record_store.advisory_xact_lock(conn, 'registered-account:' + email)
            if import_conflict(email, conn=conn):
                skipped += 1
                continue
            payload = {'email': email, 'status': 'available', 'used_at': None, 'note': None,
                       'imported_at': datetime.now().isoformat(timespec='seconds')}
            if source == 'email_butler':
                if profile is None:
                    profile = _fixed_butler_profile(conn)
                payload.update(inbox_profile_id=profile['id'], provider='icloud_hme',
                    identity_type='plus_alias' if '+' in email.partition('@')[0] else 'primary',
                    mailbox_email=profile['inbox_locator']['mailbox_email'],
                    recipient_mode='forwarded_exact_v1', strict_family=True)
            elif source == 'generic_api':
                payload.update(code_url=code_url)
            else:
                payload.update(password=str(raw.get('password') or '').strip(),
                    client_id=str(raw.get('client_id') or raw.get('clientId') or '').strip(),
                    refresh_token=str(raw.get('refresh_token') or raw.get('refreshToken') or '').strip())
            if source != 'email_butler':
                payload.update(access_token=str(raw.get('access_token') or '').strip(),
                               totp_secret=str(raw.get('totp_secret') or '').strip())
            if record_store.insert_row_if_absent(TABLES[source], 'email', payload, conn=conn) is None:
                skipped += 1
            else:
                inserted += 1
    return inserted, skipped


def get_butler_email(email: str) -> dict | None:
    return record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', str(email or '').strip(), lower=True)


def pool_mutation_protected(row: dict | None, *, conn=None) -> bool:
    """Used or uncertain identity history survives UI reset/delete/reimport flows."""
    if row is None:
        return False
    if (str(row.get('status') or '').lower() in {
            'used', 'issued', 'reserved', 'registered', 'request_unknown', 'unknown',
            'result_unknown', 'replaced', 'retired', 'tombstone', 'submitting', 'running'}
            or row.get('used_at') or row.get('registered_account_id')):
        return True
    from core import postgres_store

    def check(current):
        address = str(row.get('email') or '').strip().lower()
        for table, field in ((record_store.ACCOUNTS, 'email'),
                             (record_store.EMAIL_ADDRESS_ALLOCATIONS, 'address_norm'),
                             (record_store.LOCAL_EMAIL_CLAIMS, 'address_norm')):
            if record_store.get_row_by(table, field, address, lower=True, conn=current):
                return True
        remote = postgres_store.qualified(record_store.EMAIL_BUTLER_CLAIM_INTENTS.name)
        with current.cursor() as cursor:
            cursor.execute(f"SELECT 1 FROM {remote} WHERE lower(COALESCE(address_norm, data->'mailbox'->>'email', ''))=%s AND status NOT IN ('prepared','rejected') LIMIT 1", (address,))
            return cursor.fetchone() is not None
    if conn is not None:
        return check(conn)
    with record_store.transaction() as current:
        return check(current)


def set_butler_status(email: str, *, status: str, note=None) -> bool:
    address = str(email or '').strip().lower()
    with record_store.transaction() as conn:
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, lower=True, conn=conn, for_update=True)
        if row is None:
            return False
        record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        if status == 'available' and pool_mutation_protected(row, conn=conn):
            raise ValueError('已使用、已保留或结果未知的邮箱不能重新变为可用')
        changes = {'status': status}
        if status != 'available':
            changes['used_at'] = row.get('used_at') or datetime.now().isoformat(timespec='seconds')
        if note is not None:
            changes['note'] = note
        return record_store.patch_row(record_store.EMAIL_BUTLER_POOL, row['id'], changes, conn=conn)


def delete_butler_email(email: str) -> bool:
    """Preserve a tombstone so a later paste cannot revive removed stock."""
    address = str(email or '').strip().lower()
    with record_store.transaction() as conn:
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, lower=True, conn=conn, for_update=True)
        record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        if not row or pool_mutation_protected(row, conn=conn):
            return False
        return record_store.patch_row(record_store.EMAIL_BUTLER_POOL, row['id'], {'status': 'tombstone'}, conn=conn)


def butler_email_secret(email: str, field: str) -> str:
    row = get_butler_email(email)
    if row is None:
        raise LookupError('邮箱不存在')
    if field == 'copy_line':
        return row['email']
    raise ValueError('Butler 导入邮箱仅支持复制完整地址，连接凭据不作为邮箱素材导出')
