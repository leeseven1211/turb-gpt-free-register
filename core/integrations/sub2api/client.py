# -*- coding: utf-8 -*-
"""sub2api Codex OAuth 凭证导入客户端。"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

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
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.message = message
        self.uploaded = uploaded
        self.sub2api_account_id = sub2api_account_id


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
    # 旧上传函数保留手工上传的详细消息；此处只提取其固定 HTTP 状态前缀。
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


def upload_and_enable_configured_codex_oauth_credential(
    auth_json: dict[str, Any],
    *,
    checkpoint: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """上传一份 OAuth 凭证，并恢复本次导入账号的错误状态和调度。"""
    from config import sub2api as sub2api_cfg

    import_url = configured_codex_import_url()
    import_path = "/api/v1/admin/accounts/import/codex-session"
    if not import_url or not import_url.endswith(import_path):
        raise Sub2ApiSyncError("upload", "sub2api_config_invalid", "请配置有效的 Sub2API API 基址或 Codex Session 导入地址")
    if not isinstance(auth_json, dict) or not any(str(auth_json.get(key) or "").strip() for key in ("refresh_token", "access_token")):
        raise Sub2ApiSyncError("upload", "sub2api_credential_invalid", "Codex OAuth 凭证缺少可上传的 Token")

    token = str(getattr(sub2api_cfg, "SUB2API_API_KEY", "") or getattr(sub2api_cfg, "SUB2API_API_TOKEN", "") or "").strip()
    header = str(getattr(sub2api_cfg, "SUB2API_API_AUTH_HEADER", "x-api-key") or "x-api-key").strip() or "x-api-key"
    prefix = str(getattr(sub2api_cfg, "SUB2API_API_AUTH_PREFIX", "") or "").strip()
    headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "turb-gpt-free-register/sub2api"}
    if token:
        headers[header] = f"{prefix} {token}".strip() if prefix else token
    try:
        timeout = float(getattr(sub2api_cfg, "SUB2API_API_TIMEOUT", 20) or 20)
    except (TypeError, ValueError):
        raise Sub2ApiSyncError("upload", "sub2api_config_invalid", "Sub2API 请求超时配置无效") from None

    if checkpoint is not None:
        checkpoint()
    try:
        result = upload_codex_oauth_credential(
            auth_json,
            import_url,
            api_token=token,
            auth_header=header,
            auth_prefix=prefix,
            timeout=timeout,
        )
    except Exception as exc:
        raise _safe_sync_failure("upload", exc) from None

    body = result.get("response") if isinstance(result, dict) else None
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise Sub2ApiSyncError("resolve_account", "sub2api_import_result_invalid", "Sub2API 导入结果缺少账号明细")
    try:
        counters = {key: int(data.get(key) or 0) for key in ("total", "created", "updated", "failed", "skipped")}
    except (TypeError, ValueError):
        raise Sub2ApiSyncError("resolve_account", "sub2api_import_result_invalid", "Sub2API 导入结果的统计字段无效") from None
    uploaded = counters["total"] == 1 and counters["created"] + counters["updated"] == 1 and counters["failed"] == 0
    if counters["skipped"]:
        raise Sub2ApiSyncError("resolve_account", "sub2api_import_skipped", "Sub2API 跳过了本次凭证导入，尚未恢复账号调度", uploaded=uploaded)
    items = data.get("items")
    if not uploaded or not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise Sub2ApiSyncError("resolve_account", "sub2api_import_result_invalid", "Sub2API 导入结果无法唯一确认成功账号", uploaded=uploaded)
    item = items[0]
    action = item.get("action")
    if item.get("index") != 1 or action not in ("created", "updated") or counters[action] != 1:
        raise Sub2ApiSyncError("resolve_account", "sub2api_import_result_invalid", "Sub2API 导入明细未确认账号创建或更新成功", uploaded=uploaded)
    remote_id = item.get("account_id")
    if isinstance(remote_id, bool) or not isinstance(remote_id, (int, str)) or not re.fullmatch(r"[1-9]\d*", str(remote_id)):
        raise Sub2ApiSyncError("resolve_account", "sub2api_account_id_missing", "Sub2API 导入结果缺少有效的远端账号 ID", uploaded=uploaded)
    account_id = int(remote_id)

    account_url = f"{import_url[:-len(import_path)]}/api/v1/admin/accounts/{account_id}"

    for stage, endpoint, payload in (
        ("reset_error", "clear-error", {}),
        ("enable_scheduling", "schedulable", {"schedulable": True}),
    ):
        if checkpoint is not None:
            try:
                checkpoint()
            except Exception as exc:
                exc.sub2api_uploaded = True
                exc.sub2api_account_id = account_id
                exc.sub2api_stage = stage
                raise
        try:
            response = requests.post(f"{account_url}/{endpoint}", headers=headers, json=payload, timeout=timeout)
            status = int(response.status_code)
            if status < 200 or status >= 300:
                raise _sync_http_failure(stage, status)
            response_body = response.json()
            if not isinstance(response_body, dict):
                raise Sub2ApiSyncError(stage, "sub2api_response_invalid", "Sub2API 返回的数据格式无效")
            if response_body.get("code") not in (None, 0, 200):
                raise Sub2ApiSyncError(stage, "sub2api_operation_rejected", "Sub2API 拒绝恢复账号状态，请重试同步")
        except Exception as exc:
            error = exc if isinstance(exc, Sub2ApiSyncError) else _safe_sync_failure(stage, exc)
            error.uploaded = True
            error.sub2api_account_id = account_id
            raise error from None

    return {
        "ok": True,
        "status": "success",
        "uploaded": True,
        "enabled": True,
        "sub2api_account_id": account_id,
        "created": counters["created"],
        "updated": counters["updated"],
    }


def configured_codex_import_url() -> str:
    """返回当前配置的 sub2api Codex Session 导入地址。"""
    from config import sub2api as sub2api_cfg

    api_base = str(getattr(sub2api_cfg, "SUB2API_API_BASE", "") or "").strip()
    if api_base:
        return api_base.rstrip("/") + "/api/v1/admin/accounts/import/codex-session"
    return str(getattr(sub2api_cfg, "SUB2API_API_URL", "") or "").strip()


def export_configured_accounts() -> list[dict[str, Any]]:
    """读取 sub2api 的完整账号导出，不把响应内容写入日志或文件。"""
    from config import sub2api as sub2api_cfg

    base = str(getattr(sub2api_cfg, "SUB2API_API_BASE", "") or "").strip().rstrip("/")
    if not base:
        raise ValueError("SUB2API_API_BASE 为空，无法导出账号")
    token = str(
        getattr(sub2api_cfg, "SUB2API_API_KEY", "")
        or getattr(sub2api_cfg, "SUB2API_API_TOKEN", "")
        or ""
    ).strip()
    header_name = str(getattr(sub2api_cfg, "SUB2API_API_AUTH_HEADER", "x-api-key") or "x-api-key").strip()
    prefix = str(getattr(sub2api_cfg, "SUB2API_API_AUTH_PREFIX", "") or "").strip()
    headers = {
        "Accept": "application/json",
        "User-Agent": "turb-gpt-free-register/sub2api-sync",
    }
    if token:
        headers[header_name] = f"{prefix} {token}".strip() if prefix else token

    response = requests.get(
        f"{base}/api/v1/admin/accounts/data",
        headers=headers,
        timeout=float(getattr(sub2api_cfg, "SUB2API_API_TIMEOUT", 20) or 20),
    )
    try:
        body = response.json()
    except Exception as exc:
        raise RuntimeError(f"sub2api 账号导出响应不是 JSON: HTTP {response.status_code}") from exc
    if response.status_code < 200 or response.status_code >= 300:
        message = body.get("message") if isinstance(body, dict) else ""
        raise RuntimeError(f"sub2api 账号导出失败 HTTP {response.status_code}: {str(message)[:300]}")
    if isinstance(body, dict) and body.get("code") not in (None, 0, 200):
        raise RuntimeError(f"sub2api 账号导出失败: {body.get('message') or str(body)[:300]}")
    data = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else {}
    accounts = data.get("accounts")
    if not isinstance(accounts, list):
        raise RuntimeError("sub2api 账号导出缺少 data.accounts")
    return [item for item in accounts if isinstance(item, dict)]


def upload_configured_codex_oauth_credential(auth_json: dict[str, Any]) -> dict[str, Any]:
    """使用项目当前 sub2api 配置上传一份 Codex OAuth 凭证。"""
    from config import sub2api as sub2api_cfg

    return upload_codex_oauth_credential(
        auth_json,
        configured_codex_import_url(),
        api_token=str(
            getattr(sub2api_cfg, "SUB2API_API_KEY", "")
            or getattr(sub2api_cfg, "SUB2API_API_TOKEN", "")
            or ""
        ).strip(),
        auth_header=str(
            getattr(sub2api_cfg, "SUB2API_API_AUTH_HEADER", "x-api-key") or "x-api-key"
        ).strip(),
        auth_prefix=str(getattr(sub2api_cfg, "SUB2API_API_AUTH_PREFIX", "") or "").strip(),
        timeout=float(getattr(sub2api_cfg, "SUB2API_API_TIMEOUT", 20) or 20),
    )


def upload_codex_oauth_credential(
    auth_json: dict[str, Any],
    api_url: str,
    *,
    api_token: str | None = None,
    auth_header: str = "x-api-key",
    auth_prefix: str = "",
    timeout: float = 20.0,
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
        "concurrency": 3,
        "priority": 50,
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

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    status = int(getattr(resp, "status_code", 0) or 0)
    text = getattr(resp, "text", "") or ""
    try:
        body = resp.json()
    except Exception:
        body = {"text": text[:1000]}
    if status < 200 or status >= 300:
        raise RuntimeError(f"sub2api 上传失败 HTTP {status}: {text[:800]}")
    if isinstance(body, dict) and body.get("code") not in (None, 0, 200):
        raise RuntimeError(f"sub2api 上传失败: {body.get('message') or body.get('error') or str(body)[:800]}")

    data = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else body
    if isinstance(data, dict):
        failed = int(data.get("failed") or 0)
        if failed:
            errors = data.get("errors") if isinstance(data.get("errors"), list) else []
            detail = "; ".join(
                str(item.get("message") or item)
                for item in errors[:3]
                if isinstance(item, dict)
            )
            raise RuntimeError(f"sub2api Codex 凭证导入失败: {detail or f'failed={failed}'}")

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
