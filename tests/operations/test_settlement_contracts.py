"""Offline regressions for the execution-local settlement request boundary."""
from dataclasses import FrozenInstanceError
import json

import pytest

from core.operations.settlement_contracts import (
    SettlementDomain, same_intent, seal_intent, thaw,
)


ORIGIN = {"permit_id": "p1", "execution_id": "e1", "run_id": 7, "run_uuid": "r7"}


def test_nested_result_and_obligations_cannot_change_after_sealing():
    summary = {"steps": [{"state": "done"}]}
    obligations = [{"kind": "marker_clear", "reference": {"run_id": 7}}]
    intent = seal_intent(kind="terminal", origin=ORIGIN,
                         payload={"status": "success", "summary": summary},
                         obligations=obligations, transition_id="t1")
    summary["steps"][0]["state"] = "changed"
    obligations[0]["reference"]["run_id"] = 99
    assert thaw(intent.payload)["summary"]["steps"][0]["state"] == "done"
    assert thaw(intent.obligations)[0]["reference"]["run_id"] == 7
    with pytest.raises(TypeError):
        intent.payload["status"] = "failed"
    with pytest.raises(FrozenInstanceError):
        intent.kind = "defer"
    exported = thaw(intent.payload)
    exported["summary"]["steps"].clear()
    assert thaw(intent.payload)["summary"]["steps"] == [{"state": "done"}]


def test_digest_is_canonical_and_checks_transition_identity_and_obligations():
    first = seal_intent(kind="defer", origin=ORIGIN,
                        payload={"delay": 1, "result": {"b": 2, "a": 1}},
                        transition_id="t1")
    reordered = seal_intent(kind="defer", origin=dict(reversed(list(ORIGIN.items()))),
                            payload={"result": {"a": 1, "b": 2}, "delay": 1},
                            transition_id="t1")
    assert first.request_digest == reordered.request_digest
    assert same_intent(first, reordered)
    other = seal_intent(kind="defer", origin=ORIGIN, payload=thaw(first.payload),
                        transition_id="t2")
    assert not same_intent(first, other)
    obligation = seal_intent(kind="defer", origin=ORIGIN,
                            payload=thaw(first.payload),
                            obligations=[{"kind": "marker_clear"}], transition_id="t1")
    assert first.request_digest != obligation.request_digest
    json.dumps(thaw(first.payload), allow_nan=False)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), object(), {1: "bad"}, {"bad": {1, 2}}])
def test_non_json_values_are_rejected_before_any_submission(bad):
    with pytest.raises((TypeError, ValueError)):
        seal_intent(kind="terminal", origin=ORIGIN, payload={"value": bad})


def test_domain_and_intent_representations_do_not_print_connection_or_payload():
    domain = SettlementDomain("postgres://user:secret@host/db", "ops", "permits", "d1")
    intent = seal_intent(kind="terminal", origin={**ORIGIN, "database_url": domain.database_url},
                         payload={"private": "result-secret"})
    assert "secret" not in repr(domain)
    assert "secret" not in repr(intent)
