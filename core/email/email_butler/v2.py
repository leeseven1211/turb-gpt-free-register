"""Email Butler v2 公开租约 API；调用方持久保存原幂等键与租约身份。"""
from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import quote, urlsplit, urlunsplit

import requests

from core.email.mailbox_wait import bounded_timeout

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
_SERVICE = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")
_ADDRESS = re.compile(r"^[^\s<>@,;]+@[^\s<>@,;]+$")
_LEASE_STATES = {"active", "released", "expired", "revoked"}
_RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504, 520, 522, 523, 524}


class ButlerV2Error(RuntimeError):
    """保留稳定分类和重试属性，不携带上游正文、验证码或凭据。"""

    def __init__(self, error_code: str, message: str = "Email Butler v2 请求未完成", *,
                 status_code: int | None = None, retryable: bool = False,
                 request_unknown: bool = False, request_id: str = ""):
        super().__init__(f"{error_code}: {message}")
        self.error_code = self.code = error_code
        self.status_code = status_code
        self.retryable = retryable
        self.request_unknown = request_unknown
        self.request_id = request_id
        self.definite_rejection = (status_code is not None and 400 <= status_code < 500
                                   and status_code not in {408, 425, 429})


def normalize_base(base: str) -> str:
    """将已知旧入口规范为 v2 根地址；禁止通过重定向发送凭据。"""
    value = str(base or "").strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                 and not parsed.username and not parsed.password
                 and not parsed.query and not parsed.fragment
                 and not any(char.isspace() or char == "\\" for char in value))
        parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ButlerV2Error("butler_configuration_invalid", "请配置有效的 Email Butler /v2 根地址")
    path = parsed.path.rstrip("/")
    if any(part in {".", ".."} for part in path.split("/")):
        raise ButlerV2Error("butler_configuration_invalid", "Email Butler 地址不能包含相对路径")
    if parsed.hostname.lower() == "codex-auth.leeseven.com" and path in {
        "/email-butler", "/email-butler/v1", "/email-butler/v2",
    }:
        return "https://email-butler.leeseven.com/v2"
    if path.endswith("/v1"):
        path = path[:-3] + "/v2"
    elif not path.endswith("/v2"):
        path += "/v2"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _mutation(method: str, path: str) -> bool:
    return method not in {"GET", "HEAD", "OPTIONS"} and not path.endswith(
        ("/code", "/code-batch", "/query-batch"))


def _response_error(code: str, *, mutation: bool = False, request_id: str = ""):
    return ButlerV2Error(code, "Email Butler v2 回执不符合接口合同，保留原请求供恢复",
                         retryable=True, request_unknown=mutation, request_id=request_id)


def request(method: str, path: str, *, api_base: str, api_key: str,
            params: dict | None = None, json: dict | None = None,
            idempotency_key: str | None = None, timeout: int | float | None = None) -> dict:
    """执行一次请求并验证 envelope；网络重试由持有原意图的调用方决定。"""
    method = str(method).upper()
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
            or any(char in path for char in "?#\\") or ".." in path.split("/")):
        raise ButlerV2Error("butler_request_invalid", "Email Butler 请求路径无效")
    key = str(api_key or "").strip()
    if not key or "\r" in key or "\n" in key:
        raise ButlerV2Error("butler_credentials_missing", "请配置有效的 Email Butler API Key")
    headers = {"Authorization": "Bearer " + key, "Accept": "application/json"}
    if json is not None:
        headers["Content-Type"] = "application/json"
    if idempotency_key is not None:
        if (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 200
                or not idempotency_key.strip() or any(ord(char) < 32 or ord(char) > 126 for char in idempotency_key)):
            raise ButlerV2Error("idempotency_key_invalid", "幂等键须为 1—200 个可打印 ASCII 字符")
        headers["Idempotency-Key"] = idempotency_key
    writes = _mutation(method, path)
    try:
        response = requests.request(method, normalize_base(api_base) + path, params=params,
                                    json=json, headers=headers,
                                    timeout=bounded_timeout(30 if timeout is None else timeout),
                                    allow_redirects=False)
    except requests.RequestException as exc:
        code = ("butler_transport_timeout" if isinstance(exc, requests.Timeout)
                else "butler_transport_connection" if isinstance(exc, requests.ConnectionError)
                else "butler_transport_failed")
        raise ButlerV2Error(code, "Email Butler 网络请求未确认，请沿用原请求重试",
                            retryable=True, request_unknown=writes) from None
    status = response.status_code
    if 300 <= status < 400:
        raise ButlerV2Error("butler_endpoint_redirect", "Email Butler 接口发生跳转，请核对 /v2 根地址",
                            status_code=status, request_unknown=writes)
    try:
        payload = response.json()
    except ValueError:
        raise ButlerV2Error("butler_response_not_json", "Email Butler 未返回 JSON 回执",
                            status_code=status, retryable=status in _RETRYABLE_HTTP or status < 400,
                            request_unknown=writes and (status < 400 or status >= 500 or status == 408)) from None
    if not isinstance(payload, dict):
        raise _response_error("butler_response_invalid",
                              mutation=writes and (status < 400 or status >= 500 or status == 408))
    request_id = payload.get("request_id")
    request_id = request_id if isinstance(request_id, str) and _IDENTIFIER.fullmatch(request_id) else ""
    if status >= 400 or "error" in payload:
        error = payload.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        code = code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,100}", code) else f"butler_http_{status}"
        retryable = error.get("retryable") if isinstance(error, dict) else None
        retryable = retryable if isinstance(retryable, bool) else status in _RETRYABLE_HTTP
        raise ButlerV2Error(code, "Email Butler 拒绝请求，请根据错误分类处理原意图",
                            status_code=status, retryable=retryable,
                            request_unknown=writes and (status >= 500 or status == 408), request_id=request_id)
    if not 200 <= status < 300 or "data" not in payload or not request_id:
        raise _response_error("butler_response_invalid", mutation=writes, request_id=request_id)
    return payload


