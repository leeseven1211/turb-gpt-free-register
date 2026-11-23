"""已保存密码但内核不支持续跑时，重试投影必须在入口处拒绝。"""
from __future__ import annotations

import json

from core.registration import service


def _pending_case(driver: str) -> dict:
    job = {
        "id": 11, "status": "failed", "email": "pending@example.test",
        "account_id": 21, "config_snapshot": {"registration_driver": driver},
    }
    account = {
        "id": 21, "email": "pending@example.test", "access_token": "",
        "account_status": "", "codex_status": "",
        "extra_json": json.dumps({
            "registration_checkpoint": "email_verification_pending",
            "account_password": "pending-pass",
            "account_password_state": "candidate",
        }),
    }
    attempt = {
        "id": 31, "email_snapshot": "pending@example.test", "account_id": 21,
        "checkpoint": "password_confirmed", "target_status": "not_created",
        "local_account_state": "saved", "remote_account_state": "not_started",
        "data": {"has_password": True},
    }
    return {"job": job, "account": account, "attempt": attempt}


def test_sentinel_rs_saved_password_is_not_advertised_as_resumable():
    case = _pending_case("sentinel_rs")
    info = service._build_retry_info(
        case["job"], account=case["account"], successful_retry=None,
        attempt=case["attempt"], root_job=case["job"],
    )
    assert info["retryable"] is False
    assert info["retry_action"] is None
    assert info["next_actions"] == []
    assert "Rust 内核不支持原身份续跑" in info["retry_reason"]


def test_gate_only_applies_to_the_rust_kernel():
    assert service._resume_driver_unsupported({"config_snapshot": {"registration_driver": "sentinel_rs"}})
    assert service._resume_driver_unsupported({"data": {"config_snapshot": {"registration_driver": "sentinel_rs"}}})
    assert not service._resume_driver_unsupported({"config_snapshot": {"registration_driver": "protocol_oss_2"}})
    assert not service._resume_driver_unsupported({"config_snapshot": {}})
