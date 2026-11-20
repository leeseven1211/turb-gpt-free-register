"""按操作隔离的静态驱动契约，不加载配置、执行器或运行服务。"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from contracts.kernel_catalog import (
    operation_binding as operation_binding,
    operation_selection_policy as operation_selection_policy,
)


@dataclass(frozen=True)
class DriverDefinition:
    """一种操作可选择的规范值与现有中文标签。"""

    value: str
    label: str


@dataclass(frozen=True)
class RegistrationDriverDefinition(DriverDefinition):
    """注册外围服务需要的静态属性，不保存执行函数或并发额度。"""

    description: str
    admission_class: str
    password_required: bool
    debug_supported: bool
    codex_driver: str
    browser_required: bool = False


_DRIVERS: Mapping[str, tuple[DriverDefinition, ...]] = MappingProxyType({
    "registration": (
        RegistrationDriverDefinition(
            "protocol_oss_2", "开源protocol-2",
            "使用 wangshen233 开源协议流程，邮箱、任务恢复和账号后处理沿用本地服务。",
            "registration_proto2", True, True, "protocol",
        ),
        RegistrationDriverDefinition(
            "roxy", "本地 Roxy", "使用本地 RoxyBrowser 注册与账号后处理流程。",
            "registration_roxy", True, True, "roxy", browser_required=True,
        ),
    ),
    "refresh_at": (
        DriverDefinition("protocol", "协议刷新"),
        DriverDefinition("browser_roxy", "Roxy 指纹浏览器"),
    ),
    "password_setup": (
        DriverDefinition("roxy", "RoxyBrowser（默认）"),
        DriverDefinition("protocol", "纯协议（登录后添加密码）"),
    ),
    "twofa": (
        DriverDefinition("auto", "自动选择（协议优先）"),
        DriverDefinition("protocol", "协议开通"),
        DriverDefinition("browser", "浏览器页面（RoxyBrowser）"),
    ),
    "codex_oauth": (
        DriverDefinition("protocol", "纯协议授权"),
        DriverDefinition("roxy", "RoxyBrowser"),
        DriverDefinition("same_as_registration", "跟随注册驱动"),
    ),
    "live_check": (
        DriverDefinition("protocol_current", "现有协议（保持现状）"),
        DriverDefinition("browser_roxy", "Roxy 浏览器（旧 AT probe）"),
    ),
    "plan_check": (
        DriverDefinition("protocol", "纯协议（当前唯一实现）"),
    ),
})

_ALIASES: Mapping[str, Mapping[str, str]] = MappingProxyType({
    "registration": MappingProxyType({
        "protocol": "protocol_oss_2", "protocol_oss": "protocol_oss_2",
        "api": "protocol_oss_2", "http": "protocol_oss_2",
        "roxy_oss": "roxy", "roxybrowser": "roxy", "fingerprint": "roxy", "browser": "roxy",
        "browser_use": "roxy", "skyvern": "roxy", "cloak": "roxy", "cloakbrowser": "roxy",
    }),
    "refresh_at": MappingProxyType({"roxy": "browser_roxy"}),
    "password_setup": MappingProxyType({"roxybrowser": "roxy", "browser": "roxy"}),
    "twofa": MappingProxyType({
        "protocol_direct": "auto", "api": "protocol", "http": "protocol",
        "roxy": "browser", "roxybrowser": "browser",
    }),
    "codex_oauth": MappingProxyType({
        "api": "protocol", "http": "protocol", "roxybrowser": "roxy",
        "fingerprint": "roxy", "browser": "roxy",
    }),
    "live_check": MappingProxyType({
        "": "protocol_current", "current": "protocol_current", "protocol": "protocol_current",
    }),
    "plan_check": MappingProxyType({"api": "protocol", "http": "protocol"}),
})

PROTOCOL_VERSION_OPTIONS = (
    ("v1", "协议 v1（现有稳定实现）"),
    ("v2", "协议 v2（已支持的步骤）"),
    ("v3", "协议 v3（会话复用与增强认证）"),
)
PROTOCOL_VERSION_ALIASES: Mapping[str, str] = MappingProxyType({
    "1": "v1", "v_1": "v1", "2": "v2", "v_2": "v2", "3": "v3", "v_3": "v3",
})
PROTOCOL_STEP_CAPABILITIES: Mapping[str, frozenset[str]] = MappingProxyType({
    "registration": frozenset({"v1"}),
    "twofa": frozenset({"v1"}),
    "plan_check": frozenset({"v1"}),
    "live_check": frozenset({"v1"}),
    "refresh_at": frozenset({"v1", "v2", "v3"}),
    "codex_oauth": frozenset({"v1"}),
})

# 这些是 AT 刷新的显式兼容输入，不是其它操作可选的驱动。
# protocol_v2 的旧兼容开关仍由原服务判断。
REFRESH_AT_VERSION_ALIASES: Mapping[str, str] = MappingProxyType({
    "v1": "v1", "1": "v1", "v2": "v2", "2": "v2",
    "v3": "v3", "3": "v3", "protocol_v3": "v3",
    "current": "v1", "protocol": "v1", "protocol_current": "v1", "legacy": "v1", "": "v1",
    "protocol_v2": "v2",
})
REFRESH_AT_INTERNAL_DRIVERS: Mapping[str, str] = MappingProxyType({
    "v1": "legacy", "v2": "protocol_v2", "v3": "protocol_v3",
})


def operation_driver_definitions(operation: str) -> tuple[DriverDefinition, ...]:
    """读取一个明确操作的规范选项，未知操作不回退到其它操作。"""
    return _DRIVERS[operation]


def operation_driver_options(operation: str) -> tuple[tuple[str, str], ...]:
    """提供配置 schema 需要的现有值和标签，保留原顺序。"""
    return tuple((item.value, item.label) for item in operation_driver_definitions(operation))


def operation_driver_aliases(operation: str) -> Mapping[str, str]:
    """返回操作自己的历史别名，不自动应用到 API 或任务。"""
    return _ALIASES[operation]


def operation_driver_values(operation: str, *, include_aliases: bool = False) -> frozenset[str]:
    """规范输入和历史输入由调用边界明确区分。"""
    values = frozenset(item.value for item in operation_driver_definitions(operation))
    return values | frozenset(operation_driver_aliases(operation)) if include_aliases else values


def get_operation_driver(operation: str, value: str) -> DriverDefinition:
    """只查规范值；历史别名必须由原业务边界显式解析。"""
    for definition in operation_driver_definitions(operation):
        if definition.value == value:
            return definition
    raise KeyError(value)


def registration_codex_driver(value: str) -> str:
    """仅映射注册到 Codex，不改变各调用方已有的归一化范围。"""
    for definition in operation_driver_definitions("registration"):
        if definition.value == value:
            return definition.codex_driver
    return {"protocol_oss": "protocol", "roxy_oss": "roxy"}.get(value, value)


VALID_TWOFA_MODES = operation_driver_values("twofa")
TWOFA_MODE_ALIASES = operation_driver_aliases("twofa")


def normalize_twofa_mode(value: str | None, default: str = "auto") -> str:
    """将公开或历史 2FA 输入归一化到现行模式。"""
    default_mode = str(default or "auto").strip().lower() or "auto"
    default_mode = TWOFA_MODE_ALIASES.get(default_mode, default_mode)
    if default_mode not in VALID_TWOFA_MODES:
        default_mode = "auto"
    raw = default_mode if value is None else str(value or "").strip().lower()
    normalized = TWOFA_MODE_ALIASES.get(raw, raw or default_mode)
    if normalized not in VALID_TWOFA_MODES:
        raise ValueError("2FA 驱动只支持 auto、protocol 或 browser")
    return normalized


def canonical_twofa_executor(mode: str | None) -> str:
    """将公开 2FA 模式映射到对应执行器的规范值。"""
    return "browser" if normalize_twofa_mode(mode) == "browser" else "protocol"
