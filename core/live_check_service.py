# -*- coding: utf-8 -*-
"""账号查活后台队列：协议 BrowserSession 指纹环境 + 独立日志。"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from core.operations import task_gateway as account_task_store
from core.storage import accounts as db
from core.account_liveness import check_account_liveness, log_path
from core.task_reporter import TaskReporter
from core.chatgpt_plan import check_account_plan, token_claims
from core.live_check_router import LiveCheckDriverError, resolve_driver, run_probe
from core.openai_auth import detect_account_unusable_text
from core.auth_challenge import auth_result_for_operation

logger = logging.getLogger(__name__)

_WORKERS = 3
_QUEUE_LIMIT = 500
_EXECUTOR = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="live-check")
_QUEUE_SLOTS = threading.BoundedSemaphore(_QUEUE_LIMIT)
_RUNNING: set[int] = set()
_LOCK = threading.Lock()


def _attach_auth_projection(
    result: dict,
    *,
    auth_method: str,
    remote_identity: str = "existing",
) -> dict:
    """Attach the safe cross-driver authentication result to a task result."""
    if isinstance(result, dict):
        result.setdefault(
            "auth",
            auth_result_for_operation(
                result,
                auth_method=auth_method,
                remote_identity=remote_identity,
            ).as_dict(),
        )
    return result


def is_checking(email: str) -> bool:
    acc = db.get_account_by_email(email)
    if not acc:
        return False
    return str(acc.get("live_check_status") or "") in {"queued", "running"}


def _append_log(email: str, line: str, *, clear: bool = False) -> None:
    p = log_path(email)
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H:%M:%S")
    mode = "w" if clear else "a"
    with p.open(mode, encoding="utf-8") as f:
        f.write(f"{stamp} [INFO] {line}\n")


def _token_probe_retryable(result: dict) -> bool:
    """只有网络/风控类结果才值得换线路；查活不会因 Token 失效自动重登录。"""
    if result.get("needs_live_check") or result.get("token_expired") is True:
        return False
    status = result.get("http_status")
    if status is None:
        return True
    try:
        status = int(status)
    except (TypeError, ValueError):
        return False
    return status in {403, 408, 409, 425, 429} or status >= 500


def _roxy_fallback_enabled() -> bool:
    # 通过 config.proxy 读取，保证 WebUI 写入 .env 后 reload_all() 能立即生效。
    from config import proxy as proxy_config

    return bool(getattr(proxy_config, "LIVE_CHECK_ROXY_FALLBACK_ENABLED", True))


def _resolve_refresh_driver(requested: str | None = None) -> str:
    """Resolve and freeze the explicit AT-refresh implementation for one task."""
    from config import account as account_config
    from core.protocol_version import resolve_protocol_version

    value = None if requested is None else str(requested or "").strip().lower()
    legacy_v2_alias = value == "protocol_v2"
    if value is None:
        try:
            version = resolve_protocol_version("refresh_at")
        except ValueError as exc:
            logger.warning("[查活] 协议版本配置无效，刷新 AT 回落 v1：%s", exc)
            version = "v1"
    elif value in {"v1", "1"}:
        version = "v1"
    elif value in {"v2", "2"}:
        version = "v2"
    elif value in {"current", "protocol", "protocol_current", "legacy", ""}:
        version = "v1"
    elif legacy_v2_alias:
        version = "v2"
    else:
        logger.warning("[查活] 不支持的刷新 AT 版本/驱动 %r，回落 v1", value)
        version = "v1"

    # Only the old literal driver name keeps the old kill-switch semantics.
    # The new OPENAI_PROTOCOL_VERSION=v2 is the explicit replacement and must
    # not be silently disabled by a stale compatibility flag.
    if legacy_v2_alias and not bool(getattr(account_config, "ACCOUNT_AUTH_V2_ENABLED", False)):
        logger.warning("[查活] 旧配置 protocol_v2 未开启兼容开关，刷新 AT 回落 v1")
        version = "v1"
    return "protocol_v2" if resolve_protocol_version("refresh_at", requested=version) == "v2" else "legacy"


def _refresh_protocol_version(refresh_driver: str | None) -> str | None:
    """Expose the stable public version for a legacy internal driver value."""
    if refresh_driver is None:
        return None
    return "v2" if str(refresh_driver).strip().lower() == "protocol_v2" else "v1"


def _resolve_protocol_identity(account_id: int, refresh_driver: str | None):
    """Load the optional stable identity only for the explicit Protocol v2 path."""
    if refresh_driver != "protocol_v2":
        return None
    from config import account as account_config

    mode = str(getattr(account_config, "ACCOUNT_AUTH_PROFILE_MODE", "current") or "current").strip().lower()
    if mode in {"", "current"}:
        return None
    if mode != "account_stable":
        logger.warning("[查活] 不支持的 Protocol 设备画像模式 %r，保持当前会话随机画像", mode)
        return None
    from core.storage.account_auth import ensure_account_protocol_identity

    identity = ensure_account_protocol_identity(account_id)
    logger.info(
        "[查活][Protocol v2] 使用账号稳定设备画像 profile_ref=%s version=%s",
        identity.profile_ref,
        identity.profile_version,
    )
    return identity


def _report_protocol_v2_refresh(reporter: TaskReporter, result: dict) -> None:
    """Project Protocol v2's actual auth method without inventing OTP success."""
    auth_method = str(result.get("auth_method") or "protocol_v2")
    password_status = str(result.get("password_auth_status") or "")
    uses_email = (
        "email" in auth_method
        or auth_method == "legacy_email_otp"
        or result.get("error") in {
            "password_rejected_email_fallback_failed",
            "passwordless_fallback_unavailable",
        }
    )
    uses_mfa = "mfa" in auth_method

    if password_status == "rejected":
        reporter.stage(
            "login_password",
            "failed",
            "保存的账号密码被拒绝，保留密码错误证据",
            level="WARNING",
            detail={"auth_method": auth_method},
        )
    elif password_status == "verified":
        reporter.stage("login_password", "success", "账号密码验证通过")
    elif auth_method == "legacy_email_otp":
        reporter.stage("login_password", "skipped", "账号没有保存密码，沿用邮箱认证")
    elif result.get("ok"):
        reporter.stage("login_password", "success", "协议认证已完成", detail={"auth_method": auth_method})
    else:
        reporter.stage(
            "login_password",
            "failed",
            "Protocol v2 密码认证未完成",
            level="ERROR",
            detail={"error": result.get("error"), "auth_method": auth_method},
        )

    reporter.stage(
        "mfa_challenge",
        "success" if uses_mfa and result.get("ok") else "skipped" if not uses_mfa else "failed",
        "TOTP MFA 验证已完成" if uses_mfa and result.get("ok") else "本次认证未进入 TOTP MFA" if not uses_mfa else "TOTP MFA 未完成",
        level="ERROR" if uses_mfa and not result.get("ok") else "INFO",
        detail={"auth_method": auth_method},
    )
    reporter.stage(
        "email_otp",
        "success" if uses_email and result.get("ok") else "skipped" if not uses_email else "failed",
        "邮箱验证码已通过" if uses_email and result.get("ok") else "本次认证未使用邮箱验证码" if not uses_email else "邮箱验证码未完成",
        level="ERROR" if uses_email and not result.get("ok") else "INFO",
        detail={"auth_method": auth_method, "fallback_used": bool(result.get("fallback_used"))},
    )
    if result.get("ok"):
        reporter.stage("token", "success", "最新 AT 已获取并保存")


