# -*- coding: utf-8 -*-
"""使用 Roxy 指纹浏览器为已注册账号刷新 ChatGPT accessToken。

该流程只允许进入“已有账号登录 → 邮箱 OTP”；一旦识别为新账号密码/资料页会
立即停止，避免查活意外创建账号。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from config import roxybrowser as cfg
from core.email_provider import wait_for_otp
from core.openai_auth import AccountUnusableError, detect_account_unusable_text
from core.roxy_registration import (
    _build_driver,
    _center_browser_window,
    _clear_otp_inputs,
    _click_continue,
    _click_passwordless_signup_if_present,
    _click_resend_email_otp,
    _fetch_chatgpt_session,
    _has_access_token,
    _is_email_verification_page,
    _is_login_password_page,
    _maybe_accept,
    _page_warmup,
    _safe_get,
    _submit_email_step,
    _submit_email_via_browser_nextauth,
    _type_email_address,
    _type_otp,
    _wait_after_email_otp_submit,
    _wait_email_submit_next_state,
)
from core.roxybrowser_client import RoxyBrowserClient

logger = logging.getLogger(__name__)


def available() -> bool:
    driver = str(getattr(cfg, "REGISTRATION_DRIVER", "") or "").strip().lower()
    return (
        driver in {"roxy", "roxybrowser", "fingerprint", "browser"}
        and bool(str(getattr(cfg, "ROXY_API_BASE", "") or "").strip())
        and bool(str(getattr(cfg, "ROXY_API_TOKEN", "") or "").strip())
        and bool(str(getattr(cfg, "ROXY_WORKSPACE_ID", "") or "").strip())
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _enter_existing_account_otp(driver, email: str) -> str:
    """提交邮箱并进入已有账号 OTP；返回 otp/logged_in。"""
    _type_email_address(driver, email, timeout=25)
    _submit_email_step(driver, email)
    state = _wait_email_submit_next_state(driver, email, timeout=30)
    if state in {"blank_shell", "email_page", "email_cleared", "unknown"}:
        fallback = _submit_email_via_browser_nextauth(driver, email)
        state = str(fallback.get("state") or "")
        if not state:
            state = _wait_email_submit_next_state(
                driver,
                email,
                timeout=35,
                wait_through_transient=True,
            )
        if not fallback.get("ok") and state not in {"otp", "password", "login_password", "logged_in"}:
            raise RuntimeError(f"浏览器 NextAuth 登录导航失败: {fallback}")
    if state == "logged_in" or _has_access_token(driver):
        return "logged_in"
    if state == "password" and not _is_login_password_page(driver):
        raise RuntimeError("邮箱进入新账号创建密码页，查活已停止，未创建账号")
    if state == "login_password" or _is_login_password_page(driver):
        passwordless = _click_passwordless_signup_if_present(driver)
        if not passwordless.get("ok"):
            raise RuntimeError(f"已有账号登录页没有可用的邮箱一次性验证码入口: {passwordless}")
        end = time.time() + 30
        while time.time() < end:
            if _is_email_verification_page(driver):
                return "otp"
            if _has_access_token(driver):
                return "logged_in"
            time.sleep(0.5)
        raise RuntimeError("点击一次性验证码登录后未进入验证码页")
    if state == "otp" or _is_email_verification_page(driver):
        return "otp"
    raise RuntimeError(f"浏览器登录未进入已有账号 OTP，最后状态={state}")


def _complete_otp(driver, email: str, after_ts: float) -> None:
    current_otp = None
    for attempt in range(1, 4):
        if current_otp is None:
            current_otp = wait_for_otp(email, after_ts=after_ts)
        _clear_otp_inputs(driver)
        _type_otp(driver, current_otp)
        try:
            _click_continue(driver)
        except Exception:
            pass
        if _wait_after_email_otp_submit(driver, timeout=35) == "accepted":
            return
        if attempt >= 3:
            break
        after_ts = time.time()
        _click_resend_email_otp(driver, timeout=25)
        current_otp = None
    raise RuntimeError("邮箱验证码连续错误/过期，已达到最大重试次数")


def refresh_access_token(email: str, *, proxy: str | None = None) -> dict:
    """在一次性 Roxy 环境中登录已有账号并返回刷新后的 Session/AT。"""
    checked_at = _now()
    if not available():
        return {"ok": False, "status": "failed", "checked_at": checked_at, "error": "Roxy 浏览器兜底未配置"}
    client = RoxyBrowserClient()
    opened = None
    driver = None
    try:
        logger.info("[查活][Roxy] 协议登录未通过，创建指纹浏览器环境：%s", email)
        opened = client.open_profile(proxy_url=proxy)
        driver = _build_driver(opened)
        _center_browser_window(driver)
        driver.set_page_load_timeout(int(getattr(cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90))
        try:
            driver.set_script_timeout(15)
        except Exception:
            pass
        _safe_get(
            driver,
            "https://chatgpt.com/auth/login",
            timeout=min(50, int(getattr(cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
            attempts=2,
            accept_hosts=("chatgpt.com", "auth.openai.com"),
        )
        _page_warmup(driver, reason="live_check_login")
        _maybe_accept(driver)
        otp_after_ts = time.time()
        state = _enter_existing_account_otp(driver, email)
        if state == "otp":
            _complete_otp(driver, email, otp_after_ts)
        session_info = _fetch_chatgpt_session(driver, timeout=120)
        access_token = str(session_info.get("accessToken") or "").strip()
        if not access_token:
            raise RuntimeError("Roxy 登录完成但未拿到 accessToken")
        return {
            "ok": True,
            "status": "live",
            "checked_at": checked_at,
            "access_token": access_token,
            "session": session_info,
            "proxy_used": proxy or None,
            "validation_method": "roxy_email_otp",
        }
    except AccountUnusableError as exc:
        code = getattr(exc, "error_code", "") or detect_account_unusable_text(str(exc)) or "account_deactivated"
        return {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": code, "validation_method": "roxy_email_otp"}
    except Exception as exc:
        code = detect_account_unusable_text(str(exc))
        if code:
            return {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": code, "validation_method": "roxy_email_otp"}
        logger.warning("[查活][Roxy] 失败：%s: %s", type(exc).__name__, str(exc)[:260])
        return {
            "ok": False,
            "status": "failed",
            "checked_at": checked_at,
            "error": f"Roxy {type(exc).__name__}: {str(exc)[:500]}",
            "validation_method": "roxy_email_otp",
        }
    finally:
        if driver is not None and not bool(getattr(cfg, "ROXY_KEEP_BROWSER_OPEN", False)):
            try:
                driver.quit()
            except Exception:
                pass
        if opened is not None and not bool(getattr(cfg, "ROXY_KEEP_BROWSER_OPEN", False)):
            try:
                client.cleanup_profile(opened)
            except Exception:
                logger.exception("[查活][Roxy] 清理临时环境失败：profile=%s", getattr(opened, "profile_id", "-"))
