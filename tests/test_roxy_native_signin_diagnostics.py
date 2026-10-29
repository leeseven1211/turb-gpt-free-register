"""本地 Roxy 原生登录入口的最终失败归因，不改变等待和提交行为。"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from core.browser_traffic import _SummaryOnlyCDPSession
from core.registration import roxy
from core.registration_debug import _RoxyTargetCollector
from core.registration.state_machine import StageTimeout
from core.task_errors import classify_task_error
from tests import test_registration_resume_session as resume


NATIVE_URL = "https://chatgpt.com/auth/login_with?callback_path=/"


def event(request_id, *, url="https://chatgpt.com/api/auth/signin/openai?state=private-token",
          method="POST", started=11.0, target="current-target", status=None, headers=None,
          resource_type="Fetch", redirect_index=0):
    return {
        "request_id": request_id, "target_id": target, "redirect_index": redirect_index,
        "url": url, "method": method, "resource_type": resource_type,
        "started_monotonic": started, "status": status,
        "response_headers": headers or {},
    }


def navigation(request_id="document", **kwargs):
    return event(request_id, url=NATIVE_URL, method="GET", started=10.0,
                 resource_type="Document", **kwargs)


class NativeSigninDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.shared = Mock()
        self.diagnostic = roxy._NativeSigninFailureDiagnostics(self.shared)
        self.driver = SimpleNamespace(current_url=NATIVE_URL, current_window_handle="CDwindow-current-target")

    def observe(self, record, phase="request"):
        self.diagnostic.observe_network(record, phase=phase)

    def start(self):
        self.diagnostic.begin_navigation(self.driver)
        self.observe(navigation())

    def challenge(self, request_id="signin", **kwargs):
        self.observe(event(request_id, **kwargs))
        self.observe(event(request_id, status=403,
                           headers={"CF-Mitigated": "challenge", "set-cookie": "private-token"},
                           **kwargs), phase="response")

    def test_current_navigation_challenge_uses_fixed_safe_evidence(self):
        self.start()
        self.challenge()
        result = self.diagnostic.failure_diagnostic(self.driver)
        self.assertEqual(result["cause_code"], "auth_cloudflare_challenge")
        self.assertEqual(result["cause_diagnostics"], {
            "http_status": 403, "auth_endpoint": "nextauth_signin",
            "response_kind": "cloudflare_challenge",
        })
        self.assertNotIn("private-token", repr(result))
        self.assertEqual(self.shared.observe_network.call_count, 3)
        info = classify_task_error("StageTimeout: 邮箱输入准备超时", task_type="registration", stage="submit_email",
                                   error_code="registration_failed", result_summary=result)
        self.assertEqual(info["code"], "auth_cloudflare_challenge")
        self.assertEqual(info["display_code"], "OA-AUTH-CF-CHALLENGE")

    def test_unrelated_tab_challenge_cannot_replace_current_target(self):
        self.start()
        self.observe(navigation("other-document", target="other-target"))
        self.challenge(target="other-target")
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_unrelated_tab_document_cannot_clear_current_challenge(self):
        self.start()
        self.challenge()
        self.observe(navigation("other-document", target="other-target"))
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver).get("cause_code"),
                         "auth_cloudflare_challenge")

    def test_collector_late_extra_headers_complete_only_current_navigation_evidence(self):
        for new_navigation in (False, True):
            with self.subTest(new_navigation=new_navigation):
                self._collector_late_extra_headers(new_navigation=new_navigation)

    def _collector_late_extra_headers(self, *, new_navigation):
        session = _SummaryOnlyCDPSession("test-native-diagnostic")
        session.auth_diagnostic_observer = self.diagnostic.observe_network
        collector = _RoxyTargetCollector(
            SimpleNamespace(session=session, public_asset_cache=None, data_saver=None),
            "current-target", "", "page",
        )
        self.diagnostic.begin_navigation(self.driver)
        for method, params in (
            ("Network.requestWillBeSent", {
                "requestId": "document", "timestamp": 10.0, "type": "Document",
                "request": {"method": "GET", "url": NATIVE_URL},
            }),
            ("Network.requestWillBeSent", {
                "requestId": "signin", "timestamp": 11.0, "type": "Fetch",
                "request": {"method": "POST", "url": "https://chatgpt.com/api/auth/signin/openai"},
            }),
            ("Network.responseReceived", {
                "requestId": "signin", "response": {
                    "status": 403, "mimeType": "text/html", "headers": {"content-type": "text/html"},
                },
            }),
            ("Network.loadingFinished", {
                "requestId": "signin", "timestamp": 12.0, "encodedDataLength": 100,
            }),
        ):
            collector._handle({"method": method, "params": params})
        if new_navigation:
            collector._handle({"method": "Network.requestWillBeSent", "params": {
                "requestId": "next-document", "timestamp": 13.0, "type": "Document",
                "request": {"method": "GET", "url": NATIVE_URL},
            }})
        collector._handle({"method": "Network.responseReceivedExtraInfo", "params": {
            "requestId": "signin", "statusCode": 403, "headers": {"cf-mitigated": "challenge"},
        }})
        self.assertNotIn("started_monotonic", collector._summary_response_records["signin"])
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver).get("cause_code"),
                         None if new_navigation else "auth_cloudflare_challenge")

    def test_missing_or_unreadable_driver_target_disables_navigation_diagnostic(self):
        for handle in (None, "", "CDwindow-", "untrusted target", Mock()):
            with self.subTest(handle=handle):
                self.driver.current_window_handle = handle
                self.start()
                self.challenge()
                self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_raw_chrome_target_handle_is_bound_without_prefix(self):
        self.driver.current_window_handle = "current-target"
        self.start()
        self.challenge()
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver).get("cause_code"),
                         "auth_cloudflare_challenge")

    def test_ordinary_403_and_cloudflare_server_are_not_challenge_evidence(self):
        for headers in ({}, {"server": "cloudflare", "cf-ray": "fixed-ray"}):
            with self.subTest(headers=headers):
                self.start()
                self.observe(event("signin"))
                self.observe(event("signin", status=403, headers=headers), phase="response")
                self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_old_request_late_response_does_not_belong_to_new_navigation(self):
        self.observe(event("old", started=1.0))
        self.start()
        self.observe(event("old", started=1.0, status=403,
                           headers={"cf-mitigated": "challenge"}), phase="response")
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_new_document_discards_prior_navigation_challenge(self):
        self.start()
        self.challenge()
        self.observe(navigation("second-document"))
        self.observe(event("signin", status=403, headers={"cf-mitigated": "challenge"}), phase="complete")
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_late_response_from_previous_redirect_does_not_replace_current_result(self):
        self.start()
        self.challenge("redirected", redirect_index=0)
        self.observe(event("redirected", redirect_index=1, started=12.0))
        self.observe(event("redirected", redirect_index=1, started=12.0, status=200), phase="response")
        self.observe(event("redirected", status=403, headers={"cf-mitigated": "challenge"}), phase="complete")
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_new_auth_success_wins_over_late_old_challenge(self):
        self.start()
        self.challenge("old")
        self.observe(event("new", started=12.0))
        self.observe(event("new", started=12.0, status=200), phase="response")
        self.observe(event("old", started=None, status=403,
                           headers={"cf-mitigated": "challenge"}), phase="complete")
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_later_auth_progress_or_pending_submission_clears_previous_challenge(self):
        for url in ("https://chatgpt.com/api/auth/signin/openai",
                    "https://auth.openai.com/api/accounts/password/verify"):
            with self.subTest(url=url):
                self.start()
                self.challenge("old")
                self.observe(event("next", url=url, started=12.0))
                self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_untrusted_or_unmatched_request_cannot_supply_challenge(self):
        for kwargs in (
            {"url": "https://chatgpt.com.other.test/api/auth/signin/openai"},
            {"url": "https://chatgpt.com:8443/api/auth/signin/openai"},
            {"method": "GET"}, {"target": "other-target"},
            {"started": 1.0}, {"started": None},
        ):
            with self.subTest(kwargs=kwargs):
                self.start()
                self.challenge(**kwargs)
                self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_retained_old_page_and_navigation_away_do_not_reuse_challenge(self):
        self.observe(navigation())
        self.challenge()
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})
        self.start()
        self.challenge()
        self.driver.current_url = "https://auth.openai.com/log-in/password"
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})


class NativeSigninFlowTests(unittest.TestCase):
    def run_failure(self, *, response_status=403, response_headers=None, error=None, helpers=None):
        flow = resume.ResumeSessionFlowTests()
        with flow.run_context(opened_profile="replacement-profile") as (driver, mocks):
            driver.current_window_handle = "CDwindow-current-target"
            capture = Mock()
            mocks["opened"].return_value.traffic_capture = capture

            def navigate(_driver, url, **_kwargs):
                driver.current_url = url
                observe = capture.set_auth_diagnostic_observer.call_args.args[0]
                observe(event("document", url=url, method="GET", started=10.0,
                              resource_type="Document"), phase="request")
                observe(event("signin"), phase="request")
                observe(event("signin", status=response_status, headers=response_headers), phase="response")

            mocks["navigate"].side_effect = navigate
            mocks["_submit_email_and_wait_next"].side_effect = error or StageTimeout("邮箱输入准备恢复 exceeded shared stage timeout")
            result = flow.run_registration(**({"_browser_helpers": helpers} if helpers is not None else {}))
        return result, mocks

    def test_local_form_timeout_reports_current_challenge_and_preserves_execution_without_rotation_context(self):
        result, mocks = self.run_failure(response_headers={"cf-mitigated": "challenge"})
        self.assertFalse(result["success"])
        self.assertEqual(result['cause_code'], 'auth_cloudflare_challenge')
        self.assertIn('Cloudflare', result['error'])
        self.assertFalse(result['cf_proxy_rotation_ready'])
        self.assertIn("StageTimeout", result["error"])
        self.assertEqual(result["error_code"], "registration_failed")
        self.assertFalse(result["request_unknown"])
        mocks["navigate"].assert_called_once()
        self.assertEqual(mocks["navigate"].call_args.args[1], "https://chatgpt.com/auth/login")
        self.assertEqual(mocks["navigate"].call_args.kwargs["attempts"], 2)
        mocks["_submit_email_and_wait_next"].assert_called_once()
        self.assertEqual(mocks["_submit_email_and_wait_next"].call_args.kwargs["attempts"], 3)
        mocks["_fill_password_page_if_present"].assert_not_called()
        mocks["release"].assert_not_called()
        mocks["retain"].assert_called_once()

    def test_roxy_oss_keeps_shared_observer_and_original_failure(self):
        helpers = SimpleNamespace(
            driver_name="roxy_oss", complete_profile_page=Mock(),
            submit_email_and_wait_next=Mock(side_effect=StageTimeout("unit adapter timeout")),
        )
        result, _ = self.run_failure(response_headers={"cf-mitigated": "challenge"}, helpers=helpers)
        self.assertNotIn("cause_code", result)
        self.assertNotIn("Cloudflare", result["error"])
        helpers.submit_email_and_wait_next.assert_called_once()
        self.assertNotIn("recover_late_email_entry", helpers.submit_email_and_wait_next.call_args.kwargs)

    def test_ordinary_403_and_explicit_non_timeout_keep_original_failure(self):
        for kwargs in ({"response_headers": {"server": "cloudflare"}},
                       {"response_headers": {"cf-mitigated": "challenge"},
                        "error": RuntimeError("unit explicit failure")}):
            with self.subTest(kwargs=kwargs):
                result, _ = self.run_failure(**kwargs)
                self.assertNotIn("cause_code", result)
                self.assertNotIn("Cloudflare", result["error"])


if __name__ == "__main__":
    unittest.main()
