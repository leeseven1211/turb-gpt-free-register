# -*- coding: utf-8 -*-
"""
接码平台客户端。

用于 Codex OAuth "全新 session" 流程过 OpenAI 的 /phone-verification 手机号验证：
    1. acquire_number()       getNumber 取一个手机号（返回 激活ID + 号码）
    2. wait_for_sms_code()    轮询 getStatus 直到拿到短信验证码
    3. complete() / cancel()  setStatus 标记完成(6) / 取消(8)

当前支持：
    - GrizzlySMS：GET 文本接口，文档 https://api.grizzlysms.com
    - L：本地 JSON 管理接口，文档 L_API.md
    - H：本地 JSON 管理接口，文档 H_API.md

价格相关：每取一个号、收到短信都会计费，所以：
    - 取号后若收不到短信，必须 cancel(8) 释放，避免白扣钱；
    - 成功拿到码后 complete(6) 正式完成激活。
"""
import json
import logging
import math
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from curl_cffi.requests import Session as CurlSession

# 注意：用 `from config import codex` 而不是 `from config.codex import X`，
# 这样 WebUI 调 config.reload_all() 后，本模块通过 codex.X 读到的是最新值。
from config import codex as _cfg
from config import IMPERSONATE

logger = logging.getLogger(__name__)

# GrizzlySMS 的客户端接口只在 getNumberV2 中返回 activationTime，不返回精确的
# canCancelAt/剩余秒数。实际可取消窗口可能晚于旧规则，因此先按 5 分钟计划一次取消；
# 如果平台仍返回 EARLY_CANCEL_DENIED，则写回持久化队列并做低频退避，不高频轮询。
_GRIZZLY_CANCEL_INITIAL_DELAY = 305
_GRIZZLY_CANCEL_EARLY_BACKOFF = (60, 120, 300, 600)
_GRIZZLY_CANCEL_ERROR_BACKOFF = (30, 60, 120, 300, 600)
_CANCEL_QUEUE_PATH = Path(__file__).resolve().parent.parent / "run" / "sms_cancel_queue.json"

# 记录每个 activation_id 的取号时间与服务端 activationTime；返回值仍保持二元组，
# 避免影响现有调用方。持久化取消队列只保存 activation_id/时间，不含 API key/手机号。
_ACQUIRED_AT: dict[str, float] = {}
_ACTIVATION_META: dict[str, dict] = {}
_CANCEL_QUEUE_LOCK = threading.RLock()
_CANCEL_WORKER_LOCK = threading.Lock()
_CANCEL_WAKE_EVENT = threading.Event()
_CANCEL_WORKER: threading.Thread | None = None
_GRIZZLY_COUNTRY_LOCK = threading.Lock()
_GRIZZLY_COUNTRY_CURSOR = 0


class SmsProviderError(RuntimeError):
    """接码平台通用错误。"""


class SmsNoNumbersError(SmsProviderError):
    """暂无可用号码（NO_NUMBERS），可换国家或稍后重试。"""


class SmsNoBalanceError(SmsProviderError):
    """余额不足（NO_BALANCE），必须充值，重试无意义——上层应立即停止。"""


class SmsPriceLimitError(SmsProviderError):
    """号码价格超过 SMS_MAX_PRICE，重复取同国家不会自行恢复。"""


class SmsCodeTimeout(SmsProviderError):
    """单个号等短信超时（OpenAI 没发或没到达）。"""


def _http() -> CurlSession:
    s = CurlSession(impersonate=IMPERSONATE)
    s.timeout = _cfg.SMS_REQUEST_TIMEOUT
    return s


def _provider() -> str:
    return str(getattr(_cfg, "SMS_PROVIDER", "grizzly") or "grizzly").strip().lower()


def _grizzly_country_candidates(value: str | None = None) -> list[str]:
    """Grizzly country 支持逗号/分号/换行分隔的有序备用列表。"""
    raw = str(value if value is not None else getattr(_cfg, "SMS_COUNTRY", "") or "")
    items = []
    for part in raw.replace("\n", ",").replace(";", ",").split(","):
        one = part.strip()
        if one and one not in items:
            items.append(one)
    return items


def _request_grizzly(http: CurlSession, params: dict) -> str:
    """
    发一个 GrizzlySMS API 请求，返回去空白的响应文本。
    统一识别公共错误码并抛对应异常。
    """
    base_params = {"api_key": _cfg.SMS_API_KEY}
    base_params.update(params)
    resp = http.get(_cfg.SMS_API_BASE, params=base_params)
    if resp.status_code != 200:
        raise SmsProviderError(
            f"GrizzlySMS HTTP {resp.status_code}: {(resp.text or '')[:200]}"
        )
    text = (resp.text or "").strip()

    # 公共错误码（任何 action 都可能返回）
    if text == "BAD_KEY":
        raise SmsProviderError("接码平台 API key 无效（BAD_KEY）")
    if text == "NO_BALANCE":
        raise SmsNoBalanceError("接码平台余额不足（NO_BALANCE），请充值")
    if text == "NO_NUMBERS":
        raise SmsNoNumbersError("接码平台暂无可用号码（NO_NUMBERS）")
    if text.startswith("WRONG_MAX_PRICE"):
        required = text.split(":", 1)[1].strip() if ":" in text else "未知"
        raise SmsPriceLimitError(
            f"号码价格超过 SMS_MAX_PRICE（平台最低要求 {required}），请提高上限或更换国家"
        )
    if text == "SERVICE_UNAVAILABLE_REGION":
        raise SmsProviderError("接码平台地区受限（SERVICE_UNAVAILABLE_REGION），请换 IP")
    if text in ("BAD_ACTION", "BAD_SERVICE", "BAD_STATUS"):
        raise SmsProviderError(f"接码平台请求参数错误：{text}")
    if text == "NO_ACTIVATION":
        raise SmsProviderError("激活 ID 不存在（NO_ACTIVATION）")
    if text.startswith("The service is prohibited"):
        raise SmsProviderError(f"该服务被平台禁售：{text}")

    return text


