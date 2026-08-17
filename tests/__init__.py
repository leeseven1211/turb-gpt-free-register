# -*- coding: utf-8 -*-
"""测试包。

存在的意义是让 `tests.support_pg` 这类共享工具在两种调用方式下都能导入：
    python -m unittest discover -s tests -p 'test_*.py'
    python -m unittest tests.test_dashboard_api
"""
