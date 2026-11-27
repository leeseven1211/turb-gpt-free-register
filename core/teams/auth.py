"""恢复 Team 只读认证，个人协议会话与账号材料保持独立。"""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from core.teams.errors import TeamError
from core.auth.state_machine import CancellationRequested
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost


class TeamRemoteError(TeamError):
    """远端阶段可分类、可重跑的失败，不携带认证材料。"""

    def __init__(self, code: str, message: str | None = None, *, retryable: bool = True,
                 http_status: int | None = None, details: dict | None = None):
        super().__init__(code, message, retryable=retryable, details=details)
        self.http_status = http_status


def _object(value: Any) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value if isinstance(value, dict) else {}


def verify_identity(account: dict, info: dict) -> None:
    """校验用户身份；个人 workspace 与目标 Team 不要求相等。"""
    from core.accounts.plans.client import token_claims

    user = _object(info.get("user"))
    email = str(account.get("email") or "").strip().lower()
    expected_user = str(account.get("user_id") or _object(account.get("user")).get("id") or "")
    if not email or str(user.get("email") or "").strip().lower() != email:
        raise TeamRemoteError("account_identity_changed", "认证邮箱与目标账号不一致")
    actual_user = str(user.get("id") or "")
    if not actual_user or (expected_user and actual_user != expected_user):
        raise TeamRemoteError("account_identity_changed", "认证用户与目标账号不一致")
    token = str(info.get("accessToken") or "")
    if token:
        claims = token_claims(token)
        if ((claims.get("email") and str(claims["email"]).strip().lower() != email)
                or (claims.get("user_id") and str(claims["user_id"]) != actual_user)):
            raise TeamRemoteError("account_identity_changed", "认证 Token 身份与目标账号不一致")
        current_workspace = str(_object(info.get("account")).get("id") or "")
        if (current_workspace and claims.get("account_id")
                and str(claims["account_id"]) != current_workspace):
            raise TeamRemoteError("account_identity_changed", "认证 Token 与当前工作区不一致")


def _close(session) -> None:
    """清理失败不覆盖原始业务结果或控制信号。"""
    if session is not None:
        try:
            session.session.close()
        except Exception:
            pass


def _raise_auth_error(exception: Exception, *, stage: str) -> None:
    from core.accounts.liveness.protocol.v2 import ProtocolV2AuthError, _reraise_control
    from core.auth.protocol.openai_auth import AccountUnusableError
    from core.operations.error_labels import label_for_code

    _reraise_control(exception)
    if isinstance(exception, TeamError):
        raise exception
    if isinstance(exception, AccountUnusableError):
        code = getattr(exception, "error_code", "")
        code = code if code in {"account_deactivated", "account_deleted", "account_banned"} else "account_deactivated"
        raise TeamRemoteError(code, "账号已停用", retryable=False) from None
    if isinstance(exception, ProtocolV2AuthError):
        code = exception.code
        message = label_for_code("cause_code", code) if isinstance(code, str) and code.isascii() else None
        if message:
            raise TeamRemoteError(code, message, retryable=exception.retryable) from None
    code, message = (
        ("team_auth_network_failed", "账号登录预检失败") if stage == "preflight" else
        ("team_auth_required", "账号登录尚未完成")
    )
    raise TeamRemoteError(code, message) from None


@dataclass
class TeamAuthentication:
    account_id: int
    email: str
    user_id: str
    access_token: str
    session: Any
    workspace_id: str | None
    session_info: dict

    def context(self, workspace_id: str) -> dict:
        """仅交付给私有加密仓储，不能进入公开响应或日志。"""
        return {
            "version": 1, "account_id": self.account_id, "email": self.email,
            "user_id": self.user_id, "workspace_id": workspace_id,
            "access_token": self.access_token,
            "session": {key: self.session_info[key] for key in ("user", "account", "sessionToken")
                        if key in self.session_info},
        }


