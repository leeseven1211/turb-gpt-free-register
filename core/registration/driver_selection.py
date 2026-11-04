"""注册执行时统一解析现行与历史驱动名称。"""
from config.registration_drivers import REGISTRATION_DRIVERS, normalize_registration_driver

__all__ = ["REGISTRATION_DRIVERS", "normalize_registration_driver"]
