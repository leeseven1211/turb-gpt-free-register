"""补密码只复用在线确认且身份匹配的 Cookie，故障不得伪装为会话失效。"""
import base64
import copy
import json
import unittest
from contextlib import ExitStack
from http.cookiejar import CookieJar
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.accounts.password_setup import session as reuse

EMAIL = "password-session@example.test"
INFO = {"accessToken": "fixture-at", "user": {"email": EMAIL, "id": "fixture-user"},
        "account": {"id": "fixture-account"}}
PROFILE = {"screen_width": 1920, "screen_height": 1080, "device_pixel_ratio": 1,
           "hardware_concurrency": 8, "device_memory": 8, "js_heap_size_limit": 4096000000}
CACHE = {"device_id": "fixture-device", "browser_profile": PROFILE,
         "user_id": "fixture-user", "chatgpt_account_id": "fixture-account", "cookies": [
             {"name": "__Secure-next-auth.session-token", "value": "fixture-session-cookie",
              "domain": ".chatgpt.com", "path": "/", "secure": True, "expires": None}]}


class Response:
    def __init__(self, payload=None, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class Session:
    def __init__(self, response):
        self.get = Mock(side_effect=response if isinstance(response, Exception) else None,
                        return_value=response)
        self.session = SimpleNamespace(cookies=CookieJar(), close=Mock())
        self.device_id = "fixture-device"
        self.browser_profile = {**PROFILE, "not_a_profile_field": "private-fixture"}

    def get_nextauth_headers(self, *, referer):
        return {"referer": referer}


class PasswordSetupSessionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.account = {"id": 7, "email": EMAIL, "user_id": "fixture-user",
                        "chatgpt_account_id": "fixture-account"}
        self.cached = copy.deepcopy(CACHE)
        self.client = Session(Response(copy.deepcopy(INFO)))
        self.load = self.stack.enter_context(patch.object(reuse.protocol_sessions, "load_session",
                                                        return_value=self.cached))
        self.private_session = self.stack.enter_context(patch.object(reuse.db, "get_account_chatgpt_session",
                                                                   return_value=None))
        self.save = self.stack.enter_context(patch.object(reuse.protocol_sessions, "save_session"))
        self.invalidate = self.stack.enter_context(patch.object(reuse.protocol_sessions, "invalidate_session"))
        self.browser = self.stack.enter_context(patch.object(reuse, "BrowserSession", return_value=self.client))

    def open(self, **kwargs):
        return reuse.try_reuse_session(self.account, EMAIL, proxy=None, **kwargs)

    def test_verified_cookie_session_skips_password_verification_and_closes_after_use(self):
        supplier, checkpoint = Mock(return_value="fixture-route"), Mock()
        with self.open(proxy_supplier=supplier, checkpoint=checkpoint) as restored:
            auth, session = restored
            self.assertIs(self.client, session)
            self.assertEqual(INFO, auth["session"])
            self.assertTrue(auth["session_reused"])
            self.assertEqual("session_cookie", auth["auth_method"])
            self.assertEqual("skipped", auth["password_auth_status"])
            self.assertEqual("fixture-at", auth["access_token"])
            self.assertFalse(self.client.session.close.called)
            cookies = list(self.client.session.cookies)
            self.assertEqual("fixture-session-cookie", cookies[0].value)
            self.client.get.assert_called_once_with("https://chatgpt.com/api/auth/session",
                headers={"referer": "https://chatgpt.com/"}, allow_redirects=False)
        self.client.session.close.assert_called_once_with()
        supplier.assert_called_once_with(1)
        self.assertGreaterEqual(checkpoint.call_count, 6)
        self.assertEqual("fixture-route", self.browser.call_args.kwargs["proxy"])
        self.private_session.assert_not_called()

    def test_absent_cache_does_not_open_client_or_acquire_an_extra_route(self):
        self.account.update(access_token="fixture-at", chatgpt_session=json.dumps(INFO))
        self.load.return_value = None
        supplier = Mock()
        with self.open(proxy_supplier=supplier) as restored:
            self.assertIsNone(restored)
        self.browser.assert_not_called()
        supplier.assert_not_called()

    def test_saved_session_token_accepts_json_dict_and_both_field_names(self):
        self.load.return_value = None
        for encoded in (False, True):
            for token_key in ("sessionToken", "session_token"):
                with self.subTest(encoded=encoded, token_key=token_key):
                    saved = {**copy.deepcopy(INFO), token_key: "fixture-saved-session"}
                    self.account["chatgpt_session"] = json.dumps(saved) if encoded else saved
                    with self.open() as restored:
                        auth, client = restored
                        self.assertIs(self.client, client)
                        self.assertTrue(auth["session_reused"])
                        self.assertEqual("session_token", auth["auth_method"])
                        self.assertEqual("skipped", auth["password_auth_status"])
                        cookies = list(client.session.cookies)
                        self.assertEqual("fixture-saved-session", cookies[0].value)
                        self.assertEqual("chatgpt.com", cookies[0].domain)
                        self.assertNotIn("fixture-saved-session", str(auth))
                    self.assertNotIn("identity", self.browser.call_args.kwargs)
        self.assertEqual(4, self.client.get.call_count)
        self.assertEqual(4, self.client.session.close.call_count)
        self.invalidate.assert_not_called()

    def test_private_session_reader_supplies_token_missing_from_public_account(self):
        self.load.return_value = None
        self.private_session.return_value = {**INFO, "sessionToken": "fixture-private-session"}
        original = copy.deepcopy(self.account)
        with self.open() as restored:
            auth, client = restored
            self.assertEqual("session_token", auth["auth_method"])
            self.assertEqual("fixture-private-session", list(client.session.cookies)[0].value)
            self.assertNotIn("fixture-private-session", str(auth))
        self.private_session.assert_called_once_with(7)
        self.assertEqual(original, self.account)

    def test_private_session_read_failure_is_classified_without_login_or_private_error(self):
        self.load.return_value = None
        self.private_session.side_effect = RuntimeError("fixture-private-session")
        with self.assertRaises(reuse.ProtocolPasswordSetupError) as caught, self.open():
            self.fail("凭据读取失败不能当成会话失效")
        self.assertEqual("password_setup_runtime_failed", caught.exception.code)
        self.assertNotIn("fixture-private-session", str(caught.exception))
        self.browser.assert_not_called()
        signal = reuse.OperationLeaseLost("fixture-stop")
        self.private_session.side_effect = signal
        with self.assertRaises(reuse.OperationLeaseLost) as caught, self.open():
            self.fail("凭据读取必须保留租约失效")
        self.assertIs(signal, caught.exception)

    def test_saved_session_preserves_device_id_and_caches_actual_new_profile(self):
        self.load.return_value = None
        self.account.update(chatgpt_session={**INFO, "sessionToken": "fixture-saved-session"},
                            extra_json=json.dumps({"device_id": "saved-device"}))
        with patch.object(reuse, "pick_browser_profile", return_value=copy.deepcopy(PROFILE)) as profile:
            with self.open() as restored:
                auth, client = restored
                reuse.cache_authenticated_session(client, auth["session"], 7, EMAIL)
        profile.assert_called_once_with()
        self.assertEqual({"device_id": "saved-device", "browser_profile": PROFILE},
                         self.browser.call_args.kwargs["identity"])
        saved_payload = self.save.call_args.args[2]
        self.assertEqual(self.client.device_id, saved_payload["device_id"])
        self.assertEqual(PROFILE, saved_payload["browser_profile"])
        self.assertEqual("fixture-saved-session", saved_payload["cookies"][0]["value"])

    def test_private_cookie_cache_takes_precedence_over_saved_session_token(self):
        self.account["chatgpt_session"] = {**INFO, "sessionToken": "fixture-saved-session"}
        with self.open() as restored:
            auth, client = restored
            self.assertEqual("session_cookie", auth["auth_method"])
            self.assertEqual("fixture-session-cookie", list(client.session.cookies)[0].value)
        self.client.get.assert_called_once()
        self.private_session.assert_not_called()

    def test_invalid_private_cache_does_not_hide_a_saved_session_token(self):
        self.load.return_value = {**CACHE, "browser_profile": {}}
        self.private_session.return_value = {**INFO, "sessionToken": "fixture-private-session"}
        with self.open() as restored:
            auth, client = restored
            self.assertEqual("session_token", auth["auth_method"])
            self.assertEqual("fixture-private-session", list(client.session.cookies)[0].value)
        self.browser.assert_called_once()
        self.invalidate.assert_called_once_with(7, EMAIL)

    def test_expired_or_wrong_private_session_closes_before_trying_saved_token(self):
        for first_response in (Response({}, 401),
                               Response({**INFO, "user": {"email": "other@example.test", "id": "fixture-user"}})):
            with self.subTest(status=first_response.status_code):
                first, second = Session(first_response), Session(Response(copy.deepcopy(INFO)))
                def create_client(**kwargs):
                    if not first.get.called:
                        return first
                    first.session.close.assert_called_once_with()
                    return second
                self.browser.side_effect = create_client
                self.private_session.return_value = {**INFO, "sessionToken": "fixture-private-session"}
                supplier = Mock(return_value="fixture-route")
                with self.open(proxy_supplier=supplier) as restored:
                    auth, client = restored
                    self.assertIs(second, client)
                    self.assertEqual("session_token", auth["auth_method"])
                first.get.assert_called_once()
                second.get.assert_called_once()
                second.session.close.assert_called_once_with()
                supplier.assert_called_once_with(1)
        self.assertEqual(2, self.invalidate.call_count)

    def test_both_session_sources_are_attempted_at_most_once(self):
        first, second = Session(Response({}, 401)), Session(Response({}, 401))
        self.browser.side_effect = [first, second]
        self.private_session.return_value = {**INFO, "sessionToken": "fixture-private-session"}
        with self.open() as restored:
            self.assertIsNone(restored)
        self.assertEqual(2, self.browser.call_count)
        first.session.close.assert_called_once_with()
        second.session.close.assert_called_once_with()
        self.private_session.assert_called_once_with(7)
        self.invalidate.assert_called_once_with(7, EMAIL)

    def test_expired_or_mismatched_saved_token_falls_back_without_changing_original_data(self):
        self.load.return_value = None
        self.account["chatgpt_session"] = json.dumps({**INFO, "sessionToken": "fixture-saved-session"})
        original = copy.deepcopy(self.account)
        expired = base64.urlsafe_b64encode(json.dumps({"exp": 1}).encode()).decode().rstrip("=")
        responses = (Response({}, 401), Response({}),
                     Response({**INFO, "accessToken": f"fixture.{expired}.signature"}),
                     Response({**INFO, "user": {"email": "other@example.test", "id": "fixture-user"}}))
        for response in responses:
            with self.subTest(status=response.status_code):
                self.client.get.return_value = response
                with self.open() as restored:
                    self.assertIsNone(restored)
                self.assertEqual(original, self.account)
        self.invalidate.assert_not_called()
        self.save.assert_not_called()

    def test_saved_session_identity_is_checked_separately_from_target_account(self):
        self.load.return_value = None
        self.account["chatgpt_session"] = {**INFO, "sessionToken": "fixture-saved-session",
                                           "user": {"email": EMAIL, "id": "different-saved-user"}}
        with self.open() as restored:
            self.assertIsNone(restored)
        self.invalidate.assert_not_called()

    def test_saved_token_network_and_wrapped_cancellation_keep_existing_semantics(self):
        self.load.return_value = None
        self.account["chatgpt_session"] = {**INFO, "sessionToken": "fixture-saved-session"}
        self.client.get.side_effect = RuntimeError("Proxy CONNECT aborted fixture-saved-session")
        with self.assertRaises(reuse.ProtocolPasswordSetupError) as caught, self.open():
            self.fail("保存的凭据发生网络故障时不能假定会话过期")
        self.assertEqual("password_setup_network_failed", caught.exception.code)
        self.assertTrue(caught.exception.proxy_transport_failed)
        self.assertNotIn("fixture-saved-session", str(caught.exception))
        signal = reuse.CancellationRequested("fixture-stop")
        self.client.get.side_effect = signal
        with self.assertRaises(reuse.CancellationRequested) as caught, self.open():
            self.fail("保存的凭据校验也必须传递取消")
        self.assertIs(signal, caught.exception)
        self.invalidate.assert_not_called()

    def test_missing_or_broken_cookie_cache_falls_back_without_network(self):
        for changed in ({"cookies": []}, {"cookies": [{"domain": "foreign.example"}]},
                        {"cookies": [{"domain": "chatgpt.com", "name": "x", "value": "y", "expires": "bad"}]},
                        {"device_id": ""}, {"browser_profile": None}):
            with self.subTest(changed=changed):
                self.load.return_value = {**copy.deepcopy(CACHE), **changed}
                with self.open() as restored:
                    self.assertIsNone(restored)
                self.client.get.assert_not_called()
        self.assertEqual(5, self.invalidate.call_count)

    def test_incomplete_device_profile_falls_back_before_client_or_route_acquisition(self):
        profiles = [{}, None, *({key: value for key, value in PROFILE.items() if key != missing}
                               for missing in PROFILE)]
        supplier = Mock()
        for profile in profiles:
            with self.subTest(profile=profile):
                self.load.return_value = {**copy.deepcopy(CACHE), "browser_profile": profile}
                with self.open(proxy_supplier=supplier) as restored:
                    self.assertIsNone(restored)
        self.assertEqual(len(profiles), self.invalidate.call_count)
        self.browser.assert_not_called()
        supplier.assert_not_called()

    def test_explicitly_expired_or_anonymous_session_returns_to_login(self):
        expired = base64.urlsafe_b64encode(json.dumps({"exp": 1}).encode()).decode().rstrip("=")
        for response in (Response({}, 401), Response({}),
                         Response({**INFO, "accessToken": f"fixture.{expired}.signature"})):
            with self.subTest(status=response.status_code, payload=response.payload):
                self.client.get.return_value = response
                with self.open() as restored:
                    self.assertIsNone(restored)
        self.assertEqual(3, self.invalidate.call_count)

    def test_target_and_cache_identity_must_both_match_online_session(self):
        for changed in ({"user": {"email": "different@example.test", "id": "fixture-user"}},
                        {"user": {"email": EMAIL, "id": "other-user"}},
                        {"account": {"id": "other-account"}}):
            with self.subTest(changed=changed):
                self.client.get.return_value = Response({**INFO, **changed})
                with self.open() as restored:
                    self.assertIsNone(restored)
        self.client.get.return_value = Response(copy.deepcopy(INFO))
        self.load.return_value = {**CACHE, "user_id": "other-cache-user"}
        with self.open() as restored:
            self.assertIsNone(restored)
        self.assertEqual(4, self.invalidate.call_count)

    def test_http_and_schema_failures_are_classified_without_invalidating_cache(self):
        for response, code in ((Response({}, 403), "password_setup_security_check"),
                               (Response({}, 429), "password_setup_rate_limited"),
                               (Response({}, 503), "password_setup_network_failed"),
                               (Response(ValueError("private-json")), "password_setup_response_invalid"),
                               (Response([]), "password_setup_response_invalid"),
                               (Response({"user": {"email": EMAIL}}), "password_setup_response_invalid")):
            with self.subTest(status=response.status_code, code=code):
                self.client.get.return_value = response
                with self.assertRaises(reuse.ProtocolPasswordSetupError) as caught, self.open():
                    self.fail("校验故障不得转为匿名登录")
                self.assertEqual(code, caught.exception.code)
                self.assertFalse(caught.exception.request_unknown)
                self.assertNotIn("private-json", str(caught.exception))
        self.invalidate.assert_not_called()
        self.private_session.assert_not_called()

    def test_proxy_transport_failure_keeps_fault_evidence_but_not_private_error_text(self):
        self.client.get.side_effect = RuntimeError("curl: (56) Proxy CONNECT aborted; private-route")
        with self.assertRaises(reuse.ProtocolPasswordSetupError) as caught, self.open():
            self.fail("网络故障不得转为匿名登录")
        self.assertTrue(caught.exception.proxy_transport_failed)
        self.assertEqual("password_setup_network_failed", caught.exception.code)
        self.assertNotIn("private-route", str(caught.exception))
        self.invalidate.assert_not_called()
        self.client.session.close.assert_called_once_with()
        self.private_session.assert_not_called()

    def test_cancellation_wrapped_by_session_reader_is_propagated(self):
        for control in (reuse.CancellationRequested, reuse.OperationCancelled, reuse.OperationLeaseLost):
            with self.subTest(control=control):
                signal = control("fixture-stop")
                self.client.get.side_effect = signal
                with self.assertRaises(control) as caught, self.open():
                    self.fail("取消不能被转换为会话失败")
                self.assertIs(signal, caught.exception)
        self.invalidate.assert_not_called()

    def test_checkpoint_after_read_and_caller_errors_still_close_client(self):
        stop = reuse.OperationLeaseLost("fixture-stop")
        def checkpoint():
            if self.client.get.called:
                raise stop
        with self.assertRaises(reuse.OperationLeaseLost), self.open(checkpoint=checkpoint):
            self.fail("读取后的租约检查应阻止继续补密码")
        self.client.session.close.assert_called_once_with()
        self.client.session.close.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "caller"), self.open():
            raise RuntimeError("caller")
        self.client.session.close.assert_called_once_with()

    def test_cache_save_uses_cookie_allowlist_and_does_not_overwrite_success_on_failure(self):
        with self.open():
            reuse.cache_authenticated_session(self.client, INFO, 7, EMAIL)
        account_id, email, saved = self.save.call_args.args
        self.assertEqual((7, EMAIL), (account_id, email))
        self.assertEqual(CACHE["cookies"], saved["cookies"])
        self.assertEqual(PROFILE, saved["browser_profile"])
        self.save.side_effect = RuntimeError("private-storage-error")
        with self.assertLogs(reuse.logger, level="WARNING") as logs:
            reuse.cache_authenticated_session(self.client, INFO, 7, EMAIL)
        self.assertNotIn("private-storage-error", " ".join(logs.output))

    def test_cache_storage_cancellation_is_never_swallowed(self):
        signal = reuse.CancellationRequested("fixture-stop")
        self.load.side_effect = signal
        with self.assertRaises(reuse.CancellationRequested), self.open():
            self.fail("缓存读取也必须传递取消")
        self.save.side_effect = signal
        with self.assertRaises(reuse.CancellationRequested):
            reuse.cache_authenticated_session(self.client, INFO, 7, EMAIL)
