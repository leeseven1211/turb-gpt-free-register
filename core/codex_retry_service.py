# -*- coding: utf-8 -*-
"""Codex 授权补跑服务，供账号页和注册任务队列共同使用。"""
import json
import logging
import threading
import time
from pathlib import Path

from core import db, task_run_log
from core.operations import task_gateway as account_task_store
from core.auth_challenge import PasswordSetupUnsupportedError, auth_result_for_operation
from core.openai_auth import AccountUnusableError

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).resolve().parent.parent / "注册日志"
_RETRYING: set[str] = set()
_RETRYING_LOCK = threading.Lock()
_STOP_REQUESTED: set[str] = set()
_RUNNING_THREADS: dict[str, int] = {}
_RESERVED_AT: dict[str, float] = {}
_ACCOUNT_SETUP_DB_LOCK = threading.RLock()


def _attach_auth_projection(
    result: dict,
    *,
    auth_method: str,
    remote_identity: str = "existing",
) -> dict:
    """Attach the shared safe authentication projection to account operations."""
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


class CodexRetryStopped(RuntimeError):
    """用户手动停止 Codex 补跑。"""


def _totp_setup_pending(account: dict) -> bool:
    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    return bool(raw_extra.get("totp_setup_pending")) if isinstance(raw_extra, dict) else False


def _account_login_password(account: dict | None) -> str:
    """读取账号当前密码；旧账号兼容历史字段。"""
    raw_extra = (account or {}).get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    if not isinstance(raw_extra, dict):
        return ""
    return str(
        raw_extra.get("account_password")
        or raw_extra.get("login_password")
        or raw_extra.get("registration_password")
        or ""
    ).strip()


def _persist_account_deactivated(email: str, exc: BaseException) -> bool:
    """Persist a confirmed unusable result without touching saved credentials."""
    code = str(getattr(exc, "error_code", "") or "").strip() or "account_deactivated"
    try:
        account = db.get_account_by_email(email) or {}
        account_id = int(account.get("id") or 0)
        if not account_id:
            return False
        return bool(db.update_account_liveness(
            account_id,
            {
                "ok": False,
                "status": "deactivated",
                "error": code,
                "validation_method": "account_setup",
            },
        ))
    except Exception:
        logger.exception("写回废号账号状态失败：email=%s", email)
        return False


def _should_browser_fallback_after_protocol_error(exc: BaseException) -> bool:
    """Avoid repeating browser OTP when the shared mailbox path already failed."""
    text = f"{type(exc).__name__}: {exc}".lower()
    mailbox_markers = (
        "forwardimaperror",
        "icloudhmeerror",
        "emailbutler",
        "email_butler",
        "imap",
        "mailbox",
        "尚未收到新的 openai 验证码",
        "等待新的邮箱验证码超时",
        "等待邮箱验证码超时",
    )
    return not any(marker in text for marker in mailbox_markers)


def _run_protocol_direct_twofa(
    email: str,
    account: dict,
    account_route,
    task_id: int | None,
    *,
    protocol_reauth_enabled: bool = True,
) -> dict:
    """Use the Protocol-first path to enable 2FA without opening Roxy when possible.

    ``BrowserSession`` here is the existing curl/cffi protocol client, not a
    visible browser.  Missing/stale AT enters protocol email reauthentication;
    the caller decides whether a protocol failure may continue into the
    browser fallback.
    """
    existing_secret = str(account.get("totp_secret") or "").strip()
    if existing_secret and not _totp_setup_pending(account):
        account_task_store.append_event(
            task_id,
            stage="twofa",
            message="账号已有 Authenticator 2FA，跳过重复设置",
            detail={
                "driver": "protocol",
                "auth_source": "existing_at",
                "browser_opened": False,
            },
            state="skipped",
        )
        return {
            "status": "success",
            "ok": True,
            "message": "账号已有 Authenticator 2FA，无需重复设置",
            "twofa_driver": "protocol",
            "auth_source": "existing_at",
            "browser_opened": False,
        }

    access_token = str(account.get("access_token") or "").strip()
    account_task_store.append_event(
        task_id,
        stage="twofa",
        message=(
            "账号已有 access_token，先使用协议开通 Authenticator 2FA"
            if access_token
            else "账号没有可复用 access_token，先通过协议重认证获取新 AT"
        ),
        detail={
            "driver": "protocol",
            "auth_source": "existing_at" if access_token else "protocol_reauth",
            "browser_opened": False,
            "protocol_reauth_enabled": bool(protocol_reauth_enabled),
        },
        state="running",
    )
    state = {"secret": ""}

    def _checkpoint(secret: str) -> None:
        normalized = str(secret or "").strip()
        if not normalized:
            raise RuntimeError("Authenticator key 检查点为空")
        with _ACCOUNT_SETUP_DB_LOCK:
            if not db.update_account_totp_secret(email, normalized, setup_pending=True):
                raise RuntimeError("Authenticator key 写入账号检查点失败")
        state["secret"] = normalized

    from core.account_export import TwofaEnrollmentAuthRequired, setup_2fa, setup_2fa_protocol
    from core.session import BrowserSession

    protocol_session = BrowserSession(
        proxy=str(getattr(account_route, "proxy_url", "") or ""),
    )
    auth_source_used = "existing_at" if access_token else "protocol_reauth"

    def _protocol_reauth() -> str:
        if not protocol_reauth_enabled:
            raise RuntimeError("协议 2FA 需要近期认证，但已关闭协议重认证")
        account_task_store.append_event(
            task_id,
            stage="twofa",
            message="协议 2FA 需要近期认证，转为协议邮箱重认证获取新 AT",
            detail={
                "driver": "protocol",
                "auth_source": "protocol_reauth",
                "browser_opened": False,
            },
            state="running",
        )

        def _save_refreshed_token(new_token: str) -> None:
            normalized = str(new_token or "").strip()
            if not normalized:
                raise RuntimeError("协议重认证未返回新的 access_token")
            if not db.update_account_session(email, normalized):
                raise RuntimeError("协议重认证取得新 AT，但写回账号失败")
            account_task_store.append_event(
                task_id,
                stage="token",
                message="协议邮箱重认证取得的新 AT 已写回账号",
                detail={"saved": True, "source": "protocol_reauth"},
                state="success",
            )

        nonlocal auth_source_used
        secret = setup_2fa(
            protocol_session,
            email,
            on_secret=_checkpoint,
            on_access_token=_save_refreshed_token,
        )
        auth_source_used = "protocol_reauth"
        return secret

    if access_token:
        try:
            secret = setup_2fa_protocol(
                protocol_session,
                access_token,
                on_secret=_checkpoint,
            )
        except TwofaEnrollmentAuthRequired:
            secret = _protocol_reauth()
    else:
        secret = _protocol_reauth()
    if not state["secret"]:
        _checkpoint(secret)
    with _ACCOUNT_SETUP_DB_LOCK:
        if not db.update_account_totp_secret(email, state["secret"], setup_pending=False):
            raise RuntimeError("Authenticator 完成状态写入账号失败")
        if not db.update_account_twofa_status(email, "success", "Authenticator 2FA 已启用"):
            raise RuntimeError("Authenticator 结果状态写入账号失败")
    check_stop_requested(email)
    account_task_store.append_event(
        task_id,
        stage="twofa_result",
        message="协议已启用 Authenticator 2FA，未打开浏览器",
        detail={
            "enabled": True,
            "driver": "protocol",
            "auth_source": auth_source_used,
            "browser_opened": False,
        },
        state="success",
    )
    return {
        "status": "success",
        "ok": True,
        "message": "Authenticator 2FA 已通过协议启用",
        "twofa_driver": "protocol",
        "auth_source": auth_source_used,
        "browser_opened": False,
    }


