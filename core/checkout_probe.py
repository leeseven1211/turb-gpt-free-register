# -*- coding: utf-8 -*-
"""查询官方结账会话的支付方式和应付金额，不确认支付或绑定支付方式。"""
from __future__ import annotations

import json
import logging
import math
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from curl_cffi.requests import Session, exceptions as curl_exceptions

from core.operation_runtime import OperationAccountDeactivated, OperationCancelled, check_cancelled
from core.operations.task_gateway import OperationLeaseLost
from core.sentinel import build_sentinel_request_body, generate_requirements_token
from core.sentinel_runner import generate_sentinel_token

logger = logging.getLogger(__name__)
_STAGES = frozenset({"pricing", "sentinel_request", "sentinel_token", "create", "oaics_state", "stripe_init", "parse"})
_HTTP_STAGES = frozenset({"pricing", "sentinel_request", "create", "oaics_state", "stripe_init"})
_CHATGPT = "https://chatgpt.com"
_CHECKOUT_PATH = "/backend-api/payments/checkout"
_ENTITIES = {"openai_llc", "openai_ie"}
# 仅保存可显示的支付方式代码，拒绝任意标识符、凭据和未知字符串。
_METHODS = frozenset("""
card link paypal upi pix momo gopay grabpay gcash ideal blik twint kakao kakao_pay
naver_pay bizum cashapp cash_app amazon_pay alipay alipay_hk wechat_pay apple_pay
google_pay bancontact eps p24 giropay sofort sepa_debit bacs_debit au_becs_debit
acss_debit us_bank_account ach_credit_transfer bank_transfer customer_balance
boleto oxxo konbini promptpay paynow pay_by_bank mobilepay revolut_pay swish
satispay multibanco mb_way klarna affirm afterpay_clearpay zip alma atome
kr_card korean_card kr_market naverpay samsung_pay kakao_pay payco toss_pay
paypay au_pay rakuten_pay dana ovo shopeepay boost touch_n_go fpx netbanking
id_bank_transfer id_wallet vn_wallet cash eftpos interac_present card_present
""".split())
_METHOD_NAME_ALIASES = {
    "银行卡": "card", "信用卡": "card", "借记卡": "card",
    "bank card": "card", "credit card": "card", "debit card": "card",
    "credit/debit card": "card", "credit or debit card": "card",
    "微信支付": "wechat_pay", "支付宝": "alipay",
    "apple pay": "apple_pay", "google pay": "google_pay",
    "cash app": "cashapp", "amazon pay": "amazon_pay",
}
_METHOD_NAME_FIELDS = ("name", "display_name", "displayName", "display", "label")
_CURRENCY_CODE_FIELDS = ("symbol_code", "code", "currency_code", "currencyCode")
_WRAPPERS = (
    "checkout_session", "checkoutSession", "session", "checkout", "data", "result",
    "payload", "response", "checkout_state", "checkoutState", "checkout_snapshot", "checkoutSnapshot",
)
_AMOUNT_PATHS = (
    ("checkout_amount_minor",), ("total_summary", "due"), ("totalSummary", "due"),
    ("invoice", "amount_due"), ("invoice", "amountDue"), ("amount_due",),
    ("amountDue",), ("amount_total",), ("amountTotal",), ("total", "due"), ("total", "total"),
)
_ERRORS = frozenset({
    "缺少访问凭据", "国家代码无效", "没有可核验的优惠活动", "暂不支持该套餐的结账预检",
    "结账预检预算已用尽", "结账预检失败", "定价配置查询失败", "定价配置无效",
    "结账风控预检失败", "创建结账会话失败", "结账会话类型未知", "结账处理实体无效",
    "结账会话状态查询失败", "Stripe 初始化查询失败", "结账会话缺少支付方式",
    "结账公开密钥无效", "结账币种与定价配置不一致",
})


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 2**53 - 1 else None
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() and 0 <= value <= 2**53 - 1 else None
    if isinstance(value, str) and re.fullmatch(r"\d{1,16}", value):
        number = int(value)
        return number if number <= 2**53 - 1 else None
    if isinstance(value, dict):
        for key in ("minorUnitsAmount", "minor_units_amount", "amount"):
            if key in value and not isinstance(value[key], dict):
                return _integer(value[key])
    return None


