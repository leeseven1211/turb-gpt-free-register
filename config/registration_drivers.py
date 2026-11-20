"""现行注册驱动与历史配置的执行映射。"""
from __future__ import annotations

from typing import cast

from config.operation_drivers import (
    RegistrationDriverDefinition,
    get_operation_driver,
    operation_driver_aliases,
    operation_driver_values,
)

REGISTRATION_DRIVERS = operation_driver_values("registration")
_REGISTRATION_ALIASES = operation_driver_aliases("registration")


def get_registration_driver(value: str) -> RegistrationDriverDefinition:
    """读取注册规范值的描述，历史快照由调用方先归一化。"""
    return cast(RegistrationDriverDefinition, get_operation_driver("registration", value))


def normalize_registration_driver(value: object) -> str:
    """仅归一化配置和历史执行快照；新 API 输入仍校验现行枚举。"""
    driver = str(value or "roxy").strip().lower()
    return _REGISTRATION_ALIASES.get(driver, driver)
