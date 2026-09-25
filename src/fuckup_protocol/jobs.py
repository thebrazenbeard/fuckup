from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRY = "RETRY"
    COMPLETED = "COMPLETED"
    DEAD_LETTERED = "DEAD_LETTERED"


@dataclass(frozen=True, slots=True)
class JobState:
    id: str
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 5
    locked_by: str | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        if self.attempts < 0:
            raise ValueError("attempts must be >= 0")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        if self.attempts > self.max_attempts:
            raise ValueError("attempts cannot exceed max_attempts")


class InvalidJobTransition(ValueError):
    pass


def claim(job: JobState, worker_id: str) -> JobState:
    if job.status not in {JobStatus.PENDING, JobStatus.RETRY}:
        raise InvalidJobTransition(f"cannot claim job in state {job.status}")
    if job.attempts >= job.max_attempts:
        raise InvalidJobTransition("retry budget exhausted")
    if not worker_id:
        raise ValueError("worker_id is required")
    return replace(job, status=JobStatus.RUNNING, attempts=job.attempts + 1, locked_by=worker_id)


def succeed(job: JobState) -> JobState:
    if job.status != JobStatus.RUNNING:
        raise InvalidJobTransition(f"cannot complete job in state {job.status}")
    return replace(job, status=JobStatus.COMPLETED, locked_by=None, last_error=None)


def fail(job: JobState, *, error: str, retryable: bool) -> JobState:
    if job.status != JobStatus.RUNNING:
        raise InvalidJobTransition(f"cannot fail job in state {job.status}")
    if not retryable or job.attempts >= job.max_attempts:
        return replace(job, status=JobStatus.DEAD_LETTERED, locked_by=None, last_error=error)
    return replace(job, status=JobStatus.RETRY, locked_by=None, last_error=error)


def recover_expired_lease(job: JobState, *, error: str = "worker lease expired") -> JobState:
    if job.status != JobStatus.RUNNING:
        raise InvalidJobTransition(f"cannot recover lease in state {job.status}")
    if job.attempts >= job.max_attempts:
        return replace(job, status=JobStatus.DEAD_LETTERED, locked_by=None, last_error=error)
    return replace(job, status=JobStatus.RETRY, locked_by=None, last_error=error)
