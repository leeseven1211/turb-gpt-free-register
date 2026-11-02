"""暗光一条虫原生 UPI 自动支付；只续查原任务，不创建独立扫码订单。"""
from __future__ import annotations

import copy
import json as json_module
import math
import time
import uuid
from collections.abc import Mapping
from datetime import timezone
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from core.extract_link.contracts import (
    ExtractRequest,
    ProviderError,
    ProviderHTTPError,
    ProviderJob,
    ProviderUnsupported,
    request,
    require_capability,
    response_dict,
    safe_links,
    safe_payment_artifact,
)
from core.storage.runtime_config import RuntimeConfigStoreError, decrypt_private_text, encrypt_private_text


_EXTRACTION = {
    "PENDING": "queued", "QUEUED": "queued", "SUBMITTING": "running", "RUNNING": "running",
    "SUCCEEDED": "succeeded", "FAILED": "failed", "REJECTED": "failed",
    "CANCELED": "failed", "CANCELLED": "failed", "UNKNOWN": "unknown",
}
_SCAN_PENDING = {"NONE", "READY", "AWAITING_FUNDS", "AWAITING_SLOT", "SUBMITTING", "awaiting_worker", "claimed", "verifying"}
_SCAN_FAILED = {"failed", "expired", "cancelled", "rejected"}
_SCAN_KNOWN = _SCAN_PENDING | _SCAN_FAILED | {"completed", "UNKNOWN"}
_RETRY_ACTIVE = {"QUEUED", "RUNNING", "SCANNING"}
_PLANS = {"chatgptplusplan", "chatgptgoplan", "chatgptprolite"}
_SUBMISSION_REJECTIONS = {400, 401, 402, 403, 404, 405, 413, 422}
_FAILURES = {
    "invalid_token": "访问令牌无效，平台未受理任务",
    "expired_token": "访问令牌已过期，平台未受理任务",
    "failure_cooldown": "账号处于失败冷却期，平台已跳过",
    "account_failure_cooldown": "账号处于失败冷却期，平台已跳过",
    "account_daily_limit": "账号今日提炼次数已达上限",
    "token_has_active_task": "账号已有未结束任务，请核对平台原任务",
    "duplicate_task": "平台已跳过重复任务",
    "insufficient_balance": "平台可用积分不足",
    "service_unavailable": "平台服务暂不可用",
    "service_maintenance": "平台正在维护",
    "plan_unavailable": "平台暂不提供所选套餐",
    "invalid_options": "平台未接受任务参数",
}


def _uuid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
    return str(parsed) if str(parsed) == value.lower() else None


def _api_base(value: object) -> str:
    if not isinstance(value, str) or any(ord(char) < 33 or ord(char) == 127 for char in value):
        raise ProviderError("暗光 API 地址无效")
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError:
        raise ProviderError("暗光 API 地址无效") from None
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderError("暗光 API 地址无效")
    return value.rstrip("/")


