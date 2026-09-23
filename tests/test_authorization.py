import pytest

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


def test_authorization_recomputes_validation_policy_and_binds_effect_scope():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    auth = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope={"agent": "demo"},
        rollback_condition={"signal": "regression"},
    )
    assert auth.validation.passed
    assert auth.decision.allow
    assert dict(auth.activation_scope or {}) == {"agent": "demo"}
    assert dict(auth.rollback_condition or {}) == {"signal": "regression"}
    with pytest.raises(TypeError):
        auth.activation_scope["agent"] = "other"  # type: ignore[index]


def test_authorization_fails_closed_on_bad_qualification():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    auth = authorize_promotion(
        correction=correction,
        qualification=_qualification(correction, fail_kind=TestKind.RETAIN),
        root_cause_supported=True,
        ambiguous=False,
        activation_scope={"agent": "demo"},
        rollback_condition={"signal": "regression"},
    )
    assert not auth.validation.passed
    assert not auth.decision.allow


def test_authorization_rejects_blank_scope_value():
    correction = CorrectionRevision("c1", 1, "sha256:a", {"rule": "x"})
    with pytest.raises(ValueError):
        authorize_promotion(
            correction=correction,
            qualification=_qualification(correction),
            root_cause_supported=True,
            ambiguous=False,
            activation_scope={"agent": ""},
            rollback_condition={"signal": "regression"},
        )


def test_direct_authorization_construction_is_rejected():
    from fuckup_protocol.authorization import PromotionAuthorization
    from fuckup_protocol.models import PolicyDecision
    from fuckup_protocol.validation import ValidationReport, DEFAULT_REQUIRED_KINDS

    report = ValidationReport(
        correction_id="c1",
        correction_revision=1,
        exact_subject_digest="sha256:a",
        suite_version="suite-v1",
        required_kinds=DEFAULT_REQUIRED_KINDS,
        current=True,
        passed=True,
        missing_kinds=frozenset(),
        failed_test_names=(),
        unknown_test_names=(),
    )
    with pytest.raises(ValueError, match="issued by authorize_promotion"):
        PromotionAuthorization(
            validation=report,
            decision=PolicyDecision(allow=True),
            activation_scope={"agent": "demo"},
            rollback_condition={"signal": "regression"},
        )
