# -*- coding: utf-8 -*-
"""Remail 开放 API 邮箱客户端。

Remail 的开放 API 与本项目已有的“生成随机邮箱”类服务不同：

1. 先用 API Key 按项目下一个 ``code`` 或 ``purchase`` 订单；
2. 订单返回交付邮箱和只属于该订单的 service token；
3. 取码时使用 ``/v1/pickup``，不再携带 API Key，只携带邮箱和 service token。

因此 service token 必须和邮箱一起保存在当前进程上下文中，不能只根据邮箱地址
重新拼接取件请求。
"""
from __future__ import annotations

from core.mailbox_wait import bounded_sleep, bounded_timeout
import json
import logging
import math
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit, urlunsplit

import requests

from config import email as _email_cfg
from core.otp_utils import extract_otp

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://remail.aishop6.com"
REQUEST_TIMEOUT = 20
_CODE_RE = re.compile(r"\b(\d{6})\b")
_FINAL_ORDER_STATUSES = {"failed", "refunded", "closed"}


class RemailError(RuntimeError):
    """Remail API 请求、下单或取码失败。

    错误文本面向操作者，不能承载响应体、URL 或认证资料；结构化字段供
    任务中心和订单协调器保存安全原因。
    """

    error_code = "remail_error"
    request_unknown = False

    def __init__(self, message: str, *, operation_phase: str = "request",
                 http_status: int | None = None, cause_code: str | None = None,
                 unknown_scope: str | None = None, allowed_error: str | None = None,
                 missing_fields: tuple[str, ...] | list[str] | None = None,
                 elapsed_ms: int | None = None, order_known: bool = False):
        super().__init__(str(message or "Remail 操作失败"))
        self.operation_phase = str(operation_phase or "request")
        self.http_status = int(http_status) if http_status is not None else None
        self.cause_code = str(cause_code or self.error_code)
        self.unknown_scope = str(unknown_scope or ("mailbox_order" if self.request_unknown else "none"))
        self.allowed_error = str(allowed_error or "") or None
        self.missing_fields = tuple(str(x) for x in (missing_fields or ()) if str(x))
        self.elapsed_ms = int(elapsed_ms) if elapsed_ms is not None else None
        self.order_known = bool(order_known)

    def safe_details(self) -> dict:
        """返回可持久化的白名单详情，绝不包含原始响应或凭据。"""
        return {
            "unknown_scope": self.unknown_scope,
            "operation_phase": self.operation_phase,
            "cause_code": self.cause_code,
            "http_status": self.http_status,
            "allowed_error": self.allowed_error,
            "missing_fields": list(self.missing_fields),
            "elapsed_ms": self.elapsed_ms,
            "order_known": self.order_known,
        }


class RemailOrderUncertain(RemailError):
    """下单可能已生效；调用方必须保留核对围栏，不能直接重试付费请求。"""

    request_unknown = True
    error_code = "remail_order_request_unknown"

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("operation_phase", "post")
        kwargs.setdefault("unknown_scope", "mailbox_order")
        kwargs.setdefault("cause_code", self.error_code)
        super().__init__(message, **kwargs)


class RemailOrderRejected(RemailError):
    """供应商明确拒绝且没有跨越付费结果未知边界。"""

    error_code = "remail_order_rejected"


class RemailOrderReadBlocked(RemailError):
    """已知订单的 GET 核验被权限或网络阻断，不能覆盖原订单事实。"""

    error_code = "remail_order_read_blocked"


# 兼容调用方可能使用的命名。
RemailClientError = RemailError


def safe_error_details(exc: BaseException) -> dict:
    """把任意 Remail 异常转换为可持久化的安全白名单。"""
    if isinstance(exc, RemailError):
        return exc.safe_details()
    return {
        "unknown_scope": "none", "operation_phase": "local", "cause_code": type(exc).__name__,
        "http_status": None, "allowed_error": None, "missing_fields": [],
        "elapsed_ms": None, "order_known": False,
    }


@dataclass
class RemailAccount:
    """一次 Remail 订单的取件上下文。"""

    email: str = field(repr=False)
    service_token: str = field(repr=False)
    order_no: str = field(repr=False)
    project_id: int
    email_suffix: str
    acquisition_id: str = field(default="", repr=False)


