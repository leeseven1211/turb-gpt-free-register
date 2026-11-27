"""Team 输入边界的无副作用校验。"""
from __future__ import annotations

import pytest

from core.teams.errors import TeamError
from core.teams.validation import idempotency_key, local_id, validate_payload, validate_query


def test_ids_never_accept_lossy_numeric_input_or_noncanonical_strings():
    assert local_id("9007199254740993", "account_id") == "9007199254740993"
    for value in (1, True, 1.0, None, "0", "-1", " 1", "1 ", "01", "١",
                  "9223372036854775808", "9" * 300):
        with pytest.raises(TeamError) as caught:
            local_id(value, "account_id")
        assert caught.value.code == "parameter_invalid"
        assert caught.value.field == "account_id"


@pytest.mark.parametrize("value", ["1", "999999999999999999", "9223372036854775806", "9223372036854775807"])
def test_local_id_accepts_every_supported_decimal_length_without_integer_coercion(value):
    assert local_id(value, "account_id") == value


@pytest.mark.parametrize("value", [
    "", "00", "01", "+1", "1.0", "1e3", "\n1", "1\n", "١", "１",
    "9223372036854775808", "9999999999999999999", "10000000000000000000", "0" * 10000,
])
def test_local_id_decimal_fast_path_keeps_exact_bigint_and_ascii_boundaries(value):
    with pytest.raises(TeamError) as caught:
        local_id(value, "account_id")
    assert caught.value.code == "parameter_invalid" and caught.value.field == "account_id"


def test_explicit_target_duplicates_and_email_snapshot_survive_for_correct_receipt_counts():
    body = {
        "account_ids": ["101", "101", "102"],
        "expected_emails": {"101": " first@example.test ", "102": "second@example.test"},
    }
    value = validate_payload("join", body)
    assert value == {
        "account_ids": ["101", "101", "102"],
        "expected_emails": {"101": "first@example.test", "102": "second@example.test"},
    }
    assert body["expected_emails"]["101"] == " first@example.test "


def test_resolve_rejects_ids_outside_storage_range_before_query():
    with pytest.raises(TeamError) as caught:
        validate_payload("resolve", {"values": ["9223372036854775808"]})
    assert caught.value.code == "parameter_invalid"
    assert caught.value.status == 422


def test_clearing_editable_fields_is_distinct_from_missing_and_zero():
    assert validate_payload("update", {
        "expected_revision": 2, "display_name": " \t ", "planned_member_limit": None,
    }) == {"expected_revision": 2, "display_name": None, "planned_member_limit": None}
    assert validate_payload("update", {
        "expected_revision": 2, "manager_account_id": "101", "probe_id": "21", "probe_revision": 3,
    }) == {"expected_revision": 2, "manager_account_id": "101", "probe_id": "21", "probe_revision": 3}
    with pytest.raises(TeamError):
        validate_payload("update", {"expected_revision": 2, "planned_member_limit": 0})


def test_read_posts_reject_idempotency_field_and_unpublished_join_options():
    for kind, body in (
        ("preview", {"account_ids": ["1"], "idempotency_key": "team-read-request-0001"}),
        ("resolve", {"values": ["101"], "idempotency_key": "team-read-request-0001"}),
        ("join", {"account_ids": ["1"], "role": "admin"}),
        ("join", {"account_ids": ["1"], "merge_personal_data": True}),
    ):
        with pytest.raises(TeamError) as caught:
            validate_payload(kind, body)
        assert caught.value.code == "field_not_supported"


def test_resolve_only_accepts_email_or_positive_decimal_account_id_after_trim():
    assert validate_payload("resolve", {"values": [" 101 ", "member@example.test"]}) == {
        "values": ["101", "member@example.test"],
    }
    for value in ("not-an-email", "0", "-1", "1.5", "member @example.test"):
        with pytest.raises(TeamError) as caught:
            validate_payload("resolve", {"values": [value]})
        assert caught.value.field == "values"


def test_all_target_array_limits_apply_before_service_acceptance():
    for kind, field, maximum in (
        ("join", "account_ids", 10_000), ("sync_bulk", "team_ids", 100),
        ("invitation_bulk", "invitation_ids", 10_000), ("resolve", "values", 10_000),
    ):
        accepted = {field: ["1"] * maximum}
        assert len(validate_payload(kind, accepted)[field]) == maximum
        with pytest.raises(TeamError) as caught:
            validate_payload(kind, {field: ["1"] * (maximum + 1)})
        assert caught.value.field == field and caught.value.status == 422


def test_opaque_workspace_id_is_not_converted_to_local_id():
    assert validate_payload("probe", {
        "manager_account_id": "101", "target_workspace_id": "workspace:personal-or-team",
    }) == {"manager_account_id": "101", "target_workspace_id": "workspace:personal-or-team"}
    assert validate_payload("probe", {"manager_account_id": "101"}) == {"manager_account_id": "101"}


def test_both_key_sources_are_trimmed_and_must_be_nonempty_when_present():
    assert idempotency_key(" team-write-request-0001 ", {
        "idempotency_key": "team-write-request-0001",
    }) == "team-write-request-0001"
    for body in ({"idempotency_key": None}, {"idempotency_key": ""}, {"idempotency_key": False}):
        with pytest.raises(TeamError) as caught:
            idempotency_key("team-write-request-0001", body)
        assert caught.value.code == "idempotency_key_invalid"


def test_list_normalization_defaults_do_not_invent_filter_scopes():
    assert validate_query("teams", {}) == {"page": 1, "page_size": 20, "include_facets": False}
    assert validate_query("invitations", {"execution_status": ["waiting"], "q": [" test "]}) == {
        "execution_status": "waiting", "q": "test", "page": 1, "page_size": 20, "include_facets": False,
    }
    assert validate_query("join_items", {"acceptance_status": "reused", "include_facets": "1"}) == {
        "acceptance_status": "reused", "include_facets": True, "page": 1, "page_size": 20,
    }
