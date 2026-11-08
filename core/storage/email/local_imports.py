"""导入本地素材与 Butler 已确认租约，完整地址保持独立。"""
from __future__ import annotations

from datetime import datetime
from contextlib import nullcontext
import hashlib
import logging
import re

from core.storage import records as record_store

logger = logging.getLogger(__name__)

_ADDRESS = re.compile(r'[^\s<>@,;]+@[^\s<>@,;]+\Z')


def butler_forward_address(value) -> str:
    address = str(value or '').strip().lower()
    if (not _ADDRESS.fullmatch(address) or len(address) > 254
            or len(address.partition('@')[0]) > 64):
        raise ValueError('butler_address_invalid: 请填写完整邮箱地址')
    return address


def _fixed_butler_profile(conn, *, _connection=None) -> dict:
    from config import email as config
    from core.email.derivation import _save_profile_secret
    from core.storage.email.address_allocations import create_inbox_profile

    selected = _connection if _connection is not None else {
        'api_base': getattr(config, 'EMAIL_BUTLER_API_BASE', ''),
        'api_key': getattr(config, 'EMAIL_BUTLER_API_KEY', ''),
        'mailbox_email': getattr(config, 'ICLOUD_HME_FORWARD_IMAP_EMAIL', ''),
    }
    from core.email.email_butler import v2

    base = v2.normalize_base(str(selected.get('api_base') or ''))
    key = str(selected.get('api_key') or '').strip()
    if not key:
        raise ValueError('butler_configuration_required: 导入前请配置 Email Butler 地址和 API Key')
    identity = hashlib.sha256(f'butler-v2:{base}'.encode()).hexdigest()
    version = hashlib.sha256(f'{identity}:{key}'.encode()).hexdigest()
    reference = 'EMAIL_DERIVATION_BUTLER_SECRET_' + version[:20].upper()
    _save_profile_secret(reference, key)
    return create_inbox_profile(inbox_key='butler-v2:' + identity, connector='forward_butler',
        credential_ref=reference, inbox_locator={'api_base': base, 'api_version': 2},
        data={'api_version': 2, 'require_recipient_evidence': False}, conn=conn)


def _existing_v2_handoff(email, profile, *, conn=None, client_id='', acquisition_id='', connection=None):
    """粘贴只恢复本人已有租约，不为给定地址随机申请替代邮箱。"""
    from core.email.derivation import _profile_credentials
    from core.email.email_butler import lease_bindings

    connection = _profile_credentials(profile) if connection is None else connection
    binding = lease_bindings.resolve(email, api_base=connection['api_base'], api_key=connection['api_key'],
        credential_ref=profile['credential_ref'], client_id=client_id, acquisition_id=acquisition_id, conn=conn)
    if (str(binding.get('email') or binding.get('address_norm') or '').strip().lower() != email
            or binding.get('status') != 'active' or binding.get('service') != 'openai'
            or client_id and binding.get('client_id') != client_id):
        raise ValueError('handoff_identity_mismatch: 原租约地址、状态、服务或客户端不一致')
    original_ref = acquisition_id or binding.get('acquisition_id') or 'turb-lease:' + binding['lease_id']
    verified_refs = set(binding.get('verified_acquisition_refs') or [])
    exact_ref = (original_ref in verified_refs or binding.get('acquisition_id') == original_ref
                 and binding.get('original_ref_verified'))
    receipt = {'version': 2, 'state': 'issued', 'owner_kind': 'local_inventory',
            'owner_id': binding['client_id'], 'client_id': binding['client_id'],
            'acquisition_id': original_ref, 'original_ref_verified': bool(exact_ref),
            'verified_acquisition_refs': sorted(verified_refs),
            'lease_id': binding['lease_id'], 'email': email, 'provider': binding['provider'],
            'service': 'openai', 'expires_at': binding.get('expires_at')}
    _v2_handoff_payload(email, receipt)
    return receipt


def _v2_handoff_payload(email, handoff):
    """本地发布必须取得原完整地址的有效长期租约回执。"""
    provider = handoff.get('provider')
    if (handoff.get('state') != 'issued' or handoff.get('service') != 'openai'
            or str(handoff.get('email') or '').strip().lower() != email
            or provider not in {'icloud_hme', 'outlook_graph', 'cloudflare', 'mailcom'}
            or not all(str(handoff.get(key) or '').strip() for key in
                       ('lease_id', 'client_id', 'acquisition_id'))
            or handoff.get('expires_at') is not None):
        raise ValueError('handoff_identity_mismatch: 未确认完整邮箱的长期 OpenAI 租约')
    return {'provider': provider, 'butler_handoff': handoff, 'api_version': 2,
            'lease_id': handoff['lease_id'], 'service': 'openai',
            'identity_type': 'plus_alias' if '+' in email.partition('@')[0] else 'primary',
            'service_sync_state': 'local_only', 'service_fact_permanent': False, 'service_fact_scope': 'local'}



