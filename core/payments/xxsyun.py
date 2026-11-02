"""XXSYUN 官方 Bearer API；提交回执缺失时沿持久幂等意图恢复。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import re
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

API_BASE = "https://upi.xxsyun.xyz/api/v1"
_RETRYABLE = {"INSUFFICIENT_QUOTA", "EMPLOYER_SUBMISSION_COOLDOWN", "RATE_LIMITED"}
_MESSAGES = {
    "CONFIG_INVALID": "XXSYUN API 配置无效",
    "API_KEY_MISSING": "XXSYUN API Key 未配置",
    "REQUEST_INVALID": "XXSYUN 支付请求参数无效",
    "REQUEST_TIMEOUT": "XXSYUN 请求超时，将使用原幂等意图恢复",
    "TRANSPORT_ERROR": "XXSYUN 网络传输失败",
    "INVALID_RESPONSE": "XXSYUN 响应格式错误",
    "INCOMPLETE_RECEIPT": "XXSYUN 提交回执不完整，将使用原幂等意图恢复",
    "UPSTREAM_HTTP_ERROR": "XXSYUN HTTP 请求失败",
    "UPSTREAM_BUSINESS_ERROR": "XXSYUN 业务拒绝",
    "MATERIAL_MISSING": "未取得可提交的 UPI 支付材料",
    "MATERIAL_UNSUPPORTED": "支付材料不是官方支持的 UPI instructions HTTPS 链接",
    "UNAUTHENTICATED": "XXSYUN API Key 无效",
    "EMPLOYER_PENDING": "XXSYUN 平台账号尚未就绪",
    "PASSWORD_CHANGE_REQUIRED": "XXSYUN 平台要求先修改密码",
    "INSUFFICIENT_QUOTA": "XXSYUN 积分不足，等待额度恢复",
    "EMPLOYER_SUBMISSION_COOLDOWN": "XXSYUN 提交冷却中",
    "RATE_LIMITED": "XXSYUN 请求限流",
    "INVALID_AT": "支付账号 AT 无效",
    "LINK_INVALID": "UPI 支付链接无效",
    "LINK_EXPIRED": "UPI 支付链接已过期",
    "ACCOUNT_MISMATCH": "支付链接与账号不匹配",
    "ACCOUNT_MATCH_UNVERIFIED": "平台无法确认支付链接的账号归属",
    "ICLOUD_EMAIL_BLOCKED": "XXSYUN 对邮箱或提交出口有限制",
    "NON_ZERO_TRIAL": "试用金额非零，平台拒绝扫码",
    "BLOCKED_EXTERNAL": "上游校验被拦截或无法确认",
    "IDEMPOTENCY_CONFLICT": "持久支付请求与幂等键原请求不一致",
    "ORDER_CANCEL_RESTRICTED": "平台不允许取消此支付订单",
}


def _seconds(value) -> int:
    try:
        return max(0, min(86400 * 30, int(value)))
    except (TypeError, ValueError, OverflowError):
        return 0


def safe_message(value, *, secrets=()) -> str:
    """保留平台原因，过滤请求凭据、访问链接与邮箱。"""
    if not isinstance(value, str):
        return ""
    for secret in secrets:
        if isinstance(secret, str) and secret:
            value = value.replace(secret, "[已隐藏]")
    value = re.sub(r"(?i)Bearer\s+\S+|(?:https?://|upi://)\S+|eyJ[A-Za-z0-9_.-]+", "[已隐藏]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[邮箱已隐藏]", value)
    value = re.sub(r"(?i)\b(?:at|token|api[_-]?key|password)\s*[:=]\s*[^\s,;]+", "凭据=[已隐藏]", value)
    return " ".join(value.split())[:300]


class PaymentError(RuntimeError):
    """可直接展示的支付错误；不保留原始响应或异常。"""
    def __init__(self, code: str, *, retryable=False, submission_unknown=False, retry_after_seconds=0, message=""):
        self.code = code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", code) else "UPSTREAM_BUSINESS_ERROR"
        self.category = self.code if self.code in _MESSAGES else "UPSTREAM_BUSINESS_ERROR"
        self.retryable = bool(retryable)
        self.submission_unknown = bool(submission_unknown)
        self.retry_after_seconds = _seconds(retry_after_seconds)
        self.summary = {"error_category": self.category}
        text = _MESSAGES.get(self.code, f"XXSYUN 业务拒绝（{self.code}）")
        super().__init__(f"{text}：{message}" if message else text)


def validate_api_base(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise PaymentError("CONFIG_INVALID")
    value = value.strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        parsed.port
        valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                 and "?" not in value and "#" not in value and "\\" not in value
                 and not any(ord(ch) < 33 or ord(ch) == 127 for ch in value)
                 and not any(part in {".", ".."} for part in unquote(parsed.path).split("/")))
    except ValueError:
        valid = False
    if not valid:
        raise PaymentError("CONFIG_INVALID")
    return value


def _compatible_url(value) -> bool:
    if not isinstance(value, str) or len(value) > 16384 or any(ord(ch) < 33 or ord(ch) == 127 for ch in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and parsed.hostname == "payments.stripe.com"
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and parsed.path.startswith("/upi/instructions/") and bool(parsed.path.removeprefix("/upi/instructions/"))
                and not parsed.fragment)
    except ValueError:
        return False


def select_payment_url(artifact: dict, *, links=(), payment_links=()) -> str:
    artifact = artifact if isinstance(artifact, dict) else {}
    candidates = [artifact.get("payment_url"), artifact.get("payment_page_url"), *payment_links, *links]
    for value in candidates:
        if _compatible_url(value):
            return value
    raise PaymentError("MATERIAL_UNSUPPORTED" if any(candidates) or artifact else "MATERIAL_MISSING")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DirectTransport:
    """直连订单冻结地址，禁用环境代理与重定向，避免凭据转发。"""
    def __init__(self, api_base: str):
        self.api_base = validate_api_base(api_base)
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def request(self, method, path, *, json=None, headers=None, timeout=30):
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path or any(part in {".", ".."} for part in unquote(path).split("/")):
            raise PaymentError("REQUEST_INVALID")
        raw = None if json is None else __import__("json").dumps(json, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False).encode("utf-8")
        request = Request(self.api_base + path, data=raw, headers=headers or {}, method=method)
        try:
            response = self.opener.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            content = response.read()
            status, response_headers = response.code, dict(response.headers)
        try:
            payload = __import__("json").loads(content.decode("utf-8"))
        except (ValueError, UnicodeError):
            payload = None
        return SimpleNamespace(status_code=status, headers=response_headers, json=lambda: payload)


class XXSYUNClient:
    def __init__(self, api_base: str, api_key: str, timeout: float = 30, transport=None):
        self.api_base = validate_api_base(api_base)
        if not isinstance(api_key, str) or not api_key.strip() or any(ord(ch) < 32 or ord(ch) == 127 for ch in api_key):
            raise PaymentError("API_KEY_MISSING")
        self.api_key = api_key.strip()
        try:
            self.timeout = float(timeout)
            if not math.isfinite(self.timeout) or self.timeout <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise PaymentError("CONFIG_INVALID") from None
        self.transport = transport if transport is not None else DirectTransport(self.api_base)

    def _business_error(self, value, *, retry_after=0, secrets=()):
        value = value if isinstance(value, dict) else {}
        code = value.get("code") or "UPSTREAM_BUSINESS_ERROR"
        if not isinstance(code, str) or any(secret and secret in code for secret in (self.api_key, *secrets)):
            code = "UPSTREAM_BUSINESS_ERROR"
        error = PaymentError(code, retryable=code in _RETRYABLE,
                             retry_after_seconds=value.get("retry_after_seconds") or retry_after,
                             message=safe_message(value.get("message"), secrets=(self.api_key, *secrets)))
        amount = _number(value.get("amount_due_minor"))
        if amount is not None:
            error.summary["amount_due_minor"] = amount
        currency = value.get("currency")
        if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency):
            error.summary["currency"] = currency.upper()
        return error

    def _request(self, method, path, *, body=None, key=None):
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json", "Content-Type": "application/json", "Cache-Control": "no-store"}
        if key is not None:
            headers["Idempotency-Key"] = key
        error_code = None
        try:
            response = self.transport.request(method, path, json=deepcopy(body), headers=headers, timeout=self.timeout)
        except Exception as exc:
            reason = exc.reason if isinstance(exc, URLError) else exc
            error_code = "REQUEST_TIMEOUT" if isinstance(reason, TimeoutError) or "timeout" in type(reason).__name__.lower() else "TRANSPORT_ERROR"
        if error_code:
            raise PaymentError(error_code, retryable=True, submission_unknown=method == "POST")
        status = getattr(response, "status_code", 200)
        response_headers = getattr(response, "headers", {}) or {}
        retry_after = _seconds(response_headers.get("Retry-After", response_headers.get("retry-after")))
        if not retry_after and response_headers.get("Retry-After"):
            try:
                retry_after = _seconds((parsedate_to_datetime(response_headers["Retry-After"]) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
        try:
            data = response if isinstance(response, dict) else response.json()
        except Exception:
            data = None
        secrets = tuple(row.get("at", "") for row in (body or {}).get("items", []) if isinstance(row, dict))
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            raise self._business_error(data["error"], retry_after=retry_after, secrets=secrets)
        if type(status) is not int or not 200 <= status < 300:
            code = "RATE_LIMITED" if status == 429 else "UNAUTHENTICATED" if status == 401 else "UPSTREAM_HTTP_ERROR"
            raise PaymentError(code, retryable=code != "UNAUTHENTICATED", submission_unknown=method == "POST" and status not in (401, 403, 429), retry_after_seconds=retry_after)
        if not isinstance(data, dict) or data.get("ok") is not True:
            raise PaymentError("INVALID_RESPONSE", retryable=True, submission_unknown=method == "POST")
        return data

    def _order(self, value, *, expected_id=None, secrets=()):
        if not isinstance(value, dict) or type(value.get("id")) not in (str, int) or not str(value["id"]).strip():
            raise PaymentError("INCOMPLETE_RECEIPT", retryable=True, submission_unknown=expected_id is None)
        order_id = str(value["id"])
        if expected_id is not None and order_id != str(expected_id):
            raise PaymentError("INCOMPLETE_RECEIPT", retryable=True)
        remote = value.get("status")
        if not isinstance(remote, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", remote):
            raise PaymentError("INCOMPLETE_RECEIPT", retryable=True, submission_unknown=expected_id is None)
        normalized = remote.lower()
        state = "succeeded" if normalized == "completed" else "failed" if normalized in {"failed", "expired", "cancelled"} else "pending" if normalized in {"pending", "queued", "created", "processing", "assigned", "awaiting_worker", "claimed", "scanning", "verifying", "waiting", "in_progress"} else "unknown"
        code = value.get("failure_code")
        code = code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", code) else ""
        reason = safe_message(value.get("failure_reason"), secrets=(self.api_key, *secrets))
        summary = {"remote_status": remote, "failure_code": code, "failure_message": reason}
        cost = _number(value.get("cost_points"))
        if cost is not None:
            summary["cost_points"] = cost
        return {"order_id": order_id, "state": state, "remote_status": remote, "failure_code": code,
                "failure_message": reason, "can_cancel": value.get("can_cancel") if type(value.get("can_cancel")) is bool else None, "summary": summary}

    def submit(self, body: dict, idempotency_key: str) -> dict:
        if not isinstance(body, dict) or not isinstance(body.get("items"), list) or len(body["items"]) != 1:
            raise PaymentError("REQUEST_INVALID")
        row = body["items"][0]
        if (not isinstance(row, dict) or not isinstance(row.get("at"), str) or not row["at"].strip()
                or not _compatible_url(row.get("link")) or not isinstance(idempotency_key, str)
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", idempotency_key)):
            raise PaymentError("REQUEST_INVALID")
        data = self._request("POST", "/orders/batch", body=body, key=idempotency_key)
        if any(not isinstance(data.get(name, []), list) for name in ("created", "duplicated", "failed")):
            raise PaymentError("INCOMPLETE_RECEIPT", retryable=True, submission_unknown=True)
        rows = [*data.get("created", []), *data.get("duplicated", [])]
        failures = data.get("failed", [])
        if len(rows) + len(failures) != 1:
            raise PaymentError("INCOMPLETE_RECEIPT", retryable=True, submission_unknown=True)
        response_row = (rows or failures)[0]
        if not isinstance(response_row, dict) or ("index" in response_row and (type(response_row["index"]) is not int or response_row["index"] != 0)):
            raise PaymentError("INCOMPLETE_RECEIPT", retryable=True, submission_unknown=True)
        if failures:
            failure = failures[0]
            details = {**failure, "message": failure.get("error")}
            raise self._business_error(details, secrets=(row["at"],))
        return self._order(rows[0].get("order") if isinstance(rows[0], dict) else None, secrets=(row["at"],))

    def get_order(self, order_id: str) -> dict:
        if type(order_id) not in (str, int) or not str(order_id).strip() or len(str(order_id)) > 240:
            raise PaymentError("REQUEST_INVALID")
        return self._order(self._request("GET", "/orders/" + quote(str(order_id), safe="")).get("order"), expected_id=order_id)

    def query_balance(self) -> dict:
        summary = self._request("GET", "/tickets").get("summary")
        if not isinstance(summary, dict):
            raise PaymentError("INVALID_RESPONSE", retryable=True)
        return {name: _number(summary.get(name)) for name in ("available_points", "pending_points", "used_points", "cost_points")}


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
        if not math.isfinite(number) or number < 0:
            return None
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError, OverflowError):
        return None
