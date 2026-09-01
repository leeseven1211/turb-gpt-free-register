#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受控验证 Roxy 登录、邮箱 OTP、TOTP 和 session 接口。

默认只读到登录页面；真实凭据和验证码步骤必须分别显式传入开关。
输出只包含账号 ID、URL path、控件技术属性、HTTP 状态和脱敏错误码。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import queue
import re
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import websocket

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config import roxybrowser as roxy_cfg  # noqa: E402
from core import db  # noqa: E402
from core.account_proxy import acquire_account_proxy  # noqa: E402
from core.email_provider import wait_for_otp  # noqa: E402
from core.proxy_provider import active_proxy_leases  # noqa: E402
from core.registration.selenium_auth import (  # noqa: E402
    build_driver,
    center_browser_window,
    clear_otp_inputs,
    fetch_chatgpt_session,
    recover_email_submit_if_stuck,
    submit_email_step,
    submit_email_via_browser_nextauth,
    type_email_address,
    type_otp,
)
from core.roxy_codex_oauth import (  # noqa: E402
    _click_passwordless_signup_if_present,
    _install_email_otp_validate_hook,
    _is_email_verification_page,
    _is_login_advanced,
    _is_login_password_page,
    _is_totp_login_page,
    _login_challenge_state,
    _submit_saved_login_password,
    _submit_saved_login_totp,
    _wait_after_email_otp_submit,
    clear_roxy_browser_auth_state,
)
from core.roxybrowser_client import (  # noqa: E402
    RoxyBrowserClient,
    cleanup_orphaned_profiles,
)

logging.disable(logging.CRITICAL)

_INTERESTING_PATH = re.compile(
    r"/api/auth|/api/accounts|/oauth|/log-in|/email-otp|/mfa|/totp",
    re.IGNORECASE,
)
_PASSWORD_REJECTED_MARKERS = (
    "incorrect password",
    "invalid password",
    "wrong password",
    "password is incorrect",
    "incorrect email or password",
    "密码错误",
    "密码不正确",
    "パスワードが正しくありません",
    "パスワードが違います",
    "メールアドレスまたはパスワード",
)


def _digest(value: Any) -> str:
    return hashlib.sha256(repr(value).encode("utf-8", "replace")).hexdigest()


def _account_snapshot(account: dict[str, Any]) -> dict[str, str]:
    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    if not isinstance(raw_extra, dict):
        raw_extra = {}
    password = (
        raw_extra.get("account_password")
        or raw_extra.get("login_password")
        or raw_extra.get("registration_password")
        or ""
    )
    return {
        "email": _digest(account.get("email")),
        "password": _digest(password),
        "access_token": _digest(account.get("access_token")),
        "totp": _digest(account.get("totp_secret")),
        "extra_json": _digest(account.get("extra_json")),
        "updated_at": str(account.get("updated_at") or ""),
    }


def _path(value: Any) -> str:
    try:
        return urlparse(str(value or "")).path or "/"
    except Exception:
        return ""


def _clean(value: Any, limit: int = 120) -> str:
    text = re.sub(
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        "<email>",
        str(value or ""),
    )
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _saved_credentials(account: dict[str, Any]) -> tuple[str, str, str]:
    email = str(account.get("email") or "").strip()
    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    if not isinstance(raw_extra, dict):
        raw_extra = {}
    password = str(
        raw_extra.get("account_password")
        or raw_extra.get("login_password")
        or raw_extra.get("registration_password")
        or ""
    ).strip()
    totp_secret = str(account.get("totp_secret") or "").strip()
    return email, password, totp_secret


