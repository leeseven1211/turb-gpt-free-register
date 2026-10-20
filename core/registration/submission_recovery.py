"""认证提交的脱敏观测与有界页面恢复，不重放原来的 POST。"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import logging
import re
import threading
import time
import uuid
from urllib.parse import urlsplit

from selenium.common.exceptions import TimeoutException

from core.http_response_diagnostics import (
    auth_submission_endpoint, is_auth_session_diagnostic, response_rejection_diagnostic,
    safe_auth_error, safe_response_headers,
)

from .auth_context import checkpoint
from .browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from .selenium_dom import _check_manual_stop, _log_prefix
from .state_machine import StageBudget

logger = logging.getLogger(__name__)
RECOVERY_WINDOW_SECONDS = 20.0
_AUTH_HOSTS = frozenset({"chatgpt.com", "auth.openai.com", "chat.openai.com"})
_SAFE_PATH_PARTS = frozenset({
    "", "api", "auth", "accounts", "csrf", "signin", "openai", "auth0", "session", "callback",
    "password", "email-otp", "send", "resend", "validate", "verify", "authorize", "login", "logout",
    "error", "register", "user", "create", "create-account", "log-in", "email-verification", "about-you",
    "profile", "token", "refresh", "account", "check", "continue", "consent", "set-password",
    "client_auth_session_dump", "passwordless", "send-otp", "create_account",
})
_PAGE_SCRIPT = r"""
const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
const body = String(document.body?.innerText || '').toLowerCase();
const markers = {
  invalid_auth_step:['invalid_auth_step'],
  route_content_type:['invalid content type: text/html'],
  auth_error:['authentication error','callback error','oauth error','认证失败','登录失败'],
  auth_session_ended:['your session has ended','session has expired','session ended','session expired',
    '会话已结束','会话已过期','会话已失效','セッションが終了しました','セッションの有効期限が切れ'],
  account_create_rejected:['account could not be created',"couldn't create account",'无法创建账号'],
  rate_limited:['too many requests','rate limit'],
  challenge:['verify you are human','checking your browser'],
};
return {
  url:location.href, ready_state:document.readyState,
  text_length:body.length, html_length:document.documentElement?.outerHTML.length || 0,
  error_markers:Object.keys(markers).filter(key => markers[key].some(text => body.includes(text))),
  controls:[...document.querySelectorAll('input,button,select,textarea')].filter(visible).slice(0,20).map(el => ({
    type:el.type || el.tagName.toLowerCase(), disabled:!!el.disabled,
    read_only:!!el.readOnly, value_present:!!el.value,
    valid:el.validity ? el.validity.valid : null,
  })),
  resources:performance.getEntriesByType('resource').slice(-30).map(item => ({
    url:item.name, duration_ms:item.duration, status:item.responseStatus,
  })),
};
"""


def _auth_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme == "https" and parsed.hostname in _AUTH_HOSTS
                and parsed.port in (None, 443) and not parsed.username and not parsed.password):
            return value
    except ValueError:
        pass
    return None


def _safe_location(value: object) -> dict:
    if not _auth_url(value):
        return {"origin": "其他页面", "path": ""}
    parsed = urlsplit(str(value))
    # 路径也可能携带身份标识；只保存固定路由词，未知路径用指纹区分。
    parts = parsed.path.split("/")
    safe = all(part in _SAFE_PATH_PARTS for part in parts)
    return {"origin": f"https://{parsed.hostname}", "path": parsed.path[:160] if safe else "其他认证路径",
            **({} if safe else {"path_fingerprint": hashlib.sha256(parsed.path.encode()).hexdigest()[:12]})}


def _navigation_url(value: object) -> str | None:
    url = _auth_url(value)
    if url and urlsplit(url).path.rstrip("/") in {
        "", "/auth/login", "/auth/error", "/about-you", "/profile", "/create-account/profile",
        "/email-verification", "/create-account/password", "/signup/password", "/log-in/password",
    }:
        return url
    # 认证 API 和携带一次性授权码的 callback 地址不能作为刷新/回退目标。
    return None


def _number(value: object, maximum: int = 900_000) -> int | None:
    try:
        return max(0, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return None


def _current_url(driver) -> object:
    try:
        return getattr(driver, "current_url", "")
    except Exception:
        return ""


def has_visible_auth_inputs(snapshot, *, allow_password: bool = True) -> bool:
    """恢复后的路由必须有真实可见表单，空壳 URL 不能确认提交结果。"""
    if not isinstance(snapshot, dict):
        return False
    inputs = snapshot.get("inputs")
    if not isinstance(inputs, list):
        return False
    return any(isinstance(item, dict) and item.get("visible", True)
               and str(item.get("type") or "").lower() not in ({"hidden"} if allow_password else {"hidden", "password"})
               for item in inputs)


class SubmissionDiagnostics:
    """每个浏览器独立保存有限条接口元数据，和既有 CDP 采集共用事件流。"""

    def __init__(self) -> None:
        self.stage = "auth"
        self.network: OrderedDict[str, dict] = OrderedDict()
        self.lock = threading.Lock()
        self.auth_generation = 0
        self.session_requests: OrderedDict[str, int] = OrderedDict()

    def begin_session(self) -> None:
        with self.lock:
            self.auth_generation += 1

    def observe_network(self, record, *, phase: str) -> None:
        if not isinstance(record, dict) or not _auth_url(record.get("url")):
            return
        location = _safe_location(record.get("url"))
        if not (urlsplit(record["url"]).path.startswith(("/api/", "/auth/")) or record.get("resource_type") == "Document"):
            return
        method = record.get("method")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
            return
        key = hashlib.sha256(
            f"{record.get('target_id')}:{record.get('request_id')}:{record.get('redirect_index', 0)}".encode()
        ).hexdigest()[:12]
        status = _number(record.get("status"), 599)
        failure = re.search(r"(?:net::)?ERR_[A-Z_]+", str(record.get("failure") or ""))
        with self.lock:
            session_diagnostic = is_auth_session_diagnostic(record.get("url")) and method == "GET"
            if session_diagnostic and phase == "request":
                self.session_requests[key] = self.auth_generation
                self.session_requests.move_to_end(key)
                while len(self.session_requests) > 64:
                    self.session_requests.popitem(last=False)
            request_generation = self.session_requests.get(key) if session_diagnostic else None
            previous = self.network.get(key, {})
            headers = {**previous.get("response_headers", {}),
                       **safe_response_headers(record.get("response_headers"))}
            headers_observed = record.get("response_headers_observed")
            if headers_observed is None:
                headers_observed = isinstance(record.get("response_headers"), dict)
            observed_status = status if status and status >= 100 else previous.get("status")
            auth_error = safe_auth_error(record.get("auth_error")) or safe_auth_error(previous.get("auth_error"))
            self.network[key] = {
                **location, "request": key, "stage": previous.get("stage", self.stage),
                "method": method, "phase": phase,
                "status": observed_status,
                "duration_ms": _number(record.get("duration_ms")),
                "network_error": failure.group(0) if failure else ("网络请求未完成" if record.get("failure") else ""),
                "response_headers": headers,
                "response_headers_observed": bool(previous.get("response_headers_observed") or headers_observed),
                "endpoint_kind": auth_submission_endpoint(record.get("url")) or (
                    "auth_session_dump" if is_auth_session_diagnostic(record.get("url")) else ""
                ),
                **({"auth_error": auth_error} if auth_error else {}),
                **({"auth_generation": request_generation} if request_generation is not None else {}),
                **({"rejection": response_rejection_diagnostic(observed_status, headers)}
                   if observed_status == 403 else {}),
            }
            while len(self.network) > 40:
                self.network.popitem(last=False)

    def recent_network(self) -> list[dict]:
        with self.lock:
            return [dict(item) for item in list(self.network.values())[-20:]]


def diagnostics_for(driver) -> SubmissionDiagnostics:
    diagnostics = getattr(driver, "_registration_submission_diagnostics", None)
    if not isinstance(diagnostics, SubmissionDiagnostics):
        diagnostics = SubmissionDiagnostics()
        try:
            driver._registration_submission_diagnostics = diagnostics
        except (AttributeError, TypeError):
            # 只读适配器仍可返回本次诊断，观测不能阻断认证状态判断。
            pass
    return diagnostics


def auth_session_unavailable(driver) -> bool:
    """只读取本浏览器最近一次认证会话接口结果，不主动请求或重放认证。"""
    ignored = getattr(driver, "_registration_previous_auth_session_requests", ())
    for item in reversed(diagnostics_for(driver).recent_network()):
        if (item.get("origin") == "https://auth.openai.com"
                and item.get("path") == "/api/accounts/client_auth_session_dump"
                and item.get("request") not in ignored):
            # 实际抓包出现 404 / missing_session；404 本身只确认接口不可用。
            # 较新的成功或尚未完成请求优先，不能沿用旧失败误判新会话。
            return item.get("status") == 404
    return False


def begin_auth_session(driver) -> None:
    """新登录保留旧诊断，旧请求的迟到响应不能判定新会话失效。"""
    diagnostics = diagnostics_for(driver)
    diagnostics.begin_session()
    driver._registration_previous_auth_session_requests = frozenset(
        item.get("request") for item in diagnostics.recent_network()
        if item.get("origin") == "https://auth.openai.com"
        and item.get("path") == "/api/accounts/client_auth_session_dump"
    )


def auth_session_missing(driver) -> bool:
    """只有当前会话最新诊断明确缺失，才允许提交前恢复；404 本身不够。"""
    ignored = getattr(driver, "_registration_previous_auth_session_requests", ())
    diagnostics = diagnostics_for(driver)
    for item in reversed(diagnostics.recent_network()):
        if (item.get("origin") == "https://auth.openai.com"
                and item.get("path") == "/api/accounts/client_auth_session_dump"
                and item.get("request") not in ignored
                and item.get("auth_generation") == diagnostics.auth_generation):
            return (item.get("method") == "GET" and item.get("status") == 404
                    and safe_auth_error(item.get("auth_error")).get("code") == "missing_session")
    return False


def _log_diagnostic_chunks(driver, safe: dict) -> None:
    """按同一采集 ID 拆分元数据，避免任务日志的 4000 字符上限截断 JSON。"""
    capture_id = uuid.uuid4().hex[:12]

    def emit(payload):
        logger.info("%s 认证提交诊断：%s", _log_prefix(driver),
                    json.dumps({"capture_id": capture_id, **payload}, ensure_ascii=False, separators=(",", ":")))

    emit({"section": "page", **{key: value for key, value in safe.items()
                               if key not in {"controls", "resources", "network"}}})
    for section in ("controls", "resources", "network"):
        chunk, part = [], 1
        for item in safe[section]:
            if chunk and len(json.dumps(chunk + [item], ensure_ascii=False)) > 2200:
                emit({"stage": safe["stage"], "point": safe["point"], "section": section,
                      "part": part, "items": chunk})
                chunk, part = [], part + 1
            chunk.append(item)
        if chunk:
            emit({"stage": safe["stage"], "point": safe["point"], "section": section,
                  "part": part, "items": chunk})


def log_submission_diagnostics(driver, stage: str, point: str, *, receipt=None, ui=None) -> dict:
    diagnostics = diagnostics_for(driver)
    diagnostics.stage = stage
    old_script_timeout = None
    try:
        current_timeout = driver.timeouts.script
        if isinstance(current_timeout, (int, float)):
            driver.set_script_timeout(min(2.0, max(0.1, current_timeout)))
            old_script_timeout = current_timeout
    except Exception:
        pass
    try:
        raw = driver.execute_script(_PAGE_SCRIPT)
        raw = raw if isinstance(raw, dict) else {}
    except Exception as exc:
        raw = {"capture_error": type(exc).__name__}
    finally:
        if old_script_timeout is not None:
            try:
                driver.set_script_timeout(old_script_timeout)
            except Exception:
                pass
    controls = []
    for item in raw.get("controls", []) if isinstance(raw.get("controls"), list) else []:
        if not isinstance(item, dict):
            continue
        controls.append({
            "type": item.get("type") if isinstance(item.get("type"), str) and item.get("type") in {
                "email", "password", "text", "number", "tel", "date", "checkbox", "submit",
                "button", "select-one", "select-multiple", "textarea", "hidden",
            } else "other",
            **{key: item.get(key) if type(item.get(key)) is bool else None
               for key in ("disabled", "read_only", "value_present", "valid")},
        })
    resources = []
    for item in raw.get("resources", []) if isinstance(raw.get("resources"), list) else []:
        if isinstance(item, dict) and _auth_url(item.get("url")):
            status = _number(item.get("status"), 599)
            resources.append({**_safe_location(item.get("url")), "duration_ms": _number(item.get("duration_ms")),
                              "status": status if status and status >= 100 else None})
    safe = {
        "stage": stage, "point": point,
        **_safe_location(raw.get("url") or _current_url(driver)),
        "ready_state": raw.get("ready_state") if isinstance(raw.get("ready_state"), str) and raw.get("ready_state") in {"loading", "interactive", "complete"} else "unknown",
        "text_length": _number(raw.get("text_length"), 10_000_000),
        "html_length": _number(raw.get("html_length"), 10_000_000),
        "error_markers": [item for item in raw.get("error_markers", []) if isinstance(item, str) and item in {
            "invalid_auth_step", "route_content_type", "auth_error", "auth_session_ended", "account_create_rejected", "rate_limited", "challenge",
        }] if isinstance(raw.get("error_markers"), list) else [],
        "controls": controls[:20], "resources": resources[-10:], "network": diagnostics.recent_network(),
    }
    if raw.get("capture_error"):
        safe["capture_error"] = raw["capture_error"]
    if isinstance(receipt, BrowserSubmissionReceipt):
        safe["submission"] = {key: value for key, value in receipt.safe_fact().items() if key not in {"error_type"}}
    if isinstance(ui, dict):
        safe["ui"] = {key: value for key, value in ui.items() if type(value) is bool or (
            key == "phase" and isinstance(value, str) and value in {"queued", "dispatched", "cancelled", "dispatch_unknown", "unknown"}
        )}
    session = getattr(driver, "_registration_session_diagnostic", None)
    if isinstance(session, dict):
        safe["session"] = {
            "status": _number(session.get("status"), 599),
            "duration_ms": _number(session.get("duration_ms")),
            **{key: session.get(key) if type(session.get(key)) is bool else None
               for key in ("token_present", "json_valid")},
            "marker": session.get("marker") if session.get("marker") in {"WARNING_BANNER", "no_access_token"} else "",
            "error_type": session.get("error_type") if session.get("error_type") in {
                "origin_changed", "timeout", "session_read_failed", "browser_read_failed",
            } else "",
        }
    _log_diagnostic_chunks(driver, safe)
    return safe


def _previous_auth_url(driver, current_url: str) -> str | None:
    try:
        history = driver.execute_cdp_cmd("Page.getNavigationHistory", {})
        if isinstance(history, dict):
            entries = history.get("entries") or []
            for entry in reversed(entries[:int(history.get("currentIndex", 0))]):
                url = entry.get("url") if isinstance(entry, dict) else None
                if _navigation_url(url) and url != current_url:
                    return url
    except Exception:
        pass
    return None


def recover_submission_page(driver, stage: str, observe, *, budget: StageBudget,
                            allow_back: bool = False, receipt=None, sleeper=time.sleep,
                            on_navigation=None):
    """刷新后只观察原结果；资料阶段可再回到上一认证地址，整个恢复共用剩余预算。"""
    get = getattr(driver, "get", None)
    current_url = _navigation_url(_current_url(driver))
    if not callable(get) or current_url is None or budget.expired():
        return None
    recovery = budget.child(RECOVERY_WINDOW_SECONDS)
    previous_url = _previous_auth_url(driver, current_url) if allow_back else None
    if allow_back and previous_url is None:
        logger.info("%s 未找到可核验的上一认证页面，本次只执行受控刷新", _log_prefix(driver))
    actions = [("refresh", current_url)]
    if previous_url:
        actions.append(("back", previous_url))

    def observe_current():
        if not _auth_url(_current_url(driver)):
            return None
        return observe(recovery)

    for index, (action, url) in enumerate(actions):
        checkpoint()
        recovery.check_cancelled()
        _check_manual_stop()
        if recovery.expired():
            break
        result = observe_current()
        if result:
            log_submission_diagnostics(driver, stage, "already_confirmed", receipt=receipt)
            return result
        if recovery.expired():
            break
        log_submission_diagnostics(driver, stage, f"before_{action}", receipt=receipt)
        if receipt is not None and receipt.phase not in {"confirmed", "rejected", "not_dispatched", "unknown"}:
            record_browser_submission_fact(driver, "unknown", receipt=receipt, result="unknown")
        if recovery.remaining() < 0.1:
            break
        logger.warning("%s %s提交未确认，执行一次%s并观察原结果", _log_prefix(driver),
                       {"email": "邮箱", "password": "密码", "profile": "资料", "otp": "验证码"}.get(stage, "认证"),
                       "受控刷新" if action == "refresh" else "认证页面回退")
        try:
            from core.registration_debug import current_session

            debug_session = current_session()
            if debug_session is not None and debug_session.capture_mode == "full":
                debug_session.capture_page_snapshot(driver, f"{stage}_before_{action}")
        except Exception:
            logger.debug("%s 保存恢复前页面现场失败", _log_prefix(driver), exc_info=True)
        if recovery.expired():
            break
        old_timeout = None
        try:
            old_timeout = driver.timeouts.page_load
            driver.set_page_load_timeout(max(0.1, min(8.0, recovery.remaining() / (len(actions) - index))))
        except Exception:
            pass
        try:
            # 显式 GET 当前/上一认证地址，防止浏览器刷新或历史回退重放原表单 POST。
            get(url)
        except Exception as exc:
            logger.warning("%s 认证页面%s未完成，异常类型=%s，继续观察页面", _log_prefix(driver), action, type(exc).__name__)
            if isinstance(exc, TimeoutException):
                try:
                    driver.execute_script("window.stop();")
                except Exception:
                    pass
        finally:
            if isinstance(old_timeout, (int, float)):
                try:
                    driver.set_page_load_timeout(old_timeout)
                except Exception as exc:
                    logger.warning("%s 恢复页面加载超时设置失败，异常类型=%s", _log_prefix(driver), type(exc).__name__)
        log_submission_diagnostics(driver, stage, f"after_{action}", receipt=receipt)
        if on_navigation is not None:
            on_navigation(action)
        action_end = recovery.clock() + recovery.remaining() / (len(actions) - index)
        while True:
            checkpoint()
            recovery.check_cancelled()
            _check_manual_stop()
            if recovery.expired():
                break
            result = observe_current()
            if result:
                log_submission_diagnostics(driver, stage, f"{action}_confirmed", receipt=receipt)
                return result
            remaining = min(recovery.remaining(), action_end - recovery.clock())
            if remaining <= 0:
                break
            sleeper(min(0.4, remaining))
    log_submission_diagnostics(driver, stage, "recovery_unconfirmed", receipt=receipt)
    return None
