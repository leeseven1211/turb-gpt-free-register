#!/usr/bin/env python3
"""Codex 凭证页的内存合成验收；不导入业务模块，不连接数据库或远端服务。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
import logging
from pathlib import Path
import sys
import zipfile

from flask import Response, jsonify, request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.diagnostics.preview_task_center import create_preview


def create_codex_preview(count: int = 300_000):
    app = create_preview(now=datetime(2026, 11, 14, tzinfo=timezone.utc))
    mutations: dict[int, dict] = {}
    calls: list[dict] = []

    def row(n):
        return {
            'filename': f'fixture-{n:06}@example.test-free.json', 'email': f'fixture-{n:06}@example.test',
            'plan': ['free', 'plus', 'team'][n % 3], 'account_id': f'oauth-{n}',
            'sub2api_account_id': n if n % 4 == 0 else None,
            'exported': n % 4 == 0, 'exported_count': 0, 'sub2_uploaded_count': 1 if n % 4 == 0 else 0,
            'mtime': '2026-11-14T08:00:00+08:00', 'expired': '2026-12-14T08:00:00+08:00',
            'oauth_expires_at': '2026-12-14T08:00:00+08:00', 'oauth_seconds_left': 2_592_000,
            'oauth_refreshable': True, 'oauth_status': ['valid', 'expired', 'expiring', 'missing'][n % 4],
            'oauth_reauth_required': False, 'sub2api_http_status': 401 if n % 11 == 0 else None,
            'oauth_refresh_error': '合成刷新失败：请查看任务中心完整诊断' if n % 11 == 0 else None,
            'archived': n % 10 == 0, **mutations.get(n, {}),
        }

    def number(filename):
        return int(filename.split('@', 1)[0].replace('fixture-', ''))

    @app.get('/api/codex')
    def codex_list():
        args = request.args
        calls.append({'method': 'GET', 'path': request.path, 'query': dict(args)})
        archived = args.get('archived') == 'only'
        ids = [n for n in range(count, 0, -1) if not mutations.get(n, {}).get('deleted')
               and mutations.get(n, {}).get('archived', n % 10 == 0) == archived]
        # 只为涉及其他列筛选的情况构造行；普通分页始终仅序列化本页。
        keys = ['q', 'plan', 'status', 'oauth_status', 'account_id', 'sub2api_id', 'date_from', 'date_to', 'expired_date']
        if any(args.get(key) for key in keys):
            def matches(n):
                value = row(n)
                q = args.get('q', '').lower()
                if q and q not in ' '.join(str(value.get(k) or '') for k in ['filename', 'email', 'account_id', 'sub2api_account_id']).lower():
                    return False
                for key in ['plan', 'oauth_status']:
                    if args.get(key) and args[key] != value[key]: return False
                if args.get('status') and args['status'] != ('exported' if value['exported'] else 'unexported'): return False
                if args.get('account_id') and args['account_id'] not in value['account_id']: return False
                if args.get('sub2api_id') and args['sub2api_id'] != str(value['sub2api_account_id']): return False
                if args.get('date_from') and args['date_from'] > value['mtime'][:10]: return False
                if args.get('date_to') and args['date_to'] < value['mtime'][:10]: return False
                if args.get('expired_date') and args['expired_date'] != value['expired'][:10]: return False
                return True
            ids = [n for n in ids if matches(n)]
        page, size = max(1, args.get('page', 1, type=int)), min(500, max(1, args.get('page_size', 20, type=int)))
        return jsonify(ok=True, accounts=[row(n) for n in ids[(page-1)*size:page*size]], total=len(ids), page=page,
                       page_size=size, offset=(page-1)*size, limit=size, revision=str(len(calls)),
                       facets={key: [{'value': value, 'count': count // len(values)} for value in values]
                               for key, values in {'plan': ['free', 'plus', 'team'], 'status': ['exported', 'unexported', 'archived'],
                                                   'oauth_status': ['valid', 'expired', 'expiring', 'missing']}.items()},
                       summary={'total': count-count//10, 'exported': count//4, 'pending': count-count//10-count//4})

    def download(names, cpa=False, single=False):
        content = {'synthetic': True, 'access_token': 'SYNTHETIC-NOT-A-CREDENTIAL'}
        if single:
            payload, filename, mimetype = json.dumps(content).encode(), names[0], 'application/json'
        elif cpa:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as archive:
                for name in names: archive.writestr(name, json.dumps(content))
                archive.writestr('manifest.json', json.dumps({'synthetic': True, 'count': len(names)}))
            payload, filename, mimetype = stream.getvalue(), 'fixture-cpa.zip', 'application/zip'
        else:
            payload = json.dumps({'count': len(names), 'credentials': [{'filename': name, 'content': content} for name in names], 'errors': []}).encode()
            filename, mimetype = 'fixture-backup.json', 'application/json'
        return Response(payload, mimetype=mimetype, headers={'Content-Disposition': f'attachment; filename="{filename}"'})

    @app.get('/api/codex/download/<path:filename>')
    @app.get('/api/codex/download-from-cpa/<path:filename>')
    def single_download(filename):
        calls.append({'method': 'GET', 'path': request.path})
        return download([filename], single=True)

    @app.post('/api/codex/<action>')
    def codex_action(action):
        data = request.get_json() or {}
        calls.append({'method': 'POST', 'path': request.path, 'body': data})
        names = data.get('filenames') or [data.get('filename')]
        if not all(isinstance(name, str) and name.startswith('fixture-') and '@example.test-' in name for name in names):
            return jsonify(ok=False, error='仅接受合成凭证'), 400
        if action.startswith('download-bulk'): return download(names, cpa=action.endswith('from-cpa'))
        if action in ['archive', 'archive-bulk']:
            for name in names: mutations.setdefault(number(name), {})['archived'] = data['archived']
            return jsonify(ok=True, filename=names[0], updated=[{'filename': name} for name in names], updated_count=len(names))
        if action in ['delete', 'delete-bulk']:
            for name in names: mutations.setdefault(number(name), {})['deleted'] = True
            return jsonify(ok=True, deleted=names[0] if action == 'delete' else names, deleted_count=len(names), skipped=[])
        if action == 'reset-export': return jsonify(ok=True)
        receipts = [{'accepted': True, 'filename': name, 'task_id': 121, 'run_id': 1212} for name in names]
        if action == 'upload-sub2-bulk': return jsonify(ok=True, accepted=True, queued_count=len(names), queued=receipts), 202
        if action in ['retry-bulk', 'refresh-token-bulk']: return jsonify(ok=True, started_count=len(names), started=receipts, skipped=[]), 202
        return jsonify(ok=False, error='未定义合成操作'), 404

    @app.get('/__preview__/calls')
    def recorded_calls():
        return jsonify(calls=calls)

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8021)
    parser.add_argument('--count', type=int, default=300_000)
    args = parser.parse_args()
    if not 125 <= args.count <= 500_000: parser.error('合成数量须在125至500000之间')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    create_codex_preview(args.count).run(host='127.0.0.1', port=args.port, debug=False, threaded=True)
