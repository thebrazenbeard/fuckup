"""Source-contract tests for DriftGuard's CI-result consumer boundary."""

from datetime import datetime, timedelta, timezone
import json

import pytest

from fuckup_protocol import consume_driftguard_ci_result


# The digest is fixed independently of the consumer implementation using the
# DriftGuard V1 canonical JSON rule. Regressions must not self-verify with the
# same digest helper that production uses.
_GATE = {
    "schema": "DRIFTGUARD_CI_GATE_RESULT_V1",
    "decision": "BLOCK",
    "policy_id": "agent-quality",
    "policy_digest": "1" * 64,
    "baseline_digest": "2" * 64,
    "candidate_digest": "3" * 64,
    "metrics": [
        {
            "name": "task_success",
            "status": "BLOCK",
            "severity": "block",
            "direction": "higher",
            "baseline": 0.95,
            "candidate": 0.89,
            "regression": 0.06,
            "max_regression": 0.03,
            "reasons": ["regression_0.06_exceeds_0.03"],
        }
    ],
    "reasons": ["one_or_more_blocking_metrics_failed"],
    "claim_ceiling": [
        "Deterministic comparison of supplied baseline/candidate metrics under the exact supplied policy.",
        "Does not prove evaluator correctness, benchmark representativeness, causal drift, or production impact.",
        "A PASS is admission evidence for this policy/input tuple only.",
    ],
}
_FIXED_DIGEST = "bdc5500a1a6169ef78669518ff94c646584dd9e068744b70a3ef360b1bc90eda"
_OBSERVED = datetime(2026, 10, 25, 12, 30, tzinfo=timezone(timedelta(hours=-4)))


def _json(payload=None, *, result_digest=_FIXED_DIGEST):
    value = dict(_GATE if payload is None else payload)
    value["result_digest"] = result_digest
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _consume(json_text, **overrides):
    args = {
        "event_id": "drift-observation-1",
        "source": "urn:bt2:driftguard-consumer",
        "subject": "agent/checkout-evaluator",
        "observed_at": _OBSERVED,
    }
    args.update(overrides)
    return consume_driftguard_ci_result(json_text, **args)


def _signed_json(payload):
    from hashlib import sha256

    digest = sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return _json(payload, result_digest=digest)


def _valid_gate_for_decision(decision):
    payload = json.loads(json.dumps(_GATE))
    payload["decision"] = decision
    metric = payload["metrics"][0]
    if decision == "PASS":
        metric.update(status="PASS", candidate=0.94, regression=0.01,
                      reasons=["within_policy"])
        payload["reasons"] = ["all_metrics_within_policy"]
    elif decision == "WARN":
        metric.update(status="WARN", severity="warn")
        payload["reasons"] = ["one_or_more_warning_metrics_failed"]
    elif decision == "UNKNOWN":
        metric.update(status="UNKNOWN", candidate=None, regression=None,
                      reasons=["missing_candidate_metric"])
        payload["reasons"] = ["required_metric_evidence_missing"]
    return payload


@pytest.mark.parametrize("decision", ["PASS", "WARN", "BLOCK", "UNKNOWN"])
def test_all_decisions_are_neutral_observations_without_incident_flagging(decision):
    from hashlib import sha256

    payload = _valid_gate_for_decision(decision)
    # The fixture differs by decision; use the independently specified wire
    # canonicalization in this test for each variation.
    digest = sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    event = _consume(_json(payload, result_digest=digest))
    assert event.type == "org.fuckup.admission.observed"
    assert event.id == "drift-observation-1"
    assert event.source == "urn:bt2:driftguard-consumer"
    assert event.subject == "agent/checkout-evaluator"
    assert event.time == _OBSERVED
    assert event.data["gate_result"]["decision"] == decision
    assert event.data["gate_result"]["result_digest"] == digest
    assert event.data["authority"] == "untrusted-admission-evidence"
    assert event.provenance[0].digest == f"sha256:{digest}"
    assert event.provenance[0].ref == f"driftguard:ci-result:{digest}"
    exported = event.to_cloudevent()
    assert exported["data"]["gate_result"]["decision"] == decision
    assert exported["type"] != "org.fuckup.failure.flagged"


