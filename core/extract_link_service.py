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
from urllib.parse import quote, urlencode
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
) -> dict:
    base = _api_base(api_base)
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
                f"{base}/api/extract",
                data=body,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            if not isinstance(data, dict) or not data.get("job_id"):
                raise RuntimeError(f"提链服务未返回 job_id: {data}")
            return data
        resp = s.post(f"{base}/api/extract", json=payload, timeout=timeout)
        try:
            data = resp.json()
        except Exception:
            data = {"error": (resp.text or "")[:300]}
        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(data.get("error") or f"HTTP {resp.status_code}")
        if not isinstance(data, dict) or not data.get("job_id"):
            raise RuntimeError(f"提链服务未返回 job_id: {data}")
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
            reporter.note(safe_message, stage="preflight", event_type="extract.preflight")

        def mark_refresh_start() -> None:
            nonlocal refresh_started, task_stage
            refresh_started = True
            task_stage = "refresh_token"
            reporter.stage("refresh_token", "running", "现有 AT 已失效，正在刷新 AT")

        def mark_refresh_success() -> None:
            reporter.stage("refresh_token", "success", "AT 刷新成功")

        reporter.stage("preflight", "running", "提炼前正在在线查活")

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
        reporter.stage("access_token", "success", "已取得可用 AT")
        if not refresh_started:
            reporter.stage("refresh_token", "skipped", "现有 AT 有效，无需刷新")
        progress("AT 已确认有效，正在创建提链任务")
        task_stage = "extract_link"
        reporter.stage("extract_link", "running", "正在创建提炼任务")
        _checkpoint(operation_context, "创建提链任务前检查取消状态")
        request_id = None
        if operation_context is not None:
            request_id = f"extract-job:{operation_context.run_id}:{uuid.uuid4().hex}"
            # This is the last durable action before the remote job-create
            # request.  Never persist the AT, CDK, payment links, or raw body.
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
                **create_kwargs,
            )
        except account_task_store.OperationLeaseLost:
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
                        "response_observed": False,
                        "exception_type": type(exc).__name__,
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
        reporter.stage(
            task_stage,
            "failed" if unknown else "cancelled",
            "远端提链结果待确认" if unknown else "提炼已取消",
            level="WARNING" if unknown else "INFO",
            detail={"error": safe_reason, "remote_job_created": bool(job_id)},
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
        result = {
            "ok": False,
            "status": "request_unknown" if unknown else "failed",
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
        reporter.stage(
            task_stage,
            "failed",
            "远端提炼结果待确认" if unknown else "提炼失败",
            level="WARNING" if unknown else "ERROR",
            detail={"error": safe_reason},
        )
        reporter.finish(
            status="request_unknown" if unknown else "failed",
            message="远端提炼结果待确认" if unknown else "提炼失败",
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


def _handle_extract_operation(context):
    data = context.run.get("data") if isinstance(context.run.get("data"), dict) else {}
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
    )
    return True


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
    account = db.get_account(account_id)
    if not account:
        return {"accepted": False, "busy": False, "error": "账号不存在"}
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
