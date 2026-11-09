"""保留本地永久服务事实；仅退租通过 Butler v2 持久发送。"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone

from core.storage import postgres as pg, records as store

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_worker = None
_stop = threading.Event()
_TABLE = store.EMAIL_SERVICE_SYNC


def _tables():
    from core.email.inventory import TABLES
    return TABLES


def _address(value):
    return str(value or '').strip().lower()


def permanent_tags(tags=None):
    """导入后的 OpenAI 标签只能追加，保留其他服务。"""
    return sorted({'openai', *(str(tag).strip().lower() for tag in tags or [] if str(tag).strip())})


def validate_fact(value, *, expected_address=None):
    if (not isinstance(value, dict) or value.get('service') != 'openai'
            or value.get('ever_imported') is not True or value.get('permanent') is not True):
        raise ValueError('service_fact_receipt_invalid: Butler 未确认永久 OpenAI 导入事实')
    if expected_address and value.get('address') != _address(expected_address):
        raise ValueError('service_fact_receipt_mismatch: Butler 永久事实完整地址不一致')
    return {'service': 'openai', 'ever_imported': True, 'permanent': True,
            **({'address': _address(expected_address)} if expected_address else {})}


def _new_route():
    from config import email as config
    from core.email.derivation import _save_profile_secret
    base = str(getattr(config, 'EMAIL_BUTLER_API_BASE', '') or '').strip().rstrip('/')
    key = str(getattr(config, 'EMAIL_BUTLER_API_KEY', '') or '').strip()
    try:
        from core.email.email_butler.v2 import normalize_base
        base = normalize_base(base)
        valid = bool(base)
    except ValueError:
        valid = False
    if not valid or not key:
        return {'api_base': '', 'credential_ref': '', 'error_code': 'service_fact_configuration_missing'}
    reference = 'EMAIL_SERVICE_FACT_SECRET_' + hashlib.sha256((base + ':' + key).encode()).hexdigest()[:20].upper()
    _save_profile_secret(reference, key)
    return {'api_base': base, 'credential_ref': reference}


def enqueue_import(source, row, *, conn, final_status='available', as_registered=False):
    """v2 不接收业务事实：原子保存本地证据并完成本地导入。"""
    from core.email.email_butler.inventory_handoff import _consumer_instance
    address = _address(row['email'])
    event_key = f"{'registered-import' if as_registered else 'import'}:{source}:{row['id']}"
    existing = store.get_row_by(_TABLE, 'event_key', event_key, conn=conn)
    if existing:
        return existing
    instance = _consumer_instance()
    evidence = 'turb-import:' + hashlib.sha256(f"{instance}:{event_key}:{address}".encode()).hexdigest()
    payload = {'address': address, 'service': 'openai', 'fact_type': 'imported', 'evidence_id': evidence,
               'source_instance': instance, 'source_record': f"{source}:{row['id']}",
               'observed_at': datetime.now(timezone.utc).isoformat()}
    event_id = store.insert_row(_TABLE, {'event_key': event_key, 'kind': 'import', 'address_norm': address,
        'source': source, 'pool_id': row['id'], 'state': 'local_only', 'attempts': 0,
        'api_base': '', 'credential_ref': '', 'error_code': 'service_facts_unsupported',
        'payload': payload, 'final_status': final_status, 'as_registered': as_registered}, conn=conn)
    event = store.get_row(_TABLE, event_id, conn=conn)
    _publish_import_local(event, row, conn=conn)
    return event


def _publish_import_local(event, row, *, conn):
    """新导入和旧 pending_sync 共用发布规则，不伪造远端事实回执。"""
    if not row or _address(row['email']) != event['address_norm']:
        return
    if row.get('status') in {'tombstone', 'replaced', 'request_unknown', 'reserved', 'running'}:
        return
    final_status = event.get('final_status') or 'available'
    if event['source'] == 'icloud_hide' and row.get('remote_active') is False:
        final_status = 'disabled'
    changes = {'service_sync_state': 'local_only', 'service_sync_error': None,
        'service_fact_scope': 'local', 'service_fact_permanent': True,
        'service_tags': permanent_tags(row.get('service_tags'))}
    if row.get('status') in {'pending_sync', 'available'}:
        changes['status'] = final_status
    store.patch_row(_tables()[event['source']], row['id'], changes, conn=conn)
    if event.get('as_registered'):
        from core.storage.db_legacy import import_registered_email_accounts
        imported, _ = import_registered_email_accounts(
            [{**row, 'expires_at': row.get('registered_expires_at')}], event['source'],
            _service_fact_confirmed=True, _conn=conn)
        if not imported and not store.get_row_by(store.ACCOUNTS, 'email', row['email'], lower=True, conn=conn):
            raise ValueError('registered_import_conflict: 原已注册账号导入无法完成')


def enqueue_return(source, row, *, conn):
    """删除前固定原远端归属；无远端交接的普通素材无须释放其他客户端资源。"""
    address = _address(row['email'])
    event_key = f"return:{source}:{row['id']}"
    existing = store.get_row_by(_TABLE, 'event_key', event_key, conn=conn)
    if existing:
        return existing
    profile_id = row.get('local_inbox_profile_id') or row.get('inbox_profile_id') or (row.get('derivation_policy') or {}).get('inbox_profile_id')
    profile = store.get_row(store.EMAIL_INBOX_PROFILES, int(profile_id), conn=conn) if profile_id else None
    from core.email.email_butler.client import original_handoff_acquisition
    acquisition = original_handoff_acquisition(address, row=row, profile=profile)
    lease_id = str((row.get('butler_handoff') or {}).get('lease_id') or '')
    if source != 'email_butler' and not acquisition and not lease_id:
        return None
    error = None
    if not profile or profile.get('connector') != 'forward_butler' or profile.get('state') != 'active':
        error = 'fixed_route_unavailable'
    elif not acquisition and not lease_id:
        error = 'acquisition_required'
    payload = {'email': address, 'service': 'openai', 'acquisition_id': acquisition}
    if lease_id:
        payload['lease_id'] = lease_id
    client_id = str((row.get('butler_handoff') or {}).get('client_id') or '')
    if client_id:
        payload['client_id'] = client_id
    from core.storage.email.deletion import lease_return_block_reason

    # 固定删除前的使用状态，发送时不能把 tombstone 当作从未使用的证据。
    evidence = {'version': 1, 'pool_status': row.get('status'), 'used_at': row.get('used_at')}
    safety_reason = lease_return_block_reason(address, conn=conn, pool=row,
        account_id=row.get('registered_account_id'),
        unused_inventory=evidence['pool_status'] == 'available' and not evidence['used_at'])
    retained = safety_reason in {'registration_confirmed', 'registration_result_unverified'}
    if retained:
        state = 'local_only'
    elif safety_reason == 'registration_active':
        state = 'pending'
    else:
        state = 'blocked' if error else 'pending'
    event_id = store.insert_row(_TABLE, {'event_key': event_key, 'kind': 'return', 'address_norm': address,
        'source': source, 'pool_id': row['id'], 'state': state, 'attempts': 0,
        'profile_id': profile_id,
        'api_base': ((profile or {}).get('inbox_locator') or {}).get('api_base', ''),
        'credential_ref': (profile or {}).get('credential_ref') or '',
        'error_code': safety_reason or error, 'payload': payload, 'return_evidence': evidence}, conn=conn)
    return store.get_row(_TABLE, event_id, conn=conn)


def _public(row):
    error = row.get('error_code')
    retained = row['kind'] == 'return' and error in {
        'registration_confirmed', 'registration_result_unverified', 'registration_active'}
    messages = {
        'registration_confirmed': '本地已移除，注册成功已确认，已保留原租约',
        'registration_result_unverified': '本地已移除，注册结果未确认，已保留原租约',
        'registration_active': '本地已移除，任务仍在执行，暂不退还原租约',
    }
    message = messages.get(error, '') if row['kind'] == 'return' else ''
    if row['kind'] == 'return' and not message:
        message = {'pending': '本地已移除，原租约退还处理中',
                   'sending': '本地已移除，原租约退还处理中',
                   'delivered': '本地已移除，原租约已退还',
                   'blocked': '本地已移除，原租约尚未退还'}.get(row['state'], '')
    return {'source': row['source'], 'email': row['address_norm'], 'kind': row['kind'],
            'state': row['state'], 'error_code': error, 'lease_retained': retained, 'message': message,
            'permanent': row['kind'] == 'return' or row['state'] in {'delivered', 'local_only'},
            'scope': 'local' if row['state'] == 'local_only' else 'remote',
            'updated_at': row.get('updated_at')}


def sync_status(source, email):
    rows = store.list_rows(_TABLE, where='source=%s AND address_norm=%s', params=(source, _address(email)),
                           order_by='id DESC', limit=1)
    return _public(rows[0]) if rows else {'state': 'not_required', 'kind': 'return', 'error_code': None, 'permanent': True}


def list_sync(limit=100):
    rows = store.list_rows(_TABLE, order_by="CASE WHEN state IN ('pending','sending','blocked') THEN 0 ELSE 1 END, id DESC",
                           limit=max(1, min(int(limit), 500)))
    return [_public(row) for row in rows]


def summary():
    counts = {state: 0 for state in ('pending', 'sending', 'delivered', 'blocked', 'local_only')}
    with store.transaction() as conn, conn.cursor() as cur:
        cur.execute(f'SELECT state,count(*) AS n FROM {pg.qualified(_TABLE.name)} GROUP BY state')
        for row in cur.fetchall():
            if row['state'] in counts:
                counts[row['state']] = int(row['n'])
    return counts


def pending_count(source, emails):
    with store.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(DISTINCT address_norm) AS n FROM {pg.qualified(_TABLE.name)} "
                    "WHERE source=%s AND kind='import' AND state NOT IN ('delivered','local_only') AND address_norm=ANY(%s)",
                    (source, sorted({_address(value) for value in emails})))
        return int(cur.fetchone()['n'])


def retry(source, email, kind):
    if kind not in {'import', 'return'}:
        raise ValueError('service_sync_kind_invalid: 同步类型无效')
    with store.transaction() as conn:
        rows = store.list_rows(_TABLE, where='source=%s AND address_norm=%s AND kind=%s',
            params=(source, _address(email), kind), order_by='id DESC', limit=1, conn=conn)
        if not rows:
            return False
        store.get_row(_tables()[source], rows[0]['pool_id'], conn=conn, for_update=True)
        row = store.get_row(_TABLE, rows[0]['id'], conn=conn, for_update=True)
        if row['state'] in {'sending', 'delivered', 'local_only'}:
            return True
        changes = {'state': 'pending', 'next_attempt_at': None, 'error_code': None}
        # 尚未建立连接的意图可首次补齐连接；已固定的原连接永不改绑。
        if kind == 'return' and row.get('error_code') in {'fixed_route_unavailable', 'acquisition_required'}:
            profile = store.get_row(store.EMAIL_INBOX_PROFILES, row['profile_id'], conn=conn) if row.get('profile_id') else None
            if (not profile or profile.get('state') != 'active' or profile.get('connector') != 'forward_butler'
                    or not (row['payload'].get('acquisition_id') or row['payload'].get('lease_id'))):
                changes.update(state='blocked', error_code=row['error_code'])
        store.patch_row(_TABLE, row['id'], changes, conn=conn)
        _update_pool(row, changes['state'], changes.get('error_code'), conn=conn)
    return True


def _update_pool(event, state, error, *, conn):
    row = store.get_row(_tables()[event['source']], event['pool_id'], conn=conn, for_update=True)
    if event['kind'] == 'return':
        if row:
            store.patch_row(_tables()[event['source']], row['id'],
                {'return_sync_state': state, 'return_sync_error': error}, conn=conn)
        return
    if row and row.get('status') == 'pending_sync':
        store.patch_row(_tables()[event['source']], row['id'],
            {'service_sync_state': state, 'service_sync_error': error}, conn=conn)


def _claim_next():
    with store.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {pg.qualified(_TABLE.name)} WHERE "
            "(kind='import' AND state IN ('pending','blocked')) "
            "OR (state='pending' AND (next_attempt_at IS NULL OR next_attempt_at<=now())) "
            "OR (state='sending' AND lease_until<=now()) ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1")
        row = store.merge_row(_TABLE, cur.fetchone())
        if not row:
            return None
        changes = {'state': 'sending', 'lease_owner': uuid.uuid4().hex,
                   'lease_until': datetime.now(timezone.utc) + timedelta(seconds=120), 'attempts': row['attempts'] + 1}
        store.patch_row(_TABLE, row['id'], changes, conn=conn)
        return {**row, **changes}


def _finish(event, *, delivered=False, blocked=False, local_only=False, error=None, status_code=None):
    with store.transaction() as conn, conn.cursor() as cur:
        if event.get('as_registered'):
            from core.storage.email.validity import lock_email_validity
            lock_email_validity(conn, shared=True)
        # 与库存结果及管理操作一致：先锁池行，事件锁最后获取。
        row = store.get_row(_tables()[event['source']], event['pool_id'], conn=conn, for_update=True)
        if event.get('as_registered'):
            store.advisory_xact_lock(conn, 'registered-account:' + event['address_norm'])
        cur.execute(f"SELECT id FROM {pg.qualified(_TABLE.name)} WHERE id=%s AND state='sending' AND lease_owner=%s FOR UPDATE",
                    (event['id'], event['lease_owner']))
        if not cur.fetchone():
            return
        state = 'local_only' if local_only else 'delivered' if delivered else 'blocked' if blocked else 'pending'
        if local_only and event['kind'] == 'import':
            _publish_import_local(event, row, conn=conn)
        if delivered and event['kind'] == 'import':
            table = _tables()[event['source']]
            if row and _address(row['email']) == event['address_norm'] and row.get('status') == 'pending_sync':
                final_status = event.get('final_status') or 'available'
                if event['source'] == 'icloud_hide' and row.get('remote_active') is False:
                    final_status = 'disabled'
                store.patch_row(table, row['id'], {'status': final_status,
                    'service_sync_state': 'delivered', 'service_sync_error': None,
                    'service_tags': permanent_tags(row.get('service_tags')), 'service_fact_permanent': True}, conn=conn)
                if event.get('as_registered'):
                    from core.storage.db_legacy import import_registered_email_accounts
                    imported, _ = import_registered_email_accounts(
                        [{**row, 'expires_at': row.get('registered_expires_at')}], event['source'],
                        _service_fact_confirmed=True, _conn=conn)
                    if not imported and not store.get_row_by(store.ACCOUNTS, 'email', row['email'], lower=True, conn=conn):
                        raise ValueError('registered_import_conflict: 原已注册账号导入无法完成')
        _update_pool(event, state, error, conn=conn)
        delay = 5 if error == 'registration_active' else min(3600, 5 * 2 ** min(event['attempts'], 10))
        store.patch_row(_TABLE, event['id'], {'state': state, 'error_code': error,
            'error_status_code': status_code if type(status_code) is int else None,
            'lease_owner': None, 'lease_until': None,
            'next_attempt_at': datetime.now(timezone.utc) + timedelta(seconds=delay) if state == 'pending' else None,
            'delivered_at': datetime.now(timezone.utc) if delivered else None}, conn=conn)


def _delivery_error(exc, kind):
    """按故障层归类，只保存错误码，不持久化远端正文或带凭据地址。"""
    import requests
    prefix = 'service_fact' if kind == 'import' else 'return'
    code = str(getattr(exc, 'error_code', '') or '')
    if not code and isinstance(exc, ValueError):
        code = str(exc).split(':', 1)[0]
    if re.fullmatch(r'[a-z][a-z0-9_]{1,100}', code):
        return code
    cause = exc.__cause__ or exc
    if isinstance(cause, requests.Timeout):
        return prefix + '_timeout'
    if isinstance(cause, requests.ConnectionError):
        return prefix + '_connection_failed'
    status = getattr(exc, 'status_code', None)
    if isinstance(status, int):
        return prefix + '_http_' + str(status)
    return prefix + '_response_invalid' if isinstance(cause, ValueError) else prefix + '_delivery_failed'


def dispatch_once():
    event = _claim_next()
    if not event:
        return False
    if event['kind'] == 'import':
        _finish(event, local_only=True, error='service_facts_unsupported')
        return True
    try:
        from config.runtime import read_persisted_values
        from core.email.email_butler import client
        from core.storage.email.deletion import lease_return_block_reason

        # 删除可先隐藏素材；与成功落库共享地址锁，退租前再次核对。
        # _finish 会获取池行锁，必须在退出本事务后调用，保持统一取锁顺序。
        with store.transaction() as conn:
            pool = store.get_row(_tables()[event['source']], event['pool_id'], conn=conn, for_update=True)
            store.advisory_xact_lock(conn, 'registered-account:' + event['address_norm'])
            store.advisory_xact_lock(conn, 'email-usage:' + event['address_norm'])
            evidence = event.get('return_evidence') or {}
            unused = (isinstance(evidence, dict) and evidence.get('version') == 1
                and evidence.get('pool_status') == 'available' and not evidence.get('used_at'))
            safety_reason = lease_return_block_reason(event['address_norm'], conn=conn, pool=pool,
                account_id=(pool or {}).get('registered_account_id'), unused_inventory=unused)
            if safety_reason:
                result = None
            else:
                result = _return_original_lease(event, client, read_persisted_values)
        if safety_reason:
            _finish(event, local_only=safety_reason != 'registration_active', error=safety_reason)
            return True
        if result.get('ok') is False:
            code = str(result.get('error_code') or 'return_response_invalid')
            if not re.fullmatch(r'[a-z][a-z0-9_]{1,100}', code):
                code = 'return_response_invalid'
            unknown = result.get('request_unknown') is True
            retryable = result.get('retryable') is True
            _finish(event, blocked=not unknown and not retryable, error=code, status_code=result.get('status_code'))
            return True
        if (result.get('email') != event['address_norm'] or result.get('service') != 'openai'
                or result.get('released') is not True):
            raise ValueError('return_receipt_mismatch')
        _finish(event, delivered=True)
    except Exception as exc:
        status = getattr(exc, 'status_code', None)
        code = _delivery_error(exc, event['kind'])
        _finish(event, blocked=isinstance(status, int) and 400 <= status < 500 and status not in {408, 425, 429},
                error=code, status_code=status)
    return True


def _return_original_lease(event, client, read_persisted_values):
    key = str(read_persisted_values().get(event.get('credential_ref')) or os.environ.get(event.get('credential_ref') or '', '') or '')
    if not key or not event.get('api_base'):
        return {'ok': False, 'error_code': 'original_credential_missing'}
    return client.return_account(event['address_norm'], service='openai',
        api_base=event['api_base'], api_key=key,
        acquisition_id=event['payload'].get('acquisition_id') or '',
        lease_id=event['payload'].get('lease_id') or '',
        client_id=event['payload'].get('client_id') or '')


def worker_status():
    return {'alive': bool(_worker and _worker.is_alive()), 'counts': summary()}


def _run():
    while not _stop.is_set():
        try:
            if dispatch_once():
                continue
        except Exception as exc:
            logger.warning('邮箱服务同步暂不可用：%s', type(exc).__name__)
        _stop.wait(3)


def start_worker():
    global _worker
    with _lock:
        if _worker and _worker.is_alive():
            return False
        store.init()
        _stop.clear()
        _worker = threading.Thread(target=_run, name='email-service-sync', daemon=True)
        _worker.start()
        return True
