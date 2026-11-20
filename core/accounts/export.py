# -*- coding: utf-8 -*-
"""
注册后处理模块：
    1. 拉取 /api/auth/session，从中抽取 accessToken / user 信息
    2. 设置 2FA（TOTP），返回 secret
    3. 把账号信息（邮箱 + accessToken + TOTP secret）写入 PostgreSQL

整体复用注册阶段的 BrowserSession（同一 cookie jar / 同一 IP / 同一 UA），
避免再起新会话被风控关联或缺失登录态。
"""
import json
import logging
import re
import time
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlencode, urlparse

import pyotp

from core.auth.humanize import delay as human_delay
from core.accounts.plans.promotion import promotion_label
from core.auth.protocol.session import BrowserSession

from core.kernels.protocol.local import twofa as _twofa_kernel

logger = logging.getLogger('core.account_export')

_TWOFA_PROXY_URL_RE = re.compile(
    r"(?P<scheme>\b[a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@[^\s/]+",
    re.IGNORECASE,
)


TwofaEnrollmentAuthRequired = _twofa_kernel.TwofaEnrollmentAuthRequired


TwofaProtocolHTTPError = _twofa_kernel.TwofaProtocolHTTPError


TwofaProtocolTransportError = _twofa_kernel.TwofaProtocolTransportError


TwofaProtocolStepError = _twofa_kernel.TwofaProtocolStepError


def _sanitize_twofa_payload(payload):
    from core.registration.debug import sanitize_body

    return sanitize_body(payload)


def _twofa_error_fields(response) -> tuple[str, str, str]:
    return _twofa_kernel._twofa_error_fields(response, sanitize_body=_sanitize_twofa_payload)


def _twofa_http_error(operation: str, response) -> TwofaProtocolHTTPError:
    return _twofa_kernel._twofa_http_error(operation, response, _twofa_error_fields=_twofa_error_fields)


def _is_retryable_twofa_transport_error(exc: BaseException) -> bool:
    return _twofa_kernel._is_retryable_twofa_transport_error(exc)


def _activation_400_is_retryable(exc: TwofaProtocolHTTPError) -> bool:
    return _twofa_kernel._activation_400_is_retryable(exc)


def _wait_for_next_totp_window() -> None:
    return _twofa_kernel._wait_for_next_totp_window(clock=time)


def _clear_twofa_session_circuit(session: BrowserSession, *, source: str = "可选预热") -> None:
    return _twofa_kernel._clear_twofa_session_circuit(session, source=source)


_RETRYABLE_REAUTH_HINTS = (
    "403", "408", "425", "429", "500", "502", "503", "504",
    "proxy", "socks", "timeout", "timed out", "connection", "closed",
    "reset", "temporarily unavailable", "熔断冷却",
)


def _is_retryable_reauth_error(exc: BaseException) -> bool:
    return _twofa_kernel._is_retryable_reauth_error(exc)


def _raise_twofa_http_response(operation: str, response) -> None:
    return _twofa_kernel._raise_twofa_http_response(operation, response, _twofa_http_error=_twofa_http_error)


def _reauth_retry_settings() -> tuple[int, float]:
    from config import twofa as _twofa_cfg

    max_attempts = max(1, min(8, int(getattr(_twofa_cfg, "TWOFA_REAUTH_MAX_ATTEMPTS", 3) or 3)))
    base_delay = max(0.0, min(60.0, float(getattr(_twofa_cfg, "TWOFA_REAUTH_RETRY_DELAY", 3.0) or 0.0)))
    return max_attempts, base_delay


def _run_reauth_step_with_retry(operation: str, session: BrowserSession, callback, *, retry_forbidden: bool = True):
    return _twofa_kernel._run_reauth_step_with_retry(
        operation,
        session,
        callback,
        retry_forbidden=retry_forbidden,
        _clear_twofa_session_circuit=_clear_twofa_session_circuit,
        _is_retryable_reauth_error=_is_retryable_reauth_error,
        _twofa_http_error=_twofa_http_error,
        _reauth_retry_settings=_reauth_retry_settings,
        clock=time,
    )


def follow_oauth_callback(
    session: BrowserSession,
    continue_url: str,
    referer: str = "https://auth.openai.com/about-you",
    *,
    timeout: float | None = None,
) -> str:
    return _twofa_kernel.follow_oauth_callback(session, continue_url, referer, timeout=timeout)


def fetch_session(session: BrowserSession, *, timeout: float | None = None) -> dict:
    return _twofa_kernel.fetch_session(session, timeout=timeout)


def _trigger_reauth(session: BrowserSession, email: str) -> str:
    return _twofa_kernel._trigger_reauth(session, email, _raise_twofa_http_response=_raise_twofa_http_response)


