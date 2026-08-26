"""Roxy 注册旧导入路径的模块级兼容别名。

实际实现已迁移到 :mod:`core.registration.roxy`。这里将旧模块名绑定到同一个
模块对象，使历史调用和测试 patch 点在兼容期内继续生效。
"""
from __future__ import annotations

import sys

from core.registration import roxy as _implementation

sys.modules[__name__] = _implementation
