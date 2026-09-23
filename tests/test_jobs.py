import pytest

from fuckup_protocol.jobs import InvalidJobTransition, JobState, JobStatus, claim, fail, recover_expired_lease, succeed


def test_retryable_failure_consumes_budget_then_dead_letters():
    job = JobState(id="j1", max_attempts=2)
    job = claim(job, "worker-a")
    job = fail(job, error="temporary", retryable=True)
    assert job.status == JobStatus.RETRY

    job = claim(job, "worker-b")
    job = fail(job, error="temporary-again", retryable=True)
    assert job.status == JobStatus.DEAD_LETTERED
    assert job.attempts == 2


def test_non_retryable_failure_dead_letters_immediately():
    job = claim(JobState(id="j1"), "worker-a")
    job = fail(job, error="invalid schema", retryable=False)
    assert job.status == JobStatus.DEAD_LETTERED


def test_success_is_terminal_for_claiming():
    job = succeed(claim(JobState(id="j1"), "worker-a"))
    assert job.status == JobStatus.COMPLETED
    with pytest.raises(InvalidJobTransition):
        claim(job, "worker-b")


def test_expired_lease_retries_until_budget_exhausted():
    job = claim(JobState(id="j1", max_attempts=1), "worker-a")
    recovered = recover_expired_lease(job)
    assert recovered.status == JobStatus.DEAD_LETTERED
