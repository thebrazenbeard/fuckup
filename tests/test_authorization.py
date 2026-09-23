from fuckup_protocol.authorization import authorize_promotion
from fuckup_protocol.models import CorrectionRevision, QualificationResult, TestResult
from fuckup_protocol.validation import TestKind


def _qualification(correction, *, fail_kind=None):
    tests = tuple(
        TestResult(kind=kind.value, name=kind.value.lower(), passed=kind != fail_kind)
        for kind in [
            TestKind.MFT,
            TestKind.CONTRAST,
            TestKind.TRANSFER,
            TestKind.RETAIN,
            TestKind.ANTI_TRIGGER,
        ]
    )
    return QualificationResult(
        correction.correction_id,
        correction.revision,
        correction.subject_digest,
        "suite-v1",
        tests,
    )


def test_authorization_recomputes_validation_and_policy():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    auth = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope={"agent": "demo"},
        rollback_condition="revoke on regression",
    )
    assert auth.validation.passed
    assert auth.decision.allow
    assert dict(auth.activation_scope) == {"agent": "demo"}
    assert auth.authorization_ref is not None
    assert auth.authorization_ref.startswith("sha256:")


def test_authorization_fails_closed_on_bad_qualification():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    auth = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction, fail_kind=TestKind.RETAIN),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope={"agent": "demo"},
        rollback_condition="revoke on regression",
    )
    assert not auth.validation.passed
    assert not auth.decision.allow
    assert auth.authorization_ref is None


def test_authorization_rejects_non_selector_activation_scope():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    auth = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope={"agent": {"nested": "not-allowed"}},
        rollback_condition="revoke on regression",
    )
    assert not auth.decision.allow
    assert auth.activation_scope is None
    assert auth.authorization_ref is None
    assert any("flat selector" in reason for reason in auth.decision.reasons)


def test_authorization_ref_binds_scope_and_does_not_follow_mutation():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    scope = {"agent": "demo"}
    auth = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope=scope,
        rollback_condition="revoke on regression",
    )
    first_ref = auth.authorization_ref
    scope["agent"] = "other"

    assert dict(auth.activation_scope) == {"agent": "demo"}
    assert auth.authorization_ref == first_ref

    broader = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope={"agent": "demo", "model": "x"},
        rollback_condition="revoke on regression",
    )
    assert broader.authorization_ref != first_ref


def test_authorization_ref_binds_rollback_condition():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    left = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope={"agent": "demo"},
        rollback_condition="revoke on regression",
    )
    right = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope={"agent": "demo"},
        rollback_condition="revoke on security regression",
    )
    assert left.authorization_ref != right.authorization_ref
