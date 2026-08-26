"""账号任务旧入口的模块级兼容别名。"""
from __future__ import annotations

import sys

from core.operations import legacy_task_store as _implementation

sys.modules[__name__] = _implementation
