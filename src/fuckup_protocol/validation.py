from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import CorrectionRevision, QualificationResult


class TestKind(StrEnum):
    __test__ = False
    MFT = "MFT"
    INV = "INV"
    DIR = "DIR"
    CONTRAST = "CONTRAST"
    TRANSFER = "TRANSFER"
    RETAIN = "RETAIN"
    ANTI_TRIGGER = "ANTI_TRIGGER"


DEFAULT_REQUIRED_KINDS = frozenset({
    TestKind.MFT,
    TestKind.CONTRAST,
    TestKind.TRANSFER,
    TestKind.RETAIN,
    TestKind.ANTI_TRIGGER,
})


@dataclass(frozen=True, slots=True)
class ValidationReport:
    correction_id: str
    correction_revision: int
    exact_subject_digest: str
    suite_version: str
    required_kinds: frozenset[TestKind]
    current: bool
    passed: bool
    missing_kinds: frozenset[TestKind]
    failed_test_names: tuple[str, ...]
    unknown_test_names: tuple[str, ...]

    def matches_correction(self, correction: CorrectionRevision) -> bool:
        return (
            self.correction_id == correction.correction_id
            and self.correction_revision == correction.revision
            and self.exact_subject_digest == correction.subject_digest
        )

    @classmethod
    def evaluate(
        cls,
        correction: CorrectionRevision,
        qualification: QualificationResult,
        required_kinds: frozenset[TestKind] = DEFAULT_REQUIRED_KINDS,
    ) -> "ValidationReport":
        required_kinds = frozenset(required_kinds)
        if not DEFAULT_REQUIRED_KINDS.issubset(required_kinds):
            missing_canonical = sorted(kind.value for kind in DEFAULT_REQUIRED_KINDS - required_kinds)
            raise ValueError(
                "required_kinds cannot weaken the canonical validation suite; "
                f"missing: {', '.join(missing_canonical)}"
            )

        current = qualification.matches(correction)
        observed: set[TestKind] = set()
        failed: list[str] = []
        unknown: list[str] = []

        for result in qualification.tests:
            try:
                kind = TestKind(result.kind)
            except ValueError:
                unknown.append(result.name)
                continue
            observed.add(kind)
            if not result.passed:
                failed.append(result.name)

        missing = frozenset(required_kinds - observed)
        passed = current and not missing and not failed and not unknown
        return cls(
            correction_id=qualification.correction_id,
            correction_revision=qualification.correction_revision,
            exact_subject_digest=qualification.exact_subject_digest,
            suite_version=qualification.suite_version,
            required_kinds=required_kinds,
            current=current,
            passed=passed,
            missing_kinds=missing,
            failed_test_names=tuple(failed),
            unknown_test_names=tuple(unknown),
        )
