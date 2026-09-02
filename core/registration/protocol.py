"""纯协议注册流程。

该模块承接原先位于 `main.py` 的 HTTP/curl_cffi 注册主体。驱动选择不在这里处理，
由 `core.registration.dispatcher` 统一完成。
"""
from __future__ import annotations

import logging
import time

from config import email as _email_cfg
from config import codex as _codex_cfg
from config import openai_protocol as _protocol_cfg
from config import twofa as _twofa_cfg
from core.account_export import (
    fetch_session,
    follow_oauth_callback,
    setup_2fa_protocol,
)
from core.chatgpt_auth import get_csrf_token, get_providers, signin_openai
from core.email_provider import wait_for_otp
from core.humanize import delay as human_delay
from core.openai_auth import (
    EmailOtpInvalidError,
    build_sentinel_header,
    create_account,
    follow_authorize,
    navigate_about_you,
    network_preflight,
    request_sentinel_token,
    send_email_otp,
    validate_email_otp,
)
from core.profile_utils import generate_random_birthday
from core.session import BrowserSession
from core.registration.state_machine import PageState, StageBudget, StageTimeout, classify_page

logger = logging.getLogger(__name__)

_FINALIZE_SESSION_MAX_ATTEMPTS = 5
_FINALIZE_SESSION_BACKOFF_BASE = 2.0


def _protocol_terminal_state(value: object) -> PageState | None:
    """Map callback/session errors to terminal states instead of polling blindly."""
    response = getattr(value, "response", None)
    if response is not None:
        response_url = str(getattr(response, "url", "") or "").lower()
        response_text = str(getattr(response, "text", "") or "").lower()
        try:
            status = int(getattr(response, "status_code", 0) or 0)
        except (TypeError, ValueError):
            status = 0
        if "callback" in response_url and status in (400, 401, 403, 422):
            return PageState.AUTH_ERROR
        if any(marker in response_text for marker in ("oauth callback error", "invalid_grant", "session has ended")):
            return PageState.AUTH_ERROR
    if isinstance(value, dict):
        error_text = " ".join(str(value.get(key) or "") for key in ("error", "error_code", "message", "detail", "url"))
        if any(marker in error_text.lower() for marker in (
            "oauthcallback", "oauth callback error", "callback error", "session has ended",
            "logged out", "unauthorized", "invalid_grant",
        )):
            state = classify_page({"url": value.get("url"), "text": error_text})
            return state if state in (PageState.AUTH_ERROR, PageState.LOGGED_OUT) else PageState.AUTH_ERROR
        return classify_page(value)
    text = str(value or "")
    if not text:
        return None
    state = classify_page({"url": getattr(value, "url", "") or (text if text.startswith("http") else ""), "text": text})
    return state if state in (PageState.AUTH_ERROR, PageState.LOGGED_OUT) else None


def _finalize_registration_session(
    session: BrowserSession,
    continue_url: str,
    email: str,
    callback_referer: str = "https://auth.openai.com/about-you",
    *,
    total_timeout: float = 90.0,
    budget: StageBudget | None = None,
) -> tuple[dict, str]:
    """完成 OAuth 回调并拉取 accessToken under one shared stage budget."""
    if not continue_url:
        raise RuntimeError("create_account 响应缺少 continue_url，无法完成 OAuth 回调")

    budget = budget or StageBudget.start(total_timeout)
    last_exc: Exception | None = None
    for attempt in range(1, _FINALIZE_SESSION_MAX_ATTEMPTS + 1):
        budget.require("OAuth callback/session")
        try:
            logger.info(
                f"[登录态] 完成 OAuth 回调并拉取 Token：{email} "
                f"(尝试 {attempt}/{_FINALIZE_SESSION_MAX_ATTEMPTS})"
            )
            callback_url = follow_oauth_callback(session, continue_url, referer=callback_referer)
            terminal = _protocol_terminal_state(callback_url)
            if terminal in (PageState.AUTH_ERROR, PageState.LOGGED_OUT):
                raise RuntimeError(f"OAuth callback reached terminal state: {terminal.value}")
            human_delay("post_auth")
            session_info = fetch_session(session)
            terminal = _protocol_terminal_state(session_info)
            if terminal in (PageState.AUTH_ERROR, PageState.LOGGED_OUT):
                raise RuntimeError(f"ChatGPT session reached terminal state: {terminal.value}")
            access_token = session_info.get("accessToken")
            if not access_token:
                raise RuntimeError("session 响应缺少 accessToken")
            logger.info(f"[登录态] 已拿到 accessToken：{email}")
            return session_info, access_token
        except Exception as exc:
            last_exc = exc
            terminal = _protocol_terminal_state(exc)
            if terminal in (PageState.AUTH_ERROR, PageState.LOGGED_OUT):
                raise RuntimeError(
                    f"OAuth callback/session entered terminal state {terminal.value}: {str(exc)[:240]}"
                ) from exc
            if attempt >= _FINALIZE_SESSION_MAX_ATTEMPTS:
                break
            backoff = _FINALIZE_SESSION_BACKOFF_BASE ** (attempt - 1)
            remaining = budget.remaining()
            if remaining <= 0:
                break
            logger.warning(
                f"[登录态] 回调或拉取 Token 失败：{email}，"
                f"{type(exc).__name__}: {str(exc)[:180]}，{backoff:.1f}s 后重试"
            )
            time.sleep(min(backoff, remaining))

    if budget.expired():
        raise StageTimeout(
            f"OAuth callback/session exceeded shared stage timeout {int(total_timeout)} seconds"
        ) from last_exc
    raise RuntimeError(
        f"OAuth 回调/拉取 Token 重试耗尽：{email}，"
        f"最后错误：{type(last_exc).__name__ if last_exc else 'Unknown'}: {last_exc}"
    ) from last_exc


def run_protocol_registration(
    email: str,
    name: str,
    birthday: str | None = None,
    proxy: str | None = None,
    otp_code: str | None = None,
    batch_dir=None,
    registration_options: dict | None = None,
) -> dict:
    """执行完整的纯协议 ChatGPT 注册流程。"""
    from core.registration_service import report_job_progress

    options = dict(registration_options or {})
    password_required = bool(options.get("password_enabled", False))
    twofa_enabled = bool(options.get("twofa_enabled", _twofa_cfg.ENABLE_2FA))
    # ``dict.get`` evaluates its default argument eagerly.  Read the live
    # config only for legacy callers that did not provide a job snapshot.
    codex_enabled = (
        bool(options["codex_enabled"])
        if "codex_enabled" in options
        else bool(getattr(_codex_cfg, "ENABLE_CODEX_AUTO", False))
    )
    plan_check_enabled = bool(options.get("plan_check_enabled", True))

    report_job_progress("browser", "running", "正在初始化协议注册会话")
    session = BrowserSession(proxy=proxy)
    report_job_progress("browser", "success", "协议注册会话已初始化")

    # 从代理 URL 中抽取 sid 段做日志，避免把账号密码完整打印。
    proxy_label = "无"
    if session.proxy:
        try:
            sid_part = next(
                (seg for seg in session.proxy.split("@")[0].split("-") if len(seg) == 8),
                "***",
            )
            proxy_label = f"{session.proxy.split('://')[0]}://...sid-{sid_part}...@{session.proxy.split('@')[-1]}"
        except Exception:
            proxy_label = "已配置"

    if not birthday:
        birthday = generate_random_birthday()

    logger.info(f"[注册] 开始：{email}，代理={proxy_label}")
    logger.info(f"[注册] 本次随机生日: {birthday}")
    logger.debug("[注册] 设备/会话标识已生成（原值不写日志）")

    create_acknowledged = False
    try:
        report_job_progress("page", "running", "正在初始化 ChatGPT 注册页状态")
        # 网络预检必须在 signin/follow_authorize 之前完成；预检不带邮箱，不会触发 OTP。
        network_preflight(session)
        human_delay("navigate")

        # 根据 HAR 补齐匿名态 ChatGPT 首屏/模型预热链路。
        if getattr(_protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", True):
            from core.chatgpt_bootstrap import anonymous_bootstrap

            anonymous_bootstrap(
                session,
                strict=bool(getattr(_protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False)),
            )
            human_delay("navigate")

        # ==================== 阶段1: ChatGPT 认证 ====================
        get_providers(session)
        human_delay("api")

        csrf_token = get_csrf_token(session)
        human_delay("api")
        report_job_progress("page", "success", "注册页状态已初始化")

        report_job_progress("submit_email", "running", "正在提交邮箱")
        authorize_url = signin_openai(session, csrf_token, email)
        report_job_progress("submit_email", "success", "邮箱已提交")
        report_job_progress("auth_redirect", "running", "正在跟随 OpenAI 认证跳转")
        human_delay("api")

        # 只读取本次 OTP 触发之后的邮件，避免命中旧验证码。
        otp_after_ts = time.time()

        # ==================== 阶段2: OpenAI Auth ====================
        follow_authorize(session, authorize_url)
        human_delay("navigate")
        report_job_progress("auth_redirect", "success", "已进入邮箱验证码页")

        # ==================== 阶段3: 验证码验证 ====================
        report_job_progress("email_otp", "running", "正在等待并验证邮箱验证码")
        validate_result = None
        max_otp_attempts = 3
        current_otp = otp_code
        for otp_attempt in range(1, max_otp_attempts + 1):
            if current_otp is None:
                if _email_cfg.USE_EMAIL_SERVICE:
                    logger.info(f"[OTP] 等待验证码：{email}（第 {otp_attempt}/{max_otp_attempts} 次）")
                    current_otp = wait_for_otp(email, after_ts=otp_after_ts)
                else:
                    logger.info("")
                    logger.info(f"[OTP] 请检查邮箱，输入收到的 6 位验证码（第 {otp_attempt}/{max_otp_attempts} 次）:")
                    current_otp = input(">>> 验证码: ").strip()

            human_delay("otp_input")
            try:
                sentinel_header_9 = None
                so_header_9 = None
                if getattr(_protocol_cfg, "SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE", False):
                    sentinel_resp_9 = request_sentinel_token(session, "authorize_continue")
                    sentinel_header_9, so_header_9 = build_sentinel_header(
                        session, sentinel_resp_9, "authorize_continue"
                    )
                    human_delay("challenge")

                validate_result = validate_email_otp(session, current_otp, sentinel_header_9, so_header_9)
                break
            except EmailOtpInvalidError as exc:
                if otp_attempt >= max_otp_attempts:
                    raise
                logger.warning(f"[OTP] 验证码错误/过期：{str(exc)[:180]}，准备重新发送并重新获取验证码")
                otp_after_ts = time.time()
                send_email_otp(session)
                human_delay("api")
                current_otp = None

        if validate_result is None:
            raise RuntimeError("OTP 验证未完成")
        report_job_progress("email_otp", "success", "邮箱验证码已通过")
        human_delay("api")

        # OTP 校验后的下一步由服务端 auth session 决定。
        page = validate_result.get("page") if isinstance(validate_result, dict) else {}
        page = page if isinstance(page, dict) else {}
        page_type = str(page.get("type") or "")
        otp_continue_url = (
            validate_result.get("continue_url")
            or validate_result.get("external_url")
            or validate_result.get("url")
            or page.get("continue_url")
            or page.get("external_url")
            or page.get("url")
        )
        logger.info(
            f"[步骤10] 后续分支判断: page_type={page_type or '空'}, "
            f"has_continue_url={bool(otp_continue_url)}"
        )

        # ==================== 阶段5/6: 完成注册或直接 OAuth 回调 ====================
        otp_continue_text = str(otp_continue_url or "")
        direct_oauth_after_otp = bool(
            otp_continue_text
            and "about-you" not in otp_continue_text
            and (
                "chatgpt.com/api/auth/callback" in otp_continue_text
                or "auth.openai.com/authorize/continue" in otp_continue_text
                or page_type == "external_url"
            )
        )
        if page_type == "external_url" or direct_oauth_after_otp:
            report_job_progress("profile", "skipped", "已有账号状态，无需填写资料")
            if not otp_continue_url:
                raise RuntimeError(f"OTP external_url 响应缺少可跟随 URL，无法继续: {validate_result}")
            logger.info(f"[注册] OTP 后进入 OAuth 回调分支，跳过 create_account：{email}")
            create_acknowledged = True
            report_job_progress("token", "running", "正在完成 OAuth 回调并获取 Token")
            session_info, access_token = _finalize_registration_session(
                session,
                otp_continue_url,
                email,
                callback_referer="https://auth.openai.com/email-verification",
            )
            report_job_progress("token", "success", "已获取 accessToken")
            if getattr(_protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", True):
                from core.chatgpt_bootstrap import authenticated_bootstrap

                authenticated_bootstrap(
                    session,
                    access_token,
                    strict=bool(getattr(_protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False)),
                )
            human_delay("post_auth")
        else:
            report_job_progress("profile", "running", "正在填写账号资料")
            if page_type and page_type not in ("about_you", "about-you"):
                if otp_continue_url and "about-you" not in str(otp_continue_url):
                    raise RuntimeError(
                        f"OTP 后续页面类型未知，不应盲目 create_account: "
                        f"page_type={page_type}, resp={validate_result}"
                    )
                logger.warning(
                    f"[步骤10] 未知 page_type={page_type}，但 continue_url 指向 about-you，继续 create_account"
                )

            about_url = str(otp_continue_url) if otp_continue_url and "about-you" in str(otp_continue_url) else None
            navigate_about_you(session, about_url)
            human_delay("navigate")

            sentinel_resp_11 = request_sentinel_token(session, "oauth_create_account")
            sentinel_header_11, so_header_11 = build_sentinel_header(
                session, sentinel_resp_11, "oauth_create_account"
            )
            human_delay("challenge")
            human_delay("form")

            create_result = create_account(session, name, birthday, sentinel_header_11, so_header_11)
            create_acknowledged = True
            report_job_progress("profile", "success", "账号资料已提交")

            logger.info(f"[注册] 创建接口已通过：{email}，继续完成 OAuth 回调")
            human_delay("post_auth")

            continue_url = create_result.get("continue_url")
            if not continue_url:
                raise RuntimeError(f"create_account 响应缺少 continue_url，无法继续: {create_result}")

            report_job_progress("token", "running", "正在完成 OAuth 回调并获取 Token")
            session_info, access_token = _finalize_registration_session(
                session,
                continue_url,
                email,
            )
            report_job_progress("token", "success", "已获取 accessToken")
            if getattr(_protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", True):
                from core.chatgpt_bootstrap import authenticated_bootstrap

                authenticated_bootstrap(
                    session,
                    access_token,
                    strict=bool(getattr(_protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False)),
                )
            human_delay("post_auth")

        # Token is the registration boundary.  Persist the core account before
        # entering any independent 2FA/Codex/plan work.  This is outside the
        # page-shape branches so the existing-session OAuth path is covered too.
        from core.registration_service import persist_registration_core
        from core.email_provider import resolve_email_source

        account_id = persist_registration_core(
            email=email,
            access_token=access_token,
            email_source=resolve_email_source(email),
            proxy_used=session.proxy or None,
            batch_dir=batch_dir,
            extra={
                "user": session_info.get("user"),
                "account": session_info.get("account"),
                "expires": session_info.get("expires"),
                "device_id": session.device_id,
                "sentinel_sid": getattr(session, "sentinel_sid", None),
                "browser_profile": getattr(session, "browser_profile", None),
                "registration_checkpoint": "core_persisted",
            },
        )
        logger.info("[核心完成] %s，账号ID=%s，Token 已获取（原值不写日志）", email, account_id)

        # ==================== 阶段7: 设置 2FA ====================
        totp_secret = None
        if twofa_enabled:
            report_job_progress("twofa", "running", "正在设置 Authenticator 2FA")
            try:
                twofa_driver = _twofa_cfg.get_twofa_driver()
                if twofa_driver != "protocol":
                    raise RuntimeError("协议注册驱动只支持 protocol 2FA；browser 模式请切换到 RoxyBrowser 注册")
                totp_secret = setup_2fa_protocol(session, access_token)
                report_job_progress("twofa", "success", "协议 2FA 已启用")
            except Exception as exc:
                logger.error(f"2FA 设置失败: {exc}")
                logger.debug("2FA 错误详情:", exc_info=True)
                logger.warning("将继续保存账号信息（不含 TOTP secret），可后续手动设置")
                report_job_progress("twofa", "failed", f"2FA 设置失败: {type(exc).__name__}: {str(exc)[:180]}")
        else:
            logger.debug("已跳过 2FA 设置 (config.ENABLE_2FA=False)")
            report_job_progress("twofa", "skipped", "未启用 Authenticator 2FA")

        # ==================== 阶段 7.5: Codex OAuth ====================
        codex_result = {"status": "skipped", "ok": False, "message": "未触发"}
        try:
            from core.codex_oauth import run_codex_oauth

            if codex_enabled:
                report_job_progress("codex", "running", "正在执行 Codex OAuth")
                codex_result = run_codex_oauth(email, proxy=session.proxy)
                report_job_progress(
                    "codex",
                    "success"
                    if codex_result.get("ok")
                    else "skipped"
                    if codex_result.get("status") == "skipped"
                    else "failed",
                    str(codex_result.get("message") or "Codex OAuth 已完成")[:300],
                )
            else:
                codex_result = {
                    "status": "skipped",
                    "ok": True,
                    "message": "ENABLE_CODEX_AUTO=False，跳过 Codex",
                }
                report_job_progress("codex", "skipped", codex_result["message"])
        except Exception as exc:
            codex_result = {
                "status": "failed",
                "ok": False,
                "message": f"{type(exc).__name__}: {str(exc)[:180]}",
            }
            report_job_progress("codex", "failed", codex_result["message"])

        if codex_result.get("ok"):
            logger.info(
                f"[Codex] 成功：{email}，file={codex_result.get('file_path')}，"
                f"callback={codex_result.get('callback_url')}"
            )
        elif codex_result.get("status") == "skipped":
            logger.info(f"[Codex] 跳过：{email}，原因={codex_result.get('message')}")
        else:
            logger.warning(f"[Codex] 失败：{email}，原因={codex_result.get('message')}")

        # Post-processing is deliberately outside the core persistence call.
        # Keep the existing status projections for account setup/retry views.
        from core import db
        if codex_result.get("status") in {"success", "failed", "skipped"}:
            codex_status = "success" if codex_result.get("ok") and codex_result.get("status") != "skipped" else codex_result.get("status")
            db.update_account_codex_status(
                email,
                codex_status,
                None if codex_status in {"success", "skipped"} else str(codex_result.get("message") or "")[:500],
            )
        if totp_secret:
            db.update_account_totp_secret(email, totp_secret)
            db.update_account_twofa_status(email, "success", "协议 2FA 已启用")
        elif twofa_enabled:
            db.update_account_twofa_status(email, "failed", "Authenticator 2FA 尚未完成")

        # 套餐查询独立入队；注册主体不再等待它完成。
        plan_result = {"status": "pending", "ok": False, "message": "套餐查询已独立入队"}
        if plan_check_enabled:
            try:
                from core.plan_check_service import enqueue_account_plan_check

                queued = enqueue_account_plan_check(
                    account_id=account_id,
                    email=email,
                    access_token=access_token,
                    trigger="registration_auto",
                )
                plan_result = {
                    "status": "pending" if queued.get("accepted") or queued.get("busy") else "failed",
                    # Enqueued/busy means the capability is not confirmed yet;
                    # keep it visible as a plan_check next action until its worker
                    # records a successful result.
                    "ok": False,
                    "message": "套餐查询已入队" if queued.get("accepted") else str(queued.get("error") or "套餐查询未入队"),
                }
            except Exception as exc:
                plan_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
        else:
            plan_result = {"status": "skipped", "ok": True, "message": "未启用注册后自动查套餐"}

        # ==================== 阶段9: 后置自动触发 flow ====================
        flow_result = {"status": "skipped", "ok": False, "message": "未触发"}
        try:
            from core.flow_trigger import trigger_flow

            flow_result = trigger_flow(access_token)
        except Exception as exc:
            flow_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}

        if flow_result.get("ok"):
            logger.info(
                f"[Flow] 成功：{email}，HTTP={flow_result.get('http_status')}, "
                f"flow_id={flow_result.get('flow_id') or '未解析'}"
            )
        elif flow_result.get("status") == "skipped":
            logger.info(f"[Flow] 跳过：{email}，原因={flow_result.get('message')}")
        else:
            logger.warning(
                f"[Flow] 失败：{email}，HTTP={flow_result.get('http_status') or '无'}, "
                f"原因={flow_result.get('message')}"
            )

        logger.debug(f"[完成] TOTP Secret: {totp_secret or '(未设置)'}")

        codex_ok = codex_result.get("ok") or codex_result.get("status") == "skipped"
        twofa_ok = (not twofa_enabled) or bool(totp_secret)
        postprocess_success = bool(codex_ok and twofa_ok and plan_result.get("ok"))
        task_error = None if postprocess_success else "; ".join(
            item for item in (
                None if codex_ok else f"Codex 未完成: {codex_result.get('message', '未知')}",
                None if twofa_ok else "2FA 未完成",
                None if plan_result.get("ok") else "套餐查询待重试",
            ) if item
        )
        from core.registration_postprocess import summarize_postprocess
        readiness = summarize_postprocess(
            core_success=True,
            password_present=True,
            outcomes={"twofa": {"status": "success" if twofa_ok else "failed", "ok": twofa_ok},
                      "codex": codex_result, "plan_check": plan_result},
            password_required=password_required,
            twofa_required=twofa_enabled,
            codex_enabled=codex_enabled,
            plan_check_required=plan_check_enabled,
        )

        return {
            "success": True,
            "registration_success": True,
            "postprocess_success": postprocess_success,
            "partial_success": not postprocess_success,
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "flow": flow_result,
            "codex": codex_result,
            "plan_check": plan_result,
            "next_actions": [action.as_dict() for action in readiness.next_actions],
            "account_readiness": readiness.account_readiness,
            "error": task_error,
        }

    except Exception as exc:
        logger.error(f"[失败] {email}: {type(exc).__name__}: {exc}")
        logger.debug("详细错误信息:", exc_info=True)
        from core.openai_auth import AccountUnusableError

        account_dead = isinstance(exc, AccountUnusableError)
        try:
            if email:
                from core.email_provider import release_email

                if account_dead:
                    src = release_email(
                        email,
                        status="failed",
                        note=f"账号已废弃，邮箱不可用: {str(exc)[:180]}",
                    )
                    logger.warning(f"[邮箱:{src}] {email} 账号已废弃，标记为 failed，不再重新注册")
                elif create_acknowledged:
                    src = release_email(
                        email,
                        status="failed",
                        note=f"创建接口已通过但后续失败，已废弃: {str(exc)[:180]}",
                    )
                    logger.warning(f"[邮箱:{src}] {email} 已创建但后续失败，标记为 failed，不再重新注册")
                else:
                    src = release_email(email, status="available", note=f"上次失败: {str(exc)[:180]}")
                    logger.info(f"[邮箱:{src}] {email} 已恢复 available")
        except Exception:
            pass
        return {"success": False, "email": email, "error": str(exc)}
