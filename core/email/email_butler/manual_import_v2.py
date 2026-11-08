"""人工确认后的 v2 长期租约导入；每个持久槽位只对应一次分配意图。"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid

from core.email.email_butler import v2
from core.storage import records as record_store
from core.storage.email import butler_manual_imports as store, local_imports as imports
from core.operations import concurrency

PROVIDERS = {
    'icloud_hme': 'iCloud 隐藏邮箱', 'outlook_graph': 'Outlook / Hotmail',
    'cloudflare': 'Cloudflare', 'mailcom': 'mail.com', 'auto': '全部来源',
}


def configuration():
    from config import email as config

    try:
        base = v2.normalize_base(str(getattr(config, 'EMAIL_BUTLER_API_BASE', '') or ''))
    except (ValueError, v2.ButlerV2Error):
        raise ValueError('butler_configuration_required') from None
    key = str(getattr(config, 'EMAIL_BUTLER_API_KEY', '') or '').strip()
    if not key:
        raise ValueError('butler_configuration_required')
    return {'api_base': base, 'api_key': key, 'api_version': 2,
            'fingerprint': hashlib.sha256(json.dumps([base, key]).encode()).hexdigest()}


def filters(data):
    if not isinstance(data, dict):
        raise ValueError('invalid_import_filters')
    provider, count = data.get('provider', 'icloud_hme'), data.get('count')
    if provider not in PROVIDERS:
        raise ValueError('unsupported_import_type')
    if type(count) is not int or count < 1:
        raise ValueError('invalid_import_count')
    if (data.get('identity_type') not in (None, '', 'all')
            or any(data.get(name) for name in ('domain', 'group'))):
        raise ValueError('butler_filter_unsupported: 当前租用接口仅支持来源和数量')
    return {'provider': provider, 'count': count}


def verify_client(who, *, client_id='', allocating=True):
    services = who.get('allowed_services') or []
    permissions = set(who.get('permissions') or [])
    required = {'leases.create', 'leases.long_term', 'leases.read', 'codes.read'} if allocating else {'leases.read'}
    if (not who.get('client_id') or services != '*' and not {'*', 'openai'}.intersection(services)
            or '*' not in permissions and not required.issubset(permissions)
            or client_id and who['client_id'] != client_id):
        raise ValueError('handoff_contract_unsupported: 当前 Key 的服务、客户端或长期租用权限不匹配')
    return str(who['client_id'])


def options():
    return {'ok': True, 'api_version': 2,
            'providers': [{'value': value, 'label': label} for value, label in PROVIDERS.items()],
            'max_count': None, 'identity_types': [], 'domains': [], 'groups': []}


def preview(data):
    selected = filters(data)
    connection = configuration()
    who = v2.me(api_base=connection['api_base'], api_key=connection['api_key'])
    client_id = verify_client(who)
    result = v2.availability(selected['provider'], service='openai',
        api_base=connection['api_base'], api_key=connection['api_key'])
    available = result.get('available')
    if type(available) is not int or available < 0 or result.get('service') != 'openai':
        raise ValueError('butler_availability_invalid: Butler 可用数量响应无效')
    amount = min(available, selected['count'])
    token = str(uuid.uuid4())
    record_store.insert_row(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS, {
        'preview_token': token, 'expires_at': datetime.now(timezone.utc) + timedelta(minutes=15),
        'filters': selected, 'selected': amount, 'candidates': [], 'api_version': 2,
        'config_fingerprint': connection['fingerprint'], 'client_id': client_id,
        'idempotency_retention_seconds': int((who.get('limits') or {}).get('idempotency_retention_seconds') or 604800),
    })
    return {'ok': True, 'api_version': 2, 'preview_token': token, 'available': available,
            'selected': amount, 'count': selected['count'], 'items': [], 'filters': selected}


def create(data):
    from core.email.email_butler import manual_import as service

    if not isinstance(data, dict):
        raise ValueError('invalid_import_request')
    request_id = service._uuid(data.get('request_id'), 'request_id')
    token = service._uuid(data.get('preview_token'), 'preview_token')
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'butler-import-request:' + request_id)
        previous = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'request_id', request_id, conn=conn)
        if previous:
            if previous['preview_token'] != token:
                raise ValueError('import_request_conflict')
            return service._public(previous, conn=conn)
        snapshot = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS, 'preview_token', token, conn=conn)
        if not snapshot:
            raise ValueError('import_preview_not_found')
        expires = snapshot['expires_at']
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
        if expires <= datetime.now(timezone.utc):
            raise ValueError('import_preview_expired')
        connection = configuration()
        if snapshot.get('api_version') != 2 or snapshot['config_fingerprint'] != connection['fingerprint']:
            raise ValueError('import_snapshot_conflict')
        amount = int(snapshot.get('selected') or 0)
        if amount < 1:
            raise ValueError('import_preview_empty')
        profile = imports._fixed_butler_profile(conn, _connection=connection)
        batch_id = str(uuid.uuid4())
        row_id = record_store.insert_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, {
            'batch_id': batch_id, 'request_id': request_id, 'preview_token': token, 'status': 'running',
            'filters': snapshot['filters'], 'profile_id': profile['id'], 'client_id': snapshot['client_id'],
            'api_version': 2, 'error_code': None,
            'idempotency_retention_seconds': snapshot.get('idempotency_retention_seconds', 604800),
        }, conn=conn)
        for position in range(amount):
            intent = 'turb-import:' + hashlib.sha256(f'{batch_id}:{position}'.encode()).hexdigest()
            record_store.insert_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, {
                'batch_id': batch_id, 'position': position, 'address_norm': '',
                'acquisition_id': intent, 'idempotency_key': intent, 'external_ref': intent,
                'candidate': None, 'status': 'pending', 'error_code': None,
                'api_version': 2, 'requested_provider': snapshot['filters']['provider'],
            }, conn=conn)
        result = service._public(record_store.get_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, row_id, conn=conn), conn=conn)
    service._launch(batch_id)
    return result


def _receipt(lease, *, client_id, acquisition_id, provider='auto', external_ref=None,
             original_ref_verified=True, verified_acquisition_refs=None):
    email = imports.butler_forward_address(lease.get('email'))
    if (lease.get('status') != 'active' or lease.get('service') != 'openai'
            or lease.get('client_id') not in (None, '', client_id)
            or lease.get('provider') not in set(PROVIDERS) - {'auto'}
            or provider != 'auto' and lease.get('provider') != provider
            or not lease.get('id') or lease.get('expires_at') is not None
            or external_ref is not None and lease.get('external_ref') != external_ref):
        raise ValueError('handoff_identity_mismatch: 分配回执与原长期租约意图不一致')
    return {'version': 2, 'state': 'issued', 'owner_kind': 'local_inventory', 'owner_id': client_id,
            'client_id': client_id, 'acquisition_id': acquisition_id, 'lease_id': lease['id'],
            'service': 'openai', 'email': email, 'provider': lease['provider'], 'expires_at': None,
            'original_ref_verified': bool(original_ref_verified),
            'verified_acquisition_refs': sorted(set(verified_acquisition_refs or [])
                | ({acquisition_id} if original_ref_verified else set()))}


def _finish(item, profile, lease, receipt, *, client_id):
    from core.email.email_butler import lease_bindings, manual_import as service

    address = receipt['email']
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        current = record_store.get_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item['id'], conn=conn)
        if current['status'] == 'imported':
            return
        existing = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, lower=True, conn=conn)
        if existing and (existing.get('butler_handoff') or {}).get('lease_id') == lease['id']:
            service._patch_item(item['id'], {'status': 'imported', 'address_norm': address,
                'pool_id': existing['id'], 'error_code': None}, conn=conn)
            return
        # 先保存远端回执；即使本地冲突，也保留已经取得的原租约，不自动退租。
        changes = {'address_norm': address, 'candidate': {'email': address, 'provider': lease['provider']},
                   'lease': lease, 'receipt': receipt}
        service._patch_item(item['id'], changes, conn=conn)
        lease_bindings.save(lease, api_base=profile['inbox_locator']['api_base'],
            credential_ref=profile['credential_ref'], client_id=client_id,
            acquisition_id=item['acquisition_id'], conn=conn,
            original_ref_verified=bool(receipt.get('original_ref_verified')))
        if store.conflicts([address], conn=conn, exclude_item_id=item['id']):
            service._patch_item(item['id'], {'status': 'unknown', 'error_code': 'local_email_conflict'}, conn=conn)
            return
        inserted, _ = imports.import_resources([changes['candidate']], source='email_butler',
            _fixed_profile=profile, _handoffs={address: receipt}, _manual_item_id=item['id'], _conn=conn)
        if inserted != 1:
            raise ValueError('local_import_unconfirmed: 本地库存未确认')
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, conn=conn)
        service._patch_item(item['id'], {'status': 'imported', 'pool_id': row['id'], 'error_code': None}, conn=conn)


def _item(batch, item, profile, connection):
    from core.email.email_butler import lease_bindings, manual_import as service

    def claim(conn, execution_id):
        current = record_store.get_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item['id'], conn=conn)
        if current['status'] == 'imported':
            return None
        service._patch_item(item['id'], {'status': 'submitting', 'error_code': None,
            'first_submitted_at': current.get('first_submitted_at') or datetime.now(timezone.utc).isoformat()}, conn=conn)
        return {'execution_id': execution_id}

    context = service._wait_import_execution(batch, f"item:{item['id']}", claim)
    if context is None:
        return
    try:
        with concurrency.execution_scope(context):
            try:
                if batch.get('api_version') == 2:
                    lease = item.get('lease')
                    if lease is not None:
                        # 本地冲突可能跨越管理员收回；重新核对原租约当前状态后再发布。
                        lease = v2.get_lease(lease['id'], api_base=connection['api_base'], api_key=connection['api_key'])
                    if lease is None:
                        submitted = item.get('first_submitted_at')
                        first_at = (datetime.fromisoformat(submitted.replace('Z', '+00:00')) if submitted else None)
                        expired = bool(first_at and (datetime.now(timezone.utc) - first_at).total_seconds()
                            >= int(batch.get('idempotency_retention_seconds') or 604800))
                        if expired:
                            originals = v2.list_leases(service='openai', external_ref=item['external_ref'],
                                status='all', api_base=connection['api_base'], api_key=connection['api_key'])
                            if len(originals) != 1:
                                raise v2.ButlerV2Error('idempotency_result_expired',
                                    '原幂等回执已超出保留期，未找到唯一原租约，继续保留原意图')
                            lease = originals[0]
                        else:
                            lease = v2.create_lease(service='openai', provider=item['requested_provider'],
                                external_ref=item['external_ref'], idempotency_key=item['idempotency_key'],
                                ttl_seconds=None, api_base=connection['api_base'], api_key=connection['api_key'])
                    receipt = _receipt(lease, client_id=batch['client_id'], acquisition_id=item['acquisition_id'],
                        provider=item['requested_provider'], external_ref=item['external_ref'])
                else:
                    # 旧未知交接只找回同地址原归属，绝不能重新调用随机分配。
                    binding = lease_bindings.resolve(item['address_norm'], api_base=connection['api_base'],
                        api_key=connection['api_key'], credential_ref=profile['credential_ref'],
                        acquisition_id=item['acquisition_id'], client_id=batch['client_id'])
                    lease = {**binding, 'id': binding['lease_id']}
                    verified_refs = set(binding.get('verified_acquisition_refs') or [])
                    exact_ref = (item['acquisition_id'] in verified_refs or
                        binding.get('acquisition_id') == item['acquisition_id'] and binding.get('original_ref_verified'))
                    receipt = _receipt(lease, client_id=batch['client_id'], acquisition_id=item['acquisition_id'],
                        original_ref_verified=bool(exact_ref), verified_acquisition_refs=verified_refs)
                _finish(item, profile, lease, receipt, client_id=batch['client_id'])
            except Exception as exc:
                code = str(getattr(exc, 'error_code', '') or getattr(exc, 'code', '')
                           or str(exc).partition(':')[0])
                if not code or any(ch not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for ch in code):
                    code = service._batch_error_code(exc)
                status = getattr(exc, 'status_code', None)
                definite = (item['status'] == 'pending' and isinstance(status, int)
                    and 400 <= status < 500 and status not in {408, 425, 429}
                    and not getattr(exc, 'request_unknown', False))
                service._record_item_error(item, code, rejected=definite)
    finally:
        concurrency.release_execution(context, reason='worker_exit')


def run_batch(batch):
    from core.email.derivation import _profile_credentials
    from core.email.email_butler import manual_import as service

    remaining = [item for item in store.items(batch['batch_id'])
                 if item['status'] in {'pending', 'submitting', 'unknown'}]
    if not remaining:
        return
    profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, int(batch['profile_id']))
    if not profile or profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
        raise ValueError('fixed_route_unavailable')
    connection = _profile_credentials(profile)
    connection['api_base'] = v2.normalize_base(connection['api_base'])
    context = service._wait_import_execution(batch, 'preflight', lambda _conn, execution_id: {'execution_id': execution_id})
    try:
        with concurrency.execution_scope(context):
            who = v2.me(api_base=connection['api_base'], api_key=connection['api_key'])
            verify_client(who, client_id=batch['client_id'], allocating=batch.get('api_version') == 2)
    finally:
        concurrency.release_execution(context, reason='worker_exit')
    record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'], {'status': 'running', 'error_code': None})
    # 固定数量的在途 future，批次再大也不一次性提交全部任务。
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='butler-v2-import') as executor:
        candidates = iter(remaining)
        futures = set()
        exhausted = False
        while futures or not exhausted:
            while len(futures) < 4 and not exhausted:
                item = next(candidates, None)
                if item is None:
                    exhausted = True
                    break
                futures.add(executor.submit(_item, batch, item, profile, connection))
            if futures:
                completed, futures = wait(futures, return_when=FIRST_COMPLETED)
                for future in completed:
                    future.result()
