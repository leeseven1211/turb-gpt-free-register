#!/usr/bin/env python3
"""生成任务错误短语前端目录；仅标准库，不导入执行器或连接数据库。"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'core/operations/error_labels.py'
TARGET = ROOT / 'frontend/src/generated/task-error-labels.json'


def rendered_catalog() -> str:
    spec = importlib.util.spec_from_file_location('task_error_labels', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog = module.label_catalog()
    labels = [catalog['fallback']]
    for field in ('codeLabels', 'causeCodeLabels', 'displayCodeLabels', 'categoryLabels'):
        labels.extend(catalog[field].values())
    labels.extend(rule['label'] for rule in catalog['rules'])
    if any(not value or len(value) > catalog['maxLength'] for value in labels):
        raise ValueError('错误短语必须为 1–10 个 Unicode 字符，不能截断原始错误代替分类')
    return json.dumps(catalog, ensure_ascii=False, indent=2) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只验证已提交目录与源文件一致')
    args = parser.parse_args()
    content = rendered_catalog()
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != content:
            print('错误短语目录有漂移，请运行 python3 tools/maintenance/generate_task_error_labels.py')
            return 1
        print('任务错误短语目录一致')
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content)
    print(f'已生成 {TARGET.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
