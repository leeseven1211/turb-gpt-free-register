import unittest
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from flask import Flask

from webui import auth


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.next_values = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "next" and attrs.get("type") == "hidden":
            self.next_values.append(attrs.get("value"))


class LoginReturnTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask("webui")
        self.app.secret_key = "login-return-test"
        auth_code = patch.object(auth, "_AUTH_CODE", "local-test")
        auth_code.start()
        self.addCleanup(auth_code.stop)
        auth.register_auth_routes(self.app)
        self.app.add_url_rule("/overview", view_func=lambda: "overview")

    def test_login_form_returns_to_the_requested_path_and_query(self):
        for target in ("/overview", "/overview?view=summary&tag=a%26b&tag=two"):
            with self.subTest(target=target):
                client = self.app.test_client()
                redirect = client.get(target)
                self.assertEqual(redirect.status_code, 302)
                login = urlsplit(redirect.location)
                self.assertEqual(login.path, "/login")
                self.assertEqual(parse_qs(login.query), {"next": [target]})

                form = LoginForm()
                form.feed(client.get(redirect.location).get_data(as_text=True))
                self.assertEqual(form.next_values, [target])
                submitted = client.post(login.path, data={"auth_code": "local-test", "next": form.next_values[0]})
                self.assertEqual(submitted.status_code, 302)
                self.assertEqual(submitted.location, target)
                self.assertEqual(client.get(submitted.location).get_data(as_text=True), "overview")

    def test_unauthorized_api_request_returns_json_without_a_login_redirect(self):
        response = self.app.test_client().get("/api/summary?view=compact")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.is_json)
        self.assertFalse(response.get_json()["ok"])
        self.assertNotIn("Location", response.headers)
