"""按需集合读取邮箱素材；敏感值仅留在当前响应，不写任务和事件。"""
from collections import defaultdict
from contextlib import nullcontext

from core.storage import records as store
from core.storage.email.bulk_mutations import _TABLES


def read_many(items, field='copy_line', *, default_source='outlook', conn=None):
    from core.storage.db_legacy import _outlook_line, _generic_api_email_line, _account_line
    targets, seen = [], set()
    for raw in items:
        item = raw if isinstance(raw, dict) else {'email': raw}
        source = str(item.get('source') or default_source or 'outlook').strip()
        email = str(item.get('email') or '').strip()
        key = (source, email.lower())
        if email and key not in seen:
            targets.append((source, email))
            seen.add(key)
    rows, accounts = {}, []
    groups = defaultdict(list)
    for source, email in targets:
        if source in _TABLES:
            groups[source].append(email.lower())
    with (nullcontext(conn) if conn is not None else store.transaction()) as active:
        for source, addresses in groups.items():
            for row in store.list_rows(_TABLES[source], where='lower(email)=ANY(%s)',
                    params=(addresses,), order_by='id ASC', conn=active):
                rows.setdefault((source, row['email'].lower()), row)
        if field in {'access_token', 'account_copy_line'}:
            pool_rows = [row for (source, _), row in rows.items() if source != 'email_butler']
            ids = [row['registered_account_id'] for row in pool_rows if row.get('registered_account_id')]
            addresses = [row['email'].lower() for row in pool_rows]
            if addresses:
                accounts = store.list_rows(store.ACCOUNTS, where='id=ANY(%s) OR lower(email)=ANY(%s)',
                    params=(ids, addresses), order_by='id ASC', conn=active)
    by_id = {row['id']: row for row in accounts}
    by_email = {}
    for row in accounts:
        by_email.setdefault(row['email'].lower(), row)
    values, skipped = [], []
    for source, email in targets:
        row = rows.get((source, email.lower()))
        reason, value = '', ''
        if source not in _TABLES:
            reason = '邮箱来源非法'
        elif row is None:
            reason = '邮箱不存在'
        elif source == 'email_butler':
            if field != 'copy_line':
                reason = 'Butler 导入邮箱仅支持复制完整地址，连接凭据不作为邮箱素材导出'
            else:
                value = row['email']
        elif field == 'copy_line':
            if source == 'outlook':
                value = _outlook_line(row)
            elif source == 'generic_api':
                value = _generic_api_email_line(row) + ('----' + str(row['expires_at']) if row.get('expires_at') else '')
            else:
                value = row['email']
        elif field in {'access_token', 'account_copy_line'}:
            account = by_id.get(row.get('registered_account_id')) or by_email.get(row['email'].lower())
            value = (str((account or {}).get('access_token') or row.get('access_token') or '')
                if field == 'access_token' else _account_line(account) if account else '')
        elif field in {'password', 'client_id', 'refresh_token', 'code_url'}:
            value = str(row.get(field) or '')
        else:
            reason = '不支持的敏感字段'
        if reason or not value:
            skipped.append({'source': source, 'email': email, 'reason': reason or '值为空'})
        else:
            values.append({'source': source, 'email': email, 'value': value})
    return {'ok': True, 'field': field, 'values': values, 'count': len(values), 'skipped': skipped}