_CONTEXT_CACHE: dict[str, RemailAccount] = {}
_CONTEXT_LOCK = threading.RLock()


def _cache_key(email: str) -> str:
    return str(email or "").strip().lower()


def _base_url(value: str | None = None) -> str:
    """返回 API 根地址，也兼容用户误填文档地址 ``.../docs``。"""
    raw = str(
        value if value is not None else getattr(_email_cfg, "REMAIL_API_BASE", DEFAULT_API_BASE) or ""
    ).strip()
    if not raw:
        raise RemailError("Remail API 地址未配置，请填写 REMAIL_API_BASE")
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        if "://" in raw:
            raise RemailError("Remail API 地址仅支持 HTTP 或 HTTPS")
        raw = "https://" + raw

    try:
        parsed = urlsplit(raw.rstrip("/"))
        parsed.port
    except ValueError:
        raise RemailError("Remail API 地址无效") from None
    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.hostname
        or any(ch.isspace() for ch in raw)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RemailError("Remail API 地址无效，请填写 https://remail.aishop6.com（不要填写接口路径）")

    path = parsed.path.rstrip("/")
    # 文档链接可直接粘贴到配置页；API 实际位于同一域名根路径。
    if path.lower() == "/docs":
        path = ""
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def _request_timeout() -> int:
    try:
        value = int(getattr(_email_cfg, "REMAIL_REQUEST_TIMEOUT", REQUEST_TIMEOUT) or REQUEST_TIMEOUT)
    except (TypeError, ValueError):
        value = REQUEST_TIMEOUT
    return max(1, min(120, value))


def _api_key() -> str:
    value = str(getattr(_email_cfg, "REMAIL_API_KEY", "") or "").strip()
    if not value:
        raise RemailError("Remail API Key 未配置，请在配置 → 邮箱 / OTP 填写 REMAIL_API_KEY")
    return value


def _auth_headers() -> dict[str, str]:
    return {"Accept": "application/json", "Authorization": f"Bearer {_api_key()}"}


