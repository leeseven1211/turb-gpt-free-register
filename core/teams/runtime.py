"""Team 运行时登记；扫描与执行均由共享持久任务调度器承担。"""
from core.teams.execution import recover_pending, register_handlers

__all__ = ["recover_pending", "register_handlers"]
