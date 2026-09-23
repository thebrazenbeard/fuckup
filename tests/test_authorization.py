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
        activation_scope="agent:demo",
        rollback_condition="revoke on regression",
    )
    assert auth.validation.passed
    assert auth.decision.allow


def test_authorization_fails_closed_on_bad_qualification():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    auth = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction, fail_kind=TestKind.RETAIN),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope="agent:demo",
        rollback_condition="revoke on regression",
    )
    assert not auth.validation.passed
    assert not auth.decision.allow
