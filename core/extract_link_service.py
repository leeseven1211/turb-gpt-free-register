# -*- coding: utf-8 -*-
"""Plus 试用提链后台队列。"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

try:
    from curl_cffi import requests as curl_requests
except Exception:  # WebUI 环境未装 curl_cffi 时使用标准库兜底
    curl_requests = None

from config import extract_link as cfg
from config.schema import get_config_snapshot
from core import db
from core.operation_runtime import OperationCancelled
from core import task_run_log
from core.account_operation_executor import configured_workers
from core.operations import task_gateway as account_task_store
from core.task_reporter import TaskReporter

logger = logging.getLogger(__name__)


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
            self._context.report(stage="preflight", state="running", message=message)

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
    因此每次实际读取时都重新加载 .env，避免“页面已保存但当前进程仍读到空值”。
    """
    try:
        from config.env_loader import load_env
        load_env(override=True)
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
        "label": "现有提链服务",
        "prefix": "EXTRACT_LINK_LEGACY",
        "config_prefix": "EXTRACT_LINK",
        "concurrency_key": "EXTRACT_LINK_LEGACY_CONCURRENCY",
        "supports": {"extract_only": True, "manual_payment": True, "auto_payment": False},
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
        "supports": {"extract_only": True, "manual_payment": True, "auto_payment": False},
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
    timeout = _int_setting(f"{config_prefix}_REQUEST_TIMEOUT", 30, 5, 300)
    event_timeout = _int_setting(f"{config_prefix}_EVENT_TIMEOUT", 180, 30, 900)
    poll_interval = _int_setting(f"{config_prefix}_POLL_INTERVAL", 5, 1, 60)
    capabilities = {
        "extract": _provider_mode_enabled(provider_id, "extract_only"),
        "payment": (
            _provider_mode_enabled(provider_id, "manual_payment")
            or _provider_mode_enabled(provider_id, "auto_payment")
        ),
    }
    config = ProviderConfig(
        provider_id=provider_id,
        api_base=api_base,
        cdk=cdk,
        capabilities=capabilities,
        concurrency=_int_setting(settings["concurrency_key"], 1, 1, 32),
        timeout=timeout,
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
    if _bool_setting("EXTRACT_LINK_ENABLED", True):
        for provider_id, settings in _PROVIDER_SETTINGS.items():
            try:
                runtime_config = _provider_configuration(provider_id)
            except (ValueError, TypeError):
                continue
            modes = [
                mode for mode in ("extract_only", "manual_payment", "auto_payment")
                if _provider_mode_enabled(provider_id, mode)
            ]
            if provider_id == "lumen_flow" and runtime_config.default_type != "momo":
                modes = [mode for mode in modes if mode != "auto_payment"]
            if not modes:
                continue
            providers.append({
                "id": provider_id,
                "label": settings["label"],
                "default_type": runtime_config.default_type,
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
        "default_provider": default_provider,
        "default_mode": default_mode,
        "providers": providers,
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
) -> str:
    """提炼前在线验证 Token，失效时同步刷新并读取数据库新 Token。"""
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

        reporter.stage("preflight", "running", "提炼前正在在线查活")
        preflight_open = True

        # 不使用入队时传进来的 Token 快照；查活/刷新完成后重新从数据库读取，
        # 确保外部提链网站拿到的是刚刚验证过或刚刚刷新写回的 AT。
        extract_token = _ensure_extract_token(
            account_id=account_id,
            email=email,
            progress=progress,
            on_refresh_start=mark_refresh_start,
            on_refresh_success=mark_refresh_success,
            operation_context=operation_context,
            config_snapshot=config_snapshot,
        )
        reporter.stage("preflight", "success", "提炼前 Token 检查完成")
        preflight_open = False
        reporter.stage("access_token", "success", "已取得可用 AT")
        if not refresh_started:
            reporter.stage("refresh_token", "skipped", "现有 AT 有效，无需刷新")
        task_stage = "extract_link"
        reporter.stage("extract_link", "running", "正在创建提炼任务")
        progress("AT 已确认有效，正在创建提链任务")
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


def _provider_dispatch_capacity_key(run: dict) -> str:
    data = run.get("data") if isinstance(run, dict) else {}
    provider_id = str((data or {}).get("provider_id") or "legacy").strip().lower()
    return provider_id if provider_id in _PROVIDER_SETTINGS else "invalid"


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
    return link_type


def _provider_request_options(provider_id: str, options: object, *, mode: str, link_type: str) -> dict:
    source = options if isinstance(options, dict) else {}
    if provider_id == "legacy":
        return _paypal_options(source)
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
    from core.extract_link_providers.contracts import ProviderJob

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
    for key in ("current_step", "percent", "outcome"):
        value = summary.get(key)
        if key == "percent" and isinstance(value, (int, float)) and not isinstance(value, bool):
            safe_summary[key] = max(0, min(100, int(value)))
        elif isinstance(value, str):
            safe_summary[key] = value[:100]
    return {
        "extraction_state": extraction_state,
        "payment_state": payment_state,
        "preflight_status": str(preflight_status or "pending")[:40],
        "plus_status": str(plus_status or "unknown")[:40],
        "aftercare_status": str(aftercare_status or "not_started")[:40],
        "links": list(item.links or ()),
        "payment_links": list(item.payment_links or ()),
        "summary": safe_summary,
        "message": str(message or "")[:300],
    }


def _update_provider_job(context, provider_id: str, job_id: str | None, state: dict, private_data=None) -> None:
    from core.storage import extract_link_jobs

    private = private_data if isinstance(private_data, dict) else {}
    extract_link_jobs.save_provider_job(context.run_id, provider_id, job_id, state, private)


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
        return True
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
    progress = {
        "label": str(row.get("progress_stage") or row.get("current_stage") or ""),
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
    message = str(state.get("message") or run_summary.get("message") or error or "")
    created_at = row.get("run_created_at") or row.get("task_created_at")
    updated_at = row.get("task_updated_at") or row.get("run_completed_at") or created_at
    return {
        "task_id": int(row.get("task_id") or 0),
        "run_id": int(row.get("run_id") or 0) or None,
        "account_id": int(row.get("account_id") or 0) or None,
        "email": str(row.get("email") or ""),
        "provider_id": provider_id,
        "mode": mode,
        "link_type": str(data.get("link_type") or "")[:80],
        "task_status": task_status,
        "preflight_status": preflight,
        "extraction_status": extraction,
        "payment_status": payment,
        "plus_status": plus,
        "run_count": int(row.get("run_count") or 0),
        "progress": progress,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
        "message": message[:500],
        "error": error[:500],
        "has_extract_link": bool(state.get("links") or legacy_has_link),
        "has_payment_link": bool(state.get("payment_links") or state.get("links") or legacy_has_link),
    }


def _workbench_status_matches(item: dict, status: str) -> bool:
    if not status:
        return True
    task_status = str(item.get("task_status") or "")
    extraction = str(item.get("extraction_status") or "")
    payment = str(item.get("payment_status") or "")
    plus = str(item.get("plus_status") or "")
    if status == "processing":
        return task_status in {"queued", "running", "waiting", "cancelling", "settling"} or extraction in {"queued", "running"}
    if status == "running":
        return task_status in {"running", "cancelling", "settling"} or extraction == "running"
    if status == "extraction_succeeded":
        return extraction == "success"
    if status == "payment_succeeded":
        return payment == "paid"
    if status == "plus_confirmed":
        return plus == "confirmed"
    if status == "needs_attention":
        return task_status in {"failed", "request_unknown", "cancelled", "attention_required"} or "unknown" in {extraction, payment, plus} or extraction == "failed"
    return False


def create_workbench_tasks(
    *, account_ids: list[int], provider_id: str, mode: str,
    type: str | None = None, options: dict | None = None,
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
        if not account or db.account_is_deactivated(account):
            skipped += 1
            continue
        try:
            if not plus_promotion.is_free_trial_record(account):
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
                dispatch=True,
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
) -> dict:
    from core.storage import extract_link_jobs

    rows = extract_link_jobs.list_workbench_rows(
        provider_id=provider_id, mode=mode, query=query,
    )
    account_rows = db.get_accounts_for_jobs([
        {
            "id": int(row.get("task_id") or 0),
            "account_id": row.get("account_id"),
            "email": row.get("email"),
        }
        for row in rows
    ])
    items = [
        _workbench_task_item(row, account=account_rows.get(int(row.get("task_id") or 0)))
        for row in rows
    ]
    counts = {
        "all": len(items),
        "processing": sum(_workbench_status_matches(item, "processing") for item in items),
        "running": sum(_workbench_status_matches(item, "running") for item in items),
        "extraction_succeeded": sum(_workbench_status_matches(item, "extraction_succeeded") for item in items),
        "payment_succeeded": sum(_workbench_status_matches(item, "payment_succeeded") for item in items),
        "plus_confirmed": sum(_workbench_status_matches(item, "plus_confirmed") for item in items),
        "needs_attention": sum(_workbench_status_matches(item, "needs_attention") for item in items),
    }
    filtered = [item for item in items if _workbench_status_matches(item, status)]
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    total = len(filtered)
    selected = filtered[(page - 1) * page_size:page * page_size]
    return {"items": selected, "total": total, "page": page, "page_size": page_size, "counts": counts}


def extract_workbench_task_link(task_id: int, kind: str) -> dict | None:
    from core.storage import extract_link_jobs, operation

    task = operation.get_task(int(task_id), include_events=False)
    if not task or str(task.get("task_type") or "") != "extract_link":
        return None
    run_id = int(task.get("last_run_id") or 0)
    if not run_id:
        return None
    job = extract_link_jobs.get_provider_job_public(run_id)
    if job:
        state = job.get("public_state") if isinstance(job.get("public_state"), dict) else {}
        candidates = state.get("links") if kind == "extract" else state.get("payment_links") or state.get("links")
        if isinstance(candidates, list) and candidates:
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


def extract_workbench_task_detail(task_id: int) -> dict | None:
    from core.storage import extract_link_jobs, operation

    task = operation.get_task(int(task_id), include_events=True)
    if not task or str(task.get("task_type") or "") != "extract_link":
        return None
    row = next(
        (item for item in extract_link_jobs.list_workbench_rows() if int(item.get("task_id") or 0) == int(task_id)),
        None,
    )
    if row is None:
        return None
    item = _workbench_task_item(row)
    history = []
    for run in task.get("runs") or []:
        run_id = int(run.get("id") or 0)
        job = extract_link_jobs.get_provider_job_public(run_id) if run_id else None
        state = job.get("public_state") if job and isinstance(job.get("public_state"), dict) else {}
        history.append({
            "run_id": run_id,
            "run_no": run.get("run_no"),
            "status": run.get("status"),
            "provider_id": (job or {}).get("provider_id") or (run.get("data") or {}).get("provider_id") or "legacy",
            "extraction_status": state.get("extraction_state") or "unknown",
            "payment_status": state.get("payment_state") or "not_started",
            "created_at": run.get("created_at"),
            "completed_at": run.get("completed_at"),
            "message": task_run_log.redact_text(str(run.get("error_message") or ""), 500),
        })
    events = []
    for event in (task.get("events") or [])[-200:]:
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
        if prior_job and prior_job.get("job_id") and str(prior_state.get("extraction_state") or "") not in {"failed"}:
            workbench_action = "sync_status"
        else:
            if not _provider_mode_enabled(provider_id, "extract_only"):
                return {"accepted": False}
            workbench_action = "create"
            if mode == "auto_payment":
                mode = "extract_only"
                run_data["mode"] = mode
            run_data.update({
                "provider_id": provider_id,
                "mode": mode,
                "link_type": data.get("link_type"),
                "options": data.get("options") if isinstance(data.get("options"), dict) else {},
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
        if not prior_job or not prior_job.get("job_id"):
            return {"accepted": False}
        workbench_action = "sync_status"
    else:
        return {"accepted": False}
    if requested_action == "sync_status" and not prior_job:
        return {"accepted": False}
    if requested_action != "retry":
        if not prior_job or not prior_job.get("job_id"):
            return {"accepted": False}
        run_data.update({
            "provider_id": provider_id,
            "mode": mode,
            "provider_job_run_id": latest_run_id,
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


def _acquire_huanguang_proxies(context):
    from core import proxy_pool

    leases = []
    resource_ids = []
    try:
        for purpose in ("entry", "exit"):
            context.checkpoint("正在分配幻光提链线路")
            lease = proxy_pool.acquire_proxy(
                purpose=f"extract_link_{purpose}",
                timeout=45,
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


def _handle_provider_operation(context):
    from core.extract_link_providers.contracts import ExtractRequest, ProviderJob
    from core.storage import extract_link_jobs

    data = context.run.get("data") if isinstance(context.run.get("data"), dict) else {}
    provider_id = str(data.get("provider_id") or "legacy").strip().lower()
    mode = str(data.get("mode") or "extract_only").strip().lower()
    action = str(data.get("workbench_action") or "create").strip().lower()
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
    if action == "create" and not plus_promotion.is_free_trial_record(account):
        context.finish(status="failed", message="账号已不符合 Plus 试用资格，未提交提链", error="账号不符合提链资格")
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
    prior_run_id = int(data.get("provider_job_run_id") or 0)
    prior_job = extract_link_jobs.get_provider_job_private(prior_run_id) if prior_run_id else None
    prior_private = prior_job.get("private_data") if prior_job and isinstance(prior_job.get("private_data"), dict) else {}
    job_id = str(prior_job.get("job_id") or "") if prior_job else ""
    state = _safe_provider_job_state(
        ProviderJob(job_id=job_id or None, extraction_state="pending"),
        mode=mode,
        preflight_status="pending",
        plus_status="not_applicable",
    )
    leases = []
    proxy_resource_ids = []
    remote_write_started = False
    latest_token = ""
    schedule_plan_check = False
    terminal_status = "failed"
    status_message = "提链失败"
    safe_error = ""

    try:
        with context.lease(resource_family="openai_interactive"):
            context.checkpoint()
            if action == "create":
                if not db.mark_account_extract_running(account_id):
                    raise RuntimeError("账号提链状态无法转为运行中")
                state["preflight_status"] = "running"
                state["message"] = "正在检查账号与 AT"
                _update_provider_job(context, provider_id, None, state, {})
                context.report(stage="preflight", state="running", message="正在检查账号与 AT")
                latest_token = _ensure_extract_token(
                    account_id=account_id,
                    email=email,
                    progress=lambda message: context.report(stage="preflight", message=message),
                    on_refresh_start=lambda: context.report(stage="refresh_token", state="running", message="AT 已确认失效，正在刷新"),
                    on_refresh_success=lambda: context.report(stage="refresh_token", state="success", message="AT 刷新成功"),
                    operation_context=context,
                    config_snapshot=context.config_snapshot,
                )
                state["preflight_status"] = "passed"
                state["message"] = "账号查活通过，已使用数据库最新 AT"
                _update_provider_job(context, provider_id, None, state, {})
                context.report(stage="preflight", state="success", message="账号查活通过，已使用数据库最新 AT")
                if provider_id == "huanguang":
                    leases, proxy_resource_ids = _acquire_huanguang_proxies(context)
                request_data = ExtractRequest(
                    account_id=account_id,
                    access_token=latest_token,
                    link_type=link_type,
                    mode=mode,
                    idempotency_key=f"extract-link:{context.run_id}",
                    options=options,
                    entry_proxy=getattr(leases[0], "proxy_url", None) if leases else None,
                    exit_proxy=getattr(leases[1], "proxy_url", None) if len(leases) > 1 else None,
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
                job_id = str(job.job_id or "").strip()
                state = _safe_provider_job_state(
                    job,
                    mode=mode,
                    preflight_status="passed",
                    plus_status="not_applicable",
                )
                if job_id:
                    _update_provider_job(context, provider_id, job_id, state, job.private_data)
                    if callable(getattr(context, "remote_request_receipt", None)):
                        context.remote_request_receipt(
                            outcome="confirmed",
                            action="extract_link_create",
                            request_id=request_id,
                            detail={
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
                        status_message = "平台已明确拒绝提链请求"
                        raise RuntimeError("平台已明确拒绝提链请求")
                    if callable(getattr(context, "remote_request_receipt", None)):
                        context.remote_request_receipt(
                            outcome="response_received",
                            action="extract_link_create",
                            request_id=request_id,
                            detail={"response_observed": True, "remote_result_confirmed": False},
                        )
                    terminal_status = "request_unknown"
                    status_message = "平台响应未能确认远端任务，保留结果并允许后续重跑"
                    raise RuntimeError("request_unknown: 提链服务未返回可确认的任务 ID")
                if mode == "auto_payment" and callable(getattr(provider, "get_automatic_payment_status", None)):
                    payment_job = provider.get_automatic_payment_status(job_id)
                    job = _merge_provider_jobs(job, payment_job)
                    state = _safe_provider_job_state(
                        job,
                        mode=mode,
                        preflight_status="passed",
                        plus_status="not_applicable",
                    )
                    _update_provider_job(context, provider_id, job_id, state, job.private_data)
            elif action == "sync_status":
                if not prior_job or not job_id:
                    raise RuntimeError("没有可同步的远端任务")
                job = provider.get_status(job_id, private_data=prior_private)
                state = _safe_provider_job_state(
                    job,
                    mode=mode,
                    preflight_status=prior_job.get("public_state", {}).get("preflight_status", "passed"),
                    plus_status=prior_job.get("public_state", {}).get("plus_status", "not_applicable"),
                    aftercare_status=prior_job.get("public_state", {}).get("aftercare_status", "not_started"),
                )
                if (
                    mode == "manual_payment"
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
            else:
                raise ValueError("提链操作类型无效")

            started_at = time.monotonic()
            deadline = started_at + runtime.event_timeout
            while job_id and time.monotonic() < deadline:
                extraction_pending = state["extraction_state"] in {"queued", "running", "unknown"}
                payment_pending = mode == "auto_payment" and state["payment_state"] in {
                    "not_started", "pending", "unknown",
                }
                if not extraction_pending and not payment_pending:
                    break
                if action == "sync_status" and time.monotonic() > started_at:
                    break
                context.checkpoint()
                time.sleep(runtime.poll_interval)
                try:
                    status_job = provider.get_status(job_id, private_data=prior_private or state.get("private_data"))
                    if mode == "auto_payment" and callable(getattr(provider, "get_automatic_payment_status", None)):
                        payment_job = provider.get_automatic_payment_status(job_id)
                        job = _merge_provider_jobs(status_job, payment_job)
                    else:
                        job = status_job
                    state = _safe_provider_job_state(
                        job,
                        mode=mode,
                        preflight_status=state.get("preflight_status", "passed"),
                        plus_status=state.get("plus_status", "not_applicable"),
                        aftercare_status=state.get("aftercare_status", "not_started"),
                    )
                    _update_provider_job(context, provider_id, job_id, state, job.private_data or prior_private)
                except Exception as exc:
                    safe_error = task_run_log.redact_text(str(exc), 300)
                    state["extraction_state"] = "unknown"
                    if mode != "extract_only" and mode == "auto_payment":
                        state["payment_state"] = "unknown"
                    _update_provider_job(context, provider_id, job_id, state, prior_private)
                    break
            if state["payment_state"] == "succeeded":
                context.report(stage="payment", state="success", message="平台已确认支付成功")
                aftercare = state.get("aftercare_status") or "not_started"
                if aftercare in {"not_started", "pending"}:
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
                if _bool_setting("EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED", False):
                    schedule_plan_check = True
                    state["plus_status"] = "pending"
                else:
                    state["plus_status"] = "not_applicable"
                context.report(stage="plus", state=state["plus_status"], message="Plus 权益核验状态已单独记录")
            elif mode == "extract_only":
                state["payment_state"] = "not_started"
                state["plus_status"] = "not_applicable"
            else:
                state["plus_status"] = "not_applicable"

            _update_provider_job(context, provider_id, job_id or None, state, job.private_data if "job" in locals() else prior_private)
            extraction = state["extraction_state"]
            payment = state["payment_state"]
            terminal_extraction = extraction in {"succeeded", "failed"}
            if provider_id == "huanguang":
                _release_huanguang_proxies(context, leases, proxy_resource_ids, terminal=terminal_extraction)
            if extraction == "succeeded":
                terminal_status = "success"
                status_message = "提链成功"
                context.report(stage="extraction", state="success", message="提链成功")
                if mode == "auto_payment" and payment in {"unknown", "pending"}:
                    terminal_status = "request_unknown" if payment == "unknown" else "partial_success"
                    status_message = "提链成功，自动支付状态待确认"
                elif mode == "manual_payment" and payment not in {"succeeded", "failed"}:
                    status_message = "提链成功，等待手动支付"
            elif extraction == "failed":
                terminal_status = "failed"
                status_message = "平台提链失败"
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
                context.report(stage="payment", state="unknown", message="支付状态待确认")

            result = {
                "ok": terminal_status == "success" and extraction == "succeeded",
                "status": "success" if extraction == "succeeded" else "failed",
                "job_id": job_id or None,
                "link_type": link_type,
                "message": status_message,
                "result": {
                    "long_url": (state.get("links") or [None])[0],
                    "payment_link": (state.get("payment_links") or [None])[0],
                },
            }
            if action == "create":
                db.update_account_extract(account_id, result)
            if callable(getattr(context, "finish", None)) and not getattr(context, "finished", False):
                context.finish(
                    status=terminal_status,
                    message=status_message,
                    error=safe_error or (status_message if terminal_status in {"failed", "request_unknown"} else None),
                    result_summary={
                        "provider_id": provider_id,
                        "mode": mode,
                        "extraction_status": extraction,
                        "payment_status": payment,
                        "preflight_status": state.get("preflight_status"),
                        "aftercare_status": state.get("aftercare_status"),
                        "plus_status": state.get("plus_status"),
                        "remote_job_created": bool(job_id),
                        "outcome": state.get("summary", {}).get("outcome"),
                    },
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
                    state["message"] = "支付已成功，但 Plus 套餐核验未能排队"
            else:
                state["plus_status"] = "failed"
                state["message"] = "支付已成功，但数据库没有可用 AT 供套餐核验"
            extract_link_jobs.update_provider_job_state(context.run_id, state)
        return None
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
        remote_rejected = str(state.get("summary", {}).get("outcome") or "").upper() == "REJECTED"
        if remote_write_started and terminal_status != "request_unknown" and not remote_rejected:
            terminal_status = "request_unknown"
            status_message = "远端提链结果待确认"
        elif terminal_status != "request_unknown" and not remote_rejected:
            terminal_status = "failed"
            status_message = "提链失败"
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
                terminal=bool(job_id and state.get("extraction_state") in {"succeeded", "failed"}),
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
                    "provider_id": provider_id,
                    "mode": mode,
                    "preflight_status": state.get("preflight_status"),
                    "extraction_status": state.get("extraction_state"),
                    "payment_status": state.get("payment_state"),
                    "remote_job_created": bool(job_id),
                },
            )
        return None


def _merge_provider_jobs(primary, secondary):
    from core.extract_link_providers.contracts import ProviderJob

    if not isinstance(primary, ProviderJob):
        primary = ProviderJob()
    if not isinstance(secondary, ProviderJob):
        return primary
    return ProviderJob(
        job_id=secondary.job_id or primary.job_id,
        extraction_state=secondary.extraction_state if secondary.extraction_state != "unknown" else primary.extraction_state,
        payment_state=secondary.payment_state if secondary.payment_state != "not_started" else primary.payment_state,
        links=tuple(dict.fromkeys((*primary.links, *secondary.links))),
        payment_links=tuple(dict.fromkeys((*primary.payment_links, *secondary.payment_links))),
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


def resume_known_remote_jobs() -> int:
    """服务启动时为已知远端任务排队状态同步，避免等待人工重跑。"""
    if not _bool_setting("EXTRACT_LINK_ENABLED", True):
        return 0
    from core.storage import extract_link_jobs, operation

    resumed = 0
    for item in extract_link_jobs.list_recoverable_workbench_jobs():
        provider_id = str(item.get("provider_id") or "legacy").strip().lower()
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
                    "provider_job_run_id": run_id,
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
        return {"accepted": False, "busy": False, "error": "legacy 平台或提取能力已关闭"}
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