def _l_url(path: str) -> str:
    base = str(getattr(_cfg, "L_API_BASE", "") or "").strip()
    if not base:
        raise SmsProviderError("L_API_BASE 不能为空")
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def _l_headers() -> dict:
    token = str(getattr(_cfg, "L_ADMIN_AUTH_CODE", "") or "").strip()
    if not token:
        raise SmsProviderError("L_ADMIN_AUTH_CODE 不能为空")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _post_l_json(http: CurlSession, path: str, payload: dict) -> dict:
    resp = http.post(_l_url(path), headers=_l_headers(), data=json.dumps(payload))
    text = (resp.text or "").strip()
    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code != 200:
        msg = data.get("error") if isinstance(data, dict) else ""
        raise SmsProviderError(f"L HTTP {resp.status_code}: {(msg or text)[:200]}")
    if isinstance(data, dict) and data.get("error"):
        error = str(data.get("error") or "")
        raw = str(data.get("raw") or "")
        combined = f"{error} {raw}".strip()
        if "NO_BALANCE" in combined or "余额不足" in combined:
            raise SmsNoBalanceError(f"L 余额不足：{combined}")
        if "NO_NUMBERS" in combined or "暂无号码" in combined:
            raise SmsNoNumbersError(f"L 暂无可用号码：{combined}")
        raise SmsProviderError(f"L 请求失败：{combined}")
    if not isinstance(data, dict):
        raise SmsProviderError(f"L 响应不是 JSON 对象：{text[:200]}")
    return data


def _h_url(path: str) -> str:
    base = str(getattr(_cfg, "H_API_BASE", "") or "").strip()
    if not base:
        raise SmsProviderError("H_API_BASE 不能为空")
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def _h_headers() -> dict:
    token = str(getattr(_cfg, "H_ADMIN_AUTH_CODE", "") or "").strip()
    if not token:
        raise SmsProviderError("H_ADMIN_AUTH_CODE 不能为空")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _post_h_json(http: CurlSession, path: str, payload: dict) -> dict:
    resp = http.post(_h_url(path), headers=_h_headers(), data=json.dumps(payload))
    text = (resp.text or "").strip()
    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code != 200:
        msg = data.get("error") if isinstance(data, dict) else ""
        raise SmsProviderError(f"H HTTP {resp.status_code}: {(msg or text)[:200]}")
    if isinstance(data, dict) and data.get("error"):
        error = str(data.get("error") or "")
        raw = str(data.get("raw") or "")
        combined = f"{error} {raw}".strip()
        if "NO_BALANCE" in combined or "余额不足" in combined:
            raise SmsNoBalanceError(f"H 余额不足：{combined}")
        if "NO_NUMBERS" in combined or "暂无号码" in combined:
            raise SmsNoNumbersError(f"H 暂无可用号码：{combined}")
        raise SmsProviderError(f"H 请求失败：{combined}")
    if not isinstance(data, dict):
        raise SmsProviderError(f"H 响应不是 JSON 对象：{text[:200]}")
    return data


def _release_h_number(activation_id: str, http: CurlSession | None = None) -> dict:
    """调用 H_API /api/admin/h/release 释放单个号码。"""
    activation_id = str(activation_id or "").strip()
    if not activation_id:
        raise SmsProviderError("H release 缺少 id")
    own_http = http is None
    http = http or _http()
    try:
        data = _post_h_json(http, "/api/admin/h/release", {"id": activation_id})
        failed = data.get("failed") if isinstance(data, dict) else None
        if isinstance(failed, list) and failed:
            detail = json.dumps(failed, ensure_ascii=False)[:300]
            raise SmsProviderError(f"H release 失败 id={activation_id}: {detail}")
        released = data.get("released", data.get("updated", 0)) if isinstance(data, dict) else 0
        logger.info(f"[SMS:H] 已释放号码 id={activation_id}, released={released}")
        _ACQUIRED_AT.pop(activation_id, None)
        return data
    finally:
        if own_http:
            http.close()


