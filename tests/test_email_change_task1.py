# -*- coding: utf-8 -*-
"""Focused contracts for the protocol-only email-change operation."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core import account_proxy
from core.task_progress import build_progress_snapshot
from core.task_errors import classify_task_error


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.posts = []
        self.device_id = "device-test"

    def get_chatgpt_headers(self, *, referer):
        return {"content-type": "application/json", "referer": referer}

    def post(self, url, *, headers, json=None, data=None, **kwargs):
        body = json if json is not None else json_loads(data)
        self.posts.append((url, headers, body, kwargs))
        return FakeResponse(payload={"status": "pending"})


def json_loads(value):
    return json.loads(value) if isinstance(value, str) else value


def _event(stage, state, message="", detail=None):
    return {
        "id": hash((stage, state, message)) & 0xFFFF,
        "stage": stage,
        "event_type": f"stage.{state}",
        "message": message,
        "detail": {"step_state": state, **(detail or {})},
    }


def _run(status="running", progress_stage=""):
    return {
        "id": 77,
        "task_id": 70,
        "status": status,
        "progress_stage": progress_stage,
        "result_summary": {},
    }


def test_submit_email_change_uses_native_durable_operation_and_safe_data():
    from core import email_change_service

    submitted = {"accepted": True, "task_id": 11, "run_id": 12, "status": "queued"}
    with (
        patch.object(email_change_service.db, "get_account", return_value={
            "id": 7, "email": "old@example.com", "access_token": "at-secret",
        }),
        patch.object(email_change_service.db, "get_account_by_email", return_value=None),
        patch.object(email_change_service.task_gateway, "submit_durable_operation", return_value=submitted) as submit,
        patch.object(email_change_service, "get_config_snapshot", return_value={
            "ACCOUNT_EMAIL_CHANGE_PROXY_MODE": "direct",
            "OPENAI_PROTOCOL_VERSION": "v1",
            "ROXY_API_TOKEN": "must-not-persist",
        }),
    ):
        result = email_change_service.submit_email_change(
            account_id=7,
            new_email="new@example.com",
            trigger="manual",
            idempotency_key="request-1",
        )

    assert result["accepted"] is True
    kwargs = submit.call_args.kwargs
    assert kwargs["task_type"] == "email_change"
    assert kwargs["source_system"] == "native_operations"
    assert kwargs["resource_family"] == "openai_interactive"
    assert kwargs["data"] == {
        "new_email": "new@example.com",
        "email_source": None,
    }
    assert kwargs["idempotency_key"] == "request-1"
    assert "at-secret" not in repr(kwargs)
    assert "ROXY_API_TOKEN" not in repr(kwargs)


def test_protocol_client_uses_change_email_begin_and_verify_contract():
    from core.email_change_service import ChangeEmailProtocolClient

    session = FakeSession()
    client = ChangeEmailProtocolClient()
    client.begin(session, "at-secret", "new@example.com")
    client.verify(session, "at-secret", "123456")

    assert session.posts[0][0].endswith("/backend-api/accounts/change_email/begin")
    assert session.posts[0][2] == {"new_email": "new@example.com"}
    assert session.posts[1][0].endswith("/backend-api/accounts/change_email/verify")
    assert session.posts[1][2] == {"code": "123456"}
    assert session.posts[0][1]["authorization"] == "Bearer at-secret"


def test_email_change_progress_has_protocol_steps_without_browser_step():
    from core.email_change_service import EMAIL_CHANGE_TASK_TYPE

    events = [
        _event("email", "success"),
        _event("network", "success"),
        _event("reauth", "running"),
        _event("email_change_begin", "success"),
        _event("email_otp", "running"),
        _event("email_change_verify", "running"),
    ]
    snapshot = build_progress_snapshot(70, 77, EMAIL_CHANGE_TASK_TYPE, _run(), events)

    assert [item["id"] for item in snapshot["main_steps"]] == [
        "email", "network", "authenticate", "email_change_begin",
        "email_change_verify", "refresh_dispatch", "result",
    ]
    assert "browser" not in [item["id"] for item in snapshot["main_steps"]]
    assert snapshot["current"]["step_id"] == "authenticate"


def test_explicit_reauth_retries_begin_once_then_waits_new_email_otp():
    from core import email_change_service

    context = _fake_context()
    client = MagicMock()
    client.begin.side_effect = [
        email_change_service.ProtocolResponse(
            status_code=401, payload={"error": {"code": "reauth_required"}},
        ),
        email_change_service.ProtocolResponse(
            status_code=200, payload={"status": "pending"},
        ),
    ]
    client.verify.return_value = email_change_service.ProtocolResponse(
        status_code=200, payload={"status": "success"},
    )
    route = SimpleNamespace(proxy_url="http://proxy.invalid", provider="test", region="JP")
    identity = SimpleNamespace(session_payload=lambda: {"device_id": "device-test", "browser_profile": {}})
    with (
        patch.object(email_change_service.db, "get_account", return_value={
            "id": 7, "email": "old@example.com", "access_token": "at-secret",
        }),
        patch.object(email_change_service.db, "get_account_by_email", return_value=None),
        patch.object(email_change_service.account_proxy, "acquire_account_proxy", return_value=route),
        patch.object(email_change_service.account_auth, "ensure_account_protocol_identity", return_value=identity),
        patch.object(email_change_service, "BrowserSession", return_value=FakeSession()),
        patch.object(email_change_service, "authenticated_bootstrap"),
        patch.object(email_change_service, "run_recent_login", return_value="fresh-at-secret") as reauth,
        patch.object(email_change_service.email_provider, "wait_for_otp", return_value="654321"),
        patch.object(email_change_service, "ChangeEmailProtocolClient", return_value=client),
        patch.object(email_change_service.db, "update_account_email_after_change", return_value={
            "account_id": 7,
            "old_email": "old@example.com",
            "new_email": "new@example.com",
            "local_readback_confirmed": True,
        }),
        patch.object(email_change_service.live_check_service, "enqueue_account_live_check", return_value={
            "accepted": True,
            "task_id": 99,
            "source_system": "native_operations",
            "source_id": "maintenance:token_refresh:7:child",
        }) as enqueue_child,
        patch.object(email_change_service.operation_task_store, "register_task_dependency") as register_dependency,
    ):
        result = email_change_service.handle_email_change(context)

    reauth.assert_called_once()
    assert client.begin.call_count == 2
    client.verify.assert_called_once_with(context.session, "fresh-at-secret", "654321")
    enqueue_child.assert_called_once()
    register_dependency.assert_called_once()
    assert context.release_calls == 1
    assert result.status == "partial_success"
    assert "fresh-at-secret" not in repr(result.summary)
    assert "654321" not in repr(result.summary)


def test_remote_timeout_after_begin_is_request_unknown_and_never_verifies():
    from core import email_change_service

    context = _fake_context()
    client = MagicMock()
    client.begin.side_effect = TimeoutError("connection reset")
    route = SimpleNamespace(proxy_url="", provider="direct", region=None)
    with (
        patch.object(email_change_service.db, "get_account", return_value={
            "id": 7, "email": "old@example.com", "access_token": "at-secret",
        }),
        patch.object(email_change_service.db, "get_account_by_email", return_value=None),
        patch.object(email_change_service.account_proxy, "acquire_account_proxy", return_value=route),
        patch.object(email_change_service.account_auth, "ensure_account_protocol_identity", return_value=None),
        patch.object(email_change_service, "BrowserSession", return_value=FakeSession()),
        patch.object(email_change_service, "authenticated_bootstrap"),
        patch.object(email_change_service, "ChangeEmailProtocolClient", return_value=client),
    ):
        result = email_change_service.handle_email_change(context)

    assert result.status == "request_unknown"
    assert result.summary["outcome"] == "request_unknown"
    assert result.summary["reconcile_required"] is True
    client.verify.assert_not_called()
    assert context.receipts[-1]["outcome"] == "request_unknown"
    assert "at-secret" not in repr(result.summary)


def test_email_change_storage_writeback_preserves_original_material_and_clears_at():
    from core.storage import accounts
    from core.storage import db_legacy

    account = {
        "id": 7,
        "email": "old@example.com",
        "access_token": "at-secret",
        "original_email_line": "old@example.com----mail-password----client-id",
        "password": "mail-password",
        "totp_secret": "totp-secret",
    }
    with patch.object(db_legacy.record_store, "transaction") as transaction:
        transaction.return_value.__enter__.return_value = MagicMock()
        with (
            patch.object(db_legacy, "_locked_row_by_email", side_effect=[account, None, {"id": 31, "email": "new@example.com", "status": "used"}]),
            patch.object(db_legacy.record_store, "patch_row", return_value=True) as patch_row,
            patch.object(db_legacy.record_store, "get_row", return_value={
                **account,
                "email": "new@example.com",
                "access_token": None,
                "original_email_line": account["original_email_line"],
            }),
        ):
            result = accounts.update_account_email_after_change(
                account_id=7,
                expected_old_email="old@example.com",
                new_email="new@example.com",
                email_source="outlook",
            )

    assert result["local_readback_confirmed"] is True
    account_changes = patch_row.call_args_list[0].args[2]
    assert account_changes["email"] == "new@example.com"
    assert account_changes["email_source"] == "outlook"
    assert account_changes["access_token"] is None
    assert "original_email_line" not in account_changes
    assert "password" not in result
    assert "totp_secret" not in result


def test_email_change_retry_is_rejected_when_remote_result_needs_reconciliation():
    from core import email_change_service

    task = {"id": 12, "task_type": "email_change", "status": "attention_required"}
    with patch.object(email_change_service.operation_task_store, "retry_runtime_task") as retry:
        result = email_change_service.retry_email_change(task)

    assert result["accepted"] is False
    assert result["reconcile_required"] is True
    retry.assert_not_called()


def test_email_change_error_projection_is_safe_and_actionable():
    info = classify_task_error(
        "email_change_verify request_unknown: connection reset after remote submission",
        stage="email_change_verify",
        task_type="email_change",
    )

    assert info["code"] == "external.network"
    assert info["retryability"] == "retryable"
    assert info["next_action"] == "retry_request_or_reconcile"
    assert "request_unknown" in info["summary"]
    assert "Bearer" not in info["summary"]


def test_email_change_proxy_mode_is_purpose_specific():
    with patch("config.account.ACCOUNT_EMAIL_CHANGE_PROXY_MODE", "direct", create=True):
        assert account_proxy.account_action_proxy_mode("email-change") == "direct"


def test_email_change_single_and_bulk_entries_are_durable():
    from webui.routes.accounts import create_accounts_blueprint

    context = SimpleNamespace(
        enqueue_account_setup=MagicMock(),
        enqueue_account_completion=MagicMock(),
        enqueue_email_change=MagicMock(side_effect=lambda account_id, **kwargs: {
            "accepted": True, "account_id": account_id, "task_type": "email_change",
        }),
        put_prepared_download=MagicMock(),
        logger=MagicMock(),
    )
    bp = create_accounts_blueprint(context)
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(bp)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/accounts/<int:acc_id>/email-change" in rules
    assert "/api/accounts/email-change-bulk" in rules
    assert context.enqueue_email_change.called is False


def _fake_context():
    from core.operations.task_gateway import OperationResult

    class Context:
        account_id = 7
        task_id = 70
        run_id = 77
        email = "old@example.com"
        source_system = "native_operations"
        session = FakeSession()
        run = {"data": {"new_email": "new@example.com", "email_source": "outlook"}}

        def __init__(self):
            self.receipts = []
            self.reports = []
            self.release_calls = 0
            self.finished = False

        def report(self, **kwargs):
            self.reports.append(kwargs)

        def checkpoint(self, *args, **kwargs):
            return None

        def acquire_lease(self, **kwargs):
            return SimpleNamespace(released=False, token="lease")

        def release_lease(self):
            self.release_calls += 1
            return True

        def remote_request_started(self, *args, **kwargs):
            return {"id": len(self.receipts) + 1}

        def remote_request_receipt(self, **kwargs):
            self.receipts.append(kwargs)
            return kwargs

        def finish(self, result=None, **kwargs):
            self.finished = True
            if result is not None:
                self.result = result
            else:
                self.result = OperationResult(
                    kwargs.get("status") or "failed",
                    kwargs.get("result_summary") or {},
                    kwargs.get("message") or "",
                )
            return {"status": self.result.status}

        @property
        def last_result(self):
            return getattr(self, "result", None)

    return Context()
