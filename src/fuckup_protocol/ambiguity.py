from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class CausalHypothesis:
    id: str
    proposition: str
    support: float
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    counterevidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("hypothesis id is required")
        if not self.proposition:
            raise ValueError("hypothesis proposition is required")
        if not 0 <= self.support <= 1:
            raise ValueError("support must be between 0 and 1")


class AmbiguityRoute(StrEnum):
    PROCEED_TO_CORRECTION = "PROCEED_TO_CORRECTION"
    COLLECT_EVIDENCE = "COLLECT_EVIDENCE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class AmbiguityAssessment:
    ranked: tuple[CausalHypothesis, ...]
    ambiguous: bool
    reason: str | None
    decision_margin: float | None
    missing_evidence: tuple[str, ...]

    @property
    def top(self) -> CausalHypothesis | None:
        return self.ranked[0] if self.ranked else None


def assess_ambiguity(
    hypotheses: tuple[CausalHypothesis, ...],
    *,
    minimum_support: float = 0.70,
    minimum_margin: float = 0.15,
    missing_evidence: tuple[str, ...] = (),
) -> AmbiguityAssessment:
    if not 0 <= minimum_support <= 1:
        raise ValueError("minimum_support must be between 0 and 1")
    if not 0 <= minimum_margin <= 1:
        raise ValueError("minimum_margin must be between 0 and 1")

    ranked = tuple(sorted(hypotheses, key=lambda item: (-item.support, item.id)))
    if not ranked:
        return AmbiguityAssessment(
            ranked=(),
            ambiguous=True,
            reason="no causal hypothesis is available",
            decision_margin=None,
            missing_evidence=missing_evidence,
        )

    top = ranked[0]
    if top.support < minimum_support:
        return AmbiguityAssessment(
            ranked=ranked,
            ambiguous=True,
            reason="top hypothesis is below minimum support",
            decision_margin=None if len(ranked) == 1 else top.support - ranked[1].support,
            missing_evidence=missing_evidence,
        )

    if len(ranked) > 1:
        margin = top.support - ranked[1].support
        if margin < minimum_margin:
            return AmbiguityAssessment(
                ranked=ranked,
                ambiguous=True,
                reason="competing hypotheses are too close to resolve safely",
                decision_margin=margin,
                missing_evidence=missing_evidence,
            )
    else:
        margin = None

    return AmbiguityAssessment(
        ranked=ranked,
        ambiguous=False,
        reason=None,
        decision_margin=margin,
        missing_evidence=missing_evidence,
    )


def route_ambiguity(
    assessment: AmbiguityAssessment,
    *,
    human_review_when_missing_evidence: bool = False,
) -> AmbiguityRoute:
    """Choose a bounded next route; this is not an authorization decision."""

    if assessment.ambiguous:
        if human_review_when_missing_evidence and assessment.missing_evidence:
            return AmbiguityRoute.HUMAN_REVIEW
        return AmbiguityRoute.COLLECT_EVIDENCE
    return AmbiguityRoute.PROCEED_TO_CORRECTION
