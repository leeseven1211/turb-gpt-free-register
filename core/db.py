"""业务存储旧入口的模块级兼容别名。

真实实现已归位到 :mod:`core.storage.db_legacy`。领域仓储从
``core.storage.accounts/jobs/email_pool/codex`` 暴露，迁移期间保留该入口以兼容
现有调用和测试。
"""
from __future__ import annotations

import sys

from core.storage import db_legacy as _implementation

sys.modules[__name__] = _implementation
