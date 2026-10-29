# -*- coding: utf-8 -*-
"""Plus 试用提链后台队列。"""
from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

try:
    from curl_cffi import requests as curl_requests
except Exception:  # WebUI 环境未装 curl_cffi 时使用标准库兜底
    curl_requests = None

from config import extract_link as cfg
from config.schema import get_config_snapshot, validate_value
from core import db
from core.operation_runtime import OperationCancelled
from core import task_run_log
from core.account_operation_executor import configured_workers
from core.operations import task_gateway as account_task_store
from core.task_reporter import TaskReporter

logger = logging.getLogger(__name__)
_WORKBENCH_PROCESS_STARTED_AT = datetime.now(timezone.utc)
_RUNTIME_ENV_LOAD_LOCK = threading.RLock()
_RUNTIME_ENV_SIGNATURE = None
_HUANGUANG_QUOTA_LOCK = threading.RLock()
_HUANGUANG_QUOTA_BLOCKS = {}
_HUANGUANG_QUOTA_INFLIGHT = {}
_HUANGUANG_QUOTA_ADMITTED = {}
_HUANGUANG_QUOTA_STAGES = {
    "quota_extraction_exhausted": "提链 CDK 次数已用完，等待补充额度",
    "quota_payment_exhausted": "支付扫码 CDK 次数已用完，等待补充额度",
    "quota_extraction_disabled": "提链 CDK 已停用，等待更新配置",
    "quota_payment_disabled": "支付扫码 CDK 已停用，等待更新配置",
    "quota_unavailable": "CDK 额度暂无法确认，等待重新查询",
    "quota_local_reserved": "CDK 可用次数已分配给正在提交的任务，等待额度释放",
}


class ExtractCreateRejected(RuntimeError):
    """远端明确拒绝创建提链任务；只保留安全的 HTTP 状态码。"""

    def __init__(self, http_status: int):
        self.http_status = int(http_status)
        self.response_observed = True
        super().__init__(f"提链创建请求被远端拒绝（HTTP {self.http_status}）")


class ExtractCreateResponseUnknown(RuntimeError):
    """创建请求已有响应，但尚无法确认远端任务标识。"""

    def __init__(self, http_status: int, *, failure_kind: str = "missing_job_id"):
        self.http_status = int(http_status)
        self.response_observed = True
        self.failure_kind = failure_kind
        message = (
            "提链服务响应缺少可确认的 job_id，结果待确认"
            if failure_kind == "missing_job_id"
            else "提链服务响应格式异常，结果待确认"
            if failure_kind == "invalid_json"
            else f"提链创建请求 HTTP {self.http_status}，结果待确认"
        )
        super().__init__(message)


def _create_http_rejected(status: int) -> bool:
    # 408/409/425/429 仍可能对应超时、并发或限流中的未明结果。
    return 400 <= status < 500 and status not in {408, 409, 425, 429}


# API endpoint and timing are non-sensitive inputs needed by the durable
# worker.  The CDK remains an on-demand secret and is deliberately excluded.
EXTRACT_CONFIG_ALLOWLIST = {
    "api_base": "EXTRACT_LINK_API_BASE",
    "link_type": "EXTRACT_LINK_TYPE",
    "request_timeout": "EXTRACT_LINK_REQUEST_TIMEOUT",
    "event_timeout": "EXTRACT_LINK_EVENT_TIMEOUT",
    "refresh_driver": "ACCOUNT_AT_REFRESH_DRIVER",
    "refresh_protocol_version": "OPENAI_PROTOCOL_VERSION",
    "refresh_roxy_debug_enabled": "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED",
}


def _snapshot_value(snapshot, key: str, default=None):
    if isinstance(snapshot, dict) and key in snapshot:
        return snapshot[key]
    return default


def _captured_int(
    snapshot: dict | None,
    key: str,
    setting_name: str,
    default: int,
    lower: int,
    upper: int,
) -> int:
    if snapshot is None:
        return _int_setting(setting_name, default, lower, upper)
    value = _snapshot_value(snapshot, key, default)
    try:
        value = int(value or default)
    except (TypeError, ValueError):
        value = default
    return max(lower, min(value, upper))


