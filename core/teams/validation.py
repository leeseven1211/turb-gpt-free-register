"""Team HTTP 与应用服务共用的严格输入校验。"""
from __future__ import annotations

import re
from collections.abc import Mapping

from core.teams.errors import TeamError


ROLE = ("owner", "admin", "member", "unknown")
MEMBERSHIP = ("joined", "left", "unconfirmed")
INVITATION = ("not_sent", "pending", "accepted", "revoked", "expired", "unconfirmed")
EXECUTION = (
    "none", "queued", "running", "waiting", "cancelling", "settling", "stopping", "success",
    "partial_success", "failed", "stopped", "cancelled", "interrupted", "deactivated", "unsupported",
)
STAGE = ("queued", "manager_verify", "state_check", "invite", "member_auth", "accept", "member_verify", "persist", "complete")
SYNC_STATUS = ("never", "queued", "running", "success", "partial_success", "failed", "interrupted")
ACCEPTANCE = ("pending", "accepted", "reused", "skipped", "failed")
_DECIMAL_ID = re.compile(r"[1-9][0-9]*\Z", re.ASCII)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")
_QUERY_ENUMS = {
    "teams": {"role": ROLE, "last_sync_status": SYNC_STATUS},
    "members": {"membership_state": MEMBERSHIP, "role": ROLE, "linked": ("all", "linked", "unlinked")},
    "invitations": {
        "invitation_state": INVITATION, "membership_state": MEMBERSHIP,
        "execution_status": EXECUTION, "stage": STAGE,
    },
    "candidates": {
        "scope": ("unassigned", "all"), "archived": ("0", "only", "all"),
        "email_status": ("invalid", "unmarked"),
    },
    "join_items": {"acceptance_status": ACCEPTANCE, "execution_status": EXECUTION},
    "empty": {},
}
_QUERY_IDS = {"teams": {"manager_account_id"}, "invitations": {"join_request_id"}}
_QUERY_BOOLS = {"has_access_token", "has_password", "totp_enabled"}
_PAYLOAD_FIELDS = {
    "probe": {"manager_account_id", "target_workspace_id"},
    "create": {"manager_account_id", "workspace_id", "probe_id", "probe_revision", "display_name", "planned_member_limit"},
    "update": {"expected_revision", "display_name", "planned_member_limit", "manager_account_id", "probe_id", "probe_revision"},
    "sync": set(), "reverify": set(), "sync_bulk": {"team_ids"},
    "resolve": {"values"},
    "preview": {"account_ids", "expected_emails", "selection_id", "selection_revision"},
    "join": {"account_ids", "expected_emails", "selection_id", "selection_revision"},
    "invitation": set(), "invitation_bulk": {"invitation_ids"},
}
_READ_POSTS = {"resolve", "preview"}


def _invalid(field, message="参数不符合 Team 接口约定。"):
    raise TeamError("parameter_invalid", message, status=422, field=field)


def _unknown(values, allowed):
    fields = sorted(set(values) - set(allowed))
    if fields:
        raise TeamError("field_not_supported", "请求包含不支持的字段。", status=422,
                        field=fields[0], details={"fields": fields})


def local_id(value, field):
    """本地 ID 始终保留为无损的正整数十进制字符串。"""
    if not isinstance(value, str):
        _invalid(field, "本地 ID 必须是正整数十进制字符串。")
    size = len(value)
    # 同长度十进制数字的字典序等同整数序，避免批量校验逐项转换大整数。
    if (not 0 < size <= 19 or not value.isascii() or not value.isdecimal() or value[0] == "0"
            or (size == 19 and value > "9223372036854775807")):
        _invalid(field, "本地 ID 必须是正整数十进制字符串。")
    return value


def _positive_integer(value, field):
    if type(value) is not int or value < 1:
        _invalid(field, "版本或上限必须是正整数。")
    return value


def _nonempty_string(value, field):
    if not isinstance(value, str) or not value.strip():
        _invalid(field, "此字段必须是非空字符串。")
    return value


