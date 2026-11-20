"""三类内核及逐操作能力的纯身份目录，不读取配置或加载执行代码。"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

SelectionPolicy = Literal["fixed", "auto", "same_as_registration"]


@dataclass(frozen=True)
class KernelDefinition:
    """彼此并列的产品内核分类。"""

    key: str
    label: str


@dataclass(frozen=True)
class KernelImplementation:
    """实现属于一个明确内核，不继承同内核其它实现的能力。"""

    kernel: str
    key: str
    label: str


@dataclass(frozen=True)
class OperationBinding:
    """一个已选择的操作执行身份；变体仅属于该操作。"""

    operation: str
    kernel: str
    implementation: str
    variant: str | None = None


KERNELS: Mapping[str, KernelDefinition] = MappingProxyType({
    "browser": KernelDefinition("browser", "浏览器内核"),
    "protocol": KernelDefinition("protocol", "协议内核"),
    "rust": KernelDefinition("rust", "Rust 内核"),
})
IMPLEMENTATIONS: Mapping[tuple[str, str], KernelImplementation] = MappingProxyType({
    ("browser", "roxy"): KernelImplementation("browser", "roxy", "本地 Roxy"),
    ("protocol", "local"): KernelImplementation("protocol", "local", "本地协议"),
    ("protocol", "protocol_oss_2"): KernelImplementation("protocol", "protocol_oss_2", "开源protocol-2"),
})

_FIXED_BINDINGS: Mapping[tuple[str, str], OperationBinding] = MappingProxyType({
    ("registration", "roxy"): OperationBinding("registration", "browser", "roxy"),
    ("registration", "protocol_oss_2"): OperationBinding("registration", "protocol", "protocol_oss_2"),
    ("refresh_at", "browser_roxy"): OperationBinding("refresh_at", "browser", "roxy"),
    ("password_setup", "roxy"): OperationBinding("password_setup", "browser", "roxy"),
    ("password_setup", "protocol"): OperationBinding("password_setup", "protocol", "local"),
    ("twofa", "browser"): OperationBinding("twofa", "browser", "roxy"),
    ("twofa", "protocol"): OperationBinding("twofa", "protocol", "local"),
    ("codex_oauth", "roxy"): OperationBinding("codex_oauth", "browser", "roxy"),
    ("codex_oauth", "protocol"): OperationBinding("codex_oauth", "protocol", "local"),
    ("live_check", "browser_roxy"): OperationBinding("live_check", "browser", "roxy"),
    ("live_check", "protocol_current"): OperationBinding("live_check", "protocol", "local"),
    ("plan_check", "protocol"): OperationBinding("plan_check", "protocol", "local"),
})
_REFRESH_BINDINGS: Mapping[str, OperationBinding] = MappingProxyType({
    version: OperationBinding("refresh_at", "protocol", "local", version)
    for version in ("v1", "v2", "v3")
})
_SELECTION_POLICIES: Mapping[tuple[str, str], SelectionPolicy] = MappingProxyType({
    ("twofa", "auto"): "auto",
    ("codex_oauth", "same_as_registration"): "same_as_registration",
})
OPERATION_BINDINGS = frozenset((*_FIXED_BINDINGS.values(), *_REFRESH_BINDINGS.values()))


def operation_binding(
    operation: str, driver: str, *, protocol_version: str = "v1",
) -> OperationBinding:
    """将已解析规范值投影为执行身份，不解释历史别名或业务选择策略。

    ``protocol_version`` 只影响协议刷新 AT；原业务入口继续决定版本、部署
    开关、认证上下文、回退和旧输入的处理方式。
    """
    if (operation, driver) == ("refresh_at", "protocol"):
        return _REFRESH_BINDINGS[protocol_version]
    return _FIXED_BINDINGS[(operation, driver)]


def operation_selection_policy(operation: str, driver: str) -> SelectionPolicy:
    """描述规范选项的选择方式，不替业务解析 auto 或跟随注册快照。"""
    key = (operation, driver)
    if key in _SELECTION_POLICIES:
        return _SELECTION_POLICIES[key]
    operation_binding(operation, driver)
    return "fixed"


__all__ = [
    "KERNELS",
    "IMPLEMENTATIONS",
    "OPERATION_BINDINGS",
    "KernelDefinition",
    "KernelImplementation",
    "OperationBinding",
    "SelectionPolicy",
    "operation_binding",
    "operation_selection_policy",
]