def test_known_producer_digest_matches_independent_fixed_vector():
    event = _consume(_json())
    assert event.data["gate_result"]["result_digest"] == _FIXED_DIGEST


def test_equal_results_can_be_distinct_occurrences():
    first = _consume(_json(), event_id="occurrence-1")
    second = _consume(_json(), event_id="occurrence-2")
    assert first.id != second.id
    assert first.data["gate_result"] == second.data["gate_result"]
    assert first.provenance == second.provenance


def test_input_bytes_supported_and_serialized_result_detached():
    event = _consume(_json().encode("utf-8"))
    external = event.to_cloudevent()
    external["data"]["gate_result"]["reasons"].append("fabricated")
    assert event.to_cloudevent()["data"]["gate_result"]["reasons"] == _GATE["reasons"]


def test_nested_mutation_after_validation_cannot_rebind_provenance():
    event = _consume(_json())
    event.data["gate_result"]["decision"] = "PASS"
    event.data["gate_result"]["metrics"][0]["status"] = "PASS"
    event.data["gate_result"]["reasons"].append("fabricated")
    with pytest.raises(TypeError):
        event.data["authority"] = "trusted"
    exported = event.to_cloudevent()
    assert exported["data"]["gate_result"]["decision"] == "BLOCK"
    assert exported["data"]["gate_result"]["metrics"][0]["status"] == "BLOCK"
    assert exported["data"]["gate_result"]["reasons"] == _GATE["reasons"]
    assert exported["fuckupprovenance"][0]["digest"] == f"sha256:{_FIXED_DIGEST}"


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-32", "latin-1"])
def test_non_utf8_input_bytes_rejected(encoding):
    if encoding == "latin-1":
        # UTF-8 is a strict subset for ASCII; a non-UTF-8 byte is required.
        wire = _json().encode("ascii") + b"\xff"
    else:
        wire = _json().encode(encoding)
    with pytest.raises(ValueError):
        _consume(wire)


def test_lone_unicode_surrogate_rejected_as_value_error():
    payload = dict(_GATE, policy_id="\ud800")
    with pytest.raises(ValueError, match="invalid Unicode"):
        _consume(_json(payload))


@pytest.mark.parametrize("change", [
    lambda value: value.update(policy_id="different-policy"),
    lambda value: value["metrics"][0].update(candidate=0.99),
])
def test_tampering_without_recomputed_digest_rejected(change):
    payload = json.loads(json.dumps(_GATE))
    change(payload)
    with pytest.raises(ValueError, match="digest mismatch"):
        _consume(_json(payload))


@pytest.mark.parametrize("aggregate", ["PASS", "WARN", "UNKNOWN"])
def test_resigned_block_metric_cannot_claim_nonblocking_aggregate(aggregate):
    from hashlib import sha256

    payload = json.loads(json.dumps(_GATE))
    payload["decision"] = aggregate
    payload["reasons"] = {
        "PASS": ["all_metrics_within_policy"],
        "WARN": ["one_or_more_warning_metrics_failed"],
        "UNKNOWN": ["required_metric_evidence_missing"],
    }[aggregate]
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="aggregate decision contradicts metric"):
        _consume(_json(payload, result_digest=digest))


@pytest.mark.parametrize("change", [
    lambda payload: payload["metrics"][0].update(severity="warn"),
    lambda payload: payload["metrics"][0].update(
        status="PASS", candidate=None, regression=None,
        reasons=["within_policy"]),
])
def test_rehashed_metric_producer_contradictions_rejected(change):
    payload = json.loads(json.dumps(_GATE))
    change(payload)
    if payload["metrics"][0]["status"] == "PASS":
        payload["decision"] = "PASS"
        payload["reasons"] = ["all_metrics_within_policy"]
    with pytest.raises(ValueError, match="metric"):
        _consume(_signed_json(payload))


def test_new_producer_regression_overflow_is_unknown_observation():
    payload = json.loads(json.dumps(_GATE))
    payload["decision"] = "UNKNOWN"
    payload["reasons"] = ["one_or_more_regressions_unrepresentable"]
    payload["metrics"][0].update(
        baseline=1e308, candidate=-1e308, regression=None,
        status="UNKNOWN", reasons=["regression_unrepresentable"],
    )
    event = _consume(_signed_json(payload))
    assert event.type == "org.fuckup.admission.observed"
    assert event.data["gate_result"]["decision"] == "UNKNOWN"
    assert event.data["gate_result"]["metrics"][0]["reasons"] == ["regression_unrepresentable"]


