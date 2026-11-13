"""AT 发码使用真实 POST 契约，并保留会话身份和请求前的收件时间。"""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch

from core.accounts.liveness.protocol import otp_delivery
from core.accounts.password_setup import protocol as password_setup
from core.auth.protocol.openai_auth import EmailOtpInvalidError, EmailOtpSendError
from core.auth.state_machine import CancellationRequested, StageTimeout
from core.email.email_butler.client import EmailButlerClientError
from core.network.at_transport_recovery import AtRecoveryScope, AtRecoveryTimeout


EMAIL = "at-otp@example.test"
AUTH = "https://auth.openai.com"
EMAIL_PAGE = AUTH + "/email-verification"


class Response:
    def __init__(self, payload=None, *, status=200, text=None):
        self.payload = payload
        self.status_code = status
        self.text = (json.dumps(payload) if payload is not None else "") if text is None else text

    def json(self):
        if self.payload is None:
            raise ValueError("测试空响应")
        return deepcopy(self.payload)


def context(*, pending=True, **changes):
    return Response({"client_auth_session": {
        "session_id": "fixture-session", "email": EMAIL,
        "email_verification_mode": "passwordless_login",
        "passwordless_email_otp_send_pending": pending, **changes,
    }})


class Session:
    def __init__(self, contexts, responses=()):
        self.contexts = iter(contexts)
        self.responses = iter(responses)
        self.events = []

    def get_auth_headers(self, *, referer):
        return {"referer": referer, "content-type": "application/json",
                "openai-sentinel-token": "fixture-old-token", "openai-sentinel-so-token": "fixture-old-observer"}

    def get(self, url, **kwargs):
        self.events.append(("GET", url, kwargs))
        return next(self.contexts)

    def post(self, url, **kwargs):
        self.events.append(("POST", url, kwargs))
        return next(self.responses)


