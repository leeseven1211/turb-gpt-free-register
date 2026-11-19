#!/usr/bin/env python3
"""账号页内存验收：合成账号、合成动作回执，不连接业务数据库或远端。"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys

from flask import jsonify, request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.diagnostics.preview_codex import create_codex_preview


def create_accounts_preview(count=300_000):
    app = create_codex_preview(count)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    calls, changes = [], {}
    epoch = 0

    def row(account_id):
        n = account_id
        return {
            'id': n, 'email': f'account-{n:06}@example.test', 'user_name': f'合成账号 {n}',
            'email_source': ['outlook', 'icloud_hide', 'cloudflare'][n % 3],
            'registration_driver': ['roxy', 'protocol', 'protocol_oss_2'][n % 3],
            'has_access_token': n % 3 != 0, 'has_account_password': n % 2 == 0,
            'totp_enabled': n % 2 == 0, 'email_invalid': n % 11 == 0,
            'email_invalid_reason': '合成邮箱无法接收邮件' if n % 11 == 0 else None,
            'email_invalid_at': None, 'email_invalid_source': None,
            'plus_promo_kind': 'free_trial', 'plus_promo_eligible': True,
            'plus_trial_eligible': True, 'plus_discount_eligible': False,
            'account_promotions': [{'plan': 'plus', 'kind': 'free_trial', 'country': 'JP'}],
            'promotion_query_snapshot': None, 'plan_check_country_results': [],
            'plan_type': ['free', 'plus', 'team'][n % 3], 'plan_check_status': 'success',
            'plan_checked_at': '2026-11-15T08:00:00+08:00',
            'account_status': 'active', 'last_password_auth_status': 'unknown',
            'codex_status': 'failed' if n % 7 == 0 else 'success',
            'codex_error': '合成凭证处理失败，完整原因仅用于详情验收' if n % 7 == 0 else None,
            'codex_execution_status': '', 'created_at': '2026-11-01T09:00:00+08:00',
            'updated_at': '2026-11-15T08:00:00+08:00', 'archived': n % 10 == 0,
            **changes.get(n, {}),
        }

    def record():
        calls.append({'method': request.method, 'path': request.path, 'query': dict(request.args),
                      'body': request.get_json(silent=True)})

    def listing(compact=False):
        record()
        args = request.args
        if args.get('q') == 'invalid:':
            return jsonify(ok=False, code='account_search_invalid', error='合成搜索语法错误'), 400
        ids = [n for n in range(count, 0, -1) if not changes.get(n, {}).get('deleted')
               and (args.get('archived') in ('all', 'include')
                    or changes.get(n, {}).get('archived', n % 10 == 0) == (args.get('archived') == 'only'))]
        for key in ('id', 'email', 'q'):
            value = args.get(key, '').lstrip('#').lower()
            if value:
                ids = [n for n in ids if value in (str(n) if key == 'id' else f'account-{n:06}@example.test 合成账号 {n}')]
        for field, key in (('email_source', 'source'), ('registration_driver', 'registration_driver'), ('plan_type', 'plan')):
            values = args.get(key, '').split(',')
            if values != ['']:
                ids = [n for n in ids if row(n)[field] in values]
        if args.get('email_status'):
            invalid = args['email_status'] == 'invalid'
            ids = [n for n in ids if row(n)['email_invalid'] == invalid]
        page = max(1, args.get('page', 1, type=int))
        size = max(1, min(500, args.get('page_size', 10, type=int)))
        items = [row(n) for n in ids[(page-1)*size:page*size]]
        revision = hashlib.sha256(json.dumps([epoch, args.to_dict(), ids[:1], len(ids)]).encode()).hexdigest()[:16]
        payload = {'ok': True, 'items': items, 'total': len(ids), 'page': page, 'page_size': size,
                   'offset': (page-1)*size, 'limit': size, 'revision': revision}
        if compact:
            for item in items:
                item.update(plan_details_revision=f'fixture-{epoch}', plan_summary={'promotions': [], 'countries': []})
            payload.update(status_fields=['codex_error'], queue={'workers': 1, 'registration_workers': 1,
                           'queue_limit': 100, 'min_interval': 0, 'jitter': 0})
        else:
            payload.update(compact=True, search_terms=[], facets={
                key: [{'value': value, 'count': len(ids)//len(values)} for value in values]
                for key, values in {'source': ['outlook', 'icloud_hide', 'cloudflare'],
                    'registration_driver': ['roxy', 'protocol', 'protocol_oss_2'], 'plan': ['free', 'plus', 'team'],
                    'email_status': ['invalid', 'unmarked'], 'account_status': ['active']}.items()})
        return jsonify(payload)

    app.add_url_rule('/api/accounts', 'accounts_list', lambda: listing(False))
    app.add_url_rule('/api/accounts/plan-check-status', 'account_statuses', lambda: listing(True))

    @app.get('/api/accounts/<int:account_id>/plan-details')
    def details(account_id):
        record()
        return jsonify(ok=True, item={key: row(account_id)[key] for key in (
            'account_promotions', 'promotion_query_snapshot', 'plan_check_country_results')})

    @app.get('/api/accounts/<int:account_id>/roxy-profile')
    def profile(account_id):
        record()
        return jsonify(ok=True, profile_id=f'synthetic-{account_id}', window_name='合成窗口')

    @app.post('/api/accounts/<action>')
    def mutate(action):
        nonlocal epoch
        record()
        data = request.get_json() or {}
        ids = data.get('account_ids', [])
        if not ids or not all(isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= count for n in ids):
            return jsonify(ok=False, error='仅接受合成账号 ID'), 400
        if action == 'email-invalid-bulk':
            updated, skipped = [], []
            for n in ids:
                if data.get('expected_emails', {}).get(str(n)) != row(n)['email']:
                    skipped.append({'id': n})
                else:
                    changes.setdefault(n, {}).update(email_invalid=data['invalid'], email_invalid_reason=data.get('reason'))
                    updated.append({'id': n})
            epoch += 1
            return jsonify(ok=True, updated=updated, updated_count=len(updated), skipped=skipped)
        if action in ('archive-bulk', 'delete-bulk'):
            for n in ids:
                changes.setdefault(n, {}).update({'archived': data['archived']} if action == 'archive-bulk' else {'deleted': True})
            epoch += 1
            key = 'updated' if action == 'archive-bulk' else 'deleted'
            return jsonify(ok=True, **{key: [{'id': n} for n in ids], key+'_count': len(ids)}, skipped=[])
        if action in ('check-plan-bulk', 'check-live-bulk', 'refresh-token-bulk', 'action-bulk', 'email-change-bulk'):
            refs = [{'accepted': True, 'account_id': n, 'task_id': 121, 'run_id': 1212} for n in ids]
            return jsonify(ok=True, accepted=True, queued=refs, queued_count=len(refs), started=refs, started_count=len(refs), skipped=[]), 202
        return jsonify(ok=False, error='未定义合成操作'), 404

    @app.get('/api/email-sources')
    def email_sources():
        record()
        return jsonify(sources=[{'value': 'outlook', 'label': 'Outlook', 'enabled': True},
                               {'value': 'cloudflare', 'label': 'Cloudflare', 'enabled': True},
                               {'value': 'mailcode', 'label': 'MailCode', 'enabled': False, 'reason': '合成未配置'}])

    @app.post('/api/accounts/<int:account_id>/email-change')
    def email_change(account_id):
        record()
        return jsonify(ok=True, accepted=True, task_id=121, run_id=1212, message='合成换绑任务已入队'), 202

    @app.route('/api/accounts/inspections', methods=['GET', 'POST'])
    def inspections():
        record()
        if request.method == 'POST':
            return jsonify(ok=True, created=True, task={'id': 121}), 202
        return jsonify(ok=True, total=1, active=False, items=[{
            'id': 17, 'task_id': 121, 'workers': 4, 'archived': '0', 'status': 'completed',
            'created_at': '2026-11-15T08:00:00+08:00', 'checked_count': 3, 'skipped_count': 1,
            'total_count': 4, 'invalid_count': 2, 'live_success_count': 1, 'live_failed_count': 1,
            'deactivated_skipped_count': 1, 'plan_success_count': 1, 'plan_failed_count': 0}])

    @app.get('/api/accounts/inspections/<int:inspection_id>/failures')
    def inspection_failures(inspection_id):
        record()
        return jsonify(ok=True, total=1, items=[{'account_id': 299999, 'email': 'account-299999@example.test',
            'status': 'deactivated_skipped', 'failed_at': '2026-11-15T08:00:00+08:00', 'error': '合成已废跳过'}])

    @app.post('/api/accounts/c2a/sync-bulk')
    def c2a():
        record()
        ids = (request.get_json() or {}).get('account_ids', [])
        return jsonify(ok=True, accepted=True, queued_count=len(ids), skipped_count=0, failed_count=0,
                       queued=[{'id': n, 'accepted': True, 'task_id': 121, 'run_id': 1212} for n in ids], skipped=[], failed=[]), 202

    @app.get('/__preview__/accounts-calls')
    def recorded():
        return jsonify(calls=calls)

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8128)
    parser.add_argument('--count', type=int, default=300_000)
    args = parser.parse_args()
    if not 125 <= args.count <= 500_000:
        parser.error('合成账号数量须在125至500000之间')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    create_accounts_preview(args.count).run(host='127.0.0.1', port=args.port, debug=False, threaded=True)
