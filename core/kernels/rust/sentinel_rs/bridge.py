"""sentinel-rs 原生进程桥接。

只负责一件事：把一个已经由本地任务分配的邮箱和代理交给内核自有进程，并把
进程写回的账号事实读成结构化结果。任务、Attempt/Run、邮箱/代理租约、账号保
存和后处理仍由注册领域持有。

进程边界用一次性静态邮箱行（``email----code_url``）交给原生端，不在 Python
和 Rust 之间复制 Cookie、密码或 OTP；原生端只写自己的临时 SQLite。当前版本
要求邮箱来源为 ``generic_api``，因为只有这种来源本身就提供取码 URL。
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_CANDIDATES = (
    _REPO_ROOT / "native" / "sentinel-rs" / "target" / "release" / "sentinel-rs",
    Path("/srv/apps/sentinel-rs/target/release/sentinel-rs"),
    Path("/usr/local/bin/sentinel-rs"),
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(token|password|passwd|secret|key|code)=([^&\s\"']+)"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)(\S+)"),
)
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

_STAGES = (
    ("[1/10]", "authenticate", "Rust 内核预热会话"),
    ("[2/10]", "auth_redirect", "Rust 内核获取授权地址"),
    ("[3/10]", "auth_redirect", "Rust 内核建立认证会话"),
    ("[4/10]", "login_password", "Rust 内核创建密码"),
    ("[5/10]", "login_password", "Rust 内核账号已在服务端建立"),
    ("[6/10]", "email_otp", "Rust 内核已请求邮箱验证码"),
    ("[7/10]", "email_otp", "Rust 内核验证码已通过"),
    ("[8/10]", "profile", "Rust 内核提交流程资料"),
    ("[9/10]", "token", "Rust 内核建立登录态"),
    ("[10/10]", "token", "Rust 内核获取 Token"),
)


class SentinelRsUnavailable(RuntimeError):
    """原生二进制不存在或不可执行。"""

    cause_code = "sentinel_rs_binary_unavailable"


class SentinelRsFailed(RuntimeError):
    """原生进程失败；消息只保留脱敏后的尾部诊断。"""

    cause_code = "sentinel_rs_registration_failed"

    def __init__(self, message: str, *, exit_code: int | None = None, diagnostics: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.diagnostics = diagnostics


class SentinelRsResultInvalid(RuntimeError):
    """进程退出但结果缺少可核验的账号事实。"""

    cause_code = "sentinel_rs_result_invalid"


def configured_binary() -> str:
    """读取显式配置的二进制路径（默认空 = 自动查找）。"""
    try:
        from config import sentinel_rs as cfg

        return str(getattr(cfg, "SENTINEL_RS_BIN", "") or "").strip()
    except Exception:
        return str(os.getenv("SENTINEL_RS_BIN") or "").strip()


def timeout_seconds() -> int:
    try:
        from config import sentinel_rs as cfg

        value = int(getattr(cfg, "SENTINEL_RS_TIMEOUT_SECONDS", 1200) or 1200)
    except Exception:
        value = 1200
    return max(60, value)


def log_level() -> str:
    try:
        from config import sentinel_rs as cfg

        value = str(getattr(cfg, "SENTINEL_RS_LOG_LEVEL", "info") or "info").strip().lower()
    except Exception:
        value = "info"
    return value if value in {"trace", "debug", "info", "warn", "error", "off"} else "info"


def resolve_binary() -> Path:
    """按显式配置、项目内、约定的外部构建目录、PATH 的顺序查找。"""
    explicit = configured_binary()
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path
        raise SentinelRsUnavailable(f"SENTINEL_RS_BIN 指向的文件不可执行: {explicit}")
    for candidate in _DEFAULT_CANDIDATES:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    import shutil

    found = shutil.which("sentinel-rs")
    if found:
        return Path(found)
    raise SentinelRsUnavailable("未找到 sentinel-rs 二进制；请构建 native/sentinel-rs 或设置 SENTINEL_RS_BIN")


def binary_status() -> tuple[bool, str]:
    """能力检查：只校验可执行和版本，不发网络请求。"""
    try:
        binary = resolve_binary()
    except SentinelRsUnavailable as exc:
        return False, str(exc)
    try:
        completed = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"sentinel-rs 无法启动: {type(exc).__name__}"
    if completed.returncode != 0:
        return False, f"sentinel-rs --version 退出码 {completed.returncode}"
    return True, ""


def _redact(line: str) -> str:
    text = _EMAIL_PATTERN.sub("<email>", str(line or ""))
    text = _SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}=<redacted>", text)
    text = _SECRET_PATTERNS[1].sub(lambda m: f"{m.group(1)}<redacted>", text)
    return text.strip()[:300]


def _tail_diagnostics(lines: list[str]) -> str:
    return " | ".join(_redact(line) for line in lines[-12:] if str(line).strip())[:1800]


@dataclass(frozen=True)
class BridgeRequest:
    email: str
    proxy: str
    code_url: str
    binary: Path
    workdir: Path
    timeout_seconds: int
    log_level: str


@dataclass(frozen=True)
class BridgeAccount:
    email: str
    password: str
    access_token: str
    totp_secret: str
    cookies: str
    status: str
    account_id: int | None = None


def _write_email_pool(request: BridgeRequest) -> Path:
    path = request.workdir / "email_pool.txt"
    line = f"{request.email}----{request.code_url}\n"
    path.write_text(line, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _account_from_row(row: sqlite3.Row) -> BridgeAccount:
    return BridgeAccount(
        email=str(row["email"] or ""), password=str(row["password"] or ""),
        access_token=str(row["access_token"] or ""), totp_secret=str(row["totp_secret"] or ""),
        cookies=str(row["cookies"] or ""), status=str(row["status"] or ""),
        account_id=int(row["id"]) if row["id"] is not None else None,
    )


def read_accounts(db_path: Path) -> list[BridgeAccount]:
    """读取内核临时库里的全部账号行；失败路径也用它保住已生成的密码。"""
    path = Path(db_path)
    if not path.is_file():
        return []
    try:
        con = sqlite3.connect(str(path), timeout=5)
    except sqlite3.Error:
        return []
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, email, password, access_token, totp_secret, cookies, status "
            "FROM accounts ORDER BY id",
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return [_account_from_row(row) for row in rows]


def _read_account(db_path: Path, email: str) -> BridgeAccount | None:
    matched = [
        account for account in read_accounts(db_path)
        if account.email.strip().lower() == str(email or "").strip().lower()
    ]
    return matched[-1] if matched else None


def run_registration(
    request: BridgeRequest,
    *,
    on_progress: Callable[[str, str, str | None], None] | None = None,
    check_cancel: Callable[[], None] | None = None,
) -> BridgeAccount:
    """运行一次真实注册并返回已落库账号；任何成功判断都必须有 AT 和身份证据。"""
    email_pool = _write_email_pool(request)
    db_path = request.workdir / "accounts.db"
    command = [
        str(request.binary), "register", "--live", "--count", "1",
        "--db", str(db_path), "--proxy", request.proxy,
    ]
    env = {
        **os.environ,
        "REG_MAIL_EMAIL_FILE": str(email_pool),
        "REG_MAIL_ALLOW_INSECURE": "1",
        "SENTINEL_DB_PATH": str(db_path),
        "SENTINEL_LOG": request.log_level,
        "SENTINEL_ENABLE_2FA": "0",
        "SENTINEL_FP_GEO_PROBE": "1",
        "OTP_MAX_WAIT": str(min(request.timeout_seconds, 300)),
    }
    lines: list[str] = []
    last_stage = None
    deadline = time.monotonic() + request.timeout_seconds

    logger.info("sentinel-rs 启动：binary=%s timeout=%ss", request.binary.name, request.timeout_seconds)
    try:
        process = subprocess.Popen(
            command, cwd=str(request.workdir), env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True,
        )
    except OSError as exc:
        raise SentinelRsUnavailable(f"sentinel-rs 无法启动: {type(exc).__name__}") from exc

    def reader() -> None:
        nonlocal last_stage
        if process.stdout is None:
            return
        for raw in process.stdout:
            line = raw.rstrip("\n")
            lines.append(line)
            if len(lines) > 400:
                del lines[:100]
            for marker, stage, detail in _STAGES:
                if marker in line:
                    if stage != last_stage and on_progress is not None:
                        if last_stage is not None:
                            try:
                                on_progress(last_stage, "success", None)
                            except Exception:
                                logger.exception("sentinel-rs 阶段完成上报失败")
                        last_stage = stage
                        try:
                            on_progress(stage, "running", detail)
                        except Exception:
                            logger.exception("sentinel-rs 进度上报失败")
                    break

    reader_thread = threading.Thread(target=reader, name="sentinel-rs-stdout", daemon=True)
    reader_thread.start()

    cancelled = False
    try:
        while process.poll() is None:
            if check_cancel is not None:
                try:
                    check_cancel()
                except BaseException:
                    cancelled = True
                    raise
            if time.monotonic() >= deadline:
                diagnostics = _tail_diagnostics(lines)
                logger.error("sentinel-rs 超时：diagnostics=%s", diagnostics)
                raise SentinelRsFailed("sentinel-rs 注册超时", exit_code=None, diagnostics=diagnostics)
            time.sleep(0.2)
    finally:
        if process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), 15)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(process.pid), 9)
                except (ProcessLookupError, PermissionError):
                    pass
                process.wait(timeout=5)
        reader_thread.join(timeout=3)

    exit_code = process.returncode
    diagnostics = _tail_diagnostics(lines)
    if cancelled:
        logger.warning("sentinel-rs 已取消：exit=%s diagnostics=%s", exit_code, diagnostics)
        raise SentinelRsFailed("sentinel-rs 注册已取消", exit_code=exit_code, diagnostics=diagnostics)
    if exit_code != 0:
        logger.error("sentinel-rs 失败：exit=%s diagnostics=%s", exit_code, diagnostics)
        raise SentinelRsFailed(
            f"sentinel-rs 退出码 {exit_code}", exit_code=exit_code, diagnostics=diagnostics,
        )
    if last_stage is not None and on_progress is not None:
        try:
            on_progress(last_stage, "success", None)
        except Exception:
            logger.exception("sentinel-rs 收尾阶段上报失败")
    account = _read_account(db_path, request.email)
    logger.info("sentinel-rs 完成：exit=0 account=%s", account.email if account else "missing")
    if account is None:
        raise SentinelRsResultInvalid("sentinel-rs 未写回账号记录")
    if account.email.strip().lower() != request.email.strip().lower():
        raise SentinelRsResultInvalid("sentinel-rs 返回的邮箱与本次任务不一致")
    if account.status != "registered":
        raise SentinelRsResultInvalid(f"sentinel-rs 账号状态为 {account.status or '空'}")
    if not account.access_token:
        raise SentinelRsResultInvalid("sentinel-rs 账号缺少 Access Token")
    return account


__all__ = [
    "BridgeAccount", "BridgeRequest", "SentinelRsFailed", "SentinelRsResultInvalid",
    "SentinelRsUnavailable", "binary_status", "read_accounts", "resolve_binary", "run_registration",
    "timeout_seconds", "log_level",
]
