# -*- coding: utf-8 -*-
"""C2A 3.2.9 管理接口的最小 AT 同步客户端。

本模块按邮箱定位账号，覆盖既有账号 AT 或创建缺失账号；不会直接调用删除、启用、
清错、Refresh Token、分组或代理接口。C2A 通用更新接口仍可能按其自身规则处理
凭据错误，因此远端异常状态可能随 AT 更新变化。所有异常使用固定错误码，避免把
Token、管理 Key 或远端响应正文写入任务日志。
"""
from __future__ import annotations

import hashlib
import importlib
import math
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests


class C2AError(RuntimeError):
    """携带 C2A 同步阶段与稳定原因码的安全异常。"""

    def __init__(
        self,
        stage: str,
        code: str,
        message: str,
        *,
        backend_identity: str | None = None,
        remote_account_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = str(stage)
        self.code = str(code)
        self.message = str(message)
        self.backend_identity = backend_identity
        self.remote_account_id = remote_account_id


# 兼容 Python 命名习惯的引用；业务侧应优先使用 C2AError。
C2aSyncError = C2AError


@dataclass(frozen=True)
class _ClientConfig:
    base: str
    headers: dict[str, str] = field(repr=False)
    timeout: float
    backend_identity: str


@dataclass(frozen=True)
class SafeMutationPolicy:
    """兼容 C2A 旧接口时，由设置预检生成的单次写入前置条件。"""

    backend_identity: str


_MAX_ACCOUNT_PAGES = 100
_PAGE_SIZE = 500


def _config_error() -> C2AError:
    return C2AError(
        "configuration",
        "c2a_config_invalid",
        "C2A 配置无效，请检查 API 地址、管理 Key 与请求超时设置",
    )


def normalize_base(raw: str) -> str:
    """规范 C2A API 基址，拒绝嵌入凭据及非 HTTP(S) 目标。"""
    try:
        value = str(raw or "").strip()
        if not value or any(char.isspace() for char in value):
            raise ValueError
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
        path_parts = [part for part in parsed.path.split("/") if part]
        if any(part in {".", ".."} for part in path_parts):
            raise ValueError
        port = parsed.port
        host = parsed.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        scheme = parsed.scheme.lower()
        if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
            host = f"{host}:{port}"
        path = parsed.path.rstrip("/")
        return urlunsplit((scheme, host, path, "", ""))
    except (TypeError, ValueError):
        raise _config_error() from None


# 与既有 integration client 的私有命名保持一致，方便内部测试和迁移调用。
_normalize_base = normalize_base


def _c2a_config_module():
    try:
        return importlib.import_module("config.c2a")
    except (ImportError, ModuleNotFoundError):
        raise _config_error() from None


def _reload_lock():
    try:
        import config

        lock = getattr(config, "_RELOAD_LOCK", None)
        return lock if lock is not None else nullcontext()
    except Exception:
        return nullcontext()


def _capture_config(expected_backend: str | None = None) -> _ClientConfig:
    """在配置锁内复制一次配置；网络请求不持有热重载锁。"""
    with _reload_lock():
        cfg = _c2a_config_module()
        try:
            base = normalize_base(getattr(cfg, "C2A_API_BASE", ""))
            api_key = str(getattr(cfg, "C2A_API_KEY", "") or "").strip()
            if not api_key:
                raise ValueError
            timeout = float(getattr(cfg, "C2A_API_TIMEOUT", 20))
            if not math.isfinite(timeout) or not 0 < timeout <= 3600:
                raise ValueError
        except (TypeError, ValueError, C2AError):
            error = _config_error()
            try:
                error.backend_identity = hashlib.sha256(base.encode("utf-8")).hexdigest()
            except UnboundLocalError:
                pass
            raise error from None

    identity = hashlib.sha256(base.encode("utf-8")).hexdigest()
    if expected_backend is not None and str(expected_backend) != identity:
        raise C2AError(
            "configuration",
            "c2a_backend_changed",
            "C2A 目标已变化，请重新确认同步目标",
            backend_identity=identity,
        )
    return _ClientConfig(
        base=base,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "turb-gpt-free-register/c2a",
        },
        timeout=timeout,
        backend_identity=identity,
    )


def configured_backend_identity() -> str:
    """返回规范化 C2A 基址的 SHA-256 摘要，不包含管理 Key。"""
    return _capture_config().backend_identity


