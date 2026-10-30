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


def _auth_result_clauses(raw: str) -> list[str]:
    """按认证结果语法分段；注释或引号里的分号不能创造另一条验证结果。"""
    raw = re.sub(r"\r?\n[ \t]+", " ", str(raw))
    if "\r" in raw or "\n" in raw:
        return []
    clauses, current = [], []
    depth = 0
    quoted = False
    escaped = False
    for char in raw:
        if escaped:
            if not depth:
                current.append(char)
            escaped = False
            continue
        if char == "\\" and (depth or quoted):
            escaped = True
            if not depth:
                current.append(char)
            continue
        if depth:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            continue
        if char == '"':
            quoted = not quoted
            current.append(char)
        elif char == "(" and not quoted:
            depth = 1
            current.append(" ")
        elif char == ")" and not quoted:
            return []
        elif char == ";" and not quoted:
            clauses.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if depth or quoted or escaped:
        return []
    clauses.append("".join(current).strip())
    return clauses


def _openai_verp_recipient(address: str) -> str | None:
    """仅解码已实测的两种 OpenAI VERP 模板，不推断普通退信地址。"""
    match = re.fullmatch(
        r"bounces\+[0-9]+-[a-z0-9]+-([^@\s<>]+)@em[0-9]+\.tm\.openai\.com",
        str(address or "").lower(),
    )
    if match is None:
        match = re.fullmatch(
            r"bounce\+[0-9a-f]{6}\.[0-9a-f]{6}-([^@\s<>]+)@tm1\.openai\.com",
            str(address or "").lower(),
        )
    if match is None:
        return None
    local, separator, domain = match.group(1).rpartition("=")
    if not separator or not local or "=" in local:
        return None
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", domain):
        return None
    recipient = local + "@" + domain
    if len(local.encode()) > 64 or len(recipient.encode()) > 254:
        return None
    return recipient if _addresses([recipient]) == {recipient} else None


def _unresolved_openai_child_families(address: str, hme_recipients: set[str]) -> set[str]:
    """已知域的未知模板若明确含完整 child，只能阻断同母回退，不能认领验证码。"""
    local, separator, domain = str(address or "").lower().rpartition("@")
    if not separator or re.fullmatch(r"(?:em[0-9]+\.tm\.openai\.com|tm1\.openai\.com)", domain) is None:
        return set()
    blocked = set()
    for parent in hme_recipients:
        family = _family(parent)
        parent_local, _, parent_domain = family.partition("@")
        match = re.search(r"(?:^|[-.])(" + re.escape(parent_local) + r"\+[^@=\s<>]+)=" + re.escape(parent_domain) + r"\Z", local)
        if match is not None:
            recipient = match.group(1) + "@" + parent_domain
            if _addresses([recipient]) == {recipient}:
                blocked.add(family)
    return blocked


def _hme_addresses(values: list[str]) -> set[str]:
    """HME 原始参数头只取实测 p= 母地址；f=/s= 是其他角色，不能混用。"""
    recipients = set()
    for raw in values:
        clauses = _auth_result_clauses(raw)
        if not clauses:
            continue
        if not any(re.match(r"^[a-z][a-z0-9_-]*\s*=", clause, re.I) for clause in clauses):
            # 保留连接器/历史邮件提供的裸母地址格式。
            parent = raw.strip().lower()
            if _ADDRESS.fullmatch(parent) and _addresses([parent]) == {parent}:
                recipients.add(parent)
            continue
        parents = [match.group(1).strip() for clause in clauses if (match := re.fullmatch(r"p\s*=\s*(.+)", clause, re.I))]
        if len(parents) != 1:
            continue
        parent = parents[0]
        if parent.startswith('"') and parent.endswith('"'):
            parent = parent[1:-1]
        parent = parent.lower()
        if _ADDRESS.fullmatch(parent) and _addresses([parent]) == {parent}:
            recipients.add(parent)
    # 同一封 HME 邮件只能指向一个母资源；多头不同 p 不能任取其一佐证。
    return recipients if len(recipients) == 1 else set()


