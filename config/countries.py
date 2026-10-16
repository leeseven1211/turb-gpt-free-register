# -*- coding: utf-8 -*-
"""查套餐国家配置的规范化与 ISO 3166-1 alpha-2 校验。"""
from __future__ import annotations

import re
from collections.abc import Iterable


# ISO 3166-1 alpha-2 中的国家、地区和特殊区域代码。查询线路只接受
# 供应商可以识别的两位代码，但不能把配置范围错误限制为少数默认国家。
ISO_3166_ALPHA2 = frozenset(
    """
    AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ
    CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ
    NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
    """.split()
)


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if value.strip() == "[]":
            return []
        return [part for part in re.split(r"[\s,]+", value.strip()) if part]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        result: list[str] = []
        for item in value:
            result.extend(_tokens(item))
        return result
    return [str(value).strip()]


def _normalize_countries(value: object, label: str) -> list[str]:
    """规范化国家列表，错误文案标明实际配置用途。"""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in _tokens(value):
        country = str(raw).strip().upper()
        if country == "RAND" or country not in ISO_3166_ALPHA2:
            raise ValueError(f"{label}必须是已知 ISO 3166-1 两位代码：{raw}")
        if country not in seen:
            seen.add(country)
            normalized.append(country)
    return normalized


def normalize_plan_check_countries(value: object) -> list[str]:
    """空列表沿用账号注册国家，其余返回有序且去重的国家代码。"""
    return _normalize_countries(value, "查套餐国家")


def normalize_proxy_pool_countries(value: object) -> list[str]:
    """空列表不额外预热国家，业务查询国家由独立配置决定。"""
    return _normalize_countries(value, "代理池预热国家")


__all__ = ["ISO_3166_ALPHA2", "normalize_plan_check_countries", "normalize_proxy_pool_countries"]
