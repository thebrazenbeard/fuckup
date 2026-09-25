from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ObservationPhase(StrEnum):
    BASELINE = "BASELINE"
    ACTIVE = "ACTIVE"


@dataclass(frozen=True, slots=True)
class EffectivenessSubject:
    correction_id: str
    correction_revision: int
    scope_digest: str
    promotion_id: str | None = None
    binding_id: str | None = None

    def __post_init__(self) -> None:
        if not self.correction_id:
            raise ValueError("correction_id is required")
        if self.correction_revision < 1:
            raise ValueError("correction_revision must be >= 1")
        if not self.scope_digest:
            raise ValueError("scope_digest is required")


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    phase: ObservationPhase
    failure_occurred: bool
    correction_triggered: bool = False
    prevented: bool = False
    regression: bool = False
    subject: EffectivenessSubject | None = None


class EffectivenessState(StrEnum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    IMPROVEMENT_OBSERVED = "IMPROVEMENT_OBSERVED"
    NO_IMPROVEMENT = "NO_IMPROVEMENT"
    REGRESSION_OBSERVED = "REGRESSION_OBSERVED"


@dataclass(frozen=True, slots=True)
class EffectivenessSummary:
    state: EffectivenessState
    baseline_exposures: int
    baseline_failures: int
    active_exposures: int
    active_failures: int
    prevented_attempts: int
    regressions: int
    baseline_failure_rate: float | None
    active_failure_rate: float | None
    subject: EffectivenessSubject | None = None


def _validate_subjects(
    observations: tuple[OutcomeObservation, ...],
) -> EffectivenessSubject | None:
    if not observations:
        return None

    bound = tuple(item.subject is not None for item in observations)
    if any(bound) and not all(bound):
        raise ValueError("cannot mix bound and unbound effectiveness observations")
    if not any(bound):
        return None

    subjects = tuple(item.subject for item in observations if item.subject is not None)
    exact_subjects = {
        (subject.correction_id, subject.correction_revision, subject.scope_digest)
        for subject in subjects
    }
    if len(exact_subjects) != 1:
        raise ValueError("mixed effectiveness subjects")

    active_subjects = tuple(
        item.subject
        for item in observations
        if item.phase == ObservationPhase.ACTIVE and item.subject is not None
    )
    if active_subjects:
        if any(not subject.promotion_id or not subject.binding_id for subject in active_subjects):
            raise ValueError("active effectiveness observations require promotion and binding identity")
        active_bindings = {
            (subject.promotion_id, subject.binding_id)
            for subject in active_subjects
        }
        if len(active_bindings) != 1:
            raise ValueError("mixed active bindings")
        return active_subjects[0]

    return subjects[0]


def summarize_effectiveness(
    observations: tuple[OutcomeObservation, ...],
    *,
    minimum_active_exposures: int = 5,
) -> EffectivenessSummary:
    if minimum_active_exposures < 1:
        raise ValueError("minimum_active_exposures must be >= 1")

    subject = _validate_subjects(observations)
    baseline = [item for item in observations if item.phase == ObservationPhase.BASELINE]
    active = [item for item in observations if item.phase == ObservationPhase.ACTIVE]

    baseline_failures = sum(item.failure_occurred for item in baseline)
    active_failures = sum(item.failure_occurred for item in active)
    prevented = sum(item.prevented for item in active)
    regressions = sum(item.regression for item in active)

    baseline_rate = baseline_failures / len(baseline) if baseline else None
    active_rate = active_failures / len(active) if active else None

    if regressions:
        state = EffectivenessState.REGRESSION_OBSERVED
    elif not baseline or len(active) < minimum_active_exposures:
        state = EffectivenessState.INSUFFICIENT_EVIDENCE
    elif active_rate is not None and baseline_rate is not None and active_rate < baseline_rate:
        state = EffectivenessState.IMPROVEMENT_OBSERVED
    else:
        state = EffectivenessState.NO_IMPROVEMENT

    return EffectivenessSummary(
        state=state,
        baseline_exposures=len(baseline),
        baseline_failures=baseline_failures,
        active_exposures=len(active),
        active_failures=active_failures,
        prevented_attempts=prevented,
        regressions=regressions,
        baseline_failure_rate=baseline_rate,
        active_failure_rate=active_rate,
        subject=subject,
    )