def _method_types(value: Any, *, allow_custom_names: bool = False) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:128]:
        candidates = [item]
        if isinstance(item, dict):
            candidates = [item.get(key) for key in ("type", "payment_method_type", "paymentMethodType")]
            if allow_custom_names:
                for key in _METHOD_NAME_FIELDS:
                    label = item.get(key)
                    if isinstance(label, dict):
                        candidates.extend(label.get(field) for field in _METHOD_NAME_FIELDS if field != "display")
                    else:
                        candidates.append(label)
        for candidate in candidates:
            name = candidate.strip().lower() if isinstance(candidate, str) else ""
            if allow_custom_names:
                name = _METHOD_NAME_ALIASES.get(name, name)
            if name in _METHODS:
                if name not in result:
                    result.append(name)
                break
    return result[:32]


def _source_allowed(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 180:
        return False
    parts = value.split(".")
    return any(tuple(parts[-len(path):]) == path and len(parts) - len(path) <= 3
               and all(part in _WRAPPERS for part in parts[:-len(path)]) for path in _AMOUNT_PATHS)


def public_checkout_details(value: Any) -> dict:
    """输出可持久化的白名单字段，任何上游原文和会话标识均不透传。"""
    value = value if isinstance(value, dict) else {}
    if not any(key.startswith("checkout_") or key in {"payment_method_types", "session_type"}
               for key in value if isinstance(key, str)):
        return {}
    status = value.get("checkout_status")
    session_type = value.get("session_type")
    currency = value.get("checkout_currency")
    country = value.get("checkout_country")
    exponent = value.get("checkout_currency_exponent")
    http_status = value.get("checkout_http_status")
    checked_at = value.get("checkout_checked_at")
    try:
        checked_at = datetime.fromisoformat(checked_at).isoformat(timespec="seconds") if isinstance(checked_at, str) else None
    except (ValueError, OverflowError):
        checked_at = None
    error = value.get("checkout_error")
    methods = _method_types(value.get("payment_method_types"))
    status = status if isinstance(status, str) and status in {"success", "failed", "skipped"} else "failed"
    if status == "success" and not methods:
        status = "failed"
    return {
        "checkout_status": status,
        "checkout_checked_at": checked_at,
        "checkout_http_status": http_status if isinstance(http_status, int) and not isinstance(http_status, bool) and 100 <= http_status <= 599 else None,
        "checkout_error": error if isinstance(error, str) and error in _ERRORS else ("结账预检失败" if error else None),
        "session_type": session_type if isinstance(session_type, str) and session_type in {"cs_live", "oaics"} else "unknown",
        "payment_method_types": methods,
        "checkout_amount_due_minor": _integer(value.get("checkout_amount_due_minor")),
        "checkout_currency": currency.upper() if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency) else None,
        "checkout_currency_exponent": exponent if isinstance(exponent, int) and not isinstance(exponent, bool) and 0 <= exponent <= 3 else None,
        "checkout_amount_source": value.get("checkout_amount_source") if _source_allowed(value.get("checkout_amount_source")) else None,
        "checkout_source": "checkout",
        "checkout_country": country.upper() if isinstance(country, str) and re.fullmatch(r"[A-Za-z]{2}", country) else None,
    }


class _ProbeFailure(Exception):
    def __init__(self, message: str, status: int | None = None):
        self.message = message
        self.status = status