def test_block_dominates_unrepresentable_and_unrepresentable_dominates_warn():
    block = json.loads(json.dumps(_GATE["metrics"][0]))
    block["name"] = "a_block"
    overflow = json.loads(json.dumps(_GATE["metrics"][0]))
    overflow.update(
        name="b_overflow", baseline=1e308, candidate=-1e308,
        regression=None, status="UNKNOWN", reasons=["regression_unrepresentable"],
    )
    payload = json.loads(json.dumps(_GATE))
    payload["metrics"] = [block, overflow]
    assert _consume(_signed_json(payload)).data["gate_result"]["decision"] == "BLOCK"
    payload["metrics"][0].update(status="WARN", severity="warn")
    payload["decision"] = "UNKNOWN"
    payload["reasons"] = ["one_or_more_regressions_unrepresentable"]
    assert _consume(_signed_json(payload)).data["gate_result"]["decision"] == "UNKNOWN"


def test_below_display_resolution_regression_violation_remains_flagged_by_producer():
    payload = json.loads(json.dumps(_GATE))
    payload["metrics"][0].update(
        baseline=1e100, candidate=-1e-100, regression=1e100,
        max_regression=1e100,
        reasons=["regression_exceeds_limit_below_display_resolution"],
    )
    event = _consume(_signed_json(payload))
    assert event.data["gate_result"]["metrics"][0]["reasons"] == [
        "regression_exceeds_limit_below_display_resolution"
    ]


def test_rehashed_unrepresentable_aggregate_requires_unrepresentable_metric():
    payload = json.loads(json.dumps(_GATE))
    payload["decision"] = "UNKNOWN"
    payload["reasons"] = ["one_or_more_regressions_unrepresentable"]
    with pytest.raises(ValueError, match="aggregate decision"):
        _consume(_signed_json(payload))


@pytest.mark.parametrize("digest", [
    "", "abc", "sha256:" + "a" * 64, "A" * 64, "z" * 64, "0" * 63, 42,
])
def test_malformed_result_digests_rejected(digest):
    with pytest.raises(ValueError, match="result_digest"):
        _consume(_json(result_digest=digest))


@pytest.mark.parametrize("wire", [
    '{"schema":"DRIFTGUARD_CI_GATE_RESULT_V1","schema":"DRIFTGUARD_CI_GATE_RESULT_V1"}',
    _json().replace('"policy_id": "agent-quality"', '"policy_id": "agent-quality", "policy_id": "agent-quality"'),
    _json().replace('"candidate": 0.89', '"candidate": 0.89, "candidate": 0.89'),
])
def test_duplicate_json_keys_rejected_even_when_nested(wire):
    with pytest.raises(ValueError, match="duplicate JSON key"):
        _consume(wire)


@pytest.mark.parametrize("wire", [
    "{", "[]", "null", "", _json() + "{}", _json().replace("0.89", "NaN"),
    _json().replace("0.89", "1e999"),
])
def test_malformed_or_nonfinite_json_rejected(wire):
    with pytest.raises(ValueError):
        _consume(wire)


@pytest.mark.parametrize("change", [
    lambda value: value.update(schema="DRIFTGUARD_CI_GATE_RESULT_V2"),
    lambda value: value.update(decision="ALLOW"),
    lambda value: value.update(unexpected=True),
    lambda value: value.update(metrics={}),
    lambda value: value["metrics"][0].update(status="INDETERMINATE"),
    lambda value: value["metrics"][0].update(baseline=True),
    lambda value: value["metrics"][0].update(baseline=10 ** 400),
    lambda value: value.update(policy_digest="not-a-digest"),
    lambda value: value.update(claim_ceiling=["proof of deployment"]),
])
def test_invalid_producer_shapes_rejected_even_if_digest_recomputed(change):
    from hashlib import sha256

    payload = json.loads(json.dumps(_GATE))
    change(payload)
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                   allow_nan=False).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError):
        _consume(_json(payload, result_digest=digest))


def test_timezone_naive_observation_time_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        _consume(_json(), observed_at=datetime(2026, 10, 25, 12, 30))