def release_h_numbers(ids: list[str], http: CurlSession | None = None) -> dict:
    """批量释放 H 号码。"""
    ids = [str(x or "").strip() for x in (ids or []) if str(x or "").strip()]
    if not ids:
        raise SmsProviderError("H release 缺少 ids")
    own_http = http is None
    http = http or _http()
    try:
        data = _post_h_json(http, "/api/admin/h/release", {"ids": ids})
        released = data.get("released", data.get("updated", 0)) if isinstance(data, dict) else 0
        failed = data.get("failed") if isinstance(data, dict) else []
        logger.info(f"[SMS:H] 批量释放号码完成 released={released}, failed={len(failed) if isinstance(failed, list) else 0}")
        for activation_id in ids:
            _ACQUIRED_AT.pop(activation_id, None)
        return data
    finally:
        if own_http:
            http.close()


def _release_l_number(activation_id: str, http: CurlSession | None = None) -> dict:
    """调用 L_API /api/admin/l/release 释放单个号码。"""
    activation_id = str(activation_id or "").strip()
    if not activation_id:
        raise SmsProviderError("L release 缺少 id")
    own_http = http is None
    http = http or _http()
    try:
        data = _post_l_json(http, "/api/admin/l/release", {"id": activation_id})
        failed = data.get("failed") if isinstance(data, dict) else None
        if isinstance(failed, list) and failed:
            # 接口允许部分失败。单个释放时 failed 非空基本代表这个 id 释放失败。
            detail = json.dumps(failed, ensure_ascii=False)[:300]
            raise SmsProviderError(f"L release 失败 id={activation_id}: {detail}")
        released = data.get("released", data.get("updated", 0)) if isinstance(data, dict) else 0
        logger.info(f"[SMS:L] 已释放号码 id={activation_id}, released={released}")
        _ACQUIRED_AT.pop(activation_id, None)
        return data
    finally:
        if own_http:
            http.close()


def release_l_numbers(ids: list[str], http: CurlSession | None = None) -> dict:
    """批量释放 L 号码，供工具/后续批处理复用。"""
    ids = [str(x or "").strip() for x in (ids or []) if str(x or "").strip()]
    if not ids:
        raise SmsProviderError("L release 缺少 ids")
    own_http = http is None
    http = http or _http()
    try:
        data = _post_l_json(http, "/api/admin/l/release", {"ids": ids})
        released = data.get("released", data.get("updated", 0)) if isinstance(data, dict) else 0
        failed = data.get("failed") if isinstance(data, dict) else []
        logger.info(f"[SMS:L] 批量释放号码完成 released={released}, failed={len(failed) if isinstance(failed, list) else 0}")
        for activation_id in ids:
            _ACQUIRED_AT.pop(activation_id, None)
        return data
    finally:
        if own_http:
            http.close()


def _normalize_phone_digits(value: str) -> str:
    """把平台返回/配置的号码片段规范化为纯数字，避免 +-849... 这类非法 E.164。"""
    return "".join(ch for ch in str(value or "").strip() if ch.isdigit())


def _normalize_l_phone(phone: str) -> str:
    phone = _normalize_phone_digits(phone)
    prefix = _normalize_phone_digits(getattr(_cfg, "L_PHONE_PREFIX", ""))
    if prefix and phone and not phone.startswith(prefix):
        return f"{prefix}{phone}"
    return phone


def _normalize_h_phone(phone: str) -> str:
    phone = _normalize_phone_digits(phone)
    prefix = _normalize_phone_digits(getattr(_cfg, "H_PHONE_PREFIX", ""))
    if prefix and phone and not phone.startswith(prefix):
        return f"{prefix}{phone}"
    return phone


def _h_phone_acquire_mode() -> str:
    """
    H 取号模式：
      - reusable/reuse/prefer_reuse：优先复用，调用 /api/admin/h/take-reusable-phone
      - new/fresh/always_new：每次取新号，调用 /api/admin/h/take-phone
    """
    raw = str(getattr(_cfg, "H_PHONE_ACQUIRE_MODE", "reusable") or "reusable").strip().lower()
    if raw in ("new", "fresh", "always_new", "take_phone", "take-phone", "每次取新号", "新号"):
        return "new"
    return "reusable"


# ============================================================
# 取号
# ============================================================