def _browser_live_check_probe(
    *,
    token: str,
    proxy: str | None,
    context_recorder=None,
    route_context: dict | None = None,
) -> dict:
    """延迟加载 Roxy AT probe，避免 current 路径提前初始化浏览器依赖。"""
    from core.live_check_browser import run_probe

    return run_probe(
        token=token,
        proxy=proxy,
        context_recorder=context_recorder,
        route_context=route_context,
    )


def _run_live_check(
    *,
    account_id: int,
    email: str,
    proxy: str | None,
    trigger: str,
    task_id: int | None = None,
    force_refresh: bool = False,
    driver: str | None = None,
    refresh_driver: str | None = None,
) -> dict:
    account_route = None
    route: dict = {}
    reporter = TaskReporter(task_id)
    try:
        with _LOCK:
            _RUNNING.add(int(account_id))
        if not db.mark_account_live_check_running(account_id):
            _append_log(email, "[查活] 账号已删除或查活状态已被重置，取消执行")
            reporter.finish(
                status="cancelled",
                message="账号已删除或查活状态已被重置",
            )
            return {"ok": False, "status": "failed", "error": "账号已删除或查活状态已被重置"}
        # 入队时已经解析并冻结了 driver；直接调用 worker 的旧测试/兼容入口
        # 没有传值时才在这里读取当前配置，避免任务排队期间热改配置导致中途换路。
        selected_live_check_driver = None if force_refresh else (driver or resolve_driver())
        selected_refresh_driver = _resolve_refresh_driver(refresh_driver) if force_refresh else None
        reporter.start(message="开始刷新账号 AT" if force_refresh else "开始验证账号 accessToken")
        if selected_live_check_driver:
            reporter.note(
                stage="access_token",
                message=f"普通查活驱动：{selected_live_check_driver}",
                detail={"live_check_driver": selected_live_check_driver},
            )
        if selected_refresh_driver:
            reporter.note(
                stage="login_password",
                message=f"刷新 AT 协议版本：{_refresh_protocol_version(selected_refresh_driver)}",
                detail={
                    "protocol_version": _refresh_protocol_version(selected_refresh_driver),
                    "token_refresh_driver": selected_refresh_driver,
                },
            )
        from core.account_proxy import acquire_account_proxy

        def acquire_retry_route(attempt: int) -> str:
            """网络预检每次重试都释放旧租约并申请新线路。"""
            nonlocal account_route, route
            if account_route is not None:
                account_route.release(reason=f"live-check-{account_id}-preflight-rotate")
            account_route = acquire_account_proxy(
                account_id=account_id,
                email=email,
                purpose="live-check",
            )
            route = account_route.public_dict()
            _append_log(
                email,
                f"[查活] 查活线路 {attempt}/4 "
                f"network_route={route.get('network_route')} proxy_mode={route.get('proxy_mode')} "
                f"proxy_used={route.get('proxy_used') or '-'} "
                f"fallback_reason={route.get('proxy_fallback_reason') or '-'}",
            )
            reporter.resource(
                "resource.acquired",
                message=f"已选择查活线路（第 {attempt}/4 次）",
                stage="network",
                detail=route,
            )
            reporter.stage("network", "success", "网络线路已就绪", detail={
                key: route.get(key)
                for key in ("network_route", "proxy_mode", "proxy_provider", "proxy_region")
            })
            if force_refresh:
                reporter.stage("login_password", "running", "正在通过邮箱登录刷新 AT")
            return account_route.proxy_url

        def acquire_explicit_route() -> str:
            """显式代理只申请一次，后续步骤严格复用调用方指定线路。"""
            nonlocal account_route, route
            if account_route is None:
                account_route = acquire_account_proxy(
                    account_id=account_id,
                    email=email,
                    purpose="live-check",
                    explicit_proxy=proxy,
                )
                route = account_route.public_dict()
                reporter.resource("resource.acquired", "已选择指定账号线路", stage="network", detail=route)
                reporter.stage("network", "success", "网络线路已就绪")
                if force_refresh:
                    reporter.stage("login_password", "running", "正在通过邮箱登录刷新 AT")
            return account_route.proxy_url

        # 查活和刷新 AT 是两个不同动作：
        # - 查活只验证数据库里的现有 AT，不发送邮箱 OTP，也不偷偷刷新 AT。
        # - 刷新 AT（force_refresh=True）才跳过旧 AT，执行邮箱 OTP 重登录。
        account = db.get_account(account_id) or {}
        protocol_identity = _resolve_protocol_identity(account_id, selected_refresh_driver)
        auth_context_recorder = None
        if selected_refresh_driver == "protocol_v2" or selected_live_check_driver in {"protocol_current", "browser_roxy"}:
            from config import account as account_config

            if bool(getattr(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", False)):
                from core.storage.account_auth import AuthContextRecorder

                auth_context_recorder = AuthContextRecorder.from_account_action_task(
                    task_id,
                    account_id=account_id,
                    protocol_identity=protocol_identity,
                    action="token_refresh" if selected_refresh_driver == "protocol_v2" else "live_check",
                    driver=selected_refresh_driver or selected_live_check_driver or "unknown",
                )
        saved_access_token = str(account.get("access_token") or "").strip()
        saved_claims = token_claims(saved_access_token) if saved_access_token else {}
        result = None
        last_probe_error = ""
        last_probe_error_category = None
        last_probe_http_status = None
        if saved_access_token and not force_refresh:
            probe_attempts = 4 if proxy is None else 1
            _append_log(email, "[查活] 优先验证现有 accessToken；有效则无需重复发送邮箱验证码")
            for attempt in range(1, probe_attempts + 1):
                selected_proxy = acquire_retry_route(attempt) if proxy is None else acquire_explicit_route()
                reporter.stage(
                    "access_token",
                    "running",
                    message="优先在线验证现有 AT；有效则不发送邮箱验证码",
                    detail={
                        "attempt_no": attempt,
                        "token_expires_at": saved_claims.get("token_expires_at"),
                    },
                )
                probe = run_probe(
                    driver=selected_live_check_driver,
                    probe=check_account_plan,
                    token=saved_access_token,
                    proxy=selected_proxy,
                    max_attempts=1,
                    browser_probe=_browser_live_check_probe,
                    context_recorder=auth_context_recorder,
                    route_context=route,
                )
                try:
                    last_probe_http_status = int(probe.get("http_status"))
                except (TypeError, ValueError):
                    last_probe_http_status = None
                last_probe_error_category = probe.get("error_category")
                if probe.get("ok"):
                    result = {
                        "ok": True,
                        "status": "live",
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                        "http_status": last_probe_http_status or 200,
                        "access_token": saved_access_token,
                        "session": {
                            "account": {"planType": probe.get("current_plan_type")},
                        },
                        "proxy_used": selected_proxy or None,
                        "validation_method": "access_token",
                        "live_check_driver": probe.get("live_check_driver") or selected_live_check_driver,
                    }
                    _append_log(
                        email,
                        f"[查活] accessToken 验证成功：HTTP {probe.get('http_status') or 200} "
                        f"plan={probe.get('current_plan_type') or 'unknown'}",
                    )
                    reporter.stage(
                        "access_token",
                        "success",
                        message="AT 在线验证成功",
                        detail={
                            "http_status": probe.get("http_status") or 200,
                            "plan": probe.get("current_plan_type") or "unknown",
                        },
                    )
                    break

                unusable_code = detect_account_unusable_text(
                    f"{probe.get('error') or ''} {probe.get('response_preview') or ''}"
                )
                if unusable_code:
                    result = {
                        "ok": False,
                        "status": "deactivated",
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                        "error": unusable_code,
                        "http_status": last_probe_http_status,
                        "validation_method": "access_token",
                        "error_category": probe.get("error_category"),
                        "live_check_driver": probe.get("live_check_driver") or selected_live_check_driver,
                    }
                    break

                _append_log(
                    email,
                    f"[查活] accessToken 验证未通过（{attempt}/{probe_attempts}）："
                    f"{str(probe.get('error') or '未知错误')[:220]}",
                )
                last_probe_error = str(probe.get("error") or "现有 accessToken 无法验证")[:220]
                reporter.note(
                    stage="access_token",
                    level="WARNING",
                    message=f"AT 在线验证未通过（{attempt}/{probe_attempts}）",
                    detail={
                        "http_status": probe.get("http_status"),
                        "error_category": probe.get("error_category"),
                        "error": probe.get("error"),
                    },
                )
                if not _token_probe_retryable(probe) or attempt >= probe_attempts:
                    _append_log(email, "[查活] 现有 Token 无法确认状态；不会自动登录，请单独点击“刷新AT”")
                    break

            if result is None:
                probe_driver = probe.get("live_check_driver") or selected_live_check_driver
                reporter.stage(
                    "access_token", "failed", "AT 在线验证未通过",
                    level="ERROR",
                    detail={
                        "http_status": last_probe_http_status,
                        "error_category": last_probe_error_category,
                        "error": last_probe_error,
                    },
                )
                result = {
                    "ok": False,
                    "status": "failed",
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                    "error": "现有 accessToken 已过期或失效，请点击“刷新AT”",
                    "http_status": last_probe_http_status,
                    "validation_method": "access_token",
                    "probe_error": last_probe_error,
                    "error_category": probe.get("error_category"),
                    "live_check_driver": probe_driver,
                }
        elif not force_refresh:
            result = {
                "ok": False,
                "status": "failed",
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "error": "账号没有 accessToken，请点击“刷新AT”后再查活",
                "validation_method": "access_token",
            }

        if result is None:
            reporter.note(
                stage="reauth",
                message=(
                    "AT 即将过期，按计划转邮箱 OTP 登录刷新"
                    if force_refresh
                    else "查活未通过；如需获取新 AT，请单独点击“刷新AT”"
                ),
            )

        if not force_refresh and result is not None:
            result.setdefault("live_check_driver", selected_live_check_driver)

        if result is None and proxy is None:
            # WebUI 默认调用由账号代理配置选路，重试时允许真正轮换线路。
            _append_log(email, f"[查活] 开始后台执行 trigger={trigger}，网络预检失败时将轮换代理")
            if selected_refresh_driver == "protocol_v2":
                from core.protocol_v2_liveness import refresh_access_token

                result = refresh_access_token(
                    email,
                    proxy=None,
                    proxy_supplier=acquire_retry_route,
                    identity=protocol_identity,
                    context_recorder=auth_context_recorder,
                )
            else:
                result = check_account_liveness(
                    email,
                    proxy=None,
                    clear_log=False,
                    proxy_supplier=acquire_retry_route,
                )
        elif result is None:
            # API 显式传入的代理（包括空字符串直连）尊重调用方选择，不擅自改线。
            selected_proxy = acquire_explicit_route()
            _append_log(
                email,
                "[查活] 开始后台执行 "
                f"trigger={trigger} network_route={route.get('network_route')} "
                f"proxy_mode={route.get('proxy_mode')} proxy_used={route.get('proxy_used') or '-'} "
                f"fallback_reason={route.get('proxy_fallback_reason') or '-'}",
            )
            if selected_refresh_driver == "protocol_v2":
                from core.protocol_v2_liveness import refresh_access_token

                result = refresh_access_token(
                    email,
                    proxy=selected_proxy,
                    identity=protocol_identity,
                    context_recorder=auth_context_recorder,
                )
            else:
                result = check_account_liveness(email, proxy=selected_proxy, clear_log=False)
        if (
            not result.get("ok")
            and result.get("status") != "deactivated"
            and bool(saved_access_token)
            and force_refresh
            and _roxy_fallback_enabled()
            and result.get("roxy_fallback_allowed", True)
        ):
            from core.roxy_liveness import available as roxy_available, refresh_access_token
            if roxy_available():
                reporter.note(
                    stage="roxy_fallback",
                    level="WARNING",
                    message="协议登录未通过，启用 Roxy 浏览器 NextAuth 兜底",
                    detail={"protocol_error": result.get("error")},
                )
                _append_log(email, "[查活] 协议登录未通过，启用 Roxy 浏览器 NextAuth 兜底")
                result = refresh_access_token(
                    email,
                    proxy=account_route.proxy_url if account_route is not None else proxy,
                )
        if isinstance(result, dict):
            _attach_auth_projection(
                result,
                auth_method=str(
                    result.get("auth_method")
                    or result.get("live_check_driver")
                    or ("legacy_email_otp" if force_refresh else "access_token")
                ),
            )
        if force_refresh:
            if selected_refresh_driver == "protocol_v2":
                _report_protocol_v2_refresh(reporter, result)
            elif result.get("ok"):
                reporter.stage("login_password", "success", "邮箱登录已完成")
                reporter.stage("email_otp", "success", "登录验证已通过")
                reporter.stage("token", "success", "最新 AT 已获取并保存")
            else:
                reporter.stage(
                    "login_password", "failed", "邮箱登录刷新 AT 未完成",
                    level="ERROR", detail={"error": result.get("error")},
                )
        if selected_refresh_driver:
            result.setdefault("token_refresh_driver", selected_refresh_driver)
            result.setdefault("protocol_version", _refresh_protocol_version(selected_refresh_driver))
        result.update({
            "proxy_provider": route.get("proxy_provider"),
            "proxy_region": route.get("proxy_region"),
            "network_route": route.get("network_route"),
            "proxy_used": route.get("proxy_used"),
        })
        db.update_account_liveness(account_id, result)
        if result.get("ok"):
            if result.get("validation_method") == "access_token":
                _append_log(email, "[查活] 完成：账号正常，现有 accessToken 已通过在线验证")
            else:
                _append_log(email, "[查活] 完成：账号正常，已通过邮箱登录刷新 accessToken")
        elif result.get("status") == "deactivated":
            _append_log(email, f"[查活] 完成：账号已废 {result.get('error') or ''}")
        else:
            _append_log(email, f"[查活] 完成：失败 {result.get('error') or ''}")
        final_status = "success" if result.get("ok") else (
            "deactivated" if result.get("status") == "deactivated" else "failed"
        )
        reporter.finish(
            status=final_status,
            message=(
                "账号正常，AT 在线验证成功"
                if result.get("ok") and result.get("validation_method") == "access_token"
                else "账号正常，已通过邮箱登录刷新 AT"
                if result.get("ok")
                else "账号已确认停用"
                if final_status == "deactivated"
                else "查活失败"
            ),
            error=result.get("error") if not result.get("ok") else None,
            result_summary={
                "ok": bool(result.get("ok")),
                "status": result.get("status"),
                "http_status": result.get("http_status"),
                "error_category": result.get("error_category"),
                "checked_at": result.get("checked_at"),
                "plan": (result.get("session") or {}).get("account", {}).get("planType"),
                "live_check_driver": result.get("live_check_driver"),
                "token_refresh_driver": selected_refresh_driver,
                "protocol_version": _refresh_protocol_version(selected_refresh_driver),
                "auth_method": result.get("auth_method"),
                "password_auth_status": result.get("password_auth_status"),
                "fallback_used": result.get("fallback_used"),
                "fingerprint": result.get("fingerprint"),
            },
            route={**route, **{key: result.get(key) for key in ("network_route", "proxy_provider", "proxy_region", "proxy_used")}},
            validation_method=result.get("validation_method"),
        )
        return result
    except Exception as exc:
        result = {
            "ok": False,
            "status": "failed",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            "error_code": str(
                getattr(exc, "code", "") or getattr(exc, "error_code", "") or ""
            ).strip() or None,
            "auth_method": "legacy_email_otp" if force_refresh else "access_token",
        }
        _attach_auth_projection(
            result,
            auth_method=result["auth_method"],
        )
        try:
            db.update_account_liveness(account_id, result)
        except Exception:
            logger.exception("[查活] 写入异常状态失败: account_id=%s", account_id)
        logger.exception("[查活] 后台异常: %s", email)
        try:
            _append_log(email, f"[查活] 后台异常：{result['error']}")
        except Exception:
            pass
        reporter.stage(
            "login_password" if force_refresh else "access_token",
            "failed",
            "刷新 AT 后台异常" if force_refresh else "AT 验证后台异常",
            level="ERROR",
            detail={"error": result["error"]},
        )
        reporter.finish(
            status="failed",
            message="查活后台执行异常",
            error=result["error"],
            route=route,
        )
        return result
    finally:
        if account_route is not None:
            account_route.release(reason=f"live-check-{account_id}")
        with _LOCK:
            _RUNNING.discard(int(account_id))
        _QUEUE_SLOTS.release()


def enqueue_account_live_check(
    *,
    account_id: int,
    email: str,
    trigger: str = "manual",
    proxy: str | None = None,
    batch_id: str | None = None,
    force_refresh: bool = False,
    driver: str | None = None,
) -> dict:
    account_id = int(account_id)
    email = str(email or "").strip()
    if not email:
        return {"accepted": False, "busy": False, "error": "email 为空"}
    effective_live_check_driver = None
    effective_refresh_driver = None
    if not force_refresh:
        try:
            effective_live_check_driver = resolve_driver(driver)
        except LiveCheckDriverError as exc:
            return {"accepted": False, "busy": False, "error": str(exc)}
    else:
        effective_refresh_driver = _resolve_refresh_driver()
    account = db.get_account(account_id)
    if not account:
        return {"accepted": False, "busy": False, "error": "账号不存在"}
    if db.account_is_deactivated(account):
        return {
            "accepted": False,
            "busy": False,
            "deactivated": True,
            "error": "账号已标记为封号，停止查活/刷新 AT",
        }
    if force_refresh and not str(account.get("access_token") or "").strip():
        return {
            "accepted": False,
            "busy": False,
            "not_registered": True,
            "error": "账号没有现有 access_token，拒绝刷新 AT；请先完成账号注册或执行注册续跑",
        }
    if not _QUEUE_SLOTS.acquire(blocking=False):
        return {"accepted": False, "busy": False, "queue_full": True, "error": "查活队列已满，请稍后重试"}
    if not db.claim_account_live_check(acc_id=account_id, trigger=trigger):
        _QUEUE_SLOTS.release()
        return {"accepted": False, "busy": True, "error": "该账号正在查活"}

    action_label = "刷新AT" if str(trigger or "").startswith("token_refresh") else "查活"
    driver_suffix = f" driver={effective_live_check_driver}" if effective_live_check_driver else ""
    _append_log(email, f"[{action_label}] 已入队 account_id={account_id} trigger={trigger}{driver_suffix}", clear=True)
    task_type = "token_refresh" if str(trigger or "").startswith("token_refresh") else "live_check"
    task_id = account_task_store.create_task(
        task_type=task_type,
        account_id=account_id,
        email=email,
        trigger=str(trigger or "manual"),
        batch_id=batch_id,
    )
    try:
        _EXECUTOR.submit(
            _run_live_check,
            account_id=account_id,
            email=email,
            proxy=proxy,
            trigger=str(trigger or "manual"),
            task_id=task_id,
            force_refresh=bool(force_refresh),
            driver=effective_live_check_driver,
            # Pass the public version into the worker.  ``protocol_v2`` is a
            # legacy compatibility alias and intentionally remains protected
            # by ACCOUNT_AUTH_V2_ENABLED; a newly selected v2 task must not
            # be downgraded when the worker re-resolves its frozen choice.
            refresh_driver=_refresh_protocol_version(effective_refresh_driver),
        )
    except Exception as exc:
        _QUEUE_SLOTS.release()
        result = {
            "ok": False,
            "status": "failed",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"查活入队失败: {type(exc).__name__}: {str(exc)[:160]}",
        }
        db.update_account_liveness(account_id, result)
        _append_log(email, result["error"])
        account_task_store.finish_task(
            task_id,
            status="failed",
            message="查活任务入队失败",
            error=result["error"],
        )
        return {"accepted": False, "busy": False, "error": result["error"]}

    response = {
        "accepted": True,
        "busy": False,
        "account_id": account_id,
        "email": email,
        "status": "queued",
        "trigger": str(trigger or "manual"),
        "task_id": task_id,
    }
    if effective_live_check_driver:
        response["live_check_driver"] = effective_live_check_driver
    if force_refresh:
        response["token_refresh_driver"] = effective_refresh_driver
        response["protocol_version"] = _refresh_protocol_version(effective_refresh_driver)
    return response


def queue_settings() -> dict:
    return {"workers": _WORKERS, "queue_limit": _QUEUE_LIMIT}
