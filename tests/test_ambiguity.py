import pytest

from fuckup_protocol.ambiguity import (
    AmbiguityRoute,
    CausalHypothesis,
    assess_ambiguity,
    route_ambiguity,
)


def test_no_hypothesis_is_explicitly_ambiguous():
    assessment = assess_ambiguity(())
    assert assessment.ambiguous
    assert assessment.top is None
    assert route_ambiguity(assessment) == AmbiguityRoute.COLLECT_EVIDENCE


def test_low_support_cannot_proceed_even_when_uncontested():
    assessment = assess_ambiguity((CausalHypothesis("h1", "maybe", 0.55),))
    assert assessment.ambiguous
    assert route_ambiguity(assessment) == AmbiguityRoute.COLLECT_EVIDENCE


def test_close_competing_hypotheses_remain_ambiguous():
    assessment = assess_ambiguity((
        CausalHypothesis("h1", "cause one", 0.82),
        CausalHypothesis("h2", "cause two", 0.76),
    ))
    assert assessment.ambiguous
    assert assessment.decision_margin == pytest.approx(0.06)


def test_supported_separated_hypothesis_can_proceed():
    assessment = assess_ambiguity((
        CausalHypothesis("h1", "cause one", 0.91),
        CausalHypothesis("h2", "cause two", 0.50),
    ))
    assert not assessment.ambiguous
    assert assessment.top.id == "h1"
    assert route_ambiguity(assessment) == AmbiguityRoute.PROCEED_TO_CORRECTION


def test_missing_evidence_can_route_to_human_review_by_policy():
    assessment = assess_ambiguity(
        (CausalHypothesis("h1", "cause one", 0.60),),
        missing_evidence=("trace-span-42",),
    )
    assert route_ambiguity(assessment, human_review_when_missing_evidence=True) == AmbiguityRoute.HUMAN_REVIEW
