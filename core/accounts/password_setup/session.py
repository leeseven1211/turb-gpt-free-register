"""仅为已有账号补密码恢复并验证私有协议会话。"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager

from config import pick_browser_profile
from core import db
from core.accounts.liveness.protocol import v3
from core.accounts.password_setup.protocol import ProtocolPasswordSetupError
from core.accounts.password_setup.proxy import is_proxy_transport_failure
from core.auth.protocol.session import BrowserSession
from core.auth.state_machine import CancellationRequested
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost
from core.storage.accounts import protocol_sessions

logger = logging.getLogger(__name__)
_CONTROL_ERRORS = (CancellationRequested, OperationCancelled, OperationLeaseLost)
_REQUIRED_PROFILE_FIELDS = {
    "screen_width", "screen_height", "device_pixel_ratio",
    "hardware_concurrency", "device_memory", "js_heap_size_limit",
}


def _check(checkpoint):
    if checkpoint is not None:
        checkpoint()


def _reraise_control(error):
    """共享读取原语可能包装取消异常，仍须保留其控制语义。"""
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, _CONTROL_ERRORS):
            raise current
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)


def _invalidate(account_id, email):
    try:
        protocol_sessions.invalidate_session(account_id, email)
    except Exception as exc:
        _reraise_control(exc)
        logger.warning("[补密码] 失效协议会话缓存清理失败")


def _session_error(error):
    _reraise_control(error)
    diagnostics = getattr(error, "diagnostics", {}) or {}
    status = diagnostics.get("http_status") if isinstance(diagnostics, dict) else None
    if status == 403:
        code, message = "password_setup_security_check", "补密码会话校验未通过安全检查，请检查当前会话和代理"
    elif status == 429:
        code, message = "password_setup_rate_limited", "补密码会话校验受到限流，请稍后重试"
    elif getattr(error, "category", "") == "response":
        code, message = "password_setup_response_invalid", "补密码会话校验返回了无法确认的数据格式"
    else:
        code, message = "password_setup_network_failed", "补密码会话校验未完成，请检查连接后重试"
    return ProtocolPasswordSetupError(code, message, proxy_transport_failed=is_proxy_transport_failure(error))


def _object(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


def _saved_token_session(account):
    """保存的 sessionToken 才是 Cookie 凭据，普通会话 JSON 和 AT 不作替代。"""
    info = _object(account.get("chatgpt_session"))
    token = next((value.strip() for key in ("sessionToken", "session_token")
                  if isinstance(value := info.get(key), str) and value.strip()), "")
    if not token:
        return None
    user, target = _object(info.get("user")), _object(info.get("account"))
    device_id = _object(account.get("extra_json")).get("device_id")
    return {"device_id": device_id.strip() if isinstance(device_id, str) else "",
            "user_id": str(user.get("id") or ""), "chatgpt_account_id": str(target.get("id") or ""),
            "cookies": [{"name": "__Secure-next-auth.session-token", "value": token,
                         "domain": "chatgpt.com", "path": "/", "secure": True, "expires": None}]}


def _session_sources(account, account_id, cached, checkpoint):
    """最多依次提供私有 Cookie 缓存与账号保存的 sessionToken。"""
    if cached:
        yield True, cached
    _check(checkpoint)
    source_account = dict(account)
    if "chatgpt_session" not in source_account:
        try:
            source_account["chatgpt_session"] = db.get_account_chatgpt_session(account_id)
        except Exception as exc:
            _reraise_control(exc)
            raise ProtocolPasswordSetupError("password_setup_runtime_failed",
                "读取账号已保存的登录会话失败，尚未重新登录") from None
    _check(checkpoint)
    saved = _saved_token_session(source_account)
    if saved is not None:
        yield False, saved


@contextmanager
def try_reuse_session(account: dict, email: str, *, proxy: str | None, checkpoint=None, proxy_supplier=None):
    """在线确认 Cookie 与目标身份后提供会话；缓存不可用时由调用方登录。"""
    _check(checkpoint)
    account_id = int(account.get("id") or 0)
    if not account_id:
        yield None
        return
    try:
        cached = protocol_sessions.load_session(account_id, email)
    except Exception as exc:
        _reraise_control(exc)
        logger.warning("[补密码] 协议会话缓存读取失败")
        cached = None
    _check(checkpoint)
    selected_proxy, proxy_selected = proxy, False
    for private_cache, source in _session_sources(account, account_id, cached, checkpoint):
        if private_cache and (not isinstance(source, dict) or not isinstance(source.get("device_id"), str)
                or not source["device_id"] or not isinstance(source.get("browser_profile"), dict)
                or not _REQUIRED_PROFILE_FIELDS.issubset(source["browser_profile"])):
            _invalidate(account_id, email)
            continue

        def invalidate_source():
            # 账号原始 sessionToken 留作事实，只失效实际读取的私有缓存。
            if private_cache:
                _invalidate(account_id, email)

        session = None
        try:
            try:
                if not proxy_selected:
                    selected_proxy = proxy_supplier(1) if callable(proxy_supplier) else proxy
                    proxy_selected = True
                _check(checkpoint)
                identity = None
                if private_cache:
                    identity = {"device_id": source["device_id"], "browser_profile": source["browser_profile"]}
                elif source["device_id"]:
                    # 只保留已保存的设备 ID；画像使用当前配置生成，不冒充旧画像。
                    identity = {"device_id": source["device_id"], "browser_profile": pick_browser_profile()}
                session = BrowserSession(proxy=selected_proxy or "", detect_exit_geo=False,
                    **({"identity": identity} if identity is not None else {}))
                if not private_cache:
                    source.update(device_id=session.device_id, browser_profile=session.browser_profile)
            except _CONTROL_ERRORS:
                raise
            except Exception as exc:
                raise _session_error(exc) from None
            _check(checkpoint)
            try:
                v3._restore_cookies(session, source)
            except (KeyError, TypeError, ValueError, OverflowError):
                invalidate_source()
                continue
            _check(checkpoint)
            try:
                info = v3._read_session(session, cached=True)
                _check(checkpoint)
                if info:
                    v3._verify_identity(info, email, account)
                    v3._verify_identity(info, email, source)
                else:
                    invalidate_source()
                    continue
            except _CONTROL_ERRORS:
                raise
            except v3.ProtocolV3AuthError as exc:
                _reraise_control(exc)
                if exc.code in {"access_token_expired", "identity_mismatch"}:
                    invalidate_source()
                    continue
                else:
                    raise _session_error(exc) from None
            except Exception as exc:
                raise _session_error(exc) from None
            auth = {"ok": True, "status": "live", "access_token": info["accessToken"],
                "session": info, "session_reused": True,
                "auth_method": "session_cookie" if private_cache else "session_token",
                "password_auth_status": "skipped"}
            _check(checkpoint)
            yield auth, session
            return
        finally:
            if session is not None:
                try:
                    session.session.close()
                except Exception as exc:
                    _reraise_control(exc)
                    logger.warning("[补密码] 协议会话关闭失败")
    yield None


def cache_authenticated_session(session, info: dict, account_id: int, email: str) -> None:
    """保存完整 Cookie 供后续复用，缓存故障不覆盖已确认的账号事实。"""
    try:
        protocol_sessions.save_session(account_id, email, v3._cookie_payload(session, info))
    except Exception as exc:
        _reraise_control(exc)
        logger.warning("[补密码] 协议会话缓存保存失败")
