"""协议改密 P1 回执在账号配置组合层的传播契约。"""
from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.accounts import operation_results, setup_execution
from core.operations import task_gateway


EMAIL = "p1-receipt@example.test"


def _private_session() -> dict:
    return {
        "cookies": [{"name": "session", "value": "cookie"}],
        "user_id": "user-1",
        "chatgpt_account_id": "account-1",
    }


def _account() -> dict:
    return {
        "id": 7,
        "email": EMAIL,
        "access_token": "fresh-at",
        "extra_json": {
            "account_password": "candidate-password",
            "account_password_state": "confirmed",
        },
    }


def _password_result(**overrides) -> dict:
    value = {
        "ok": True,
        "status": "success",
        "password_reset": "confirmed",
        "password_confirmed": True,
        "credentials_saved": True,
        "business_verified": True,
        "completion_pending": False,
    }
    value.update(overrides)
    return value


def _setup_result(password: dict) -> dict:
    return {
        "ok": bool(password.get("ok")),
        "status": password.get("status"),
        "password_driver": "protocol",
        "step_results": {"password": password},
        "password_setup": dict(password),
    }


def test_p1_success_requires_complete_credentials_and_business_evidence():
    result = _setup_result(_password_result())
    with (
        patch.object(operation_results.db, "get_account", return_value=_account()),
        patch.object(
            operation_results.db,
            "get_account_chatgpt_session",
            return_value={"accessToken": "fresh-at", "user": {"id": "user-1"}},
        ),
        patch(
            "core.storage.accounts.protocol_sessions.load_session",
            return_value=_private_session(),
        ),
    ):
        state, detail = operation_results.account_setup_receipt(
            7, EMAIL, {"password"}, result,
        )

    assert state == "confirmed"
    assert detail["local_readback_checks"] == {
        "password": True,
        "access_token": True,
        "session": True,
        "protocol_session": True,
        "credentials_saved": True,
        "business_verified": True,
    }
    normalized = operation_results.safe_operation_result(result)
    assert normalized.status == "success"
    assert normalized.summary["password_reset"] == "confirmed"
    assert normalized.summary["completion_pending"] is False


def test_p1_success_without_private_session_or_business_evidence_cannot_be_reported_success():
    result = _setup_result(_password_result(business_verified=False))
    with (
        patch.object(operation_results.db, "get_account", return_value=_account()),
        patch.object(operation_results.db, "get_account_chatgpt_session", return_value=None),
        patch("core.storage.accounts.protocol_sessions.load_session", return_value=None),
    ):
        state, detail = operation_results.account_setup_receipt(
            7, EMAIL, {"password"}, result,
        )

    assert state == "local_commit_required"
    assert detail["local_readback_checks"]["session"] is False
    assert detail["local_readback_checks"]["protocol_session"] is False
    assert detail["local_readback_checks"]["business_verified"] is False


def test_p1_confirmed_completion_failure_keeps_password_receipt_and_specific_cause():
    result = _setup_result(_password_result(
        ok=False,
        status="failed",
        credentials_saved=False,
        business_verified=False,
        completion_pending=True,
        stage="business_verification",
        cause_code="token_revoked",
        retryable=False,
    ))

    state, detail = operation_results.account_setup_receipt(
        7, EMAIL, {"password"}, result,
    )

    assert state == "local_commit_required"
    assert detail["password_reset"] == "confirmed"
    assert detail["password_confirmed"] is True
    assert detail["completion_pending"] is True
    assert detail["remote_password_confirmed"] is True
    assert detail["stage"] == "business_verification"
    assert detail["cause_code"] == "token_revoked"

    normalized = operation_results.safe_operation_result(result)
    assert normalized.status == "failed"
    assert normalized.error == "token_revoked"
    assert normalized.summary["cause_code"] == "token_revoked"
    assert normalized.summary["completion_pending"] is True


def test_setup_execution_does_not_rewrite_confirmed_p1_failure_as_request_unknown():
    context = SimpleNamespace(
        account_id=7,
        email=EMAIL,
        task_id=701,
        run_id=702,
        task_type="password_change",
        run={"data": {"steps": ["password"]}, "trigger": "manual_account_password_change"},
        config_snapshot={},
        execution_fence={"run_id": 702, "execution_id": "worker", "lease_token": "lease"},
        finished=False,
        last_result=None,
        report=Mock(),
        lease=Mock(return_value=nullcontext()),
        remote_request_started=Mock(),
        remote_request_receipt=Mock(),
    )

    result = _setup_result(_password_result(
        ok=False,
        status="failed",
        credentials_saved=False,
        business_verified=False,
        completion_pending=True,
        stage="business_verification",
        cause_code="token_revoked",
        retryable=False,
    ))
    worker = Mock(return_value=result)

    def finish(value):
        context.finished = True
        context.last_result = value
        return value

    context.finish = finish

    with (
        patch.object(
            setup_execution.operation_settings,
            "completion_settings_from_snapshot",
            return_value={
                "password_driver": "protocol",
                "twofa_driver": "auto",
                "plan_check_driver": "protocol",
            },
        ),
        patch("core.runtime.capabilities.account_setup_unavailable", return_value=None),
        patch("core.accounts.completion.active_registration_job", return_value=None),
        patch.object(setup_execution.codex_retry_service, "run_twofa_worker", worker),
        patch.object(operation_results.db, "get_account", return_value=_account()),
    ):
        normalized = setup_execution.handle_native_account_setup(context)

    assert normalized.status == "failed"
    assert normalized.status != "request_unknown"
    assert normalized.error == "token_revoked"
    assert normalized.summary["password_reset"] == "confirmed"
    assert normalized.summary["completion_pending"] is True
    assert context.remote_request_receipt.call_args.kwargs["outcome"] == "local_commit_required"
