# -*- coding: utf-8 -*-
"""协议改密页面上下文适配器契约测试。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from core.accounts.password_setup.reset_support import PasswordResetAuthPageSession


HEADER = "OpenAI-Auth-Page"


class _BaseSession:
    def __init__(self):
        self.calls = []
        self.auth_headers = {"accept": "application/json"}
        self.response = SimpleNamespace(
            status_code=200,
            url="https://auth.openai.com/log-in",
            headers={},
            history=[],
            json=lambda: {},
        )

    def get_auth_headers(self, **kwargs):
        return dict(self.auth_headers)

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url, headers, kwargs))
        return self.response

    def post(self, url, headers=None, **kwargs):
        self.calls.append(("POST", url, headers, kwargs))
        return self.response


class PasswordResetAuthPageSessionTests(TestCase):
    def setUp(self):
        self.base = _BaseSession()
        self.session = PasswordResetAuthPageSession(self.base)

    def test_trusted_redirect_observes_auth_page_context(self):
        self.base.response = SimpleNamespace(
            status_code=302,
            url="https://auth.openai.com/log-in",
            headers={"Location": "/email-verification?auth_page=redirected"},
            history=[],
            json=lambda: {},
        )

        self.session.get("https://auth.openai.com/log-in?auth_page=initial")

        self.assertEqual("redirected", self.session.get_auth_headers()[HEADER])

    def test_navigation_propagates_known_page_when_target_lacks_parameter(self):
        self.session.observe_url("/log-in?auth_page=selected")

        self.session.get("https://auth.openai.com/email-verification?state=known")

        self.assertEqual(
            "https://auth.openai.com/email-verification?state=known&auth_page=selected",
            self.base.calls[-1][1],
        )

    def test_auth_post_header_uses_selected_page(self):
        self.session.observe_url("/email-verification?auth_page=selected")

        self.session.post(
            "https://auth.openai.com/api/accounts/password/verify",
            headers={"content-type": "application/json"},
            data="{}",
        )

        self.assertEqual(
            {"content-type": "application/json", HEADER: "selected"},
            self.base.calls[-1][2],
        )

    def test_untrusted_navigation_does_not_receive_context_or_header(self):
        self.session.observe_url("/email-verification?auth_page=selected")

        self.session.get(
            "https://evil.example.test/email-verification",
            headers={"accept": "*/*", HEADER: "caller-value"},
        )

        self.assertEqual("https://evil.example.test/email-verification", self.base.calls[-1][1])
        self.assertEqual({"accept": "*/*"}, self.base.calls[-1][2])

    def test_defaults_and_explicit_updates_keep_base_behavior(self):
        self.session.get("https://auth.openai.com/email-verification?state=known")
        self.assertEqual(
            "https://auth.openai.com/email-verification?state=known",
            self.base.calls[-1][1],
        )
        self.assertNotIn(HEADER, self.session.get_auth_headers())

        self.session.observe_url("/email-verification?auth_page=selected")
        self.session.get("https://auth.openai.com/email-verification?state=known")
        self.assertIn("auth_page=selected", self.base.calls[-1][1])

        self.session.observe_url("/email-verification?auth_page=")
        self.session.get("https://auth.openai.com/email-verification?state=known")
        self.assertEqual(
            "https://auth.openai.com/email-verification?state=known",
            self.base.calls[-1][1],
        )
