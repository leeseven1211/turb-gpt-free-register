"""仅供单次 Codex 登录诊断：观察既有请求，并在 MFA 后查询一次官方会话。"""
from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Mapping
from urllib.parse import unquote, urlsplit

from core.codex.auth_page import CodexAuthPageSession, _trusted_url


_ORIGIN = "https://auth.openai.com"
_DUMP_URL = _ORIGIN + "/api/accounts/client_auth_session_dump"
_STAGES = ("bootstrap", "primary_verify", "mfa_issue", "mfa_verify")
_POST_STAGES = {"/api/accounts/password/verify": "primary_verify", "/api/accounts/mfa/issue_challenge": "mfa_issue",
                "/api/accounts/mfa/verify": "mfa_verify"}
_JAR_ALIASES = {"client_state": "oai-client-auth-session", "device_marker": "oai-did",
                "minimized_checksum": "auth-session-minimized-client-checksum"}
_KNOWN_KEYS = ("client_auth_session", "legacy_client_state", "session_identifier", "checksum", "page", "continue_url", "error")
_KEY_ALIASES = {"legacy_client_state": "oai-client-auth-session", "session_identifier": "session_id"}
_FLAGS = ("observed", "response_received", "json_parsed", "top_session_id_present", "nested_session_id_present",
          "auth_session_logging_id_present", "checksum_present", "session_id_comparable", "session_id_changed",
          "checksum_comparable", "checksum_changed", "jar_comparable", "jar_changed",
          "session_id_nested_comparable", "session_id_matches_nested", "minimized_checksum_present",
          "dump_checksum_jar_comparable", "dump_checksum_matches_jar")
_FAILURES = {"", "mfa_unconfirmed", "transport_error", "http_error", "invalid_json", "unknown_schema"}
_NEXT_TYPES = {"phone", "add_phone", "phone_verification", "workspace_select", "workspace_selection", "consent",
               "authorize", "email_verification", "email_otp", "email_otp_verify"}
_CAS_BOOLS = ("username_verified", "email_verified", "set_phone_number_verified", "phone_number_verified", "multi_channel_allowed")
_CAS_MODES = ("email_verification_mode", "phone_verification_mode")
_CAS_CHANNELS = ("phone_verification_channel", "set_phone_verification_channel")
_CAS_KEYS = _CAS_BOOLS + _CAS_MODES + _CAS_CHANNELS


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _status(value):
    return value if type(value) is int and 100 <= value <= 599 else 0


def _safe_cas(value):
    item = _mapping(value)
    result = {key: item.get(key) is True for key in _CAS_BOOLS}
    result.update({key + "_present": item.get(key + "_present") is True for key in _CAS_KEYS})
    for key in _CAS_CHANNELS:
        channel = item.get(key)
        result[key] = channel if isinstance(channel, str) and channel in {"", "sms", "whatsapp", "other"} else ""
    return result


def _safe_record(value):
    item = _mapping(value)
    result = {key: item.get(key) is True for key in _FLAGS}
    result["http_status"] = _status(item.get("http_status"))
    for key in ("jar_count", "auth_path_jar_count"):
        number = item.get(key)
        result[key] = number if type(number) is int and number >= 0 else 0
    for key, allowed in (("known_key_flags", _KNOWN_KEYS), ("known_jar_presence", _JAR_ALIASES)):
        values = _mapping(item.get(key))
        result[key] = {name: values.get(name) is True for name in allowed}
    result["client_auth_session"] = _safe_cas(item.get("client_auth_session"))
    return result


def safe_session_diagnostics(value) -> dict:
    """持久化前重新投影固定字段，仅输出布尔、整数和固定错误分类。"""
    item = _mapping(value)
    failure = item.get("dump_failure_kind")
    return {
        "mfa_verified": item.get("mfa_verified") is True,
        "dump_attempted": item.get("dump_attempted") is True,
        "dump_response_received": item.get("dump_response_received") is True,
        "dump_http_status": _status(item.get("dump_http_status")),
        "dump_failure_kind": failure if isinstance(failure, str) and failure in _FAILURES else "",
        "stages": {stage: _safe_record(_mapping(item.get("stages")).get(stage)) for stage in _STAGES},
        "dump": _safe_record(item.get("dump")),
    }


def _nonempty(value):
    return value if isinstance(value, str) and value else None


