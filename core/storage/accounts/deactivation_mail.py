"""停用邮件扫描投影的集合 SQL，保持单条写入的证据与解封语义。"""
from __future__ import annotations

import json

from core.storage import postgres as pg, records as store
from core.storage.email.bulk_mutations import _patch_many


def load_many(account_ids, *, conn):
    with conn.cursor() as cur:
        cur.execute(f'SELECT * FROM {pg.qualified(store.ACCOUNTS.name)} WHERE id=ANY(%s) ORDER BY id FOR UPDATE',
                    (sorted(set(account_ids)),))
        return {int(row['id']): store.merge_row(store.ACCOUNTS, row) for row in cur.fetchall()}


def hme_anchor(*, conn):
    with conn.cursor() as cur:
        cur.execute(f"SELECT id,email FROM {pg.qualified(store.ACCOUNTS.name)} "
                    "WHERE archived=FALSE AND lower(btrim(email_source))='icloud_hide' ORDER BY id LIMIT 1")
        return cur.fetchone()


def update_many(results, *, conn=None, accounts=None):
    """一个事务保存一块结果；仅返回实际存在且已写入的账号。"""
    if not results:
        return []
    if conn is None:
        with store.transaction() as own:
            return update_many(results, conn=own)
    from core.storage.db_legacy import _deactivation_mail_precedes_restoration
    rows = accounts if accounts is not None else load_many(results, conn=conn)
    now = store._now()
    changes, dead_emails = {}, set()
    for account_id, result in results.items():
        row = rows.get(int(account_id))
        if row is None:
            continue
        result = result or {}
        status = str(result.get('status') or 'failed')
        patch = {'deactivation_mail_scan_status': status,
                 'deactivation_mail_scan_trigger': str(result.get('trigger') or ''), 'updated_at': now}
        if status == 'queued':
            patch['deactivation_mail_scan_queued_at'] = now
        elif status == 'running':
            patch['deactivation_mail_scan_started_at'] = now
        elif status == 'success':
            patch.update(deactivation_mail_checked_at=result.get('checked_at') or now, deactivation_mail_error=None)
            if bool(result.get('detected')) and not _deactivation_mail_precedes_restoration(row, result):
                patch.update(deactivation_mail_detected=True,
                    deactivation_mail_received_at=result.get('received_at') or '',
                    deactivation_mail_subject=str(result.get('subject') or '')[:300],
                    deactivation_mail_sender=str(result.get('sender') or '')[:200],
                    deactivation_mail_message_id=str(result.get('message_id') or '')[:300],
                    deactivation_mail_confidence=str(result.get('confidence') or 'high'),
                    account_status='deactivated', account_status_reason='account_deactivated',
                    account_status_at=now, account_status_source='deactivation_mail', codex_status='deactivated',
                    codex_credential_state='deactivated', codex_error='account_deactivated')
                email = str(row.get('email') or '').strip().lower()
                if email:
                    dead_emails.add(email)
        elif status in {'failed', 'unsupported'}:
            if not result.get('preserve_checked_at'):
                patch['deactivation_mail_checked_at'] = result.get('checked_at') or now
            patch['deactivation_mail_error'] = str(result.get('error') or '')[:500]
        # 用 records 的字段派生规则计算账号筛选投影，避免 account_status 已变而 is_deactivated 未变。
        promoted, rest = store._split(store.ACCOUNTS, patch, partial=True)
        changes[int(account_id)] = {**promoted, **rest}
    _patch_many(conn, store.ACCOUNTS, changes)
    if dead_emails:
        patch = {'oauth_status': 'deactivated', 'oauth_account_status': 'deactivated',
                 'oauth_account_status_reason': 'account_deactivated', 'oauth_account_status_at': now,
                 'oauth_reauth_required': True, 'oauth_refresh_error': 'account_deactivated', 'updated_at': now}
        promoted, rest = store._split(store.CODEX_CREDENTIALS, patch, partial=True)
        assignments = [f'{pg.quote_identifier(field)}=%s' for field in promoted]
        assignments.append("data=COALESCE(data,'{}'::jsonb) || %s::jsonb")
        with conn.cursor() as cur:
            cur.execute(f'UPDATE {pg.qualified(store.CODEX_CREDENTIALS.name)} SET {", ".join(assignments)} '
                        "WHERE lower(btrim(email))=ANY(%s)",
                        (*promoted.values(), json.dumps(rest), sorted(dead_emails)))
    return list(changes)
