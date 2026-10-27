"""本地库存是新邮箱领取的唯一事实；收件连接仍由原来源固定保存。"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime

from core import postgres_store, record_store
from core.email_resource_lifetime import eligibility_sql, require_usable

TABLES = {
    'outlook': record_store.OUTLOOK_POOL,
    'generic_api': record_store.GENERIC_API_POOL,
    'cloudflare_domain': record_store.DOMAIN_POOL,
    'icloud_hide': record_store.ICLOUD_HIDE_POOL,
    'email_butler': record_store.EMAIL_BUTLER_POOL,
}
_COUNT_FIELDS = ('total', 'available', 'used', 'failed', 'disabled')


class LocalEmailInventoryError(RuntimeError):
    """可分类的本地库存或业务身份错误。"""
    def __init__(self, code: str, message: str):
        super().__init__(f'{code}: {message}')
        self.error_code = code
        self.identity_locked = code in {'email_derivation_identity_conflict', 'local_email_identity_unavailable'}
        self.request_unknown = code == 'request_unknown'


@contextmanager
def _connection(conn=None):
    if conn is not None:
        yield conn
    else:
        with record_store.transaction() as current:
            yield current


def _table(source: str):
    if source not in TABLES:
        raise LocalEmailInventoryError('local_inventory_source_required', '新注册只允许从已导入的本地邮箱库存领取')
    return TABLES[source]


def find_local_email(address: str, *, conn=None) -> tuple[str, dict] | None:
    """按完整邮箱查询，供固定收件恢复及跨来源导入去重使用。"""
    address = str(address or '').strip().lower()
    with _connection(conn) as current:
        for source, table in TABLES.items():
            row = record_store.get_row_by(table, 'email', address, lower=True, conn=current)
            if row:
                return source, row
    return None


def import_conflict(address: str, *, conn=None) -> str:
    """导入方持有 registered-account 地址锁后调用；不访问远端服务。"""
    address = str(address or '').strip().lower()
    with _connection(conn) as current:
        if find_local_email(address, conn=current):
            return 'local_email_duplicate'
        if record_store.get_row_by(record_store.ACCOUNTS, 'email', address, lower=True, conn=current):
            return 'registered_email'
        if record_store.get_row_by(record_store.EMAIL_ADDRESS_ALLOCATIONS, 'address_norm', address, conn=current):
            return 'email_address_allocated'
        if record_store.get_row_by(record_store.LOCAL_EMAIL_CLAIMS, 'address_norm', address, conn=current):
            return 'local_email_claimed'
        table = postgres_store.qualified(record_store.EMAIL_BUTLER_CLAIM_INTENTS.name)
        with current.cursor() as cursor:
            cursor.execute(f"SELECT 1 FROM {table} WHERE lower(COALESCE(address_norm, data->'mailbox'->>'email', '')) = %s AND status NOT IN ('prepared', 'rejected') LIMIT 1", (address,))
            if cursor.fetchone():
                return 'email_remote_claimed'
    return ''


def _eligibility(source: str, *, alias: str = 'p', batch_id: str = '') -> tuple[str, list]:
    """容量与领取共用同一 SQL 条件，旧占用记录不能被重新导入或重置复用。"""
    _table(source)
    email = f'lower({alias}.email)'
    conditions = [f"{alias}.status = 'available'", f'{alias}.registered_account_id IS NULL',
        f"NULLIF(BTRIM({alias}.used_at), '') IS NULL",
        f"lower(COALESCE({alias}.data->>'email_invalid', 'false')) NOT IN ('true', '1', 'yes')",
        f"lower(COALESCE({alias}.data->>'remote_active', 'true')) NOT IN ('false', '0', 'no')",
        f"lower(COALESCE({alias}.data->>'archived', 'false')) NOT IN ('true', '1', 'yes')",
        eligibility_sql(alias)]
    handoff = f"{alias}.data->'butler_handoff'"
    confirmed_handoff = (f"{handoff}->>'version' = '1' AND {handoff}->>'state' = 'issued' "
        f"AND {handoff}->>'owner_kind' = 'local_inventory' "
        + ''.join(f"AND NULLIF(BTRIM({handoff}->>'{field}'), '') IS NOT NULL "
                  for field in ('acquisition_id', 'owner_id', 'identity_id')))
    if source == 'email_butler':
        profiles = postgres_store.qualified(record_store.EMAIL_INBOX_PROFILES.name)
        conditions += [f"{alias}.data->>'provider' = 'icloud_hme'",
            f"{alias}.data->>'recipient_mode' = 'forwarded_exact_v1'",
            f"{alias}.data->>'strict_family' = 'true'",
            confirmed_handoff,
            f"EXISTS (SELECT 1 FROM {profiles} profile WHERE profile.id::text = {alias}.data->>'inbox_profile_id' AND profile.state = 'active' AND profile.connector = 'forward_butler' AND NULLIF(BTRIM(profile.credential_ref), '') IS NOT NULL AND NULLIF(BTRIM(profile.data->'inbox_locator'->>'api_base'), '') IS NOT NULL AND strpos(COALESCE(profile.data->'inbox_locator'->>'mailbox_email', ''), '@') > 1)"]
    if source == 'icloud_hide':
        profiles = postgres_store.qualified(record_store.EMAIL_INBOX_PROFILES.name)
        conditions.append(f"EXISTS (SELECT 1 FROM {profiles} profile WHERE profile.id::text = {alias}.data->'derivation_policy'->>'inbox_profile_id' AND profile.state = 'active' AND profile.connector IN ('forward_butler', 'forward_imap') AND NULLIF(BTRIM(profile.credential_ref), '') IS NOT NULL AND ((profile.connector = 'forward_butler' AND NULLIF(BTRIM(profile.data->'inbox_locator'->>'api_base'), '') IS NOT NULL AND strpos(COALESCE(profile.data->'inbox_locator'->>'mailbox_email', ''), '@') > 1) OR (profile.connector = 'forward_imap' AND NULLIF(BTRIM(profile.data->'inbox_locator'->>'server'), '') IS NOT NULL AND strpos(COALESCE(profile.data->'inbox_locator'->>'email', ''), '@') > 1)))")
        conditions.append(f"EXISTS (SELECT 1 FROM {profiles} profile WHERE profile.id::text = {alias}.data->'derivation_policy'->>'inbox_profile_id' AND (profile.connector = 'forward_imap' OR ({confirmed_handoff})))")
    for spec, column in ((record_store.ACCOUNTS, 'email'),
                         (record_store.EMAIL_ADDRESS_ALLOCATIONS, 'address_norm'),
                         (record_store.LOCAL_EMAIL_CLAIMS, 'address_norm')):
        table = postgres_store.qualified(spec.name)
        conditions.append(f'NOT EXISTS (SELECT 1 FROM {table} held WHERE lower(held.{column}) = {email})')
    remote = postgres_store.qualified(record_store.EMAIL_BUTLER_CLAIM_INTENTS.name)
    conditions.append(f"NOT EXISTS (SELECT 1 FROM {remote} held WHERE lower(COALESCE(held.address_norm, held.data->'mailbox'->>'email', '')) = {email} AND held.status NOT IN ('prepared', 'rejected'))")
    for other, spec in TABLES.items():
        if other != source:
            conditions.append(f"NOT EXISTS (SELECT 1 FROM {postgres_store.qualified(spec.name)} occupied WHERE lower(occupied.email) = {email} AND (COALESCE(occupied.status, '') <> 'available' OR occupied.registered_account_id IS NOT NULL OR NULLIF(BTRIM(occupied.used_at), '') IS NOT NULL))")
    # 兼容历史跨来源重复导入：完整地址只归第一个本地来源，不能重复计数或领取。
    for previous, spec in TABLES.items():
        if previous == source:
            break
        conditions.append(f'NOT EXISTS (SELECT 1 FROM {postgres_store.qualified(spec.name)} duplicate WHERE lower(duplicate.email) = {email})')
    params = []
    if batch_id:
        claims = postgres_store.qualified(record_store.REGISTRATION_BATCH_EMAIL_CLAIMS.name)
        jobs = postgres_store.qualified(record_store.JOBS.name)
        conditions += [f'NOT EXISTS (SELECT 1 FROM {claims} prior WHERE prior.batch_id = %s AND lower(prior.email) = {email})',
                       f'NOT EXISTS (SELECT 1 FROM {jobs} prior WHERE prior.batch_id = %s AND lower(prior.email) = {email})']
        params = [batch_id, batch_id]
    return ' AND '.join(conditions), params


def summary(source: str | None = None) -> dict:
    """只汇总本地五池；available 使用与领取一致的健康和占用过滤。"""
    selected = [source] if source is not None else list(TABLES)
    rows = []
    with _connection() as conn, conn.cursor() as cursor:
        for item in selected:
            table = postgres_store.qualified(_table(item).name)
            eligible, params = _eligibility(item)
            cursor.execute(f"SELECT count(*) AS total, count(*) FILTER (WHERE {eligible}) AS available, count(*) FILTER (WHERE p.status IN ('used','reserved','registered','request_unknown','unknown','replaced')) AS used, count(*) FILTER (WHERE p.status = 'failed') AS failed, count(*) FILTER (WHERE p.status = 'disabled') AS disabled FROM {table} p", params)
            counts = cursor.fetchone()
            rows.append({'source': item, **{field: int(counts[field] or 0) for field in _COUNT_FIELDS}})
    return {**{field: sum(row[field] for row in rows) for field in _COUNT_FIELDS}, 'sources': rows}


def has_claim(address: str, *, conn=None) -> bool:
    with _connection(conn) as current:
        return record_store.get_row_by(record_store.LOCAL_EMAIL_CLAIMS, 'address_norm',
            str(address or '').strip().lower(), conn=current) is not None


def record_outcome(address: str, *, source: str | None = None, status='used', note=None) -> bool:
    """本地领取只更新本地结果；未知结果与 available 回收请求仍保留原占用。"""
    address = str(address or '').strip().lower()
    with _connection() as conn:
        previous = record_store.get_row_by(record_store.LOCAL_EMAIL_CLAIMS, 'address_norm', address, conn=conn)
        if not previous:
            # Butler 人工库存从不依赖远端租约，即使仅做了预览/收码也不远端释放。
            if source not in {'email_butler', 'icloud_hide'}:
                return False
            row = record_store.get_row_by(TABLES[source], 'email', address, lower=True, conn=conn)
            if not row:
                return False
            row = record_store.get_row(TABLES[source], row['id'], conn=conn, for_update=True)
        else:
            if source and source != previous['source']:
                raise LocalEmailInventoryError('email_derivation_identity_conflict', '本地领取结果来源不一致')
            source = previous['source']
            row = record_store.get_row(TABLES[source], previous['pool_id'], conn=conn, for_update=True)
            if not row:
                return True
        record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        normalized = str(status or '').strip().lower()
        if normalized in {'request_unknown', 'unknown', 'running', 'reserved', 'available'}:
            return True
        normalized = {'success': 'used', 'succeeded': 'used', 'registered': 'used'}.get(normalized, normalized)
        if normalized not in {'used', 'failed', 'disabled', 'replaced', 'retired'}:
            raise LocalEmailInventoryError('local_email_status_invalid', '不支持的本地邮箱结果状态')
        from core.email_usage_reports import enqueue, has_success
        with conn.cursor() as cursor:
            if normalized != 'used' and has_success(address, cursor=cursor):
                return True
            enqueue(address, status=normalized, source=source, row=row, claim=previous, cursor=cursor)
        changes = {'status': normalized}
        if note is not None:
            changes['note'] = str(note)
        record_store.patch_row(TABLES[source], row['id'], changes, conn=conn)
        if previous:
            record_store.patch_row(record_store.LOCAL_EMAIL_CLAIMS, previous['id'], {'status': normalized}, conn=conn)
        return True


def _bind_job(conn, row: dict, source: str, claim_id: int, batch_id: str, job_id: int | None) -> None:
    changes = {'email': row['email'], 'email_source': source, 'email_lease_id': f'local:{claim_id}'}
    if job_id is not None:
        job = record_store.get_row(record_store.JOBS, int(job_id), conn=conn, for_update=True)
        if not job:
            raise LocalEmailInventoryError('local_email_job_missing', '领取所属注册任务不存在')
        if job.get('email') and str(job['email']).lower() != str(row['email']).lower():
            raise LocalEmailInventoryError('email_derivation_identity_conflict', '注册任务已绑定其他完整邮箱')
        record_store.patch_row(record_store.JOBS, job['id'], changes, conn=conn)
        root_id = int(job.get('root_job_id') or job['id'])
        if root_id != int(job_id):
            root = record_store.get_row(record_store.JOBS, root_id, conn=conn, for_update=True)
            if root and root.get('email') and str(root['email']).lower() != str(row['email']).lower():
                raise LocalEmailInventoryError('email_derivation_identity_conflict', '根任务已绑定其他完整邮箱')
            if root:
                record_store.patch_row(record_store.JOBS, root_id, changes, conn=conn)
        attempts = postgres_store.qualified('registration_attempts')
        with conn.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s) AS relation', (attempts,))
            if cursor.fetchone()['relation']:
                cursor.execute(f'UPDATE {attempts} SET email = %s, email_snapshot = %s, email_source = %s, data = data || %s::jsonb, updated_at = now() WHERE root_job_id = %s',
                               (row['email'], row['email'], source, json.dumps(changes), root_id))
        batch_id = batch_id or str(job.get('batch_id') or '')
    if batch_id:
        key = batch_id + '\x1f' + str(row['email']).lower()
        previous = record_store.get_row_by(record_store.REGISTRATION_BATCH_EMAIL_CLAIMS, 'claim_key', key, conn=conn)
        if previous and previous.get('job_id') != job_id:
            raise LocalEmailInventoryError('email_derivation_identity_conflict', '本批次其他任务已领取该邮箱')
        if not previous:
            record_store.insert_row(record_store.REGISTRATION_BATCH_EMAIL_CLAIMS, {
                'claim_key': key, 'batch_id': batch_id, 'email': str(row['email']).lower(),
                'job_id': job_id, 'email_source': source, 'claimed_at': datetime.now().isoformat(),
            }, conn=conn)


def claim(source: str, *, owner_kind=None, owner_id=None, acquisition_id=None,
          batch_id=None, job_id=None) -> dict | None:
    """同事务领取本地行并保存业务意图；重入只恢复原完整地址。"""
    spec = _table(source)
    stable_id = str(acquisition_id or (f'local-job:{job_id}' if job_id is not None else 'local:' + uuid.uuid4().hex))
    owner_kind = str(owner_kind or ('registration_job' if job_id is not None else 'local'))
    owner_id = str(owner_id if owner_id is not None else job_id if job_id is not None else stable_id)
    batch = str(batch_id or '').strip()
    with _connection() as conn:
        record_store.advisory_xact_lock(conn, 'local-email-acquisition:' + stable_id)
        remote = record_store.get_row_by(record_store.EMAIL_BUTLER_CLAIM_INTENTS, 'acquisition_id', stable_id, conn=conn)
        if remote:
            if source not in {'icloud_hide', 'email_butler'}:
                raise LocalEmailInventoryError('email_derivation_identity_conflict', '原 Butler 意图不能切换本地来源')
            if (remote['owner_kind'], str(remote['owner_id'])) != (owner_kind, owner_id):
                raise LocalEmailInventoryError('email_derivation_identity_conflict', '原远端意图属于其他业务')
            if remote['status'] == 'claimed' and remote.get('mailbox'):
                return {**remote['mailbox'], 'status': 'used', '_legacy_butler_intent': remote}
            raise LocalEmailInventoryError('request_unknown', '原 Butler 领取意图尚未明确，保留原意图，不能换领本地邮箱')
        previous = record_store.get_row_by(record_store.LOCAL_EMAIL_CLAIMS, 'acquisition_id', stable_id, conn=conn)
        if previous:
            if (previous['source'], previous['owner_kind'], str(previous['owner_id'])) != (source, owner_kind, owner_id):
                raise LocalEmailInventoryError('email_derivation_identity_conflict', '原本地领取意图的来源或归属不一致')
            row = record_store.get_row(spec, int(previous['pool_id']), conn=conn, for_update=True)
            if not row or str(row['email']).lower() != previous['address_norm']:
                raise LocalEmailInventoryError('local_email_identity_unavailable', '原本地完整邮箱已删除或变更，不能改领其他地址')
            require_usable(row)
            _bind_job(conn, row, source, previous['id'], batch, job_id)
            return row
        table = postgres_store.qualified(spec.name)
        eligible, params = _eligibility(source, batch_id=batch)
        while True:
            with conn.cursor() as cursor:
                cursor.execute(f'SELECT p.id, p.email FROM {table} p WHERE {eligible} ORDER BY p.id LIMIT 1 FOR UPDATE OF p SKIP LOCKED', params)
                candidate = cursor.fetchone()
            if not candidate:
                return None
            address = str(candidate['email']).strip().lower()
            record_store.advisory_xact_lock(conn, 'registered-account:' + address)
            with conn.cursor() as cursor:
                cursor.execute(f'SELECT p.id FROM {table} p WHERE p.id = %s AND {eligible}', [candidate['id'], *params])
                if not cursor.fetchone():
                    continue
            original = record_store.get_row(spec, candidate['id'], conn=conn)
            require_usable(original)
            profile_id = ((original.get('derivation_policy') or {}).get('inbox_profile_id')
                          if source == 'icloud_hide' else original.get('inbox_profile_id'))
            claim_id = record_store.insert_row(record_store.LOCAL_EMAIL_CLAIMS, {
                'acquisition_id': stable_id, 'owner_kind': owner_kind, 'owner_id': owner_id,
                'source': source, 'pool_id': candidate['id'], 'address_norm': address, 'status': 'claimed',
                'inbox_profile_id': profile_id,
            }, conn=conn)
            record_store.patch_row(spec, candidate['id'], {
                'status': 'used', 'used_at': datetime.now().isoformat(), 'local_acquisition_id': stable_id,
                'local_owner_kind': owner_kind, 'local_owner_id': owner_id,
                'local_inbox_profile_id': profile_id,
            }, conn=conn)
            row = record_store.get_row(spec, candidate['id'], conn=conn)
            _bind_job(conn, row, source, claim_id, batch, job_id)
            return row