def verify_safe_mutation_policy(
    *,
    expected_backend: str | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> SafeMutationPolicy:
    """以 fail-closed 方式检查当前 C2A 自动清理策略。

    C2A 3.2.9 的通用更新接口在自动移除异常/限流账号打开时，可能在写入
    期间删除状态未恢复的账号。因此此处只读查询 C2A 设置；任一开关不是
    明确 ``false`` 都拒绝后续写入，也绝不替用户修改远端全局策略。旧接口
    没有把 settings revision 原子绑定到更新请求，调用方仍须保持远端策略稳定。
    """
    config = _capture_config(expected_backend)
    body = _request_json(
        config,
        "get",
        "/api/settings",
        stage="c2a_safety",
        checkpoint=checkpoint,
    )
    settings = body.get("settings")
    if not isinstance(settings, dict):
        raise C2AError(
            "c2a_safety",
            "c2a_remote_policy_unverified",
            "无法验证 C2A 自动清理策略，未更新远端账号",
            backend_identity=config.backend_identity,
        )
    policies = (settings.get("auto_remove_invalid_accounts"), settings.get("auto_remove_rate_limited_accounts"))
    if any(value is True for value in policies):
        raise C2AError(
            "c2a_safety",
            "c2a_remote_auto_removal_enabled",
            "C2A 自动移除异常或限流账号已开启，未更新远端账号",
            backend_identity=config.backend_identity,
        )
    if any(value is not False for value in policies):
        raise C2AError(
            "c2a_safety",
            "c2a_remote_policy_unverified",
            "无法验证 C2A 自动清理策略，未更新远端账号",
            backend_identity=config.backend_identity,
        )
    return SafeMutationPolicy(backend_identity=config.backend_identity)


def _checkpoint(checkpoint: Callable[[], None] | None) -> None:
    if checkpoint is not None:
        checkpoint()


def _http_error(stage: str, status: int, *, remote_account_id: str | None = None) -> C2AError:
    if status in {401, 403}:
        return C2AError(stage, "c2a_auth_rejected", "C2A 管理接口鉴权失败或权限不足", remote_account_id=remote_account_id)
    if status == 404 and stage == "update_account":
        return C2AError(stage, "c2a_remote_account_missing", "C2A 目标账号已不存在", remote_account_id=remote_account_id)
    if status == 429:
        return C2AError(stage, "c2a_rate_limited", "C2A 管理接口请求过于频繁，请稍后重试", remote_account_id=remote_account_id)
    if 500 <= status <= 599:
        return C2AError(stage, "c2a_server_error", "C2A 管理接口暂时不可用，请稍后重试", remote_account_id=remote_account_id)
    if 400 <= status <= 499 and stage == "update_account":
        return C2AError(stage, "c2a_update_rejected", f"C2A 管理接口拒绝更新（HTTP {status}）", remote_account_id=remote_account_id)
    if 400 <= status <= 499 and stage == "create_account":
        return C2AError(stage, "c2a_create_rejected", f"C2A 管理接口拒绝新建（HTTP {status}）", remote_account_id=remote_account_id)
    return C2AError(stage, "c2a_http_error", f"C2A 管理接口返回 HTTP {status}", remote_account_id=remote_account_id)


def _safe_request_error(stage: str, exc: Exception, *, remote_account_id: str | None = None) -> C2AError:
    if isinstance(exc, requests.Timeout):
        return C2AError(stage, "c2a_timeout", "C2A 请求超时，请重试同步", remote_account_id=remote_account_id)
    if isinstance(exc, requests.ConnectionError):
        return C2AError(stage, "c2a_connection_failed", "无法连接 C2A，请检查连接配置后重试", remote_account_id=remote_account_id)
    if isinstance(exc, ValueError):
        return C2AError(stage, "c2a_response_invalid", "C2A 返回的数据格式无效", remote_account_id=remote_account_id)
    if isinstance(exc, requests.RequestException):
        return C2AError(stage, "c2a_request_failed", "C2A 网络请求失败，请重试同步", remote_account_id=remote_account_id)
    return C2AError(stage, "c2a_client_error", "C2A 客户端处理失败，请查看同步阶段服务日志", remote_account_id=remote_account_id)


def _request_json(
    config: _ClientConfig,
    method: str,
    path: str,
    *,
    stage: str,
    checkpoint: Callable[[], None] | None = None,
    remote_account_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """执行一次 C2A 请求，绝不把远端正文拼入异常。"""
    _checkpoint(checkpoint)
    try:
        if method == "get":
            response = requests.get(
                f"{config.base}{path}", headers=config.headers, timeout=config.timeout, **kwargs,
            )
        elif method == "post":
            response = requests.post(
                f"{config.base}{path}",
                headers={**config.headers, "Content-Type": "application/json"},
                timeout=config.timeout,
                **kwargs,
            )
        else:
            raise RuntimeError("unsupported C2A request method")
        status = int(response.status_code)
        if not 200 <= status < 300:
            raise _http_error(stage, status, remote_account_id=remote_account_id)
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError
        return body
    except C2AError as exc:
        if exc.backend_identity is None:
            exc.backend_identity = config.backend_identity
        if exc.remote_account_id is None:
            exc.remote_account_id = remote_account_id
        raise
    except Exception as exc:
        error = _safe_request_error(stage, exc, remote_account_id=remote_account_id)
        error.backend_identity = config.backend_identity
        raise error from None


def _normalized_email(email: str) -> str:
    normalized = str(email or "").strip().casefold()
    if not normalized or "@" not in normalized or any(char.isspace() for char in normalized):
        raise C2AError("find_account", "c2a_account_identity_invalid", "本地账号缺少有效邮箱身份")
    return normalized


def _account_id(value: Any) -> str:
    account_id = str(value or "").strip()
    if not account_id or len(account_id) > 240 or any(char.isspace() for char in account_id):
        raise ValueError
    return account_id


def _list_matching_accounts(
    config: _ClientConfig,
    email: str,
    *,
    checkpoint: Callable[[], None] | None,
) -> list[dict[str, str]]:
    """按完整邮箱检索所有页面，并仅保留精确同邮箱行。"""
    matched: dict[str, dict[str, str]] = {}
    page = 1
    total: int | None = None
    while page <= _MAX_ACCOUNT_PAGES:
        body = _request_json(
            config,
            "get",
            "/api/accounts",
            stage="find_account",
            checkpoint=checkpoint,
            params={
                "page": page,
                "page_size": _PAGE_SIZE,
                "keyword": email,
                "status": "all",
                "group_id": "all",
                "memory_state": "all",
            },
        )
        items = body.get("items")
        raw_total = body.get("total")
        if isinstance(raw_total, bool):
            raise C2AError("find_account", "c2a_response_invalid", "C2A 账号列表分页信息无效", backend_identity=config.backend_identity)
        try:
            current_total = int(raw_total)
        except (TypeError, ValueError):
            raise C2AError("find_account", "c2a_response_invalid", "C2A 账号列表分页信息无效", backend_identity=config.backend_identity) from None
        if current_total < 0 or not isinstance(items, list):
            raise C2AError("find_account", "c2a_response_invalid", "C2A 账号列表格式无效", backend_identity=config.backend_identity)
        if total is None:
            total = current_total
        elif total != current_total:
            raise C2AError("find_account", "c2a_response_invalid", "C2A 账号列表在查询期间发生变化，请重新同步", backend_identity=config.backend_identity)
        for item in items:
            if not isinstance(item, dict):
                raise C2AError("find_account", "c2a_response_invalid", "C2A 账号列表包含无效记录", backend_identity=config.backend_identity)
            remote_email = str(item.get("email") or "").strip().casefold()
            if remote_email != email:
                continue
            try:
                remote_id = _account_id(item.get("id"))
            except ValueError:
                raise C2AError("find_account", "c2a_response_invalid", "C2A 同邮箱账号缺少有效管理 ID", backend_identity=config.backend_identity) from None
            matched[remote_id.casefold()] = {"id": remote_id, "email": remote_email}
        if total <= page * _PAGE_SIZE:
            return list(matched.values())
        page += 1
    raise C2AError("find_account", "c2a_pagination_limit", "C2A 账号查询超过分页保护上限", backend_identity=config.backend_identity)


def find_unique_account(
    email: str,
    *,
    expected_backend: str | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> dict[str, str]:
    """查找唯一的 C2A 同邮箱账号；未找到或重复时不进行任何写操作。"""
    normalized_email = _normalized_email(email)
    config = _capture_config(expected_backend)
    matches = _list_matching_accounts(config, normalized_email, checkpoint=checkpoint)
    if not matches:
        raise C2AError(
            "find_account",
            "c2a_account_missing",
            "C2A 中未找到同邮箱账号，未创建新账号",
            backend_identity=config.backend_identity,
        )
    if len(matches) != 1:
        raise C2AError(
            "find_account",
            "c2a_account_ambiguous",
            "C2A 中同一邮箱存在多条账号，未覆盖任何账号",
            backend_identity=config.backend_identity,
        )
    return {**matches[0], "backend_identity": config.backend_identity}


def _confirmed_update(body: dict[str, Any], remote_id: str) -> bool:
    updated = body.get("updated")
    if isinstance(updated, bool) or not isinstance(updated, int) or updated != 1:
        return False
    updated_ids = body.get("updated_ids")
    removed_ids = body.get("removed_ids")
    errors = body.get("errors")
    items = body.get("items")
    if not isinstance(updated_ids, list) or not isinstance(removed_ids, list) or not isinstance(errors, list) or not isinstance(items, list):
        return False
    if updated_ids != [remote_id]:
        return False
    if removed_ids or errors:
        return False
    return any(
        isinstance(item, dict) and item.get("id") == remote_id
        for item in items
    )


def update_account_access_token(
    remote_id: str,
    access_token: str,
    *,
    expected_backend: str | None = None,
    checkpoint: Callable[[], None] | None = None,
    safe_mutation_policy: SafeMutationPolicy | None = None,
) -> dict[str, Any]:
    """覆盖一个已确认 C2A 管理 ID 的 AT，并严格核验远端回执。

    调用方必须在创建远端写入意图前完成安全策略预检，并传入同一 C2A
    目标返回的 ``SafeMutationPolicy``。这里不隐式补做 GET，避免把只读
    安全检查误记成已经开始的远端写入。当前 C2A 通用更新接口会按远端规则
    处理凭据错误，调用方不得把本函数理解为“远端状态不会变化”。
    """
    try:
        account_id = _account_id(remote_id)
    except ValueError:
        raise C2AError("update_account", "c2a_remote_account_id_invalid", "C2A 目标账号管理 ID 无效") from None
    token = str(access_token or "").strip()
    if not token:
        raise C2AError("update_account", "c2a_local_access_token_missing", "本地账号缺少可同步的 Access Token", remote_account_id=account_id)
    config = _capture_config(expected_backend)
    if (
        not isinstance(safe_mutation_policy, SafeMutationPolicy)
        or safe_mutation_policy.backend_identity != config.backend_identity
    ):
        raise C2AError(
            "c2a_safety",
            "c2a_remote_policy_unverified",
            "尚未确认 C2A 自动清理策略，未更新远端账号",
            backend_identity=config.backend_identity,
            remote_account_id=account_id,
        )
    body = _request_json(
        config,
        "post",
        "/api/accounts/update",
        stage="update_account",
        checkpoint=checkpoint,
        remote_account_id=account_id,
        json={"id": account_id, "access_token": token},
    )
    if not _confirmed_update(body, account_id):
        raise C2AError(
            "update_account",
            "c2a_update_unconfirmed",
            "C2A 未返回可确认的 Access Token 更新回执",
            backend_identity=config.backend_identity,
            remote_account_id=account_id,
        )
    return {"id": account_id, "updated": True, "backend_identity": config.backend_identity}


def _confirmed_import(body: dict[str, Any], email: str) -> tuple[str, bool] | None:
    """只接受单账号、未同步且身份一致的完整导入回执。"""
    added, skipped, synced = (body.get(key) for key in ("added", "skipped", "synced"))
    if any(type(count) is not int for count in (added, skipped, synced)):
        return None
    if (added, skipped) not in {(1, 0), (0, 1)} or synced != 0:
        return None
    updated_ids, removed_ids, errors, items = (
        body.get(key) for key in ("updated_ids", "removed_ids", "errors", "items")
    )
    if any(not isinstance(value, list) for value in (updated_ids, removed_ids, errors, items)):
        return None
    if len(updated_ids) != 1 or len(items) != 1 or removed_ids or errors:
        return None
    try:
        remote_id = _account_id(updated_ids[0])
    except ValueError:
        return None
    item = items[0]
    if (
        not isinstance(item, dict)
        or item.get("id") != remote_id
        or str(item.get("email") or "").strip().casefold() != email
    ):
        return None
    return remote_id, added == 1


def create_account_access_token(
    email: str,
    access_token: str,
    *,
    expected_backend: str | None = None,
    checkpoint: Callable[[], None] | None = None,
    safe_mutation_policy: SafeMutationPolicy | None = None,
) -> dict[str, Any]:
    """新建缺失账号；去重跳过时返回管理 ID，由调用方另行覆盖 AT。"""
    normalized_email = _normalized_email(email)
    token = str(access_token or "").strip()
    if not token:
        raise C2AError("create_account", "c2a_local_access_token_missing", "本地账号缺少可同步的 Access Token")
    config = _capture_config(expected_backend)
    if (
        not isinstance(safe_mutation_policy, SafeMutationPolicy)
        or safe_mutation_policy.backend_identity != config.backend_identity
    ):
        raise C2AError(
            "c2a_safety", "c2a_remote_policy_unverified",
            "尚未确认 C2A 自动清理策略，未新建远端账号",
            backend_identity=config.backend_identity,
        )
    body = _request_json(
        config, "post", "/api/accounts", stage="create_account", checkpoint=checkpoint,
        json={
            "accounts": [{"email": normalized_email, "access_token": token}],
            "sync_after_import": False,
        },
    )
    confirmed = _confirmed_import(body, normalized_email)
    if confirmed is None:
        raise C2AError(
            "create_account", "c2a_create_unconfirmed", "C2A 未返回可确认的账号导入回执",
            backend_identity=config.backend_identity,
        )
    remote_id, created = confirmed
    return {"id": remote_id, "created": created, "updated": False, "backend_identity": config.backend_identity}
