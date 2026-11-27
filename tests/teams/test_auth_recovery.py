"""Team 复用账号登录时的身份、恢复和个人会话隔离回归。"""
from __future__ import annotations

import base64
import json
import unittest
from contextlib import ExitStack
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.teams.auth import TeamAuthenticator, TeamRemoteError

_LOAD_CONTEXT = TeamAuthenticator._load_context


def token(*, email="member@example.test", user="user-member", workspace="personal", expired=False):
    payload = {
        "exp": 1 if expired else 4_102_444_800,
        "https://api.openai.com/profile": {"email": email},
        "https://api.openai.com/auth": {
            "chatgpt_user_id": user, "chatgpt_account_id": workspace,
        },
    }
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return encode({"alg": "none"}) + "." + encode(payload) + ".test"


def session_info(access_token=None, *, email="member@example.test", user="user-member", workspace="personal"):
    return {
        "user": {"id": user, "email": email}, "account": {"id": workspace},
        "accessToken": access_token or token(email=email, user=user, workspace=workspace),
        "sessionToken": "测试私有Cookie",
    }


class HttpSession:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.session = SimpleNamespace(cookies=Mock(), close=Mock())
        self.proxy = "http://proxy.invalid"
        self.requests = []

    def get_chatgpt_headers(self, **_kwargs):
        return {}

    def get_nextauth_headers(self, **_kwargs):
        return {}

    def get_auth_headers(self, **_kwargs):
        return {}

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def response(data, status=200):
    return SimpleNamespace(status_code=status, json=lambda: data)


class TeamAuthRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.account = {"id": 7, "email": "member@example.test", "user_id": "user-member"}
        self.route = SimpleNamespace(proxy_url="http://proxy.invalid", release=Mock())
        self.sessions = []
        self.stack.enter_context(patch("core.storage.accounts.get_account", return_value=self.account))
        self.saved = self.stack.enter_context(
            patch("core.storage.accounts.get_account_chatgpt_session", return_value=None))
        self.stack.enter_context(
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=self.route))
        self.stack.enter_context(
            patch.object(TeamAuthenticator, "_load_context", return_value={}))
        self.stack.enter_context(
            patch("core.storage.accounts.protocol_sessions.load_session", return_value=None))
        self.credentials = self.stack.enter_context(
            patch("core.accounts.credentials.get_account_login_credentials", return_value=("测试密码", "测试TOTP")))
        self.preflight = self.stack.enter_context(
            patch("core.accounts.liveness.protocol.v3._network_preflight_with_retry"))
        from core.accounts.liveness.protocol import v3
        self.original_authenticate = v3._authenticate
        self.authenticate = self.stack.enter_context(
            patch("core.accounts.liveness.protocol.v3._authenticate"))
        self.cache_save = self.stack.enter_context(
            patch("core.storage.accounts.protocol_sessions.save_session",
                  side_effect=AssertionError("不得覆盖个人会话")))
        self.account_save = self.stack.enter_context(
            patch("core.storage.accounts.update_account_liveness",
                  side_effect=AssertionError("不得覆盖账号个人凭据")))
        self.stack.enter_context(
            patch("core.storage.accounts.device_profiles.remember_session",
                  side_effect=AssertionError("不得写个人设备会话")))
        self.stack.enter_context(
            patch("core.auth.protocol.session.BrowserSession", side_effect=self.browser))

    def browser(self, **_kwargs):
        session = self.sessions.pop(0)
        return session

    def login_boundary(self, info=None):
        fresh = HttpSession()
        self.preflight.return_value = fresh, "https://auth.openai.com/log-in/password"
        self.authenticate.return_value = info or session_info(), ["password", "email_otp", "mfa"]
        return fresh

    def test_password_only_account_recovers_inline_without_personal_writes(self):
        fresh = self.login_boundary()
        self.sessions = [HttpSession()]
        with TeamAuthenticator().open(7, "not-joined-yet") as authentication:
            self.assertEqual(authentication.session, fresh)
            self.assertEqual(authentication.user_id, "user-member")
            self.assertEqual(authentication.workspace_id, "not-joined-yet")
            target = self.authenticate.call_args.kwargs["target"]
            self.assertNotEqual(target.get("chatgpt_account_id"), "not-joined-yet")
        self.assertEqual(self.authenticate.call_args.kwargs["password"], "测试密码")
        self.assertEqual(self.authenticate.call_args.kwargs["secret"], "测试TOTP")
        fresh.session.close.assert_called_once()
        self.route.release.assert_called_once()
        self.cache_save.assert_not_called()
        self.account_save.assert_not_called()

    def test_rejected_stored_token_falls_back_to_existing_login(self):
        self.account["access_token"] = token()
        stale = HttpSession([response({}, 401)])
        self.sessions = [stale]
        fresh = self.login_boundary()
        with TeamAuthenticator().open(7) as authentication:
            self.assertIs(authentication.session, fresh)
        self.assertTrue(any("accounts/check" in url for url, _ in stale.requests))
        self.assertEqual(self.authenticate.call_count, 1)

    def test_valid_target_context_is_preferred_and_not_saved_to_personal_account(self):
        preferred = token(workspace="team-a")
        self.account["access_token"] = token(workspace="personal")
        context = {
            "account_id": 7, "email": self.account["email"], "workspace_id": "team-a",
            "access_token": preferred, "session": session_info(preferred, workspace="team-a"),
        }
        self.stack.enter_context(patch.object(TeamAuthenticator, "_load_context", return_value=context))
        self.sessions = [HttpSession([response({"accounts": {}})])]
        with TeamAuthenticator().open(7, "team-a") as authentication:
            self.assertEqual(authentication.access_token, preferred)
            saved = authentication.context("team-a")
            self.assertEqual(saved["account_id"], 7)
            self.assertEqual(saved["workspace_id"], "team-a")
        self.authenticate.assert_not_called()

    def test_expired_target_context_can_reuse_valid_personal_token(self):
        personal = token()
        self.account["access_token"] = personal
        self.stack.enter_context(patch.object(TeamAuthenticator, "_load_context", return_value={
            "access_token": token(workspace="team-a", expired=True),
            "session": {"user": {"id": "user-member", "email": "member@example.test"}},
        }))
        self.sessions = [HttpSession([response({"accounts": {}})])]
        with TeamAuthenticator().open(7, "team-a") as authentication:
            self.assertEqual(authentication.access_token, personal)
        self.authenticate.assert_not_called()

    def test_opaque_token_never_borrows_local_identity_as_proof(self):
        self.account["access_token"] = "opaque私有AT"
        self.sessions = [HttpSession()]
        fresh = self.login_boundary()
        with TeamAuthenticator().open(7) as authentication:
            self.assertEqual(authentication.session, fresh)
            self.assertNotEqual(authentication.access_token, "opaque私有AT")
        self.authenticate.assert_called_once()

    def test_cookie_restore_validates_server_identity_before_yield(self):
        saved = session_info()
        saved.pop("accessToken")
        self.saved.return_value = saved
        browser = HttpSession([response(session_info(email="other@example.test", user="other"))])
        self.sessions = [browser]
        with self.assertRaises(TeamRemoteError) as raised:
            with TeamAuthenticator().open(7):
                self.fail("错误用户不得取得认证上下文")
        self.assertEqual(raised.exception.code, "account_identity_changed")
        self.authenticate.assert_not_called()

    def test_login_challenges_receive_empty_password_for_otp_only_account(self):
        self.credentials.return_value = "", ""
        self.sessions = [HttpSession()]
        self.login_boundary()
        with TeamAuthenticator().open(7):
            pass
        self.assertEqual(self.authenticate.call_args.kwargs["password"], "")
        self.assertEqual(self.authenticate.call_args.kwargs["secret"], "")

    def test_login_result_with_different_user_is_rejected_and_closed(self):
        self.sessions = [HttpSession()]
        fresh = self.login_boundary(session_info(email="other@example.test", user="other"))
        with self.assertRaises(TeamRemoteError) as raised:
            with TeamAuthenticator().open(7):
                self.fail("登录身份不符不得继续")
        self.assertEqual(raised.exception.code, "account_identity_changed")
        fresh.session.close.assert_called_once()

    def test_login_error_uses_fixed_code_and_summary_without_private_text(self):
        from core.accounts.liveness.protocol.v2 import ProtocolV2AuthError

        self.sessions = [HttpSession()]
        self.login_boundary()
        self.authenticate.side_effect = ProtocolV2AuthError(
            "password_rejected", "测试密码 OTP=123456 Cookie=private")
        with self.assertRaises(TeamRemoteError) as raised:
            with TeamAuthenticator().open(7):
                pass
        self.assertEqual(raised.exception.code, "password_rejected")
        self.assertNotIn("123456", str(raised.exception))
        self.assertNotIn("private", str(raised.exception))

    def test_cancellation_is_not_reclassified_as_auth_failure(self):
        from core.operations.runtime import OperationCancelled

        self.sessions = [HttpSession()]
        fresh = self.login_boundary()
        cancellation = OperationCancelled("用户停止")
        self.authenticate.side_effect = cancellation
        with self.assertRaises(OperationCancelled) as raised:
            with TeamAuthenticator().open(7):
                pass
        self.assertIs(raised.exception, cancellation)
        fresh.session.close.assert_called_once()

    def test_caller_remote_error_after_yield_does_not_repeat_login(self):
        self.sessions = [HttpSession()]
        self.login_boundary()
        with self.assertRaises(TeamRemoteError) as raised:
            with TeamAuthenticator().open(7):
                raise TeamRemoteError("team_invite_rejected", "邀请被拒")
        self.assertEqual(raised.exception.code, "team_invite_rejected")
        self.assertEqual(self.authenticate.call_count, 1)

    def test_bad_decryption_is_classified_without_exposing_ciphertext(self):
        from core.storage.runtime_config import RuntimeConfigStoreError

        self.stack.enter_context(patch("core.storage.teams.repository.find_auth_context",
            return_value={"encrypted_context": "测试私有密文"}))
        self.stack.enter_context(patch("core.storage.runtime_config.decrypt_private_text",
            side_effect=RuntimeConfigStoreError("decryption_failed")))
        # 直接调用未替换的静态方法，避免 open 的测试替身掩盖恢复失败。
        with self.assertRaises(TeamRemoteError) as raised:
            _LOAD_CONTEXT(7, "team-a", self.account["email"])
        self.assertEqual(raised.exception.code, "team_auth_context_invalid")
        self.assertNotIn("测试私有密文", str(raised.exception))

    def test_injected_loaders_never_read_default_account_or_context_sources(self):
        self.stack.enter_context(patch("core.storage.accounts.get_account",
            side_effect=AssertionError("不得读取生产账号")))
        self.stack.enter_context(patch("core.storage.accounts.get_account_chatgpt_session",
            side_effect=AssertionError("不得读取生产Session")))
        self.stack.enter_context(patch("core.storage.accounts.protocol_sessions.load_session",
            side_effect=AssertionError("不得读取生产缓存")))
        self.stack.enter_context(patch("core.storage.teams.repository.find_auth_context",
            side_effect=AssertionError("不得读取生产Team上下文")))
        browser = HttpSession([response({"accounts": {}})])
        self.sessions = [browser]
        owner = {**self.account, "access_token": token()}
        auth = TeamAuthenticator(
            account_loader=lambda account_id: owner if account_id == 7 else None,
            account_session_loader=lambda _account_id: None,
            context_loader=lambda _account_id, _workspace, _email: {},
            login_cache_loader=lambda _account_id, _email: None,
            route_factory=lambda **_kwargs: self.route,
        )
        with auth.open(7, "team-a") as authentication:
            self.assertEqual(authentication.email, owner["email"])
        self.authenticate.assert_not_called()

    def test_injected_password_materials_do_not_load_default_credentials(self):
        owner = {
            **self.account, "account_password": "内存密码", "totp_secret": "内存TOTP",
        }
        self.stack.enter_context(patch("core.accounts.credentials.get_account_login_credentials",
            side_effect=AssertionError("不得读取生产凭据")))
        self.stack.enter_context(patch("core.auth.email_guard.email_auth_session",
                                      return_value=nullcontext()))
        self.sessions = [HttpSession()]
        self.login_boundary()
        auth = TeamAuthenticator(
            account_loader=lambda _account_id: owner,
            account_session_loader=lambda _account_id: None,
            context_loader=lambda *_args: {},
            login_cache_loader=lambda *_args: None,
            route_factory=lambda **_kwargs: self.route,
        )
        with auth.open(7):
            pass
        self.assertEqual(self.authenticate.call_args.kwargs["password"], "内存密码")
        self.assertEqual(self.authenticate.call_args.kwargs["secret"], "内存TOTP")

    def test_wrapped_cancellation_is_preserved_without_exposing_wrapper(self):
        from core.operations.runtime import OperationCancelled

        self.sessions = [HttpSession()]
        fresh = self.login_boundary()
        cancellation = OperationCancelled("用户停止")
        wrapper = RuntimeError("私有OTP=123456")
        wrapper.__cause__ = cancellation
        self.authenticate.side_effect = wrapper
        with self.assertRaises(OperationCancelled) as raised:
            with TeamAuthenticator().open(7):
                pass
        self.assertIs(raised.exception, cancellation)
        fresh.session.close.assert_called_once()

    def test_cached_token_does_not_carry_another_users_cookie(self):
        self.account["access_token"] = token()
        self.saved.return_value = session_info(email="other@example.test", user="other")
        self.sessions = [HttpSession([response({"accounts": {}})])]
        with self.assertRaises(TeamRemoteError) as raised:
            with TeamAuthenticator().open(7):
                self.fail("不能将其他用户Cookie附到本账号上下文")
        self.assertEqual(raised.exception.code, "account_identity_changed")

    def test_http_200_without_accounts_is_not_an_authenticated_token_probe(self):
        self.account["access_token"] = token()
        self.sessions = [HttpSession([response({"page": "login"})])]
        with self.assertRaises(TeamRemoteError) as raised:
            with TeamAuthenticator().open(7):
                self.fail("认证壳不能作为AT有效证据")
        self.assertEqual(raised.exception.code, "team_auth_response_invalid")

    def test_account_material_read_failure_has_safe_public_summary(self):
        auth = TeamAuthenticator(account_loader=Mock(side_effect=RuntimeError("私有DSN和Cookie")))
        with self.assertRaises(TeamRemoteError) as raised:
            with auth.open(7):
                pass
        self.assertEqual(raised.exception.code, "team_auth_context_invalid")
        self.assertNotIn("DSN", str(raised.exception))

    def test_existing_login_kernel_completes_password_otp_and_totp_in_same_session(self):
        self.sessions = [HttpSession()]
        fresh = self.login_boundary()
        self.authenticate.side_effect = self.original_authenticate
        self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._follow",
            side_effect=lambda _session, url, **_kwargs: url))
        self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._client_auth_context", return_value={}))
        self.stack.enter_context(patch("core.accounts.liveness.protocol.v3.account_email_is_invalid", return_value=False))
        password = self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._password_verify",
            return_value={"continue_url": "https://auth.openai.com/email-verification"}))
        send = self.stack.enter_context(patch("core.accounts.liveness.protocol.v3.send_email_otp"))
        otp = self.stack.enter_context(patch("core.accounts.liveness.protocol.v3.wait_for_otp",
                                             return_value="测试OTP"))
        post = self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._post_json",
            return_value={"continue_url": "https://auth.openai.com/mfa-challenge"}))
        self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._factor", return_value="factor"))
        issue = self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._mfa_issue_challenge"))
        self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._totp_code", return_value="测试动态码"))
        mfa = self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._mfa_verify",
            return_value={"continue_url": "https://chatgpt.com/api/auth/callback/openai"}))
        self.stack.enter_context(patch("core.accounts.liveness.protocol.v3._read_session",
                                      return_value=session_info()))
        with TeamAuthenticator().open(7, "not-joined-yet") as authentication:
            self.assertIs(authentication.session, fresh)
        password.assert_called_once_with(fresh, "测试密码")
        send.assert_called_once_with(fresh)
        self.assertEqual(otp.call_args.args, ("member@example.test",))
        self.assertEqual(post.call_args.kwargs["payload"], {"code": "测试OTP"})
        issue.assert_called_once_with(fresh, "factor")
        mfa.assert_called_once_with(fresh, "factor", "测试动态码")
        self.cache_save.assert_not_called()
