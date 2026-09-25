from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_deep_freeze(item) for item in value)
    return value


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
        object.__setattr__(self, "payload", _deep_freeze(self.payload))


@dataclass(frozen=True, slots=True)
class TestResult:
    __test__ = False
    kind: str
    name: str
    passed: bool
    evidence_ref: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("test kind is required")
        if not self.name:
            raise ValueError("test name is required")


@dataclass(frozen=True, slots=True)
class QualificationResult:
    correction_id: str
    correction_revision: int
    exact_subject_digest: str
    suite_version: str
    tests: tuple[TestResult, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.correction_id:
            raise ValueError("correction_id is required")
        if self.correction_revision < 1:
            raise ValueError("correction_revision must be >= 1")
        if not self.exact_subject_digest:
            raise ValueError("exact_subject_digest is required")
        if not self.suite_version:
            raise ValueError("suite_version is required")
        object.__setattr__(self, "tests", tuple(self.tests))

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

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))
        object.__setattr__(self, "required_actions", tuple(self.required_actions))