class AtProtocolOtpDeliveryTests(unittest.TestCase):
    def setUp(self):
        sentinel_patch = patch.object(otp_delivery, "request_sentinel_token", return_value={"fixture": True})
        self.sentinel = sentinel_patch.start()
        self.addCleanup(sentinel_patch.stop)
        build_patch = patch.object(otp_delivery, "build_sentinel_header", return_value=(
            "fixture-current-token", "fixture-current-observer"))
        self.build_sentinel = build_patch.start()
        self.addCleanup(build_patch.stop)

    def ensure(self, session, **kwargs):
        return otp_delivery.ensure_initial_otp_sent(session, EMAIL, 100.0, **kwargs)

    def test_pending_initial_send_uses_bodyless_post_and_captures_time_before_dispatch(self):
        session = Session([context(), context()], [Response({"page": {"type": "email_otp_verification"}})])
        with patch.object(otp_delivery.time, "time", return_value=123.0):
            self.assertEqual(123.0, self.ensure(session))
        self.assertEqual(["GET", "GET", "POST"], [event[0] for event in session.events])
        request = session.events[-1]
        self.assertEqual(AUTH + "/api/accounts/passwordless/send-otp", request[1])
        self.assertFalse(request[2]["allow_redirects"])
        self.assertIsNone(request[2]["headers"]["content-type"])
        self.assertNotIn("data", request[2])
        self.assertNotIn("json", request[2])
        self.assertEqual("fixture-current-token", request[2]["headers"]["openai-sentinel-token"])
        self.sentinel.assert_called_once_with(session, "authorize_continue")

    def test_existing_challenge_does_not_send_or_generate_sentinel(self):
        session = Session([context(pending=False)])
        self.assertEqual(100.0, self.ensure(session))
        self.assertEqual(["GET"], [event[0] for event in session.events])
        self.sentinel.assert_not_called()

    def test_missing_pending_preserves_challenge_without_inventing_initial_send(self):
        response = context()
        response.payload["client_auth_session"].pop("passwordless_email_otp_send_pending")
        session = Session([response])
        self.assertEqual(100.0, self.ensure(session))
        self.sentinel.assert_not_called()
        self.assertEqual(1, len(session.events))

    def test_pending_cleared_during_sentinel_generation_preserves_original_window(self):
        session = Session([context(), context(pending=False)])
        self.assertEqual(100.0, self.ensure(session))
        self.assertEqual(["GET", "GET"], [event[0] for event in session.events])

    def test_changed_session_identity_or_mode_is_not_sent(self):
        for changes in ({"session_id": "fixture-other-session"}, {"email": "other@example.test"},
                        {"email_verification_mode": "passwordless_signup"}):
            with self.subTest(changes=changes):
                session = Session([context(), context(**changes)])
                with self.assertRaises(EmailOtpSendError):
                    self.ensure(session)
                self.assertFalse(any(event[0] == "POST" for event in session.events))

    def test_invalid_context_and_unsupported_pending_mode_are_not_sent(self):
        for response in (context(email="other@example.test"), context(is_missing_session=True),
                         context(pending="true"), context(email_verification_mode="post_signup")):
            with self.subTest(payload=response.payload):
                session = Session([response])
                with self.assertRaises(EmailOtpSendError):
                    self.ensure(session)
                self.assertEqual(["GET"], [event[0] for event in session.events])

    def test_resend_uses_post_without_sentinel_and_allows_empty_http_success(self):
        for status in (200, 204):
            with self.subTest(status=status):
                session = Session([], [Response(status=status)])
                with patch.object(otp_delivery.time, "time", return_value=456.0):
                    self.assertEqual(456.0, otp_delivery.resend_otp(session))
                method, url, kwargs = session.events[0]
                self.assertEqual(("POST", AUTH + "/api/accounts/email-otp/resend"), (method, url))
                self.assertFalse(kwargs["allow_redirects"])
                self.assertIsNone(kwargs["headers"]["content-type"])
                self.assertNotIn("data", kwargs)
                self.assertNotIn("json", kwargs)
                self.assertNotIn("openai-sentinel-token", kwargs["headers"])
                self.assertNotIn("openai-sentinel-so-token", kwargs["headers"])
        self.sentinel.assert_not_called()

    def test_redirect_http_rejection_and_business_rejection_preserve_send_failure(self):
        for response, reason in ((Response(status=302), "unconfirmed"), (Response(status=429), "http_error"),
                                 (Response({"error": {"code": "invalid_auth_step"}}), "rejected"),
                                 (Response({"success": False}), "rejected")):
            with self.subTest(status=response.status_code, reason=reason):
                session = Session([], [response])
                with self.assertRaises(EmailOtpSendError) as caught:
                    otp_delivery.resend_otp(session)
                self.assertEqual(reason, caught.exception.reason)
                self.assertEqual(response.status_code, caught.exception.status_code)

    def test_initial_send_requires_verification_page_json(self):
        for response in (Response(text="<html>verification page</html>"), Response({"success": True}),
                         Response({"page": {"type": "email_otp_verification", "payload": {"errors": ["fixture"]}}})):
            with self.subTest(response=response.text):
                session = Session([context(), context()], [response])
                with self.assertRaises(EmailOtpSendError) as caught:
                    self.ensure(session)
                self.assertEqual("unconfirmed", caught.exception.reason)

    def test_cancellation_and_total_budget_failure_are_not_converted_to_send_errors(self):
        for error in (CancellationRequested("测试取消"), StageTimeout("测试总预算结束")):
            with self.subTest(error=type(error).__name__):
                session = Session([], [Response()])
                with self.assertRaises(type(error)) as caught:
                    otp_delivery.resend_otp(session, checkpoint=Mock(side_effect=error))
                self.assertIs(error, caught.exception)
                self.assertEqual([], session.events)

    def test_context_transport_and_control_errors_keep_the_original_exception(self):
        for error in (ConnectionError("测试连接故障"), StageTimeout("测试阶段到期"),
                      AtRecoveryTimeout("测试 AT 总预算到期"), CancellationRequested("测试取消")):
            with self.subTest(error=type(error).__name__):
                session = Session([])
                session.get = Mock(side_effect=error)
                with self.assertRaises(type(error)) as caught:
                    self.ensure(session)
                self.assertIs(error, caught.exception)

    def test_sentinel_network_and_control_errors_keep_the_original_exception(self):
        from requests.exceptions import ConnectionError, SSLError

        for error in (ConnectionError("测试连接"), SSLError("测试 TLS"), StageTimeout("测试阶段预算"),
                      AtRecoveryTimeout("测试 AT 总预算"), CancellationRequested("测试取消")):
            for boundary in ("request", "build"):
                with self.subTest(error=type(error).__name__, boundary=boundary):
                    session = Session([context()])
                    self.sentinel.side_effect = error if boundary == "request" else None
                    self.build_sentinel.side_effect = error if boundary == "build" else None
                    with self.assertRaises(type(error)) as caught:
                        self.ensure(session)
                    self.assertIs(error, caught.exception)
                    self.assertEqual(["GET"], [event[0] for event in session.events])

    def test_missing_sentinel_token_is_unconfirmed_before_dispatch(self):
        session = Session([context()])
        self.build_sentinel.return_value = (None, None)
        with self.assertRaises(EmailOtpSendError) as caught:
            self.ensure(session)
        self.assertEqual("unconfirmed", caught.exception.reason)
        self.assertEqual(["GET"], [event[0] for event in session.events])

    def test_unknown_remote_error_logs_only_fixed_label(self):
        session = Session([], [Response({"error": {"code": "fixture-private-server-value"}})])
        with self.assertLogs(otp_delivery.logger, level="INFO") as logs, self.assertRaises(EmailOtpSendError):
            otp_delivery.resend_otp(session)
        self.assertIn("remote.error.code=other", "\n".join(logs.output))
        self.assertNotIn("fixture-private-server-value", "\n".join(logs.output))

    def test_at_logs_do_not_mislabel_source_or_contain_identity_or_sentinel(self):
        session = Session([context(), context()], [Response({"page": {"type": "email_otp_verification"}})])
        with self.assertLogs(level="INFO") as logs:
            self.ensure(session)
        output = "\n".join(logs.output)
        self.assertIn("[查活][AT]", output)
        for value in ("[补密码]", EMAIL, "fixture-session", "fixture-current-token", "fixture-current-observer"):
            self.assertNotIn(value, output)

    def test_at_scope_initial_and_retry_share_actual_post_contract_and_two_rounds(self):
        from core.accounts.liveness.protocol import legacy

        session = Session([context(), context()], [
            Response({"page": {"type": "email_otp_verification"}}), Response(status=204),
        ])
        clock = {"now": 120.0}
        reads = []

        def wait(_email, *, after_ts, **_kwargs):
            reads.append(after_ts)
            if len(reads) == 1:
                clock["now"] = 200.0
            raise EmailButlerClientError("测试当前窗口无邮件", error_code="inbound_code_timeout")

        with (patch.object(legacy, "wait_for_otp", side_effect=wait),
              patch.object(legacy, "validate_email_otp") as validate,
              patch.object(legacy, "send_email_otp") as shared_send,
              patch.object(legacy.time, "time", side_effect=lambda: clock["now"]),
              patch.object(legacy.time, "sleep"), AtRecoveryScope().activate(),
              self.assertRaises(EmailButlerClientError)):
            legacy._validate_with_retry(session, EMAIL, 100.0, max_otp_attempts=5)
        self.assertEqual([120.0, 200.0], reads)
        self.assertEqual([AUTH + "/api/accounts/passwordless/send-otp", AUTH + "/api/accounts/email-otp/resend"],
                         [event[1] for event in session.events if event[0] == "POST"])
        shared_send.assert_not_called()
        validate.assert_not_called()

    def test_non_at_shared_login_keeps_its_original_send_and_does_not_read_at_context(self):
        from core.accounts.liveness.protocol import legacy

        session = object()
        success = {"continue_url": AUTH + "/authorize/continue"}
        with (patch.object(legacy, "wait_for_otp", side_effect=["fixture-code", "fixture-code"]),
              patch.object(legacy, "validate_email_otp", side_effect=[EmailOtpInvalidError("测试无效码"), success]),
              patch.object(legacy, "send_email_otp") as shared_send,
              patch.object(legacy, "_ensure_at_otp_sent") as initial,
              patch.object(legacy, "_resend_at_otp") as resend,
              patch.object(legacy.time, "sleep")):
            self.assertIs(success, legacy._validate_with_retry(session, EMAIL, 100.0))
        shared_send.assert_called_once_with(session)
        initial.assert_not_called()
        resend.assert_not_called()

    def test_v2_full_refresh_preserves_at_initial_send_budget_exceptions(self):
        from core.accounts.liveness.protocol import legacy, v2

        for error in (StageTimeout("测试初发阶段预算"), AtRecoveryTimeout("测试初发总预算")):
            for callback_recovery in (False, True):
                with self.subTest(error=type(error).__name__, callback_recovery=callback_recovery):
                    session = Mock()
                    with (patch.object(v2, "get_account_login_credentials", return_value=("fixture-password", "")),
                          patch.object(v2, "account_email_is_invalid", return_value=False),
                          patch.object(v2, "_network_preflight_with_retry", return_value=(session, AUTH + "/authorize")),
                          patch.object(v2, "follow_authorize", return_value=EMAIL_PAGE),
                          patch.object(v2, "_open_offered_password_login", return_value=EMAIL_PAGE),
                          patch.object(legacy, "_ensure_at_otp_sent", side_effect=error),
                          patch.object(legacy, "wait_for_otp") as wait,
                          AtRecoveryScope().activate(), self.assertRaises(type(error)) as caught):
                        v2.refresh_access_token(EMAIL, proxy="", callback_recovery=callback_recovery)
                    self.assertIs(error, caught.exception)
                    wait.assert_not_called()
                    session.session.close.assert_called_once()