def _log_failure(country: str, stage: str, exc: Exception) -> None:
    """只记录受控分类，不把异常原文、请求地址或私有响应写入日志。"""
    safe_country = country if re.fullmatch(r"[A-Z]{2}", country) else "unknown"
    safe_stage = stage if stage in _STAGES else "parse"
    name = type(exc).__name__
    safe_name = name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", name) else "Exception"
    code = getattr(exc, "code", None)
    safe_code = int(code) if isinstance(code, int) and not isinstance(code, bool) and 0 <= code <= 999 else None
    logger.warning("[结账预检] 失败 country=%s stage=%s exception=%s curl_code=%s",
                   safe_country, safe_stage, safe_name, safe_code)


def _remaining(timeout: float, deadline_at: float) -> float:
    remaining = min(timeout, deadline_at - time.time())
    if remaining < 0.001:
        raise TimeoutError("结账预检预算已用尽")
    return remaining


def _checkpoint(callback, message: str) -> None:
    check_cancelled(message)
    if callback is not None:
        callback(message)


def _response_json(response, message: str) -> dict:
    status = getattr(response, "status_code", None)
    if not isinstance(status, int) or not 200 <= status < 300:
        raise _ProbeFailure(message, status)
    try:
        data = response.json()
    except (ValueError, TypeError):
        raise _ProbeFailure(message, status) from None
    if not isinstance(data, dict) or data.get("error") or data.get("errors"):
        raise _ProbeFailure(message, status)
    return data


def _headers(session, token: str, path: str, *, claims: dict | None = None, referer: str = _CHATGPT + "/") -> dict:
    headers = session.get_chatgpt_headers(referer=referer)
    headers.update({"authorization": f"Bearer {token}", "origin": _CHATGPT,
                    "x-openai-target-path": path, "x-openai-target-route": path})
    account_id = claims.get("account_id") if isinstance(claims, dict) else None
    if isinstance(account_id, str) and account_id:
        headers["chatgpt-account-id"] = account_id
    return headers


def _checkout_risk_headers(session, campaign: str, timeout: float, deadline_at: float, checkpoint,
                           stage_callback=None) -> dict:
    if stage_callback is not None:
        stage_callback("sentinel_request")
    flow = "chatgpt_checkout"
    profile = dict(getattr(session, "browser_profile", None) or {})
    from config import SENTINEL_SV
    profile["script_src_samples"] = [f"https://sentinel.openai.com/sentinel/{SENTINEL_SV}/sdk.js"]
    proof = generate_requirements_token(getattr(session, "sentinel_sid", session.device_id), profile=profile)
    _checkpoint(checkpoint, "结账风控查询")
    response = session.post(
        "https://sentinel.openai.com/backend-api/sentinel/req",
        headers=session.get_sentinel_headers(),
        data=build_sentinel_request_body(proof, session.device_id, flow),
        timeout=_remaining(timeout, deadline_at), allow_redirects=False,
    )
    challenge = _response_json(response, "结账风控预检失败")
    challenge["_request_p"] = proof
    if stage_callback is not None:
        stage_callback("sentinel_token")
    _checkpoint(checkpoint, "生成结账风控令牌")
    token = generate_sentinel_token(
        challenge=challenge, flow=flow, device_id=session.device_id,
        page_url=f"{_CHATGPT}/?promo_campaign={quote(campaign, safe='')}",
        user_agent=profile.get("user_agent"), browser_profile=profile,
        sentinel_sid=getattr(session, "sentinel_sid", None),
        react_listening_key=getattr(session, "react_listening_key", None),
        react_container_key=getattr(session, "react_container_key", None),
        react_resources_key=getattr(session, "react_resources_key", None),
        cookie=session.chatgpt_cookie_header(), timeout_seconds=_remaining(timeout, deadline_at),
    )
    parsed = json.loads(token)
    if not isinstance(parsed, dict) or parsed.get("id") != session.device_id or parsed.get("flow") != flow or not parsed.get("p") or not parsed.get("c"):
        raise _ProbeFailure("结账风控预检失败")
    output = {key: parsed[key] for key in ("p", "t", "c", "id", "flow") if key in parsed}
    headers = {"openai-sentinel-token": json.dumps(output, separators=(",", ":"))}
    so = parsed.get("_so") or parsed.get("so")
    if so:
        headers["openai-sentinel-so-token"] = json.dumps(
            {"so": so, "c": parsed["c"], "id": session.device_id, "flow": flow}, separators=(",", ":"))
    return headers


