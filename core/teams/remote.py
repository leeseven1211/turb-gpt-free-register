"""ChatGPT Team 远端边界，成员与邀请名单分别保留完整性证据。"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote, urlencode

from core.teams.auth import TeamAuthenticator, TeamRemoteError
from core.auth.state_machine import CancellationRequested
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost

_BASE = "https://chatgpt.com"
_CHECK = "/backend-api/accounts/check/v4-2023-04-27"
_ADMIN_ROLES = {"owner", "admin"}
_ROLES = {"account-owner": "owner", "account-admin": "admin",
          "standard-user": "member", "account-user": "member",
          "owner": "owner", "admin": "admin", "member": "member"}
_JOIN_ERRORS = {
    "workspace_paid_seat_capacity_exhausted": "工作区席位不足",
    "workspace_join_request_pending": "加入申请等待审批",
    "workspace_invite_seat_type_mismatch": "邀请席位类型不符",
    "autojoin_retry_pending": "工作区加入等待重试",
}


def _role(value):
    return _ROLES.get(str(value or ""), "unknown")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _integer(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


class TeamRemoteAdapter:
    """请求严格绑定管理/成员账号与 workspace，不修改个人会话。"""

    def __init__(self, *, auth=None, timeout=20, max_pages=1000):
        self.auth = auth or TeamAuthenticator()
        self.timeout = timeout
        self.max_pages = max_pages

    def _request(self, authentication, path, *, workspace_id=None, method="GET", body=None,
                 allow_empty=False):
        headers = authentication.session.get_chatgpt_headers(referer=_BASE + "/")
        headers["authorization"] = "Bearer " + authentication.access_token
        if workspace_id:
            headers["chatgpt-account-id"] = workspace_id
        try:
            kwargs = {"headers": headers, "timeout": self.timeout, "allow_redirects": False}
            if body is not None:
                kwargs["json"] = body
            response = getattr(authentication.session, method.lower())(_BASE + path, **kwargs)
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            raise
        except Exception as exception:
            from core.accounts.liveness.protocol.v2 import _reraise_control
            _reraise_control(exception)
            raise TeamRemoteError("team_remote_network_failed", "Team 远端请求网络失败") from None
        status = int(response.status_code)
        if not 200 <= status < 300:
            try:
                rejected = response.json()
            except Exception:
                rejected = {}
            if isinstance(rejected, dict):
                causes = [rejected.get("code")]
                causes.extend(value.get("code") for value in (rejected.get("detail"), rejected.get("error"))
                              if isinstance(value, dict))
                upstream_code = next((value for value in causes
                                      if isinstance(value, str) and value in _JOIN_ERRORS), None)
                if upstream_code:
                    raise TeamRemoteError(upstream_code, _JOIN_ERRORS[upstream_code], http_status=status)
            code = ("team_auth_required" if status == 401 else "team_permission_denied" if status == 403
                    else "team_invite_rate_limited" if status == 429 else
                    "team_workspace_unavailable" if status == 404 else "team_remote_http_failed")
            raise TeamRemoteError(code, f"Team 远端请求返回 HTTP {status}", http_status=status)
        if allow_empty and status == 204:
            return {}
        try:
            result = response.json()
        except Exception:
            if allow_empty and not str(getattr(response, "text", "") or "").strip():
                return {}
            raise TeamRemoteError("team_remote_response_invalid", "Team 远端响应不是 JSON") from None
        if not isinstance(result, dict):
            raise TeamRemoteError("team_remote_response_invalid", "Team 远端响应不是对象")
        return result

    def _discover(self, authentication, workspace_id=None):
        data = self._request(authentication, _CHECK, workspace_id=workspace_id)
        source = data.get("accounts")
        if not isinstance(source, dict):
            raise TeamRemoteError("team_remote_response_invalid", "工作区响应缺少 accounts")
        workspaces = {}
        for key, entry in source.items():
            if not isinstance(entry, dict) or not isinstance(entry.get("account"), dict):
                continue
            account = entry["account"]
            wid = str(account.get("account_id") or (key if key != "default" else "") or "")
            if not wid or wid in workspaces:
                continue
            if account.get("structure") != "workspace":
                continue
            entitlement = entry.get("entitlement") or {}
            remote_role = str(account.get("account_user_role") or "")
            role = _role(remote_role)
            workspaces[wid] = {
                "id": wid, "workspace_id": wid, "name": account.get("name") or account.get("display_name") or None,
                "type": "team", "workspace_type": "team",
                "plan_type": account.get("plan_type"), "role": role,
                "membership_confirmed": bool(account.get("account_user_id") and remote_role
                    and entry.get("can_access_with_session") is True
                    and account.get("is_deactivated") is not True),
                "remote_account_user_id": account.get("account_user_id"),
                "can_manage": False, "can_invite": False,
                "capabilities": {"read_members": None, "read_invitations": None, "invite_members": None},
                "permission_evidence": {"source": "accounts_check", "remote_role": remote_role},
                "purchased_seats": None,
                "subscription": {key: entitlement.get(key) for key in (
                    "has_active_subscription", "subscription_plan", "expires_at", "renews_at", "cancels_at")},
                "can_access_with_session": entry.get("can_access_with_session"),
            }
        return list(workspaces.values())

    def discover(self, account_id, target_workspace_id=None):
        with self.auth.open(account_id, target_workspace_id) as authentication:
            workspaces = self._discover(authentication, target_workspace_id)
            if target_workspace_id is not None:
                workspaces = [row for row in workspaces if row["workspace_id"] == target_workspace_id]
            for workspace in workspaces:
                if workspace["role"] not in _ADMIN_ROLES:
                    continue
                try:
                    wid = workspace["workspace_id"]
                    for collection in ("users", "invites"):
                        path = "/backend-api/accounts/" + quote(wid, safe="") + "/" + collection
                        payload = self._request(authentication, path + "?offset=0&limit=1",
                                                workspace_id=wid)
                        if not isinstance(payload.get("items"), list):
                            raise TeamRemoteError("team_remote_response_invalid", "权限核验名单格式不符")
                    workspace["can_manage"] = True
                    workspace["capabilities"].update(read_members=True, read_invitations=True)
                    workspace["permission_evidence"].update(source="remote_reads",
                        members_read=True, invitations_read=True, checked_at=_now())
                except TeamRemoteError as error:
                    workspace["permission_evidence"]["reason_code"] = error.code
            return {"account_id": account_id, "workspaces": workspaces, "checked_at": _now()}

    @staticmethod
    def _workspace(workspaces, workspace_id):
        matched = next((w for w in workspaces if w["workspace_id"] == workspace_id), None)
        if matched is None:
            raise TeamRemoteError("team_workspace_unavailable", "目标 Team 对当前账号不可见")
        return matched

    def _pages(self, authentication, workspace_id, collection):
        items, seen = [], set()
        offset, total = 0, None
        complete = False
        checked_at = _now()
        path = "/backend-api/accounts/" + quote(workspace_id, safe="") + "/" + collection
        for _ in range(self.max_pages):
            query = {"offset": offset, "limit": 100}
            if collection == "users":
                query["query"] = ""
            else:
                query["status"] = "invited"
            data = self._request(authentication, path + "?" + urlencode(query), workspace_id=workspace_id)
            page = data.get("items")
            page_total = _integer(data.get("total"))
            page_offset, limit = _integer(data.get("offset")), _integer(data.get("limit"))
            if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
                raise TeamRemoteError("team_remote_response_invalid", "Team 名单响应缺少有效 items")
            if page_offset != offset or limit is None or limit <= 0 or page_total is None:
                items.extend(page)
                break
            if total is None:
                total = page_total
            elif total != page_total:
                items.extend(page)
                break
            duplicate = False
            for row in page:
                identity = str(row.get("id") or row.get("account_user_id") or row.get("email") or "")
                if identity and identity in seen:
                    duplicate = True
                    continue
                if identity:
                    seen.add(identity)
                items.append(row)
            if duplicate or len(page) > limit or offset + len(page) > total:
                break
            offset += len(page)
            if offset == total:
                complete = True
                break
            if not page:
                break
        return items, complete, len(items) if complete else None, checked_at

    @staticmethod
    def _member(row):
        return {
            "remote_user_id": row.get("id"), "remote_account_user_id": row.get("account_user_id"),
            "email": row.get("email"), "name": row.get("name"), "role": _role(row.get("role")),
            "joined_at": row.get("created_time"), "membership_state": "joined",
        }

    @staticmethod
    def _invitation(row):
        remote_status = str(row.get("status") or "invited")
        state = {"2": "pending", "invited": "pending", "pending": "pending", "accepted": "accepted",
                 "revoked": "revoked", "expired": "expired"}.get(remote_status, "unconfirmed")
        return {
            "remote_invitation_id": row.get("id"), "id": row.get("id"),
            "email": row.get("email_address") or row.get("email"),
            "role": _role(row.get("role")), "status": remote_status, "invitation_state": state,
            "created_at": row.get("created_time"), "expires_at": row.get("expires_at"),
        }

    def snapshot(self, manager_account_id, workspace_id):
        with self.auth.open(manager_account_id, workspace_id) as authentication:
            workspace = self._workspace(self._discover(authentication, workspace_id), workspace_id)
            members, member_complete, member_count, members_at = self._pages(
                authentication, workspace_id, "users")
            invitations, invite_complete, invite_count, invitations_at = self._pages(
                authentication, workspace_id, "invites")
            workspace["can_manage"] = workspace["role"] in _ADMIN_ROLES
            workspace["capabilities"].update(read_members=True, read_invitations=True)
            workspace["permission_evidence"].update(
                members_read=True, invitations_read=True, checked_at=_now())
            return {
                "workspace": workspace, "workspace_id": workspace_id,
                "members": [self._member(row) for row in members],
                "invitations": [self._invitation(row) for row in invitations],
                "members_complete": member_complete, "invitations_complete": invite_complete,
                "confirmed_member_count": member_count, "pending_invite_count": invite_count,
                "purchased_seats": workspace["purchased_seats"],
                "members_checked_at": members_at, "invitations_checked_at": invitations_at,
                "checked_at": _now(),
            }

    def invite(self, manager_account_id, workspace_id, email):
        """按官方客户端协议发普通成员邀请；先续接已有邀请，再核验远端回执。"""
        normalized = str(email or "").strip().lower()
        if not normalized or "@" not in normalized:
            raise TeamRemoteError("parameter_invalid", "邀请目标邮箱无效", retryable=False)
        with self.auth.open(manager_account_id, workspace_id) as authentication:
            workspace = self._workspace(self._discover(authentication, workspace_id), workspace_id)
            if workspace["role"] not in _ADMIN_ROLES:
                raise TeamRemoteError("team_permission_denied", "管理账号没有已确认的管理角色")

            def find_invite():
                rows, complete, _, _ = self._pages(authentication, workspace_id, "invites")
                found = next((row for row in rows
                    if str(row.get("email_address") or row.get("email") or "").strip().lower() == normalized
                    and str(row.get("status", "invited")) in {"2", "invited", "pending"}), None)
                if found is None and not complete:
                    raise TeamRemoteError("team_invite_receipt_missing", "邀请名单尚未完整读取，请重跑核对")
                return found

            existing = find_invite()
            if existing is not None:
                return {"workspace_id": workspace_id, "invitation": self._invitation(existing),
                        "reused": True, "checked_at": _now()}
            path = "/backend-api/accounts/" + quote(workspace_id, safe="") + "/invites"
            # 官方客户端的 purchase_seats_if_needed 为独立可选分支；这里不启用购买。
            receipt = self._request(authentication, path, workspace_id=workspace_id, method="POST",
                                    body={"email_addresses": [normalized], "role": "standard-user"})
            rejected = receipt.get("rejected_emails") or []
            for row in rejected if isinstance(rejected, list) else []:
                if (isinstance(row, dict)
                        and str(row.get("email_address") or "").strip().lower() == normalized):
                    reason = str(row.get("reason_code") or row.get("reason") or row.get("code") or "")
                    safe_reason = reason if reason.replace("_", "").replace("-", "").isalnum() else ""
                    raise TeamRemoteError("team_invite_rejected", "远端拒绝了目标邀请",
                                          details={"remote_reason_code": safe_reason})
            uncertain = []
            for key in ("retry_email_addresses", "uncertain_email_addresses", "unattempted_email_addresses"):
                values = receipt.get(key)
                if isinstance(values, list):
                    uncertain.extend(str(value).strip().lower() for value in values)
            if normalized in uncertain:
                raise TeamRemoteError("team_invite_receipt_missing", "远端尚未确认目标邀请结果")
            confirmed = find_invite()
            if confirmed is None:
                raise TeamRemoteError("team_invite_receipt_missing", "邀请提交后尚未读取到目标邀请")
            return {"workspace_id": workspace_id, "invitation": self._invitation(confirmed),
                    "reused": False, "checked_at": _now()}

    def accept(self, account_id, workspace_id, invitation):
        """邮件邀请按受邀用户身份接受，不触发个人数据合并或管理审批接口。"""
        invitation = invitation if isinstance(invitation, dict) else {}
        invitation_workspace = invitation.get("workspace_id")
        if invitation_workspace and str(invitation_workspace) != str(workspace_id):
            raise TeamRemoteError("team_workspace_mismatch", "邀请工作区与目标 Team 不一致")
        with self.auth.open(account_id, workspace_id) as authentication:
            expected_email = str(invitation.get("email_snapshot") or invitation.get("email") or "").strip().lower()
            if expected_email and expected_email != authentication.email.strip().lower():
                raise TeamRemoteError("account_identity_changed", "受邀邮箱与成员认证身份不一致")
            current = self._verification(authentication, workspace_id)
            if current["joined"]:
                return {**current, "reused": True}
            path = "/backend-api/accounts/" + quote(workspace_id, safe="") + "/invites/accept"
            current_account = getattr(authentication, "session_info", {}).get("account") or {}
            current_workspace = current_account.get("id")
            self._request(authentication, path, workspace_id=current_workspace, method="POST", allow_empty=True)
            verified = self._verification(authentication, workspace_id)
            if not verified["joined"]:
                raise TeamRemoteError("team_member_unconfirmed", "接受邀请后成员关系尚未确认")
            return {**verified, "reused": False}

    def verify_member(self, account_id, workspace_id):
        with self.auth.open(account_id, workspace_id) as authentication:
            return self._verification(authentication, workspace_id)

    def _verification(self, authentication, workspace_id):
        workspaces = self._discover(authentication, workspace_id)
        workspace = next((w for w in workspaces if w["workspace_id"] == workspace_id), None)
        joined = bool(workspace and workspace["membership_confirmed"])
        member = None
        if joined:
            expected_account_user = authentication.user_id + "__" + workspace_id
            if workspace["remote_account_user_id"] != expected_account_user:
                raise TeamRemoteError("account_identity_changed", "成员关系证据属于其他用户身份")
            # 待接受邀请也会出现在 accounts/check；必须另取真实成员名单确认。
            path = "/backend-api/accounts/" + quote(workspace_id, safe="") + "/users?"
            payload = self._request(authentication, path + urlencode({
                "offset": 0, "limit": 10, "query": authentication.email}), workspace_id=workspace_id)
            rows = payload.get("items")
            if not isinstance(rows, list):
                raise TeamRemoteError("team_remote_response_invalid", "成员核验名单格式不符")
            matched = next((row for row in rows if isinstance(row, dict)
                and (str(row.get("id") or "") == authentication.user_id
                     or str(row.get("account_user_id") or "") == expected_account_user)), None)
            joined = matched is not None
            if joined:
                member = {"remote_user_id": authentication.user_id,
                          "remote_account_user_id": workspace["remote_account_user_id"],
                          "email": authentication.email, "role": _role(matched.get("role")) or workspace["role"],
                          "membership_state": "joined"}
        return {"joined": joined, "workspace_id": workspace_id, "member": member,
                "workspace": workspace, "checked_at": _now(),
                "auth_context": authentication.context(workspace_id) if joined else None}