def _run_retry_plan_check(
    email: str,
    account: dict,
    account_route,
    task_id: int | None,
    *,
    trigger: str,
) -> dict | None:
    """补跑前同步补查套餐；失败只记事件，不阻断后续账号动作。"""
    if str(account.get("plan_check_status") or "").lower() == "success":
        account_task_store.append_event(
            task_id,
            stage="plan_check",
            message="账号已有成功套餐记录，跳过重复查询",
            state="skipped",
        )
        return {"status": "success", "ok": True, "message": "账号已有成功套餐记录"}
    token = str(account.get("access_token") or "").strip()
    if not token:
        account_task_store.append_event(
            task_id,
            stage="plan_check",
            message="账号缺少 access_token，暂时无法补查套餐",
            level="WARNING",
            state="skipped",
        )
        return None
    account_task_store.append_event(
        task_id,
        stage="plan_check",
        message="账号缺少成功套餐记录，开始补查套餐",
        state="running",
    )
    try:
        from core.plan_check_service import check_registration_account_plan

        result = check_registration_account_plan(
            account_id=int(account.get("id") or 0),
            email=email,
            access_token=token,
            proxy=(getattr(account_route, "proxy_url", None) if account_route is not None else None),
            trigger=str(trigger or "retry_plan_check"),
        )
        if result.get("ok"):
            account_task_store.append_event(
                task_id,
                stage="plan_check_result",
                message="套餐查询完成",
                detail={
                    "current_plan_type": result.get("current_plan_type"),
                    "plus_trial_eligible": bool(result.get("plus_trial_eligible")),
                },
                state="success",
            )
        else:
            account_task_store.append_event(
                task_id,
                stage="plan_check_result",
                message="套餐查询失败，继续执行其它补跑步骤",
                level="WARNING",
                detail={"error": result.get("error")},
                state="failed",
            )
        return result
    except Exception as exc:
        account_task_store.append_event(
            task_id,
            stage="plan_check_result",
            message="套餐查询异常，继续执行其它补跑步骤",
            level="WARNING",
            detail={"error": f"{type(exc).__name__}: {str(exc)[:180]}"},
            state="failed",
        )
        logger.warning("[补跑][套餐] %s 补查异常：%s: %s", email, type(exc).__name__, str(exc)[:180])
        return None


def _thread_alive(thread_id: int | None) -> bool:
    if not thread_id:
        return False
    try:
        tid = int(thread_id)
    except Exception:
        return False
    return any(getattr(t, "ident", None) == tid and t.is_alive() for t in threading.enumerate())


def _clear_state_locked(key: str) -> None:
    _RETRYING.discard(key)
    _RUNNING_THREADS.pop(key, None)
    _RESERVED_AT.pop(key, None)


def log_path(email: str) -> Path:
    safe = email.replace("/", "_").replace("\\", "_").replace(":", "_")
    return _LOG_DIR / f"codex-retry-{safe}.log"


def reserve(email: str) -> bool:
    """进程内防止同一账号被重复补跑。"""
    key = (email or "").strip().lower()
    if not key:
        return False
    with _RETRYING_LOCK:
        if key in _RETRYING:
            thread_id = _RUNNING_THREADS.get(key)
            alive = _thread_alive(thread_id)
            age = time.time() - float(_RESERVED_AT.get(key) or 0)
            stop_req = key in _STOP_REQUESTED
            try:
                acc = db.get_account_by_email(email)
                status = str((acc or {}).get("codex_status") or "").lower()
            except Exception:
                status = ""
            # 修复“实际已停止/线程已结束，但进程内占位未释放”导致无法再次补跑。
            # 用户点停止后，部分浏览器/短信等待步骤可能不会立刻退出，UI 已是 stopped 但进程占位仍在。
            # 这种场景允许清理占位后重新补跑；旧线程仍保留 stop_requested，会在检查点退出。
            terminal_status = status in {"stopped", "failed", "success", "deactivated", "skipped", "cancelled"}
            if ((not alive) and (status != "retrying" or age > 15 * 60)) or (terminal_status and (stop_req or age > 30)):
                logger.warning(
                    "[Codex 补跑] 清理脏占位：email=%s status=%s thread_id=%s alive=%s stop_requested=%s age=%.1fs",
                    email, status or "-", thread_id or "-", alive, stop_req, age,
                )
                _clear_state_locked(key)
            else:
                return False
        _STOP_REQUESTED.discard(key)
        _RUNNING_THREADS.pop(key, None)
        _RETRYING.add(key)
        _RESERVED_AT[key] = time.time()
        return True


def release(email: str) -> None:
    key = (email or "").strip().lower()
    with _RETRYING_LOCK:
        _clear_state_locked(key)


def is_retrying(email: str) -> bool:
    with _RETRYING_LOCK:
        return (email or "").strip().lower() in _RETRYING


def is_stop_requested(email: str) -> bool:
    with _RETRYING_LOCK:
        return (email or "").strip().lower() in _STOP_REQUESTED


def check_stop_requested(email: str) -> None:
    if is_stop_requested(email):
        raise CodexRetryStopped("用户手动停止 Codex 补跑")


