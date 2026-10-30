"""子地址库存管理接口的参数与公开边界。"""
import logging
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from core import email as core_email
from config import schema
from webui.routes.email_pool import create_email_pool_blueprint

def test_derivation_policies_are_legacy_only_but_env_and_snapshot_values_still_parse():
    defaults = {
        "EMAIL_DERIVATION_ENABLED": False,
        "EMAIL_DERIVATION_SOURCES": "icloud_hide",
        "EMAIL_DERIVATION_MAX_CHILDREN": 3,
        "EMAIL_DERIVATION_TAG_LENGTH": 6,
    }
    editable = {field["key"] for field in schema.CONFIG_SCHEMA.editor_metadata()}
    for key, value in defaults.items():
        assert schema.CONFIG_SCHEMA[key].default == value
        assert key not in editable
        with pytest.raises(schema.ConfigValidationError):
            schema.validate_config_updates({key: value})
    historical = {"EMAIL_DERIVATION_ENABLED": "true", "EMAIL_DERIVATION_SOURCES": "Outlook,icloud_hide,outlook",
                  "EMAIL_DERIVATION_MAX_CHILDREN": "6", "EMAIL_DERIVATION_TAG_LENGTH": "8"}
    namespace = {"__name__": "config.email", **defaults}
    with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", **historical}, clear=True):
        schema.apply_env_namespace(namespace)
    assert namespace == {"__name__": "config.email", "EMAIL_DERIVATION_ENABLED": True,
                         "EMAIL_DERIVATION_SOURCES": "outlook,icloud_hide", "EMAIL_DERIVATION_MAX_CHILDREN": 6,
                         "EMAIL_DERIVATION_TAG_LENGTH": 8}
    snapshot = schema.resolve_config(historical)
    assert snapshot["EMAIL_DERIVATION_MAX_CHILDREN"].value == 6
    assert snapshot["EMAIL_DERIVATION_ENABLED"].value is True
    frozen = schema.build_non_sensitive_snapshot(historical, strict=False)
    assert frozen["EMAIL_DERIVATION_MAX_CHILDREN"] == 6
    assert frozen["EMAIL_DERIVATION_ENABLED"] is True
    assert schema.resolve_config({"EMAIL_DERIVATION_SOURCES": ""})["EMAIL_DERIVATION_SOURCES"].value == ""
    for key, value in (("EMAIL_DERIVATION_MAX_CHILDREN", 0), ("EMAIL_DERIVATION_TAG_LENGTH", 25), ("EMAIL_DERIVATION_SOURCES", "generic_api")):
        with pytest.raises(schema.ConfigValidationError):
            schema.validate_value(key, value)


@pytest.fixture
def derivation_client():
    """替换库存服务边界，不连接数据库或启动 worker。"""
    service = SimpleNamespace(public_summary=Mock(), list_allocations=Mock(),
                              generate_inventory=Mock(), update_inventory_status=Mock())
    app = Flask(__name__)
    app.register_blueprint(create_email_pool_blueprint(SimpleNamespace(logger=logging.getLogger('tests.test_email_derivation_ui_api'))))
    with patch.object(core_email, "derivation", service, create=True):
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


def test_column_filters_preserve_history_without_inventory_write_capabilities(derivation_client):
    client, service = derivation_client
    service.list_allocations.return_value = {"items": [{"id": 7, "state": "available", "can_disable": True,
        "can_restore": False, "generation_key": "private-key"}], "total": 1}
    response = client.get('/api/email-derivation/allocations', query_string={
        "q": "child", "parent_q": "parent", "source": "outlook", "state": "available",
        "related_q": "42", "created_from": "2026-10-01", "created_to": "2026-10-27"})
    assert response.status_code == 200
    service.list_allocations.assert_called_once_with(source="outlook", parent_id=None, page=1, page_size=50,
        q="child", parent_q="parent", state="available", related_q="42", created_from="2026-10-01", created_to="2026-10-27")
    assert response.get_json()["items"] == [{"id": 7, "state": "available"}]


@pytest.mark.parametrize('query', ['state=bad', 'created_from=2026-02-30', 'created_to=not-date',
    'created_from=2026-10-27&created_to=2026-10-01', 'q=' + 'x' * 513])
def test_invalid_column_filters_are_rejected(derivation_client, query):
    client, service = derivation_client
    assert client.get('/api/email-derivation/allocations?' + query).status_code == 400
    service.list_allocations.assert_not_called()


@pytest.mark.parametrize("path,data", [
    ("generate", {"source": "icloud_hide", "count": 5, "request_id": "stable-request-001", "parent_id": 8}),
    ("generate", {"source": "outlook", "count": 1, "request_id": "stable-request-002"}),
    ("generate", {}),
    ("generate", []),
    ("status-bulk", {"ids": [1, 2], "state": "disabled"}),
    ("status-bulk", {"ids": [1], "state": "available"}),
    ("status-bulk", []),
])
def test_local_inventory_writes_are_gone_and_direct_callers_are_sent_to_butler(derivation_client, path, data):
    client, service = derivation_client
    service.generate_inventory.side_effect = AssertionError("local generation must not run")
    service.update_inventory_status.side_effect = AssertionError("local inventory must not change")
    response = client.post('/api/email-derivation/' + path, json=data)
    assert response.status_code == 410
    result = response.get_json()
    assert result["ok"] is False
    assert result["reason_code"] == "email_derivation_managed_by_butler"
    assert "Email Butler" in result["error"]
