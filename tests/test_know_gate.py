"""Adversarial structural tests; these do not verify source authenticity."""
from dataclasses import replace

from fuckup_protocol.know_gate import (
    ClaimKind, ClaimProposal, EvidenceKind, EvidenceRef, GateState,
    assess_know_claim,
)


S = "sha256:exact-incident"
O = "sha256:other-incident"
ALONE = EvidenceRef("user-1", S, EvidenceKind.USER_REPORT, "participants", "one")


def claim(kind=ClaimKind.REPORTED_FACT, **kwargs):
    args = dict(subject_digest=S, statement="Reported speaking while alone",
                kind=kind, support_refs=("user-1",), fact_key="participants",
                fact_value="one")
    args.update(kwargs)
    return ClaimProposal(**args)


def test_report_preserves_user_attribution_not_causal_truth():
    report = assess_know_claim(claim(), (ALONE,))
    assert report.state is GateState.PROVENANCE_BOUND
    assert not report.review_ready


def test_invented_conversational_partner_fails_closed():
    invented = claim(statement="Another person took part in the conversation",
                     fact_value="multiple")
    result = assess_know_claim(invented, (ALONE,))
    assert result.state is GateState.BLOCKED
    assert "fact_not_supported_or_conflicts" in result.reasons


def test_missing_source_and_wrong_subject_fail():
    assert "unknown_evidence_ref" in assess_know_claim(
        claim(support_refs=("invented",)), (ALONE,)
    ).reasons
    assert "stale_or_unrelated_subject" in assess_know_claim(
        claim(), (replace(ALONE, subject_digest=O),)
    ).reasons


def test_model_review_is_not_direct_observation():
    evidence = replace(ALONE, kind=EvidenceKind.MODEL_REVIEW)
    result = assess_know_claim(claim(kind=ClaimKind.OBSERVED_FACT), (evidence,))
    assert "missing_observation_provenance" in result.reasons


def test_bare_root_cause_assertion_cannot_be_known():
    root = claim(kind=ClaimKind.ROOT_CAUSE, fact_key=None, fact_value=None)
    result = assess_know_claim(root, (ALONE,))
    assert result.state is GateState.BLOCKED
    assert "missing_falsifier" in result.reasons
    assert "missing_competing_explanation" in result.reasons
    assert "missing_falsification_attempt" in result.reasons


def test_model_agreement_does_not_count_as_causal_test():
    model = EvidenceRef("review-1", S, EvidenceKind.MODEL_REVIEW)
    root = claim(kind=ClaimKind.ROOT_CAUSE, fact_key=None, fact_value=None,
                 support_refs=("review-1",), falsifier="If counterexample occurs",
                 falsification_refs=("review-1",), alternatives=("attention error",))
    result = assess_know_claim(root, (model,))
    assert "no_test_or_probe_support" in result.reasons
    assert "no_test_or_probe_falsification" in result.reasons


def test_structurally_complete_causes_only_ready_for_review():
    test = EvidenceRef("probe-1", S, EvidenceKind.REAL_SYSTEM_PROBE)
    falsify = EvidenceRef("test-2", S, EvidenceKind.TEST)
    root = claim(kind=ClaimKind.ROOT_CAUSE, fact_key=None, fact_value=None,
                 support_refs=("probe-1",), falsifier="Repeat with other inputs",
                 falsification_refs=("test-2",), alternatives=("source error",))
    result = assess_know_claim(root, (test, falsify))
    assert result.state is GateState.REVIEW_READY
    assert result.review_ready
    assert not hasattr(result, "root_cause_verified")


def test_duplicate_and_cross_incident_falsification_fail():
    test = EvidenceRef("probe-1", S, EvidenceKind.TEST)
    other = EvidenceRef("test-2", O, EvidenceKind.TEST)
    root = claim(kind=ClaimKind.ROOT_CAUSE, fact_key=None, fact_value=None,
                 support_refs=("probe-1", "probe-1"), falsifier="A",
                 falsification_refs=("test-2",), alternatives=("B",))
    result = assess_know_claim(root, (test, other))
    assert result.state is GateState.BLOCKED
    assert "duplicate_support" in result.reasons
    assert "stale_or_unrelated_subject" in result.reasons


def test_wrong_claim_type_cannot_be_silently_coerced():
    try:
        claim(kind="ROOT_CAUSE")
    except ValueError:
        pass
    else:
        assert False, "unknown kind must be rejected"



def test_inconsistent_supporting_fact_values_are_blocked():
    contradiction = EvidenceRef("report-2", S, EvidenceKind.USER_REPORT,
                                "participants", "multiple")
    result = assess_know_claim(
        claim(support_refs=("user-1", "report-2")), (ALONE, contradiction)
    )
    assert result.state is GateState.BLOCKED
    assert "conflicting_fact_evidence" in result.reasons


def test_same_proof_cannot_double_as_falsification_attempt():
    proof = EvidenceRef("probe-1", S, EvidenceKind.TEST)
    root = claim(kind=ClaimKind.ROOT_CAUSE, fact_key=None, fact_value=None,
                 support_refs=("probe-1",), falsifier="Repeat with altered input",
                 falsification_refs=("probe-1",), alternatives=("Other explanation",))
    result = assess_know_claim(root, (proof,))
    assert result.state is GateState.BLOCKED
    assert "support_falsification_overlap" in result.reasons