def _build_roxy_twofa_setup(
    email: str,
    task_id: int,
    *,
    proxy: str | None = None,
    access_token: str | None = None,
    twofa_driver: str | None = None,
    browser_fallback_enabled: bool = True,
):
    """为缺少 TOTP 的补跑构造一次性 2FA 前置步骤。"""
    state = {"secret": ""}

    def _setup(driver) -> bool:
        current = db.get_account_by_email(email) or {}
        existing_secret = str(current.get("totp_secret") or state["secret"] or "").strip()
        setup_pending = _totp_setup_pending(current)
        if existing_secret and not setup_pending:
            state["secret"] = existing_secret
            account_task_store.append_event(
                task_id,
                stage="twofa",
                message="账号已有 Authenticator 2FA，跳过重复设置",
                state="skipped",
            )
            logger.info("[Codex 补跑][2FA] 本地已存在 Authenticator key，跳过重复设置：%s", email)
            return False

        check_stop_requested(email)
        account_task_store.append_event(
            task_id,
            stage="twofa",
            message="账号未设置 2FA，开始启用 Authenticator",
            state="running",
        )
        logger.info("[Codex 补跑][2FA] 账号缺少 Authenticator key，开始前置设置：%s", email)

        def _checkpoint(secret: str) -> None:
            normalized = str(secret or "").strip()
            if not normalized:
                raise RuntimeError("Authenticator key 写入账号检查点失败")
            with _ACCOUNT_SETUP_DB_LOCK:
                if not db.update_account_totp_secret(email, normalized, setup_pending=True):
                    raise RuntimeError("Authenticator key 写入账号检查点失败")
            state["secret"] = normalized
            logger.info("[Codex 补跑][2FA] Authenticator key 已在激活前写入账号检查点")

        try:
            from config import twofa as twofa_cfg

            selected_twofa_driver = twofa_cfg.get_twofa_driver(twofa_driver) if twofa_driver else twofa_cfg.get_twofa_driver()
            if selected_twofa_driver == "protocol":
                # Roxy 负责登录和拿到本次新鲜 session；enroll/activate 直接走协议，
                # 若 OpenAI 要求 recent_auth，则复用当前已登录浏览器完成邮箱重认证，
                # 不能让整个账号配置任务直接失败。
                from core.registration.selenium_auth import fetch_chatgpt_session as _fetch_chatgpt_session
                from core.session import BrowserSession

                # 补密码可能触发设置页邮箱重认证，重认证后旧的 ChatGPT AT
                # 可能已经被 OpenAI 作废。这里必须在密码步骤结束后重新从
                # 当前浏览器登录态取一次 Token，不能复用进入设置页前的 AT。
                fresh_access_token = ""
                refreshed_session = None
                try:
                    refreshed_session = _fetch_chatgpt_session(driver, timeout=60, auto_jump_wait=5)
                    fresh_access_token = str((refreshed_session or {}).get("accessToken") or "").strip()
                    if fresh_access_token and fresh_access_token != str(access_token or "").strip():
                        expires_at = str((refreshed_session or {}).get("expires") or "") or None
                        if not db.update_account_session(email, fresh_access_token, expires_at=expires_at):
                            logger.warning("[账号补跑][2FA] 已取得重认证后的 AT，但写回账号失败，继续使用当前会话")
                except Exception as exc:
                    logger.warning(
                        "[账号补跑][2FA] 重认证后刷新 AT 失败，将尝试使用已有 AT：%s: %s",
                        type(exc).__name__, str(exc)[:160],
                    )
                    fresh_access_token = str(access_token or "").strip()
                if not fresh_access_token:
                    raise RuntimeError("协议开通 2FA 未拿到新鲜 accessToken")
                protocol_session = BrowserSession(proxy=proxy)
                if browser_fallback_enabled:
                    from core.registration.selenium_auth import setup_protocol_2fa_with_browser_fallback

                    secret, fallback_used = setup_protocol_2fa_with_browser_fallback(
                        driver,
                        email,
                        protocol_session,
                        fresh_access_token,
                        on_secret=_checkpoint,
                        existing_secret=existing_secret or None,
                    )
                else:
                    from core.account_export import setup_2fa_protocol

                    secret = setup_2fa_protocol(
                        protocol_session,
                        fresh_access_token,
                        on_secret=_checkpoint,
                    )
                    fallback_used = False
                logger.info(
                    "[账号补跑][2FA] 已开通 Authenticator：%s driver=%s",
                    email,
                    "browser_fallback" if fallback_used else "protocol",
                )
            else:
                from core.registration.selenium_auth import setup_roxy_2fa

                secret = setup_roxy_2fa(
                    driver,
                    email,
                    on_secret=_checkpoint,
                    existing_secret=existing_secret or None,
                )
                logger.info("[账号补跑][2FA] 使用 browser 安全设置页开通 Authenticator：%s", email)
            if not state["secret"]:
                _checkpoint(secret)
            with _ACCOUNT_SETUP_DB_LOCK:
                if not db.update_account_totp_secret(email, state["secret"], setup_pending=False):
                    raise RuntimeError("Authenticator 完成状态写入账号失败")
                if not db.update_account_twofa_status(email, "success", "Authenticator 2FA 已启用"):
                    raise RuntimeError("Authenticator 结果状态写入账号失败")
            check_stop_requested(email)
            account_task_store.append_event(
                task_id,
                stage="twofa_result",
                message="Authenticator 2FA 已启用",
                detail={"enabled": True},
                state="success",
            )
            logger.info("[Codex 补跑][2FA] Authenticator 2FA 已启用：%s", email)
            return True
        except CodexRetryStopped:
            raise
        except Exception as exc:
            with _ACCOUNT_SETUP_DB_LOCK:
                db.update_account_twofa_status(
                    email,
                    "failed",
                    f"{type(exc).__name__}: {str(exc)[:220]}",
                )
            account_task_store.append_event(
                task_id,
                stage="twofa_result",
                message="Authenticator 2FA 设置失败，已停止后续账号流程",
                level="ERROR",
                detail={"enabled": False, "error": f"{type(exc).__name__}: {str(exc)[:220]}"},
                state="failed",
            )
            raise RuntimeError(
                f"2FA 设置失败，已停止进入 Codex OAuth：{type(exc).__name__}: {str(exc)[:180]}"
            ) from exc

    return _setup


