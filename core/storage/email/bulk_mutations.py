"""邮箱池集合写入；可加入 Worker 的分块事务，远端退租仍由原同步 Worker 执行。"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import json

from core.operations.contracts import BulkItemResult
from core.storage import postgres as pg, records as store

_TABLES = {'outlook': store.OUTLOOK_POOL, 'generic_api': store.GENERIC_API_POOL,
    'cloudflare_domain': store.DOMAIN_POOL, 'icloud_hide': store.ICLOUD_HIDE_POOL,
    'email_butler': store.EMAIL_BUTLER_POOL}
_STATUSES = frozenset({'available', 'used', 'failed', 'disabled'})
_DERIVATION_STATES = frozenset({'available', 'disabled', 'reserved', 'used', 'replaced', 'retired'})


@contextmanager
def _connection(conn):
    if conn is not None:
        yield conn
    else:
        with store.transaction() as own:
            yield own


def normalize_items(items, *, default_source='outlook', deduplicate=True):
    """目标采用可持久化的 source:email 身份，完整地址仅规范大小写与空白。"""
    values, seen = [], set()
    for raw in items:
        if isinstance(raw, dict):
            source, email = raw.get('source') or default_source, raw.get('email')
        elif isinstance(raw, (tuple, list)) and len(raw) == 2:
            source, email = raw
        else:
            source, email = default_source, raw
            if isinstance(raw, str) and ':' in raw:
                source, email = raw.split(':', 1)
        source = str(source or default_source).strip().lower()
        source = 'outlook' if source == 'all' else source
        email = str(email or '').strip().lower()
        if source not in _TABLES or '@' not in email or any(char.isspace() for char in email):
            raise ValueError('invalid_email_target: 邮箱来源或地址无效')
        key = f'{source}:{email}'
        if not deduplicate or key not in seen:
            values.append(key)
            seen.add(key)
    return tuple(values)


def _load_targets(conn, targets):
    grouped = defaultdict(list)
    for key in targets:
        source, email = key.split(':', 1)
        grouped[source].append(email)
    result = defaultdict(list)
    for source in sorted(grouped):
        spec = _TABLES[source]
        with conn.cursor() as cur:
            cur.execute(f'SELECT * FROM {pg.qualified(spec.name)} WHERE lower(email)=ANY(%s) ORDER BY id FOR UPDATE',
                (sorted(grouped[source]),))
            for raw in cur.fetchall():
                row = store.merge_row(spec, raw)
                result[f"{source}:{str(row['email']).lower()}"].append(row)
    from core.storage.email.collections import lock_keys
    lock_keys(conn, ['registered-account:' + key.split(':', 1)[1] for key in targets])
    return result


def _patch_many(conn, spec, changes):
    """一个来源一次 UPDATE，JSONB 扩展事实按行合并，不覆盖并行写入的其他字段。"""
    if not changes:
        return
    table = pg.qualified(spec.name)
    patches = [{**value, 'updated_at': store._now()} for value in changes.values()]
    fields = sorted(set(spec.promoted) & set().union(*(patch.keys() for patch in patches)))
    assignments = [f'{pg.quote_identifier(field)}=CASE WHEN v.patch ? %s THEN x.{pg.quote_identifier(field)} ELSE p.{pg.quote_identifier(field)} END'
        for field in fields]
    assignments.append('data=COALESCE(p.data,\'{}\'::jsonb) || (v.patch - %s::text[])')
    params = [*fields, list(spec.promoted)]
    values = ','.join('(%s::bigint,%s::jsonb)' for _ in changes)
    for row_id, patch in zip(changes, patches):
        params.extend((row_id, json.dumps(patch, ensure_ascii=False)))
    with conn.cursor() as cur:
        cur.execute(f'UPDATE {table} p SET {", ".join(assignments)} FROM (VALUES {values}) v(id,patch) '
            f'CROSS JOIN LATERAL jsonb_populate_record(NULL::{table},v.patch) x WHERE p.id=v.id', params)


def _result(key, reason_code='', reason='', **data):
    return BulkItemResult(key=key, status='skipped' if reason_code else 'updated',
        reason_code=reason_code or None, reason=reason, data=data or None)


def update_status_many(items, status, note=None, *, conn=None):
    if status not in _STATUSES:
        raise ValueError('invalid_email_status: 邮箱状态无效')
    targets = normalize_items(items)
    if not targets:
        return ()
    with _connection(conn) as current:
        rows = _load_targets(current, targets)
        changes, results = defaultdict(dict), []
        for key in targets:
            source, email = key.split(':', 1)
            parents = rows[key]
            reason, message = '', ''
            if not parents:
                reason, message = 'email_not_found', '邮箱不存在'
            for row in parents:
                if row.get('status') == 'tombstone' or row.get('pool_deleted_at'):
                    reason, message = 'local_email_deleted', '邮箱已删除'
                elif row.get('status') == 'pending_sync' or row.get('service_sync_state') in {'pending', 'sending', 'blocked'}:
                    reason, message = 'service_fact_sync_pending', '邮箱导入尚未完成'
                elif status == 'available':
                    if row.get('status') == 'replaced':
                        reason, message = 'email_replaced', '换绑后邮箱不能恢复为可用'
                if reason:
                    break
            if not reason:
                for row in parents:
                    patch = {'status': status, 'used_at': None if status == 'available' else row.get('used_at') or store._now()}
                    if source == 'icloud_hide':
                        patch['disabled_reason'] = 'manual' if status == 'disabled' else None
                    if note is not None:
                        patch['note'] = note
                    changes[source][row['id']] = patch
            results.append(_result(key, reason, message, source=source, email=email, status=status))
        for source, patches in changes.items():
            _patch_many(current, _TABLES[source], patches)
        return tuple(results)


def delete_many(items, *, conn=None):
    from core.email.email_butler import service_facts
    from core.storage.email.deletion_snapshot import load_snapshot
    targets = normalize_items(items)
    if not targets:
        return ()
    with _connection(conn) as current:
        rows = _load_targets(current, targets)
        changes, results = defaultdict(dict), []
        return_keys = [f"return:{key.split(':', 1)[0]}:{row['id']}" for key, parents in rows.items() for row in parents]
        return_events = {row['event_key']: row for row in store.list_rows(store.EMAIL_SERVICE_SYNC,
            where='event_key=ANY(%s)', params=(return_keys,), conn=current)} if return_keys else {}
        # 已存在子地址的母资源保留历史恢复资料，并停止新增分配。
        parent_ids = defaultdict(set)
        with current.cursor() as cur:
            cur.execute(f'SELECT DISTINCT source,parent_id FROM {pg.qualified(store.EMAIL_ADDRESS_ALLOCATIONS.name)} '
                'WHERE source=ANY(%s) AND parent_id=ANY(%s)',
                (list(_TABLES), [row['id'] for parents in rows.values() for row in parents]))
            for row in cur.fetchall():
                parent_ids[row['source']].add(row['parent_id'])
        snapshot = load_snapshot([row for parents in rows.values() for row in parents
                                  if row.get('status') != 'tombstone'], conn=current)
        protected = {key for key, parents in rows.items()
                     if any(snapshot.confirmed(row) for row in parents if row.get('status') != 'tombstone')}
        returning = [(key.split(':', 1)[0], row) for key, parents in rows.items()
                     if key not in protected for row in parents
                     if row.get('status') != 'tombstone' and not row.get('pool_deleted_at')
                     and row['id'] not in parent_ids[key.split(':', 1)[0]]]
        return_by_pool = service_facts.enqueue_return_many(returning, conn=current,
            snapshot=snapshot, existing=return_events)
        for key in targets:
            source, email = key.split(':', 1)
            parents = rows[key]
            if not parents:
                results.append(_result(key, 'email_not_found', '邮箱不存在', source=source, email=email))
                continue
            if key in protected:
                results.append(_result(key, 'registration_confirmed', '邮箱已确认注册成功，不能删除', source=source, email=email))
                continue
            sync = None
            for row in parents:
                if row.get('status') == 'tombstone' or row.get('pool_deleted_at'):
                    event = return_events.get(f"return:{source}:{row['id']}")
                    sync = service_facts._public(event) if event else sync
                    continue
                if row['id'] in parent_ids[source]:
                    changes[source][row['id']] = {'archived': True, 'status': 'disabled',
                        'derivation_policy': {**(row.get('derivation_policy') or {}), 'enabled': False},
                        'pool_deleted_at': store._now(), 'note': '母资源关联已有子地址，已停止新分配并保留历史恢复资料'}
                else:
                    event = return_by_pool.get((source, row['id']))
                    sync = service_facts._public(event) if event else None
                    patch = {'status': 'tombstone', 'deleted_at': store._now(), 'pool_deleted_at': store._now()}
                    if source == 'email_butler':
                        patch.update(service_tags=service_facts.permanent_tags(row.get('service_tags')),
                            return_sync_state=(event or {}).get('state', 'not_required'))
                    changes[source][row['id']] = patch
            results.append(_result(key, source=source, email=email, local_deleted=True, sync=sync))
        for source, patches in changes.items():
            _patch_many(current, _TABLES[source], patches)
        return tuple(results)


def update_derivation_status_many(ids, state, *, conn=None):
    if state not in _DERIVATION_STATES:
        raise ValueError('invalid_derivation_state: 子地址状态无效')
    targets = tuple(dict.fromkeys(int(value) for value in ids))
    if not targets:
        return ()
    with _connection(conn) as current, current.cursor() as cur:
        spec = store.EMAIL_ADDRESS_ALLOCATIONS
        cur.execute(f'SELECT * FROM {pg.qualified(spec.name)} WHERE id=ANY(%s) ORDER BY id FOR UPDATE', (list(targets),))
        rows = {raw['id']: store.merge_row(spec, raw) for raw in cur.fetchall()}
        changes, results = {}, []
        for key in targets:
            row = rows.get(key)
            reason, message = '', ''
            if row is None:
                reason, message = 'email_allocation_not_found', '子地址不存在'
            elif state in {'available', 'disabled'} and (row['state'] not in {'available', 'disabled'} or any(
                    row.get(field) is not None for field in ('acquisition_id', 'owner_kind', 'owner_id', 'account_id'))):
                reason, message = 'email_allocation_claimed', '已领取或绑定的子地址不能重新投入库存'
            elif row['state'] in {'replaced', 'retired'} and state != row['state']:
                reason, message = 'email_allocation_retired', '已替换或退役的子地址不能重新分配'
            if not reason:
                changes[key] = {'state': state}
            results.append(_result(key, reason, message))
        _patch_many(current, spec, changes)
        return tuple(results)


def _handle_status_chunk(chunk, parameters, *, conn):
    return update_status_many(chunk, parameters['status'], parameters.get('note'), conn=conn)


def _handle_delete_chunk(chunk, parameters, *, conn):
    return delete_many(chunk, conn=conn)


def _after_commit(chunk, parameters, items):
    from core.storage import compat_export
    kinds = {'generic_api': 'generic_api_emails', 'cloudflare_domain': 'domain_emails'}
    changed_sources = set()
    for item in items:
        status = item.get('status') if isinstance(item, dict) else item.status
        data = item.get('data') if isinstance(item, dict) else item.data
        if status == 'updated' and isinstance(data, dict):
            changed_sources.add(data.get('source'))
    for source in sorted(changed_sources & kinds.keys()):
        compat_export.schedule(kinds[source])


def register_handlers(register=None):
    """由运行时显式安装；业务写入与完整分块回执使用 Worker 提供的同一事务。"""
    if register is None:
        from core.operations.bulk_mutation_worker import register_bulk_mutation_handler as register
    register('email_pool_status', _handle_status_chunk,
        parameter_allowlist=('status', 'note'), after_commit=_after_commit)
    register('email_pool_delete', _handle_delete_chunk, after_commit=_after_commit)