def _parse_grizzly_number_response(text: str) -> tuple[str, str, dict]:
    """兼容 getNumberV2 JSON 与旧 getNumber 文本响应。"""
    raw = str(text or "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        data = None

    if isinstance(data, dict):
        activation_id = str(data.get("activationId") or data.get("activation_id") or "").strip()
        phone = str(data.get("phoneNumber") or data.get("phone_number") or "").strip().lstrip("+")
        if not activation_id or not phone:
            raise SmsProviderError(f"getNumberV2 响应缺少 activationId/phoneNumber：{raw[:240]}")
        meta = {
            "activation_time": str(data.get("activationTime") or data.get("activation_time") or "").strip(),
            "activation_cost": data.get("activationCost", data.get("activation_cost")),
            "country_code": str(data.get("countryCode") or data.get("country_code") or "").strip(),
            # 当前官方响应没有这些字段；保留兼容，若平台以后返回即可直接采用。
            "cancel_at_hint": next((data.get(key) for key in (
                "canCancelAt", "cancelAt", "cancelTime", "cancel_at", "cancel_at_time",
            ) if data.get(key) not in (None, "")), None),
            "cancel_after_hint": next((data.get(key) for key in (
                "cancelAfter", "cancelAfterSeconds", "retryAfter", "retry_after",
            ) if data.get(key) not in (None, "")), None),
        }
        return activation_id, phone, meta

    if raw.startswith("ACCESS_NUMBER:"):
        parts = raw.split(":")
        if len(parts) >= 3 and parts[1].strip() and parts[2].strip():
            return parts[1].strip(), parts[2].strip().lstrip("+"), {}
    raise SmsProviderError(f"getNumber 非预期响应：{raw[:240]}")


def _timestamp_hint(value, *, now: float, relative: bool = False) -> float | None:
    """解析接口可能返回的 epoch/毫秒 epoch/ISO 时间或相对秒数。"""
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        number = float(text)
        if relative:
            return now + max(0.0, number)
        if number > 10_000_000_000:
            return number / 1000.0
        if number > 1_000_000_000:
            return number
        return None
    except Exception:
        pass
    if relative:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _planned_cancel_at(meta: dict, acquired_at: float) -> float:
    absolute = _timestamp_hint(meta.get("cancel_at_hint"), now=acquired_at)
    relative = _timestamp_hint(meta.get("cancel_after_hint"), now=acquired_at, relative=True)
    candidate = absolute or relative
    # 防止异常字段把任务安排到过去或遥远未来；正常激活窗口不会超过一天。
    if candidate and acquired_at - 60 <= candidate <= acquired_at + 86400:
        return candidate + 5
    return acquired_at + _GRIZZLY_CANCEL_INITIAL_DELAY


def _retry_at_from_cancel_response(raw: str, now: float) -> float | None:
    """若 EARLY_CANCEL_DENIED 将来携带时间/剩余秒数，直接采用该提示。"""
    text = str(raw or "").strip()
    try:
        data = json.loads(text)
    except Exception:
        data = None
    if isinstance(data, dict):
        absolute = next((data.get(key) for key in (
            "canCancelAt", "cancelAt", "retryAt", "cancel_at", "retry_at",
        ) if data.get(key) not in (None, "")), None)
        relative = next((data.get(key) for key in (
            "retryAfter", "retry_after", "remainingSeconds", "remaining_seconds",
        ) if data.get(key) not in (None, "")), None)
        return _timestamp_hint(absolute, now=now) or _timestamp_hint(relative, now=now, relative=True)
    if text.startswith("EARLY_CANCEL_DENIED:"):
        hint = text.split(":", 1)[1].strip()
        return _timestamp_hint(hint, now=now) or _timestamp_hint(hint, now=now, relative=True)
    return None

def acquire_number(
    http: CurlSession | None = None,
    service: str | None = None,
    country: str | None = None,
) -> tuple[str, str]:
    """
    取一个手机号（getNumber）。

    Returns:
        (activation_id, phone_number) —— phone_number 不带 + 前缀（如 16195366483）

    Raises:
        SmsNoNumbersError / SmsNoBalanceError / SmsProviderError
    """
    own_http = http is None
    http = http or _http()
    try:
        if _provider() == "l":
            payload = {
                "service": service or _cfg.SMS_SERVICE,
                "country": country or _cfg.SMS_COUNTRY,
            }
            if _cfg.SMS_MAX_PRICE:
                payload["maxPrice"] = _cfg.SMS_MAX_PRICE

            data = _post_l_json(http, "/api/admin/l/take-phone", payload)
            item = data.get("item") or {}
            activation_id = str(item.get("id") or "").strip()
            raw_phone = str(item.get("phone") or "")
            raw_prefix = str(getattr(_cfg, "L_PHONE_PREFIX", "") or "")
            phone = _normalize_l_phone(raw_phone)
            if raw_phone.strip() != phone or raw_prefix.strip():
                logger.info(
                    f"[SMS:L] 号码规范化：raw_phone={raw_phone!r}, "
                    f"prefix={raw_prefix!r}, normalized=+{phone}"
                )
            if not activation_id or not phone:
                raise SmsProviderError(f"L take-phone 响应缺少 item.id/item.phone：{str(data)[:200]}")
            _ACQUIRED_AT[activation_id] = time.time()
            logger.info(f"[SMS:L] 取号成功：id={activation_id}, phone=+{phone}")
            return activation_id, phone

        if _provider() == "h":
            # H_API 使用 projectId + country；统一复用 SMS_SERVICE / SMS_COUNTRY，
            # 避免接码平台之间出现重复的“服务/国家”配置。
            project_id = str(service or _cfg.SMS_SERVICE).strip()
            h_country = str(country or _cfg.SMS_COUNTRY).strip()
            if not project_id:
                raise SmsProviderError("H projectId 不能为空：请填写 SMS_SERVICE")
            if not h_country:
                raise SmsProviderError("H country 不能为空：请填写 SMS_COUNTRY")
            payload = {
                "projectId": project_id,
                "country": h_country,
            }
            mode = _h_phone_acquire_mode()
            api_path = "/api/admin/h/take-phone" if mode == "new" else "/api/admin/h/take-reusable-phone"
            data = _post_h_json(http, api_path, payload)
            item = data.get("item") or {}
            activation_id = str(item.get("id") or "").strip()
            raw_phone = str(item.get("phone") or "")
            raw_prefix = str(getattr(_cfg, "H_PHONE_PREFIX", "") or "")
            phone = _normalize_h_phone(raw_phone)
            if raw_phone.strip() != phone or raw_prefix.strip():
                logger.info(
                    f"[SMS:H] 号码规范化：raw_phone={raw_phone!r}, "
                    f"prefix={raw_prefix!r}, normalized=+{phone}"
                )
            if not activation_id or not phone:
                raise SmsProviderError(f"H {api_path.rsplit('/', 1)[-1]} 响应缺少 item.id/item.phone：{str(data)[:200]}")
            _ACQUIRED_AT[activation_id] = time.time()
            logger.info(
                f"[SMS:H] 取号成功：mode={mode}, api={api_path}, id={activation_id}, phone=+{phone}, "
                f"reused={bool(data.get('reused'))}, duplicate={bool(data.get('duplicate'))}"
            )
            return activation_id, phone

        countries = _grizzly_country_candidates(country)
        if not countries:
            raise SmsProviderError("GrizzlySMS country 不能为空：请填写 SMS_COUNTRY")
        global _GRIZZLY_COUNTRY_CURSOR
        with _GRIZZLY_COUNTRY_LOCK:
            start_index = _GRIZZLY_COUNTRY_CURSOR % len(countries)
        ordered = countries[start_index:] + countries[:start_index]
        last_country_error = None
        activation_id = phone = ""
        meta = {}
        chosen_country = ""
        for candidate in ordered:
            params = {
                "action": "getNumberV2",
                "service": service or _cfg.SMS_SERVICE,
                "country": candidate,
            }
            if _cfg.SMS_MAX_PRICE:
                params["maxPrice"] = _cfg.SMS_MAX_PRICE
            try:
                text = _request_grizzly(http, params)
                activation_id, phone, meta = _parse_grizzly_number_response(text)
                chosen_country = candidate
                with _GRIZZLY_COUNTRY_LOCK:
                    _GRIZZLY_COUNTRY_CURSOR = (countries.index(candidate) + 1) % len(countries)
                break
            except (SmsNoNumbersError, SmsPriceLimitError) as exc:
                last_country_error = exc
                if len(ordered) > 1:
                    logger.warning(
                        "[SMS] 国家 %s 暂不可用，自动尝试备用国家：%s",
                        candidate, str(exc)[:180],
                    )
                    continue
                raise
        if not activation_id or not phone:
            raise last_country_error or SmsNoNumbersError("配置的接码国家均暂无可用号码")
        acquired_at = time.time()
        _ACQUIRED_AT[activation_id] = acquired_at
        _ACTIVATION_META[activation_id] = {
            **meta,
            "requested_country": chosen_country,
            "acquired_at": acquired_at,
            "cancel_at": _planned_cancel_at(meta, acquired_at),
        }
        logger.info(
            "[SMS] 取号成功：activation_id=%s, phone=+%s, country=%s, activation_time=%s, planned_cancel_at=%s",
            activation_id,
            phone,
            chosen_country,
            meta.get("activation_time") or "-",
            datetime.fromtimestamp(_ACTIVATION_META[activation_id]["cancel_at"]).isoformat(timespec="seconds"),
        )
        # 取号后立刻登记兜底取消，而不是等业务异常才登记。这样 WebUI 在等待短信时
        # 被重启/杀掉，订单仍会由新进程恢复并在可取消时间到达后回收。
        _enqueue_grizzly_cancel(activation_id, safety_delay=15)
        start_cancel_worker()
        return activation_id, phone
    finally:
        if own_http:
            http.close()


# ============================================================
# 取短信验证码
# ============================================================

def _sms_code_wait_window(activation_id: str, max_wait: int | None = None) -> tuple[int, int]:
    """返回 (配置等待秒数, 实际等待秒数)；Grizzly 会延长到计划取消时间。"""
    configured_wait = int(max_wait or _cfg.SMS_CODE_WAIT)
    total_wait = configured_wait
    if _provider() == "grizzly" and max_wait is None:
        meta = _ACTIVATION_META.get(str(activation_id)) or {}
        cancel_at = float(meta.get("cancel_at") or 0)
        remaining_until_cancel = math.ceil(cancel_at - time.time()) if cancel_at else 0
        total_wait = max(total_wait, remaining_until_cancel)
    return configured_wait, total_wait

def wait_for_sms_code(
    activation_id: str,
    http: CurlSession | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
) -> str:
    """
    轮询 getStatus 直到拿到短信验证码。

    Returns:
        验证码字符串

    Raises:
        SmsCodeTimeout —— 超时没收到（上层可换号重试）
        SmsProviderError —— 激活被取消等
    """
    own_http = http is None
    http = http or _http()
    provider = _provider()
    configured_wait, total_wait = _sms_code_wait_window(activation_id, max_wait)
    # Grizzly 号码在配置的 120s 后仍可能收到迟到验证码。只要这是正常业务调用
    # （未显式传 max_wait），就继续守住当前号码直到计划可取消时间，避免提前换号。
    if total_wait > configured_wait:
        logger.info(
            "[SMS] 启用迟到验证码保护：activation_id=%s configured_wait=%ss effective_wait=%ss，"
            "期间不申请新号码",
            activation_id, configured_wait, total_wait,
        )
    deadline = time.time() + total_wait
    interval = poll_interval or _cfg.SMS_POLL_INTERVAL
    try:
        logger.info(f"[SMS] 等待短信验证码 activation_id={activation_id}，最长 {total_wait}s...")
        round_no = 0
        while time.time() < deadline:
            try:
                from core.registration_service import check_stop_requested
                check_stop_requested()
            except ImportError:
                pass
            round_no += 1
            elapsed = max(0, int(total_wait - max(0, deadline - time.time())))
            remaining_before = max(0, int(deadline - time.time()))
            logger.info(
                f"[SMS] 第 {round_no} 轮获取验证码 activation_id={activation_id}，"
                f"已等 {elapsed}s，剩余约 {remaining_before}s"
            )
            if provider == "l":
                data = _post_l_json(http, "/api/admin/l/fetch-code", {"id": activation_id})
                code = str(data.get("code") or "").strip()
                raw = str(data.get("raw") or "").strip()
                status = str((data.get("item") or {}).get("status") or "").strip()
                if code:
                    logger.info(f"[SMS:L] 第 {round_no} 轮收到验证码：{code}")
                    return code
                remaining = max(0, int(deadline - time.time()))
                logger.info(
                    f"[SMS:L] 第 {round_no} 轮未收到验证码，状态={status or raw or 'WAIT'}，"
                    f"{interval}s 后重试（剩余 {remaining}s）"
                )
                time.sleep(interval)
                continue

            if provider == "h":
                data = _post_h_json(http, "/api/admin/h/fetch-code", {"id": activation_id})
                code = str(data.get("code") or "").strip()
                raw = str(data.get("raw") or "").strip()
                status = str((data.get("item") or {}).get("status") or "").strip()
                if code:
                    logger.info(f"[SMS:H] 第 {round_no} 轮收到验证码：{code}")
                    return code
                remaining = max(0, int(deadline - time.time()))
                logger.info(
                    f"[SMS:H] 第 {round_no} 轮未收到验证码，状态={status or raw or 'WAIT'}，"
                    f"{interval}s 后重试（剩余 {remaining}s）"
                )
                time.sleep(interval)
                continue

            text = _request_grizzly(http, {"action": "getStatus", "id": activation_id})

            if text.startswith("STATUS_OK:"):
                code = text.split(":", 1)[1].strip()
                logger.info(f"[SMS] 第 {round_no} 轮收到验证码：{code}")
                return code
            if text == "STATUS_CANCEL":
                raise SmsProviderError("激活已被取消（STATUS_CANCEL）")
            # STATUS_WAIT_CODE / STATUS_WAIT_RETRY:* / STATUS_WAIT_RESEND → 继续等
            remaining = max(0, int(deadline - time.time()))
            logger.info(f"[SMS] 第 {round_no} 轮未收到验证码，状态={text}，{interval}s 后重试（剩余 {remaining}s）")
            time.sleep(interval)

        # 截止点再查一次，尽量接住恰好在最后一次 sleep 期间到达的迟到验证码。
        if provider == "grizzly":
            text = _request_grizzly(http, {"action": "getStatus", "id": activation_id})
            if text.startswith("STATUS_OK:"):
                code = text.split(":", 1)[1].strip()
                logger.info("[SMS] 截止取消前收到迟到验证码：activation_id=%s code=%s", activation_id, code)
                return code
            if text == "STATUS_CANCEL":
                raise SmsProviderError("激活已被取消（STATUS_CANCEL）")
        raise SmsCodeTimeout(
            f"等待短信超时（configured={configured_wait}s effective={total_wait}s），activation_id={activation_id}"
        )
    finally:
        if own_http:
            http.close()


# ============================================================
# 改状态
# ============================================================

def set_status(activation_id: str, status: int, http: CurlSession | None = None) -> str:
    """
    设置激活状态（setStatus）。
        1 = 号码已就绪（短信已发出）
        3 = 等下一条短信（重发）
        6 = 完成激活
        8 = 取消激活
    """
    own_http = http is None
    http = http or _http()
    try:
        if _provider() == "l":
            logger.debug(f"[SMS:L] 忽略状态设置 id={activation_id}, status={status}")
            return "OK"
        return _request_grizzly(http, {"action": "setStatus", "status": str(status), "id": activation_id})
    finally:
        if own_http:
            http.close()


def complete(activation_id: str, http: CurlSession | None = None) -> None:
    """标记激活完成（status=6）。失败只告警不抛，避免影响主流程。"""
    if _provider() == "l":
        logger.info(f"[SMS:L] 已完成 id={activation_id}")
        _ACQUIRED_AT.pop(activation_id, None)
        _ACTIVATION_META.pop(activation_id, None)
        return
    if _provider() == "h":
        # H 成功 fetch-code 后后台会自动按多次收码策略重取；这里不 release。
        logger.info(f"[SMS:H] 已完成 id={activation_id}")
        _ACQUIRED_AT.pop(activation_id, None)
        _ACTIVATION_META.pop(activation_id, None)
        return
    try:
        set_status(activation_id, 6, http=http)
        logger.info(f"[SMS] 已标记完成 activation_id={activation_id}")
        _remove_grizzly_cancel(activation_id)
        _ACQUIRED_AT.pop(activation_id, None)
        _ACTIVATION_META.pop(activation_id, None)
    except Exception as exc:
        logger.warning(f"[SMS] 标记完成失败（不影响结果）：{exc}")


def _load_cancel_queue_locked() -> list[dict]:
    try:
        raw = json.loads(_CANCEL_QUEUE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.warning("[SMS] 读取取消队列失败：%s", exc)
        return []
    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict) and str(item.get("activation_id") or "").strip()]


