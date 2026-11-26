"""Shared Beijing calendar date expression for stored account creation times."""
from __future__ import annotations

import re


_SQL_ALIAS = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)
_DATE_SYNTAX = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_TIME_SYNTAX = r"(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]([.][0-9]+)?"
_ZONE_SYNTAX = r"([zZ]|[+-][0-9]{2}(:?[0-9]{2})?)"


def account_created_date_sql(alias: str = "a") -> str:
    """Return an account's Beijing date, or NULL for absent/invalid values.

    Historical timestamps without a zone already record Beijing wall time.
    Their calendar date is used directly, independent of the database timezone.
    Explicit offsets are converted to Asia/Shanghai before extracting the date.
    Both syntax and PostgreSQL input validation guard every timestamp cast.
    """
    if not _SQL_ALIAS.fullmatch(alias):
        raise ValueError("Account date SQL requires a plain table alias")
    value = f"NULLIF(BTRIM({alias}.created_at), '')"
    naive_syntax = f"^{_DATE_SYNTAX}[T ]{_TIME_SYNTAX}$"
    zoned_syntax = f"^{_DATE_SYNTAX}[T ]{_TIME_SYNTAX}{_ZONE_SYNTAX}$"
    return f"""CASE
        WHEN {value} ~ '^{_DATE_SYNTAX}$'
         AND pg_input_is_valid({value}, 'date')
            THEN {value}::date
        WHEN {value} ~ '{naive_syntax}'
         AND pg_input_is_valid({value}, 'timestamp without time zone')
            THEN {value}::timestamp::date
        WHEN {value} ~ '{zoned_syntax}'
         AND pg_input_is_valid({value}, 'timestamp with time zone')
            THEN ({value}::timestamptz AT TIME ZONE 'Asia/Shanghai')::date
        ELSE NULL::date
    END"""