def _inventory_unavailable(payload) -> bool:
    """只识别供应商明确的库存错误码，不把响应原文带入提示。"""
    if not isinstance(payload, dict):
        return False
    candidates = [payload, *(payload.get(key) for key in ("error", "data", "order"))]
    return any(
        isinstance(item, dict) and any(
            item.get(key) == "insufficient_inventory"
            for key in ("code", "error", "failureCode", "failure_code")
        )
        for item in candidates
    )


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    headers: dict[str, str] | None = None,
    authenticated: bool = True,
    timeout: float | None = None,
):
    """直连 API；异常不携带 URL、服务凭证、响应正文或原始网络异常。"""
    request_headers = {"Accept": "application/json"}
    if authenticated:
        request_headers.update(_auth_headers())
    if headers:
        request_headers.update(headers)
    url = _base_url() + (path if str(path).startswith("/") else f"/{path}")
    request_timeout = _request_timeout() if timeout is None else min(_request_timeout(), max(0.001, timeout))
    started = time.monotonic()
    try:
        # 每次请求独立 Session，避免多线程共享 Cookie；忽略进程代理环境与 netrc。
        with requests.Session() as session:
            session.trust_env = False
            response = session.request(
                method.upper(), url, params=params, json=json_body,
                headers=request_headers, timeout=bounded_timeout(request_timeout), allow_redirects=False,
            )
    except requests.RequestException as exc:
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        category = "请求超时" if isinstance(exc, requests.Timeout) else "网络连接失败"
        if method.upper() == "POST":
            raise RemailOrderUncertain(
                f"Remail {category}；下单结果不明，请先核对订单，勿直接重复下单",
                cause_code="remail_post_timeout" if isinstance(exc, requests.Timeout) else "remail_post_network_error",
                elapsed_ms=elapsed_ms,
            ) from None
        raise RemailError(
            f"Remail {category}", operation_phase="get", cause_code="remail_get_timeout" if isinstance(exc, requests.Timeout) else "remail_get_network_error", elapsed_ms=elapsed_ms,
        ) from None

    if response.status_code >= 300:
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        if method.upper() == "POST" and (response.status_code >= 500 or response.status_code == 409):
            raise RemailOrderUncertain(
                f"Remail 下单结果不明 (HTTP {response.status_code})；请先核对订单，勿直接重复下单",
                http_status=response.status_code,
                cause_code="remail_post_http_unknown",
                allowed_error="server_error" if response.status_code >= 500 else "conflict",
                elapsed_ms=elapsed_ms,
            )
        if method.upper() == "GET" and response.status_code in (401, 403):
            raise RemailOrderReadBlocked(
                f"Remail 原订单核验被拒绝 (HTTP {response.status_code})",
                operation_phase="get", http_status=response.status_code,
                cause_code="remail_order_read_blocked", allowed_error="unauthorized" if response.status_code == 401 else "forbidden", elapsed_ms=elapsed_ms,
            )
        descriptions = {
            400: "请求参数无效", 401: "API Key 无效或已失效" if authenticated else "取件凭证无效或已失效",
            403: "无权执行该操作", 404: "资源不存在", 409: "订单冲突或资源不可用",
            422: "请求参数或订单状态无效", 429: "请求过于频繁",
        }
        reason = descriptions.get(response.status_code, "服务暂时不可用" if response.status_code >= 500 else "响应状态异常")
        allowed_error = {400: "invalid_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict", 422: "invalid_state", 429: "rate_limited"}.get(response.status_code)
        if response.status_code in (400, 422):
            try:
                inventory_unavailable = _inventory_unavailable(response.json())
            except ValueError:
                inventory_unavailable = False
            if inventory_unavailable:
                reason = "库存不足"
                allowed_error = "insufficient_inventory"
        error_type = RemailOrderRejected if method.upper() == "POST" else RemailError
        raise error_type(
            f"Remail {reason} (HTTP {response.status_code})",
            operation_phase="post" if method.upper() == "POST" else "get",
            http_status=response.status_code,
            cause_code="remail_post_rejected" if method.upper() == "POST" else "remail_get_error",
            allowed_error=allowed_error,
            elapsed_ms=elapsed_ms,
        ) from None
    try:
        return response.json()
    except ValueError:
        if method.upper() == "POST":
            raise RemailOrderUncertain(
                "Remail 下单响应不是有效 JSON，结果不明；请先核对订单，勿重复下单",
                cause_code="remail_post_invalid_json",
                elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
            ) from None
        raise RemailError("Remail 响应不是有效 JSON") from None


def _first_value(data: dict, *keys: str):
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return None


