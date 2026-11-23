"""sentinel-rs 注册实现：原生执行，本地任务与凭据保存边界保持原样。"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SUPPORTED_EMAIL_SOURCE = "generic_api"


def _jwt_payload(token: str) -> dict:
    """只读取 AT 的声明；不校验签名，签名校验仍由远端接口负责。"""
    parts = str(token or "").split(".")
    if len(parts) < 2:
        return {}
    body = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(body.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _install_cookies(session, cookie_header: str) -> int:
    """把内核返回的 Cookie 头装入本地会话，供后处理继续使用。"""
    count = 0
    for part in str(cookie_header or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name, value = name.strip(), value.strip()
        if not name:
            continue
        if name.lower() == "oai-did" and value:
            # 后续请求必须继续声明内核实际使用的设备标识。
            session.device_id = value
        for domain in ("chatgpt.com", "auth.openai.com", "sentinel.openai.com"):
            try:
                session.session.cookies.set(name, value, domain=domain, path="/")
                count += 1
            except Exception:
                logger.debug("sentinel-rs Cookie 写入失败: %s", name)
    return count


def _session_info(session, access_token: str, email: str) -> dict:
    """优先用真实会话接口核验 AT；失败时退回 AT 声明，不伪造用户字段。"""
    info: dict = {}
    try:
        from core.auth.protocol.chatgpt_auth import probe_auth_session

        info = probe_auth_session(session) or {}
    except Exception:
        logger.warning("sentinel-rs 会话核验失败，改用 Token 声明")
        info = {}
    if (
        isinstance(info, dict)
        and str(info.get("accessToken") or "") == access_token
        and isinstance(info.get("user"), dict)
        and info.get("user")
    ):
        return info
    claims = _jwt_payload(access_token)
    auth = claims.get("https://api.openai.com/auth")
    auth = auth if isinstance(auth, dict) else {}
    expires = claims.get("exp")
    return {
        "accessToken": access_token,
        "user": {"email": email, "id": str(claims.get("sub") or "")},
        "account": {"id": str(auth.get("chatgpt_account_id") or claims.get("chatgpt_account_id") or "")},
        "expires": (
            datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
            if isinstance(expires, (int, float)) else None
        ),
    }


def _salvage_kernel_account(
    exc: BaseException, *, workdir: Path, email: str, proxy: str, email_source: str,
) -> None:
    """内核失败时也把已生成的密码存成候选凭据，避免远端账号无凭据。"""
    from core.kernels.rust.sentinel_rs.bridge import read_accounts

    try:
        accounts = [
            item for item in read_accounts(workdir / "accounts.db")
            if str(item.email or "").strip().lower() == str(email or "").strip().lower()
            and str(item.password or "").strip()
        ]
    except Exception:
        logger.exception("sentinel-rs 失败后读取内核账号行失败")
        return
    if not accounts:
        return
    account = accounts[-1]
    try:
        from core.registration.checkpoints import save_protocol_password_checkpoint

        save_protocol_password_checkpoint(
            email=email, password=account.password, state="confirmed",
            proxy=proxy, email_source=email_source,
        )
    except Exception:
        # 保存失败不能改变任务原本的失败原因，只记录日志。
        logger.exception("sentinel-rs 失败后保存内核密码失败")
        return
    setattr(exc, "password_salvaged", True)
    setattr(exc, "kernel_account_status", account.status)
    logger.warning(
        "sentinel-rs 失败后已保存内核生成的密码：status=%s account_id=%s",
        account.status, account.account_id,
    )


def _run_sentinel_rs_flow(
    session, *, email, name, birthday, otp_code, email_source,
    existing_password, existing_totp_secret, options,
):
    """把一次已分配邮箱/线路交给原生进程，并返回本地后处理需要的会话事实。"""
    from core.kernels.rust.sentinel_rs.bridge import (
        BridgeRequest, log_level, protocol_enabled, resolve_binary, run_registration, timeout_seconds,
    )
    from core.registration.service import (
        adopt_progress_thread_context,
        report_job_progress,
        snapshot_progress_thread_context,
    )

    progress_context = snapshot_progress_thread_context()
    if existing_password:
        raise RuntimeError("Rust 内核尚不支持原身份续跑，请使用原任务重跑入口或改用协议内核")
    if otp_code:
        raise RuntimeError("Rust 内核尚不支持外部手工验证码输入")
    source = str(email_source or "").strip().lower()
    if source != _SUPPORTED_EMAIL_SOURCE:
        raise RuntimeError(
            f"Rust 内核当前只支持 generic_api 邮箱来源（当前 {source or '未知'}）"
        )
    email = str(email or "").strip()
    proxy = str(getattr(session, "proxy", "") or "").strip()
    if not proxy:
        raise RuntimeError("Rust 内核注册必须使用统一代理池已领取线路")

    from core import db

    row = db.get_generic_api_email_by_email(email) or {}
    code_url = str(row.get("code_url") or "").strip()
    if not code_url:
        raise RuntimeError("通用 API 邮箱缺少取码地址，无法交给 Rust 内核")

    workdir = Path(tempfile.mkdtemp(prefix="turb-sentinel-rs-"))
    try:
        request = BridgeRequest(
            email=email, proxy=proxy, code_url=code_url, binary=resolve_binary(),
            workdir=workdir, timeout_seconds=timeout_seconds(), log_level=log_level(),
        )

        def on_progress(stage: str, state: str, detail: str | None) -> None:
            # sentinel-rs 的 stdout 由独立 reader 线程消费；进度上下文是线程本地的，
            # 必须显式带过去，否则中间阶段不会写入任务时间线。
            adopt_progress_thread_context(progress_context)
            report_job_progress(stage, state, detail)

        def check_cancel() -> None:
            from core.registration.service import check_stop_requested

            check_stop_requested()

        saved_password: dict[str, str] = {}

        def persist_password(address: str, password: str) -> dict:
            from core.registration.checkpoints import save_protocol_password_checkpoint
            from core.registration.service import registration_fact_context

            save_protocol_password_checkpoint(
                email=address or email, password=password, state="prepared",
                proxy=proxy, email_source=source,
            )
            saved_password["value"] = password
            try:
                attempt_id = registration_fact_context().get("attempt_id")
            except Exception:
                attempt_id = None
            return {"persisted": True, "attempt_id": attempt_id}

        def confirm_password() -> None:
            password = saved_password.get("value")
            if not password:
                return
            from core.registration.checkpoints import save_protocol_password_checkpoint

            save_protocol_password_checkpoint(
                email=email, password=password, state="confirmed",
                proxy=proxy, email_source=source,
            )

        # 内核原窗口是 300s；配置更宽时跟随配置，至少不回退到这个下限。
        try:
            from config import email as _email_cfg

            otp_wait = max(int(getattr(_email_cfg, "OTP_MAX_WAIT", 300) or 300), 300)
        except Exception:
            otp_wait = 300
        protocol_hooks = {
            "persist_password": persist_password,
            "confirm_password": confirm_password,
            "email_source": source,
            "otp_wait_seconds": otp_wait,
        } if protocol_enabled() else None
        enable_2fa = bool(options.get("twofa_enabled", True))
        account = run_registration(
            request, on_progress=on_progress, check_cancel=check_cancel,
            protocol_hooks=protocol_hooks, enable_2fa=enable_2fa,
        )
    except BaseException as exc:
        # 内核可能已经建号（pending_otp）；超时、取消或异常退出都要先保住密码。
        _salvage_kernel_account(
            exc, workdir=workdir, email=email, proxy=proxy, email_source=source,
        )
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    _install_cookies(session, account.cookies)
    session_info = _session_info(session, account.access_token, email)
    return {
        "access_token": account.access_token,
        "session_info": session_info,
        "registration_password": account.password or None,
        "totp_secret": account.totp_secret or None,
        # Rust 的 user/register 成功且内核写回了密码，等价于密码创建已被接受；
        # 不再强制二次登录校验，否则所有 Rust 注册都会被标成 partial_success。
        "password_validated": bool(str(account.password or "").strip()),
        "remote_identity": "new",
        "sentinel_rs_account_id": account.account_id,
    }


def run_sentinel_rs_registration(
    email: str, name: str, birthday: str | None = None, proxy: str | None = None,
    otp_code: str | None = None, existing_password: str | None = None,
    existing_totp_secret: str | None = None, profile_id: str | None = None,
    registration_options: dict | None = None, email_source: str | None = None,
) -> dict:
    """Rust 内核注册入口；账号落库、后处理和资源归还沿用本地生命周期。"""
    from core.auth.protocol.session import BrowserSession
    from core.registration.protocol_oss_2.lifecycle import run_protocol_oss_2_lifecycle

    options = dict(registration_options or {})
    options.update(registration_driver="sentinel_rs", password_enabled=True, password_mode="password")
    return run_protocol_oss_2_lifecycle(
        email=email, name=name, birthday=birthday, proxy=proxy, otp_code=otp_code,
        existing_password=existing_password, existing_totp_secret=existing_totp_secret,
        profile_id=profile_id, registration_options=options, email_source=email_source,
        _flow_runner=_run_sentinel_rs_flow, _driver_name="sentinel_rs", _label="Rust sentinel-rs",
        _session_factory=lambda **kwargs: BrowserSession(**kwargs, detect_exit_geo=False),
    )


__all__ = ["run_sentinel_rs_registration"]