def _save_cancel_queue_locked(items: list[dict]) -> None:
    _CANCEL_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CANCEL_QUEUE_PATH.with_suffix(".tmp")
    payload = {"version": 1, "items": items, "updated_at": time.time()}
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _CANCEL_QUEUE_PATH)


def _cancel_backoff(values: tuple[int, ...], attempt: int) -> int:
    index = max(0, min(int(attempt) - 1, len(values) - 1))
    return int(values[index])


def _remove_grizzly_cancel(activation_id: str) -> bool:
    activation_id = str(activation_id or "").strip()
    with _CANCEL_QUEUE_LOCK:
        items = _load_cancel_queue_locked()
        remaining = [item for item in items if str(item.get("activation_id")) != activation_id]
        removed = len(remaining) != len(items)
        if removed:
            _save_cancel_queue_locked(remaining)
    if removed:
        _CANCEL_WAKE_EVENT.set()
    return removed


def _enqueue_grizzly_cancel(activation_id: str, *, safety_delay: int = 0) -> dict:
    activation_id = str(activation_id or "").strip()
    now = time.time()
    meta = dict(_ACTIVATION_META.get(activation_id) or {})
    acquired_at = float(meta.get("acquired_at") or _ACQUIRED_AT.get(activation_id) or now)
    cancel_at = float(meta.get("cancel_at") or (acquired_at + _GRIZZLY_CANCEL_INITIAL_DELAY))
    next_attempt_at = cancel_at + max(0, int(safety_delay or 0))
    with _CANCEL_QUEUE_LOCK:
        items = _load_cancel_queue_locked()
        existing = next((item for item in items if str(item.get("activation_id")) == activation_id), None)
        if existing is None:
            existing = {
                "activation_id": activation_id,
                "activation_time": str(meta.get("activation_time") or ""),
                "acquired_at": acquired_at,
                "cancel_at": cancel_at,
                "next_attempt_at": next_attempt_at,
                "attempts": 0,
                "early_denied_count": 0,
                "last_result": "scheduled",
            }
            items.append(existing)
            _save_cancel_queue_locked(items)
        result = dict(existing)
    _CANCEL_WAKE_EVENT.set()
    logger.info(
        "[SMS] 已记录待取消订单：activation_id=%s activation_time=%s cancel_at=%s",
        activation_id,
        result.get("activation_time") or "-",
        datetime.fromtimestamp(float(result["next_attempt_at"])).isoformat(timespec="seconds"),
    )
    return result