def _openai_spf_recipients(headers: dict[str, list[str]], hme_recipients: set[str]) -> tuple[set[str], set[str]]:
    """使用 iCloud 已验证 SPF 的同一方法条目恢复完整目标，拒绝跨条目拼接。

    该规则来自目标平台的真实 HME 转发样本。Authentication-Results 必须来自
    收件连接器保留的原始头；它不是任意正文或裸 Return-Path 的通用推断规则。
    """
    recipients, conflicts = set(), set()
    claims: dict[str, set[tuple[str, str]]] = {}
    for raw in headers.get("authentication-results", []):
        clauses = _auth_result_clauses(raw)
        if not clauses or clauses[0].lower() != "spf.icloud.com":
            continue
        for clause in clauses[1:]:
            method = re.match(r"^spf\s*=\s*(pass|fail|softfail|neutral|none|temperror|permerror)(?:\s|$)", clause, re.I)
            if method is None:
                continue
            # 带点的属性键不是认证方法；reason 是方法的可选说明。其余裸键
            # 只能有开头的 spf，避免漏列 auth 或未来方法而拼接出一条假 SPF 结果。
            unquoted = re.sub(r'"(?:\\.|[^"\\])*"', lambda match: " " * len(match.group()), clause)
            method_keys = [key.lower() for key in re.findall(r"(?:^|\s)([a-z][a-z0-9_-]*)\s*=", unquoted, re.I) if key.lower() != "reason"]
            if method_keys != ["spf"]:
                continue
            # 一个 SPF 方法条目只接受一个 smtp.mailfrom；不能借其他方法的 pass。
            properties = [match for match in re.finditer(
                r'(?:^|\s)(?P<name>smtp\.mailfrom)\s*=\s*(?P<value>"[^"\\]*"|[^\s;]+)(?=\s|$)', clause, re.I,
            ) if unquoted[match.start("name"):match.end("name")].lower() == "smtp.mailfrom"]
            if len(properties) != 1:
                continue
            value = properties[0].group("value")
            if value.startswith('"'):
                value = value[1:-1]
            recipient = _openai_verp_recipient(value)
            if recipient is None:
                conflicts.update(_unresolved_openai_child_families(value, hme_recipients))
                continue
            family = _family(recipient)
            hme_family = {address for address in hme_recipients if _family(address) == family}
            if not hme_family:
                continue
            # HME 通常给出母地址；若它明确给出另一个 child，则不能只凭同母忽略冲突。
            if any("+" in address.partition("@")[0] and address != recipient for address in hme_family):
                conflicts.add(family)
                continue
            verdict = method.group(1).lower()
            claims.setdefault(family, set()).add((recipient, verdict))
            if verdict == "pass":
                recipients.add(recipient)
            else:
                # 未通过 SPF 的完整同族声明不可认领，也不能回退到改写后的母 To。
                conflicts.add(family)
    for family, family_claims in claims.items():
        passed = {(address, verdict) for address, verdict in family_claims if verdict == "pass"}
        if passed and (len(passed) != 1 or family_claims != passed):
            conflicts.add(family)
    return recipients, conflicts


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
    hme_recipients = _hme_addresses(headers.get("x-icloud-hme", []))
    received_for = set()
    evidence = []
    provider_recipients, conflicting_families = _openai_spf_recipients(headers, hme_recipients)
    if provider_recipients:
        original.update(provider_recipients)
        evidence.append({"kind": "openai_icloud_spf_verp", "addresses": sorted(provider_recipients)})
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
        "conflicting_original_families": sorted(conflicting_families),
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
    family = _family(target)
    if family in evidence.get("conflicting_original_families", []):
        return False
    hme_recipients = {str(value).lower() for value in evidence.get("hme_recipients", [])}
    if any(_family(address) == family and "+" in address.partition("@")[0] and address != target for address in hme_recipients):
        return False
    family_original = {address for address in original if _family(address) == _family(target)}
    if family_original:
        return len(family_original) == 1 and target in family_original
    family_displayed = {address for address in displayed if _family(address) == _family(target)}
    if forwarded and "+" in target.partition("@")[0]:
        # HME 未改写完整 To 时可依据完整目标及 HME 母资源共同判断；
        # To 只剩母地址仍无法判定 child，不能退回母邮箱的最新码。
        hme_family = any(_family(address) == _family(target) for address in hme_recipients)
        return hme_family and family_displayed == {target}
    if forwarded and strict_family:
        # 上层已知母地址有派生历史时，显示母地址无法排除被改写的 child。
        return False
    if family_displayed:
        return target in family_displayed and not any(address != target for address in family_displayed)
    # 历史 HME 可只有 Delivered-To；子地址不能借最终转发目的地认领。
    return forwarded and "+" not in target.partition("@")[0] and target in forwarding
