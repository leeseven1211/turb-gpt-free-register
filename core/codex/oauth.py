# -*- coding: utf-8 -*-
"""注册成功后的 Codex OAuth 授权模块。

Protocol 使用独立会话提交邮箱，再按 OpenAI 返回的登录挑战完成密码、
Authenticator 2FA 或邮箱验证码；必要时继续手机号验证和 workspace 授权。
回调凭据只交给对应授权后端处理，不写入日志。
"""
import base64
import hashlib
import json
import logging
import random
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, quote, urljoin

# 用模块属性方式访问 config，支持 WebUI 热加载（config.reload_all()）。
# 协议级常量（CLIENT_ID/URL/SCOPE/OUTPUT_DIRNAME）虽然不会改，统一从 _cfg 读，
# 这样 reload 后立即生效，不用再分两套导入。
from config import codex as _cfg
from config.operation_drivers import registration_codex_driver
from core.auth.email_guard import bind_auth_observer, serialize_email_auth
from core.auth.protocol.session import BrowserSession
from core.auth.humanize import delay as human_delay
from core.auth.protocol.openai_auth import _is_transient_network_error, _extract_error_code, detect_account_unusable_response_body, AccountUnusableError, request_sentinel_token, build_sentinel_header, network_preflight, navigate_email_otp_send, _rotate_document_navigation_id
from core.codex import cpa_download
from core.codex.phone_errors import CodexPhoneVerificationError, phone_failure_from_response
from core.codex.auth_page import CodexAuthPageSession
from core.codex.session_diagnostics import CodexDiagnosticSession, safe_session_diagnostics
from core.sms import provider as sms_provider
from core.operations.runtime import OperationCancelled, call_cancellable, check_cancelled, current_token, report_stage
from curl_cffi import requests as curl_requests

logger = logging.getLogger('core.codex_oauth')


class CodexAuthResultUnknown(RuntimeError):
    """验证请求可能已被服务端处理，禁止在本轮盲目重交凭据。"""


class CodexConsentUnverifiableError(RuntimeError):
    """授权确认页缺少可确认的单一工作区，需交由浏览器处理。"""


class CodexPhoneVerificationDisabled(RuntimeError):
    """授权要求手机验证，但任务已关闭接码。"""

    code = "codex_phone_verification_disabled"

    def __init__(self):
        super().__init__("Codex OAuth 需要手机号验证，但手机接码已关闭，已退出授权")


def _ensure_phone_verification_enabled(phone_enabled: bool | None = None) -> None:
    """只在已确认手机挑战后检查开关，任务快照优先于当前配置。"""
    enabled = getattr(_cfg, "CODEX_PHONE_ENABLED", True) if phone_enabled is None else phone_enabled
    if not enabled:
        error = CodexPhoneVerificationDisabled()
        report_stage("phone_check", str(error), state="failed", detail={"cause_code": error.code})
        raise error


def _phone_verification_disabled_result(email: str, exc: CodexPhoneVerificationDisabled) -> dict:
    """保留明确的配置失败；手机和凭据授权均未继续提交，可直接重跑。"""
    return {
        **_codex_result(status="failed", email=email, message=str(exc)),
        "error_code": exc.code,
        "cause_code": exc.code,
        "error_category": "configuration",
        "remote_write_rejected": True,
        "auth_diagnostics": {
            "operation": "phone_verification",
            "failure_kind": "phone_verification_disabled",
        },
    }


_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 跟重定向链时的最大跳数，防死循环
_MAX_REDIRECTS = 15

# 网络层临时性错误（代理抖动 / TLS 握手失败 / 重置）重试参数，对齐 openai_auth.follow_authorize
_NET_MAX_ATTEMPTS = 3
_NET_BACKOFF_BASE = 2.0

# Auth 响应设置 cookie 与后续 workspace/select 之间偶尔存在短暂竞态。
_WORKSPACE_COOKIE_WAIT_SECONDS = 4.0
_WORKSPACE_POLL_INTERVAL_SECONDS = 0.2


def _with_net_retry(label: str, fn):
    """
    对临时性网络错误（TLS/代理/超时/重置）做重试包装。
    非临时错误（业务 4xx 等）直接抛。最多 _NET_MAX_ATTEMPTS 次。
    """
    from core.kernels.protocol.local.codex_oauth import _with_net_retry as execute

    return execute(_protocol_execution_context(), label, fn)


class _CodexSessionDiagnosticComplete(Exception):
    def __init__(self, detail):
        self.detail = safe_session_diagnostics(detail)
        super().__init__("MFA 会话诊断已停止；未申请号码或提交授权 callback")


def _codex_result(
    *,
    status: str,
    ok: bool = False,
    http_status: int | None = None,
    email: str | None = None,
    file_path: str | None = None,
    callback_url: str | None = None,
    message: str = "",
    credential_confirmed: bool = False,
    callback_submitted: bool = False,
    receipt_path: str | None = None,
    email_permanently_unusable: bool = False,
    account_unusable_error_code: str | None = None,
) -> dict:
    """构造与 flow_trigger._flow_result 同形态的结构化结果。"""
    return {
        "status": status,
        "ok": ok,
        "http_status": http_status,
        "email": email,
        "file_path": file_path,
        "callback_url": callback_url,
        "message": message,
        "credential_confirmed": bool(credential_confirmed),
        "callback_submitted": bool(callback_submitted),
        "receipt_path": receipt_path,
        "email_permanently_unusable": bool(email_permanently_unusable),
        "account_unusable_error_code": account_unusable_error_code,
    }


# ============================================================
# PKCE / state（对照 CLIProxyAPI pkce.go）
# ============================================================

def _generate_pkce() -> tuple[str, str]:
    """生成 PKCE 代码对：verifier=base64url(96字节)，challenge=base64url(sha256(verifier))。"""
    verifier_bytes = secrets.token_bytes(96)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _generate_state() -> str:
    """生成 OAuth state 随机串，防 CSRF。"""
    return secrets.token_urlsafe(32)


def _build_authorize_url(state: str, code_challenge: str, prompt: str | None = "login") -> str:
    """按 CLIProxyAPI openai_auth.go 的参数集拼 Codex 授权 URL。"""
    params = {
        "client_id": _cfg.CODEX_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": _cfg.CODEX_REDIRECT_URI,
        "scope": _cfg.CODEX_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    if prompt:
        params["prompt"] = prompt
    return f"{_cfg.CODEX_AUTH_URL}?{urlencode(params)}"


def _ensure_oai_context_url(auth_url: str, session: BrowserSession) -> str:
    """在 Codex OAuth 授权 URL 上补齐前端同源上下文参数，保持 oai-did 连续。"""
    try:
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        changed = False
        additions = {
            "ext-oai-did": session.device_id,
            "auth_session_logging_id": session.auth_session_logging_id,
            "screen_hint": "login_or_signup",
        }
        for key, value in additions.items():
            if not params.get(key):
                params[key] = [value]
                changed = True
        if not changed:
            return auth_url
        query = urlencode(params, doseq=True)
        return parsed._replace(query=query).geturl()
    except Exception:
        return auth_url


# ============================================================
# CPA 管理接口：授权地址由 CPA 生成，成功回调提交给 CPA
# ============================================================

def _codex_auth_url_source() -> str:
    return str(getattr(_cfg, "CODEX_AUTH_URL_SOURCE", "cpa") or "cpa").strip().lower()


def _cpa_management_origin() -> str:
    raw = str(getattr(_cfg, "CPA_MANAGEMENT_URL", "") or "").strip()
    if not raw:
        raise RuntimeError("[Codex][CPA] 尚未配置 CPA_MANAGEMENT_URL")
    try:
        parsed = urlparse(raw)
    except Exception as exc:
        raise RuntimeError(f"[Codex][CPA] CPA_MANAGEMENT_URL 格式无效: {raw}") from exc
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError(f"[Codex][CPA] CPA_MANAGEMENT_URL 格式无效: {raw}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _cpa_management_key() -> str:
    key = str(getattr(_cfg, "CPA_MANAGEMENT_KEY", "") or "").strip()
    if not key:
        raise RuntimeError("[Codex][CPA] 尚未配置 CPA_MANAGEMENT_KEY")
    return key


def _cpa_request_json(method: str, path: str, body: dict | None = None, *, download_phase: str = "") -> dict:
    """调用 CPA 管理接口，兼容 FlowPilot 的 /v0/management/* 协议。"""
    origin = _cpa_management_origin()
    key = _cpa_management_key()
    timeout = int(getattr(_cfg, "CPA_REQUEST_TIMEOUT", 30) or 30)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "X-Management-Key": key,
    }
    url = f"{origin}{path}"
    session = curl_requests.Session(curl_infos=cpa_download.CURL_INFOS) if download_phase else curl_requests.Session()
    try:
        resp = cpa_download.send(
            session,
            method.upper(),
            url,
            phase=download_phase,
            headers=headers,
            data=None if body is None else json.dumps(body),
            timeout=timeout,
        )
        try:
            payload = resp.json()
        except Exception:
            payload = {}
        if resp.status_code < 200 or resp.status_code >= 300:
            category = "http_error"
            if method.upper() == "POST" and path == "/v0/management/oauth-callback" and resp.status_code == 409:
                body = " ".join(
                    str(payload.get(key) or "") for key in ("error", "message", "detail", "reason")
                ) if isinstance(payload, dict) else ""
                if "timeout waiting for oauth callback" in f"{body} {resp.text or ''}".lower():
                    category = "oauth_callback_timeout"
            raise RuntimeError(f"[Codex][CPA] 管理接口失败 status={resp.status_code} category={category}")
        return payload if isinstance(payload, dict) else {}
    finally:
        try:
            session.close()
        except Exception:
            pass


def _sub2_codex_base() -> str:
    from config import sub2api as _sub2_cfg
    raw = str(
        getattr(_sub2_cfg, "SUB2API_API_BASE", "")
        or getattr(_sub2_cfg, "SUB2_CODEX_API_BASE", "")
        or ""
    ).strip().rstrip("/")
    if not raw:
        raise RuntimeError("[Codex][sub2] 尚未配置 SUB2API_API_BASE")
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError(f"[Codex][sub2] SUB2API_API_BASE 格式无效: {raw}")
    return raw


def _sub2_codex_headers() -> dict:
    from config import sub2api as _sub2_cfg
    token = str(getattr(_sub2_cfg, "SUB2_CODEX_API_TOKEN", "") or getattr(_sub2_cfg, "SUB2API_API_KEY", "") or getattr(_sub2_cfg, "SUB2API_API_TOKEN", "") or "").strip()
    auth_header = str(getattr(_sub2_cfg, "SUB2_CODEX_AUTH_HEADER", "") or getattr(_sub2_cfg, "SUB2API_API_AUTH_HEADER", "x-api-key") or "x-api-key").strip()
    auth_prefix = str(getattr(_sub2_cfg, "SUB2_CODEX_AUTH_PREFIX", "") or getattr(_sub2_cfg, "SUB2API_API_AUTH_PREFIX", "") or "").strip()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "turb-gpt-free-register/codex-sub2",
    }
    if token:
        headers[auth_header] = f"{auth_prefix} {token}".strip() if auth_prefix else token
    return headers