def _cancel_grizzly_once(activation_id: str) -> tuple[str, str]:
    """只发送一次取消请求；返回 (outcome, raw)。"""
    http = _http()
    try:
        raw = _request_grizzly(http, {
            "action": "setStatus",
            "status": "8",
            "id": activation_id,
        })
        if raw == "ACCESS_CANCEL":
            return "cancelled", raw
        if raw == "EARLY_CANCEL_DENIED" or raw.startswith("EARLY_CANCEL_DENIED:"):
            return "early", raw
        # 有些兼容实现可能直接返回最终状态。
        if raw == "STATUS_CANCEL":
            return "cancelled", raw
        return "unexpected", raw
    except Exception as exc:
        if "NO_ACTIVATION" in str(exc) or "激活 ID 不存在" in str(exc):
            return "gone", f"{type(exc).__name__}: {exc}"
        return "error", f"{type(exc).__name__}: {exc}"
    finally:
        try:
            http.close()
        except Exception:
            pass


def _update_cancel_job_after_attempt(activation_id: str, outcome: str, raw: str) -> bool:
    """更新持久化任务；返回 True 表示订单已取消并从队列移除。"""
    now = time.time()
    with _CANCEL_QUEUE_LOCK:
        items = _load_cancel_queue_locked()
        job = next((item for item in items if str(item.get("activation_id")) == activation_id), None)
        if job is None:
            return outcome == "cancelled"
        job["attempts"] = int(job.get("attempts") or 0) + 1
        job["last_attempt_at"] = now
        job["last_result"] = raw[:300]
        if outcome in ("cancelled", "gone"):
            items.remove(job)
            _save_cancel_queue_locked(items)
            _ACQUIRED_AT.pop(activation_id, None)
            _ACTIVATION_META.pop(activation_id, None)
            if outcome == "cancelled":
                logger.info("[SMS] 已取消 activation_id=%s response=%s", activation_id, raw)
            else:
                logger.info("[SMS] 订单已自然终止，无需再取消：activation_id=%s response=%s", activation_id, raw)
            return True

        if outcome == "early":
            count = int(job.get("early_denied_count") or 0) + 1
            job["early_denied_count"] = count
            retry_at = _retry_at_from_cancel_response(raw, now)
            if retry_at and retry_at > now:
                job["next_attempt_at"] = retry_at + 5
                delay = max(1, int(job["next_attempt_at"] - now))
                reason = "平台返回可取消时间"
            else:
                delay = _cancel_backoff(_GRIZZLY_CANCEL_EARLY_BACKOFF, count)
                job["next_attempt_at"] = now + delay
                reason = "平台尚未开放取消"
        else:
            count = int(job.get("error_count") or 0) + 1
            job["error_count"] = count
            delay = _cancel_backoff(_GRIZZLY_CANCEL_ERROR_BACKOFF, count)
            reason = "取消请求异常" if outcome == "error" else "取消响应未确认"
            job["next_attempt_at"] = now + delay
        _save_cancel_queue_locked(items)
        logger.warning(
            "[SMS] %s，已持久化并延后 %ss 再尝试：activation_id=%s response=%s",
            reason, delay, activation_id, raw[:220],
        )
        return False