class CdpNetworkProbe:
    """Collect allowlisted request paths and status codes without request bodies."""

    def __init__(self) -> None:
        self.ws = None
        self.stop_event = threading.Event()
        self.thread = None
        self.events: list[dict[str, Any]] = []
        self._pending: dict[int, queue.Queue] = {}
        self._pending_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._next_id = 1

    def attach(self, debugger_address: str) -> bool:
        try:
            base = str(debugger_address or "").strip()
            if not base:
                return False
            if not base.startswith("http"):
                base = f"http://{base}"
            tabs = requests.get(f"{base.rstrip('/')}/json/list", timeout=5).json()
            pages = [
                item
                for item in tabs
                if str(item.get("type") or "") == "page"
                and item.get("webSocketDebuggerUrl")
            ]
            if not pages:
                return False
            self.ws = websocket.create_connection(
                pages[0]["webSocketDebuggerUrl"],
                timeout=0.5,
                origin=None,
            )
            self.thread = threading.Thread(target=self._receive, daemon=True)
            self.thread.start()
            self.command("Network.enable", timeout=5)
            return True
        except Exception:
            self.close()
            return False

    def _receive(self) -> None:
        while not self.stop_event.is_set() and self.ws is not None:
            try:
                raw = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                return
            try:
                message = json.loads(raw)
            except Exception:
                continue
            command_id = message.get("id")
            if command_id is not None:
                with self._pending_lock:
                    target = self._pending.get(int(command_id))
                if target is not None:
                    target.put(message)
                continue
            self._record_event(message)

    def _record_event(self, message: dict[str, Any]) -> None:
        method = str(message.get("method") or "")
        params = message.get("params") or {}
        if method == "Network.requestWillBeSent":
            request = params.get("request") or {}
            path = _path(request.get("url"))
            if _INTERESTING_PATH.search(path):
                self.events.append(
                    {
                        "kind": "request",
                        "request_id": str(params.get("requestId") or ""),
                        "path": path,
                        "method": str(request.get("method") or ""),
                    }
                )
        elif method == "Network.responseReceived":
            response = params.get("response") or {}
            path = _path(response.get("url"))
            if _INTERESTING_PATH.search(path):
                self.events.append(
                    {
                        "kind": "response",
                        "request_id": str(params.get("requestId") or ""),
                        "path": path,
                        "status": int(response.get("status") or 0),
                    }
                )
        elif method == "Network.loadingFailed":
            self.events.append(
                {
                    "kind": "loading_failed",
                    "request_id": str(params.get("requestId") or ""),
                    "error": _clean(params.get("errorText"), 80),
                }
            )
        if len(self.events) > 200:
            self.events = self.events[-200:]

    def command(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 5,
    ) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("cdp_not_attached")
        with self._pending_lock:
            command_id = self._next_id
            self._next_id += 1
            target: queue.Queue = queue.Queue(maxsize=1)
            self._pending[command_id] = target
        payload = {"id": command_id, "method": method, "params": params or {}}
        try:
            with self._send_lock:
                self.ws.send(json.dumps(payload))
            return target.get(timeout=timeout)
        finally:
            with self._pending_lock:
                self._pending.pop(command_id, None)

    def snapshot(self, start: int = 0) -> list[dict[str, Any]]:
        result = []
        for item in self.events[max(0, start) :]:
            safe = {key: value for key, value in item.items() if key != "request_id"}
            result.append(safe)
        return result[-50:]

    def close(self) -> None:
        self.stop_event.set()
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
        self.ws = None