class _ReporterAdapter:
    """Route the existing extract progress vocabulary to a durable Run."""

    def __init__(self, task_id: int | None, context=None):
        self._legacy = TaskReporter(task_id) if context is None else None
        self._context = context

    def start(self, message: str = "开始执行") -> None:
        if self._context is None:
            self._legacy.start(message)
        else:
            self._context.report(stage="preflight", message=message)

    def stage(self, stage: str, state: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.stage(stage, state, message, **kwargs)
        else:
            self._context.report(stage=stage, state=state, message=message, **kwargs)

    def note(self, message: str, *, stage: str = "event", **kwargs) -> None:
        if self._context is None:
            self._legacy.note(message, stage=stage, **kwargs)
        else:
            self._context.report(stage=stage, message=message, **kwargs)

    def finish(self, *, status: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.finish(status=status, message=message, **kwargs)
            return
        summary = dict(kwargs.get("result_summary") or {})
        for key in ("route", "validation_method"):
            if kwargs.get(key) is not None:
                summary[key] = kwargs[key]
        self._context.finish(
            status=status,
            message=message,
            error=kwargs.get("error"),
            result_summary=summary,
        )


def _checkpoint(context, message: str = "用户手动停止提链任务") -> None:
    if context is not None:
        context.checkpoint(message)


def _runtime_setting(name: str, default=None):
    """
    提链配置多数保存在 .env。服务模块会在 WebUI 启动时较早 import，
    因此首次读取及 .env 变更后重新加载，避免“页面已保存但当前进程仍读到空值”。
    """
    global _RUNTIME_ENV_SIGNATURE
    try:
        from config.env_loader import dotenv_loading_disabled, env_file_lock, env_path, load_env

        path = env_path()

        def current_signature():
            try:
                stat = path.stat()
            except FileNotFoundError:
                file_signature = (False,)
            except OSError:
                return None
            else:
                file_signature = (
                    stat.st_dev,
                    stat.st_ino,
                    stat.st_size,
                    stat.st_mtime_ns,
                    stat.st_ctime_ns,
                )
            return file_signature, dotenv_loading_disabled()

        signature = current_signature()
        if signature is None or signature != _RUNTIME_ENV_SIGNATURE:
            with _RUNTIME_ENV_LOAD_LOCK:
                signature = current_signature()
                if signature is None or signature != _RUNTIME_ENV_SIGNATURE:
                    try:
                        with env_file_lock():
                            before_load = current_signature()
                            if before_load is None or before_load != _RUNTIME_ENV_SIGNATURE:
                                load_env(override=True)
                                after_load = current_signature()
                                if before_load is not None and after_load == before_load:
                                    _RUNTIME_ENV_SIGNATURE = after_load
                    except Exception:
                        pass
    except Exception:
        pass
    raw = os.getenv(name)
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip()
    return getattr(cfg, name, default)


def _int_setting(name: str, default: int, lower: int, upper: int) -> int:
    try:
        value = int(_runtime_setting(name, default) or default)
    except (TypeError, ValueError):
        value = default
    return max(lower, min(upper, value))


_PROVIDER_SETTINGS = {
    "legacy": {
        "label": "虾扯蛋链",
        "prefix": "EXTRACT_LINK_LEGACY",
        "config_prefix": "EXTRACT_LINK",
        "concurrency_key": "EXTRACT_LINK_LEGACY_CONCURRENCY",
        "supports": {"extract_only": True, "manual_payment": True, "auto_payment": True},
    },
    "lumen_flow": {
        "label": "Lumen Flow",
        "prefix": "EXTRACT_LINK_LUMEN_FLOW",
        "concurrency_key": "EXTRACT_LINK_LUMEN_FLOW_CONCURRENCY",
        "supports": {"extract_only": True, "manual_payment": True, "auto_payment": True},
    },
    "huanguang": {
        "label": "幻光",
        "prefix": "EXTRACT_LINK_HUANGUANG",
        "concurrency_key": "EXTRACT_LINK_HUANGUANG_CONCURRENCY",
        "supports": {"extract_only": True, "manual_payment": True, "auto_payment": True},
    },
}


def _bool_setting(name: str, default: bool = False) -> bool:
    value = _runtime_setting(name, default)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _valid_provider_base(value: object) -> str:
    base = str(value or "").strip().rstrip("/")
    try:
        parsed = urlsplit(base)
    except ValueError:
        parsed = None
    if (
        not parsed
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return ""
    return base


def _provider_enabled(provider_id: str) -> bool:
    provider = _PROVIDER_SETTINGS.get(str(provider_id or "").strip())
    if not provider or not _bool_setting("EXTRACT_LINK_ENABLED", True):
        return False
    return _bool_setting(f"{provider['prefix']}_ENABLED", provider_id == "legacy")


def _provider_mode_enabled(provider_id: str, mode: str) -> bool:
    provider = _PROVIDER_SETTINGS.get(str(provider_id or "").strip())
    if not provider or not _provider_enabled(provider_id):
        return False
    if not provider["supports"].get(mode, False):
        return False
    if provider_id in {"legacy", "huanguang"} and mode == "auto_payment" and not str(
        _runtime_setting(f"EXTRACT_LINK_{provider_id.upper()}_PAYMENT_CDK", "") or ""
    ).strip():
        return False
    if mode != "extract_only" and not (
        _bool_setting("EXTRACT_LINK_EXTRACT_ENABLED", True)
        and _bool_setting(f"{provider['prefix']}_EXTRACT_ENABLED", provider_id == "legacy")
    ):
        return False
    global_key, provider_key = {
        "extract_only": ("EXTRACT_LINK_EXTRACT_ENABLED", f"{provider['prefix']}_EXTRACT_ENABLED"),
        "manual_payment": (
            "EXTRACT_LINK_MANUAL_PAYMENT_ENABLED",
            f"{provider['prefix']}_MANUAL_PAYMENT_ENABLED",
        ),
        "auto_payment": (
            "EXTRACT_LINK_AUTO_PAYMENT_ENABLED",
            f"{provider['prefix']}_AUTO_PAYMENT_ENABLED",
        ),
    }.get(mode, ("", ""))
    return bool(
        global_key
        and _bool_setting(global_key, mode == "extract_only")
        and _bool_setting(provider_key, mode == "extract_only" and provider_id == "legacy")
    )


def _provider_configuration(provider_id: str):
    from core.extract_link_providers.contracts import ProviderConfig

    provider_id = str(provider_id or "").strip().lower()
    settings = _PROVIDER_SETTINGS.get(provider_id)
    if not settings:
        raise ValueError("未知提链平台")
    prefix = settings["prefix"]
    if not _bool_setting("EXTRACT_LINK_ENABLED", True):
        raise ValueError("提链工作台已关闭")
    if not _bool_setting(f"{prefix}_ENABLED", provider_id == "legacy"):
        raise ValueError("提链平台未启用")
    config_prefix = settings.get("config_prefix", prefix)
    api_base = _valid_provider_base(_runtime_setting(f"{config_prefix}_API_BASE", ""))
    cdk = str(_runtime_setting(f"{config_prefix}_CDK", "") or "").strip()
    if not api_base or not cdk:
        raise ValueError("提链平台 API 地址或 CDK 未配置")
    default_type = str(_runtime_setting(f"{config_prefix}_DEFAULT_TYPE", "") or "").strip().lower()
    if provider_id == "legacy":
        default_type = str(_runtime_setting("EXTRACT_LINK_TYPE", "pix") or "pix").strip().lower()
    if default_type not in SUPPORTED_LINK_TYPES:
        default_type = "pix"
    if provider_id == "huanguang":
        # 兼容旧版配置写入的 pix；当前平台仅开放 UPI。
        default_type = "upi"
    timeout = _int_setting(f"{config_prefix}_REQUEST_TIMEOUT", 30, 5, 300)
    event_timeout = _int_setting(f"{config_prefix}_EVENT_TIMEOUT", 180, 30, 900)
    poll_interval = _int_setting(f"{config_prefix}_POLL_INTERVAL", 5, 1, 60)
    capabilities = {
        "extract": _provider_mode_enabled(provider_id, "extract_only"),
        "payment": (
            _provider_mode_enabled(provider_id, "manual_payment")
            or _provider_mode_enabled(provider_id, "auto_payment")
        ),
        "auto_payment": _provider_mode_enabled(provider_id, "auto_payment"),
    }
    config = ProviderConfig(
        provider_id=provider_id,
        api_base=api_base,
        cdk=cdk,
        capabilities=capabilities,
        concurrency=_int_setting(settings["concurrency_key"], 1, 1, 32),
        timeout=timeout,
        payment_cdk=(str(_runtime_setting(f"EXTRACT_LINK_{provider_id.upper()}_PAYMENT_CDK", "") or "").strip()
                     if provider_id in {"legacy", "huanguang"} else ""),
        xxsyun_api_key=(str(_runtime_setting("EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY", "") or "").strip()
                        if provider_id == "huanguang" else ""),
        scan_fallback_enabled=(
            provider_id == "huanguang"
            and _bool_setting("EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED", False)
        ),
    )
    return SimpleNamespace(
        config=config,
        api_base=api_base,
        cdk=cdk,
        default_type=default_type,
        timeout=timeout,
        poll_interval=poll_interval,
        event_timeout=event_timeout,
        capabilities=capabilities,
    )


class _ProviderHTTPTransport:
    """Adapter transport; responses and errors never include request secrets."""

    def __init__(self, runtime_config):
        self.runtime_config = runtime_config

    def request(self, method, path, *, json=None, headers=None, timeout=30):
        deadline = getattr(self, "deadline", None)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("平台监控等待时间已到")
            timeout = min(float(timeout), remaining)
        url = f"{self.runtime_config.api_base}/{str(path or '').lstrip('/')}"
        safe_headers = {"Accept": "application/json", **dict(headers or {})}
        if curl_requests is not None:
            return curl_requests.request(
                str(method).upper(), url, json=json, headers=safe_headers,
                timeout=timeout,
            )
        body = None if json is None else __import__("json").dumps(json).encode("utf-8")
        request = Request(url, data=body, headers=safe_headers, method=str(method).upper())
        try:
            with urlopen(request, timeout=timeout) as response:
                content = response.read()
                status = int(getattr(response, "status", 200) or 200)
        except HTTPError as exc:
            content = exc.read()
            status = int(getattr(exc, "code", 0) or 0)
        try:
            payload = __import__("json").loads(content.decode("utf-8", "replace") or "{}")
        except (TypeError, ValueError):
            payload = None
        return SimpleNamespace(status_code=status, json=lambda: payload)

    def events(self, path, *, timeout=None):
        parsed = urlsplit(str(path or ""))
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 4 or parts[-1] != "events":
            raise RuntimeError("提链任务事件路径无效")
        job_id = unquote(parts[-2])
        return _iter_sse_events(
            job_id=job_id,
            cdk=self.runtime_config.cdk,
            api_base=self.runtime_config.api_base,
            event_timeout=self.runtime_config.event_timeout,
        )


def _provider(provider_id: str, runtime_config=None):
    from core.extract_link_providers import get_provider

    runtime_config = runtime_config or _provider_configuration(provider_id)
    return get_provider(
        provider_id,
        config=runtime_config.config,
        transport=_ProviderHTTPTransport(runtime_config),
    )


def workbench_config() -> dict:
    """返回工作台可选择的平台与模式，不包含密钥或 API 凭据。"""
    providers = []
    unavailable_providers = []
    if _bool_setting("EXTRACT_LINK_ENABLED", True):
        for provider_id, settings in _PROVIDER_SETTINGS.items():
            if not _provider_enabled(provider_id):
                continue
            try:
                runtime_config = _provider_configuration(provider_id)
            except ValueError as exc:
                message = str(exc)
                if message == "提链平台 API 地址或 CDK 未配置":
                    config_prefix = settings.get("config_prefix", settings["prefix"])
                    missing = []
                    if not _valid_provider_base(_runtime_setting(f"{config_prefix}_API_BASE", "")):
                        missing.append("API 地址")
                    if not str(_runtime_setting(f"{config_prefix}_CDK", "") or "").strip():
                        missing.append("CDK")
                    if missing == ["API 地址", "CDK"]:
                        reason = "缺少API地址和平台授权信息"
                    elif missing == ["API 地址"]:
                        reason = "缺少API地址"
                    elif missing == ["CDK"]:
                        reason = "缺少平台授权信息"
                    else:
                        reason = "连接配置无效"
                else:
                    reason = "平台配置暂不可用"
                unavailable_providers.append({
                    "id": provider_id,
                    "label": settings["label"],
                    "unavailable_reason": reason,
                })
                continue
            except TypeError:
                continue
            modes = [
                mode for mode in ("extract_only", "manual_payment", "auto_payment")
                if _provider_mode_enabled(provider_id, mode)
            ]
            if provider_id == "lumen_flow" and runtime_config.default_type != "momo":
                modes = [mode for mode in modes if mode != "auto_payment"]
            if provider_id == "legacy" and runtime_config.default_type != "upi":
                modes = [mode for mode in modes if mode != "auto_payment"]
            if not modes:
                unavailable_providers.append({
                    "id": provider_id,
                    "label": settings["label"],
                    "unavailable_reason": "未启用可用运行模式",
                })
                continue
            providers.append({
                "id": provider_id,
                "label": settings["label"],
                "default_type": runtime_config.default_type,
                "link_types": _provider_link_types(provider_id),
                "modes": modes,
            })
    default_provider = str(_runtime_setting("EXTRACT_LINK_DEFAULT_PROVIDER", "legacy") or "legacy").strip()
    if not any(item["id"] == default_provider for item in providers):
        default_provider = providers[0]["id"] if providers else ""
    provider = next((item for item in providers if item["id"] == default_provider), None)
    configured_mode = str(_runtime_setting("EXTRACT_LINK_DEFAULT_MODE", "extract_only") or "extract_only").strip()
    default_mode = configured_mode if provider and configured_mode in provider["modes"] else ""
    if provider and not default_mode:
        default_mode = "extract_only" if "extract_only" in provider["modes"] else provider["modes"][0]
    return {
        "batch_workers_default": _int_setting("EXTRACT_LINK_BATCH_WORKERS", 1, 1, 16),
        "batch_workers_max": 16,
        "default_provider": default_provider,
        "default_mode": default_mode,
        "providers": providers,
        "unavailable_providers": unavailable_providers,
    }


SUPPORTED_LINK_TYPES = {
    "pix",
    "gopay",
    "upi",
    "ideal",
    "ideal_short",
    "kakao_pay",
    "momo",
    "gcash",
    "paypal",
    "ph_short",
}

DEFAULT_LINK_TYPE_ORDER = (
    "pix",
    "gopay",
    "upi",
    "kakao_pay",
    "momo",
    "gcash",
    "paypal",
    "ideal",
    "ideal_short",
    "ph_short",
)

def _provider_link_types(provider_id: str) -> list[str]:
    """返回服务端可校验的平台提链类型选项。"""
    provider_id = str(provider_id or "").strip().lower()
    if provider_id == "huanguang":
        return ["upi"]
    if provider_id == "lumen_flow":
        return [value for value in DEFAULT_LINK_TYPE_ORDER if value not in {"ideal_short", "ph_short"}]
    return list(DEFAULT_LINK_TYPE_ORDER)


def _link_type(value: str | None = None) -> str:
    t = str(value or _runtime_setting("EXTRACT_LINK_TYPE", "pix") or "pix").strip().lower()
    if t not in SUPPORTED_LINK_TYPES:
        raise ValueError("提链类型无效，请从网站当前启用类型中选择")
    return t


def _failed_link_types(account: dict | None) -> set[str]:
    value = (account or {}).get("extract_link_failed_types")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = []
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {
        str(item or "").strip().lower()
        for item in value
        if str(item or "").strip().lower() in SUPPORTED_LINK_TYPES
    }


def _enabled_link_type_order() -> tuple[str, ...]:
    """按网站当前顺序返回启用类型，远端不可用时使用文档顺序。"""
    try:
        items = query_link_types().get("items") or []
        remote = []
        for item in items:
            if not isinstance(item, dict):
                continue
            value = str(item.get("type") or "").strip().lower()
            if (
                value in SUPPORTED_LINK_TYPES
                and item.get("visible", True) is not False
                and item.get("enabled", True) is not False
                and value not in remote
            ):
                remote.append(value)
        if remote:
            return tuple(remote)
    except Exception as exc:
        logger.warning("读取提链类型失败，使用备用顺序：%s", type(exc).__name__)
    return DEFAULT_LINK_TYPE_ORDER


def _select_account_link_type(*, account: dict, requested: str | None) -> tuple[str, str | None]:
    """账号已失败当前类型时，按网站启用顺序切换其它类型。"""
    selected = _link_type(requested)
    failed = _failed_link_types(account)
    if selected not in failed:
        return selected, None
    for candidate in _enabled_link_type_order():
        if candidate not in failed:
            return candidate, selected
    raise ValueError("该账号已记录所有当前启用提链类型均失败，请更换账号或清理失败标记")


def _api_base(override: str | None = None) -> str:
    base = str(
        override if override is not None else _runtime_setting("EXTRACT_LINK_API_BASE", "")
        or ""
    ).strip().rstrip("/")
    if not base:
        raise ValueError("EXTRACT_LINK_API_BASE 为空")
    return base


def _cdk(value: str | None = None) -> str:
    cdk = str(value or _runtime_setting("EXTRACT_LINK_CDK", "") or "").strip()
    if not cdk:
        raise ValueError("EXTRACT_LINK_CDK/CDK 为空")
    return cdk


_QUEUE_LIMIT = _int_setting("EXTRACT_LINK_QUEUE_LIMIT", 500, configured_workers(), 5000)
_QUEUE_SLOTS = threading.BoundedSemaphore(_QUEUE_LIMIT)


def queue_settings() -> dict:
    return {"workers": configured_workers(), "queue_limit": _QUEUE_LIMIT}


def _session():
    if curl_requests is None:
        return None
    return curl_requests.Session()


def query_cdk(*, cdk: str | None = None) -> dict:
    base = _api_base()
    code = _cdk(cdk)
    timeout = _int_setting("EXTRACT_LINK_REQUEST_TIMEOUT", 30, 5, 300)
    s = _session()
    try:
        if s is None:
            req = Request(f"{base}/api/cdk?{urlencode({'code': code})}", headers={"Accept": "application/json"})
            with urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            return payload if isinstance(payload, dict) else {}
        resp = s.get(f"{base}/api/cdk?{urlencode({'code': code})}", timeout=timeout)
        try:
            payload = resp.json()
        except Exception:
            payload = {"error": (resp.text or "")[:300]}
        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(payload.get("error") or f"HTTP {resp.status_code}")
        return payload if isinstance(payload, dict) else {}
    finally:
        try:
            s.close()
        except Exception:
            pass


def query_link_types() -> dict:
    """读取提链站点当前公开的类型开关；该接口不需要 CDK。"""
    base = _api_base()
    timeout = _int_setting("EXTRACT_LINK_REQUEST_TIMEOUT", 30, 5, 300)
    s = _session()
    try:
        if s is None:
            req = Request(f"{base}/api/link-types", headers={"Accept": "application/json"})
            with urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        else:
            resp = s.get(f"{base}/api/link-types", timeout=timeout)
            try:
                payload = resp.json()
            except Exception:
                payload = {"error": (resp.text or "")[:300]}
            if resp.status_code < 200 or resp.status_code >= 300:
                raise RuntimeError(payload.get("error") or f"HTTP {resp.status_code}")
        if not isinstance(payload, dict):
            raise RuntimeError("提链服务返回的类型列表格式无效")
        items = payload.get("items")
        if not isinstance(items, list):
            raise RuntimeError("提链服务未返回类型列表")
        return {"ok": bool(payload.get("ok", True)), "items": items}
    finally:
        try:
            s.close()
        except Exception:
            pass


def query_huanguang_xxsyun_quota(api_key: str | None = None) -> dict:
    """只读查询备用扫码次数；草稿 Key 不写入配置或任务数据。"""
    from core.extract_link_providers.huanguang import HuanguangQuotaError, query_quota_response

    key = (_runtime_setting("EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY", "")
           if api_key is None else api_key)
    if key is None or (isinstance(key, str) and not key.strip()):
        raise HuanguangQuotaError("key_missing")
    if not isinstance(key, str) or len(key) > 512:
        raise HuanguangQuotaError("key_invalid")
    key = key.strip()
    base = _valid_provider_base(_runtime_setting("EXTRACT_LINK_HUANGUANG_API_BASE", ""))
    if not base:
        raise HuanguangQuotaError("config_invalid")
    payload = query_quota_response(
        _ProviderHTTPTransport(SimpleNamespace(api_base=base)), "/api/xxsyun-quota",
        body={"api_key": key}, credential="key",
        timeout=_int_setting("EXTRACT_LINK_HUANGUANG_REQUEST_TIMEOUT", 30, 5, 300),
    )
    result = {"ok": True}
    for name in ("remainingUses", "totalUses", "reservedUses"):
        value = payload.get(name)
        if name != "remainingUses" and value is None:
            result[name] = None
        elif type(value) is int and 0 <= value <= 2**53 - 1:
            result[name] = value
        else:
            raise HuanguangQuotaError("invalid_response")
    return result


def query_huanguang_saved_cdk_quota(kind: str) -> dict:
    """独立查询一项已保存 CDK，不依赖任务开关或另一项凭据。"""
    from core.extract_link_providers.contracts import ProviderConfig
    from core.extract_link_providers.huanguang import HuanguangProvider, HuanguangQuotaError

    if kind not in {"extraction", "payment"}:
        raise HuanguangQuotaError("config_invalid")
    base = _valid_provider_base(_runtime_setting("EXTRACT_LINK_HUANGUANG_API_BASE", ""))
    if not base:
        raise HuanguangQuotaError("config_invalid", credential=kind)
    setting = "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK" if kind == "payment" else "EXTRACT_LINK_HUANGUANG_CDK"
    cdk = _runtime_setting(setting, "")
    config = ProviderConfig(
        provider_id="huanguang", api_base=base, cdk="",
        timeout=_int_setting("EXTRACT_LINK_HUANGUANG_REQUEST_TIMEOUT", 30, 5, 300),
    )
    provider = HuanguangProvider(config, _ProviderHTTPTransport(SimpleNamespace(api_base=base)))
    return {"ok": True, "quota": provider.query_cdk_quota(cdk, payment=kind == "payment")}


def query_huanguang_cdk_quota(*, include_payment: bool = True, runtime=None) -> dict:
    """查询已配置的双 CDK；查询不查账号、不扣次，未知额度保持未知。"""
    runtime = runtime or _provider_configuration("huanguang")
    provider = _provider("huanguang", runtime)
    extraction = provider.query_cdk_quota(runtime.config.cdk)
    payment = provider.query_cdk_quota(runtime.config.payment_cdk, payment=True) if include_payment else {
        "required": False, "remaining": None, "reserved": None, "active": None,
    }
    return {"ok": True, "extraction": extraction, "payment": payment}


def _huanguang_quota_keys(runtime, mode: str) -> tuple:
    def key(kind, secret):
        value = f"{runtime.config.api_base}\0{secret}".encode()
        return kind, hashlib.sha256(value).hexdigest()
    return (key("extraction", runtime.config.cdk),) + (
        (key("payment", runtime.config.payment_cdk),) if mode == "auto_payment" else ()
    )


@contextmanager
def _huanguang_create_quota(context, runtime, *, provider_id: str, mode: str, action: str):
    """新提链先检查额度；无额度同 Run 延期，原单续查不受影响。"""
    if provider_id != "huanguang" or action != "create":
        yield True
        return
    keys = _huanguang_quota_keys(runtime, mode)
    stage = ""
    from_cache = False
    with _HUANGUANG_QUOTA_LOCK:
        observed = {key: _HUANGUANG_QUOTA_ADMITTED.get(key, 0) for key in keys}
        cached = _HUANGUANG_QUOTA_BLOCKS.get(keys)
        if cached and cached[0] > time.monotonic():
            stage = cached[1]
            from_cache = True
    quotas = None
    if not stage:
        try:
            # HTTP 查询不持预算锁，避免其他 worker 持账号租约排队等待网络超时。
            quotas = query_huanguang_cdk_quota(include_payment=mode == "auto_payment", runtime=runtime)
        except Exception:
            stage = "quota_unavailable"
    with _HUANGUANG_QUOTA_LOCK:
        if quotas is not None:
            try:
                for key in keys:
                    kind = key[0]
                    quota = quotas[kind]
                    if quota.get("required") is False:
                        continue
                    if quota.get("active") is False:
                        stage = f"quota_{kind}_disabled"
                    elif quota.get("active") is not True or type(quota.get("remaining")) is not int:
                        stage = "quota_unavailable"
                    elif quota["remaining"] <= 0:
                        stage = f"quota_{kind}_exhausted"
                    elif quota["remaining"] <= max(
                        _HUANGUANG_QUOTA_INFLIGHT.get(key, 0),
                        _HUANGUANG_QUOTA_ADMITTED.get(key, 0) - observed[key],
                    ):
                        stage = "quota_local_reserved"
                    if stage:
                        break
            except Exception:
                stage = "quota_unavailable"
        if stage and not from_cache:
            if len(_HUANGUANG_QUOTA_BLOCKS) >= 32:
                _HUANGUANG_QUOTA_BLOCKS.clear()
            _HUANGUANG_QUOTA_BLOCKS[keys] = (time.monotonic() + 15, stage)
        if not stage:
            # 正额度不缓存；本机待提交任务先占预算，避免并发共同消费最后一次。
            for key in keys:
                _HUANGUANG_QUOTA_INFLIGHT[key] = _HUANGUANG_QUOTA_INFLIGHT.get(key, 0) + 1
                _HUANGUANG_QUOTA_ADMITTED[key] = _HUANGUANG_QUOTA_ADMITTED.get(key, 0) + 1
    if stage:
        context.defer(delay_seconds=60, reason=_HUANGUANG_QUOTA_STAGES[stage], stage=stage)
        yield False
        return
    released = False

    def release():
        nonlocal released
        with _HUANGUANG_QUOTA_LOCK:
            if released:
                return
            released = True
            for key in keys:
                remaining = _HUANGUANG_QUOTA_INFLIGHT.get(key, 1) - 1
                if remaining:
                    _HUANGUANG_QUOTA_INFLIGHT[key] = remaining
                else:
                    _HUANGUANG_QUOTA_INFLIGHT.pop(key, None)
    try:
        yield release
    finally:
        release()


def _paypal_options(payment_options: dict | None) -> dict:
    """只透传手册允许的 PayPal 国家选择字段。"""
    source = payment_options if isinstance(payment_options, dict) else {}
    out = {}
    for key in ("paypal_region_selected", "paypal_country", "paypal_currency", "paypal_region"):
        value = source.get(key)
        if value is None or str(value).strip() == "":
            continue
        if key == "paypal_region_selected":
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("paypal_region_selected 必须是数字") from exc
            if value < 0:
                raise ValueError("paypal_region_selected 不能为负数")
        out[key] = value
    return out


def _create_extract_job(
    *,
    token: str,
    link_type: str,
    cdk: str,
    payment_options: dict | None = None,
    api_base: str | None = None,
    request_timeout: int | float | None = None,
    on_request_started=None,
) -> dict:
    base = _api_base(api_base)
    parsed_base = urlsplit(base)
    if parsed_base.scheme.lower() not in {"http", "https"} or not parsed_base.hostname:
        raise ValueError("EXTRACT_LINK_API_BASE 地址无效")
    request_url = f"{base}/api/extract"
    timeout = (
        _int_setting("EXTRACT_LINK_REQUEST_TIMEOUT", 30, 5, 300)
        if request_timeout is None
        else max(5, min(300, int(request_timeout or 30)))
    )
    payload = {"link_type": _link_type(link_type), "cdk": _cdk(cdk), "token": token}
    if payload["link_type"] == "paypal":
        payload.update(_paypal_options(payment_options))
    s = _session()
    try:
        if s is None:
            body = json.dumps(payload).encode("utf-8")
            req = Request(
                request_url,
                data=body,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                method="POST",
            )
            if callable(on_request_started):
                on_request_started()
            try:
                with urlopen(req, timeout=timeout) as resp:
                    status = int(getattr(resp, "status", 200) or 200)
                    try:
                        data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
                    except (AttributeError, TypeError, ValueError):
                        raise ExtractCreateResponseUnknown(status, failure_kind="invalid_json") from None
            except HTTPError as exc:
                status = int(getattr(exc, "code", 0) or 0)
                if _create_http_rejected(status):
                    raise ExtractCreateRejected(status) from exc
                raise ExtractCreateResponseUnknown(status, failure_kind="http_error") from exc
            if not isinstance(data, dict) or not data.get("job_id"):
                raise ExtractCreateResponseUnknown(status)
            return data
        if callable(on_request_started):
            on_request_started()
        resp = s.post(request_url, json=payload, timeout=timeout)
        status = int(getattr(resp, "status_code", 0) or 0)
        if status < 200 or status >= 300:
            if _create_http_rejected(status):
                raise ExtractCreateRejected(status)
            raise ExtractCreateResponseUnknown(status, failure_kind="http_error")
        try:
            data = resp.json()
        except Exception:
            raise ExtractCreateResponseUnknown(status, failure_kind="invalid_json") from None
        if not isinstance(data, dict) or not data.get("job_id"):
            raise ExtractCreateResponseUnknown(status)
        return data
    finally:
        try:
            s.close()
        except Exception:
            pass


def _iter_sse_events(
    *,
    job_id: str,
    cdk: str,
    api_base: str | None = None,
    event_timeout: int | float | None = None,
):
    base = _api_base(api_base)
    timeout = (
        _int_setting("EXTRACT_LINK_EVENT_TIMEOUT", 180, 30, 900)
        if event_timeout is None
        else max(30, min(900, int(event_timeout or 180)))
    )
    url = f"{base}/api/jobs/{quote(job_id, safe='')}/events?{urlencode({'cdk': _cdk(cdk)})}"
    s = _session()
    try:
        if s is None:
            req = Request(url, headers={"Accept": "text/event-stream"})
            with urlopen(req, timeout=timeout) as resp:
                event = "message"
                data_lines: list[str] = []
                for raw in resp:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line == "":
                        if data_lines:
                            text = "\n".join(data_lines)
                            try:
                                data = json.loads(text)
                            except Exception:
                                data = {"raw": text}
                            yield event, data
                        event = "message"
                        data_lines = []
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event = line.split(":", 1)[1].strip() or "message"
                    elif line.startswith("data:"):
                        data_lines.append(line.split(":", 1)[1].lstrip())
                if data_lines:
                    text = "\n".join(data_lines)
                    try:
                        data = json.loads(text)
                    except Exception:
                        data = {"raw": text}
                    yield event, data
            return
        resp = s.get(url, timeout=timeout, stream=True)
        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(f"监听提链事件失败 HTTP {resp.status_code}: {(resp.text or '')[:300]}")
        event = "message"
        data_lines: list[str] = []
        for raw in resp.iter_lines():
            if raw is None:
                continue
            if isinstance(raw, bytes):
                line = raw.decode("utf-8", "replace")
            else:
                line = str(raw)
            line = line.rstrip("\r")
            if line == "":
                if data_lines:
                    text = "\n".join(data_lines)
                    try:
                        data = json.loads(text)
                    except Exception:
                        data = {"raw": text}
                    yield event, data
                event = "message"
                data_lines = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip() or "message"
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
        if data_lines:
            text = "\n".join(data_lines)
            try:
                data = json.loads(text)
            except Exception:
                data = {"raw": text}
            yield event, data
    finally:
        try:
            s.close()
        except Exception:
            pass


def _extract_error_message(data) -> str:
    """尽量从提链服务返回的任意错误结构中提取用户可读原因。"""
    if data is None:
        return ""
    if isinstance(data, str):
        return data.strip()
    if not isinstance(data, dict):
        return str(data)
    err = data.get("error")
    if isinstance(err, dict):
        for key in ("message", "detail", "reason", "error", "msg", "description"):
            value = err.get(key)
            if value:
                return str(value).strip()
        return json.dumps(err, ensure_ascii=False)[:500]
    if err:
        return str(err).strip()
    for key in ("message", "detail", "reason", "msg", "description", "raw"):
        value = data.get(key)
        if value:
            return str(value).strip()
    return json.dumps(data, ensure_ascii=False)[:500]


def _format_failure_reason(exc: Exception, logs: list[str] | None = None, last_event: dict | None = None) -> str:
    reason = f"{type(exc).__name__}: {str(exc)}".strip()
    if (not str(exc).strip()) and logs:
        reason = str(logs[-1])
    if last_event and "提链事件流结束但未返回 result" in reason:
        extracted = _extract_error_message(last_event.get("data"))
        if extracted:
            reason = f"提链事件流结束但未返回 result；最后事件 {last_event.get('event')}: {extracted}"
    return reason[:500]


def _explicit_remote_failure_status(last_event: dict | None, reason: str) -> str | None:
    """把远端 SSE 明确拒绝转换成终态，而不是未知结果。"""
    if not isinstance(last_event, dict) or str(last_event.get("event") or "") != "error":
        return None
    text = str(reason or "")
    lowered = text.lower()
    if "不支持" in text or "unsupported" in lowered or "not supported" in lowered:
        return "unsupported"
    return "failed"


def _token_is_invalid_for_extract(result: dict) -> bool:
    """只把明确的 Token 失效交给邮箱登录刷新；网络错误不自动重登。"""
    if bool(result.get("token_expired") or result.get("needs_live_check")):
        return True
    try:
        if int(result.get("http_status")) == 401:
            return True
    except (TypeError, ValueError):
        pass
    error = str(result.get("error") or "").lower()
    return "at已过期" in error or "access_token 已过期" in error or "access_token已过期" in error


def _preflight_failure(result: dict, fallback: str) -> str:
    """把查活/刷新失败压缩成适合账号提链状态栏的低敏原因。"""
    error = str(result.get("error") or "").strip()
    if error:
        return error[:300]
    return fallback


def _is_request_unknown_error(exc: BaseException) -> bool:
    text = str(exc or "").strip().lower()
    return "request_unknown" in text or "manual_reconcile" in text or "结果待确认" in text


def _record_extract_receipt(context, boundary: dict | None, outcome: str, detail: dict | None = None) -> None:
    """Persist the extract remote-job receipt without hiding fence errors."""
    if context is None or not boundary:
        return
    context.remote_request_receipt(
        outcome=outcome,
        action=str(boundary["action"]),
        request_id=str(boundary["request_id"]),
        detail=dict(detail or {}),
    )
    boundary["receipt_outcome"] = str(outcome)
    boundary["pending_confirmation"] = str(outcome) == "response_received"


def _confirm_extract_job_receipt(
    *, context, boundary: dict | None, account_id: int, job_id: str, writeback_ok: bool,
) -> bool:
    """Confirm job creation only after its local running row can be read back."""
    if context is None or not boundary or not boundary.get("pending_confirmation"):
        return True
    account_after = db.get_account(account_id) if writeback_ok else None
    stored_job_id = str((account_after or {}).get("extract_link_job_id") or "").strip()
    local_readback_confirmed = bool(
        account_after
        and str((account_after or {}).get("extract_link_status") or "").strip() == "running"
        and stored_job_id == str(job_id).strip()
    )
    evidence = {
        "remote_result_confirmed": bool(str(job_id).strip()),
        "local_business_writeback_confirmed": bool(writeback_ok),
        "local_readback_confirmed": local_readback_confirmed,
        "response_observed": True,
    }
    if all(evidence.values()):
        _record_extract_receipt(context, boundary, "confirmed", evidence)
        return True
    _record_extract_receipt(context, boundary, "local_commit_required", evidence)
    return False


def _ensure_extract_token(
    *, account_id: int, email: str, progress=None, on_refresh_start=None,
    on_refresh_success=None, operation_context=None, config_snapshot=None,
    preflight_enabled: bool | None = None, refresh_at_enabled: bool | None = None,
) -> str:
    """按提炼预检开关查活及刷新，始终读取数据库最新 Token。"""
    if preflight_enabled is None:
        preflight_enabled = _bool_setting("EXTRACT_LINK_PREFLIGHT_ENABLED", True)
    if not preflight_enabled:
        account = db.get_account(account_id) or {}
        token = str(account.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("提炼前预检已关闭，但数据库没有 access_token，未调用提炼网站")
        return token
    if refresh_at_enabled is None:
        refresh_at_enabled = _bool_setting("EXTRACT_LINK_PREFLIGHT_REFRESH_AT_ENABLED", True)
    from core import live_check_service

    if progress:
        progress("提炼前正在在线查活")
    live_kwargs = {
        "account_id": account_id,
        "email": email,
        "trigger": "extract_preflight",
        "force_refresh": False,
    }
    if operation_context is not None:
        live_kwargs["operation_context"] = operation_context
    if config_snapshot is not None:
        live_kwargs["config_snapshot"] = config_snapshot
    live = live_check_service.run_account_live_check_inline(**live_kwargs)
    if not live.get("accepted"):
        raise RuntimeError(f"提炼前查活未执行：{live.get('error') or '任务未接受'}")
    live_result = live.get("result") if isinstance(live.get("result"), dict) else {}
    if live_result.get("status") == "cancelled":
        raise OperationCancelled(live_result.get("error") or "提炼前查活已取消")
    if live_result.get("status") == "request_unknown" or live_result.get("manual_reconcile"):
        raise RuntimeError(
            f"request_unknown: 提炼前查活结果待确认：{_preflight_failure(live_result, '需人工对账')}"
        )
    if live_result.get("ok"):
        account = db.get_account(account_id) or {}
        token = str(account.get("access_token") or "").strip()
        if token:
            return token
        raise RuntimeError("提炼前查活成功，但数据库没有写回 access_token")
    if live_result.get("status") == "deactivated":
        raise RuntimeError(_preflight_failure(live_result, "提炼前查活确认账号已停用"))
    if not _token_is_invalid_for_extract(live_result):
        raise RuntimeError(
            f"提炼前查活失败，未判定为 Token 失效，已停止提炼："
            f"{_preflight_failure(live_result, '未知查活错误')}"
        )
    if not refresh_at_enabled:
        raise RuntimeError("AT 已失效，预检刷新 AT 已关闭，未调用提炼网站")

    if progress:
        progress("现有 AT 已失效，正在刷新 AT；刷新成功后继续提炼")
    if on_refresh_start:
        on_refresh_start()
    refresh_kwargs = {
        "account_id": account_id,
        "email": email,
        "trigger": "token_refresh_extract_preflight",
        "force_refresh": True,
    }
    if operation_context is not None:
        refresh_kwargs["operation_context"] = operation_context
    if config_snapshot is not None:
        refresh_kwargs["config_snapshot"] = config_snapshot
    refreshed = live_check_service.run_account_live_check_inline(**refresh_kwargs)
    if not refreshed.get("accepted"):
        raise RuntimeError(f"AT 刷新未执行：{refreshed.get('error') or '任务未接受'}")
    refresh_result = refreshed.get("result") if isinstance(refreshed.get("result"), dict) else {}
    if refresh_result.get("status") == "cancelled":
        raise OperationCancelled(refresh_result.get("error") or "提炼前 AT 刷新已取消")
    if refresh_result.get("status") == "request_unknown" or refresh_result.get("manual_reconcile"):
        raise RuntimeError(
            f"request_unknown: AT 刷新结果待确认：{_preflight_failure(refresh_result, '需人工对账')}"
        )
    if not refresh_result.get("ok"):
        raise RuntimeError(
            f"AT 已失效，但刷新失败，未调用提炼网站："
            f"{_preflight_failure(refresh_result, '未知刷新错误')}"
        )
    account = db.get_account(account_id) or {}
    token = str(account.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("AT 刷新成功，但数据库没有写回 access_token，未调用提炼网站")
    if on_refresh_success:
        on_refresh_success()
    if progress:
        progress("AT 刷新成功，已读取数据库新 Token，开始提炼")
    return token


def _extract_task_result_summary(*, result: dict, link_type: str, job_id: str, ok: bool = True) -> dict:
    """只把可展示的提炼摘要写入任务中心，不保存支付链接或二维码地址。"""
    return {
        "ok": bool(ok),
        "link_type": link_type,
        "remote_job_id": job_id or None,
        "has_link": bool(result.get("long_url") or result.get("copy_paste")),
        "has_qr": bool(result.get("image_url_png") or result.get("image_url_svg")),
        "payment_method": result.get("payment_method"),
        "payment_link_type": result.get("payment_link_type"),
        "expires_at": result.get("expires_at"),
        "cdk_remaining": result.get("cdk_remaining"),
    }


def _run_extract(
    *, account_id: int, email: str, access_token: str, link_type: str, cdk: str,
    trigger: str, payment_options: dict | None = None, task_id: int | None = None,
    operation_context=None, release_queue_slot: bool = True, config_snapshot=None,
) -> dict:
    logs: list[str] = []
    last_event = None
    job_id = ""
    reporter = _ReporterAdapter(task_id, operation_context)
    refresh_started = False
    preflight_open = False
    task_stage = "preflight"
    remote_boundary: dict | None = None
    try:
        _checkpoint(operation_context)
        if not db.mark_account_extract_running(account_id):
            message = "账号已删除或提链状态已被重置"
            reporter.finish(status="cancelled", message=message, error=message)
            return {"ok": False, "status": "cancelled", "error": message}

        reporter.start("开始执行提炼")

        def progress(message: str) -> None:
            safe_message = task_run_log.redact_text(message, 1200)
            db.update_account_extract(account_id, {
                "ok": False,
                "status": "running",
                "link_type": link_type,
                "message": message,
            })
            reporter.note(
                safe_message, stage=task_stage,
                event_type="extract.preflight" if preflight_open else "extract.progress",
            )

        def mark_refresh_start() -> None:
            nonlocal refresh_started, task_stage
            refresh_started = True
            task_stage = "refresh_token"
            reporter.stage("refresh_token", "running", "现有 AT 已失效，正在刷新 AT")

        def mark_refresh_success() -> None:
            nonlocal task_stage
            reporter.stage("refresh_token", "success", "AT 刷新成功")
            task_stage = "preflight"

        preflight_enabled = _bool_setting("EXTRACT_LINK_PREFLIGHT_ENABLED", True)
        refresh_at_enabled = preflight_enabled and _bool_setting("EXTRACT_LINK_PREFLIGHT_REFRESH_AT_ENABLED", True)
        if preflight_enabled:
            reporter.stage("preflight", "running", "提炼前正在在线查活")
            preflight_open = True
        else:
            reporter.stage("preflight", "skipped", "提炼前预检已关闭，直接使用数据库 AT")
            task_stage = "access_token"
        if not refresh_at_enabled:
            reporter.stage("refresh_token", "skipped", "预检刷新 AT 已关闭" if preflight_enabled else "预检已关闭，跳过刷新 AT")

        # 不使用入队时传进来的 Token 快照；关闭预检时也读取数据库最新 AT。
        extract_token = _ensure_extract_token(
            account_id=account_id,
            email=email,
            progress=progress,
            on_refresh_start=mark_refresh_start,
            on_refresh_success=mark_refresh_success,
            operation_context=operation_context,
            config_snapshot=config_snapshot,
            preflight_enabled=preflight_enabled,
            refresh_at_enabled=refresh_at_enabled,
        )
        if preflight_enabled:
            reporter.stage("preflight", "success", "提炼前 Token 检查完成")
        preflight_open = False
        reporter.stage("access_token", "success", "已取得可用 AT" if preflight_enabled else "已读取数据库最新 AT")
        if refresh_at_enabled and not refresh_started:
            reporter.stage("refresh_token", "skipped", "现有 AT 有效，无需刷新")
        task_stage = "extract_link"
        reporter.stage("extract_link", "running", "正在创建提炼任务")
        progress("AT 已确认有效，正在创建提链任务" if preflight_enabled else "已读取数据库 AT，正在创建提链任务")
        _checkpoint(operation_context, "创建提链任务前检查取消状态")
        def mark_remote_create_started() -> None:
            nonlocal remote_boundary
            if operation_context is None or remote_boundary is not None:
                return
            request_id = f"extract-job:{operation_context.run_id}:{uuid.uuid4().hex}"
            # 本地参数、请求对象及会话准备完成后，发送前记录远端 intent。
            # 回执不得包含 AT、CDK、支付链接或原始正文。
            operation_context.remote_request_started(
                "extract_job_create",
                request_id=request_id,
                detail={
                    "link_type": link_type,
                    "trigger": str(trigger or "manual"),
                },
            )
            remote_boundary = {
                "action": "extract_job_create",
                "request_id": request_id,
                "receipt_outcome": "started",
                "pending_confirmation": False,
            }
        try:
            create_kwargs = {}
            if config_snapshot is not None:
                create_kwargs = {
                    "api_base": _snapshot_value(config_snapshot, "api_base"),
                    "request_timeout": _captured_int(
                        config_snapshot,
                        "request_timeout",
                        "EXTRACT_LINK_REQUEST_TIMEOUT",
                        30,
                        5,
                        300,
                    ),
                }
            job = _create_extract_job(
                token=extract_token,
                link_type=link_type,
                cdk=cdk,
                payment_options=payment_options,
                on_request_started=mark_remote_create_started,
                **create_kwargs,
            )
        except account_task_store.OperationLeaseLost:
            raise
        except ExtractCreateRejected as exc:
            if remote_boundary:
                _record_extract_receipt(
                    operation_context,
                    remote_boundary,
                    "rejected",
                    {"response_observed": True, "http_status": exc.http_status},
                )
            raise
        except OperationCancelled:
            if remote_boundary:
                _record_extract_receipt(
                    operation_context,
                    remote_boundary,
                    "unknown",
                    {"response_observed": False, "cancelled": True},
                )
            raise
        except Exception as exc:
            if remote_boundary:
                _record_extract_receipt(
                    operation_context,
                    remote_boundary,
                    "unknown",
                    {
                        "response_observed": bool(getattr(exc, "response_observed", False)),
                        "exception_type": type(exc).__name__,
                        "http_status": getattr(exc, "http_status", None),
                        "failure_kind": getattr(exc, "failure_kind", None),
                    },
                )
            raise
        job_id = str(job.get("job_id") or "")
        if not job_id:
            if remote_boundary:
                _record_extract_receipt(
                    operation_context,
                    remote_boundary,
                    "unknown",
                    {"response_observed": True, "job_id_present": False},
                )
            raise RuntimeError("提链服务未返回 job_id，结果待确认")
        if remote_boundary:
            _record_extract_receipt(
                operation_context,
                remote_boundary,
                "response_received",
                {
                    "response_observed": True,
                    "remote_result_confirmed": True,
                    "job_id_present": True,
                },
            )
            _checkpoint(operation_context, "提链任务远端响应后检查取消状态")
        running_payload = {
            "ok": False,
            "status": "running",
            "job_id": job_id,
            "link_type": link_type,
            "message": "提链任务已创建，等待结果",
            "cdk_remaining": job.get("cdk_remaining"),
        }
        try:
            writeback_ok = bool(db.update_account_extract(account_id, running_payload))
        except Exception:
            if remote_boundary and remote_boundary.get("pending_confirmation"):
                _record_extract_receipt(
                    operation_context,
                    remote_boundary,
                    "local_commit_required",
                    {
                        "remote_result_confirmed": True,
                        "local_business_writeback_confirmed": False,
                        "local_readback_confirmed": False,
                        "response_observed": True,
                    },
                )
            raise
        if remote_boundary and remote_boundary.get("pending_confirmation"):
            if not _confirm_extract_job_receipt(
                context=operation_context,
                boundary=remote_boundary,
                account_id=account_id,
                job_id=job_id,
                writeback_ok=writeback_ok,
            ):
                unknown_result = {
                    "ok": False,
                    "status": "request_unknown",
                    "job_id": job_id,
                    "link_type": link_type,
                    "error": "远端提链任务已创建，但本地业务写回/读回未完成，需人工对账",
                    "message": "远端提链任务已创建，但本地业务写回/读回未完成，需人工对账",
                    "request_unknown": True,
                    "manual_reconcile": True,
                    "next_action": "manual_reconcile",
                }
                try:
                    db.update_account_extract(account_id, unknown_result)
                except Exception:
                    logger.exception("[提链] 远端创建未确认状态写回失败: account_id=%s", account_id)
                reporter.stage(
                    task_stage,
                    "failed",
                    "远端提链任务结果待确认",
                    level="WARNING",
                    detail={"remote_job_created": True, "error": unknown_result["error"]},
                )
                reporter.finish(
                    status="request_unknown",
                    message="远端提链任务结果待确认",
                    error=unknown_result["error"],
                    result_summary={
                        "remote_job_created": True,
                        "outcome": "request_unknown",
                        "reconcile_required": True,
                    },
                    validation_method="extract_job_create",
                )
                return unknown_result
        reporter.note(
            "远端提炼任务已创建",
            stage="extract_link",
            event_type="extract.remote_job_created",
            detail={
                "job_id": job_id,
                "link_type": link_type,
                "cdk_remaining": job.get("cdk_remaining"),
            },
        )
        event_kwargs = {}
        if config_snapshot is not None:
            event_kwargs = {
                "api_base": _snapshot_value(config_snapshot, "api_base"),
                "event_timeout": _captured_int(
                    config_snapshot,
                    "event_timeout",
                    "EXTRACT_LINK_EVENT_TIMEOUT",
                    180,
                    30,
                    900,
                ),
            }
        for event, data in _iter_sse_events(job_id=job_id, cdk=cdk, **event_kwargs):
            _checkpoint(operation_context, "处理提链事件前检查取消状态")
            last_event = {"event": event, "data": data}
            if event == "log":
                msg = task_run_log.redact_text(str((data or {}).get("message") or ""), 300)
                if msg:
                    logs.append(msg)
                    db.update_account_extract(account_id, {
                        "ok": False,
                        "status": "running",
                        "job_id": job_id,
                        "link_type": link_type,
                        "message": msg,
                    })
                    reporter.note(msg, stage="extract_link", event_type="extract.remote_log")
            elif event == "result":
                result = (data or {}).get("result") if isinstance(data, dict) else None
                if not isinstance(result, dict):
                    result = {}
                final = {"ok": True, "status": "success", "job_id": job_id, "link_type": link_type, "result": result, "logs": logs}
                if operation_context is None:
                    # Keep the legacy synchronous API's mocked/test and
                    # projection behavior unchanged; only a durable native
                    # Run has the remote receipt/readback contract.
                    db.update_account_extract(account_id, final)
                else:
                    try:
                        final_writeback_ok = bool(db.update_account_extract(account_id, final))
                        final_account = db.get_account(account_id) if final_writeback_ok else None
                    except Exception as exc:
                        raise RuntimeError(
                            f"提链结果本地写回失败，结果待确认: {type(exc).__name__}"
                        ) from exc
                    if not (
                        final_writeback_ok
                        and final_account
                        and str(final_account.get("extract_link_status") or "").strip() == "success"
                        and bool(final_account.get("extract_link_ok"))
                        and str(final_account.get("extract_link_job_id") or "").strip() == job_id
                    ):
                        raise RuntimeError("提链结果本地写回/读回未完成，结果待确认")
                summary = _extract_task_result_summary(result=result, link_type=link_type, job_id=job_id)
                reporter.stage("extract_link", "success", "提炼成功", detail=summary)
                reporter.finish(
                    status="success",
                    message="提炼成功",
                    result_summary=summary,
                    validation_method="extract_link_sse",
                )
                logger.info("[提链] 成功: %s type=%s job=%s", email, link_type, job_id)
                return final
            elif event == "error":
                msg = task_run_log.redact_text(_extract_error_message(data), 500)
                reporter.note(msg or "远端提炼任务返回失败", stage="extract_link", level="ERROR", event_type="extract.remote_error")
                raise RuntimeError(msg or "提链任务失败")
            elif event == "done":
                break
        raise RuntimeError(f"提链事件流结束但未返回 result: {last_event}")
    except OperationCancelled as exc:
        receipt_outcome = str((remote_boundary or {}).get("receipt_outcome") or "")
        remote_unknown = bool(remote_boundary and receipt_outcome != "rejected")
        if remote_unknown and receipt_outcome not in {"unknown", "local_commit_required", "confirmed"}:
            _record_extract_receipt(
                operation_context,
                remote_boundary,
                "unknown",
                {"response_observed": receipt_outcome == "response_received", "cancelled": True},
            )
        unknown = bool(job_id or remote_unknown)
        reason = str(exc) or ("远端提链任务已创建，取消结果待确认" if unknown else "提链任务已取消")
        status = "request_unknown" if unknown else "cancelled"
        result = {
            "ok": False,
            "status": status,
            "job_id": job_id or None,
            "link_type": link_type,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": reason,
            "message": reason,
        }
        if unknown:
            result.update({"request_unknown": True, "manual_reconcile": True, "next_action": "manual_reconcile"})
        safe_reason = task_run_log.redact_text(reason, 1200)
        try:
            db.update_account_extract(account_id, result)
        except Exception:
            logger.exception("[提链] 取消/未知状态写入失败: account_id=%s", account_id)
        if job_id and not unknown:
            try:
                db.mark_extract_link_type_failed(account_id, link_type, reason)
            except Exception:
                logger.exception("[提链] 取消类型状态写入失败: account_id=%s type=%s", account_id, link_type)
        interruption_detail = {
            "error": safe_reason,
            "remote_job_created": bool(job_id),
            "reconcile_required": unknown,
            "cancelled": not unknown,
        }
        if preflight_open and task_stage != "preflight":
            reporter.note(
                "提炼前 Token 检查结果待确认" if unknown else "提炼前 Token 检查已取消",
                stage="preflight",
                level="WARNING" if unknown else "INFO",
                detail=interruption_detail,
            )
        reporter.note(
            "远端提链结果待确认" if unknown else "提炼已取消",
            stage=task_stage,
            level="WARNING" if unknown else "INFO",
            detail=interruption_detail,
        )
        reporter.finish(
            status=status,
            message="远端提链结果待确认" if unknown else "提炼已取消",
            error=safe_reason,
            result_summary={
                "remote_job_created": bool(job_id),
                "outcome": "request_unknown" if unknown else "cancelled",
                "reconcile_required": unknown,
            },
            validation_method="extract_link_sse" if job_id else "extract_preflight",
        )
        return result
    except account_task_store.OperationLeaseLost:
        # The shared gateway must own the lease-loss fence and unknown result.
        raise
    except Exception as exc:
        receipt_outcome = str((remote_boundary or {}).get("receipt_outcome") or "")
        remote_unknown = bool(remote_boundary and receipt_outcome != "rejected")
        if remote_unknown and receipt_outcome not in {"unknown", "local_commit_required", "confirmed"}:
            try:
                _record_extract_receipt(
                    operation_context,
                    remote_boundary,
                    "unknown",
                    {"response_observed": receipt_outcome == "response_received"},
                )
            except Exception:
                logger.exception("[提链] 远端创建异常回执写入失败: account_id=%s", account_id)
        unknown = bool(job_id or _is_request_unknown_error(exc) or remote_unknown)
        reason = _format_failure_reason(exc, logs=logs, last_event=last_event)
        explicit_remote_status = (
            "failed" if isinstance(exc, ExtractCreateRejected)
            else _explicit_remote_failure_status(last_event, reason)
        )
        if explicit_remote_status:
            unknown = False
            remote_reason = _extract_error_message(last_event.get("data")) if last_event else ""
            if remote_reason:
                reason = remote_reason[:500]
        final_status = explicit_remote_status or ("request_unknown" if unknown else "failed")
        result = {
            "ok": False,
            "status": final_status,
            "job_id": job_id or None,
            "link_type": link_type,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": reason,
            "message": reason,
        }
        if unknown:
            result.update({"request_unknown": True, "manual_reconcile": True, "next_action": "manual_reconcile"})
        safe_reason = task_run_log.redact_text(reason, 1200)
        failure_summary = _extract_task_result_summary(
            result={}, link_type=link_type, job_id=job_id, ok=False,
        )
        failure_summary["remote_job_created"] = bool(job_id)
        if isinstance(exc, ExtractCreateResponseUnknown):
            failure_summary["cause_code"] = {
                "http_error": "extract_create_http_unknown",
                "invalid_json": "extract_create_invalid_json",
                "missing_job_id": "extract_create_missing_job_id",
            }.get(exc.failure_kind, "extract_create_response_unknown")
            failure_summary["cause_diagnostics"] = {
                "failure_kind": exc.failure_kind,
                "http_status": exc.http_status,
                "response_observed": True,
            }
        elif remote_boundary and not job_id and type(exc).__name__ in {
            "Timeout", "TimeoutError", "ReadTimeout", "ConnectTimeout", "ConnectionError", "SSLError",
        }:
            failure_summary["cause_code"] = "extract_create_transport_error"
            failure_summary["cause_diagnostics"] = {
                "failure_kind": "transport_error",
                "exception_type": type(exc).__name__,
                "response_observed": False,
            }
        if explicit_remote_status:
            failure_summary["remote_result_state"] = "rejected"
        if isinstance(exc, ExtractCreateRejected):
            failure_summary["cause_code"] = "extract_create_rejected"
            failure_summary["http_status"] = exc.http_status
        stage_message = (
            "远端提炼结果待确认" if unknown
            else "当前支付方式不支持" if final_status == "unsupported"
            else "提炼失败"
        )
        # Token 刷新属于预检内部步骤；它失败时也要结束仍打开的预检，
        # 但取消和远端结果不明不能被补成失败或成功。
        if preflight_open and task_stage != "preflight":
            if unknown:
                reporter.note(
                    "提炼前 Token 检查结果待确认",
                    stage="preflight",
                    level="WARNING",
                    detail={"error": safe_reason, "reconcile_required": True},
                )
            else:
                reporter.stage(
                    "preflight", "failed", "提炼前 Token 检查失败",
                    level="ERROR", detail={"error": safe_reason},
                )
        if unknown:
            reporter.note(
                stage_message,
                stage=task_stage,
                level="WARNING",
                detail={"error": safe_reason, "reconcile_required": True},
            )
        else:
            reporter.stage(
                task_stage, "failed", stage_message,
                level="ERROR", detail={"error": safe_reason},
            )
        reporter.finish(
            status=final_status,
            message=stage_message,
            error=safe_reason,
            result_summary=failure_summary,
            validation_method="extract_link_sse" if job_id else "extract_preflight",
        )
        try:
            db.update_account_extract(account_id, result)
        except Exception:
            logger.exception("[提链] 写入失败状态异常: account_id=%s", account_id)
        if job_id and not unknown:
            try:
                db.mark_extract_link_type_failed(account_id, link_type, reason)
            except Exception:
                logger.exception("[提链] 记录失败类型异常: account_id=%s type=%s", account_id, link_type)
        logger.exception("[提链] 失败: %s", email)
        return result
    finally:
        if release_queue_slot:
            _QUEUE_SLOTS.release()


def _numeric_batch_id(value: str | int | None) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip().isdigit() else None
    except (TypeError, ValueError):
        return None


def _native_response(submitted: dict, *, account_id: int, email: str, trigger: str, link_type: str) -> dict:
    accepted = bool(submitted.get("accepted"))
    response = {
        "accepted": accepted,
        "busy": bool(submitted.get("busy")) and not accepted,
        "account_id": account_id,
        "email": email,
        "status": submitted.get("status") or ("queued" if accepted else "failed"),
        "trigger": trigger,
        "task_id": submitted.get("task_id"),
        "run_id": submitted.get("run_id"),
        "link_type": link_type,
        "reused": bool(submitted.get("reused")),
        # Routes discard this key before JSON serialization.  Keeping it in the
        # compatibility shape avoids making callers branch on queue backend.
        "future": None,
    }
    if submitted.get("error"):
        response["error"] = submitted["error"]
    return response


def _cancel_unclaimed_native_run(run_id: int | None) -> None:
    if not run_id:
        return
    try:
        from core.storage import operation_runtime_store

        operation_runtime_store.request_run_cancel(int(run_id), reason="账号提链业务状态已被其他请求占用")
    except Exception:
        logger.exception("[提链] 取消孤立 durable run 失败: run_id=%s", run_id)


def _provider_dispatch_capacity_key(run: dict) -> str | dict[str, int]:
    data = run.get("data") if isinstance(run, dict) else {}
    provider_id = str((data or {}).get("provider_id") or "legacy").strip().lower()
    provider_id = provider_id if provider_id in _PROVIDER_SETTINGS else "invalid"
    workers = run.get("batch_workers")
    if run.get("batch_id") and isinstance(workers, int) and not isinstance(workers, bool) and 1 <= workers <= 16:
        # 一次预约两个维度，批次满额时不消耗平台或共享 worker。
        return {provider_id: _provider_dispatch_capacity_limit(provider_id),
                f"batch:{int(run['batch_id'])}": workers}
    return provider_id


def _provider_dispatch_capacity_limit(provider_id: str) -> int:
    settings = _PROVIDER_SETTINGS.get(str(provider_id or "").strip().lower())
    if not settings:
        return 0
    return _int_setting(settings["concurrency_key"], 1, 1, 32)


def _provider_link_type(provider_id: str, value: object, default: str) -> str:
    link_type = str(value or default or "pix").strip().lower()
    if link_type not in SUPPORTED_LINK_TYPES:
        raise ValueError("提链类型无效")
    if provider_id == "lumen_flow" and link_type in {"ideal_short", "ph_short"}:
        raise ValueError("Lumen Flow 不支持当前提链类型")
    if provider_id == "huanguang" and link_type != "upi":
        raise ValueError("幻光当前仅支持 UPI 提链")
    return link_type


def _provider_request_options(provider_id: str, options: object, *, mode: str, link_type: str) -> dict:
    source = options if isinstance(options, dict) else {}
    if provider_id == "legacy":
        if mode == "auto_payment" and link_type != "upi":
            raise ValueError("虾扯蛋链自动支付仅支持 UPI")
        return _paypal_options(source)
    if provider_id == "huanguang":
        if "retry_count" not in source:
            return {}
        count = source["retry_count"]
        if type(count) is not int or not 1 <= count <= 10:
            raise ValueError("幻光单任务尝试次数必须是 1 至 10 的整数")
        return {"retry_count": count}
    if provider_id != "lumen_flow":
        return {}
    allowed = {
        "payment_method", "processing_mode", "plan_name", "promo_code",
        "max_amount_cents", "apply_promotion", "promotion_campaign_id",
    }
    result = {}
    for key in allowed:
        value = source.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if key in {"payment_method", "processing_mode", "plan_name", "promo_code", "promotion_campaign_id"}:
            if not isinstance(value, str) or len(value) > 160:
                raise ValueError(f"{key} 格式无效")
            result[key] = value.strip()
        elif key == "max_amount_cents":
            if isinstance(value, bool):
                raise ValueError("max_amount_cents 格式无效")
            try:
                amount = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("max_amount_cents 格式无效") from exc
            if amount < 0:
                raise ValueError("max_amount_cents 不能为负数")
            result[key] = amount
        elif key == "apply_promotion":
            if not isinstance(value, bool):
                raise ValueError("apply_promotion 必须是布尔值")
            result[key] = value
    if mode == "auto_payment":
        payment_method = str(result.get("payment_method") or link_type).strip().upper()
        if payment_method != "MOMO":
            raise ValueError("Lumen Flow 自动支付仅支持 MOMO")
        result["payment_method"] = payment_method
    return result


def _safe_provider_job_state(
    job,
    *,
    mode: str,
    preflight_status: str = "pending",
    plus_status: str = "unknown",
    aftercare_status: str = "not_started",
    message: str = "",
) -> dict:
    from core.extract_link_providers.contracts import ProviderJob, safe_payment_artifact

    item = job if isinstance(job, ProviderJob) else ProviderJob()
    extraction_state = str(item.extraction_state or "unknown").strip().lower()
    extraction_state = {
        "success": "succeeded",
        "done": "succeeded",
        "complete": "succeeded",
        "completed": "succeeded",
        "error": "failed",
        "cancelled": "failed",
        "canceled": "failed",
    }.get(extraction_state, extraction_state)
    if extraction_state not in {"pending", "queued", "running", "succeeded", "failed", "unknown"}:
        extraction_state = "unknown"
    payment_state = str(item.payment_state or "not_started").strip().lower()
    payment_state = {
        "success": "succeeded",
        "paid": "succeeded",
        "complete": "succeeded",
        "completed": "succeeded",
        "error": "failed",
        "canceled": "failed",
        "cancelled": "failed",
        "unpaid": "not_started",
    }.get(payment_state, payment_state)
    if mode == "extract_only":
        payment_state = "not_started"
    elif payment_state not in {"not_started", "pending", "succeeded", "failed", "unknown"}:
        payment_state = "unknown"
    summary = item.summary if isinstance(item.summary, dict) else {}
    safe_summary = {}
    for key in ("current_step", "percent", "outcome", "failure_code", "failure_type", "last_event",
                "plus_verification_status", "automatic_payment_status", "payment_check_status", "platform_plus_status",
                "payment_confirmed_plan_checked_at"):
        value = summary.get(key)
        if key == "percent" and isinstance(value, (int, float)) and not isinstance(value, bool):
            safe_summary[key] = max(0, min(100, int(value)))
        elif isinstance(value, str):
            safe_summary[key] = value[:100]
    if summary.get("payment_confirmation_source") == "local_plan_check":
        safe_summary["payment_confirmation_source"] = "local_plan_check"
    for key in ("completed_steps", "total_steps", "run_attempt", "step_attempt", "max_attempts", "queue_position",
                "auto_relink_attempt", "remote_chain_length"):
        value = summary.get(key)
        if type(value) is int and 0 <= value <= 1000000:
            safe_summary[key] = value
    for key in ("automatic_payment_terminal", "automatic_payment_requires_reconcile", "remote_polling",
                "entitlement_active", "entitlement_inferred", "xxsyun_polling", "scan_fallback_polling", "submission_receipt_pending",
                "extraction_ever_succeeded", "local_plan_check_pending", "local_reconcile_halted"):
        if type(summary.get(key)) is bool:
            safe_summary[key] = summary[key]
    if summary.get("local_reconcile_reason") in {"remote_not_found", "query_failures", "timeout", "no_progress"}:
        safe_summary["local_reconcile_reason"] = summary["local_reconcile_reason"]
    if isinstance(summary.get("local_reconcile_halted_at"), str):
        safe_summary["local_reconcile_halted_at"] = summary["local_reconcile_halted_at"][:80]
    for key, allowed in {
        "xxsyun_status": {"submitting", "awaiting_worker", "claimed", "verifying", "completed", "failed",
                          "expired", "cancelled", "rejected", "manual_review", "credentials_required"},
        "scan_fallback_status": {"checking", "submitting", "submitted", "existing", "unavailable", "skipped", "manual_review"},
        "scan_fallback_provider": {"xxsyun", "chongyun", "seashore"},
        "auto_relink_status": {"checking_payment", "starting", "started", "submitted", "failed", "skipped", "completed", "unavailable"},
        "remote_chain_error": {"invalid_child_id", "invalid_chain", "cycle", "chain_limit"},
    }.items():
        value = summary.get(key)
        if isinstance(value, str) and value in allowed:
            safe_summary[key] = value
    remote_status = summary.get("remote_status")
    if remote_status in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "ERROR", "DONE", "AWAITING_BLIK_CODE", "CANCELED", "CANCELLED"}:
        safe_summary["remote_status"] = remote_status
    if extraction_state == "failed" and summary.get("remote_terminal_failure") is True:
        safe_summary["remote_terminal_failure"] = True
    failure_message = summary.get("failure_message")
    if isinstance(failure_message, str) and failure_message.strip():
        safe_summary["failure_message"] = task_run_log.redact_text(failure_message, 300)
    return {
        "extraction_state": extraction_state,
        "payment_state": payment_state,
        "preflight_status": str(preflight_status or "pending")[:40],
        "plus_status": str(plus_status or "unknown")[:40],
        "aftercare_status": str(aftercare_status or "not_started")[:40],
        "links": list(item.links or ()),
        "payment_links": list(item.payment_links or ()),
        "payment_artifact": safe_payment_artifact(item.payment_artifact),
        "summary": safe_summary,
        "message": task_run_log.redact_text(message or safe_summary.get("failure_message") or "", 300),
    }


def _update_provider_job(context, provider_id: str, job_id: str | None, state: dict, private_data=None) -> None:
    from core.storage import extract_link_jobs

    private = private_data if isinstance(private_data, dict) else {}
    context.checkpoint()
    fence = getattr(context, "execution_fence", None)
    extract_link_jobs.save_provider_job(context.run_id, provider_id, job_id, state, private, execution_fence=fence)


def _provider_has_reference(job) -> bool:
    if not isinstance(job, dict):
        return False
    summary = (job.get("public_state") or {}).get("summary") or {}
    return bool(job.get("job_id") or summary.get("submission_receipt_pending") is True)


def _provider_resume_private(provider_id, private, state):
    """旧幻光原单迁入节点链时，传递已保存的同单材料。"""
    if provider_id != "huanguang" or private.get("job_chain"):
        return private
    from core.extract_link_providers.contracts import safe_payment_artifact

    artifact = safe_payment_artifact(state.get("payment_artifact"))
    if not (state.get("links") or state.get("payment_links") or any(artifact.get(key) for key in (
        "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
    ))):
        return private
    return {**private, "previous_public_state": state}


def _huanguang_needs_continuation(state: dict) -> bool:
    """只续查仍在执行的原单；明确结束或人工核对不无限占用队列。"""
    summary = state.get("summary") or {}
    if summary.get("local_reconcile_halted") is True:
        return False
    if summary.get("remote_chain_error") or summary.get("outcome") == "REJECTED":
        return False
    if summary.get("submission_receipt_pending") is True or summary.get("remote_polling") is True:
        return True
    if summary.get("automatic_payment_requires_reconcile") is True or summary.get("remote_terminal_failure") is True:
        return False
    return state.get("extraction_state") in {"queued", "running", "pending", "unknown"}


_HUANGUANG_RECONCILE_MESSAGES = {
    "remote_not_found": "原单连续查询返回 HTTP 404，已停止自动续查，待核验",
    "query_failures": "原单连续查询失败达到上限，已停止自动续查，待核验",
    "timeout": "原单自动续查已超过总时限，已停止自动续查，待核验",
    "no_progress": "原单长时间没有有效进展，已停止自动续查，待核验",
}


def _record_huanguang_reconcile(context, private, state, *, succeeded=None, http_status=None, started_at=None):
    from core.extract_link_reconcile_policy import record_reconcile

    private = dict(private or {})
    if succeeded is True and private.get("latest_query_failed") is True:
        succeeded = False
        http_status = private.get("latest_query_http_status")
    private["local_reconcile"] = record_reconcile(
        private.get("local_reconcile"), state, now=datetime.now(timezone.utc),
        started_at=started_at or context.run.get("created_at"),
        query_succeeded=succeeded, http_status=http_status,
    )
    return private


def _huanguang_reconcile_halt_reason(private) -> str:
    from core.extract_link_reconcile_policy import halt_reason

    return halt_reason(
        (private or {}).get("local_reconcile"), now=datetime.now(timezone.utc),
        total_timeout=_int_setting("EXTRACT_LINK_HUANGUANG_RECONCILE_TIMEOUT", 3600, 60, 86400),
        no_progress_timeout=_int_setting("EXTRACT_LINK_HUANGUANG_NO_PROGRESS_TIMEOUT", 900, 60, 86400),
        max_query_failures=_int_setting("EXTRACT_LINK_HUANGUANG_MAX_QUERY_FAILURES", 12, 3, 100),
    )


def _halt_huanguang_reconcile(context, state, private, *, job_id, mode, reason, leases, proxy_resource_ids):
    """只停止本地查询，保留原单及材料，不推断远端失败或取消付款。"""
    message = _HUANGUANG_RECONCILE_MESSAGES[reason]
    private = dict(private or {})
    metadata = dict(private.get("local_reconcile") or {})
    halted_at = metadata.get("halted_at") or datetime.now(timezone.utc).isoformat()
    metadata.update(halted_reason=reason, halted_at=halted_at)
    private["local_reconcile"] = metadata
    summary = state.setdefault("summary", {})
    summary.update(local_reconcile_halted=True, local_reconcile_reason=reason,
                   local_reconcile_halted_at=halted_at, current_step=message, percent=None)
    if state.get("extraction_state") != "succeeded" and summary.get("extraction_ever_succeeded") is not True:
        state["extraction_state"] = "unknown"
    if mode != "extract_only" and state.get("payment_state") not in {"succeeded", "failed"}:
        state["payment_state"] = "unknown"
    state["message"] = message
    _update_provider_job(context, "huanguang", job_id or None, state, private)
    context.report(stage="remote_sync", level="warning", message=message,
                   detail={"cause_code": "extract_reconcile_halted", "local_reconcile_reason": reason})
    _release_huanguang_proxies(context, leases, proxy_resource_ids, terminal=False)
    extracted = state.get("extraction_state") == "succeeded" or summary.get("extraction_ever_succeeded") is True
    db.update_account_extract(int(context.account_id), {
        "status": "success" if extracted else "request_unknown", "ok": extracted,
        "job_id": job_id or None, "message": message, "error": message,
    })
    context.finish(status="request_unknown", message=message, error=message, result_summary={
        "provider_id": "huanguang", "mode": mode, "extraction_status": state.get("extraction_state"),
        "payment_status": state.get("payment_state"), "plus_status": state.get("plus_status"),
        "remote_job_created": bool(job_id), "cause_code": "extract_reconcile_halted",
        "local_reconcile_halted": True, "local_reconcile_reason": reason,
    })


def _defer_huanguang_job(context, runtime, state, *, reason="等待平台原单同步"):
    state["message"] = reason
    context.defer(
        delay_seconds=max(10, min(30, runtime.poll_interval)), reason=reason,
        data={"extract_poll_continuation": True, "workbench_action": "sync_status", "provider_job_run_id": context.run_id},
    )


def _provider_status_label(status: str) -> str:
    return {
        "succeeded": "success",
        "success": "success",
        "queued": "queued",
        "running": "running",
        "failed": "failed",
        "pending": "pending",
        "unknown": "unknown",
        "not_started": "not_started",
    }.get(str(status or "").lower(), "unknown")


def _provider_payment_sync_due(private_data: object, *, now: datetime | None = None) -> bool:
    details = private_data if isinstance(private_data, dict) else {}
    raw = details.get("next_payment_state_sync_at")
    if not raw:
        return False
    try:
        due_at = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if due_at.tzinfo is None:
        due_at = due_at.astimezone()
    current = now or datetime.now(due_at.tzinfo)
    if current.tzinfo is None:
        current = current.astimezone()
    return current >= due_at


def _generic_workbench_failure(value: str) -> bool:
    text = value.strip().rstrip("。.!！:： ").lower()
    if text.startswith("平台提链失败：") or text.startswith("平台提链失败:"):
        text = text[7:].strip()
    return text in {
        "", "任务处理失败", "任务失败", "处理失败", "提链失败", "平台提链失败", "请求失败",
        "error", "failed", "task failed", "task processing failed", "unknown error",
    }


def _workbench_failure_detail(summary: dict) -> str:
    # 旧记录的通用错误仅用已保存的明确失败原因补全，不触发远端查询或业务重跑。
    for key in ("failure_message", "current_step"):
        detail = summary.get(key)
        if not isinstance(detail, str) or _generic_workbench_failure(detail):
            continue
        detail = detail.strip()
        if detail.startswith(("正在", "等待", "排队", "准备")):
            continue
        if key == "current_step" and not re.search(
            r"失败|错误|异常|无效|不足|已用完|用尽|耗尽|未执行|取消|拒绝|超时|不可用|无法|"
            r"\b(?:error|failed|invalid|exhausted|insufficient|timeout|denied|cancelled|canceled)\b",
            detail, re.IGNORECASE,
        ):
            continue
        detail = task_run_log.redact_text(detail, len(detail))
        detail = re.sub(r"(?i)\b(?:https?|socks5h?)://[^\s<>]+", "[REDACTED_URL]", detail)
        detail = re.sub(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", detail)
        return " ".join(detail.split())[:300]
    return ""


def _workbench_task_item(row: dict, *, account: dict | None = None) -> dict:
    data = row.get("task_data") if isinstance(row.get("task_data"), dict) else {}
    state = row.get("public_state") if isinstance(row.get("public_state"), dict) else {}
    summary = state.get("summary") if isinstance(state.get("summary"), dict) else {}
    run_summary = row.get("result_summary") if isinstance(row.get("result_summary"), dict) else {}
    provider_id = str(data.get("provider_id") or row.get("job_provider_id") or "legacy")
    mode = str(data.get("mode") or "extract_only")
    task_status = str(row.get("run_status") or row.get("task_status") or "queued").lower()
    if task_status == "attention_required":
        task_status = "request_unknown"
    extraction_value = state.get("extraction_state") or run_summary.get("extraction_status")
    if provider_id == "huanguang" and summary.get("extraction_ever_succeeded") is True:
        extraction_value = "succeeded"
    if not extraction_value and provider_id == "legacy":
        if task_status == "success" and (run_summary.get("has_link") or run_summary.get("remote_job_id")):
            extraction_value = "success"
        elif task_status in {"failed", "request_unknown", "attention_required", "cancelled", "stopped"}:
            extraction_value = "failed"
    extraction = str(extraction_value or "pending").lower()
    extraction = _provider_status_label(extraction)
    payment = str(state.get("payment_state") or run_summary.get("payment_status") or "not_started").lower()
    if mode == "extract_only":
        payment = "not_started"
    payment = {
        "succeeded": "paid", "success": "paid", "paid": "paid",
        "not_started": "unpaid", "failed": "failed",
        "pending": "pending_payment", "unknown": "request_unknown",
    }.get(payment, "pending_payment")
    preflight = str(state.get("preflight_status") or run_summary.get("preflight_status") or "pending").lower()
    plus = str(state.get("plus_status") or run_summary.get("plus_status") or "unknown").lower()
    if account and payment == "paid" and plus in {"unknown", "pending", "queued"}:
        check_status = str(account.get("plan_check_status") or "").lower()
        plan = str(account.get("current_plan_type") or account.get("plan_type") or "").lower()
        if check_status == "success":
            plus = "confirmed" if ("plus" in plan or "pro" in plan or bool(account.get("has_active_subscription"))) else "not_confirmed"
    if mode in {"auto_payment", "manual_payment"} and extraction == "success":
        from core.storage.extract_link_jobs import independent_plus_is_confirmed
        if independent_plus_is_confirmed(account, task_created_at=row.get("task_created_at")):
            plus = "confirmed"
    progress = {
        "label": str(summary.get("current_step") or row.get("progress_stage") or row.get("current_stage") or ""),
        "percent": summary.get("percent"),
    }
    error = str(row.get("error_message") or "")
    legacy_projection_matches = bool(
        provider_id == "legacy"
        and run_summary.get("remote_job_id")
        and account
        and str(account.get("extract_link_job_id") or "") == str(run_summary.get("remote_job_id") or "")
    )
    legacy_has_link = bool(legacy_projection_matches and account.get("extract_link_long_url"))
    from core.extract_link_providers.contracts import safe_payment_artifact
    artifact = safe_payment_artifact(state.get("payment_artifact"))
    has_payment_entry = bool(
        state.get("payment_links") or state.get("links") or legacy_has_link
        or any(artifact.get(key) for key in (
            "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
        ))
    )
    message = str(state.get("message") or run_summary.get("message") or error or "")
    quota_stage = str(row.get("progress_stage") or row.get("current_stage") or "")
    if provider_id == "huanguang" and task_status == "queued" and quota_stage in _HUANGUANG_QUOTA_STAGES:
        message = _HUANGUANG_QUOTA_STAGES[quota_stage]
        progress["label"] = message
        progress["percent"] = None
        error = ""
    elif provider_id == "huanguang" and extraction == "failed" and _generic_workbench_failure(error):
        detail = _workbench_failure_detail(summary) if _generic_workbench_failure(message) else (
            _workbench_failure_detail({"current_step": message})
        )
        if detail:
            error = detail if detail.startswith("平台提链失败") else f"平台提链失败：{detail}"
            if _generic_workbench_failure(message):
                message = error
    created_at = row.get("run_created_at") or row.get("task_created_at")
    updated_at = row.get("job_updated_at") or row.get("task_updated_at") or row.get("run_completed_at") or created_at
    return {
        "task_id": int(row.get("task_id") or 0),
        "run_id": int(row.get("run_id") or 0) or None,
        "account_id": int(row.get("account_id") or 0) or None,
        "batch_id": int(row.get("batch_id") or 0) or None,
        "email": str(row.get("email") or ""),
        "provider_id": provider_id,
        "mode": mode,
        "link_type": str(data.get("link_type") or "")[:80],
        "task_status": task_status,
        "preflight_status": preflight,
        "extraction_status": extraction,
        "payment_status": payment,
        "payment_confirmation_source": "local_plan_check" if (
            payment == "paid" and summary.get("payment_confirmation_source") == "local_plan_check"
        ) else "",
        "plus_status": plus,
        "run_count": int(row.get("run_count") or 0),
        "progress": progress,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
        "message": message[:500],
        "error": error[:500],
        "has_extract_link": bool(state.get("links") or artifact.get("payment_page_url") or state.get("payment_links") or legacy_has_link),
        "has_payment_link": bool(artifact.get("payment_url") or artifact.get("payment_page_url") or state.get("payment_links") or state.get("links") or legacy_has_link),
        "has_payment_entry": has_payment_entry,
        "has_qr": bool(artifact.get("qr_data") or artifact.get("qr_image_url_png") or artifact.get("qr_image_url_svg")),
        "local_reconcile_halted": provider_id == "huanguang" and summary.get("local_reconcile_halted") is True,
    }


def _workbench_status_matches(item: dict, status: str) -> bool:
    if not status:
        return True
    task_status = str(item.get("task_status") or "")
    extraction = str(item.get("extraction_status") or "")
    payment = str(item.get("payment_status") or "")
    plus = str(item.get("plus_status") or "")
    if item.get("local_reconcile_halted") is True and status in {"processing", "running", "needs_attention"}:
        return status == "needs_attention"
    if status == "processing":
        return (
            task_status in {"queued", "running", "waiting", "cancelling", "settling", "stopping"}
            or (item.get("mode") == "auto_payment" and payment == "pending_payment")
            or (payment == "paid" and plus in {"unknown", "pending", "queued"})
        )
    if status == "running":
        return task_status in {"running", "cancelling", "settling", "stopping"}
    if status == "extraction_succeeded":
        return extraction == "success"
    if status == "payment_succeeded":
        return payment == "paid"
    if status == "plus_confirmed":
        return plus == "confirmed"
    if status == "needs_attention":
        return (
            task_status in {"failed", "request_unknown", "cancelled", "attention_required", "partial_success", "stopped"}
            or extraction in {"unknown", "failed"} or payment in {"request_unknown", "failed"}
            or plus in {"failed", "not_confirmed"} or (payment == "paid" and plus == "unknown")
        )
    return False


def create_workbench_tasks(
    *, account_ids: list[int], provider_id: str, mode: str,
    type: str | None = None, options: dict | None = None,
    batch_id: int | None = None, dispatch: bool = True,
) -> dict:
    provider_id = str(provider_id or "").strip().lower()
    mode = str(mode or "").strip().lower()
    if not _provider_mode_enabled(provider_id, mode):
        raise ValueError("当前配置未启用该平台或运行模式")
    runtime_config = _provider_configuration(provider_id)
    link_type = _provider_link_type(provider_id, type, runtime_config.default_type)
    safe_options = _provider_request_options(provider_id, options, mode=mode, link_type=link_type)
    if mode == "auto_payment" and not runtime_config.capabilities.get("payment"):
        raise ValueError("平台没有可用的支付能力")
    ids = []
    for value in account_ids if isinstance(account_ids, list) else []:
        account_id = int(value)
        if account_id > 0 and account_id not in ids:
            ids.append(account_id)
    if not ids or len(ids) > 500:
        raise ValueError("账号数量必须在 1 至 500 之间")

    started = skipped = failed = 0
    from core import plus_promotion
    from core.storage import extract_link_jobs
    register_operation_handlers()
    for account_id in ids:
        account = db.get_account(account_id)
        if not account or account.get("archived") or db.account_is_deactivated(account):
            skipped += 1
            continue
        try:
            if not plus_promotion.is_extract_link_eligible(account):
                skipped += 1
                continue
        except Exception:
            skipped += 1
            continue
        if mode == "auto_payment" and extract_link_jobs.has_unresolved_auto_payment(account_id):
            skipped += 1
            continue
        if not str(account.get("access_token") or "").strip():
            skipped += 1
            continue
        if not db.claim_account_extract(account_id, trigger="extract_workbench", link_type=link_type):
            skipped += 1
            continue
        email = str(account.get("email") or "").strip()
        data = {
            "provider_id": provider_id,
            "mode": mode,
            "link_type": link_type,
            "options": safe_options,
            "workbench_action": "create",
        }
        try:
            submitted = account_task_store.submit_durable_operation(
                task_type="extract_link",
                account_id=account_id,
                email=email,
                trigger="extract_workbench",
                source_system="native_operations",
                source_id=f"extract-workbench:{account_id}:{uuid.uuid4().hex}",
                resource_family="openai_interactive",
                data=data,
                config_snapshot_provider=get_config_snapshot,
                config_allowlist=EXTRACT_CONFIG_ALLOWLIST,
                dispatch=dispatch,
                **({"batch_id": int(batch_id)} if batch_id is not None else {}),
            )
        except Exception:
            db.update_account_extract(account_id, {
                "status": "failed", "ok": False, "link_type": link_type,
                "message": "提链任务持久化失败", "error": "提链任务持久化失败",
            })
            failed += 1
            continue
        if not submitted.get("accepted"):
            db.update_account_extract(account_id, {
                "status": "failed", "ok": False, "link_type": link_type,
                "message": "提链任务未能入队", "error": str(submitted.get("error") or "提链任务未能入队")[:300],
            })
            skipped += 1
            continue
        db.update_account_extract(account_id, {
            "status": "queued", "ok": False, "link_type": link_type, "message": "已入队",
        })
        started += 1
    return {"started": started, "skipped": skipped, "failed": failed}


def list_workbench_tasks(
    *, provider_id: str | None = None, mode: str | None = None,
    status: str = "", query: str = "", page: int = 1, page_size: int = 20,
    batch_id: int | None = None,
) -> dict:
    from core.storage import extract_link_jobs

    result = extract_link_jobs.list_workbench_page(
        provider_id=provider_id, mode=mode, query=query, status=status,
        page=page, page_size=page_size,
        **({"batch_id": int(batch_id)} if batch_id is not None else {}),
    )
    return {**result, "items": _workbench_project_rows(result["items"])}


def _workbench_project_rows(rows: list[dict]) -> list[dict]:
    account_rows = db.get_accounts_for_jobs([
        {
            "id": int(row.get("task_id") or 0),
            "account_id": row.get("account_id"),
            "email": row.get("email"),
        }
        for row in rows
    ])
    return [
        _workbench_task_item(row, account=account_rows.get(int(row.get("task_id") or 0)))
        for row in rows
    ]


def _workbench_counts(items: list[dict]) -> dict:
    return {
        "all": len(items),
        "processing": sum(_workbench_status_matches(item, "processing") for item in items),
        "running": sum(_workbench_status_matches(item, "running") for item in items),
        "extraction_succeeded": sum(_workbench_status_matches(item, "extraction_succeeded") for item in items),
        "payment_succeeded": sum(_workbench_status_matches(item, "payment_succeeded") for item in items),
        "plus_confirmed": sum(_workbench_status_matches(item, "plus_confirmed") for item in items),
        "needs_attention": sum(_workbench_status_matches(item, "needs_attention") for item in items),
    }


def preview_workbench_candidates(*, filters: dict | None = None, limit: int = 100) -> dict:
    from core.storage import extract_link_batches

    result = extract_link_batches.candidate_accounts(filters=filters, limit=limit)
    items = result.get("items") or []
    return {
        "total": int(result.get("total") or 0),
        "selected_count": len(items),
        "limit": int(result["limit"]),
        "max_batch_size": extract_link_batches.MAX_BATCH_SIZE,
        "items": items[:20],
    }


def create_workbench_batch(
    *, title: str = "", provider_id: str, mode: str, filters: dict | None = None,
    limit: int = 100, type: str | None = None, options: dict | None = None,
    submission_id: str | None = None, workers: int | None = None,
) -> dict:
    """按提交时筛选快照创建同一批次，逐个任务仍执行既有资格与占用检查。"""
    from core.storage import extract_link_batches, operation

    submission_id = extract_link_batches.normalize_submission_id(submission_id)
    selected_workers = extract_link_batches.normalize_workers(
        _int_setting("EXTRACT_LINK_BATCH_WORKERS", 1, 1, 16) if workers is None else workers,
    )
    if submission_id:
        existing = extract_link_batches.submission_result(submission_id)
        if existing is not None:
            return existing
    provider_id = str(provider_id or "").strip().lower()
    mode = str(mode or "").strip().lower()
    if not _provider_mode_enabled(provider_id, mode):
        raise ValueError("当前配置未启用该平台或运行模式")
    runtime_config = _provider_configuration(provider_id)
    link_type = _provider_link_type(provider_id, type, runtime_config.default_type)
    safe_options = _provider_request_options(provider_id, options, mode=mode, link_type=link_type)
    if mode == "auto_payment" and not runtime_config.capabilities.get("payment"):
        raise ValueError("平台没有可用的支付能力")
    if not isinstance(title, str) or len(title.strip()) > 120:
        raise ValueError("批次名称最多 120 个字符")
    selected_title = title.strip() or f"提链批次 · {datetime.now():%Y-%m-%d %H:%M}"
    if submission_id:
        reservation = extract_link_batches.reserve_submission(
            submission_id=submission_id, title=selected_title, provider_id=provider_id,
            mode=mode, link_type=link_type, filters=filters, limit=limit, workers=selected_workers,
        )
        if not reservation["created"]:
            return reservation["result"]
        batch_id, ids = reservation["batch_id"], reservation["account_ids"]
    else:
        candidates = extract_link_batches.candidate_accounts(filters=filters, limit=limit)
        ids = [int(item["account_id"]) for item in candidates.get("items") or []]
        if not ids:
            raise ValueError("当前筛选没有符合提链条件的账号")
        batch = operation.create_runtime_batch(
            batch_type="extract_link", title=selected_title, requested_count=len(ids),
            trigger="extract_workbench_batch",
            data={
                "workbench_batch": True, "provider_id": provider_id, "mode": mode,
                "link_type": link_type, "filters": candidates["filters"], "limit": candidates["limit"],
                "submission_complete": False, "workers": selected_workers,
            },
        )
        batch_id = int(batch["id"])
    skipped = failed = started = 0
    complete = False
    try:
        for offset in range(0, len(ids), 500):
            result = create_workbench_tasks(
                account_ids=ids[offset:offset + 500], provider_id=provider_id, mode=mode,
                type=link_type, options=safe_options, batch_id=batch_id, dispatch=False,
            )
            skipped += int(result.get("skipped") or 0)
            failed += int(result.get("failed") or 0)
        complete = True
    finally:
        started = extract_link_batches.finish_submission(
            batch_id, skipped=skipped, failed=failed, complete=complete,
        )
        if started:
            account_task_store.notify_dispatch()
    return {"batch_id": batch_id, "requested": len(ids), "started": started, "skipped": skipped, "failed": failed}


def _workbench_batch_summary(batch: dict, aggregate: dict) -> dict:
    data = batch.get("data") if isinstance(batch.get("data"), dict) else {}
    counts = {key: int(aggregate.get(key) or 0) for key in (
        "all", "processing", "running", "extraction_succeeded", "payment_succeeded", "plus_confirmed", "needs_attention",
    )}
    requested = int(batch.get("requested_count") or 0)
    skipped = int(data.get("submission_skipped") or 0)
    failed = int(data.get("submission_failed") or 0)
    incomplete = not data.get("submission_complete") or requested != counts["all"] + skipped + failed
    if counts["running"]:
        status = "running"
    elif counts["processing"]:
        status = "queued" if aggregate.get("task_queued") else "waiting"
    elif incomplete or skipped or failed or counts["needs_attention"]:
        status = "partial_success" if aggregate.get("task_succeeded") or counts["extraction_succeeded"] or counts["payment_succeeded"] else "failed"
    else:
        status = "success" if counts["all"] else "failed"
    created_at = batch.get("created_at")
    workers = data.get("workers")
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 16:
        workers = None
    return {
        "batch_id": int(batch["id"]), "title": str(batch.get("title") or "提链批次")[:240],
        "workers": workers,
        "provider_id": str(data.get("provider_id") or "legacy"), "mode": str(data.get("mode") or "extract_only"),
        "status": status, "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "requested_count": requested, "started_count": counts["all"], "skipped_count": skipped,
        "submission_failed_count": failed, "submission_incomplete": bool(incomplete), "counts": counts,
    }


def list_workbench_batches(*, page: int = 1, page_size: int = 20) -> dict:
    from core.storage import extract_link_batches

    result = extract_link_batches.batch_rows(page=page, page_size=page_size)
    batches = result.get("items") or []
    grouped = extract_link_batches.batch_task_counts([int(batch["id"]) for batch in batches])
    return {**result, "items": [_workbench_batch_summary(batch, grouped.get(int(batch["id"]), {})) for batch in batches]}


def workbench_batch_detail(batch_id: int) -> dict | None:
    from core.storage import extract_link_batches

    batches = extract_link_batches.batch_rows(batch_id=int(batch_id)).get("items") or []
    if not batches:
        return None
    counts = extract_link_batches.batch_task_counts([int(batch_id)])
    return _workbench_batch_summary(batches[0], counts.get(int(batch_id), {}))


def cancel_workbench_batch(batch_id: int) -> dict | None:
    """取消指定工作台批次的排队 Run，保留已经开始执行的任务。"""
    from core import record_store
    from core.storage import extract_link_batches, operation

    if isinstance(batch_id, bool) or not isinstance(batch_id, int) or batch_id < 1:
        raise ValueError("batch_id 参数无效")
    batches = extract_link_batches.batch_rows(batch_id=batch_id).get("items") or []
    if not batches:
        return None
    batch = batches[0]
    data = batch.get("data") if isinstance(batch.get("data"), dict) else {}
    if (data.get("submission_complete") is False
            and data.get("submission_skipped") is None and data.get("submission_failed") is None):
        try:
            created_at = datetime.fromisoformat(str(batch.get("created_at") or "").replace("Z", "+00:00"))
            created_at = created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at
        except ValueError:
            created_at = _WORKBENCH_PROCESS_STARTED_AT
        # 当前服务仍可能继续入队；重启前遗留的未收尾批次可以取消现存队列。
        if created_at >= _WORKBENCH_PROCESS_STARTED_AT:
            raise ValueError("批次正在入队，请等待入队结束后再取消")

    # 先读取完整批次快照，再执行取消，避免列表缩短后翻页漏项。
    # 读取时不按排队状态筛选，worker 开始执行不会挤动后续分页。
    queued_runs = {}
    cancelled_runs = set()
    page = 1
    page_size = 200
    while True:
        tasks = operation.list_tasks(
            batch_id=batch_id, task_type="extract_link", source="native_operations",
            page=page, page_size=page_size,
        )
        items = tasks["items"]
        for task in items:
            run_id = task.get("last_run_id")
            if not run_id:
                continue
            if task.get("status") == "queued":
                queued_runs[int(run_id)] = int(task.get("account_id") or 0)
            elif task.get("status") == "cancelled" and task.get("account_id"):
                cancelled_runs.add(int(run_id))
        if page * page_size >= tasks["total"] or len(items) < page_size:
            break
        page += 1

    cancelled = skipped = failed = 0
    changed = False
    for run_id, account_id in sorted(queued_runs.items()):
        try:
            account = record_store.get_row(record_store.ACCOUNTS, account_id, include_version=True) if account_id else None
            version = account.get("__record_version") if account else None
            result = operation.request_run_cancel(
                run_id, reason="用户取消提链批次的排队任务", expected_status="queued",
            )
            if result.get("cancel_skipped") or result.get("status") != "cancelled":
                skipped += 1
                continue
            changed = True
            if account_id and not extract_link_batches.sync_cancelled_account_extraction(
                run_id, expected_account_version=version,
            ):
                failed += 1
                logger.warning("[提链] 批次取消后的账号状态未同步：batch_id=%s run_id=%s", batch_id, run_id)
                continue
            cancelled += 1
        except LookupError:
            skipped += 1
        except Exception as exc:
            failed += 1
            logger.warning("[提链] 批次排队取消失败：batch_id=%s run_id=%s error_type=%s",
                batch_id, run_id, type(exc).__name__)
    # 重复操作只补齐已取消任务的账号状态，不重复统计为本次新取消。
    for run_id in sorted(cancelled_runs):
        try:
            if not extract_link_batches.sync_cancelled_account_extraction(run_id):
                failed += 1
                logger.warning("[提链] 批次已取消任务的账号状态未同步：batch_id=%s run_id=%s", batch_id, run_id)
        except Exception as exc:
            failed += 1
            logger.warning("[提链] 批次已取消任务的账号状态同步失败：batch_id=%s run_id=%s error_type=%s",
                batch_id, run_id, type(exc).__name__)
    if changed:
        account_task_store.notify_dispatch()
    return {"batch_id": batch_id, "cancelled": cancelled, "skipped": skipped, "failed": failed}


def extract_workbench_task_link(task_id: int, kind: str) -> dict | None:
    from core.storage import extract_link_jobs, operation
    from core.extract_link_providers.contracts import safe_links, safe_payment_artifact

    task = operation.get_task(int(task_id), include_events=False)
    if not task or str(task.get("task_type") or "") != "extract_link":
        return None
    run_id = int(task.get("last_run_id") or 0)
    if not run_id:
        return None
    job = extract_link_jobs.get_provider_job_public(run_id)
    if job:
        state = job.get("public_state") if isinstance(job.get("public_state"), dict) else {}
        artifact = safe_payment_artifact(state.get("payment_artifact"))
        candidates = safe_links(
            *((state.get("links") or []) if kind == "extract" else []),
            artifact.get("payment_page_url") if kind == "extract" else artifact.get("payment_url"),
            artifact.get("payment_page_url"),
            *(state.get("payment_links") or []),
            *(state.get("links") or []),
        )
        if candidates:
            return {"url": candidates[0]}
    data = task.get("data") if isinstance(task.get("data"), dict) else {}
    if str(data.get("provider_id") or "legacy") != "legacy":
        return None
    run = operation.get_run(run_id) or {}
    summary = run.get("result_summary") if isinstance(run.get("result_summary"), dict) else {}
    remote_job_id = str(summary.get("remote_job_id") or "").strip()
    if not summary.get("has_link") or not remote_job_id:
        return None
    account = db.get_account(int(task.get("account_id") or 0)) or {}
    if str(account.get("extract_link_job_id") or "") != remote_job_id:
        return None
    candidate = str(account.get("extract_link_long_url") or "").strip()
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    return {"url": candidate}


def extract_workbench_task_payment_entry(task_id: int) -> dict | None:
    """按需读取本地已保存的支付产物，不触发远端查询或支付。"""
    from core.extract_link_providers.contracts import safe_links, safe_payment_artifact
    from core.storage import extract_link_jobs, operation

    task = operation.get_task(int(task_id), include_events=False)
    if not task or str(task.get("task_type") or "") != "extract_link":
        return None
    run_id = int(task.get("last_run_id") or 0)
    job = extract_link_jobs.get_provider_job_public(run_id) if run_id else None
    state = job.get("public_state") if job and isinstance(job.get("public_state"), dict) else {}
    entry = safe_payment_artifact(state.get("payment_artifact"))
    links = safe_links(*(state.get("links") or []))
    payment_links = safe_links(*(state.get("payment_links") or []))
    if not entry.get("payment_page_url") and links:
        entry["payment_page_url"] = links[0]
    elif not entry.get("payment_page_url") and not entry.get("payment_url") and payment_links:
        entry["payment_page_url"] = payment_links[0]
    if not any(entry.get(name) for name in (
        "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
    )):
        legacy_link = extract_workbench_task_link(int(task_id), "payment")
        if legacy_link:
            entry["payment_page_url"] = legacy_link["url"]
    if not any(entry.get(name) for name in (
        "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
    )):
        return None
    return entry


def extract_workbench_task_detail(task_id: int) -> dict | None:
    from core.storage import extract_link_jobs

    detail = extract_link_jobs.get_workbench_detail_rows(int(task_id))
    if detail is None:
        return None
    item = _workbench_project_rows([detail["item"]])[0]
    history = []
    for run in detail["history"]:
        history.append({
            "run_id": run["run_id"],
            "run_no": run.get("run_no"),
            "status": run.get("status"),
            "provider_id": run["provider_id"],
            "extraction_status": run["extraction_status"],
            "payment_status": run["payment_status"],
            "created_at": run.get("created_at"),
            "completed_at": run.get("completed_at"),
            "message": task_run_log.redact_text(str(run.get("error_message") or ""), 500),
        })
    events = []
    for event in detail["events"]:
        message = task_run_log.redact_text(str(event.get("message") or ""), 500)
        events.append({
            "id": event.get("id"),
            "run_id": event.get("run_id"),
            "stage": str(event.get("stage") or "")[:80],
            "status": str(event.get("status") or "")[:80],
            "label": str(event.get("label") or event.get("stage") or "事件")[:100],
            "message": message,
            "created_at": event.get("created_at"),
        })
    return {"item": item, "history": history, "events": events}


def perform_extract_workbench_action(task_id: int, action: str) -> dict:
    from core.storage import extract_link_jobs, operation

    if not _bool_setting("EXTRACT_LINK_ENABLED", True):
        return {"accepted": False}
    task_id = int(task_id)
    task = operation.get_task(task_id, include_events=False)
    if not task or str(task.get("task_type") or "") != "extract_link":
        return {"accepted": False}
    if str(task.get("source_system") or "") != "native_operations":
        return {"accepted": False}
    if str(task.get("status") or "").lower() in {"queued", "running", "waiting", "cancelling", "settling"}:
        return {"accepted": False}
    data = task.get("data") if isinstance(task.get("data"), dict) else {}
    provider_id = str(data.get("provider_id") or "legacy").strip().lower()
    mode = str(data.get("mode") or "extract_only").strip().lower()
    if provider_id not in _PROVIDER_SETTINGS or not _provider_enabled(provider_id):
        return {"accepted": False}
    runs = task.get("runs") if isinstance(task.get("runs"), list) else []
    latest = max(runs, key=lambda row: (int(row.get("run_no") or 0), int(row.get("id") or 0))) if runs else {}
    latest_run_id = int(latest.get("id") or task.get("last_run_id") or 0)
    prior_job = extract_link_jobs.get_provider_job_public(latest_run_id) if latest_run_id else None
    prior_state = prior_job.get("public_state") if prior_job and isinstance(prior_job.get("public_state"), dict) else {}

    requested_action = str(action or "").strip().lower()
    workbench_action = requested_action
    run_data = {"provider_id": provider_id, "mode": mode}
    if requested_action == "retry":
        halted = provider_id == "huanguang" and (prior_state.get("summary") or {}).get("local_reconcile_halted") is True
        if not halted and _provider_has_reference(prior_job) and str(prior_state.get("extraction_state") or "") not in {"failed"}:
            workbench_action = "sync_status"
        else:
            if not _provider_mode_enabled(provider_id, mode):
                return {"accepted": False}
            workbench_action = "create"
            run_data.update({
                "provider_id": provider_id,
                "mode": mode,
                "link_type": data.get("link_type"),
                "options": data.get("options") if isinstance(data.get("options"), dict) else {},
                "extract_poll_continuation": False,
            })
    elif requested_action in {"sync_status", "manual_payment", "auto_payment"}:
        expected_mode = {
            "manual_payment": "manual_payment",
            "auto_payment": "auto_payment",
        }.get(requested_action)
        if expected_mode and mode != expected_mode:
            return {"accepted": False}
        if expected_mode and not _provider_mode_enabled(provider_id, expected_mode):
            return {"accepted": False}
        if not _provider_has_reference(prior_job):
            return {"accepted": False}
        workbench_action = "sync_status"
    else:
        return {"accepted": False}
    if requested_action == "sync_status" and not prior_job:
        return {"accepted": False}
    if requested_action != "retry":
        if not _provider_has_reference(prior_job):
            return {"accepted": False}
        run_data.update({
            "provider_id": provider_id,
            "mode": mode,
            "provider_job_run_id": latest_run_id,
            **({"extract_poll_continuation": False} if provider_id == "huanguang" else {}),
        })
    else:
        run_data["provider_job_run_id"] = latest_run_id if workbench_action == "sync_status" else None
    run_data["workbench_action"] = workbench_action
    claimed_extract = False
    if requested_action == "retry" and workbench_action == "create":
        account_id = int(task.get("account_id") or 0)
        link_type = str(run_data.get("link_type") or data.get("link_type") or "pix")
        if not account_id or not db.claim_account_extract(
            account_id, trigger="extract_workbench_retry", link_type=link_type,
        ):
            return {"accepted": False}
        claimed_extract = True
    try:
        submitted = operation.retry_runtime_task(
            task_id,
            trigger=f"extract_workbench_{requested_action}",
            data=run_data,
        )
    except Exception:
        if claimed_extract:
            db.update_account_extract(int(task.get("account_id") or 0), {
                "status": "failed", "ok": False, "message": "提链重跑未能入队",
                "error": "提链重跑未能入队",
            })
        raise
    if isinstance(submitted, dict) and isinstance(submitted.get("run"), dict):
        run = submitted["run"]
    elif isinstance(submitted, dict) and submitted.get("id"):
        run = submitted
    else:
        run = {}
    if not run:
        return {"accepted": False}
    account_task_store.notify_dispatch()
    return {"accepted": True, "task_id": task_id, "run_id": int(run.get("id") or 0) or None}


def _call_if_available(target, name: str, *args, **kwargs):
    method = getattr(target, name, None)
    if not callable(method):
        return None
    return method(*args, **kwargs)


def _acquire_huanguang_proxies(context, *, purposes=("entry", "exit")):
    from core import proxy_pool

    leases = []
    resource_ids = []
    try:
        for purpose in purposes:
            context.checkpoint("正在分配幻光提链线路")
            context.report(stage="network", state="running", message=f"正在申请幻光 {purpose} 印度线路，最多等待 45 秒")
            lease = proxy_pool.acquire_proxy(
                purpose=f"extract_link_{purpose}",
                country="IN",
                timeout=45,
                progress_callback=lambda message: context.report(stage="network", message=str(message)),
                cancel=lambda: context.is_cancel_requested(),
                account_id=int(context.account_id),
                operation_task_id=int(context.task_id),
                operation_run_id=int(context.run_id),
                correlation_id=f"extract-link:{context.run_id}:{purpose}",
            )
            leases.append(lease)
            resource = context.register_resource(
                resource_type="proxy_lease",
                provider=str(getattr(lease, "provider", "proxy_pool") or "proxy_pool"),
                external_id=str(getattr(lease, "lease_id", "") or ""),
                detail={"purpose": purpose, "region": str(getattr(lease, "region", "") or "")[:20]},
            )
            resource_ids.append(int(resource.get("id") or 0))
        return leases, resource_ids
    except Exception:
        from core import proxy_provider
        for lease in leases:
            try:
                proxy_provider.release_proxy(lease, reason="extract_link_allocation_failed")
            except Exception:
                logger.exception("[提链] 释放未使用的幻光线路失败")
        for resource_id in resource_ids:
            if resource_id:
                try:
                    context.release_resource(resource_id, state="released")
                except Exception:
                    pass
        raise


def _prepare_huanguang_proxies(context):
    """手动候选优先，只有留空的一侧才领取本地印度线路。"""
    routes = {}
    for purpose in ("entry", "exit"):
        key = f"EXTRACT_LINK_HUANGUANG_{purpose.upper()}_PROXIES"
        routes[purpose] = tuple(validate_value(key, _runtime_setting(key, [])))
    purposes = tuple(purpose for purpose, candidates in routes.items() if not candidates)
    leases, resource_ids = _acquire_huanguang_proxies(context, purposes=purposes) if purposes else ([], [])
    for purpose, lease in zip(purposes, leases):
        routes[purpose] = (lease.proxy_url,)
    return routes, leases, resource_ids


def _release_huanguang_proxies(context, leases, resource_ids, *, terminal: bool) -> None:
    if not terminal:
        return
    from core import proxy_provider
    for lease in leases or []:
        try:
            proxy_provider.release_proxy(lease, reason="extract_link_completed")
        except Exception:
            logger.exception("[提链] 释放幻光线路失败")
    for resource_id in resource_ids or []:
        if resource_id:
            try:
                context.release_resource(resource_id, state="released")
            except Exception:
                logger.exception("[提链] 收口幻光线路资源失败")


def _huanguang_proxy_references(leases, resource_ids):
    """只保留释放统一池租约所需的标识，不复制完整代理地址。"""
    return [{
        "lease_id": lease.lease_id, "provider": lease.provider, "resource_id": resource_id,
        "pool_resource_id": lease.metadata["pool_resource_id"],
        "pool_anchor_id": lease.metadata["pool_anchor_id"],
    } for lease, resource_id in zip(leases, resource_ids)
        if getattr(lease, "metadata", {}).get("pool_resource_id") and lease.metadata.get("pool_anchor_id")]


def _restore_huanguang_proxy_references(private):
    from core.proxy_provider import ProxyLease

    leases, resource_ids = [], []
    refs = private.get("huanguang_proxy_leases")
    for ref in refs[:2] if isinstance(refs, list) else []:
        if not isinstance(ref, dict) or not all(isinstance(ref.get(key), str) and ref[key] for key in (
            "lease_id", "provider", "pool_resource_id", "pool_anchor_id",
        )) or type(ref.get("resource_id")) is not int or ref["resource_id"] <= 0:
            continue
        leases.append(ProxyLease(ref["lease_id"], ref["provider"], "", "", datetime.now(), metadata={
            "pool_resource_id": ref["pool_resource_id"], "pool_anchor_id": ref["pool_anchor_id"],
        }))
        resource_ids.append(ref["resource_id"])
    return leases, resource_ids


def _monitor_provider_job(context, provider, runtime, job, state, *, provider_id, mode, action):
    """在有限预算内跟踪远端任务，并持久化可供排障的安全进度。"""
    from core.extract_link_providers.contracts import ProviderJob

    started_at = time.monotonic()
    deadline = started_at + runtime.event_timeout
    transport = getattr(provider, "transport", None)
    if transport is not None:
        transport.deadline = deadline
    query_count = 0
    errors = 0
    next_wait = runtime.poll_interval
    last_report = started_at
    last_signature = None
    safe_error = ""

    def report_snapshot(*, force=False, request_seconds=None):
        nonlocal last_report, last_signature
        summary = state.get("summary") or {}
        signature = (state["extraction_state"], state["payment_state"], tuple(sorted(summary.items())))
        now = time.monotonic()
        if not force and signature == last_signature and now - last_report < 30:
            return
        labels = {"queued": "排队中", "running": "执行中", "unknown": "待确认", "succeeded": "成功",
                  "failed": "失败", "pending": "等待中", "not_started": "未开始"}
        parts = [f"平台提链：{labels.get(state['extraction_state'], '待确认')}"]
        for key, label in (("current_step", "步骤"), ("percent", "进度"), ("step_attempt", "步骤尝试"),
                           ("run_attempt", "任务尝试"), ("queue_position", "队列位置"), ("failure_code", "失败码")):
            if summary.get(key) is not None:
                parts.append(f"{label} {summary[key]}" + ("%" if key == "percent" else ""))
        if mode != "extract_only":
            parts.append(f"支付：{labels.get(state['payment_state'], '待确认')}")
        if provider_id == "huanguang" and mode == "auto_payment":
            fallback_label = {
                "checking": "确认取消与退次", "submitting": "正在提交备用扫码",
                "submitted": "已转交备用扫码", "existing": "沿用已有备用订单",
                "unavailable": "备用扫码暂不可用", "skipped": "平台未执行转单", "manual_review": "等待人工核实",
            }.get(summary.get("scan_fallback_status"))
            xxsyun_label = {
                "submitting": "正在提交", "awaiting_worker": "等待接单", "claimed": "已接单",
                "verifying": "正在核验", "completed": "扫码完成，等待到账核验", "failed": "扫码失败",
                "expired": "订单已过期", "cancelled": "订单已取消", "rejected": "提交被拒绝",
                "manual_review": "等待人工核实", "credentials_required": "需要恢复订单查询凭据",
            }.get(summary.get("xxsyun_status"))
            if fallback_label:
                parts.append(f"转单：{fallback_label}")
            if xxsyun_label:
                parts.append(f"XXSYUN：{xxsyun_label}")
        parts.append(f"已监控 {int(now - started_at)} 秒，第 {query_count} 次查询")
        detail = {"provider_id": provider_id, "poll_count": query_count, "elapsed_seconds": round(now - started_at, 2),
                  "remaining_seconds": max(0, round(deadline - now, 2)), **summary}
        if request_seconds is not None:
            detail["request_seconds"] = round(request_seconds, 2)
        context.report(stage="payment" if mode != "extract_only" and state["extraction_state"] == "succeeded" else "extraction",
                       message="；".join(parts), detail=detail)
        last_report, last_signature = now, signature

    try:
        report_snapshot(force=True)
        while job.job_id and action != "sync_status":
            summary = state.get("summary") or {}
            if mode == "auto_payment" and summary.get("automatic_payment_requires_reconcile") is True:
                context.report(stage="payment", message="自动支付结果待核实，已停止本次自动查询；可主动同步状态或重跑")
                break
            extraction_pending = state["extraction_state"] in {"queued", "running", "unknown"}
            payment_pending = mode == "auto_payment" and state["payment_state"] in {"not_started", "pending", "unknown"}
            payment_pending = payment_pending and not summary.get("automatic_payment_terminal", False)
            remote_pending = mode in {"manual_payment", "auto_payment"} and summary.get("remote_polling") is True
            if not (extraction_pending or payment_pending or remote_pending):
                break
            if time.monotonic() >= deadline:
                context.report(stage="extraction", message="本次平台监控等待时间已到，已保留远端任务，可继续同步状态或重跑",
                               detail={"poll_count": query_count, "monitor_timeout_seconds": runtime.event_timeout})
                break
            # 分段等待以响应取消，不把剩余监控预算再次花在完整轮询间隔上。
            wait_until = min(deadline, time.monotonic() + next_wait)
            while time.monotonic() < wait_until:
                context.checkpoint()
                time.sleep(max(0, min(5, wait_until - time.monotonic())))
            if time.monotonic() >= deadline:
                continue
            context.checkpoint()
            query_count += 1
            request_started = time.monotonic()
            if query_count == 1 or request_started - last_report >= 30:
                context.report(stage="extraction", message=f"正在查询平台状态（第 {query_count} 次，已监控 {int(request_started - started_at)} 秒），本次请求最多等待 {min(runtime.timeout, deadline - request_started):.1f} 秒",
                               detail={"poll_count": query_count, "elapsed_seconds": round(request_started - started_at, 2)})
                last_report = request_started
            try:
                phase = "query"
                private_data = job.private_data
                status_job = provider.get_status(job.job_id, private_data=_provider_resume_private(provider_id, private_data, state))
                saved = ProviderJob(extraction_state=job.extraction_state, links=job.links, payment_links=job.payment_links,
                                    payment_artifact=job.payment_artifact, private_data=private_data)
                if mode == "auto_payment" and callable(getattr(provider, "get_automatic_payment_status", None)):
                    payment_job = provider.get_automatic_payment_status(job.job_id)
                    status_job = _merge_provider_jobs(status_job, payment_job)
                job = _merge_provider_jobs(saved, status_job)
                state = _safe_provider_job_state(job, mode=mode,
                    preflight_status=state.get("preflight_status", "passed"), plus_status=state.get("plus_status", "not_applicable"),
                    aftercare_status=state.get("aftercare_status", "not_started"))
                if provider_id == "huanguang":
                    from dataclasses import replace
                    private = _record_huanguang_reconcile(context, job.private_data, state, succeeded=True)
                    job = replace(job, private_data=private)
                request_seconds = time.monotonic() - request_started
                logger.info("[提链] 已收到平台状态：run_id=%s provider=%s query=%s 耗时=%.2f秒 提链=%s 支付=%s，正在保存状态",
                            context.run_id, provider_id, query_count, request_seconds, state["extraction_state"], state["payment_state"])
                phase = "save"
                _update_provider_job(context, provider_id, job.job_id, state, job.private_data)
                logger.info("[提链] 平台状态已保存：run_id=%s query=%s 保存耗时=%.2f秒",
                            context.run_id, query_count, time.monotonic() - request_started - request_seconds)
                report_snapshot(request_seconds=request_seconds)
                errors, next_wait, safe_error = 0, runtime.poll_interval, ""
                if provider_id == "huanguang" and _huanguang_reconcile_halt_reason(job.private_data):
                    break
            except (OperationCancelled, account_task_store.OperationLeaseLost):
                raise
            except Exception as exc:
                errors += 1
                safe_error = task_run_log.redact_text(str(exc), 300) if phase == "query" else "平台状态保存暂时失败"
                next_wait = min(30, 10 * errors)
                context.report(stage="extraction", level="warning",
                    message=f"第 {query_count} 次平台状态查询失败，保留上次有效结果，将在 {next_wait} 秒后重试：{safe_error}",
                    detail={"poll_count": query_count, "request_seconds": round(time.monotonic() - request_started, 2)})
                if provider_id == "huanguang" and phase == "query":
                    from dataclasses import replace
                    private = _record_huanguang_reconcile(
                        context, job.private_data, state, succeeded=False, http_status=getattr(exc, "http_status", None),
                    )
                    job = replace(job, private_data=private)
                    _update_provider_job(context, provider_id, job.job_id, state, private)
                    if _huanguang_reconcile_halt_reason(private):
                        break
        return job, state, safe_error
    finally:
        if transport is not None:
            transport.deadline = None


def _payment_aftercare(context, account_id: int, email: str, *, config_snapshot=None) -> tuple[str, str, bool]:
    if not _bool_setting("EXTRACT_LINK_POST_PAYMENT_CHECK_ENABLED", False):
        return "skipped", "", False
    from core import live_check_service

    checked = live_check_service.run_account_live_check_inline(
        account_id=int(account_id),
        email=email,
        trigger="extract_post_payment",
        force_refresh=False,
        operation_context=context,
        config_snapshot=config_snapshot,
    )
    result = checked.get("result") if isinstance(checked, dict) and isinstance(checked.get("result"), dict) else {}
    if result.get("ok"):
        fresh = db.get_account(account_id) or {}
        return "succeeded", str(fresh.get("access_token") or "").strip(), False
    if result.get("status") == "cancelled":
        return "cancelled", "", False
    if not _token_is_invalid_for_extract(result):
        return "failed", "", False
    if not _bool_setting("EXTRACT_LINK_POST_PAYMENT_REFRESH_AT_ENABLED", False):
        return "token_invalid", "", False
    refreshed = live_check_service.run_account_live_check_inline(
        account_id=int(account_id),
        email=email,
        trigger="extract_post_payment_refresh",
        force_refresh=True,
        operation_context=context,
        config_snapshot=config_snapshot,
    )
    refresh_result = refreshed.get("result") if isinstance(refreshed, dict) and isinstance(refreshed.get("result"), dict) else {}
    if not refresh_result.get("ok"):
        return "failed", "", False
    fresh = db.get_account(account_id) or {}
    return "succeeded", str(fresh.get("access_token") or "").strip(), False


def _provider_job_for_sync(run_id: int):
    """跳过旧版同步失败写入的空状态，沿相同远端任务恢复最近有效记录。"""
    from core.storage import extract_link_jobs, operation

    seen = set()
    job = None
    while run_id and run_id not in seen and len(seen) < 20:
        seen.add(run_id)
        current = extract_link_jobs.get_provider_job_private(run_id)
        if not current or (job and (current.get("job_id"), current.get("provider_id")) != (job.get("job_id"), job.get("provider_id"))):
            return job
        job = current
        public = job.get("public_state") or {}
        if public.get("extraction_state") not in {"pending", "unknown"} or public.get("preflight_status") != "failed":
            return job
        run = operation.get_run(run_id) or {}
        data = run.get("data") or {}
        if data.get("workbench_action") != "sync_status":
            return job
        run_id = int(data.get("provider_job_run_id") or 0)
    return job


def _huanguang_scan_completed(state: dict) -> bool:
    """原单已结束扫码，具备发起独立套餐核验的条件。"""
    summary = state.get("summary") or {}
    artifact = state.get("payment_artifact") or {}
    completed = (
        state.get("extraction_state") == "succeeded" and state.get("payment_state") == "unknown"
        and summary.get("automatic_payment_terminal") is True and summary.get("remote_polling") is False
        and summary.get("remote_status") == "DONE"
        and summary.get("remote_terminal_failure") is not True
        and not summary.get("remote_chain_error")
    )
    inferred_complete = (
        artifact.get("payment_status") == "completed" and summary.get("automatic_payment_status") == "COMPLETED"
        and summary.get("platform_plus_status") == "inferred" and summary.get("entitlement_inferred") is True
        and summary.get("entitlement_active") is True and summary.get("payment_check_status") == "completed"
    )
    fallback_complete = (
        summary.get("automatic_payment_status") == "XXSYUN_COMPLETED"
        and summary.get("xxsyun_status") == "completed"
        and artifact.get("payment_status") in {"completed", "verification_unavailable", "payment_check_error"}
    )
    return bool(completed and (inferred_complete or fallback_complete))


def _reconcile_huanguang_automatic_payment(context, state: dict, *, provider_id: str, mode: str, prior_state: dict) -> bool:
    """结合原单扫码完成和独立套餐事实确认付款，保留平台推断标记。"""
    if not (provider_id == "huanguang" and mode == "auto_payment" and _huanguang_scan_completed(state)):
        return False
    summary = state.get("summary") or {}
    from core.storage import extract_link_jobs, operation

    task = operation.get_task(int(context.task_id), include_events=False) or {}
    prior_summary = prior_state.get("summary") or {}
    prior_confirmed = (
        prior_state.get("payment_state") == "succeeded" and prior_state.get("plus_status") == "confirmed"
        and prior_summary.get("payment_confirmation_source") == "local_plan_check"
    )
    if prior_confirmed:
        # 后续查套餐失败不抹掉本任务已经核实的到账事实；远端明确失败仍由上面的状态门槛拦截。
        account = {
            "plan_check_status": "success", "current_plan_type": "plus",
            "plan_checked_at": prior_summary.get("payment_confirmed_plan_checked_at"),
        }
    else:
        account = db.get_account(int(context.account_id)) or {}
    if not extract_link_jobs.independent_plus_is_confirmed(account, task_created_at=task.get("created_at")):
        return False
    checked_at = str(account.get("plan_checked_at") or "").strip() or str(account.get("plan_last_success_at") or "").strip()
    state["payment_state"] = "succeeded"
    state["plus_status"] = "confirmed"
    summary["payment_confirmation_source"] = "local_plan_check"
    summary["payment_confirmed_plan_checked_at"] = checked_at
    summary["automatic_payment_requires_reconcile"] = False
    state["summary"] = summary
    return True


def _handle_provider_operation(context):
    from core.extract_link_providers.contracts import ExtractRequest, ProviderJob
    from core.storage import extract_link_jobs

    data = context.run.get("data") if isinstance(context.run.get("data"), dict) else {}
    provider_id = str(data.get("provider_id") or "legacy").strip().lower()
    mode = str(data.get("mode") or "extract_only").strip().lower()
    action = str(data.get("workbench_action") or "create").strip().lower()
    continuation = provider_id == "huanguang" and data.get("extract_poll_continuation") is True
    if continuation:
        action = "sync_status"
    if context.account_id is None:
        context.finish(status="failed", message="提链缺少账号", error="提链缺少账号")
        return None
    account_id = int(context.account_id)
    account = db.get_account(account_id)
    if not account:
        context.finish(status="cancelled", message="账号不存在，取消提链", error="账号不存在")
        return None
    if db.account_is_deactivated(account):
        context.finish(status="cancelled", message="账号已停用，取消提链", error="账号已停用")
        return None
    from core import plus_promotion
    if action == "create" and not plus_promotion.is_extract_link_eligible(account):
        context.finish(status="failed", message="账号已不符合 Plus 优惠资格，未提交提链", error="账号不符合提链资格")
        return None
    if provider_id not in _PROVIDER_SETTINGS or not _provider_enabled(provider_id):
        context.finish(status="failed", message="平台或运行模式已在配置中关闭", error="平台或运行模式未启用")
        return None
    if action == "create" and not _provider_mode_enabled(provider_id, mode):
        context.finish(status="failed", message="平台或运行模式已在配置中关闭", error="平台或运行模式未启用")
        return None
    runtime = _provider_configuration(provider_id)
    link_type = _provider_link_type(provider_id, data.get("link_type"), runtime.default_type)
    options = _provider_request_options(
        provider_id, data.get("options") or data.get("payment_options"),
        mode=mode, link_type=link_type,
    )
    provider = _provider(provider_id, runtime)
    email = str(account.get("email") or context.email or "").strip()
    prior_run_id = int(data.get("provider_job_run_id") or (context.run_id if continuation else 0))
    prior_job = _provider_job_for_sync(prior_run_id) if prior_run_id else None
    prior_private = prior_job.get("private_data") if prior_job and isinstance(prior_job.get("private_data"), dict) else {}
    job_id = str(prior_job.get("job_id") or "") if prior_job else ""
    state = _safe_provider_job_state(
        ProviderJob(job_id=job_id or None, extraction_state="pending"),
        mode=mode,
        preflight_status="pending",
        plus_status="not_applicable",
    )
    if action == "sync_status" and prior_job:
        prior_state = prior_job.get("public_state") or {}
        state = _safe_provider_job_state(ProviderJob(
            job_id=job_id, extraction_state=prior_state.get("extraction_state", "unknown"),
            payment_state=prior_state.get("payment_state", "not_started"),
            links=tuple(prior_state.get("links") or ()), payment_links=tuple(prior_state.get("payment_links") or ()),
            payment_artifact=prior_state.get("payment_artifact") or {}, summary=prior_state.get("summary") or {},
        ), mode=mode, preflight_status=prior_state.get("preflight_status", "passed"),
            plus_status=prior_state.get("plus_status", "not_applicable"),
            aftercare_status=prior_state.get("aftercare_status", "not_started"))
    if provider_id == "huanguang" and action == "sync_status" and prior_job:
        prior_private = _record_huanguang_reconcile(
            context, prior_private, state, started_at=prior_job.get("created_at") or context.run.get("created_at"),
        )
        if state.get("summary", {}).get("local_reconcile_halted") is True:
            prior_private["local_reconcile"]["halted_reason"] = state["summary"].get("local_reconcile_reason") or "timeout"
    leases = []
    proxy_resource_ids = []
    if provider_id == "huanguang" and prior_private:
        leases, proxy_resource_ids = _restore_huanguang_proxy_references(prior_private)
    remote_write_started = False
    latest_token = ""
    schedule_plan_check = False
    terminal_status = "failed"
    status_message = "提链失败"
    safe_error = ""

    with context.lease(resource_family="openai_interactive"), _huanguang_create_quota(
        context, runtime, provider_id=provider_id, mode=mode, action=action,
    ) as quota_ready:
        if not quota_ready:
            return None
        try:
            context.checkpoint()
            if (provider_id == "huanguang" and continuation
                    and state.get("summary", {}).get("local_reconcile_halted") is True):
                reason = state["summary"].get("local_reconcile_reason") or "timeout"
                _halt_huanguang_reconcile(context, state, prior_private, job_id=job_id, mode=mode, reason=reason,
                                         leases=leases, proxy_resource_ids=proxy_resource_ids)
                return None
            if action == "create":
                if not db.mark_account_extract_running(account_id):
                    raise RuntimeError("账号提链状态无法转为运行中")
                preflight_enabled = _bool_setting("EXTRACT_LINK_PREFLIGHT_ENABLED", True)
                refresh_at_enabled = preflight_enabled and _bool_setting("EXTRACT_LINK_PREFLIGHT_REFRESH_AT_ENABLED", True)
                state["preflight_status"] = "running" if preflight_enabled else "skipped"
                state["message"] = "正在检查账号与 AT" if preflight_enabled else "提链前预检已关闭，直接使用数据库 AT"
                _update_provider_job(context, provider_id, None, state, {})
                context.report(stage="preflight", state="running" if preflight_enabled else "skipped", message=state["message"],
                               detail={"provider_id": provider_id, "mode": mode, "request_timeout_seconds": runtime.timeout,
                                       "monitor_timeout_seconds": runtime.event_timeout, "poll_interval_seconds": runtime.poll_interval})
                if not refresh_at_enabled:
                    context.report(stage="refresh_token", state="skipped", message="预检刷新 AT 已关闭" if preflight_enabled else "预检已关闭，跳过刷新 AT")
                latest_token = _ensure_extract_token(
                    account_id=account_id,
                    email=email,
                    progress=lambda message: context.report(stage="preflight", message=message),
                    on_refresh_start=lambda: context.report(stage="refresh_token", state="running", message="AT 已确认失效，正在刷新"),
                    on_refresh_success=lambda: context.report(stage="refresh_token", state="success", message="AT 刷新成功"),
                    operation_context=context,
                    config_snapshot=context.config_snapshot,
                    preflight_enabled=preflight_enabled,
                    refresh_at_enabled=refresh_at_enabled,
                )
                state["preflight_status"] = "passed" if preflight_enabled else "skipped"
                state["message"] = "账号查活通过，已使用数据库最新 AT" if preflight_enabled else "预检已跳过，已读取数据库最新 AT"
                _update_provider_job(context, provider_id, None, state, {})
                if preflight_enabled:
                    context.report(stage="preflight", state="success", message=state["message"])
                else:
                    context.report(stage="access_token", state="success", message=state["message"])
                proxy_routes = {}
                if provider_id == "huanguang":
                    proxy_routes, leases, proxy_resource_ids = _prepare_huanguang_proxies(context)
                    references = _huanguang_proxy_references(leases, proxy_resource_ids)
                    if references:
                        prior_private["huanguang_proxy_leases"] = references
                        _update_provider_job(context, provider_id, None, state, prior_private)
                def checkpoint_submission(private_data):
                    nonlocal prior_private
                    prior_private = {**prior_private, **private_data}
                    state["summary"].update({"submission_receipt_pending": True, "remote_polling": True})
                    _update_provider_job(context, provider_id, None, state, prior_private)

                request_data = ExtractRequest(
                    account_id=account_id,
                    access_token=latest_token,
                    link_type=link_type,
                    mode=mode,
                    idempotency_key=f"extract-link:{context.run_id}",
                    options=options,
                    entry_proxies=proxy_routes.get("entry", ()),
                    exit_proxies=proxy_routes.get("exit", ()),
                    submission_checkpoint=checkpoint_submission if provider_id == "huanguang" else None,
                )
                context.report(stage="extraction", state="running", message=f"正在向 {provider_id} 提交提链任务")
                request_id = str(uuid.uuid4())
                if callable(getattr(context, "remote_request_started", None)):
                    context.remote_request_started(
                        "extract_link_create",
                        request_id=request_id,
                        detail={"provider_id": provider_id, "mode": mode, "run_id": context.run_id},
                    )
                remote_write_started = True
                job = provider.create_job(request_data)
                if callable(quota_ready):
                    quota_ready()
                job_id = str(job.job_id or "").strip()
                state = _safe_provider_job_state(
                    job,
                    mode=mode,
                    preflight_status=state["preflight_status"],
                    plus_status="not_applicable",
                )
                if provider_id == "huanguang":
                    from dataclasses import replace
                    private = _record_huanguang_reconcile(
                        context, {**prior_private, **job.private_data}, state,
                        succeeded=True, started_at=datetime.now(timezone.utc),
                    )
                    job = replace(job, private_data=private)
                if job_id:
                    _update_provider_job(context, provider_id, job_id, state, job.private_data)
                    if callable(getattr(context, "remote_request_receipt", None)):
                        context.remote_request_receipt(
                            outcome="confirmed",
                            action="extract_link_create",
                            request_id=request_id,
                            detail={
                                "provider_id": provider_id,
                                "remote_job_id": job_id,
                                "remote_result_confirmed": True,
                                "local_business_writeback_confirmed": True,
                                "local_readback_confirmed": True,
                                "response_observed": True,
                            },
                        )
                else:
                    _update_provider_job(context, provider_id, None, state, job.private_data)
                    if str(state.get("summary", {}).get("outcome") or "").upper() == "REJECTED":
                        if callable(getattr(context, "remote_request_receipt", None)):
                            context.remote_request_receipt(
                                outcome="rejected",
                                action="extract_link_create",
                                request_id=request_id,
                                detail={"response_observed": True, "remote_result_confirmed": False},
                            )
                        terminal_status = "failed"
                        failure_message = state.get("summary", {}).get("failure_message")
                        status_message = "平台已明确拒绝提链请求" + (f"：{failure_message}" if failure_message else "")
                        context.report(
                            stage="extraction", state="failed", message=status_message,
                            detail={"cause_code": "extract_provider_failed", "error_code": "extract_provider_failed"},
                        )
                        raise RuntimeError(status_message)
                    if callable(getattr(context, "remote_request_receipt", None)):
                        context.remote_request_receipt(
                            outcome="response_received",
                            action="extract_link_create",
                            request_id=request_id,
                            detail={"response_observed": True, "remote_result_confirmed": False},
                        )
                    if not (provider_id == "huanguang" and state["summary"].get("submission_receipt_pending") is True):
                        terminal_status = "request_unknown"
                        status_message = "平台响应未能确认远端任务，保留结果并允许后续重跑"
                        raise RuntimeError("request_unknown: 提链服务未返回可确认的任务 ID")
                if mode == "auto_payment" and callable(getattr(provider, "get_automatic_payment_status", None)):
                    payment_job = provider.get_automatic_payment_status(job_id)
                    job = _merge_provider_jobs(job, payment_job)
                    state = _safe_provider_job_state(
                        job,
                        mode=mode,
                        preflight_status=state["preflight_status"],
                        plus_status="not_applicable",
                    )
                    _update_provider_job(context, provider_id, job_id, state, job.private_data)
            elif action == "sync_status":
                if not _provider_has_reference(prior_job):
                    raise RuntimeError("没有可同步的远端任务")
                # 首次恢复可能引用旧 Run；在任何网络读取前落盘当前 Run 的恢复引用。
                _update_provider_job(context, provider_id, job_id or None, state, prior_private)
                context.report(stage="extraction", message=f"正在读取已有远端任务状态，本次请求最多等待 {runtime.timeout} 秒")
                job = provider.get_status(job_id, private_data=_provider_resume_private(provider_id, prior_private, state))
                context.checkpoint()
                job_id = str(job.job_id or job_id or "").strip()
                saved_state = prior_job.get("public_state") if isinstance(prior_job.get("public_state"), dict) else {}
                job = _merge_provider_jobs(ProviderJob(
                    extraction_state=saved_state.get("extraction_state", "unknown"),
                    links=tuple(saved_state.get("links") or ()),
                    payment_links=tuple(saved_state.get("payment_links") or ()),
                    payment_artifact=saved_state.get("payment_artifact") or {},
                ), job)
                state = _safe_provider_job_state(
                    job,
                    mode=mode,
                    preflight_status=prior_job.get("public_state", {}).get("preflight_status", "passed"),
                    plus_status=prior_job.get("public_state", {}).get("plus_status", "not_applicable"),
                    aftercare_status=prior_job.get("public_state", {}).get("aftercare_status", "not_started"),
                )
                if (
                    mode == "manual_payment"
                    and state["extraction_state"] == "succeeded"
                    and callable(getattr(provider, "sync_payment_state", None))
                    and _provider_payment_sync_due(job.private_data or prior_private)
                ):
                    payment_job = provider.sync_payment_state(job_id)
                    job = _merge_provider_jobs(job, payment_job)
                    state = _safe_provider_job_state(
                        job,
                        mode=mode,
                        preflight_status=state["preflight_status"],
                        plus_status=state["plus_status"],
                        aftercare_status=state["aftercare_status"],
                    )
                elif mode == "auto_payment" and callable(getattr(provider, "get_automatic_payment_status", None)):
                    payment_job = provider.get_automatic_payment_status(job_id)
                    job = _merge_provider_jobs(job, payment_job)
                    state = _safe_provider_job_state(
                        job,
                        mode=mode,
                        preflight_status=state["preflight_status"],
                        plus_status=state["plus_status"],
                        aftercare_status=state["aftercare_status"],
                    )
                _update_provider_job(context, provider_id, job_id, state, job.private_data or prior_private)
                intent = data.get("remote_intent")
                if (provider_id == "huanguang" and isinstance(intent, dict)
                        and intent.get("action") == "extract_link_create"
                        and (intent.get("receipt_state") or intent.get("state")) not in {"confirmed", "rejected", "not_submitted"}):
                    if job_id:
                        context.remote_request_receipt(
                            outcome="confirmed", action="extract_link_create", request_id=intent.get("request_id"),
                            detail={"provider_id": provider_id, "remote_job_id": job_id, "remote_result_confirmed": True,
                                    "local_business_writeback_confirmed": True, "local_readback_confirmed": True,
                                    "response_observed": True},
                        )
                    elif state.get("summary", {}).get("outcome") == "REJECTED":
                        context.remote_request_receipt(
                            outcome="rejected", action="extract_link_create", request_id=intent.get("request_id"),
                            detail={"response_observed": True, "remote_result_confirmed": False},
                        )
            else:
                raise ValueError("提链操作类型无效")

            job, state, safe_error = _monitor_provider_job(
                context, provider, runtime, job, state,
                provider_id=provider_id, mode=mode, action=action,
            )
            if provider_id == "huanguang":
                from dataclasses import replace
                private = _record_huanguang_reconcile(
                    context, {**prior_private, **job.private_data}, state,
                    succeeded=True if action == "sync_status" else None,
                )
                job = replace(job, private_data=private)
                if _huanguang_needs_continuation(state):
                    reason = _huanguang_reconcile_halt_reason(private)
                    if reason:
                        _halt_huanguang_reconcile(context, state, private, job_id=job_id, mode=mode, reason=reason,
                                                 leases=leases, proxy_resource_ids=proxy_resource_ids)
                        return None
                else:
                    # 手动核对已取得终态时清除本地收口标记，保留新的平台终态。
                    private["local_reconcile"].pop("halted_reason", None)
                    private["local_reconcile"].pop("halted_at", None)
                    state["summary"]["local_reconcile_halted"] = False
            if (
                provider_id == "huanguang" and mode == "auto_payment"
                and state["extraction_state"] == "succeeded" and state["payment_state"] == "not_started"
            ):
                state["payment_state"] = "unknown"
            local_payment_confirmed = _reconcile_huanguang_automatic_payment(
                context, state, provider_id=provider_id, mode=mode,
                prior_state=(prior_job or {}).get("public_state") or {},
            )
            if (provider_id == "huanguang" and callable(getattr(context, "defer", None))
                    and (job_id or state["summary"].get("submission_receipt_pending") is True)
                    and _huanguang_needs_continuation(state)):
                state["message"] = "等待平台原单同步"
                _update_provider_job(context, provider_id, job_id or None, state, job.private_data or prior_private)
                _release_huanguang_proxies(context, leases, proxy_resource_ids, terminal=False)
                _defer_huanguang_job(context, runtime, state)
                return None
            scan_awaiting_verification = (
                provider_id == "huanguang" and mode == "auto_payment" and _huanguang_scan_completed(state)
                and _bool_setting("EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED", False)
            )
            if state["payment_state"] == "succeeded" or scan_awaiting_verification:
                context.report(
                    stage="payment", state="pending" if scan_awaiting_verification else "success",
                    message=("扫码已完成，等待独立套餐核验" if scan_awaiting_verification else
                             "扫码完成，独立套餐查询已确认 Plus 到账" if local_payment_confirmed else "平台已确认支付成功"),
                    detail={"payment_confirmation_source": "local_plan_check"} if local_payment_confirmed else {},
                )
                aftercare = state.get("aftercare_status") or "not_started"
                if not local_payment_confirmed and aftercare in {"not_started", "pending"}:
                    aftercare_status, latest_token, _ = _payment_aftercare(
                        context, account_id, email, config_snapshot=context.config_snapshot,
                    )
                    state["aftercare_status"] = aftercare_status
                    if aftercare_status == "succeeded":
                        context.report(stage="aftercare", state="success", message="支付后账号查活完成")
                    elif aftercare_status == "skipped":
                        context.report(stage="aftercare", state="skipped", message="支付后查活按配置关闭")
                    elif aftercare_status == "token_invalid":
                        context.report(stage="aftercare", state="failed", message="支付后 AT 已失效，自动刷新按配置关闭")
                    else:
                        context.report(stage="aftercare", state="failed", message="支付后账号查活未完成")
                if scan_awaiting_verification:
                    from core import plan_check_service
                    state["plus_status"] = "pending"
                    state["summary"]["local_plan_check_pending"] = True
                    state["message"] = "扫码已完成，正在独立核验 Plus 套餐"
                    _update_provider_job(context, provider_id, job_id or None, state, job.private_data or prior_private)
                    current = db.get_account(account_id) or {}
                    token = str(current.get("access_token") or latest_token or "").strip()
                    try:
                        checked = plan_check_service.run_account_plan_check_inline(
                            account_id=account_id, email=email, access_token=token,
                            trigger="extract_post_payment", operation_context=context,
                        )
                    except (account_task_store.OperationLeaseLost, OperationCancelled):
                        raise
                    except Exception as exc:
                        logger.warning("[提链] 内联套餐核验未完成: run_id=%s error=%s", context.run_id,
                                       task_run_log.redact_text(str(exc), 300))
                        checked = {"accepted": False}
                    context.checkpoint()
                    state["summary"]["local_plan_check_pending"] = False
                    checked_result = checked.get("result") if isinstance(checked, dict) else None
                    checked_result = checked_result if isinstance(checked_result, dict) else {}
                    if checked_result.get("status") == "cancelled" or checked_result.get("cancelled") is True:
                        raise OperationCancelled("独立套餐核验已取消")
                    local_payment_confirmed = _reconcile_huanguang_automatic_payment(
                        context, state, provider_id=provider_id, mode=mode,
                        prior_state=(prior_job or {}).get("public_state") or {},
                    )
                    if not local_payment_confirmed:
                        state["plus_status"] = "not_confirmed" if checked_result.get("ok") else "failed"
                if local_payment_confirmed:
                    state["plus_status"] = "confirmed"
                elif not scan_awaiting_verification and _bool_setting("EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED", False):
                    schedule_plan_check = True
                    state["plus_status"] = "pending"
                elif not scan_awaiting_verification:
                    state["plus_status"] = "not_applicable"
                context.report(
                    stage="plus", state=("success" if local_payment_confirmed else "pending" if state["plus_status"] == "pending"
                                        else "failed" if state["plus_status"] in {"failed", "not_confirmed"} else "skipped"),
                    message=("独立套餐查询已确认 Plus 到账" if local_payment_confirmed else
                             "独立套餐查询尚未确认 Plus 到账" if state["plus_status"] == "not_confirmed" else
                             "独立套餐核验失败，可同步原单重查" if state["plus_status"] == "failed" else "Plus 权益核验状态已单独记录"),
                    detail={"plus_status": state["plus_status"]},
                )
            elif mode == "extract_only":
                state["payment_state"] = "not_started"
                state["plus_status"] = "not_applicable"
            else:
                state["plus_status"] = "not_applicable"

            extraction = state["extraction_state"]
            payment = state["payment_state"]
            terminal_extraction = (extraction in {"succeeded", "failed"}
                and state.get("summary", {}).get("remote_polling") is not True
                and not state.get("summary", {}).get("remote_chain_error"))
            if provider_id == "huanguang":
                _release_huanguang_proxies(context, leases, proxy_resource_ids, terminal=terminal_extraction)
            if extraction == "succeeded":
                terminal_status = "success"
                status_message = "提链成功"
                context.report(stage="extraction", state="success", message="提链成功")
                if mode == "auto_payment" and payment in {"unknown", "pending"}:
                    terminal_status = "request_unknown" if payment == "unknown" else "partial_success"
                    status_message = "提链成功，自动支付状态待确认"
                elif local_payment_confirmed:
                    status_message = "提链并支付成功，独立套餐查询已确认 Plus 到账"
                elif mode == "manual_payment" and payment not in {"succeeded", "failed"}:
                    status_message = "提链成功，等待手动支付"
            elif extraction == "failed":
                terminal_status = "failed"
                failure_message = state.get("summary", {}).get("failure_message")
                status_message = f"平台提链失败：{failure_message}" if failure_message else "平台提链失败，平台未提供失败细项"
                context.report(
                    stage="extraction", state="failed", message=status_message,
                    detail={"cause_code": "extract_provider_failed", "error_code": "extract_provider_failed"},
                )
            elif terminal_status != "request_unknown":
                terminal_status = "request_unknown"
                status_message = "远端任务状态暂未收敛，保留任务以便继续同步"

            if mode == "extract_only":
                context.report(stage="payment", state="skipped", message="仅提链模式未触发任何支付接口")
            elif payment == "succeeded":
                context.report(stage="payment", state="success", message="支付成功")
            elif payment == "failed":
                context.report(stage="payment", state="failed", message="平台确认支付失败")
            elif payment in {"pending", "not_started"}:
                context.report(stage="payment", state="pending", message="等待支付或手动付款")
            else:
                # 业务结果保留 unknown，步骤契约用 pending 表示仍需确认。
                context.report(stage="payment", state="pending", message="支付状态待确认",
                               detail={"payment_state": state["payment_state"]})

            state["message"] = status_message
            _update_provider_job(context, provider_id, job_id or None, state, job.private_data if "job" in locals() else prior_private)
            artifact = state.get("payment_artifact") or {}
            checkout_url = (state.get("links") or [None])[0] or artifact.get("payment_page_url") or (state.get("payment_links") or [None])[0]
            result_summary = {
                "provider_id": provider_id,
                "mode": mode,
                "ok": extraction == "succeeded",
                "status": "success" if extraction == "succeeded" else terminal_status,
                "message": status_message,
                "link_type": link_type,
                "has_link": bool(checkout_url or artifact.get("payment_url")),
                "has_qr": bool(any(artifact.get(key) for key in ("qr_data", "qr_image_url_png", "qr_image_url_svg"))),
                "extraction_status": extraction,
                "payment_status": payment,
                "preflight_status": state.get("preflight_status"),
                "aftercare_status": state.get("aftercare_status"),
                "plus_status": state.get("plus_status"),
                "remote_job_created": bool(job_id),
                "outcome": state.get("summary", {}).get("outcome"),
            }
            if local_payment_confirmed:
                result_summary.update({
                    "payment_confirmation_source": "local_plan_check",
                    "payment_confirmed_plan_checked_at": state["summary"]["payment_confirmed_plan_checked_at"],
                })
            if extraction == "failed":
                result_summary.update({
                    "cause_code": "extract_provider_failed",
                    "remote_result_state": "failed",
                    "remote_terminal_failure": state.get("summary", {}).get("remote_terminal_failure") is True,
                    "remote_status": state.get("summary", {}).get("remote_status"),
                    "failure_message": state.get("summary", {}).get("failure_message") or "平台未提供失败细项",
                })
            result = {
                "ok": extraction == "succeeded",
                "status": "success" if extraction == "succeeded" else terminal_status,
                "job_id": job_id or None,
                "link_type": link_type,
                "message": status_message,
                "result": {
                    "long_url": (state.get("links") or [None])[0],
                    "payment_link": (state.get("payment_links") or [None])[0],
                },
            }
            if action == "create" or continuation:
                db.update_account_extract(account_id, result)
            if callable(getattr(context, "finish", None)) and not getattr(context, "finished", False):
                context.finish(
                    status=terminal_status,
                    message=status_message,
                    error=safe_error or (status_message if terminal_status in {"failed", "request_unknown"} else None),
                    result_summary=result_summary,
                )
            if schedule_plan_check:
                current = db.get_account(account_id) or {}
                token = str(current.get("access_token") or latest_token or "").strip()
                if token:
                    from core import plan_check_service
                    result = plan_check_service.enqueue_account_plan_check(
                        account_id=account_id,
                        email=email,
                        access_token=token,
                        trigger="extract_post_payment",
                        idempotency_key=f"extract-workbench:{context.task_id}:payment-success",
                    )
                    if result.get("accepted"):
                        state["plus_status"] = "pending"
                    else:
                        state["plus_status"] = "failed"
                        state["message"] = "扫码已完成，但 Plus 套餐核验未能排队"
                else:
                    state["plus_status"] = "failed"
                    state["message"] = "扫码已完成，但数据库没有可用 AT 供套餐核验"
                extract_link_jobs.update_provider_job_state(context.run_id, state)
            return None
        except account_task_store.OperationLeaseLost:
            raise
        except OperationCancelled as exc:
            safe_error = task_run_log.redact_text(str(exc), 300)
            if remote_write_started and mode == "auto_payment" and state.get("payment_state") not in {"succeeded", "failed"}:
                state["payment_state"] = "unknown"
            state["preflight_status"] = "cancelled" if state.get("preflight_status") in {"pending", "running"} else state["preflight_status"]
            if mode == "extract_only" or state.get("payment_state") != "succeeded":
                state["plus_status"] = "not_applicable"
            state["message"] = "提链已取消"
            try:
                _update_provider_job(context, provider_id, job_id or None, state, prior_private)
            except Exception:
                logger.exception("[提链] 保存取消状态失败: run_id=%s", context.run_id)
            if provider_id == "huanguang":
                _release_huanguang_proxies(context, leases, proxy_resource_ids, terminal=False)
            if action == "create":
                db.update_account_extract(account_id, {
                    "status": "stopped", "ok": False, "link_type": link_type,
                    "message": "提链已取消", "error": safe_error,
                })
            if not getattr(context, "finished", False):
                context.finish(status="cancelled", message="提链已取消", error=safe_error)
            return None
        except Exception as exc:
            safe_error = task_run_log.redact_text(str(exc), 500)
            if (provider_id == "huanguang" and action == "sync_status"
                    and _provider_has_reference(prior_job) and callable(getattr(context, "defer", None))):
                context.checkpoint()
                prior_private = _record_huanguang_reconcile(
                    context, prior_private, state, succeeded=False, http_status=getattr(exc, "http_status", None),
                )
                reason = _huanguang_reconcile_halt_reason(prior_private)
                if reason:
                    _halt_huanguang_reconcile(context, state, prior_private, job_id=job_id, mode=mode, reason=reason,
                                             leases=leases, proxy_resource_ids=proxy_resource_ids)
                    return None
                state["message"] = "原单查询暂时失败，等待重试"
                _update_provider_job(context, provider_id, job_id or None, state, prior_private)
                context.report(stage="extraction", level="warning", message=f"原单查询暂时失败，保留上次结果并稍后续查：{safe_error}")
                _defer_huanguang_job(context, runtime, state, reason="原单查询暂时失败，等待重试")
                return None
            remote_rejected = str(state.get("summary", {}).get("outcome") or "").upper() == "REJECTED"
            if remote_write_started and terminal_status != "request_unknown" and not remote_rejected:
                terminal_status = "request_unknown"
                status_message = "远端提链结果待确认"
            elif terminal_status != "request_unknown" and not remote_rejected:
                terminal_status = "failed"
                status_message = "提链失败"
            if action == "sync_status":
                status_message = "同步状态失败，已保留上次平台结果"
                context.report(stage="extraction", level="warning", message=f"{status_message}：{safe_error}")
            if (
                remote_write_started
                and not remote_rejected
                and mode == "auto_payment"
                and state.get("payment_state") not in {"succeeded", "failed"}
            ):
                state["payment_state"] = "unknown"
            state["message"] = status_message
            if state.get("preflight_status") in {"pending", "running"}:
                state["preflight_status"] = "failed"
                context.report(stage="preflight", state="failed", message=f"提链前预检失败：{safe_error}")
            if mode == "extract_only" or state.get("payment_state") != "succeeded":
                state["plus_status"] = "not_applicable"
            if provider_id in _PROVIDER_SETTINGS:
                try:
                    _update_provider_job(context, provider_id, job_id or None, state, prior_private)
                except Exception:
                    logger.exception("[提链] 保存平台状态失败: run_id=%s", context.run_id)
            if provider_id == "huanguang":
                _release_huanguang_proxies(
                    context, leases, proxy_resource_ids,
                    terminal=(action == "create" and not remote_write_started) or remote_rejected or bool(
                        job_id and state.get("extraction_state") in {"succeeded", "failed"}
                        and state.get("summary", {}).get("remote_polling") is not True
                        and not state.get("summary", {}).get("remote_chain_error")),
                )
            if action == "create":
                db.update_account_extract(account_id, {
                    "status": "request_unknown" if terminal_status == "request_unknown" else "failed",
                    "ok": False, "link_type": link_type,
                    "job_id": job_id or None, "message": status_message, "error": safe_error,
                })
            if not getattr(context, "finished", False):
                context.finish(
                    status=terminal_status,
                    message=status_message,
                    error=safe_error,
                    result_summary={
                        "message": status_message,
                        "provider_id": provider_id,
                        "mode": mode,
                        "preflight_status": state.get("preflight_status"),
                        "extraction_status": state.get("extraction_state"),
                        "payment_status": state.get("payment_state"),
                        "remote_job_created": bool(job_id),
                        **({"cause_code": "extract_provider_failed", "remote_result_state": "rejected"} if remote_rejected else {}),
                    },
                )
            return None


def _merge_provider_jobs(primary, secondary):
    from core.extract_link_providers.contracts import ProviderJob, safe_payment_artifact

    if not isinstance(primary, ProviderJob):
        primary = ProviderJob()
    if not isinstance(secondary, ProviderJob):
        return primary
    if isinstance(secondary.private_data, dict) and secondary.private_data.get("job_chain"):
        # 幻光 Provider 已按节点保留历史材料；当前付款入口只能属于当前节点。
        return secondary
    artifact = safe_payment_artifact(primary.payment_artifact)
    confirmed_extraction = primary.extraction_state == "succeeded" and bool(
        primary.links or primary.payment_links or any(artifact.get(key) for key in (
            "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
        ))
    )
    return ProviderJob(
        job_id=secondary.job_id or primary.job_id,
        extraction_state="succeeded" if confirmed_extraction else secondary.extraction_state if secondary.extraction_state != "unknown" else primary.extraction_state,
        payment_state=secondary.payment_state if secondary.payment_state != "not_started" else primary.payment_state,
        links=tuple(dict.fromkeys((*primary.links, *secondary.links))),
        payment_links=tuple(dict.fromkeys((*primary.payment_links, *secondary.payment_links))),
        payment_artifact={**safe_payment_artifact(primary.payment_artifact), **safe_payment_artifact(secondary.payment_artifact)},
        private_data={**(primary.private_data or {}), **(secondary.private_data or {})},
        summary={**(primary.summary or {}), **(secondary.summary or {})},
    )


def _handle_extract_operation(context):
    data = context.run.get("data") if isinstance(context.run.get("data"), dict) else {}
    if data.get("provider_id"):
        return _handle_provider_operation(context)
    if not _provider_mode_enabled("legacy", "extract_only"):
        context.finish(status="failed", message="提链平台或提取能力已关闭", error="提链功能未启用")
        return None
    if context.account_id is None:
        context.finish(status="failed", message="提链缺少账号", error="提链缺少账号")
        return None
    account = db.get_account(int(context.account_id))
    if not account:
        context.finish(status="cancelled", message="账号不存在，取消提链", error="账号不存在")
        return None
    email = str(account.get("email") or context.email or "").strip()
    link_type = str(
        data.get("link_type")
        or _snapshot_value(context.config_snapshot, "link_type", "pix")
        or "pix"
    ).strip().lower()
    # CDK is a connection secret.  Durable data contains no copy; resolve it
    # once at claim time and keep it only in the worker's local call chain.
    cdk = _cdk()
    with context.lease(resource_family="openai_interactive"):
        _run_extract(
            account_id=int(context.account_id),
            email=email,
            # The worker deliberately re-reads the account after preflight;
            # never persist or trust an access-token enqueue snapshot.
            access_token="",
            link_type=link_type,
            cdk=cdk,
            trigger=str(context.run.get("trigger") or "manual"),
            payment_options=data.get("payment_options") if isinstance(data.get("payment_options"), dict) else None,
            task_id=int(context.task_id),
            operation_context=context,
            release_queue_slot=False,
            config_snapshot=context.config_snapshot,
        )
    return None


def register_operation_handlers() -> bool:
    register = getattr(account_task_store, "register_operation_handler", None)
    if not callable(register):
        return False
    register(
        "extract_link",
        _handle_extract_operation,
        source_systems=("native_operations",),
        config_allowlist=EXTRACT_CONFIG_ALLOWLIST,
        dispatch_capacity_key=_provider_dispatch_capacity_key,
        dispatch_capacity_limit=_provider_dispatch_capacity_limit,
    )
    return True


def resume_known_remote_jobs(*, continuous_only: bool = False) -> int:
    """服务启动时为已知远端任务排队状态同步，避免等待人工重跑。"""
    if not _bool_setting("EXTRACT_LINK_ENABLED", True):
        return 0
    from core.storage import extract_link_jobs, operation

    resumed = 0
    for item in extract_link_jobs.list_recoverable_workbench_jobs():
        provider_id = str(item.get("provider_id") or "legacy").strip().lower()
        if continuous_only and provider_id != "huanguang":
            continue
        mode = str(item.get("mode") or "extract_only").strip().lower()
        task_id = int(item.get("task_id") or 0)
        run_id = int(item.get("run_id") or 0)
        if (
            task_id <= 0
            or run_id <= 0
            or provider_id not in _PROVIDER_SETTINGS
            or not _provider_enabled(provider_id)
        ):
            continue
        try:
            queued = operation.retry_runtime_task(
                task_id,
                trigger="extract_workbench_restart_sync",
                data={
                    "provider_id": provider_id,
                    "mode": mode,
                    "workbench_action": "sync_status",
                    "provider_job_run_id": int(item.get("provider_job_run_id") or run_id),
                    **({"extract_poll_continuation": True} if provider_id == "huanguang" else {}),
                },
            )
        except Exception:
            continue
        if queued:
            resumed += 1
    if resumed:
        account_task_store.notify_dispatch()
    return resumed


def start_dispatcher() -> bool:
    if not register_operation_handlers():
        return False
    starter = getattr(account_task_store, "start_dispatcher", None)
    return bool(starter()) if callable(starter) else False


def _submit_native_extract(
    *, account_id: int, email: str, trigger: str, link_type: str, cdk: str,
    payment_options: dict | None, batch_id: str | None, idempotency_key: str | None,
) -> dict:
    register_operation_handlers()
    key = str(idempotency_key or "").strip() or None
    source_id = (
        f"maintenance:extract_link:{account_id}:{key}"
        if key else f"maintenance:extract_link:{account_id}:{uuid.uuid4().hex}"
    )
    return account_task_store.submit_durable_operation(
        task_type="extract_link",
        account_id=account_id,
        email=email,
        trigger=trigger,
        source_system="native_operations",
        source_id=source_id,
        idempotency_key=key,
        batch_id=_numeric_batch_id(batch_id),
        resource_family="openai_interactive",
        data={
            "link_type": link_type,
            # CDK is intentionally not persisted.  The handler obtains the
            # current secret on demand after the durable Run is claimed.
            "payment_options": _paypal_options(payment_options),
        },
        config_snapshot_provider=get_config_snapshot,
        config_allowlist=EXTRACT_CONFIG_ALLOWLIST,
        dispatch=True,
    )


def enqueue_account_extract(
    *, account_id: int, email: str, access_token: str, trigger: str = "manual",
    link_type: str | None = None, cdk: str | None = None,
    payment_options: dict | None = None, batch_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Persist one extract operation; execution is owned by the native dispatcher."""
    account_id = int(account_id)
    email = str(email or "").strip()
    trigger = str(trigger or "manual")
    if not _provider_mode_enabled("legacy", "extract_only"):
        return {"accepted": False, "busy": False, "error": "虾扯蛋链平台或提取能力已关闭"}
    account = db.get_account(account_id)
    if not account:
        return {"accepted": False, "busy": False, "error": "账号不存在"}
    if db.account_is_deactivated(account):
        return {
            "accepted": False,
            "busy": False,
            "deactivated": True,
            "error": "账号已废号，不能提链",
        }
    lt, fallback_from = _select_account_link_type(account=account, requested=link_type)
    code = _cdk(cdk)
    key = str(idempotency_key or "").strip() or None
    claimed = False
    if not key:
        if not db.claim_account_extract(account_id, trigger=trigger, link_type=lt):
            return {"accepted": False, "busy": True, "error": "该账号正在提链中"}
        claimed = True
    try:
        submitted = _submit_native_extract(
            account_id=account_id, email=email, trigger=trigger, link_type=lt,
            cdk=code, payment_options=payment_options,
            batch_id=batch_id, idempotency_key=key,
        )
    except Exception as exc:
        error = f"提炼任务持久化失败: {type(exc).__name__}: {str(exc)[:300]}"
        if claimed:
            db.update_account_extract(account_id, {
                "ok": False, "status": "failed", "link_type": lt,
                "message": error, "error": error,
            })
        return {"accepted": False, "busy": False, "error": error}
    if not submitted.get("accepted"):
        return _native_response(
            submitted, account_id=account_id, email=email, trigger=trigger, link_type=lt,
        )
    if key and not submitted.get("reused"):
        if not db.claim_account_extract(account_id, trigger=trigger, link_type=lt):
            _cancel_unclaimed_native_run(submitted.get("run_id"))
            return {
                "accepted": False, "busy": True, "account_id": account_id,
                "email": email, "task_id": submitted.get("task_id"),
                "run_id": submitted.get("run_id"), "link_type": lt,
                "error": "该账号正在提链中",
            }
    if not submitted.get("reused"):
        db.update_account_extract(account_id, {
            "ok": False, "status": "queued", "link_type": lt,
            "message": "已入队",
        })
    response = _native_response(
        submitted, account_id=account_id, email=email, trigger=trigger, link_type=lt,
    )
    if fallback_from:
        response["fallback_from"] = fallback_from
    return response


# Register with the shared dispatcher when the runtime imports this service.
# The runtime owns the single dispatcher thread; this call only installs the
# task-type handler and its allowlist.
register_operation_handlers()