def _sub2_codex_request_json(method: str, path: str, body: dict | None = None) -> dict:
    from config import sub2api as _sub2_cfg
    base = _sub2_codex_base()
    timeout = int(getattr(_sub2_cfg, "SUB2API_API_TIMEOUT", 20) or 20)
    normalized_path = "/" + str(path or "").lstrip("/")
    url = f"{base}{normalized_path}"
    session = curl_requests.Session()
    try:
        resp = session.request(
            method.upper(),
            url,
            headers=_sub2_codex_headers(),
            data=None if body is None else json.dumps(body),
            timeout=timeout,
        )
        try:
            payload = resp.json()
        except Exception:
            payload = {}
        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(f"[Codex][sub2] 管理接口失败 status={resp.status_code} category=http_error")
        return payload if isinstance(payload, dict) else {}
    finally:
        try:
            session.close()
        except Exception:
            pass


def _request_sub2_authorize_url() -> dict:
    """从 sub2 生成 Codex OAuth 授权地址；本地不生成 PKCE。"""
    from config import sub2api as _sub2_cfg
    path = str(getattr(_sub2_cfg, "SUB2_CODEX_AUTH_URL_PATH", "/api/v1/admin/openai/generate-auth-url") or "/api/v1/admin/openai/generate-auth-url")
    logger.info("[Codex][sub2] 正在通过 sub2 接口生成授权地址...")
    payload = _sub2_codex_request_json("POST", path, {})
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    auth_url = _first_non_empty(
        payload.get("url"), payload.get("auth_url"), payload.get("authUrl"),
        data.get("url"), data.get("auth_url"), data.get("authUrl"),
    )
    session_id = _first_non_empty(
        payload.get("session_id"), payload.get("sessionId"),
        data.get("session_id"), data.get("sessionId"),
    )
    state = _first_non_empty(
        payload.get("state"), payload.get("auth_state"), payload.get("authState"),
        data.get("state"), data.get("auth_state"), data.get("authState"),
        _extract_state_from_auth_url(auth_url),
    )
    if not auth_url.startswith("http"):
        raise RuntimeError("[Codex][sub2] sub2 未返回有效 auth_url")
    if not state:
        raise RuntimeError("[Codex][sub2] 授权地址缺少 state")
    logger.info("[Codex][sub2] 已获取授权地址 path=%s", urlparse(auth_url).path or "-")
    if not session_id:
        logger.warning("[Codex][sub2] 授权地址响应缺少 session_id，后续 exchange-code 可能失败")
    return {"auth_url": auth_url, "state": state, "session_id": session_id, "origin": _sub2_codex_base(), "raw": payload}


def _summarize_sub2_response(payload: dict) -> str:
    """仅记录回调响应的布尔状态，避免返回的凭据进入日志。"""
    if not isinstance(payload, dict):
        return "已响应"
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    success = payload.get("success")
    if not isinstance(success, bool):
        success = data.get("success")
    if isinstance(success, bool):
        return f"success={str(success).lower()}"
    return "已响应"


def _submit_sub2_callback(callback_url: str, *, session_id: str = "", redirect_uri: str = "") -> dict:
    """提交 OAuth callback 给 sub2。"""
    from config import sub2api as _sub2_cfg
    path = str(getattr(_sub2_cfg, "SUB2_CODEX_CALLBACK_PATH", "/api/v1/admin/openai/create-from-oauth") or "/api/v1/admin/openai/create-from-oauth")
    mode = str(getattr(_sub2_cfg, "SUB2_CODEX_CALLBACK_PAYLOAD_MODE", "create_from_oauth") or "create_from_oauth").strip().lower()
    if mode == "callback_url":
        body = {"callback_url": str(callback_url or "").strip()}
    elif mode == "redirect_url":
        body = {"redirect_url": str(callback_url or "").strip()}
    else:
        parsed = urlparse(str(callback_url or ""))
        qs = parse_qs(parsed.query)
        code = (qs.get("code") or [""])[0]
        state = (qs.get("state") or [""])[0]
        if not session_id:
            raise RuntimeError("[Codex][sub2] exchange-code 缺少 session_id")
        if not code:
            raise RuntimeError("[Codex][sub2] callback_url 缺少 code")
        if not state:
            raise RuntimeError("[Codex][sub2] callback_url 缺少 state")
        body = {"session_id": session_id, "code": code, "state": state}
        if redirect_uri:
            body["redirect_uri"] = redirect_uri
        if mode in {"create_from_oauth", "create-from-oauth", "create_oauth_account"}:
            body.setdefault("concurrency", 3)
            body.setdefault("priority", 50)

    max_attempts = max(1, int(getattr(_cfg, "CPA_CALLBACK_SUBMIT_RETRIES", 5) or 5))
    base_delay = max(1.0, float(getattr(_cfg, "CPA_CALLBACK_SUBMIT_RETRY_DELAY", 6) or 6))
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("[Codex][sub2] 正在上传 OAuth callback（第 %s/%s 次）", attempt, max_attempts)
            payload = _sub2_codex_request_json("POST", path, body)
            logger.info("[Codex][sub2] callback 已上传并处理完成（第 %s 次成功）响应=%s", attempt, _summarize_sub2_response(payload))
            return payload
        except Exception as exc:
            last_exc = exc
            retryable = _is_cpa_callback_retryable(exc)
            if attempt >= max_attempts or not retryable:
                logger.warning("[Codex][sub2] callback 上传失败且不再重试：attempt=%s/%s retryable=%s error=%s", attempt, max_attempts, retryable, exc)
                raise
            delay = base_delay * attempt
            logger.warning("[Codex][sub2] callback 上传失败，将在 %.1fs 后重试：attempt=%s/%s error=%s", delay, attempt, max_attempts, exc)
            time.sleep(delay)
    raise RuntimeError(f"[Codex][sub2] callback 上传失败：{last_exc}")