def _data(payload: dict, *, mutation: bool = False) -> dict:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise _response_error("butler_response_invalid", mutation=mutation,
                              request_id=payload.get("request_id", ""))
    return data


def _timestamp(value, *, nullable: bool = False) -> bool:
    if value is None:
        return nullable
    try:
        return isinstance(value, str) and datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _lease(data: dict, *, lease_id: str | None = None, mutation: bool = False) -> dict:
    if (not isinstance(data.get("id"), str) or not _IDENTIFIER.fullmatch(data["id"])
            or not isinstance(data.get("email"), str) or not _ADDRESS.fullmatch(data["email"])
            or not isinstance(data.get("service"), str) or not _SERVICE.fullmatch(data["service"])
            or not isinstance(data.get("provider"), str) or not data["provider"]
            or data.get("status") not in _LEASE_STATES
            or not _timestamp(data.get("created_at")) or "expires_at" not in data
            or not _timestamp(data["expires_at"], nullable=True)):
        raise _response_error("butler_lease_response_invalid", mutation=mutation)
    if lease_id is not None and data["id"] != lease_id:
        raise _response_error("butler_lease_identity_mismatch", mutation=mutation)
    return data


def _lease_path(lease_id: str) -> str:
    if not isinstance(lease_id, str) or not _IDENTIFIER.fullmatch(lease_id):
        raise ButlerV2Error("butler_lease_id_invalid", "缺少有效的原租约 ID")
    return "/leases/" + quote(lease_id, safe="")


def me(*, api_base: str, api_key: str, timeout: int | float | None = None) -> dict:
    data = _data(request("GET", "/me", api_base=api_base, api_key=api_key, timeout=timeout))
    services = data.get("allowed_services")
    if (not isinstance(data.get("client_id"), str) or not data["client_id"]
            or not isinstance(data.get("permissions"), list)
            or any(not isinstance(value, str) for value in data["permissions"])
            or not (services == "*" or isinstance(services, list) and all(isinstance(value, str) for value in services))
            or not isinstance(data.get("limits"), dict)):
        raise _response_error("butler_client_response_invalid")
    return data


def list_leases(*, api_base: str, api_key: str, email: str | None = None,
                service: str = "openai", external_ref: str | None = None,
                status: str = "active", timeout: int | float | None = None) -> list[dict]:
    params = {"service": service, "status": status, "limit": 100}
    if email is not None:
        params["email"] = str(email).strip().lower()
    if external_ref is not None:
        params["external_ref"] = external_ref
    rows, cursors, identities = [], set(), set()
    while True:
        result = request("GET", "/leases", api_base=api_base, api_key=api_key, params=dict(params), timeout=timeout)
        data, page = result.get("data"), result.get("page")
        if (not isinstance(data, list) or not isinstance(page, dict)
                or type(page.get("has_more")) is not bool
                or type(page.get("limit")) is not int or not 1 <= page["limit"] <= 100
                or "next_cursor" not in page or len(data) > page["limit"]):
            raise _response_error("butler_pagination_invalid")
        for value in data:
            if not isinstance(value, dict):
                raise _response_error("butler_lease_response_invalid")
            value = _lease(value)
            if (value["id"] in identities or value["service"] != service
                    or email is not None and value["email"].strip().lower() != params["email"]
                    or external_ref is not None and value.get("external_ref") != external_ref
                    or status != "all" and value["status"] != status):
                raise _response_error("butler_lease_identity_mismatch")
            identities.add(value["id"])
            rows.append(value)
        if not page["has_more"]:
            return rows
        cursor = page.get("next_cursor")
        if not data or not isinstance(cursor, str) or not cursor or cursor in cursors:
            raise _response_error("butler_pagination_invalid")
        cursors.add(cursor)
        params["cursor"] = cursor