def _follow_reauth(session: BrowserSession, auth_url: str) -> str:
    return _twofa_kernel._follow_reauth(session, auth_url, _raise_twofa_http_response=_raise_twofa_http_response)


def _trigger_reauth_with_retry(session: BrowserSession, email: str) -> str:
    return _twofa_kernel._trigger_reauth_with_retry(
        session, email, _run_reauth_step_with_retry=_run_reauth_step_with_retry, _trigger_reauth=_trigger_reauth
    )


def _warm_auth_document_for_reauth(session: BrowserSession) -> None:
    return _twofa_kernel._warm_auth_document_for_reauth(
        session, _clear_twofa_session_circuit=_clear_twofa_session_circuit, clock=time
    )


def _follow_reauth_with_retry(session: BrowserSession, auth_url: str) -> str:
    return _twofa_kernel._follow_reauth_with_retry(
        session,
        auth_url,
        _follow_reauth=_follow_reauth,
        _run_reauth_step_with_retry=_run_reauth_step_with_retry,
        _warm_auth_document_for_reauth=_warm_auth_document_for_reauth,
    )


def _validate_reauth_otp(session: BrowserSession, code: str) -> str:
    return _twofa_kernel._validate_reauth_otp(session, code, _raise_twofa_http_response=_raise_twofa_http_response)


def _validate_reauth_otp_with_retry(session: BrowserSession, code: str) -> str:
    return _twofa_kernel._validate_reauth_otp_with_retry(
        session,
        code,
        _clear_twofa_session_circuit=_clear_twofa_session_circuit,
        _is_retryable_twofa_transport_error=_is_retryable_twofa_transport_error,
        _validate_reauth_otp=_validate_reauth_otp,
        _reauth_retry_settings=_reauth_retry_settings,
        clock=time,
    )


def _exchange_new_token(session: BrowserSession, continue_url: str) -> str:
    return _twofa_kernel._exchange_new_token(
        session, continue_url, _raise_twofa_http_response=_raise_twofa_http_response, fetch_session=fetch_session
    )


def _exchange_new_token_with_retry(session: BrowserSession, continue_url: str) -> str:
    return _twofa_kernel._exchange_new_token_with_retry(
        session,
        continue_url,
        _exchange_new_token=_exchange_new_token,
        _run_reauth_step_with_retry=_run_reauth_step_with_retry,
    )


def _enroll_totp(session: BrowserSession, access_token: str) -> tuple[str, str]:
    return _twofa_kernel._enroll_totp(
        session,
        access_token,
        _clear_twofa_session_circuit=_clear_twofa_session_circuit,
        _is_retryable_twofa_transport_error=_is_retryable_twofa_transport_error,
        _twofa_http_error=_twofa_http_error,
        clock=time,
    )


def _activate_totp(session: BrowserSession, access_token: str, secret: str, session_id: str) -> bool:
    return _twofa_kernel._activate_totp(
        session,
        access_token,
        secret,
        session_id,
        _activation_400_is_retryable=_activation_400_is_retryable,
        _clear_twofa_session_circuit=_clear_twofa_session_circuit,
        _is_retryable_twofa_transport_error=_is_retryable_twofa_transport_error,
        _twofa_http_error=_twofa_http_error,
        _wait_for_next_totp_window=_wait_for_next_totp_window,
        clock=time,
        totp_factory=pyotp.TOTP,
    )


def setup_2fa_protocol(session: BrowserSession, access_token: str, *, on_secret=None) -> str:
    return _twofa_kernel.setup_2fa_protocol(
        session, access_token, on_secret=on_secret, enroll_totp=_enroll_totp, activate_totp=_activate_totp, clock=time
    )


