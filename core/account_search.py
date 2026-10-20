# -*- coding: utf-8 -*-
"""账号高级搜索语法；列表与轻量状态查询共用同一份解析规则。"""
from __future__ import annotations

from dataclasses import dataclass


class AccountSearchError(ValueError):
    """可直接在搜索框旁展示的输入错误。"""


REGISTRATION_DRIVERS = {
    "protocol": frozenset({"protocol", "api", "http"}),
    "protocol_oss": frozenset({"protocol_oss"}),
    "protocol_oss_2": frozenset({"protocol_oss_2"}),
    "roxy": frozenset({"roxy", "roxybrowser", "fingerprint", "browser"}),
    "roxy_oss": frozenset({"roxy_oss"}),
    "browser": frozenset({
        "roxy", "roxy_oss", "roxybrowser", "browser", "browser_use", "skyvern",
        "fingerprint", "cloak", "cloakbrowser",
    }),
}
_METHOD_ALIASES = {
    **dict.fromkeys(("协议", "协议注册", "protocol", "api", "http"), "protocol"),
    **dict.fromkeys(("优化协议", "本地优化协议"), "protocol"),
    **dict.fromkeys(("开源协议", "开源协议注册", "protocol_oss"), "protocol_oss"),
    **dict.fromkeys(("开源protocol-2", "protocol-2", "开源协议2", "protocol_oss_2"), "protocol_oss_2"),
    **dict.fromkeys((
        "roxy", "roxy注册", "本地roxy", "本地roxy注册", "本地浏览器", "roxybrowser", "roxybrowser注册", "fingerprint",
    ), "roxy"),
    **dict.fromkeys(("roxy_oss", "开源roxy", "开源roxy注册", "开源浏览器"), "roxy_oss"),
    **dict.fromkeys((
        "浏览器", "浏览器注册", "browser", "browser_use", "skyvern",
        "cloak", "cloakbrowser",
    ), "browser"),
}
_FIELD_ALIASES = {
    **dict.fromkeys(("方式", "注册方式", "method", "driver"), "method"),
    **dict.fromkeys(("地区", "国家", "注册地区", "注册出口", "注册出口国家", "region", "country"), "region"),
    **dict.fromkeys(("邮箱", "email"), "email"),
    **dict.fromkeys(("姓名", "name"), "name"),
    **dict.fromkeys(("来源", "source"), "source"),
    **dict.fromkeys(("备注", "note"), "note"),
    **dict.fromkeys(("id", "编号"), "id"),
}
_FIELD_LABELS = {
    "method": "注册方式", "region": "注册出口", "email": "邮箱",
    "name": "姓名", "source": "来源", "note": "备注", "id": "ID", "text": "关键词",
}
_COUNTRY_CODES = frozenset("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL
BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV
CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD
GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM
IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK
LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW
MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR
PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS
ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY
UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
""".split())
_COUNTRY_LABELS = dict(
    US="美国", JP="日本", GB="英国", CA="加拿大", AU="澳大利亚", DE="德国",
    FR="法国", NL="荷兰", SG="新加坡", KR="韩国", HK="中国香港", TW="中国台湾",
    CN="中国", ES="西班牙", IT="意大利", CH="瑞士", SE="瑞典", NO="挪威",
    PL="波兰", BR="巴西", MX="墨西哥", IN="印度", ID="印度尼西亚", TH="泰国",
    VN="越南", PH="菲律宾", MY="马来西亚", AE="阿联酋", TR="土耳其",
    NZ="新西兰", IE="爱尔兰", RU="俄罗斯", ZA="南非",
)
_COUNTRY_ALIASES = {label: code for code, label in _COUNTRY_LABELS.items()}
_COUNTRY_ALIASES.update({"香港": "HK", "台湾": "TW", "英国": "GB", "UK": "GB"})


@dataclass(frozen=True)
class AccountSearchTerm:
    field: str
    value: str
    raw: str

    def display(self, query_without: str) -> dict[str, str]:
        value = self.value
        if self.field == "method":
            value = {
                "protocol": "本地优化协议",
                "protocol_oss": "开源协议",
                "protocol_oss_2": "开源protocol-2",
                "roxy": "本地 Roxy",
                "roxy_oss": "开源 Roxy",
                "browser": "浏览器",
            }[value]
        elif self.field == "region" and value in _COUNTRY_LABELS:
            value = f"{_COUNTRY_LABELS[value]} {value}"
        return {
            "field": self.field, "label": _FIELD_LABELS[self.field],
            "value": self.value, "display_value": value, "query_without": query_without,
        }


def _tokens(query: str) -> list[tuple[str, str, int | None, bool]]:
    """仅在引号外拆分空格和斜杠，保留原输入以便逐项移除条件。"""
    result = []
    index = 0
    while index < len(query):
        if query[index].isspace() or query[index] == "/":
            index += 1
            continue
        start = index
        chars: list[str] = []
        quoted = False
        in_quote = False
        colon = None
        while index < len(query):
            char = query[index]
            if char == '"':
                quoted = True
                in_quote = not in_quote
            elif in_quote and char == "\\" and index + 1 < len(query) and query[index + 1] in ('"', "\\"):
                index += 1
                chars.append(query[index])
            elif not in_quote and (char.isspace() or char == "/"):
                # 支持「地区: JP」，但字段值仍必须存在。
                if char.isspace() and colon is not None and len(chars) == colon + 1:
                    index += 1
                    continue
                break
            else:
                if not in_quote and char in (":", "：") and colon is None:
                    colon = len(chars)
                chars.append(char)
            index += 1
        if in_quote:
            raise AccountSearchError('双引号未闭合，请在完整文字末尾补上 "。')
        value = "".join(chars)
        if not value:
            raise AccountSearchError("搜索条件不能为空，请填写双引号中的文字。")
        result.append((value, query[start:index], colon, quoted))
        if len(result) > 32:
            raise AccountSearchError("搜索条件过多，请最多输入 32 个条件。")
    return result


def _country(value: str) -> str | None:
    value = value.upper()
    if value.endswith("注册"):
        value = value[:-2]
    return _COUNTRY_ALIASES.get(value) or (value if value in _COUNTRY_CODES else None)


def parse_account_search(query: str) -> list[AccountSearchTerm]:
    query = str(query or "").strip()
    if len(query) > 1000:
        raise AccountSearchError("搜索内容过长，请控制在 1000 个字符以内。")
    terms = []
    for text, raw, colon, quoted in _tokens(query):
        field = "text"
        value = text
        if colon is not None:
            field_name, value = text[:colon].lower(), text[colon + 1:]
            field = _FIELD_ALIASES.get(field_name)
            if field is None:
                raise AccountSearchError("不支持该搜索字段，可用：方式、地区、邮箱、姓名、来源、备注、ID；完整文字请加双引号。")
            if not value:
                raise AccountSearchError(f"{_FIELD_LABELS[field]}缺少搜索内容，请在冒号后填写。")
        elif not quoted:
            if value.lower() in _METHOD_ALIASES:
                field = "method"
            elif _country(value):
                field = "region"
        if field == "method":
            value = _METHOD_ALIASES.get(value.lower())
            if value is None:
                raise AccountSearchError("注册方式不支持该值，请输入本地优化协议、开源协议、本地Roxy、开源Roxy或浏览器。")
        elif field == "region":
            value = _country(value)
            if value is None:
                raise AccountSearchError("注册地区不支持该值，请输入有效的两位国家代码，例如「地区:JP」或「地区:日本」。")
        elif field == "id":
            value = value.lstrip("#")
            if not value.isascii() or not value.isdecimal():
                raise AccountSearchError("账号 ID 必须是数字，例如「ID:123」。")
        terms.append(AccountSearchTerm(field=field, value=value, raw=raw))
    return terms


def account_search_filters(terms: list[AccountSearchTerm]) -> list[dict[str, str]]:
    return [
        term.display(" ".join(other.raw for other_index, other in enumerate(terms) if other_index != index))
        for index, term in enumerate(terms)
    ]
