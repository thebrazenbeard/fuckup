from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class CorrectionRevision:
    correction_id: str
    revision: int
    subject_digest: str
    payload: Mapping[str, Any]
    reversible: bool = True

    def __post_init__(self) -> None:
        if not self.correction_id:
            raise ValueError("correction_id is required")
        if self.revision < 1:
            raise ValueError("revision must be >= 1")
        if not self.subject_digest:
            raise ValueError("subject_digest is required")


@dataclass(frozen=True, slots=True)
class TestResult:
    __test__ = False
    kind: str
    name: str
    passed: bool
    evidence_ref: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class QualificationResult:
    correction_id: str
    correction_revision: int
    exact_subject_digest: str
    suite_version: str
    tests: tuple[TestResult, ...] = field(default_factory=tuple)

    def matches(self, correction: CorrectionRevision) -> bool:
        return (
            self.correction_id == correction.correction_id
            and self.correction_revision == correction.revision
            and self.exact_subject_digest == correction.subject_digest
        )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allow: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    required_actions: tuple[str, ...] = field(default_factory=tuple)
