"""固定地址与 v2 原租约的持久映射；恢复永远不创建替代租约。"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib

from core.email.email_butler import v2
from core.storage import records


def _address(value):
    value = str(value or '').strip().lower()
    if not value.partition('@')[0] or not value.partition('@')[2]:
        raise v2.ButlerV2Error('recipient_mismatch', '原租约完整邮箱无效')
    return value


def _refs(row, *, verified=False):
    """每个原意图分别保存证据，不能将一个意图的释放权转给另一个。"""
    row = row or {}
    values = row.get('verified_acquisition_refs' if verified else 'acquisition_refs') or []
    result = {value for value in values if isinstance(value, str) and value}
    original = row.get('acquisition_id')
    if original and (not verified or row.get('original_ref_verified')):
        result.add(str(original))
    return result


def save(lease, *, api_base, credential_ref, client_id, acquisition_id='', conn=None,
         original_ref_verified=True):
    """在本地库存事务内保存已核验回执，保持旧租约历史和固定客户端。"""
    base, address = v2.normalize_base(api_base), _address(lease.get('email'))
    if (not lease.get('id') or lease.get('service') != 'openai'
            or lease.get('client_id') != client_id or not client_id
            or lease.get('status') not in {'active', 'released', 'expired', 'revoked'}):
        raise v2.ButlerV2Error('lease_identity_mismatch', 'Butler 原租约的地址、服务或客户端未确认')
    key = hashlib.sha256(f'{base}:{client_id}:{lease["id"]}'.encode()).hexdigest()
    with (nullcontext(conn) if conn is not None else records.transaction()) as conn:
        if acquisition_id:
            intent_key = hashlib.sha256(f'{base}:{client_id}:{acquisition_id}'.encode()).hexdigest()
            records.advisory_xact_lock(conn, 'butler-v2-binding-intent:' + intent_key)
            conflicts = records.list_rows(records.EMAIL_BUTLER_LEASE_BINDINGS,
                where="api_base = %s AND client_id = %s AND service = %s AND lease_id <> %s "
                      "AND (acquisition_id = %s OR COALESCE(data->'acquisition_refs', '[]'::jsonb) ? %s)",
                params=(base, client_id, 'openai', lease['id'], acquisition_id, acquisition_id), conn=conn)
            if conflicts:
                raise v2.ButlerV2Error('lease_mapping_ambiguous', '原操作已经对应其他租约，不能重新绑定')
        records.advisory_xact_lock(conn, 'butler-v2-binding:' + key)
        old = records.get_row_by(records.EMAIL_BUTLER_LEASE_BINDINGS, 'binding_key', key, conn=conn)
        if old and (old['address_norm'] != address or old['service'] != lease['service']):
            raise v2.ButlerV2Error('lease_identity_mismatch', '已有租约映射与原地址不一致')
        references, verified_references = _refs(old), _refs(old, verified=True)
        if acquisition_id:
            references.add(acquisition_id)
            if original_ref_verified:
                verified_references.add(acquisition_id)
        primary_ref = (old or {}).get('acquisition_id') or acquisition_id or ''
        payload = {'binding_key': key, 'address_norm': address, 'email': address, 'api_base': base,
                   'client_id': client_id, 'lease_id': lease['id'], 'service': lease['service'],
                   'status': lease['status'], 'expires_at': lease.get('expires_at'),
                   'provider': lease.get('provider'), 'external_ref': lease.get('external_ref'),
                   'credential_ref': credential_ref or (old or {}).get('credential_ref') or '',
                   'acquisition_id': primary_ref, 'acquisition_refs': sorted(references),
                   'verified_acquisition_refs': sorted(verified_references),
                   'original_ref_verified': (primary_ref in verified_references if primary_ref else
                                             bool(original_ref_verified or (old or {}).get('original_ref_verified')))}
        if old:
            records.patch_row(records.EMAIL_BUTLER_LEASE_BINDINGS, old['id'], payload, conn=conn)
            row_id = old['id']
        else:
            row_id = records.insert_row(records.EMAIL_BUTLER_LEASE_BINDINGS, payload, conn=conn)
        return records.get_row(records.EMAIL_BUTLER_LEASE_BINDINGS, row_id, conn=conn)


def _state(lease):
    state = lease.get('status')
    expiry = lease.get('expires_at')
    if state == 'active' and expiry:
        try:
            parsed = expiry if isinstance(expiry, datetime) else datetime.fromisoformat(str(expiry).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            raise v2.ButlerV2Error('lease_expiry_invalid', '原租约的到期时间无效，不能确认读取权') from None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed <= datetime.now(timezone.utc):
            state = 'expired'
    return state


def _usable(lease):
    return _state(lease) == 'active'


def resolve(email, *, api_base, api_key, credential_ref='', acquisition_id='', lease_id='',
            client_id='', conn=None, for_release=False):
    """用原客户端及完整地址恢复；退租额外要求原操作映射证据。"""
    base, address = v2.normalize_base(api_base), _address(email)
    connection = {'api_base': base, 'api_key': api_key}
    who = v2.me(**connection)
    owner = who['client_id']
    if client_id and owner != client_id:
        raise v2.ButlerV2Error('lease_client_mismatch', '原收件客户端已经变化，保留原地址与归属')
    saved = records.list_rows(records.EMAIL_BUTLER_LEASE_BINDINGS,
        where='api_base = %s AND address_norm = %s AND service = %s',
        params=(base, address, 'openai'), order_by='id DESC', conn=conn)
    rows = [row for row in saved if row['client_id'] == owner]
    foreign = [row for row in saved if row['client_id'] != owner]
    if foreign and (not rows or any(
            acquisition_id and acquisition_id in _refs(row)
            or lease_id and lease_id == row['lease_id'] for row in foreign)):
        raise v2.ButlerV2Error('lease_client_mismatch', '固定原租约属于其他客户端，不能改用当前 Key 恢复')
    if lease_id and str(lease_id).startswith('lse_'):
        pinned_rows = [row for row in rows if row['lease_id'] == lease_id]
    else:
        pinned_rows = [row for row in rows if acquisition_id and acquisition_id in _refs(row)]
    if len(pinned_rows) > 1:
        raise v2.ButlerV2Error('lease_mapping_ambiguous', '原操作存在多个本地租约映射，不能任取最新记录')
    pinned = pinned_rows[0] if pinned_rows else None
    known_id = lease_id if str(lease_id).startswith('lse_') else (pinned or {}).get('lease_id')
    verified = bool(acquisition_id and acquisition_id in _refs(pinned, verified=True))
    if known_id:
        lease = v2.get_lease(known_id, **connection)
        verified = (verified or bool(acquisition_id and lease.get('external_ref') == acquisition_id)
                    or bool(lease_id and str(lease_id).startswith('lse_') and not acquisition_id))
    else:
        leases = v2.list_leases(email=address, service='openai', status='all', **connection)
        originals = [r for r in leases if acquisition_id and r.get('external_ref') == acquisition_id]
        if len(originals) > 1:
            raise v2.ButlerV2Error('lease_mapping_ambiguous', '原归属匹配多个租约，不能任取其中一个')
        if originals:
            lease, verified = originals[0], True
        else:
            active = [r for r in leases if _usable(r)]
            if len(active) != 1:
                code = ('lease_mapping_ambiguous' if len(active) > 1 else
                        'lease_' + str(_state(leases[0])) if leases else 'lease_restore_required')
                raise v2.ButlerV2Error(code, '未找到唯一有效的原地址租约，保留原任务供恢复')
            lease = active[0]
            # 合并迁移的 external_ref 可能属于同组 read binding，只能恢复读取；
            # 退租必须等待精确原操作映射，不能结束后来的新租约。
            verified = False
    if (_address(lease.get('email')) != address or lease.get('service') != 'openai'
            or lease.get('client_id') != owner):
        raise v2.ButlerV2Error('lease_identity_mismatch', 'Butler 租约回执不属于原完整邮箱及服务')
    if for_release and not verified:
        raise v2.ButlerV2Error('lease_original_mapping_required', '退租需要原交接到 v2 租约的精确映射')
    if not for_release and not _usable(lease):
        raise v2.ButlerV2Error('lease_' + str(_state(lease)), '原租约已经结束，不能改领其他邮箱')
    return save(lease, **{k: v for k, v in {'api_base': base, 'credential_ref': credential_ref,
        'client_id': owner, 'acquisition_id': acquisition_id, 'conn': conn,
        'original_ref_verified': verified}.items()})