def _cpa_request_raw(method: str, path: str, body: dict | None = None, *, response_type: str = "text",
                     download_phase: str = ""):
    """调用 CPA 管理接口并返回原始响应；用于下载 auth-files 这类非 JSON 响应。"""
    origin = _cpa_management_origin()
    key = _cpa_management_key()
    timeout = int(getattr(_cfg, "CPA_REQUEST_TIMEOUT", 30) or 30)
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "X-Management-Key": key,
    }
    url = f"{origin}{path}"
    session = curl_requests.Session(curl_infos=cpa_download.CURL_INFOS) if download_phase else curl_requests.Session()
    try:
        resp = cpa_download.send(
            session,
            method.upper(),
            url,
            phase=download_phase,
            headers=headers,
            data=None if body is None else json.dumps(body),
            timeout=timeout,
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(
                f"[Codex][CPA] 管理接口失败 status={resp.status_code} category=http_error"
            )
        if response_type == "bytes":
            return resp.content
        return resp.text
    finally:
        try:
            session.close()
        except Exception:
            pass


def list_cpa_codex_auth_files(*, observe_web_download: bool = False) -> list[dict]:
    """读取 CPA auth-files 列表，仅返回 type/name/email 可识别为 codex 的凭证。"""
    payload = _cpa_request_json(
        "GET", "/v0/management/auth-files", download_phase="auth_files" if observe_web_download else "",
    )
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    out = []
    for item in files:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        ftype = str(item.get("type") or "").strip().lower()
        email = str(item.get("email") or "").strip().lower()
        if ftype == "codex" or name.lower().startswith("codex-") or "codex" in name.lower():
            copied = dict(item)
            copied["name"] = name
            copied["email"] = email or str(item.get("email") or "")
            out.append(copied)
    return out


def find_cpa_codex_auth_file(
    *, email: str = "", local_filename: str = "", observe_web_download: bool = False,
    files: list[dict] | None = None,
) -> dict | None:
    """按本地回执/凭证文件名或邮箱匹配 CPA 侧 codex auth 文件。"""
    email_l = str(email or "").strip().lower()
    local_name_l = str(local_filename or "").strip().lower()
    local_stem_l = local_name_l[:-5] if local_name_l.endswith(".json") else local_name_l
    if files is None:
        files = list_cpa_codex_auth_files(observe_web_download=observe_web_download)

    def score(item: dict) -> int:
        name_l = str(item.get("name") or "").lower()
        item_email_l = str(item.get("email") or "").lower()
        s = 0
        if local_name_l and name_l == local_name_l:
            s = max(s, 100)
        if local_stem_l and name_l.startswith(local_stem_l):
            s = max(s, 80)
        if email_l and item_email_l == email_l:
            s = max(s, 70)
        if email_l and email_l in name_l:
            s = max(s, 60)
        # 本地 CPA 回执名一般是 codex-邮箱-cpa-callback.json，CPA 实际文件是 codex-邮箱-free.json。
        if local_stem_l.endswith("-cpa-callback"):
            base = local_stem_l[:-len("-cpa-callback")]
            if base and name_l.startswith(base + "-"):
                s = max(s, 75)
        return s

    best_score, best_file = max(((score(item), item) for item in files), key=lambda pair: pair[0], default=(0, None))
    return best_file if best_score > 0 else None


def download_cpa_codex_auth_text(
    *, cpa_name: str | None = None, email: str = "", local_filename: str = "", observe_web_download: bool = False,
    files: list[dict] | None = None,
) -> tuple[str, str, dict]:
    """
    从 CPA auth-files 下载一个 Codex JSON 文本。
    Returns: (content_text, download_filename, matched_file_meta)
    """
    meta = None
    name = str(cpa_name or "").strip()
    if name:
        # 已经拿到 CPA 文件名时直接下载，不再额外拉取一次 auth-files 列表。
        # 账号列表批量下载会先统一列一次列表；这里重复列会导致选中多账号时浏览器长时间等待下载确认。
        meta = {"name": name}
    else:
        meta = find_cpa_codex_auth_file(
            email=email, local_filename=local_filename, observe_web_download=observe_web_download, files=files,
        )
        name = str((meta or {}).get("name") or "").strip()
    if not name:
        target = email or local_filename or cpa_name or "未知"
        raise RuntimeError(f"[Codex][CPA] 未在 CPA auth-files 中找到匹配的 Codex 凭证: {target}")
    text = _cpa_request_raw(
        "GET", f"/v0/management/auth-files/download?name={quote(name, safe='')}",
        response_type="text", download_phase="auth_file_download" if observe_web_download else "",
    )
    # 下载接口正常应返回 JSON 文本，这里做一次轻校验，避免把 HTML/错误文本当凭证导出。
    try:
        parsed = json.loads(text)
    except Exception as exc:
        raise RuntimeError(f"[Codex][CPA] CPA 下载内容不是有效 JSON: {name}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"[Codex][CPA] CPA 下载内容不是 JSON 对象: {name}")
    return json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", name, (meta or {"name": name})


def _capture_cpa_credential_baseline(email: str) -> dict:
    """在开始新授权前记录 CPA 凭证内容指纹，用于排除旧凭证假阳性。"""
    try:
        meta = find_cpa_codex_auth_file(email=email)
        if not meta:
            return {"captured": True, "fingerprint": "", "name": ""}
        text, name, _ = download_cpa_codex_auth_text(cpa_name=str(meta.get("name") or ""))
        return {
            "captured": True,
            "fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "name": name,
        }
    except Exception as exc:
        logger.warning("[Codex][CPA] 授权前凭证基线读取失败，本次不做自动成功确认：%s", str(exc)[:180])
        return {"captured": False, "fingerprint": "", "name": ""}


def _confirm_cpa_credential_after_callback(email: str, baseline: dict) -> Path | None:
    """有界轮询 CPA，下载、校验并保存本次新产生的真实凭证。"""
    if not baseline or not baseline.get("captured"):
        return None
    timeout = max(0, min(30, int(getattr(_cfg, "CPA_CREDENTIAL_CONFIRM_TIMEOUT", 12) or 12)))
    deadline = time.monotonic() + timeout
    baseline_hash = str(baseline.get("fingerprint") or "")
    while True:
        try:
            text, _name, _meta = download_cpa_codex_auth_text(email=email)
            fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
            payload = json.loads(text)
            usable = _extract_cpa_auth_json({"auth_json": payload})
            if usable and fingerprint != baseline_hash:
                effective_email = str(usable.get("email") or email)
                plan = str(usable.get("plan_type") or usable.get("chatgpt_plan_type") or "")
                return save_codex_credential(usable, effective_email, plan)
        except Exception as exc:
            logger.debug("[Codex][CPA] 等待远端凭证确认：%s", str(exc)[:160])
        if time.monotonic() >= deadline:
            return None
        # Callback 已经交给远端，此处故意完成有界对账再响应取消，避免把未知远端状态
        # 错报成“完全取消”。最长等待由 CPA_CREDENTIAL_CONFIRM_TIMEOUT 限制。
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))

def _first_non_empty(*values) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _extract_state_from_auth_url(auth_url: str) -> str:
    try:
        return parse_qs(urlparse(auth_url).query).get("state", [""])[0]
    except Exception:
        return ""


def _request_cpa_authorize_url() -> dict:
    """从 CPA 生成 Codex OAuth 授权地址；本地不生成 PKCE。"""
    logger.info("[Codex][CPA] 正在通过 CPA 管理接口生成授权地址...")
    payload = _cpa_request_json("GET", "/v0/management/codex-auth-url")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    auth_url = _first_non_empty(
        payload.get("url"),
        payload.get("auth_url"),
        payload.get("authUrl"),
        data.get("url"),
        data.get("auth_url"),
        data.get("authUrl"),
    )
    state = _first_non_empty(
        payload.get("state"),
        payload.get("auth_state"),
        payload.get("authState"),
        data.get("state"),
        data.get("auth_state"),
        data.get("authState"),
        _extract_state_from_auth_url(auth_url),
    )
    if not auth_url.startswith("http"):
        raise RuntimeError("[Codex][CPA] CPA 未返回有效 auth_url")
    if not state:
        raise RuntimeError("[Codex][CPA] CPA 授权地址缺少 state")
    logger.info("[Codex][CPA] 已获取授权地址 path=%s", urlparse(auth_url).path or "-")
    return {
        "auth_url": auth_url,
        "state": state,
        "origin": _cpa_management_origin(),
        "raw": payload,
    }


