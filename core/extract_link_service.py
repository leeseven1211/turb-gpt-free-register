# -*- coding: utf-8 -*-
"""Plus 试用提链后台队列。"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

try:
    from curl_cffi import requests as curl_requests
except Exception:  # WebUI 环境未装 curl_cffi 时使用标准库兜底
    curl_requests = None

from config import extract_link as cfg
from core import db
from core import task_run_log
from core.account_operation_executor import configured_workers
from core.account_operation_executor import executor as _EXECUTOR
from core.operations import task_gateway as account_task_store
from core.task_reporter import TaskReporter

logger = logging.getLogger(__name__)


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


def _api_base() -> str:
    base = str(_runtime_setting("EXTRACT_LINK_API_BASE", "") or "").strip().rstrip("/")
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


def _create_extract_job(*, token: str, link_type: str, cdk: str, payment_options: dict | None = None) -> dict:
    base = _api_base()
    timeout = _int_setting("EXTRACT_LINK_REQUEST_TIMEOUT", 30, 5, 300)
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


def _iter_sse_events(*, job_id: str, cdk: str):
    base = _api_base()
    timeout = _int_setting("EXTRACT_LINK_EVENT_TIMEOUT", 180, 30, 900)
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


def _ensure_extract_token(*, account_id: int, email: str, progress=None, on_refresh_start=None, on_refresh_success=None) -> str:
    """提炼前在线验证 Token，失效时同步刷新并读取数据库新 Token。"""
    from core import live_check_service

    if progress:
        progress("提炼前正在在线查活")
    live = live_check_service.run_account_live_check_inline(
        account_id=account_id,
        email=email,
        trigger="extract_preflight",
        force_refresh=False,
    )
    if not live.get("accepted"):
        raise RuntimeError(f"提炼前查活未执行：{live.get('error') or '任务未接受'}")
    live_result = live.get("result") if isinstance(live.get("result"), dict) else {}
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
    refreshed = live_check_service.run_account_live_check_inline(
        account_id=account_id,
        email=email,
        trigger="token_refresh_extract_preflight",
        force_refresh=True,
    )
    if not refreshed.get("accepted"):
        raise RuntimeError(f"AT 刷新未执行：{refreshed.get('error') or '任务未接受'}")
    refresh_result = refreshed.get("result") if isinstance(refreshed.get("result"), dict) else {}
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


def _run_extract(*, account_id: int, email: str, access_token: str, link_type: str, cdk: str, trigger: str, payment_options: dict | None = None, task_id: int | None = None) -> dict:
    logs: list[str] = []
    last_event = None
    job_id = ""
    reporter = TaskReporter(task_id)
    refresh_started = False
    task_stage = "preflight"
    try:
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
        )
        reporter.stage("preflight", "success", "提炼前 Token 检查完成")
        reporter.stage("access_token", "success", "已取得可用 AT")
        if not refresh_started:
            reporter.stage("refresh_token", "skipped", "现有 AT 有效，无需刷新")
        progress("AT 已确认有效，正在创建提链任务")
        task_stage = "extract_link"
        reporter.stage("extract_link", "running", "正在创建提炼任务")
        job = _create_extract_job(
            token=extract_token,
            link_type=link_type,
            cdk=cdk,
            payment_options=payment_options,
        )
        job_id = str(job.get("job_id") or "")
        db.update_account_extract(account_id, {
            "ok": False,
            "status": "running",
            "job_id": job_id,
            "link_type": link_type,
            "message": "提链任务已创建，等待结果",
            "cdk_remaining": job.get("cdk_remaining"),
        })
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
        for event, data in _iter_sse_events(job_id=job_id, cdk=cdk):
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
                db.update_account_extract(account_id, final)
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
    except Exception as exc:
        reason = _format_failure_reason(exc, logs=logs, last_event=last_event)
        result = {
            "ok": False,
            "status": "failed",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": reason,
            "message": reason,
        }
        safe_reason = task_run_log.redact_text(reason, 1200)
        failure_summary = _extract_task_result_summary(
            result={}, link_type=link_type, job_id=job_id, ok=False,
        )
        failure_summary["remote_job_created"] = bool(job_id)
        reporter.stage(
            task_stage,
            "failed",
            "提炼失败",
            level="ERROR",
            detail={"error": safe_reason},
        )
        reporter.finish(
            status="failed",
            message="提炼失败",
            error=safe_reason,
            result_summary=failure_summary,
            validation_method="extract_link_sse" if job_id else "extract_preflight",
        )
        try:
            db.update_account_extract(account_id, result)
        except Exception:
            logger.exception("[提链] 写入失败状态异常: account_id=%s", account_id)
        if job_id:
            try:
                db.mark_extract_link_type_failed(account_id, link_type, reason)
            except Exception:
                logger.exception("[提链] 记录失败类型异常: account_id=%s type=%s", account_id, link_type)
        logger.exception("[提链] 失败: %s", email)
        return result
    finally:
        _QUEUE_SLOTS.release()


def enqueue_account_extract(*, account_id: int, email: str, access_token: str, trigger: str = "manual", link_type: str | None = None, cdk: str | None = None, payment_options: dict | None = None, batch_id: str | None = None) -> dict:
    if not _QUEUE_SLOTS.acquire(blocking=False):
        return {"accepted": False, "busy": False, "error": "提链队列已满"}
    claimed = False
    task_id = None
    try:
        account = db.get_account(account_id)
        if not account:
            _QUEUE_SLOTS.release()
            return {"accepted": False, "busy": False, "error": "账号不存在"}
        lt, fallback_from = _select_account_link_type(account=account, requested=link_type)
        code = _cdk(cdk)
        if not db.claim_account_extract(account_id, trigger=trigger, link_type=lt):
            _QUEUE_SLOTS.release()
            return {"accepted": False, "busy": True, "error": "该账号正在提链中"}
        claimed = True
        try:
            task_id = account_task_store.create_task(
                task_type="extract_link",
                account_id=account_id,
                email=email,
                trigger=trigger,
                batch_id=batch_id,
            )
        except Exception as exc:
            error = f"提炼任务记录创建失败：{type(exc).__name__}: {exc}"
            try:
                db.update_account_extract(account_id, {
                    "ok": False,
                    "status": "failed",
                    "link_type": lt,
                    "message": error,
                    "error": error,
                })
            except Exception:
                logger.exception("[提链] 任务记录失败后的账号状态写入异常：account_id=%s", account_id)
            raise RuntimeError(error) from exc
        fut = _EXECUTOR.submit(
            _run_extract,
            account_id=account_id,
            email=email,
            access_token=access_token,
            link_type=lt,
            cdk=code,
            trigger=trigger,
            payment_options=payment_options,
            task_id=task_id,
        )
        response = {
            "accepted": True,
            "busy": False,
            "future": fut,
            "task_id": task_id,
            "account_id": account_id,
            "status": "queued",
            "trigger": trigger,
            "link_type": lt,
        }
        if fallback_from:
            response["fallback_from"] = fallback_from
        return response
    except Exception as exc:
        if claimed and task_id is None:
            try:
                db.update_account_extract(account_id, {
                    "ok": False,
                    "status": "failed",
                    "message": f"提炼入队失败：{type(exc).__name__}: {exc}",
                    "error": f"{type(exc).__name__}: {exc}",
                })
            except Exception:
                logger.exception("[提链] 入队失败后的账号状态写入异常：account_id=%s", account_id)
        _QUEUE_SLOTS.release()
        raise
