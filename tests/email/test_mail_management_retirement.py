"""Turb consumes imported mailboxes while mailbox management stays upstream."""
import logging
import os
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask

from config import schema
from webui.routes.config import create_config_blueprint
from webui.routes.integrations import create_integrations_blueprint


@pytest.mark.parametrize("method,path", [
    ("get", "/api/icloud-hme/accounts"),
    ("post", "/api/icloud-hme/test"),
    ("post", "/api/cloudmail/gen-token"),
    ("post", "/api/cloudmail/domains"),
    ("get", "/api/mailcode/catalog"),
])
def test_legacy_management_routes_are_gone_without_network_or_config_writes(method, path):
    app = Flask(__name__)
    context = SimpleNamespace(logger=logging.getLogger('tests.test_mail_management_retirement'))
    app.register_blueprint(create_config_blueprint(context))
    app.register_blueprint(create_integrations_blueprint(context))
    forbidden = [
        "core.email.icloud_hide.client.list_accounts", "core.email.icloud_hide.client.test_connection",
        "core.email.icloud_hide.client.sync_aliases", "core.email.icloud_hide.client.create_address",
        "core.email.cloudmail.client.gen_token", "core.email.cloudmail.client.fetch_domains",
        "core.email.mailcode.client.list_products", "core.email.mailcode.client.get_wallet",
        "webui.config_editor.update_config",
    ]
    with ExitStack() as stack:
        calls = [stack.enter_context(patch(name, side_effect=AssertionError("must not run"))) for name in forbidden]
        result = getattr(app.test_client(), method)(path, json={"password": "private-draft", "api_base": "https://private.test"})
    assert result.status_code == 410
    assert result.get_json()["reason_code"] == "email_management_managed_by_service"
    assert result.get_json()["ok"] is False
    assert "邮箱服务" in result.get_json()["error"]
    assert "private" not in result.get_data(as_text=True)
    for call in calls:
        call.assert_not_called()


SUPPLY_KEYS = {
    "ICLOUD_HME_ACCOUNT_ID", "ICLOUD_HME_SYNC_TTL", "ICLOUD_HME_AUTO_CREATE", "ICLOUD_HME_CREATE_LABEL_PREFIX",
    "CLOUDMAIL_ADMIN_EMAIL", "CLOUDMAIL_PASSWORD", "CLOUDMAIL_TOKEN_PATH", "CLOUDMAIL_DOMAINS",
    "CLOUDMAIL_AUTO_ADD_USER", "CLOUDMAIL_RANDOM_LOCAL_LENGTH", "MAIL_NEST_PROJECT_CODE",
    "MAILCODE_PRODUCT_ID", "MAILCODE_CHANNEL_WAIT_SECONDS", "XIGUA_PROJECT_SLUG", "XIGUA_OFFER_ID",
    "REMAIL_PROJECT_ID", "REMAIL_EMAIL_SUFFIX", "REMAIL_SERVICE_MODE", "REMAIL_SUPPLY_POLICY", "REMAIL_ORDER_WAIT_SECONDS",
    "CLOUDFLARE_PATH_ACCOUNTS", "CLOUDFLARE_DEFAULT_DOMAINS", "CLOUDFLARE_NAME_LENGTH",
}


def test_supply_policy_is_hidden_and_uneditable_but_historical_values_still_resolve():
    editable = {field["key"] for field in schema.CONFIG_SCHEMA.editor_metadata()}
    assert SUPPLY_KEYS.isdisjoint(editable)
    for key in SUPPLY_KEYS:
        with pytest.raises(schema.ConfigValidationError):
            schema.validate_config_updates({key: schema.CONFIG_SCHEMA[key].default})
    historical = schema.resolve_config({
        "ICLOUD_HME_ACCOUNT_ID": "legacy-fixed-account", "ICLOUD_HME_AUTO_CREATE": "true",
        "CLOUDMAIL_PASSWORD": "legacy-private-password", "REMAIL_SERVICE_MODE": "code",
    }, strict=True)
    assert historical["ICLOUD_HME_ACCOUNT_ID"].value == "legacy-fixed-account"
    assert historical["ICLOUD_HME_AUTO_CREATE"].value is True
    assert historical["CLOUDMAIL_PASSWORD"].value == "legacy-private-password"
    assert historical["REMAIL_SERVICE_MODE"].value == "code"


def test_fixed_inbox_connections_and_otp_configuration_remain_editable():
    editable = {field["key"] for field in schema.CONFIG_SCHEMA.editor_metadata()}
    assert {
        "EMAIL_BUTLER_API_BASE", "EMAIL_BUTLER_API_KEY", "OTP_MAX_WAIT", "OTP_POLL_INTERVAL",
        "ICLOUD_HME_API_BASE", "ICLOUD_HME_API_TOKEN", "ICLOUD_HME_INBOX_MODE",
        "ICLOUD_HME_FORWARD_IMAP_EMAIL", "ICLOUD_HME_FORWARD_IMAP_PASSWORD",
        "OUTLOOK_FETCH_MODE", "CLOUDMAIL_AUTH_TOKEN", "MAILCODE_API_KEY", "REMAIL_API_KEY",
    } <= editable


def test_cli_default_order_only_offers_local_pools_without_erasing_legacy_environment():
    metadata = next(field for field in schema.CONFIG_SCHEMA.editor_metadata() if field["key"] == "EMAIL_SOURCE")
    assert {option["value"] for option in metadata["options"]} == {
        "outlook", "generic_api", "cloudflare_domain", "icloud_hide", "email_butler",
    }
    with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
        assert schema.validate_config_updates({"EMAIL_SOURCE": "generic_api,outlook,generic_api"}) == {
            "EMAIL_SOURCE": "generic_api,outlook"}
        with pytest.raises(schema.ConfigValidationError):
            schema.validate_config_updates({"EMAIL_SOURCE": "remail,outlook"})
    assert schema.resolve_config({"EMAIL_SOURCE": "REMAIL,outlook"}, strict=True)["EMAIL_SOURCE"].value == "remail,outlook"


def test_historical_child_policy_cannot_block_unrelated_configuration_saves():
    with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", "EMAIL_DERIVATION_ENABLED": "true",
                                 "EMAIL_DERIVATION_SOURCES": ""}, clear=True):
        assert schema.validate_config_updates({"OTP_MAX_WAIT": 240}) == {"OTP_MAX_WAIT": 240}
