"""Pure, non-authoritative consumer of DriftGuard CI gate-result JSON V1.

The digest checks JSON content integrity. It cannot establish that a trusted
evaluator produced the result, or that an admission decision is an incident.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
import json
import math
import re
from typing import Any

from .events import FuckupEvent
from .provenance import ProvenanceKind, ProvenanceRef


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_RESULT_KEYS = frozenset({
    "schema", "decision", "policy_id", "policy_digest", "baseline_digest",
    "candidate_digest", "metrics", "reasons", "claim_ceiling", "result_digest",
})
_METRIC_KEYS = frozenset({
    "name", "status", "severity", "direction", "baseline", "candidate",
    "regression", "max_regression", "reasons",
})
_DECISIONS = frozenset({"PASS", "WARN", "BLOCK", "UNKNOWN"})
_CLAIM_CEILING = (
    "Deterministic comparison of supplied baseline/candidate metrics under the exact supplied policy.",
    "Does not prove evaluator correctness, benchmark representativeness, causal drift, or production impact.",
    "A PASS is admission evidence for this policy/input tuple only.",
)


@dataclass(frozen=True, slots=True)
class _JSONSnapshot(Mapping[str, Any]):
    """Keep event data immutable while returning detached structured reads.

    ``FuckupEvent.to_cloudevent()`` serializes ``dict(self.data)``. Each
    mapping read materializes from immutable JSON, so mutation of a nested
    read cannot silently change the result under a fixed provenance digest.
    """

    wire: str

    def __getitem__(self, key: str) -> Any:
        return json.loads(self.wire)[key]

    def __iter__(self) -> Iterator[str]:
        return iter(json.loads(self.wire))

    def __len__(self) -> int:
        return len(json.loads(self.wire))


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _nonfinite_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number: {value}")


def _nonempty_string(value: Any, label: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


def _digest_string(value: Any, label: str) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase 64-character SHA-256 hex digest")


def _number(value: Any, label: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if type(value) not in (float, int):
        raise ValueError(f"{label} must be a finite JSON number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{label} must be a finite JSON number")


def _reasons(value: Any, label: str) -> None:
    if type(value) is not list or not value:
        raise ValueError(f"{label} must be a nonempty list")
    for reason in value:
        _nonempty_string(reason, label + " entry")


def _validate_result(value: Any) -> dict[str, Any]:
    if type(value) is not dict or value.keys() != _RESULT_KEYS:
        raise ValueError("DriftGuard V1 result must have exactly the producer fields")
    if value["schema"] != "DRIFTGUARD_CI_GATE_RESULT_V1":
        raise ValueError("unsupported DriftGuard result schema")
    if type(value["decision"]) is not str or value["decision"] not in _DECISIONS:
        raise ValueError("unknown DriftGuard decision")
    _nonempty_string(value["policy_id"], "policy_id")
    for field in ("policy_digest", "baseline_digest", "candidate_digest", "result_digest"):
        _digest_string(value[field], field)
    _reasons(value["reasons"], "result reasons")
    if value["claim_ceiling"] != list(_CLAIM_CEILING):
        raise ValueError("DriftGuard V1 claim_ceiling does not match the producer contract")

    metrics = value["metrics"]
    if type(metrics) is not list:
        raise ValueError("DriftGuard metrics must be an array")
    metric_names: list[str] = []
    metric_statuses: list[str] = []
    unrepresentable_regressions = False
    missing_metrics = False
    for metric in metrics:
        if type(metric) is not dict or metric.keys() != _METRIC_KEYS:
            raise ValueError("DriftGuard metric must have exactly the producer fields")
        _nonempty_string(metric["name"], "metric name")
        if type(metric["status"]) is not str or metric["status"] not in _DECISIONS:
            raise ValueError("unknown DriftGuard metric status")
        if metric["severity"] not in ("block", "warn"):
            raise ValueError("unknown DriftGuard metric severity")
        if metric["direction"] not in ("higher", "lower"):
            raise ValueError("unknown DriftGuard metric direction")
        for field in ("baseline", "candidate", "regression"):
            _number(metric[field], f"metric {field}", nullable=True)
        _number(metric["max_regression"], "metric max_regression")
        if metric["max_regression"] < 0:
            raise ValueError("metric max_regression cannot be negative")
        _reasons(metric["reasons"], "metric reasons")
        missing = [field for field in ("baseline", "candidate") if metric[field] is None]
        if missing:
            expected = "missing_" + "_and_".join(missing) + "_metric"
            if (metric["status"] != "UNKNOWN" or metric["regression"] is not None
                    or metric["reasons"] != [expected]):
                raise ValueError("missing DriftGuard metric evidence contradicts metric status")
            missing_metrics = True
        elif metric["status"] == "UNKNOWN":
            if (metric["regression"] is not None
                    or metric["reasons"] != ["regression_unrepresentable"]):
                raise ValueError("unknown DriftGuard metric must identify unrepresentable regression")
            unrepresentable_regressions = True
        else:
            if metric["regression"] is None:
                raise ValueError("complete DriftGuard metric requires regression")
            if metric["status"] == "PASS":
                if metric["reasons"] != ["within_policy"]:
                    raise ValueError("passing DriftGuard metric requires within_policy")
            elif metric["status"] == "BLOCK":
                if metric["severity"] != "block" or metric["reasons"] == ["within_policy"]:
                    raise ValueError("blocking DriftGuard metric requires blocking severity and violation")
            elif metric["status"] == "WARN":
                if metric["severity"] != "warn" or metric["reasons"] == ["within_policy"]:
                    raise ValueError("warning DriftGuard metric requires warning severity and violation")
        metric_names.append(metric["name"])
        metric_statuses.append(metric["status"])
    if metric_names != sorted(set(metric_names)):
        raise ValueError("metric names must be unique and sorted")

    # These branches mirror the producer's aggregate status precedence. They
    # catch internally impossible assertions even if an adversary re-hashes
    # altered JSON (which an unkeyed digest alone cannot prevent).
    decision, reasons = value["decision"], value["reasons"]
    if not metrics:
        consistent = decision == "UNKNOWN" and reasons == ["baseline_candidate_subject_mismatch"]
    elif "BLOCK" in metric_statuses:
        consistent = decision == "BLOCK" and reasons == ["one_or_more_blocking_metrics_failed"]
    elif unrepresentable_regressions:
        consistent = decision == "UNKNOWN" and reasons == ["one_or_more_regressions_unrepresentable"]
    elif missing_metrics:
        if decision == "UNKNOWN":
            consistent = reasons == ["required_metric_evidence_missing"]
        elif decision == "WARN":
            expected = []
            if "WARN" in metric_statuses:
                expected.append("one_or_more_warning_metrics_failed")
            expected.append("metric_evidence_missing_but_policy_warns")
            consistent = reasons == expected
        else:
            consistent = False
    elif "WARN" in metric_statuses:
        consistent = decision == "WARN" and reasons == ["one_or_more_warning_metrics_failed"]
    else:
        consistent = decision == "PASS" and reasons == ["all_metrics_within_policy"]
    if not consistent:
        raise ValueError("DriftGuard aggregate decision contradicts metric evidence")

    supplied = value["result_digest"]
    payload = {key: item for key, item in value.items() if key != "result_digest"}
    try:
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("DriftGuard JSON contains invalid Unicode") from exc
    calculated = sha256(canonical).hexdigest()
    if not compare_digest(calculated, supplied):
        raise ValueError("DriftGuard result_digest mismatch")
    return value


def consume_driftguard_ci_result(
    json_text: str | bytes,
    *,
    event_id: str,
    source: str,
    subject: str,
    observed_at: datetime,
) -> FuckupEvent:
    """Validate wire JSON and build a neutral observation, without any effect.

    All four decisions produce ``org.fuckup.admission.observed``. A separate
    caller policy must decide whether any observation represents an incident.
    Distinct occurrences require distinct caller-provided ``event_id`` values.
    ``result_digest`` binds result *content*, not its origin or authority.
    """
    if not isinstance(json_text, str | bytes):
        raise ValueError("DriftGuard result must be JSON text or UTF-8 bytes")
    if isinstance(json_text, bytes):
        try:
            json_text = json_text.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("DriftGuard result bytes must use UTF-8") from exc
    try:
        raw = json.loads(
            json_text,
            object_pairs_hook=_unique_keys,
            parse_constant=_nonfinite_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid DriftGuard JSON") from exc
    result = _validate_result(raw)
    digest = result["result_digest"]
    return FuckupEvent(
        id=event_id,
        source=source,
        type="org.fuckup.admission.observed",
        subject=subject,
        time=observed_at,
        data=_JSONSnapshot(json.dumps({
            "authority": "untrusted-admission-evidence",
            "gate_result": result,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)),
        provenance=(
            ProvenanceRef(
                kind=ProvenanceKind.EVENT,
                ref=f"driftguard:ci-result:{digest}",
                digest=f"sha256:{digest}",
                media_type="application/json",
                source="driftguard:ci",
            ),
        ),
    )