def _candidates(payload: dict):
    pending = [(payload, "", ())]
    visited = set()
    while pending and len(visited) < 256:
        node, prefix, ancestors = pending.pop(0)
        if id(node) in visited:
            continue
        visited.add(id(node))
        yield node, prefix, ancestors
        if len(ancestors) < 3:
            for key in _WRAPPERS:
                if isinstance(node.get(key), dict):
                    pending.append((node[key], prefix + key + ".", (*ancestors, node)))


def _verify_currency(node: dict, expected: str) -> None:
    """只核对金额所属节点的显式币种，拒绝用定价币种覆盖不同币种。"""
    for key in ("currency", "currency_code", "currencyCode"):
        value = node.get(key)
        if value is None:
            continue
        codes = [value]
        if isinstance(value, dict):
            codes = [value[field] for field in _CURRENCY_CODE_FIELDS if value.get(field) is not None]
        if not codes or any(not isinstance(code, str) or not re.fullmatch(r"[A-Za-z]{3}", code)
                            or code.upper() != expected.upper() for code in codes):
            raise _ProbeFailure("结账币种与定价配置不一致")


def _details(payload: dict, expected_currency: str) -> tuple[list[str], int | None, str | None]:
    methods = []
    amount = source = None
    _verify_currency(payload, expected_currency)
    for node, prefix, ancestors in _candidates(payload):
        for key in ("payment_method_types", "paymentMethodTypes", "custom_payment_methods", "customPaymentMethods"):
            for method in _method_types(node.get(key), allow_custom_names=key in {"custom_payment_methods", "customPaymentMethods"}):
                if method not in methods:
                    methods.append(method)
        if amount is None:
            for path in _AMOUNT_PATHS:
                value = node
                amount_nodes = list(ancestors)
                for part in path:
                    if isinstance(value, dict):
                        amount_nodes.append(value)
                    value = value.get(part) if isinstance(value, dict) else None
                parsed = _integer(value)
                if parsed is not None:
                    if isinstance(value, dict):
                        amount_nodes.append(value)
                    for amount_node in amount_nodes:
                        _verify_currency(amount_node, expected_currency)
                    amount, source = parsed, prefix + ".".join(path)
                    break
    return methods[:32], amount, source