def _build_roxy_account_setup(
    email: str,
    task_id: int,
    *,
    proxy: str | None = None,
    include_password: bool = True,
    include_twofa: bool = True,
    twofa_driver: str | None = None,
    browser_fallback_enabled: bool = True,
):
    """按步骤补账号密码/Authenticator 2FA；默认保持旧的组合行为。"""

    def _setup(driver, session_info: dict | None = None) -> bool:
        account = db.get_account_by_email(email) or {}
        fresh_access_token = str((session_info or {}).get("accessToken") or "").strip()
        if fresh_access_token:
            if not db.update_account_session(
                email,
                fresh_access_token,
                expires_at=str((session_info or {}).get("expires") or "") or None,
            ):
                raise RuntimeError("重新登录已取得 ChatGPT Token，但写回账号失败")
            account_task_store.append_event(
                task_id,
                stage="token",
                message="重新登录取得的 ChatGPT Token 已写回账号",
                detail={"saved": True},
                state="success",
            )
            account = db.get_account_by_email(email) or account
        account_token = str(account.get("access_token") or "").strip()
        needs_password = bool(include_password and account_token) and not _account_login_password(account)
        needs_twofa = bool(include_twofa) and (
            not bool(str(account.get("totp_secret") or "").strip())
            or _totp_setup_pending(account)
        )
        if not include_password:
            account_task_store.append_event(
                task_id,
                stage="login_password",
                message="本次操作未请求补充账号密码，跳过此步骤",
                state="skipped",
            )
        if not include_twofa:
            account_task_store.append_event(
                task_id,
                stage="twofa",
                message="本次操作未请求补充 Authenticator 2FA，跳过此步骤",
                state="skipped",
            )
        if not needs_password:
            account_task_store.append_event(
                task_id,
                stage="login_password",
                message="账号密码无需补充，跳过此步骤",
                state="skipped",
            )
        if not needs_twofa:
            account_task_store.append_event(
                task_id,
                stage="twofa",
                message="账号已有 Authenticator 2FA，跳过此步骤",
                state="skipped",
            )
        if not needs_password and not needs_twofa:
            return False

        from config import twofa as twofa_cfg
        from core.twofa_flow import canonical_twofa_executor

        selected_twofa_driver = canonical_twofa_executor(
            twofa_driver if twofa_driver is not None else twofa_cfg.get_twofa_driver()
        )
        # 密码补充、浏览器 2FA，以及协议 2FA 失败后的浏览器回退都会共享
        # 同一个 Selenium driver。Selenium driver 不是线程安全的；并发导航
        # 会把页面互相覆盖，常见结果就是只剩本地化的“设置”壳层。
        parallel_setup = False
        protocol_access_token = fresh_access_token or None

        twofa_setup = _build_roxy_twofa_setup(
            email,
            task_id,
            proxy=proxy,
            access_token=protocol_access_token,
            twofa_driver=selected_twofa_driver,
            browser_fallback_enabled=browser_fallback_enabled,
        )

        def _setup_password() -> tuple[bool, str | None]:
            # 没有完整 AT 的历史检查点不能安全判断账号已完成注册，交给
            # 外层登录流程处理；有 AT 但没有密码时才进入“添加密码”流程。
            if not needs_password:
                return False, None
            from core.registration.selenium_auth import registration_password, set_login_password

            password = registration_password()
            password_saved = False

            def _checkpoint_submitted_password(value: str) -> None:
                nonlocal password_saved
                with _ACCOUNT_SETUP_DB_LOCK:
                    if not db.update_account_login_password(email, value, source="retry"):
                        raise RuntimeError("账号密码提交后写入账号检查点失败")
                password_saved = True
                account_task_store.append_event(
                    task_id,
                    stage="login_password",
                    message="账号密码提交后已写入本地检查点，等待页面确认",
                    detail={"saved": True, "checkpoint": "password_submitted"},
                    state="running",
                )

            account_task_store.append_event(
                task_id,
                stage="login_password",
                message="账号缺少账号密码，先在安全设置中补充随机密码",
                state="running",
            )
            try:
                set_login_password(
                    driver,
                    email,
                    password,
                    on_password_submitted=_checkpoint_submitted_password,
                )
                if not password_saved:
                    _checkpoint_submitted_password(password)
            except CodexRetryStopped:
                raise
            except PasswordSetupUnsupportedError as exc:
                db.update_account_password_capability(
                    email,
                    eligible=False,
                    reason="remote_not_eligible",
                )
                account_task_store.append_event(
                    task_id,
                    stage="login_password_result",
                    message="ChatGPT 当前不支持添加账号密码，跳过重复重试",
                    level="WARNING",
                    detail={"eligible": False, "reason": "remote_not_eligible"},
                    state="skipped",
                )
                raise
            except Exception as exc:
                account_task_store.append_event(
                    task_id,
                    stage="login_password_result",
                    message="账号密码补充失败，停止后续账号配置",
                    level="ERROR",
                    detail={"error": f"{type(exc).__name__}: {str(exc)[:220]}"},
                    state="failed",
                )
                return False, f"{type(exc).__name__}: {str(exc)[:180]}"
            account_task_store.append_event(
                task_id,
                stage="login_password_result",
                message="账号密码已补充并保存",
                detail={"saved": True},
                state="success",
            )
            return True, None

        def _setup_twofa() -> tuple[bool, str | None]:
            if not needs_twofa:
                return False, None
            return bool(twofa_setup(driver)), None

        changed = False
        errors: list[str] = []
        unsupported_errors: list[str] = []

        def _collect(label: str, future_or_result) -> None:
            nonlocal changed
            try:
                if hasattr(future_or_result, "result"):
                    step_changed, error = future_or_result.result()
                else:
                    step_changed, error = future_or_result
            except CodexRetryStopped:
                raise
            except PasswordSetupUnsupportedError as exc:
                step_changed, error = False, f"{type(exc).__name__}: {str(exc)[:180]}"
                unsupported_errors.append(error)
            except Exception as exc:
                step_changed, error = False, f"{type(exc).__name__}: {str(exc)[:180]}"
            changed = changed or bool(step_changed)
            if error:
                errors.append(f"{label}：{error}")

        account_task_store.append_event(
            task_id,
            stage="account_setup",
            message="账号密码与 Authenticator 2FA 串行执行，避免覆盖同一浏览器会话",
            detail={"parallel": False, "twofa_driver": selected_twofa_driver},
        )
        _collect("账号密码", _setup_password())
        _collect("Authenticator 2FA", _setup_twofa())

        if errors:
            account_task_store.append_event(
                task_id,
                stage="account_setup_result",
                message="账号配置部分完成，存在失败步骤，可重跑补齐",
                level="ERROR",
                detail={"errors": errors, "parallel": parallel_setup},
            )
            if unsupported_errors:
                raise PasswordSetupUnsupportedError("；".join(errors))
            raise RuntimeError("账号配置部分失败：" + "；".join(errors))
        return changed

    return _setup


def request_stop(email: str) -> dict:
    """兼容入口：原生 Codex run 使用数据库取消令牌；旧账号配置任务只置停止位。"""
    from core import codex_operation_service

    native = codex_operation_service.request_cancel(email=email)
    if native.get("run_id") or native.get("state") != "empty":
        return native
    key = (email or "").strip().lower()
    if not key:
        return {"ok": False, "error": "email 为空", "status": 400}
    with _RETRYING_LOCK:
        retrying = key in _RETRYING
        thread_id = _RUNNING_THREADS.get(key)
        _STOP_REQUESTED.add(key)
    if not retrying:
        db.update_account_codex_status(email, "stopped", "用户手动停止（未发现运行中的补跑）")
        return {"ok": True, "message": "未发现运行中的补跑，已标记为已停止", "state": "stopped", "running": False}

    db.update_account_codex_status(email, "stopped", "用户手动停止 Codex 补跑")
    with _RETRYING_LOCK:
        if not _thread_alive(thread_id):
            _clear_state_locked(key)
    try:
        p = log_path(email)
        p.parent.mkdir(parents=True, exist_ok=True)
        task_run_log.append(
            p,
            level="WARNING",
            message="用户手动停止，已记录协作式停止信号",
            stage="cancelling",
            event_type="run.cancel_requested",
        )
    except Exception:
        logger.exception("写入 Codex 停止日志失败")
    return {"ok": True, "message": "已记录停止请求，将在安全检查点退出", "state": "cancelling", "running": True}