def _cancel_worker_loop() -> None:
    global _CANCEL_WORKER
    try:
        while True:
            with _CANCEL_QUEUE_LOCK:
                items = _load_cancel_queue_locked()
                job = min(items, key=lambda item: float(item.get("next_attempt_at") or 0)) if items else None
            if job is None:
                return
            wait = max(0.0, float(job.get("next_attempt_at") or 0) - time.time())
            if wait > 0:
                _CANCEL_WAKE_EVENT.wait(timeout=min(wait, 60.0))
                _CANCEL_WAKE_EVENT.clear()
                continue
            activation_id = str(job.get("activation_id") or "")
            outcome, raw = _cancel_grizzly_once(activation_id)
            _update_cancel_job_after_attempt(activation_id, outcome, raw)
    finally:
        restart_needed = False
        with _CANCEL_WORKER_LOCK:
            _CANCEL_WORKER = None
            with _CANCEL_QUEUE_LOCK:
                restart_needed = bool(_load_cancel_queue_locked())
        # 关闭与新任务入队恰好并发时，重新拉起 worker，避免任务留在队列无人处理。
        if restart_needed:
            start_cancel_worker()


def start_cancel_worker() -> None:
    """恢复并启动 Grizzly 持久化取消队列；没有任务时立即退出。"""
    global _CANCEL_WORKER
    with _CANCEL_WORKER_LOCK:
        if _CANCEL_WORKER is not None and _CANCEL_WORKER.is_alive():
            _CANCEL_WAKE_EVENT.set()
            return
        _CANCEL_WORKER = threading.Thread(
            target=_cancel_worker_loop,
            name="sms-cancel-worker",
            daemon=True,
        )
        _CANCEL_WORKER.start()