def _array(value, field, maximum, *, ids=False):
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        _invalid(field, f"此字段必须包含 1 至 {maximum} 项。")
    for item in value:
        if ids:
            local_id(item, field)
        else:
            _nonempty_string(item, field)
    return list(value)


def idempotency_key(header, payload):
    """接收头或 JSON 请求键，双源必须在去除首尾空格后相同。"""
    body = payload.get("idempotency_key")
    supplied = []
    for provided, value in ((header is not None, header), ("idempotency_key" in payload, body)):
        if not provided:
            continue
        if not isinstance(value, str):
            raise TeamError("idempotency_key_invalid", "幂等键必须是 16 至 128 字符的字符串。",
                            status=422, field="idempotency_key")
        key = value.strip()
        if not 16 <= len(key) <= 128:
            raise TeamError("idempotency_key_invalid", "幂等键必须是 16 至 128 字符的字符串。",
                            status=422, field="idempotency_key")
        supplied.append(key)
    if not supplied:
        raise TeamError("idempotency_key_required", "写请求必须提供幂等键。", status=422, field="idempotency_key")
    if len(set(supplied)) > 1:
        raise TeamError("idempotency_key_mismatch", "请求头与 JSON 中的幂等键不一致。",
                        status=422, field="idempotency_key")
    return supplied[0]


def validate_query(kind, values):
    """只接受端点公布的单值筛选，并补充分页和业务默认值。"""
    enums = _QUERY_ENUMS[kind]
    allowed = set(enums) | _QUERY_IDS.get(kind, set())
    if kind != "empty":
        allowed |= {"page", "page_size", "include_facets"}
    if kind in {"teams", "members", "invitations", "candidates"}:
        allowed.add("q")
    if kind == "candidates":
        allowed |= _QUERY_BOOLS
    if kind == "join_items":
        allowed.add("reason_code")
    _unknown(values, allowed)
    result = {}
    for field, raw in values.items():
        if isinstance(raw, (list, tuple)):
            if len(raw) != 1:
                _invalid(field, "筛选字段只接受一个值。")
            raw = raw[0]
        if not isinstance(raw, str):
            _invalid(field)
        if field in {"page", "page_size"}:
            if _DECIMAL_ID.fullmatch(raw) is None:
                _invalid(field, "分页参数必须是正整数。")
            try:
                result[field] = int(raw)
            except ValueError:
                _invalid(field, "分页参数超出可处理范围。")
            if field == "page_size" and result[field] > 100:
                _invalid(field, "分页大小必须为 1 至 100。")
        elif field == "include_facets":
            if raw not in {"0", "1"}:
                _invalid(field, "include_facets 只接受 0 或 1。")
            result[field] = raw == "1"
        elif field in _QUERY_IDS.get(kind, set()):
            result[field] = local_id(raw, field)
        elif field in enums:
            if raw not in enums[field]:
                _invalid(field, "筛选值不属于允许的枚举。")
            result[field] = raw
        elif field in _QUERY_BOOLS:
            if raw not in {"true", "false"}:
                _invalid(field, "布尔筛选只接受 true 或 false。")
            result[field] = raw == "true"
        else:
            if field == "reason_code" and not raw.strip():
                _invalid(field)
            result[field] = raw.strip()
    if kind != "empty":
        result.setdefault("page", 1)
        result.setdefault("page_size", 20)
        result.setdefault("include_facets", False)
    if kind == "members":
        result.setdefault("membership_state", "joined")
    if kind == "candidates":
        result.setdefault("scope", "unassigned")
        result.setdefault("archived", "0")
    return result