def run_twofa_worker(
    email: str,
    *,
    clear_log: bool = True,
    target_log_path: str | Path | None = None,
    task_id: int | None = None,
    task_trigger: str = "manual",
    steps: set[str] | tuple[str, ...] | list[str] | None = None,
    manage_task: bool = True,
    twofa_driver_override: str | None = None,
    password_driver_override: str | None = None,
    plan_driver_override: str | None = None,
) -> dict:
    """重新登录并执行指定账号配置步骤，不重复执行 Codex OAuth。

    ``steps`` 为空时兼容历史行为：执行 password + plan_check + twofa。
    ``manage_task=False`` 用于“补全账号”协调器复用同一个父任务生命周期。
    """
    fh: logging.Handler | None = None
    root_logger = logging.getLogger()
    result: dict = {"status": "failed", "ok": False, "message": "账号配置重试未返回结果"}
    account_route = None
    route_summary: dict = {}
    browser_stage_started = False
    browser_stage_finished = False
    key = (email or "").strip().lower()
    requested_steps = {"password", "plan_check", "twofa"} if steps is None else {
        str(item or "").strip().lower() for item in steps
    }
    requested_steps &= {"password", "plan_check", "twofa"}
    if not requested_steps:
        return {"status": "success", "ok": True, "message": "没有需要执行的账号配置步骤"}
    setup_labels = [
        label for key_name, label in (
            ("password", "账号密码"), ("plan_check", "套餐"), ("twofa", "Authenticator 2FA"),
        ) if key_name in requested_steps
    ]
    setup_message = "、".join(setup_labels) + "已补齐或确认"
    try:
        account = db.get_account_by_email(email) or {}
        if task_id is None:
            task_id = account_task_store.create_task(
                task_type=("password_setup" if requested_steps == {"password"} else "twofa_retry"),
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(task_trigger or "manual"),
            )
        with _RETRYING_LOCK:
            _RUNNING_THREADS[key] = threading.get_ident()
            _RESERVED_AT[key] = time.time()
        check_stop_requested(email)
        if manage_task:
            account_task_store.start_task(task_id, message=f"开始处理{ '、'.join(setup_labels) }")

        task_row = account_task_store.get_task(task_id) or {}
        path = Path(target_log_path) if target_log_path else Path(task_row.get("log_file") or log_path(email))
        path.parent.mkdir(parents=True, exist_ok=True)
        if clear_log:
            path.write_text("", encoding="utf-8")
        thread_name = threading.current_thread().name
        fh = task_run_log.TaskRunLogHandler(str(path), task_id=task_id, stage="account_setup")
        fh.setLevel(logging.DEBUG)
        fh.addFilter(lambda record: record.threadName == thread_name)
        root_logger.addHandler(fh)

        import config as config_pkg

        config_pkg.reload_all()
        from config import account as account_cfg
        from core.twofa_flow import normalize_twofa_mode, plan_twofa_context

        password_driver = str(
            password_driver_override
            if password_driver_override is not None
            else getattr(account_cfg, "ACCOUNT_PASSWORD_DRIVER", "roxy")
        ).strip().lower()
        plan_driver = str(
            plan_driver_override
            if plan_driver_override is not None
            else getattr(account_cfg, "ACCOUNT_PLAN_CHECK_DRIVER", "protocol")
        ).strip().lower()
        if "password" in requested_steps and password_driver not in {"roxy", "roxybrowser", "browser"}:
            raise RuntimeError(f"账号密码补全当前仅支持 roxy 驱动，当前驱动={password_driver or '-'}")
        if "plan_check" in requested_steps and plan_driver not in {"protocol", "api", "http"}:
            raise RuntimeError(f"套餐补全当前仅支持 protocol 驱动，当前驱动={plan_driver or '-'}")
        if "twofa" in requested_steps:
            selected_twofa_mode = normalize_twofa_mode(str(
                twofa_driver_override
                if twofa_driver_override is not None
                else getattr(account_cfg, "ACCOUNT_2FA_DRIVER", "auto")
            ).strip().lower())
        else:
            selected_twofa_mode = "auto"
        browser_fallback_enabled = bool(
            getattr(account_cfg, "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", True)
        )
        protocol_reauth_enabled = bool(
            getattr(account_cfg, "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED", True)
        )

        # 账号密码和显式 browser 2FA 需要浏览器会话；这和 Codex OAuth
        # 的驱动是两个独立边界，不能拿 CODEX_OAUTH_DRIVER 误拦截账号配置。
        browser_session_required = "password" in requested_steps or (
            "twofa" in requested_steps and selected_twofa_mode == "browser"
        )

        from core.account_proxy import acquire_account_proxy

        account_route = acquire_account_proxy(
            account_id=int(account.get("id") or 0) or None,
            email=email,
            purpose="twofa-retry",
        )
        route_summary = account_route.public_dict()
        account_task_store.append_event(
            task_id,
            stage="network",
            message="已分配账号配置重试线路",
            detail={
                "network_route": route_summary.get("network_route"),
                "proxy_mode": account_route.mode,
                "proxy_provider": account_route.provider,
                "proxy_region": account_route.region,
            },
            state="success",
        )
        plan_result = None
        if "plan_check" in requested_steps:
            plan_result = _run_retry_plan_check(
                email,
                account,
                account_route,
                task_id,
                trigger=str(task_trigger or "manual") + "_plan_check",
            )
        if requested_steps == {"plan_check"}:
            result = {
                "status": "success" if plan_result and plan_result.get("ok") else "failed",
                "ok": bool(plan_result and plan_result.get("ok")),
                "message": "套餐已补查并确认" if plan_result and plan_result.get("ok") else "套餐补查未完成",
                "proxy_provider": account_route.provider,
                "proxy_region": account_route.region,
                "proxy_mode": account_route.mode,
            }
            return result

        context_plan = plan_twofa_context(
            selected_twofa_mode,
            has_access_token=bool(str(account.get("access_token") or "").strip()),
            browser_session_required=browser_session_required,
        )
        browser_twofa_driver = context_plan.executor
        direct_protocol_failed = False
        if requested_steps == {"twofa"} and context_plan.executor == "protocol":
            try:
                direct_result = _run_protocol_direct_twofa(
                    email,
                    account,
                    account_route,
                    task_id,
                    protocol_reauth_enabled=protocol_reauth_enabled,
                )
            except CodexRetryStopped:
                raise
            except Exception as exc:
                direct_protocol_failed = True
                direct_error = f"{type(exc).__name__}: {str(exc)[:220]}"
                account_task_store.append_event(
                    task_id,
                    stage="twofa_result",
                    message="协议 2FA 开通失败",
                    level="WARNING",
                    detail={
                        "driver": "protocol",
                        "auth_source": context_plan.auth_source,
                        "browser_fallback_enabled": browser_fallback_enabled,
                        "protocol_reauth_enabled": protocol_reauth_enabled,
                        "error": direct_error,
                    },
                    state="failed",
                )
                if not browser_fallback_enabled or not _should_browser_fallback_after_protocol_error(exc):
                    db.update_account_twofa_status(email, "failed", direct_error)
                    if browser_fallback_enabled:
                        message = "邮箱收件链路失败，跳过浏览器兜底，避免重复等待验证码"
                    else:
                        message = "协议 2FA 失败，且已关闭浏览器兜底"
                    result = {
                        "status": "failed",
                        "ok": False,
                        "message": f"{message}：{direct_error}",
                        "twofa_driver": "protocol",
                        "auth_source": context_plan.auth_source,
                        "browser_opened": False,
                        "proxy_provider": account_route.provider,
                        "proxy_region": account_route.region,
                        "proxy_mode": account_route.mode,
                    }
                    return result
                account_task_store.append_event(
                    task_id,
                    stage="twofa",
                    message="协议 2FA 未完成，按配置回退 Roxy 安全设置页面",
                    detail={
                        "driver": "browser_fallback",
                        "auth_source": "browser_session",
                        "protocol_error": direct_error,
                    },
                    state="running",
                )
                browser_twofa_driver = "browser"
            else:
                result = {
                    **direct_result,
                    "plan_check": {"status": "skipped", "ok": True, "message": "本次未请求套餐补全"},
                    "proxy_provider": account_route.provider,
                    "proxy_region": account_route.region,
                    "proxy_mode": account_route.mode,
                }
                return result
        account_task_store.append_event(
            task_id,
            stage="browser",
            message=f"重新登录 ChatGPT，处理{ '、'.join(label for label in setup_labels if label != '套餐') }",
            state="running",
        )
        browser_stage_started = True
        from core.roxy_codex_oauth import run_roxy_chatgpt_account_action

        def _report_browser_login_stage(**event) -> None:
            account_task_store.append_event(
                task_id,
                stage=str(event.get("stage") or "browser"),
                message=str(event.get("message") or "浏览器登录处理中"),
                level=str(event.get("level") or "INFO"),
                detail=dict(event.get("detail") or {}),
                state=str(event.get("state") or "running"),
            )

        run_roxy_chatgpt_account_action(
            email,
            proxy=account_route.proxy_url,
            stage_reporter=_report_browser_login_stage,
            action=_build_roxy_account_setup(
                email,
                task_id,
                proxy=(account_route.proxy_url if account_route is not None else None),
                include_password="password" in requested_steps,
                include_twofa="twofa" in requested_steps,
                twofa_driver=browser_twofa_driver,
                browser_fallback_enabled=browser_fallback_enabled,
            ),
        )
        account_task_store.append_event(
            task_id,
            stage="browser",
            message="ChatGPT 重新登录与账号配置检查已完成",
            state="success",
        )
        browser_stage_finished = True
        check_stop_requested(email)
        result = {
            "status": "success",
            "ok": True,
            "message": setup_message,
            "plan_check": (
                {
                    "status": str(plan_result.get("status") or "failed"),
                    "ok": bool(plan_result.get("ok")),
                    "message": plan_result.get("message"),
                }
                if "plan_check" in requested_steps and isinstance(plan_result, dict)
                else {"status": "skipped", "ok": True, "message": "本次未请求套餐补全"}
            ),
            "proxy_provider": account_route.provider,
            "proxy_region": account_route.region,
            "proxy_mode": account_route.mode,
            "twofa_driver": "browser_fallback" if direct_protocol_failed else context_plan.executor,
            "auth_source": "browser_session" if direct_protocol_failed else context_plan.auth_source,
            "browser_opened": True,
        }
        return result
    except CodexRetryStopped as exc:
        if browser_stage_started and not browser_stage_finished:
            account_task_store.append_event(
                task_id,
                stage="browser",
                message="ChatGPT 重新登录流程已被用户停止",
                level="ERROR",
                state="failed",
            )
        result = {"status": "stopped", "ok": False, "message": str(exc) or "用户手动停止账号配置重试"}
        return result
    except Exception as exc:
        unsupported = isinstance(exc, PasswordSetupUnsupportedError)
        if browser_stage_started and not browser_stage_finished and not unsupported:
            account_task_store.append_event(
                task_id,
                stage="browser",
                message="ChatGPT 重新登录与账号配置检查失败",
                level="ERROR",
                detail={"error": f"{type(exc).__name__}: {str(exc)[:220]}"},
                state="failed",
            )
        deactivated = isinstance(exc, AccountUnusableError)
        deactivated_persisted = False
        error_code = str(
            getattr(exc, "code", "") or getattr(exc, "error_code", "") or ""
        ).strip() or None
        if deactivated:
            deactivated_persisted = _persist_account_deactivated(email, exc)
            error_code = error_code or "account_deactivated"
            account_task_store.append_event(
                task_id,
                stage="account_status",
                message=(
                    "已确认账号废号并写回账号状态"
                    if deactivated_persisted
                    else "已确认账号废号，但账号状态写回失败"
                ),
                level="INFO" if deactivated_persisted else "ERROR",
                detail={
                    "status": "deactivated",
                    "reason": error_code,
                    "persisted": deactivated_persisted,
                },
                state="success" if deactivated_persisted else "failed",
            )
        result = {
            "status": "deactivated" if deactivated else "unsupported" if unsupported else "failed",
            "ok": False,
            "message": f"{type(exc).__name__}: {exc}",
            "error_code": error_code,
            "account_status_persisted": deactivated_persisted if deactivated else None,
        }
        logger.exception("[账号配置重试] %s 异常", email)
        return result
    finally:
        _attach_auth_projection(
            result,
            auth_method=str(
                result.get("auth_method")
                or result.get("twofa_driver")
                or ("roxy" if result.get("browser_opened") else "protocol")
            ),
        )
        if fh is not None:
            try:
                root_logger.removeHandler(fh)
                fh.close()
            except Exception:
                pass
        if account_route is not None:
            account_route.release(reason=f"twofa-retry-{email}")
        # “补全账号”把多个独立步骤串在同一个父任务里；子步骤结束后
        # 仍需保留父任务的账号租约，避免 Codex 入队前被其它操作插入。
        if manage_task:
            release(email)
        with _RETRYING_LOCK:
            if key:
                _STOP_REQUESTED.discard(key)
        task_status = (
            "success" if result.get("ok")
            else "unsupported" if result.get("status") == "unsupported"
            else "cancelled" if result.get("status") == "stopped"
            else "failed"
        )
        try:
            if manage_task:
                account_task_store.finish_task(
                    task_id,
                    status=task_status,
                    message=(
                        setup_message
                        if task_status == "success"
                        else "账号配置重试已停止" if task_status == "cancelled" else "账号配置重试失败"
                    ),
                    error=None if task_status == "success" else str(result.get("message") or "账号配置重试失败"),
                    result_summary={
                        "ok": bool(result.get("ok")),
                        "status": result.get("status"),
                        "message": result.get("message"),
                        "plan_check": result.get("plan_check"),
                        "twofa_driver": result.get("twofa_driver"),
                        "auth_source": result.get("auth_source"),
                        "browser_opened": result.get("browser_opened"),
                    },
                    route={
                        "network_route": route_summary.get("network_route"),
                        "proxy_mode": result.get("proxy_mode") or getattr(account_route, "mode", None),
                        "proxy_provider": result.get("proxy_provider") or getattr(account_route, "provider", None),
                        "proxy_region": result.get("proxy_region") or getattr(account_route, "region", None),
                        "proxy_used": route_summary.get("proxy_used"),
                    },
                    validation_method="chatgpt_account_setup",
                )
        except Exception:
            logger.exception("[账号配置重试] 写入任务实例失败：task_id=%s email=%s", task_id or "-", email)