def _unwrap_order(payload) -> dict:
    """读取 OpenAPI 定义的 Order，并兼容少数网关包裹 data/order 的响应。"""
    if not isinstance(payload, dict):
        raise RemailError("Remail 下单响应不是对象", cause_code="remail_response_shape", missing_fields=("order",))
    if any(
        k in payload
        for k in ("orderNo", "order_no", "deliveryEmail", "delivery_email", "serviceToken", "service_token")
    ):
        return payload
    for key in ("data", "order"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    raise RemailError("Remail 下单响应缺少订单数据", cause_code="remail_response_missing_order", missing_fields=("order",))


def _project_id() -> int:
    raw = getattr(_email_cfg, "REMAIL_PROJECT_ID", 2)
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        raise RemailError(
            "Remail 项目 ID 未配置，请先通过 Remail API 查询项目后填写 REMAIL_PROJECT_ID"
        )
    return value


def _email_suffix() -> str:
    suffix = str(getattr(_email_cfg, "REMAIL_EMAIL_SUFFIX", "outlook.com") or "").strip().lstrip("@")
    if not suffix or "@" in suffix or any(ch.isspace() for ch in suffix):
        raise RemailError("Remail 邮箱后缀无效，请填写 outlook.com 等域名（不要填写完整邮箱）")
    return suffix


def _supply_policy() -> str:
    value = str(getattr(_email_cfg, "REMAIL_SUPPLY_POLICY", "public_only") or "public_only").strip().lower()
    if value not in {"private_first", "public_only"}:
        raise RemailError("Remail 库存策略无效，只支持 private_first 或 public_only")
    return value


def _service_mode() -> str:
    value = str(getattr(_email_cfg, "REMAIL_SERVICE_MODE", "purchase") or "purchase").strip().lower()
    if value not in {"code", "purchase"}:
        raise RemailError("Remail 服务模式无效，只支持 code 或 purchase")
    return value


def validate_configuration() -> None:
    """仅检查当前配置，不发请求、不下单。"""
    _base_url()
    _api_key()
    _project_id()
    _email_suffix()
    _service_mode()
    _supply_policy()


def _order_wait_seconds() -> int:
    try:
        value = int(getattr(_email_cfg, "REMAIL_ORDER_WAIT_SECONDS", 30))
    except (TypeError, ValueError):
        value = 30
    return max(0, min(180, value))


def _order_credentials(order: dict) -> tuple[str, str, str] | None:
    email = str(_first_value(order, "deliveryEmail", "delivery_email") or "").strip()
    token = str(_first_value(order, "serviceToken", "service_token") or "").strip()
    order_no = str(_first_value(order, "orderNo", "order_no") or "").strip()
    if email and "@" in email and token:
        return email, token, order_no
    return None


def _cache_context(account: RemailAccount) -> RemailAccount:
    """缓存订单取件上下文并返回对象。"""
    with _CONTEXT_LOCK:
        _CONTEXT_CACHE[_cache_key(account.email)] = account
    return account


def _context_from_order(order: dict, target_email: str) -> RemailAccount | None:
    """从订单对象创建上下文，并要求交付邮箱完全匹配。"""
    if _order_status_error(order):
        return None
    credentials = _order_credentials(order)
    if not credentials:
        return None
    email, service_token, order_no = credentials
    if email.casefold() != str(target_email or "").strip().casefold():
        return None

    raw_project_id = _first_value(order, "projectId", "project_id")
    try:
        project_id = int(str(raw_project_id).strip()) if raw_project_id is not None else _project_id()
    except (TypeError, ValueError, RemailError):
        # 订单详情理论上一定有 projectId；历史接口缺失时不影响取件，保留
        # 当前配置值作为展示/兼容字段。
        try:
            project_id = _project_id()
        except RemailError:
            project_id = 0

    suffix = str(
        _first_value(order, "emailSuffix", "email_suffix")
        or email.rsplit("@", 1)[-1]
        or getattr(_email_cfg, "REMAIL_EMAIL_SUFFIX", "outlook.com")
    ).strip().lstrip("@")
    return RemailAccount(
        email=email,
        service_token=service_token,
        order_no=order_no,
        project_id=project_id,
        email_suffix=suffix,
    )


def _order_list_items(payload) -> list[dict]:
    """读取订单列表响应，兼容 data/items 的网关包裹。"""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _saved_context_metadata(email: str) -> dict:
    """读取账号保存的 Remail 订单凭证，不把解析失败传播到查活主流程。"""
    try:
        from core import db

        row = db.get_account_by_email(email)
    except Exception:
        logger.debug("[Remail] 读取已注册账号订单信息失败")
        return {}
    if not row:
        return {}

    raw = row.get("extra_json")
    if isinstance(raw, str) and raw.strip():
        try:
            extra = json.loads(raw)
        except (TypeError, ValueError):
            extra = {}
    elif isinstance(raw, dict):
        extra = raw
    else:
        extra = {}
    if not isinstance(extra, dict):
        return {}

    # 新字段使用 email_service；同时兼容早期开发版本可能使用 remail。
    for key in ("email_service", "remail"):
        value = extra.get(key)
        if isinstance(value, dict):
            source = str(value.get("source") or "remail").strip().lower()
            if source == "remail":
                return dict(value)
    return {}


def get_account_context_metadata(email: str) -> dict | None:
    """返回可持久化的 Remail 订单上下文，用于注册账号落库。

    service token 是取件凭证，不写日志；这里仅由账号持久化层调用，普通列表
    API 不会直接返回 ``extra_json``。
    """
    account = get_account_context(email)
    if account is None:
        return None
    return {
        "source": "remail",
        "email": account.email,
        "service_token": account.service_token,
        "order_no": account.order_no,
        "project_id": account.project_id,
        "email_suffix": account.email_suffix,
    }


def restore_account_context(email: str, *, compatibility: bool = False) -> RemailAccount | None:
    """恢复已注册账号的 Remail 取件上下文。

    进程重启后 ``_CONTEXT_CACHE`` 会丢失。优先使用账号保存的 service token，
    其次按保存的订单号查详情。旧的“按邮箱搜索最新订单”仅由显式兼容入口
    开启；正常注册/换绑恢复没有原订单号时必须停在核验围栏，不能猜测同邮箱
    的其他订单。
    """
    target = str(email or "").strip()
    if not target:
        return None
    cached = get_account_context(target)
    if cached is not None:
        return cached

    metadata = _saved_context_metadata(target)
    saved_email = str(metadata.get("email") or "").strip()
    if saved_email and saved_email.casefold() != target.casefold():
        metadata = {}

    saved_token = str(metadata.get("service_token") or metadata.get("serviceToken") or "").strip()
    if saved_token:
        order = {
            "deliveryEmail": saved_email or target,
            "serviceToken": saved_token,
            "orderNo": str(metadata.get("order_no") or metadata.get("orderNo") or "").strip(),
            "projectId": metadata.get("project_id") or metadata.get("projectId"),
            "emailSuffix": metadata.get("email_suffix") or metadata.get("emailSuffix"),
        }
        account = _context_from_order(order, target)
        if account is not None:
            logger.info("[Remail] 已从账号保存信息恢复取件上下文")
            return _cache_context(account)

    saved_order_no = str(metadata.get("order_no") or metadata.get("orderNo") or "").strip()
    if saved_order_no:
        try:
            detail = _unwrap_order(
                _request("GET", f"/v1/open/orders/{quote(saved_order_no, safe='')}")
            )
        except RemailError:
            logger.debug("[Remail] 按已保存订单号恢复失败")
        else:
            account = _context_from_order(detail, target)
            if account is not None:
                logger.info("[Remail] 已按订单号恢复取件上下文")
                return _cache_context(account)

    if not compatibility:
        return None

    # 兼容旧账号数据：搜索是服务端模糊过滤，客户端仍检查完整邮箱；最多读取五页，避免无限翻页。
    candidates = []
    cursor = None
    seen_cursors = set()
    for _ in range(5):
        params = {"search": target, "limit": 100}
        if cursor is not None:
            params["afterId"] = cursor
        try:
            payload = _request("GET", "/v1/open/orders", params=params)
        except RemailError:
            logger.debug("[Remail] 按邮箱搜索订单失败")
            break
        candidates.extend(
            item for item in _order_list_items(payload)
            if str(_first_value(item, "deliveryEmail", "delivery_email") or "").strip().casefold() == target.casefold()
            and not _order_status_error(item)
        )
        page = payload.get("data", payload) if isinstance(payload, dict) else {}
        if not isinstance(page, dict) or not page.get("hasNext"):
            break
        cursor = page.get("nextAfterId")
        if not isinstance(cursor, int) or cursor <= 0 or cursor in seen_cursors:
            break
        seen_cursors.add(cursor)

    candidates.sort(
        key=lambda item: _parse_timestamp(_first_value(item, "updatedAt", "updated_at", "createdAt", "created_at")) or float("-inf"),
        reverse=True,
    )
    for order in candidates[:5]:
        account = _context_from_order(order, target)
        if account is None:
            order_no = str(_first_value(order, "orderNo", "order_no") or "").strip()
            if not order_no:
                continue
            try:
                detail = _unwrap_order(_request("GET", f"/v1/open/orders/{quote(order_no, safe='')}"))
            except RemailError:
                continue
            account = _context_from_order(detail, target)
        if account is not None:
            logger.info("[Remail] 已按邮箱匹配订单恢复取件上下文")
            return _cache_context(account)
    return None


def _order_status_error(order: dict) -> str | None:
    status = str(order.get("status") or "").strip().lower()
    if status == "failed" and _inventory_unavailable(order):
        return "Remail 库存不足"
    if status in _FINAL_ORDER_STATUSES:
        return f"Remail 订单不可用: status={status}"
    return None


def _wait_for_order_credentials(order: dict) -> tuple[str, str, str]:
    error = _order_status_error(order)
    if error:
        raise RemailError(error)
    credentials = _order_credentials(order)
    if credentials:
        return credentials
    order_no = str(_first_value(order, "orderNo", "order_no") or "").strip()
    if not order_no:
        raise RemailOrderUncertain(
            "Remail 下单响应缺少 service token 或订单号；请先核对订单，勿重复下单",
            cause_code="remail_response_missing_credentials",
            missing_fields=("service_token", "order_no"),
        )

    deadline = time.monotonic() + _order_wait_seconds()
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            latest = _unwrap_order(_request("GET", f"/v1/open/orders/{quote(order_no, safe='')}", timeout=remaining))
        except RemailError:
            # 订单已创建，只重试查询；不能在取凭证超时时重新下单。
            pass
        else:
            error = _order_status_error(latest)
            if error:
                raise RemailError(error)
            credentials = _order_credentials(latest)
            if credentials:
                return credentials
        remaining = deadline - time.monotonic()
        if remaining > 0:
            bounded_sleep(min(1, remaining))
    raise RemailOrderUncertain("Remail 等待订单取件凭证超时；请先核对订单，勿重复下单")


def pick_account(*, owner_kind: str | None = None, owner_id: str | int | None = None,
                 acquisition_id: str | None = None, compatibility: bool = False) -> RemailAccount:
    """按配置创建订单。

    显式提供 owner 身份时走持久订单协调器。无身份的旧入口只有在调用方
    明确传入 ``compatibility=True`` 时才保留；业务注册/换绑路径不得使用它。
    """
    if owner_kind and owner_id is not None:
        from core.remail_order_coordinator import RemailOrderCoordinator
        return RemailOrderCoordinator().acquire(
            owner_kind=str(owner_kind), owner_id=str(owner_id), acquisition_id=acquisition_id,
        )
    if not compatibility:
        raise RemailError(
            "Remail 领取缺少稳定 owner/acquisition_id，已停止下单",
            operation_phase="prepare",
            cause_code="remail_missing_owner",
            missing_fields=("owner_kind", "owner_id", "acquisition_id"),
        )
    logger.warning("[Remail] 使用显式兼容入口；本次订单不会绑定可恢复任务意图")
    validate_configuration()
    project_id = _project_id()
    email_suffix = _email_suffix()
    service_mode = _service_mode()
    supply = _supply_policy()
    idempotency_key = f"turb-gpt-free-register-{uuid.uuid4()}"

    payload = _request(
        "POST",
        "/v1/open/orders",
        params={"serviceMode": service_mode, "supply": supply},
        json_body={"projectId": project_id, "emailSuffix": email_suffix},
        headers={"Idempotency-Key": idempotency_key},
    )
    try:
        order = _unwrap_order(payload)
    except RemailError:
        raise RemailOrderUncertain("Remail 下单响应缺少可查询的订单信息；请先核对订单，勿重复下单") from None
    email, service_token, order_no = _wait_for_order_credentials(order)
    account = RemailAccount(
        email=email,
        service_token=service_token,
        order_no=order_no,
        project_id=project_id,
        email_suffix=email_suffix,
    )
    _cache_context(account)
    logger.info("[Remail] 已创建邮箱订单，项目 ID=%s", project_id)
    return account


def get_email() -> str:
    """兼容其他临时邮箱客户端的旧入口。"""
    return pick_account().email


def get_account_context(email: str) -> RemailAccount | None:
    with _CONTEXT_LOCK:
        return _CONTEXT_CACHE.get(_cache_key(email))


def release_account(email: str, status: str = "available", note: str | None = None) -> None:
    """释放本地取件上下文；订单生命周期由 Remail 服务端管理。"""
    with _CONTEXT_LOCK:
        account = _CONTEXT_CACHE.pop(_cache_key(email), None)
    if account:
        logger.info("[Remail] 已释放本地取件上下文")


def _parse_timestamp(raw) -> float | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        return (value / 1000.0 if value > 10_000_000_000 else value) if math.isfinite(value) else None

    text = str(raw).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        value = float(text)
        return (value / 1000.0 if value > 10_000_000_000 else value) if math.isfinite(value) else None
    try:
        iso = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def _pickup_items(payload) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict):
        payload = data
    elif isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    items = payload.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _message_code(message: dict) -> str | None:
    direct = _first_value(message, "verificationCode", "verification_code", "code", "otp")
    if direct is not None:
        match = _CODE_RE.search(str(direct))
        if match:
            return match.group(1)

    preview = str(_first_value(message, "bodyPreview", "body_preview", "body", "text", "content") or "")
    return extract_otp(
        {
            "from": str(_first_value(message, "sender", "from", "fromEmail") or ""),
            "subject": str(message.get("subject") or ""),
            "text": preview,
            "content": preview,
        }
    )


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    """轮询 Remail pickup，返回领取时间之后最新的六位验证码。"""
    target = str(email or "").strip()
    if not target:
        raise RemailError("Remail 取码缺少邮箱地址")
    account = get_account_context(target) or restore_account_context(target)
    if account is None:
        raise RemailError(
            "Remail 找不到该邮箱的 service token，且无法从已保存订单恢复；"
            "请确认账号注册来源为 Remail、订单仍可取件，并已配置 Remail API Key"
        )

    try:
        wait_seconds = int(max_wait if max_wait is not None else getattr(_email_cfg, "OTP_MAX_WAIT", 90))
    except (TypeError, ValueError):
        wait_seconds = 90
    try:
        interval = int(poll_interval if poll_interval is not None else getattr(_email_cfg, "OTP_POLL_INTERVAL", 3))
    except (TypeError, ValueError):
        interval = 3
    try:
        settle = int(settle_seconds if settle_seconds is not None else getattr(_email_cfg, "OTP_SETTLE_SECONDS", 5))
    except (TypeError, ValueError):
        settle = 5
    interval = max(1, interval)
    settle = max(0, settle)
    deadline = time.monotonic() + max(0, wait_seconds)
    best_otp: str | None = None
    best_timestamp = float("-inf")
    settle_until: float | None = None
    last_error = "收件箱为空或尚未出现新的验证码"

    logger.info("[Remail] 开始轮询验证码，最长 %ss", max(0, wait_seconds))
    first_poll = True
    while first_poll or time.monotonic() < deadline:
        first_poll = False
        try:
            payload = _request(
                "GET",
                "/v1/pickup",
                params={"email": target, "token": account.service_token},
                authenticated=False,
                timeout=max(0.001, deadline - time.monotonic()),
            )
            items = _pickup_items(payload)
            messages = []
            for message in items:
                received_at = _first_value(
                    message, "receivedAt", "received_at", "timestamp", "createdAt", "created_at"
                )
                timestamp = _parse_timestamp(received_at)
                if after_ts is not None and (timestamp is None or timestamp < after_ts):
                    continue
                code = _message_code(message)
                if code:
                    messages.append((timestamp, code))

            messages.sort(
                key=lambda value: value[0] if value[0] is not None else float("-inf"),
                reverse=True,
            )
            # 只比较本轮最新一封，不能被遍历到的旧码或同时间另一封覆盖。
            for timestamp, code in messages[:1]:
                candidate_time = float("-inf") if timestamp is None else timestamp
                if (
                    best_otp is None
                    or candidate_time > best_timestamp
                ):
                    best_otp = code
                    best_timestamp = candidate_time
                    settle_until = time.monotonic() + settle
                    logger.info("[Remail] 锁定 OTP 候选，等待 %ss 确认", settle)

            if best_otp and settle_until is not None and time.monotonic() >= settle_until:
                return best_otp
        except RemailError as exc:
            last_error = str(exc)
        except (TypeError, ValueError):
            last_error = "邮件响应格式异常"

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        bounded_sleep(min(interval, remaining))

    if best_otp:
        return best_otp
    raise RemailError(f"等待 Remail 验证码超时；{last_error}")


def list_projects(*, search: str | None = None, product_type: str | None = "microsoft") -> list[dict]:
    """查询当前 API Key 可见项目，供配置/诊断使用。"""
    params = {"offset": 0, "limit": 100}
    if search:
        params["search"] = str(search).strip()
    if product_type:
        params["productType"] = str(product_type).strip()
    payload = _request("GET", "/v1/open/projects", params=params)
    if isinstance(payload, dict):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []
