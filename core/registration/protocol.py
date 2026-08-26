"""纯协议注册流程。

该模块承接原先位于 `main.py` 的 HTTP/curl_cffi 注册主体。驱动选择不在这里处理，
由 `core.registration.dispatcher` 统一完成。
"""
from __future__ import annotations

import logging
import time

from config import email as _email_cfg
from config import openai_protocol as _protocol_cfg
from config import twofa as _twofa_cfg
from core.account_export import (
    fetch_session,
    follow_oauth_callback,
    save_account_data,
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

logger = logging.getLogger(__name__)

_FINALIZE_SESSION_MAX_ATTEMPTS = 5
_FINALIZE_SESSION_BACKOFF_BASE = 2.0


def _finalize_registration_session(
    session: BrowserSession,
    continue_url: str,
    email: str,
    callback_referer: str = "https://auth.openai.com/about-you",
) -> tuple[dict, str]:
    """完成 OAuth 回调并拉取 accessToken。"""
    if not continue_url:
        raise RuntimeError("create_account 响应缺少 continue_url，无法完成 OAuth 回调")

    last_exc: Exception | None = None
    for attempt in range(1, _FINALIZE_SESSION_MAX_ATTEMPTS + 1):
        try:
            logger.info(
                f"[登录态] 完成 OAuth 回调并拉取 Token：{email} "
                f"(尝试 {attempt}/{_FINALIZE_SESSION_MAX_ATTEMPTS})"
            )
            follow_oauth_callback(session, continue_url, referer=callback_referer)
            human_delay("post_auth")
            session_info = fetch_session(session)
            access_token = session_info.get("accessToken")
            if not access_token:
                raise RuntimeError("session 响应缺少 accessToken")
            logger.info(f"[登录态] 已拿到 accessToken：{email}")
            return session_info, access_token
        except Exception as exc:
            last_exc = exc
            if attempt >= _FINALIZE_SESSION_MAX_ATTEMPTS:
                break
            backoff = _FINALIZE_SESSION_BACKOFF_BASE ** (attempt - 1)
            logger.warning(
                f"[登录态] 回调或拉取 Token 失败：{email}，"
                f"{type(exc).__name__}: {str(exc)[:180]}，{backoff:.1f}s 后重试"
            )
            time.sleep(backoff)

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
) -> dict:
    """执行完整的纯协议 ChatGPT 注册流程。"""
    from core.registration_service import report_job_progress

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
    logger.debug(f"[注册] 设备ID={session.device_id}，会话日志ID={session.auth_session_logging_id}")

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
            session_info, access_token = _finalize_registration_session(session, continue_url, email)
            report_job_progress("token", "success", "已获取 accessToken")
            if getattr(_protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", True):
                from core.chatgpt_bootstrap import authenticated_bootstrap

                authenticated_bootstrap(
                    session,
                    access_token,
                    strict=bool(getattr(_protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False)),
                )
            human_delay("post_auth")

        # ==================== 阶段7: 设置 2FA ====================
        totp_secret = None
        if _twofa_cfg.ENABLE_2FA:
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
            from config import codex as _codex_cfg
            from core.codex_oauth import run_codex_oauth

            if bool(getattr(_codex_cfg, "ENABLE_CODEX_AUTO", False)):
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

        # ==================== 阶段8: 持久化账号 ====================
        from core.email_provider import resolve_email_source

        account_id = save_account_data(
            email=email,
            access_token=access_token,
            totp_secret=totp_secret,
            email_source=resolve_email_source(email),
            proxy_used=session.proxy or None,
            plan_check_proxy=session.proxy,
            plan_check_session=session,
            batch_dir=batch_dir,
            extra={
                "user": session_info.get("user"),
                "account": session_info.get("account"),
                "expires": session_info.get("expires"),
                "device_id": session.device_id,
                "sentinel_sid": getattr(session, "sentinel_sid", None),
                "browser_profile": getattr(session, "browser_profile", None),
                "codex": codex_result,
            },
        )

        logger.info(f"[完成] {email}，账号ID={account_id}，Token={access_token[:16]}...")

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
        task_success = codex_ok
        task_error = None
        if not task_success:
            task_error = f"Codex 未完成: {codex_result.get('message', '未知')}"
            logger.warning(f"[任务结果] {email} 账号已保存但任务标失败，原因: {task_error}")

        return {
            "success": task_success,
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "flow": flow_result,
            "codex": codex_result,
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
