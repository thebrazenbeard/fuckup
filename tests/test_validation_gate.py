import pytest

from fuckup_protocol.models import CorrectionRevision, QualificationResult, TestResult
from fuckup_protocol.policy import PromotionContext, StrictPromotionPolicy
from fuckup_protocol.validation import TestKind, ValidationReport


def _correction(revision=1, digest="abc"):
    return CorrectionRevision("corr-1", revision, digest, {"rule": "replacement"})


def _qualification(revision=1, digest="abc", fail_kind=None):
    kinds = [TestKind.MFT, TestKind.CONTRAST, TestKind.TRANSFER, TestKind.RETAIN, TestKind.ANTI_TRIGGER]
    tests = tuple(TestResult(kind=k.value, name=k.value.lower(), passed=k != fail_kind) for k in kinds)
    return QualificationResult("corr-1", revision, digest, "suite-v1", tests)


def test_exact_revision_and_required_suite_can_promote():
    correction = _correction()
    report = ValidationReport.evaluate(correction, _qualification())
    decision = StrictPromotionPolicy().evaluate(PromotionContext(
        correction=correction,
        validation=report,
        root_cause_supported=True,
        ambiguous=False,
        activation_scope="agent:demo",
        rollback_condition="revoke on regression",
    ))
    assert report.passed
    assert decision.allow


def test_changed_revision_makes_old_qualification_stale():
    correction = _correction(revision=2, digest="new")
    report = ValidationReport.evaluate(correction, _qualification(revision=1, digest="old"))
    assert not report.current
    assert not report.passed


def test_retain_failure_blocks_promotion():
    correction = _correction()
    report = ValidationReport.evaluate(correction, _qualification(fail_kind=TestKind.RETAIN))
    decision = StrictPromotionPolicy().evaluate(PromotionContext(
        correction=correction,
        validation=report,
        root_cause_supported=True,
        ambiguous=False,
        activation_scope="agent:demo",
        rollback_condition="revoke on regression",
    ))
    assert not report.passed
    assert not decision.allow


def test_validation_report_from_another_correction_is_rejected():
    correction_a = _correction(revision=1, digest="a")
    report_a = ValidationReport.evaluate(correction_a, _qualification(revision=1, digest="a"))
    correction_b = CorrectionRevision("corr-2", 1, "b", {"rule": "other"})
    decision = StrictPromotionPolicy().evaluate(PromotionContext(
        correction=correction_b,
        validation=report_a,
        root_cause_supported=True,
        ambiguous=False,
        activation_scope="agent:demo",
        rollback_condition="revoke on regression",
    ))
    assert not decision.allow
    assert any("exact correction" in reason for reason in decision.reasons)


def test_required_kinds_cannot_weaken_canonical_suite():
    correction = _correction()
    with pytest.raises(ValueError):
        ValidationReport.evaluate(correction, _qualification(), required_kinds=frozenset())


def test_unknown_test_kind_fails_closed():
    correction = _correction()
    qualification = _qualification()
    qualification = QualificationResult(
        qualification.correction_id,
        qualification.correction_revision,
        qualification.exact_subject_digest,
        qualification.suite_version,
        qualification.tests + (TestResult(kind="MYSTERY", name="unknown", passed=True),),
    )
    report = ValidationReport.evaluate(correction, qualification)
    assert not report.passed
    assert report.unknown_test_names == ("unknown",)