def _cancel_job_exists(activation_id: str) -> bool:
    with _CANCEL_QUEUE_LOCK:
        return any(str(item.get("activation_id")) == str(activation_id) for item in _load_cancel_queue_locked())


def _do_cancel_sync(activation_id: str) -> None:
    """同步等待持久化 worker 确认订单终止；本线程不重复发送 API 请求。"""
    _enqueue_grizzly_cancel(activation_id)
    start_cancel_worker()
    while _cancel_job_exists(activation_id):
        with _CANCEL_QUEUE_LOCK:
            job = next(
                (item for item in _load_cancel_queue_locked() if str(item.get("activation_id")) == str(activation_id)),
                None,
            )
        if job is None:
            return
        wait = max(0.0, float(job.get("next_attempt_at") or 0) - time.time())
        # 这里只等本地队列状态；真正的取消请求始终由单一 worker 发送。
        time.sleep(max(0.25, min(wait if wait > 0 else 0.5, 5.0)))


def cancel(activation_id: str, http: CurlSession | None = None, background: bool = True) -> None:
    """
    取消激活（status=8），释放号码避免白扣费。

    GrizzlySMS 不返回精确可取消时间。程序会记录 getNumberV2 的 activationTime、
    本地取号时间和计划取消时间到 run/sms_cancel_queue.json，并由单一后台 worker
    到点发起取消；EARLY_CANCEL_DENIED 会低频退避，不做高频轮询。

    WebUI 重启时会恢复未完成队列。background=False 时同步等到确认取消后返回。

    失败只告警不抛，不影响主流程。
    """
    if _provider() == "l":
        try:
            _release_l_number(activation_id, http=http)
        except Exception as exc:
            logger.warning(f"[SMS:L] 释放号码失败（不影响主流程）：id={activation_id}, {type(exc).__name__}: {exc}")
            _ACQUIRED_AT.pop(activation_id, None)
            _ACTIVATION_META.pop(activation_id, None)
        return
    if _provider() == "h":
        try:
            _release_h_number(activation_id, http=http)
        except Exception as exc:
            logger.warning(f"[SMS:H] 释放号码失败（不影响主流程）：id={activation_id}, {type(exc).__name__}: {exc}")
            _ACQUIRED_AT.pop(activation_id, None)
            _ACTIVATION_META.pop(activation_id, None)
        return

    if not background:
        _do_cancel_sync(activation_id)
        return
    _enqueue_grizzly_cancel(activation_id)
    start_cancel_worker()
    logger.debug("[SMS] 取消任务已进入持久化队列：activation_id=%s", activation_id)