class AuthInterfaceRun:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = RoxyBrowserClient()
        self.route = None
        self.opened = None
        self.driver = None
        self.network = CdpNetworkProbe()
        self.account: dict[str, Any] = {}
        self.email = ""
        self.password = ""
        self.totp_secret = ""
        self.otp_after_ts = 0.0
        self.before_assets: dict[str, str] | None = None
        self.events: list[dict[str, Any]] = []
        self.result: dict[str, Any] = {
            "account_id": int(args.account_id),
            "outcome": "not_started",
            "password_result": "not_submitted",
            "password_submitted": False,
            "email_otp_submitted": False,
            "totp_submitted": False,
            "session_access_token_present": False,
            "events": self.events,
            "assets_unchanged": False,
            "cleanup": {},
        }

    def page_class(self, state: dict[str, Any] | None = None) -> str:
        state = state or _login_challenge_state(self.driver)
        # /mfa-challenge 同样使用 one-time-code 输入框。必须先判明确的
        # Authenticator/MFA，再使用通用邮箱 OTP 识别，否则会白等邮件。
        if _is_totp_login_page(self.driver, state):
            return "totp"
        if _is_email_verification_page(self.driver):
            return "email_otp"
        if _is_login_password_page(self.driver):
            return "password_login"
        if _is_login_advanced(self.driver, state):
            return "advanced"
        if _path(state.get("url")) == "/auth/login":
            return "login_shell"
        return "unknown"

    def safe_page(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state or _login_challenge_state(self.driver)
        combined = (
            " ".join(str(item) for item in (state.get("errors") or []))
            + " "
            + str(state.get("text") or "")
        ).lower()
        error_kinds = []
        if any(marker in combined for marker in _PASSWORD_REJECTED_MARKERS):
            error_kinds.append("password_rejected")
        if state.get("errors"):
            error_kinds.append("visible_error")
        if any(
            str(item.get("ariaInvalid") or "").lower() == "true"
            for item in (state.get("inputs") or [])
        ):
            error_kinds.append("aria_invalid")
        inputs = [
            {
                key: _clean(item.get(key))
                for key in (
                    "type",
                    "name",
                    "id",
                    "autocomplete",
                    "inputmode",
                    "ariaInvalid",
                )
                if item.get(key)
            }
            for item in (state.get("inputs") or [])[:20]
        ]
        buttons = [
            {
                key: _clean(item.get(key))
                for key in (
                    "tag",
                    "type",
                    "name",
                    "value",
                    "aria",
                    "testid",
                    "action",
                    "text",
                )
                if item.get(key)
            }
            for item in (state.get("buttons") or [])[:20]
        ]
        return {
            "path": _path(state.get("url")),
            "page_class": self.page_class(state),
            "inputs": inputs,
            "buttons": buttons,
            "error_kinds": sorted(set(error_kinds)),
        }

    def wait_until_not(self, current_class: str, timeout: int) -> tuple[str, dict, float]:
        started = time.monotonic()
        last_state: dict[str, Any] = {}
        while time.monotonic() - started < timeout:
            try:
                last_state = _login_challenge_state(self.driver)
                page_class = self.page_class(last_state)
                safe = self.safe_page(last_state)
                if page_class != current_class or safe.get("error_kinds"):
                    return page_class, last_state, time.monotonic() - started
            except Exception:
                pass
            time.sleep(0.5)
        try:
            last_state = _login_challenge_state(self.driver)
        except Exception:
            last_state = {}
        return self.page_class(last_state), last_state, time.monotonic() - started

    def wait_for_one_of(self, classes: set[str], timeout: int) -> tuple[str, dict, float]:
        started = time.monotonic()
        last_state: dict[str, Any] = {}
        while time.monotonic() - started < timeout:
            try:
                last_state = _login_challenge_state(self.driver)
                page_class = self.page_class(last_state)
                if page_class in classes:
                    return page_class, last_state, time.monotonic() - started
            except Exception:
                pass
            time.sleep(0.5)
        try:
            last_state = _login_challenge_state(self.driver)
        except Exception:
            last_state = {}
        return self.page_class(last_state), last_state, time.monotonic() - started

    def strict_submit_email_otp(self) -> dict[str, Any]:
        try:
            result = self.driver.execute_script(
                r"""
                const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                  && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
                  && !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
                const inputs = [...document.querySelectorAll('input')].filter(visible).filter(el => {
                  const attrs = [el.type, el.name, el.id, el.autocomplete, el.inputMode, el.getAttribute('aria-label')].join(' ').toLowerCase();
                  return /one-time|otp|code|numeric|tel/.test(attrs);
                });
                if (inputs.length !== 1) return {ok:false, reason:'otp_input_count_' + inputs.length};
                const form = inputs[0].closest('form');
                if (!form) return {ok:false, reason:'otp_form_missing'};
                const submitters = [...form.querySelectorAll('button,input[type="submit"]')].filter(visible);
                const validators = submitters.filter(el =>
                  String(el.getAttribute('name') || '').toLowerCase() === 'intent'
                  && String(el.getAttribute('value') || '').toLowerCase() === 'validate'
                );
                const submitter = validators.length === 1
                  ? validators[0]
                  : submitters.length === 1
                    ? submitters[0]
                    : null;
                if (!submitter) return {
                  ok:false,
                  reason:'otp_validate_submitter_count_' + validators.length + '_all_' + submitters.length
                };
                if (typeof form.requestSubmit === 'function') form.requestSubmit(submitter);
                else form.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}));
                return {ok:true, reason:'otp_form_request_submit', name:submitter.name || '', value:submitter.value || ''};
                """
            ) or {"ok": False, "reason": "empty_result"}
            return {
                "ok": bool(result.get("ok")),
                "reason": _clean(result.get("reason")),
                "name": _clean(result.get("name")),
                "value": _clean(result.get("value")),
            }
        except Exception as exc:
            return {"ok": False, "reason": type(exc).__name__}

    def setup(self) -> None:
        self.account = db.get_account(int(self.args.account_id)) or {}
        if not self.account:
            raise RuntimeError("account_not_found")
        self.email, self.password, self.totp_secret = _saved_credentials(self.account)
        if not self.email:
            raise RuntimeError("email_missing")
        if self.args.allow_password and not self.password:
            raise RuntimeError("saved_password_missing")
        if self.args.allow_totp and not self.totp_secret:
            raise RuntimeError("saved_totp_missing")
        self.before_assets = _account_snapshot(self.account)
        self.events.append(
            {
                "preflight": "ok",
                "saved_password": bool(self.password),
                "saved_totp": bool(self.totp_secret),
                "has_access_token": bool(self.account.get("access_token")),
            }
        )
        self.route = acquire_account_proxy(
            account_id=int(self.args.account_id),
            email=self.email,
            purpose="manual-roxy-real-auth-interface",
        )
        self.events.append(
            {
                "route": "acquired",
                "provider": self.route.provider,
                "mode": self.route.mode,
                "region": self.route.region or "",
                "has_proxy_lease": bool(self.route.lease),
            }
        )
        self.opened = self.client.open_profile(
            proxy_url=self.route.proxy_url,
            headless=False,
        )
        self.events.append(
            {
                "roxy_open": "ok",
                "created_by_run": bool(self.opened.created_by_run),
            }
        )
        self.driver = build_driver(self.opened)
        center_browser_window(self.driver)
        self.driver.set_page_load_timeout(45)
        self.driver.set_script_timeout(30)
        clear_roxy_browser_auth_state(self.driver)
        attached = self.network.attach(self.opened.debugger_address or "")
        self.events.append({"cdp_network_probe": attached})

    def login_email(self) -> tuple[str, dict[str, Any]]:
        self.driver.get("https://chatgpt.com/auth/login")
        page_class, state, elapsed = self.wait_for_one_of(
            {"login_shell", "password_login", "email_otp", "totp", "advanced"},
            25,
        )
        self.events.append(
            {
                "initial_page": self.safe_page(state),
                "elapsed_seconds": round(elapsed, 2),
            }
        )
        if page_class != "login_shell":
            return page_class, state

        type_email_address(self.driver, self.email, timeout=20)
        self.otp_after_ts = time.time()
        submit_email_step(self.driver)
        self.events.append({"email_submitted_once": True})
        started = time.monotonic()
        nextauth_done = False
        resubmit_done = False
        last_state = state
        while time.monotonic() - started < 45:
            last_state = _login_challenge_state(self.driver)
            page_class = self.page_class(last_state)
            if page_class != "login_shell":
                self.events.append(
                    {
                        "after_email": self.safe_page(last_state),
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                    }
                )
                return page_class, last_state
            current_url = str(last_state.get("url") or "").lower()
            elapsed = time.monotonic() - started
            if "email=" in current_url and elapsed >= 3 and not nextauth_done:
                result = submit_email_via_browser_nextauth(self.driver, self.email)
                nextauth_done = True
                self.events.append(
                    {
                        "email_nextauth_fallback": bool(result.get("ok")),
                        "at_seconds": round(elapsed, 2),
                    }
                )
            elif (
                "email=" in current_url
                and elapsed >= 10
                and nextauth_done
                and not resubmit_done
            ):
                result = recover_email_submit_if_stuck(self.driver, self.email)
                resubmit_done = True
                self.events.append(
                    {
                        "email_form_resubmit": bool(result.get("ok")),
                        "at_seconds": round(elapsed, 2),
                    }
                )
            time.sleep(0.5)
        self.events.append(
            {
                "after_email": self.safe_page(last_state),
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "result": "timeout_still_login_shell",
            }
        )
        return "login_shell", last_state

    def submit_password(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        self.events.append({"password_page": self.safe_page(state)})
        if not self.args.allow_password:
            if self.args.allow_email_otp:
                network_start = len(self.network.events)
                self.otp_after_ts = time.time()
                result = _click_passwordless_signup_if_present(self.driver)
                safe_result = {
                    "ok": bool(result.get("ok")),
                    "reason": _clean(result.get("reason")),
                    "name": _clean(result.get("name")),
                    "value": _clean(result.get("value")),
                    "text": _clean(result.get("text")),
                }
                self.events.append({"passwordless_fallback": safe_result})
                if result.get("ok"):
                    page_class, next_state, elapsed = self.wait_until_not(
                        "password_login",
                        30,
                    )
                    self.events.append(
                        {
                            "after_passwordless_fallback": self.safe_page(next_state),
                            "elapsed_seconds": round(elapsed, 2),
                            "network": self.network.snapshot(network_start),
                        }
                    )
                    return page_class, next_state
            return "password_login", state
        network_start = len(self.network.events)
        self.otp_after_ts = time.time()
        password_mode = (
            "random_wrong" if self.args.use_random_wrong_password else "saved"
        )
        password_value = self.password
        if self.args.use_random_wrong_password:
            password_value = "T3st!" + secrets.token_urlsafe(24)
            if password_value == self.password:
                password_value += "x"
        _submit_saved_login_password(self.driver, self.email, password_value)
        password_value = ""
        self.password = ""
        self.result["password_submitted"] = True
        page_class, next_state, elapsed = self.wait_until_not(
            "password_login",
            int(self.args.password_wait),
        )
        safe = self.safe_page(next_state)
        if page_class == "password_login" and not safe.get("error_kinds"):
            password_result = "timeout_still_password_page"
        elif "password_rejected" in safe.get("error_kinds", []):
            password_result = "rejected"
        elif page_class != "password_login":
            password_result = f"advanced_to_{page_class}"
        else:
            password_result = "visible_error"
        self.result["password_result"] = password_result
        self.events.append(
            {
                "after_password": safe,
                "password_result": password_result,
                "password_mode": password_mode,
                "elapsed_seconds": round(elapsed, 2),
                "network": self.network.snapshot(network_start),
                "otp_window_started": bool(self.otp_after_ts),
            }
        )
        if (
            self.args.use_random_wrong_password
            and self.args.allow_email_otp
            and page_class == "password_login"
        ):
            self.otp_after_ts = time.time()
            fallback = _click_passwordless_signup_if_present(self.driver)
            safe_fallback = {
                "ok": bool(fallback.get("ok")),
                "reason": _clean(fallback.get("reason")),
                "name": _clean(fallback.get("name")),
                "value": _clean(fallback.get("value")),
                "text": _clean(fallback.get("text")),
            }
            self.events.append({"wrong_password_email_fallback": safe_fallback})
            if fallback.get("ok"):
                page_class, next_state, fallback_elapsed = self.wait_until_not(
                    "password_login",
                    30,
                )
                self.events.append(
                    {
                        "after_wrong_password_fallback": self.safe_page(next_state),
                        "elapsed_seconds": round(fallback_elapsed, 2),
                    }
                )
        return page_class, next_state

    def submit_email_otp(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        self.events.append({"email_otp_page": self.safe_page(state)})
        if not self.args.allow_email_otp:
            return "email_otp", state
        network_start = len(self.network.events)
        _install_email_otp_validate_hook(self.driver)
        code = str(
            wait_for_otp(
                self.email,
                after_ts=self.otp_after_ts or time.time(),
                max_wait=int(self.args.otp_wait),
                poll_interval=3,
                settle_seconds=2,
            )
            or ""
        ).strip()
        if not re.fullmatch(r"\d{6}", code):
            raise RuntimeError("email_otp_format_invalid")
        clear_otp_inputs(self.driver)
        type_otp(self.driver, code, timeout=15)
        code = ""
        time.sleep(3)
        submit_result = {"ok": True, "reason": "auto_submit_or_page_advanced"}
        if _is_email_verification_page(self.driver):
            submit_result = self.strict_submit_email_otp()
        self.result["email_otp_submitted"] = bool(submit_result.get("ok"))
        otp_result = _wait_after_email_otp_submit(self.driver, timeout=45)
        page_class, next_state, elapsed = self.wait_until_not("email_otp", 10)
        self.events.append(
            {
                "after_email_otp": self.safe_page(next_state),
                "otp_result": _clean(otp_result),
                "submit": submit_result,
                "elapsed_seconds": round(elapsed, 2),
                "network": self.network.snapshot(network_start),
            }
        )
        return page_class, next_state

    def submit_totp(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        self.events.append({"totp_page": self.safe_page(state)})
        if not self.args.allow_totp:
            return "totp", state
        network_start = len(self.network.events)
        _submit_saved_login_totp(self.driver, self.email, self.totp_secret)
        self.totp_secret = ""
        self.result["totp_submitted"] = True
        page_class, next_state, elapsed = self.wait_until_not("totp", 45)
        self.events.append(
            {
                "after_totp": self.safe_page(next_state),
                "elapsed_seconds": round(elapsed, 2),
                "network": self.network.snapshot(network_start),
            }
        )
        return page_class, next_state

    def fetch_session(self) -> None:
        try:
            session = fetch_chatgpt_session(
                self.driver,
                timeout=60,
                auto_jump_wait=8,
            )
            has_token = bool(
                session.get("accessToken")
                or session.get("access_token")
                or session.get("token")
            )
            self.result["session_access_token_present"] = has_token
            self.events.append(
                {"session_fetch": "completed", "access_token_present": has_token}
            )
        except Exception as exc:
            self.events.append({"session_fetch_error_type": type(exc).__name__})

    def execute(self) -> None:
        self.setup()
        page_class, state = self.login_email()
        if page_class == "password_login":
            page_class, state = self.submit_password(state)
        if page_class == "email_otp":
            page_class, state = self.submit_email_otp(state)
        if page_class == "totp":
            page_class, state = self.submit_totp(state)
        if page_class == "advanced":
            self.events.append({"advanced_page": self.safe_page(state)})
            self.fetch_session()

        if self.result["session_access_token_present"]:
            self.result["outcome"] = "authenticated_session_confirmed"
        elif page_class == "password_login":
            self.result["outcome"] = str(
                self.result.get("password_result") or "stopped_on_password_page"
            )
        elif page_class == "email_otp":
            self.result["outcome"] = "stopped_on_email_otp"
        elif page_class == "totp":
            self.result["outcome"] = "stopped_on_totp"
        elif page_class == "login_shell":
            self.result["outcome"] = "email_submit_unconfirmed"
        else:
            self.result["outcome"] = f"ended_on_{page_class}"

    def cleanup(self) -> None:
        self.password = ""
        self.totp_secret = ""
        self.network.close()
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
        if self.opened is not None:
            try:
                self.client.cleanup_profile(self.opened)
            except Exception:
                pass
        else:
            try:
                cleanup_orphaned_profiles()
            except Exception:
                pass
        if self.route is not None:
            try:
                self.route.release(reason="manual-roxy-real-auth-interface-complete")
            except Exception:
                pass
        time.sleep(1)

        try:
            after = db.get_account(int(self.args.account_id)) or {}
            self.result["assets_unchanged"] = (
                self.before_assets is not None
                and _account_snapshot(after) == self.before_assets
            )
        except Exception:
            self.result["assets_unchanged"] = False

        registry_count = -1
        try:
            registry_path = _PROJECT_ROOT / "run" / "roxy_active_profiles.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            items = (
                registry.get("items", [])
                if isinstance(registry, dict)
                else registry
                if isinstance(registry, list)
                else []
            )
            registry_count = len(items)
        except Exception:
            pass
        try:
            active_leases = len(active_proxy_leases())
        except Exception:
            active_leases = -1
        try:
            self.client.list_workspaces()
            api_ok = True
        except Exception:
            api_ok = False
        self.result["cleanup"] = {
            "roxy_api_ok": api_ok,
            "tracked_profiles": registry_count,
            "active_proxy_leases": active_leases,
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", type=int, required=True)
    parser.add_argument("--allow-password", action="store_true")
    parser.add_argument("--use-random-wrong-password", action="store_true")
    parser.add_argument("--allow-email-otp", action="store_true")
    parser.add_argument("--allow-totp", action="store_true")
    parser.add_argument("--password-wait", type=int, default=60)
    parser.add_argument("--otp-wait", type=int, default=180)
    args = parser.parse_args()
    if args.use_random_wrong_password and not args.allow_password:
        parser.error("--use-random-wrong-password requires --allow-password")
    return args


def main() -> int:
    args = _parse_args()
    roxy_cfg.ROXY_SELENIUM_TIMEOUT = 60
    roxy_cfg.ROXY_API_RETRIES = 1
    run = AuthInterfaceRun(args)
    try:
        run.execute()
    except Exception as exc:
        run.result["outcome"] = f"failed:{type(exc).__name__}"
        run.events.append({"error_type": type(exc).__name__})
    finally:
        run.cleanup()
    print(json.dumps(run.result, ensure_ascii=False))
    return 0 if not str(run.result["outcome"]).startswith("failed:") else 1


if __name__ == "__main__":
    raise SystemExit(main())