def get_lease(lease_id: str, *, api_base: str, api_key: str, timeout: int | float | None = None) -> dict:
    return _lease(_data(request("GET", _lease_path(lease_id), api_base=api_base, api_key=api_key,
                                timeout=timeout)), lease_id=lease_id)


def create_lease(*, api_base: str, api_key: str, external_ref: str, idempotency_key: str,
                 service: str = "openai", provider: str = "icloud_hme", ttl_seconds: int | None = None,
                 timeout: int | float | None = None) -> dict:
    if not idempotency_key:
        raise ButlerV2Error("idempotency_key_required", "租用须提供已保存的原幂等键")
    body = {"service": service, "provider": provider, "external_ref": external_ref, "ttl_seconds": ttl_seconds}
    data = _lease(_data(request("POST", "/leases", api_base=api_base, api_key=api_key, json=body,
                                idempotency_key=idempotency_key, timeout=timeout), mutation=True), mutation=True)
    if (data["service"] != service or provider != "auto" and data["provider"] != provider
            or data.get("external_ref") != external_ref):
        raise _response_error("butler_lease_identity_mismatch", mutation=True)
    return data


def code(lease_id: str, *, api_base: str, api_key: str, since: str | None = None,
         after_code_id: str | None = None, wait_seconds: int = 20, timeout: int | float | None = None) -> dict:
    if type(wait_seconds) is not int or not 0 <= wait_seconds <= 20:
        raise ButlerV2Error("butler_wait_invalid", "单次取码等待须为 0—20 秒")
    if since is not None and not _timestamp(since):
        raise ButlerV2Error("butler_since_invalid", "取码起始时间须包含明确时区")
    body = {"wait_seconds": wait_seconds}
    if since is not None:
        body["since"] = since
    if after_code_id is not None:
        body["after_code_id"] = after_code_id
    data = _data(request("POST", _lease_path(lease_id) + "/code", api_base=api_base, api_key=api_key,
                          json=body, timeout=wait_seconds + 10 if timeout is None else timeout))
    if (data.get("lease_id") != lease_id or not isinstance(data.get("service"), str)
            or not _SERVICE.fullmatch(data["service"]) or data.get("status") not in {"matched", "pending", "ambiguous"}
            or not {"verification_code", "code_id", "received_at"}.issubset(data)):
        raise _response_error("butler_code_response_invalid")
    if data["status"] == "matched":
        if (not isinstance(data["verification_code"], str) or not data["verification_code"]
                or not isinstance(data["code_id"], str) or not data["code_id"] or not _timestamp(data["received_at"])):
            raise _response_error("butler_code_response_invalid")
    elif any(data[field] is not None for field in ("verification_code", "code_id", "received_at")):
        raise _response_error("butler_code_response_invalid")
    return data


def release(lease_id: str, *, api_base: str, api_key: str, reason: str = "",
            timeout: int | float | None = None) -> dict:
    data = _lease(_data(request("POST", _lease_path(lease_id) + "/release", api_base=api_base,
                                api_key=api_key, json={"reason": reason}, timeout=timeout), mutation=True),
                  lease_id=lease_id, mutation=True)
    if (data["status"] == "active" or type(data.get("service_tag_removed")) is not bool
            or type(data.get("already_inactive")) is not bool):
        raise _response_error("butler_release_response_invalid", mutation=True)
    return data


def renew(lease_id: str, ttl_seconds: int | None, idempotency_key: str, *, api_base: str,
          api_key: str, timeout: int | float | None = None) -> dict:
    if not idempotency_key:
        raise ButlerV2Error("idempotency_key_required", "续租须提供已保存的原幂等键")
    return _lease(_data(request("POST", _lease_path(lease_id) + "/renew", api_base=api_base, api_key=api_key,
                                json={"ttl_seconds": ttl_seconds}, idempotency_key=idempotency_key,
                                timeout=timeout), mutation=True), lease_id=lease_id, mutation=True)


def availability(provider: str = "icloud_hme", service: str = "openai", *, api_base: str,
                 api_key: str, timeout: int | float | None = None) -> dict:
    data = _data(request("GET", "/availability", api_base=api_base, api_key=api_key,
                          params={"service": service, "provider": provider}, timeout=timeout))
    if (data.get("service") != service or data.get("provider") != provider
            or any(type(data.get(field)) is not int or data[field] < 0
                   for field in ("resource_total", "available", "client_active_leases"))
            or data["available"] > data["resource_total"] or not isinstance(data.get("availability_buckets"), dict)
            or not _timestamp(data.get("as_of"))):
        raise _response_error("butler_availability_response_invalid")
    return data
