# -*- coding: utf-8 -*-
"""完整收件地址的结构化证据与母子地址隔离。"""
from __future__ import annotations

import re
from collections.abc import Mapping
from email.message import Message
from email.utils import getaddresses

_ADDRESS = re.compile(r"[^\s<>@,;]+@[^\s<>@,;]+\Z")
# 只解析 Received 的正式 for 子句，不扫描 from/by/comment 里的邮箱。
_RECEIVED_FOR = re.compile(r"\bfor\s+(?:<([^<>\r\n]+)>|([^\s<>;]+))\s*(?=;|$)", re.I)
_RECEIVED_BY = re.compile(r"\bby\s+([a-z0-9][a-z0-9.-]*)\b", re.I)


def _addresses(values) -> set[str]:
    if isinstance(values, str):
        values = [values]
    result = set()
    for _name, address in getaddresses([str(value) for value in (values or [])]):
        address = address.strip().lower()
        if _ADDRESS.fullmatch(address):
            result.add(address)
    return result


def _api_addresses(values) -> set[str]:
    if isinstance(values, (str, Mapping)):
        values = [values]
    out = set()
    for value in values or []:
        if isinstance(value, Mapping):
            value = value.get("emailAddress") or value.get("EmailAddress") or value
            value = value.get("address") or value.get("Address") or "" if isinstance(value, Mapping) else value
        out.update(_addresses([value]))
    return out


def _header_values(candidate) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    if isinstance(candidate, Message):
        pairs = candidate.items()
    else:
        raw = candidate.get("internetMessageHeaders") or candidate.get("InternetMessageHeaders") or candidate.get("headers") or []
        if isinstance(raw, Mapping):
            pairs = [(key, entry) for key, value in raw.items() for entry in (value if isinstance(value, list) else [value])]
        else:
            pairs = [(row.get("name") or row.get("Name") or "", row.get("value") or row.get("Value") or "") for row in raw if isinstance(row, Mapping)]
    for name, value in pairs:
        headers.setdefault(str(name).lower(), []).append(str(value))
    return headers


def extract_recipient_evidence(candidate: Message | Mapping) -> dict:
    """提取地址及出处；Received 的 iCloud for 证据只适用于已验证的 HME 链路。

    主机语法不是身份认证；连接器必须读取真实收件箱原始头，不能把用户正文
    或未验证外部接口的自称头字段提升为投递证据。
    """
    if isinstance(candidate, Mapping) and isinstance(candidate.get("recipient_evidence"), Mapping):
        return dict(candidate["recipient_evidence"])
    headers = _header_values(candidate)
    displayed = _addresses(headers.get("to", []) + headers.get("cc", []))
    original = _addresses(headers.get("x-original-to", []) + headers.get("envelope-to", []))
    forwarding = _addresses(headers.get("delivered-to", []) + headers.get("x-forwarded-to", []))
    hme_recipients = _addresses(headers.get("x-icloud-hme", []))
    received_for = set()
    evidence = []
    for raw in headers.get("received", []):
        value = re.sub(r"\r?\n[ \t]+", " ", raw)
        # 注释不能制造伪造的 for/by 子句；嵌套注释保守移除。
        previous = None
        while previous != value:
            previous = value
            value = re.sub(r"\([^()]*\)", " ", value)
        matches = list(_RECEIVED_FOR.finditer(value))
        by = _RECEIVED_BY.search(value)
        if (len(matches) != 1 or by is None
                or len(re.findall(r"\bfor\s+", value, re.I)) != 1
                or by.start() > matches[0].start()):
            continue
        addresses = _addresses([matches[0].group(1) or matches[0].group(2)])
        if len(addresses) != 1:
            continue
        received_for.update(addresses)
        host = by.group(1).lower().rstrip(".")
        # 来自其他 hop 的最终 Gmail 目标单独留存，不能成为 HME 原始目标。
        is_icloud_hop = (
            any(host == domain or host.endswith("." + domain) for domain in ("icloud.com", "apple.com"))
            or re.fullmatch(r"p[0-9]+-icloudmta-[a-z0-9-]+", host) is not None
        )
        if is_icloud_hop:
            original.update(addresses)
            evidence.append({"kind": "icloud_received_for", "addresses": sorted(addresses)})
        else:
            forwarding.update(addresses)
    if isinstance(candidate, Mapping):
        displayed.update(_api_addresses(candidate.get("toRecipients") or candidate.get("ToRecipients") or []))
        displayed.update(_api_addresses(candidate.get("ccRecipients") or candidate.get("CcRecipients") or []))
        displayed.update(_addresses([candidate.get("to") or "", candidate.get("cc") or ""]))
        original.update(_api_addresses(candidate.get("original_recipients") or []))
        forwarding.update(_api_addresses(candidate.get("forwarding_destinations") or []))
    return {
        "original_recipients": sorted(original),
        "displayed_recipients": sorted(displayed),
        "forwarding_destinations": sorted(forwarding),
        "received_for": sorted(received_for),
        "hme_recipients": sorted(hme_recipients),
        "sources": evidence,
    }


def _family(address: str) -> str:
    local, sep, domain = address.partition("@")
    return local.split("+", 1)[0] + sep + domain


def candidate_match(target: str, candidate: Message | Mapping, *, forwarded: bool = False, strict_family: bool = False) -> bool:
    """精确匹配完整地址；已证明的同母原始目标优先，冲突时不降级。"""
    target = str(target or "").strip().lower()
    if not _ADDRESS.fullmatch(target):
        return False
    evidence = extract_recipient_evidence(candidate)
    original = {str(value).lower() for value in evidence.get("original_recipients", [])}
    displayed = {str(value).lower() for value in evidence.get("displayed_recipients", [])}
    forwarding = {str(value).lower() for value in evidence.get("forwarding_destinations", [])}
    family_original = {address for address in original if _family(address) == _family(target)}
    if family_original:
        return len(family_original) == 1 and target in family_original
    family_displayed = {address for address in displayed if _family(address) == _family(target)}
    if forwarded and "+" in target.partition("@")[0]:
        # HME 未改写完整 To 时可依据完整目标及 HME 母资源共同判断；
        # To 只剩母地址仍无法判定 child，不能退回母邮箱的最新码。
        hme_recipients = {str(value).lower() for value in evidence.get("hme_recipients", [])}
        hme_family = any(_family(address) == _family(target) for address in hme_recipients)
        return hme_family and family_displayed == {target}
    if forwarded and strict_family:
        # 上层已知母地址有派生历史时，显示母地址无法排除被改写的 child。
        return False
    if family_displayed:
        return target in family_displayed and not any(address != target for address in family_displayed)
    # 历史 HME 可只有 Delivered-To；子地址不能借最终转发目的地认领。
    return forwarded and "+" not in target.partition("@")[0] and target in forwarding
