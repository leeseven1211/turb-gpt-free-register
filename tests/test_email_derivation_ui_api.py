"""子地址库存管理接口的参数与公开边界。"""
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
    """替换库存服务边界，不连接数据库或启动 worker。"""
    service = SimpleNamespace(public_summary=Mock(), list_allocations=Mock(),
                              generate_inventory=Mock(), update_inventory_status=Mock())
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


def test_column_filters_and_inventory_capabilities_are_forwarded(derivation_client):
    client, service = derivation_client
    service.list_allocations.return_value = {"items": [{"id": 7, "state": "available", "can_disable": True,
        "can_restore": False, "generation_key": "private-key"}], "total": 1}
    response = client.get('/api/email-derivation/allocations', query_string={
        "q": "child", "parent_q": "parent", "source": "outlook", "state": "available",
        "related_q": "42", "created_from": "2026-10-01", "created_to": "2026-10-27"})
    assert response.status_code == 200
    service.list_allocations.assert_called_once_with(source="outlook", parent_id=None, page=1, page_size=50,
        q="child", parent_q="parent", state="available", related_q="42", created_from="2026-10-01", created_to="2026-10-27")
    assert response.get_json()["items"] == [{"id": 7, "state": "available", "can_disable": True, "can_restore": False}]


@pytest.mark.parametrize('query', ['state=bad', 'created_from=2026-02-30', 'created_to=not-date',
    'created_from=2026-10-27&created_to=2026-10-01', 'q=' + 'x' * 513])
def test_invalid_column_filters_are_rejected(derivation_client, query):
    client, service = derivation_client
    assert client.get('/api/email-derivation/allocations?' + query).status_code == 400
    service.list_allocations.assert_not_called()


def test_generation_preserves_stable_request_and_reports_partial_capacity(derivation_client):
    client, service = derivation_client
    service.generate_inventory.return_value = {"requested": 5, "created": 3, "reused": 0, "shortfall": 2,
        "reason_code": "email_derivation_capacity_exhausted", "reason": "母邮箱剩余额度不足", "private": "secret"}
    response = client.post('/api/email-derivation/generate', json={"source": "icloud_hide", "count": 5,
        "request_id": "stable-request-001", "parent_id": 8})
    assert response.status_code == 200
    service.generate_inventory.assert_called_once_with(source="icloud_hide", count=5,
        request_id="stable-request-001", parent_id=8)
    assert response.get_json() == {"ok": True, "requested": 5, "created": 3, "reused": 0, "shortfall": 2,
        "reason_code": "email_derivation_capacity_exhausted", "reason": "母邮箱剩余额度不足"}


@pytest.mark.parametrize('data', [[], {}, {"source": "unknown", "count": 1, "request_id": "request-001"},
    {"source": "outlook", "count": True, "request_id": "request-001"},
    {"source": "outlook", "count": 1001, "request_id": "request-001"},
    {"source": "outlook", "count": 1.5, "request_id": "request-001"},
    {"source": "outlook", "count": 1, "request_id": ""},
    {"source": "outlook", "count": 1, "request_id": "request-001", "parent_id": False}])
def test_invalid_generation_does_not_reach_service(derivation_client, data):
    client, service = derivation_client
    response = client.post('/api/email-derivation/generate', json=data)
    assert response.status_code == 400
    assert response.get_json()["reason_code"] == "email_derivation_invalid_request"
    service.generate_inventory.assert_not_called()


def test_bulk_inventory_management_reports_immutable_rows(derivation_client):
    client, service = derivation_client
    service.update_inventory_status.return_value = {"updated": 1, "skipped": 1, "results": [
        {"id": 1, "ok": True, "reason_code": "", "reason": "", "private": "secret"},
        {"id": 2, "ok": False, "reason_code": "email_derivation_already_claimed", "reason": "已分配地址不能重新入库"}]}
    response = client.post('/api/email-derivation/status-bulk', json={"ids": [1, 2, 1], "state": "disabled"})
    assert response.status_code == 200
    service.update_inventory_status.assert_called_once_with(ids=[1, 2], state="disabled")
    assert response.get_json()["updated"] == 1
    assert response.get_json()["skipped"] == 1
    assert "private" not in response.get_data(as_text=True)


@pytest.mark.parametrize('data', [{"ids": [1], "state": "reserved"}, {"ids": [True], "state": "disabled"},
    {"ids": [], "state": "available"}, {"ids": ["1"], "state": "available"}, []])
def test_invalid_bulk_changes_are_rejected(derivation_client, data):
    client, service = derivation_client
    assert client.post('/api/email-derivation/status-bulk', json=data).status_code == 400
    service.update_inventory_status.assert_not_called()


def test_known_generation_errors_keep_specific_reason_code(derivation_client):
    client, service = derivation_client
    error = RuntimeError('email_derivation_profile_unavailable: 母邮箱收件配置不可用')
    error.code = 'email_derivation_profile_unavailable'
    service.generate_inventory.side_effect = error
    response = client.post('/api/email-derivation/generate', json={"source": "outlook", "count": 1,
        "request_id": "request-001"})
    assert response.status_code == 409
    assert response.get_json()["reason_code"] == error.code
    assert response.get_json()["error"] == '母邮箱收件配置不可用'
