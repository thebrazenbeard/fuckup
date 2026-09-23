from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ObservationPhase(StrEnum):
    BASELINE = "BASELINE"
    ACTIVE = "ACTIVE"


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    phase: ObservationPhase
    failure_occurred: bool
    correction_triggered: bool = False
    prevented: bool = False
    regression: bool = False


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


def summarize_effectiveness(
    observations: tuple[OutcomeObservation, ...],
    *,
    minimum_active_exposures: int = 5,
) -> EffectivenessSummary:
    if minimum_active_exposures < 1:
        raise ValueError("minimum_active_exposures must be >= 1")

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
    )