def validate_payload(kind, payload):
    """保留原目标顺序和重复项，数量与去重由持久服务按原请求计算。"""
    if not isinstance(payload, dict):
        raise TeamError("invalid_json", "请求体必须是 JSON 对象。", status=400)
    allowed = _PAYLOAD_FIELDS[kind]
    if kind not in _READ_POSTS:
        allowed = allowed | {"idempotency_key"}
    _unknown(payload, allowed)
    result = {key: value for key, value in payload.items() if key != "idempotency_key"}
    required = {
        "probe": {"manager_account_id"},
        "create": {"manager_account_id", "workspace_id", "probe_id", "probe_revision"},
        "update": {"expected_revision"}, "sync_bulk": {"team_ids"}, "resolve": {"values"},
        "invitation_bulk": {"invitation_ids"},
    }.get(kind, set())
    for field in sorted(required):
        if field not in result:
            _invalid(field, "缺少必填字段。")
    for field in {"manager_account_id", "probe_id", "selection_id"} & result.keys():
        local_id(result[field], field)
    for field in {"expected_revision", "probe_revision", "selection_revision"} & result.keys():
        _positive_integer(result[field], field)
    for field in {"workspace_id", "target_workspace_id"} & result.keys():
        _nonempty_string(result[field], field)
    if "display_name" in result and result["display_name"] is not None:
        name = result["display_name"]
        if not isinstance(name, str) or len(name) > 120:
            _invalid("display_name", "备注名必须为不超过 120 字符的字符串或 null。")
        result["display_name"] = name.strip() or None
    if "planned_member_limit" in result and result["planned_member_limit"] is not None:
        _positive_integer(result["planned_member_limit"], "planned_member_limit")
    for field, maximum in (("team_ids", 100), ("invitation_ids", 10_000), ("account_ids", 10_000)):
        if field in result:
            result[field] = _array(result[field], field, maximum, ids=True)
    if kind == "resolve":
        result["values"] = [value.strip() for value in _array(result["values"], "values", 10_000)]
        for value in result["values"]:
            if _DECIMAL_ID.fullmatch(value) is None and re.fullmatch(r"[^@\s]+@[^@\s]+", value) is None:
                _invalid("values", "解析目标必须是邮箱或正整数账号 ID。")
            if _DECIMAL_ID.fullmatch(value) is not None:
                local_id(value, "values")
    if kind == "update":
        if not {"display_name", "planned_member_limit", "manager_account_id"} & result.keys():
            _invalid(None, "至少提交一个可编辑字段。")
        if "manager_account_id" in result:
            for field in ("probe_id", "probe_revision"):
                if field not in result:
                    _invalid(field, "更换管理账号必须提供匹配的探测证据。")
        elif {"probe_id", "probe_revision"} & result.keys():
            _invalid("probe_id", "未更换管理账号时不能提交探测证据。")
    if kind in {"join", "preview"}:
        explicit = "account_ids" in result
        selection = "selection_id" in result
        if explicit == selection:
            _invalid(None, "account_ids 与 selection_id 必须且只能提供一种。")
        if selection:
            if "selection_revision" not in result:
                _invalid("selection_revision", "固定名单必须提供 selection_revision。")
            if "expected_emails" in result:
                _invalid("expected_emails", "固定名单使用已保存的邮箱快照。")
        else:
            if "selection_revision" in result:
                _invalid("selection_revision", "显式账号模式不接受 selection_revision。")
            if "expected_emails" in result:
                snapshots = result["expected_emails"]
                if not isinstance(snapshots, Mapping):
                    _invalid("expected_emails", "邮箱快照必须是账号 ID 到邮箱的对象。")
                normalized = {}
                selected_ids = set(result["account_ids"])
                for account_id, email in snapshots.items():
                    if account_id not in selected_ids:
                        _invalid("expected_emails", "邮箱快照的账号必须属于 account_ids。")
                    if not isinstance(email, str):
                        _invalid("expected_emails", "邮箱快照必须是非空邮箱。")
                    email = email.strip()
                    if _EMAIL.fullmatch(email) is None:
                        _invalid("expected_emails", "邮箱快照必须是非空邮箱。")
                    normalized[account_id] = email
                result["expected_emails"] = normalized
    return result
