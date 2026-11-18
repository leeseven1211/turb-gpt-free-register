#!/usr/bin/env python3
"""以 Playwright CLI 对两个已启动的合成预览交替测量；不连接数据库。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, required=True, help='playwright_cli.sh 路径')
    parser.add_argument('--session', default='task-center-benchmark')
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--baseline-port', type=int, default=8018)
    parser.add_argument('--current-port', type=int, default=8019)
    parser.add_argument('--baseline-ref', default='2fe57ac')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1 or args.warmups < 1:
        parser.error('样本和预热次数必须为正数')

    source_file = ROOT / 'tools/benchmarks/task_center_browser_sample.mjs'
    source = source_file.read_text().replace('export default ', '', 1)
    fingerprint_paths = [source_file, ROOT / 'tools/diagnostics/preview_task_center.py',
                         ROOT / 'tools/benchmarks/task_center_ui_preview.py',
                         ROOT / 'webui/static/task-center/task-center.js',
                         ROOT / 'webui/static/task-center/task-center.css',
                         ROOT / 'webui/templates/index.html',
                         ROOT / 'webui/static/js/pages/operations/page.js']

    def fingerprints() -> dict:
        return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in fingerprint_paths}

    def invoke(code: str) -> dict:
        command = [str(args.cli), f'-s={args.session}', 'run-code', code]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=90)
        if result.returncode != 0 or '### Result\n' not in result.stdout:
            raise RuntimeError('Playwright 调用失败: ' + (result.stdout + result.stderr)[-3000:])
        payload = result.stdout.split('### Result\n', 1)[1].split('\n###', 1)[0]
        return json.loads(payload)

    invoke('async (page) => { await page.goto("about:blank"); return {ready:true}; }')
    report = {
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'baseline_sha': subprocess.check_output(['git', 'rev-parse', args.baseline_ref], cwd=ROOT, text=True).strip(),
        'source_sha256': fingerprints(),
        'host': {'system': platform.system(), 'release': platform.release(),
                 'machine': platform.machine(), 'cpu_count': os.cpu_count()},
        'scope': '同一浏览器进程，每样本新建页面、CDP 禁用缓存；本机合成 API，无数据库。页面在点击后数据渲染完成并等待两帧；reentry 仅测已有数据重新可见，不等待后台刷新。',
        'data': {'tasks': 2000, 'page_size': 20, 'detail_events': 500,
                 'fixed_now_utc': '2026-11-13T00:00:00+00:00'},
        'order': '交替 baseline/current，奇数轮反向；预热不计入结果',
        'warmups_per_variant': args.warmups, 'samples_per_variant': args.samples,
        'raw_samples': [], 'warmups': [], 'summary': {},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save() -> None:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    for index in range(-args.warmups, args.samples):
        order = ('baseline', 'current') if index % 2 == 0 else ('current', 'baseline')
        for variant in order:
            config = {'variant': variant, 'index': index, 'baselinePort': args.baseline_port,
                      'currentPort': args.current_port}
            row = invoke('async (page) => await (' + source + ')(page, ' + json.dumps(config) + ')')
            if row['errors']:
                raise RuntimeError(f'{variant} 浏览器出现错误: {row["errors"]}')
            report['warmups' if index < 0 else 'raw_samples'].append(row)
            save()
        print(f'{"预热" if index < 0 else "样本"} {index + 1 if index >= 0 else index + args.warmups + 1}: 两版完成', flush=True)

    for variant in ('baseline', 'current'):
        rows = [r for r in report['raw_samples'] if r['variant'] == variant]
        summary = {}
        for action in ('cold', 'filter', 'page', 'detail', 'reentry'):
            summary[action] = {
                metric: {'p50': percentile([r['results'][action][metric] for r in rows], 50),
                         'p95': percentile([r['results'][action][metric] for r in rows], 95),
                         'min': min(r['results'][action][metric] for r in rows),
                         'max': max(r['results'][action][metric] for r in rows)}
                for metric in ('elapsed_ms', 'api_count', 'list_count', 'evidence_count',
                               'resource_count', 'bytes', 'transfer_bytes', 'long_task_ms', 'dom_nodes')}
        report['summary'][variant] = summary
    report['source_unchanged_during_measurement'] = fingerprints() == report['source_sha256']
    save()
    if not report['source_unchanged_during_measurement']:
        raise RuntimeError('测量期间相关源码变动，不能将此报告用作最终验收')
    print(json.dumps({v: {a: m['elapsed_ms'] for a, m in s.items()}
                      for v, s in report['summary'].items()}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
