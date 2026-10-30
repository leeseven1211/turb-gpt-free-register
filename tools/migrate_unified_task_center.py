#!/usr/bin/env python3
"""旧维护命令兼容入口；实现已按职责归位。"""
from pathlib import Path
import importlib
import runpy
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if __name__ == "__main__":
    runpy.run_module('tools.migrations.migrate_unified_task_center', run_name="__main__", alter_sys=False)
else:
    sys.modules[__name__] = importlib.import_module('tools.migrations.migrate_unified_task_center')
