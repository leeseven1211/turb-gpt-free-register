"""绑定注册驱动的执行入口，按实际调用加载驱动模块。"""
from __future__ import annotations

from collections.abc import Callable

from contracts.kernel_catalog import operation_binding
from core.kernels import registry

_ENTRYPOINTS = {
    "protocol_oss_2": "protocol_cli",
    "roxy": "roxy_cli",
}


def resolve_registration_runner(driver: str) -> tuple[Callable[..., dict], str]:
    """按规范值读取当前执行函数和原 CLI 入口名。"""
    return registry.resolve_operation_runner(operation_binding("registration", driver)), _ENTRYPOINTS[driver]
