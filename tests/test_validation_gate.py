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
