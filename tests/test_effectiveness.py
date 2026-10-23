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


def test_effectiveness_rejects_mixed_exact_correction_subjects():
    from fuckup_protocol.effectiveness import EffectivenessSubject

    first = EffectivenessSubject("corr-1", 1, "sha256:scope", None, None)
    second = EffectivenessSubject("corr-1", 2, "sha256:scope", None, None)
    observations = (
        OutcomeObservation(ObservationPhase.BASELINE, True, subject=first),
        OutcomeObservation(ObservationPhase.BASELINE, True, subject=second),
    )

    import pytest
    with pytest.raises(ValueError, match="mixed effectiveness subjects"):
        summarize_effectiveness(observations)


def test_active_effectiveness_requires_one_exact_binding():
    from fuckup_protocol.effectiveness import EffectivenessSubject

    baseline = EffectivenessSubject("corr-1", 1, "sha256:scope", None, None)
    active_a = EffectivenessSubject("corr-1", 1, "sha256:scope", "promo-1", "bind-a")
    active_b = EffectivenessSubject("corr-1", 1, "sha256:scope", "promo-1", "bind-b")
    observations = (
        OutcomeObservation(ObservationPhase.BASELINE, True, subject=baseline),
        OutcomeObservation(ObservationPhase.ACTIVE, False, subject=active_a),
        OutcomeObservation(ObservationPhase.ACTIVE, False, subject=active_b),
    )

    import pytest
    with pytest.raises(ValueError, match="mixed active bindings"):
        summarize_effectiveness(observations, minimum_active_exposures=1)


def test_effectiveness_summary_retains_exact_active_subject_identity():
    from fuckup_protocol.effectiveness import EffectivenessSubject

    baseline = EffectivenessSubject("corr-1", 1, "sha256:scope")
    active = EffectivenessSubject("corr-1", 1, "sha256:scope", "promo-1", "bind-1")
    observations = (
        OutcomeObservation(ObservationPhase.BASELINE, True, subject=baseline),
        OutcomeObservation(ObservationPhase.ACTIVE, False, subject=active),
    )
    summary = summarize_effectiveness(observations, minimum_active_exposures=1)

    assert summary.subject == active

def test_replayed_operation_cannot_multiply_independent_effectiveness_exposures():
    from fuckup_protocol.effectiveness import EffectivenessSubject
    import pytest

    baseline = EffectivenessSubject("corr-1", 1, "sha256:scope")
    active = EffectivenessSubject("corr-1", 1, "sha256:scope", "promo-1", "bind-1")
    observations = tuple(
        [OutcomeObservation(ObservationPhase.BASELINE, True, subject=baseline) for _ in range(5)]
        + [
            OutcomeObservation(
                ObservationPhase.ACTIVE, False, subject=active,
                operation_id="replayed-operation-1",
                effect_digest="sha256:same-effect",
                verification_evidence_ref="adapter:same-readback",
            )
            for _ in range(5)
        ]
    )
    with pytest.raises(ValueError, match="duplicate effectiveness operation_id"):
        summarize_effectiveness(observations)


def test_distinct_verified_operations_still_report_observational_improvement():
    from fuckup_protocol.effectiveness import EffectivenessSubject

    baseline = EffectivenessSubject("corr-1", 1, "sha256:scope")
    active = EffectivenessSubject("corr-1", 1, "sha256:scope", "promo-1", "bind-1")
    observations = tuple(
        [OutcomeObservation(ObservationPhase.BASELINE, True, subject=baseline) for _ in range(5)]
        + [
            OutcomeObservation(
                ObservationPhase.ACTIVE, False, subject=active,
                operation_id=f"distinct-operation-{i}",
                effect_digest=f"sha256:effect-{i}",
                verification_evidence_ref=f"adapter:readback-{i}",
            )
            for i in range(5)
        ]
    )
    outcome = summarize_effectiveness(observations)
    assert outcome.state == EffectivenessState.IMPROVEMENT_OBSERVED
    assert outcome.active_exposures == 5


def test_reused_operation_id_between_baseline_and_active_is_not_distinct():
    from fuckup_protocol.effectiveness import EffectivenessSubject
    import pytest

    baseline = EffectivenessSubject("corr-1", 1, "sha256:scope")
    active = EffectivenessSubject("corr-1", 1, "sha256:scope", "promo-1", "bind-1")
    observations = (
        OutcomeObservation(
            ObservationPhase.BASELINE, True, subject=baseline,
            operation_id="same-operation",
        ),
        OutcomeObservation(
            ObservationPhase.ACTIVE, False, subject=active,
            operation_id="same-operation",
        ),
    )
    with pytest.raises(ValueError, match="duplicate effectiveness operation_id"):
        summarize_effectiveness(observations, minimum_active_exposures=1)