class AtProtocolV3OtpDeliveryTests(unittest.TestCase):
    """v3 复用 AT 投递调度，验证码提交仍由原结构化接口处理。"""

    def setUp(self):
        from core.accounts.liveness.protocol import v3

        self.v3 = v3

    def authenticate(self, session, progress):
        return self.v3._authenticate(session, AUTH + "/authorize", email=EMAIL, target={},
                                     password="", secret="", progress=progress)

    def test_at_v3_uses_real_initial_and_resend_posts_with_original_validation_contract(self):
        from core.accounts.liveness.protocol import legacy

        session = Session([context(), context()], [
            Response({"page": {"type": "email_otp_verification"}}), Response(status=204),
            Response({"continue_url": "https://chatgpt.com/api/auth/callback/openai"}),
        ])
        progress = {"methods": [], "attempted": ""}
        success = {"accessToken": "fixture-session"}
        with (patch.object(self.v3, "_follow", side_effect=[EMAIL_PAGE, "https://chatgpt.com/"]),
              patch.object(self.v3, "_read_session", return_value=success),
              patch.object(self.v3, "_client_auth_context", return_value={}),
              patch.object(self.v3, "account_email_is_invalid", return_value=False),
              patch.object(self.v3, "send_email_otp") as shared,
              patch.object(legacy, "wait_for_otp", side_effect=[EmailButlerClientError(
                  "测试无邮件", error_code="inbound_code_timeout"), "fixture-code"]),
              patch.object(legacy, "validate_email_otp") as old_validator,
              patch.object(legacy.time, "sleep"),
              patch.object(otp_delivery, "request_sentinel_token", return_value={}),
              patch.object(otp_delivery, "build_sentinel_header", return_value=("fixture-token", None)),
              AtRecoveryScope().activate()):
            info, methods = self.authenticate(session, progress)
        self.assertIs(success, info)
        self.assertEqual(["email_otp"], methods)
        posts = [event for event in session.events if event[0] == "POST"]
        self.assertEqual([AUTH + "/api/accounts/passwordless/send-otp", AUTH + "/api/accounts/email-otp/resend",
                          AUTH + "/api/accounts/email-otp/validate"], [event[1] for event in posts])
        self.assertTrue(all(event[2]["allow_redirects"] is False for event in posts))
        self.assertEqual({"code": "fixture-code"}, json.loads(posts[-1][2]["data"]))
        shared.assert_not_called()
        old_validator.assert_not_called()

    def test_at_v3_keeps_invalid_validation_response_fact_without_replay(self):
        from core.accounts.liveness.protocol import legacy
        from core.accounts.liveness.protocol.v2 import ProtocolV2AuthError

        session = Session([context(pending=False)], [Response(["invalid-fixture-shape"])])
        progress = {"methods": [], "attempted": ""}
        with (patch.object(self.v3, "_follow", return_value=EMAIL_PAGE),
              patch.object(self.v3, "_client_auth_context", return_value={}),
              patch.object(self.v3, "account_email_is_invalid", return_value=False),
              patch.object(legacy, "wait_for_otp", return_value="fixture-code"),
              patch.object(legacy, "validate_email_otp") as old_validator,
              AtRecoveryScope().activate(), self.assertRaises(ProtocolV2AuthError) as caught):
            self.authenticate(session, progress)
        self.assertEqual("email_otp_validate_invalid_response", caught.exception.code)
        self.assertTrue(caught.exception.reconcile_required)
        self.assertTrue(caught.exception.mutation_submitted)
        self.assertEqual(1, sum(event[0] == "POST" for event in session.events))
        old_validator.assert_not_called()

    def test_at_v3_total_budget_expiry_is_not_converted_to_mailbox_failure(self):
        error = AtRecoveryTimeout("测试 AT 总预算")
        session = Session([])
        progress = {"methods": [], "attempted": ""}
        with (patch.object(self.v3, "_follow", return_value=EMAIL_PAGE),
              patch.object(self.v3, "_client_auth_context", return_value={}),
              patch.object(self.v3, "account_email_is_invalid", return_value=False),
              patch.object(self.v3, "_validate_with_retry", side_effect=error),
              AtRecoveryScope().activate(), self.assertRaises(AtRecoveryTimeout) as caught):
            self.authenticate(session, progress)
        self.assertIs(error, caught.exception)
        self.assertEqual([], session.events)

    def test_non_at_scope_v3_does_not_enter_new_delivery_dispatch(self):
        session = Session([], [Response({"continue_url": "https://chatgpt.com/api/auth/callback/openai"})])
        progress = {"methods": [], "attempted": ""}
        with (patch.object(self.v3, "_follow", side_effect=[EMAIL_PAGE, "https://chatgpt.com/"]),
              patch.object(self.v3, "_read_session", return_value={"accessToken": "fixture-session"}),
              patch.object(self.v3, "_client_auth_context", return_value={}),
              patch.object(self.v3, "account_email_is_invalid", return_value=False),
              patch.object(self.v3, "send_email_otp") as shared,
              patch.object(self.v3, "wait_for_otp", return_value="fixture-code"),
              patch.object(self.v3, "_validate_with_retry") as new_dispatch):
            self.authenticate(session, progress)
        shared.assert_called_once_with(session)
        new_dispatch.assert_not_called()