def import_resources(records: list[dict], *, source: str, _fixed_profile=None,
                     _handoffs=None, _manual_item_id=None, _conn=None, _as_registered=False) -> tuple[int, int]:
    """Insert only never-seen full addresses, with one cross-source lock per address."""
    from core.email.inventory import TABLES, import_conflict
    from core.email.resource_lifetime import normalize_expiry
    from core.email.email_butler import service_facts

    if source not in {'outlook', 'generic_api', 'email_butler'}:
        raise ValueError('不支持的手动邮箱导入来源')
    inserted = skipped = 0
    profile = _fixed_profile
    with (nullcontext(_conn) if _conn is not None else record_store.transaction()) as conn:
        if _as_registered:
            from core.storage.email.validity import lock_email_validity
            lock_email_validity(conn, shared=True)
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
            if _as_registered and source == 'outlook' and not all(str(raw.get(key) or raw.get(alias) or '').strip()
                    for key, alias in (('password', 'password'), ('client_id', 'clientId'), ('refresh_token', 'refreshToken'))):
                skipped += 1
                continue
            lifetime = {} if _as_registered else normalize_expiry(raw.get('expires_at'), reject_expired=True)
            existing = (record_store.get_row_by(TABLES[source], 'email', email, lower=True, conn=conn, for_update=True)
                        if _as_registered else None)
            record_store.advisory_xact_lock(conn, 'registered-account:' + email)
            if _as_registered:
                if existing and _stage_existing_registered(conn, source, existing, raw):
                    inserted += 1
                    continue
            if import_conflict(email, conn=conn):
                skipped += 1
                continue
            # A pending manual batch owns its fixed candidate even before the
            # remote result is known. Paste imports cannot race that intent.
            reserved = record_store.list_rows(record_store.EMAIL_BUTLER_IMPORT_ITEMS,
                where="address_norm = %s AND status <> 'skipped'" + (" AND id <> %s" if _manual_item_id else ''),
                params=(email, _manual_item_id) if _manual_item_id else (email,), limit=1, conn=conn)
            if reserved:
                skipped += 1
                continue
            # 永久标签与成功次数独立，退号不会清除导入事实。
            service_tags = raw.get('service_tags')
            service_tags = service_facts.permanent_tags(service_tags if isinstance(service_tags, list) else [])
            payload = {'email': email, 'status': 'available', 'used_at': None, 'note': None,
                       'service_tags': [str(tag).strip() for tag in service_tags if str(tag).strip()],
                       'imported_at': datetime.now().isoformat(timespec='seconds'), **lifetime}
            if source == 'email_butler':
                if profile is None:
                    profile = _fixed_butler_profile(conn)
                from core.email.email_butler.inventory_handoff import handoff_for_import
                handoff = (_handoffs[email] if _handoffs is not None
                           else handoff_for_import(email, profile, conn=conn))
                payload['inbox_profile_id'] = profile['id']
                if handoff.get('version') == 2:
                    payload.update(_v2_handoff_payload(email, handoff))
                else:
                    # 仅兼容已持久保存的旧回执，不再调用退役接口领取地址。
                    if (handoff.get('state') != 'issued' or handoff.get('owner_kind') != 'local_inventory'
                            or handoff.get('version') != 1 or not all(handoff.get(key) for key in
                            ('acquisition_id', 'owner_id', 'identity_id'))):
                        raise ValueError('handoff_identity_mismatch: 未确认完整交接身份')
                    payload.update(butler_handoff=handoff, identity_id=handoff['identity_id'],
                        parent_email=handoff['parent_email'], provider='icloud_hme',
                        identity_type='plus_alias' if '+' in email.partition('@')[0] else 'primary',
                        mailbox_email=profile['inbox_locator'].get('mailbox_email', ''),
                        recipient_mode='forwarded_exact_v1', strict_family=True)
                    service_facts.validate_fact(handoff.get('service_fact'), expected_address=email)
                    payload.update(service_sync_state='delivered', service_fact_permanent=True)
            elif source == 'generic_api':
                payload.update(code_url=code_url)
            else:
                payload.update(password=str(raw.get('password') or '').strip(),
                    client_id=str(raw.get('client_id') or raw.get('clientId') or '').strip(),
                    refresh_token=str(raw.get('refresh_token') or raw.get('refreshToken') or '').strip())
            if source != 'email_butler':
                payload.update(access_token=str(raw.get('access_token') or raw.get('token') or '').strip(),
                               totp_secret=str(raw.get('totp_secret') or raw.get('totp') or '').strip())
            if _as_registered:
                payload['registered_expires_at'] = raw.get('expires_at')
                payload.update({key: raw[key] for key in ('user_id', 'user_name', 'plan_type', 'device_id',
                    'proxy_used', 'codex_status', 'codex_error') if key in raw})
            pool_id = record_store.insert_row_if_absent(TABLES[source], 'email', payload, conn=conn)
            if pool_id is None:
                skipped += 1
            else:
                if source != 'email_butler':
                    service_facts.enqueue_import(source, {**payload, 'id': pool_id}, conn=conn,
                                                 as_registered=_as_registered)
                inserted += 1
    return inserted, skipped


