#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受控验证 auth.openai.com password/verify 协议接口。

这是只读诊断工具：它会建立一次临时登录会话并提交一次明确指定的密码，
但不会跟随 MFA/OAuth callback，也不会把响应中的 token、密码、邮箱或完整
响应正文输出到终端。真实密码测试必须显式传入 ``--allow-password``；默认
使用随机错误密码，避免误提交本地凭据。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import pyotp
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config import roxybrowser as roxy_cfg  # noqa: E402
from core import db  # noqa: E402
from core.account_liveness import _warm_protocol_login_context  # noqa: E402
from core.account_proxy import acquire_account_proxy  # noqa: E402
from core.chatgpt_auth import get_csrf_token, signin_openai  # noqa: E402
from core.roxy_codex_oauth import _account_login_credentials  # noqa: E402
from core.openai_auth import (  # noqa: E402
    build_sentinel_header,
    follow_authorize,
    request_sentinel_token,
)
from core.session import BrowserSession  # noqa: E402

logging.disable(logging.CRITICAL)

_PASSWORD_PAGE = re.compile(r"/log-in/password", re.IGNORECASE)
_INTERESTING_KEYS = {
    "code",
    "error",
    "error_code",
    "errorCode",
    "type",
    "page",
    "page_type",
    "continue_url",
    "external_url",
    "url",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(repr(value).encode("utf-8", "replace")).hexdigest()


def _safe_path(value: Any) -> str:
    try:
        path = urlparse(str(value or "")).path or "/"
        if "/mfa-challenge/" in path:
            prefix, _factor = path.split("/mfa-challenge/", 1)
            return f"{prefix}/mfa-challenge/<opaque>"
        return path
    except Exception:
        return ""


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = str(value or "")
        if isinstance(value, str) and ("token" in text.lower() or len(text) > 180):
            return f"<redacted len={len(text)} sha256={_digest(text)[:12]}>"
        return value
    return f"<redacted type={type(value).__name__}>"


def _safe_response_summary(payload: Any) -> dict[str, Any]:
    """保留响应形状和错误分类，绝不打印完整 JSON。"""
    if not isinstance(payload, dict):
        return {"json_type": type(payload).__name__}
    out: dict[str, Any] = {"top_level_keys": sorted(str(key) for key in payload)[:40]}
    for key in _INTERESTING_KEYS:
        if key not in payload:
            continue
        value = payload.get(key)
        if key in {"continue_url", "external_url", "url"}:
            out[key] = _safe_path(value)
        elif key == "page" and isinstance(value, dict):
            out["page"] = {
                "keys": sorted(str(item) for item in value)[:30],
                "type": _safe_scalar(value.get("type")),
            }
        else:
            out[key] = _safe_scalar(value)
    error = payload.get("error")
    if isinstance(error, dict):
        out["error"] = {
            "keys": sorted(str(item) for item in error)[:30],
            "code": _safe_scalar(error.get("code")),
            "type": _safe_scalar(error.get("type")),
        }
    return out


def _response_record(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = None
    return {
        "http_status": int(response.status_code),
        "content_type": str(response.headers.get("content-type") or "").split(";", 1)[0],
        "response": _safe_response_summary(payload),
    }


def _credentials(account: dict[str, Any]) -> tuple[str, str]:
    email = str(account.get("email") or "").strip()
    password = _account_login_credentials(email)[0] if email else ""
    return email, str(password or "").strip()


class ProtocolPasswordRun:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.account: dict[str, Any] = {}
        self.email = ""
        self.password = ""
        self.totp_secret = ""
        self.route = None
        self.session: BrowserSession | None = None
        self.before_assets: dict[str, str] | None = None
        self.result: dict[str, Any] = {
            "account_id": int(args.account_id),
            "mode": "random_wrong_password" if args.use_random_wrong_password else "saved_password",
            "outcome": "not_started",
        }

    def setup(self) -> None:
        self.account = db.get_account(int(self.args.account_id)) or {}
        if not self.account:
            raise RuntimeError("account_not_found")
        self.email, self.password = _credentials(self.account)
        self.totp_secret = _account_login_credentials(self.email)[1] if self.email else ""
        if not self.email:
            raise RuntimeError("email_missing")
        if not self.args.use_random_wrong_password:
            if not self.args.allow_password:
                raise RuntimeError("saved_password_requires_allow_password")
            if not self.password:
                raise RuntimeError("saved_password_missing")
            if self.args.allow_totp and not self.totp_secret:
                raise RuntimeError("saved_totp_missing")
        self.before_assets = {
            "access_token": _digest(self.account.get("access_token")),
            "password": _digest(self.password),
            "totp": _digest(self.account.get("totp_secret")),
            "extra_json": _digest(self.account.get("extra_json")),
            "updated_at": str(self.account.get("updated_at") or ""),
        }
        self.route = acquire_account_proxy(
            account_id=int(self.args.account_id),
            email=self.email,
            purpose="manual-protocol-password-interface",
        )
        self.result["route"] = {
            "provider": self.route.provider,
            "mode": self.route.mode,
            "region": self.route.region or "",
            "has_proxy_lease": bool(self.route.lease),
        }
        self.session = BrowserSession(proxy=self.route.proxy_url)

    def execute(self) -> None:
        self.setup()
        assert self.session is not None
        self.session.session.timeout = max(20, int(self.args.request_timeout))
        started = time.monotonic()
        _warm_protocol_login_context(self.session)
        self.result["context_warm_seconds"] = round(time.monotonic() - started, 2)
        csrf = get_csrf_token(self.session)
        authorize_url = signin_openai(self.session, csrf, self.email)
        final_url = follow_authorize(self.session, authorize_url)
        self.result["authorize_page"] = _safe_path(final_url)
        if not _PASSWORD_PAGE.search(final_url):
            self.result["outcome"] = "password_page_not_reached"
            return

        sentinel_started = time.monotonic()
        challenge = request_sentinel_token(self.session, "password_verify")
        sentinel_header, so_header = build_sentinel_header(
            self.session,
            challenge,
            "password_verify",
        )
        self.result["sentinel_seconds"] = round(time.monotonic() - sentinel_started, 2)
        self.result["sentinel_requirements"] = {
            "turnstile": bool((challenge.get("turnstile") or {}).get("required")),
            "so": bool((challenge.get("so") or {}).get("required")),
            "pow": bool((challenge.get("proofofwork") or {}).get("required")),
        }
        headers = self.session.get_auth_headers(referer="https://auth.openai.com/log-in/password")
        headers["openai-sentinel-token"] = sentinel_header
        if so_header:
            headers["openai-sentinel-so-token"] = so_header
        password = (
            f"codex-diagnostic-invalid-{time.time_ns()}-{hashlib.sha256(self.email.encode()).hexdigest()[:10]}"
            if self.args.use_random_wrong_password
            else self.password
        )
        request_started = time.monotonic()
        # 直接使用 curl_cffi 会话，避免本次诊断把密码原文交给项目调试记录器。
        response = self.session.session.post(
            "https://auth.openai.com/api/accounts/password/verify",
            headers=headers,
            data=json.dumps({"password": password}),
            allow_redirects=False,
            timeout=max(20, int(self.args.request_timeout)),
        )
        self.password = ""
        self.result["password_verify_seconds"] = round(time.monotonic() - request_started, 2)
        self.result.update(_response_record(response))
        if 200 <= response.status_code < 300:
            self.result["outcome"] = "accepted"
            if self.args.allow_totp:
                self._verify_totp(response)
        elif response.status_code in {401, 403}:
            self.result["outcome"] = "credential_rejected_or_blocked"
        elif response.status_code == 429:
            self.result["outcome"] = "rate_limited"
        else:
            self.result["outcome"] = "http_error"

    def _verify_totp(self, password_response: Any) -> None:
        try:
            payload = password_response.json()
        except Exception:
            payload = {}
        page = payload.get("page") if isinstance(payload, dict) else {}
        page = page if isinstance(page, dict) else {}
        continue_url = str(
            payload.get("continue_url")
            or page.get("continue_url")
            or ""
        )
        factor_id = continue_url.rstrip("/").rsplit("/", 1)[-1] if "/mfa-challenge/" in continue_url else ""
        if not factor_id:
            self.result["totp_outcome"] = "mfa_factor_missing"
            return
        assert self.session is not None
        headers = self.session.get_auth_headers(referer="https://auth.openai.com/mfa-challenge")
        headers.pop("openai-sentinel-token", None)
        headers.pop("openai-sentinel-so-token", None)
        issue = self.session.session.post(
            "https://auth.openai.com/api/accounts/mfa/issue_challenge",
            headers=headers,
            data=json.dumps({"id": factor_id, "type": "totp", "force_fresh_challenge": False}),
            allow_redirects=False,
            timeout=max(20, int(self.args.request_timeout)),
        )
        self.result["mfa_issue"] = _response_record(issue)
        if issue.status_code < 200 or issue.status_code >= 300:
            self.result["totp_outcome"] = "mfa_issue_failed"
            return
        code = pyotp.TOTP(self.totp_secret).now()
        verify = self.session.session.post(
            "https://auth.openai.com/api/accounts/mfa/verify",
            headers=headers,
            data=json.dumps({"id": factor_id, "type": "totp", "code": code}),
            allow_redirects=False,
            timeout=max(20, int(self.args.request_timeout)),
        )
        self.result["mfa_verify"] = _response_record(verify)
        self.result["totp_outcome"] = "accepted" if 200 <= verify.status_code < 300 else "rejected_or_blocked"
        verify_payload = self.result.get("mfa_verify", {}).get("response", {})
        if isinstance(verify_payload, dict):
            self.result["totp_continue_path"] = verify_payload.get("continue_url") or ""

    def cleanup(self) -> None:
        self.password = ""
        self.totp_secret = ""
        if self.session is not None:
            try:
                self.session.session.close()
            except Exception:
                pass
        if self.route is not None:
            try:
                self.route.release(reason="manual-protocol-password-interface-complete")
            except Exception:
                pass
        try:
            after = db.get_account(int(self.args.account_id)) or {}
            _email, password = _credentials(after)
            after_assets = {
                "access_token": _digest(after.get("access_token")),
                "password": _digest(password),
                "totp": _digest(after.get("totp_secret")),
                "extra_json": _digest(after.get("extra_json")),
                "updated_at": str(after.get("updated_at") or ""),
            }
            self.result["assets_unchanged"] = self.before_assets == after_assets
        except Exception:
            self.result["assets_unchanged"] = False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", type=int, required=True)
    parser.add_argument("--allow-password", action="store_true")
    parser.add_argument("--allow-totp", action="store_true")
    parser.add_argument("--use-random-wrong-password", action="store_true")
    parser.add_argument("--request-timeout", type=int, default=45)
    args = parser.parse_args()
    if not args.use_random_wrong_password and not args.allow_password:
        parser.error("saved password requires --allow-password; otherwise use --use-random-wrong-password")
    return args


def main() -> int:
    args = _parse_args()
    roxy_cfg.ROXY_API_RETRIES = 1
    run = ProtocolPasswordRun(args)
    try:
        run.execute()
    except Exception as exc:
        run.result["outcome"] = f"failed:{type(exc).__name__}"
        run.result["error_type"] = type(exc).__name__
    finally:
        run.cleanup()
    print(json.dumps(run.result, ensure_ascii=False))
    return 0 if not str(run.result["outcome"]).startswith("failed:") else 1


if __name__ == "__main__":
    raise SystemExit(main())
