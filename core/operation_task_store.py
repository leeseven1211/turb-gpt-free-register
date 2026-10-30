"""统一任务中心旧入口的模块级兼容别名。"""
from __future__ import annotations

import sys

from core.storage.operations import store as _implementation

sys.modules[__name__] = _implementation
