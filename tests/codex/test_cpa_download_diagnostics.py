"""通过真实 Flask 路由验证 CPA 下载结果与安全的分段诊断。"""

import io
import json
import logging
import zipfile
from unittest.mock import Mock

import pytest
from curl_cffi import CurlECode, CurlInfo
from curl_cffi.requests.exceptions import CertificateVerifyError, SSLError, Timeout
from flask import Flask

from core.codex import oauth
from webui.routes import accounts, codex
from webui.runtime import WebUIContext


@pytest.fixture
def cpa_routes(monkeypatch):
    app = Flask(__name__)
    context = WebUIContext(app, logging.getLogger(__name__))
    app.register_blueprint(accounts.create_accounts_blueprint(context))
    app.register_blueprint(codex.create_codex_blueprint(context))
    monkeypatch.setattr(accounts, "_feature_unavailable", lambda name: None)
    monkeypatch.setattr(codex, "_feature_unavailable", lambda name: None)
    monkeypatch.setattr(oauth, "_cpa_management_origin", lambda: "https://cpa.example.test")
    monkeypatch.setattr(oauth, "_cpa_management_key", lambda: "私有测试管理密钥")
    monkeypatch.setattr(accounts.account_bulk_reads, "read_accounts",
                        lambda ids, **kwargs: {int(acc_id): {"email": "example@example.test"} for acc_id in ids})
    monkeypatch.setattr(accounts.account_bulk_reads, "local_codex_filenames", lambda emails: {})
    monkeypatch.setattr(codex.db, "read_codex_credential",
                        lambda name: ('{"email":"example@example.test"}', name))
    monkeypatch.setattr(codex.codex_bulk_reads, "read_many",
                        lambda names: {name: {"email": "example@example.test"} for name in names})
    monkeypatch.setattr(codex.db, "mark_codex_exported", Mock())
    return app.test_client()


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/accounts/download-cpa-bulk", {"account_ids": [1], "prepare": True}),
    ("GET", "/api/codex/download-from-cpa/local.json", None),
    ("POST", "/api/codex/download-bulk-from-cpa", {"filenames": ["codex-local.json"]}),
])
@pytest.mark.parametrize("exc_class,curl_code,error_code,message", [
    (SSLError, CurlECode.SSL_CONNECT_ERROR, "cpa_tls_error", "CPA TLS 连接失败"),
    (CertificateVerifyError, CurlECode.PEER_FAILED_VERIFICATION, "cpa_tls_certificate_error", "CPA TLS 证书校验失败"),
])
def test_cpa_download_tls_is_classified_on_web_routes(
    cpa_routes, monkeypatch, caplog, method, path, body, exc_class, curl_code, error_code, message,
):
    transport = Mock(side_effect=exc_class("私有代理地址或诊断内容", code=curl_code))
    monkeypatch.setattr(oauth.curl_requests, "Session", Mock(return_value=Mock(request=transport)))

    with caplog.at_level(logging.INFO):
        response = cpa_routes.open(path, method=method, json=body)

    assert response.status_code == 502
    payload = response.get_json()
    detail = payload["errors"][0] if payload.get("errors") else payload
    assert detail["error_code"] == error_code
    assert message in detail["error"]
    assert "读取文件列表" in detail["error"]
    assert "私有代理地址或诊断内容" not in response.get_data(as_text=True)
    assert "私有代理地址或诊断内容" not in caplog.text
    assert "phase=auth_files" in caplog.text
    assert f"curl_code={curl_code.value}" in caplog.text
    assert transport.call_count == 1


def test_account_cpa_download_times_transport_match_and_zip(cpa_routes, monkeypatch, caplog):
    name = "codex-example@example.test-free.json"
    infos = {
        CurlInfo.NAMELOOKUP_TIME: 0.010, CurlInfo.CONNECT_TIME: 0.040,
        CurlInfo.APPCONNECT_TIME: 0.070, CurlInfo.PRETRANSFER_TIME: 0.080,
        CurlInfo.STARTTRANSFER_TIME: 0.200, CurlInfo.TOTAL_TIME: 0.250,
    }
    listed = Mock(status_code=200, infos=infos)
    listed.json.return_value = {"files": [{"name": name, "email": "example@example.test", "type": "codex"}]}
    downloaded = Mock(status_code=200, infos=infos, text='{"access_token":"私有测试凭证"}')
    transport = Mock(side_effect=[listed, downloaded])
    monkeypatch.setattr(oauth.curl_requests, "Session", Mock(return_value=Mock(request=transport)))

    with caplog.at_level(logging.DEBUG):
        response = cpa_routes.post("/api/accounts/download-cpa-bulk", json={"account_ids": [1]})

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert archive.namelist() == [name, "manifest.json"]
        assert json.loads(archive.read("manifest.json"))["count"] == 1
        assert json.loads(archive.read(name))["access_token"] == "私有测试凭证"
    assert transport.call_count == 2
    for phase in ("auth_files", "auth_file_download"):
        assert f"phase={phase}" in caplog.text
    for timing in ("connect_ms=30.0", "tls_ms=30.0", "response_wait_ms=120.0", "body_ms=50.0", "zip_ms="):
        assert timing in caplog.text
    for private in ("example@example.test", "私有测试凭证", "私有测试管理密钥"):
        assert private not in caplog.text