def setup_2fa(
    session: BrowserSession,
    email: str,
    otp_code: str | None = None,
    *,
    on_secret=None,
    on_access_token=None,
) -> str:
    """
    完整的 2FA 设置流程。
    会触发再发一份邮箱验证码：
        - USE_EMAIL_SERVICE=True 时按账号绑定的邮箱来源自动拉取
        - 否则需要用户手动输入

    Args:
        session: 已完成注册的会话
        email: 账号邮箱（用作 login_hint）
        otp_code: 邮箱验证码（None 则按上述策略获取）
        on_secret: 在激活前拿到 TOTP secret 时调用，用于持久化检查点
        on_access_token: 重认证换取新 accessToken 后调用，用于持久化新会话

    Returns:
        TOTP secret（Base32 字符串），可直接用于 pyotp.TOTP() 生成 6 位动态码
    """
    # 用模块属性读，支持 WebUI 热加载
    from config import email as _email_cfg

    logger.info("=" * 60)
    logger.info("开始设置 2FA")
    logger.info("=" * 60)

    # 阶段一：重认证
    auth_url = _trigger_reauth_with_retry(session, email)
    human_delay("api")
    _follow_reauth_with_retry(session, auth_url)
    human_delay("navigate")

    if otp_code is None:
        from core.auth.protocol.openai_auth import EmailOtpSendError, send_email_otp

        # 使用本次发码前的时间，既排除旧邮件，也不漏掉请求期间即刻送达的新邮件。
        reauth_otp_after_ts = time.time()
        try:
            send_email_otp(session)
        except EmailOtpSendError as exc:
            raise TwofaProtocolStepError("reauth_otp_send", f"email_otp_send_{exc.reason}") from None
        except Exception as exc:
            # 发码结果未知时本次不重放请求，交由既有兜底或后续任务重跑恢复。
            raise TwofaProtocolStepError("reauth_otp_send", type(exc).__name__) from None
        if _email_cfg.USE_EMAIL_SERVICE:
            from core.email.provider import wait_for_otp
            logger.info("[2FA] 自动等待邮箱重认证 OTP...")
            otp_code = wait_for_otp(email, after_ts=reauth_otp_after_ts)
        else:
            logger.info("")
            logger.info("[2FA] 请检查邮箱，输入新收到的 6 位验证码")
            otp_code = input(">>> 2FA 验证码: ").strip()

    human_delay("otp_input")
    continue_url = _validate_reauth_otp_with_retry(session, otp_code)
    human_delay("api")
    new_token = _exchange_new_token_with_retry(session, continue_url)
    if on_access_token is not None:
        on_access_token(new_token)
    human_delay("api")

    # 阶段二：enroll + activate
    secret, session_id = _enroll_totp(session, new_token)
    if on_secret is not None:
        on_secret(secret)
    human_delay("form")
    _activate_totp(session, new_token, secret, session_id)

    logger.info("=" * 60)
    logger.info("✅ 2FA 设置完成（secret 原值不写日志）")
    logger.info("=" * 60)
    return secret


def persist_account_core(
    email: str,
    access_token: str,
    totp_secret: str | None = None,
    extra: dict | None = None,
    chatgpt_session: dict | None = None,
    email_source: str | None = None,
    proxy_used: str | None = None,
) -> int:
    """Persist the registration core without running any post-processing.

    Token acquisition is the registration boundary.  This helper intentionally
    stops after the account row is durable; callers can then
    run 2FA, Codex, or plan checks independently and record their outcomes.
    """
    from core.db import insert_account

    extra = dict(extra or {})
    if str(email_source or "").strip().lower() == "remail":
        # 取件凭据随账号写入 PostgreSQL，供重启后的 OTP 流程恢复原订单。
        # 普通账号列表不返回 extra_json；不能把 service token 写入日志。
        from core.email.remail.client import get_account_context_metadata

        metadata = get_account_context_metadata(email)
        if metadata:
            extra["email_service"] = metadata
    user = extra.get("user") or {}
    account = extra.get("account") or {}
    codex = extra.get("codex") or {}
    codex_status = codex.get("status")
    codex_error = (
        "Codex 登录验证结果待核对，不能自动重新提交"
        if codex_status == "attention_required"
        else codex.get("message") if codex_status == "failed" else None
    )
    row_id = insert_account(
        email=email,
        access_token=access_token,
        totp_secret=totp_secret,
        user_id=user.get("id"),
        user_name=user.get("name"),
        plan_type=account.get("planType"),
        expires_at=extra.get("expires"),
        device_id=extra.get("device_id"),
        proxy_used=proxy_used,
        email_source=email_source,
        extra=extra,
        chatgpt_session=chatgpt_session,
        codex_status=codex_status,
        codex_error=codex_error,
    )
    logger.info("[Save] 账号核心已写入 DB, id=%s, email=%s", row_id, email)
    return row_id


