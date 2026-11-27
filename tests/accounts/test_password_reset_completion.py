"""协议改密确认后的凭据写回与业务核验契约。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.accounts.password_setup import reset_completion
from core.kernels.protocol.local.plan_check import parse_accounts_check


EMAIL = "reset@example.test"
TOKEN = "fresh-token"
SESSION = {
    "accessToken": TOKEN,
    "user": {"id": "user-1", "email": EMAIL},
    "account": {"id": "acct-1", "planType": "free"},
}
ACCOUNT = {
    "id": 7,
    "email": EMAIL,
    "user_id": "user-1",
    "chatgpt_account_id": "acct-1",
}
OWNER = {
    "account_id": 7,
    "operation_run_id": 11,
    "operation_execution_id": "execution-1",
    "operation_lease_token": "lease-1",
}


def _checkpoint():
    return SimpleNamespace(recovery_id=91, state="confirmed", version=1)


def _completed_checkpoint():
    return SimpleNamespace(recovery_id=91, state="confirmed", version=2, completion_pending=False)


def _private_cache():
    return {
        "cookies": [{"name": "__Secure-next-auth.session-token", "value": "cookie-value"}],
        "device_id": "device-1",
        "browser_profile": {"screen_width": 1440},
        "user_id": "user-1",
        "chatgpt_account_id": "acct-1",
    }


def test_validate_password_session_rejects_session_token_mismatch():
    auth = {"ok": True, "access_token": TOKEN, "session": {**SESSION, "accessToken": "other-token"}}

    with pytest.raises(reset_completion.ResetCompletionError) as caught:
        reset_completion.validate_password_session(ACCOUNT, EMAIL, auth)

    assert caught.value.stage == "password_authentication"
    assert caught.value.cause_code == "session_token_mismatch"


def test_complete_password_reset_writes_readbacks_and_business_checks_without_secrets():
    auth = {
        "ok": True,
        "access_token": TOKEN,
        "session": SESSION,
        "auth_method": "password_mfa",
        "password_auth_status": "verified",
        "_protocol_session": object(),
    }
    stored_account = {
        **ACCOUNT,
        "access_token": TOKEN,
        "chatgpt_session": SESSION,
        "live_check_ok": True,
    }
    with (
        patch.object(reset_completion, "save_manual_password_change_session") as save_credentials,
        patch.object(
            reset_completion,
            "complete_manual_password_change",
            return_value=SimpleNamespace(recovery_id=91, state="confirmed"),
        ) as complete_credentials,
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(
            reset_completion,
            "check_account_plan",
            return_value={"ok": True, "account_id": "acct-1", "response_account_id": "acct-1"},
        ) as business_check,
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=SESSION),
    ):
        result = reset_completion.complete_password_reset(
            recovery=_checkpoint(),
            owner=OWNER,
            account=ACCOUNT,
            email=EMAIL,
            auth=auth,
            proxy="fixture-proxy",
        )

    assert result["ok"] is True
    assert result["status"] == "success"
    assert result["password_confirmed"] is True
    assert result["credential_writeback"] == "confirmed"
    assert result["business_verification"] == "confirmed"
    assert TOKEN not in str(result)
    save_credentials.assert_called_once()
    assert save_credentials.call_args.args == (91,)
    assert save_credentials.call_args.kwargs["access_token"] == TOKEN
    assert save_credentials.call_args.kwargs["session_info"] == SESSION
    assert save_credentials.call_args.kwargs["protocol_session"] is auth["_protocol_session"]
    assert "verified_password" not in save_credentials.call_args.kwargs
    complete_credentials.assert_called_once_with(
        91, expected_version=1, access_token=TOKEN, **OWNER,
    )
    business_check.assert_called_once_with(
        TOKEN, proxy="fixture-proxy", session=None,
    )


def test_complete_password_reset_keeps_confirmed_fact_when_business_check_fails():
    auth = {"ok": True, "access_token": TOKEN, "session": SESSION}
    stored_account = {**ACCOUNT, "access_token": TOKEN, "chatgpt_session": SESSION}

    with (
        patch.object(reset_completion, "save_manual_password_change_session"),
        patch.object(reset_completion, "complete_manual_password_change") as complete_credentials,
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=SESSION),
        patch.object(
            reset_completion,
            "check_account_plan",
            return_value={"ok": False, "http_status": 401, "error": "token_revoked"},
        ),
    ):
        result = reset_completion.complete_password_reset(
            recovery=_checkpoint(),
            owner=OWNER,
            account=ACCOUNT,
            email=EMAIL,
            auth=auth,
        )

    assert result["ok"] is False
    assert result["password_confirmed"] is True
    assert result["stage"] == "business_verification"
    assert result["cause_code"] == "token_revoked"
    assert result["retryable"] is False
    complete_credentials.assert_not_called()


@pytest.mark.parametrize(
    ("business", "cause_code", "error_category"),
    [
        (
            {
                "ok": False,
                "http_status": 401,
                "error": "AT已过期/失效，请手动查活刷新",
                "response_preview": '{"error":{"code":"token_revoked"}}',
            },
            "token_revoked",
            "auth",
        ),
        (
            {"ok": False, "http_status": 403, "error": "HTTP 403"},
            "http_403",
            "security",
        ),
        (
            {"ok": False, "http_status": 200, "error": "响应不是 JSON 对象"},
            "response_invalid",
            "response",
        ),
    ],
)
def test_business_failure_uses_safe_http_and_preview_classification(
    business, cause_code, error_category
):
    auth = {"ok": True, "access_token": TOKEN, "session": SESSION}
    stored_account = {**ACCOUNT, "access_token": TOKEN}

    with (
        patch.object(reset_completion, "save_manual_password_change_session"),
        patch.object(reset_completion, "complete_manual_password_change"),
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=SESSION),
        patch.object(reset_completion, "check_account_plan", return_value=business),
    ):
        result = reset_completion.complete_password_reset(
            recovery=_checkpoint(),
            owner=OWNER,
            account=ACCOUNT,
            email=EMAIL,
            auth=auth,
        )

    assert result["cause_code"] == cause_code
    assert result["error_category"] == error_category
    assert "AT已过期" not in result["message"]
    assert "response_preview" not in str(result)


def test_completed_checkpoint_rerun_only_reads_and_verifies():
    auth = {"ok": True, "access_token": TOKEN, "session": SESSION}
    stored_account = {**ACCOUNT, "access_token": TOKEN}

    with (
        patch.object(reset_completion, "save_manual_password_change_session") as save_credentials,
        patch.object(reset_completion, "complete_manual_password_change") as complete_credentials,
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=SESSION),
        patch.object(
            reset_completion,
            "check_account_plan",
            return_value={"ok": True, "account_id": "acct-1", "response_account_id": "acct-1"},
        ),
    ):
        result = reset_completion.complete_password_reset(
            recovery=_completed_checkpoint(),
            owner=OWNER,
            account=ACCOUNT,
            email=EMAIL,
            auth=auth,
        )

    assert result["ok"] is True
    save_credentials.assert_not_called()
    complete_credentials.assert_not_called()


def test_verify_completed_password_reset_is_read_only():
    auth = {"ok": True, "access_token": TOKEN, "session": SESSION}
    stored_account = {**ACCOUNT, "access_token": TOKEN}

    with (
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=SESSION),
        patch.object(
            reset_completion,
            "check_account_plan",
            return_value={"ok": True, "account_id": "acct-1", "response_account_id": "acct-1"},
        ),
    ):
        result = reset_completion.verify_completed_password_reset(
            account=ACCOUNT,
            email=EMAIL,
            auth=auth,
        )

    assert result["ok"] is True
    assert result["completion_pending"] is False
    assert result["completed_recheck"] is True
    assert result["mutation_submitted"] is False
    assert result["action_dispatched"] is False


def test_verify_completed_password_reset_without_auth_reads_saved_credentials():
    stored_account = {**ACCOUNT, "access_token": TOKEN}

    with (
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=SESSION),
        patch.object(
            reset_completion,
            "check_account_plan",
            return_value={"ok": True, "account_id": "acct-1", "response_account_id": "acct-1"},
        ),
    ):
        result = reset_completion.verify_completed_password_reset(
            account=ACCOUNT,
            email=EMAIL,
            auth=None,
        )

    assert result["ok"] is True
    assert result["completion_pending"] is False
    assert result["completed_recheck"] is True


def test_verify_completed_password_reset_session_readback_error_keeps_completed_fact():
    stored_account = {**ACCOUNT, "access_token": TOKEN}

    with (
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(
            reset_completion.db,
            "get_account_chatgpt_session",
            side_effect=RuntimeError("session store unavailable"),
        ),
    ):
        result = reset_completion.verify_completed_password_reset(
            account=ACCOUNT,
            email=EMAIL,
            auth=None,
        )

    assert result["ok"] is False
    assert result["stage"] == "credential_readback"
    assert result["cause_code"] == "credential_readback_failed"
    assert result["completion_pending"] is False
    assert result["completed_recheck"] is True
    assert result["mutation_submitted"] is False
    assert result["action_dispatched"] is False


def test_business_success_without_real_identity_does_not_confirm_completion():
    auth = {
        "ok": True,
        "access_token": TOKEN,
        "session": {**SESSION, "account": {}},
    }
    account = {key: value for key, value in ACCOUNT.items() if key != "chatgpt_account_id"}
    stored_account = {**account, "access_token": TOKEN}

    with (
        patch.object(reset_completion, "save_manual_password_change_session"),
        patch.object(reset_completion, "complete_manual_password_change") as complete_credentials,
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=auth["session"]),
        patch.object(reset_completion, "token_claims", return_value={}),
        patch.object(reset_completion, "check_account_plan", return_value={"ok": True, "account_id": "default"}),
    ):
        result = reset_completion.complete_password_reset(
            recovery=_checkpoint(),
            owner=OWNER,
            account=account,
            email=EMAIL,
            auth=auth,
        )

    assert result["ok"] is False
    assert result["cause_code"] == "business_identity_missing"
    complete_credentials.assert_not_called()


def test_private_session_readback_requires_nextauth_session_cookie():
    auth = {"ok": True, "access_token": TOKEN, "session": SESSION}
    stored_account = {**ACCOUNT, "access_token": TOKEN}
    invalid_cache = {**_private_cache(), "cookies": [{"name": "oai-did", "value": "only-device"}]}

    with (
        patch.object(reset_completion, "save_manual_password_change_session"),
        patch.object(reset_completion, "complete_manual_password_change") as complete_credentials,
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=invalid_cache),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=SESSION),
    ):
        result = reset_completion.complete_password_reset(
            recovery=_checkpoint(),
            owner=OWNER,
            account=ACCOUNT,
            email=EMAIL,
            auth=auth,
        )

    assert result["ok"] is False
    assert result["stage"] == "private_session_readback"
    complete_credentials.assert_not_called()


def test_completion_uses_response_account_id_instead_of_jwt_overwritten_account_id():
    auth = {"ok": True, "access_token": TOKEN, "session": SESSION}
    stored_account = {**ACCOUNT, "access_token": TOKEN}

    with (
        patch.object(reset_completion, "save_manual_password_change_session"),
        patch.object(reset_completion, "complete_manual_password_change") as complete_credentials,
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=SESSION),
        patch.object(
            reset_completion,
            "check_account_plan",
            return_value={"ok": True, "account_id": "jwt-account", "response_account_id": "acct-1"},
        ),
    ):
        result = reset_completion.complete_password_reset(
            recovery=_checkpoint(),
            owner=OWNER,
            account=ACCOUNT,
            email=EMAIL,
            auth=auth,
        )

    assert result["ok"] is True
    complete_credentials.assert_called_once()


def test_parse_accounts_check_preserves_response_identity_when_claims_override_account_id():
    payload = {
        "accounts": {
            "acct-1": {
                "account": {"account_id": "acct-1", "plan_type": "free"},
                "entitlement": {},
                "eligible_promo_campaigns": [],
                "eligible_offers": {"offers": []},
                "features": [],
            }
        }
    }
    result = parse_accounts_check(
        payload,
        token="fixture-token",
        token_claims=lambda _token: {"account_id": "jwt-account"},
    )

    assert result["account_id"] == "jwt-account"
    assert result["response_account_id"] == "acct-1"


def test_parse_accounts_check_does_not_treat_default_as_response_identity():
    payload = {
        "accounts": {
            "default": {
                "account": {},
                "entitlement": {},
                "eligible_promo_campaigns": [],
                "eligible_offers": {"offers": []},
                "features": [],
            }
        }
    }
    result = parse_accounts_check(payload, token="")

    assert result["account_id"] == "default"
    assert result["response_account_id"] == ""


@pytest.mark.parametrize("entry", ["complete", "verify"])
@pytest.mark.parametrize("failure", ["authentication", "readback", "business"])
def test_completed_rerun_failures_never_reopen_completion_pending(entry, failure):
    auth = {"ok": True, "access_token": TOKEN, "session": SESSION}
    if failure == "authentication":
        auth = {"ok": False, "error": "password_rejected"}
    stored_account = {**ACCOUNT, "access_token": TOKEN}
    save_credentials = Mock()
    complete_credentials = Mock()
    saved_session = SESSION if failure != "readback" else None
    business = (
        {"ok": True, "account_id": "jwt-account", "response_account_id": "acct-1"}
        if failure != "business"
        else {"ok": False, "http_status": 401, "error": "token_revoked"}
    )

    with (
        patch.object(reset_completion, "save_manual_password_change_session", save_credentials),
        patch.object(reset_completion, "complete_manual_password_change", complete_credentials),
        patch.object(reset_completion.protocol_sessions, "load_session", return_value=_private_cache()),
        patch.object(reset_completion.db, "get_account", return_value=stored_account),
        patch.object(reset_completion.db, "get_account_chatgpt_session", return_value=saved_session),
        patch.object(reset_completion, "check_account_plan", return_value=business),
    ):
        if entry == "complete":
            result = reset_completion.complete_password_reset(
                recovery=_completed_checkpoint(),
                owner=OWNER,
                account=ACCOUNT,
                email=EMAIL,
                auth=auth,
            )
        else:
            result = reset_completion.verify_completed_password_reset(
                account=ACCOUNT,
                email=EMAIL,
                auth=auth,
            )

    assert result["ok"] is False
    assert result["completion_pending"] is False
    assert result["completed_recheck"] is True
    assert result["password_reset"] == "confirmed"
    save_credentials.assert_not_called()
    complete_credentials.assert_not_called()
