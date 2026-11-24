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



def _import_snapshot(conn, source, addresses, *, registered=False, exclude_item_ids=()):
    """一次集合读取跨来源历史；注册兼容路径还锁原池行。"""
    from core.email.inventory import TABLES
    from core.storage import postgres as pg
    if registered:
        with conn.cursor() as cur:
            cur.execute(f'SELECT * FROM {pg.qualified(TABLES[source].name)} '
                'WHERE lower(email)=ANY(%s) ORDER BY id FOR UPDATE', (addresses,))
            existing = {row['email'].lower(): record_store.merge_row(TABLES[source], row) for row in cur.fetchall()}
    else:
        existing = {}
    from core.storage.email.collections import lock_keys
    lock_keys(conn, ['registered-account:' + email for email in addresses])
    branches = []
    tables = [(spec, 'email', 'pool') for spec in TABLES.values()] + [
        (record_store.ACCOUNTS, 'email', 'account'),
        (record_store.EMAIL_ADDRESS_ALLOCATIONS, 'address_norm', 'allocation'),
        (record_store.LOCAL_EMAIL_CLAIMS, 'address_norm', 'claim'),
        (record_store.EMAIL_SERVICE_SYNC, 'address_norm', 'sync')]
    for spec, field, kind in tables:
        branches.append(f"SELECT lower({field}) AS address,'{kind}' AS kind FROM {pg.qualified(spec.name)}")
    branches.append(f"SELECT lower(COALESCE(address_norm,data->'mailbox'->>'email','')) AS address,'remote' AS kind "
        f"FROM {pg.qualified(record_store.EMAIL_BUTLER_CLAIM_INTENTS.name)} WHERE status NOT IN ('prepared','rejected')")
    occupied = {}
    with conn.cursor() as cur:
        cur.execute('SELECT DISTINCT address,kind FROM (' + ' UNION ALL '.join(branches) + ') all_history WHERE address=ANY(%s)', (addresses,))
        for row in cur.fetchall():
            occupied.setdefault(row['address'], set()).add(row['kind'])
        cur.execute(f'SELECT address_norm,id FROM {pg.qualified(record_store.EMAIL_BUTLER_IMPORT_ITEMS.name)} '
            "WHERE address_norm=ANY(%s) AND status <> 'skipped' AND NOT (id=ANY(%s))",
            (addresses, list(exclude_item_ids)))
        for row in cur.fetchall():
            occupied.setdefault(row['address_norm'], set()).add('manual')
    return existing, occupied


def import_resources(records: list[dict], *, source: str, _fixed_profile=None,
                     _handoffs=None, _manual_item_id=None, _manual_item_ids=(), _conn=None, _as_registered=False) -> tuple[int, int]:
    """集合预检、集合插入与本地服务事实同事务；远端原租约核验保持逐地址。"""
    from core.email.inventory import TABLES
    from core.email.resource_lifetime import normalize_expiry
    from core.email.email_butler import service_facts
    from core.storage.email.collections import insert_many, patch_many
    if source not in {'outlook', 'generic_api', 'email_butler'}:
        raise ValueError('不支持的手动邮箱导入来源')
    candidates, skipped = {}, 0
    for raw in sorted(records, key=lambda item: str(item.get('email') or '').strip().lower()):
        email = str(raw.get('email') or '').strip().lower()
        if not _ADDRESS.fullmatch(email):
            skipped += 1
            continue
        if source == 'email_butler':
            email = butler_forward_address(email)
        if source == 'generic_api' and not str(raw.get('code_url') or raw.get('url') or '').strip():
            skipped += 1
            continue
        if _as_registered and source == 'outlook' and not all(str(raw.get(key) or raw.get(alias) or '').strip()
                for key, alias in (('password','password'),('client_id','clientId'),('refresh_token','refreshToken'))):
            skipped += 1
            continue
        lifetime = {} if _as_registered else normalize_expiry(raw.get('expires_at'), reject_expired=True)
        if email in candidates:
            skipped += 1
        else:
            candidates[email] = (raw, lifetime)
    if not candidates:
        return 0, skipped
    profile = _fixed_profile
    with (nullcontext(_conn) if _conn is not None else record_store.transaction()) as conn:
        if _as_registered:
            from core.storage.email.validity import lock_email_validity
            lock_email_validity(conn, shared=True)
        excluded = tuple(_manual_item_ids) + ((_manual_item_id,) if _manual_item_id else ())
        existing, occupied = _import_snapshot(conn, source, list(candidates), registered=_as_registered,
            exclude_item_ids=excluded)
        payloads, staged, staged_rows = [], {}, []
        for email, (raw, lifetime) in candidates.items():
            previous = existing.get(email)
            if _as_registered and previous and previous.get('status') not in {
                    'pending_sync','replaced','tombstone','request_unknown','reserved','running'} and not (
                    occupied.get(email, set()) & {'account','allocation','claim'}):
                changes = _registered_material(raw, source)
                staged[previous['id']] = changes
                staged_rows.append({**previous, **changes})
                continue
            if occupied.get(email):
                skipped += 1
                continue
            code_url = str(raw.get('code_url') or raw.get('url') or '').strip()
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
            payloads.append(payload)
        patch_many(conn, TABLES[source], staged)
        fresh = insert_many(conn, TABLES[source], payloads, conflict_key='email')
        skipped += len(payloads) - len(fresh)
        accepted = [*staged_rows, *fresh]
        if source != 'email_butler':
            service_facts.enqueue_import_many(source, accepted, conn=conn, as_registered=_as_registered)
        return len(accepted), skipped