def test_account_cpa_download_preserves_partial_zip_and_tls_diagnosis(cpa_routes, monkeypatch):
    names = ["codex-first.json", "codex-second.json"]
    listed = Mock(status_code=200, infos={})
    listed.json.return_value = {"files": [
        {"name": name, "email": f"{acc_id}@example.test", "type": "codex"}
        for acc_id, name in enumerate(names, start=1)
    ]}
    valid = Mock(status_code=200, infos={}, text='{"type":"codex"}')
    tls_failure = SSLError("私有代理诊断", code=CurlECode.SSL_CONNECT_ERROR)
    transport = Mock(side_effect=[listed, valid, tls_failure])
    monkeypatch.setattr(accounts.account_bulk_reads, "read_accounts",
                        lambda ids, **kwargs: {int(acc_id): {"email": f"{acc_id}@example.test"} for acc_id in ids})
    monkeypatch.setattr(oauth.curl_requests, "Session", Mock(return_value=Mock(request=transport)))

    response = cpa_routes.post("/api/accounts/download-cpa-bulk", json={"account_ids": [1, 2]})

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert archive.namelist() == [names[0], "manifest.json"]
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["count"] == 1
        detail = manifest["errors"][0]
        assert detail["id"] == 2
        assert detail["error_code"] == "cpa_tls_error"
        assert detail["error"] == "CPA TLS 连接失败（下载凭证文件）"
    assert transport.call_count == 3


def test_codex_bulk_reuses_one_remote_list_and_keeps_first_matching_file(cpa_routes, monkeypatch):
    names = ["codex-first.json", "codex-second.json", "codex-tie.json"]
    listed = Mock(status_code=200, infos={})
    listed.json.return_value = {"files": [
        {"name": name, "email": "2@example.test" if name == names[1] else "1@example.test", "type": "codex"}
        for name in names
    ]}
    valid = Mock(status_code=200, infos={}, text='{"type":"codex"}')
    transport = Mock(side_effect=[listed, valid, valid])
    monkeypatch.setattr(oauth.curl_requests, "Session", Mock(return_value=Mock(request=transport)))
    monkeypatch.setattr(codex.codex_bulk_reads, "read_many",
                        lambda names: {name: {"email": f"{index}@example.test"}
                                       for index, name in enumerate(names, start=1)})

    response = cpa_routes.post("/api/codex/download-bulk-from-cpa",
                               json={"filenames": ["codex-local-1.json", "codex-local-2.json"]})

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert archive.namelist() == [*names[:2], "manifest.json"]
        assert json.loads(archive.read("manifest.json"))["count"] == 2
    paths = [call.args[1].split("/v0/management/", 1)[1].split("?", 1)[0] for call in transport.call_args_list]
    assert paths == ["auth-files", "auth-files/download", "auth-files/download"]


def test_codex_bulk_reuses_one_remote_list_failure_for_all_files(cpa_routes, monkeypatch):
    transport = Mock(side_effect=Timeout("读取 CPA 超时", code=CurlECode.OPERATION_TIMEDOUT))
    monkeypatch.setattr(oauth.curl_requests, "Session", Mock(return_value=Mock(request=transport)))

    response = cpa_routes.post("/api/codex/download-bulk-from-cpa",
                               json={"filenames": ["codex-local-1.json", "codex-local-2.json"]})

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["error_code"] == "cpa_timeout"
    assert [(entry["filename"], entry["error_code"]) for entry in payload["errors"]] == [
        ("codex-local-1.json", "cpa_timeout"), ("codex-local-2.json", "cpa_timeout"),
    ]
    assert transport.call_count == 1
