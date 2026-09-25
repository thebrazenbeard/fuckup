from fuckup_protocol.experiment import ExperimentOutcome, factorial_conditions


def test_factorial_design_crosses_all_declared_factors():
    conditions = factorial_conditions()
    assert len(conditions) == 3 * 2 * 4 * 2
    assert len({condition.id for condition in conditions}) == len(conditions)


def test_durable_success_requires_transfer_and_retain_without_new_error():
    outcome = ExperimentOutcome(
        condition_id="c001",
        model_id="model-a",
        task_id="task-1",
        initial_correct=False,
        correction_applied=True,
        exact_recurrence_passed=True,
        near_transfer_passed=True,
        far_transfer_passed=False,
        retain_passed=True,
        anti_trigger_passed=True,
        schema_valid=True,
        introduced_error=False,
    )
    assert outcome.durable_correction_success


def test_retain_regression_prevents_success():
    outcome = ExperimentOutcome(
        condition_id="c001",
        model_id="model-a",
        task_id="task-1",
        initial_correct=False,
        correction_applied=True,
        exact_recurrence_passed=True,
        near_transfer_passed=True,
        far_transfer_passed=True,
        retain_passed=False,
        anti_trigger_passed=True,
        schema_valid=True,
        introduced_error=False,
    )
    assert not outcome.durable_correction_success
