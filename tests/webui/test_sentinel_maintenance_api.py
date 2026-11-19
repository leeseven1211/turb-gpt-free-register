"""Sentinel maintenance routes share the existing WebUI authorization gate."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from flask import Flask

from webui.auth import init_auth, register_auth_routes
from webui.routes.config import create_config_blueprint
from tests.auth.test_sentinel_maintenance import WorkerConsumer, LOADER, SDK, service, isolated_maintenance_database  # noqa: F401


def client():
    app = Flask(__name__)
    init_auth(app, auth_code="test-auth")
    register_auth_routes(app)
    app.register_blueprint(create_config_blueprint(SimpleNamespace(logger=logging.getLogger(__name__))))
    return app.test_client()


def bind_service(tmp_path, monkeypatch):
    from core.maintenance import sentinel

    worker = WorkerConsumer()
    maintenance = service(tmp_path / "cache", replies=[LOADER, SDK], worker=worker)
    monkeypatch.setattr(sentinel, "get_service", lambda: maintenance)
    return maintenance, worker


def test_sentinel_status_and_check_require_existing_authorization():
    web = client()
    assert web.get("/api/maintenance/sentinel").status_code == 401
    assert web.post("/api/maintenance/sentinel/check", json={}).status_code == 401


def test_status_is_local_and_explicit_check_returns_accepted_without_waiting(tmp_path, monkeypatch):
    maintenance, worker = bind_service(tmp_path, monkeypatch)
    web = client()
    headers = {"X-Auth-Code": "test-auth"}
    initial = web.get("/api/maintenance/sentinel", headers=headers)
    assert initial.status_code == 200
    assert initial.json["last_status"] == "never"
    assert initial.json["candidate"] is None
    assert not (tmp_path / "cache").exists()
    accepted = web.post("/api/maintenance/sentinel/check", headers=headers, json={})
    assert accepted.status_code == 202 and accepted.json["started"] is True
    duplicate = web.post("/api/maintenance/sentinel/check", headers=headers, json={})
    assert duplicate.status_code == 202 and duplicate.json["started"] is False
    assert accepted.json["run_id"] == duplicate.json["run_id"]
    assert accepted.json["task_id"] == duplicate.json["task_id"]
    assert not (tmp_path / "cache").exists()
    assert maintenance.manager.opener.replies == [LOADER, SDK]
    assert web.get("/api/maintenance/sentinel", headers=headers).json["running"] is True
    worker.finish()
    assert web.get("/api/maintenance/sentinel", headers=headers).json["comparison"] == "same"


@pytest.mark.parametrize("body", [
    {"url": "https://secret.test"}, {"cache_dir": "/tmp/secret"}, {"activate": True},
    {"refresh": True}, {"sdk_path": "/tmp/sdk.js"}, [], None,
])
def test_check_rejects_all_client_options_and_nonobject_json(tmp_path, monkeypatch, body):
    maintenance, worker = bind_service(tmp_path, monkeypatch)
    response = client().post("/api/maintenance/sentinel/check", headers={"X-Auth-Code": "test-auth"}, json=body)
    assert response.status_code == 400
    assert response.json == {"ok": False, "error_code": "invalid_request"}
    assert maintenance.status()["running"] is False
    assert not worker.results
    assert "secret" not in response.get_data(as_text=True)


def test_check_rejects_query_options_and_malformed_json(tmp_path, monkeypatch):
    maintenance, worker = bind_service(tmp_path, monkeypatch)
    web = client()
    headers = {"X-Auth-Code": "test-auth"}
    query = web.post("/api/maintenance/sentinel/check?activate=1", headers=headers, json={})
    malformed = web.post("/api/maintenance/sentinel/check", headers=headers, data="{", content_type="application/json")
    assert query.status_code == malformed.status_code == 400
    assert not worker.results


def test_app_creation_does_not_initialize_a_check_or_touch_candidate_cache(tmp_path, monkeypatch):
    maintenance, worker = bind_service(tmp_path, monkeypatch)
    client()
    assert not worker.results
    assert not (tmp_path / "cache").exists()
