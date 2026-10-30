"""手动领取必须复用浏览器持久意图，未知结果不能改发新请求。"""
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from core.email.email_butler import client as butler
from webui import runtime
from webui.routes import integrations


REQUEST_ID = "fb4ae841-1745-4450-ae65-a73ec0f28f99"


class EmailButlerManualLeaseRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask("butler-manual-lease")
        context = runtime.WebUIContext(app, logging.getLogger("butler-manual-lease"))
        app.register_blueprint(integrations.create_integrations_blueprint(context))
        self.client = app.test_client()
        self.url = "/api/email-butler/leases"

    def test_missing_or_invalid_request_id_is_rejected_before_claiming(self):
        for body in ({}, {"request_id": ""}, {"request_id": "new"}, {"request_id": 42}, [], ["invalid"]):
            with self.subTest(body=body), patch.object(butler, "pick_account") as pick:
                response = self.client.post(self.url, json=body)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["code"], "invalid_request_id")
            self.assertFalse(response.json["request_unknown"])
            pick.assert_not_called()

    def test_manual_claim_uses_the_validated_browser_intent(self):
        item = {"email": "fixture@example.test", "mailbox_id": "fixture-lease"}
        with patch.object(butler, "pick_account", return_value=SimpleNamespace(**item)) as pick, patch.object(
            butler, "active_mailbox_leases", return_value=[item]
        ):
            response = self.client.post(self.url, json={"request_id": REQUEST_ID})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["item"], item)
        self.assertEqual(response.json["request_id"], REQUEST_ID)
        self.assertFalse(response.json["request_unknown"])
        pick.assert_called_once_with(owner_kind="manual", owner_id=REQUEST_ID, acquisition_id="manual:" + REQUEST_ID)

    def test_unknown_claim_preserves_request_id_and_explicit_unknown_marker(self):
        with patch.object(butler, "pick_account", side_effect=butler.EmailButlerClaimUnknown("request_unknown: fixture")) as pick:
            responses = [self.client.post(self.url, json={"request_id": REQUEST_ID}) for _ in range(2)]
        for response in responses:
            self.assertEqual(response.status_code, 409)
            self.assertTrue(response.json["request_unknown"])
            self.assertEqual(response.json["code"], "request_unknown")
            self.assertEqual(response.json["request_id"], REQUEST_ID)
        self.assertEqual(pick.call_count, 2)
        self.assertEqual(pick.call_args_list[0], pick.call_args_list[1])

    def test_definite_rejection_is_distinguished_from_unknown_outcome(self):
        with patch.object(butler, "pick_account", side_effect=butler.EmailButlerClientError(
            "fixture unavailable", status_code=429, error_code="inventory_empty"
        )):
            response = self.client.post(self.url, json={"request_id": REQUEST_ID})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json["request_unknown"])
        self.assertEqual(response.json["code"], "inventory_empty")
        self.assertEqual(response.json["request_id"], REQUEST_ID)
