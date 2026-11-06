"""Fail-closed structural provenance preflight for F.U.C.K.U.P. Know claims.

This cannot verify a source's authenticity, the truth of a report, semantic
entailment, causal identification, or installation into a model/host.
It never certifies a root cause as known or authorizes correction promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceKind(StrEnum):
    USER_REPORT = "USER_REPORT"
    SOURCE_INSPECTION = "SOURCE_INSPECTION"
    REAL_SYSTEM_PROBE = "REAL_SYSTEM_PROBE"
    TEST = "TEST"
    MODEL_REVIEW = "MODEL_REVIEW"
    INFERENCE = "INFERENCE"


class ClaimKind(StrEnum):
    REPORTED_FACT = "REPORTED_FACT"
    OBSERVED_FACT = "OBSERVED_FACT"
    HYPOTHESIS = "HYPOTHESIS"
    ROOT_CAUSE = "ROOT_CAUSE"


class GateState(StrEnum):
    BLOCKED = "BLOCKED"
    PROVENANCE_BOUND = "PROVENANCE_BOUND"
    REVIEW_READY = "REVIEW_READY"


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    ref_id: str
    subject_digest: str
    kind: EvidenceKind
    fact_key: str | None = None
    fact_value: str | None = None

    def __post_init__(self) -> None:
        if not self.ref_id.strip() or not self.subject_digest.strip():
            raise ValueError("evidence ref and exact subject are required")
        if not isinstance(self.kind, EvidenceKind):
            raise ValueError("unknown evidence kind")
        if (self.fact_key is None) != (self.fact_value is None):
            raise ValueError("fact key and value must be supplied together")
        if self.fact_key is not None and (not self.fact_key.strip() or not self.fact_value.strip()):
            raise ValueError("fact key/value cannot be blank")


@dataclass(frozen=True, slots=True)
class ClaimProposal:
    subject_digest: str
    statement: str
    kind: ClaimKind
    support_refs: tuple[str, ...]
    fact_key: str | None = None
    fact_value: str | None = None
    falsifier: str | None = None
    falsification_refs: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.subject_digest.strip() or not self.statement.strip():
            raise ValueError("claim subject and statement are required")
        if not isinstance(self.kind, ClaimKind):
            raise ValueError("unknown claim kind")
        if (self.fact_key is None) != (self.fact_value is None):
            raise ValueError("claim fact key/value must be supplied together")
        if self.fact_key is not None and (not self.fact_key.strip() or not self.fact_value.strip()):
            raise ValueError("claim fact key/value cannot be blank")
        for values in (self.support_refs, self.falsification_refs, self.alternatives):
            if any(not isinstance(x, str) or not x.strip() for x in values):
                raise ValueError("references and alternatives must be nonempty strings")


@dataclass(frozen=True, slots=True)
class KnowGateReport:
    state: GateState
    reasons: tuple[str, ...]
    subject_digest: str

    @property
    def review_ready(self) -> bool:
        return self.state is GateState.REVIEW_READY


def assess_know_claim(
    claim: ClaimProposal, evidence: tuple[EvidenceRef, ...]
) -> KnowGateReport:
    """Check *structural* evidence binding, not truth or causation.

    A REVIEW_READY root-cause hypothesis still requires a trusted, independent
    causal assessment before its support can be asserted in promotion policy.
    """
    reasons: list[str] = []
    by_ref: dict[str, EvidenceRef] = {}
    for item in evidence:
        if item.ref_id in by_ref:
            reasons.append("duplicate_evidence_id")
        by_ref[item.ref_id] = item

    if not claim.support_refs:
        reasons.append("missing_support")
    if len(set(claim.support_refs)) != len(claim.support_refs):
        reasons.append("duplicate_support")
    if len(set(claim.falsification_refs)) != len(claim.falsification_refs):
        reasons.append("duplicate_falsification")
    if set(claim.support_refs) & set(claim.falsification_refs):
        reasons.append("support_falsification_overlap")

    refs: list[EvidenceRef] = []
    for ref in dict.fromkeys((*claim.support_refs, *claim.falsification_refs)):
        item = by_ref.get(ref)
        if item is None:
            reasons.append("unknown_evidence_ref")
            continue
        if item.subject_digest != claim.subject_digest:
            reasons.append("stale_or_unrelated_subject")
            continue
        refs.append(item)

    supports = [by_ref[r] for r in claim.support_refs
                if r in by_ref and by_ref[r].subject_digest == claim.subject_digest]
    if claim.fact_key is not None and any(
        item.fact_key == claim.fact_key and item.fact_value != claim.fact_value
        for item in supports
    ):
        reasons.append("conflicting_fact_evidence")
    if claim.kind in (ClaimKind.REPORTED_FACT, ClaimKind.OBSERVED_FACT):
        if claim.fact_key is None:
            reasons.append("missing_atomic_fact")
        elif not any(item.fact_key == claim.fact_key
                     and item.fact_value == claim.fact_value for item in supports):
            reasons.append("fact_not_supported_or_conflicts")
        if claim.kind is ClaimKind.REPORTED_FACT and not any(
            item.kind is EvidenceKind.USER_REPORT for item in supports
        ):
            reasons.append("missing_report_provenance")
        if claim.kind is ClaimKind.OBSERVED_FACT and not any(
            item.kind in (EvidenceKind.SOURCE_INSPECTION,
                          EvidenceKind.REAL_SYSTEM_PROBE, EvidenceKind.TEST)
            for item in supports
        ):
            reasons.append("missing_observation_provenance")
    elif claim.kind in (ClaimKind.HYPOTHESIS, ClaimKind.ROOT_CAUSE):
        if not claim.alternatives:
            reasons.append("missing_competing_explanation")
        if claim.kind is ClaimKind.ROOT_CAUSE:
            if not claim.falsifier or not claim.falsifier.strip():
                reasons.append("missing_falsifier")
            if not claim.falsification_refs:
                reasons.append("missing_falsification_attempt")
            elif not any(
                by_ref.get(r) is not None
                and by_ref[r].subject_digest == claim.subject_digest
                and by_ref[r].kind in (EvidenceKind.TEST, EvidenceKind.REAL_SYSTEM_PROBE)
                for r in claim.falsification_refs
            ):
                reasons.append("no_test_or_probe_falsification")
            if not any(
                item.kind in (EvidenceKind.TEST, EvidenceKind.REAL_SYSTEM_PROBE)
                for item in supports
            ):
                reasons.append("no_test_or_probe_support")

    if reasons:
        return KnowGateReport(GateState.BLOCKED, tuple(dict.fromkeys(reasons)),
                              claim.subject_digest)
    state = (GateState.REVIEW_READY if claim.kind is ClaimKind.ROOT_CAUSE
             else GateState.PROVENANCE_BOUND)
    return KnowGateReport(state, (), claim.subject_digest)
