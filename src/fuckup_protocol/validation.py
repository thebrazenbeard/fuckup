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
    current: bool
    passed: bool
    missing_kinds: frozenset[TestKind]
    failed_test_names: tuple[str, ...]

    @classmethod
    def evaluate(
        cls,
        correction: CorrectionRevision,
        qualification: QualificationResult,
        required_kinds: frozenset[TestKind] = DEFAULT_REQUIRED_KINDS,
    ) -> "ValidationReport":
        current = qualification.matches(correction)
        observed: set[TestKind] = set()
        failed: list[str] = []

        for result in qualification.tests:
            try:
                kind = TestKind(result.kind)
            except ValueError:
                continue
            observed.add(kind)
            if not result.passed:
                failed.append(result.name)

        missing = frozenset(required_kinds - observed)
        passed = current and not missing and not failed
        return cls(
            current=current,
            passed=passed,
            missing_kinds=missing,
            failed_test_names=tuple(failed),
        )