class TeamAuthenticator:
    """在现有账号锁内恢复认证，不创建子任务，不写个人会话或凭据。"""

    def __init__(self, *, account_loader=None, account_session_loader=None,
                 context_loader=None, login_cache_loader=None, route_factory=None):
        self._account_loader = account_loader
        self._account_session_loader = account_session_loader
        self._context_loader = context_loader
        self._login_cache_loader = login_cache_loader
        self._route_factory = route_factory

    @contextmanager
    def open(self, account_id: int, workspace_id: str | None = None):
        from core.auth.protocol.session import BrowserSession
        from core.proxy.account_routes import acquire_account_proxy
        from core.storage import accounts

        account_loader = self._account_loader or accounts.get_account
        try:
            account = account_loader(int(account_id))
            if not account:
                raise TeamRemoteError("account_not_found", "目标账号不存在", retryable=False)
            email = str(account.get("email") or "").strip().lower()
            saved = _object(account.get("chatgpt_session"))
            if not saved:
                session_loader = self._account_session_loader or accounts.get_account_chatgpt_session
                saved = _object(session_loader(int(account_id)))
            # 普通账号读模型会剔除 Session；仅使用它补充同一用户的身份依据。
            account = {**account, "user_id": account.get("user_id") or _object(saved.get("user")).get("id")}
            context_loader = self._context_loader or self._load_context
            context = _object(context_loader(int(account_id), workspace_id, email)) if workspace_id else {}
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            raise
        except TeamError:
            raise
        except Exception as exception:
            from core.accounts.liveness.protocol.v2 import _reraise_control
            _reraise_control(exception)
            raise TeamRemoteError("team_auth_context_invalid", "账号认证材料读取失败") from None
        route = None
        session = None
        try:
            try:
                route_factory = self._route_factory or acquire_account_proxy
                route = route_factory(account_id=int(account_id), email=email, purpose="plan-check-team")
                session = BrowserSession(proxy=route.proxy_url, detect_exit_geo=False)
                info = self._reuse(session, account, saved, context)
                if info is None:
                    _close(session)
                    session = None
                    session, info = self._login(account, saved, route.proxy_url)
                verify_identity(account, info)
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except Exception as exception:
                _raise_auth_error(exception, stage="authenticate")
            # yield 的下游错误不进入恢复逻辑，防止已发送邀请后再次登录重放。
            yield TeamAuthentication(
                int(account_id), email, str(info["user"]["id"]), str(info["accessToken"]),
                session, workspace_id, info,
            )
        finally:
            _close(session)
            if route is not None:
                try:
                    route.release("completed")
                except Exception:
                    pass

    @staticmethod
    def _request(session, path, *, token=None):
        headers = session.get_chatgpt_headers(referer="https://chatgpt.com/")
        if token:
            headers["authorization"] = "Bearer " + token
        else:
            headers = session.get_nextauth_headers(referer="https://chatgpt.com/")
        try:
            result = session.get("https://chatgpt.com" + path, headers=headers,
                                 allow_redirects=False, timeout=20)
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            raise
        except Exception as exception:
            from core.accounts.liveness.protocol.v2 import _reraise_control
            _reraise_control(exception)
            raise TeamRemoteError("team_auth_network_failed", "读取账号会话时网络失败") from None
        if result.status_code == 401:
            return None
        if not 200 <= result.status_code < 300:
            raise TeamRemoteError("team_auth_required", "账号会话暂无法核验",
                                  http_status=result.status_code)
        try:
            value = result.json()
        except Exception:
            raise TeamRemoteError("team_auth_response_invalid", "账号会话响应无法解析") from None
        if not isinstance(value, dict):
            raise TeamRemoteError("team_auth_response_invalid", "账号会话响应格式不符")
        return value

    def _reuse(self, session, account, saved, context):
        from core.accounts.plans.client import normalize_token, token_claims
        from core.accounts.liveness.protocol import v3
        from core.storage.accounts import protocol_sessions

        target_saved = _object(context.get("session"))
        candidates = (
            (context.get("access_token"), target_saved),
            (account.get("access_token") or saved.get("accessToken"), saved),
        )
        seen = set()
        for candidate, material in candidates:
            candidate = normalize_token(str(candidate or ""))
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            claims = token_claims(candidate)
            if claims.get("token_expired") is True or not claims.get("user_id") or not claims.get("email"):
                continue
            # 不借用本地 user/email 给 opaque AT 伪造身份验证。
            info = {"user": {"id": claims["user_id"], "email": claims["email"]},
                    "account": {"id": claims.get("account_id")}, "accessToken": candidate}
            verify_identity(account, info)
            data = self._request(session, "/backend-api/accounts/check/v4-2023-04-27", token=candidate)
            if data is None:
                continue
            if not isinstance(data.get("accounts"), dict):
                raise TeamRemoteError("team_auth_response_invalid", "账号权限响应格式不符")
            if material:
                verify_identity(account, {**material, "accessToken": candidate,
                    "account": info["account"]})
                info = {**material, **info}
            return info
        for material in (target_saved, saved):
            cookie = str(material.get("sessionToken") or material.get("session_token") or "")
            if not cookie:
                continue
            session.session.cookies.set("__Secure-next-auth.session-token", cookie,
                                        domain="chatgpt.com", path="/")
            info = self._request(session, "/api/auth/session")
            if info and info.get("accessToken") and token_claims(info["accessToken"]).get("token_expired") is not True:
                verify_identity(account, info)
                return info
        # 只读取既有协议 Cookie；失效时不删除或覆盖个人缓存。
        cache_loader = self._login_cache_loader or protocol_sessions.load_session
        cached = cache_loader(int(account["id"]), account["email"])
        if cached:
            v3._restore_cookies(session, cached)
            info = self._request(session, "/api/auth/session")
            if info and info.get("accessToken") and token_claims(info["accessToken"]).get("token_expired") is not True:
                verify_identity(account, info)
                cached_user = str(cached.get("user_id") or "")
                if cached_user and info["user"]["id"] != cached_user:
                    raise TeamRemoteError("account_identity_changed", "已有会话与认证用户不一致")
                return info
        return None

    def _login(self, account, saved, proxy):
        from core.accounts.credentials import get_account_login_credentials
        from core.accounts.liveness.protocol import v3
        from core.auth.email_guard import email_auth_session

        session = None
        stage = "preflight"
        try:
            with email_auth_session(account["email"]):
                if self._account_loader is None:
                    password, secret = get_account_login_credentials(account["email"])
                else:
                    # 注入账号材料的离线恢复不再读取另一数据库里的同名账号；
                    # password 字段属于邮箱服务，不能当成 OpenAI 登录密码。
                    extra = _object(account.get("extra_json"))
                    password = str(
                        extra.get("account_password") or extra.get("login_password")
                        or extra.get("registration_password") or account.get("account_password")
                        or account.get("login_password") or account.get("registration_password") or ""
                    ).strip()
                    secret = str(account.get("totp_secret") or extra.get("totp_pending_secret") or "").strip()
                session, authorize = v3._network_preflight_with_retry(
                    account["email"], proxy, max_attempts=1,
                )
                stage = "authenticate"
                # 目标 Team 可能尚未加入：登录沿已有个人/可访问工作区，绝不
                # 把待接受 workspace 当作当前身份，也不调用写缓存的 _success。
                target = {**account, "chatgpt_session": saved}
                info, _methods = v3._authenticate(
                    session, authorize, email=account["email"], target=target,
                    password=password, secret=secret, progress={"methods": [], "attempted": ""},
                )
                if not isinstance(info, dict) or not str(info.get("accessToken") or "").strip():
                    raise TeamRemoteError("team_auth_response_invalid", "账号登录未取得有效会话")
                from core.accounts.plans.client import token_claims
                if token_claims(info["accessToken"]).get("token_expired") is True:
                    raise TeamRemoteError("team_auth_required", "账号登录返回过期会话")
                verify_identity(account, info)
                return session, info
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            _close(session)
            raise
        except Exception as exception:
            _close(session)
            _raise_auth_error(exception, stage=stage)

    @staticmethod
    def _load_context(account_id: int, workspace_id: str, email: str) -> dict:
        from core.storage.teams import repository
        from core.storage.runtime_config import RuntimeConfigStoreError, decrypt_private_text

        row = repository.find_auth_context(account_id, workspace_id)
        if not row:
            return {}
        try:
            value = json.loads(decrypt_private_text(row["encrypted_context"]))
        except (ValueError, TypeError, KeyError, RuntimeConfigStoreError):
            raise TeamRemoteError("team_auth_context_invalid", "工作区认证材料无法恢复") from None
        if (not isinstance(value, dict) or value.get("account_id") != account_id
                or value.get("workspace_id") != workspace_id
                or str(value.get("email") or "").strip().lower() != email):
            raise TeamRemoteError("account_identity_changed", "工作区认证材料与目标身份不一致")
        return value
