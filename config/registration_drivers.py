"""现行注册驱动与历史配置的执行映射。"""
from __future__ import annotations

REGISTRATION_DRIVERS = frozenset({"protocol_oss_2", "roxy"})
_REGISTRATION_ALIASES = {
    "protocol": "protocol_oss_2", "protocol_oss": "protocol_oss_2",
    "api": "protocol_oss_2", "http": "protocol_oss_2",
    "roxy_oss": "roxy", "roxybrowser": "roxy", "fingerprint": "roxy", "browser": "roxy",
    "browser_use": "roxy", "skyvern": "roxy", "cloak": "roxy", "cloakbrowser": "roxy",
}


def normalize_registration_driver(value: object) -> str:
    """仅归一化配置和历史执行快照；新 API 输入仍校验现行枚举。"""
    driver = str(value or "roxy").strip().lower()
    return _REGISTRATION_ALIASES.get(driver, driver)