def _stripe_init(session, checkout_id: str, key: str, timeout: float, deadline_at: float) -> tuple[dict, int]:
    """Stripe 使用相同代理和浏览器身份，隔离 ChatGPT 的 Cookie 与默认认证头。"""
    profile = getattr(session, "browser_profile", None) or {}
    identity = getattr(session, "chrome_identity", None) or {}
    stripe = Session(impersonate=identity.get("impersonate") or "chrome")
    try:
        if session.proxy:
            stripe.proxies = {"http": session.proxy, "https": session.proxy}
        headers = {"Origin": "https://js.stripe.com", "Referer": "https://js.stripe.com/",
                   "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
        common = session.get_chatgpt_headers()
        for name in ("user-agent", "accept-language"):
            value = next((value for key, value in common.items() if key.lower() == name), None)
            if value:
                headers[name] = value
        locale = profile.get("navigator_language") or "en-US"
        body = {
            "browser_locale": locale, "browser_timezone": profile.get("timezone_iana") or "UTC",
            "elements_session_client[client_betas][0]": "custom_checkout_server_updates_1",
            "elements_session_client[client_betas][1]": "custom_checkout_manual_approval_1",
            "elements_session_client[elements_init_source]": "custom_checkout",
            "elements_session_client[referrer_host]": "chatgpt.com",
            "elements_session_client[stripe_js_id]": str(uuid.uuid4()),
            "elements_session_client[locale]": str(locale).split("-")[0],
            "elements_options_client[saved_payment_method][enable_save]": "auto",
            "elements_options_client[saved_payment_method][enable_redisplay]": "auto",
            "key": key,
            "_stripe_version": "2025-03-31.basil; checkout_server_update_beta=v1; checkout_manual_approval_preview=v1",
        }
        response = stripe.post(f"https://api.stripe.com/v1/payment_pages/{checkout_id}/init",
                               headers=headers, data=body, timeout=_remaining(timeout, deadline_at), allow_redirects=False)
        return _response_json(response, "Stripe 初始化查询失败"), response.status_code
    finally:
        stripe.close()


def query_checkout_details(token: str, *, session, country: str, campaign_id: str,
                           plan: str = "plus", timeout: float = 15, deadline_at: float | None = None,
                           checkpoint=None, claims: dict | None = None) -> dict:
    """每次调用最多创建一个结账会话，后续只读已返回的官方会话。"""
    result = {"checkout_status": "failed", "checkout_checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "checkout_country": str(country or "").strip().upper()}
    stage = "parse"

    def mark_stage(value: str) -> None:
        nonlocal stage
        stage = value if value in _STAGES else "parse"

    try:
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise TimeoutError
        deadline_at = float(deadline_at) if deadline_at is not None else time.time() + timeout
        if not math.isfinite(deadline_at):
            raise TimeoutError
        _checkpoint(checkpoint, "开始结账预检")
        _remaining(timeout, deadline_at)
        token = token.strip() if isinstance(token, str) else ""
        campaign = campaign_id.strip() if isinstance(campaign_id, str) else ""
        if not token:
            raise _ProbeFailure("缺少访问凭据")
        if not re.fullmatch(r"[A-Z]{2}", result["checkout_country"]):
            raise _ProbeFailure("国家代码无效")
        if plan != "plus":
            result["checkout_status"] = "skipped"
            raise _ProbeFailure("暂不支持该套餐的结账预检")
        if not campaign or len(campaign) > 200 or not re.fullmatch(r"[A-Za-z0-9_-]+", campaign):
            result["checkout_status"] = "skipped"
            raise _ProbeFailure("没有可核验的优惠活动")
        cc = result["checkout_country"]
        pricing_path = f"/backend-api/checkout_pricing_config/configs/{cc}"
        stage = "pricing"
        _checkpoint(checkpoint, "查询结账定价配置")
        response = session.get(_CHATGPT + pricing_path, headers=_headers(session, token, pricing_path, claims=claims),
                               timeout=_remaining(timeout, deadline_at), allow_redirects=False)
        pricing = _response_json(response, "定价配置查询失败")
        result["checkout_http_status"] = response.status_code
        currency = pricing.get("currency_config")
        if not isinstance(currency, dict) or str(pricing.get("country_code") or "").upper() != cc:
            raise _ProbeFailure("定价配置无效")
        code, exponent = currency.get("symbol_code"), currency.get("minor_unit_exponent")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z]{3}", code) or isinstance(exponent, bool) or not isinstance(exponent, int) or not 0 <= exponent <= 3:
            raise _ProbeFailure("定价配置无效")
        result.update(checkout_currency=code.upper(), checkout_currency_exponent=exponent)
        stage = "sentinel_request"
        risk_headers = _checkout_risk_headers(session, campaign, timeout, deadline_at, checkpoint, mark_stage)
        stage = "create"
        _checkpoint(checkpoint, "创建结账预检会话")
        headers = _headers(session, token, _CHECKOUT_PATH, claims=claims,
                           referer=f"{_CHATGPT}/?promo_campaign={quote(campaign, safe='')}")
        headers.update(risk_headers)
        payload = {"entry_point": "all_plans_pricing_modal", "plan_name": "chatgptplusplan",
                   "billing_details": {"country": cc, "currency": code.upper()}, "checkout_ui_mode": "custom",
                   "promo_campaign": {"promo_campaign_id": campaign, "is_coupon_from_query_param": False}}
        response = session.post(_CHATGPT + _CHECKOUT_PATH, json=payload, headers=headers,
                                timeout=_remaining(timeout, deadline_at), allow_redirects=False)
        data = _response_json(response, "创建结账会话失败")
        result["checkout_http_status"] = response.status_code
        stage = "parse"
        checkout_id = data.get("checkout_session_id") or data.get("id")
        if isinstance(checkout_id, str) and re.fullmatch(r"oaics_[A-Za-z0-9_-]{1,240}", checkout_id):
            result["session_type"] = "oaics"
            entity = data.get("processor_entity")
            if entity not in _ENTITIES:
                raise _ProbeFailure("结账处理实体无效")
            stage = "oaics_state"
            _checkpoint(checkpoint, "读取结账会话状态")
            path = f"{_CHECKOUT_PATH}/{entity}/{checkout_id}"
            response = session.get(_CHATGPT + path, headers=_headers(session, token, path, claims=claims),
                                   timeout=_remaining(timeout, deadline_at), allow_redirects=False)
            data = _response_json(response, "结账会话状态查询失败")
            result["checkout_http_status"] = response.status_code
        elif isinstance(checkout_id, str) and re.fullmatch(r"cs_live_[A-Za-z0-9_-]{1,240}", checkout_id):
            result["session_type"] = "cs_live"
            key = data.get("publishable_key")
            if not isinstance(key, str) or not re.fullmatch(r"pk_live_[A-Za-z0-9]{8,240}", key):
                raise _ProbeFailure("结账公开密钥无效")
            stage = "stripe_init"
            _checkpoint(checkpoint, "读取 Stripe 支付方式")
            data, result["checkout_http_status"] = _stripe_init(session, checkout_id, key, timeout, deadline_at)
        else:
            raise _ProbeFailure("结账会话类型未知")
        stage = "parse"
        _checkpoint(checkpoint, "完成结账预检")
        _remaining(timeout, deadline_at)
        methods, amount, source = _details(data, code)
        if not methods:
            raise _ProbeFailure("结账会话缺少支付方式")
        result.update(checkout_status="success", checkout_error=None, payment_method_types=methods,
                      checkout_amount_due_minor=amount, checkout_amount_source=source)
    except (OperationCancelled, OperationAccountDeactivated, OperationLeaseLost):
        raise
    except TimeoutError as exc:
        _log_failure(result["checkout_country"], stage, exc)
        result["checkout_http_status"] = None
        result["checkout_error"] = "结账预检预算已用尽"
    except _ProbeFailure as exc:
        result["checkout_error"] = exc.message
        if exc.status is not None:
            result["checkout_http_status"] = exc.status
    except Exception as exc:
        # 不返回异常原文；其中可能含 Token、Cookie、URL、代理凭据或服务端原文。
        _log_failure(result["checkout_country"], stage, exc)
        result["checkout_http_status"] = None
        result["checkout_error"] = "结账预检失败"
        response_status = getattr(getattr(exc, "response", None), "status_code", None)
        has_http_response = (isinstance(response_status, int) and not isinstance(response_status, bool)
                             and 100 <= response_status <= 599)
        # ProxyError 已确认代理隧道失败；附带的连接阶段响应不代表目标请求已完成。
        transport_failure = isinstance(exc, curl_exceptions.ProxyError) or (
            not has_http_response and isinstance(exc, (
                curl_exceptions.ConnectionError, curl_exceptions.SSLError, curl_exceptions.Timeout,
            )))
        if (stage in _HTTP_STAGES and str(getattr(session, "proxy", None) or "").strip()
                and transport_failure):
            result["proxy_transport_failure"] = True
    public = public_checkout_details(result)
    # 仅供本次查询释放线路时使用，持久化优惠仍由公开字段白名单过滤。
    if result.get("proxy_transport_failure") is True:
        public["proxy_transport_failure"] = True
    return public