def _api_key(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 8192 or any(ord(char) < 33 or ord(char) == 127 for char in value.strip()):
        raise ProviderError("暗光一条虫 API Key 不可用")
    return value.strip()


def _encrypted_intent(intent: dict) -> str:
    try:
        encrypted = encrypt_private_text(json_module.dumps(intent, ensure_ascii=False))
    except RuntimeConfigStoreError:
        encrypted = None
    if encrypted is None:
        raise ProviderError("暗光提交凭据无法加密，请检查配置加密密钥")
    return encrypted


def _load_intent(private: dict) -> dict:
    intent = None
    encrypted = private.get("anguang_request_encrypted")
    if isinstance(encrypted, str) and encrypted:
        try:
            intent = json_module.loads(decrypt_private_text(encrypted))
        except (RuntimeConfigStoreError, ValueError, TypeError):
            pass
    if not isinstance(intent, dict):
        raise ProviderError("暗光原任务恢复凭据不可用，请检查配置加密密钥")
    _api_base(intent.get("api_base"))
    _api_key(intent.get("api_key"))
    return intent


def _retry_delay(header, data) -> int | None:
    delays = []
    for value, date_allowed in ((header, True), (data.get("retryAfter"), False)):
        seconds = None
        if type(value) in (int, float) or isinstance(value, str):
            try:
                seconds = float(value)
            except (ValueError, OverflowError):
                if date_allowed and isinstance(value, str):
                    try:
                        parsed = parsedate_to_datetime(value)
                        seconds = parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp() - time.time()
                    except (ValueError, TypeError, OverflowError):
                        pass
        if seconds is not None and math.isfinite(seconds) and seconds > 0:
            delays.append(min(86400, math.ceil(seconds)))
    return max(delays) if delays else None


def _waiting_for_retry(private) -> bool:
    until = private.get("anguang_retry_not_before")
    return type(until) in (int, float) and math.isfinite(until) and time.time() < until


def _query_failed(private, error):
    private.update(latest_query_failed=True, latest_query_http_status=error.http_status if isinstance(error, ProviderHTTPError) else None)
    delay = getattr(error, "retry_after_seconds", None)
    if type(delay) is int and 0 < delay <= 86400:
        private["anguang_retry_not_before"] = time.time() + delay


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AnguangHTTPTransport:
    """凭据仅发送至已配置地址，禁用环境代理与所有 HTTP 重定向。"""

    def __init__(self, api_base):
        self.api_base = _api_base(api_base)

    def for_api_base(self, api_base):
        transport = type(self)(api_base)
        if hasattr(self, "deadline"):
            transport.deadline = self.deadline
        return transport

    def request(self, method, path, *, json=None, headers=None, timeout=30):
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or any(ord(char) < 33 for char in path):
            raise ProviderError("暗光请求路径无效")
        deadline = getattr(self, "deadline", None)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("暗光查询时间已到")
            timeout = min(float(timeout), remaining)
        body = None if json is None else json_module.dumps(json).encode("utf-8")
        request_headers = {"Accept": "application/json", "Content-Type": "application/json", **dict(headers or {}), "User-Agent": "Mozilla/5.0"}
        http_request = Request(f"{self.api_base}{path}", data=body, headers=request_headers, method=str(method).upper())
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(http_request, timeout=timeout) as response:
                content, status, response_headers = response.read(), response.status, dict(response.headers)
        except HTTPError as error:
            with error:
                content, status, response_headers = error.read(), error.code, dict(error.headers)
        try:
            payload = json_module.loads(content.decode("utf-8"))
        except (ValueError, UnicodeError):
            payload = None
        return SimpleNamespace(status_code=status, headers=response_headers, json=lambda: payload)


class AnguangProvider:
    provider_id = "anguang"

    def __init__(self, config, transport):
        self.config, self.transport = config, transport

    def create_job(self, request_data: ExtractRequest) -> ProviderJob:
        for capability in ("extract", "payment", "auto_payment"):
            require_capability(self.config, capability)
        if request_data.mode != "auto_payment" or request_data.link_type != "upi":
            raise ProviderError("暗光一条虫仅支持 UPI 原生自动支付")
        if not isinstance(request_data.idempotency_key, str) or not request_data.idempotency_key.strip():
            raise ProviderError("暗光提交缺少原任务幂等身份")
        if not isinstance(request_data.access_token, str) or not request_data.access_token.strip():
            raise ProviderError("暗光提交缺少访问令牌")
        options = request_data.options
        if str(options.get("payment_method", "UPI")).upper() != "UPI":
            raise ProviderError("暗光一条虫仅支持 UPI")
        processing_mode = options.get("processing_mode", "STANDARD")
        plan_name = options.get("plan_name", "chatgptplusplan")
        auto_retry = options.get("auto_retry", False)
        if (not isinstance(processing_mode, str) or processing_mode not in {"STANDARD", "STRICT"}
                or not isinstance(plan_name, str) or plan_name not in _PLANS or type(auto_retry) is not bool):
            raise ProviderError("暗光提交参数无效")
        request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"turb:anguang:{request_data.idempotency_key}"))
        body = {
            "requestId": request_id, "tokens": [request_data.access_token],
            "processingMode": processing_mode, "planName": plan_name,
            "paymentMethodType": "UPI", "autoSubmit": True, "autoRetry": auto_retry, "maxAmountCents": 0,
        }
        private = {"anguang_submission_pending": True, "anguang_request_encrypted": _encrypted_intent({
            "request_id": request_id, "body": body,
            "api_base": _api_base(self.config.api_base), "api_key": _api_key(self.config.cdk),
        })}
        # 保存失败则不发送请求；恢复必须重放同一份 body 和 requestId。
        if callable(request_data.submission_checkpoint):
            request_data.submission_checkpoint(copy.deepcopy(private))
        return self._submit(private)

    def get_status(self, job_ref: str, *, private_data: dict | None = None) -> ProviderJob:
        require_capability(self.config, "extract")
        private = copy.deepcopy(private_data or {})
        if not job_ref:
            return self._submit(private, replay=True)
        job_id = _uuid(job_ref)
        if job_id is None:
            raise ProviderError("暗光任务编号无效")
        if "anguang_request_encrypted" not in private:
            private["anguang_request_encrypted"] = _encrypted_intent({
                "api_base": _api_base(self.config.api_base), "api_key": _api_key(self.config.cdk),
            })
        intent = _load_intent(private)
        private["anguang_submission_pending"] = False
        if _waiting_for_retry(private):
            return self._pending(private, job_id)
        private.pop("anguang_retry_not_before", None)
        private.update(anguang_submission_pending=False, latest_query_failed=False, latest_query_http_status=None)
        try:
            data = self._request("GET", f"/tasks/{job_id}", intent)
            # 网页单条接口直接返回任务；兼容显式 task 包装，不接受其他任务编号。
            row = data.get("task") if isinstance(data.get("task"), dict) else data
            if _uuid(row.get("id")) != job_id:
                raise ProviderError("暗光状态响应的任务编号与请求不一致")
            return self._job(row, private, job_id)
        except ProviderError as error:
            _query_failed(private, error)
        return self._pending(private, job_id)

    def start_payment(self, job_ref: str, options: dict) -> ProviderJob:
        raise ProviderUnsupported()

    def _request(self, method, path, intent, *, body=None):
        base, key = _api_base(intent["api_base"]), _api_key(intent["api_key"])
        transport = self.transport
        if callable(getattr(transport, "for_api_base", None)):
            transport = transport.for_api_base(base)
        elif base != _api_base(self.config.api_base):
            raise ProviderError("暗光原任务 API 地址不可用")
        retry_delay = None

        def observed_request(*args, **kwargs):
            nonlocal retry_delay
            response = transport.request(*args, **kwargs)
            if getattr(response, "status_code", None) == 429:
                headers = getattr(response, "headers", {})
                header = (headers.get("Retry-After") or headers.get("retry-after")) if isinstance(headers, Mapping) else None
                try:
                    data = response_dict(response)
                except ProviderError:
                    data = {}
                retry_delay = _retry_delay(header, data)
            return response

        try:
            return request(SimpleNamespace(request=observed_request), method, path, body=copy.deepcopy(body), headers={
                "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                "Cache-Control": "no-store", "User-Agent": "Mozilla/5.0",
            }, timeout=self.config.timeout)
        except ProviderHTTPError as error:
            if error.http_status == 429 and retry_delay is not None:
                error.retry_after_seconds = retry_delay
            raise

    @staticmethod
    def _validate_intent(private):
        intent = _load_intent(private)
        body = intent.get("body")
        if private.get("anguang_submission_pending") is not True or not isinstance(body, dict):
            raise ProviderError("暗光原任务提交意图不可用")
        request_id = _uuid(intent.get("request_id"))
        allowed = {"requestId", "tokens", "processingMode", "planName", "paymentMethodType", "autoSubmit", "autoRetry", "maxAmountCents"}
        tokens = body.get("tokens")
        if (set(body) != allowed or not request_id or body.get("requestId") != request_id
                or not isinstance(tokens, list) or len(tokens) != 1 or not isinstance(tokens[0], str) or not tokens[0].strip()
                or not isinstance(body.get("processingMode"), str) or body["processingMode"] not in {"STANDARD", "STRICT"}
                or not isinstance(body.get("planName"), str) or body["planName"] not in _PLANS
                or body.get("paymentMethodType") != "UPI" or body.get("autoSubmit") is not True
                or type(body.get("autoRetry")) is not bool or type(body.get("maxAmountCents")) is not int or body["maxAmountCents"] != 0):
            raise ProviderError("暗光原任务提交意图无效")
        return intent

    def _submit(self, private, *, replay=False):
        private = copy.deepcopy(private)
        intent = self._validate_intent(private)
        if _waiting_for_retry(private):
            return self._pending(private)
        private.pop("anguang_retry_not_before", None)
        private.update(latest_query_failed=False, latest_query_http_status=None)
        try:
            data = self._request("POST", "/tasks", intent, body=intent["body"])
        except ProviderError as error:
            if not replay and isinstance(error, ProviderHTTPError) and error.http_status in _SUBMISSION_REJECTIONS:
                return self._rejected(private, "REJECTED", f"暗光平台未受理任务（HTTP {error.http_status}）")
            _query_failed(private, error)
            return self._pending(private)
        if "requestId" in data and data["requestId"] != intent["request_id"]:
            return self._pending(private)
        items = data.get("items")
        if isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict):
            row = items[0]
            job_id = _uuid(row.get("id"))
            if type(row.get("index")) is int and row["index"] == 0 and job_id:
                private["anguang_submission_pending"] = False
                return self._job(row, private, job_id)
            if row.get("index") == 0 and row.get("status") == "REJECTED" and not row.get("id"):
                return self._pending(private) if replay else self._rejected(private, "REJECTED", "暗光平台未受理任务")
            return self._pending(private)
        if items == [] and data.get("accepted", 0) == 0 and data.get("unknown", 0) == 0:
            for field, message in (
                ("cooldown", "账号处于失败冷却期，平台已跳过"), ("expired", "访问令牌已过期，平台已跳过"),
                ("invalid", "访问令牌格式无效，平台已跳过"), ("skipped", "平台已跳过当前任务"),
                ("rejected", "暗光平台未受理任务"),
            ):
                if type(data.get(field)) is int and data[field] == 1:
                    return self._pending(private) if replay else self._rejected(private, field.upper(), message)
        return self._pending(private)

    @staticmethod
    def _rejected(private, outcome, message):
        private = {**private, "anguang_submission_pending": False}
        return ProviderJob(extraction_state="failed", private_data=private, summary={
            "outcome": outcome, "failure_message": message, "submission_receipt_pending": False,
            "remote_polling": False, "automatic_payment_terminal": True, "automatic_payment_requires_reconcile": False,
        })

    @staticmethod
    def _previous(private):
        value = private.get("anguang_last_state", private.get("previous_public_state", {}))
        return value if isinstance(value, dict) else {}

    def _pending(self, private, job_id=None):
        previous = self._previous(private)
        extraction = previous.get("extraction_state")
        payment = previous.get("payment_state")
        terminal = payment in {"succeeded", "failed"}
        if payment == "succeeded":
            extraction = "succeeded"
        summary = {
            "submission_receipt_pending": private.get("anguang_submission_pending") is True and not terminal,
            "remote_polling": not terminal, "automatic_payment_terminal": terminal,
            "automatic_payment_requires_reconcile": not terminal,
        }
        if terminal:
            summary["automatic_payment_status"] = "completed" if payment == "succeeded" else "failed"
            summary["xxsyun_status"] = summary["automatic_payment_status"]
            if extraction == "failed":
                summary["remote_terminal_failure"] = True
        else:
            summary["outcome"] = "UNKNOWN"
        return ProviderJob(
            job_id=job_id, extraction_state=extraction if extraction in {"queued", "running", "succeeded", "failed"} else "unknown",
            payment_state=payment if terminal else "unknown", links=safe_links(*previous.get("links", [])),
            payment_links=safe_links(*previous.get("payment_links", [])),
            payment_artifact=safe_payment_artifact(previous.get("payment_artifact")), private_data=copy.deepcopy(private),
            summary=summary,
        )

    def _job(self, row, private, job_id):
        previous = self._previous(private)
        remote_status = row.get("status") if isinstance(row.get("status"), str) else ""
        extraction = _EXTRACTION.get(remote_status, "unknown")
        if previous.get("extraction_state") == "succeeded":
            extraction = "succeeded"
        scan = row.get("scan") if isinstance(row.get("scan"), dict) else {}
        scan_status = scan.get("status") if isinstance(scan.get("status"), str) else ""
        # 缺失、未知或旧进度不能推翻同单已观测的扫码完成；明确失败仍采用最新证据。
        if previous.get("payment_state") == "succeeded" and scan_status not in _SCAN_FAILED:
            scan_status = "completed"
        payment = ("succeeded" if scan_status == "completed" else "failed" if scan_status in _SCAN_FAILED
                   else "pending" if scan_status in _SCAN_PENDING else "unknown")
        # 已完成扫码证明原链成功生成支付材料，冲突的旧提链失败状态不能阻断本地套餐核验。
        if payment == "succeeded":
            extraction = "succeeded"
        retry = row.get("retry") if isinstance(row.get("retry"), dict) else {}
        retry_status = retry.get("status")
        retry_active = isinstance(retry_status, str) and retry_status in _RETRY_ACTIVE and payment != "succeeded"
        if retry_active:
            payment = "pending"
            if extraction == "failed":
                extraction = "running"
        elif retry_status == "UNKNOWN" and payment != "succeeded":
            payment = "unknown"
        elif retry_status == "FAILED" and payment != "succeeded" and scan_status != "UNKNOWN":
            payment = "failed"
        if extraction == "failed" and scan_status in {"", "NONE"} and not retry_active and retry_status != "UNKNOWN":
            payment = "failed"
        polling = retry_active or payment in {"pending", "unknown"}
        if extraction in {"queued", "running", "unknown"} and payment != "succeeded":
            polling = True
        summary = {
            "submission_receipt_pending": False, "remote_polling": polling,
            "automatic_payment_terminal": not polling, "automatic_payment_requires_reconcile": payment == "unknown",
        }
        if remote_status in _EXTRACTION:
            # PENDING/SUBMITTING 是暗光队列状态，存储层只使用现有公共枚举。
            summary["remote_status"] = {"PENDING": "QUEUED", "SUBMITTING": "RUNNING"}.get(remote_status, remote_status)
        if extraction == "failed" and not polling:
            summary["remote_terminal_failure"] = True
        if isinstance(scan_status, str) and scan_status in _SCAN_KNOWN:
            summary["xxsyun_status"] = scan_status
            summary["automatic_payment_status"] = scan_status
        if extraction == "failed" or payment == "failed":
            code = row.get("failureCode")
            message = _FAILURES.get(code) if isinstance(code, str) else None
            if message:
                summary["failure_code"] = code
            summary["failure_message"] = message or ("暗光平台提链失败" if extraction == "failed" else "暗光平台扫码失败")
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        artifact = result.get("paymentArtifact") if isinstance(result.get("paymentArtifact"), dict) else {}
        links = safe_links(result.get("paymentUrl"), result.get("checkoutUrl"), result.get("shortLink")) or safe_links(*previous.get("links", []))
        payment_links = safe_links(artifact.get("url"), artifact.get("processorUrl"), artifact.get("hostedInstructionsUrl"), result.get("hostedUrl")) or safe_links(*previous.get("payment_links", []))
        material = {**safe_payment_artifact(previous.get("payment_artifact")), **safe_payment_artifact({
            "payment_page_url": result.get("hostedUrl"), "payment_url": payment_links[0] if payment_links else None,
            "qr_data": artifact.get("data"), "qr_image_url_png": artifact.get("imageUrlPng"),
            "qr_image_url_svg": artifact.get("imageUrlSvg"), "amount": result.get("amount", artifact.get("amount")),
            "currency": result.get("currency") or artifact.get("currency"), "expires_at": artifact.get("expiresAt"),
            "payment_status": scan_status if scan_status in _SCAN_KNOWN else None,
        })}
        state = {"extraction_state": extraction, "payment_state": payment, "links": links,
                 "payment_links": payment_links, "payment_artifact": material, "summary": summary}
        private = {**private, "anguang_last_state": copy.deepcopy(state)}
        return ProviderJob(job_id=job_id, **state, private_data=private)


__all__ = ["AnguangHTTPTransport", "AnguangProvider"]
