"""子地址配置和只读台账接口的公开边界。"""
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

import core
from config import email as email_config
from config import schema
from webui.routes.email_pool import create_email_pool_blueprint

ROOT = Path(__file__).resolve().parents[1]


def test_derivation_defaults_and_editable_contract_are_consistent():
    defaults = {
        "EMAIL_DERIVATION_ENABLED": False,
        "EMAIL_DERIVATION_SOURCES": "icloud_hide",
        "EMAIL_DERIVATION_MAX_CHILDREN": 3,
        "EMAIL_DERIVATION_TAG_LENGTH": 6,
    }
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key, value in defaults.items():
        assert schema.CONFIG_SCHEMA[key].default == value
        assert getattr(email_config, key) == value
        assert schema.CONFIG_SCHEMA[key].group == "邮箱 / OTP"
        assert f"{key}={value}" in template
    assert schema.validate_value("EMAIL_DERIVATION_SOURCES", "Outlook,icloud_hide,outlook") == "outlook,icloud_hide"
    assert set(schema.CONFIG_SCHEMA["EMAIL_DERIVATION_SOURCES"].csv_options) == {"icloud_hide", "outlook"}
    with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
        assert schema.validate_config_updates({"EMAIL_DERIVATION_MAX_CHILDREN": 6}) == {"EMAIL_DERIVATION_MAX_CHILDREN": 6}
    assert schema.resolve_config({"EMAIL_DERIVATION_SOURCES": ""})["EMAIL_DERIVATION_SOURCES"].value == ""
    with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
        with pytest.raises(schema.ConfigValidationError):
            schema.validate_config_updates({"EMAIL_DERIVATION_ENABLED": True, "EMAIL_DERIVATION_SOURCES": ""})
    for key, value in (("EMAIL_DERIVATION_MAX_CHILDREN", 0), ("EMAIL_DERIVATION_TAG_LENGTH", 25), ("EMAIL_DERIVATION_SOURCES", "generic_api")):
        with pytest.raises(schema.ConfigValidationError):
            schema.validate_value(key, value)


@pytest.fixture
def derivation_client():
    """只注册读接口，替换仓储边界，不连接数据库或启动 worker。"""
    service = SimpleNamespace(public_summary=Mock(), list_allocations=Mock())
    app = Flask(__name__)
    app.register_blueprint(create_email_pool_blueprint(SimpleNamespace(logger=logging.getLogger(__name__))))
    with patch.object(core, "email_derivation", service, create=True):
        yield app.test_client(), service


def test_summary_whitelists_nested_parent_fields(derivation_client):
    client, service = derivation_client
    service.public_summary.return_value = {
        "enabled": True, "sources": ["icloud_hide"], "max_children": 3, "total": 2,
        "credential_ref": "private-ref", "password": "private-password",
        "parents": [{"source": "icloud_hide", "parent_id": 8, "parent_email": "parent@example.test", "child_count": 2, "max_children": 3, "remaining": 1, "refresh_token": "private-token", "inbox_profile": {"password": "private"}}],
    }
    response = client.get("/api/email-derivation/summary?source=icloud_hide")
    assert response.status_code == 200
    result = response.get_json()
    service.public_summary.assert_called_once_with(source="icloud_hide")
    assert result["parents"][0] == {"source": "icloud_hide", "parent_id": 8, "parent_email": "parent@example.test", "child_count": 2, "max_children": 3, "remaining": 1}
    assert "private" not in response.get_data(as_text=True)
    assert result["max_children"] == 3


def test_allocations_preserve_full_distinct_addresses_and_ownership(derivation_client):
    client, service = derivation_client
    service.list_allocations.return_value = {"items": [
        {"id": 1, "email": "parent+abc123@example.test", "parent_id": 8, "parent_email": "parent@example.test", "source": "icloud_hide", "state": "used", "root_task_id": "root-1", "registered_account_id": 40, "password": "private-password", "code_url": "https://private.example.test"},
        {"id": 2, "email": "parent+def456@example.test", "parent_id": 8, "parent_email": "parent@example.test", "source": "icloud_hide", "state": "reserved", "root_task_id": "root-2", "inbox_profile": {"password": "private"}},
    ], "total": 60, "raw_snapshot": {"token": "private"}}
    response = client.get("/api/email-derivation/allocations?source=icloud_hide&parent_id=8&page=2&page_size=50")
    assert response.status_code == 200
    result = response.get_json()
    service.list_allocations.assert_called_once_with(source="icloud_hide", parent_id=8, page=2, page_size=50)
    assert [row["email"] for row in result["items"]] == ["parent+abc123@example.test", "parent+def456@example.test"]
    assert result["items"][0]["registered_account_id"] == 40
    assert result["items"][1]["root_task_id"] == "root-2"
    assert result["page"] == 2 and result["total"] == 60
    assert "private" not in response.get_data(as_text=True)


@pytest.mark.parametrize("query", ["source=unknown", "source=all&parent_id=1", "parent_id=oops", "page=0", "page=-2", "page_size=101", "source=outlook&parent_id=0", "page_size=no"])
def test_invalid_filters_do_not_call_repository(derivation_client, query):
    client, service = derivation_client
    response = client.get("/api/email-derivation/allocations?" + query)
    assert response.status_code == 400
    service.list_allocations.assert_not_called()


def test_all_source_is_unfiltered_and_uses_bounded_page(derivation_client):
    client, service = derivation_client
    service.list_allocations.return_value = {"items": [], "total": 0}
    response = client.get("/api/email-derivation/allocations?source=all")
    assert response.status_code == 200
    service.list_allocations.assert_called_once_with(source=None, parent_id=None, page=1, page_size=50)
