"""邮箱删除只保护已确认的注册事实，领取和密码占位不是成功证据。"""
from __future__ import annotations

import json

from core.storage import postgres as pg, records as store


def _exists(cur, name):
    cur.execute('SELECT to_regclass(%s) AS relation', (pg.qualified(name),))
    return bool(cur.fetchone()['relation'])


def registration_confirmed(address, *, conn, account_id=None):
    """判断注册完成事实；远端身份和邮箱使用报告不等于注册成功。"""
    address = str(address or '').strip().lower()
    if not address:
        return False
    with conn.cursor() as cur:
        cur.execute(f'''SELECT data,account_has_access_token FROM {pg.qualified(store.ACCOUNTS.name)}
            WHERE lower(email)=%s OR id=%s
            OR lower(split_part(COALESCE(data->>'original_email_line',''),'----',1))=%s''',
            (address, account_id, address))
        for row in cur.fetchall():
            if row['account_has_access_token']:
                return True
            extra = row['data'].get('extra_json') or {}
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except (TypeError, ValueError):
                    extra = {}
            if isinstance(extra, dict) and extra.get('imported_registered') is True:
                return True
            if (isinstance(extra, dict) and extra.get('registration_checkpoint') in {
                    'registered', 'token_obtained', 'core_persisted', 'postprocessing', 'completed'}
                    or row['data'].get('email_change_status') == 'success'):
                return True
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.EMAIL_SERVICE_SYNC.name)}
            WHERE address_norm=%s AND kind='import' AND data->>'as_registered'='true'
            AND state IN ('local_only','delivered') LIMIT 1''', (address,))
        if cur.fetchone():
            return True
        if _exists(cur, 'registration_attempts'):
            attempts = pg.qualified('registration_attempts')
            identity = "(lower(email)=%s OR lower(email_snapshot)=%s)"
            cur.execute(f'''SELECT 1 FROM {attempts} WHERE {identity} AND (
                local_account_state IN ('token_obtained','persisted')
                OR checkpoint IN ('token_obtained','core_persisted','postprocessing','completed','registered')) LIMIT 1''',
                (address, address))
            if cur.fetchone():
                return True
            if _exists(cur, 'registration_events'):
                cur.execute(f'''SELECT 1 FROM {pg.qualified('registration_events')} e
                    JOIN {attempts} a ON a.id=e.attempt_id
                    WHERE (lower(a.email)=%s OR lower(a.email_snapshot)=%s)
                    AND e.event_type='core_persisted' LIMIT 1''', (address, address))
                if cur.fetchone():
                    return True
    return False


def lease_return_block_reason(address, *, conn, pool=None, account_id=None, unused_inventory=False):
    """本地可删除不代表租约可退；仅完整确认从未使用的库存自动退租。

    unused_inventory 只能来自删除事务保存的原始 available/used_at 快照。
    not_started、失败状态或缺少事件均不能证明注册请求从未发出。
    """
    address = str(address or '').strip().lower()
    if not address:
        return 'registration_result_unverified'
    if str((pool or {}).get('access_token') or '').strip() or registration_confirmed(
            address, conn=conn, account_id=account_id):
        return 'registration_confirmed'
    if registration_active(address, conn=conn):
        return 'registration_active'
    if not unused_inventory or (pool or {}).get('used_at') or (pool or {}).get('registered_account_id'):
        return 'registration_result_unverified'
    with conn.cursor() as cur:
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.ACCOUNTS.name)}
            WHERE lower(email)=%s OR id=%s
            OR lower(split_part(COALESCE(data->>'original_email_line',''),'----',1))=%s LIMIT 1''',
            (address, account_id, address))
        if cur.fetchone():
            return 'registration_result_unverified'
        for table, field in ((store.LOCAL_EMAIL_CLAIMS, 'address_norm'),
                             (store.REGISTRATION_BATCH_EMAIL_CLAIMS, 'email'),
                             (store.JOBS, 'email'),
                             (store.EMAIL_USAGE_REPORTS, 'address_norm'),
                             (store.EMAIL_OTP_REQUESTS, 'address_key'),
                             (store.EMAIL_ADDRESS_ALLOCATIONS, 'address_norm')):
            cur.execute(f'SELECT 1 FROM {pg.qualified(table.name)} WHERE lower({field})=%s LIMIT 1', (address,))
            if cur.fetchone():
                return 'registration_result_unverified'
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.EMAIL_BUTLER_CLAIM_INTENTS.name)}
            WHERE lower(COALESCE(NULLIF(address_norm,''),data->'mailbox'->>'email',''))=%s LIMIT 1''', (address,))
        if cur.fetchone():
            return 'registration_result_unverified'
        if _exists(cur, 'registration_attempts'):
            cur.execute(f'''SELECT 1 FROM {pg.qualified('registration_attempts')}
                WHERE lower(email)=%s OR lower(email_snapshot)=%s LIMIT 1''', (address, address))
            if cur.fetchone():
                return 'registration_result_unverified'
        # 跨来源重复库存也可能保留旧领取记录，不替它释放共享的原租约。
        from core.email.inventory import TABLES
        matches = 0
        for table in TABLES.values():
            cur.execute(f'''SELECT status,used_at,registered_account_id
                FROM {pg.qualified(table.name)} WHERE lower(email)=%s''', (address,))
            for row in cur.fetchall():
                matches += 1
                if row['status'] not in {'available', 'tombstone'} or row['used_at'] or row['registered_account_id']:
                    return 'registration_result_unverified'
        if matches != 1:
            return 'registration_result_unverified'
    return ''


def registration_active(address, *, conn):
    """本地可先移除；活跃执行结束前不提前退还它仍在读取的租约。"""
    address = str(address or '').strip().lower()
    with conn.cursor() as cur:
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.JOBS.name)} WHERE lower(email)=%s
            AND status IN ('pending','queued','running','stopping','cancelling') LIMIT 1''', (address,))
        if cur.fetchone():
            return True
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.EMAIL_OTP_REQUESTS.name)} WHERE lower(address_key)=%s
            AND state='active' AND lease_expires_at>%s LIMIT 1''', (address, store._now()))
        if cur.fetchone():
            return True
        if _exists(cur, 'registration_attempts') and _exists(cur, 'registration_runs'):
            cur.execute(f'''SELECT 1 FROM {pg.qualified('registration_runs')} r
                JOIN {pg.qualified('registration_attempts')} a ON a.id=r.attempt_id
                WHERE (lower(a.email)=%s OR lower(a.email_snapshot)=%s)
                AND r.status IN ('queued','running') LIMIT 1''', (address, address))
            return bool(cur.fetchone())
    return False


def pool_deleted(address, *, conn):
    from core.email.inventory import TABLES

    with conn.cursor() as cur:
        for spec in TABLES.values():
            cur.execute(f'''SELECT 1 FROM {pg.qualified(spec.name)} WHERE lower(email)=%s
                AND (status='tombstone' OR COALESCE(data->>'pool_deleted_at','')<>'') LIMIT 1''',
                (str(address or '').strip().lower(),))
            if cur.fetchone():
                return True
    return False