def _run_worker_legacy(
    email: str,
    *,
    batch_label: str | None = None,
    clear_log: bool = True,
    target_log_path: str | Path | None = None,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> dict:
    """执行一次 Codex 补跑，并把脱敏后的关键阶段写入统一任务实例。"""
    fh: logging.Handler | None = None
    root_logger = logging.getLogger()
    result: dict = {"status": "failed", "ok": False, "message": "Codex 补跑未返回结果"}
    account_route = None
    route_summary: dict = {}
    oauth_driver = ""
    key = (email or "").strip().lower()
    sms_batch_bound = False
    if batch_label:
        from core import sms_provider

        # WebUI 会在同一批次标签后追加“#序号/总数”；去掉序号后共享一次选国结果。
        sms_provider.set_sms_batch_context(f"codex-retry:{batch_label.split(' #', 1)[0]}")
        sms_batch_bound = True
    try:
        if task_id is None:
            account = db.get_account_by_email(email) or {}
            task_id = account_task_store.create_task(
                task_type="codex_retry",
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(task_trigger or "manual"),
            )
        with _RETRYING_LOCK:
            _RUNNING_THREADS[key] = threading.get_ident()
            _RESERVED_AT[key] = time.time()
        check_stop_requested(email)

        account_task_store.start_task(task_id, message="开始补跑 Codex OAuth 授权")

        from core.codex_oauth import run_codex_oauth

        task_row = account_task_store.get_task(task_id) or {}
        path = Path(target_log_path) if target_log_path else Path(task_row.get("log_file") or log_path(email))
        path.parent.mkdir(parents=True, exist_ok=True)
        if clear_log:
            path.write_text("", encoding="utf-8")

        thread_name = threading.current_thread().name
        fh = task_run_log.TaskRunLogHandler(str(path), task_id=task_id, stage="codex")
        fh.setLevel(logging.DEBUG)
        fh.addFilter(lambda record: record.threadName == thread_name)
        root_logger.addHandler(fh)

        try:
            import config as config_pkg
            config_pkg.reload_all()
            from config import codex as codex_cfg
            from config import roxybrowser as roxy_cfg
            logger.info(
                "[Codex 补跑] 已热加载配置：CODEX_OAUTH_DRIVER=%s ROXY_OPEN_HEADLESS=%s ROXY_KEEP_BROWSER_OPEN=%s",
                getattr(codex_cfg, "CODEX_OAUTH_DRIVER", ""),
                getattr(roxy_cfg, "ROXY_OPEN_HEADLESS", ""),
                getattr(roxy_cfg, "ROXY_KEEP_BROWSER_OPEN", ""),
            )
        except Exception as exc:
            logger.warning("[Codex 补跑] 配置热加载失败，将继续使用当前内存配置：%s: %s", type(exc).__name__, exc)

        if batch_label:
            logger.info("[Codex 补跑] 批量任务：%s", batch_label)
        logger.info("[Codex 补跑] 开始：%s", email)
        logger.info(
            "[Codex 补跑] 阶段说明：获取授权地址 → 登录邮箱 → 邮箱 OTP → "
            "缺失时先补账号密码/套餐/2FA → 手机验证 → 捕获 callback → 提交/保存凭证"
        )
        check_stop_requested(email)
        from config import codex as codex_cfg
        from config import roxybrowser as roxy_cfg
        oauth_driver = str(getattr(codex_cfg, "CODEX_OAUTH_DRIVER", "protocol") or "protocol").strip().lower()
        if oauth_driver == "same_as_registration":
            oauth_driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
        account_task_store.append_event(
            task_id,
            stage="driver",
            message=f"使用 {oauth_driver or 'protocol'} 驱动执行 Codex OAuth",
            detail={"oauth_driver": oauth_driver or "protocol"},
            state="success",
        )
        from core.account_proxy import acquire_account_proxy
        account = db.get_account_by_email(email) or {}
        account_route = acquire_account_proxy(
            account_id=int(account.get("id") or 0) or None,
            email=email,
            purpose="codex-oauth",
        )
        route_summary = account_route.public_dict()
        logger.info(
            "[Codex 补跑] 账号网络：provider=%s region=%s route=%s proxy=%s",
            account_route.provider,
            account_route.region or "-",
            account_route.public_dict().get("network_route"),
            account_route.public_dict().get("proxy_used") or "-",
        )
        account_task_store.append_event(
            task_id,
            stage="network",
            message="已分配账号补跑线路",
            detail={
                "network_route": route_summary.get("network_route"),
                "proxy_mode": account_route.mode,
                "proxy_provider": account_route.provider,
                "proxy_region": account_route.region,
                "proxy_used": route_summary.get("proxy_used"),
            },
            state="success",
        )
        account = db.get_account_by_email(email) or {}
        _run_retry_plan_check(
            email,
            account,
            account_route,
            task_id,
            trigger=str(task_trigger or "manual") + "_plan_check",
        )
        needs_twofa = (
            not bool(str(account.get("totp_secret") or "").strip())
            or _totp_setup_pending(account)
        )
        needs_login_password = bool(str(account.get("access_token") or "").strip()) and not _account_login_password(account)
        needs_roxy_setup = needs_twofa or needs_login_password
        account_task_store.append_event(
            task_id,
            stage="oauth",
            message=(
                "账号缺少账号密码/2FA，将先补齐账号配置再完成 OAuth"
                if needs_roxy_setup and oauth_driver in {"roxy", "roxybrowser", "fingerprint", "browser"}
                else "开始获取授权地址并完成邮箱、短信与 callback 流程"
            ),
            state="running",
        )
        if needs_roxy_setup and oauth_driver in {"roxy", "roxybrowser", "fingerprint", "browser"}:
            from core.roxy_codex_oauth import run_roxy_codex_oauth

            result = run_roxy_codex_oauth(
                email,
                proxy=(account_route.proxy_url if account_route is not None else None),
                force=True,
                before_oauth_setup=_build_roxy_account_setup(
                    email,
                    task_id,
                    proxy=(account_route.proxy_url if account_route is not None else None),
                ),
            )
        else:
            result = run_codex_oauth(
                email,
                proxy=(account_route.proxy_url if account_route is not None else None),
                force=True,
            )
        if account_route is not None:
            # 标准任务页需要展示补跑实际使用的平台/地区；只写公开元数据，绝不落代理凭据。
            result["proxy_provider"] = account_route.provider
            result["proxy_region"] = account_route.region
            result["proxy_mode"] = account_route.mode
        check_stop_requested(email)
        logger.info(
            "[Codex 补跑] 结果：status=%s ok=%s file=%s callback=%s",
            result.get("status"), result.get("ok"), result.get("file_path"), result.get("callback_url"),
        )
        account_task_store.append_event(
            task_id,
            stage="oauth_result",
            message="Codex OAuth 已返回成功结果" if result.get("ok") else "Codex OAuth 返回失败结果",
            level="INFO" if result.get("ok") else "ERROR",
            detail={
                "ok": bool(result.get("ok")),
                "status": result.get("status"),
                "message": result.get("message"),
                "credential_saved": bool(result.get("file_path")),
            },
            state="success" if result.get("ok") else "failed",
        )
        result_status = result.get("status", "failed")
        if result.get("ok"):
            db.update_account_codex_status(email, "success", None)
            logger.info("[Codex 补跑] %s 成功", email)
        elif result_status == "deactivated":
            db.update_account_codex_status(email, "deactivated", result.get("message"))
            logger.warning("[Codex 补跑] %s 账号已废: %s", email, result.get("message"))
        else:
            db.update_account_codex_status(email, result_status, result.get("message"))
            logger.warning("[Codex 补跑] %s 失败: %s", email, result.get("message"))
        return result
    except CodexRetryStopped as exc:
        result = {"status": "stopped", "ok": False, "message": str(exc) or "用户手动停止 Codex 补跑"}
        db.update_account_codex_status(email, "stopped", result["message"])
        logger.warning("[Codex 补跑] %s 已停止: %s", email, result["message"])
        return result
    except Exception as exc:
        if is_stop_requested(email):
            result = {"status": "stopped", "ok": False, "message": "用户手动停止 Codex 补跑"}
            db.update_account_codex_status(email, "stopped", result["message"])
            logger.warning("[Codex 补跑] %s 已停止", email)
            return result
        result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}
        db.update_account_codex_status(email, "failed", result["message"])
        logger.exception("[Codex 补跑] %s 异常", email)
        logger.error("[Codex 补跑] 已结束：异常失败")
        return result
    finally:
        try:
            logger.info("[Codex 补跑] 结束：%s", email)
            if fh is not None:
                root_logger.removeHandler(fh)
                fh.close()
        finally:
            if account_route is not None:
                account_route.release(reason=f"codex-oauth-{email}")
            release(email)
            with _RETRYING_LOCK:
                if key:
                    _STOP_REQUESTED.discard(key)
            result_status = str(result.get("status") or "failed").lower()
            task_status = (
                "success" if result.get("ok")
                else "deactivated" if result_status == "deactivated"
                else "cancelled" if result_status in {"stopped", "cancelled"}
                else "failed"
            )
            route = {
                "network_route": route_summary.get("network_route"),
                "proxy_mode": result.get("proxy_mode") or getattr(account_route, "mode", None),
                "proxy_provider": result.get("proxy_provider") or getattr(account_route, "provider", None),
                "proxy_region": result.get("proxy_region") or getattr(account_route, "region", None),
                "proxy_used": route_summary.get("proxy_used"),
            }
            try:
                account_task_store.finish_task(
                    task_id,
                    status=task_status,
                    message=(
                        "Codex 补跑成功" if task_status == "success"
                        else "Codex 补跑已停止" if task_status == "cancelled"
                        else "账号已停用" if task_status == "deactivated"
                        else "Codex 补跑失败"
                    ),
                    error=None if task_status == "success" else str(result.get("message") or "Codex 补跑失败"),
                    result_summary={
                        "ok": bool(result.get("ok")),
                        "status": result_status,
                        "message": result.get("message"),
                        "credential_saved": bool(result.get("file_path")),
                        "oauth_driver": oauth_driver or None,
                    },
                    route=route,
                    validation_method=f"codex_oauth:{oauth_driver or 'unknown'}",
                )
            except Exception:
                logger.exception("[Codex 补跑] 写入任务实例失败：task_id=%s email=%s", task_id or "-", email)
            if sms_batch_bound:
                from core import sms_provider

                sms_provider.clear_sms_batch_context()


def run_worker(
    email: str,
    *,
    batch_label: str | None = None,
    clear_log: bool = True,
    target_log_path: str | Path | None = None,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> dict:
    """旧同步入口的兼容委托；业务执行统一由 Codex operation 协调器完成。"""
    from core import codex_operation_service, operation_task_store

    queued = codex_operation_service.submit(email, trigger=task_trigger)
    if not queued.get("accepted"):
        if queued.get("busy") and queued.get("run_id"):
            run_id = int(queued["run_id"])
        else:
            return {
                "status": "failed",
                "ok": False,
                "message": str(queued.get("error") or "Codex operation 入队失败"),
            }
    else:
        run_id = int(queued["run_id"])
    try:
        while True:
            run = operation_task_store.get_run(run_id) or {}
            status = str(run.get("status") or "")
            if status not in {"queued", "running", "cancelling", "settling"}:
                summary = run.get("result_summary") or {}
                return {
                    **summary,
                    "status": status or "failed",
                    "ok": status == "success",
                    "message": run.get("error_message") or summary.get("message") or status,
                }
            time.sleep(0.25)
    finally:
        # 兼容调用方可能在调用前执行过旧 reserve；它不再参与 Codex 并发事实。
        release(email)