def _stage_existing_registered(conn, source, row, raw):
    """兼容把已有素材导入为账号，仍等待永久事实且不覆盖运行中的任务。"""
    from core.email.email_butler import service_facts
    address = str(row['email']).strip().lower()
    if row.get('status') in {'pending_sync', 'replaced', 'tombstone', 'request_unknown', 'reserved', 'running'}:
        return False
    for table, field in ((record_store.ACCOUNTS, 'email'),
                         (record_store.EMAIL_ADDRESS_ALLOCATIONS, 'address_norm'),
                         (record_store.LOCAL_EMAIL_CLAIMS, 'address_norm')):
        if record_store.get_row_by(table, field, address, lower=True, conn=conn):
            return False
    changes = {'access_token': str(raw.get('access_token') or raw.get('token') or '').strip(),
               'totp_secret': str(raw.get('totp_secret') or raw.get('totp') or '').strip()}
    changes['registered_expires_at'] = raw.get('expires_at')
    changes.update({key: raw[key] for key in ('user_id', 'user_name', 'plan_type', 'device_id',
        'proxy_used', 'codex_status', 'codex_error') if key in raw})
    if source == 'generic_api':
        changes['code_url'] = str(raw.get('code_url') or raw.get('url') or '').strip()
    else:
        changes.update(password=str(raw.get('password') or '').strip(),
                       client_id=str(raw.get('client_id') or raw.get('clientId') or '').strip(),
                       refresh_token=str(raw.get('refresh_token') or raw.get('refreshToken') or '').strip())
    record_store.patch_row(record_store.OUTLOOK_POOL if source == 'outlook' else record_store.GENERIC_API_POOL,
                           row['id'], changes, conn=conn)
    service_facts.enqueue_import(source, {**row, **changes}, conn=conn, as_registered=True)
    return True


def get_butler_email(email: str) -> dict | None:
    return record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', str(email or '').strip(), lower=True)


def pool_mutation_protected(row: dict | None, *, conn=None) -> bool:
    """删除邮箱资源时保留已有使用、占用或结果未知的身份历史。"""
    if row is None:
        return False
    if (str(row.get('status') or '').lower() in {
            'used', 'issued', 'reserved', 'registered', 'request_unknown', 'unknown',
            'result_unknown', 'replaced', 'retired', 'tombstone', 'submitting', 'running'}
            or row.get('used_at') or row.get('registered_account_id')):
        return True
    from core.storage import postgres as postgres_store

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
        if row.get('status') == 'pending_sync':
            raise ValueError('service_fact_sync_pending: 导入服务事实尚未确认，请重试同步')
        record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        if status == 'available' and str(row.get('status') or '').strip().lower() == 'replaced':
            raise ValueError('换绑后邮箱不能恢复为可用')
        changes = {'status': status}
        if status == 'available':
            changes['used_at'] = None
        else:
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
        from core.email.email_butler import service_facts
        event = service_facts.enqueue_return('email_butler', row, conn=conn)
        changed = record_store.patch_row(record_store.EMAIL_BUTLER_POOL, row['id'], {
            'status': 'tombstone', 'service_tags': service_facts.permanent_tags(row.get('service_tags')),
            'return_sync_state': (event or {}).get('state', 'not_required'),
        }, conn=conn)
    return changed


def butler_email_secret(email: str, field: str) -> str:
    row = get_butler_email(email)
    if row is None:
        raise LookupError('邮箱不存在')
    if field == 'copy_line':
        return row['email']
    raise ValueError('Butler 导入邮箱仅支持复制完整地址，连接凭据不作为邮箱素材导出')