def test_opt_in_reference_completeness_rejects_anonymous_improvement():
    from fuckup_protocol.effectiveness import EffectivenessSubject
    import pytest

    subject = EffectivenessSubject("correction", 1, "sha256:scope")
    active = EffectivenessSubject("correction", 1, "sha256:scope", "promotion", "binding")
    observations = tuple(
        [OutcomeObservation(ObservationPhase.BASELINE, True, subject=subject) for _ in range(5)]
        + [OutcomeObservation(ObservationPhase.ACTIVE, False, subject=active) for _ in range(5)]
    )
    assert summarize_effectiveness(observations).state == EffectivenessState.IMPROVEMENT_OBSERVED
    with pytest.raises(ValueError, match="reference completeness"):
        summarize_effectiveness(observations, require_reference_completeness=True)


def test_opt_in_reference_completeness_does_not_attest_evidence_truth():
    from fuckup_protocol.effectiveness import EffectivenessSubject

    baseline = EffectivenessSubject("correction", 1, "sha256:scope")
    active = EffectivenessSubject("correction", 1, "sha256:scope", "promotion", "binding")
    observations = tuple(
        [OutcomeObservation(
            ObservationPhase.BASELINE, True, subject=baseline,
            operation_id=f"baseline-{i}",
            verification_evidence_ref=f"unverified:baseline-ref-{i}",
        ) for i in range(5)]
        + [OutcomeObservation(
            ObservationPhase.ACTIVE, False, subject=active,
            operation_id=f"active-{i}",
            effect_digest=f"sha256:caller-assertion-{i}",
            verification_evidence_ref=f"unverified:caller-ref-{i}",
        ) for i in range(5)]
    )
    # The inputs *claim* references; their existence or truth is NOT checked.
    result = summarize_effectiveness(observations, require_reference_completeness=True)
    assert result.state == EffectivenessState.IMPROVEMENT_OBSERVED
    assert result.active_exposures == 5


def test_opt_in_reference_completeness_requires_every_identity_and_active_reference():
    from dataclasses import replace
    from fuckup_protocol.effectiveness import EffectivenessSubject
    import pytest

    b = EffectivenessSubject("corr", 1, "sha256:scope")
    a = EffectivenessSubject("corr", 1, "sha256:scope", "promo", "bind")
    valid = (
        OutcomeObservation(
            ObservationPhase.BASELINE, True, subject=b, operation_id="baseline",
            verification_evidence_ref="source:baseline-readback",
        ),
        OutcomeObservation(
            ObservationPhase.ACTIVE, False, subject=a, operation_id="active",
            effect_digest="sha256:effect", verification_evidence_ref="source:readback",
        ),
    )
    for incomplete in (
        (replace(valid[0], subject=None), valid[1]),
        (replace(valid[0], operation_id=None), valid[1]),
        (replace(valid[0], verification_evidence_ref=None), valid[1]),
        (valid[0], replace(valid[1], effect_digest=None)),
        (valid[0], replace(valid[1], verification_evidence_ref="")),
    ):
        with pytest.raises(ValueError, match="reference completeness"):
            summarize_effectiveness(
                incomplete, minimum_active_exposures=1,
                require_reference_completeness=True,
            )



def test_opt_in_must_not_accept_unverified_baseline_outcomes():
    from fuckup_protocol.effectiveness import EffectivenessSubject
    import pytest

    baseline = EffectivenessSubject("corr", 1, "scope")
    active = EffectivenessSubject("corr", 1, "scope", "promotion", "binding")
    observations = tuple(
        OutcomeObservation(
            ObservationPhase.BASELINE, True, subject=baseline,
            operation_id=f"baseline-{i}",
        ) for i in range(5)
    ) + tuple(
        OutcomeObservation(
            ObservationPhase.ACTIVE, False, subject=active,
            operation_id=f"active-{i}",
            effect_digest=f"fictional:effect-{i}",
            verification_evidence_ref=f"fictional:active-readback-{i}",
        ) for i in range(5)
    )
    # The legacy descriptive path still reports the supplied arithmetic.
    assert summarize_effectiveness(observations).state == EffectivenessState.IMPROVEMENT_OBSERVED
    # Opt-in evidence hygiene requires references for BOTH comparison arms.
    with pytest.raises(ValueError, match="reference completeness"):
        summarize_effectiveness(observations, require_reference_completeness=True)
