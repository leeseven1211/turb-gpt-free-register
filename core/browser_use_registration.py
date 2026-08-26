"""Browser Use 注册旧导入路径的模块级兼容别名。

实际实现已迁移到 :mod:`core.registration.browser_use`。旧模块名与新模块名绑定
到同一个模块对象，兼容既有外部导入和测试 patch 点。
"""
from __future__ import annotations

import sys

from core.registration import browser_use as _implementation

sys.modules[__name__] = _implementation