def _is_cpa_callback_retryable(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return (
        "status=409" in text
        or "timeout waiting for oauth callback" in text
        or "timeout" in text
        or "timed out" in text
        or "connection" in text
        or "status=429" in text
        or "status=500" in text
        or "status=502" in text
        or "status=503" in text
        or "status=504" in text
    )


def _is_cpa_callback_reauth_error(exc_or_text) -> bool:
    """CPA 收到 callback 后仍 409 timeout，通常需要重新生成授权地址重新跑一轮 OAuth。"""
    text = str(exc_or_text or "").lower()
    return (
        "status=409" in text and "category=oauth_callback_timeout" in text
    ) or (
        "oauth-callback" in text
        and "status=409" in text
        and "timeout waiting for oauth callback" in text
    ) or (
        "timeout waiting for oauth callback" in text
    )


def _submit_cpa_callback(callback_url: str) -> dict:
    """提交 OAuth callback 给 CPA。

    CPA 偶发会在浏览器已拿到 localhost callback 后仍返回
    “409 Timeout waiting for OAuth callback”，通常是管理端等待/入库的竞态；
    这里按同一个 callback URL 做多次重试，不重新生成授权地址。
    """
    body = {
        "provider": "codex",
        "redirect_url": str(callback_url or "").strip(),
    }
    max_attempts = max(1, int(getattr(_cfg, "CPA_CALLBACK_SUBMIT_RETRIES", 5) or 5))
    base_delay = max(1.0, float(getattr(_cfg, "CPA_CALLBACK_SUBMIT_RETRY_DELAY", 6) or 6))
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(
                "[Codex][CPA] 正在提交 OAuth callback 给 CPA（第 %s/%s 次）",
                attempt, max_attempts,
            )
            payload = _cpa_request_json("POST", "/v0/management/oauth-callback", body)
            logger.info("[Codex][CPA] callback 已提交（第 %s 次成功）", attempt)
            return payload
        except Exception as exc:
            last_exc = exc
            retryable = _is_cpa_callback_retryable(exc)
            if attempt >= max_attempts or not retryable:
                logger.warning(
                    "[Codex][CPA] callback 提交失败且不再重试：attempt=%s/%s retryable=%s error=%s",
                    attempt, max_attempts, retryable, exc
                )
                raise
            delay = base_delay * attempt
            logger.warning(
                "[Codex][CPA] callback 提交失败，将在 %.1fs 后重试：attempt=%s/%s error=%s",
                delay, attempt, max_attempts, exc
            )
            time.sleep(delay)
    raise RuntimeError(f"[Codex][CPA] callback 提交失败：{last_exc}")


# ============================================================
# 小工具：判定/解析
# ============================================================

def _is_redirect_uri(location: str) -> bool:
    """判断 Location 是否指向注册的 redirect_uri（localhost:1455/auth/callback）。"""
    from core.kernels.protocol.local.codex_oauth import _is_redirect_uri as execute

    return execute(_protocol_execution_context(), location)


def _extract_code(location: str, state: str) -> str:
    """从 redirect_uri 的 Location 里提取并校验 code。"""
    from core.kernels.protocol.local.codex_oauth import _extract_code as execute

    return execute(_protocol_execution_context(), location, state)


def _decode_jwt_segment(seg: str) -> dict:
    """base64url 解码一个 JWT/cookie 段为 JSON dict（失败返回 {}）。"""
    from core.kernels.protocol.local.codex_oauth import _decode_jwt_segment as execute

    return execute(_protocol_execution_context(), seg)


def _post_json(session: BrowserSession, url: str, payload: dict, referer: str,
               sentinel_header: str | None = None, so_header: str | None = None):
    """统一发 /api/accounts/* 的 JSON POST。"""
    from core.kernels.protocol.local.codex_oauth import _post_json as execute

    return execute(_protocol_execution_context(), session, url, payload, referer, sentinel_header, so_header)


def _resp_json(resp) -> dict:
    from core.kernels.protocol.local.codex_oauth import _resp_json as execute

    return execute(_protocol_execution_context(), resp)


def _decode_auth_session_metadata(value) -> dict:
    """把响应中的 oai-client-auth-session 转成 workspace payload。"""
    from core.kernels.protocol.local.codex_oauth import _decode_auth_session_metadata as execute

    return execute(_protocol_execution_context(), value)


def _cache_auth_session_metadata(session: BrowserSession, resp) -> None:
    """缓存 Auth 响应携带的 session 元数据，供 cookie 尚未落地时恢复 workspace。"""
    from core.kernels.protocol.local.codex_oauth import _cache_auth_session_metadata as execute

    return execute(_protocol_execution_context(), session, resp)


def _cache_auth_session_payload(
    session: BrowserSession, payload: dict | None, *, base_url: str | None = "https://auth.openai.com/",
) -> None:
    """仅保留用于工作区选择的 ID，不保存响应中的其他字段。"""
    from core.kernels.protocol.local.codex_oauth import _cache_auth_session_payload as execute

    return execute(_protocol_execution_context(), session, payload, base_url=base_url)


# ============================================================
# 步骤 0：用全新 session 跟随 Codex authorize URL，建立 auth.openai.com 会话
# ============================================================

def _bootstrap_authorize(
    session: BrowserSession,
    state: str,
    code_challenge: str | None = None,
    auth_url: str | None = None,
) -> None:
    """
    GET Codex authorize URL 并跟随重定向，落到登录页，建立 auth.openai.com cookies
    （含 oai-client-auth-session：内含 Codex 目标 + 后续要用的 workspace 列表）。
    """
    # 默认使用调用方传入的 CPA 授权地址；未传时才走保留的本地 PKCE 生成逻辑。
    from core.kernels.protocol.local.codex_oauth import _bootstrap_authorize as execute

    return execute(_protocol_execution_context(), session, state, code_challenge, auth_url)


# ============================================================
# 步骤 1：提交邮箱并确认下一步登录挑战
# ============================================================

def _authorize_login_step(result: dict) -> tuple[str, str]:
    """按服务端给出的页面和下一步地址识别登录挑战。"""
    from core.kernels.protocol.local.codex_oauth import _authorize_login_step as execute

    return execute(_protocol_execution_context(), result)


def _confirm_email_step(
    session: BrowserSession,
    step: str,
    continue_url: str,
    after_ts: float,
    *,
    referer: str = "https://auth.openai.com/log-in",
) -> tuple[str, str, float]:
    """只沿受信任的发码地址建立邮箱验证码页。"""
    from core.kernels.protocol.local.codex_oauth import _confirm_email_step as execute

    return execute(_protocol_execution_context(), session, step, continue_url, after_ts, referer=referer)


def _submit_email(
    session: BrowserSession, email: str, *, login_totp_secret: str | None = None
) -> tuple[str, str, float]:
    """POST authorize/continue，返回已确认的下一步登录挑战。"""
    from core.kernels.protocol.local.codex_oauth import _submit_email as execute

    return execute(_protocol_execution_context(), session, email, login_totp_secret=login_totp_secret)


def _verify_saved_login_password(
    session: BrowserSession, email: str, continue_url: str = "", *,
    login_password: str | None = None,
    login_totp_secret: str | None = None,
) -> tuple[str, str, float]:
    """使用本轮或已保存的 OpenAI 密码，并识别服务端下一步。"""
    from core.kernels.protocol.local.codex_oauth import _verify_saved_login_password as execute

    return execute(
        _protocol_execution_context(),
        session,
        email,
        continue_url,
        login_password=login_password,
        login_totp_secret=login_totp_secret,
    )


def _verify_saved_login_mfa(
    session: BrowserSession, email: str, result: dict, continue_url: str, *,
    login_totp_secret: str | None = None,
) -> tuple[str, str, float]:
    """在当前 Codex Auth 会话完成 TOTP，保留后续 OAuth 地址供本驱动处理。"""
    from core.kernels.protocol.local.codex_oauth import _verify_saved_login_mfa as execute

    return execute(
        _protocol_execution_context(),
        session,
        email,
        result,
        continue_url,
        login_totp_secret=login_totp_secret,
    )


# ============================================================
# 步骤 2：提交邮箱 OTP
# ============================================================

def _submit_email_otp(session: BrowserSession, code: str) -> dict:
    """POST email-otp/validate 提交邮箱验证码。带 sentinel(authorize_continue)。"""
    from core.kernels.protocol.local.codex_oauth import _submit_email_otp as execute

    return execute(_protocol_execution_context(), session, code)


# ============================================================
# 步骤 3-4：手机号验证（接码，失败换号重试）
# ============================================================

def _sms_provider_name() -> str:
    """当前接码通道名，仅用于 Codex 流程日志。"""
    return str(getattr(_cfg, "SMS_PROVIDER", "grizzly") or "grizzly").strip().lower()


def _sleep_before_phone_retry(
    attempt: int,
    max_retries: int,
    *,
    prefix: str = "[Codex]",
    deadline: float | None = None,
) -> None:
    """换号前随机等待，至少 3 秒，避免连续提交号码过快。"""
    if attempt >= max_retries:
        return
    seconds = random.uniform(3.0, 8.0)
    if deadline is not None:
        seconds = min(seconds, max(0.0, deadline - time.monotonic()))
    if seconds <= 0:
        return
    logger.info(f"{prefix} 换号前随机等待 {seconds:.1f} 秒")
    from core.operations.runtime import cancellable_sleep
    cancellable_sleep(seconds)


def _do_phone_verification(session: BrowserSession, *, phone_enabled: bool | None = None) -> dict:
    """
    用接码平台拿号 → add-phone/send 发短信 → 收码 → phone-otp/validate。
    发送失败、收码超时、验证码提交失败按原逻辑取消换号，最多 SMS_MAX_RETRIES 次。
    预算耗尽仅停止后续尝试，不覆盖最后一次明确失败的响应证据。

    实际平台适配在 core.sms.provider：
        - SMS_PROVIDER="grizzly"：GrizzlySMS handler_api.php
        - SMS_PROVIDER="l"：README“本地 L 接码服务”约定的 JSON 接口
    """
    _ensure_phone_verification_enabled(phone_enabled)
    http = sms_provider._http()
    max_retries = _cfg.SMS_MAX_RETRIES
    provider = _sms_provider_name()
    total_budget = max(30, int(getattr(_cfg, "CODEX_PHONE_TOTAL_TIMEOUT", 300) or 300))
    deadline = time.monotonic() + total_budget
    last_error = None
    unconfirmed_attempt_seen = False
    last_attempt = 0
    failure_stage = "phone_acquire"
    operation = "phone_provider"
    try:
        for attempt in range(1, max_retries + 1):
            last_attempt = attempt
            remaining = max(0, int(deadline - time.monotonic()))
            if remaining <= 0:
                if last_error:
                    logger.info("[Codex] 手机验证预算已耗尽，保留最后一次失败原因并停止继续尝试")
                    raise last_error
                raise CodexPhoneVerificationError(
                    operation=operation, failure_kind="budget_exhausted",
                    attempt=attempt, max_attempts=max_retries,
                )
            activation_id = None
            completed = False
            operation = "phone_provider"
            try:
                check_cancelled()
                failure_stage = "phone_acquire"
                activation_id, phone = sms_provider.acquire_number(http)
                failure_stage = "phone_otp"
                logger.info(
                    "[Codex] 手机验证尝试 %s/%s，provider=%s",
                    attempt, max_retries, provider,
                )

                # 发短信
                operation = "phone_send"
                report_stage("phone_otp", "已申请号码，正在请求发送短信验证码")
                send_resp = _post_json(
                    session,
                    "https://auth.openai.com/api/accounts/add-phone/send",
                    {"phone_number": f"+{phone}", "channel": "sms"},
                    referer="https://auth.openai.com/add-phone",
                )
                send_error = phone_failure_from_response(
                    send_resp, operation=operation, attempt=attempt, max_attempts=max_retries,
                    sensitive_values=(activation_id, phone, f"+{phone}"),
                )
                if send_error:
                    raise send_error

                # 通知平台短信已发出（status=1）
                operation = "phone_provider"
                sms_provider.set_status(activation_id, 1, http=http)

                # 定时轮询接码平台获取短信；单号与整段手机验证均受硬预算限制。
                operation = "phone_wait"
                report_stage("phone_otp", "短信发送请求已通过，正在等待短信验证码")
                logger.info(
                    "[Codex] 短信已发送，开始轮询验证码 wait=%ss interval=%ss",
                    _cfg.SMS_CODE_WAIT, _cfg.SMS_POLL_INTERVAL,
                )
                remaining = max(0, int(deadline - time.monotonic()))
                if remaining <= 0:
                    raise CodexPhoneVerificationError(
                        operation=operation, failure_kind="budget_exhausted",
                        attempt=attempt, max_attempts=max_retries,
                    )
                sms_code = sms_provider.wait_for_sms_code(
                    activation_id,
                    http,
                    max_wait=min(int(_cfg.SMS_CODE_WAIT), remaining),
                )

                # 验手机码
                operation = "phone_validate"
                report_stage("phone_otp", "已收到短信验证码，正在提交验证")
                val_resp = _post_json(
                    session,
                    "https://auth.openai.com/api/accounts/phone-otp/validate",
                    {"code": sms_code},
                    referer="https://auth.openai.com/phone-verification",
                )
                validation_error = phone_failure_from_response(
                    val_resp, operation=operation, attempt=attempt, max_attempts=max_retries,
                    sensitive_values=(activation_id, phone, f"+{phone}", sms_code),
                )
                if validation_error:
                    raise validation_error

                # 成功
                operation = "phone_provider"
                sms_provider.complete(activation_id, http)
                completed = True
                logger.info("[Codex] 手机号验证通过")
                return _resp_json(val_resp)

            except OperationCancelled:
                raise
            except CodexPhoneVerificationError as exc:
                if not exc.number_retry_allowed:
                    raise
                last_error = exc
            except sms_provider.SmsCodeTimeout:
                last_error = CodexPhoneVerificationError(
                    operation="phone_wait", failure_kind="sms_timeout",
                    attempt=attempt, max_attempts=max_retries, number_retry_allowed=True,
                )
            except sms_provider.SmsProviderError as exc:
                failure_kind = "provider_error"
                if isinstance(exc, sms_provider.SmsNoBalanceError):
                    failure_kind = "provider_no_balance"
                elif isinstance(exc, sms_provider.SmsPriceLimitError):
                    failure_kind = "provider_price_limit"
                elif isinstance(exc, sms_provider.SmsNoNumbersError):
                    failure_kind = "provider_no_numbers"
                error = CodexPhoneVerificationError(
                    operation="phone_provider", failure_kind=failure_kind,
                    attempt=attempt, max_attempts=max_retries,
                    number_retry_allowed=not isinstance(
                        exc, (sms_provider.SmsNoBalanceError, sms_provider.SmsPriceLimitError),
                    ),
                )
                if not error.number_retry_allowed:
                    raise error from None
                last_error = error
            except Exception as exc:
                is_transport = isinstance(exc, OSError) or _is_transient_network_error(exc)
                raise CodexPhoneVerificationError(
                    operation=operation,
                    failure_kind="transport_error" if is_transport else "unexpected_response",
                    attempt=attempt, max_attempts=max_retries,
                    server_message=type(exc).__name__,
                ) from None
            finally:
                if activation_id and last_error and last_error.diagnostics.get("attempt") == attempt:
                    try:
                        sms_provider.report_activation_failure(activation_id, last_error.diagnostics["failure_kind"])
                    except Exception as report_exc:
                        logger.warning("[Codex] 接码失败统计写回未确认 reason=%s", type(report_exc).__name__)
                if activation_id and not completed:
                    try:
                        sms_provider.cancel(activation_id, http, background=True)
                    except Exception as cleanup_exc:
                        logger.warning("[Codex] 接码订单取消未确认 reason=%s", type(cleanup_exc).__name__)

            if unconfirmed_attempt_seen:
                last_error.diagnostics["earlier_attempt_unconfirmed"] = True
            if (
                last_error.diagnostics.get("operation") in {"phone_send", "phone_validate"}
                and last_error.diagnostics.get("response_received") is True
                and not last_error.as_result()["remote_write_rejected"]
            ):
                unconfirmed_attempt_seen = True
            logger.warning("[Codex] 手机验证尝试 %s/%s 失败：%s", attempt, max_retries, last_error)
            report_stage(
                failure_stage,
                f"手机验证第 {attempt}/{max_retries} 次尝试失败：{last_error}",
                state="running", level="WARNING",
                detail={"cause_code": "codex_phone_verification_failed", "auth_diagnostics": last_error.diagnostics},
            )
            _sleep_before_phone_retry(attempt, max_retries, deadline=deadline)

        budget_exhausted = time.monotonic() >= deadline
        if budget_exhausted:
            logger.info("[Codex] 手机验证预算已耗尽，已停止继续尝试")
        if last_error:
            raise last_error
        if budget_exhausted:
            raise CodexPhoneVerificationError(
                operation=operation, failure_kind="budget_exhausted",
                attempt=last_attempt, max_attempts=max_retries,
            )
        raise CodexPhoneVerificationError(
            operation=operation, failure_kind="retry_exhausted",
            attempt=last_attempt, max_attempts=max_retries,
        )
    except CodexPhoneVerificationError as exc:
        if unconfirmed_attempt_seen:
            exc.diagnostics["earlier_attempt_unconfirmed"] = True
        report_stage(
            failure_stage,
            str(exc), state="failed", level="ERROR",
            detail={"cause_code": "codex_phone_verification_failed", "auth_diagnostics": exc.diagnostics},
        )
        raise
    finally:
        http.close()


# ============================================================
# 步骤 5：选 workspace → 拿 callback code
# ============================================================

def _current_workspace_id(session: BrowserSession) -> tuple[str, str, bool]:
    """只读取当前会话已确认的工作区 ID；不发请求、不等待。"""
    from core.kernels.protocol.local.codex_oauth import _current_workspace_id as execute

    return execute(_protocol_execution_context(), session)


def _confirmed_consent_workspace_id(session: BrowserSession) -> str:
    """确认 Cookie 与本轮 Auth 元数据中只有一个一致的工作区。"""
    from core.kernels.protocol.local.codex_oauth import _confirmed_consent_workspace_id as execute

    return execute(_protocol_execution_context(), session)


def _get_workspace_id(session: BrowserSession) -> str:
    """
    优先从 oai-client-auth-session cookie 解出 workspace；cookie 尚未落地时，
    退回 Auth 响应元数据，并在有界时间内等待 cookie/响应状态完成。
    """
    from core.kernels.protocol.local.codex_oauth import _get_workspace_id as execute

    return execute(_protocol_execution_context(), session)


def _extract_continue_url(result: dict | None) -> str:
    """从 Auth JSON 响应中提取 continue/redirect URL。"""
    from core.kernels.protocol.local.codex_oauth import _extract_continue_url as execute

    return execute(_protocol_execution_context(), result)


def _url_path_for_log(value: str | None) -> str:
    """仅保留 URL path，避免日志记录 OAuth state/code 等 query 参数。"""
    from core.kernels.protocol.local.codex_oauth import _url_path_for_log as execute

    return execute(_protocol_execution_context(), value)


def _login_target(value: str, *, base_url: str = "https://auth.openai.com/") -> tuple[str, bool]:
    """沿服务端返回地址继续登录，不按域名白名单阻断后续跳转。"""
    from core.kernels.protocol.local.codex_oauth import _login_target as execute

    return execute(_protocol_execution_context(), value, base_url=base_url)


def _login_target_for_log(value: str, *, base_url: str = "https://auth.openai.com/") -> str:
    """记录跳转结构，省略凭据、查询值及未知路径中的动态标识。"""
    from core.kernels.protocol.local.codex_oauth import _login_target_for_log as execute

    return execute(_protocol_execution_context(), value, base_url=base_url)


def _safe_login_path(value: str | None) -> str:
    """诊断仅保留已知路径，动态挑战 ID 与查询参数一律不写日志。"""
    from core.kernels.protocol.local.codex_oauth import _safe_login_path as execute

    return execute(_protocol_execution_context(), value)


def _login_session_presence(session: BrowserSession) -> tuple[bool, bool]:
    """脱敏诊断只报告 Auth Cookie 和工作区缓存是否存在。"""
    from core.kernels.protocol.local.codex_oauth import _login_session_presence as execute

    return execute(_protocol_execution_context(), session)


def _login_page_type_for_log(payload: dict) -> str:
    from core.kernels.protocol.local.codex_oauth import _login_page_type_for_log as execute

    return execute(_protocol_execution_context(), payload)


def _follow_login_continue_step(
    session: BrowserSession, continue_url: str, state: str,
) -> tuple[str, str]:
    """逐跳识别登录后续；工作区步骤可携带授权页已确认的 ID。"""
    from core.kernels.protocol.local.codex_oauth import _follow_login_continue_step as execute

    return execute(_protocol_execution_context(), session, continue_url, state)


def _follow_login_continue(session: BrowserSession, continue_url: str, state: str) -> str | None:
    """兼容旧调用方：仅在确认 callback 后返回 URL。"""
    from core.kernels.protocol.local.codex_oauth import _follow_login_continue as execute

    return execute(_protocol_execution_context(), session, continue_url, state)


def _select_workspace_and_get_callback(
    session: BrowserSession, state: str, *, workspace_id: str | None = None,
    phone_enabled: bool | None = None,
) -> str:
    """
    POST workspace/select，然后跟随后续重定向/响应里的 URL 直到命中 localhost:1455 callback。
    返回完整 callback URL（含 code）。
    """
    from core.kernels.protocol.local.codex_oauth import _select_workspace_and_get_callback as execute

    return execute(
        _protocol_execution_context(),
        session,
        state,
        workspace_id=workspace_id,
        phone_enabled=phone_enabled,
    )


def _follow_until_callback(
    session: BrowserSession, url: str, state: str, *, phone_enabled: bool | None = None,
) -> str:
    """从给定 URL 起逐跳跟随，命中 localhost:1455 callback 时返回其 Location。"""
    from core.kernels.protocol.local.codex_oauth import _follow_until_callback as execute

    return execute(_protocol_execution_context(), session, url, state, phone_enabled=phone_enabled)


# ============================================================
# 换 token（对照 CLIProxyAPI ExchangeCodeForTokensWithRedirect）—— 未改动
# ============================================================

def exchange_codex_token(session: BrowserSession, code: str, code_verifier: str) -> dict:
    """用 authorization code 换 token。"""
    from core.kernels.protocol.local.codex_oauth import exchange_codex_token as execute

    return execute(_protocol_execution_context(), session, code, code_verifier)


# ============================================================
# 解析 id_token / 落盘 —— 未改动
# ============================================================

def _parse_id_token(id_token: str) -> dict:
    """base64 解码 JWT payload（不验签），抽 email / account_id / plan_type。"""
    if not id_token:
        return {}
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return {}
        claims = _decode_jwt_segment(parts[1])
    except Exception as exc:
        logger.warning(f"[Codex] id_token 解析失败: {exc}")
        return {}

    auth_claim = claims.get("https://api.openai.com/auth", {}) or {}
    profile_claim = claims.get("https://api.openai.com/profile", {}) or {}
    # OpenAI 新版 id_token 的 email 在顶层 claim；旧版/CLIProxyAPI 实现里在 profile_claim。
    # 顶层优先，否则回退 profile_claim，避免落盘的 codex-邮箱.json 里 email 字段为空。
    email_value = claims.get("email") or profile_claim.get("email", "")
    return {
        "email": email_value,
        "account_id": auth_claim.get("chatgpt_account_id", ""),
        "plan_type": auth_claim.get("chatgpt_plan_type", ""),
    }


def build_codex_storage(token_resp: dict, id_claims: dict) -> dict:
    """组装 CLIProxyAPI CodexTokenStorage JSON 结构。"""
    expires_in = token_resp.get("expires_in", 0) or 0
    expired_dt = datetime.now(timezone.utc) + _timedelta_seconds(expires_in)
    last_refresh_dt = datetime.now(timezone.utc)
    return {
        "id_token": token_resp.get("id_token", ""),
        "access_token": token_resp.get("access_token", ""),
        "refresh_token": token_resp.get("refresh_token", ""),
        "account_id": id_claims.get("account_id", ""),
        "last_refresh": last_refresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "email": id_claims.get("email", ""),
        "type": "codex",
        "expired": expired_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _timedelta_seconds(seconds: int):
    from datetime import timedelta
    return timedelta(seconds=int(seconds))


def _credential_file_name(email: str, plan_type: str) -> str:
    """对照 CLIProxyAPI filename.go：无 plan→codex-{email}.json，否则带 plan 后缀。"""
    email = (email or "").strip()
    plan = (plan_type or "").strip().lower()
    if plan == "":
        return f"codex-{email}.json"
    return f"codex-{email}-{plan}.json"


def save_codex_credential(storage: dict, email: str, plan_type: str) -> Path:
    """保存 Codex 凭证到数据库；返回兼容路径标识，不生成本地文件。"""
    out_dir = _PROJECT_ROOT / _cfg.CODEX_OUTPUT_DIRNAME
    fname = _credential_file_name(email, plan_type)
    path = out_dir / fname
    from core import db
    db.save_codex_credential_record(fname, storage)
    return path


def _extract_cpa_auth_json(payload: dict) -> dict | None:
    """
    尝试从 CPA oauth-callback 响应里提取完整授权文件。
    不同 CPA 版本字段名可能不同；只要看起来是 codex auth json 就落本地。
    """
    if not isinstance(payload, dict):
        return None
    candidates = [
        payload.get("auth_json"),
        payload.get("authJson"),
        payload.get("auth"),
        payload.get("auth_file"),
        payload.get("authFile"),
        payload.get("file"),
        payload.get("data"),
    ]
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    candidates.extend([
        data.get("auth_json"),
        data.get("authJson"),
        data.get("auth"),
        data.get("auth_file"),
        data.get("authFile"),
        data.get("file"),
    ])
    for item in candidates:
        if isinstance(item, dict) and (
            item.get("type") == "codex"
            or item.get("access_token")
            or item.get("refresh_token")
            or item.get("id_token")
        ):
            return item
    return None


def _save_cpa_local_record(
    *,
    email: str,
    callback_url: str,
    auth_url: str,
    state: str,
    submit_payload: dict,
) -> Path | None:
    """
    在数据库记录 CPA 授权结果：
      1) 如果 CPA 返回完整 auth json，保存为可用 Codex 凭证；
      2) 否则按配置单独保存 callback 提交回执，便于追踪 CPA 侧授权文件。
    """
    auth_json = _extract_cpa_auth_json(submit_payload)
    if auth_json:
        effective_email = auth_json.get("email") or email
        plan = auth_json.get("plan_type") or auth_json.get("chatgpt_plan_type") or ""
        return save_codex_credential(auth_json, effective_email, plan)

    if not bool(getattr(_cfg, "CPA_SAVE_CALLBACK_RECEIPT", True)):
        return None

    out_dir = _PROJECT_ROOT / _cfg.CODEX_OUTPUT_DIRNAME
    safe_email = (email or "unknown").strip().replace("/", "_").replace("\\", "_")
    path = out_dir / f"codex-{safe_email}-cpa-callback.json"
    record = {
        "type": "codex_cpa_callback",
        "email": email,
        "state": state,
        "auth_url": auth_url,
        "callback_url": callback_url,
        "cpa_management_origin": _cpa_management_origin(),
        "cpa_submit_response": submit_payload,
        "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "授权地址由 CPA 生成；callback 已提交给 CPA。若 CPA 响应未包含 token，本记录仅为数据库回执。",
    }
    from core.storage import codex as codex_store
    codex_store.save_codex_callback_receipt(path.name, record, source="cpa")
    return path


def _save_sub2_local_record(
    *,
    email: str,
    callback_url: str,
    auth_url: str,
    state: str,
    submit_payload: dict,
) -> Path | None:
    """在数据库单独记录 sub2 回执；完整 auth json 则保存为可用 Codex 凭证。"""
    auth_json = _extract_cpa_auth_json(submit_payload)
    if auth_json:
        effective_email = auth_json.get("email") or email
        plan = auth_json.get("plan_type") or auth_json.get("chatgpt_plan_type") or ""
        return save_codex_credential(auth_json, effective_email, plan)

    if not bool(getattr(_cfg, "CPA_SAVE_CALLBACK_RECEIPT", True)):
        return None

    out_dir = _PROJECT_ROOT / _cfg.CODEX_OUTPUT_DIRNAME
    safe_email = (email or "unknown").strip().replace("/", "_").replace("\\", "_")
    path = out_dir / f"codex-{safe_email}-sub2-callback.json"
    try:
        sub2_origin = _sub2_codex_base()
    except Exception:
        sub2_origin = ""
    record = {
        "type": "codex_sub2_callback",
        "email": email,
        "state": state,
        "auth_url": auth_url,
        "callback_url": callback_url,
        "sub2_origin": sub2_origin,
        "sub2_submit_response": submit_payload,
        "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "授权地址由 sub2 生成；callback 已上传给 sub2。若 sub2 响应未包含 token，本记录仅为数据库回执。",
    }
    from core.storage import codex as codex_store
    codex_store.save_codex_callback_receipt(path.name, record, source="sub2")
    return path


def _remote_callback_result(
    *, source: str, email: str, callback_url: str, auth_url: str, state: str,
    submit_payload: dict, driver_message: str = "", cpa_baseline: dict | None = None,
) -> dict:
    """将 CPA/sub2 callback 与凭证确认分开。

    管理端接受 callback 只说明交接完成；只有响应中带有完整 auth JSON 并已写入
    codex_credentials，才允许把本次执行标记为 success。
    """
    auth_json = _extract_cpa_auth_json(submit_payload)
    if source == "cpa":
        path = _save_cpa_local_record(
            email=email, callback_url=callback_url, auth_url=auth_url,
            state=state, submit_payload=submit_payload,
        )
        default_message = "CPA callback submitted"
    elif source == "sub2":
        path = _save_sub2_local_record(
            email=email, callback_url=callback_url, auth_url=auth_url,
            state=state, submit_payload=submit_payload,
        )
        default_message = "sub2 callback uploaded"
    else:
        raise ValueError(f"不支持的远端 callback 来源: {source}")
    confirmed = auth_json is not None
    if source == "cpa" and not confirmed and cpa_baseline is not None:
        token = current_token()
        if token is not None:
            from core import operation_task_store

            operation_task_store.mark_run_settling(token.run_id)
        confirmed_path = _confirm_cpa_credential_after_callback(email, cpa_baseline)
        if confirmed_path is not None:
            path = confirmed_path
            confirmed = True
    message = str(
        submit_payload.get("message")
        or submit_payload.get("status_message")
        or default_message
    )
    if driver_message:
        message = f"{driver_message}: {message}"
    report_stage(
        "credential_confirm",
        "远端凭证已确认" if confirmed else "Callback 已接收，等待远端凭证确认",
        state="success" if confirmed else "failed",
        level="INFO" if confirmed else "WARNING",
    )
    return _codex_result(
        status="success" if confirmed else "attention_required",
        ok=confirmed,
        email=str((auth_json or {}).get("email") or email),
        file_path=str(path) if confirmed and path else None,
        receipt_path=str(path) if (not confirmed) and path else None,
        callback_url=callback_url,
        callback_submitted=True,
        credential_confirmed=confirmed,
        message=(message if confirmed else f"{message}；callback 已接收，等待远端凭证确认"),
    )


# ============================================================
# 入口
# ============================================================

@serialize_email_auth
def run_codex_oauth(
    email: str,
    otp_provider=None,
    proxy: str | None = None,
    force: bool = False,
    _cpa_reauth_round: int = 1,
    driver_override: str | None = None,
    allow_password_reset: bool = False,
    on_password_reset_submitted=None,
    *,
    login_password: str | None = None,
    login_totp_secret: str | None = None,
    phone_enabled: bool | None = None,
    diagnostic_after_mfa: bool = False,
) -> dict:
    """
    Codex OAuth 授权入口。Protocol 使用独立 BrowserSession，并根据服务端
    登录挑战选择密码、Authenticator 2FA、邮箱 OTP 或后续授权步骤。
    浏览器驱动仍按自身入口复用登录态。

    Args:
        email: 已注册成功的账号邮箱
        otp_provider: 邮箱 OTP 获取回调 fn(email, after_ts)->code，默认用 wait_for_otp
        proxy: 显式代理；不传时由账号功能代理服务按注册地区领取线路。
        force: True 时跳过 ENABLE_CODEX_AUTO 开关限制，供手动补跑使用
        login_password: 新注册本轮已知的 OpenAI 密码，仅在内存中传递。
        login_totp_secret: 新注册本轮启用的 TOTP secret，仅在内存中传递。
        phone_enabled: 入队时的手机接码开关；未传时读取当前配置。
        diagnostic_after_mfa: 本次登录仅在 MFA 后查询一次会话并停止，不申请号码。

    Returns:
        结构化结果 dict。已提交验证但结果未知时返回 attention_required。
    """
    if type(diagnostic_after_mfa) is not bool or (diagnostic_after_mfa and driver_override != "protocol"):
        return _codex_result(status="failed", email=email, message="MFA 诊断仅支持显式 protocol 驱动及布尔选项")
    if not force and not _cfg.ENABLE_CODEX_AUTO:
        return _codex_result(status="skipped", message="ENABLE_CODEX_AUTO=False")
    if not email:
        return _codex_result(status="skipped", message="email 为空")

    # 独立调用也必须遵守统一账号代理策略。以前 proxy=None 会在 BrowserSession
    # 里静默抽取 PROXY_POOL，导致已启用 1024Proxy 时仍命中 127.0.0.1 静态代理。
    # Protocol/Roxy OAuth 均使用统一账号代理策略。
    if proxy is None:
        from core import db
        from core.proxy.account_routes import acquire_account_proxy

        account = db.get_account_by_email(email) or {}
        route = acquire_account_proxy(
            account_id=int(account.get("id") or 0) or None,
            email=email,
            purpose="codex-oauth",
        )
        try:
            logger.info(
                "[Codex] 统一账号网络：provider=%s region=%s route=%s",
                route.provider,
                route.region or "-",
                route.public_dict().get("network_route"),
            )
            return run_codex_oauth(
                email,
                otp_provider=otp_provider,
                proxy=route.proxy_url,
                force=force,
                _cpa_reauth_round=_cpa_reauth_round,
                driver_override=driver_override,
                allow_password_reset=allow_password_reset,
                on_password_reset_submitted=on_password_reset_submitted,
                login_password=login_password,
                login_totp_secret=login_totp_secret,
                phone_enabled=phone_enabled,
                diagnostic_after_mfa=diagnostic_after_mfa,
            )
        finally:
            route.release(reason=f"codex-oauth-{email}")

    # Codex OAuth 只保留 protocol 与 Roxy；Roxy 用真实浏览器捕获 localhost callback。
    try:
        from config import codex as _codex_cfg
        from config import roxybrowser as _roxy_cfg
        oauth_driver = str(
            driver_override if driver_override is not None
            else getattr(_codex_cfg, "CODEX_OAUTH_DRIVER", "protocol")
        ).strip().lower()
        if oauth_driver == "same_as_registration":
            oauth_driver = str(getattr(_roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
            oauth_driver = registration_codex_driver(oauth_driver)
        if oauth_driver in ("roxy", "roxybrowser", "fingerprint", "browser"):
            from contracts.kernel_catalog import operation_binding
            from core.kernels.registry import resolve_operation_runner

            run_roxy_codex_oauth = resolve_operation_runner(
                operation_binding("codex_oauth", "roxy")
            )
            return run_roxy_codex_oauth(
                email,
                otp_provider=otp_provider,
                proxy=proxy,
                force=True,
                allow_password_reset=allow_password_reset,
                on_password_reset_submitted=on_password_reset_submitted,
                phone_enabled=phone_enabled,
            )
        if oauth_driver not in ("protocol", "api", "http"):
            raise RuntimeError(f"[Codex] 不支持的 CODEX_OAUTH_DRIVER={oauth_driver!r}，当前仅支持 protocol / roxy / same_as_registration")
    except ImportError:
        # 没装 selenium / 未提供 roxy 配置时继续走协议模式，保持旧行为。
        pass

    if otp_provider is None:
        from core.email.provider import wait_for_otp as otp_provider

    session_type = CodexDiagnosticSession if diagnostic_after_mfa else CodexAuthPageSession
    session = session_type(BrowserSession(proxy=proxy))
    try:
        check_cancelled()
        logger.info(f"[Codex] 开始授权（全新 session）：{email}")

        # 1. 授权地址
        #    默认由 CPA 生成（本地不生成 PKCE/state）；local 模式保留旧代码用于兼容。
        auth_source = _codex_auth_url_source()
        report_stage("auth_url", "开始获取 Codex 授权地址")
        cpa_auth = None
        cpa_baseline = None
        code_verifier = None
        code_challenge = None
        auth_url = None
        if auth_source == "cpa":
            cpa_baseline = _capture_cpa_credential_baseline(email)
            cpa_auth = _request_cpa_authorize_url()
            state = cpa_auth["state"]
            auth_url = cpa_auth["auth_url"]
            logger.info("[Codex] 当前使用 CPA 授权地址 path=%s", _url_path_for_log(auth_url))
        elif auth_source == "sub2":
            sub2_auth = _request_sub2_authorize_url()
            state = sub2_auth["state"]
            auth_url = sub2_auth["auth_url"]
            logger.info("[Codex] 当前使用 sub2 授权地址 path=%s", _url_path_for_log(auth_url))
        elif auth_source == "local":
            code_verifier, code_challenge = _generate_pkce()
            state = _generate_state()
            logger.info("[Codex] 当前使用本地 PKCE 生成授权地址")
        else:
            raise RuntimeError(f"[Codex] 不支持的 CODEX_AUTH_URL_SOURCE={auth_source!r}")
        report_stage("auth_url", "Codex 授权地址已准备", state="success", detail={"source": auth_source})

        # 2. 网络预检 + 建立会话。预检不携带邮箱，不触发 OTP；
        #    真正烧邮箱的 authorize/continue 只在预检成功后执行。
        network_preflight(session)
        report_stage("network", "OAuth 网络预检通过", state="success")
        human_delay("navigate")

        _bootstrap_authorize(session, state, code_challenge, auth_url=auth_url)
        human_delay("navigate")

        # 3. 提交邮箱，沿服务端返回的挑战处理密码或邮箱 OTP。
        login_step, login_continue, otp_after_ts = _submit_email(
            session, email, login_totp_secret=login_totp_secret
        )
        report_stage("login", "已提交 OpenAI 登录邮箱", state="success")
        human_delay("form")
        if login_step == "password":
            report_stage("login_password", "正在验证已保存的 OpenAI 登录密码")
            login_step, login_continue, otp_after_ts = _verify_saved_login_password(
                session, email, login_continue,
                login_password=login_password,
                login_totp_secret=login_totp_secret,
            )
            report_stage("login_password", "OpenAI 登录密码已通过", state="success")
        if login_step == "mfa":
            raise RuntimeError("[Codex] 登录下一步要求 MFA 验证，当前 Protocol OAuth 未执行该挑战")

        # 4. 仅在明确的邮箱验证码页收码；密码直接通过时跳过该步骤。
        if login_step == "verify":
            check_cancelled()
            report_stage("email_otp", "等待邮箱验证码")
            logger.info("[Codex] 等待邮箱 OTP")
            email_otp = call_cancellable(bind_auth_observer(otp_provider), email, after_ts=otp_after_ts)
            logger.info("[Codex] 已收到邮箱 OTP")
            human_delay("otp_input")
            otp_result = _submit_email_otp(session, email_otp)
            report_stage("email_otp", "邮箱验证码已通过", state="success")
            human_delay("api")
            if otp_result:
                login_step, login_continue = _authorize_login_step(otp_result)
                if login_step == "mfa":
                    login_step, login_continue, _ = _verify_saved_login_mfa(
                        session, email, otp_result, login_continue,
                        login_totp_secret=login_totp_secret,
                    )
                if login_step not in ("phone", "continue", "workspace", "consent", "callback"):
                    raise RuntimeError("[Codex] 邮箱验证码通过后出现未支持的登录挑战，已停止继续")
            else:
                raise RuntimeError("[Codex] 邮箱验证码通过后未返回明确下一步，已停止继续")
        elif login_step in ("continue", "workspace", "consent", "callback"):
            report_stage("email_otp", "当前登录已进入后续授权，无需邮箱验证码", state="skipped")
        elif login_step != "phone":
            raise RuntimeError("[Codex] 登录下一步未知，已停止等待邮箱验证码")

        if diagnostic_after_mfa:
            # 没有 MFA 的登录也必须在任何手机、授权或凭据动作之前停止。
            raise _CodexSessionDiagnosticComplete(session.snapshot())

        # 5-6. 仅按明确挑战处理手机、继续跳转和工作区选择。
        # 授权页须经 GET 确认且仅有一个一致的工作区，否则交给可交互驱动。
        phone_ran = False
        callback_url = ""
        for _ in range(_MAX_REDIRECTS):
            if login_step == "phone":
                if phone_ran:
                    raise RuntimeError("[Codex] 手机验证后仍停留在同一挑战，已停止重复提交")
                phone_ran = True
                report_stage("phone_check", "服务端要求手机号验证")
                phone_result = _do_phone_verification(session, phone_enabled=phone_enabled)
                if phone_result:
                    login_step, login_continue = _authorize_login_step(phone_result)
                else:
                    workspace_id, source, _ = _current_workspace_id(session)
                    if not workspace_id:
                        raise RuntimeError("[Codex] 手机验证码已通过，但未确认后续地址或工作区，已停止继续")
                    logger.info("[Codex] 手机验证响应无下一步，已确认工作区来源=%s", source)
                    login_step, login_continue = "workspace", ""
                report_stage("phone_check", "手机号验证已完成", state="success")
            elif login_step == "continue":
                login_step, login_continue = _follow_login_continue_step(
                    session, login_continue, state
                )
            elif login_step == "workspace":
                human_delay("post_auth")
                callback_url = _select_workspace_and_get_callback(
                    session, state, workspace_id=login_continue or None,
                    phone_enabled=phone_enabled,
                )
                break
            elif login_step == "callback":
                callback_url, is_callback = _login_target(login_continue)
                if not is_callback:
                    raise RuntimeError("[Codex] 服务端 callback 地址未获确认")
                break
            elif login_step == "consent":
                if login_continue:
                    login_step, login_continue = _follow_login_continue_step(
                        session, login_continue, state
                    )
                    if login_step != "consent":
                        continue
                raise CodexConsentUnverifiableError(
                    "[Codex] 已进入授权确认页，但服务端未返回可验证的下一步；需使用浏览器驱动"
                )
            else:
                raise RuntimeError("[Codex] 登录后续步骤未知，已停止继续")
        else:
            raise RuntimeError("[Codex] 登录后续步骤超过有界次数，已停止继续")
        if not phone_ran:
            report_stage("phone_check", "当前登录会话无需手机验证", state="skipped")

        report_stage("callback", "已捕获 OAuth callback", state="success")
        code = _extract_code(callback_url, state)
        logger.info("[Codex] 已取得 authorization code")

        # 7A. CPA 模式：把 callback URL 交给 CPA，由 CPA 持有 verifier 并完成换 token / 写 auth。
        #     本地不再用 code 换 token；仅保存 CPA 返回的授权文件或回调回执。
        if auth_source == "cpa":
            submit_payload = _submit_cpa_callback(callback_url)
            result = _remote_callback_result(
                source="cpa", email=email, callback_url=callback_url,
                auth_url=auth_url or "", state=state, submit_payload=submit_payload,
                cpa_baseline=cpa_baseline,
            )
            logger.info("[Codex][CPA] callback 处理完成：%s status=%s", email, result["status"])
            return result

        # 7A-sub2. sub2 模式：把 callback URL 上传给 sub2。
        if auth_source == "sub2":
            submit_payload = _submit_sub2_callback(
                callback_url,
                session_id=(sub2_auth or {}).get("session_id", ""),
                redirect_uri=(parse_qs(urlparse(auth_url or "").query).get("redirect_uri") or [""])[0],
            )
            result = _remote_callback_result(
                source="sub2", email=email, callback_url=callback_url,
                auth_url=auth_url or "", state=state, submit_payload=submit_payload,
            )
            logger.info("[Codex][sub2] callback 处理完成：%s status=%s", email, result["status"])
            return result

        # 7B. local 模式：保留旧实现，用本地 verifier 换 token 并保存 CPA 兼容授权文件。
        if not code_verifier:
            raise RuntimeError("[Codex] local 模式缺少 code_verifier")
        token_resp = exchange_codex_token(session, code, code_verifier)

        # 8. 解析 id_token + 落盘
        id_claims = _parse_id_token(token_resp.get("id_token", ""))
        effective_email = id_claims.get("email") or email
        storage = build_codex_storage(token_resp, id_claims)
        path = save_codex_credential(storage, effective_email, id_claims.get("plan_type", ""))
        report_stage("credential_persist", "Codex 凭证已写入数据库", state="success")

        logger.info(
            f"[Codex] 成功：{effective_email}，plan={id_claims.get('plan_type') or 'unknown'}, "
            f"account_id={id_claims.get('account_id') or 'unknown'}, 已保存到 {path}"
        )
        return _codex_result(
            status="success",
            ok=True,
            email=effective_email,
            file_path=str(path),
            callback_url=callback_url,
            message=f"plan={id_claims.get('plan_type') or 'unknown'}",
            credential_confirmed=True,
        )
    except _CodexSessionDiagnosticComplete as exc:
        report_stage("login_mfa", str(exc), state="success" if exc.detail.get("mfa_verified") else "skipped", detail=exc.detail)
        return {
            **_codex_result(status="interrupted", email=email, message=str(exc)),
            "diagnostic_complete": True,
            "session_diagnostics": exc.detail,
        }
    except OperationCancelled:
        raise
    except AccountUnusableError as exc:
        logger.warning(f"[Codex] 账号已废（{exc.error_code}）：{email}")
        return _codex_result(
            status="deactivated",
            email=email,
            message=f"账号已废（{exc.error_code}）",
            email_permanently_unusable=True,
            account_unusable_error_code=exc.error_code,
        )
    except CodexAuthResultUnknown as exc:
        logger.warning("[Codex] 登录验证结果未知，需人工核对后继续")
        return {
            **_codex_result(status="attention_required", email=email, message=str(exc)),
            "outcome": "request_unknown",
            "reconcile_required": True,
            **({"session_diagnostics": session.snapshot()} if diagnostic_after_mfa else {}),
        }
    except CodexPhoneVerificationDisabled as exc:
        logger.warning("[Codex] %s", exc)
        return _phone_verification_disabled_result(email, exc)
    except CodexPhoneVerificationError as exc:
        logger.warning("[Codex] %s", exc)
        return {
            **_codex_result(status="failed", email=email, message=str(exc)),
            **exc.as_result(),
        }
    except CodexConsentUnverifiableError as exc:
        logger.warning("[Codex] 授权确认页无法确认单一工作区，需使用浏览器驱动")
        return {
            **_codex_result(status="failed", email=email, message=str(exc)),
            "cause_code": "codex_consent_unverifiable",
            "error_category": "auth",
            "auth_diagnostics": {
                "operation": "consent",
                "failure_kind": "next_step_unverifiable",
                "oauth_driver": "protocol",
                "page_path": "/sign-in-with-chatgpt/codex/consent",
            },
        }
    except Exception as exc:
        if not diagnostic_after_mfa and _is_cpa_callback_reauth_error(exc) and _cpa_reauth_round < 2:
            logger.warning(
                "[Codex][CPA] callback 返回 Timeout waiting for OAuth callback，重新开启第 %s/2 轮 Codex 授权：%s",
                _cpa_reauth_round + 1, email,
            )
            return run_codex_oauth(
                email,
                otp_provider=otp_provider,
                proxy=proxy,
                force=force,
                _cpa_reauth_round=_cpa_reauth_round + 1,
                driver_override=driver_override,
                allow_password_reset=allow_password_reset,
                on_password_reset_submitted=on_password_reset_submitted,
                login_password=login_password,
                login_totp_secret=login_totp_secret,
                phone_enabled=phone_enabled,
            )
        logger.warning(f"[Codex] 失败：{email}，{type(exc).__name__}: {str(exc)[:200]}")
        logger.debug("[Codex] 失败详情:", exc_info=True)
        return {
            **_codex_result(
            status="failed",
            email=email,
            message=f"{type(exc).__name__}: {str(exc)[:200]}",
            ),
            **({"session_diagnostics": session.snapshot()} if diagnostic_after_mfa else {}),
        }
    finally:
        if diagnostic_after_mfa:
            try:
                session.close()
            except Exception:
                logger.warning("[Codex] 诊断会话关闭未获确认")


def _protocol_execution_context():
    """Capture current helpers at the legacy patch boundary for this call."""
    from core.kernels.protocol.local.codex_oauth import ProtocolExecutionContext

    return ProtocolExecutionContext(
        AccountUnusableError=AccountUnusableError,
        CodexAuthPageSession=CodexAuthPageSession,
        CodexAuthResultUnknown=CodexAuthResultUnknown,
        CodexDiagnosticSession=CodexDiagnosticSession,
        CodexSessionDiagnosticComplete=_CodexSessionDiagnosticComplete,
        authorize_login_step=_authorize_login_step,
        build_authorize_url=_build_authorize_url,
        build_sentinel_header=build_sentinel_header,
        cache_auth_session_metadata=_cache_auth_session_metadata,
        cache_auth_session_payload=_cache_auth_session_payload,
        check_cancelled=check_cancelled,
        load_client_id=lambda: _cfg.CODEX_CLIENT_ID,
        confirm_email_step=_confirm_email_step,
        confirmed_consent_workspace_id=_confirmed_consent_workspace_id,
        current_workspace_id=_current_workspace_id,
        decode_auth_session_metadata=_decode_auth_session_metadata,
        decode_jwt_segment=_decode_jwt_segment,
        detect_account_unusable_response_body=detect_account_unusable_response_body,
        ensure_oai_context_url=_ensure_oai_context_url,
        ensure_phone_verification_enabled=_ensure_phone_verification_enabled,
        extract_code=_extract_code,
        extract_continue_url=_extract_continue_url,
        extract_error_code=_extract_error_code,
        follow_login_continue_step=_follow_login_continue_step,
        follow_until_callback=_follow_until_callback,
        get_workspace_id=_get_workspace_id,
        is_transient_network_error=_is_transient_network_error,
        logger=logger,
        clock=time,
        login_page_type_for_log=_login_page_type_for_log,
        login_session_presence=_login_session_presence,
        login_target=_login_target,
        login_target_for_log=_login_target_for_log,
        max_redirects=_MAX_REDIRECTS,
        mfa_auth=_mfa_auth_callbacks,
        navigate_email_otp_send=navigate_email_otp_send,
        net_backoff_base=_NET_BACKOFF_BASE,
        net_max_attempts=_NET_MAX_ATTEMPTS,
        password_auth=_password_auth_callbacks,
        post_json=_post_json,
        load_redirect_uri=lambda: _cfg.CODEX_REDIRECT_URI,
        report_stage=report_stage,
        request_sentinel_token=request_sentinel_token,
        resp_json=_resp_json,
        rotate_document_navigation_id=_rotate_document_navigation_id,
        safe_login_path=_safe_login_path,
        load_token_url=lambda: _cfg.CODEX_TOKEN_URL,
        url_path_for_log=_url_path_for_log,
        verify_saved_login_mfa=_verify_saved_login_mfa,
        with_net_retry=_with_net_retry,
        workspace_cookie_wait_seconds=_WORKSPACE_COOKIE_WAIT_SECONDS,
        workspace_poll_interval_seconds=_WORKSPACE_POLL_INTERVAL_SECONDS,
    )


def _password_auth_callbacks():
    # Preserve the original lazy import and account credential ownership.
    from core.accounts.credentials import get_account_login_credentials
    from core.accounts.liveness.protocol.v2 import ProtocolV2AuthError, _password_verify
    from core.kernels.protocol.local.codex_oauth import PasswordAuthCallbacks

    return PasswordAuthCallbacks(get_account_login_credentials, ProtocolV2AuthError, _password_verify)


def _mfa_auth_callbacks():
    from core.accounts.credentials import get_account_login_credentials
    from core.accounts.liveness.protocol.v2 import (
        ProtocolV2AuthError, _extract_factor_id, _mfa_issue_challenge, _mfa_verify, _totp_code,
    )
    from core.kernels.protocol.local.codex_oauth import MfaAuthCallbacks

    return MfaAuthCallbacks(
        get_account_login_credentials, ProtocolV2AuthError, _extract_factor_id,
        _mfa_issue_challenge, _mfa_verify, _totp_code,
    )