def _registered_material(raw, source):
    changes = {'access_token': str(raw.get('access_token') or raw.get('token') or '').strip(),
        'totp_secret': str(raw.get('totp_secret') or raw.get('totp') or '').strip(),
        'registered_expires_at': raw.get('expires_at')}
    changes.update({key: raw[key] for key in ('user_id','user_name','plan_type','device_id',
        'proxy_used','codex_status','codex_error') if key in raw})
    if source == 'generic_api':
        changes['code_url'] = str(raw.get('code_url') or raw.get('url') or '').strip()
    else:
        changes.update(password=str(raw.get('password') or '').strip(),
            client_id=str(raw.get('client_id') or raw.get('clientId') or '').strip(),
            refresh_token=str(raw.get('refresh_token') or raw.get('refreshToken') or '').strip())
    return changes


def publish_registered_many(source, rows, *, conn):
    """已确认本地永久事实后集合创建兼容账号；保留原池失效证据。"""
    import json
    from core.storage.db_legacy import _outlook_line, _generic_api_email_line
    from core.storage.email.collections import insert_many, patch_many
    from core.storage.email.validity import lock_email_validity
    from core.email.inventory import TABLES
    lock_email_validity(conn, shared=True)
    addresses = [row['email'].lower() for row in rows]
    existing = record_store.list_rows(record_store.ACCOUNTS, where='lower(email)=ANY(%s)', params=(addresses,), conn=conn)
    allocated = record_store.list_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, where='address_norm=ANY(%s)', params=(addresses,), conn=conn)
    blocked = {row['email'].lower() for row in existing} | {row['address_norm'] for row in allocated}
    if blocked:
        raise ValueError('registered_import_conflict: 原已注册账号导入无法完成')
    payloads, pool_by_email, changes = [], {}, {}
    for row in rows:
        email, now = row['email'], record_store._now()
        pool_by_email[email.lower()] = row
        patch = {'status': 'used', 'used_at': row.get('used_at') or now,
            'completed_at': row.get('completed_at') or now,
            'note': row.get('note') or '导入为已注册账号，用于 Codex 授权'}
        material = {**row, **patch}
        account = {'email': email, 'created_at': now, 'updated_at': now,
            'access_token': str(row.get('access_token') or '').strip(),
            'totp_secret': str(row.get('totp_secret') or '').strip() or None,
            'user_id': row.get('user_id'), 'user_name': row.get('user_name') or 'Imported Account',
            'plan_type': row.get('plan_type'), 'expires_at': row.get('registered_expires_at'),
            'device_id': row.get('device_id'), 'proxy_used': row.get('proxy_used'), 'email_source': source,
            'extra_json': json.dumps({'imported_registered': True}, ensure_ascii=False),
            'codex_status': row.get('codex_status') or '', 'codex_error': row.get('codex_error'),
            'original_email_line': _outlook_line(material) if source == 'outlook' else _generic_api_email_line(material)}
        if source == 'outlook':
            account.update({key: row.get(key) for key in ('password','client_id','refresh_token')})
        if row.get('email_invalid') is True:
            account.update({key: row.get(key) for key in ('email_invalid','email_invalid_reason',
                'email_invalid_source','email_invalid_at')})
            account['email_invalid_email'] = email
        payloads.append(account)
        changes[row['id']] = patch
    accounts = insert_many(conn, record_store.ACCOUNTS, payloads)
    for account in accounts:
        row = pool_by_email[account['email'].lower()]
        changes[row['id']].update(registered_account_id=account['id'], access_token=account.get('access_token') or '')
        if account.get('totp_secret'):
            changes[row['id']]['totp_secret'] = account['totp_secret']
    patch_many(conn, TABLES[source], changes)
    return accounts


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
    """只有已确认注册成功的完整邮箱阻止删除。"""
    if row is None:
        return False
    if str(row.get('access_token') or '').strip():
        return True
    from core.storage.email.deletion import registration_confirmed

    def check(current):
        return registration_confirmed(row.get('email'), account_id=row.get('registered_account_id'), conn=current)
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
        if row.get('status') == 'tombstone':
            raise ValueError('local_email_deleted: 邮箱已删除，不能恢复为可用')
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
        if not row:
            return False
        if row.get('status') == 'tombstone':
            return True
        if pool_mutation_protected(row, conn=conn):
            return False
        from core.email.email_butler import service_facts
        event = service_facts.enqueue_return('email_butler', row, conn=conn)
        changed = record_store.patch_row(record_store.EMAIL_BUTLER_POOL, row['id'], {
            'status': 'tombstone', 'service_tags': service_facts.permanent_tags(row.get('service_tags')),
            'deleted_at': datetime.now().isoformat(timespec='seconds'),
            'pool_deleted_at': datetime.now().isoformat(timespec='seconds'),
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