def _normalized_checksum(value):
    value = _nonempty(value)
    if value is None:
        return None
    try:
        decoded = json.loads(base64.b64decode(value + "=" * (-len(value) % 4), validate=True))
        return _nonempty(_mapping(decoded).get("cs")) or value
    except (ValueError, TypeError, UnicodeError):
        return value


def _cookie_matches(cookie, path):
    domain = str(getattr(cookie, "domain", "") or "").lstrip(".").lower()
    cookie_path = str(getattr(cookie, "path", "/") or "/")
    return bool(domain and (domain == "auth.openai.com" or "auth.openai.com".endswith("." + domain))
                and (path == cookie_path or path.startswith(cookie_path if cookie_path.endswith("/") else cookie_path + "/")))


def _cookies(base, path):
    """原始 Cookie 标识和值仅用于内存比较，返回摘要不含动态键名或地址。"""
    try:
        cookies = list(base.session.cookies.jar)
    except Exception:
        return None, {"jar_count": 0, "auth_path_jar_count": 0, "known_jar_presence": {}}, None
    state = tuple(sorted((str(cookie.name), str(cookie.domain), str(cookie.path), str(cookie.value)) for cookie in cookies))
    matching = [cookie for cookie in cookies if _cookie_matches(cookie, path)]
    summary = {"jar_count": len(cookies), "auth_path_jar_count": len(matching),
               "known_jar_presence": {alias: any(cookie.name == name for cookie in matching) for alias, name in _JAR_ALIASES.items()}}
    checksum = None
    for cookie in matching:
        if cookie.name == "auth-session-minimized-client-checksum":
            try:
                checksum = _normalized_checksum(_mapping(json.loads(unquote(cookie.value))).get("affinity"))
            except (ValueError, TypeError, UnicodeError):
                pass
    return state, summary, checksum


def _known_next(payload):
    page = _mapping(payload.get("page"))
    page_type = page.get("type")
    if isinstance(page_type, str) and page_type:
        return page_type in _NEXT_TYPES
    target = payload.get("continue_url")
    if not isinstance(target, str):
        return False
    parsed = _trusted_url(target)
    if parsed is None:
        try:
            callback = urlsplit(target)
            return (callback.scheme == "http" and callback.hostname in {"localhost", "127.0.0.1"}
                    and callback.port == 1455 and callback.path == "/auth/callback"
                    and callback.username is None and callback.password is None
                    and not any(ord(char) < 32 or ord(char) == 127 for char in target))
        except ValueError:
            return False
    return bool(parsed and parsed.path.rstrip("/") in {
        "/add-phone", "/phone-verification", "/email-verification", "/api/accounts/workspace/select",
        "/sign-in-with-chatgpt/codex/consent",
    })


