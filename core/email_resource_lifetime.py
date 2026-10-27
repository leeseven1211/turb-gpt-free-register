"""Explicit mailbox/read-receipt expiry; unspecified lifetimes stay unspecified."""
from __future__ import annotations

import math
import re
import time
from datetime import datetime, timezone

_ISO_EXPIRY = re.compile(r'^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$')


class EmailResourceLifetimeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f'{code}: {message}')
        self.error_code = self.cause_code = code
        self.identity_locked = True
        self.request_unknown = False


def normalize_expiry(value, *, reject_expired: bool = False, now: float | None = None) -> dict:
    """Normalize an explicit timezone-qualified ISO datetime, without guessing TTL."""
    if value is None or value == '':
        return {}
    raw = value.strip() if isinstance(value, str) else ''
    if not raw:
        if isinstance(value, str):
            return {}
        raise ValueError('email_resource_expiry_invalid: 有效期须为带时区的 ISO8601 时间')
    try:
        if not _ISO_EXPIRY.fullmatch(raw):
            raise ValueError
        parsed = datetime.fromisoformat(raw.replace('t', 'T').replace('z', 'Z').replace('Z', '+00:00'))
        if parsed.utcoffset() is None:
            raise ValueError
        utc = parsed.astimezone(timezone.utc)
        epoch = utc.timestamp()
    except (ValueError, OverflowError):
        raise ValueError('email_resource_expiry_invalid: 有效期须为带时区的有效 ISO8601 时间') from None
    if reject_expired and epoch <= (time.time() if now is None else now):
        raise ValueError('email_resource_expired: 邮箱或取码凭据已过期，请保留原领取记录')
    return {'expires_at': utc.isoformat().replace('+00:00', 'Z'), 'expires_at_epoch': epoch}


def require_usable(resource, *, now: float | None = None) -> None:
    """Refuse expired or inconsistent receipts without changing their ownership."""
    def field(name):
        return resource.get(name) if isinstance(resource, dict) else getattr(resource, name, None)

    raw, epoch = field('expires_at'), field('expires_at_epoch')
    try:
        normalized = normalize_expiry(raw)
        if normalized:
            parsed_epoch = normalized['expires_at_epoch']
            if epoch not in (None, '') and abs(float(epoch) - parsed_epoch) > 0.001:
                raise ValueError
            epoch = parsed_epoch
        if epoch in (None, ''):
            return
        if isinstance(epoch, bool) or not math.isfinite(float(epoch)):
            raise ValueError
        epoch = float(epoch)
    except (ValueError, TypeError, OverflowError):
        raise EmailResourceLifetimeError('email_resource_expiry_invalid', '原邮箱有效期无效，不能继续或改领其他地址') from None
    if epoch <= (time.time() if now is None else now):
        raise EmailResourceLifetimeError('email_resource_expired', '邮箱或取码凭据已过期，保留原领取事实，不能自动换号')


def eligibility_sql(alias: str) -> str:
    """Use DB time and fail closed for noncanonical imported expiry metadata."""
    epoch = f"{alias}.data->>'expires_at_epoch'"
    expiry = f"{alias}.data->>'expires_at'"
    instant = f"to_timestamp(({epoch})::double precision) AT TIME ZONE 'UTC'"
    canonical = (f"(NULLIF(BTRIM({expiry}), '') IS NULL OR "
                 f"{expiry} = to_char({instant}, 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') OR "
                 f"{expiry} = to_char({instant}, 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"'))")
    return (f"((NULLIF(BTRIM({expiry}), '') IS NULL AND NULLIF(BTRIM({epoch}), '') IS NULL) OR "
            f"CASE WHEN {epoch} ~ '^[0-9]+([.][0-9]+)?$' THEN "
            f"CASE WHEN ({epoch})::numeric BETWEEN 0 AND 253402300799.999999 THEN "
            f"({epoch})::numeric > EXTRACT(EPOCH FROM clock_timestamp()) AND {canonical} "
            f"ELSE FALSE END ELSE FALSE END)")
