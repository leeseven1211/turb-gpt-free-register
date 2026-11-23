"""Rust 失败任务的续跑入口：允许跨内核，由协议内核继续邮箱验证。"""
from __future__ import annotations

import json

from core.registration import service


def _pending_case(driver: str) -> dict:
    job = {
        "id": 11, "status": "failed", "email": "pending@example.test",
        "account_id": 21, "attempt_id": 31,
        "config_snapshot": {"registration_driver": driver},
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
        "source_root_job_id": 11, "checkpoint": "otp_started",
        "target_status": "not_created", "local_account_state": "none",
        "remote_account_state": "not_started",
        "data": {"has_password": True},
    }
    return {"job": job, "account": account, "attempt": attempt}


def test_sentinel_rs_saved_password_is_resumable_through_the_protocol_kernel():
    case = _pending_case("sentinel_rs")
    info = service._build_retry_info(
        case["job"], account=case["account"], successful_retry=None,
        attempt=case["attempt"], root_job=case["job"],
    )
    assert info["retryable"] is True
    assert info["retry_action"] == "registration_resume"
    assert info["retry_label"] == "继续注册（协议内核）"
    assert "协议内核" in info["retry_reason"]


def test_identity_verification_required_blocks_retry():
    job = {
        "id": 12, "status": "failed", "email": "idv@example.test",
        "error_message": "request_unknown: registration_identity_verification_required: 资料已接受，OpenAI 仍要求身份验证",
    }
    info = service._build_retry_info(
        job, account=None, successful_retry=None, attempt=None, root_job=job,
    )
    assert info["retryable"] is False
    assert "身份验证" in info["retry_reason"]


def test_protocol_failures_resume_with_their_own_kernel():
    case = _pending_case("protocol_oss_2")
    info = service._build_retry_info(
        case["job"], account=case["account"], successful_retry=None,
        attempt=case["attempt"], root_job=case["job"],
    )
    assert info["retryable"] is True
    assert info["retry_action"] == "registration_resume"
    assert info["retry_label"] == "继续邮箱验证"
    assert "协议内核" not in info["retry_reason"]


def test_resume_driver_detection_only_targets_the_rust_kernel():
    assert service._resume_driver_unsupported({"config_snapshot": {"registration_driver": "sentinel_rs"}})
    assert service._resume_driver_unsupported({"data": {"config_snapshot": {"registration_driver": "sentinel_rs"}}})
    assert not service._resume_driver_unsupported({"config_snapshot": {"registration_driver": "protocol_oss_2"}})
    assert not service._resume_driver_unsupported({"config_snapshot": {}})
