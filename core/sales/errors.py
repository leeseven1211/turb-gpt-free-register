"""销售适配器的稳定错误分类。"""

from __future__ import annotations


class SalesError(ValueError):
    """可向销售服务层传递的已分类错误。"""

    def __init__(self, code: str, message: str, status: int = 400):
        self.code = str(code)
        self.message = str(message)
        self.status = int(status)
        super().__init__(self.message)
