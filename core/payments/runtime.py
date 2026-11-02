"""独立支付公共运行配置和只读积分查询。"""
from __future__ import annotations

import os
from types import SimpleNamespace

from core.payments.xxsyun import API_BASE, PaymentError, XXSYUNClient, validate_api_base


def _setting(name, default=None):
    from config.env_loader import load_env
    load_env(override=True)
    import config
    return os.environ.get(name, getattr(config, name, default))


def configuration(settings=None):
    read = settings if settings is not None else _setting
    if isinstance(read, dict):
        read = read.get
    prefix = "EXTRACT_LINK_PAYMENT_XXSYUN_"

    def number(name, default, lower, upper):
        try:
            return max(lower, min(upper, int(read(prefix + name, default))))
        except (TypeError, ValueError, OverflowError):
            return default

    return SimpleNamespace(api_base=validate_api_base(read(prefix + "API_BASE", API_BASE)),
                           api_key=str(read(prefix + "API_KEY", "") or "").strip(),
                           timeout=number("REQUEST_TIMEOUT", 30, 5, 300),
                           poll_interval=number("POLL_INTERVAL", 10, 10, 300),
                           concurrency=number("CONCURRENCY", 1, 1, 50))


def query_xxsyun_balance(api_key: str | None = None) -> dict:
    config = configuration()
    key = config.api_key if api_key is None else str(api_key).strip()
    if not key:
        raise PaymentError("API_KEY_MISSING")
    balance = XXSYUNClient(config.api_base, key, timeout=config.timeout).query_balance()
    return {"ok": True, "payment_provider": "xxsyun", "balance": balance}