def save_account_data(
    email: str,
    access_token: str,
    totp_secret: str | None = None,
    extra: dict | None = None,
    output_path: Path | None = None,  # 兼容老接口；不再写文件
    email_source: str | None = None,
    proxy_used: str | None = None,
    plan_check_proxy: str | None = None,
    captured_plan_result: dict | None = None,
    plan_check_session: BrowserSession | None = None,
    *,
    chatgpt_session: dict | None = None,
) -> int:
    """
    将账号信息保存到 PostgreSQL。
    返回新插入/更新的 row id。
    """
    extra = extra or {}
    row_id = persist_account_core(
        email=email,
        access_token=access_token,
        totp_secret=totp_secret,
        extra=extra,
        chatgpt_session=chatgpt_session,
        email_source=email_source,
        proxy_used=proxy_used,
    )

    # WebUI 注册线程会把这个阶段写入当前任务；CLI 或非任务调用中会自动忽略。
    from core.registration.service import report_job_progress
    report_job_progress("plan_check", "running", "正在查询账号套餐与 Plus 优惠资格")

    # 注册浏览器若已经收到完整 accounts/check 权益响应，直接复用它，
    # 避免再发一次相同的套餐请求。原始响应只保留在浏览器内存，
    # 这里仅接收已经解析且不含凭据的结果。
    if isinstance(captured_plan_result, dict) and captured_plan_result.get("ok"):
        from core import db

        captured = dict(captured_plan_result)
        if not captured.get("quota_status"):
            from core.accounts.plans.client import query_account_quota
            captured.update(query_account_quota(
                access_token,
                proxy=plan_check_proxy,
                session=plan_check_session,
            ))
        captured["trigger"] = "registration_browser_response"
        db.update_account_plan_check(acc_id=row_id, result=captured)
        report_job_progress(
            "plan_check",
            "success",
            f"复用浏览器权益数据：{captured.get('current_plan_type') or 'unknown'}，"
            f"Plus {promotion_label(captured)}",
        )
        logger.info(
            "[Plan] 复用注册浏览器权益响应: id=%s, email=%s, plus_promo=%s",
            row_id,
            email,
            captured.get("plus_promo_kind") or "none",
        )
        return row_id

    # session 中的 account.planType 不能说明 Plus 优惠。
    # 有注册任务代理时必须同步查完再返回，让上层随后释放代理租约；没有可复用代理时
    # 保持原来的后台队列行为，按套餐查询网络配置选择线路。
    try:
        explicit_proxy = str(plan_check_proxy or "").strip()
        if plan_check_proxy is not None:
            from core.accounts.plans.service import check_registration_account_plan

            logger.info(f"[Plan] 使用本次注册代理同步查询，完成后再释放租约: id={row_id}, email={email}")
            if plan_check_session is not None:
                logger.info("[Plan] 复用 2FA 协议会话查询套餐，保留同一设备与 CF Cookie: id=%s", row_id)
            query_kwargs = {
                "account_id": row_id,
                "email": email,
                "access_token": access_token,
                "proxy": explicit_proxy,
            }
            if plan_check_session is not None:
                query_kwargs["session"] = plan_check_session
            result = check_registration_account_plan(**query_kwargs)
            if result.get("ok"):
                plan_type = str(result.get("current_plan_type") or "unknown")
                report_job_progress(
                    "plan_check",
                    "success",
                    f"套餐查询完成：{plan_type}，Plus {promotion_label(result)}",
                )
                logger.info(
                    f"[Plan] 注册代理同步查询完成: id={row_id}, email={email}, "
                    f"plus_promo={result.get('plus_promo_kind') or 'none'}"
                )
            else:
                report_job_progress(
                    "plan_check",
                    "failed",
                    f"套餐查询失败（不影响注册）：{str(result.get('error') or '未知错误')[:240]}",
                )
                logger.warning(f"[Plan] 注册代理同步查询失败（不影响注册结果）: {email}, {result.get('error')}")
        else:
            from core.accounts.plans.service import enqueue_account_plan_check

            queued = enqueue_account_plan_check(
                account_id=row_id,
                email=email,
                access_token=access_token,
                trigger="registration_auto",
            )
            if queued.get("accepted"):
                report_job_progress("plan_check", "skipped", "套餐查询已加入后台队列")
                logger.info(f"[Plan] 注册后自动查询已入队: id={row_id}, email={email}")
            elif queued.get("busy"):
                report_job_progress("plan_check", "skipped", "该账号已有套餐查询正在执行")
                logger.info(f"[Plan] 账号已有套餐查询，注册流程不重复入队: id={row_id}, email={email}")
            else:
                report_job_progress(
                    "plan_check",
                    "failed",
                    f"套餐查询入队失败（不影响注册）：{str(queued.get('error') or '未知错误')[:230]}",
                )
                logger.warning(f"[Plan] 注册后自动查询入队失败（不影响注册结果）: {email}, {queued.get('error')}")
    except Exception as exc:
        report_job_progress(
            "plan_check",
            "failed",
            f"套餐查询异常（不影响注册）：{type(exc).__name__}: {str(exc)[:200]}",
        )
        logger.warning(
            f"[Plan] 注册后自动查询入队异常（不影响注册结果）: "
            f"{email}, {type(exc).__name__}: {str(exc)[:180]}"
        )
    return row_id
