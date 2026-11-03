# -*- coding: utf-8 -*-
"""sub2api Codex OAuth 凭证导入客户端。"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests


class Sub2ApiSyncError(RuntimeError):
    """保存同步失败阶段与原因，消息不包含远端正文或凭据。"""

    def __init__(
        self,
        stage: str,
        code: str,
        message: str,
        *,
        uploaded: bool = False,
        sub2api_account_id: int | None = None,
        backend_identity: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.message = message
        self.uploaded = uploaded
        self.sub2api_account_id = sub2api_account_id
        self.backend_identity = backend_identity


def _safe_sync_failure(stage: str, exc: Exception) -> Sub2ApiSyncError:
    if isinstance(exc, requests.Timeout):
        return Sub2ApiSyncError(stage, "sub2api_timeout", "Sub2API 请求超时，请重试同步")
    if isinstance(exc, requests.ConnectionError):
        return Sub2ApiSyncError(stage, "sub2api_connection_failed", "无法连接 Sub2API，请检查连接配置后重试")
    if isinstance(exc, requests.exceptions.JSONDecodeError):
        return Sub2ApiSyncError(stage, "sub2api_response_invalid", "Sub2API 返回的数据格式无效")
    if isinstance(exc, requests.RequestException):
        return Sub2ApiSyncError(stage, "sub2api_request_failed", "Sub2API 网络请求失败，请重试同步")
    if isinstance(exc, ValueError):
        return Sub2ApiSyncError(stage, "sub2api_response_invalid", "Sub2API 返回的数据格式无效")
    # 兼容旧适配器，只提取固定 HTTP 状态前缀，不传递异常正文。
    match = re.match(r"sub2api 上传失败 HTTP (\d+):", str(exc))
    if match:
        return _sync_http_failure(stage, int(match.group(1)))
    if stage == "upload" and isinstance(exc, RuntimeError):
        return Sub2ApiSyncError(stage, "sub2api_upload_rejected", "Sub2API 拒绝导入 Codex 凭证，请检查服务端导入结果")
    return Sub2ApiSyncError(stage, "sub2api_client_error", "Sub2API 客户端处理失败，请检查同步阶段的服务日志")


def _sync_http_failure(stage: str, status: int) -> Sub2ApiSyncError:
    if status in (401, 403):
        return Sub2ApiSyncError(stage, "sub2api_auth_rejected", "Sub2API 管理接口鉴权失败或权限不足")
    return Sub2ApiSyncError(stage, "sub2api_http_error", f"Sub2API 管理接口返回 HTTP {status}")


_IMPORT_PATH = "/api/v1/admin/accounts/import/codex-session"
_OAUTH_FIELDS = (
    "access_token", "refresh_token", "id_token", "email", "chatgpt_account_id",
    "chatgpt_user_id", "user_id", "expires_at", "token_type", "scope",
    "client_id", "plan_type", "organization_id",
)


@dataclass(frozen=True)
class _ClientConfig:
    base: str
    headers: dict[str, str] = field(repr=False)
    timeout: float
    options: dict[str, Any]
    backend_identity: str


def _config_invalid() -> Sub2ApiSyncError:
    return Sub2ApiSyncError("configuration", "sub2api_config_invalid", "Sub2API 配置无效，请检查目标地址、请求超时与上传参数")


def _normalize_base(raw: str) -> str:
    try:
        parsed = urlsplit(str(raw or "").strip())
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError
        port = parsed.port
        host = parsed.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        if port and not (parsed.scheme.lower() == "https" and port == 443 or parsed.scheme.lower() == "http" and port == 80):
            host += f":{port}"
        return urlunsplit((parsed.scheme.lower(), host, parsed.path.rstrip("/"), "", ""))
    except (ValueError, TypeError):
        raise _config_invalid() from None


def _configured_base() -> str:
    from config import sub2api as cfg

    raw = str(getattr(cfg, "SUB2API_API_BASE", "") or "").strip()
    if not raw:
        url = str(getattr(cfg, "SUB2API_API_URL", "") or "").strip().rstrip("/")
        if not url.endswith(_IMPORT_PATH):
            raise _config_invalid()
        raw = url[:-len(_IMPORT_PATH)]
    return _normalize_base(raw)


def configured_backend_identity() -> str:
    """返回规范化目标地址的稳定摘要，任务中不保存地址或鉴权信息。"""
    import config

    with config._RELOAD_LOCK:
        return hashlib.sha256(_configured_base().encode("utf-8")).hexdigest()


def configured_upload_options() -> dict[str, Any]:
    """只返回显式填写的上传参数；空值不覆盖远端已有设置。"""
    import config

    with config._RELOAD_LOCK:
        return _configured_upload_options_locked()


def _configured_upload_options_locked() -> dict[str, Any]:
    from config import sub2api as cfg

    options: dict[str, Any] = {}
    try:
        groups = str(getattr(cfg, "SUB2API_UPLOAD_GROUP_IDS", "") or "").strip()
        if groups:
            options["group_ids"] = list(dict.fromkeys(_positive_id(item.strip()) for item in groups.split(",")))
        for key, field in (("SUB2API_UPLOAD_PROXY_ID", "proxy_id"), ("SUB2API_UPLOAD_CONCURRENCY", "concurrency"), ("SUB2API_UPLOAD_PRIORITY", "priority")):
            text = str(getattr(cfg, key, "") or "").strip()
            if text:
                number = _positive_id(text) if field == "proxy_id" else _nonnegative_integer(text)
                if field == "concurrency" and number == 0:
                    raise ValueError
                options[field] = number
        load = str(getattr(cfg, "SUB2API_UPLOAD_LOAD_FACTOR", "") or "").strip()
        if load:
            number = _positive_id(load)
            if number > 10000:
                raise ValueError
            options["load_factor"] = number
        models = str(getattr(cfg, "SUB2API_UPLOAD_MODELS", "") or "").strip()
        if models:
            options["model_whitelist"] = list(dict.fromkeys(item.strip() for item in re.split(r"[,\n\r]", models) if item.strip()))
    except (ValueError, TypeError):
        raise _config_invalid() from None
    return options


def _positive_id(value: Any) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[1-9]\d*", str(value)):
        raise ValueError
    return int(value)


def _nonnegative_integer(value: Any) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value)) or not 0 <= int(value) <= 10000:
        raise ValueError
    return int(value)


def _capture_config(expected_backend: str | None = None) -> _ClientConfig:
    import config

    # 与热重载共用锁，只在复制配置时持有；网络请求期间不占用此锁。
    with config._RELOAD_LOCK:
        return _capture_config_locked(expected_backend)


def _capture_config_locked(expected_backend: str | None) -> _ClientConfig:
    from config import sub2api as cfg

    base = _configured_base()
    identity = hashlib.sha256(base.encode("utf-8")).hexdigest()
    if expected_backend is not None and expected_backend != identity:
        raise Sub2ApiSyncError("configuration", "sub2api_backend_changed", "Sub2API 目标已变更，请重新确认同步目标", backend_identity=identity)
    headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "turb-gpt-free-register/sub2api"}
    token = str(getattr(cfg, "SUB2API_API_KEY", "") or getattr(cfg, "SUB2API_API_TOKEN", "") or "").strip()
    header = str(getattr(cfg, "SUB2API_API_AUTH_HEADER", "x-api-key") or "x-api-key").strip() or "x-api-key"
    prefix = str(getattr(cfg, "SUB2API_API_AUTH_PREFIX", "") or "").strip()
    if token:
        headers[header] = f"{prefix} {token}".strip() if prefix else token
    try:
        timeout = float(getattr(cfg, "SUB2API_API_TIMEOUT", 20) or 20)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError
        options = configured_upload_options()
    except (ValueError, TypeError, Sub2ApiSyncError):
        error = _config_invalid()
        error.backend_identity = identity
        raise error from None
    return _ClientConfig(base, headers, timeout, options, identity)


def _checkpoint(checkpoint: Callable[[], None] | None, *, config: _ClientConfig, stage: str, account_id: int | None = None, uploaded: bool = False) -> None:
    if checkpoint is None:
        return
    try:
        checkpoint()
    except Exception as exc:
        exc.sub2api_uploaded = uploaded
        exc.sub2api_account_id = account_id
        exc.sub2api_stage = stage
        exc.backend_identity = config.backend_identity
        raise


def _request_json(config: _ClientConfig, method: str, path: str, *, stage: str, checkpoint: Callable[[], None] | None = None, account_id: int | None = None, uploaded: bool = False, **kwargs: Any) -> Any:
    _checkpoint(checkpoint, config=config, stage=stage, account_id=account_id, uploaded=uploaded)
    try:
        response = getattr(requests, method)(f"{config.base}{path}", headers=config.headers, timeout=config.timeout, **kwargs)
        status = int(response.status_code)
        if not 200 <= status < 300:
            if status == 404 and stage == "resolve_account":
                raise Sub2ApiSyncError(stage, "sub2api_account_missing", "Sub2API 目标账号已不存在")
            raise _sync_http_failure(stage, status)
        body = response.json()
        if not isinstance(body, dict) or body.get("code") not in (None, 0, 200):
            raise Sub2ApiSyncError(stage, "sub2api_operation_rejected", "Sub2API 未确认本次操作成功")
        return body.get("data", body)
    except Exception as exc:
        error = exc if isinstance(exc, Sub2ApiSyncError) else _safe_sync_failure(stage, exc)
        error.uploaded = uploaded
        error.sub2api_account_id = account_id
        error.backend_identity = config.backend_identity
        raise error from None


def _remote_email(account: dict[str, Any]) -> str:
    credentials = account.get("credentials") if isinstance(account.get("credentials"), dict) else {}
    extra = account.get("extra") if isinstance(account.get("extra"), dict) else {}
    for value in (credentials.get("email"), extra.get("email")):
        if str(value or "").strip():
            return str(value).strip().casefold()
    name = str(account.get("name") or "").strip()
    if name.casefold().startswith("oauth---"):
        name = name[len("oauth---"):]
    match = re.search(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", name)
    return match.group(0).casefold() if match else ""


def _list_accounts(config: _ClientConfig, *, status: str | None = None, email: str | None = None, checkpoint: Callable[[], None] | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    page = 1
    while page <= 1000:
        params: dict[str, Any] = {"page": page, "page_size": 100, "platform": "openai"}
        if status:
            params["status"] = status
        data = _request_json(config, "get", "/api/v1/admin/accounts", stage="list_accounts", checkpoint=checkpoint, params=params)
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise Sub2ApiSyncError("list_accounts", "sub2api_response_invalid", "Sub2API 账号列表格式无效", backend_identity=config.backend_identity)
        for account in items:
            if not isinstance(account, dict) or str(account.get("platform") or "").lower() != "openai":
                continue
            if status and str(account.get("status") or "").lower() != status:
                continue
            if email and _remote_email(account) != email.casefold():
                continue
            try:
                account_id = _positive_id(account.get("id"))
            except ValueError:
                continue
            if account_id not in seen:
                result.append(account)
                seen.add(account_id)
        pages = data.get("pages")
        if pages is not None:
            try:
                count = _nonnegative_integer(pages)
            except ValueError:
                raise Sub2ApiSyncError("list_accounts", "sub2api_response_invalid", "Sub2API 分页字段无效", backend_identity=config.backend_identity) from None
            if page >= count:
                return result
        elif len(items) < 100:
            return result
        page += 1
    raise Sub2ApiSyncError("list_accounts", "sub2api_pagination_limit", "Sub2API 账号列表超过单次巡检上限", backend_identity=config.backend_identity)


def list_configured_error_accounts(
    *, group_ids: list[int] | None = None, expected_backend: str | None = None,
) -> list[dict[str, Any]]:
    """分页读取 OpenAI 异常账号，并按指定分组筛选。"""
    config = _capture_config(expected_backend)
    try:
        wanted = {_positive_id(value) for value in (group_ids or [])}
    except ValueError:
        raise _config_invalid() from None
    accounts = _list_accounts(config, status="error")
    if not wanted:
        return accounts
    result = []
    for account in accounts:
        groups = list(account.get("group_ids") or [])
        groups.extend(item.get("group_id") for item in account.get("account_groups", []) if isinstance(item, dict))
        if any(str(value).isdigit() and int(value) in wanted for value in groups):
            result.append(account)
    return result


def _validate_credential(auth_json: dict[str, Any], config: _ClientConfig) -> str:
    if not isinstance(auth_json, dict) or not any(str(auth_json.get(key) or "").strip() for key in ("refresh_token", "access_token")):
        raise Sub2ApiSyncError("upload", "sub2api_credential_invalid", "Codex OAuth 凭证缺少可上传的 Token", backend_identity=config.backend_identity)
    email = str(auth_json.get("email") or "").strip().casefold()
    if not email or "@" not in email:
        raise Sub2ApiSyncError("resolve_account", "sub2api_credential_identity_missing", "Codex OAuth 凭证缺少有效邮箱", backend_identity=config.backend_identity)
    return email


def _jwt_identity_fields(auth_json: dict[str, Any]) -> dict[str, str]:
    # 与导入接口一致，仅补充新凭据携带的身份元数据；此处不把 claims 当作鉴权证明。
    fields: dict[str, str] = {}
    for token_field in ("id_token", "access_token"):
        token = auth_json.get(token_field)
        if not isinstance(token, str) or len(parts := token.split(".")) != 3:
            continue
        try:
            claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(claims, dict):
            continue
        auth = claims.get("https://api.openai.com/auth")
        auth = auth if isinstance(auth, dict) else {}
        organizations = auth.get("organizations")
        organizations = [item for item in organizations if isinstance(item, dict)] if isinstance(organizations, list) else []
        organization = next((item for item in organizations if item.get("is_default") is True), organizations[0] if organizations else {})
        candidates = {
            "chatgpt_account_id": auth.get("chatgpt_account_id"),
            "chatgpt_user_id": auth.get("chatgpt_user_id") or auth.get("user_id") or claims.get("sub"),
            "plan_type": auth.get("chatgpt_plan_type"),
            "organization_id": auth.get("poid") or organization.get("id"),
        }
        for key, value in candidates.items():
            if isinstance(value, str) and value.strip():
                fields.setdefault(key, value.strip())
    return fields


def _credentials_payload(auth_json: dict[str, Any], config: _ClientConfig, remote: dict[str, Any]) -> dict[str, Any]:
    credentials = {**dict(remote.get("credentials") or {}), **_jwt_identity_fields(auth_json)}
    for field in _OAUTH_FIELDS:
        if auth_json.get(field) is not None and str(auth_json[field]).strip():
            credentials[field] = auth_json[field]
    if auth_json.get("account_id"):
        credentials["chatgpt_account_id"] = auth_json["account_id"]
    if auth_json.get("expired"):
        credentials["expires_at"] = auth_json["expired"]
    payload = {key: value for key, value in config.options.items() if key != "model_whitelist"}
    if "group_ids" in payload:
        payload["confirm_mixed_channel_risk"] = True
    if "model_whitelist" in config.options:
        credentials["model_mapping"] = {model: model for model in config.options["model_whitelist"]}
    payload["credentials"] = credentials
    return payload


def _update_account(config: _ClientConfig, auth_json: dict[str, Any], account_id: int, *, checkpoint: Callable[[], None] | None, enable: bool) -> dict[str, Any]:
    email = _validate_credential(auth_json, config)
    try:
        account_id = _positive_id(account_id)
    except ValueError:
        raise Sub2ApiSyncError("resolve_account", "sub2api_account_id_invalid", "Sub2API 目标账号 ID 无效", backend_identity=config.backend_identity) from None
    remote = _request_json(config, "get", f"/api/v1/admin/accounts/{account_id}", stage="resolve_account", checkpoint=checkpoint, account_id=account_id)
    if not isinstance(remote, dict) or str(remote.get("id")) != str(account_id) or str(remote.get("platform") or "").lower() != "openai" or str(remote.get("type") or "").lower() != "oauth" or _remote_email(remote) != email or not isinstance(remote.get("credentials"), dict):
        raise Sub2ApiSyncError("resolve_account", "sub2api_account_identity_mismatch", "Sub2API 目标账号身份、平台或类型不匹配", sub2api_account_id=account_id, backend_identity=config.backend_identity)
    payload = _credentials_payload(auth_json, config, remote)
    _request_json(config, "put", f"/api/v1/admin/accounts/{account_id}", stage="upload", checkpoint=checkpoint, account_id=account_id, json=payload)
    if enable:
        _enable_account(config, account_id, checkpoint)
    return {"ok": True, "status": "success", "uploaded": True, "enabled": enable, "sub2api_account_id": account_id, "backend_identity": config.backend_identity, "created": 0, "updated": 1}


def _enable_account(config: _ClientConfig, account_id: int, checkpoint: Callable[[], None] | None) -> None:
    for stage, endpoint, payload in (("reset_error", "clear-error", {}), ("enable_scheduling", "schedulable", {"schedulable": True})):
        _request_json(config, "post", f"/api/v1/admin/accounts/{account_id}/{endpoint}", stage=stage, checkpoint=checkpoint, account_id=account_id, uploaded=True, json=payload)


def update_and_enable_configured_account(auth_json: dict[str, Any], account_id: int, *, checkpoint: Callable[[], None] | None = None, expected_backend: str | None = None) -> dict[str, Any]:
    """校验指定远端账号后增量更新凭据、清错并恢复调度。"""
    return _update_account(_capture_config(expected_backend), auth_json, account_id, checkpoint=checkpoint, enable=True)


def _configured_upload(auth_json: dict[str, Any], *, checkpoint: Callable[[], None] | None, enable: bool, expected_backend: str | None = None) -> dict[str, Any]:
    config = _capture_config(expected_backend)
    email = _validate_credential(auth_json, config)
    existing = _list_accounts(config, email=email, checkpoint=checkpoint)
    if len(existing) > 1:
        raise Sub2ApiSyncError("resolve_account", "sub2api_account_ambiguous", "Sub2API 中同一邮箱存在多条账号，请按远端 ID 分别同步", backend_identity=config.backend_identity)
    if existing:
        return _update_account(config, auth_json, existing[0]["id"], checkpoint=checkpoint, enable=enable)
    _checkpoint(checkpoint, config=config, stage="upload")
    try:
        result = upload_codex_oauth_credential(auth_json, f"{config.base}{_IMPORT_PATH}", api_token=config.headers.get("x-api-key"), timeout=config.timeout, upload_options=config.options, request_headers=config.headers)
    except Exception as exc:
        error = exc if isinstance(exc, Sub2ApiSyncError) else _safe_sync_failure("upload", exc)
        error.backend_identity = config.backend_identity
        raise error from None
    result["backend_identity"] = config.backend_identity
    if not enable and not config.options:
        return result
    data = result.get("response", {}).get("data")
    uploaded = False
    try:
        if not isinstance(data, dict):
            raise ValueError
        counters = {key: int(data.get(key) or 0) for key in ("total", "created", "updated", "failed", "skipped")}
        uploaded = counters["total"] == 1 and counters["created"] + counters["updated"] == 1 and counters["failed"] == 0
        items = data.get("items")
        if counters["skipped"] or not uploaded or not isinstance(items, list) or len(items) != 1:
            raise ValueError
        item = items[0]
        action = item.get("action")
        if item.get("index") != 1 or action not in ("created", "updated") or counters[action] != 1:
            raise ValueError
        account_id = _positive_id(item.get("account_id"))
    except (ValueError, TypeError, AttributeError):
        raise Sub2ApiSyncError("resolve_account", "sub2api_import_result_invalid", "Sub2API 导入结果无法唯一确认成功账号", uploaded=uploaded, backend_identity=config.backend_identity) from None
    # 导入接口不保证支持所有可选设置；按导入结果确认的原 ID 增量应用。
    if config.options:
        try:
            updated = _update_account(config, auth_json, account_id, checkpoint=checkpoint, enable=enable)
        except Exception as exc:
            if isinstance(exc, Sub2ApiSyncError):
                exc.uploaded = True
                exc.sub2api_account_id = account_id
            else:
                exc.sub2api_uploaded = True
                exc.sub2api_account_id = account_id
            exc.backend_identity = config.backend_identity
            raise
        updated.update(created=counters["created"], updated=counters["updated"])
        return updated
    _enable_account(config, account_id, checkpoint)
    return {"ok": True, "status": "success", "uploaded": True, "enabled": True, "sub2api_account_id": account_id, "backend_identity": config.backend_identity, "created": counters["created"], "updated": counters["updated"]}


def upload_and_enable_configured_codex_oauth_credential(auth_json: dict[str, Any], *, checkpoint: Callable[[], None] | None = None, expected_backend: str | None = None) -> dict[str, Any]:
    """上传或增量更新 OAuth 凭证，并恢复错误状态与调度。"""
    return _configured_upload(auth_json, checkpoint=checkpoint, enable=True, expected_backend=expected_backend)


def configured_codex_import_url() -> str:
    """返回当前配置的 sub2api Codex Session 导入地址。"""
    from config import sub2api as sub2api_cfg

    api_base = str(getattr(sub2api_cfg, "SUB2API_API_BASE", "") or "").strip()
    if api_base:
        return api_base.rstrip("/") + "/api/v1/admin/accounts/import/codex-session"
    return str(getattr(sub2api_cfg, "SUB2API_API_URL", "") or "").strip()


def export_configured_accounts() -> list[dict[str, Any]]:
    """读取完整账号导出，异常中不包含远端正文或凭据。"""
    config = _capture_config()
    data = _request_json(config, "get", "/api/v1/admin/accounts/data", stage="export_accounts")
    accounts = data.get("accounts") if isinstance(data, dict) else None
    if not isinstance(accounts, list):
        raise Sub2ApiSyncError("export_accounts", "sub2api_response_invalid", "Sub2API 账号导出缺少账号列表", backend_identity=config.backend_identity)
    return [item for item in accounts if isinstance(item, dict)]


def upload_configured_codex_oauth_credential(auth_json: dict[str, Any]) -> dict[str, Any]:
    """使用当前配置同步 OAuth 凭证，保留未显式配置的远端参数。"""
    return _configured_upload(auth_json, checkpoint=None, enable=False)


def upload_codex_oauth_credential(
    auth_json: dict[str, Any],
    api_url: str,
    *,
    api_token: str | None = None,
    auth_header: str = "x-api-key",
    auth_prefix: str = "",
    timeout: float = 20.0,
    upload_options: dict[str, Any] | None = None,
    request_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """把 Codex OAuth JSON 导入 sub2api 的 Codex Session 接口。"""
    if not isinstance(auth_json, dict):
        raise ValueError("Codex OAuth 凭证必须是 JSON 对象")
    refresh_token = str(auth_json.get("refresh_token") or "").strip()
    access_token = str(auth_json.get("access_token") or "").strip()
    if not refresh_token and not access_token:
        raise ValueError("Codex OAuth 凭证缺少 refresh_token/access_token")

    url = str(api_url or "").strip()
    if not url:
        raise ValueError("SUB2API_API_BASE 为空，无法上传到 sub2api")

    email = str(auth_json.get("email") or "").strip()
    account_id = str(auth_json.get("account_id") or "").strip()
    payload = {
        "contents": [json.dumps(auth_json, ensure_ascii=False)],
        "name": email or (f"codex-{account_id[:8]}" if account_id else "codex-oauth"),
        "update_existing": True,
        "confirm_mixed_channel_risk": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "turb-gpt-free-register/sub2api",
    }
    token = str(api_token or "").strip()
    header_name = str(auth_header or "x-api-key").strip() or "x-api-key"
    prefix = str(auth_prefix or "").strip()
    if token:
        headers[header_name] = f"{prefix} {token}".strip() if prefix else token

    if request_headers is not None:
        headers = dict(request_headers)
    for key in ("group_ids", "proxy_id", "concurrency", "priority", "load_factor"):
        if key in (upload_options or {}):
            payload[key] = upload_options[key]
    if (upload_options or {}).get("model_whitelist"):
        payload["credential_extras"] = {
            "model_mapping": {model: model for model in upload_options["model_whitelist"]},
        }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        status = int(getattr(resp, "status_code", 0) or 0)
        if not 200 <= status < 300:
            raise _sync_http_failure("upload", status)
        body = resp.json()
        if not isinstance(body, dict):
            raise Sub2ApiSyncError("upload", "sub2api_response_invalid", "Sub2API 导入响应格式无效")
        if body.get("code") not in (None, 0, 200):
            raise Sub2ApiSyncError("upload", "sub2api_upload_rejected", "Sub2API 拒绝导入 Codex 凭证")
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if int(data.get("failed") or 0):
            raise Sub2ApiSyncError("upload", "sub2api_upload_rejected", "Sub2API 未完成 Codex 凭证导入，请检查远端导入状态")
    except Exception as exc:
        raise exc if isinstance(exc, Sub2ApiSyncError) else _safe_sync_failure("upload", exc) from None

    return {
        "ok": True,
        "uploaded": True,
        "url": url,
        "status_code": status,
        "email": email or None,
        "account_id": account_id or None,
        "total": data.get("total") if isinstance(data, dict) else None,
        "created": data.get("created") if isinstance(data, dict) else None,
        "updated": data.get("updated") if isinstance(data, dict) else None,
        "skipped": data.get("skipped") if isinstance(data, dict) else None,
        "response": body,
    }