class CodexDiagnosticSession(CodexAuthPageSession):
    """保留原连接与 Cookie；新增输出只含白名单存在性与内存比较结果。"""

    def __init__(self, session):
        super().__init__(session)
        cookie_state, _, _ = _cookies(session, "/")
        object.__setattr__(self, "_diagnostic", {
            "safe": safe_session_diagnostics({}), "collected": False, "cookies": cookie_state,
            "session_id": None, "checksum": None,
        })

    @property
    def mfa_verified(self):
        return self._diagnostic["safe"]["mfa_verified"]

    def snapshot(self) -> dict:
        return safe_session_diagnostics(self._diagnostic["safe"])

    def _record(self, response, path):
        status = _status(getattr(response, "status_code", None))
        try:
            payload = response.json()
            json_parsed = True
        except Exception:
            payload, json_parsed = {}, False
        payload = _mapping(payload)
        nested = _mapping(payload.get("client_auth_session")) or _mapping(payload.get("oai-client-auth-session"))
        top_id, nested_id = _nonempty(payload.get("session_id")), _nonempty(nested.get("session_id"))
        session_id = top_id or nested_id
        checksum = _normalized_checksum(payload.get("checksum"))
        cookie_state, cookie_summary, cookie_checksum = _cookies(self._base_session, path)
        previous = self._diagnostic
        result = {
            "observed": True, "response_received": response is not None, "http_status": status, "json_parsed": json_parsed,
            "known_key_flags": {key: _KEY_ALIASES.get(key, key) in payload for key in _KNOWN_KEYS},
            "top_session_id_present": top_id is not None, "nested_session_id_present": nested_id is not None,
            "auth_session_logging_id_present": _nonempty(nested.get("auth_session_logging_id")) is not None,
            "checksum_present": checksum is not None,
            "session_id_comparable": session_id is not None and previous["session_id"] is not None,
            "session_id_changed": session_id is not None and previous["session_id"] is not None and session_id != previous["session_id"],
            "checksum_comparable": checksum is not None and previous["checksum"] is not None,
            "checksum_changed": checksum is not None and previous["checksum"] is not None and checksum != previous["checksum"],
            "jar_comparable": cookie_state is not None and previous["cookies"] is not None,
            "jar_changed": cookie_state is not None and previous["cookies"] is not None and cookie_state != previous["cookies"],
            "session_id_nested_comparable": top_id is not None and nested_id is not None,
            "session_id_matches_nested": top_id is not None and nested_id is not None and top_id == nested_id,
            "minimized_checksum_present": cookie_checksum is not None,
            "dump_checksum_jar_comparable": checksum is not None and cookie_checksum is not None,
            "dump_checksum_matches_jar": checksum is not None and cookie_checksum is not None and checksum == cookie_checksum,
            **cookie_summary,
        }
        result["client_auth_session"] = {
            **{key: nested.get(key) is True for key in _CAS_BOOLS},
            **{key + "_present": key in nested for key in _CAS_KEYS},
            **{key: nested[key] if nested.get(key) in ("sms", "whatsapp") else "other" if key in nested else ""
               for key in _CAS_CHANNELS},
        }
        if session_id is not None:
            previous["session_id"] = session_id
        if checksum is not None:
            previous["checksum"] = checksum
        previous["cookies"] = cookie_state
        return _safe_record(result), payload

    def _request(self, method, url, headers, kwargs):
        parsed = _trusted_url(url)
        stage = None
        if parsed:
            if method == "POST":
                stage = _POST_STAGES.get(parsed.path)
            elif parsed.path in {"/oauth/authorize", "/authorize"}:
                stage = "bootstrap"
        try:
            response = (super().post if method == "POST" else super().get)(url, headers=headers, **kwargs)
        except Exception:
            if stage:
                record, _ = self._record(None, parsed.path)
                self._diagnostic["safe"]["stages"][stage] = record
            raise
        if stage:
            record, payload = self._record(response, parsed.path)
            self._diagnostic["safe"]["stages"][stage] = record
            if stage == "mfa_verify":
                self._diagnostic["safe"]["mfa_verified"] = 200 <= record["http_status"] < 300 and _known_next(payload)
        return response

    def get(self, url, headers=None, **kwargs):
        return self._request("GET", url, headers, kwargs)

    def post(self, url, headers=None, **kwargs):
        return self._request("POST", url, headers, kwargs)

    def collect_after_mfa(self) -> dict:
        """最多查询一次；无论成功、失败或不具备 MFA 证据都返回可终止诊断摘要。"""
        if self._diagnostic["collected"]:
            return self.snapshot()
        self._diagnostic["collected"] = True
        state = self._diagnostic["safe"]
        if not self.mfa_verified:
            state["dump_failure_kind"] = "mfa_unconfirmed"
            return self.snapshot()
        state["dump_attempted"] = True
        try:
            headers = {key: value for key, value in self.get_auth_headers(referer=_ORIGIN + "/add-phone").items()
                       if key.lower() not in {"content-type", "authorization", "proxy-authorization"}
                       and not key.lower().startswith("openai-sentinel-")}
            headers["x-access-flow-invocation-id"] = str(uuid.uuid4())
            headers["x-openai-document-navigation-id"] = self.document_navigation_id
            response = self._base_session.get(_DUMP_URL, headers=headers, allow_redirects=False)
            record, payload = self._record(response, "/api/accounts/client_auth_session_dump")
            state.update(dump=record, dump_response_received=True, dump_http_status=record["http_status"])
            if not 200 <= record["http_status"] < 300:
                state["dump_failure_kind"] = "http_error"
            elif not record["json_parsed"]:
                state["dump_failure_kind"] = "invalid_json"
            elif (not isinstance(payload.get("client_auth_session"), Mapping)
                  or not isinstance(payload.get("checksum"), str) or "session_id" not in payload
                  or payload["session_id"] is not None and not isinstance(payload["session_id"], str)):
                state["dump_failure_kind"] = "unknown_schema"
        except Exception:
            state["dump_failure_kind"] = "transport_error"
        return self.snapshot()
