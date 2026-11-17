"""当前请求事实优先于历史里程碑，并只保存固定的端点类别。"""
import json

import pytest

from core.operations.errors import (
    registration_diagnostic_cause_code,
    safe_registration_diagnostics,
)


@pytest.mark.parametrize("facts,expected", [
    ({"operation": "session", "failure_kind": "http_error", "http_status": 401},
     "protocol_auth_http_failed"),
    ({"operation": "session", "failure_kind": "transport_error", "exception_type": "ProxyError"},
     "protocol_post_otp_transport_failed"),
    ({"operation": "session", "failure_kind": "missing_session"},
     "protocol_session_incomplete"),
    ({"operation": "other", "failure_kind": "transport_error", "request_host_class": "auth",
      "request_path_class": "unmapped", "request_method": "GET"},
     "protocol_unmapped_request_transport_failed"),
])
def test_current_failure_remains_specific_after_profile_confirmation(facts, expected):
    diagnostics = dict(facts, profile_confirmed=True, otp_received=True)
    assert registration_diagnostic_cause_code(diagnostics) == expected


def test_safe_endpoint_categories_survive_and_private_values_are_rejected():
    facts = {"request_method": "GET", "request_host_class": "auth", "request_path_class": "preauth"}
    assert safe_registration_diagnostics(facts) == facts
    private = {key: "https://private.example.test/?code=fixture-private" for key in facts}
    cleaned = safe_registration_diagnostics(private)
    assert cleaned == {}
    assert "fixture-private" not in json.dumps(cleaned)


def test_unmapped_external_service_does_not_become_registration_transport_cause():
    assert registration_diagnostic_cause_code({
        "operation": "other", "failure_kind": "transport_error", "request_host_class": "other",
        "request_path_class": "unmapped", "request_method": "GET",
    }) == "protocol_failure_evidence_missing"
