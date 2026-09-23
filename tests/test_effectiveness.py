from fuckup_protocol.effectiveness import (
    EffectivenessState,
    ObservationPhase,
    OutcomeObservation,
    summarize_effectiveness,
)


def test_storage_without_observation_is_not_learning_evidence():
    summary = summarize_effectiveness(())
    assert summary.state == EffectivenessState.INSUFFICIENT_EVIDENCE


def test_improvement_requires_baseline_and_enough_active_observations():
    observations = tuple(
        [OutcomeObservation(ObservationPhase.BASELINE, True) for _ in range(5)]
        + [OutcomeObservation(ObservationPhase.ACTIVE, False, correction_triggered=True) for _ in range(5)]
    )
    summary = summarize_effectiveness(observations)
    assert summary.state == EffectivenessState.IMPROVEMENT_OBSERVED
    assert summary.baseline_failure_rate == 1.0
    assert summary.active_failure_rate == 0.0


def test_regression_dominates_apparent_improvement():
    observations = tuple(
        [OutcomeObservation(ObservationPhase.BASELINE, True) for _ in range(5)]
        + [OutcomeObservation(ObservationPhase.ACTIVE, False) for _ in range(4)]
        + [OutcomeObservation(ObservationPhase.ACTIVE, False, regression=True)]
    )
    summary = summarize_effectiveness(observations)
    assert summary.state == EffectivenessState.REGRESSION_OBSERVED
    assert summary.regressions == 1


def test_too_few_active_observations_remain_insufficient():
    observations = (
        OutcomeObservation(ObservationPhase.BASELINE, True),
        OutcomeObservation(ObservationPhase.ACTIVE, False),
    )
    summary = summarize_effectiveness(observations, minimum_active_exposures=2)
    assert summary.state == EffectivenessState.INSUFFICIENT_EVIDENCE


def test_no_rate_improvement_is_not_reported_as_success():
    observations = tuple(
        [OutcomeObservation(ObservationPhase.BASELINE, True) for _ in range(5)]
        + [OutcomeObservation(ObservationPhase.ACTIVE, True) for _ in range(5)]
    )
    summary = summarize_effectiveness(observations)
    assert summary.state == EffectivenessState.NO_IMPROVEMENT
