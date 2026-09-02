# -*- coding: utf-8 -*-
"""
注册后处理模块：
    1. 拉取 /api/auth/session，从中抽取 accessToken / user 信息
    2. 设置 2FA（TOTP），返回 secret
    3. 把账号信息（邮箱 + accessToken + TOTP secret）落盘成 JSON

整体复用注册阶段的 BrowserSession（同一 cookie jar / 同一 IP / 同一 UA），
避免再起新会话被风控关联或缺失登录态。
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
import threading
from urllib.parse import urlencode

import pyotp

from core.session import BrowserSession
from core.humanize import delay as human_delay

logger = logging.getLogger(__name__)

# 输出目录（与项目根 .claude/ 工作区分离，单独放在 accounts/）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ACCOUNTS_DIR = _PROJECT_ROOT / "accounts"
_BATCH_ARCHIVE_LOCK = threading.RLock()


def _account_material_line(email: str, row: dict | None = None) -> str:
    """优先输出 Outlook 原始素材；没有素材时退回邮箱地址。"""
    if row:
        return row.get("original_email_line") or row.get("email") or email
    return email


def _account_copy_line(material_line: str, access_token: str, totp_secret: str | None = None) -> str:
    """生成包含 token 的整行归档，方便从批次汇总文件里复制。"""
    return f"{material_line}----{access_token}----{totp_secret}" if totp_secret else f"{material_line}----{access_token}"


def create_batch_archive_dir(count: int, workers: int = 1) -> Path:
    """为一次运行创建批次归档目录，例如 accounts/20260509-10个-3线程。"""
    day = datetime.now().strftime("%Y%m%d")
    base_name = f"{day}-{count}个" if workers <= 1 else f"{day}-{count}个-{workers}线程"
    folder = _ACCOUNTS_DIR / base_name
    suffix = 2
    while folder.exists():
        folder = _ACCOUNTS_DIR / f"{base_name}-{suffix}"
        suffix += 1
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "注册成功的邮箱.txt").write_text("", encoding="utf-8")
    (folder / "注册成功的token.txt").write_text("", encoding="utf-8")
    (folder / "注册成功整行.txt").write_text("", encoding="utf-8")
    (folder / "注册成功账号.json").write_text("[]\n", encoding="utf-8")
    return folder


def _append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def _append_batch_archive(
    *,
    row_id: int,
    email: str,
    access_token: str,
    totp_secret: str | None,
    email_source: str | None,
    proxy_used: str | None,
    extra: dict,
    batch_dir: Path | None,
) -> Path:
    """把注册成功账号追加到本次批次目录的 TXT/JSON 文件中。"""
    from core import db

    folder = batch_dir or create_batch_archive_dir(count=1)
    row = db.get_account(row_id) or {}
    folder.mkdir(parents=True, exist_ok=True)
    material_line = _account_material_line(email, row)
    copy_line = _account_copy_line(material_line, access_token, totp_secret)
    archive = {
        "id": row_id,
        "email": email,
        "email_source": email_source,
        "proxy_used": proxy_used,
        "access_token": access_token,
        "totp_secret": totp_secret,
        "material_line": material_line,
        "copy_line": copy_line,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "row": row,
        "extra": extra,
    }

    with _BATCH_ARCHIVE_LOCK:
        _append_line(folder / "注册成功的邮箱.txt", material_line)
        _append_line(folder / "注册成功的token.txt", access_token)
        _append_line(folder / "注册成功整行.txt", copy_line)

        json_path = folder / "注册成功账号.json"
        try:
            rows = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else []
        except Exception:
            rows = []
        if not isinstance(rows, list):
            rows = []
        rows.append(archive)
        json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return folder


def follow_oauth_callback(session: BrowserSession, continue_url: str, referer: str = "https://auth.openai.com/about-you") -> str:
    """
    步骤12.5: 跟随 create_account 返回的 continue_url，完成 OAuth 回调。

    create_account 成功后返回的 continue_url 一般指向
        https://auth.openai.com/authorize/continue?...
    它会再 302 到
        https://chatgpt.com/api/auth/callback/openai?code=...&state=...
    回调请求会让 chatgpt.com 设置 `__Secure-next-auth.session-token` cookie，
    之后 /api/auth/session 才能返回 accessToken。

    Returns:
        重定向链最终落点 URL（一般是 chatgpt.com 站内地址）
    """
    if not continue_url:
        raise ValueError("continue_url 为空，无法完成 OAuth 回调")

    # continue_url 通常是 auth.openai.com/authorize/continue；
    # OTP 后 external_url 分支也可能直接给 chatgpt.com 回调地址。
    # 按目标域名选择导航头，避免 auth step 正确但请求头语义不一致。
    if str(continue_url).startswith("https://chatgpt.com"):
        headers = session.get_chatgpt_navigate_headers(referer=referer)
    else:
        headers = session.get_auth_navigate_headers(referer=referer)

    logger.info(f"[OAuth回调] 跟随 continue_url 完成 OAuth 回调...")
    resp = session.get(continue_url, headers=headers, allow_redirects=True)
    logger.info("[OAuth回调] 完成（最终落点原值不写日志）")
    return resp.url


def fetch_session(session: BrowserSession) -> dict:
    """
    GET https://chatgpt.com/api/auth/session
    注册成功后立刻调用，拿到 accessToken / user / account / expires。

    Returns:
        完整 session JSON，包含字段:
            - accessToken: str (Bearer token, 用于 backend-api 调用)
            - user: {id, name, email, idp, iat, mfa}
            - account: {id, planType, structure, ...}
            - expires: ISO 时间字符串
    """
    url = "https://chatgpt.com/api/auth/session"
    headers = session.get_nextauth_headers(referer="https://chatgpt.com/")

    logger.info("[Session] 拉取 ChatGPT session 信息...")
    resp = session.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("accessToken"):
        logger.error("[Session] 响应中没有 accessToken（响应原值不写日志）")
        raise RuntimeError("未拿到 accessToken，登录态可能未建立")

    user = data.get("user") or {}
    account = data.get("account") or {}
    logger.info(
        f"[Session] 成功，user_id={user.get('id')}, email={user.get('email')}, "
        f"plan={account.get('planType')}, mfa={user.get('mfa')}"
    )
    return data


def _trigger_reauth(session: BrowserSession, email: str) -> str:
    """
    步骤2-3: 发起密码重认证，返回 OpenAI authorize URL。
    重定向链会自动触发邮箱发送一份新的 OTP（用于 2FA 重认证）。
    """
    # 重新拿一次 csrf（旧的可能已过期）
    csrf_url = "https://chatgpt.com/api/auth/csrf"
    csrf_resp = session.get(csrf_url, headers=session.get_nextauth_headers(referer="https://chatgpt.com/"))
    csrf_resp.raise_for_status()
    csrf_token = csrf_resp.json()["csrfToken"]
    logger.info("[2FA] 重认证 CSRF 已获取（原值不写日志）")

    # POST /api/auth/signin/openai 带 reauth 参数
    query = {
        "connection": "password",
        "login_hint": email,
        "reauth": "password",
        "max_age": "0",
        "ext-oai-did": session.device_id,
    }
    signin_url = "https://chatgpt.com/api/auth/signin/openai?" + urlencode(query)

    headers = session.get_nextauth_headers(referer="https://chatgpt.com/")
    headers["content-type"] = "application/x-www-form-urlencoded"
    headers["origin"] = "https://chatgpt.com"

    body = urlencode({
        "callbackUrl": "https://chatgpt.com/?action=enable&factor=totp",
        "csrfToken": csrf_token,
        "json": "true",
    })

    logger.info("[2FA] 发起重认证 signin/openai...")
    resp = session.post(signin_url, headers=headers, data=body)
    resp.raise_for_status()
    auth_url = resp.json().get("url")
    if not auth_url:
        raise RuntimeError("未拿到 reauth authorize URL（原始响应未记录）")
    return auth_url


def _follow_reauth(session: BrowserSession, auth_url: str) -> None:
    """
    步骤3: 跟随 authorize URL 触发邮箱 OTP 发送。
    auth.openai.com 会重定向到 /email-verification 页面，期间发送 OTP 邮件。
    """
    headers = session.get_auth_navigate_headers(referer="https://chatgpt.com/")
    logger.info("[2FA] 跟随 authorize URL，触发 OTP 发送...")
    resp = session.get(auth_url, headers=headers, allow_redirects=True)
    logger.info("[2FA] 已到达邮箱验证页面（落点 URL 原值不写日志）")


def _validate_reauth_otp(session: BrowserSession, code: str) -> str:
    """
    步骤4: 提交邮箱 OTP 验证。
    返回 continue_url（带 code 参数的 callback URL，用于跳回 chatgpt.com）。
    """
    url = "https://auth.openai.com/api/accounts/email-otp/validate"
    headers = session.get_auth_headers(referer="https://auth.openai.com/email-verification")
    body = json.dumps({"code": code})

    logger.info("[2FA] 提交重认证 OTP（验证码原值不写日志）")
    resp = session.post(url, headers=headers, data=body)
    resp.raise_for_status()
    data = resp.json()
    continue_url = data.get("continue_url")
    if not continue_url:
        raise RuntimeError("OTP 验证响应缺少 continue_url（原始响应未记录）")
    return continue_url


def _exchange_new_token(session: BrowserSession, continue_url: str) -> str:
    """
    步骤5: 跟随 continue_url 完成回调，再次拉 /api/auth/session 拿到新 accessToken
    （此时 token 内嵌的 pwd_auth_time 是新鲜的，2FA enroll 才会接受）。
    """
    headers = session.get_auth_navigate_headers(referer="https://auth.openai.com/email-verification")
    logger.info("[2FA] 跟随 continue_url，刷新 session-token cookie...")
    session.get(continue_url, headers=headers, allow_redirects=True)

    # 拿新的 accessToken
    new_session = fetch_session(session)
    new_token = new_session["accessToken"]
    logger.info("[2FA] 新 accessToken 已获取（原值不写日志）")
    return new_token


def _enroll_totp(session: BrowserSession, access_token: str) -> tuple[str, str]:
    """
    步骤6: 注册 TOTP，返回 (secret, session_id)
    """
    url = "https://chatgpt.com/backend-api/accounts/mfa/enroll"
    headers = session.get_chatgpt_headers(referer="https://chatgpt.com/")
    headers["authorization"] = f"Bearer {access_token}"
    headers["oai-device-id"] = session.device_id
    headers["oai-language"] = session.navigator_language()

    body = json.dumps({"factor_type": "totp"})

    logger.info("[2FA] 注册 TOTP...")
    resp = session.post(url, headers=headers, data=body)
    if resp.status_code != 200:
        logger.error("[2FA] enroll 失败 HTTP %s（响应原值不写日志）", resp.status_code)
        resp.raise_for_status()
    data = resp.json()
    secret = data.get("secret")
    session_id = data.get("session_id")
    if not secret or not session_id:
        raise RuntimeError("enroll 响应字段缺失（原始响应未记录）")
    logger.info("[2FA] TOTP secret 已获取（原值不写日志）")
    return secret, session_id


def _activate_totp(
    session: BrowserSession,
    access_token: str,
    secret: str,
    session_id: str,
) -> bool:
    """
    步骤7: 用 secret 生成 6 位 TOTP 码，激活 2FA。
    """
    url = "https://chatgpt.com/backend-api/accounts/mfa/user/activate_enrollment"
    headers = session.get_chatgpt_headers(referer="https://chatgpt.com/")
    headers["authorization"] = f"Bearer {access_token}"
    headers["oai-device-id"] = session.device_id
    headers["oai-language"] = session.navigator_language()

    totp_code = pyotp.TOTP(secret).now()
    body = json.dumps({
        "code": totp_code,
        "factor_type": "totp",
        "session_id": session_id,
    })

    logger.info("[2FA] 激活 enrollment（TOTP 原值不写日志）")
    resp = session.post(url, headers=headers, data=body)
    if resp.status_code != 200:
        logger.error("[2FA] activate 失败 HTTP %s（响应原值不写日志）", resp.status_code)
        resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError("激活返回 success=false（原始响应未记录）")
    return True


def setup_2fa_protocol(session: BrowserSession, access_token: str, *, on_secret=None) -> str:
    """使用新鲜 accessToken 直接完成 TOTP enrollment 和激活。"""
    token = str(access_token or "").strip()
    if not token:
        raise ValueError("协议开通 2FA 缺少 accessToken")

    secret, session_id = _enroll_totp(session, token)
    if on_secret is not None:
        on_secret(secret)

    # 避免在 TOTP 窗口即将切换时提交刚生成的验证码。
    remaining = 30 - (int(time.time()) % 30)
    if remaining < 6:
        time.sleep(remaining + 1)
    _activate_totp(session, token, secret, session_id)
    logger.info("[2FA] 协议模式设置完成")
    return secret


def setup_2fa(session: BrowserSession, email: str, otp_code: str | None = None) -> str:
    """
    完整的 2FA 设置流程。
    会触发再发一份邮箱验证码：
        - USE_EMAIL_SERVICE=True 时自动从 Outlook 账号池拉取
        - 否则需要用户手动输入

    Args:
        session: 已完成注册的会话
        email: 账号邮箱（用作 login_hint）
        otp_code: 邮箱验证码（None 则按上述策略获取）

    Returns:
        TOTP secret（Base32 字符串），可直接用于 pyotp.TOTP() 生成 6 位动态码
    """
    # 用模块属性读，支持 WebUI 热加载
    from config import email as _email_cfg

    logger.info("=" * 60)
    logger.info("开始设置 2FA")
    logger.info("=" * 60)

    # 阶段一：重认证
    reauth_otp_after_ts = time.time()
    auth_url = _trigger_reauth(session, email)
    human_delay("api")
    _follow_reauth(session, auth_url)
    human_delay("navigate")

    if otp_code is None:
        if _email_cfg.USE_EMAIL_SERVICE:
            from core.email_provider import wait_for_otp
            logger.info("[2FA] 自动等待邮箱重认证 OTP...")
            otp_code = wait_for_otp(email, after_ts=reauth_otp_after_ts)
        else:
            logger.info("")
            logger.info("[2FA] 请检查邮箱，输入新收到的 6 位验证码")
            otp_code = input(">>> 2FA 验证码: ").strip()

    human_delay("otp_input")
    continue_url = _validate_reauth_otp(session, otp_code)
    human_delay("api")
    new_token = _exchange_new_token(session, continue_url)
    human_delay("api")

    # 阶段二：enroll + activate
    secret, session_id = _enroll_totp(session, new_token)
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
    email_source: str | None = None,
    proxy_used: str | None = None,
    batch_dir: Path | None = None,
) -> int:
    """Persist the registration core without running any post-processing.

    Token acquisition is the registration boundary.  This helper intentionally
    stops after the account row and batch archive are durable; callers can then
    run 2FA, Codex, or plan checks independently and record their outcomes.
    """
    from core.db import insert_account

    extra = extra or {}
    user = extra.get("user") or {}
    account = extra.get("account") or {}
    codex = extra.get("codex") or {}
    codex_status = codex.get("status")
    codex_error = codex.get("message") if codex_status == "failed" else None
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
        codex_status=codex_status,
        codex_error=codex_error,
    )
    batch_folder = _append_batch_archive(
        row_id=row_id,
        email=email,
        access_token=access_token,
        totp_secret=totp_secret,
        email_source=email_source,
        proxy_used=proxy_used,
        extra=extra,
        batch_dir=batch_dir,
    )
    logger.info("[Save] 账号核心已写入 DB, id=%s, email=%s", row_id, email)
    logger.info("[Save] 批次归档目录: %s", batch_folder)
    return row_id


def save_account_data(
    email: str,
    access_token: str,
    totp_secret: str | None = None,
    extra: dict | None = None,
    output_path: Path | None = None,  # 兼容老接口，已废弃
    email_source: str | None = None,
    proxy_used: str | None = None,
    plan_check_proxy: str | None = None,
    captured_plan_result: dict | None = None,
    batch_dir: Path | None = None,
    plan_check_session: BrowserSession | None = None,
) -> int:
    """
    将账号信息保存到本地 JSON/TXT 文件存储。
    返回新插入/更新的 row id。
    """
    extra = extra or {}
    row_id = persist_account_core(
        email=email,
        access_token=access_token,
        totp_secret=totp_secret,
        extra=extra,
        email_source=email_source,
        proxy_used=proxy_used,
        batch_dir=batch_dir,
    )

    # WebUI 注册线程会把这个阶段写入当前任务；CLI 或非任务调用中会自动忽略。
    from core.registration_service import report_job_progress
    report_job_progress("plan_check", "running", "正在查询账号套餐与 Plus 试用资格")

    # 注册浏览器若已经收到完整 accounts/check 权益响应，直接复用它，
    # 避免再发一次相同的套餐请求。原始响应只保留在浏览器内存，
    # 这里仅接收已经解析且不含凭据的结果。
    if isinstance(captured_plan_result, dict) and captured_plan_result.get("ok"):
        from core import db

        captured = dict(captured_plan_result)
        captured["trigger"] = "registration_browser_response"
        db.update_account_plan_check(acc_id=row_id, result=captured)
        report_job_progress(
            "plan_check",
            "success",
            f"复用浏览器权益数据：{captured.get('current_plan_type') or 'unknown'}，"
            f"Plus 试用{'可用' if captured.get('plus_trial_eligible') else '不可用'}",
        )
        logger.info(
            "[Plan] 复用注册浏览器权益响应: id=%s, email=%s, plus_trial=%s",
            row_id,
            email,
            bool(captured.get("plus_trial_eligible")),
        )
        return row_id

    # session 中的 account.planType 不能说明 Plus 试用资格。
    # 有注册任务代理时必须同步查完再返回，让上层随后释放代理租约；没有可复用代理时
    # 保持原来的后台队列行为，按套餐查询网络配置选择线路。
    try:
        explicit_proxy = str(plan_check_proxy or "").strip()
        if plan_check_proxy is not None:
            from core.plan_check_service import check_registration_account_plan

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
                plus_trial = "可用" if result.get("plus_trial_eligible") else "不可用"
                report_job_progress(
                    "plan_check",
                    "success",
                    f"套餐查询完成：{plan_type}，Plus 试用{plus_trial}",
                )
                logger.info(
                    f"[Plan] 注册代理同步查询完成: id={row_id}, email={email}, "
                    f"plus_trial={bool(result.get('plus_trial_eligible'))}"
                )
            else:
                report_job_progress(
                    "plan_check",
                    "failed",
                    f"套餐查询失败（不影响注册）：{str(result.get('error') or '未知错误')[:240]}",
                )
                logger.warning(f"[Plan] 注册代理同步查询失败（不影响注册结果）: {email}, {result.get('error')}")
        else:
            from core.plan_check_service import enqueue_account_plan_check

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
